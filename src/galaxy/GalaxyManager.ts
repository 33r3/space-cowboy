import { ChunkGenerator } from './ChunkGenerator'
import { ChunkRegistry } from './ChunkRegistry'
import { chunksInBounds, chunkKey } from './ChunkCoord'
import type { ChunkCoord, WorldBounds } from './ChunkCoord'
import type { StarData } from '../stars/StarProperties'
import type { GalaxyConfig } from './GalaxyConfig'
import type { GeneratedChunk } from './ChunkGenerator'

export class GalaxyManager {
  private config: GalaxyConfig
  private registry: ChunkRegistry
  private generator: ChunkGenerator

  constructor(config: GalaxyConfig, registry: ChunkRegistry, generator: ChunkGenerator) {
    this.config = config
    this.registry = registry
    this.generator = generator
  }

  /**
   * Ensures all chunks overlapping `bounds` (plus an optional margin in chunks)
   * are generated and in memory. Call this every frame with the current viewport.
   */
  ensureChunksGenerated(bounds: WorldBounds, marginChunks = 1): void {
    const margin = marginChunks * this.config.chunkSizeLy
    const expanded: WorldBounds = {
      minX: bounds.minX - margin,
      minY: bounds.minY - margin,
      maxX: bounds.maxX + margin,
      maxY: bounds.maxY + margin,
    }

    const coords = chunksInBounds(expanded, this.config.chunkSizeLy)
    for (const coord of coords) {
      if (!this.registry.has(coord)) {
        const chunk = this.generator.generate(coord)
        this.registry.set(coord, chunk)
      }
    }
  }

  /**
   * Returns all stars currently in memory that fall within `bounds`.
   * Only already-generated chunks are queried (no implicit generation here).
   */
  getStarsInViewport(bounds: WorldBounds): StarData[] {
    const coords = chunksInBounds(bounds, this.config.chunkSizeLy)
    const stars: StarData[] = []

    for (const coord of coords) {
      const chunk = this.registry.get(coord)
      if (!chunk) continue
      for (const star of chunk.stars) {
        if (
          star.worldX >= bounds.minX && star.worldX <= bounds.maxX &&
          star.worldY >= bounds.minY && star.worldY <= bounds.maxY
        ) {
          stars.push(star)
        }
      }
    }

    return stars
  }

  isChunkGenerated(coord: ChunkCoord): boolean {
    return this.registry.has(coord)
  }

  getChunk(coord: ChunkCoord): GeneratedChunk | undefined {
    return this.registry.get(coord)
  }

  getAllGeneratedChunks(): GeneratedChunk[] {
    return Array.from(this.registry.values())
  }

  get chunkSizeLy(): number {
    return this.config.chunkSizeLy
  }

  get generatedChunkCount(): number {
    return this.registry.size()
  }
}
