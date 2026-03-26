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
    ship.setDestination(hw.star.worldX, hw.star.worldY)
    camera.worldX = hw.star.worldX
    camera.worldY = hw.star.worldY
  }
})

// ── Renderer & input ──────────────────────────────────────────────────────────

const renderer = new Renderer(ctx, camera, galaxyClient, colonyManager)
const input    = new InputHandler(canvas, camera, ship, viewport)

input.onDebugToggle = () => { renderer.showDebug = !renderer.showDebug }
input.onCameraReset = () => { camera.worldX = ship.worldX; camera.worldY = ship.worldY }

// ── Colony panel ──────────────────────────────────────────────────────────────

const colonyPanel        = document.getElementById('colony-panel')
const cpTitle            = document.getElementById('colony-panel-title')
const cpSubtitle         = document.getElementById('colony-panel-subtitle')
const cpStatus           = document.getElementById('colony-panel-status')
const cpColonySection    = document.getElementById('colony-panel-colony-section')
const cpYieldsSection    = document.getElementById('colony-panel-yields-section')
const cpYields           = document.getElementById('colony-panel-yields')
const cpFoundBtn         = document.getElementById('colony-panel-found')
const cpCloseBtn         = document.getElementById('colony-panel-close-btn')
const cpSizeName         = document.getElementById('cp-size-name')
const cpGrowthFill       = document.getElementById('cp-growth-fill')
const cpGrowthLabel      = document.getElementById('cp-growth-label')
const cpNextSize         = document.getElementById('cp-next-size')
const cpDevName          = document.getElementById('cp-dev-name')
const cpUpgradeBtn       = document.getElementById('colony-panel-upgrade-btn')
const cpUpgradeCost      = document.getElementById('cp-upgrade-cost')
const cpFlowsBody        = document.getElementById('cp-flows-body')
const cpStockpiles       = document.getElementById('cp-stockpiles')

const SIZE_NAMES = ['Outpost', 'Settlement', 'Town', 'City', 'Megacity']
const DEV_NAMES  = ['Primitive', 'Industrial', 'Advanced', 'Sophisticated', 'Transcendent']
const GROWTH_NEEDED = 10

const RES_LABELS = {
  food: 'Food', water: 'Water', organicFuels: 'Org.Fuels',
  chemFeedstocks: 'Chem.Feed', minerals: 'Minerals',
  fusionFuel: 'Fusion', metals: 'Metals', radioactives: 'Radioact.',
}

let _panelPlanet = null
let _panelMeta   = null   // { cx, cy, starIndex }

function _fmtFlow(v) {
  if (v === 0) return { text: '—', cls: 'net-zero' }
  return { text: (v > 0 ? '+' : '') + v.toFixed(3), cls: v > 0 ? 'net-pos' : 'net-neg' }
}

function _renderColonySection(colony) {
  cpColonySection.style.display = 'block'
  cpYieldsSection.style.display = 'none'
  cpFoundBtn.style.display      = 'none'

  // Size + growth
  const size = colony.size ?? 1
  cpSizeName.textContent = SIZE_NAMES[size - 1] ?? 'Outpost'
  const progress = colony.growthProgress ?? 0
  const pct = size < 5 ? Math.min(100, (progress / GROWTH_NEEDED) * 100) : 100
  cpGrowthFill.style.width = `${pct}%`
  if (size < 5) {
    cpGrowthLabel.textContent = `${progress}/${GROWTH_NEEDED}`
    cpNextSize.textContent    = `→ ${SIZE_NAMES[size] ?? ''}`
  } else {
    cpGrowthLabel.textContent = 'max'
    cpNextSize.textContent    = ''
  }

  // Development level
  const dev = colony.developmentLevel ?? 1
  cpDevName.textContent = `${DEV_NAMES[dev - 1] ?? 'Primitive'} (${dev})`
  cpUpgradeBtn.disabled = !colony.canUpgradeDev || dev >= 5
  cpUpgradeBtn.textContent = dev >= 5 ? 'Max' : `→ ${DEV_NAMES[dev] ?? ''}`

  if (colony.upgradeCost && dev < 5) {
    cpUpgradeCost.textContent = 'Cost: ' +
      Object.entries(colony.upgradeCost)
        .map(([k, v]) => `${v} ${RES_LABELS[k] ?? k}`)
        .join(' · ')
  } else {
    cpUpgradeCost.textContent = ''
  }

  // Resource flows
  const ext = colony.extractionPerTick ?? {}
  const con = colony.consumptionPerTick ?? {}
  const net = colony.netFlowPerTick ?? {}
  const allRes = Object.keys(RES_LABELS)
  const activeRes = allRes.filter(k =>
    (ext[k] ?? 0) !== 0 || (con[k] ?? 0) !== 0 || (net[k] ?? 0) !== 0
  )

  cpFlowsBody.innerHTML = activeRes.map(k => {
    const e = ext[k] ?? 0
    const c = con[k] ?? 0
    const n = net[k] ?? 0
    const { text: nt, cls: nc } = _fmtFlow(n)
    return `<tr>
      <td>${RES_LABELS[k] ?? k}</td>
      <td>${e > 0 ? '+' + e.toFixed(3) : '—'}</td>
      <td>${c > 0 ? '-' + c.toFixed(3) : '—'}</td>
      <td class="${nc}">${nt}</td>
    </tr>`
  }).join('')

  // Stockpiles
  const stocks = colony.stockpiles ?? {}
  const nonZeroStocks = Object.entries(stocks).filter(([, v]) => v > 0)
  if (nonZeroStocks.length > 0) {
    cpStockpiles.innerHTML = nonZeroStocks.map(([k, v]) =>
      `<div class="cp-stockpile-entry">
        <span class="cp-stockpile-label">${RES_LABELS[k] ?? k}</span>
        <span class="cp-stockpile-value">${v.toFixed(1)}</span>
      </div>`
    ).join('')
  } else {
    cpStockpiles.innerHTML = '<span style="color:#445566">Empty</span>'
  }
}

