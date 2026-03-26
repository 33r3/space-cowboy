"""
Full planetary system generation cascade.
Port of src/planets/PlanetFactory.ts + Lithosphere.ts + Atmosphere.ts +
Hydrosphere.ts + Biosphere.ts + Habitability.ts + PlanetResources.ts.
"""
import math
from .prng import PRNG
from .orbital_mechanics import habitable_zone, equilibrium_temperature, planet_count, generate_orbital_slots, roman_numeral

VISUAL_AU_TO_LY = 0.6

# ── Enums (string values match TypeScript enums) ──────────────────────────────

# LithosphereComposition
SILICATE   = 'Silicate'
IRON_RICH  = 'IronRich'
CARBON_RICH = 'CarbonRich'
ICY_ROCK   = 'IcyRock'
METALLIC   = 'Metallic'

# PlanetType
LAVA_PLANET  = 'LavaPlanet'
HOT_JUPITER  = 'HotJupiter'
BARREN       = 'Barren'
DESERT       = 'Desert'
ARID         = 'Arid'
TERRAN       = 'Terran'
OCEANIC      = 'Oceanic'
TUNDRA       = 'Tundra'
GLACIAL      = 'Glacial'
VOLCANIC     = 'Volcanic'
CARBON_WORLD = 'CarbonWorld'
SUPER_EARTH  = 'SuperEarth'
SUB_NEPTUNE  = 'SubNeptune'
GAS_GIANT    = 'GasGiant'
ICE_GIANT    = 'IceGiant'

# AtmoComposition
ATMO_NONE     = 'None'
ATMO_THIN     = 'Thin'
ATMO_N2O2     = 'N2O2'
ATMO_N2CO2    = 'N2CO2'
ATMO_CO2DENSE = 'CO2Dense'
ATMO_H2HE     = 'H2He'
ATMO_METHANE  = 'Methane'
ATMO_SO2      = 'SO2'

# WaterState
WATER_NONE   = 'None'
WATER_ICE    = 'Ice'
WATER_MIXED  = 'Mixed'
WATER_LIQUID = 'Liquid'
WATER_VAPOR  = 'Vapor'

# LifeStage
LIFE_NONE        = 'None'
LIFE_PREBIOTIC   = 'Prebiotic'
LIFE_MICROBIAL   = 'Microbial'
LIFE_SIMPLE_MULTI = 'SimpleMulticellular'
LIFE_COMPLEX     = 'ComplexLife'

# HabitabilityCategory
HAB_LETHAL      = 'Lethal'
HAB_HOSTILE     = 'Hostile'
HAB_MARGINAL    = 'Marginal'
HAB_HABITABLE   = 'Habitable'
HAB_COMFORTABLE = 'Comfortable'
HAB_OPTIMAL     = 'Optimal'

# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _gaussian_score(x, mean, sigma):
    d = (x - mean) / sigma
    return math.exp(-0.5 * d * d)

def _weighted_pick(items, weights, rand):
    cumulative = 0.0
    for item, w in zip(items, weights):
        cumulative += w
        if rand < cumulative:
            return item
    return items[-1]

# ── Lithosphere ───────────────────────────────────────────────────────────────

