"""
Star generation — HR diagram, spectral class sampling, name generation.
Port of src/stars/SpectralClass.ts, HRDiagram.ts, StarFactory.ts.
"""
import math
from .prng import PRNG

# ── Spectral classes ──────────────────────────────────────────────────────────

SPECTRAL_CLASSES = ['M', 'K', 'G', 'F', 'A', 'B', 'O', 'WD', 'III', 'Ia']

SPECTRAL_FREQUENCIES = {
    'M':   0.7645,
    'K':   0.1210,
    'G':   0.0760,
    'F':   0.0295,
    'A':   0.0058,
    'B':   0.0013,
    'O':   0.0000033,
    'WD':  0.0010,
    'III': 0.0008,
    'Ia':  0.0001,
}

# Build CDF once
_total = sum(SPECTRAL_FREQUENCIES.values())
_CDF: list[tuple[float, str]] = []
_cum = 0.0
for _sc, _freq in SPECTRAL_FREQUENCIES.items():
    _cum += _freq / _total
    _CDF.append((_cum, _sc))


def sample_spectral_class(rand: float) -> str:
    for cumulative, sc in _CDF:
        if rand < cumulative:
            return sc
    return 'M'


# ── HR diagram tables ─────────────────────────────────────────────────────────

MAIN_SEQUENCE = {
    'O':   dict(temp_min=30_000, temp_max=60_000, mass_min=16,    mass_max=90,    lum_min=30_000,  lum_max=1_000_000, radius_min=6.6,   radius_max=15),
    'B':   dict(temp_min=10_000, temp_max=30_000, mass_min=2.1,   mass_max=16,    lum_min=25,      lum_max=30_000,    radius_min=1.8,   radius_max=6.6),
    'A':   dict(temp_min=7_500,  temp_max=10_000, mass_min=1.4,   mass_max=2.1,   lum_min=5,       lum_max=25,        radius_min=1.4,   radius_max=1.8),
    'F':   dict(temp_min=6_000,  temp_max=7_500,  mass_min=1.04,  mass_max=1.4,   lum_min=1.5,     lum_max=5,         radius_min=1.15,  radius_max=1.4),
    'G':   dict(temp_min=5_200,  temp_max=6_000,  mass_min=0.8,   mass_max=1.04,  lum_min=0.6,     lum_max=1.5,       radius_min=0.96,  radius_max=1.15),
    'K':   dict(temp_min=3_700,  temp_max=5_200,  mass_min=0.45,  mass_max=0.8,   lum_min=0.08,    lum_max=0.6,       radius_min=0.7,   radius_max=0.96),
    'M':   dict(temp_min=2_400,  temp_max=3_700,  mass_min=0.08,  mass_max=0.45,  lum_min=0.0001,  lum_max=0.08,      radius_min=0.1,   radius_max=0.7),
    'III': dict(temp_min=3_500,  temp_max=5_000,  mass_min=1.5,   mass_max=8,     lum_min=10,      lum_max=1_000,     radius_min=10,    radius_max=100),
    'Ia':  dict(temp_min=4_000,  temp_max=20_000, mass_min=8,     mass_max=50,    lum_min=10_000,  lum_max=500_000,   radius_min=30,    radius_max=1_500),
    'WD':  dict(temp_min=8_000,  temp_max=40_000, mass_min=0.17,  mass_max=1.33,  lum_min=0.0001,  lum_max=0.005,     radius_min=0.008, radius_max=0.02),
}

LUMINOSITY_CLASS = {
    'WD':  'D',
    'III': 'III',
    'Ia':  'Ia',
}


def _luminosity_class(sc: str) -> str:
    return LUMINOSITY_CLASS.get(sc, 'V')


# ── Temperature → color ───────────────────────────────────────────────────────

