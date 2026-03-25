import { chunkKey } from './ChunkCoord'
import type { ChunkCoord } from './ChunkCoord'
import type { GeneratedChunk } from './ChunkGenerator'

const MAX_CHUNKS_IN_MEMORY = 600

/**
 * In-memory store for generated chunks with LRU eviction.
 * Since generation is fully deterministic, evicted chunks are regenerated
 * identically on next access.
 */
export class ChunkRegistry {
  private chunks = new Map<string, GeneratedChunk>()
  /** Ordered from oldest to newest access */
  private accessOrder: string[] = []

  get(coord: ChunkCoord): GeneratedChunk | undefined {
    const key = chunkKey(coord)
    const chunk = this.chunks.get(key)
    if (chunk) this.touch(key)
    return chunk
  }

  set(coord: ChunkCoord, chunk: GeneratedChunk): void {
    const key = chunkKey(coord)
    this.chunks.set(key, chunk)
    this.touch(key)
    this.evictIfNeeded()
  }

  has(coord: ChunkCoord): boolean {
    return this.chunks.has(chunkKey(coord))
  }

  values(): IterableIterator<GeneratedChunk> {
    return this.chunks.values()
  }

  size(): number {
    return this.chunks.size
  }

  private touch(key: string): void {
    const idx = this.accessOrder.indexOf(key)
    if (idx !== -1) this.accessOrder.splice(idx, 1)
    this.accessOrder.push(key)
  }

  private evictIfNeeded(): void {
    while (this.chunks.size > MAX_CHUNKS_IN_MEMORY) {
      const oldest = this.accessOrder.shift()
      if (oldest === undefined) break
      this.chunks.delete(oldest)
    }
  }
}
