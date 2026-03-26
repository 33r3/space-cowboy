import type { Camera } from './Camera'
import type { SystemData, PlanetData } from '../planets/PlanetData'
import {
  PlanetType, HabitabilityCategory, LifeStage,
  AtmoComposition, WaterState, VISUAL_AU_TO_LY,
} from '../planets/PlanetData'

const TWO_PI = Math.PI * 2

// ─── Planet colors by type ────────────────────────────────────────────────────

const PLANET_COLORS: Record<PlanetType, string> = {
  [PlanetType.LavaPlanet]:  '#ff3300',
  [PlanetType.HotJupiter]:  '#cc7733',
  [PlanetType.Barren]:      '#888888',
  [PlanetType.Desert]:      '#cc8844',
  [PlanetType.Arid]:        '#bbaa66',
  [PlanetType.Terran]:      '#4488cc',
  [PlanetType.Oceanic]:     '#2255aa',
  [PlanetType.Tundra]:      '#99bbcc',
  [PlanetType.Glacial]:     '#cce0ff',
  [PlanetType.Volcanic]:    '#dd4400',
  [PlanetType.CarbonWorld]: '#554433',
  [PlanetType.SuperEarth]:  '#5599aa',
  [PlanetType.SubNeptune]:  '#6688aa',
  [PlanetType.GasGiant]:    '#cc9955',
  [PlanetType.IceGiant]:    '#88aacc',
}

const HABITABILITY_COLORS: Record<HabitabilityCategory, string> = {
  [HabitabilityCategory.Lethal]:      '#ff2200',
  [HabitabilityCategory.Hostile]:     '#ff6600',
  [HabitabilityCategory.Marginal]:    '#ffaa00',
  [HabitabilityCategory.Habitable]:   '#aacc44',
  [HabitabilityCategory.Comfortable]: '#44cc88',
  [HabitabilityCategory.Optimal]:     '#44ffaa',
}

// ─── SystemRenderer ───────────────────────────────────────────────────────────

export class SystemRenderer {
  private ctx: CanvasRenderingContext2D
  private hoveredPlanetId: string | null = null

  constructor(ctx: CanvasRenderingContext2D) {
    this.ctx = ctx
  }

  render(
    system: SystemData,
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): void {
    const ctx = this.ctx

    // Only render if the star is somewhat centered and zoom is adequate
    const { sx: starSx, sy: starSy } = camera.worldToScreen(
      system.starWorldX, system.starWorldY, canvasW, canvasH,
    )

    // ── Habitable zone ring ───────────────────────────────────────────────────
    const hzInnerPx = system.hzInnerAU * VISUAL_AU_TO_LY * camera.zoom
    const hzOuterPx = system.hzOuterAU * VISUAL_AU_TO_LY * camera.zoom

    if (hzOuterPx > 8) {
      const ringWidth = Math.max(2, hzOuterPx - hzInnerPx)
      const grad = ctx.createRadialGradient(starSx, starSy, hzInnerPx, starSx, starSy, hzOuterPx)
      grad.addColorStop(0,   'rgba(80, 200, 80, 0.0)')
      grad.addColorStop(0.2, 'rgba(80, 200, 80, 0.12)')
      grad.addColorStop(0.5, 'rgba(100, 220, 100, 0.18)')
      grad.addColorStop(0.8, 'rgba(80, 200, 80, 0.12)')
      grad.addColorStop(1,   'rgba(80, 200, 80, 0.0)')

      ctx.beginPath()
      ctx.arc(starSx, starSy, hzOuterPx, 0, TWO_PI)
      ctx.fillStyle = grad
      ctx.fill()
    }

    // ── Orbit rings ───────────────────────────────────────────────────────────
    ctx.save()
    ctx.strokeStyle = 'rgba(100, 120, 150, 0.2)'
    ctx.lineWidth   = 0.8
    ctx.setLineDash([3, 5])

    for (const planet of system.planets) {
      const radiusPx = planet.semiMajorAxisAU * VISUAL_AU_TO_LY * camera.zoom
      if (radiusPx < 4) continue
      ctx.beginPath()
      ctx.arc(starSx, starSy, radiusPx, 0, TWO_PI)
      ctx.stroke()
    }

    ctx.setLineDash([])
    ctx.restore()

    // ── Planet icons ──────────────────────────────────────────────────────────
    for (const planet of system.planets) {
      this.renderPlanet(planet, camera, canvasW, canvasH)
    }
  }

