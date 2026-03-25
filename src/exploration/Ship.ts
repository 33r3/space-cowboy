import type { Vec2 } from '../math/vec2'

/** Radius around the ship within which chunks are generated (light-years) */
const DEFAULT_EXPLORE_RADIUS_LY = 800  // 4 chunks worth

export class Ship {
  worldX: number
  worldY: number

  /** Speed in light-years per second (game time) */
  speed: number

  /** Current heading in radians (0 = up / north) */
  heading = -Math.PI / 2  // start pointing right

  /** Whether the ship is currently traveling */
  isMoving = false

  readonly exploreRadiusLy: number

  private waypoints: Vec2[] = []

  constructor(worldX = 0, worldY = 0, speed = 80, exploreRadiusLy = DEFAULT_EXPLORE_RADIUS_LY) {
    this.worldX = worldX
    this.worldY = worldY
    this.speed = speed
    this.exploreRadiusLy = exploreRadiusLy
  }

  update(dtSec: number): void {
    if (this.waypoints.length === 0) {
      this.isMoving = false
      return
    }

    this.isMoving = true
    let remaining = this.speed * dtSec

    while (remaining > 0 && this.waypoints.length > 0) {
      const target = this.waypoints[0]
      if (!target) break

      const dx = target.x - this.worldX
      const dy = target.y - this.worldY
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < 0.001) {
        this.waypoints.shift()
        continue
      }

      this.heading = Math.atan2(dy, dx)

      if (dist <= remaining) {
        // Reach this waypoint
        this.worldX = target.x
        this.worldY = target.y
        remaining -= dist
        this.waypoints.shift()
      } else {
        // Move toward waypoint
        const t = remaining / dist
        this.worldX += dx * t
        this.worldY += dy * t
        remaining = 0
      }
    }

    if (this.waypoints.length === 0) this.isMoving = false
  }

  setDestination(worldX: number, worldY: number): void {
    this.waypoints = [{ x: worldX, y: worldY }]
  }

  addWaypoint(worldX: number, worldY: number): void {
    this.waypoints.push({ x: worldX, y: worldY })
  }

  clearWaypoints(): void {
    this.waypoints = []
    this.isMoving = false
  }

  getWaypoints(): readonly Vec2[] {
    return this.waypoints
  }

  getExplorationBounds(): { minX: number; minY: number; maxX: number; maxY: number } {
    const r = this.exploreRadiusLy
    return {
      minX: this.worldX - r,
      minY: this.worldY - r,
      maxX: this.worldX + r,
      maxY: this.worldY + r,
    }
  }
}
