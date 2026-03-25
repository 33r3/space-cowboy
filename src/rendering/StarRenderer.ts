import type { StarData } from '../stars/StarProperties'
import { SpectralClass } from '../stars/SpectralClass'
import type { Camera } from './Camera'

const TWO_PI = Math.PI * 2

/** Minimum screen radius before we stop drawing a circle and use a pixel */
const CIRCLE_THRESHOLD_PX = 1.2

/**
 * Renders stars at multiple zoom levels:
 * - Overview  (zoom < 0.08):  ImageData pixel buffer — handles 50k+ stars at 60fps
 * - Mid       (0.08–15):      Canvas arc circles with optional glow
 * - Close     (zoom > 15):    Larger circles + name labels + habitable zone ring
 */
export class StarRenderer {
  private ctx: CanvasRenderingContext2D

  constructor(ctx: CanvasRenderingContext2D) {
    this.ctx = ctx
  }

  render(
    stars: StarData[],
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): void {
    if (stars.length === 0) return

    const zoom = camera.zoom

    if (zoom < 0.08) {
      this.renderOverview(stars, camera, canvasW, canvasH)
    } else if (zoom < 15) {
      this.renderMid(stars, camera, canvasW, canvasH)
    } else {
      this.renderClose(stars, camera, canvasW, canvasH)
    }
  }

  // ── Overview: pixel buffer ─────────────────────────────────────────────────

  private renderOverview(
    stars: StarData[],
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): void {
    const dpr = window.devicePixelRatio || 1
    const pw = Math.round(canvasW * dpr)
    const ph = Math.round(canvasH * dpr)

    const imageData = this.ctx.createImageData(pw, ph)
    const data = imageData.data

    for (const star of stars) {
      const { sx, sy } = camera.worldToScreen(star.worldX, star.worldY, canvasW, canvasH)
      const px = Math.round(sx * dpr)
      const py = Math.round(sy * dpr)
      if (px < 0 || px >= pw || py < 0 || py >= ph) continue

      const [r, g, b] = hexToRgb(star.color)
      // Brighten luminous stars slightly
      const brightness = Math.min(1.5, 0.5 + 0.5 * Math.log10(star.luminositySolar + 1))
      const idx = (py * pw + px) * 4

      // Additive blending: accumulate over the existing pixel
      data[idx]     = Math.min(255, (data[idx]     ?? 0) + r * brightness)
      data[idx + 1] = Math.min(255, (data[idx + 1] ?? 0) + g * brightness)
      data[idx + 2] = Math.min(255, (data[idx + 2] ?? 0) + b * brightness)
      data[idx + 3] = 255
    }

    // Reset transform to draw pixel-perfect, then restore
    this.ctx.save()
    this.ctx.setTransform(1, 0, 0, 1, 0, 0)
    this.ctx.putImageData(imageData, 0, 0)
    this.ctx.restore()
  }

  // ── Mid zoom: circles ──────────────────────────────────────────────────────

  private renderMid(
    stars: StarData[],
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): void {
    const ctx = this.ctx

    // Sort by luminosity ascending so bright stars are drawn on top
    const sorted = [...stars].sort((a, b) => a.luminositySolar - b.luminositySolar)

    for (const star of sorted) {
      const { sx, sy } = camera.worldToScreen(star.worldX, star.worldY, canvasW, canvasH)
      if (sx < -20 || sx > canvasW + 20 || sy < -20 || sy > canvasH + 20) continue

      // Screen radius grows with luminosity (log scale) and physical zoom
      const lumRadius = 1.0 + 0.9 * Math.log10(star.luminositySolar + 1)
      const screenRadius = Math.max(CIRCLE_THRESHOLD_PX, lumRadius * Math.min(camera.zoom * 0.001, 3))

      const isLuminous = star.spectralClass === SpectralClass.O
        || star.spectralClass === SpectralClass.B
        || star.spectralClass === SpectralClass.Supergiant

      if (isLuminous && screenRadius > 2) {
        // Glow halo
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

  // ── Close zoom: circles + labels + habitable zone ─────────────────────────

  private renderClose(
    stars: StarData[],
    camera: Camera,
    canvasW: number,
    canvasH: number,
  ): void {
    const ctx = this.ctx

    for (const star of stars) {
      const { sx, sy } = camera.worldToScreen(star.worldX, star.worldY, canvasW, canvasH)
      if (sx < -100 || sx > canvasW + 100 || sy < -100 || sy > canvasH + 100) continue

      // Physical size in pixels: solar radius ≈ 0.0000047 Ly, scaled up for visibility
      const SOLAR_RADIUS_LY = 0.0000047
      const physicalPx = star.radiusSolar * SOLAR_RADIUS_LY * camera.zoom
      const screenRadius = Math.max(3, Math.min(physicalPx, 40))

      // Glow
      const glowR = screenRadius * 5
      const grad = ctx.createRadialGradient(sx, sy, screenRadius, sx, sy, glowR)
      grad.addColorStop(0, star.color + 'cc')
      grad.addColorStop(1, star.color + '00')
      ctx.beginPath()
      ctx.arc(sx, sy, glowR, 0, TWO_PI)
      ctx.fillStyle = grad
      ctx.fill()

      // Star body
      ctx.beginPath()
      ctx.arc(sx, sy, screenRadius, 0, TWO_PI)
      ctx.fillStyle = star.color
      ctx.fill()

      // Habitable zone ring for G and K stars
      if (star.spectralClass === SpectralClass.G || star.spectralClass === SpectralClass.K) {
        const hzInner = Math.sqrt(star.luminositySolar / 1.1)  // AU
        const hzOuter = Math.sqrt(star.luminositySolar / 0.53) // AU
        const AU_TO_LY = 1 / 63_241
        const innerPx = hzInner * AU_TO_LY * camera.zoom
        const outerPx = hzOuter * AU_TO_LY * camera.zoom
        if (outerPx > 4) {
          ctx.beginPath()
          ctx.arc(sx, sy, innerPx, 0, TWO_PI)
          ctx.strokeStyle = 'rgba(100,220,100,0.18)'
          ctx.lineWidth = outerPx - innerPx
          ctx.stroke()
        }
      }

      // Name label
      ctx.font = '11px "Courier New", monospace'
      ctx.fillStyle = 'rgba(180,210,240,0.7)'
      ctx.fillText(star.name, sx + screenRadius + 4, sy + 4)

      // Spectral type tag
      ctx.font = '9px "Courier New", monospace'
      ctx.fillStyle = 'rgba(100,130,160,0.55)'
      ctx.fillText(`${star.spectralClass}${star.subclass}`, sx + screenRadius + 4, sy + 15)
    }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const rgbCache = new Map<string, [number, number, number]>()

function hexToRgb(hex: string): [number, number, number] {
  const cached = rgbCache.get(hex)
  if (cached) return cached
  const n = parseInt(hex.slice(1), 16)
  const result: [number, number, number] = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
  rgbCache.set(hex, result)
  return result
}
