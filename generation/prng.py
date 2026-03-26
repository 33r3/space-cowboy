"""
Seeded PRNG using mulberry32 algorithm.
Bit-exact port of src/math/prng.ts — uses & 0xFFFFFFFF instead of >>> 0.
"""
import math


def _imul(a: int, b: int) -> int:
    """32-bit integer multiplication (Math.imul equivalent)."""
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


class PRNG:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> float:
        """Returns a float in [0, 1)."""
        self.state = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.state
        t = _imul(t ^ (t >> 15), t | 1)
        t = (t ^ (t + _imul(t ^ ((t >> 7) & 0xFFFFFFFF), t | 61))) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 0x100000000

    def next_float(self, min_val: float, max_val: float) -> float:
        return min_val + self.next() * (max_val - min_val)

    def next_int(self, min_val: int, max_val: int) -> int:
        return int(self.next_float(min_val, max_val + 1))

    def pick(self, arr: list):
        idx = int(self.next() * len(arr))
        return arr[idx]

    def next_gaussian(self) -> float:
        """Box-Muller transform — standard normal (mean=0, σ=1)."""
        u1 = self.next()
        u2 = self.next()
        safe = u1 if u1 >= 1e-10 else 1e-10
        return math.sqrt(-2 * math.log(safe)) * math.cos(2 * math.pi * u2)

    def next_gaussian_clamped(self, mean: float, stddev: float, min_val: float, max_val: float) -> float:
        raw = mean + self.next_gaussian() * stddev
        return max(min_val, min(max_val, raw))


# ── Wang hash for chunk seed derivation ──────────────────────────────────────

def wang_hash(n: int) -> int:
    n = ((n ^ 61) ^ (n >> 16)) & 0xFFFFFFFF
    n = (n * 9) & 0xFFFFFFFF
    n = (n ^ (n >> 4)) & 0xFFFFFFFF
    n = (n * 0x27D4EB2D) & 0xFFFFFFFF
    return (n ^ (n >> 15)) & 0xFFFFFFFF


def chunk_seed(galaxy_seed: int, cx: int, cy: int) -> int:
    """Derives a deterministic seed for a specific chunk from the galaxy seed."""
    ux = (-2 * cx - 1) if cx < 0 else (2 * cx)
    uy = (-2 * cy - 1) if cy < 0 else (2 * cy)
    h = wang_hash(galaxy_seed & 0xFFFFFFFF)
    h = wang_hash(h ^ wang_hash(ux & 0xFFFFFFFF))
    h = wang_hash(h ^ wang_hash(uy & 0xFFFFFFFF))
    return h
