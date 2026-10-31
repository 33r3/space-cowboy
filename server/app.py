"""The game server: FastAPI on the database, answering with the same JSON
the Flask app did, so static/js works unchanged.

    uvicorn --factory server.app:create_app

Every request that touches game state first brings the world up to the
current tick (under one lock), then acts at that tick. A background task
does the same every few seconds, so the universe runs with nobody
looking.
"""
import asyncio
import math
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from generation.chunk_generator import chunks_in_bounds, generate_chunk
from generation.colony_economics import (
    ALL_RESOURCES, COLONY_SHIP_SPEED_LY_PER_TICK, MIN_DEV_TO_COLONIZE, SIZE_MULT, STARTER_STOCKPILES,
    TICK_SECONDS, apply_upgrade_dev, can_upgrade_dev, colonization_cost, colonization_range,
    consumption_per_tick, dev_name, extraction_per_tick, net_flow_per_tick, scout_range,
    size_name, upgrade_cost,
)
from generation import terraform as tf
from generation.config import DEFAULT_CONFIG
from generation.density_field import DensityField
from generation.homeworld import find_homeworld
from generation.planet_factory import generate_system
from generation.trade_routes import (
    SCOUT_COST, SHIP_CLASSES, available_ship_classes, leg_transit_ticks, validate_route,
)

from .db import make_engine, make_sessionmaker
from .galaxy import Galaxy, split_planet_id, split_star_id
from .importer import homeworld_overrides
from .models import (Colony, Event, Notification, Planet, Player, Route, RouteLeg, Ship,
                     Stockpile, TerraformProject, World)
from .ticker import advance, colony_dict, stockpiles
from .units import fixed_map, float_map, now_tick, time_of, to_fixed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKER_EVERY_S = 5
HOMEWORLD_STOCKPILES = {
    'food': 100.0, 'water': 100.0, 'minerals': 200.0, 'metals': 150.0,
    'organicFuels': 100.0, 'chemFeedstocks': 50.0, 'fusionFuel': 50.0, 'radioactives': 10.0,
}


class Game:
    """Everything a request needs: the galaxy, the database, the lock."""
    def __init__(self, sessionmaker, config=DEFAULT_CONFIG):
        self.config = config
        self.density_field = DensityField(config)
        self.galaxy = Galaxy(config, self.density_field)
        self.sessionmaker = sessionmaker
        self.lock = threading.Lock()

    def catch_up(self) -> None:
        with self.lock, self.sessionmaker() as s:
            if s.get(World, 1) is None:              # a brand-new universe starts now
                s.add(World(id=1, last_tick=now_tick()))
            advance(s, self.galaxy, now_tick())
            s.commit()


def create_app(game: Game | None = None, run_ticker: bool = True) -> FastAPI:
    if game is None:
        from .importer import migrate
        migrate()
        game = Game(make_sessionmaker(make_engine()))

    @asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(_tick_forever(game)) if run_ticker else None
        yield
        if task:
            task.cancel()

    api = FastAPI(lifespan=lifespan)
    api.state.game = game
    api.mount('/static', StaticFiles(directory=os.path.join(ROOT, 'static')), name='static')

    @api.exception_handler(HTTPException)
    async def _error(_req, exc: HTTPException):           # {'error': ...} like Flask did
        body = exc.detail if isinstance(exc.detail, dict) else {'error': exc.detail}
        return JSONResponse(body, status_code=exc.status_code)

    _routes(api, game)
    return api


async def _tick_forever(game: Game) -> None:
    while True:
        await asyncio.to_thread(game.catch_up)
        await asyncio.sleep(TICKER_EVERY_S)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso(tick: int) -> str:
    return time_of(tick).isoformat()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ints(src: dict, *keys: str) -> list[int]:
    try:
        return [int(src[k]) for k in keys]
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, f'{", ".join(keys)} required')


def _owned(s: Session, player: Player, planet_id: str) -> Colony | None:
    return s.scalars(select(Colony).where(Colony.owner_id == player.id,
                                          Colony.planet_id == planet_id)).one_or_none()


def _colony_star(col: Colony) -> tuple[int, int, int]:
    return col.cx, col.cy, col.star_index


def _legacy_colony(col: Colony) -> dict:
    """A colony row in the old JSON shape (planet ids, cx/cy/starIndex)."""
    return {'planetId': col.planet_id, 'name': col.name, 'cx': col.cx, 'cy': col.cy,
            'starIndex': col.star_index}


