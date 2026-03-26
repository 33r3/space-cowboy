"""
Chunk generation — star placement per chunk, module-level cache, helpers.
Port of src/galaxy/ChunkGenerator.ts + ChunkCoord.ts helpers.
"""
import math
from .prng import PRNG, chunk_seed
from .star_factory import generate_star
from .config import GalaxyConfig
from .density_field import DensityField

# Module-level chunk cache
_chunk_cache: dict[str, list[dict]] = {}


def _chunk_key(cx: int, cy: int) -> str:
    return f'{cx},{cy}'


def chunks_in_bounds(min_x: float, min_y: float, max_x: float, max_y: float, chunk_size_ly: float) -> list[tuple[int, int]]:
    """Returns all chunk coords overlapping the given world-space bounds."""
    min_cx = math.floor(min_x / chunk_size_ly)
    min_cy = math.floor(min_y / chunk_size_ly)
    max_cx = math.floor((max_x - 0.001) / chunk_size_ly)
    max_cy = math.floor((max_y - 0.001) / chunk_size_ly)
    coords = []
    for cx in range(min_cx, max_cx + 1):
        for cy in range(min_cy, max_cy + 1):
            coords.append((cx, cy))
    return coords


def generate_chunk(cx: int, cy: int, config: GalaxyConfig, density_field: DensityField) -> list[dict]:
    """Generates (or returns cached) stars for a chunk at (cx, cy)."""
    key = _chunk_key(cx, cy)
    if key in _chunk_cache:
        return _chunk_cache[key]

    seed = chunk_seed(config.seed, cx, cy)
    prng = PRNG(seed)

    center_x = (cx + 0.5) * config.chunk_size_ly
    center_y = (cy + 0.5) * config.chunk_size_ly
    density = density_field.get_density(center_x, center_y)

    mean_stars = density * config.max_stars_per_chunk
    star_count = round(mean_stars + prng.next_gaussian() * math.sqrt(mean_stars + 0.5))
    clamped_count = max(0, min(config.max_stars_per_chunk, star_count))

    # Chunk bounds
    min_x = cx * config.chunk_size_ly
    min_y = cy * config.chunk_size_ly
    max_x = min_x + config.chunk_size_ly
    max_y = min_y + config.chunk_size_ly

    stars = []
    for i in range(clamped_count):
        wx = prng.next_float(min_x, max_x)
        wy = prng.next_float(min_y, max_y)
        stars.append(generate_star(prng, wx, wy, key, i))

    _chunk_cache[key] = stars
    return stars


def regenerate_star(cx: int, cy: int, index: int, config: GalaxyConfig, density_field: DensityField) -> dict | None:
    """Re-generates a specific star by its chunk coords and index.
    Always generates the full chunk (cached after first call) and returns star at index."""
    stars = generate_chunk(cx, cy, config, density_field)
    if index < 0 or index >= len(stars):
        return None
    return stars[index]
