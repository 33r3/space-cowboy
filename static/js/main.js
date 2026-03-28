import { Camera } from './camera.js'
import { Viewport } from './viewport.js'
import { GalaxyClient } from './galaxy_client.js'
import { Ship } from './ship.js'
import { ExplorationTracker } from './exploration_tracker.js'
import { InputHandler } from './input_handler.js'
import { Renderer } from './renderer.js'
import { ColonyManager } from './colony_manager.js'
import { RouteManager } from './route_manager.js'

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

// ── Route manager ─────────────────────────────────────────────────────────────

const routeManager = new RouteManager()
routeManager.init()

// ── Renderer & input ──────────────────────────────────────────────────────────

const renderer = new Renderer(ctx, camera, galaxyClient, colonyManager, routeManager)
const input    = new InputHandler(canvas, camera, ship, viewport)

input.onDebugToggle  = () => { renderer.showDebug = !renderer.showDebug }
input.onCameraReset  = () => { camera.worldX = ship.worldX; camera.worldY = ship.worldY }
input.onRoutesToggle = () => {
  if (routesPanel?.style.display === 'none' || !routesPanel?.style.display) {
    openRoutesPanel()
  } else {
    closeRoutesPanel()
  }
}
input.onColonyListToggle = () => {
  if (colonyListPanel?.style.display === 'none' || !colonyListPanel?.style.display) {
    openColonyListPanel()
  } else {
    closeColonyListPanel()
  }
}

// ── Colony panel ──────────────────────────────────────────────────────────────

const colonyPanel        = document.getElementById('colony-panel')
const cpTitle            = document.getElementById('colony-panel-title')
const cpSubtitle         = document.getElementById('colony-panel-subtitle')
const cpStatus           = document.getElementById('colony-panel-status')
const cpColonySection    = document.getElementById('colony-panel-colony-section')
const cpYieldsSection    = document.getElementById('colony-panel-yields-section')
const cpYields           = document.getElementById('colony-panel-yields')
const cpFoundBtn         = document.getElementById('colony-panel-found')
const cpSourceRow        = document.getElementById('colony-panel-source-row')
const cpSourceSelect     = document.getElementById('colony-panel-source-select')
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
const cpTransitSection   = document.getElementById('colony-panel-transit-section')
const cpTransitBar       = document.getElementById('cp-transit-bar-fill')
const cpTransitLabel     = document.getElementById('cp-transit-label')
const cpTransitSource    = document.getElementById('cp-transit-source')
const cpTransitEta       = document.getElementById('cp-transit-eta')

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

function _renderTransitSection(colony) {
  cpColonySection.style.display  = 'none'
  cpYieldsSection.style.display  = 'none'
  cpFoundBtn.style.display       = 'none'
  cpTransitSection.style.display = 'block'

  const pct = colony.transitProgressPct ?? 0
  const eta = Math.ceil(colony.ticksRemaining ?? 0)
  cpTransitBar.style.width   = `${pct}%`
  cpTransitLabel.textContent = `${pct.toFixed(1)}%`
  cpTransitEta.textContent   = `ETA: ~${eta} tick${eta !== 1 ? 's' : ''} (~${eta} min)`
  const srcCol = colony.sourcePlanetId ? colonyManager.getColony(colony.sourcePlanetId) : null
  cpTransitSource.textContent = `From: ${srcCol?.name ?? colony.sourcePlanetId ?? 'Unknown'}`
}

