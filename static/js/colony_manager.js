/**
 * ColonyManager — fetches and maintains homeworld + colony state.
 * Communicates with /api/homeworld and /api/colonies.
 * Polls /api/colonies every 30 seconds to pick up tick-advanced state.
 */
export class ColonyManager {
  #homeworldData = null   // full API response (planet, star, cx, cy, starIndex)
  #colonyIds     = new Set()
  #colonies      = []     // enriched colony records from server
  #ready         = false
  #onUpdate      = null   // callback fired after each poll refresh
  #pollInterval  = null

  async init() {
    await Promise.all([this.#fetchHomeworld(), this.#fetchColonies()])
    this.#ready = true
    // Poll every 30 seconds so UI reflects auto-ticked stockpiles
    this.#pollInterval = setInterval(() => this.#fetchColonies(), 30_000)
  }

  // ── Accessors ──────────────────────────────────────────────────────────────

  get ready()      { return this.#ready }
  get homeworld()  { return this.#homeworldData }
  get colonies()   { return this.#colonies }

  /** Called after each background poll — use to refresh open colony panel. */
  set onUpdate(fn) { this.#onUpdate = fn }

  isHomeworld(planetId) {
    return this.#homeworldData?.planet?.id === planetId
  }

  isColony(planetId) {
    return this.#colonyIds.has(planetId)
  }

  /** True only if the colony ship is still in transit (not yet established). */
  isInTransit(planetId) {
    return this.getColony(planetId)?.status === 'in_transit'
  }

  /**
   * True if the colony is fully active (has a running economy).
   * Excludes in_transit and abandoned colonies.
   */
  isActiveColony(planetId) {
    if (this.isHomeworld(planetId)) return true
    const col = this.getColony(planetId)
    return col != null && col.status !== 'in_transit' && col.status !== 'abandoned'
  }

  /** Return the enriched colony record for a planet, or null. */
  getColony(planetId) {
    return this.#colonies.find(c => c.planetId === planetId) ?? null
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /**
   * Found a colony on the given planet.
   * planet must have an `index` field (its position index in the system).
   * Returns the created colony record, or throws on error.
   */
  async foundColony(planet, cx, cy, starIndex, sourcePlanetId = undefined) {
    const body = { cx, cy, starIndex, planetIndex: planet.index }
    if (sourcePlanetId !== undefined) body.sourcePlanetId = sourcePlanetId
    const resp = await fetch('/api/colonies', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error ?? 'Failed to found colony')
    // Refresh full list so economics fields are populated
    await this.#fetchColonies()
    return this.getColony(planet.id)
  }

  /**
   * Upgrade development level of a colony.
   * Returns updated enriched colony record, or throws on error.
   */
  async upgradeColony(planetId) {
    const encoded = encodeURIComponent(planetId)
    const resp = await fetch(`/api/colonies/${encoded}/upgrade`, { method: 'POST' })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error ?? 'Upgrade failed')
    // Replace in local cache
    const updated = data.colony
    this.#colonies = this.#colonies.map(c => c.planetId === planetId ? updated : c)
    return updated
  }

  /**
   * Check whether a planet can be colonized and at what cost.
   * Returns the API response object (eligible true/false + details).
   */
  async getColonizationPreview(cx, cy, starIndex, planetIndex) {
    const params = new URLSearchParams({ cx, cy, starIndex, planetIndex })
    return fetch(`/api/colonization-preview?${params}`).then(r => r.json())
  }

  // ── Private fetch helpers ──────────────────────────────────────────────────

  async #fetchHomeworld() {
    try {
      const data = await fetch('/api/homeworld').then(r => r.json())
      if (data?.planet) this.#homeworldData = data
    } catch { /* ignore — homeworld search is best-effort */ }
  }

  async #fetchColonies() {
    try {
      const data = await fetch('/api/colonies').then(r => r.json())
      this.#colonies  = data.colonies ?? []
      this.#colonyIds = new Set(this.#colonies.map(c => c.planetId))
      this.#onUpdate?.()
    } catch { /* ignore */ }
  }
}