_LITHO_TEMPLATES = {
    LAVA_PLANET:  dict(mass_min=0.3, mass_max=3.0, radius_min=0.6, radius_max=1.4, density_min=5.5, density_max=8.0, tectonic_min=0.85, tectonic_max=1.0, magnetic_min=0.0, magnetic_max=0.3, compositions=[SILICATE, IRON_RICH], weights=[0.4, 0.6]),
    HOT_JUPITER:  dict(mass_min=80,  mass_max=300, radius_min=8,   radius_max=15,  density_min=0.3, density_max=1.5, tectonic_min=0.0,  tectonic_max=0.0, magnetic_min=0.3, magnetic_max=0.9, compositions=[ICY_ROCK], weights=[1.0]),
    BARREN:       dict(mass_min=0.01,mass_max=0.5, radius_min=0.2, radius_max=0.8, density_min=3.0, density_max=5.5, tectonic_min=0.0,  tectonic_max=0.15, magnetic_min=0.0, magnetic_max=0.1, compositions=[SILICATE, IRON_RICH], weights=[0.7, 0.3]),
    DESERT:       dict(mass_min=0.05,mass_max=1.2, radius_min=0.3, radius_max=1.1, density_min=3.5, density_max=5.5, tectonic_min=0.05, tectonic_max=0.4, magnetic_min=0.0, magnetic_max=0.3, compositions=[SILICATE, IRON_RICH, CARBON_RICH], weights=[0.6, 0.3, 0.1]),
    ARID:         dict(mass_min=0.3, mass_max=1.5, radius_min=0.7, radius_max=1.2, density_min=4.0, density_max=5.8, tectonic_min=0.1,  tectonic_max=0.5, magnetic_min=0.1, magnetic_max=0.5, compositions=[SILICATE, IRON_RICH], weights=[0.7, 0.3]),
    TERRAN:       dict(mass_min=0.5, mass_max=2.0, radius_min=0.8, radius_max=1.3, density_min=4.5, density_max=5.8, tectonic_min=0.2,  tectonic_max=0.7, magnetic_min=0.3, magnetic_max=0.8, compositions=[SILICATE, IRON_RICH], weights=[0.75, 0.25]),
    OCEANIC:      dict(mass_min=0.6, mass_max=2.5, radius_min=0.9, radius_max=1.4, density_min=3.5, density_max=4.8, tectonic_min=0.1,  tectonic_max=0.5, magnetic_min=0.2, magnetic_max=0.7, compositions=[SILICATE, ICY_ROCK], weights=[0.6, 0.4]),
    TUNDRA:       dict(mass_min=0.3, mass_max=1.5, radius_min=0.6, radius_max=1.1, density_min=3.5, density_max=5.2, tectonic_min=0.0,  tectonic_max=0.3, magnetic_min=0.0, magnetic_max=0.4, compositions=[SILICATE, ICY_ROCK], weights=[0.5, 0.5]),
    GLACIAL:      dict(mass_min=0.1, mass_max=1.2, radius_min=0.4, radius_max=1.0, density_min=2.0, density_max=4.0, tectonic_min=0.0,  tectonic_max=0.1, magnetic_min=0.0, magnetic_max=0.2, compositions=[ICY_ROCK, SILICATE], weights=[0.7, 0.3]),
    VOLCANIC:     dict(mass_min=0.2, mass_max=2.0, radius_min=0.5, radius_max=1.2, density_min=5.0, density_max=7.5, tectonic_min=0.7,  tectonic_max=1.0, magnetic_min=0.0, magnetic_max=0.4, compositions=[SILICATE, IRON_RICH], weights=[0.5, 0.5]),
    CARBON_WORLD: dict(mass_min=0.2, mass_max=1.5, radius_min=0.5, radius_max=1.1, density_min=3.0, density_max=5.0, tectonic_min=0.1,  tectonic_max=0.5, magnetic_min=0.0, magnetic_max=0.2, compositions=[CARBON_RICH], weights=[1.0]),
    SUPER_EARTH:  dict(mass_min=2.0, mass_max=10.0,radius_min=1.3, radius_max=2.0, density_min=4.5, density_max=7.0, tectonic_min=0.3,  tectonic_max=0.9, magnetic_min=0.3, magnetic_max=0.9, compositions=[SILICATE, IRON_RICH, METALLIC], weights=[0.5, 0.35, 0.15]),
    SUB_NEPTUNE:  dict(mass_min=4.0, mass_max=15.0,radius_min=2.0, radius_max=3.5, density_min=1.5, density_max=3.5, tectonic_min=0.0,  tectonic_max=0.0, magnetic_min=0.2, magnetic_max=0.7, compositions=[ICY_ROCK, SILICATE], weights=[0.7, 0.3]),
    GAS_GIANT:    dict(mass_min=30,  mass_max=300, radius_min=6,   radius_max=14,  density_min=0.5, density_max=2.0, tectonic_min=0.0,  tectonic_max=0.0, magnetic_min=0.4, magnetic_max=1.0, compositions=[ICY_ROCK], weights=[1.0]),
    ICE_GIANT:    dict(mass_min=10,  mass_max=50,  radius_min=3.5, radius_max=6,   density_min=1.2, density_max=2.5, tectonic_min=0.0,  tectonic_max=0.0, magnetic_min=0.3, magnetic_max=0.8, compositions=[ICY_ROCK], weights=[1.0]),
}

