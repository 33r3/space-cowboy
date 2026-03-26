// ─── Planet Type ──────────────────────────────────────────────────────────────

export enum PlanetType {
  // Close-in / hot
  LavaPlanet   = 'LavaPlanet',
  HotJupiter   = 'HotJupiter',
  // Terrestrial
  Barren       = 'Barren',
  Desert       = 'Desert',
  Arid         = 'Arid',
  Terran       = 'Terran',
  Oceanic      = 'Oceanic',
  Tundra       = 'Tundra',
  Glacial      = 'Glacial',
  Volcanic     = 'Volcanic',
  CarbonWorld  = 'CarbonWorld',
  // Large terrestrial
  SuperEarth   = 'SuperEarth',
  // Enveloped
  SubNeptune   = 'SubNeptune',
  // Giants
  GasGiant     = 'GasGiant',
  IceGiant     = 'IceGiant',
}

// ─── Lithosphere ──────────────────────────────────────────────────────────────

export enum LithosphereComposition {
  Silicate  = 'Silicate',
  IronRich  = 'IronRich',
  CarbonRich = 'CarbonRich',
  IcyRock   = 'IcyRock',
  Metallic  = 'Metallic',
}

export interface Lithosphere {
  massEarth: number          // Earth masses
  radiusEarth: number        // Earth radii
  gravityG: number           // surface gravity (Earth = 1)
  densityGcm3: number        // g/cm³
  tectonicActivity: number   // 0–1
  magneticField: number      // 0–1
  composition: LithosphereComposition
}

// ─── Atmosphere ───────────────────────────────────────────────────────────────

export enum AtmoComposition {
  None      = 'None',
  Thin      = 'Thin',
  N2O2      = 'N2O2',       // breathable
  N2CO2     = 'N2CO2',      // Mars-like
  CO2Dense  = 'CO2Dense',   // Venus-like
  H2He      = 'H2He',       // gas/ice giant
  Methane   = 'Methane',    // Titan-like
  SO2       = 'SO2',        // volcanic
}

export interface Atmosphere {
  pressure: number           // atm
  composition: AtmoComposition
  greenhouseEffect: number   // ΔK added to equilibrium temperature
  toxicity: number           // 0–1
  breathable: boolean
}

// ─── Hydrosphere ─────────────────────────────────────────────────────────────

export enum WaterState {
  None    = 'None',
  Ice     = 'Ice',
  Mixed   = 'Mixed',    // liquid + ice
  Liquid  = 'Liquid',
  Vapor   = 'Vapor',
}

export interface Hydrosphere {
  waterCoverage: number      // 0–1 (fraction of surface with water/ice)
  liquidFraction: number     // 0–1 of waterCoverage that is liquid
  iceCoverage: number        // 0–1 polar / surface ice
  state: WaterState
  subsurfaceOcean: boolean
}

// ─── Biosphere ───────────────────────────────────────────────────────────────

export enum LifeStage {
  None               = 'None',
  Prebiotic          = 'Prebiotic',
  Microbial          = 'Microbial',
  SimpleMulticellular = 'SimpleMulticellular',
  ComplexLife        = 'ComplexLife',
}

export interface Biosphere {
  stage: LifeStage
  coverage: number           // 0–1
  oxygenContribution: number // O2 fraction contributed (0–0.21)
}

// ─── Habitability ─────────────────────────────────────────────────────────────

export enum HabitabilityCategory {
  Lethal      = 'Lethal',       // 0–10
  Hostile     = 'Hostile',      // 11–25
  Marginal    = 'Marginal',     // 26–45
  Habitable   = 'Habitable',    // 46–65
  Comfortable = 'Comfortable',  // 66–80
  Optimal     = 'Optimal',      // 81–100
}

export interface HabitabilityScore {
  total: number
  temperature: number
  atmosphere: number
  gravity: number
  radiation: number
  water: number
  biosphere: number
  category: HabitabilityCategory
}

// ─── Resources ───────────────────────────────────────────────────────────────

export interface ResourceDeposit {
  abundance: number          // 0–1
  accessibility: number      // 0–1 (ease of extraction)
}

export interface PlanetResources {
  metals:       ResourceDeposit
  rareMetals:   ResourceDeposit
  rareEarths:   ResourceDeposit
  radioactives: ResourceDeposit
  volatiles:    ResourceDeposit
  organics:     ResourceDeposit
  exotics:      ResourceDeposit
}

// ─── Terraforming ─────────────────────────────────────────────────────────────

export interface TerraformingState {
  // Applied modifications (all zero until tech is researched)
  pressureDeltaAtm: number
  temperatureDeltaK: number
  waterCoverageDelta: number
  // Targets (set by future tech UI)
  targetPressure?: number
  targetTemperatureK?: number
  targetComposition?: AtmoComposition
  targetBiosphereStage?: LifeStage
  // Active project IDs (hooks for future tech tree)
  activeProjects: string[]
}

// ─── Combined Planet + System ────────────────────────────────────────────────

export interface PlanetData {
  id: string                 // "{starId}:{index}"
  name: string               // "{starName} I", "{starName} II", etc.
  starId: string
  index: number              // 0 = innermost

  // Orbital parameters
  semiMajorAxisAU: number
  eccentricity: number
  orbitalPeriodYears: number
  orbitalAngleRad: number    // initial angle (static this phase)
  inHabitableZone: boolean

  // Visual world position (VISUAL_AU_TO_LY scale — NOT physically accurate)
  worldX: number
  worldY: number

  planetType: PlanetType
  surfaceTempK: number       // equilibrium + greenhouse delta

  lithosphere: Lithosphere
  atmosphere: Atmosphere
  hydrosphere: Hydrosphere
  biosphere: Biosphere
  habitability: HabitabilityScore
  resources: PlanetResources
  terraforming: TerraformingState
}

export interface SystemData {
  starId: string
  starWorldX: number
  starWorldY: number
  planets: PlanetData[]
  hzInnerAU: number
  hzOuterAU: number
}

// Visual scale: 1 AU → this many light-years in world space
export const VISUAL_AU_TO_LY = 0.6
