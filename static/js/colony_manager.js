/**
 * ColonyManager — fetches and maintains homeworld + colony state.
 * Communicates with /api/homeworld and /api/colonies.
 */
export class ColonyManager {
  #homeworldData = null   // full API response (planet, star, cx, cy, starIndex)
  #colonyIds     = new Set()
  #colonies      = []     // enriched colony records from server
  #ready         = false

  async init() {
    await Promise.all([this.#fetchHomeworld(), this.#fetchColonies()])
    this.#ready = true
  }

  // ── Accessors ──────────────────────────────────────────────────────────────

  get ready()      { return this.#ready }
  get homeworld()  { return this.#homeworldData }
  get colonies()   { return this.#colonies }

  isHomeworld(planetId) {
    return this.#homeworldData?.planet?.id === planetId
  }

  isColony(planetId) {
    return this.#colonyIds.has(planetId)
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /**
   * Found a colony on the given planet.
   * planet must have an `index` field (its position index in the system).
   * Returns the created colony record, or throws on error.
   */
  async foundColony(planet, cx, cy, starIndex) {
    const resp = await fetch('/api/colonies', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ cx, cy, starIndex, planetIndex: planet.index }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error ?? 'Failed to found colony')
    this.#colonyIds.add(planet.id)
    this.#colonies.push({ ...data.colony, planet: data.planet })
    return data.colony
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
      this.#colonies = data.colonies ?? []
      this.#colonyIds = new Set(this.#colonies.map(c => c.planetId))
    } catch { /* ignore */ }
  }
}
