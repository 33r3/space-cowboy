/**
 * Planet browser (P): every planet you know, filtered and sorted in the
 * browser. Clicking a row flies to its system and opens the planet panel.
 * Filters and sort are remembered in this browser.
 */
const RES = ['food', 'water', 'organicFuels', 'chemFeedstocks', 'minerals', 'fusionFuel', 'metals', 'radioactives']
const RES_SHORT = {
  food: 'Food', water: 'Water', organicFuels: 'Org', chemFeedstocks: 'Chem',
  minerals: 'Min', fusionFuel: 'Fus', metals: 'Met', radioactives: 'Rad',
}
const SIZES = ['Outpost', 'Settlement', 'Town', 'City', 'Megacity']
const MAX_ROWS = 400
const STORE = 'space-cowboy-planet-browser'
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

const DEFAULTS = {
  q: '', type: '', minHab: 0, status: 'unsettled', inRange: false, feeds: false,
  has: '', maxDist: '', sort: 'hab', dir: -1,
}

// Sort keys: value getters
const SORTS = {
  name: p => p.name, type: p => p.type, hab: p => p.hab, size: p => p.sizeCap, temp: p => p.tempK,
  feeds: p => Math.min(p.outpostFood, p.outpostWater),
  dist: p => p.distance ?? Infinity, status: p => p.mine ?? (p.others ? 'others' : ''),
  ...Object.fromEntries(RES.map(r => [r, p => p.yields[r] ?? 0])),
}

function habColor(h) {
  return h >= 65 ? '#44cc88' : h >= 45 ? '#88cc66' : h >= 25 ? '#ddbb44' : h >= 10 ? '#dd8844' : '#cc4444'
}

export class PlanetBrowser {
  constructor(el, onPick) {
    this.el = el
    this.onPick = onPick          // (row) => void
    this.rows = []
    this.f = { ...DEFAULTS }
    try { Object.assign(this.f, JSON.parse(localStorage.getItem(STORE) ?? '{}')) } catch { /* fresh */ }
  }

  get open() { return this.el.style.display === 'block' }
  hide() { this.el.style.display = 'none' }
  toggle() { this.open ? this.hide() : this.show() }

  async show() {
    this.el.style.display = 'block'
    if (!this.el.innerHTML) this.#skeleton()
    this.el.querySelector('.pb-count').textContent = 'Loading…'
    try {
      const r = await fetch('/api/planets')
      if (r.ok) this.rows = (await r.json()).planets
    } catch { /* keep the last list */ }
    this.#fillTypes()
    this.#render()
  }