function _renderColonySection(colony) {
  cpColonySection.style.display  = 'block'
  cpYieldsSection.style.display  = 'none'
  cpTransitSection.style.display = 'none'
  cpFoundBtn.style.display       = 'none'

  if (colony.isAbandoned) {
    cpUpgradeBtn.disabled    = true
    cpUpgradeBtn.textContent = 'Abandoned'
    cpUpgradeCost.textContent = 'This colony has been abandoned due to starvation.'
    // Still show the last stockpile and flow state for information
  }

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
  if (!colony.isAbandoned) {
    cpUpgradeBtn.disabled = !colony.canUpgradeDev || dev >= 5
    cpUpgradeBtn.textContent = dev >= 5 ? 'Max' : `→ ${DEV_NAMES[dev] ?? ''}`
  }

  if (!colony.isAbandoned) {
    if (colony.upgradeCost && dev < 5) {
      cpUpgradeCost.textContent = 'Cost: ' +
        Object.entries(colony.upgradeCost)
          .map(([k, v]) => `${v} ${RES_LABELS[k] ?? k}`)
          .join(' · ')
    } else {
      cpUpgradeCost.textContent = ''
    }
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

  // Abandoned: show repopulate button using normal colonization preview
  if (colony.isAbandoned && _panelMeta && _panelPlanet) {
    cpFoundBtn.style.display = 'block'
    cpFoundBtn.disabled      = true
    cpFoundBtn.textContent   = 'Checking...'
    colonyManager.getColonizationPreview(_panelMeta.cx, _panelMeta.cy, _panelMeta.starIndex, _panelPlanet.index)
      .then(preview => {
        const firstSource      = preview.sources?.[0]
        cpFoundBtn.disabled    = !preview.eligible || !firstSource?.canAfford
        cpFoundBtn.textContent = 'Resend Colony Ship'
      })
      .catch(() => {
        cpFoundBtn.disabled    = true
        cpFoundBtn.textContent = 'Resend Colony Ship'
      })
  }
}

function _renderYieldsSection(planet, meta) {
  cpColonySection.style.display  = 'none'
  cpTransitSection.style.display = 'none'

  // Potential yields
  const yields  = planet.colonyYields ?? {}
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

  // Colonization eligibility — fetch preview async, show loading state
  cpFoundBtn.style.display  = 'block'
  cpFoundBtn.disabled       = true
  cpFoundBtn.textContent    = 'Checking...'
  cpStatus.innerHTML        = ''
  cpSourceRow.style.display = 'none'
  cpSourceSelect.innerHTML  = ''

  if (!meta) { cpFoundBtn.disabled = true; cpFoundBtn.textContent = 'Found Colony'; return }

  colonyManager.getColonizationPreview(meta.cx, meta.cy, meta.starIndex, planet.index)
    .then(preview => {
      if (!preview.eligible) {
        cpStatus.innerHTML =
          `<div style="font-size:10px;color:#cc4444">${preview.reason ?? 'Cannot colonize'}</div>`
        cpFoundBtn.disabled = true; cpFoundBtn.textContent = 'Found Colony'; return
      }

      const costStr = Object.entries(preview.cost ?? {})
        .map(([k, v]) => `${v} ${RES_LABELS[k] ?? k}`).join(' · ')

      // Populate source dropdown
      cpSourceSelect.innerHTML = ''
      for (const src of preview.sources) {
        const opt = document.createElement('option')
        opt.value       = src.planetId
        opt.textContent = `${src.name} (${src.devName})  ${src.distance} Ly`
        if (!src.canAfford) opt.style.color = '#cc4444'
        cpSourceSelect.appendChild(opt)
      }
      cpSourceRow.style.display = 'block'

      function _applySelection() {
        const src = preview.sources.find(s => s.planetId === cpSourceSelect.value)
        if (!src) return
        cpStatus.innerHTML =
          `<div style="font-size:10px;line-height:1.9;color:#556677">` +
          `Cost: <span style="color:#88aacc">${costStr}</span><br>` +
          (src.transitTicks ? `Transit: <span style="color:#88aacc">~${src.transitTicks} min</span><br>` : '') +
          `<span style="color:${src.canAfford ? '#66cc88' : '#cc4444'}">${src.canAfford ? 'affordable' : 'INSUFFICIENT FUNDS'}</span></div>`
        cpFoundBtn.disabled    = !src.canAfford
        cpFoundBtn.textContent = 'Found Colony'
      }

      _applySelection()
      cpSourceSelect.addEventListener('change', _applySelection)
    })
    .catch(() => { cpFoundBtn.disabled = true; cpFoundBtn.textContent = 'Found Colony' })
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

  const isHW        = colonyManager.isHomeworld(planet.id)
  const isTransit   = colonyManager.isInTransit(planet.id)
  const isColony    = colonyManager.isColony(planet.id)
  const col         = (isHW || isColony) ? colonyManager.getColony(planet.id) : null
  const isAbandoned = col?.isAbandoned ?? false

  cpTitle.textContent   = planet.name
  cpTitle.style.color   = isAbandoned ? '#cc4444'
                        : isHW        ? '#ffd700'
                        : isTransit   ? '#ffaa44'
                        : isColony    ? '#44ffcc'
                        : '#aaccee'
  cpSubtitle.textContent = `${planet.planetType}  ·  ${planet.semiMajorAxisAU.toFixed(2)} AU  ·  Hab ${planet.habitability.total}/100`

  if (isAbandoned)    cpStatus.innerHTML = '<span style="color:#cc4444;font-size:11px">☠ Abandoned</span>'
  else if (isHW)      cpStatus.innerHTML = '<span style="color:#ffd700;font-size:11px">★ Home World</span>'
  else if (isTransit) cpStatus.innerHTML = '<span style="color:#ffaa44;font-size:11px">▶ Colony Ship In Transit</span>'
  else if (isColony)  cpStatus.innerHTML = '<span style="color:#44ffcc;font-size:11px">■ Colony</span>'
  else                cpStatus.innerHTML = ''

  if (isTransit && col) {
    _renderTransitSection(col)
  } else if (isHW || isColony) {
    if (col) _renderColonySection(col)
    else     _renderYieldsSection(planet, _panelMeta)
  } else {
    _renderYieldsSection(planet, _panelMeta)
  }

  colonyPanel.style.display = 'block'
}

// Refresh panel if it's open and colony data was updated by polling
colonyManager.onUpdate = () => {
  if (colonyListPanel?.style.display !== 'none') _renderColonyList()
  if (colonyPanel.style.display === 'none' || !_panelPlanet) return
  const col = colonyManager.getColony(_panelPlanet.id)
  if (!col) {
    // Re-check colonization eligibility in case source stockpiles changed
    _renderYieldsSection(_panelPlanet, _panelMeta)
    return
  }
  if (col.status === 'in_transit') {
    cpTitle.style.color = '#ffaa44'
    cpStatus.innerHTML  = '<span style="color:#ffaa44;font-size:11px">▶ Colony Ship In Transit</span>'
    _renderTransitSection(col)
  } else {
    if (cpTransitSection) cpTransitSection.style.display = 'none'
    cpTitle.style.color = col.isAbandoned ? '#cc4444'
                        : colonyManager.isHomeworld(_panelPlanet.id) ? '#ffd700' : '#44ffcc'
    _renderColonySection(col)
  }
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
    const sourcePlanetId = cpSourceSelect.value || undefined
    const col = await colonyManager.foundColony(
      _panelPlanet, _panelMeta.cx, _panelMeta.cy, _panelMeta.starIndex, sourcePlanetId,
    )
    if (col?.status === 'in_transit') {
      cpTitle.style.color = '#ffaa44'
      cpStatus.innerHTML  = '<span style="color:#ffaa44;font-size:11px">▶ Colony Ship In Transit</span>'
      _renderTransitSection(col)
    } else if (col) {
      cpTitle.style.color = '#44ffcc'
      cpStatus.innerHTML  = '<span style="color:#44ffcc;font-size:11px">■ Colony</span>'
      _renderColonySection(col)
    } else {
      cpFoundBtn.textContent = 'Colonized'
      cpFoundBtn.disabled    = true
    }
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

// ── Colony list panel ─────────────────────────────────────────────────────────

const colonyListPanel = document.getElementById('colony-list-panel')
const clCloseBtn      = document.getElementById('cl-close-btn')
const clList          = document.getElementById('cl-list')

const SIZE_NAMES_SHORT = ['Outpost', 'Settlement', 'Town', 'City', 'Megacity']

function _renderColonyList() {
  const all = colonyManager.colonies
  if (!all.length) {
    clList.innerHTML = '<div class="cl-empty">No colonies founded yet.</div>'
    return
  }
  clList.innerHTML = all.map(col => {
    const isHW       = colonyManager.isHomeworld(col.planetId)
    const isTransit  = col.status === 'in_transit'
    const isAbandoned = col.isAbandoned || col.status === 'abandoned'

    let icon, color
    if (isHW)          { icon = '★'; color = '#ffd700' }
    else if (isAbandoned) { icon = '☠'; color = '#cc4444' }
    else if (isTransit)   { icon = '▶'; color = '#ffaa44' }
    else                   { icon = '■'; color = '#44ffcc' }

    let detail
    if (isAbandoned) {
      detail = 'Abandoned'
    } else if (isTransit) {
      const pct = (col.transitProgressPct ?? 0).toFixed(0)
      const eta = Math.ceil(col.ticksRemaining ?? 0)
      detail = `In Transit · ${pct}% · ~${eta} min`
    } else {
      const sz  = SIZE_NAMES_SHORT[(col.size ?? 1) - 1] ?? 'Outpost'
      const dev = col.developmentLevel ?? 1
      detail = `${sz} · Dev ${dev}`
    }

    return `<div class="cl-entry">
      <div class="cl-icon" style="color:${color}">${icon}</div>
      <div class="cl-info">
        <div class="cl-name" style="color:${color}">${col.name}</div>
        <div class="cl-detail">${detail}</div>
      </div>
      <button class="cl-zoom-btn" data-pid="${col.planetId}">→</button>
    </div>`
  }).join('')

  clList.querySelectorAll('.cl-zoom-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const col = colonyManager.getColony(btn.dataset.pid)
      if (!col?.planet) return
      camera.worldX = col.planet.worldX
      camera.worldY = col.planet.worldY
      camera.zoom   = Math.max(camera.zoom, 150)
    })
  })
}

