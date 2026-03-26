/**
 * Manages canvas sizing with proper devicePixelRatio support.
 */
export class Viewport {
  constructor(canvas) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Failed to get 2D context from canvas')
    this.ctx = ctx

    this.width = 0
    this.height = 0
    this.physicalWidth = 0
    this.physicalHeight = 0
    this._resizeCallbacks = []

    this._resize()
    window.addEventListener('resize', () => this._resize())
  }

  _resize() {
    const dpr  = window.devicePixelRatio || 1
    const cssW = this.canvas.clientWidth
    const cssH = this.canvas.clientHeight

    this.width = cssW
    this.height = cssH
    this.physicalWidth  = Math.round(cssW * dpr)
    this.physicalHeight = Math.round(cssH * dpr)

    this.canvas.width  = this.physicalWidth
    this.canvas.height = this.physicalHeight

    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    for (const cb of this._resizeCallbacks) cb()
  }

  onResize(cb) {
    this._resizeCallbacks.push(cb)
  }
}