function _renderYieldsSection(planet) {
  cpColonySection.style.display = 'none'
  const yields = planet.colonyYields ?? {}
  const nonZero = Object.entries(yields).filter(([, v]) => v > 0)
  if (nonZero.length > 0) {
    cpYieldsSection.style.display = 'block'
    const bar = v => {
      const f = Math.round(v * 5)
      return '\u2588'.repeat(f) + '\u2591'.repeat(5 - f) + ` ${v.toFixed(2)}`
    }
    cpYields.innerHTML = nonZero.map(([k, v]) =>
      `<div style="font-size:10px;line-height:1.8;color:#88aacc">` +
      `<span style="color:#445566">${(RES_LABELS[k] ?? k).padEnd(10,'\u00a0')}</span> ${bar(v)}</div>`
    ).join('')
  } else {
    cpYieldsSection.style.display = 'none'
  }
  cpFoundBtn.style.display = 'block'
  cpFoundBtn.disabled      = false
  cpFoundBtn.textContent   = 'Found Colony'
}

function openColonyPanel(planet, system) {
  _panelPlanet = planet

  const starId     = system.starId
  const parts      = starId.split(':')
  const chunkParts = parts[0].split(',')
  _panelMeta = {
    cx:        parseInt(chunkParts[0]),
    cy:        parseInt(chunkParts[1]),
    starIndex: parseInt(parts[1]),
  }

  const isHW     = colonyManager.isHomeworld(planet.id)
  const isColony = colonyManager.isColony(planet.id)

  cpTitle.textContent   = planet.name
  cpTitle.style.color   = isHW ? '#ffd700' : isColony ? '#44ffcc' : '#aaccee'
  cpSubtitle.textContent = `${planet.planetType}  ·  ${planet.semiMajorAxisAU.toFixed(2)} AU  ·  Hab ${planet.habitability.total}/100`

  if (isHW)          cpStatus.innerHTML = '<span style="color:#ffd700;font-size:11px">★ Home World</span>'
  else if (isColony) cpStatus.innerHTML = '<span style="color:#44ffcc;font-size:11px">■ Colony</span>'
  else               cpStatus.innerHTML = ''

  if (isHW || isColony) {
    const col = colonyManager.getColony(planet.id)
    if (col) _renderColonySection(col)
    else     _renderYieldsSection(planet)
  } else {
    _renderYieldsSection(planet)
  }

  colonyPanel.style.display = 'block'
}

// Refresh panel if it's open and colony data was updated by polling
colonyManager.onUpdate = () => {
  if (colonyPanel.style.display === 'none' || !_panelPlanet) return
  const col = colonyManager.getColony(_panelPlanet.id)
  if (col) _renderColonySection(col)
}

input.onCanvasClick = () => {
  const planet = renderer.hoveredPlanet
  if (!planet) {
    colonyPanel.style.display = 'none'
    return
  }
  const bounds  = camera.getViewportBounds(viewport.width, viewport.height)
  const systems = galaxyClient.getSystemsInViewport(bounds)
  const system  = systems.find(s => s.planets.some(p => p.id === planet.id))
  if (system) openColonyPanel(planet, system)
}