_GAS_TYPES = {GAS_GIANT, ICE_GIANT, HOT_JUPITER, SUB_NEPTUNE}


def _generate_lithosphere(prng: PRNG, planet_type: str) -> dict:
    t = _LITHO_TEMPLATES[planet_type]
    mass    = prng.next_float(t['mass_min'],    t['mass_max'])
    radius  = prng.next_float(t['radius_min'],  t['radius_max'])
    gravity = mass / (radius * radius)
    density = prng.next_float(t['density_min'], t['density_max'])
    tectonic = prng.next_float(t['tectonic_min'], t['tectonic_max'])
    raw_magnetic = prng.next_float(t['magnetic_min'], t['magnetic_max'])

    if planet_type in _GAS_TYPES:
        magnetic = raw_magnetic
    else:
        magnetic = raw_magnetic * (0.5 + 0.5 * tectonic) * min(1, mass * 0.8)

    composition = _weighted_pick(t['compositions'], t['weights'], prng.next())

    return {
        'massEarth':       max(0.005, mass),
        'radiusEarth':     max(0.1, radius),
        'gravityG':        max(0.01, gravity),
        'densityGcm3':     density,
        'tectonicActivity': tectonic,
        'magneticField':   _clamp(magnetic, 0, 1),
        'composition':     composition,
    }

# ── Atmosphere ────────────────────────────────────────────────────────────────

_GREENHOUSE_BASE = {
    ATMO_NONE: 0, ATMO_THIN: 2, ATMO_N2O2: 33, ATMO_N2CO2: 5,
    ATMO_CO2DENSE: 500, ATMO_H2HE: 20, ATMO_METHANE: 12, ATMO_SO2: 25,
}
_TOXICITY_BASE = {
    ATMO_NONE: 0.0, ATMO_THIN: 0.1, ATMO_N2O2: 0.0, ATMO_N2CO2: 0.6,
    ATMO_CO2DENSE: 0.95, ATMO_H2HE: 0.2, ATMO_METHANE: 0.75, ATMO_SO2: 0.9,
}
_ATMO_TEMPLATES = {
    LAVA_PLANET:  dict(pressure_min=0,    pressure_max=0.01, composition=ATMO_NONE,     greenhouse_scatter=0),
    HOT_JUPITER:  dict(pressure_min=50,   pressure_max=200,  composition=ATMO_H2HE,     greenhouse_scatter=5),
    BARREN:       dict(pressure_min=0,    pressure_max=0.005,composition=ATMO_NONE,     greenhouse_scatter=0),
    DESERT:       dict(pressure_min=0.01, pressure_max=0.5,  composition=ATMO_N2CO2,    greenhouse_scatter=3),
    ARID:         dict(pressure_min=0.3,  pressure_max=1.5,  composition=ATMO_N2CO2,    greenhouse_scatter=8),
    TERRAN:       dict(pressure_min=0.6,  pressure_max=1.5,  composition=ATMO_N2O2,     greenhouse_scatter=10),
    OCEANIC:      dict(pressure_min=0.8,  pressure_max=2.0,  composition=ATMO_N2O2,     greenhouse_scatter=12),
    TUNDRA:       dict(pressure_min=0.1,  pressure_max=0.8,  composition=ATMO_N2CO2,    greenhouse_scatter=5),
    GLACIAL:      dict(pressure_min=0,    pressure_max=0.1,  composition=ATMO_THIN,     greenhouse_scatter=1),
    VOLCANIC:     dict(pressure_min=10,   pressure_max=90,   composition=ATMO_SO2,      greenhouse_scatter=20),
    CARBON_WORLD: dict(pressure_min=1.0,  pressure_max=5.0,  composition=ATMO_METHANE,  greenhouse_scatter=4),
    SUPER_EARTH:  dict(pressure_min=1.0,  pressure_max=3.0,  composition=ATMO_N2CO2,    greenhouse_scatter=15),
    SUB_NEPTUNE:  dict(pressure_min=20,   pressure_max=100,  composition=ATMO_H2HE,     greenhouse_scatter=8),
    GAS_GIANT:    dict(pressure_min=100,  pressure_max=500,  composition=ATMO_H2HE,     greenhouse_scatter=10),
    ICE_GIANT:    dict(pressure_min=30,   pressure_max=150,  composition=ATMO_H2HE,     greenhouse_scatter=5),
}