class World_:
    """Per-request view: session + game + the calling player."""
    def __init__(self, s: Session, game: Game, player: Player):
        self.s, self.game, self.galaxy, self.player = s, game, game.galaxy, player

    def planet(self, planet_id: str) -> dict | None:
        """The planet as it is now, with its live terraforming projects."""
        row = self.s.get(Planet, planet_id)
        p = self.galaxy.planet(planet_id, row.overrides if row else None)
        if p is not None and row is not None:
            p['terraforming'] = {**p.get('terraforming', {}), 'activeProjects': [
                {'lever': pr.lever, 'target': pr.target, 'status': pr.status}
                for pr in self.live_projects(planet_id)]}
        return p

    def live_projects(self, planet_id: str) -> list[TerraformProject]:
        return list(self.s.scalars(select(TerraformProject).where(
            TerraformProject.planet_id == planet_id,
            TerraformProject.status.in_(('active', 'stalled'))).order_by(TerraformProject.id)))

    def colonies(self) -> list[Colony]:
        return list(self.s.scalars(select(Colony).where(Colony.owner_id == self.player.id)
                                   .order_by(Colony.id)))

    def star_pos(self, cx, cy, idx):
        return self.galaxy.star_pos(cx, cy, idx)

    def sources_in_range(self, target: tuple[float, float], reach) -> list[tuple[Colony, float]]:
        out = []
        for col in self.colonies():
            if col.status != 'active' or col.dev_level < MIN_DEV_TO_COLONIZE:
                continue
            pos = self.star_pos(*_colony_star(col))
            if pos is None:
                continue
            dist = math.hypot(pos[0] - target[0], pos[1] - target[1])
            if dist <= reach(col.dev_level):
                out.append((col, dist))
        out.sort(key=lambda pair: pair[1])
        return out

    def enrich(self, col: Colony) -> dict:
        planet = self.planet(col.planet_id)
        d = colony_dict(col)
        ship = None
        if col.status == 'in_transit':
            ship = self.s.scalars(select(Ship).where(Ship.kind == 'colony_ship',
                                                     Ship.to_colony_id == col.id,
                                                     Ship.status == 'in_transit')).first()
        src = self.s.get(Colony, ship.from_colony_id) if ship and ship.from_colony_id else None
        rec = {
            **_legacy_colony(col),
            'founded': time_of(col.founded_tick).date().isoformat(),
            'size': col.size, 'developmentLevel': col.dev_level,
            'growthProgress': col.growth_progress, 'starvationTicks': col.starvation_ticks,
            'status': col.status, 'isHomeworld': col.is_homeworld,
            'departedAt': _iso(ship.departed_tick) if ship else None,
            'transitTicks': ship.arrival_tick - ship.departed_tick if ship else None,
            'sourcePlanetId': src.planet_id if src else None,
            'lastTickedAt': _iso(self.s.get(World, 1).last_tick),
            'colonyYields': planet['colonyYields'] if planet else {},
            'stockpiles': d['stockpiles'],
            'planet': planet,
        }
        if ship:
            transit = ship.arrival_tick - ship.departed_tick
            elapsed = (_now() - time_of(ship.departed_tick)).total_seconds()
            return {**rec, 'isAbandoned': False,
                    'transitProgressPct': round(min(100.0, elapsed / max(1, transit * TICK_SECONDS) * 100), 1),
                    'ticksRemaining': max(0.0, round(transit - elapsed / TICK_SECONDS, 1))}
        yields = rec['colonyYields']
        hab = planet['habitability']['total'] if planet else 100
        d['habitability'] = hab
        ok, _ = can_upgrade_dev(d)
        return {**rec,
                'habitability': hab, 'sizeCap': tf.size_cap(hab),
                'lifeSupportPerTick': tf.life_support(hab, SIZE_MULT[col.size - 1]),
                'extractionPerTick': extraction_per_tick(d, yields),
                'consumptionPerTick': consumption_per_tick(d),
                'netFlowPerTick': net_flow_per_tick(d, yields),
                'sizeName': size_name(d), 'devName': dev_name(d),
                'canUpgradeDev': ok, 'upgradeCost': upgrade_cost(d),
                'isAbandoned': col.status == 'abandoned'}

    def spend(self, col: Colony, cost: dict[str, float], what: str = '') -> None:
        """Take cost from col's stockpiles, or refuse (400) if it can't pay."""
        have = stockpiles(col)
        for res, amount in cost.items():
            if have.get(res, 0) < to_fixed(amount):
                raise HTTPException(400, f'insufficient {res}{what} (need {amount}, '
                                         f'have {have.get(res, 0) / 1000:.1f})')
        for st in col.stockpiles:
            if st.resource in cost:
                st.amount -= to_fixed(cost[st.resource])

    def launch(self, kind: str, src: Colony | None, arrival: int, uid: str | None = None,
               **kw) -> Ship:
        tick = self.s.get(World, 1).last_tick
        ship = Ship(uid=uid or str(uuid4()), owner_id=self.player.id, kind=kind,
                    status='in_transit', from_colony_id=src.id if src else None,
                    departed_tick=tick, arrival_tick=arrival, cargo=kw.pop('cargo', {}), **kw)
        self.s.add(ship)
        self.s.flush()
        self.s.add(Event(due_tick=arrival, kind='ship_arrives', ref_id=ship.id))
        return ship


