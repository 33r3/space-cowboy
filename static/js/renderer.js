import { StarRenderer } from './star_renderer.js'
import { ChunkDebugRenderer } from './chunk_debug_renderer.js'
import { SystemRenderer } from './system_renderer.js'

const SYSTEM_ZOOM_THRESHOLD = 1.5

export class Renderer {
  constructor(ctx, camera, galaxyClient) {
    this.ctx          = ctx
    this.camera       = camera
    this.galaxyClient = galaxyClient

    this._starRenderer  = new StarRenderer(ctx)
    this._debugRenderer = new ChunkDebugRenderer(ctx)
    this._systemRenderer = new SystemRenderer(ctx)

    this.showDebug = false
    this.mouseX    = -1000
    this.mouseY    = -1000

    this._hoveredPlanet = null
  }

  render(canvasW, canvasH, ship, _starCount) {
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

    // ── Ship ─────────────────────────────────────────────────────────────────
    this._renderShip(ship, canvasW, canvasH)

    // ── Waypoints ─────────────────────────────────────────────────────────────
    this._renderWaypoints(ship, canvasW, canvasH)

    // ── Tooltip ───────────────────────────────────────────────────────────────
    if (this._hoveredPlanet) {
      this._systemRenderer.renderTooltip(
        this._hoveredPlanet, this.mouseX, this.mouseY, canvasW, canvasH,
      )
    }
  }

  _renderShip(ship, canvasW, canvasH) {
    const ctx = this.ctx
    const { sx, sy } = this.camera.worldToScreen(ship.worldX, ship.worldY, canvasW, canvasH)

    const SIZE  = 7
    const angle = ship.heading

    ctx.save()
    ctx.translate(sx, sy)
    ctx.rotate(angle)

    ctx.beginPath()
    ctx.moveTo(0, -SIZE)
    ctx.lineTo(SIZE * 0.55, SIZE * 0.7)
    ctx.lineTo(0, SIZE * 0.3)
    ctx.lineTo(-SIZE * 0.55, SIZE * 0.7)
    ctx.closePath()
    ctx.fillStyle   = '#88ccff'
    ctx.fill()
    ctx.strokeStyle = '#aaddff'
    ctx.lineWidth   = 0.8
    ctx.stroke()

    if (ship.isMoving) {
      ctx.beginPath()
      ctx.arc(0, SIZE * 0.5, SIZE * 0.3, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(100,180,255,0.6)'
      ctx.fill()
    }

    ctx.restore()

    const exploreRadiusPx = ship.exploreRadiusLy * this.camera.zoom
    if (exploreRadiusPx > 10 && exploreRadiusPx < canvasW) {
      ctx.beginPath()
      ctx.arc(sx, sy, exploreRadiusPx, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(60,100,140,0.15)'
      ctx.lineWidth   = 1
      ctx.stroke()
    }
  }

  _renderWaypoints(ship, canvasW, canvasH) {
    const ctx       = this.ctx
    const waypoints = ship.getWaypoints()
    if (waypoints.length === 0) return

    const allPoints = [{ x: ship.worldX, y: ship.worldY }, ...waypoints]

    ctx.beginPath()
    const first = allPoints[0]
    if (!first) return
    const start = this.camera.worldToScreen(first.x, first.y, canvasW, canvasH)
    ctx.moveTo(start.sx, start.sy)

    for (let i = 1; i < allPoints.length; i++) {
      const pt = allPoints[i]
      if (!pt) continue
      const { sx, sy } = this.camera.worldToScreen(pt.x, pt.y, canvasW, canvasH)
      ctx.lineTo(sx, sy)
    }

    ctx.strokeStyle = 'rgba(80,140,200,0.35)'
    ctx.lineWidth   = 1
    ctx.setLineDash([4, 6])
    ctx.stroke()
    ctx.setLineDash([])

    for (let i = 1; i < waypoints.length; i++) {
      const wp = waypoints[i]
      if (!wp) continue
      const { sx, sy } = this.camera.worldToScreen(wp.x, wp.y, canvasW, canvasH)
      ctx.beginPath()
      ctx.arc(sx, sy, 2.5, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(80,160,220,0.5)'
      ctx.fill()
    }

    const dest = waypoints[waypoints.length - 1]
    if (dest) {
      const { sx, sy } = this.camera.worldToScreen(dest.x, dest.y, canvasW, canvasH)
      ctx.beginPath()
      ctx.arc(sx, sy, 4, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(100,180,255,0.5)'
      ctx.lineWidth   = 1.2
      ctx.stroke()
    }
  }
}