def _generate_atmosphere(prng: PRNG, planet_type: str, litho: dict) -> dict:
    t = _ATMO_TEMPLATES[planet_type]
    pressure = prng.next_float(t['pressure_min'], t['pressure_max'])

    if planet_type not in _GAS_TYPES:
        pressure *= (1 + litho['tectonicActivity'] * 0.5)

    composition = t['composition']
    base_gh = _GREENHOUSE_BASE[composition]
    mid_pressure = (t['pressure_min'] + t['pressure_max']) / 2
    greenhouse = base_gh * (pressure / max(0.001, mid_pressure)) + prng.next_gaussian() * t['greenhouse_scatter']
    toxicity = _TOXICITY_BASE[composition] + (pressure - 2) * 0.02 if pressure > 2 else _TOXICITY_BASE[composition]

    breathable = composition == ATMO_N2O2 and 0.5 <= pressure <= 2.0

    return {
        'pressure':        max(0, pressure),
        'composition':     composition,
        'greenhouseEffect': max(0, greenhouse),
        'toxicity':        _clamp(toxicity, 0, 1),
        'breathable':      breathable,
    }


def _refine_atmosphere(atmo: dict, bio: dict) -> dict:
    if bio['oxygenContribution'] < 0.18:
        return atmo
    refined = dict(atmo)
    if atmo['composition'] == ATMO_N2CO2 and 0.5 <= atmo['pressure'] <= 2.5:
        refined['composition'] = ATMO_N2O2
        refined['toxicity']    = 0
        refined['breathable']  = True
        refined['greenhouseEffect'] = 33 + atmo['greenhouseEffect'] * 0.1
    return refined

# ── Hydrosphere ───────────────────────────────────────────────────────────────

