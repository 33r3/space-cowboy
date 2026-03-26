import { DEFAULT_GALAXY_CONFIG } from './galaxy/GalaxyConfig'
import { DensityField } from './galaxy/DensityField'
import { ChunkGenerator } from './galaxy/ChunkGenerator'
import { ChunkRegistry } from './galaxy/ChunkRegistry'
import { GalaxyManager } from './galaxy/GalaxyManager'
import { Camera } from './rendering/Camera'
import { Renderer } from './rendering/Renderer'
import { Viewport } from './input/Viewport'
import { InputHandler } from './input/InputHandler'
import { Ship } from './exploration/Ship'
import { ExplorationTracker } from './exploration/ExplorationTracker'

// ── Bootstrap ─────────────────────────────────────────────────────────────────

const canvas = document.getElementById('game-canvas') as HTMLCanvasElement | null
if (!canvas) throw new Error('Canvas element not found')

const viewport = new Viewport(canvas)
const { ctx } = viewport

// ── Galaxy setup ──────────────────────────────────────────────────────────────

const config = { ...DEFAULT_GALAXY_CONFIG }
const densityField  = new DensityField(config)
const chunkRegistry = new ChunkRegistry()
const chunkGenerator = new ChunkGenerator(config, densityField)
const galaxyManager = new GalaxyManager(config, chunkRegistry, chunkGenerator)

// ── Game objects ──────────────────────────────────────────────────────────────

// Start at galaxy center with a moderate zoom
const camera = new Camera(0, 0, 0.4)
const ship   = new Ship(0, 0, 100)
const explorationTracker = new ExplorationTracker()
explorationTracker.restore()

// ── Renderer & input ──────────────────────────────────────────────────────────

const renderer = new Renderer(ctx, camera, galaxyManager)
const input    = new InputHandler(canvas, camera, ship, viewport)

input.onDebugToggle = () => {
  renderer.showDebug = !renderer.showDebug
}

input.onCameraReset = () => {
  camera.worldX = ship.worldX
  camera.worldY = ship.worldY
}

// Forward mouse position to renderer for planet hover detection
canvas.addEventListener('mousemove', (e) => {
  renderer.mouseX = e.clientX
  renderer.mouseY = e.clientY
})
canvas.addEventListener('mouseleave', () => {
  renderer.mouseX = -9999
  renderer.mouseY = -9999
})

// ── HUD elements ──────────────────────────────────────────────────────────────

const hudPos    = document.getElementById('hud-pos')
const hudZoom   = document.getElementById('hud-zoom')
const hudStars  = document.getElementById('hud-stars')
const hudChunks = document.getElementById('hud-chunks')
const hudSeed   = document.getElementById('hud-seed')

if (hudSeed) hudSeed.textContent = String(config.seed)

let lastPersist = 0
let frameCount = 0
let lastFpsTime = 0
let fps = 60

// ── Pre-generate the initial viewport area ────────────────────────────────────
// Generate a larger area upfront so the galaxy is visible immediately on load
;(() => {
  const initialBounds = {
    minX: -config.galaxyRadiusLy * 0.6,
    minY: -config.galaxyRadiusLy * 0.6,
    maxX:  config.galaxyRadiusLy * 0.6,
    maxY:  config.galaxyRadiusLy * 0.6,
  }
  // For the overview, we want a sparse initial generation.
  // Only generate every 10th chunk to give a fast galaxy silhouette.
  // The rest are filled in lazily as the player zooms in.
  const step = config.chunkSizeLy * 8
  for (let x = initialBounds.minX; x <= initialBounds.maxX; x += step) {
    for (let y = initialBounds.minY; y <= initialBounds.maxY; y += step) {
      galaxyManager.ensureChunksGenerated({ minX: x, minY: y, maxX: x + 1, maxY: y + 1 }, 0)
    }
  }
})()

// ── Game loop ─────────────────────────────────────────────────────────────────

let lastTime = 0

function gameLoop(timestamp: number): void {
  const dtMs = Math.min(timestamp - lastTime, 100)  // cap at 100ms to avoid spiral-of-death
  const dtSec = dtMs / 1000
  lastTime = timestamp
  frameCount++

  // FPS counter
  if (timestamp - lastFpsTime >= 1000) {
    fps = Math.round(frameCount * 1000 / (timestamp - lastFpsTime))
    frameCount = 0
    lastFpsTime = timestamp
  }

  // ── Update ──────────────────────────────────────────────────────────────
  input.update()
  ship.update(dtSec)

  // Ensure chunks are generated around the ship and viewport
  const shipBounds   = ship.getExplorationBounds()
  const viewBounds   = camera.getViewportBounds(viewport.width, viewport.height)

  galaxyManager.ensureChunksGenerated(shipBounds, 1)
  galaxyManager.ensureChunksGenerated(viewBounds, 1)

  // Track exploration
  explorationTracker.markExploredBounds(
    shipBounds.minX, shipBounds.minY, shipBounds.maxX, shipBounds.maxY,
    config.chunkSizeLy,
  )

  // Persist exploration every 5 seconds
  if (timestamp - lastPersist > 5000) {
    explorationTracker.persist()
    lastPersist = timestamp
  }

  // ── Render ──────────────────────────────────────────────────────────────
  const stars = galaxyManager.getStarsInViewport(viewBounds)
  renderer.render(viewport.width, viewport.height, ship, stars.length)

  // ── HUD ─────────────────────────────────────────────────────────────────
  if (hudPos)    hudPos.textContent    = `${ship.worldX.toFixed(0)}, ${ship.worldY.toFixed(0)} Ly`
  if (hudZoom)   hudZoom.textContent   = `${camera.zoom.toFixed(4)} px/Ly`
  if (hudStars)  hudStars.textContent  = String(stars.length)
  if (hudChunks) hudChunks.textContent = `${galaxyManager.generatedChunkCount} (${explorationTracker.count} explored)`

  requestAnimationFrame(gameLoop)
}

requestAnimationFrame((t) => {
  lastTime = t
  lastFpsTime = t
  requestAnimationFrame(gameLoop)
})
