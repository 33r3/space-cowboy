/**
 * Seeded PRNG using mulberry32 algorithm.
 * Deterministic: same seed always produces the same sequence.
 */
export class PRNG {
  private state: number

  constructor(seed: number) {
    this.state = seed >>> 0
  }

  /** Returns a float in [0, 1) */
  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0
    let t = this.state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 0x100000000
  }

  nextFloat(min: number, max: number): number {
    return min + this.next() * (max - min)
  }

  nextInt(min: number, max: number): number {
    return Math.floor(this.nextFloat(min, max + 1))
  }

  pick<T>(arr: readonly T[]): T {
    const item = arr[Math.floor(this.next() * arr.length)]
    if (item === undefined) throw new Error('pick called on empty array')
    return item
  }

  /** Box-Muller transform — returns a standard normal (mean=0, σ=1) sample */
  nextGaussian(): number {
    const u1 = this.next()
    const u2 = this.next()
    // Avoid log(0)
    const safe = u1 < 1e-10 ? 1e-10 : u1
    return Math.sqrt(-2 * Math.log(safe)) * Math.cos(2 * Math.PI * u2)
  }

  /** Gaussian sample clamped to [min, max] with given mean and standard deviation */
  nextGaussianClamped(mean: number, stddev: number, min: number, max: number): number {
    const raw = mean + this.nextGaussian() * stddev
    return Math.max(min, Math.min(max, raw))
  }
}

// ─── Wang hash for chunk seed derivation ────────────────────────────────────

function wangHash(n: number): number {
  n = ((n ^ 61) ^ (n >>> 16)) >>> 0
  n = Math.imul(n, 9) >>> 0
  n = (n ^ (n >>> 4)) >>> 0
  n = Math.imul(n, 0x27d4eb2d) >>> 0
  n = (n ^ (n >>> 15)) >>> 0
  return n
}

/**
 * Derives a deterministic seed for a specific chunk from the galaxy seed.
 * Two different (cx, cy) pairs always produce different seeds.
 */
export function chunkSeed(galaxySeed: number, cx: number, cy: number): number {
  // Map negative coords to unique positive integers before hashing
  const ux = cx < 0 ? -2 * cx - 1 : 2 * cx
  const uy = cy < 0 ? -2 * cy - 1 : 2 * cy
  let h = wangHash(galaxySeed >>> 0)
  h = wangHash(h ^ wangHash(ux >>> 0))
  h = wangHash(h ^ wangHash(uy >>> 0))
  return h >>> 0
}