def _generate_hydrosphere(prng: PRNG, planet_type: str, surface_temp_k: float, litho: dict, atmo: dict) -> dict:
    if planet_type in _GAS_TYPES:
        return {'waterCoverage': 0, 'liquidFraction': 0, 'iceCoverage': 0, 'state': WATER_NONE, 'subsurfaceOcean': False}

    base_map = {
        OCEANIC:    (lambda: prng.next_float(0.7, 1.0), 0.0),
        TERRAN:     (lambda: prng.next_float(0.3, 0.8), 0.0),
        ARID:       (lambda: prng.next_float(0.05, 0.3), 0.15),
        TUNDRA:     (lambda: prng.next_float(0.2, 0.6), 0.2),
        GLACIAL:    (lambda: prng.next_float(0.4, 0.9), 0.4),
        DESERT:     (lambda: prng.next_float(0.0, 0.08), 0.1),
        BARREN:     (lambda: prng.next_float(0.0, 0.02), 0.05),
        VOLCANIC:   (lambda: prng.next_float(0.0, 0.05), 0.0),
        LAVA_PLANET:(lambda: 0.0, 0.0),
        CARBON_WORLD:(lambda: prng.next_float(0.0, 0.1), 0.0),
        SUPER_EARTH:(lambda: prng.next_float(0.1, 0.7), 0.1),
    }

    if planet_type in base_map:
        cov_fn, subsurface_chance = base_map[planet_type]
        base_coverage = cov_fn()
    else:
        base_coverage = 0.0
        subsurface_chance = 0.0

    if atmo['pressure'] < 0.01:
        base_coverage *= 0.1
        subsurface_chance *= 0.3

    base_coverage = min(1.0, base_coverage * (0.7 + 0.3 * min(1, litho['massEarth'])))

    if base_coverage < 0.001:
        state = WATER_NONE
        liquid_fraction = 0.0
        ice_coverage    = 0.0
    elif surface_temp_k > 450:
        state           = WATER_VAPOR
        liquid_fraction = 0.0
        ice_coverage    = 0.0
        base_coverage  *= 0.3
    elif surface_temp_k > 273:
        warmth = min(1, (surface_temp_k - 273) / 100)
        liquid_fraction = 0.7 + warmth * 0.3
        ice_coverage    = (1 - liquid_fraction) * base_coverage
        state = WATER_MIXED if ice_coverage > 0.05 else WATER_LIQUID
    else:
        freeze_depth    = max(0, 1 - (surface_temp_k - 150) / 123)
        liquid_fraction = max(0, 0.1 - freeze_depth * 0.1)
        ice_coverage    = base_coverage * 0.8
        state = WATER_MIXED if liquid_fraction > 0.01 else WATER_ICE

    subsurface_ocean = (
        base_coverage > 0.1
        and state in (WATER_ICE, WATER_MIXED)
        and litho['tectonicActivity'] > 0.05
        and prng.next() < subsurface_chance
    )

    return {
        'waterCoverage':  _clamp(base_coverage, 0, 1),
        'liquidFraction': _clamp(liquid_fraction, 0, 1),
        'iceCoverage':    _clamp(ice_coverage, 0, 1),
        'state':          state,
        'subsurfaceOcean': subsurface_ocean,
    }

# ── Biosphere ─────────────────────────────────────────────────────────────────

def _generate_biosphere(prng: PRNG, surface_temp_k: float, hydro: dict, atmo: dict) -> dict:
    has_liquid_water = hydro['liquidFraction'] > 0.01 or hydro['subsurfaceOcean']
    temp_ok = 150 < surface_temp_k < 400
    has_atmo = atmo['pressure'] > 0.01 and atmo['composition'] != ATMO_NONE

    if not has_liquid_water or not temp_ok or not has_atmo:
        return {'stage': LIFE_NONE, 'coverage': 0, 'oxygenContribution': 0}

    if prng.next() > 0.65:
        return {'stage': LIFE_NONE, 'coverage': 0, 'oxygenContribution': 0}

    temp_score  = _gaussian_score(surface_temp_k, 290, 60)
    water_score = hydro['liquidFraction'] * hydro['waterCoverage']
    overall     = temp_score * 0.6 + water_score * 0.4

    stage_roll = prng.next() * overall
    if stage_roll > 0.7:
        stage = LIFE_COMPLEX
    elif stage_roll > 0.45:
        stage = LIFE_SIMPLE_MULTI
    elif stage_roll > 0.2:
        stage = LIFE_MICROBIAL
    else:
        stage = LIFE_PREBIOTIC

    coverage_map = {
        LIFE_PREBIOTIC:   lambda: prng.next_float(0.0, 0.1),
        LIFE_MICROBIAL:   lambda: prng.next_float(0.1, 0.5),
        LIFE_SIMPLE_MULTI:lambda: prng.next_float(0.3, 0.7),
        LIFE_COMPLEX:     lambda: prng.next_float(0.5, 1.0),
    }
    coverage = coverage_map[stage]()

    o2 = 0.0
    if stage == LIFE_SIMPLE_MULTI:
        o2 = coverage * prng.next_float(0.05, 0.15)
    elif stage == LIFE_COMPLEX:
        o2 = coverage * prng.next_float(0.15, 0.22)

    return {
        'stage':             stage,
        'coverage':          coverage,
        'oxygenContribution': min(0.21, o2),
    }

