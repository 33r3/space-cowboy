/**
 * Terraforming section of the planet panel: the planet's current climate,
 * every live project on it (yours can be stopped), and a form to start one.
 */

const RES_SHORT = {
  food: 'Food', water: 'Water', organicFuels: 'Org.Fuels', chemFeedstocks: 'Chem.Feed',
  minerals: 'Minerals', fusionFuel: 'Fusion', metals: 'Metals', radioactives: 'Radioact.',
}
const LEVER_WORDS = {
  temperature: { up: 'warming', down: 'cooling' },
  pressure:    { up: 'thickening the air', down: 'thinning the air' },
}

const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const signed = (v, digits) => (v > 0 ? '+' : '') + v.toFixed(digits)
const costText = cost => Object.entries(cost).map(([k, v]) => `${v} ${RES_SHORT[k] ?? k}`).join(' · ')

export async function renderTerraform(el, planetId, onChange = () => {}) {
  el.innerHTML = ''
  let info
  try {
    const r = await fetch(`/api/terraform?planetId=${encodeURIComponent(planetId)}`)
    if (!r.ok) return
    info = await r.json()
  } catch { return }

  const hab = info.habitability
  const projects = info.projects.map(p => {
    const unit = info.levers[p.lever]?.unit ?? ''
    const who = p.mine ? `you (${esc(p.sourceName ?? '')})` : esc(p.owner)
    const status = p.status === 'stalled' ? ' <span style="color:#cc4444">stalled: unpaid</span>' : ''
    const stop = p.mine ? ` <button class="tf-stop" data-id="${p.id}">stop</button>` : ''
    return `<div class="tf-project">${esc(p.lever)} → ${signed(p.target, 1)} ${unit} · ${who}${status}${stop}</div>`
  }).join('') || '<div style="color:#445566">No projects running.</div>'

  el.innerHTML = `
    <hr class="cp-divider">
    <div class="cp-section-label">Terraforming</div>
    <div class="tf-climate">
      ${info.surfaceTempK.toFixed(0)} K <span class="tf-delta">(${signed(info.temperatureDeltaK, 1)})</span> ·
      ${info.pressureAtm.toFixed(2)} atm <span class="tf-delta">(${signed(info.pressureDeltaAtm, 2)})</span><br>
      Habitability ${hab.total}/100 (${esc(hab.category)}) · colonies here max ${info.sizeCap}/5
    </div>
    ${projects}
    <div id="tf-form"></div>`

  el.querySelectorAll('.tf-stop').forEach(btn => btn.addEventListener('click', async () => {
    btn.disabled = true
    await fetch(`/api/terraform/${btn.dataset.id}`, { method: 'DELETE' })
    onChange()
    renderTerraform(el, planetId, onChange)
  }))

  const form = el.querySelector('#tf-form')
  if (!info.sources.length) {
    form.innerHTML = '<div style="color:#445566;margin-top:4px">To terraform: an Advanced colony on this ' +
      'planet, or a Transcendent one within 300 Ly.</div>'
    return
  }
  form.innerHTML = `
    <div class="tf-row">
      <select id="tf-lever">
        <option value="temperature">Temperature (K)</option>
        <option value="pressure">Pressure (atm)</option>
      </select>
      <input id="tf-target" type="number" step="any" placeholder="target, e.g. -20">
    </div>
    <div class="tf-row"><select id="tf-source">${info.sources.map(s =>
      `<option value="${esc(s.planetId)}">${esc(s.name)} (${esc(s.devName)})${s.distance ? ` ${s.distance} Ly` : ''}</option>`
    ).join('')}</select></div>
    <div id="tf-hint" class="tf-hint"></div>
    <button id="tf-start">Start project</button>
    <div id="tf-error" style="color:#cc4444"></div>`

  const lever = form.querySelector('#tf-lever')
  const target = form.querySelector('#tf-target')
  const source = form.querySelector('#tf-source')
  const hint = form.querySelector('#tf-hint')
  function updateHint() {
    const L = info.levers[lever.value]
    const src = info.sources.find(s => s.planetId === source.value)
    const t = parseFloat(target.value)
    const current = lever.value === 'temperature' ? info.temperatureDeltaK : info.pressureDeltaAtm
    const up = !(t < current)
    const perDay = src?.perDay[lever.value] ?? 0
    const days = Number.isFinite(t) && perDay ? Math.abs(t - current) / perDay : null
    hint.innerHTML =
      `Target is an offset from the natural planet (±${L.max} ${L.unit}).<br>` +
      `${LEVER_WORDS[lever.value][up ? 'up' : 'down']}: ${perDay} ${L.unit}/day` +
      (days !== null ? `, ~${days < 1 ? (days * 24).toFixed(1) + ' h' : days.toFixed(1) + ' days'}` : '') +
      `<br>Costs ${costText(up ? L.costUp : L.costDown)} per tick`
  }
  ;[lever, target, source].forEach(x => x.addEventListener('input', updateHint))
  updateHint()

  form.querySelector('#tf-start').addEventListener('click', async () => {
    const err = form.querySelector('#tf-error')
    err.textContent = ''
    const r = await fetch('/api/terraform', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ planetId, lever: lever.value, target: parseFloat(target.value),
                             sourcePlanetId: source.value }),
    })
    if (!r.ok) { err.textContent = (await r.json()).error ?? 'failed'; return }
    onChange()
    renderTerraform(el, planetId, onChange)
  })
}
