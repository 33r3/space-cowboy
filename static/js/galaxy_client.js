/**
 * GalaxyClient — async fetch layer for Flask API.
 * Maintains local caches so every frame doesn't fire a network request.
 * Replaces GalaxyManager + ChunkRegistry from the TypeScript version.
 */
export class GalaxyClient {
  #chunkCache  = new Map()   // "cx,cy" → StarData[]
  #systemCache = new Map()   // starId  → SystemData
  #inflight    = new Set()   // chunk keys currently being fetched
  #sysInflight = new Set()   // star ids currently being fetched
  #config      = null

  async init() {
    this.#config = await fetch('/api/config').then(r => r.json())
  }

  // ── Synchronous accessors (return what's cached, kick off fetches) ──────────

  /**
   * Returns stars currently cached in the viewport bounds.
   * Kicks off async fetches for missing chunks (non-blocking).
   */
  getStarsInViewport(bounds) {
    if (!this.#config) return []

    const coords = this.#chunksInBounds(bounds)
    const missing = []
    const stars   = []

    for (const [cx, cy] of coords) {
      const key   = `${cx},${cy}`
      const cached = this.#chunkCache.get(key)
      if (cached) {
        for (const star of cached) {
          if (star.worldX >= bounds.minX && star.worldX <= bounds.maxX &&
              star.worldY >= bounds.minY && star.worldY <= bounds.maxY) {
            stars.push(star)
          }
        }
      } else if (!this.#inflight.has(key)) {
        missing.push([cx, cy])
      }
    }

    if (missing.length > 0) {
      this.#fetchChunks(missing)
    }

    return stars
  }

  /**
   * Returns systems for all stars in viewport that are already cached.
   * Kicks off async fetches for missing systems.
   */
  getSystemsInViewport(bounds) {
    const stars   = this.getStarsInViewport(bounds)
    const systems = []

    for (const star of stars) {
      const cached = this.#systemCache.get(star.id)
      if (cached) {
        systems.push(cached)
      } else if (!this.#sysInflight.has(star.id)) {
        const [cx, cy, index] = star.id.split(':').map((p, i) => {
          if (i < 2) return parseInt(p)
          return parseInt(p)
        })
        // star.id format: "cx,cy:index"
        const parts = star.id.split(':')
        const chunkParts = parts[0].split(',')
        const starCx    = parseInt(chunkParts[0])
        const starCy    = parseInt(chunkParts[1])
        const starIndex = parseInt(parts[1])
        this.#fetchSystem(starCx, starCy, starIndex, star.id)
      }
    }

    return systems
  }

  // ── Private fetch helpers ───────────────────────────────────────────────────

  async #fetchChunks(coords) {
    // Mark all as in-flight
    for (const [cx, cy] of coords) {
      this.#inflight.add(`${cx},${cy}`)
    }

    // Compute bounding box for the batch
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    const cs = this.#config.chunkSizeLy
    for (const [cx, cy] of coords) {
      minX = Math.min(minX, cx * cs)
      minY = Math.min(minY, cy * cs)
      maxX = Math.max(maxX, (cx + 1) * cs)
      maxY = Math.max(maxY, (cy + 1) * cs)
    }

    try {
      const params = new URLSearchParams({ minX, minY, maxX, maxY })
      const data   = await fetch(`/api/chunks?${params}`).then(r => r.json())
      for (const [key, stars] of Object.entries(data.chunks)) {
        this.#chunkCache.set(key, stars)
        this.#inflight.delete(key)
      }
    } catch (err) {
      // On error, remove in-flight markers so they can be retried
      for (const [cx, cy] of coords) {
        this.#inflight.delete(`${cx},${cy}`)
      }
    }
  }

  async #fetchSystem(cx, cy, index, starId) {
    this.#sysInflight.add(starId)
    try {
      const data = await fetch(`/api/system?cx=${cx}&cy=${cy}&index=${index}`).then(r => r.json())
      this.#systemCache.set(data.starId, data)
    } catch { /* ignore */ } finally {
      this.#sysInflight.delete(starId)
    }
  }

  // ── Chunk math ──────────────────────────────────────────────────────────────

  #chunksInBounds(bounds) {
    const cs     = this.#config?.chunkSizeLy ?? 200
    const minCx  = Math.floor(bounds.minX / cs)
    const minCy  = Math.floor(bounds.minY / cs)
    const maxCx  = Math.floor((bounds.maxX - 0.001) / cs)
    const maxCy  = Math.floor((bounds.maxY - 0.001) / cs)
    const coords = []
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        coords.push([cx, cy])
      }
    }
    return coords
  }

  // ── Accessors ───────────────────────────────────────────────────────────────

  get chunkSizeLy() {
    return this.#config?.chunkSizeLy ?? 200
  }

  get generatedChunkCount() {
    return this.#chunkCache.size
  }

  get config() {
    return this.#config
  }
}