# ── Habitability ──────────────────────────────────────────────────────────────

def _to_category(total: float) -> str:
    if total <= 10:  return HAB_LETHAL
    if total <= 25:  return HAB_HOSTILE
    if total <= 45:  return HAB_MARGINAL
    if total <= 65:  return HAB_HABITABLE
    if total <= 80:  return HAB_COMFORTABLE
    return HAB_OPTIMAL


def _compute_habitability(litho: dict, atmo: dict, hydro: dict, bio: dict, surface_temp_k: float, star: dict) -> dict:
    temperature = _gaussian_score(surface_temp_k, 293, 55)

    if atmo['breathable']:
        atmosphere = _clamp(1.0 - abs(atmo['pressure'] - 1.0) * 0.3, 0.5, 1.0)
    elif atmo['composition'] == ATMO_NONE:
        atmosphere = 0.0
    elif atmo['toxicity'] < 0.3 and 0.1 <= atmo['pressure'] <= 3.0:
        atmosphere = 0.3
    else:
        atmosphere = _clamp(0.15 - atmo['toxicity'] * 0.15, 0, 0.15)

    g = litho['gravityG']
    if g < 0.15 or g > 3.0:
        gravity = 0.0
    elif 0.4 <= g <= 1.5:
        gravity = _gaussian_score(g, 1.0, 0.4)
    else:
        gravity = 0.2 * _gaussian_score(g, 1.0, 1.0)

    atm_shielding = _clamp(atmo['pressure'] / 1.0, 0, 1)
    mag_shielding  = litho['magneticField']
    shielding      = _clamp(mag_shielding * 0.5 + atm_shielding * 0.5, 0, 1)

    sc = star['spectralClass']
    stellar_radiation = 1.0
    if sc == 'O':   stellar_radiation = 0.1
    elif sc == 'B': stellar_radiation = 0.3
    elif sc == 'A': stellar_radiation = 0.6
    elif sc == 'M': stellar_radiation = 0.8

    radiation = shielding * stellar_radiation

    liquid_water = hydro['liquidFraction'] * hydro['waterCoverage']
    if liquid_water > 0.2:
        water = 1.0
    elif liquid_water > 0.01:
        water = 0.5 + liquid_water * 2.5
    elif hydro['subsurfaceOcean']:
        water = 0.4
    elif hydro['iceCoverage'] > 0.1:
        water = 0.1
    else:
        water = 0.0

    bio_scores = {
        LIFE_NONE:        0.05,
        LIFE_PREBIOTIC:   0.1,
        LIFE_MICROBIAL:   0.2,
        LIFE_SIMPLE_MULTI:0.5,
        LIFE_COMPLEX:     0.8,
    }
    biosphere = bio_scores.get(bio['stage'], 0.0)

    total = (
        temperature * 0.25 +
        atmosphere  * 0.25 +
        gravity     * 0.15 +
        radiation   * 0.15 +
        water       * 0.15 +
        biosphere   * 0.05
    ) * 100

    return {
        'total':       _clamp(round(total), 0, 100),
        'temperature': _clamp(temperature, 0, 1),
        'atmosphere':  _clamp(atmosphere, 0, 1),
        'gravity':     _clamp(gravity, 0, 1),
        'radiation':   _clamp(radiation, 0, 1),
        'water':       _clamp(water, 0, 1),
        'biosphere':   _clamp(biosphere, 0, 1),
        'category':    _to_category(total),
    }

# ── Resources ─────────────────────────────────────────────────────────────────

def _deposit(prng: PRNG, abundance_min: float, abundance_max: float, access_min: float = 0.2, access_max: float = 0.9) -> dict:
    return {
        'abundance':    prng.next_float(abundance_min, abundance_max),
        'accessibility': prng.next_float(access_min, access_max),
    }


