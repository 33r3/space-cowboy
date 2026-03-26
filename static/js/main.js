import { Camera } from './camera.js'
import { Viewport } from './viewport.js'
import { GalaxyClient } from './galaxy_client.js'
import { Ship } from './ship.js'
import { ExplorationTracker } from './exploration_tracker.js'
import { InputHandler } from './input_handler.js'
import { Renderer } from './renderer.js'

// ── Bootstrap ─────────────────────────────────────────────────────────────────

const canvas = document.getElementById('game-canvas')
if (!canvas) throw new Error('Canvas element not found')

const viewport = new Viewport(canvas)
const { ctx } = viewport

// ── Galaxy client ─────────────────────────────────────────────────────────────

const galaxyClient = new GalaxyClient()
await galaxyClient.init()

const config = galaxyClient.config

// ── Game objects ──────────────────────────────────────────────────────────────

const camera = new Camera(0, 0, 0.4)
const ship   = new Ship(0, 0, 100)
const explorationTracker = new ExplorationTracker()
explorationTracker.restore()

// ── Renderer & input ──────────────────────────────────────────────────────────

const renderer = new Renderer(ctx, camera, galaxyClient)
const input    = new InputHandler(canvas, camera, ship, viewport)

input.onDebugToggle = () => {
  renderer.showDebug = !renderer.showDebug
}

input.onCameraReset = () => {
  camera.worldX = ship.worldX
  camera.worldY = ship.worldY
}

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

// ── Pre-fetch initial viewport area ──────────────────────────────────────────
// Kick off background fetches covering the initial galaxy overview
;(() => {
  const r    = config.galaxyRadiusLy * 0.6
  const step = config.chunkSizeLy * 8
  for (let x = -r; x <= r; x += step) {
    for (let y = -r; y <= r; y += step) {
      // Touch getStarsInViewport with a tiny bounds to trigger fetches
      galaxyClient.getStarsInViewport({ minX: x, minY: y, maxX: x + 1, maxY: y + 1 })
    }
  }
})()

// ── Game loop ─────────────────────────────────────────────────────────────────

let lastTime    = 0
let lastPersist = 0
let frameCount  = 0
let lastFpsTime = 0

function gameLoop(timestamp) {
  const dtMs  = Math.min(timestamp - lastTime, 100)
  const dtSec = dtMs / 1000
  lastTime = timestamp
  frameCount++

  if (timestamp - lastFpsTime >= 1000) {
    frameCount  = 0
    lastFpsTime = timestamp
  }

  // ── Update ────────────────────────────────────────────────────────────────
  input.update()
  ship.update(dtSec)

  const shipBounds = ship.getExplorationBounds()
  const viewBounds = camera.getViewportBounds(viewport.width, viewport.height)

  // Kick off chunk fetches for ship area + viewport (triggers async loads)
  galaxyClient.getStarsInViewport(shipBounds)

  explorationTracker.markExploredBounds(
    shipBounds.minX, shipBounds.minY, shipBounds.maxX, shipBounds.maxY,
    config.chunkSizeLy,
  )

  if (timestamp - lastPersist > 5000) {
    explorationTracker.persist()
    lastPersist = timestamp
  }

  // ── Render ────────────────────────────────────────────────────────────────
  const stars = galaxyClient.getStarsInViewport(viewBounds)
  renderer.render(viewport.width, viewport.height, ship, stars.length)

  // ── HUD ───────────────────────────────────────────────────────────────────
  if (hudPos)    hudPos.textContent    = `${ship.worldX.toFixed(0)}, ${ship.worldY.toFixed(0)} Ly`
  if (hudZoom)   hudZoom.textContent   = `${camera.zoom.toFixed(4)} px/Ly`
  if (hudStars)  hudStars.textContent  = String(stars.length)
  if (hudChunks) hudChunks.textContent = `${galaxyClient.generatedChunkCount} (${explorationTracker.count} explored)`

  requestAnimationFrame(gameLoop)
}

requestAnimationFrame((t) => {
  lastTime    = t
  lastFpsTime = t
  requestAnimationFrame(gameLoop)
})
