/**
 * RouteManager — fetches and maintains trade route state.
 * Communicates with /api/ships, /api/routes.
 * Polls /api/routes every 30 seconds to pick up completed legs.
 */
export class RouteManager {
  #routes   = []
  #onUpdate = null
  #poll     = null

  async init() {
    await this.#fetch()
    this.#poll = setInterval(() => this.#fetch(), 30_000)
  }

  // ── Accessors ──────────────────────────────────────────────────────────────

  get routes() { return this.#routes }

  /** Called after each background poll — use to refresh open routes panel. */
  set onUpdate(fn) { this.#onUpdate = fn }

  // ── Actions ────────────────────────────────────────────────────────────────

  /** Return ship classes available at a colony's dev level. */
  async getShipsForColony(planetId) {
    const encoded = encodeURIComponent(planetId)
    const resp    = await fetch(`/api/ships?planetId=${encoded}`)
    if (!resp.ok) throw new Error('Failed to fetch ship classes')
    return resp.json()
  }

  /**
   * Create a new trade route.
   * payload: { name, shipClass, legs: [{fromPlanetId, toPlanetId, cargo}] }
   * Returns the created route or throws on error.
   */
  async createRoute(payload) {
    const resp = await fetch('/api/routes', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error ?? 'Failed to create route')
    await this.#fetch()
    return data.route
  }

  /**
   * Delete a trade route by ID.
   * Does not refund setup cost or in-transit cargo.
   */
  async deleteRoute(routeId) {
    const encoded = encodeURIComponent(routeId)
    const resp    = await fetch(`/api/routes/${encoded}`, { method: 'DELETE' })
    const data    = await resp.json()
    if (!resp.ok) throw new Error(data.error ?? 'Failed to delete route')
    await this.#fetch()
  }

  // ── Private ────────────────────────────────────────────────────────────────

  async #fetch() {
    try {
      const data    = await fetch('/api/routes').then(r => r.json())
      this.#routes  = data.routes ?? []
      this.#onUpdate?.()
    } catch { /* ignore network errors */ }
  }
}
