const STORAGE_KEY = 'space-cowboy-explored'

function chunkKey(cx, cy) {
  return `${cx},${cy}`
}

export class ExplorationTracker {
  constructor() {
    this._exploredKeys = new Set()
  }

  markExploredBounds(minX, minY, maxX, maxY, chunkSizeLy) {
    const minCx = Math.floor(minX / chunkSizeLy)
    const minCy = Math.floor(minY / chunkSizeLy)
    const maxCx = Math.floor(maxX / chunkSizeLy)
    const maxCy = Math.floor(maxY / chunkSizeLy)
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        this._exploredKeys.add(chunkKey(cx, cy))
      }
    }
  }

  get count() {
    return this._exploredKeys.size
  }

  persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(this._exploredKeys)))
    } catch { /* ignore */ }
  }

  restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const keys = JSON.parse(raw)
      if (!Array.isArray(keys)) return
      for (const key of keys) {
        if (typeof key === 'string') this._exploredKeys.add(key)
      }
    } catch { /* ignore */ }
  }

  clear() {
    this._exploredKeys.clear()
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
  }
}