def _generate_resources(prng: PRNG, planet_type: str, litho: dict, bio: dict) -> dict:
    if planet_type in _GAS_TYPES:
        return {
            'metals':       _deposit(prng, 0, 0),
            'rareMetals':   _deposit(prng, 0, 0),
            'rareEarths':   _deposit(prng, 0, 0),
            'radioactives': _deposit(prng, 0, 0.05),
            'volatiles':    _deposit(prng, 0.5, 1.0, 0.1, 0.5),
            'organics':     _deposit(prng, 0, 0.1),
            'exotics':      _deposit(prng, 0, 0.02),
        }

    comp = litho['composition']

    metal_mult = 1.4 if comp == IRON_RICH else (1.7 if comp == METALLIC else 1.0)
    metals = _deposit(prng, 0.1 * metal_mult, 0.6 * metal_mult)

    rare_mult = 1.8 if comp == METALLIC else (1.2 if comp == IRON_RICH else 1.0)
    rare_metals = _deposit(prng, 0.02 * rare_mult, 0.3 * rare_mult)

    re_mult = 1.3 if comp == SILICATE else 0.7
    rare_earths = _deposit(prng, 0.01 * re_mult, 0.2 * re_mult)

    radio_mult = 1.3 if comp == IRON_RICH else 1.0
    radioactives = _deposit(prng, 0.01 * radio_mult, 0.25 * radio_mult)

    icy_bonus = 1.8 if comp == ICY_ROCK else 1.0
    vol_mult  = 1.5 if planet_type in (GLACIAL, TUNDRA) else 1.0
    volatiles = _deposit(prng, 0.05 * icy_bonus * vol_mult, 0.5 * icy_bonus * vol_mult)

    stage = bio['stage']
    if stage in (LIFE_NONE, LIFE_PREBIOTIC):
        org_ab = prng.next_float(0.2, 0.6) if planet_type == CARBON_WORLD else prng.next_float(0, 0.05)
    elif stage == LIFE_MICROBIAL:
        org_ab = prng.next_float(0.05, 0.25)
    else:
        org_ab = prng.next_float(0.2, 0.8) * bio['coverage']
    organics = _deposit(prng, org_ab, org_ab)

    exotic_chance = 0.12 if planet_type == SUPER_EARTH else (0.09 if planet_type in (VOLCANIC, LAVA_PLANET) else 0.04)
    if prng.next() < exotic_chance:
        exotics = _deposit(prng, 0.05, 0.3, 0.05, 0.4)
    else:
        exotics = {'abundance': 0, 'accessibility': 0}

    return {
        'metals': metals, 'rareMetals': rare_metals, 'rareEarths': rare_earths,
        'radioactives': radioactives, 'volatiles': volatiles,
        'organics': organics, 'exotics': exotics,
    }

# ── Planet type selection ─────────────────────────────────────────────────────

def _select_planet_type(prng: PRNG, t_eq: float, semi_major_au: float, star: dict) -> str:
    hz = habitable_zone(star['luminositySolar'])

    if semi_major_au < hz['inner'] * 0.12:
        return HOT_JUPITER if prng.next() < 0.35 else LAVA_PLANET

    if t_eq > 600: return LAVA_PLANET
    if t_eq > 380:
        r = prng.next()
        if r < 0.3: return VOLCANIC
        if r < 0.6: return BARREN
        return DESERT

    if hz['inner'] * 0.85 <= semi_major_au <= hz['outer'] * 1.15:
        r = prng.next()
        if r < 0.12: return BARREN
        if r < 0.22: return DESERT
        if r < 0.34: return ARID
        if r < 0.55: return TERRAN
        if r < 0.66: return OCEANIC
        if r < 0.74: return VOLCANIC
        if r < 0.80: return CARBON_WORLD
        if r < 0.88: return SUPER_EARTH
        return SUB_NEPTUNE

    if t_eq > 200:
        r = prng.next()
        if r < 0.25: return TUNDRA
        if r < 0.45: return ARID
        if r < 0.60: return DESERT
        if r < 0.75: return SUPER_EARTH
        return SUB_NEPTUNE

    if t_eq > 100:
        r = prng.next()
        if r < 0.35: return GLACIAL
        if r < 0.55: return TUNDRA
        if r < 0.70: return ICE_GIANT
        return SUB_NEPTUNE

    return GAS_GIANT if prng.next() < 0.55 else ICE_GIANT

