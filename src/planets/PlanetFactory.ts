import { PRNG } from '../math/prng'
import type { StarData } from '../stars/StarProperties'
import { SpectralClass } from '../stars/SpectralClass'
import {
  PlanetType, AtmoComposition,
  VISUAL_AU_TO_LY,
} from './PlanetData'
import type { PlanetData, SystemData, TerraformingState } from './PlanetData'
import {
  habitableZone, equilibriumTemperature,
  planetCount, generateOrbitalSlots, romanNumeral,
} from './OrbitalMechanics'
import { generateLithosphere } from './Lithosphere'
import { generateAtmosphere, refineAtmosphere } from './Atmosphere'
import { generateHydrosphere } from './Hydrosphere'
import { generateBiosphere } from './Biosphere'
import { computeHabitability } from './Habitability'
import { generateResources } from './PlanetResources'

// ─── Planet type selection ────────────────────────────────────────────────────

function selectPlanetType(prng: PRNG, tEq: number, semiMajorAU: number, star: StarData): PlanetType {
  const hz = habitableZone(star.luminositySolar)

  // Very close-in: molten or hot Jupiter
  if (semiMajorAU < hz.inner * 0.12) {
    return prng.next() < 0.35 ? PlanetType.HotJupiter : PlanetType.LavaPlanet
  }

  // Hot zone (inner edge to 60% of HZ inner)
  if (tEq > 600) return PlanetType.LavaPlanet
  if (tEq > 380) {
    const r = prng.next()
    if (r < 0.3) return PlanetType.Volcanic
    if (r < 0.6) return PlanetType.Barren
    return PlanetType.Desert
  }

  // Habitable zone
  if (semiMajorAU >= hz.inner * 0.85 && semiMajorAU <= hz.outer * 1.15) {
    const r = prng.next()
    if (r < 0.12) return PlanetType.Barren
    if (r < 0.22) return PlanetType.Desert
    if (r < 0.34) return PlanetType.Arid
    if (r < 0.55) return PlanetType.Terran
    if (r < 0.66) return PlanetType.Oceanic
    if (r < 0.74) return PlanetType.Volcanic
    if (r < 0.80) return PlanetType.CarbonWorld
    if (r < 0.88) return PlanetType.SuperEarth
    return PlanetType.SubNeptune
  }

  // Outer warm zone (just outside HZ)
  if (tEq > 200) {
    const r = prng.next()
    if (r < 0.25) return PlanetType.Tundra
    if (r < 0.45) return PlanetType.Arid
    if (r < 0.60) return PlanetType.Desert
    if (r < 0.75) return PlanetType.SuperEarth
    return PlanetType.SubNeptune
  }

  // Cold zone (tEq 100–200 K)
  if (tEq > 100) {
    const r = prng.next()
    if (r < 0.35) return PlanetType.Glacial
    if (r < 0.55) return PlanetType.Tundra
    if (r < 0.70) return PlanetType.IceGiant
    return PlanetType.SubNeptune
  }

  // Outer solar system (tEq < 100 K)
  return prng.next() < 0.55 ? PlanetType.GasGiant : PlanetType.IceGiant
}

// ─── Initial terraforming state ───────────────────────────────────────────────

function emptyTerraforming(): TerraformingState {
  return {
    pressureDeltaAtm: 0,
    temperatureDeltaK: 0,
    waterCoverageDelta: 0,
    activeProjects: [],
  }
}

// ─── Main factory ─────────────────────────────────────────────────────────────

export function generateSystem(star: StarData): SystemData {
  const prng = new PRNG(star.systemSeed)
  const hz   = habitableZone(star.luminositySolar)
  const count = planetCount(prng, star)
  const slots = generateOrbitalSlots(prng, count, star)

  const planets: PlanetData[] = slots.map((slot, index) => {
    const tEq = equilibriumTemperature(star.luminositySolar, slot.semiMajorAxisAU)
    const type = selectPlanetType(prng, tEq, slot.semiMajorAxisAU, star)

    // ── Sphere generation cascade ──────────────────────────────────────────
    const litho = generateLithosphere(prng, type)
    const atmo  = generateAtmosphere(prng, type, litho)

    const surfaceTempK = Math.max(10, tEq + atmo.greenhouseEffect)

    const hydro = generateHydrosphere(prng, type, surfaceTempK, litho, atmo)
    const bio   = generateBiosphere(prng, surfaceTempK, hydro, atmo)

    // Refine atmosphere based on what life produced
    const finalAtmo = refineAtmosphere(atmo, bio)

    const resources    = generateResources(prng, type, litho, bio)
    const habitability = computeHabitability(litho, finalAtmo, hydro, bio, surfaceTempK, star)

    // ── World position (visual scale) ──────────────────────────────────────
    const angle = slot.orbitalAngleRad
    const worldX = star.worldX + slot.semiMajorAxisAU * VISUAL_AU_TO_LY * Math.cos(angle)
    const worldY = star.worldY + slot.semiMajorAxisAU * VISUAL_AU_TO_LY * Math.sin(angle)

    return {
      id:      `${star.id}:${index}`,
      name:    `${star.name} ${romanNumeral(index)}`,
      starId:  star.id,
      index,

      semiMajorAxisAU:    slot.semiMajorAxisAU,
      eccentricity:       slot.eccentricity,
      orbitalPeriodYears: slot.orbitalPeriodYears,
      orbitalAngleRad:    slot.orbitalAngleRad,
      inHabitableZone:    slot.inHabitableZone,

      worldX,
      worldY,

      planetType:    type,
      surfaceTempK,

      lithosphere:  litho,
      atmosphere:   finalAtmo,
      hydrosphere:  hydro,
      biosphere:    bio,
      habitability,
      resources,
      terraforming: emptyTerraforming(),
    }
  })

  return {
    starId:     star.id,
    starWorldX: star.worldX,
    starWorldY: star.worldY,
    planets,
    hzInnerAU:  hz.inner,
    hzOuterAU:  hz.outer,
  }
}
