"""
Homeworld discovery — spiral search from galaxy center for a suitable starting planet.
"""
import json
import os

from .chunk_generator import generate_chunk
from .planet_factory import generate_system, LIFE_COMPLEX, colony_resource_yields

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
_HOMEWORLD_FILE = os.path.join(_DATA_DIR, 'homeworld.json')


def _spiral_chunks():
    """Yield chunk coords (cx, cy) spiraling outward from (0, 0)."""
    yield (0, 0)
    ring = 1
    while True:
        for cx in range(-ring, ring):
            yield (cx, -ring)
        for cy in range(-ring, ring):
            yield (ring, cy)
        for cx in range(ring, -ring, -1):
            yield (cx, ring)
        for cy in range(ring, -ring, -1):
            yield (-ring, cy)
        ring += 1


def _ensure_complex_life(planet: dict) -> bool:
    """
    Guarantee the homeworld has LIFE_COMPLEX biosphere AND minimum resource
    yields sufficient for self-sufficiency at every development level.
    Returns True if any change was made.

    A planet that produced a spacefaring civilisation must have complex life
    and the resource base to sustain advanced development without trade.
    """
    bio     = planet['biosphere']
    changed = False

    if bio['stage'] != LIFE_COMPLEX:
        bio['stage']    = LIFE_COMPLEX
        bio['coverage'] = max(bio.get('coverage', 0.0), 0.7)
        if bio.get('oxygenContribution', 0) < 0.10:
            bio['oxygenContribution'] = round(bio['coverage'] * 0.18, 3)
        planet['habitability']['biosphere'] = 0.8
        # Recompute yields with corrected biosphere (picks up new formulas too)
        planet['colonyYields'] = colony_resource_yields({
            'planetType':  planet['planetType'],
            'biosphere':   bio,
            'hydrosphere': planet['hydrosphere'],
            'resources':   planet['resources'],
        })
        changed = True

    # Enforce minimum yields for complete self-sufficiency at every dev level.
    # Values are base consumption rate × 1.5 so there is always a comfortable
    # surplus — see colony_economics.BASE_CONSUMPTION / DEV_CONSUMPTION.
    _MINS = {
        'food':           0.75,   # BASE 0.5
        'water':          0.75,   # BASE 0.5
        'minerals':       0.30,   # DEV 2 needs 0.20
        'metals':         0.15,   # DEV 3 needs 0.10
        'organicFuels':   0.15,   # DEV 3 needs 0.10
        'chemFeedstocks': 0.08,   # DEV 4 needs 0.05
        'fusionFuel':     0.08,   # DEV 4 needs 0.05
        'radioactives':   0.03,   # DEV 5 needs 0.02
    }
    cy = planet['colonyYields']
    for r, mn in _MINS.items():
        if cy.get(r, 0.0) < mn:
            cy[r] = mn
            changed = True

    return changed


def find_homeworld(config, density_field, max_rings: int = 20) -> dict | None:
    """
    Scan outward from the galaxy center and return the first Terran planet
    with habitability >= 80.  Result is cached to data/homeworld.json.
    The homeworld is always guaranteed to have LIFE_COMPLEX biosphere.
    """
    # Return cached result if available
    if os.path.exists(_HOMEWORLD_FILE):
        with open(_HOMEWORLD_FILE) as f:
            result = json.load(f)
        if _ensure_complex_life(result['planet']):
            # Biosphere was upgraded — persist the correction
            with open(_HOMEWORLD_FILE, 'w') as f:
                json.dump(result, f)
        return result

    result = None
    for cx, cy in _spiral_chunks():
        if max(abs(cx), abs(cy)) > max_rings:
            break
        stars = generate_chunk(cx, cy, config, density_field)
        for i, star in enumerate(stars):
            system = generate_system(star)
            for planet in system['planets']:
                if (planet['planetType'] == 'Terran' and
                        planet['habitability']['total'] >= 80):
                    result = {
                        'planet':     planet,
                        'star':       star,
                        'cx':         cx,
                        'cy':         cy,
                        'starIndex':  i,
                    }
                    break
            if result:
                break
        if result:
            break

    if result:
        _ensure_complex_life(result['planet'])
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_HOMEWORLD_FILE, 'w') as f:
            json.dump(result, f)

    return result