def current_player_id() -> int:
    """Who is asking. Everyone is player 1 until logins exist; tests
    override this to act as someone else."""
    return 1


def _routes(api: FastAPI, game: Game) -> None:  # noqa: C901 (one place for every endpoint)
    galaxy = game.galaxy

    def world(player_id: int = Depends(current_player_id)):
        """The request's World_: caught up to now, under the game lock,
        committed if the handler returns normally. Every lookup below goes
        through the caller's own colonies, routes and ships."""
        game.catch_up()
        with game.lock, game.sessionmaker() as s:
            advance(s, galaxy, now_tick())
            player = s.get(Player, player_id)
            if player is None:
                player = Player(id=player_id, name=f'Player {player_id}', created_tick=now_tick())
                s.add(player)
                s.flush()
            yield World_(s, game, player)
            s.commit()

    W = Depends(world)

    @api.get('/')
    def index():
        return FileResponse(os.path.join(ROOT, 'templates', 'index.html'))

    @api.get('/api/config')
    def api_config():
        c = game.config
        return {'seed': c.seed, 'galaxyRadiusLy': c.galaxy_radius_ly,
                'chunkSizeLy': c.chunk_size_ly, 'visualAuToLy': c.visual_au_to_ly}

    @api.get('/api/chunks')
    def api_chunks(request: Request):
        try:
            box = [float(request.query_params[k]) for k in ('minX', 'minY', 'maxX', 'maxY')]
        except (KeyError, ValueError):
            raise HTTPException(400, 'minX, minY, maxX, maxY required')
        coords = chunks_in_bounds(*box, game.config.chunk_size_ly)
        return {'chunks': {f'{cx},{cy}': generate_chunk(cx, cy, game.config, game.density_field)
                           for cx, cy in coords}}

    @api.get('/api/system')
    def api_system(request: Request, w: World_ = W):
        cx, cy, index = _ints(request.query_params, 'cx', 'cy', 'index')
        star = galaxy.star(cx, cy, index)
        if star is None:
            raise HTTPException(404, 'star not found')
        system = generate_system(star)
        system['planets'] = [w.planet(p['id']) for p in system['planets']]
        return system

    @api.get('/api/homeworld')
    def api_homeworld(w: World_ = W):
        hw = find_homeworld(game.config, game.density_field)
        if hw is None:
            raise HTTPException(404, 'no suitable homeworld found')
        p = hw['planet']
        if w.s.get(Planet, p['id']) is None:
            w.s.add(Planet(planet_id=p['id'], updated_tick=now_tick(),
                           overrides=homeworld_overrides(p)))
        if _owned(w.s, w.player, p['id']) is None:
            w.s.add(Colony(owner_id=w.player.id, planet_id=p['id'], name=p['name'],
                           cx=hw['cx'], cy=hw['cy'], star_index=hw['starIndex'],
                           founded_tick=w.s.get(World, 1).last_tick, status='active',
                           size=3, dev_level=3, growth_progress=0, starvation_ticks=0,
                           is_homeworld=True, stockpiles=_stock(HOMEWORLD_STOCKPILES)))
        return hw

    @api.get('/api/colonies')
    def api_colonies_get(w: World_ = W):
        cols = w.colonies()
        hw = next((c for c in cols if c.is_homeworld), None)
        return {'homeworld': {'planetId': hw.planet_id} if hw else None,
                'colonies': [w.enrich(c) for c in cols]}

    def _target(w: World_, q) -> tuple[dict, dict, int, int, int]:
        cx, cy, star_index, planet_index = _ints(q, 'cx', 'cy', 'starIndex', 'planetIndex')
        star = galaxy.star(cx, cy, star_index)
        if star is None:
            raise HTTPException(404, 'star not found')
        planets = generate_system(star)['planets']
        if not 0 <= planet_index < len(planets):
            raise HTTPException(404, 'planet not found')
        return star, w.planet(planets[planet_index]['id']), cx, cy, star_index

    @api.get('/api/colonization-preview')
    def api_colonization_preview(request: Request, w: World_ = W):
        star, planet, *_ = _target(w, request.query_params)
        cost = colonization_cost(planet['habitability']['total'])
        sources = w.sources_in_range((star['worldX'], star['worldY']), colonization_range)
        if not sources:
            return {'eligible': False,
                    'reason': f'no Advanced (dev {MIN_DEV_TO_COLONIZE}+) colony within range'}
        return {'eligible': True, 'cost': cost, 'sources': [{
            'planetId': col.planet_id, 'name': col.name, 'devName': dev_name(colony_dict(col)),
            'distance': round(dist, 1), 'maxRange': colonization_range(col.dev_level),
            'transitTicks': max(1, math.ceil(dist / COLONY_SHIP_SPEED_LY_PER_TICK)),
            'canAfford': all(stockpiles(col).get(k, 0) >= to_fixed(v) for k, v in cost.items()),
        } for col, dist in sources]}

    @api.post('/api/colonies', status_code=201)
    def api_colonies_post(body: dict = Body(default={}), w: World_ = W):
        star, planet, cx, cy, star_index = _target(w, body)
        existing = _owned(w.s, w.player, planet['id'])
        if existing and existing.status != 'abandoned':
            raise HTTPException(409, {'error': 'colony already exists',
                                      'planetId': planet['id']})
        target = (star['worldX'], star['worldY'])
        sources = w.sources_in_range(target, colonization_range)
        if body.get('sourcePlanetId'):
            src = _owned(w.s, w.player, body['sourcePlanetId'])
            if src is None:
                raise HTTPException(404, 'specified source colony not found')
            if src.status != 'active':
                raise HTTPException(400, 'specified source colony is not active')
            if src.dev_level < MIN_DEV_TO_COLONIZE:
                raise HTTPException(400, 'specified source colony has insufficient development level')
            dist = next((d for c, d in sources if c.id == src.id), None)
            if dist is None:
                raise HTTPException(400, 'specified source colony is out of range')
        elif sources:
            src, dist = sources[0]
        else:
            raise HTTPException(403, f'no Advanced (dev {MIN_DEV_TO_COLONIZE}+) colony within range')
        w.spend(src, colonization_cost(planet['habitability']['total']), ' in source colony')
        transit = max(1, math.ceil(dist / COLONY_SHIP_SPEED_LY_PER_TICK))
        tick = w.s.get(World, 1).last_tick
        col = existing or Colony(owner_id=w.player.id, planet_id=planet['id'],
                                 cx=cx, cy=cy, star_index=star_index, stockpiles=_stock({}))
        col.name, col.founded_tick, col.status = planet['name'], tick, 'in_transit'
        col.size, col.dev_level, col.growth_progress, col.starvation_ticks = 1, 1, 0, 0
        col.is_homeworld = False
        for st in col.stockpiles:          # an abandoned colony is resettled from scratch
            st.amount = to_fixed(STARTER_STOCKPILES.get(st.resource, 0.0))
        w.s.add(col)
        w.s.flush()
        w.launch('colony_ship', src, tick + transit, to_colony_id=col.id)
        w.s.flush()
        return {'colony': w.enrich(col), 'planet': planet, 'transitTicks': transit}

    @api.post('/api/colonies/{planet_id:path}/upgrade')
    def api_colony_upgrade(planet_id: str, w: World_ = W):
        col = _owned(w.s, w.player, planet_id)
        if col is None:
            raise HTTPException(404, 'colony not found')
        if col.status == 'in_transit':
            raise HTTPException(400, 'colony ship is still in transit')
        d = colony_dict(col)
        ok, reason = can_upgrade_dev(d)
        if not ok:
            raise HTTPException(400, reason)
        up = apply_upgrade_dev(d)
        col.dev_level, col.growth_progress = up['developmentLevel'], up['growthProgress']
        for st in col.stockpiles:
            st.amount = to_fixed(up['stockpiles'][st.resource])
        return {'colony': w.enrich(col)}

    # ── Trade routes ───────────────────────────────────────────────────────────

    def _by_planet(w: World_) -> dict[str, Colony]:
        return {c.planet_id: c for c in w.colonies()}

    def _route_json(w: World_, r: Route) -> dict:
        by_id = {c.id: c for c in w.colonies()}
        ship = w.s.get(Ship, r.ship_id) if r.ship_id else None
        legs = [{'fromPlanetId': by_id[l.from_colony_id].planet_id,
                 'toPlanetId': by_id[l.to_colony_id].planet_id,
                 'cargo': float_map(l.cargo)} for l in r.legs]
        out = {'routeId': r.id, 'name': r.name, 'shipClass': r.ship_class, 'legs': legs,
               'status': r.status, 'currentLegIndex': r.current_leg,
               'legDepartedAt': _iso(ship.departed_tick) if ship else None,
               'shipName': SHIP_CLASSES.get(r.ship_class, {}).get('name', r.ship_class)}
        notes = w.s.scalars(select(Notification).where(Notification.route_id == r.id)
                            .order_by(Notification.id)).all()[-10:]
        if notes:
            out['events'] = [{'message': n.message, 'timestamp': _iso(n.tick), 'read': n.read}
                             for n in notes]
        if ship and legs:
            src, dst = by_id[ship.from_colony_id], by_id[ship.to_colony_id]
            transit = ship.arrival_tick - ship.departed_tick
            elapsed = (_now() - time_of(ship.departed_tick)).total_seconds()
            fx, fy = w.planet(src.planet_id)['worldX'], w.planet(src.planet_id)['worldY']
            tx, ty = w.planet(dst.planet_id)['worldX'], w.planet(dst.planet_id)['worldY']
            out['currentLeg'] = {
                'fromName': src.name, 'toName': dst.name,
                'distanceLy': round(galaxy.distance(_colony_star(src), _colony_star(dst)), 1),
                'transitTicks': transit, 'elapsedTicks': round(elapsed / TICK_SECONDS, 2),
                'progressPct': round(min(100.0, elapsed / max(1, transit * TICK_SECONDS) * 100), 1),
                'fromWorldX': fx, 'fromWorldY': fy, 'toWorldX': tx, 'toWorldY': ty}
        return out

    def _owned_route(w: World_, route_id: str) -> Route:
        r = w.s.get(Route, route_id)
        if r is None or r.owner_id != w.player.id:
            raise HTTPException(404, 'route not found')
        return r

    def _validate(w: World_, legs: list, ship_class: str) -> dict[str, Colony]:
        by_planet = _by_planet(w)
        ok, reason = validate_route(legs, ship_class, {k: _legacy_colony(c) for k, c in by_planet.items()},
                                    game.config, game.density_field)
        if not ok:
            raise HTTPException(400, reason)
        return by_planet

    def _leg_rows(legs: list, by_planet: dict[str, Colony]) -> list[RouteLeg]:
        return [RouteLeg(idx=i, from_colony_id=by_planet[l['fromPlanetId']].id,
                         to_colony_id=by_planet[l['toPlanetId']].id,
                         cargo=fixed_map(l.get('cargo', {}))) for i, l in enumerate(legs)]

    @api.get('/api/ships')
    def api_ships(planetId: str = '', w: World_ = W):
        col = _owned(w.s, w.player, planetId)
        if col is None:
            raise HTTPException(404, 'colony not found')
        return available_ship_classes(col.dev_level)

    @api.get('/api/routes')
    def api_routes_get(w: World_ = W):
        routes = w.s.scalars(select(Route).where(Route.owner_id == w.player.id)
                             .order_by(Route.id)).all()
        return {'routes': [_route_json(w, r) for r in routes]}

    @api.post('/api/routes', status_code=201)
    def api_routes_post(body: dict = Body(default={}), w: World_ = W):
        ship_class, legs = body.get('shipClass', ''), body.get('legs', [])
        if ship_class not in SHIP_CLASSES:
            raise HTTPException(400, f'unknown ship class: {ship_class}')
        ship = SHIP_CLASSES[ship_class]
        if not legs:
            raise HTTPException(400, 'route must have at least one leg')
        src = _owned(w.s, w.player, legs[0].get('fromPlanetId'))
        if src is None:
            raise HTTPException(404, f'source colony {legs[0].get("fromPlanetId")!r} not found')
        if src.dev_level < ship['devRequired']:
            raise HTTPException(403, f'{ship["name"]} requires dev level {ship["devRequired"]}; '
                                     f'source colony is dev {src.dev_level}')
        by_planet = _validate(w, legs, ship_class)
        setup, cargo = ship['setupCost'], legs[0].get('cargo', {})
        have = stockpiles(src)
        for res, amount in setup.items():
            if have.get(res, 0) < to_fixed(amount):
                raise HTTPException(400, f'insufficient {res} for setup cost (need {amount}, '
                                         f'have {have.get(res, 0) / 1000:.1f})')
        for res, amount in cargo.items():
            after = have.get(res, 0) - to_fixed(setup.get(res, 0))
            if after < to_fixed(amount):
                raise HTTPException(400, f'insufficient {res} for first leg cargo (need {amount} '
                                         f'after setup, have {after / 1000:.1f})')
        w.spend(src, setup)
        w.spend(src, cargo)
        route = Route(id=uuid4().hex[:8], owner_id=w.player.id, name=body.get('name', 'Unnamed Route'),
                      ship_class=ship_class, status='active', current_leg=0,
                      legs=_leg_rows(legs, by_planet))
        w.s.add(route)
        dst = by_planet[legs[0]['toPlanetId']]
        dist = galaxy.distance(_colony_star(src), _colony_star(dst))
        route.ship_id = w.launch('freighter', src, w.s.get(World, 1).last_tick
                                 + leg_transit_ticks(dist, ship_class),
                                 to_colony_id=dst.id, cargo=fixed_map(cargo)).id
        w.s.flush()
        return {'route': _route_json(w, route)}

    @api.delete('/api/routes/{route_id}')
    def api_routes_delete(route_id: str, w: World_ = W):
        r = _owned_route(w, route_id)
        w.s.execute(delete(Notification).where(Notification.route_id == r.id))
        w.s.delete(r)        # its freighter flies on and arrives empty-handed (cargo lost)
        return {'ok': True}

    @api.patch('/api/routes/{route_id}')
    def api_routes_patch(route_id: str, body: dict = Body(default={}), w: World_ = W):
        r = _owned_route(w, route_id)
        if 'name' in body:
            r.name = str(body['name']).strip() or r.name
        if 'legs' in body:
            by_planet = _validate(w, body['legs'], r.ship_class)
            r.legs.clear()
            w.s.flush()
            r.legs = _leg_rows(body['legs'], by_planet)
            r.current_leg %= len(r.legs)
        w.s.flush()
        return {'route': _route_json(w, r)}

    @api.post('/api/routes/{route_id}/events/read')
    def api_route_events_read(route_id: str, w: World_ = W):
        r = _owned_route(w, route_id)
        for n in w.s.scalars(select(Notification).where(Notification.route_id == r.id)):
            n.read = True
        return {'ok': True}

    # ── Terraforming ───────────────────────────────────────────────────────────

    def _tf_sources(w: World_, planet_id: str) -> list[tuple[Colony, float]]:
        """The caller's colonies that can terraform this planet: one on it
        from Advanced, or a Transcendent one within REMOTE_RANGE_LY."""
        target = galaxy.star_pos(*split_planet_id(planet_id))
        out = []
        for col in w.colonies():
            if col.status != 'active':
                continue
            if col.planet_id == planet_id:
                if col.dev_level >= tf.MIN_DEV_LOCAL:
                    out.append((col, 0.0))
            elif col.dev_level >= tf.MIN_DEV_REMOTE and target:
                pos = galaxy.star_pos(*_colony_star(col))
                dist = math.hypot(pos[0] - target[0], pos[1] - target[1])
                if dist <= tf.REMOTE_RANGE_LY:
                    out.append((col, dist))
        return sorted(out, key=lambda pair: pair[1])

    def _project_json(w: World_, pr: TerraformProject) -> dict:
        payer = w.s.get(Colony, pr.colony_id)
        return {'id': pr.id, 'lever': pr.lever, 'target': pr.target, 'status': pr.status,
                'mine': pr.owner_id == w.player.id,
                'owner': w.s.get(Player, pr.owner_id).name,
                'sourceName': payer.name if payer and pr.owner_id == w.player.id else None,
                'startedTick': pr.started_tick}

    def _tf_planet(w: World_, planet_id: str) -> dict:
        try:
            planet = w.planet(planet_id)
        except ValueError:
            planet = None
        if planet is None:
            raise HTTPException(404, 'planet not found')
        return planet

    @api.get('/api/terraform')
    def api_terraform_get(planetId: str = '', w: World_ = W):
        planet = _tf_planet(w, planetId)
        deltas = planet.get('terraforming', {})
        return {
            'planetId': planetId,
            'surfaceTempK': planet['surfaceTempK'],
            'pressureAtm': planet['atmosphere']['pressure'],
            'temperatureDeltaK': deltas.get('temperatureDeltaK', 0.0),
            'pressureDeltaAtm': deltas.get('pressureDeltaAtm', 0.0),
            'habitability': planet['habitability'],
            'sizeCap': tf.size_cap(planet['habitability']['total']),
            'levers': {name: {'unit': l['unit'], 'max': l['max'],
                              'costUp': l['cost_up'], 'costDown': l['cost_down']}
                       for name, l in tf.LEVERS.items()},
            'sources': [{'planetId': c.planet_id, 'name': c.name,
                         'devName': dev_name(colony_dict(c)), 'distance': round(d, 1),
                         'perDay': {name: round(tf.lever_rate(name, c.dev_level) * tf.TICKS_PER_DAY, 3)
                                    for name in tf.LEVERS}}
                        for c, d in _tf_sources(w, planetId)],
            'projects': [_project_json(w, pr) for pr in w.live_projects(planetId)],
        }

    @api.post('/api/terraform', status_code=201)
    def api_terraform_post(body: dict = Body(default={}), w: World_ = W):
        planet_id, lever = body.get('planetId', ''), body.get('lever')
        planet = _tf_planet(w, planet_id)
        if lever not in tf.LEVERS:
            raise HTTPException(400, f'unknown lever: {lever!r}')
        try:
            target = float(body['target'])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, 'target required (an offset, e.g. -20 for 20 K colder)')
        if not math.isfinite(target) or abs(target) > tf.LEVERS[lever]['max']:
            raise HTTPException(400, f'target must be within ±{tf.LEVERS[lever]["max"]} '
                                     f'{tf.LEVERS[lever]["unit"]}')
        sources = {c.planet_id: c for c, _ in _tf_sources(w, planet_id)}
        src = sources.get(body.get('sourcePlanetId')) if body.get('sourcePlanetId') \
            else next(iter(sources.values()), None)
        if src is None:
            raise HTTPException(403, 'no colony of yours can terraform this planet (one on it at '
                                     f'dev {tf.MIN_DEV_LOCAL}+, or dev {tf.MIN_DEV_REMOTE} within '
                                     f'{tf.REMOTE_RANGE_LY:g} Ly)')
        if any(pr.owner_id == w.player.id and pr.lever == lever for pr in w.live_projects(planet_id)):
            raise HTTPException(409, f'you already run a {lever} project here; stop it first')
        tick = w.s.get(World, 1).last_tick
        pr = TerraformProject(planet_id=planet_id, owner_id=w.player.id, colony_id=src.id,
                              lever=lever, target=target, status='active', started_tick=tick)
        w.s.add(pr)
        w.s.flush()
        unit = tf.LEVERS[lever]['unit']
        for owner_id in set(w.s.scalars(select(Colony.owner_id).where(
                Colony.planet_id == planet_id, Colony.owner_id != w.player.id))):
            w.s.add(Notification(player_id=owner_id, tick=tick, message=(
                f'{w.player.name} began terraforming {planet["name"]}: '
                f'{lever} toward {target:+g} {unit}.')))
        return _project_json(w, pr)

    @api.delete('/api/terraform/{project_id}')
    def api_terraform_delete(project_id: int, w: World_ = W):
        pr = w.s.get(TerraformProject, project_id)
        if pr is None or pr.owner_id != w.player.id:
            raise HTTPException(404, 'project not found')
        if pr.status in ('active', 'stalled'):
            pr.status, pr.ended_tick = 'stopped', w.s.get(World, 1).last_tick
        return {'ok': True}

    # ── Notifications ──────────────────────────────────────────────────────────

    @api.get('/api/notifications')
    def api_notifications(w: World_ = W):
        rows = w.s.scalars(select(Notification).where(Notification.player_id == w.player.id)
                           .order_by(Notification.id.desc()).limit(50)).all()
        return [{'id': n.id, 'message': n.message, 'timestamp': _iso(n.tick), 'read': n.read}
                for n in rows]

    @api.post('/api/notifications/read')
    def api_notifications_read(w: World_ = W):
        for n in w.s.scalars(select(Notification).where(Notification.player_id == w.player.id,
                                                        Notification.read.is_(False))):
            n.read = True
        return {'ok': True}

    # ── Scouts ─────────────────────────────────────────────────────────────────

    def _dest(star_id: str) -> tuple[int, int, int, tuple[float, float]]:
        try:
            cx, cy, idx = split_star_id(star_id)
        except ValueError:
            raise HTTPException(400, 'invalid starId')
        pos = galaxy.star_pos(cx, cy, idx)
        if pos is None:
            raise HTTPException(404, 'star not found')
        return cx, cy, idx, pos

    @api.get('/api/scout-preview')
    def api_scout_preview(starId: str = '', w: World_ = W):
        *_, pos = _dest(starId)
        sources = w.sources_in_range(pos, scout_range)
        if not sources:
            return {'eligible': False, 'reason': 'no Advanced (dev 3+) colony within scout range'}
        return {'eligible': True, 'cost': SCOUT_COST, 'sources': [{
            'planetId': col.planet_id, 'name': col.name, 'devName': dev_name(colony_dict(col)),
            'distance': round(dist, 1), 'scoutRange': scout_range(col.dev_level),
            'transitTicks': max(1, math.ceil(dist / COLONY_SHIP_SPEED_LY_PER_TICK)),
            'canAfford': all(stockpiles(col).get(k, 0) >= to_fixed(v) for k, v in SCOUT_COST.items()),
        } for col, dist in sources]}

    def _scout_json(w: World_, sh: Ship) -> dict:
        src = w.s.get(Colony, sh.from_colony_id) if sh.from_colony_id else None
        x, y = galaxy.star_pos(*split_star_id(sh.to_star_id)) or (None, None)
        return {'scoutId': sh.uid, 'sourcePlanetId': src.planet_id if src else None,
                'destStarId': sh.to_star_id, 'destWorldX': x, 'destWorldY': y,
                'status': sh.status, 'launchedAtTick': sh.departed_tick,
                'transitTicks': sh.arrival_tick - sh.departed_tick,
                'arrivalTick': sh.arrival_tick}

    @api.get('/api/scouts')
    def api_scouts_get(w: World_ = W):
        return [_scout_json(w, sh) for sh in w.s.scalars(
            select(Ship).where(Ship.owner_id == w.player.id, Ship.kind == 'scout').order_by(Ship.id))]

    @api.post('/api/scouts', status_code=201)
    def api_scouts_post(body: dict = Body(default={}), w: World_ = W):
        if None in (body.get('destStarCx'), body.get('destStarCy'), body.get('destStarIndex')):
            raise HTTPException(400, 'destStarCx, destStarCy, destStarIndex required')
        cx, cy, idx = _ints(body, 'destStarCx', 'destStarCy', 'destStarIndex')
        pos = galaxy.star_pos(cx, cy, idx)
        if pos is None:
            raise HTTPException(404, 'destination star not found')
        src = _owned(w.s, w.player, body.get('sourcePlanetId', ''))
        if src is None:
            raise HTTPException(404, 'source colony not found')
        if src.status != 'active':
            raise HTTPException(400, 'source colony is not active')
        if src.dev_level < MIN_DEV_TO_COLONIZE:
            raise HTTPException(400, 'source colony has insufficient development level')
        sp = galaxy.star_pos(*_colony_star(src))
        dist = math.hypot(sp[0] - pos[0], sp[1] - pos[1])
        if dist > scout_range(src.dev_level):
            raise HTTPException(400, 'destination is out of scout range')
        have = stockpiles(src)
        for res, amount in SCOUT_COST.items():
            if have.get(res, 0) < to_fixed(amount):
                raise HTTPException(400, f'insufficient {res} for scout probe')
        w.spend(src, SCOUT_COST)
        transit = max(1, math.ceil(dist / COLONY_SHIP_SPEED_LY_PER_TICK))
        sh = w.launch('scout', src, w.s.get(World, 1).last_tick + transit,
                      to_star_id=f'{cx},{cy}:{idx}')
        return _scout_json(w, sh)


def _stock(amounts: dict[str, float]) -> list[Stockpile]:
    return [Stockpile(resource=r, amount=to_fixed(amounts.get(r, 0.0))) for r in ALL_RESOURCES]


