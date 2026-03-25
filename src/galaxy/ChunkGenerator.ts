import { PRNG, chunkSeed } from '../math/prng'
import { generateStar } from '../stars/StarFactory'
import type { StarData } from '../stars/StarProperties'
import type { GalaxyConfig } from './GalaxyConfig'
import type { DensityField } from './DensityField'
import { chunkKey, chunkToWorldCenter, chunkBounds } from './ChunkCoord'
import type { ChunkCoord } from './ChunkCoord'

export interface GeneratedChunk {
  coord: ChunkCoord
  stars: StarData[]
}

export class ChunkGenerator {
  private config: GalaxyConfig
  private densityField: DensityField

  constructor(config: GalaxyConfig, densityField: DensityField) {
    this.config = config
    this.densityField = densityField
  }

  generate(coord: ChunkCoord): GeneratedChunk {
    const { config } = this
    const seed = chunkSeed(config.seed, coord.cx, coord.cy)
    const prng = new PRNG(seed)
    const key = chunkKey(coord)

    // Evaluate density at chunk center to decide star count
    const center = chunkToWorldCenter(coord, config.chunkSizeLy)
    const density = this.densityField.getDensity(center.x, center.y)

    // Stochastic star count: Poisson-like via rounding a continuous value
    const meanStars = density * config.maxStarsPerChunk
    // Add noise so even low-density regions occasionally get a star
    const starCount = Math.round(meanStars + prng.nextGaussian() * Math.sqrt(meanStars + 0.5))
    const clampedCount = Math.max(0, Math.min(config.maxStarsPerChunk, starCount))

    const bounds = chunkBounds(coord, config.chunkSizeLy)
    const stars: StarData[] = []

    for (let i = 0; i < clampedCount; i++) {
      // Random position within the chunk
      const wx = prng.nextFloat(bounds.minX, bounds.maxX)
      const wy = prng.nextFloat(bounds.minY, bounds.maxY)
      stars.push(generateStar(prng, wx, wy, key, i))
    }

    return { coord, stars }
  }
}
