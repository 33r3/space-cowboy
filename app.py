from flask import Flask, jsonify, request, render_template
from generation.config import DEFAULT_CONFIG
from generation.density_field import DensityField
from generation.chunk_generator import generate_chunk, chunks_in_bounds, regenerate_star
from generation.planet_factory import generate_system

app = Flask(__name__)

config = DEFAULT_CONFIG
density_field = DensityField(config)


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


if __name__ == '__main__':
    app.run(debug=True)
