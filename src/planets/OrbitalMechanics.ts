import type { PRNG } from '../math/prng'
import { SpectralClass } from '../stars/SpectralClass'
import type { StarData } from '../stars/StarProperties'

export interface OrbitalSlot {
  semiMajorAxisAU: number
  eccentricity: number
  orbitalPeriodYears: number
  orbitalAngleRad: number
  inHabitableZone: boolean
}

// ─── Habitable Zone ───────────────────────────────────────────────────────────

/**
 * Kopparapu et al. simplified conservative habitable zone.
 * Returns inner and outer edges in AU.
 */
export function habitableZone(luminositySolar: number): { inner: number; outer: number } {
  return {
    inner: Math.sqrt(luminositySolar / 1.1),
    outer: Math.sqrt(luminositySolar / 0.36),
  }
}

// ─── Equilibrium Temperature ──────────────────────────────────────────────────

/**
 * Stefan-Boltzmann equilibrium temperature with Bond albedo = 0.3.
 * Returns surface temperature in Kelvin before greenhouse effect.
 */
export function equilibriumTemperature(luminositySolar: number, semiMajorAxisAU: number): number {
  return 278 * Math.pow(luminositySolar, 0.25) / Math.sqrt(semiMajorAxisAU)
}

// ─── Planet Count ─────────────────────────────────────────────────────────────

export function planetCount(prng: PRNG, star: StarData): number {
  let min: number, max: number
  switch (star.spectralClass) {
    case SpectralClass.O:
    case SpectralClass.Supergiant:
      min = 0; max = 3; break
    case SpectralClass.B:
      min = 1; max = 5; break
    case SpectralClass.A:
      min = 2; max = 6; break
    case SpectralClass.F:
    case SpectralClass.G:
      min = 4; max = 9; break
    case SpectralClass.K:
      min = 3; max = 8; break
    case SpectralClass.M:
      min = 3; max = 7; break
    case SpectralClass.Giant:
      min = 0; max = 4; break
    case SpectralClass.WhiteDwarf:
      min = 0; max = 2; break
    default:
      min = 2; max = 6;
  }
  return prng.nextInt(min, max)
}

// ─── Orbital Slot Generation ──────────────────────────────────────────────────

/**
 * Generates orbital parameters for `count` planets around a star.
 * Uses a modified Titius-Bode spacing: each successive orbit is 1.4–2.2×
 * the previous, starting from a fraction of the inner HZ edge.
 */
export function generateOrbitalSlots(
  prng: PRNG,
  count: number,
  star: StarData,
): OrbitalSlot[] {
  if (count === 0) return []

  const hz = habitableZone(star.luminositySolar)

  // First planet distance: 0.1–0.5 × inner HZ edge (scaled for very bright stars)
  const firstAU = Math.max(0.04, hz.inner * prng.nextFloat(0.1, 0.5))

  const slots: OrbitalSlot[] = []
  let prevAU = firstAU

  for (let i = 0; i < count; i++) {
    const au = i === 0 ? firstAU : prevAU * prng.nextFloat(1.4, 2.2)
    const ecc = prng.nextFloat(0, 0.15)  // modest eccentricity by default
    // Kepler's 3rd law: T² = a³ / M_star → T = sqrt(a³ / M)
    const period = Math.sqrt((au * au * au) / star.massSolar)
    const angle = prng.nextFloat(0, Math.PI * 2)
    const inHz = au >= hz.inner && au <= hz.outer

    slots.push({
      semiMajorAxisAU: au,
      eccentricity: ecc,
      orbitalPeriodYears: period,
      orbitalAngleRad: angle,
      inHabitableZone: inHz,
    })

    prevAU = au
  }

  return slots
}

// ─── Roman numeral helper ─────────────────────────────────────────────────────

const ROMAN = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']

export function romanNumeral(n: number): string {
  return ROMAN[n] ?? String(n + 1)
}
