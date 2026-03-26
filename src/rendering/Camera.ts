import type { WorldBounds } from '../galaxy/ChunkCoord'

const MIN_ZOOM = 0.0005   // ~100,000 Ly across screen
const MAX_ZOOM = 2000     // close-up planetary systems (1 AU ≈ 1200 px at max)

/**
 * Camera for a 2D world.
 * `worldX/worldY` is the world-space position at the center of the screen.
 * `zoom` is in pixels per light-year.
 */
export class Camera {
  worldX: number
  worldY: number
  zoom: number

  constructor(worldX = 0, worldY = 0, zoom = 0.5) {
    this.worldX = worldX
    this.worldY = worldY
    this.zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom))
  }

  worldToScreen(wx: number, wy: number, canvasW: number, canvasH: number): { sx: number; sy: number } {
    return {
      sx: (wx - this.worldX) * this.zoom + canvasW / 2,
      sy: (wy - this.worldY) * this.zoom + canvasH / 2,
    }
  }

  screenToWorld(sx: number, sy: number, canvasW: number, canvasH: number): { wx: number; wy: number } {
    return {
      wx: (sx - canvasW / 2) / this.zoom + this.worldX,
      wy: (sy - canvasH / 2) / this.zoom + this.worldY,
    }
  }

  getViewportBounds(canvasW: number, canvasH: number): WorldBounds {
    const halfW = (canvasW / 2) / this.zoom
    const halfH = (canvasH / 2) / this.zoom
    return {
      minX: this.worldX - halfW,
      minY: this.worldY - halfH,
      maxX: this.worldX + halfW,
      maxY: this.worldY + halfH,
    }
  }

  /** Pan by a delta in screen pixels */
  pan(dsx: number, dsy: number): void {
    this.worldX -= dsx / this.zoom
    this.worldY -= dsy / this.zoom
  }

  /** Zoom centered on a screen-space point */
  zoomAt(factor: number, sx: number, sy: number, canvasW: number, canvasH: number): void {
    const { wx, wy } = this.screenToWorld(sx, sy, canvasW, canvasH)
    this.zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, this.zoom * factor))
    // Adjust world position so the point under the cursor stays fixed
    const newScreen = this.worldToScreen(wx, wy, canvasW, canvasH)
    this.worldX += (newScreen.sx - sx) / this.zoom
    this.worldY += (newScreen.sy - sy) / this.zoom
  }

  /** Smoothly interpolate toward a target position and zoom */
  smoothTo(targetX: number, targetY: number, targetZoom: number, alpha: number): void {
    this.worldX = this.worldX + (targetX - this.worldX) * alpha
    this.worldY = this.worldY + (targetY - this.worldY) * alpha
    this.zoom   = this.zoom   + (targetZoom - this.zoom)   * alpha
  }
}
