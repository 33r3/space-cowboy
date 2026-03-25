import { chunkKey, parseChunkKey } from '../galaxy/ChunkCoord'
import type { ChunkCoord } from '../galaxy/ChunkCoord'

const STORAGE_KEY = 'space-cowboy-explored'

/**
 * Tracks which chunks the player has visited.
 * Persists to localStorage so exploration state survives page reloads.
 *
 * Note: this is separate from ChunkRegistry (in-memory generated data).
 * On reload, explored chunks are regenerated identically from seed.
 */
export class ExplorationTracker {
  private exploredKeys = new Set<string>()

  markExplored(coord: ChunkCoord): void {
    this.exploredKeys.add(chunkKey(coord))
  }

  markExploredBounds(minX: number, minY: number, maxX: number, maxY: number, chunkSizeLy: number): void {
    const minCx = Math.floor(minX / chunkSizeLy)
    const minCy = Math.floor(minY / chunkSizeLy)
    const maxCx = Math.floor(maxX / chunkSizeLy)
    const maxCy = Math.floor(maxY / chunkSizeLy)
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        this.exploredKeys.add(chunkKey({ cx, cy }))
      }
    }
  }

  isExplored(coord: ChunkCoord): boolean {
    return this.exploredKeys.has(chunkKey(coord))
  }

  getExploredCoords(): ChunkCoord[] {
    return Array.from(this.exploredKeys).map(parseChunkKey)
  }

  get count(): number {
    return this.exploredKeys.size
  }

  persist(): void {
    try {
      const data = JSON.stringify(Array.from(this.exploredKeys))
      localStorage.setItem(STORAGE_KEY, data)
    } catch {
      // localStorage may be unavailable (private browsing, storage full, etc.)
    }
  }

  restore(): void {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const keys = JSON.parse(raw) as unknown
      if (!Array.isArray(keys)) return
      for (const key of keys) {
        if (typeof key === 'string') this.exploredKeys.add(key)
      }
    } catch {
      // Corrupted data — start fresh
    }
  }

  clear(): void {
    this.exploredKeys.clear()
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
  }
}
