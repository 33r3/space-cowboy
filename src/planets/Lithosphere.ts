import type { PRNG } from '../math/prng'
import { PlanetType, LithosphereComposition } from './PlanetData'
import type { Lithosphere } from './PlanetData'

interface LithosphereTemplate {
  massMin: number
  massMax: number
  radiusMin: number
  radiusMax: number
  densityMin: number
  densityMax: number
  tectonicMin: number
  tectonicMax: number
  magneticMin: number
  magneticMax: number
  compositions: LithosphereComposition[]
  compositionWeights: number[]   // must sum to 1
}

const TEMPLATES: Record<PlanetType, LithosphereTemplate> = {
  [PlanetType.LavaPlanet]: {
    massMin: 0.3, massMax: 3.0, radiusMin: 0.6, radiusMax: 1.4,
    densityMin: 5.5, densityMax: 8.0,
    tectonicMin: 0.85, tectonicMax: 1.0,
    magneticMin: 0.0, magneticMax: 0.3,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich],
    compositionWeights: [0.4, 0.6],
  },
  [PlanetType.HotJupiter]: {
    massMin: 80, massMax: 300, radiusMin: 8, radiusMax: 15,
    densityMin: 0.3, densityMax: 1.5,
    tectonicMin: 0.0, tectonicMax: 0.0,
    magneticMin: 0.3, magneticMax: 0.9,
    compositions: [LithosphereComposition.IcyRock],
    compositionWeights: [1.0],
  },
  [PlanetType.Barren]: {
    massMin: 0.01, massMax: 0.5, radiusMin: 0.2, radiusMax: 0.8,
    densityMin: 3.0, densityMax: 5.5,
    tectonicMin: 0.0, tectonicMax: 0.15,
    magneticMin: 0.0, magneticMax: 0.1,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich],
    compositionWeights: [0.7, 0.3],
  },
  [PlanetType.Desert]: {
    massMin: 0.05, massMax: 1.2, radiusMin: 0.3, radiusMax: 1.1,
    densityMin: 3.5, densityMax: 5.5,
    tectonicMin: 0.05, tectonicMax: 0.4,
    magneticMin: 0.0, magneticMax: 0.3,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich, LithosphereComposition.CarbonRich],
    compositionWeights: [0.6, 0.3, 0.1],
  },
  [PlanetType.Arid]: {
    massMin: 0.3, massMax: 1.5, radiusMin: 0.7, radiusMax: 1.2,
    densityMin: 4.0, densityMax: 5.8,
    tectonicMin: 0.1, tectonicMax: 0.5,
    magneticMin: 0.1, magneticMax: 0.5,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich],
    compositionWeights: [0.7, 0.3],
  },
  [PlanetType.Terran]: {
    massMin: 0.5, massMax: 2.0, radiusMin: 0.8, radiusMax: 1.3,
    densityMin: 4.5, densityMax: 5.8,
    tectonicMin: 0.2, tectonicMax: 0.7,
    magneticMin: 0.3, magneticMax: 0.8,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich],
    compositionWeights: [0.75, 0.25],
  },
  [PlanetType.Oceanic]: {
    massMin: 0.6, massMax: 2.5, radiusMin: 0.9, radiusMax: 1.4,
    densityMin: 3.5, densityMax: 4.8,
    tectonicMin: 0.1, tectonicMax: 0.5,
    magneticMin: 0.2, magneticMax: 0.7,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IcyRock],
    compositionWeights: [0.6, 0.4],
  },
  [PlanetType.Tundra]: {
    massMin: 0.3, massMax: 1.5, radiusMin: 0.6, radiusMax: 1.1,
    densityMin: 3.5, densityMax: 5.2,
    tectonicMin: 0.0, tectonicMax: 0.3,
    magneticMin: 0.0, magneticMax: 0.4,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IcyRock],
    compositionWeights: [0.5, 0.5],
  },
  [PlanetType.Glacial]: {
    massMin: 0.1, massMax: 1.2, radiusMin: 0.4, radiusMax: 1.0,
    densityMin: 2.0, densityMax: 4.0,
    tectonicMin: 0.0, tectonicMax: 0.1,
    magneticMin: 0.0, magneticMax: 0.2,
    compositions: [LithosphereComposition.IcyRock, LithosphereComposition.Silicate],
    compositionWeights: [0.7, 0.3],
  },
  [PlanetType.Volcanic]: {
    massMin: 0.2, massMax: 2.0, radiusMin: 0.5, radiusMax: 1.2,
    densityMin: 5.0, densityMax: 7.5,
    tectonicMin: 0.7, tectonicMax: 1.0,
    magneticMin: 0.0, magneticMax: 0.4,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich],
    compositionWeights: [0.5, 0.5],
  },
  [PlanetType.CarbonWorld]: {
    massMin: 0.2, massMax: 1.5, radiusMin: 0.5, radiusMax: 1.1,
    densityMin: 3.0, densityMax: 5.0,
    tectonicMin: 0.1, tectonicMax: 0.5,
    magneticMin: 0.0, magneticMax: 0.2,
    compositions: [LithosphereComposition.CarbonRich],
    compositionWeights: [1.0],
  },
  [PlanetType.SuperEarth]: {
    massMin: 2.0, massMax: 10.0, radiusMin: 1.3, radiusMax: 2.0,
    densityMin: 4.5, densityMax: 7.0,
    tectonicMin: 0.3, tectonicMax: 0.9,
    magneticMin: 0.3, magneticMax: 0.9,
    compositions: [LithosphereComposition.Silicate, LithosphereComposition.IronRich, LithosphereComposition.Metallic],
    compositionWeights: [0.5, 0.35, 0.15],
  },
  [PlanetType.SubNeptune]: {
    massMin: 4.0, massMax: 15.0, radiusMin: 2.0, radiusMax: 3.5,
    densityMin: 1.5, densityMax: 3.5,
    tectonicMin: 0.0, tectonicMax: 0.0,
    magneticMin: 0.2, magneticMax: 0.7,
    compositions: [LithosphereComposition.IcyRock, LithosphereComposition.Silicate],
    compositionWeights: [0.7, 0.3],
  },
  [PlanetType.GasGiant]: {
    massMin: 30, massMax: 300, radiusMin: 6, radiusMax: 14,
    densityMin: 0.5, densityMax: 2.0,
    tectonicMin: 0.0, tectonicMax: 0.0,
    magneticMin: 0.4, magneticMax: 1.0,
    compositions: [LithosphereComposition.IcyRock],
    compositionWeights: [1.0],
  },
  [PlanetType.IceGiant]: {
    massMin: 10, massMax: 50, radiusMin: 3.5, radiusMax: 6,
    densityMin: 1.2, densityMax: 2.5,
    tectonicMin: 0.0, tectonicMax: 0.0,
    magneticMin: 0.3, magneticMax: 0.8,
    compositions: [LithosphereComposition.IcyRock],
    compositionWeights: [1.0],
  },
}

