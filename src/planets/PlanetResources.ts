import type { PRNG } from '../math/prng'
import { PlanetType, LithosphereComposition, LifeStage } from './PlanetData'
import type { PlanetResources, Lithosphere, Biosphere } from './PlanetData'

function deposit(prng: PRNG, abundanceMin: number, abundanceMax: number, accessMin = 0.2, accessMax = 0.9): { abundance: number; accessibility: number } {
  return {
    abundance:    prng.nextFloat(abundanceMin, abundanceMax),
    accessibility: prng.nextFloat(accessMin, accessMax),
  }
}

export function generateResources(
  prng: PRNG,
  type: PlanetType,
  litho: Lithosphere,
  bio: Biosphere,
): PlanetResources {
  const isGas = type === PlanetType.GasGiant || type === PlanetType.IceGiant
    || type === PlanetType.HotJupiter || type === PlanetType.SubNeptune

  if (isGas) {
    // Gas giants: rich in volatiles, no solid resource extraction
    return {
      metals:       deposit(prng, 0, 0),
      rareMetals:   deposit(prng, 0, 0),
      rareEarths:   deposit(prng, 0, 0),
      radioactives: deposit(prng, 0, 0.05),
      volatiles:    deposit(prng, 0.5, 1.0, 0.1, 0.5),
      organics:     deposit(prng, 0, 0.1),
      exotics:      deposit(prng, 0, 0.02),
    }
  }

  // ── Metals ─────────────────────────────────────────────────────────────────
  const metalMult = litho.composition === LithosphereComposition.IronRich ? 1.4
    : litho.composition === LithosphereComposition.Metallic ? 1.7 : 1.0
  const metals = deposit(prng, 0.1 * metalMult, 0.6 * metalMult)

  // ── Rare Metals ────────────────────────────────────────────────────────────
  const rareMult = litho.composition === LithosphereComposition.Metallic ? 1.8
    : litho.composition === LithosphereComposition.IronRich ? 1.2 : 1.0
  const rareMetals = deposit(prng, 0.02 * rareMult, 0.3 * rareMult)

  // ── Rare Earths ────────────────────────────────────────────────────────────
  // More common in old, cool planets with silicate crust
  const rareEarthMult = litho.composition === LithosphereComposition.Silicate ? 1.3 : 0.7
  const rareEarths = deposit(prng, 0.01 * rareEarthMult, 0.2 * rareEarthMult)

  // ── Radioactives ───────────────────────────────────────────────────────────
  const radioMult = litho.composition === LithosphereComposition.IronRich ? 1.3 : 1.0
  const radioactives = deposit(prng, 0.01 * radioMult, 0.25 * radioMult)

  // ── Volatiles ─────────────────────────────────────────────────────────────
  const icyBonus = litho.composition === LithosphereComposition.IcyRock ? 1.8 : 1.0
  const volatileMult = (type === PlanetType.Glacial || type === PlanetType.Tundra) ? 1.5 : 1.0
  const volatiles = deposit(prng, 0.05 * icyBonus * volatileMult, 0.5 * icyBonus * volatileMult)

  // ── Organics ──────────────────────────────────────────────────────────────
  let organicsAbundance: number
  if (bio.stage === LifeStage.None || bio.stage === LifeStage.Prebiotic) {
    organicsAbundance = type === PlanetType.CarbonWorld ? prng.nextFloat(0.2, 0.6) : prng.nextFloat(0, 0.05)
  } else if (bio.stage === LifeStage.Microbial) {
    organicsAbundance = prng.nextFloat(0.05, 0.25)
  } else {
    organicsAbundance = prng.nextFloat(0.2, 0.8) * bio.coverage
  }
  const organics = deposit(prng, organicsAbundance, organicsAbundance)

  // ── Exotics ───────────────────────────────────────────────────────────────
  // Rare; slightly more common in SuperEarth / Volcanic (extreme pressure/heat)
  const exoticChance = type === PlanetType.SuperEarth ? 0.12
    : type === PlanetType.Volcanic || type === PlanetType.LavaPlanet ? 0.09 : 0.04
  const exotics = prng.next() < exoticChance
    ? deposit(prng, 0.05, 0.3, 0.05, 0.4)
    : { abundance: 0, accessibility: 0 }

  return { metals, rareMetals, rareEarths, radioactives, volatiles, organics, exotics }
}