  private renderPlanet(
    planet: PlanetData,
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): void {
    const ctx = this.ctx
    const { sx, sy } = camera.worldToScreen(planet.worldX, planet.worldY, canvasW, canvasH)

    // Off-screen culling
    if (sx < -30 || sx > canvasW + 30 || sy < -30 || sy > canvasH + 30) return

    const isGas = planet.planetType === PlanetType.GasGiant
      || planet.planetType === PlanetType.IceGiant
      || planet.planetType === PlanetType.HotJupiter
      || planet.planetType === PlanetType.SubNeptune

    // Scale planet icon with zoom but clamp to a visible range
    const baseSize = isGas ? 8 : 5
    const radius = Math.max(baseSize * 0.5, Math.min(baseSize * 2.5, camera.zoom * 0.03 + baseSize * 0.6))

    const color = PLANET_COLORS[planet.planetType]
    const isHovered = this.hoveredPlanetId === planet.id

    // Glow for habitable/optimal worlds
    if (planet.habitability.total >= 46 || isHovered) {
      const glowColor = isHovered ? 'rgba(180,220,255,0.25)' : 'rgba(80,200,120,0.15)'
      ctx.beginPath()
      ctx.arc(sx, sy, radius * 3.5, 0, TWO_PI)
      ctx.fillStyle = glowColor
      ctx.fill()
    }

    // Planet body
    ctx.beginPath()
    ctx.arc(sx, sy, radius, 0, TWO_PI)
    ctx.fillStyle = color
    ctx.fill()

    // Habitability dot overlay (small ring around planet)
    if (planet.habitability.total > 10) {
      const dotColor = HABITABILITY_COLORS[planet.habitability.category]
      ctx.beginPath()
      ctx.arc(sx, sy, radius + 1.5, 0, TWO_PI)
      ctx.strokeStyle = dotColor + '99'
      ctx.lineWidth = 1.2
      ctx.stroke()
    }

    // Life indicator: green shimmer if biosphere exists
    if (planet.biosphere.stage !== LifeStage.None) {
      ctx.beginPath()
      ctx.arc(sx, sy, radius * 0.4, 0, TWO_PI)
      ctx.fillStyle = 'rgba(100, 240, 120, 0.7)'
      ctx.fill()
    }

    // Label (only at higher zoom)
    if (camera.zoom > 3) {
      ctx.font = `${Math.max(9, Math.min(12, camera.zoom * 0.4))}px "Courier New", monospace`
      ctx.fillStyle = 'rgba(160, 190, 220, 0.75)'
      ctx.fillText(planet.name, sx + radius + 3, sy + 4)

      if (camera.zoom > 6) {
        ctx.font = '9px "Courier New", monospace'
        ctx.fillStyle = 'rgba(100, 130, 160, 0.55)'
        ctx.fillText(`${planet.planetType} · ${planet.habitability.total}/100`, sx + radius + 3, sy + 15)
      }
    }
  }

  /**
   * Call with the current mouse position each frame to update hover state.
   * Returns the hovered planet if any.
   */
  updateHover(
    systems: SystemData[],
    mouseX: number,
    mouseY: number,
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): PlanetData | null {
    for (const system of systems) {
      for (const planet of system.planets) {
        const { sx, sy } = camera.worldToScreen(planet.worldX, planet.worldY, canvasW, canvasH)
        const dist = Math.sqrt((mouseX - sx) ** 2 + (mouseY - sy) ** 2)
        if (dist < 12) {
          this.hoveredPlanetId = planet.id
          return planet
        }
      }
    }
    this.hoveredPlanetId = null
    return null
  }

