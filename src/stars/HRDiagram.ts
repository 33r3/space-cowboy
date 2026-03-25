import { SpectralClass } from './SpectralClass'

export interface StarClassProperties {
  tempMin: number
  tempMax: number
  massMin: number
  massMax: number
  lumMin: number
  lumMax: number
  radiusMin: number
  radiusMax: number
}

/**
 * Main sequence (luminosity class V) properties per spectral class.
 * Ranges cover the span of the subclass (0–9) variation.
 */
export const MAIN_SEQUENCE: Record<SpectralClass, StarClassProperties> = {
  [SpectralClass.O]: {
    tempMin: 30_000, tempMax: 60_000,
    massMin: 16,     massMax: 90,
    lumMin:  30_000, lumMax:  1_000_000,
    radiusMin: 6.6,  radiusMax: 15,
  },
  [SpectralClass.B]: {
    tempMin: 10_000, tempMax: 30_000,
    massMin: 2.1,    massMax: 16,
    lumMin:  25,     lumMax:  30_000,
    radiusMin: 1.8,  radiusMax: 6.6,
  },
  [SpectralClass.A]: {
    tempMin: 7_500,  tempMax: 10_000,
    massMin: 1.4,    massMax: 2.1,
    lumMin:  5,      lumMax:  25,
    radiusMin: 1.4,  radiusMax: 1.8,
  },
  [SpectralClass.F]: {
    tempMin: 6_000,  tempMax: 7_500,
    massMin: 1.04,   massMax: 1.4,
    lumMin:  1.5,    lumMax:  5,
    radiusMin: 1.15, radiusMax: 1.4,
  },
  [SpectralClass.G]: {
    tempMin: 5_200,  tempMax: 6_000,
    massMin: 0.8,    massMax: 1.04,
    lumMin:  0.6,    lumMax:  1.5,
    radiusMin: 0.96, radiusMax: 1.15,
  },
  [SpectralClass.K]: {
    tempMin: 3_700,  tempMax: 5_200,
    massMin: 0.45,   massMax: 0.8,
    lumMin:  0.08,   lumMax:  0.6,
    radiusMin: 0.7,  radiusMax: 0.96,
  },
  [SpectralClass.M]: {
    tempMin: 2_400,  tempMax: 3_700,
    massMin: 0.08,   massMax: 0.45,
    lumMin:  0.0001, lumMax:  0.08,
    radiusMin: 0.1,  radiusMax: 0.7,
  },
  // Giants (luminosity class III) — inflated
  [SpectralClass.Giant]: {
    tempMin: 3_500,  tempMax: 5_000,
    massMin: 1.5,    massMax: 8,
    lumMin:  10,     lumMax:  1_000,
    radiusMin: 10,   radiusMax: 100,
  },
  // Supergiants (class Ia/Ib) — massive and luminous
  [SpectralClass.Supergiant]: {
    tempMin: 4_000,  tempMax: 20_000,
    massMin: 8,      massMax: 50,
    lumMin:  10_000, lumMax:  500_000,
    radiusMin: 30,   radiusMax: 1_500,
  },
  // White dwarfs — tiny, dim, but hot
  [SpectralClass.WhiteDwarf]: {
    tempMin: 8_000,  tempMax: 40_000,
    massMin: 0.17,   massMax: 1.33,
    lumMin:  0.0001, lumMax:  0.005,
    radiusMin: 0.008, radiusMax: 0.02,
  },
}

// ─── Temperature → Color ─────────────────────────────────────────────────────

/**
 * Approximate blackbody color from temperature using polynomial fits.
 * Returns a CSS hex color string.
 * Based on Tanner Helland's algorithm (public domain).
 */
export function temperatureToColor(tempK: number): string {
  const t = Math.max(1000, Math.min(40000, tempK)) / 100

  let r: number, g: number, b: number

  // Red
  if (t <= 66) {
    r = 255
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592)
    r = Math.max(0, Math.min(255, r))
  }

  // Green
  if (t <= 66) {
    g = 99.4708025861 * Math.log(t) - 161.1195681661
    g = Math.max(0, Math.min(255, g))
  } else {
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492)
    g = Math.max(0, Math.min(255, g))
  }

  // Blue
  if (t >= 66) {
    b = 255
  } else if (t <= 19) {
    b = 0
  } else {
    b = 138.5177312231 * Math.log(t - 10) - 305.0447927307
    b = Math.max(0, Math.min(255, b))
  }

  const ri = Math.round(r)
  const gi = Math.round(g)
  const bi = Math.round(b)
  return `#${ri.toString(16).padStart(2, '0')}${gi.toString(16).padStart(2, '0')}${bi.toString(16).padStart(2, '0')}`
}

// ─── Name generation ─────────────────────────────────────────────────────────

const NAME_PREFIXES = [
  'Al', 'Ar', 'Be', 'Ca', 'De', 'El', 'En', 'Er', 'Et', 'Ga',
  'He', 'Il', 'Ka', 'Ko', 'La', 'Le', 'Ma', 'Me', 'Mi', 'Na',
  'No', 'Nu', 'Or', 'Os', 'Pe', 'Pr', 'Ra', 'Ri', 'Ro', 'Sa',
  'Se', 'Si', 'So', 'Su', 'Ta', 'Te', 'Ti', 'To', 'Ul', 'Ur',
  'Ve', 'Vi', 'Vo', 'Xa', 'Xe', 'Yr', 'Za', 'Ze', 'Zi', 'Zu',
]

const NAME_MIDDLES = [
  'al', 'an', 'ar', 'as', 'at', 'en', 'er', 'es', 'et', 'il',
  'in', 'ir', 'is', 'on', 'or', 'os', 'ul', 'un', 'ur', 'us',
]

const NAME_SUFFIXES = [
  'a', 'ae', 'ai', 'an', 'ar', 'as', 'e', 'ei', 'en', 'er',
  'es', 'i', 'ia', 'iae', 'ian', 'iel', 'ii', 'in', 'is', 'ix',
  'o', 'oi', 'on', 'or', 'os', 'u', 'um', 'un', 'us', 'ux',
]

export function generateStarName(rand1: number, rand2: number, rand3: number): string {
  const prefix = NAME_PREFIXES[Math.floor(rand1 * NAME_PREFIXES.length)] ?? 'Al'
  const useMiddle = rand2 > 0.4
  const middle = useMiddle
    ? (NAME_MIDDLES[Math.floor(rand2 * NAME_MIDDLES.length)] ?? 'en')
    : ''
  const suffix = NAME_SUFFIXES[Math.floor(rand3 * NAME_SUFFIXES.length)] ?? 'a'
  return prefix + middle + suffix
}
