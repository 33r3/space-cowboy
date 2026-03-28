import json
import math
import os
from datetime import date, datetime, timezone
from uuid import uuid4

from flask import Flask, jsonify, request, render_template
from generation.config import DEFAULT_CONFIG
from generation.density_field import DensityField
from generation.chunk_generator import generate_chunk, chunks_in_bounds, regenerate_star
from generation.planet_factory import generate_system
from generation.homeworld import find_homeworld
from generation.colony_economics import (
    STARTER_STOCKPILES, MIN_DEV_TO_COLONIZE, TICK_SECONDS,
    COLONY_SHIP_SPEED_LY_PER_TICK,
    migrate_colony, apply_ticks, pending_ticks,
    extraction_per_tick, consumption_per_tick, net_flow_per_tick,
    can_upgrade_dev, apply_upgrade_dev, size_name, dev_name, upgrade_cost,
    colonization_cost, colonization_range,
)
from generation.trade_routes import (
    SHIP_CLASSES, available_ship_classes,
    leg_distance, leg_transit_ticks, validate_route, tick_routes,
)

app = Flask(__name__)

config        = DEFAULT_CONFIG
density_field = DensityField(config)

_DATA_DIR      = os.path.join(os.path.dirname(__file__), 'data')
_COLONIES_FILE = os.path.join(_DATA_DIR, 'colonies.json')
_ROUTES_FILE   = os.path.join(_DATA_DIR, 'routes.json')


def _load_colonies() -> dict:
    if os.path.exists(_COLONIES_FILE):
        with open(_COLONIES_FILE) as f:
            return json.load(f)
    return {'homeworld': None, 'colonies': []}


def _save_colonies(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _COLONIES_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _COLONIES_FILE)


def _load_routes() -> dict:
    if os.path.exists(_ROUTES_FILE):
        with open(_ROUTES_FILE) as f:
            return json.load(f)
    return {'routes': []}


def _save_routes(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _ROUTES_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _ROUTES_FILE)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _get_planet(cx: int, cy: int, star_index: int, planet_id: str):
    """Load a planet dict by location. Returns (system, planet) or (None, None)."""
    star = regenerate_star(cx, cy, star_index, config, density_field)
    if star is None:
        return None, None
    system  = generate_system(star)
    planets = {p['id']: p for p in system['planets']}
    return system, planets.get(planet_id)


def _star_position(colony: dict) -> tuple[float, float] | None:
    """Return (worldX, worldY) of a colony's star (uses chunk cache)."""
    star = regenerate_star(colony['cx'], colony['cy'], colony['starIndex'], config, density_field)
    return (star['worldX'], star['worldY']) if star else None


def _planet_world_pos(planet_id: str) -> tuple[float | None, float | None]:
    """Return (worldX, worldY) of a planet from its ID string 'cx,cy:starIndex:planetIndex'."""
    try:
        parts = planet_id.split(':')
        cx, cy = map(int, parts[0].split(','))
        star_index = int(parts[1])
        _, planet = _get_planet(cx, cy, star_index, planet_id)
        if planet:
            return planet.get('worldX'), planet.get('worldY')
    except (ValueError, IndexError, AttributeError):
        pass
    return None, None


def _find_source_colony(data: dict, target_x: float, target_y: float):
    """Return (colony_dict, distance_ly) of the nearest dev-3+ colony within range, or None."""
    best_col, best_dist = None, float('inf')
    for col in data['colonies']:
        col = migrate_colony(col)
        if col['developmentLevel'] < MIN_DEV_TO_COLONIZE:
            continue
        pos = _star_position(col)
        if pos is None:
            continue
        dist = math.sqrt((pos[0] - target_x) ** 2 + (pos[1] - target_y) ** 2)
        max_range = colonization_range(col['developmentLevel'])
        if dist <= max_range and dist < best_dist:
            best_col, best_dist = col, dist
    return (best_col, best_dist) if best_col else None


_ENRICHED_KEYS = frozenset({
    'planet', 'extractionPerTick', 'consumptionPerTick',
    'netFlowPerTick', 'sizeName', 'devName',
    'canUpgradeDev', 'upgradeCost', 'isAbandoned',
    'transitProgressPct', 'ticksRemaining',
})


