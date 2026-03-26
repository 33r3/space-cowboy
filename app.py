import json
import os
from datetime import date, datetime, timezone

from flask import Flask, jsonify, request, render_template
from generation.config import DEFAULT_CONFIG
from generation.density_field import DensityField
from generation.chunk_generator import generate_chunk, chunks_in_bounds, regenerate_star
from generation.planet_factory import generate_system
from generation.homeworld import find_homeworld
from generation.colony_economics import (
    STARTER_STOCKPILES, migrate_colony, apply_ticks, pending_ticks,
    extraction_per_tick, consumption_per_tick, net_flow_per_tick,
    can_upgrade_dev, apply_upgrade_dev, size_name, dev_name, upgrade_cost,
)

app = Flask(__name__)

config        = DEFAULT_CONFIG
density_field = DensityField(config)

_DATA_DIR      = os.path.join(os.path.dirname(__file__), 'data')
_COLONIES_FILE = os.path.join(_DATA_DIR, 'colonies.json')


def _load_colonies() -> dict:
    if os.path.exists(_COLONIES_FILE):
        with open(_COLONIES_FILE) as f:
            return json.load(f)
    return {'homeworld': None, 'colonies': []}


def _save_colonies(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_COLONIES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


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


def _enrich_colony(col: dict, planet: dict) -> dict:
    """Add computed economics fields to a colony record for the API response."""
    yields = planet['colonyYields']
    ext    = extraction_per_tick(col, yields)
    con    = consumption_per_tick(col)
    net    = net_flow_per_tick(col, yields)
    ok, _ = can_upgrade_dev(col)
    return {
        **col,
        'planet':           planet,
        'extractionPerTick': ext,
        'consumptionPerTick': con,
        'netFlowPerTick':   net,
        'sizeName':         size_name(col),
        'devName':          dev_name(col),
        'canUpgradeDev':    ok,
        'upgradeCost':      upgrade_cost(col),
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
            'planetId':        planet_id,
            'name':            result['planet']['name'],
            'cx':              result['cx'],
            'cy':              result['cy'],
            'starIndex':       result['starIndex'],
            'founded':         str(date.today()),
            'size':            2,
            'developmentLevel': 2,
            'lastTickedAt':    _now_iso(),
            'stockpiles':      dict(STARTER_STOCKPILES),
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

        # Apply pending ticks (lazy real-time advance)
        n = pending_ticks(col['lastTickedAt'])
        if n > 0:
            col = apply_ticks(col, planet['colonyYields'], n)
            col['lastTickedAt'] = _now_iso()
            changed = True

        enriched.append(_enrich_colony(col, planet))

    if changed:
        # Write back updated colonies (without enrichment fields)
        data['colonies'] = [
            {k: v for k, v in e.items()
             if k not in ('planet', 'extractionPerTick', 'consumptionPerTick',
                          'netFlowPerTick', 'sizeName', 'devName',
                          'canUpgradeDev', 'upgradeCost')}
            for e in enriched
        ]
        _save_colonies(data)

    return jsonify({'homeworld': data.get('homeworld'), 'colonies': enriched})


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

    colony = migrate_colony({
        'planetId':   planet_id,
        'name':       planet['name'],
        'cx':         cx,
        'cy':         cy,
        'starIndex':  star_index,
        'founded':    str(date.today()),
        'lastTickedAt': _now_iso(),
    })
    data['colonies'].append(colony)
    _save_colonies(data)
    return jsonify({'colony': colony, 'planet': planet}), 201


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

    # Apply pending ticks first
    n = pending_ticks(colony['lastTickedAt'])
    if n > 0:
        colony = apply_ticks(colony, planet['colonyYields'], n)
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


if __name__ == '__main__':
    app.run(debug=True)
