export interface ChunkCoord {
  cx: number
  cy: number
}

export interface WorldBounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export function worldToChunk(worldX: number, worldY: number, chunkSizeLy: number): ChunkCoord {
  return {
    cx: Math.floor(worldX / chunkSizeLy),
    cy: Math.floor(worldY / chunkSizeLy),
  }
}

export function chunkToWorldMin(coord: ChunkCoord, chunkSizeLy: number): { x: number; y: number } {
  return {
    x: coord.cx * chunkSizeLy,
    y: coord.cy * chunkSizeLy,
  }
}

export function chunkToWorldCenter(coord: ChunkCoord, chunkSizeLy: number): { x: number; y: number } {
  return {
    x: (coord.cx + 0.5) * chunkSizeLy,
    y: (coord.cy + 0.5) * chunkSizeLy,
  }
}

export function chunkBounds(coord: ChunkCoord, chunkSizeLy: number): WorldBounds {
  const min = chunkToWorldMin(coord, chunkSizeLy)
  return {
    minX: min.x,
    minY: min.y,
    maxX: min.x + chunkSizeLy,
    maxY: min.y + chunkSizeLy,
  }
}

export function chunkKey(coord: ChunkCoord): string {
  return `${coord.cx},${coord.cy}`
}

export function parseChunkKey(key: string): ChunkCoord {
  const parts = key.split(',')
  if (parts.length !== 2) throw new Error(`Invalid chunk key: ${key}`)
  const cx = parseInt(parts[0] ?? '0', 10)
  const cy = parseInt(parts[1] ?? '0', 10)
  return { cx, cy }
}

/** Returns all chunk coords that overlap the given world-space bounding box */
export function chunksInBounds(bounds: WorldBounds, chunkSizeLy: number): ChunkCoord[] {
  const minChunk = worldToChunk(bounds.minX, bounds.minY, chunkSizeLy)
  const maxChunk = worldToChunk(bounds.maxX - 0.001, bounds.maxY - 0.001, chunkSizeLy)

  const coords: ChunkCoord[] = []
  for (let cx = minChunk.cx; cx <= maxChunk.cx; cx++) {
    for (let cy = minChunk.cy; cy <= maxChunk.cy; cy++) {
      coords.push({ cx, cy })
    }
  }
  return coords
}