def _enrich_colony(col: dict, planet: dict) -> dict:
    """Add computed fields to a colony record for the API response."""
    if col.get('status') == 'in_transit':
        departed     = datetime.fromisoformat(col['departedAt'].replace('Z', '+00:00'))
        elapsed_s    = (datetime.now(tz=timezone.utc) - departed).total_seconds()
        transit_secs = col['transitTicks'] * TICK_SECONDS
        pct          = round(min(100.0, elapsed_s / max(1, transit_secs) * 100), 1)
        remaining    = max(0.0, round(col['transitTicks'] - elapsed_s / TICK_SECONDS, 1))
        return {
            **col,
            'planet':             planet,
            'transitProgressPct': pct,
            'ticksRemaining':     remaining,
            'isAbandoned':        False,
        }

    yields = col.get('colonyYields') or planet['colonyYields']
    ext    = extraction_per_tick(col, yields)
    con    = consumption_per_tick(col)
    net    = net_flow_per_tick(col, yields)
    ok, _ = can_upgrade_dev(col)
    return {
        **col,
        'planet':             planet,
        'extractionPerTick':  ext,
        'consumptionPerTick': con,
        'netFlowPerTick':     net,
        'sizeName':           size_name(col),
        'devName':            dev_name(col),
        'canUpgradeDev':      ok,
        'upgradeCost':        upgrade_cost(col),
        'isAbandoned':        col.get('status') == 'abandoned',
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/config')
def api_config():
    return jsonify({
        'seed':           config.seed,
        'galaxyRadiusLy': config.galaxy_radius_ly,
        'chunkSizeLy':    config.chunk_size_ly,
        'visualAuToLy':   config.visual_au_to_ly,
    })


@app.route('/api/chunks')
def api_chunks():
    try:
        min_x = float(request.args['minX'])
        min_y = float(request.args['minY'])
        max_x = float(request.args['maxX'])
        max_y = float(request.args['maxY'])
    except (KeyError, ValueError):
        return jsonify({'error': 'minX, minY, maxX, maxY required'}), 400

    coords = chunks_in_bounds(min_x, min_y, max_x, max_y, config.chunk_size_ly)
    result = {}
    for cx, cy in coords:
        stars = generate_chunk(cx, cy, config, density_field)
        result[f'{cx},{cy}'] = stars
    return jsonify({'chunks': result})


@app.route('/api/system')
def api_system():
    try:
        cx    = int(request.args['cx'])
        cy    = int(request.args['cy'])
        index = int(request.args['index'])
    except (KeyError, ValueError):
        return jsonify({'error': 'cx, cy, index required'}), 400

    star = regenerate_star(cx, cy, index, config, density_field)
    if star is None:
        return jsonify({'error': 'star not found'}), 404

    system = generate_system(star)

    # Patch homeworld planet with corrected biosphere/yields if this is the homeworld star
    hw = find_homeworld(config, density_field)
    if hw and hw['cx'] == cx and hw['cy'] == cy and hw['starIndex'] == index:
        hw_id = hw['planet']['id']
        system['planets'] = [
            hw['planet'] if p['id'] == hw_id else p
            for p in system['planets']
        ]

    return jsonify(system)


@app.route('/api/homeworld')
def api_homeworld():
    result = find_homeworld(config, density_field)
    if result is None:
        return jsonify({'error': 'no suitable homeworld found'}), 404

    planet_id = result['planet']['id']
    data      = _load_colonies()

    # Auto-found homeworld colony if not already present
    if not any(c['planetId'] == planet_id for c in data['colonies']):
        colony = migrate_colony({
            'planetId':         planet_id,
            'name':             result['planet']['name'],
            'cx':               result['cx'],
            'cy':               result['cy'],
            'starIndex':        result['starIndex'],
            'founded':          str(date.today()),
            'size':             3,
            'developmentLevel': 3,
            'isHomeworld':      True,
            'lastTickedAt':     _now_iso(),
            'colonyYields':     result['planet']['colonyYields'],
            'stockpiles': {
                'food':           100.0,
                'water':          100.0,
                'minerals':       200.0,
                'metals':         150.0,
                'organicFuels':   100.0,
                'chemFeedstocks':  50.0,
                'fusionFuel':      50.0,
                'radioactives':    10.0,
            },
        })
        data['homeworld'] = {'planetId': planet_id}
        data['colonies'].append(colony)
        _save_colonies(data)

    return jsonify(result)


@app.route('/api/colonies', methods=['GET'])
def api_colonies_get():
    data    = _load_colonies()
    changed = False
    enriched = []

    for col in data['colonies']:
        col = migrate_colony(col)

        _, planet = _get_planet(col['cx'], col['cy'], col['starIndex'], col['planetId'])
        if planet is None:
            continue

        # Lazily populate colonyYields for existing saves.
        # Homeworld uses the patched cache; others use the generated planet.
        if not col.get('colonyYields'):
            if col.get('isHomeworld'):
                hw = find_homeworld(config, density_field)
                col['colonyYields'] = hw['planet']['colonyYields'] if hw else planet['colonyYields']
            else:
                col['colonyYields'] = planet['colonyYields']
            changed = True

        # Colony ship in transit — check arrival, skip economics
        if col.get('status') == 'in_transit':
            departed  = datetime.fromisoformat(col['departedAt'].replace('Z', '+00:00'))
            elapsed_s = (datetime.now(tz=timezone.utc) - departed).total_seconds()
            if elapsed_s >= col['transitTicks'] * TICK_SECONDS:
                # Ship arrived — promote to active
                col['status']         = 'active'
                col['departedAt']     = None
                col['transitTicks']   = None
                col['sourcePlanetId'] = None
                col['lastTickedAt']   = _now_iso()
                changed = True
                # Fall through to normal economic tick below
            else:
                enriched.append(_enrich_colony(col, planet))
                changed = True   # migrate_colony may have added fields
                continue

        # Apply pending ticks using the colony's stored yields
        n = pending_ticks(col['lastTickedAt'])
        if n > 0:
            col = apply_ticks(col, col['colonyYields'], n)
            col['lastTickedAt'] = _now_iso()
            changed = True

        enriched.append(_enrich_colony(col, planet))

    if changed:
        # Write back updated colonies (strip computed-only fields)
        data['colonies'] = [
            {k: v for k, v in e.items() if k not in _ENRICHED_KEYS}
            for e in enriched
        ]
        _save_colonies(data)

    return jsonify({'homeworld': data.get('homeworld'), 'colonies': enriched})


@app.route('/api/colonization-preview')
def api_colonization_preview():
    try:
        cx           = int(request.args['cx'])
        cy           = int(request.args['cy'])
        star_index   = int(request.args['starIndex'])
        planet_index = int(request.args['planetIndex'])
    except (KeyError, ValueError):
        return jsonify({'error': 'cx, cy, starIndex, planetIndex required'}), 400

    star = regenerate_star(cx, cy, star_index, config, density_field)
    if star is None:
        return jsonify({'error': 'star not found'}), 404

    system = generate_system(star)
    if planet_index < 0 or planet_index >= len(system['planets']):
        return jsonify({'error': 'planet not found'}), 404

    planet   = system['planets'][planet_index]
    target_x = star['worldX']
    target_y = star['worldY']

    data   = _load_colonies()
    result = _find_source_colony(data, target_x, target_y)

    if result is None:
        dev_name_needed = 'Advanced'   # DEV_NAMES[MIN_DEV_TO_COLONIZE - 1]
        return jsonify({
            'eligible': False,
            'reason':   f'no {dev_name_needed} (dev {MIN_DEV_TO_COLONIZE}+) colony within range',
        })

    source_col, distance = result
    hab   = planet['habitability']['total']
    cost  = colonization_cost(hab)

    can_afford = all(
        source_col['stockpiles'].get(k, 0.0) >= v
        for k, v in cost.items()
    )

    transit_ticks = max(1, math.ceil(distance / COLONY_SHIP_SPEED_LY_PER_TICK))

    return jsonify({
        'eligible':     True,
        'cost':         cost,
        'canAfford':    can_afford,
        'distance':     round(distance, 1),
        'maxRange':     colonization_range(source_col['developmentLevel']),
        'transitTicks': transit_ticks,
        'sourceColony': {
            'planetId':         source_col['planetId'],
            'name':             source_col['name'],
            'sizeName':         size_name(source_col),
            'devName':          dev_name(source_col),
            'developmentLevel': source_col['developmentLevel'],
            'stockpiles':       source_col['stockpiles'],
        },
    })


@app.route('/api/colonies', methods=['POST'])
def api_colonies_post():
    body = request.get_json(force=True) or {}
    try:
        cx           = int(body['cx'])
        cy           = int(body['cy'])
        star_index   = int(body['starIndex'])
        planet_index = int(body['planetIndex'])
    except (KeyError, ValueError):
        return jsonify({'error': 'cx, cy, starIndex, planetIndex required'}), 400

    star = regenerate_star(cx, cy, star_index, config, density_field)
    if star is None:
        return jsonify({'error': 'star not found'}), 404

    system = generate_system(star)
    if planet_index < 0 or planet_index >= len(system['planets']):
        return jsonify({'error': 'planet not found'}), 404

    planet    = system['planets'][planet_index]
    planet_id = planet['id']

    data = _load_colonies()

    if any(c['planetId'] == planet_id for c in data['colonies']):
        return jsonify({'error': 'colony already exists', 'planetId': planet_id}), 409

    # ── Colonization constraints ───────────────────────────────────────────────
    target_x = star['worldX']
    target_y = star['worldY']
    result   = _find_source_colony(data, target_x, target_y)

    if result is None:
        return jsonify({
            'error': f'no Advanced (dev {MIN_DEV_TO_COLONIZE}+) colony within range'
        }), 403

    source_col, _distance = result
    hab  = planet['habitability']['total']
    cost = colonization_cost(hab)

    for resource, amount in cost.items():
        if source_col['stockpiles'].get(resource, 0.0) < amount:
            return jsonify({
                'error': f'insufficient {resource} in source colony '
                         f'(need {amount}, have {source_col["stockpiles"].get(resource, 0.0):.1f})'
            }), 400

    # Deduct cost from source colony
    for resource, amount in cost.items():
        source_col['stockpiles'][resource] = round(
            source_col['stockpiles'].get(resource, 0.0) - amount, 1
        )

    # Write updated source colony back
    data['colonies'] = [
        source_col if c['planetId'] == source_col['planetId'] else c
        for c in data['colonies']
    ]
    # ── Compute transit duration ────────────────────────────────────────────────
    source_pos  = _star_position(source_col)
    target_pos  = (star['worldX'], star['worldY'])
    distance_ly = math.sqrt(
        (source_pos[0] - target_pos[0]) ** 2 + (source_pos[1] - target_pos[1]) ** 2
    ) if source_pos else 0.0
    transit_ticks = max(1, math.ceil(distance_ly / COLONY_SHIP_SPEED_LY_PER_TICK))

    # ── Create in-transit colony record ────────────────────────────────────────
    colony = {
        'planetId':        planet_id,
        'name':            planet['name'],
        'cx':              cx,
        'cy':              cy,
        'starIndex':       star_index,
        'founded':         str(date.today()),
        'status':          'in_transit',
        'departedAt':      _now_iso(),
        'transitTicks':    transit_ticks,
        'sourcePlanetId':  source_col['planetId'],
        'lastTickedAt':    _now_iso(),
        'size':            1,
        'developmentLevel': 1,
        'growthProgress':  0,
        'starvationTicks': 0,
        'isHomeworld':     False,
        'stockpiles':      dict(STARTER_STOCKPILES),
        'colonyYields':    planet['colonyYields'],
    }
    data['colonies'].append(colony)
    _save_colonies(data)
    return jsonify({'colony': colony, 'planet': planet, 'transitTicks': transit_ticks}), 201


@app.route('/api/colonies/<path:planet_id>/upgrade', methods=['POST'])
def api_colony_upgrade(planet_id: str):
    data = _load_colonies()

    colony_rec = next((c for c in data['colonies'] if c['planetId'] == planet_id), None)
    if colony_rec is None:
        return jsonify({'error': 'colony not found'}), 404

    colony = migrate_colony(colony_rec)
    _, planet = _get_planet(colony['cx'], colony['cy'], colony['starIndex'], planet_id)
    if planet is None:
        return jsonify({'error': 'planet not found'}), 404

    if colony.get('status') == 'in_transit':
        return jsonify({'error': 'colony ship is still in transit'}), 400

    # Apply pending ticks first
    n = pending_ticks(colony['lastTickedAt'])
    if n > 0:
        yields = colony.get('colonyYields') or planet['colonyYields']
        colony = apply_ticks(colony, yields, n)
        colony['lastTickedAt'] = _now_iso()

    ok, reason = can_upgrade_dev(colony)
    if not ok:
        return jsonify({'error': reason}), 400

    colony = apply_upgrade_dev(colony)

    # Replace record in data
    data['colonies'] = [
        colony if c['planetId'] == planet_id else c
        for c in data['colonies']
    ]
    _save_colonies(data)

    return jsonify({'colony': _enrich_colony(colony, planet)})


# ── Trade route helpers ────────────────────────────────────────────────────────

def _enrich_route(route: dict, colonies_by_id: dict) -> dict:
    """Add transit-progress fields for the current leg."""
    route = dict(route)
    ship  = SHIP_CLASSES.get(route['shipClass'], {})
    route['shipName'] = ship.get('name', route['shipClass'])

    legs    = route.get('legs', [])
    leg_idx = route.get('currentLegIndex', 0)
    if not legs:
        return route

    leg     = legs[leg_idx % len(legs)]
    from_id = leg.get('fromPlanetId')
    to_id   = leg.get('toPlanetId')

    from_col = colonies_by_id.get(from_id)
    to_col   = colonies_by_id.get(to_id)

    dist          = leg_distance(from_col, to_col, config, density_field) if (from_col and to_col) else 0.0
    transit_ticks = leg_transit_ticks(dist, route['shipClass']) if ship else 1

    departed  = datetime.fromisoformat(route['legDepartedAt'].replace('Z', '+00:00'))
    elapsed_s = (datetime.now(tz=timezone.utc) - departed).total_seconds()
    elapsed_ticks = elapsed_s / max(1, transit_ticks * 60)

    from_wx, from_wy = _planet_world_pos(from_id) if from_id else (None, None)
    to_wx, to_wy     = _planet_world_pos(to_id)   if to_id   else (None, None)

    route['currentLeg'] = {
        'fromName':     (colonies_by_id[from_id]['name'] if from_id in colonies_by_id else from_id),
        'toName':       (colonies_by_id[to_id]['name']   if to_id   in colonies_by_id else to_id),
        'distanceLy':   round(dist, 1),
        'transitTicks': transit_ticks,
        'elapsedTicks': round(elapsed_s / 60, 2),
        'progressPct':  round(min(100.0, elapsed_ticks * 100), 1),
        'fromWorldX': from_wx, 'fromWorldY': from_wy,
        'toWorldX':   to_wx,   'toWorldY':   to_wy,
    }
    return route


# ── Trade route endpoints ──────────────────────────────────────────────────────

@app.route('/api/ships')
def api_ships():
    planet_id = request.args.get('planetId', '')
    data      = _load_colonies()
    col       = next((c for c in data['colonies'] if c['planetId'] == planet_id), None)
    if col is None:
        return jsonify({'error': 'colony not found'}), 404
    return jsonify(available_ship_classes(col['developmentLevel']))


@app.route('/api/routes', methods=['GET'])
def api_routes_get():
    routes_data  = _load_routes()
    colonies_data = _load_colonies()

    # Apply ticks to routes (lazy advance)
    routes_data, colonies_data, changed = tick_routes(
        routes_data, colonies_data, config, density_field
    )
    if changed:
        _save_routes(routes_data)
        _save_colonies(colonies_data)

    colonies_by_id = {c['planetId']: c for c in colonies_data['colonies']}
    enriched = [_enrich_route(r, colonies_by_id) for r in routes_data['routes']]
    return jsonify({'routes': enriched})


@app.route('/api/routes', methods=['POST'])
def api_routes_post():
    body = request.get_json(force=True) or {}
    name        = body.get('name', 'Unnamed Route')
    ship_class  = body.get('shipClass', '')
    legs        = body.get('legs', [])

    if ship_class not in SHIP_CLASSES:
        return jsonify({'error': f'unknown ship class: {ship_class}'}), 400

    ship = SHIP_CLASSES[ship_class]

    colonies_data  = _load_colonies()
    colonies_by_id = {c['planetId']: c for c in colonies_data['colonies']}

    # Source colony = first leg's fromPlanetId
    if not legs:
        return jsonify({'error': 'route must have at least one leg'}), 400

    source_id  = legs[0].get('fromPlanetId')
    source_col = colonies_by_id.get(source_id)
    if source_col is None:
        return jsonify({'error': f'source colony {source_id!r} not found'}), 404

    # Dev gate
    if source_col['developmentLevel'] < ship['devRequired']:
        return jsonify({
            'error': f'{ship["name"]} requires dev level {ship["devRequired"]}; '
                     f'source colony is dev {source_col["developmentLevel"]}'
        }), 403

    # Validate legs
    ok, reason = validate_route(legs, ship_class, colonies_by_id, config, density_field)
    if not ok:
        return jsonify({'error': reason}), 400

    # Check setup cost
    setup_cost = ship['setupCost']
    for resource, amount in setup_cost.items():
        if source_col['stockpiles'].get(resource, 0.0) < amount:
            return jsonify({
                'error': f'insufficient {resource} for setup cost '
                         f'(need {amount}, have {source_col["stockpiles"].get(resource, 0.0):.1f})'
            }), 400

    # Check first leg cargo
    first_cargo = legs[0].get('cargo', {})
    for resource, amount in first_cargo.items():
        available = source_col['stockpiles'].get(resource, 0.0)
        # After setup cost
        after_setup = available - setup_cost.get(resource, 0.0)
        if after_setup < amount:
            return jsonify({
                'error': f'insufficient {resource} for first leg cargo '
                         f'(need {amount} after setup, have {after_setup:.1f})'
            }), 400

    # Deduct setup cost from source
    for resource, amount in setup_cost.items():
        source_col['stockpiles'][resource] = round(
            source_col['stockpiles'].get(resource, 0.0) - amount, 3
        )

    # Deduct first leg cargo from source
    for resource, amount in first_cargo.items():
        source_col['stockpiles'][resource] = round(
            source_col['stockpiles'].get(resource, 0.0) - amount, 3
        )

    # Write updated source colony back
    colonies_data['colonies'] = [
        source_col if c['planetId'] == source_id else c
        for c in colonies_data['colonies']
    ]
    _save_colonies(colonies_data)

    # Create route
    route = {
        'routeId':         uuid4().hex[:8],
        'name':            name,
        'shipClass':       ship_class,
        'legs':            legs,
        'status':          'active',
        'currentLegIndex': 0,
        'legDepartedAt':   datetime.now(tz=timezone.utc).isoformat(),
    }
    routes_data = _load_routes()
    routes_data['routes'].append(route)
    _save_routes(routes_data)

    return jsonify({'route': route}), 201


@app.route('/api/routes/<route_id>', methods=['DELETE'])
def api_routes_delete(route_id: str):
    routes_data = _load_routes()
    before = len(routes_data['routes'])
    routes_data['routes'] = [r for r in routes_data['routes'] if r['routeId'] != route_id]
    if len(routes_data['routes']) == before:
        return jsonify({'error': 'route not found'}), 404
    _save_routes(routes_data)
    return jsonify({'ok': True})


@app.route('/api/routes/<route_id>', methods=['PATCH'])
def api_routes_patch(route_id: str):
    routes_data = _load_routes()
    route = next((r for r in routes_data['routes'] if r['routeId'] == route_id), None)
    if route is None:
        return jsonify({'error': 'route not found'}), 404

    body = request.get_json(force=True) or {}

    if 'name' in body:
        route['name'] = str(body['name']).strip() or route['name']

    if 'legs' in body:
        legs = body['legs']
        colonies_data  = _load_colonies()
        colonies_by_id = {c['planetId']: c for c in colonies_data['colonies']}
        ok, reason = validate_route(legs, route['shipClass'], colonies_by_id, config, density_field)
        if not ok:
            return jsonify({'error': reason}), 400
        route['legs'] = legs
        route['currentLegIndex'] = route.get('currentLegIndex', 0) % len(legs)

    _save_routes(routes_data)
    colonies_data  = _load_colonies()
    colonies_by_id = {c['planetId']: c for c in colonies_data['colonies']}
    return jsonify({'route': _enrich_route(route, colonies_by_id)})


@app.route('/api/routes/<route_id>/events/read', methods=['POST'])
def api_route_events_read(route_id: str):
    routes_data = _load_routes()
    for r in routes_data['routes']:
        if r['routeId'] == route_id:
            for e in r.get('events', []):
                e['read'] = True
            _save_routes(routes_data)
            return jsonify({'ok': True})
    return jsonify({'error': 'route not found'}), 404


if __name__ == '__main__':
    app.run(debug=True)