  #save() {
    try { localStorage.setItem(STORE, JSON.stringify(this.f)) } catch { /* not remembered */ }
  }

  #skeleton() {
    const f = this.f
    this.el.innerHTML = `
      <div class="rp-header"><span>PLANETS</span><button class="ol-close pb-close">✕</button></div>
      <div class="pb-filters">
        <input class="pb-q" placeholder="name or star" value="${esc(f.q)}">
        <select class="pb-type"><option value="">all types</option></select>
        <label>hab ≥ <input class="pb-hab" type="number" min="0" max="100" value="${f.minHab}"></label>
        <label>≤ <input class="pb-dist" type="number" min="0" placeholder="any" value="${esc(f.maxDist)}"> Ly</label>
        <select class="pb-status">
          <option value="unsettled">unsettled</option><option value="all">all</option>
          <option value="mine">my colonies</option><option value="others">others' colonies</option>
        </select>
        <select class="pb-has"><option value="">any yields</option>${
          RES.map(r => `<option value="${r}">makes ${RES_SHORT[r]}</option>`).join('')}</select>
        <label><input class="pb-range" type="checkbox"> in reach</label>
        <label title="a new outpost there makes at least the food and water it eats"><input class="pb-feeds" type="checkbox"> feeds itself</label>
        <button class="pb-reset">reset</button>
      </div>
      <div class="pb-count"></div>
      <div class="pb-scroll"><table class="cp-flows-table pb-table"><thead></thead><tbody></tbody></table></div>`
    const $ = s => this.el.querySelector(s)
    $('.pb-status').value = f.status
    $('.pb-has').value = f.has
    $('.pb-range').checked = f.inRange
    $('.pb-feeds').checked = f.feeds
    const bind = (sel, key, read, ev = 'input') => $(sel).addEventListener(ev, e => {
      this.f[key] = read(e.target); this.#save(); this.#render()
    })
    bind('.pb-q', 'q', t => t.value.trim())
    bind('.pb-type', 'type', t => t.value, 'change')
    bind('.pb-hab', 'minHab', t => Number(t.value) || 0)
    bind('.pb-dist', 'maxDist', t => t.value.trim())
    bind('.pb-status', 'status', t => t.value, 'change')
    bind('.pb-has', 'has', t => t.value, 'change')
    bind('.pb-range', 'inRange', t => t.checked, 'change')
    bind('.pb-feeds', 'feeds', t => t.checked, 'change')
    $('.pb-close').addEventListener('click', () => this.hide())
    this.el.addEventListener('keydown', e => {      // the map's keys ignore text boxes
      if (e.key === 'Escape') { e.target.blur?.(); this.hide() }
    })
    $('.pb-reset').addEventListener('click', () => {
      this.f = { ...DEFAULTS }; this.#save(); this.el.innerHTML = ''; this.show()
    })
  }

  #fillTypes() {
    const sel = this.el.querySelector('.pb-type')
    const types = [...new Set(this.rows.map(p => p.type))].sort()
    sel.innerHTML = '<option value="">all types</option>' +
      types.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('')
    sel.value = types.includes(this.f.type) ? this.f.type : ''
  }

  #filtered() {
    const f = this.f
    const q = f.q.toLowerCase()
    const maxDist = f.maxDist === '' ? Infinity : Number(f.maxDist)
    return this.rows.filter(p =>
      (!q || p.name.toLowerCase().includes(q) || p.starName.toLowerCase().includes(q)) &&
      (!f.type || p.type === f.type) &&
      p.hab >= f.minHab &&
      (p.distance ?? Infinity) <= maxDist &&
      (f.status === 'all' ||
        (f.status === 'unsettled' && !p.mine && !p.others) ||
        (f.status === 'mine' && p.mine && p.mine !== 'abandoned') ||
        (f.status === 'others' && p.others > 0)) &&
      (!f.has || (p.yields[f.has] ?? 0) > 0) &&
      (!f.inRange || p.inRange) &&
      (!f.feeds || (p.outpostFood >= 0 && p.outpostWater >= 0)))
  }

  #render() {
    const f = this.f
    const get = SORTS[f.sort] ?? SORTS.hab
    const list = this.#filtered().sort((a, b) => {
      const x = get(a), y = get(b)
      return (x < y ? -1 : x > y ? 1 : 0) * f.dir || a.name.localeCompare(b.name)
    })
    const cols = [
      ['name', 'planet'], ['type', 'type'], ['hab', 'hab'], ['size', 'max'], ['temp', 'K'],
      ...RES.map(r => [r, RES_SHORT[r]]), ['feeds', 'feeds'], ['dist', 'Ly'], ['status', ''],
    ]
    const arrow = k => (k === f.sort ? (f.dir > 0 ? ' ▲' : ' ▼') : '')
    this.el.querySelector('thead').innerHTML = '<tr>' + cols.map(([k, label]) =>
      `<th data-k="${k}" title="sort">${label}${arrow(k)}</th>`).join('') + '</tr>'
    this.el.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
      const k = th.dataset.k
      if (f.sort === k) f.dir = -f.dir
      else { f.sort = k; f.dir = ['name', 'type', 'dist', 'temp', 'status'].includes(k) ? 1 : -1 }
      this.#save(); this.#render()
    }))

    const shown = list.slice(0, MAX_ROWS)
    const y = v => (v ? (v >= 1 ? v.toFixed(1) : v.toFixed(2)) : '<span class="net-zero">·</span>')
    this.el.querySelector('tbody').innerHTML = shown.map((p, i) => {
      const feeds = Math.min(p.outpostFood, p.outpostWater)
      const status = p.mine === 'active' ? '<span style="color:#44ffcc">■ yours</span>'
        : p.mine === 'in_transit' ? '<span style="color:#ffaa44">▶ landing</span>'
        : p.mine === 'abandoned' ? '<span style="color:#cc4444">☠</span>'
        : p.others ? `<span style="color:#cc8844">${p.others} other${p.others > 1 ? 's' : ''}</span>`
        : p.inRange ? '' : '<span class="net-zero">out of reach</span>'
      return `<tr data-i="${i}" title="${esc(p.type)} · ${esc(p.habCategory)} · nearest colony ${esc(p.nearestColony ?? '—')}">
        <td>${esc(p.name)}</td><td>${esc(p.type)}</td>
        <td style="color:${habColor(p.hab)}">${p.hab}</td><td>${SIZES[p.sizeCap - 1]?.slice(0, 4) ?? ''}</td>
        <td>${p.tempK}</td>${RES.map(r => `<td>${y(p.yields[r])}</td>`).join('')}
        <td class="${feeds >= 0 ? 'net-pos' : 'net-neg'}">${feeds >= 0 ? 'yes' : feeds.toFixed(2)}</td>
        <td>${p.distance == null ? '' : Math.round(p.distance)}</td><td>${status}</td></tr>`
    }).join('')
    this.el.querySelectorAll('tbody tr').forEach(tr => tr.addEventListener('click', () =>
      this.onPick(shown[Number(tr.dataset.i)])))
    this.el.querySelector('.pb-count').textContent =
      `${list.length} of ${this.rows.length} known planets` +
      (list.length > MAX_ROWS ? ` (showing the first ${MAX_ROWS}; narrow the filters)` : '')
  }
}
