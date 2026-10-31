"""One-time import of the old JSON saves (data/colonies.json, routes.json,
scouts.json) into the database as player 1.

    python -m server.importer [DATA_DIR]

Colonies are first caught up to now with the old rules, so the import
starts everyone at the same tick.
"""
import json
import os
import sys
from datetime import datetime

from generation.colony_economics import ALL_RESOURCES, apply_ticks, migrate_colony, pending_ticks
from generation.trade_routes import SHIP_CLASSES, leg_distance, leg_transit_ticks

from .models import (Colony, Event, Notification, Planet, Player, Route, RouteLeg, Ship,
                     Stockpile, World)
from .units import fixed_map, now_tick, tick_of

HOMEWORLD_OVERRIDE_KEYS = ('biosphere', 'habitability', 'colonyYields')


def _tick(iso: str) -> int:
    return tick_of(datetime.fromisoformat(iso.replace('Z', '+00:00')))


def _load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def import_saves(session, colonies_data: dict, routes_data: dict, scouts: list,
                 config, density_field, homeworld: dict | None = None,
                 player_name: str = 'Player 1') -> Player:
    """Add player 1 and everything they own. The caller commits."""
    now = now_tick()
    session.add(World(id=1, last_tick=now))
    player = Player(id=1, name=player_name, created_tick=now)
    session.add(player)

    if homeworld:
        p = homeworld['planet']
        session.add(Planet(planet_id=p['id'], updated_tick=now,
                           overrides={k: p[k] for k in HOMEWORLD_OVERRIDE_KEYS}))

    by_planet: dict[str, Colony] = {}
    old_by_planet: dict[str, dict] = {}
    for raw in colonies_data.get('colonies', []):
        col = migrate_colony(raw)
        if col['status'] == 'active':
            col = apply_ticks(col, col['colonyYields'], pending_ticks(col['lastTickedAt']))
        row = Colony(
            owner_id=player.id, planet_id=col['planetId'], name=col['name'],
            cx=col['cx'], cy=col['cy'], star_index=col['starIndex'],
            founded_tick=tick_of(datetime.fromisoformat(col['founded'] + 'T00:00:00+00:00'))
            if col.get('founded') else now,
            status=col['status'], size=col['size'], dev_level=col['developmentLevel'],
            growth_progress=col['growthProgress'], starvation_ticks=col['starvationTicks'],
            is_homeworld=col['isHomeworld'],
            stockpiles=[Stockpile(resource=r, amount=v)
                        for r, v in fixed_map({r: col['stockpiles'].get(r, 0.0)
                                               for r in ALL_RESOURCES}).items()],
        )
        session.add(row)
        by_planet[col['planetId']] = row
        old_by_planet[col['planetId']] = col
    session.flush()

    for pid, col in old_by_planet.items():
        if col['status'] != 'in_transit':
            continue
        src = by_planet.get(col.get('sourcePlanetId'))
        departed = _tick(col['departedAt'])
        _travel(session, player, kind='colony_ship', uid=f'colony-{by_planet[pid].id}',
                from_colony_id=src.id if src else None, to_colony_id=by_planet[pid].id,
                departed=departed, arrival=departed + col['transitTicks'])

    for r in routes_data.get('routes', []):
        legs = r.get('legs', [])
        if not legs or r['shipClass'] not in SHIP_CLASSES \
                or any(l['fromPlanetId'] not in by_planet or l['toPlanetId'] not in by_planet
                       for l in legs):
            continue
        idx = r.get('currentLegIndex', 0) % len(legs)
        leg = legs[idx]
        route = Route(id=r['routeId'], owner_id=player.id, name=r['name'],
                      ship_class=r['shipClass'], status=r.get('status', 'active'),
                      current_leg=idx,
                      legs=[RouteLeg(idx=i, from_colony_id=by_planet[l['fromPlanetId']].id,
                                     to_colony_id=by_planet[l['toPlanetId']].id,
                                     cargo=fixed_map(l.get('cargo', {})))
                            for i, l in enumerate(legs)])
        session.add(route)
        dist = leg_distance(old_by_planet[leg['fromPlanetId']], old_by_planet[leg['toPlanetId']],
                            config, density_field)
        departed = _tick(r['legDepartedAt'])
        # the old engine didn't track what was aboard: assume the order was loaded
        ship = _travel(session, player, kind='freighter', uid=f'route-{r["routeId"]}',
                       from_colony_id=by_planet[leg['fromPlanetId']].id,
                       to_colony_id=by_planet[leg['toPlanetId']].id, departed=departed,
                       arrival=departed + leg_transit_ticks(dist, r['shipClass']),
                       cargo=fixed_map(leg.get('cargo', {})),
                       schedule=route.status == 'active')
        route.ship_id = ship.id
        for e in r.get('events', []):
            session.add(Notification(player_id=player.id, tick=_tick(e['timestamp']),
                                     message=e['message'], read=e.get('read', False),
                                     route_id=route.id))

    for s in scouts:
        src = by_planet.get(s.get('sourcePlanetId'))
        _travel(session, player, kind='scout', uid=s['scoutId'],
                from_colony_id=src.id if src else None, to_star_id=s['destStarId'],
                departed=s['launchedAtTick'], arrival=s['arrivalTick'],
                status=s['status'])
    session.flush()
    return player


def _travel(session, player, *, kind, uid, departed, arrival, from_colony_id=None,
            to_colony_id=None, to_star_id=None, cargo=None, status='in_transit',
            schedule=True) -> Ship:
    ship = Ship(uid=uid, owner_id=player.id, kind=kind, status=status,
                from_colony_id=from_colony_id, to_colony_id=to_colony_id,
                to_star_id=to_star_id, departed_tick=departed, arrival_tick=arrival,
                cargo=cargo or {})
    session.add(ship)
    session.flush()
    if status == 'in_transit' and schedule:
        session.add(Event(due_tick=arrival, kind='ship_arrives', ref_id=ship.id))
    return ship


def migrate() -> None:
    """Bring the database (SPACE_COWBOY_DB) up to the latest migration."""
    from alembic import command
    from alembic.config import Config
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(root, 'alembic.ini'))
    cfg.set_main_option('script_location', os.path.join(root, 'migrations'))
    command.upgrade(cfg, 'head')


def main(argv):
    from generation.config import DEFAULT_CONFIG
    from generation.density_field import DensityField
    from generation.homeworld import find_homeworld

    from .db import make_engine, make_sessionmaker
    data_dir = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    migrate()
    engine = make_engine()
    density_field = DensityField(DEFAULT_CONFIG)
    with make_sessionmaker(engine)() as session:
        if session.get(Player, 1):
            sys.exit('the database already has player 1; not importing twice')
        import_saves(session,
                     _load(os.path.join(data_dir, 'colonies.json'), {'colonies': []}),
                     _load(os.path.join(data_dir, 'routes.json'), {'routes': []}),
                     _load(os.path.join(data_dir, 'scouts.json'), []),
                     DEFAULT_CONFIG, density_field,
                     homeworld=find_homeworld(DEFAULT_CONFIG, density_field))
        session.commit()
    print('imported into', engine.url)


if __name__ == '__main__':
    main(sys.argv)
