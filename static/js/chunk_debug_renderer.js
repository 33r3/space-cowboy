/**
 * Optional debug overlay — chunk grid + star counts.
 * Toggle with the D key.
 */
export class ChunkDebugRenderer {
  constructor(ctx) {
    this.ctx = ctx
  }

  render(galaxyClient, camera, canvasW, canvasH) {
    const ctx       = this.ctx
    const bounds    = camera.getViewportBounds(canvasW, canvasH)
    const chunkSize = galaxyClient.chunkSizeLy

    const minCx = Math.floor(bounds.minX / chunkSize)
    const minCy = Math.floor(bounds.minY / chunkSize)
    const maxCx = Math.floor((bounds.maxX - 0.001) / chunkSize)
    const maxCy = Math.floor((bounds.maxY - 0.001) / chunkSize)

    ctx.save()
    ctx.lineWidth = 0.5
    ctx.font = '9px "Courier New", monospace'

    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        const minWX = cx * chunkSize
        const minWY = cy * chunkSize
        const { sx: x0, sy: y0 } = camera.worldToScreen(minWX, minWY, canvasW, canvasH)
        const { sx: x1, sy: y1 } = camera.worldToScreen(minWX + chunkSize, minWY + chunkSize, canvasW, canvasH)
        const w = x1 - x0
        const h = y1 - y0

        const key     = `${cx},${cy}`
        const isGenerated = galaxyClient.generatedChunkCount > 0   // rough indicator

        ctx.strokeStyle = 'rgba(0,80,120,0.4)'
        ctx.strokeRect(x0, y0, w, h)

        ctx.fillStyle = 'rgba(40,80,100,0.4)'
        ctx.fillText(`${cx},${cy}`, x0 + 3, y0 + 12)
      }
    }

    ctx.restore()
  }
}
