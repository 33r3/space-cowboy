"""
Orbital mechanics — habitable zone, planet count, orbital slots, equilibrium temp.
Port of src/planets/OrbitalMechanics.ts.
"""
import math
from .prng import PRNG

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']


def roman_numeral(n: int) -> str:
    if 0 <= n < len(ROMAN):
        return ROMAN[n]
    return str(n + 1)


def habitable_zone(luminosity_solar: float) -> dict:
    """Kopparapu et al. simplified conservative habitable zone. Returns AU."""
    return {
        'inner': math.sqrt(luminosity_solar / 1.1),
        'outer': math.sqrt(luminosity_solar / 0.36),
    }


def equilibrium_temperature(luminosity_solar: float, semi_major_au: float) -> float:
    """Stefan-Boltzmann equilibrium temperature (Bond albedo = 0.3), in Kelvin."""
    return 278 * math.pow(luminosity_solar, 0.25) / math.sqrt(semi_major_au)


def planet_count(prng: PRNG, star: dict) -> int:
    sc = star['spectralClass']
    if sc in ('O', 'Ia'):
        min_c, max_c = 0, 3
    elif sc == 'B':
        min_c, max_c = 1, 5
    elif sc == 'A':
        min_c, max_c = 2, 6
    elif sc in ('F', 'G'):
        min_c, max_c = 4, 9
    elif sc == 'K':
        min_c, max_c = 3, 8
    elif sc == 'M':
        min_c, max_c = 3, 7
    elif sc == 'III':
        min_c, max_c = 0, 4
    elif sc == 'WD':
        min_c, max_c = 0, 2
    else:
        min_c, max_c = 2, 6
    return prng.next_int(min_c, max_c)


def generate_orbital_slots(prng: PRNG, count: int, star: dict) -> list[dict]:
    """Generates orbital parameters for `count` planets using modified Titius-Bode spacing."""
    if count == 0:
        return []

    hz = habitable_zone(star['luminositySolar'])
    first_au = max(0.04, hz['inner'] * prng.next_float(0.1, 0.5))

    slots = []
    prev_au = first_au

    for i in range(count):
        au = first_au if i == 0 else prev_au * prng.next_float(1.4, 2.2)
        ecc = prng.next_float(0, 0.15)
        period = math.sqrt((au ** 3) / star['massSolar'])
        angle = prng.next_float(0, math.pi * 2)
        in_hz = hz['inner'] <= au <= hz['outer']

        slots.append({
            'semiMajorAxisAU':    au,
            'eccentricity':       ecc,
            'orbitalPeriodYears': period,
            'orbitalAngleRad':    angle,
            'inHabitableZone':    in_hz,
        })
        prev_au = au

    return slots
