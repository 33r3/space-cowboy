import { ValueNoise2D } from '../math/noise'
import type { GalaxyConfig } from './GalaxyConfig'

/**
 * Computes the local stellar density at any point in the galaxy.
 * Returns a value in [0, 1] where:
 *   0 = void (no stars)
 *   1 = peak density (spiral arm core)
 *
 * Three additive components:
 *   1. Spiral arms (logarithmic spirals with Gaussian cross-section)
 *   2. Central bulge (circular Gaussian)
 *   3. Value noise perturbation (breaks mathematical symmetry into organic clumps)
 */
export class DensityField {
  private config: GalaxyConfig
  private noise: ValueNoise2D

  constructor(config: GalaxyConfig) {
    this.config = config
    this.noise = new ValueNoise2D(config.seed ^ 0xdeadbeef)
  }

  getDensity(worldX: number, worldY: number): number {
    const { config } = this
    const r = Math.sqrt(worldX * worldX + worldY * worldY)
    const maxR = config.galaxyRadiusLy

    // Hard cutoff outside the galaxy
    if (r > maxR * 1.1) return 0

    const theta = Math.atan2(worldY, worldX)
    const rNorm = r / maxR  // 0 at center, 1 at edge

    // ── Component 1: Spiral arms ───────────────────────────────────────────
    let armDensity = 0
    if (r > 0) {
      for (let i = 0; i < config.numArms; i++) {
        // Angle of the arm centerline at this radius (logarithmic spiral)
        const armBaseAngle = (2 * Math.PI * i) / config.numArms
        const armCenterAngle = armBaseAngle + config.armTightness * Math.log(r / 200 + 1)

        // Minimum angular distance from the arm centerline (wrap around 2π)
        let angularDist = Math.abs(((theta - armCenterAngle + Math.PI) % (2 * Math.PI)) - Math.PI)

        // Gaussian falloff from arm centerline
        const armContrib = Math.exp(-(angularDist * angularDist) / (2 * config.armWidth * config.armWidth))
        armDensity = Math.max(armDensity, armContrib)
      }
    } else {
      armDensity = 1
    }

    // Radial envelope: arms fade out toward edge and toward center
    // (stars exist in the disk region, not arbitrarily far out)
    const radialEnvelope = Math.exp(-Math.pow(rNorm, config.edgeFalloffExponent) * 3.5)
      * (1 - Math.exp(-rNorm * 8))  // inner cutoff (bulge takes over near center)

    armDensity *= radialEnvelope

    // ── Component 2: Central bulge ─────────────────────────────────────────
    const bulgeR = config.bulgeRadiusFraction * maxR
    const bulgeDensity = config.bulgeDensityMultiplier
      * Math.exp(-(r * r) / (2 * bulgeR * bulgeR))
      // Normalize so bulge peaks at ~1 relative to arm peaks
      / config.bulgeDensityMultiplier

    // ── Combine arms + bulge ───────────────────────────────────────────────
    let density = Math.max(armDensity, bulgeDensity * config.bulgeDensityMultiplier * 0.3)

    // Clamp before noise to avoid negative values
    density = Math.max(0, Math.min(1, density))

    // ── Component 3: Value noise perturbation ──────────────────────────────
    if (density > 0.001) {
      const nx = worldX / config.noiseScaleLy
      const ny = worldY / config.noiseScaleLy
      const noiseVal = this.noise.fbm(nx, ny, 4)  // [0, 1]
      // Convert to [-0.5, 0.5] then scale by amplitude
      const perturbation = (noiseVal - 0.5) * config.noiseAmplitude
      density = Math.max(0, Math.min(1, density + density * perturbation))
    }

    return density
  }
}
