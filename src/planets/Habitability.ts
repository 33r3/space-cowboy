import { AtmoComposition, HabitabilityCategory, LifeStage } from './PlanetData'
import type { HabitabilityScore, Lithosphere, Atmosphere, Hydrosphere, Biosphere } from './PlanetData'
import type { StarData } from '../stars/StarProperties'
import { SpectralClass } from '../stars/SpectralClass'

function gaussianScore(x: number, mean: number, sigma: number): number {
  const d = (x - mean) / sigma
  return Math.exp(-0.5 * d * d)
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

function toCategory(total: number): HabitabilityCategory {
  if (total <= 10) return HabitabilityCategory.Lethal
  if (total <= 25) return HabitabilityCategory.Hostile
  if (total <= 45) return HabitabilityCategory.Marginal
  if (total <= 65) return HabitabilityCategory.Habitable
  if (total <= 80) return HabitabilityCategory.Comfortable
  return HabitabilityCategory.Optimal
}

export function computeHabitability(
  litho: Lithosphere,
  atmo: Atmosphere,
  hydro: Hydrosphere,
  bio: Biosphere,
  surfaceTempK: number,
  star: StarData,
): HabitabilityScore {
  // ── Temperature score ──────────────────────────────────────────────────────
  // Gaussian peak at 293 K (20°C), comfortable range 240–340 K
  const temperature = gaussianScore(surfaceTempK, 293, 55)

  // ── Atmosphere score ───────────────────────────────────────────────────────
  let atmosphere: number
  if (atmo.breathable) {
    atmosphere = clamp(1.0 - Math.abs(atmo.pressure - 1.0) * 0.3, 0.5, 1.0)
  } else if (atmo.composition === AtmoComposition.None) {
    atmosphere = 0
  } else if (atmo.toxicity < 0.3 && atmo.pressure >= 0.1 && atmo.pressure <= 3.0) {
    atmosphere = 0.3  // survivable with basic life support
  } else {
    atmosphere = clamp(0.15 - atmo.toxicity * 0.15, 0, 0.15)
  }

  // ── Gravity score ──────────────────────────────────────────────────────────
  // Human tolerance: comfortable 0.4–1.5 g, survivable down to 0.15 g and up to 2.5 g
  let gravity: number
  const g = litho.gravityG
  if (g < 0.15 || g > 3.0) {
    gravity = 0
  } else if (g >= 0.4 && g <= 1.5) {
    gravity = gaussianScore(g, 1.0, 0.4)
  } else {
    gravity = 0.2 * gaussianScore(g, 1.0, 1.0)
  }

  // ── Radiation score ────────────────────────────────────────────────────────
  // Determined by magnetic field + atmospheric shielding + stellar radiation
  const atmosphericShielding = clamp(atmo.pressure / 1.0, 0, 1)
  const magneticShielding    = litho.magneticField
  const shielding            = clamp(magneticShielding * 0.5 + atmosphericShielding * 0.5, 0, 1)

  // Stars with high UV/X-ray output reduce radiation score
  let stellarRadiation = 1.0
  if (star.spectralClass === SpectralClass.O) stellarRadiation = 0.1
  else if (star.spectralClass === SpectralClass.B) stellarRadiation = 0.3
  else if (star.spectralClass === SpectralClass.A) stellarRadiation = 0.6
  else if (star.spectralClass === SpectralClass.M) stellarRadiation = 0.8  // M-dwarfs flare, but HZ is close

  const radiation = shielding * stellarRadiation

  // ── Water score ────────────────────────────────────────────────────────────
  const liquidWater = hydro.liquidFraction * hydro.waterCoverage
  let water: number
  if (liquidWater > 0.2) {
    water = 1.0
  } else if (liquidWater > 0.01) {
    water = 0.5 + liquidWater * 2.5
  } else if (hydro.subsurfaceOcean) {
    water = 0.4
  } else if (hydro.iceCoverage > 0.1) {
    water = 0.1
  } else {
    water = 0
  }

  // ── Biosphere score ────────────────────────────────────────────────────────
  let biosphere: number
  switch (bio.stage) {
    case LifeStage.None:               biosphere = 0.05; break   // slight bonus — at least it hasn't been hostile
    case LifeStage.Prebiotic:          biosphere = 0.1;  break
    case LifeStage.Microbial:          biosphere = 0.2;  break
    case LifeStage.SimpleMulticellular:biosphere = 0.5;  break
    case LifeStage.ComplexLife:        biosphere = 0.8;  break
    default:                           biosphere = 0
  }

  // ── Weighted total ─────────────────────────────────────────────────────────
  const total = (
    temperature * 0.25 +
    atmosphere  * 0.25 +
    gravity     * 0.15 +
    radiation   * 0.15 +
    water       * 0.15 +
    biosphere   * 0.05
  ) * 100

  return {
    total:       clamp(Math.round(total), 0, 100),
    temperature: clamp(temperature, 0, 1),
    atmosphere:  clamp(atmosphere, 0, 1),
    gravity:     clamp(gravity, 0, 1),
    radiation:   clamp(radiation, 0, 1),
    water:       clamp(water, 0, 1),
    biosphere:   clamp(biosphere, 0, 1),
    category:    toCategory(total),
  }
}
