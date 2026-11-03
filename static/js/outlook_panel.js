/**
 * Outlook panel (E): where every resource is heading at today's rates,
 * for the whole civilization and colony by colony. Refreshes while open.
 */
const RES = {
  food: 'Food', water: 'Water', organicFuels: 'Org.Fuels', chemFeedstocks: 'Chem.Feed',
  minerals: 'Minerals', fusionFuel: 'Fusion', metals: 'Metals', radioactives: 'Radioact.',
}
const COLOR = { ok: '#44cc88', tight: '#ddbb44', falling: '#dd8844', critical: '#cc4444' }
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const num = v => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2))
const signed = v => (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v))

/** Ticks are minutes. */
export function duration(ticks) {
  if (ticks == null) return ''
  if (ticks < 60) return `${Math.max(1, Math.round(ticks))} min`
  if (ticks < 1440) return `${(ticks / 60).toFixed(1)} h`
  return `${(ticks / 1440).toFixed(1)} days`
}

function stateText(row) {
  const c = COLOR[row.state]
  if (row.state === 'ok') return `<span style="color:${c}">ok</span>`
  if (row.state === 'tight') return `<span style="color:${c}">tight</span>`
  return `<span style="color:${c}">${duration(row.runwayTicks)} left</span>`
}

function headline(o) {
  const civ = o.civ
  const w = civ.worst
  const room = civ.roomForOutposts
  const roomText = `Room for <b>${room.food}</b> more outpost${room.food === 1 ? '' : 's'} on food and ` +
    `<b>${room.water}</b> on water (each eats ${civ.outpostUse.food} of each per tick unless its world makes it).`
  if (!w) return `<div class="ol-verdict" style="color:${COLOR.ok}">Everything is growing.</div>${roomText}`
  const r = civ.resources.find(x => x.resource === w.resource)
  const what = RES[w.resource] ?? w.resource
  const msg = w.state === 'tight'
    ? `${what} is tight: ${signed(r.net)}/tick, only ${Math.round(100 * r.net / r.used)}% more than you use.`
    : `${what} is running out: ${signed(r.net)}/tick, gone in ${duration(r.runwayTicks)}.`
  return `<div class="ol-verdict" style="color:${COLOR[w.state]}">${msg}</div>${roomText}`
}

function civTable(o) {
  const after = o.civ.afterLanding
  const byRes = Object.fromEntries((after ?? []).map(a => [a.resource, a]))
  const rows = o.civ.resources.filter(r => r.used > 0 || r.made > 0 || r.stock > 0).map(r => `
    <tr><td>${RES[r.resource]}</td><td>${num(r.stock)}</td><td>${num(r.made)}</td><td>${num(r.used)}</td>
      <td style="color:${COLOR[r.state]}">${signed(r.net)}</td><td>${stateText(r)}</td>
      ${after ? `<td style="color:${COLOR[byRes[r.resource].state]}">${signed(byRes[r.resource].net)}</td>` : ''}</tr>`).join('')
  return `<table class="cp-flows-table ol-table">
    <thead><tr><th></th><th>stock</th><th>made</th><th>used</th><th>net</th><th>outlook</th>
      ${after ? '<th title="once the colony ships under way have landed">landed</th>' : ''}</tr></thead>
    <tbody>${rows}</tbody></table>
    <div class="tf-hint">Per tick (a minute). Stock includes goods aboard your ships.</div>`
}

function colonyList(o) {
  const civ = Object.fromEntries(o.civ.resources.map(r => [r.resource, r]))
  const cover = r => {
    const e = civ[r.resource]
    if (e.state === 'falling' || e.state === 'critical') return '<span style="color:#cc4444">empire short too</span>'
    if (e.state === 'tight') return '<span style="color:#ddbb44">empire barely covers it</span>'
    return o.traders ? '<span class="mk-incoming">empire has spare</span>'
                     : '<span class="mk-incoming">empire has spare: needs a trader or route</span>'
  }
  return o.colonies.map(c => {
    const bad = c.resources.filter(r => r.state !== 'ok')
    const lines = bad.length
      ? bad.map(r => `<div class="ol-line"><span>${RES[r.resource]}</span>
          <span style="color:${COLOR[r.state]}">${signed(r.net)}/tick</span>
          <span>${stateText(r)}</span>
          ${r.incoming > 0 ? `<span class="mk-incoming">+${num(r.incoming)} on the way</span>` : ''}
          ${r.state === 'falling' || r.state === 'critical' ? cover(r) : ''}</div>`).join('')
      : `<div class="ol-line" style="color:${COLOR.ok}">self-sufficient</div>`
    const starving = c.starving
      ? ` <span style="color:${COLOR.critical}">starving ${c.starvationTicks}/10</span>` : ''
    return `<div class="ol-colony" data-planet="${esc(c.planetId)}">
      <div class="rp-route-header"><span class="rp-route-name">${c.isHomeworld ? '★ ' : ''}${esc(c.name)}${starving}</span>
        <span class="rp-route-ship">${esc(c.sizeName)} · ${esc(c.devName)}</span></div>
      ${lines}</div>`
  }).join('')
}

export class OutlookPanel {
  constructor(el) {
    this.el = el
    this.timer = null
  }

  get open() { return this.el.style.display === 'block' }

  async show() {
    this.el.style.display = 'block'
    await this.refresh()
    clearInterval(this.timer)
    this.timer = setInterval(() => this.refresh(), 15_000)
  }

  hide() {
    this.el.style.display = 'none'
    clearInterval(this.timer)
  }

  toggle() { this.open ? this.hide() : this.show() }

  async refresh() {
    let o
    try {
      const r = await fetch('/api/outlook')
      if (!r.ok) return
      o = await r.json()
    } catch { return }
    const civ = o.civ
    const landing = civ.landing.length
      ? ` · ${civ.landing.length} colony ship${civ.landing.length > 1 ? 's' : ''} landing` : ''
    this.el.innerHTML = `
      <div class="rp-header"><span>OUTLOOK</span><button class="ol-close">✕</button></div>
      <div class="rp-builder-label">Civilization · ${civ.colonies} colonies${
        civ.starving ? ` · <span style="color:${COLOR.critical}">${civ.starving} starving</span>` : ''}${landing}</div>
      <div class="ol-summary">${headline(o)}</div>
      ${civTable(o)}
      <hr class="cp-divider">
      <div class="rp-builder-label">Colonies, most at risk first</div>
      ${colonyList(o)}
      <div class="tf-hint">A colony short of anything it uses for 10 ticks in a row loses a development
        level. Free traders (T) move spare goods to colonies that are short.</div>`
    this.el.querySelector('.ol-close').addEventListener('click', () => this.hide())
  }
}

/** One line for the colonize panel: the outpost's own net, and the
 *  civilization's food and water with it. */
export async function outpostLine(asOutpost) {
  let civ = null
  try {
    const r = await fetch('/api/outlook')
    if (r.ok) civ = (await r.json()).civ
  } catch { /* the outpost's own numbers still help */ }
  const parts = ['food', 'water'].map(k => {
    const own = asOutpost?.[k] ?? 0
    const now = civ ? civ.resources.find(r => r.resource === k).net : null
    const after = now == null ? '' : `, empire ${signed(now)} → <span style="color:${
      now + own < 0 ? COLOR.critical : COLOR.ok}">${signed(now + own)}</span>`
    return `${RES[k]} <span style="color:${own < 0 ? COLOR.falling : COLOR.ok}">${signed(own)}</span>${after}`
  })
  return `As a new outpost, per tick: ${parts.join(' · ')}`
}