function openColonyListPanel() {
  if (!colonyListPanel) return
  closeRoutesPanel()
  _renderColonyList()
  colonyListPanel.style.display = 'block'
}

function closeColonyListPanel() {
  if (colonyListPanel) colonyListPanel.style.display = 'none'
}

clCloseBtn?.addEventListener('click', closeColonyListPanel)

// ── Routes panel ──────────────────────────────────────────────────────────────

const routesPanel    = document.getElementById('routes-panel')
const rpClose        = document.getElementById('rp-close')
const rpRouteList    = document.getElementById('rp-route-list')
const rpNewBtn       = document.getElementById('rp-new-btn')
const rpBuilder      = document.getElementById('rp-builder')
const rpShipSelect   = document.getElementById('rp-ship-select')
const rpLegsDiv      = document.getElementById('rp-legs')
const rpAddLeg       = document.getElementById('rp-add-leg')
const rpNameInput    = document.getElementById('rp-name')
const rpSetupCost    = document.getElementById('rp-setup-cost')
const rpBuilderError = document.getElementById('rp-builder-error')
const rpSubmit       = document.getElementById('rp-submit')
const rpCancel       = document.getElementById('rp-cancel')
const rpBuilderTitle = document.getElementById('rp-builder-title')

const ALL_RESOURCES = [
  'food', 'water', 'organicFuels', 'chemFeedstocks',
  'minerals', 'fusionFuel', 'metals', 'radioactives',
]