cpCloseBtn.addEventListener('click', () => {
  colonyPanel.style.display = 'none'
})

cpFoundBtn.addEventListener('click', async () => {
  if (!_panelPlanet || !_panelMeta) return
  cpFoundBtn.disabled    = true
  cpFoundBtn.textContent = 'Founding...'
  try {
    const col = await colonyManager.foundColony(
      _panelPlanet, _panelMeta.cx, _panelMeta.cy, _panelMeta.starIndex,
    )
    cpStatus.innerHTML     = '<span style="color:#44ffcc;font-size:11px">■ Colony</span>'
    cpTitle.style.color    = '#44ffcc'
    if (col) _renderColonySection(col)
    else { cpFoundBtn.textContent = 'Colonized'; cpFoundBtn.disabled = true }
  } catch (err) {
    cpFoundBtn.disabled    = false
    cpFoundBtn.textContent = 'Found Colony'
    cpStatus.innerHTML     = `<span style="color:#cc4444;font-size:10px">${err.message}</span>`
  }
})

cpUpgradeBtn.addEventListener('click', async () => {
  if (!_panelPlanet) return
  cpUpgradeBtn.disabled    = true
  cpUpgradeBtn.textContent = 'Upgrading...'
  try {
    const col = await colonyManager.upgradeColony(_panelPlanet.id)
    _renderColonySection(col)
  } catch (err) {
    cpUpgradeBtn.disabled    = false
    cpStatus.innerHTML = `<span style="color:#cc4444;font-size:10px">${err.message}</span>`
  }
})

// ── Mouse tracking ────────────────────────────────────────────────────────────

canvas.addEventListener('mousemove', (e) => {
  renderer.mouseX = e.clientX
  renderer.mouseY = e.clientY
})
canvas.addEventListener('mouseleave', () => {
  renderer.mouseX = -9999
  renderer.mouseY = -9999
})

// ── HUD ───────────────────────────────────────────────────────────────────────

const hudPos    = document.getElementById('hud-pos')
const hudZoom   = document.getElementById('hud-zoom')
const hudStars  = document.getElementById('hud-stars')
const hudChunks = document.getElementById('hud-chunks')
const hudSeed   = document.getElementById('hud-seed')

if (hudSeed) hudSeed.textContent = String(config.seed)

// ── Pre-fetch initial viewport area ──────────────────────────────────────────

;(() => {
  const r    = config.galaxyRadiusLy * 0.6
  const step = config.chunkSizeLy * 8
  for (let x = -r; x <= r; x += step) {
    for (let y = -r; y <= r; y += step) {
      galaxyClient.getStarsInViewport({ minX: x, minY: y, maxX: x + 1, maxY: y + 1 })
    }
  }
})()

// ── Game loop ─────────────────────────────────────────────────────────────────

let lastTime    = 0
let lastPersist = 0

function gameLoop(timestamp) {
  const dtMs  = Math.min(timestamp - lastTime, 100)
  const dtSec = dtMs / 1000
  lastTime = timestamp

  input.update()
  ship.update(dtSec)

  const shipBounds = ship.getExplorationBounds()
  const viewBounds = camera.getViewportBounds(viewport.width, viewport.height)

  galaxyClient.getStarsInViewport(shipBounds)
  explorationTracker.markExploredBounds(
    shipBounds.minX, shipBounds.minY, shipBounds.maxX, shipBounds.maxY,
    config.chunkSizeLy,
  )

  if (timestamp - lastPersist > 5000) {
    explorationTracker.persist()
    lastPersist = timestamp
  }

  const stars = galaxyClient.getStarsInViewport(viewBounds)
  renderer.render(viewport.width, viewport.height, ship, stars.length)

  if (hudPos)    hudPos.textContent    = `${ship.worldX.toFixed(0)}, ${ship.worldY.toFixed(0)} Ly`
  if (hudZoom)   hudZoom.textContent   = `${camera.zoom.toFixed(4)} px/Ly`
  if (hudStars)  hudStars.textContent  = String(stars.length)
  if (hudChunks) hudChunks.textContent = `${galaxyClient.generatedChunkCount} (${explorationTracker.count} explored)`

  requestAnimationFrame(gameLoop)
}

requestAnimationFrame((t) => {
  lastTime = t
  requestAnimationFrame(gameLoop)
})