# ── Main factory ──────────────────────────────────────────────────────────────

_MAX_VISUAL_SYSTEM_RADIUS_LY = 15.0


def generate_system(star: dict) -> dict:
    """Generates a complete planetary system from a star dict."""
    prng   = PRNG(star['systemSeed'])
    hz     = habitable_zone(star['luminositySolar'])
    count  = planet_count(prng, star)
    slots  = generate_orbital_slots(prng, count, star)

    # Per-system visual scale: cap so no system exceeds _MAX_VISUAL_SYSTEM_RADIUS_LY.
    # Normal Sun-like stars are unaffected; only massive/luminous stars are compressed.
    outer_au = hz['outer']
    if slots:
        outer_au = max(outer_au, slots[-1]['semiMajorAxisAU'])
    visual_scale = min(VISUAL_AU_TO_LY, _MAX_VISUAL_SYSTEM_RADIUS_LY / outer_au)

    planets = []
    for index, slot in enumerate(slots):
        t_eq       = equilibrium_temperature(star['luminositySolar'], slot['semiMajorAxisAU'])
        planet_type = _select_planet_type(prng, t_eq, slot['semiMajorAxisAU'], star)

        litho        = _generate_lithosphere(prng, planet_type)
        atmo         = _generate_atmosphere(prng, planet_type, litho)
        surface_temp = max(10, t_eq + atmo['greenhouseEffect'])
        hydro        = _generate_hydrosphere(prng, planet_type, surface_temp, litho, atmo)
        bio          = _generate_biosphere(prng, surface_temp, hydro, atmo)
        final_atmo   = _refine_atmosphere(atmo, bio)
        resources    = _generate_resources(prng, planet_type, litho, bio)
        habitability = _compute_habitability(litho, final_atmo, hydro, bio, surface_temp, star)

        angle  = slot['orbitalAngleRad']
        world_x = star['worldX'] + slot['semiMajorAxisAU'] * visual_scale * math.cos(angle)
        world_y = star['worldY'] + slot['semiMajorAxisAU'] * visual_scale * math.sin(angle)

        planets.append({
            'id':      f"{star['id']}:{index}",
            'name':    f"{star['name']} {roman_numeral(index)}",
            'starId':  star['id'],
            'index':   index,

            'semiMajorAxisAU':    slot['semiMajorAxisAU'],
            'eccentricity':       slot['eccentricity'],
            'orbitalPeriodYears': slot['orbitalPeriodYears'],
            'orbitalAngleRad':    slot['orbitalAngleRad'],
            'inHabitableZone':    slot['inHabitableZone'],

            'worldX': world_x,
            'worldY': world_y,

            'planetType':   planet_type,
            'surfaceTempK': surface_temp,

            'lithosphere':  litho,
            'atmosphere':   final_atmo,
            'hydrosphere':  hydro,
            'biosphere':    bio,
            'habitability': habitability,
            'resources':    resources,
            'terraforming': {
                'pressureDeltaAtm':  0,
                'temperatureDeltaK': 0,
                'waterCoverageDelta': 0,
                'activeProjects': [],
            },
        })

    return {
        'starId':     star['id'],
        'starWorldX': star['worldX'],
        'starWorldY': star['worldY'],
        'planets':    planets,
        'hzInnerAU':  hz['inner'],
        'hzOuterAU':  hz['outer'],
        'visualScale': visual_scale,
    }
