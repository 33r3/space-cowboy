import { SpectralClass } from './constants.js'

const TWO_PI = Math.PI * 2
const CIRCLE_THRESHOLD_PX = 1.2

/**
 * Renders stars at multiple zoom levels:
 * - Overview  (zoom < 0.08):  ImageData pixel buffer
 * - Mid       (0.08–15):      Canvas arc circles with optional glow
 * - Close     (zoom > 15):    Larger circles + name labels + HZ ring
 */
export class StarRenderer {
  constructor(ctx) {
    this.ctx = ctx
  }

  render(stars, camera, canvasW, canvasH) {
    if (stars.length === 0) return
    const zoom = camera.zoom

    if (zoom < 0.08) {
      this._renderOverview(stars, camera, canvasW, canvasH)
    } else if (zoom < 15) {
      this._renderMid(stars, camera, canvasW, canvasH)
    } else {
      this._renderClose(stars, camera, canvasW, canvasH)
    }
  }

  _renderOverview(stars, camera, canvasW, canvasH) {
    const dpr = window.devicePixelRatio || 1
    const pw  = Math.round(canvasW * dpr)
    const ph  = Math.round(canvasH * dpr)

    const imageData = this.ctx.createImageData(pw, ph)
    const data = imageData.data

    for (const star of stars) {
      const { sx, sy } = camera.worldToScreen(star.worldX, star.worldY, canvasW, canvasH)
      const px = Math.round(sx * dpr)
      const py = Math.round(sy * dpr)
      if (px < 0 || px >= pw || py < 0 || py >= ph) continue

      const [r, g, b] = hexToRgb(star.color)
      const brightness = Math.min(1.5, 0.5 + 0.5 * Math.log10(star.luminositySolar + 1))
      const idx = (py * pw + px) * 4

      data[idx]     = Math.min(255, (data[idx]     ?? 0) + r * brightness)
      data[idx + 1] = Math.min(255, (data[idx + 1] ?? 0) + g * brightness)
      data[idx + 2] = Math.min(255, (data[idx + 2] ?? 0) + b * brightness)
      data[idx + 3] = 255
    }

    this.ctx.save()
    this.ctx.setTransform(1, 0, 0, 1, 0, 0)
    this.ctx.putImageData(imageData, 0, 0)
    this.ctx.restore()
  }

  _renderMid(stars, camera, canvasW, canvasH) {
    const ctx    = this.ctx
    const sorted = [...stars].sort((a, b) => a.luminositySolar - b.luminositySolar)

    for (const star of sorted) {
      const { sx, sy } = camera.worldToScreen(star.worldX, star.worldY, canvasW, canvasH)
      if (sx < -20 || sx > canvasW + 20 || sy < -20 || sy > canvasH + 20) continue

      const lumRadius  = 1.0 + 0.9 * Math.log10(star.luminositySolar + 1)
      const screenRadius = Math.max(CIRCLE_THRESHOLD_PX, lumRadius * Math.min(camera.zoom * 0.001, 3))

      const isLuminous = star.spectralClass === SpectralClass.O
        || star.spectralClass === SpectralClass.B
        || star.spectralClass === SpectralClass.Supergiant

      if (isLuminous && screenRadius > 2) {
        const glowRadius = screenRadius * 4
        const grad = ctx.createRadialGradient(sx, sy, screenRadius * 0.5, sx, sy, glowRadius)
        grad.addColorStop(0, star.color + 'aa')
        grad.addColorStop(1, star.color + '00')
        ctx.beginPath()
        ctx.arc(sx, sy, glowRadius, 0, TWO_PI)
        ctx.fillStyle = grad
        ctx.fill()
      }

      ctx.beginPath()
      ctx.arc(sx, sy, screenRadius, 0, TWO_PI)
      ctx.fillStyle = star.color
      ctx.fill()
    }
  }

  _renderClose(stars, camera, canvasW, canvasH) {
    const ctx = this.ctx

    for (const star of stars) {
      const { sx, sy } = camera.worldToScreen(star.worldX, star.worldY, canvasW, canvasH)
      if (sx < -100 || sx > canvasW + 100 || sy < -100 || sy > canvasH + 100) continue

      const SOLAR_RADIUS_LY = 0.0000047
      const physicalPx  = star.radiusSolar * SOLAR_RADIUS_LY * camera.zoom
      const screenRadius = Math.max(3, Math.min(physicalPx, 40))

      const glowR = screenRadius * 5
      const grad  = ctx.createRadialGradient(sx, sy, screenRadius, sx, sy, glowR)
      grad.addColorStop(0, star.color + 'cc')
      grad.addColorStop(1, star.color + '00')
      ctx.beginPath()
      ctx.arc(sx, sy, glowR, 0, TWO_PI)
      ctx.fillStyle = grad
      ctx.fill()

      ctx.beginPath()
      ctx.arc(sx, sy, screenRadius, 0, TWO_PI)
      ctx.fillStyle = star.color
      ctx.fill()

      if (star.spectralClass === SpectralClass.G || star.spectralClass === SpectralClass.K) {
        const hzInner = Math.sqrt(star.luminositySolar / 1.1)
        const hzOuter = Math.sqrt(star.luminositySolar / 0.53)
        const AU_TO_LY = 1 / 63_241
        const innerPx  = hzInner * AU_TO_LY * camera.zoom
        const outerPx  = hzOuter * AU_TO_LY * camera.zoom
        if (outerPx > 4) {
          ctx.beginPath()
          ctx.arc(sx, sy, innerPx, 0, TWO_PI)
          ctx.strokeStyle = 'rgba(100,220,100,0.18)'
          ctx.lineWidth   = outerPx - innerPx
          ctx.stroke()
        }
      }

      ctx.font = '11px "Courier New", monospace'
      ctx.fillStyle = 'rgba(180,210,240,0.7)'
      ctx.fillText(star.name, sx + screenRadius + 4, sy + 4)

      ctx.font = '9px "Courier New", monospace'
      ctx.fillStyle = 'rgba(100,130,160,0.55)'
      ctx.fillText(`${star.spectralClass}${star.subclass}`, sx + screenRadius + 4, sy + 15)
    }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const rgbCache = new Map()

function hexToRgb(hex) {
  const cached = rgbCache.get(hex)
  if (cached) return cached
  const n = parseInt(hex.slice(1), 16)
  const result = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
  rgbCache.set(hex, result)
  return result
}