  renderTooltip(planet: PlanetData, mouseX: number, mouseY: number, canvasW: number, canvasH: number): void {
    const ctx = this.ctx
    const lines = buildTooltipLines(planet)

    const lineH   = 15
    const padding = 10
    const w       = 220
    const h       = lines.length * lineH + padding * 2

    // Anchor tooltip so it stays on screen
    let tx = mouseX + 16
    let ty = mouseY - h / 2
    if (tx + w > canvasW - 8) tx = mouseX - w - 10
    if (ty < 8) ty = 8
    if (ty + h > canvasH - 8) ty = canvasH - h - 8

    // Background
    ctx.save()
    ctx.fillStyle = 'rgba(8, 16, 28, 0.93)'
    ctx.strokeStyle = 'rgba(80, 120, 180, 0.5)'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.roundRect(tx, ty, w, h, 4)
    ctx.fill()
    ctx.stroke()

    ctx.font = '11px "Courier New", monospace'
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      if (!line) continue
      ctx.fillStyle = line.color
      ctx.fillText(line.text, tx + padding, ty + padding + i * lineH + 10)
    }

    ctx.restore()
  }
}

// ─── Tooltip content ──────────────────────────────────────────────────────────

interface TooltipLine { text: string; color: string }

function buildTooltipLines(p: PlanetData): TooltipLine[] {
  const H = '#aaccee'   // header
  const V = '#88aacc'   // value
  const D = '#556677'   // dim / label
  const G = '#66cc88'   // good
  const W = '#cc8844'   // warning
  const R = '#cc4422'   // red / bad

  const hab = p.habitability
  const habColor = hab.total >= 66 ? G : hab.total >= 46 ? V : hab.total >= 26 ? W : R

  const atmoDesc: Record<AtmoComposition, string> = {
    [AtmoComposition.None]:     'Vacuum',
    [AtmoComposition.Thin]:     'Thin',
    [AtmoComposition.N2O2]:     'N₂/O₂ (breathable)',
    [AtmoComposition.N2CO2]:    'N₂/CO₂',
    [AtmoComposition.CO2Dense]: 'Dense CO₂',
    [AtmoComposition.H2He]:     'H₂/He',
    [AtmoComposition.Methane]:  'Methane',
    [AtmoComposition.SO2]:      'SO₂ (volcanic)',
  }

  const waterDesc: Record<WaterState, string> = {
    [WaterState.None]:   'None',
    [WaterState.Ice]:    'Ice',
    [WaterState.Mixed]:  'Liquid + Ice',
    [WaterState.Liquid]: 'Liquid',
    [WaterState.Vapor]:  'Vapor',
  }

  const lifeDesc: Record<LifeStage, string> = {
    [LifeStage.None]:               'None',
    [LifeStage.Prebiotic]:          'Prebiotic chemistry',
    [LifeStage.Microbial]:          'Microbial life',
    [LifeStage.SimpleMulticellular]:'Simple multicellular',
    [LifeStage.ComplexLife]:        'Complex life',
  }

  const tempC = Math.round(p.surfaceTempK - 273)
  const tempStr = `${p.surfaceTempK} K (${tempC > 0 ? '+' : ''}${tempC}°C)`

  return [
    { text: p.name, color: H },
    { text: `${p.planetType}  ·  ${p.semiMajorAxisAU.toFixed(2)} AU`, color: D },
    { text: '', color: D },
    { text: `Habitability: ${hab.total}/100 — ${hab.category}`, color: habColor },
    { text: '', color: D },
    { text: `Temp:    ${tempStr}`, color: V },
    { text: `Gravity: ${p.lithosphere.gravityG.toFixed(2)} g`, color: V },
    { text: `Atmo:    ${atmoDesc[p.atmosphere.composition]}  ${p.atmosphere.pressure.toFixed(2)} atm`, color: V },
    { text: `Water:   ${waterDesc[p.hydrosphere.state]}  ${Math.round(p.hydrosphere.waterCoverage * 100)}%`, color: V },
    { text: `Life:    ${lifeDesc[p.biosphere.stage]}`, color: p.biosphere.stage !== LifeStage.None ? G : D },
    { text: '', color: D },
    { text: `Tectonic: ${Math.round(p.lithosphere.tectonicActivity * 100)}%  Magnetic: ${Math.round(p.lithosphere.magneticField * 100)}%`, color: D },
  ]
}
