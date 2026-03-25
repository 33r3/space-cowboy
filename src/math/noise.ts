/**
 * Fast 2D value noise for density field perturbation.
 * Uses integer lattice hashing + bilinear interpolation with smoothstep.
 * Not tileable, but that's fine — the galaxy is effectively infinite.
 */

function hashInt(n: number): number {
  // Simple integer hash (xorshift-based)
  n = ((n ^ (n >>> 16)) * 0x45d9f3b) >>> 0
  n = ((n ^ (n >>> 16)) * 0x45d9f3b) >>> 0
  n = (n ^ (n >>> 16)) >>> 0
  return n
}

function latticeValue(ix: number, iy: number, seed: number): number {
  // Combine ix, iy, seed into a single hash → float [0,1)
  const h = hashInt(hashInt(ix >>> 0) ^ hashInt(iy >>> 0) ^ seed)
  return h / 0x100000000
}

function smoothstep(t: number): number {
  return t * t * (3 - 2 * t)
}

export class ValueNoise2D {
  private seed: number

  constructor(seed: number) {
    this.seed = seed >>> 0
  }

  /** Returns a value in [0, 1] at world position (x, y) */
  sample(x: number, y: number): number {
    const ix = Math.floor(x)
    const iy = Math.floor(y)
    const fx = x - ix
    const fy = y - iy

    const tx = smoothstep(fx)
    const ty = smoothstep(fy)

    const v00 = latticeValue(ix,     iy,     this.seed)
    const v10 = latticeValue(ix + 1, iy,     this.seed)
    const v01 = latticeValue(ix,     iy + 1, this.seed)
    const v11 = latticeValue(ix + 1, iy + 1, this.seed)

    // Bilinear interpolation
    const top    = v00 + (v10 - v00) * tx
    const bottom = v01 + (v11 - v01) * tx
    return top + (bottom - top) * ty
  }

  /**
   * Fractional Brownian Motion — multiple octaves of noise for more natural-looking features.
   * Returns [0, 1].
   */
  fbm(x: number, y: number, octaves: number, lacunarity = 2.0, gain = 0.5): number {
    let value = 0
    let amplitude = 1
    let frequency = 1
    let maxValue = 0
    for (let i = 0; i < octaves; i++) {
      value += this.sample(x * frequency, y * frequency) * amplitude
      maxValue += amplitude
      amplitude *= gain
      frequency *= lacunarity
    }
    return value / maxValue
  }
}