function _renderRouteList() {
  const routes = routeManager.routes
  if (!routes.length) {
    rpRouteList.innerHTML = '<div class="rp-empty">No trade routes. Click + New Route to begin.</div>'
    return
  }
  rpRouteList.innerHTML = routes.map(r => {
    const leg      = r.currentLeg
    const pct      = leg?.progressPct ?? 0
    const legText  = leg ? `${leg.fromName} → ${leg.toName} (${pct.toFixed(0)}%)` : ''
    const paused   = r.status === 'paused'
    const events   = r.events ?? []
    const unread   = events.filter(e => !e.read).length
    const statusBadge = paused
      ? `<span class="rp-paused-badge">⚠ paused</span>`
      : ''
    const unreadBadge = (unread > 0 && !paused)
      ? `<span class="rp-unread-badge">${unread}</span>`
      : ''

    const eventsHtml = events.length
      ? `<div class="rp-events">${
          events.slice(-3).reverse().map(e =>
            `<div class="rp-event${e.read ? '' : ' unread'}">${e.message}</div>`
          ).join('')
        }</div>`
      : ''

    return `<div class="rp-route-entry" data-id="${r.routeId}">
      <div class="rp-route-header">
        <span class="rp-route-name">${r.name}${statusBadge}${unreadBadge}</span>
        <span class="rp-route-ship">${r.shipName ?? r.shipClass}</span>
        <button class="rp-edit-btn" data-id="${r.routeId}">✎</button>
        <button class="rp-cancel-btn" data-id="${r.routeId}">✕</button>
      </div>
      ${leg && !paused ? `<div class="rp-leg-progress">
        <span class="rp-leg-label">${legText}</span>
        <div class="rp-progress-bar">
          <div class="rp-progress-fill" style="width:${pct}%"></div>
        </div>
      </div>` : ''}
      ${eventsHtml}
    </div>`
  }).join('')

  rpRouteList.querySelectorAll('.rp-cancel-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation()
      try {
        await routeManager.deleteRoute(btn.dataset.id)
        _renderRouteList()
      } catch (err) {
        console.error('Delete route failed:', err.message)
      }
    })
  })

  rpRouteList.querySelectorAll('.rp-edit-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation()
      const route = routeManager.routes.find(r => r.routeId === btn.dataset.id)
      if (route) await _openEditor(route)
    })
  })

  // Clicking route entry marks events read
  rpRouteList.querySelectorAll('.rp-route-entry').forEach(entry => {
    entry.addEventListener('click', async () => {
      const id = entry.dataset.id
      const route = routeManager.routes.find(r => r.routeId === id)
      if (route?.events?.some(e => !e.read)) {
        await routeManager.markEventsRead(id)
      }
    })
  })
}

