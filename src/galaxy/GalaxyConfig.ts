export interface GalaxyConfig {
  /** Master seed for all procedural generation */
  seed: number

  /** Radius of the galaxy in light-years */
  galaxyRadiusLy: number

  /** Number of spiral arms */
  numArms: number

  /**
   * Controls how tightly wound the spiral arms are.
   * Higher = more tightly wound (arms wrap more times).
   */
  armTightness: number

  /**
   * Angular half-width of each arm in radians.
   * Controls how wide/diffuse the arms appear.
   */
  armWidth: number

  /** Radius of the central bulge as a fraction of galaxyRadiusLy */
  bulgeRadiusFraction: number

  /** How much denser the bulge is relative to arm density */
  bulgeDensityMultiplier: number

  /** Edge of the galaxy falloff steepness */
  edgeFalloffExponent: number

  /** Scale of the noise perturbation in light-years */
  noiseScaleLy: number

  /** Amplitude of noise perturbation (0 = no perturbation, 1 = full) */
  noiseAmplitude: number

  /** Side length of each chunk in light-years */
  chunkSizeLy: number

  /** Maximum stars that can appear in a single chunk (at peak density) */
  maxStarsPerChunk: number
}

export const DEFAULT_GALAXY_CONFIG: GalaxyConfig = {
  seed:                    42,
  galaxyRadiusLy:          50_000,
  numArms:                 4,
  armTightness:            0.30,
  armWidth:                0.38,
  bulgeRadiusFraction:     0.10,
  bulgeDensityMultiplier:  3.5,
  edgeFalloffExponent:     2.5,
  noiseScaleLy:            3_000,
  noiseAmplitude:          0.55,
  chunkSizeLy:             200,
  maxStarsPerChunk:        40,
}