function weightedPick<T>(items: T[], weights: number[], rand: number): T {
  let cumulative = 0
  for (let i = 0; i < items.length; i++) {
    cumulative += weights[i] ?? 0
    if (rand < cumulative) return items[i] as T
  }
  return items[items.length - 1] as T
}

export function generateLithosphere(prng: PRNG, type: PlanetType): Lithosphere {
  const t = TEMPLATES[type]

  const mass    = prng.nextFloat(t.massMin, t.massMax)
  const radius  = prng.nextFloat(t.radiusMin, t.radiusMax)
  const gravity = mass / (radius * radius)
  const density = prng.nextFloat(t.densityMin, t.densityMax)
  const tectonic = prng.nextFloat(t.tectonicMin, t.tectonicMax)
  // Magnetic field correlates with size and tectonic activity for rocky worlds
  const rawMagnetic = prng.nextFloat(t.magneticMin, t.magneticMax)
  const magnetic = type === PlanetType.GasGiant || type === PlanetType.IceGiant || type === PlanetType.HotJupiter || type === PlanetType.SubNeptune
    ? rawMagnetic
    : rawMagnetic * (0.5 + 0.5 * tectonic) * Math.min(1, mass * 0.8)

  const composition = weightedPick(t.compositions, t.compositionWeights, prng.next())

  return {
    massEarth:      Math.max(0.005, mass),
    radiusEarth:    Math.max(0.1, radius),
    gravityG:       Math.max(0.01, gravity),
    densityGcm3:    density,
    tectonicActivity: tectonic,
    magneticField:  Math.max(0, Math.min(1, magnetic)),
    composition,
  }
}
