// Mirrors all TypeScript enums from PlanetData.ts and SpectralClass.ts

export const SpectralClass = {
  O:          'O',
  B:          'B',
  A:          'A',
  F:          'F',
  G:          'G',
  K:          'K',
  M:          'M',
  WhiteDwarf: 'WD',
  Giant:      'III',
  Supergiant: 'Ia',
}

export const PlanetType = {
  LavaPlanet:  'LavaPlanet',
  HotJupiter:  'HotJupiter',
  Barren:      'Barren',
  Desert:      'Desert',
  Arid:        'Arid',
  Terran:      'Terran',
  Oceanic:     'Oceanic',
  Tundra:      'Tundra',
  Glacial:     'Glacial',
  Volcanic:    'Volcanic',
  CarbonWorld: 'CarbonWorld',
  SuperEarth:  'SuperEarth',
  SubNeptune:  'SubNeptune',
  GasGiant:    'GasGiant',
  IceGiant:    'IceGiant',
}

export const LithosphereComposition = {
  Silicate:  'Silicate',
  IronRich:  'IronRich',
  CarbonRich:'CarbonRich',
  IcyRock:   'IcyRock',
  Metallic:  'Metallic',
}

export const AtmoComposition = {
  None:     'None',
  Thin:     'Thin',
  N2O2:     'N2O2',
  N2CO2:    'N2CO2',
  CO2Dense: 'CO2Dense',
  H2He:     'H2He',
  Methane:  'Methane',
  SO2:      'SO2',
}

export const WaterState = {
  None:   'None',
  Ice:    'Ice',
  Mixed:  'Mixed',
  Liquid: 'Liquid',
  Vapor:  'Vapor',
}

export const LifeStage = {
  None:               'None',
  Prebiotic:          'Prebiotic',
  Microbial:          'Microbial',
  SimpleMulticellular:'SimpleMulticellular',
  ComplexLife:        'ComplexLife',
}

export const HabitabilityCategory = {
  Lethal:      'Lethal',
  Hostile:     'Hostile',
  Marginal:    'Marginal',
  Habitable:   'Habitable',
  Comfortable: 'Comfortable',
  Optimal:     'Optimal',
}

export const VISUAL_AU_TO_LY = 0.6
