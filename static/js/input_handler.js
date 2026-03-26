const ZOOM_FACTOR_SCROLL = 1.12
const ZOOM_FACTOR_KEY    = 1.08

export class InputHandler {
  constructor(canvas, camera, ship, viewport) {
    this.camera   = camera
    this.ship     = ship
    this.viewport = viewport

    this._isDragging  = false
    this._dragStartX  = 0
    this._dragStartY  = 0
    this._lastMouseX  = 0
    this._lastMouseY  = 0
    this._hasDragged  = false
    this._touches     = new Map()
    this._lastPinchDist = 0
    this._keys        = new Set()

    this.onDebugToggle = null
    this.onCameraReset = null
    this.onCanvasClick = null   // fired with {clientX, clientY} on non-drag left click

    this._onMouseDown = (e) => {
      if (e.button !== 0) return
      this._isDragging = true
      this._hasDragged = false
      this._dragStartX = e.clientX
      this._dragStartY = e.clientY
      this._lastMouseX = e.clientX
      this._lastMouseY = e.clientY
    }

    this._onMouseMove = (e) => {
      if (!this._isDragging) return
      const dx = e.clientX - this._lastMouseX
      const dy = e.clientY - this._lastMouseY
      this._lastMouseX = e.clientX
      this._lastMouseY = e.clientY

      if (Math.abs(e.clientX - this._dragStartX) > 4 || Math.abs(e.clientY - this._dragStartY) > 4) {
        this._hasDragged = true
      }
      this.camera.pan(dx, dy)
    }

    this._onMouseUp = (e) => {
      if (!this._isDragging) return
      this._isDragging = false

      if (!this._hasDragged && e.button === 0) {
        this.onCanvasClick?.({ clientX: e.clientX, clientY: e.clientY })
        const { wx, wy } = this.camera.screenToWorld(
          e.clientX, e.clientY, this.viewport.width, this.viewport.height,
        )
        if (e.shiftKey) {
          this.ship.addWaypoint(wx, wy)
        } else {
          this.ship.setDestination(wx, wy)
        }
      }
    }

    this._onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY < 0 ? ZOOM_FACTOR_SCROLL : 1 / ZOOM_FACTOR_SCROLL
      this.camera.zoomAt(factor, e.clientX, e.clientY, this.viewport.width, this.viewport.height)
    }

    this._onTouchStart = (e) => {
      e.preventDefault()
      for (const t of Array.from(e.changedTouches)) {
        this._touches.set(t.identifier, { x: t.clientX, y: t.clientY })
      }
      if (this._touches.size === 2) {
        this._lastPinchDist = this._getPinchDist()
      }
    }

    this._onTouchMove = (e) => {
      e.preventDefault()
      const prev = new Map(this._touches)
      for (const t of Array.from(e.changedTouches)) {
        this._touches.set(t.identifier, { x: t.clientX, y: t.clientY })
      }
      if (this._touches.size === 1) {
        const id  = Array.from(this._touches.keys())[0]
        const cur = this._touches.get(id)
        const old = prev.get(id)
        if (cur && old) this.camera.pan(cur.x - old.x, cur.y - old.y)
      } else if (this._touches.size === 2) {
        const newDist = this._getPinchDist()
        if (this._lastPinchDist > 0) {
          const factor = newDist / this._lastPinchDist
          const center = this._getPinchCenter()
          this.camera.zoomAt(factor, center.x, center.y, this.viewport.width, this.viewport.height)
        }
        this._lastPinchDist = newDist
      }
    }

    this._onTouchEnd = (e) => {
      for (const t of Array.from(e.changedTouches)) {
        this._touches.delete(t.identifier)
      }
      this._lastPinchDist = 0
    }

    this._onKeyDown = (e) => {
      this._keys.add(e.key)

      if (e.key === '+' || e.key === '=') {
        this.camera.zoomAt(ZOOM_FACTOR_KEY, this.viewport.width / 2, this.viewport.height / 2,
          this.viewport.width, this.viewport.height)
      }
      if (e.key === '-') {
        this.camera.zoomAt(1 / ZOOM_FACTOR_KEY, this.viewport.width / 2, this.viewport.height / 2,
          this.viewport.width, this.viewport.height)
      }
      if (e.key.toLowerCase() === 'd' && !e.shiftKey) {
        this.onDebugToggle?.()
      }
      if (e.key.toLowerCase() === 'r') {
        this.onCameraReset?.()
      }
      if (e.key.toLowerCase() === 't') {
        this.onRoutesToggle?.()
      }
      if (e.key.toLowerCase() === 'l') {
        this.onColonyListToggle?.()
      }
      if (e.key === 'Escape') {
        this.ship.clearWaypoints()
      }
    }

    this._onKeyUp = (e) => {
      this._keys.delete(e.key)
    }

    canvas.addEventListener('mousedown',   this._onMouseDown)
    canvas.addEventListener('mousemove',   this._onMouseMove)
    canvas.addEventListener('mouseup',     this._onMouseUp)
    canvas.addEventListener('mouseleave',  this._onMouseUp)
    canvas.addEventListener('wheel',       this._onWheel, { passive: false })
    canvas.addEventListener('contextmenu', e => e.preventDefault())

    canvas.addEventListener('touchstart',  this._onTouchStart, { passive: false })
    canvas.addEventListener('touchmove',   this._onTouchMove,  { passive: false })
    canvas.addEventListener('touchend',    this._onTouchEnd)
    canvas.addEventListener('touchcancel', this._onTouchEnd)

    window.addEventListener('keydown', this._onKeyDown)
    window.addEventListener('keyup',   this._onKeyUp)
  }

  update() {
    const panSpeed = 400 / this.camera.zoom
    const dt = 1 / 60

    if (this._keys.has('ArrowLeft')  || this._keys.has('a')) this.camera.worldX -= panSpeed * dt
    if (this._keys.has('ArrowRight') || this._keys.has('d')) this.camera.worldX += panSpeed * dt
    if (this._keys.has('ArrowUp')    || this._keys.has('w')) this.camera.worldY -= panSpeed * dt
    if (this._keys.has('ArrowDown')  || this._keys.has('s')) this.camera.worldY += panSpeed * dt
  }

  _getPinchDist() {
    const pts = Array.from(this._touches.values())
    if (pts.length < 2) return 0
    const a = pts[0], b = pts[1]
    return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
  }

  _getPinchCenter() {
    const pts = Array.from(this._touches.values())
    if (pts.length < 2) return { x: 0, y: 0 }
    const a = pts[0], b = pts[1]
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  }
}
