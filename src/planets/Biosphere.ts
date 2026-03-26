import type { PRNG } from '../math/prng'
import { LifeStage, WaterState, AtmoComposition } from './PlanetData'
import type { Biosphere, Hydrosphere, Atmosphere } from './PlanetData'

/**
 * Generates a biosphere based on habitability preconditions.
 * Life requires: liquid water (or subsurface ocean), survivable temperature,
 * and a non-vacuum atmosphere.
 */
export function generateBiosphere(
  prng: PRNG,
  surfaceTempK: number,
  hydro: Hydrosphere,
  atmo: Atmosphere,
): Biosphere {
  // Hard requirements for abiogenesis
  const hasLiquidWater = hydro.liquidFraction > 0.01 || hydro.subsurfaceOcean
  const tempOk = surfaceTempK > 150 && surfaceTempK < 400
  const hasAtmo = atmo.pressure > 0.01 && atmo.composition !== AtmoComposition.None

  if (!hasLiquidWater || !tempOk || !hasAtmo) {
    return { stage: LifeStage.None, coverage: 0, oxygenContribution: 0 }
  }

  // Probability of life originating at all — generous for gameplay
  const lifeChance = 0.65
  if (prng.next() > lifeChance) {
    return { stage: LifeStage.None, coverage: 0, oxygenContribution: 0 }
  }

  // If life exists, determine max possible stage from conditions
  // Optimal conditions: 270–320 K, liquid ocean, moderate atmosphere
  const tempScore = gaussianScore(surfaceTempK, 290, 60)
  const waterScore = hydro.liquidFraction * hydro.waterCoverage
  const overallScore = tempScore * 0.6 + waterScore * 0.4

  // Determine stage (better conditions → higher stage)
  let stage: LifeStage
  const stageRoll = prng.next() * overallScore

  if (stageRoll > 0.7) {
    stage = LifeStage.ComplexLife
  } else if (stageRoll > 0.45) {
    stage = LifeStage.SimpleMulticellular
  } else if (stageRoll > 0.2) {
    stage = LifeStage.Microbial
  } else {
    stage = LifeStage.Prebiotic
  }

  // Coverage grows with stage complexity
  let coverage: number
  switch (stage) {
    case LifeStage.Prebiotic:          coverage = prng.nextFloat(0.0, 0.1); break
    case LifeStage.Microbial:          coverage = prng.nextFloat(0.1, 0.5); break
    case LifeStage.SimpleMulticellular:coverage = prng.nextFloat(0.3, 0.7); break
    case LifeStage.ComplexLife:        coverage = prng.nextFloat(0.5, 1.0); break
    default:                           coverage = 0
  }

  // O2 contribution: only photosynthetic/complex life produces significant O2
  let oxygenContribution = 0
  if (stage === LifeStage.SimpleMulticellular) {
    oxygenContribution = coverage * prng.nextFloat(0.05, 0.15)
  } else if (stage === LifeStage.ComplexLife) {
    oxygenContribution = coverage * prng.nextFloat(0.15, 0.22)
  }

  return {
    stage,
    coverage,
    oxygenContribution: Math.min(0.21, oxygenContribution),
  }
}

function gaussianScore(x: number, mean: number, sigma: number): number {
  const d = (x - mean) / sigma
  return Math.exp(-0.5 * d * d)
}
