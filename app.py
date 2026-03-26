import json
import os
from datetime import date

from flask import Flask, jsonify, request, render_template
from generation.config import DEFAULT_CONFIG
from generation.density_field import DensityField
from generation.chunk_generator import generate_chunk, chunks_in_bounds, regenerate_star
from generation.planet_factory import generate_system
from generation.homeworld import find_homeworld

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
    return jsonify(result)


@app.route('/api/colonies', methods=['GET'])
def api_colonies_get():
    data = _load_colonies()
    # Enrich each colony record with full planet data
    enriched = []
    for col in data['colonies']:
        star = regenerate_star(col['cx'], col['cy'], col['starIndex'], config, density_field)
        if star is None:
            continue
        system  = generate_system(star)
        planets = {p['id']: p for p in system['planets']}
        planet  = planets.get(col['planetId'])
        enriched.append({**col, 'planet': planet})
    return jsonify({'homeworld': data.get('homeworld'), 'colonies': enriched})


@app.route('/api/colonies', methods=['POST'])
def api_colonies_post():
    body = request.get_json(force=True) or {}
    try:
        cx          = int(body['cx'])
        cy          = int(body['cy'])
        star_index  = int(body['starIndex'])
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

    # Prevent duplicate colonies
    if any(c['planetId'] == planet_id for c in data['colonies']):
        return jsonify({'error': 'colony already exists', 'planetId': planet_id}), 409

    colony = {
        'planetId':   planet_id,
        'name':       planet['name'],
        'cx':         cx,
        'cy':         cy,
        'starIndex':  star_index,
        'founded':    str(date.today()),
    }
    data['colonies'].append(colony)
    _save_colonies(data)
    return jsonify({'colony': colony, 'planet': planet}), 201


if __name__ == '__main__':
    app.run(debug=True)
