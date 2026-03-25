/**
 * Manages canvas sizing with proper devicePixelRatio support.
 * CSS dimensions fill the window; backing buffer is scaled for crisp rendering.
 */
export class Viewport {
  readonly canvas: HTMLCanvasElement
  readonly ctx: CanvasRenderingContext2D

  /** CSS (logical) dimensions */
  width = 0
  height = 0

  /** Physical pixel dimensions (width * dpr) */
  physicalWidth = 0
  physicalHeight = 0

  private onResizeCallbacks: Array<() => void> = []

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Failed to get 2D context from canvas')
    this.ctx = ctx

    this.resize()
    window.addEventListener('resize', () => this.resize())
  }

  private resize(): void {
    const dpr = window.devicePixelRatio || 1
    const cssW = this.canvas.clientWidth
    const cssH = this.canvas.clientHeight

    this.width = cssW
    this.height = cssH
    this.physicalWidth  = Math.round(cssW * dpr)
    this.physicalHeight = Math.round(cssH * dpr)

    this.canvas.width  = this.physicalWidth
    this.canvas.height = this.physicalHeight

    // Scale all drawing operations so we work in logical CSS pixels
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    for (const cb of this.onResizeCallbacks) cb()
  }

  onResize(cb: () => void): void {
    this.onResizeCallbacks.push(cb)
  }
}
