const MIN_ZOOM = 0.0005
const MAX_ZOOM = 2000

/**
 * Camera for a 2D world.
 * worldX/worldY is the world-space position at the center of the screen.
 * zoom is in pixels per light-year.
 */
export class Camera {
  constructor(worldX = 0, worldY = 0, zoom = 0.5) {
    this.worldX = worldX
    this.worldY = worldY
    this.zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom))
  }

  worldToScreen(wx, wy, canvasW, canvasH) {
    return {
      sx: (wx - this.worldX) * this.zoom + canvasW / 2,
      sy: (wy - this.worldY) * this.zoom + canvasH / 2,
    }
  }

  screenToWorld(sx, sy, canvasW, canvasH) {
    return {
      wx: (sx - canvasW / 2) / this.zoom + this.worldX,
      wy: (sy - canvasH / 2) / this.zoom + this.worldY,
    }
  }

  getViewportBounds(canvasW, canvasH) {
    const halfW = (canvasW / 2) / this.zoom
    const halfH = (canvasH / 2) / this.zoom
    return {
      minX: this.worldX - halfW,
      minY: this.worldY - halfH,
      maxX: this.worldX + halfW,
      maxY: this.worldY + halfH,
    }
  }

  pan(dsx, dsy) {
    this.worldX -= dsx / this.zoom
    this.worldY -= dsy / this.zoom
  }

  zoomAt(factor, sx, sy, canvasW, canvasH) {
    const { wx, wy } = this.screenToWorld(sx, sy, canvasW, canvasH)
    this.zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, this.zoom * factor))
    const newScreen = this.worldToScreen(wx, wy, canvasW, canvasH)
    this.worldX += (newScreen.sx - sx) / this.zoom
    this.worldY += (newScreen.sy - sy) / this.zoom
  }

  smoothTo(targetX, targetY, targetZoom, alpha) {
    this.worldX = this.worldX + (targetX - this.worldX) * alpha
    this.worldY = this.worldY + (targetY - this.worldY) * alpha
    this.zoom   = this.zoom   + (targetZoom - this.zoom) * alpha
  }
}
