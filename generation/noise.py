"""
2D value noise + FBM.
Bit-exact port of src/math/noise.ts.
"""


def _hash_int(n: int) -> int:
    """xorshift-based integer hash."""
    n = ((n ^ (n >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    n = ((n ^ (n >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFFFFFF


def _lattice_value(ix: int, iy: int, seed: int) -> float:
    h = _hash_int(_hash_int(ix & 0xFFFFFFFF) ^ _hash_int(iy & 0xFFFFFFFF) ^ (seed & 0xFFFFFFFF))
    return h / 0x100000000


def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


class ValueNoise2D:
    def __init__(self, seed: int) -> None:
        self.seed = seed & 0xFFFFFFFF

    def sample(self, x: float, y: float) -> float:
        """Returns a value in [0, 1] at world position (x, y)."""
        import math
        ix = math.floor(x)
        iy = math.floor(y)
        fx = x - ix
        fy = y - iy

        tx = _smoothstep(fx)
        ty = _smoothstep(fy)

        v00 = _lattice_value(ix,     iy,     self.seed)
        v10 = _lattice_value(ix + 1, iy,     self.seed)
        v01 = _lattice_value(ix,     iy + 1, self.seed)
        v11 = _lattice_value(ix + 1, iy + 1, self.seed)

        top    = v00 + (v10 - v00) * tx
        bottom = v01 + (v11 - v01) * tx
        return top + (bottom - top) * ty

    def fbm(self, x: float, y: float, octaves: int, lacunarity: float = 2.0, gain: float = 0.5) -> float:
        """Fractional Brownian Motion — returns [0, 1]."""
        value = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0
        for _ in range(octaves):
            value    += self.sample(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= gain
            frequency *= lacunarity
        return value / max_value
