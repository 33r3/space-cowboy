import type { PRNG } from '../math/prng'
import { SpectralClass, sampleSpectralClass } from './SpectralClass'
import type { LuminosityClass } from './SpectralClass'
import { MAIN_SEQUENCE, temperatureToColor, generateStarName } from './HRDiagram'
import type { StarData } from './StarProperties'

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

function luminosityClassForSpectral(sc: SpectralClass): LuminosityClass {
  switch (sc) {
    case SpectralClass.WhiteDwarf: return 'D'
    case SpectralClass.Giant:      return 'III'
    case SpectralClass.Supergiant: return 'Ia'
    default:                       return 'V'  // main sequence
  }
}

/**
 * Generates a single star's properties from a seeded PRNG.
 * All values are physically correlated following the H-R diagram.
 */
export function generateStar(
  prng: PRNG,
  worldX: number,
  worldY: number,
  chunkKey: string,
  index: number,
): StarData {
  const spectralClass = sampleSpectralClass(prng.next())
  const subclass = prng.nextInt(0, 9)

  const props = MAIN_SEQUENCE[spectralClass]

  // Interpolation position within the class range.
  // subclass 0 = hottest end, subclass 9 = coolest end.
  // Add Gaussian scatter (σ = 8% of range) so stars don't cluster on grid points.
  const baseT = subclass / 9
  const scatter = prng.nextGaussian() * 0.08
  const t = Math.max(0, Math.min(1, baseT + scatter))

  const temperatureK = Math.round(lerp(props.tempMax, props.tempMin, t))
  const massSolar    = lerp(props.massMax, props.massMin, t) * (1 + prng.nextGaussian() * 0.05)
  const lumSolar     = lerp(props.lumMax, props.lumMin, t) * Math.pow(2, prng.nextGaussian() * 0.15)
  const radiusSolar  = lerp(props.radiusMax, props.radiusMin, t) * (1 + prng.nextGaussian() * 0.05)

  const color = temperatureToColor(temperatureK)
  const luminosityClass = luminosityClassForSpectral(spectralClass)

  const name = generateStarName(prng.next(), prng.next(), prng.next())

  // System seed for deterministic planet generation later
  const systemSeed = Math.floor(prng.next() * 0x100000000)

  return {
    id: `${chunkKey}:${index}`,
    worldX,
    worldY,
    spectralClass,
    subclass,
    luminosityClass,
    massSolar:       Math.max(0.001, massSolar),
    luminositySolar: Math.max(0.00001, lumSolar),
    temperatureK,
    radiusSolar:     Math.max(0.005, radiusSolar),
    color,
    name,
    systemSeed,
  }
}
