"""The generated galaxy as the server sees it: stars and planets from the
seed, with each planet's shared overrides (planets table) on top.

Overrides (all optional):
    biosphere      a replacement biosphere layer (the homeworld's fix)
    yieldFloor     minimum colony yields (the homeworld's guarantee)
    terraforming   {'temperatureDeltaK', 'pressureDeltaAtm'} pushed by projects
Any of them makes the planet derived: air, water, habitability and yields
are recomputed (generation/terraform.py).
"""
import math
from functools import lru_cache

from generation.chunk_generator import regenerate_star
from generation.planet_factory import generate_system
from generation.terraform import derive_planet


def split_star_id(star_id: str) -> tuple[int, int, int]:
    """'cx,cy:star' -> (cx, cy, star_index)."""
    chunk, star = star_id.split(':')
    cx, cy = map(int, chunk.split(','))
    return cx, cy, int(star)


def split_planet_id(planet_id: str) -> tuple[int, int, int]:
    """'cx,cy:star:planet' -> (cx, cy, star_index)."""
    chunk, star, _ = planet_id.split(':')
    cx, cy = map(int, chunk.split(','))
    return cx, cy, int(star)


class Galaxy:
    def __init__(self, config, density_field):
        self.config = config
        self.density_field = density_field
        self._system = lru_cache(maxsize=4096)(self._system_uncached)
        self._base_state = lru_cache(maxsize=200_000)(self._base_state_uncached)

    def star(self, cx: int, cy: int, index: int) -> dict | None:
        return regenerate_star(cx, cy, index, self.config, self.density_field)

    def star_pos(self, cx: int, cy: int, index: int) -> tuple[float, float] | None:
        s = self.star(cx, cy, index)
        return (s['worldX'], s['worldY']) if s else None

    def _system_uncached(self, cx: int, cy: int, index: int) -> dict | None:
        s = self.star(cx, cy, index)
        return generate_system(s) if s else None

    def system(self, cx: int, cy: int, index: int) -> dict | None:
        """The generated system (cached; don't mutate it)."""
        return self._system(cx, cy, index)

    def planet(self, planet_id: str, overrides: dict | None = None) -> dict | None:
        """The planet as everyone on it lives with it. Callers get their own
        top-level copy (don't mutate the nested layers)."""
        system = self._system(*split_planet_id(planet_id))
        if system is None:
            return None
        base = next((p for p in system['planets'] if p['id'] == planet_id), None)
        if base is None:
            return None
        if not overrides:
            return dict(base)
        if 'biosphere' in overrides:
            base = {**base, 'biosphere': overrides['biosphere']}
        floor = overrides.get('yieldFloor', overrides.get('colonyYields'))   # old key
        return derive_planet(base, self.star(*split_planet_id(planet_id)),
                             overrides.get('terraforming'), floor)

    def distance(self, a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
        pa, pb = self.star_pos(*a), self.star_pos(*b)
        if pa is None or pb is None:
            return math.inf
        return math.hypot(pa[0] - pb[0], pa[1] - pb[1])

    def _base_state_uncached(self, planet_id: str) -> tuple[dict, int] | None:
        p = self.planet(planet_id)
        return (p['colonyYields'], p['habitability']['total']) if p else None

    def state(self, planet_id: str, overrides: dict | None = None) -> tuple[dict, int] | None:
        """(colony yields per tick, habitability) of a planet. Untouched
        planets are cached; changed ones (few) are derived each time."""
        if not overrides:
            return self._base_state(planet_id)
        p = self.planet(planet_id, overrides)
        return (p['colonyYields'], p['habitability']['total']) if p else None
