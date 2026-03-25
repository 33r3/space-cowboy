/**
 * Stellar spectral classification.
 * Frequencies based on real stellar population statistics.
 */

export enum SpectralClass {
  O = 'O',
  B = 'B',
  A = 'A',
  F = 'F',
  G = 'G',
  K = 'K',
  M = 'M',
  WhiteDwarf = 'WD',
  Giant = 'III',       // Luminosity class III (red/orange giants)
  Supergiant = 'Ia',   // Luminosity class Ia/Ib supergiants
}

export type LuminosityClass = 'Ia' | 'Ib' | 'II' | 'III' | 'IV' | 'V' | 'VI' | 'D'

/** Approximate fraction of all stars in the solar neighborhood */
const SPECTRAL_FREQUENCIES: Record<SpectralClass, number> = {
  [SpectralClass.M]:          0.7645,
  [SpectralClass.K]:          0.1210,
  [SpectralClass.G]:          0.0760,
  [SpectralClass.F]:          0.0295,
  [SpectralClass.A]:          0.0058,
  [SpectralClass.B]:          0.0013,
  [SpectralClass.O]:          0.0000033,
  [SpectralClass.WhiteDwarf]: 0.0010,  // Reduced — many real WDs are too dim to see; keeps gameplay variety
  [SpectralClass.Giant]:      0.0008,
  [SpectralClass.Supergiant]: 0.0001,
}

/** CDF entry for binary search */
interface CDFEntry {
  cumulative: number
  spectralClass: SpectralClass
}

// Build cumulative distribution function once at module load
const CDF: CDFEntry[] = (() => {
  const entries = Object.entries(SPECTRAL_FREQUENCIES) as [SpectralClass, number][]
  const total = entries.reduce((sum, [, f]) => sum + f, 0)
  let cumulative = 0
  return entries.map(([spectralClass, freq]) => {
    cumulative += freq / total
    return { cumulative, spectralClass }
  })
})()

/**
 * Sample a spectral class from the realistic frequency distribution.
 * @param rand A float in [0, 1)
 */
export function sampleSpectralClass(rand: number): SpectralClass {
  for (const entry of CDF) {
    if (rand < entry.cumulative) return entry.spectralClass
  }
  // Fallback (floating point rounding)
  return SpectralClass.M
}
