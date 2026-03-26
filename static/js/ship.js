const DEFAULT_EXPLORE_RADIUS_LY = 800

export class Ship {
  constructor(worldX = 0, worldY = 0, speed = 80, exploreRadiusLy = DEFAULT_EXPLORE_RADIUS_LY) {
    this.worldX = worldX
    this.worldY = worldY
    this.speed  = speed
    this.exploreRadiusLy = exploreRadiusLy
    this.heading  = -Math.PI / 2
    this.isMoving = false
    this._waypoints = []
  }

  update(dtSec) {
    if (this._waypoints.length === 0) {
      this.isMoving = false
      return
    }

    this.isMoving = true
    let remaining = this.speed * dtSec

    while (remaining > 0 && this._waypoints.length > 0) {
      const target = this._waypoints[0]
      if (!target) break

      const dx   = target.x - this.worldX
      const dy   = target.y - this.worldY
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < 0.001) {
        this._waypoints.shift()
        continue
      }

      this.heading = Math.atan2(dy, dx)

      if (dist <= remaining) {
        this.worldX = target.x
        this.worldY = target.y
        remaining  -= dist
        this._waypoints.shift()
      } else {
        const t = remaining / dist
        this.worldX += dx * t
        this.worldY += dy * t
        remaining = 0
      }
    }

    if (this._waypoints.length === 0) this.isMoving = false
  }

  setDestination(worldX, worldY) {
    this._waypoints = [{ x: worldX, y: worldY }]
  }

  addWaypoint(worldX, worldY) {
    this._waypoints.push({ x: worldX, y: worldY })
  }

  clearWaypoints() {
    this._waypoints = []
    this.isMoving = false
  }

  getWaypoints() {
    return this._waypoints
  }

  getExplorationBounds() {
    const r = this.exploreRadiusLy
    return {
      minX: this.worldX - r,
      minY: this.worldY - r,
      maxX: this.worldX + r,
      maxY: this.worldY + r,
    }
  }
}
