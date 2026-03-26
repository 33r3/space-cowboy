import { Camera } from './camera.js'
import { Viewport } from './viewport.js'
import { GalaxyClient } from './galaxy_client.js'
import { Ship } from './ship.js'
import { ExplorationTracker } from './exploration_tracker.js'
import { InputHandler } from './input_handler.js'
import { Renderer } from './renderer.js'
import { ColonyManager } from './colony_manager.js'

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

// ── Colony manager ────────────────────────────────────────────────────────────

const colonyManager = new ColonyManager()
colonyManager.init().then(() => {
  const hw = colonyManager.homeworld
  if (hw?.star) {
    // Navigate ship to the homeworld's star on first load
    ship.setDestination(hw.star.worldX, hw.star.worldY)
    camera.worldX = hw.star.worldX
    camera.worldY = hw.star.worldY
  }
})

// ── Renderer & input ──────────────────────────────────────────────────────────

const renderer = new Renderer(ctx, camera, galaxyClient, colonyManager)
const input    = new InputHandler(canvas, camera, ship, viewport)

input.onDebugToggle = () => {
  renderer.showDebug = !renderer.showDebug
}

input.onCameraReset = () => {
  camera.worldX = ship.worldX
  camera.worldY = ship.worldY
}

// ── Colony panel ──────────────────────────────────────────────────────────────

const colonyPanel      = document.getElementById('colony-panel')
const colonyPanelTitle = document.getElementById('colony-panel-title')
const colonyPanelSub   = document.getElementById('colony-panel-subtitle')
const colonyPanelStatus = document.getElementById('colony-panel-status')
const colonyPanelYields = document.getElementById('colony-panel-yields')
const colonyPanelFound = document.getElementById('colony-panel-found')
const colonyPanelClose = document.getElementById('colony-panel-close')

let _colonyPanelPlanet = null
let _colonyPanelMeta   = null   // { cx, cy, starIndex } from system

function _openColonyPanel(planet, system) {
  _colonyPanelPlanet = planet
  _colonyPanelMeta   = { cx: null, cy: null, starIndex: null }

  // Derive cx/cy/starIndex from the star id  (format: "cx,cy:starIndex")
  const starId    = system.starId
  const parts     = starId.split(':')
  const chunkParts = parts[0].split(',')
  _colonyPanelMeta = {
    cx:         parseInt(chunkParts[0]),
    cy:         parseInt(chunkParts[1]),
    starIndex:  parseInt(parts[1]),
  }

  const isHW     = colonyManager.isHomeworld(planet.id)
  const isColony = colonyManager.isColony(planet.id)

  colonyPanelTitle.textContent = planet.name
  colonyPanelTitle.style.color = isHW ? '#ffd700' : isColony ? '#44ffcc' : '#aaccee'

  colonyPanelSub.textContent = `${planet.planetType}  ·  ${planet.semiMajorAxisAU.toFixed(2)} AU  ·  Hab ${planet.habitability.total}/100`

  if (isHW)          colonyPanelStatus.innerHTML = '<span style="color:#ffd700">★ Home World</span>'
  else if (isColony) colonyPanelStatus.innerHTML = '<span style="color:#44ffcc">■ Colony established</span>'
  else               colonyPanelStatus.textContent = ''

  // Yields
  const yields = planet.colonyYields
  if (yields) {
    const nonZero = Object.entries(yields).filter(([, v]) => v > 0)
    if (nonZero.length > 0) {
      const LABELS = {
        food: 'Food', water: 'Water', organicFuels: 'Org. Fuels',
        chemFeedstocks: 'Chem. Feed.', minerals: 'Minerals',
        fusionFuel: 'Fusion Fuel', metals: 'Metals', radioactives: 'Radioactives',
      }
      const bar = v => {
        const f = Math.round(v * 5)
        return '\u2588'.repeat(f) + '\u2591'.repeat(5 - f) + ` ${v.toFixed(2)}`
      }
      colonyPanelYields.innerHTML =
        '<div class="yields-header">COLONY YIELDS</div>' +
        nonZero.map(([k, v]) =>
          `<div>${(LABELS[k] ?? k).padEnd(12, '\u00a0')} ${bar(v)}</div>`
        ).join('')
    } else {
      colonyPanelYields.textContent = ''
    }
  } else {
    colonyPanelYields.textContent = ''
  }

  colonyPanelFound.disabled = isHW || isColony
  colonyPanelFound.textContent = isHW ? 'Home World' : isColony ? 'Colonized' : 'Found Colony'

  colonyPanel.style.display = 'block'
}

input.onCanvasClick = () => {
  const planet = renderer.hoveredPlanet
  if (!planet) {
    colonyPanel.style.display = 'none'
    return
  }
  // Find which system this planet belongs to
  const bounds  = camera.getViewportBounds(viewport.width, viewport.height)
  const systems = galaxyClient.getSystemsInViewport(bounds)
  const system  = systems.find(s => s.planets.some(p => p.id === planet.id))
  if (system) _openColonyPanel(planet, system)
}

colonyPanelClose.addEventListener('click', () => {
  colonyPanel.style.display = 'none'
})

colonyPanelFound.addEventListener('click', async () => {
  if (!_colonyPanelPlanet || !_colonyPanelMeta) return
  colonyPanelFound.disabled = true
  colonyPanelFound.textContent = 'Founding...'
  try {
    await colonyManager.foundColony(
      _colonyPanelPlanet,
      _colonyPanelMeta.cx,
      _colonyPanelMeta.cy,
      _colonyPanelMeta.starIndex,
    )
    colonyPanelFound.textContent = 'Colonized'
    colonyPanelStatus.innerHTML = '<span style="color:#44ffcc">■ Colony established</span>'
    colonyPanelTitle.style.color = '#44ffcc'
  } catch (err) {
    colonyPanelFound.disabled = false
    colonyPanelFound.textContent = 'Found Colony'
    colonyPanelStatus.textContent = `Error: ${err.message}`
  }
})

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
