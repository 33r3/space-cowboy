"""
Terraforming and what a planet's habitability costs the people on it.
Pure functions, no I/O.

A planet's state = its generated layers + two offsets that projects push:
    temperatureDeltaK   added to the surface temperature
    pressureDeltaAtm    added to the atmospheric pressure (the greenhouse
                        effect scales with it, so thickening also warms)
From those, derive_planet() recomputes the air, the water (ice melts,
seas boil or freeze), habitability and colony yields. Life (biosphere)
doesn't change stage yet (that comes with the air-chemistry/life lever),
but it suffers: food and the biosphere's organics fall as the climate
leaves the one that life grew up in, and crash without liquid water.

Habitability then matters to every colony on the planet (Brent 2026-10-31):
    size cap       harsh worlds can't hold big colonies; a colony above
                   the cap shrinks one size every SHRINK_TICKS
    life support   below LIFE_SUPPORT_HAB a colony pays water + metals
                   every tick, more the harsher the world; unpaid it
                   starves by the usual rules
"""
import math

from .planet_factory import (
    ATMO_N2O2, WATER_ICE, WATER_MIXED, WATER_VAPOR, _clamp, _compute_habitability,
    _gaussian_score, colony_resource_yields, water_phase,
)

# ── Habitability's cost ───────────────────────────────────────────────────────

SIZE_CAP_BY_HAB = [(65, 5), (45, 4), (25, 3), (10, 2)]   # hab >= key -> max size
SHRINK_TICKS = 60                                          # an hour over the cap per size lost

LIFE_SUPPORT_HAB = 45            # Habitable and better: no life support
LIFE_SUPPORT_PER_TICK = {'water': 0.2, 'metals': 0.05}     # x size mult, at habitability 0


def size_cap(habitability: float) -> int:
    for floor, cap in SIZE_CAP_BY_HAB:
        if habitability >= floor:
            return cap
    return 1


def life_support(habitability: float, size_mult: float) -> dict[str, float]:
    """Per-tick upkeep of a colony with this size multiplier."""
    gap = max(0.0, LIFE_SUPPORT_HAB - habitability) / LIFE_SUPPORT_HAB
    return {k: round(v * gap * size_mult, 3) for k, v in LIFE_SUPPORT_PER_TICK.items() if gap > 0}


# ── Projects ──────────────────────────────────────────────────────────────────
# "Days" (Brent): ~10 K or ~0.2 atm in about three days at dev 3.

TICKS_PER_DAY = 1440
LEVERS = {
    'temperature': {'key': 'temperatureDeltaK', 'unit': 'K', 'rate': 10 / (3 * TICKS_PER_DAY),
                    'max': 150.0,
                    'cost_up':   {'chemFeedstocks': 0.05, 'fusionFuel': 0.02},   # greenhouse gases
                    'cost_down': {'metals': 0.08, 'fusionFuel': 0.02}},          # orbital shades
    'pressure':    {'key': 'pressureDeltaAtm', 'unit': 'atm', 'rate': 0.2 / (3 * TICKS_PER_DAY),
                    'max': 5.0,
                    'cost_up':   {'chemFeedstocks': 0.04, 'fusionFuel': 0.04},   # outgassing
                    'cost_down': {'fusionFuel': 0.05, 'metals': 0.03}},          # atmosphere strippers
}
DEV_RATE = {3: 1.0, 4: 1.5, 5: 2.0}
MIN_DEV_LOCAL = 3        # a colony on the planet can terraform it from Advanced
MIN_DEV_REMOTE = 5       # Transcendent colonies can do it from another system...
REMOTE_RANGE_LY = 300.0  # ...this close


def lever_rate(lever: str, dev_level: int) -> float:
    return LEVERS[lever]['rate'] * DEV_RATE.get(dev_level, 0.0)


def lever_cost(lever: str, direction: int) -> dict[str, float]:
    return dict(LEVERS[lever]['cost_up' if direction > 0 else 'cost_down'])


def step_toward(current: float, target: float, rate: float) -> float:
    if abs(target - current) <= rate:
        return target
    return current + math.copysign(rate, target - current)


# ── Deriving the planet ───────────────────────────────────────────────────────

BIO_YIELDS = ('food', 'organicFuels', 'chemFeedstocks')
DRY_LIFE = 0.2           # life left when the seas freeze or boil away


def _life_score(temp: float, hydro: dict) -> float:
    wet = hydro['liquidFraction'] > 0.01 or hydro['subsurfaceOcean']
    return _gaussian_score(temp, 290, 60) * (1.0 if wet else DRY_LIFE)


def life_stress(planet: dict, temp: float, hydro: dict) -> float:
    """0-1: how much of its life a planet keeps in a changed climate,
    compared with the climate it formed in (better never counts as more)."""
    base = _life_score(planet['surfaceTempK'], planet['hydrosphere'])
    return 1.0 if base <= 0 else min(1.0, _life_score(temp, hydro) / base)


def _extra_toxicity(pressure: float) -> float:
    return max(0.0, pressure - 2) * 0.02          # as in _generate_atmosphere


def derive_planet(planet: dict, star: dict, deltas: dict | None = None,
                  yield_floor: dict | None = None) -> dict:
    """`planet` as generated (with any whole-layer overrides already
    applied) moved by `deltas`. Returns a new dict; habitability and
    yields are recomputed, then raised to `yield_floor` if given."""
    deltas = deltas or {}
    d_t = deltas.get('temperatureDeltaK', 0.0)
    d_p = deltas.get('pressureDeltaAtm', 0.0)
    atmo0, hydro0 = planet['atmosphere'], planet['hydrosphere']

    p0 = atmo0['pressure']
    p = max(0.0, p0 + d_p)
    g0 = atmo0['greenhouseEffect']
    g = g0 * (p / p0) if p0 > 0.01 else g0
    t_eq = planet['surfaceTempK'] - g0
    temp = max(10.0, t_eq + g + d_t)

    atmo = {**atmo0, 'pressure': p, 'greenhouseEffect': g,
            'toxicity': _clamp(atmo0['toxicity'] - _extra_toxicity(p0) + _extra_toxicity(p), 0, 1),
            'breathable': atmo0['composition'] == ATMO_N2O2 and 0.5 <= p <= 2.0}

    base_cov = hydro0['waterCoverage'] / 0.3 if hydro0['state'] == WATER_VAPOR \
        else hydro0['waterCoverage']
    cov, liquid, ice, state = water_phase(base_cov, temp)
    hydro = {'waterCoverage': _clamp(cov, 0, 1), 'liquidFraction': _clamp(liquid, 0, 1),
             'iceCoverage': _clamp(ice, 0, 1), 'state': state,
             'subsurfaceOcean': hydro0['subsurfaceOcean'] and state in (WATER_ICE, WATER_MIXED)}

    bio = planet['biosphere']
    out = {**planet, 'surfaceTempK': temp, 'atmosphere': atmo, 'hydrosphere': hydro,
           'habitability': _compute_habitability(planet['lithosphere'], atmo, hydro, bio, temp, star)}
    yields = colony_resource_yields(out)
    stress = life_stress(planet, temp, hydro)
    for k in BIO_YIELDS:
        yields[k] = round(yields[k] * stress, 2)
    for k, v in (yield_floor or {}).items():
        yields[k] = max(yields.get(k, 0.0), v)
    out['colonyYields'] = yields
    out['terraforming'] = {**planet.get('terraforming', {}),
                           'temperatureDeltaK': d_t, 'pressureDeltaAtm': d_p}
    return out