routeManager.onUpdate = () => {
  if (routesPanel && routesPanel.style.display !== 'none') {
    _renderRouteList()
  }
}

// ── Route builder ──────────────────────────────────────────────────────────────

let _builderShips   = []
let _builderLegs    = []   // [{ fromId, toId, cargo }]
let _builderMode    = 'create'   // 'create' | 'edit'
let _builderRouteId = null

function _getColonyOptions() {
  return colonyManager.colonies
    .filter(c => colonyManager.isActiveColony(c.planetId))
    .map(c => `<option value="${c.planetId}">${c.name}</option>`)
    .join('')
}

function _updateSetupCostDisplay() {
  const shipId = rpShipSelect.value
  const ship   = _builderShips.find(s => s.id === shipId)
  if (!ship) { rpSetupCost.innerHTML = ''; return }
  const costParts = Object.entries(ship.setupCost ?? {})
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${v} ${RES_LABELS[k] ?? k}`)
    .join(' · ')
  rpSetupCost.innerHTML =
    `<div class="rp-cost-label">Setup cost: <span>${costParts || 'free'}</span></div>` +
    `<div class="rp-cost-label">Capacity: <span>${ship.capacity} units · ` +
    `${ship.maxRangeLy} Ly max range · ${ship.speedLyPerTick} Ly/tick</span></div>`
}

function _updateRangeHint(legIdx) {
  const hint = rpLegsDiv.querySelector(`.rp-range-hint[data-idx="${legIdx}"]`)
  if (!hint) return
  const leg      = _builderLegs[legIdx]
  const ship     = _builderShips.find(s => s.id === rpShipSelect?.value)
  const maxRange = ship?.maxRangeLy ?? Infinity
  const fromCol  = leg?.fromId ? colonyManager.getColony(leg.fromId) : null
  const toCol    = leg?.toId   ? colonyManager.getColony(leg.toId)   : null
  if (!fromCol?.planet || !toCol?.planet || leg.fromId === leg.toId) {
    hint.textContent = ''; hint.className = 'rp-range-hint'; return
  }
  const dx   = fromCol.planet.worldX - toCol.planet.worldX
  const dy   = fromCol.planet.worldY - toCol.planet.worldY
  const dist = Math.sqrt(dx * dx + dy * dy)
  const ok   = dist <= maxRange
  hint.textContent = `${Math.round(dist)} / ${maxRange} Ly`
  hint.className   = `rp-range-hint ${ok ? 'rp-range-ok' : 'rp-range-over'}`
}

function _renderBuilderLegs() {
  const colonyOptions = _getColonyOptions()
  rpLegsDiv.innerHTML = _builderLegs.map((leg, i) => {
    const cargoRows = ALL_RESOURCES.map(res => {
      const val = leg.cargo[res] ?? 0
      return `<div class="rp-cargo-row">
        <label>${RES_LABELS[res] ?? res}</label>
        <input type="number" min="0" step="1" value="${val}"
          data-leg="${i}" data-res="${res}" class="rp-cargo-input">
      </div>`
    }).join('')

    return `<div class="rp-leg">
      <div class="rp-leg-header">Leg ${i + 1}
        ${_builderLegs.length > 1 ? `<button class="rp-remove-leg" data-idx="${i}">remove</button>` : ''}
      </div>
      <div class="rp-leg-from-to">
        <select class="rp-from-select" data-idx="${i}">${colonyOptions}</select>
        <span>→</span>
        <select class="rp-to-select" data-idx="${i}">${colonyOptions}</select>
        <span class="rp-range-hint" data-idx="${i}"></span>
      </div>
      <div class="rp-cargo-grid">${cargoRows}</div>
    </div>`
  }).join('')

  // Restore selections
  rpLegsDiv.querySelectorAll('.rp-from-select').forEach(sel => {
    const idx = parseInt(sel.dataset.idx)
    if (_builderLegs[idx]?.fromId) sel.value = _builderLegs[idx].fromId
  })
  rpLegsDiv.querySelectorAll('.rp-to-select').forEach(sel => {
    const idx = parseInt(sel.dataset.idx)
    if (_builderLegs[idx]?.toId) sel.value = _builderLegs[idx].toId
  })

  // Initial range hints
  _builderLegs.forEach((_, i) => _updateRangeHint(i))

  rpLegsDiv.querySelectorAll('.rp-from-select').forEach(sel => {
    sel.addEventListener('change', () => {
      const idx = parseInt(sel.dataset.idx)
      _builderLegs[idx].fromId = sel.value
      _updateRangeHint(idx)
    })
  })
  rpLegsDiv.querySelectorAll('.rp-to-select').forEach(sel => {
    sel.addEventListener('change', () => {
      const idx = parseInt(sel.dataset.idx)
      _builderLegs[idx].toId = sel.value
      _updateRangeHint(idx)
    })
  })
  rpLegsDiv.querySelectorAll('.rp-cargo-input').forEach(inp => {
    inp.addEventListener('input', () => {
      const legIdx = parseInt(inp.dataset.leg)
      const res    = inp.dataset.res
      _builderLegs[legIdx].cargo[res] = Math.max(0, parseFloat(inp.value) || 0)
    })
  })
  rpLegsDiv.querySelectorAll('.rp-remove-leg').forEach(btn => {
    btn.addEventListener('click', () => {
      _builderLegs.splice(parseInt(btn.dataset.idx), 1)
      _renderBuilderLegs()
    })
  })
}

async function _openBuilder() {
  _builderMode    = 'create'
  _builderRouteId = null
  rpBuilder.style.display    = 'block'
  rpNewBtn.style.display     = 'none'
  rpBuilderError.textContent = ''
  rpBuilderTitle.textContent = 'NEW ROUTE'
  rpSubmit.textContent       = 'Create Route'
  rpShipSelect.disabled      = false

  const colonies = colonyManager.colonies.filter(c => colonyManager.isActiveColony(c.planetId))
  if (!colonies.length) {
    rpBuilderError.textContent = 'No active colonies available.'
    return
  }

  // Load ships available from first colony
  try {
    _builderShips = await routeManager.getShipsForColony(colonies[0].planetId)
  } catch {
    _builderShips = []
  }

  rpShipSelect.innerHTML = _builderShips.map(s =>
    `<option value="${s.id}">${s.name} (dev ${s.devRequired}+, cap ${s.capacity})</option>`
  ).join('')

  _builderLegs = [{
    fromId: colonies[0]?.planetId ?? '',
    toId:   colonies[1]?.planetId ?? colonies[0]?.planetId ?? '',
    cargo:  {},
  }]

  _updateSetupCostDisplay()
  _renderBuilderLegs()
}

function _closeBuilder() {
  rpBuilder.style.display    = 'none'
  rpNewBtn.style.display     = 'block'
  rpBuilderError.textContent = ''
  rpShipSelect.disabled      = false
  _builderMode    = 'create'
  _builderRouteId = null
}

async function _openEditor(route) {
  _builderMode    = 'edit'
  _builderRouteId = route.routeId
  rpBuilder.style.display    = 'block'
  rpNewBtn.style.display     = 'none'
  rpBuilderError.textContent = ''
  rpBuilderTitle.textContent = 'EDIT ROUTE'
  rpSubmit.textContent       = 'Save Changes'
  rpSubmit.disabled          = false

  const colonies = colonyManager.colonies.filter(c => colonyManager.isActiveColony(c.planetId))
  if (!colonies.length) { rpBuilderError.textContent = 'No active colonies.'; return }

  try { _builderShips = await routeManager.getShipsForColony(colonies[0].planetId) }
  catch { _builderShips = [] }

  rpShipSelect.innerHTML = _builderShips.map(s =>
    `<option value="${s.id}">${s.name} (dev ${s.devRequired}+, cap ${s.capacity})</option>`
  ).join('')
  rpShipSelect.value    = route.shipClass
  rpShipSelect.disabled = true

  rpNameInput.value = route.name ?? ''

  _builderLegs = (route.legs ?? []).map(leg => ({
    fromId: leg.fromPlanetId,
    toId:   leg.toPlanetId,
    cargo:  { ...(leg.cargo ?? {}) },
  }))

  _updateSetupCostDisplay()
  _renderBuilderLegs()
}

rpShipSelect?.addEventListener('change', () => {
  _updateSetupCostDisplay()
  _builderLegs.forEach((_, i) => _updateRangeHint(i))
})

rpAddLeg?.addEventListener('click', () => {
  const colonies = colonyManager.colonies.filter(c => colonyManager.isActiveColony(c.planetId))
  const lastLeg  = _builderLegs[_builderLegs.length - 1]
  _builderLegs.push({
    fromId: lastLeg?.toId ?? colonies[0]?.planetId ?? '',
    toId:   colonies[1]?.planetId ?? colonies[0]?.planetId ?? '',
    cargo:  {},
  })
  _renderBuilderLegs()
})

rpSubmit?.addEventListener('click', async () => {
  rpBuilderError.textContent = ''
  rpSubmit.disabled = true

  const name      = rpNameInput?.value.trim() || 'Trade Route'
  const shipClass = rpShipSelect?.value

  const legs = _builderLegs.map((leg, i) => {
    const fromSel = rpLegsDiv.querySelector(`.rp-from-select[data-idx="${i}"]`)
    const toSel   = rpLegsDiv.querySelector(`.rp-to-select[data-idx="${i}"]`)
    const cargo   = {}
    rpLegsDiv.querySelectorAll(`.rp-cargo-input[data-leg="${i}"]`).forEach(inp => {
      const v = parseFloat(inp.value) || 0
      if (v > 0) cargo[inp.dataset.res] = v
    })
    return {
      fromPlanetId: fromSel?.value ?? leg.fromId,
      toPlanetId:   toSel?.value   ?? leg.toId,
      cargo,
    }
  })

  try {
    if (_builderMode === 'edit') {
      await routeManager.updateRoute(_builderRouteId, { name, legs })
    } else {
      await routeManager.createRoute({ name, shipClass, legs })
    }
    rpSubmit.disabled = false
    _closeBuilder()
    _renderRouteList()
  } catch (err) {
    rpBuilderError.textContent = err.message
    rpSubmit.disabled = false
  }
})

rpCancel?.addEventListener('click', _closeBuilder)

function openRoutesPanel() {
  if (!routesPanel) return
  closeColonyListPanel()
  _renderRouteList()
  routesPanel.style.display = 'block'
}

function closeRoutesPanel() {
  if (!routesPanel) return
  routesPanel.style.display = 'none'
  _closeBuilder()
}

rpClose?.addEventListener('click', closeRoutesPanel)
rpNewBtn?.addEventListener('click', _openBuilder)

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
