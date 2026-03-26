import type { PRNG } from '../math/prng'
import { PlanetType, AtmoComposition } from './PlanetData'
import type { Atmosphere, Lithosphere, Biosphere } from './PlanetData'

// Greenhouse effect per composition in Kelvin
const GREENHOUSE_BASE: Record<AtmoComposition, number> = {
  [AtmoComposition.None]:     0,
  [AtmoComposition.Thin]:     2,
  [AtmoComposition.N2O2]:     33,   // Earth baseline
  [AtmoComposition.N2CO2]:    5,    // Mars-like
  [AtmoComposition.CO2Dense]: 500,  // Venus-like
  [AtmoComposition.H2He]:     20,
  [AtmoComposition.Methane]:  12,
  [AtmoComposition.SO2]:      25,
}

// Base toxicity per composition
const TOXICITY_BASE: Record<AtmoComposition, number> = {
  [AtmoComposition.None]:     0.0,
  [AtmoComposition.Thin]:     0.1,
  [AtmoComposition.N2O2]:     0.0,
  [AtmoComposition.N2CO2]:    0.6,
  [AtmoComposition.CO2Dense]: 0.95,
  [AtmoComposition.H2He]:     0.2,
  [AtmoComposition.Methane]:  0.75,
  [AtmoComposition.SO2]:      0.9,
}

interface AtmoTemplate {
  pressureMin: number
  pressureMax: number
  composition: AtmoComposition
  // Scatter on greenhouse and toxicity
  greenhouseScatter: number
}

const TEMPLATES: Record<PlanetType, AtmoTemplate> = {
  [PlanetType.LavaPlanet]:  { pressureMin: 0,    pressureMax: 0.01, composition: AtmoComposition.None,     greenhouseScatter: 0 },
  [PlanetType.HotJupiter]:  { pressureMin: 50,   pressureMax: 200,  composition: AtmoComposition.H2He,     greenhouseScatter: 5 },
  [PlanetType.Barren]:      { pressureMin: 0,    pressureMax: 0.005,composition: AtmoComposition.None,     greenhouseScatter: 0 },
  [PlanetType.Desert]:      { pressureMin: 0.01, pressureMax: 0.5,  composition: AtmoComposition.N2CO2,    greenhouseScatter: 3 },
  [PlanetType.Arid]:        { pressureMin: 0.3,  pressureMax: 1.5,  composition: AtmoComposition.N2CO2,    greenhouseScatter: 8 },
  [PlanetType.Terran]:      { pressureMin: 0.6,  pressureMax: 1.5,  composition: AtmoComposition.N2O2,     greenhouseScatter: 10 },
  [PlanetType.Oceanic]:     { pressureMin: 0.8,  pressureMax: 2.0,  composition: AtmoComposition.N2O2,     greenhouseScatter: 12 },
  [PlanetType.Tundra]:      { pressureMin: 0.1,  pressureMax: 0.8,  composition: AtmoComposition.N2CO2,    greenhouseScatter: 5 },
  [PlanetType.Glacial]:     { pressureMin: 0,    pressureMax: 0.1,  composition: AtmoComposition.Thin,     greenhouseScatter: 1 },
  [PlanetType.Volcanic]:    { pressureMin: 10,   pressureMax: 90,   composition: AtmoComposition.SO2,      greenhouseScatter: 20 },
  [PlanetType.CarbonWorld]: { pressureMin: 1.0,  pressureMax: 5.0,  composition: AtmoComposition.Methane,  greenhouseScatter: 4 },
  [PlanetType.SuperEarth]:  { pressureMin: 1.0,  pressureMax: 3.0,  composition: AtmoComposition.N2CO2,    greenhouseScatter: 15 },
  [PlanetType.SubNeptune]:  { pressureMin: 20,   pressureMax: 100,  composition: AtmoComposition.H2He,     greenhouseScatter: 8 },
  [PlanetType.GasGiant]:    { pressureMin: 100,  pressureMax: 500,  composition: AtmoComposition.H2He,     greenhouseScatter: 10 },
  [PlanetType.IceGiant]:    { pressureMin: 30,   pressureMax: 150,  composition: AtmoComposition.H2He,     greenhouseScatter: 5 },
}

function isBreathable(comp: AtmoComposition, pressure: number): boolean {
  return comp === AtmoComposition.N2O2 && pressure >= 0.5 && pressure <= 2.0
}

export function generateAtmosphere(prng: PRNG, type: PlanetType, litho: Lithosphere): Atmosphere {
  const t = TEMPLATES[type]
  let pressure = prng.nextFloat(t.pressureMin, t.pressureMax)

  // Tectonic outgassing thickens atmosphere for rocky worlds
  if (type !== PlanetType.GasGiant && type !== PlanetType.IceGiant &&
      type !== PlanetType.HotJupiter && type !== PlanetType.SubNeptune) {
    pressure *= (1 + litho.tectonicActivity * 0.5)
  }

  const composition = t.composition
  const baseGreenhouse = GREENHOUSE_BASE[composition]
  const greenhouse = baseGreenhouse * (pressure / Math.max(0.001, (t.pressureMin + t.pressureMax) / 2))
    + prng.nextGaussian() * t.greenhouseScatter
  const toxicity = TOXICITY_BASE[composition] + (pressure > 2 ? (pressure - 2) * 0.02 : 0)

  return {
    pressure:        Math.max(0, pressure),
    composition,
    greenhouseEffect: Math.max(0, greenhouse),
    toxicity:        Math.max(0, Math.min(1, toxicity)),
    breathable:      isBreathable(composition, pressure),
  }
}

/**
 * Refine atmosphere after biosphere generation.
 * Life with sufficient O2 contribution can shift atmosphere toward N2O2.
 */
export function refineAtmosphere(atmo: Atmosphere, bio: Biosphere): Atmosphere {
  if (bio.oxygenContribution < 0.18) return atmo   // not enough O2 yet

  const refined = { ...atmo }
  if (atmo.composition === AtmoComposition.N2CO2 && atmo.pressure >= 0.5 && atmo.pressure <= 2.5) {
    refined.composition = AtmoComposition.N2O2
    refined.toxicity    = 0
    refined.breathable  = true
    refined.greenhouseEffect = 33 + atmo.greenhouseEffect * 0.1
  }
  return refined
}

