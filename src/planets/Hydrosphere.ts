import type { PRNG } from '../math/prng'
import { PlanetType, WaterState } from './PlanetData'
import type { Hydrosphere, Atmosphere, Lithosphere } from './PlanetData'

export function generateHydrosphere(
  prng: PRNG,
  type: PlanetType,
  surfaceTempK: number,
  litho: Lithosphere,
  atmo: Atmosphere,
): Hydrosphere {
  // Giants and gas-dominated worlds have no meaningful surface hydrosphere
  const noSurface = type === PlanetType.GasGiant || type === PlanetType.IceGiant
    || type === PlanetType.HotJupiter || type === PlanetType.SubNeptune
  if (noSurface) {
    return { waterCoverage: 0, liquidFraction: 0, iceCoverage: 0, state: WaterState.None, subsurfaceOcean: false }
  }

  // Base water coverage by planet type
  let baseCoverage: number
  let subsurfaceChance: number
  switch (type) {
    case PlanetType.Oceanic:    baseCoverage = prng.nextFloat(0.7, 1.0);  subsurfaceChance = 0.0;  break
    case PlanetType.Terran:     baseCoverage = prng.nextFloat(0.3, 0.8);  subsurfaceChance = 0.0;  break
    case PlanetType.Arid:       baseCoverage = prng.nextFloat(0.05, 0.3); subsurfaceChance = 0.15; break
    case PlanetType.Tundra:     baseCoverage = prng.nextFloat(0.2, 0.6);  subsurfaceChance = 0.2;  break
    case PlanetType.Glacial:    baseCoverage = prng.nextFloat(0.4, 0.9);  subsurfaceChance = 0.4;  break
    case PlanetType.Desert:     baseCoverage = prng.nextFloat(0.0, 0.08); subsurfaceChance = 0.1;  break
    case PlanetType.Barren:     baseCoverage = prng.nextFloat(0.0, 0.02); subsurfaceChance = 0.05; break
    case PlanetType.Volcanic:   baseCoverage = prng.nextFloat(0.0, 0.05); subsurfaceChance = 0.0;  break
    case PlanetType.LavaPlanet: baseCoverage = 0;                          subsurfaceChance = 0.0;  break
    case PlanetType.CarbonWorld:baseCoverage = prng.nextFloat(0.0, 0.1);  subsurfaceChance = 0.0;  break
    case PlanetType.SuperEarth: baseCoverage = prng.nextFloat(0.1, 0.7);  subsurfaceChance = 0.1;  break
    default:                    baseCoverage = 0;                          subsurfaceChance = 0.0;
  }

  // No atmosphere → water escapes (boil off or freeze and sublimate)
  if (atmo.pressure < 0.01) {
    baseCoverage *= 0.1
    subsurfaceChance *= 0.3
  }

  // High gravity retains more volatiles
  baseCoverage = Math.min(1, baseCoverage * (0.7 + 0.3 * Math.min(1, litho.massEarth)))

  // Determine water state from surface temperature and pressure
  let state: WaterState
  let liquidFraction: number
  let iceCoverage: number

  if (baseCoverage < 0.001) {
    state          = WaterState.None
    liquidFraction = 0
    iceCoverage    = 0
  } else if (surfaceTempK > 450) {
    // Too hot — all vapour
    state          = WaterState.Vapor
    liquidFraction = 0
    iceCoverage    = 0
    baseCoverage   *= 0.3  // most escapes
  } else if (surfaceTempK > 273) {
    // Liquid range
    const warmth = Math.min(1, (surfaceTempK - 273) / 100)
    liquidFraction = 0.7 + warmth * 0.3
    iceCoverage    = (1 - liquidFraction) * baseCoverage
    state          = iceCoverage > 0.05 ? WaterState.Mixed : WaterState.Liquid
  } else {
    // Below freezing — mostly ice
    const freezeDepth = Math.max(0, 1 - (surfaceTempK - 150) / 123)  // 0 at 273K, 1 at 150K
    liquidFraction = Math.max(0, 0.1 - freezeDepth * 0.1)
    iceCoverage    = baseCoverage * 0.8
    state          = liquidFraction > 0.01 ? WaterState.Mixed : WaterState.Ice
  }

  // Subsurface ocean: possible if frozen world with enough radiogenic/tidal heating
  const subsurfaceOcean = baseCoverage > 0.1
    && (state === WaterState.Ice || state === WaterState.Mixed)
    && litho.tectonicActivity > 0.05
    && prng.next() < subsurfaceChance

  return {
    waterCoverage:   Math.max(0, Math.min(1, baseCoverage)),
    liquidFraction:  Math.max(0, Math.min(1, liquidFraction)),
    iceCoverage:     Math.max(0, Math.min(1, iceCoverage)),
    state,
    subsurfaceOcean,
  }
}
