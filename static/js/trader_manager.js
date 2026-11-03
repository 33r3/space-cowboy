/**
 * TraderManager — the player's free traders (/api/traders), polled every
 * 10 s (a trip is only a few ticks), plus the Free Traders section of the
 * routes panel.
 */
const RES_SHORT = {
  food: 'Food', water: 'Water', organicFuels: 'Org.Fuels', chemFeedstocks: 'Chem.Feed',
  minerals: 'Minerals', fusionFuel: 'Fusion', metals: 'Metals', radioactives: 'Radioact.',
}
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const goods = cargo => Object.entries(cargo ?? {})
  .map(([k, v]) => `${v >= 100 ? v.toFixed(0) : v.toFixed(1)} ${RES_SHORT[k] ?? k}`).join(', ')

export class TraderManager {
  #traders  = []
  #onUpdate = null

  async init() {
    await this.refresh()
    setInterval(() => this.refresh(), 10_000)
  }

  get traders() { return this.#traders }
  set onUpdate(fn) { this.#onUpdate = fn }

  async refresh() {
    try {
      const r = await fetch('/api/traders')
      if (r.ok) this.#traders = (await r.json()).traders
    } catch { /* keep the last list */ }
    this.#onUpdate?.()
  }

  async build(planetId, shipClass) {
    const r = await fetch('/api/traders', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ planetId, shipClass }),
    })
    if (!r.ok) throw new Error((await r.json()).error ?? 'failed')
    await this.refresh()
  }

  async scrap(id) {
    await fetch(`/api/traders/${encodeURIComponent(id)}`, { method: 'DELETE' })
    await this.refresh()
  }
}

function statusLine(t) {
  if (t.status === 'idle') {
    const last = t.last ? ` · last: ${goods(t.last.cargo)} to ${esc(t.last.to)}` : ''
    return `<span class="net-zero">waiting at ${esc(t.atName)}</span>${last}`
  }
  const pct = (t.progressPct ?? 0).toFixed(0)
  if (t.status === 'pickup') {
    return `→ ${esc(t.toName)} to collect ${goods(t.want)} for ${esc(t.thenName)} (${pct}%)`
  }
  return `${esc(t.fromName)} → ${esc(t.toName)}: ${goods(t.cargo)} (${pct}%)`
}

/** The list of traders (redrawn on every poll). */
export function renderTraderList(el, mgr) {
  el.innerHTML = mgr.traders.map(t => `
    <div class="rp-route-entry ft-entry">
      <div class="rp-route-header">
        <span class="rp-route-name">${esc(t.shipName)}${t.retiring ? ' <span class="rp-paused-badge">scrapping after this trip</span>' : ''}</span>
        <span class="rp-route-ship">${t.trips} trips · ${Math.round(t.valueMoved)} cr</span>
        <button class="rp-cancel-btn ft-scrap" data-id="${esc(t.traderId)}" title="Scrap">✕</button>
      </div>
      <div class="rp-leg-label">${statusLine(t)}</div>
      ${t.status !== 'idle' ? `<div class="rp-progress-bar"><div class="rp-progress-fill" style="width:${t.progressPct ?? 0}%"></div></div>` : ''}
    </div>`).join('') ||
    '<div class="rp-empty">No free traders. Build one: it finds its own work, carrying spare goods to colonies that are short.</div>'
  el.querySelectorAll('.ft-scrap').forEach(b => b.addEventListener('click', async e => {
    e.stopPropagation()
    b.disabled = true
    await mgr.scrap(b.dataset.id)
  }))
}

/**
 * The build form (drawn when the panel opens).
 * colonies: active colonies [{planetId, name}]; getShips(planetId) -> classes.
 */
export function renderTraderForm(el, mgr, colonies, getShips) {
  const opts = colonies.map(c => `<option value="${esc(c.planetId)}">${esc(c.name)}</option>`).join('')
  el.innerHTML = `
    <div class="tf-row">
      <select id="ft-colony">${opts}</select>
      <select id="ft-class"></select>
    </div>
    <div id="ft-cost" class="rp-cost-label"></div>
    <button id="ft-build">+ Build free trader</button>
    <div id="ft-error" style="color:#cc4444"></div>`

  const colSel = el.querySelector('#ft-colony')
  const clsSel = el.querySelector('#ft-class')
  const cost = el.querySelector('#ft-cost')
  let ships = []
  const showCost = () => {
    const s = ships.find(x => x.id === clsSel.value)
    cost.innerHTML = s
      ? `holds ${s.capacity} · ${s.speedLyPerTick} Ly/tick · range ${s.maxRangeLy} Ly<br>costs <span>${
          Object.entries(s.setupCost).map(([k, v]) => `${v} ${RES_SHORT[k] ?? k}`).join(' · ')}</span>`
      : ''
  }
  const loadShips = async () => {
    if (!colSel.value) return
    try { ships = await getShips(colSel.value) } catch { ships = [] }
    clsSel.innerHTML = ships.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')
    showCost()
  }
  colSel.addEventListener('change', loadShips)
  clsSel.addEventListener('change', showCost)
  loadShips()

  el.querySelector('#ft-build').addEventListener('click', async () => {
    const err = el.querySelector('#ft-error')
    err.textContent = ''
    try { await mgr.build(colSel.value, clsSel.value) }
    catch (e) { err.textContent = e.message }
  })
}
