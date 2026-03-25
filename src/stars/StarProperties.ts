import type { SpectralClass, LuminosityClass } from './SpectralClass'

/**
 * All properties of a generated star.
 * Positions are in light-years from galaxy center.
 */
export interface StarData {
  /** Unique deterministic ID: "{chunkKey}:{index}" */
  id: string

  worldX: number
  worldY: number

  spectralClass: SpectralClass
  /** 0–9 subclass within the spectral class (lower = hotter within class) */
  subclass: number
  luminosityClass: LuminosityClass

  /** Mass in solar masses */
  massSolar: number
  /** Luminosity in solar luminosities */
  luminositySolar: number
  /** Effective surface temperature in Kelvin */
  temperatureK: number
  /** Radius in solar radii */
  radiusSolar: number

  /** CSS hex color derived from temperature */
  color: string

  /** Procedurally generated name */
  name: string

  /**
   * Seed for generating this star's planetary system.
   * Derived deterministically — same star always has same planets.
   */
  systemSeed: number
}
