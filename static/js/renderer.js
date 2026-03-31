import { StarRenderer } from './star_renderer.js'
import { ChunkDebugRenderer } from './chunk_debug_renderer.js'
import { SystemRenderer } from './system_renderer.js'

const SYSTEM_ZOOM_THRESHOLD = 1.5

export class Renderer {
  constructor(ctx, camera, galaxyClient, colonyManager = null, routeManager = null) {
    this.ctx          = ctx
    this.camera       = camera
    this.galaxyClient = galaxyClient
    this._routeManager = routeManager

    this._starRenderer   = new StarRenderer(ctx)
    this._debugRenderer  = new ChunkDebugRenderer(ctx)
    this._systemRenderer = new SystemRenderer(ctx)
    this._systemRenderer.colonyManager = colonyManager

    this.showDebug = false
    this.mouseX    = -1000
    this.mouseY    = -1000

    this._hoveredPlanet = null
    this._hoveredStar   = null
  }

  get hoveredPlanet() { return this._hoveredPlanet }
  get hoveredStar()   { return this._hoveredStar }

  render(canvasW, canvasH, _starCount) {
    const ctx    = this.ctx
    const camera = this.camera

    // ── Background ────────────────────────────────────────────────────────────
    ctx.fillStyle = '#05050c'
    ctx.fillRect(0, 0, canvasW, canvasH)

    // ── Debug overlay ─────────────────────────────────────────────────────────
    if (this.showDebug) {
      this._debugRenderer.render(this.galaxyClient, camera, canvasW, canvasH)
    }

    const bounds = camera.getViewportBounds(canvasW, canvasH)

    // ── Planetary systems ─────────────────────────────────────────────────────
    if (camera.zoom >= SYSTEM_ZOOM_THRESHOLD) {
      const systems = this.galaxyClient.getSystemsInViewport(bounds)
      for (const system of systems) {
        this._systemRenderer.render(system, camera, canvasW, canvasH)
      }
      this._hoveredPlanet = this._systemRenderer.updateHover(
        systems, this.mouseX, this.mouseY, camera, canvasW, canvasH,
      )
    } else {
      this._hoveredPlanet = null
    }

    // ── Stars ─────────────────────────────────────────────────────────────────
    const stars = this.galaxyClient.getStarsInViewport(bounds)
    this._starRenderer.render(stars, camera, canvasW, canvasH)
    // Only track hovered star when not in system view (planet hover takes priority)
    this._hoveredStar = camera.zoom < SYSTEM_ZOOM_THRESHOLD
      ? this._starRenderer.updateHover(stars, this.mouseX, this.mouseY, camera, canvasW, canvasH)
      : null

    // ── Transit ships ─────────────────────────────────────────────────────────
    this._renderTransitShips(canvasW, canvasH)

    // ── Tooltip ───────────────────────────────────────────────────────────────
    if (this._hoveredPlanet) {
      this._systemRenderer.renderTooltip(
        this._hoveredPlanet, this.mouseX, this.mouseY, canvasW, canvasH,
      )
    }
  }

  _renderTransitShips(canvasW, canvasH) {
    if (this.camera.zoom < 0.02) return

    // ── Colony ships ─────────────────────────────────────────────────────────
    const colonies = this._systemRenderer.colonyManager?.colonies ?? []
    for (const col of colonies) {
      if (col.status !== 'in_transit') continue
      const srcCol = this._systemRenderer.colonyManager?.getColony(col.sourcePlanetId)
      if (!srcCol?.planet || !col.planet) continue

      const t   = (col.transitProgressPct ?? 0) / 100
      const wx  = srcCol.planet.worldX + (col.planet.worldX - srcCol.planet.worldX) * t
      const wy  = srcCol.planet.worldY + (col.planet.worldY - srcCol.planet.worldY) * t
      const hdg = Math.atan2(
        col.planet.worldY - srcCol.planet.worldY,
        col.planet.worldX - srcCol.planet.worldX,
      ) + Math.PI / 2

      const { sx: x1, sy: y1 } = this.camera.worldToScreen(srcCol.planet.worldX, srcCol.planet.worldY, canvasW, canvasH)
      const { sx: x2, sy: y2 } = this.camera.worldToScreen(col.planet.worldX,    col.planet.worldY,    canvasW, canvasH)
      const { sx,     sy     } = this.camera.worldToScreen(wx, wy, canvasW, canvasH)

      this._drawTransitLine(x1, y1, x2, y2, 'rgba(255,170,68,0.12)')
      this._drawShipSprite(sx, sy, hdg, '#ffaa44', '#ffcc88')
    }

    // ── Trade route ships ─────────────────────────────────────────────────────
    const routes = this._routeManager?.routes ?? []
    for (const route of routes) {
      if (route.status === 'paused') continue
      const leg = route.currentLeg
      if (!leg || leg.fromWorldX == null || leg.toWorldX == null) continue

      const t   = (leg.progressPct ?? 0) / 100
      const wx  = leg.fromWorldX + (leg.toWorldX - leg.fromWorldX) * t
      const wy  = leg.fromWorldY + (leg.toWorldY - leg.fromWorldY) * t
      const hdg = Math.atan2(
        leg.toWorldY - leg.fromWorldY,
        leg.toWorldX - leg.fromWorldX,
      ) + Math.PI / 2

      const { sx: x1, sy: y1 } = this.camera.worldToScreen(leg.fromWorldX, leg.fromWorldY, canvasW, canvasH)
      const { sx: x2, sy: y2 } = this.camera.worldToScreen(leg.toWorldX,   leg.toWorldY,   canvasW, canvasH)
      const { sx,     sy     } = this.camera.worldToScreen(wx, wy, canvasW, canvasH)

      this._drawTransitLine(x1, y1, x2, y2, 'rgba(136,204,255,0.10)')
      this._drawShipSprite(sx, sy, hdg, '#88ccff', '#aaddff')
    }
  }

  _drawTransitLine(x1, y1, x2, y2, color) {
    const ctx = this.ctx
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.strokeStyle = color
    ctx.lineWidth   = 0.8
    ctx.setLineDash([3, 5])
    ctx.stroke()
    ctx.setLineDash([])
  }

  _drawShipSprite(sx, sy, heading, fill, stroke, size = 5) {
    const ctx = this.ctx
    ctx.save()
    ctx.translate(sx, sy)
    ctx.rotate(heading)
    ctx.beginPath()
    ctx.moveTo(0,            -size)
    ctx.lineTo( size * 0.55,  size * 0.7)
    ctx.lineTo(0,              size * 0.3)
    ctx.lineTo(-size * 0.55,  size * 0.7)
    ctx.closePath()
    ctx.fillStyle   = fill
    ctx.fill()
    ctx.strokeStyle = stroke
    ctx.lineWidth   = 0.7
    ctx.stroke()
    ctx.restore()
  }
}