def temperature_to_color(temp_k: float) -> str:
    t = max(1000, min(40000, temp_k)) / 100

    if t <= 66:
        r = 255
    else:
        r = 329.698727446 * math.pow(t - 60, -0.1332047592)
        r = max(0, min(255, r))

    if t <= 66:
        g = 99.4708025861 * math.log(t) - 161.1195681661
        g = max(0, min(255, g))
    else:
        g = 288.1221695283 * math.pow(t - 60, -0.0755148492)
        g = max(0, min(255, g))

    if t >= 66:
        b = 255
    elif t <= 19:
        b = 0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307
        b = max(0, min(255, b))

    ri = round(r)
    gi = round(g)
    bi = round(b)
    return f'#{ri:02x}{gi:02x}{bi:02x}'


# ── Name generation ───────────────────────────────────────────────────────────

_PREFIXES = [
    'Al', 'Ar', 'Be', 'Ca', 'De', 'El', 'En', 'Er', 'Et', 'Ga',
    'He', 'Il', 'Ka', 'Ko', 'La', 'Le', 'Ma', 'Me', 'Mi', 'Na',
    'No', 'Nu', 'Or', 'Os', 'Pe', 'Pr', 'Ra', 'Ri', 'Ro', 'Sa',
    'Se', 'Si', 'So', 'Su', 'Ta', 'Te', 'Ti', 'To', 'Ul', 'Ur',
    'Ve', 'Vi', 'Vo', 'Xa', 'Xe', 'Yr', 'Za', 'Ze', 'Zi', 'Zu',
]
_MIDDLES = [
    'al', 'an', 'ar', 'as', 'at', 'en', 'er', 'es', 'et', 'il',
    'in', 'ir', 'is', 'on', 'or', 'os', 'ul', 'un', 'ur', 'us',
]
_SUFFIXES = [
    'a', 'ae', 'ai', 'an', 'ar', 'as', 'e', 'ei', 'en', 'er',
    'es', 'i', 'ia', 'iae', 'ian', 'iel', 'ii', 'in', 'is', 'ix',
    'o', 'oi', 'on', 'or', 'os', 'u', 'um', 'un', 'us', 'ux',
]


def _generate_star_name(rand1: float, rand2: float, rand3: float) -> str:
    prefix = _PREFIXES[int(rand1 * len(_PREFIXES))]
    use_middle = rand2 > 0.4
    middle = _MIDDLES[int(rand2 * len(_MIDDLES))] if use_middle else ''
    suffix = _SUFFIXES[int(rand3 * len(_SUFFIXES))]
    return prefix + middle + suffix


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ── Star generation ───────────────────────────────────────────────────────────

def generate_star(prng: PRNG, world_x: float, world_y: float, chunk_key: str, index: int) -> dict:
    """Generates a single star dict. Mirrors generateStar() in TypeScript exactly."""
    sc = sample_spectral_class(prng.next())
    subclass = prng.next_int(0, 9)

    props = MAIN_SEQUENCE[sc]

    base_t = subclass / 9
    scatter = prng.next_gaussian() * 0.08
    t = max(0.0, min(1.0, base_t + scatter))

    temperature_k = round(_lerp(props['temp_max'], props['temp_min'], t))
    mass_solar    = _lerp(props['mass_max'],   props['mass_min'],   t) * (1 + prng.next_gaussian() * 0.05)
    lum_solar     = _lerp(props['lum_max'],    props['lum_min'],    t) * math.pow(2, prng.next_gaussian() * 0.15)
    radius_solar  = _lerp(props['radius_max'], props['radius_min'], t) * (1 + prng.next_gaussian() * 0.05)

    color = temperature_to_color(temperature_k)
    luminosity_class = _luminosity_class(sc)

    name = _generate_star_name(prng.next(), prng.next(), prng.next())

    system_seed = int(prng.next() * 0x100000000)

    return {
        'id':               f'{chunk_key}:{index}',
        'worldX':           world_x,
        'worldY':           world_y,
        'spectralClass':    sc,
        'subclass':         subclass,
        'luminosityClass':  luminosity_class,
        'massSolar':        max(0.001, mass_solar),
        'luminositySolar':  max(0.00001, lum_solar),
        'temperatureK':     temperature_k,
        'radiusSolar':      max(0.005, radius_solar),
        'color':            color,
        'name':             name,
        'systemSeed':       system_seed,
    }
