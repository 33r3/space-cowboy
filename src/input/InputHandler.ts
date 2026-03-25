import type { Camera } from '../rendering/Camera'
import type { Ship } from '../exploration/Ship'
import type { Viewport } from './Viewport'

const ZOOM_FACTOR_SCROLL = 1.12
const ZOOM_FACTOR_KEY    = 1.08

export class InputHandler {
  private camera: Camera
  private ship: Ship
  private viewport: Viewport

  private isDragging = false
  private dragStartX = 0
  private dragStartY = 0
  private lastMouseX = 0
  private lastMouseY = 0
  private hasDragged = false

  // Touch tracking for pinch-zoom
  private touches: Map<number, { x: number; y: number }> = new Map()
  private lastPinchDist = 0

  // Keyboard state
  private keys = new Set<string>()

  onDebugToggle?: () => void
  onCameraReset?: () => void

  constructor(canvas: HTMLCanvasElement, camera: Camera, ship: Ship, viewport: Viewport) {
    this.camera = camera
    this.ship = ship
    this.viewport = viewport

    canvas.addEventListener('mousedown', this.onMouseDown)
    canvas.addEventListener('mousemove', this.onMouseMove)
    canvas.addEventListener('mouseup',   this.onMouseUp)
    canvas.addEventListener('mouseleave', this.onMouseUp)
    canvas.addEventListener('wheel',     this.onWheel, { passive: false })
    canvas.addEventListener('contextmenu', e => e.preventDefault())

    canvas.addEventListener('touchstart', this.onTouchStart, { passive: false })
    canvas.addEventListener('touchmove',  this.onTouchMove,  { passive: false })
    canvas.addEventListener('touchend',   this.onTouchEnd)
    canvas.addEventListener('touchcancel', this.onTouchEnd)

    window.addEventListener('keydown', this.onKeyDown)
    window.addEventListener('keyup',   this.onKeyUp)
  }

  /** Call once per frame to handle held keys */
  update(): void {
    const panSpeed = 400 / this.camera.zoom  // constant screen-space speed
    const dt = 1 / 60  // approximate

    if (this.keys.has('ArrowLeft')  || this.keys.has('a'))
      this.camera.worldX -= panSpeed * dt
    if (this.keys.has('ArrowRight') || this.keys.has('d'))
      this.camera.worldX += panSpeed * dt
    if (this.keys.has('ArrowUp')    || this.keys.has('w'))
      this.camera.worldY -= panSpeed * dt
    if (this.keys.has('ArrowDown') || this.keys.has('s'))
      this.camera.worldY += panSpeed * dt
  }

  // ── Mouse ────────────────────────────────────────────────────────────────

  private onMouseDown = (e: MouseEvent): void => {
    if (e.button !== 0) return
    this.isDragging = true
    this.hasDragged = false
    this.dragStartX = e.clientX
    this.dragStartY = e.clientY
    this.lastMouseX = e.clientX
    this.lastMouseY = e.clientY
  }

  private onMouseMove = (e: MouseEvent): void => {
    if (!this.isDragging) return
    const dx = e.clientX - this.lastMouseX
    const dy = e.clientY - this.lastMouseY
    this.lastMouseX = e.clientX
    this.lastMouseY = e.clientY

    if (Math.abs(e.clientX - this.dragStartX) > 4 || Math.abs(e.clientY - this.dragStartY) > 4) {
      this.hasDragged = true
    }

    this.camera.pan(dx, dy)
  }

  private onMouseUp = (e: MouseEvent): void => {
    if (!this.isDragging) return
    this.isDragging = false

    if (!this.hasDragged && e.button === 0) {
      // Click without drag → set ship destination
      const { wx, wy } = this.camera.screenToWorld(
        e.clientX, e.clientY,
        this.viewport.width, this.viewport.height,
      )
      if (e.shiftKey) {
        this.ship.addWaypoint(wx, wy)
      } else {
        this.ship.setDestination(wx, wy)
      }
    }
  }

  private onWheel = (e: WheelEvent): void => {
    e.preventDefault()
    const factor = e.deltaY < 0 ? ZOOM_FACTOR_SCROLL : 1 / ZOOM_FACTOR_SCROLL
    this.camera.zoomAt(factor, e.clientX, e.clientY, this.viewport.width, this.viewport.height)
  }

  // ── Touch ────────────────────────────────────────────────────────────────

  private onTouchStart = (e: TouchEvent): void => {
    e.preventDefault()
    for (const t of Array.from(e.changedTouches)) {
      this.touches.set(t.identifier, { x: t.clientX, y: t.clientY })
    }
    if (this.touches.size === 2) {
      this.lastPinchDist = this.getPinchDist()
    }
  }

  private onTouchMove = (e: TouchEvent): void => {
    e.preventDefault()
    const prev = new Map(this.touches)

    for (const t of Array.from(e.changedTouches)) {
      this.touches.set(t.identifier, { x: t.clientX, y: t.clientY })
    }

    if (this.touches.size === 1) {
      // Pan
      const id = Array.from(this.touches.keys())[0]
      if (id === undefined) return
      const cur = this.touches.get(id)
      const old = prev.get(id)
      if (!cur || !old) return
      this.camera.pan(cur.x - old.x, cur.y - old.y)
    } else if (this.touches.size === 2) {
      // Pinch zoom
      const newDist = this.getPinchDist()
      if (this.lastPinchDist > 0) {
        const factor = newDist / this.lastPinchDist
        const center = this.getPinchCenter()
        this.camera.zoomAt(factor, center.x, center.y, this.viewport.width, this.viewport.height)
      }
      this.lastPinchDist = newDist
    }
  }

  private onTouchEnd = (e: TouchEvent): void => {
    for (const t of Array.from(e.changedTouches)) {
      this.touches.delete(t.identifier)
    }
    this.lastPinchDist = 0
  }

  private getPinchDist(): number {
    const pts = Array.from(this.touches.values())
    if (pts.length < 2) return 0
    const a = pts[0]!
    const b = pts[1]!
    return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
  }

  private getPinchCenter(): { x: number; y: number } {
    const pts = Array.from(this.touches.values())
    if (pts.length < 2) return { x: 0, y: 0 }
    const a = pts[0]!
    const b = pts[1]!
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  }

  // ── Keyboard ──────────────────────────────────────────────────────────────

  private onKeyDown = (e: KeyboardEvent): void => {
    this.keys.add(e.key)

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
    if (e.key === 'Escape') {
      this.ship.clearWaypoints()
    }
  }

  private onKeyUp = (e: KeyboardEvent): void => {
    this.keys.delete(e.key)
  }
}
