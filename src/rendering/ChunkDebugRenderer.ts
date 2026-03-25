import type { Camera } from './Camera'
import type { GalaxyManager } from '../galaxy/GalaxyManager'
import { chunkToWorldMin, chunksInBounds } from '../galaxy/ChunkCoord'

/**
 * Optional debug overlay that draws chunk grid boundaries and star counts.
 * Toggle with the D key.
 */
export class ChunkDebugRenderer {
  private ctx: CanvasRenderingContext2D

  constructor(ctx: CanvasRenderingContext2D) {
    this.ctx = ctx
  }

  render(galaxyManager: GalaxyManager, camera: Camera, canvasW: number, canvasH: number): void {
    const ctx = this.ctx
    const bounds = camera.getViewportBounds(canvasW, canvasH)
    const chunkSize = galaxyManager.chunkSizeLy
    const coords = chunksInBounds(bounds, chunkSize)

    ctx.save()
    ctx.lineWidth = 0.5
    ctx.font = '9px "Courier New", monospace'

    for (const coord of coords) {
      const min = chunkToWorldMin(coord, chunkSize)
      const { sx: x0, sy: y0 } = camera.worldToScreen(min.x, min.y, canvasW, canvasH)
      const { sx: x1, sy: y1 } = camera.worldToScreen(min.x + chunkSize, min.y + chunkSize, canvasW, canvasH)
      const w = x1 - x0
      const h = y1 - y0

      const chunk = galaxyManager.getChunk(coord)
      const isGenerated = chunk !== undefined

      ctx.strokeStyle = isGenerated ? 'rgba(0,80,120,0.4)' : 'rgba(60,30,0,0.25)'
      ctx.strokeRect(x0, y0, w, h)

      if (isGenerated && chunk) {
        ctx.fillStyle = 'rgba(0,120,180,0.5)'
        ctx.fillText(`${chunk.stars.length}★`, x0 + 3, y0 + 12)
        ctx.fillStyle = 'rgba(40,80,100,0.4)'
        ctx.fillText(`${coord.cx},${coord.cy}`, x0 + 3, y0 + 23)
      }
    }

    ctx.restore()
  }
}
