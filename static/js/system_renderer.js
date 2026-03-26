import {
  PlanetType, HabitabilityCategory, LifeStage,
  AtmoComposition, WaterState, VISUAL_AU_TO_LY,
} from './constants.js'

const TWO_PI = Math.PI * 2

const PLANET_COLORS = {
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

const HABITABILITY_COLORS = {
  [HabitabilityCategory.Lethal]:      '#ff2200',
  [HabitabilityCategory.Hostile]:     '#ff6600',
  [HabitabilityCategory.Marginal]:    '#ffaa00',
  [HabitabilityCategory.Habitable]:   '#aacc44',
  [HabitabilityCategory.Comfortable]: '#44cc88',
  [HabitabilityCategory.Optimal]:     '#44ffaa',
}

export class SystemRenderer {
  constructor(ctx) {
    this.ctx = ctx
    this._hoveredPlanetId = null
    this.colonyManager = null
  }

  render(system, camera, canvasW, canvasH) {
    const ctx = this.ctx
    const { sx: starSx, sy: starSy } = camera.worldToScreen(
      system.starWorldX, system.starWorldY, canvasW, canvasH,
    )

    // ── HZ ring ─────────────────────────────────────────────────────────────
    const vs = system.visualScale ?? VISUAL_AU_TO_LY
    const hzInnerPx = system.hzInnerAU * vs * camera.zoom
    const hzOuterPx = system.hzOuterAU * vs * camera.zoom

    if (hzOuterPx > 8) {
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

    // ── Orbit rings ──────────────────────────────────────────────────────────
    ctx.save()
    ctx.strokeStyle = 'rgba(100, 120, 150, 0.2)'
    ctx.lineWidth   = 0.8
    ctx.setLineDash([3, 5])

    for (const planet of system.planets) {
      const radiusPx = planet.semiMajorAxisAU * vs * camera.zoom
      if (radiusPx < 4) continue
      ctx.beginPath()
      ctx.arc(starSx, starSy, radiusPx, 0, TWO_PI)
      ctx.stroke()
    }

    ctx.setLineDash([])
    ctx.restore()

    // ── Planet icons ─────────────────────────────────────────────────────────
    for (const planet of system.planets) {
      this._renderPlanet(planet, camera, canvasW, canvasH)
    }
  }

  _renderPlanet(planet, camera, canvasW, canvasH) {
    const ctx = this.ctx
    const { sx, sy } = camera.worldToScreen(planet.worldX, planet.worldY, canvasW, canvasH)

    if (sx < -30 || sx > canvasW + 30 || sy < -30 || sy > canvasH + 30) return

    const isGas = planet.planetType === PlanetType.GasGiant
      || planet.planetType === PlanetType.IceGiant
      || planet.planetType === PlanetType.HotJupiter
      || planet.planetType === PlanetType.SubNeptune

    const baseSize = isGas ? 8 : 5
    const radius   = Math.max(baseSize * 0.5, Math.min(baseSize * 2.5, camera.zoom * 0.03 + baseSize * 0.6))

    const color     = PLANET_COLORS[planet.planetType]
    const isHovered = this._hoveredPlanetId === planet.id

    if (planet.habitability.total >= 46 || isHovered) {
      const glowColor = isHovered ? 'rgba(180,220,255,0.25)' : 'rgba(80,200,120,0.15)'
      ctx.beginPath()
      ctx.arc(sx, sy, radius * 3.5, 0, TWO_PI)
      ctx.fillStyle = glowColor
      ctx.fill()
    }

    ctx.beginPath()
    ctx.arc(sx, sy, radius, 0, TWO_PI)
    ctx.fillStyle = color
    ctx.fill()

    if (planet.habitability.total > 10) {
      const dotColor = HABITABILITY_COLORS[planet.habitability.category]
      ctx.beginPath()
      ctx.arc(sx, sy, radius + 1.5, 0, TWO_PI)
      ctx.strokeStyle = dotColor + '99'
      ctx.lineWidth   = 1.2
      ctx.stroke()
    }

    if (planet.biosphere.stage !== LifeStage.None) {
      ctx.beginPath()
      ctx.arc(sx, sy, radius * 0.4, 0, TWO_PI)
      ctx.fillStyle = 'rgba(100, 240, 120, 0.7)'
      ctx.fill()
    }

    // ── Colony / homeworld rings ─────────────────────────────────────────────
    if (this.colonyManager) {
      if (this.colonyManager.isHomeworld(planet.id)) {
        ctx.beginPath()
        ctx.arc(sx, sy, radius + 4, 0, TWO_PI)
        ctx.strokeStyle = '#ffd700'
        ctx.lineWidth   = 2
        ctx.stroke()
      } else if (this.colonyManager.isColony(planet.id)) {
        ctx.beginPath()
        ctx.arc(sx, sy, radius + 3, 0, TWO_PI)
        ctx.strokeStyle = '#44ffcc'
        ctx.lineWidth   = 1.5
        ctx.stroke()
      }
    }

    if (camera.zoom > 8) {
      ctx.font = `${Math.max(9, Math.min(12, camera.zoom * 0.4))}px "Courier New", monospace`
      ctx.fillStyle = 'rgba(160, 190, 220, 0.75)'
      ctx.fillText(planet.name, sx + radius + 3, sy + 4)

      if (camera.zoom > 15) {
        ctx.font = '9px "Courier New", monospace'
        ctx.fillStyle = 'rgba(100, 130, 160, 0.55)'
        ctx.fillText(`${planet.planetType} · ${planet.habitability.total}/100`, sx + radius + 3, sy + 15)
      }
    }
  }

  updateHover(systems, mouseX, mouseY, camera, canvasW, canvasH) {
    for (const system of systems) {
      for (const planet of system.planets) {
        const { sx, sy } = camera.worldToScreen(planet.worldX, planet.worldY, canvasW, canvasH)
        const dist = Math.sqrt((mouseX - sx) ** 2 + (mouseY - sy) ** 2)
        if (dist < 12) {
          this._hoveredPlanetId = planet.id
          return planet
        }
      }
    }
    this._hoveredPlanetId = null
    return null
  }

  renderTooltip(planet, mouseX, mouseY, canvasW, canvasH) {
    const ctx   = this.ctx
    const isHomeworld = this.colonyManager?.isHomeworld(planet.id) ?? false
    const isColony    = this.colonyManager?.isColony(planet.id)    ?? false
    const lines = buildTooltipLines(planet, isHomeworld, isColony)

    const lineH   = 15
    const padding = 10
    const w       = 230
    const h       = lines.length * lineH + padding * 2

    let tx = mouseX + 16
    let ty = mouseY - h / 2
    if (tx + w > canvasW - 8) tx = mouseX - w - 10
    if (ty < 8) ty = 8
    if (ty + h > canvasH - 8) ty = canvasH - h - 8

    ctx.save()
    ctx.fillStyle   = 'rgba(8, 16, 28, 0.93)'
    ctx.strokeStyle = 'rgba(80, 120, 180, 0.5)'
    ctx.lineWidth   = 1
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

// ── Tooltip ───────────────────────────────────────────────────────────────────

const ATMO_DESC = {
  [AtmoComposition.None]:     'Vacuum',
  [AtmoComposition.Thin]:     'Thin',
  [AtmoComposition.N2O2]:     'N\u2082/O\u2082 (breathable)',
  [AtmoComposition.N2CO2]:    'N\u2082/CO\u2082',
  [AtmoComposition.CO2Dense]: 'Dense CO\u2082',
  [AtmoComposition.H2He]:     'H\u2082/He',
  [AtmoComposition.Methane]:  'Methane',
  [AtmoComposition.SO2]:      'SO\u2082 (volcanic)',
}

const WATER_DESC = {
  [WaterState.None]:   'None',
  [WaterState.Ice]:    'Ice',
  [WaterState.Mixed]:  'Liquid + Ice',
  [WaterState.Liquid]: 'Liquid',
  [WaterState.Vapor]:  'Vapor',
}

const LIFE_DESC = {
  [LifeStage.None]:               'None',
  [LifeStage.Prebiotic]:          'Prebiotic chemistry',
  [LifeStage.Microbial]:          'Microbial life',
  [LifeStage.SimpleMulticellular]:'Simple multicellular',
  [LifeStage.ComplexLife]:        'Complex life',
}

const YIELD_LABELS = {
  food:           'Food      ',
  water:          'Water     ',
  organicFuels:   'Org.Fuels ',
  chemFeedstocks: 'Chem.Feed ',
  minerals:       'Minerals  ',
  fusionFuel:     'Fusion    ',
  metals:         'Metals    ',
  radioactives:   'Radioact. ',
}

function _yieldBar(v) {
  const filled = Math.round(v * 5)
  return '\u2588'.repeat(filled) + '\u2591'.repeat(5 - filled) + ` ${v.toFixed(2)}`
}

function buildTooltipLines(p, isHomeworld, isColony) {
  const H  = '#aaccee'
  const V  = '#88aacc'
  const D  = '#556677'
  const G  = '#66cc88'
  const W  = '#cc8844'
  const R  = '#cc4422'
  const GD = '#ffd700'
  const CY = '#44ffcc'

  const hab = p.habitability
  const habColor = hab.total >= 66 ? G : hab.total >= 46 ? V : hab.total >= 26 ? W : R

  const tempC   = Math.round(p.surfaceTempK - 273)
  const tempStr = `${p.surfaceTempK} K (${tempC > 0 ? '+' : ''}${tempC}\u00b0C)`

  const lines = [
    { text: p.name, color: isHomeworld ? GD : isColony ? CY : H },
    { text: `${p.planetType}  \u00b7  ${p.semiMajorAxisAU.toFixed(2)} AU`, color: D },
  ]

  if (isHomeworld) lines.push({ text: '\u2605 Home World', color: GD })
  else if (isColony) lines.push({ text: '\u25a0 Colony', color: CY })

  lines.push(
    { text: '', color: D },
    { text: `Habitability: ${hab.total}/100 \u2014 ${hab.category}`, color: habColor },
    { text: '', color: D },
    { text: `Temp:    ${tempStr}`, color: V },
    { text: `Gravity: ${p.lithosphere.gravityG.toFixed(2)} g`, color: V },
    { text: `Atmo:    ${ATMO_DESC[p.atmosphere.composition]}  ${p.atmosphere.pressure.toFixed(2)} atm`, color: V },
    { text: `Water:   ${WATER_DESC[p.hydrosphere.state]}  ${Math.round(p.hydrosphere.waterCoverage * 100)}%`, color: V },
    { text: `Life:    ${LIFE_DESC[p.biosphere.stage]}`, color: p.biosphere.stage !== LifeStage.None ? G : D },
    { text: '', color: D },
    { text: `Tectonic: ${Math.round(p.lithosphere.tectonicActivity * 100)}%  Magnetic: ${Math.round(p.lithosphere.magneticField * 100)}%`, color: D },
  )

  // Colony yields — show all non-zero resources
  const yields = p.colonyYields
  if (yields) {
    const nonZero = Object.entries(yields).filter(([, v]) => v > 0)
    if (nonZero.length > 0) {
      lines.push({ text: '', color: D })
      lines.push({ text: 'COLONY YIELDS', color: isHomeworld ? GD : isColony ? CY : V })
      for (const [key, val] of nonZero) {
        lines.push({ text: `${YIELD_LABELS[key] ?? key}${_yieldBar(val)}`, color: V })
      }
    }
  }

  return lines
}
