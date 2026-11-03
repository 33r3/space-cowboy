/**
 * Market section of the colony panel: what this colony keeps of each
 * resource, its local price, and whether free traders may sell from or
 * buy into it here. Blank "keep" = automatic (an hour of what it uses,
 * plus the next upgrade if it is saving for one).
 */

const RES_SHORT = {
  food: 'Food', water: 'Water', organicFuels: 'Org.Fuels', chemFeedstocks: 'Chem.Feed',
  minerals: 'Minerals', fusionFuel: 'Fusion', metals: 'Metals', radioactives: 'Radioact.',
}
const fmt = v => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1))

async function patch(planetId, body) {
  const r = await fetch('/api/market', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ planetId, ...body }),
  })
  if (!r.ok) throw new Error((await r.json()).error ?? 'failed')
  return r.json()
}

export async function renderMarket(el, planetId) {
  let info
  try {
    const r = await fetch(`/api/market?planetId=${encodeURIComponent(planetId)}`)
    if (!r.ok) { el.innerHTML = ''; return }
    info = await r.json()
  } catch { el.innerHTML = ''; return }
  draw(el, planetId, info)
}

function draw(el, planetId, info) {
  const rows = info.resources.map(x => {
    const ratio = x.price / x.basePrice
    const cls = ratio > 1.05 ? 'net-neg' : ratio < 0.95 ? 'net-pos' : 'net-zero'
    const state = x.shortfall >= 0.5 ? `<span class="net-neg" title="short: wants ${fmt(x.shortfall)} more">−${fmt(x.shortfall)}</span>`
                : x.surplus >= 0.5   ? `<span class="net-pos" title="spare: ${fmt(x.surplus)} for traders">+${fmt(x.surplus)}</span>`
                : '<span class="net-zero">·</span>'
    const inc = Math.abs(x.incoming) > 0.05
      ? ` <span class="mk-incoming">${x.incoming > 0 ? '+' : ''}${fmt(x.incoming)}</span>` : ''
    return `<tr data-res="${x.resource}">
      <td>${RES_SHORT[x.resource] ?? x.resource}</td>
      <td>${fmt(x.stock)}${inc}</td>
      <td><input class="mk-keep" type="number" min="0" step="any"
                 placeholder="${x.autoTarget >= 10 ? x.autoTarget.toFixed(0) : x.autoTarget.toFixed(1)}" value="${x.keep ?? ''}"
                 title="Keep this much here (blank = automatic: ${fmt(x.autoTarget)})"></td>
      <td class="${cls}" title="base ${x.basePrice}">${x.price.toFixed(2)}</td>
      <td>${state}</td>
      <td><input class="mk-export" type="checkbox" ${x.export ? 'checked' : ''} title="Traders may take surplus from here"></td>
      <td><input class="mk-import" type="checkbox" ${x.import ? 'checked' : ''} title="Traders may bring shortfalls here"></td>
    </tr>`
  }).join('')

  el.innerHTML = `
    <hr class="cp-divider">
    <div class="cp-section-label">Market</div>
    <table class="cp-flows-table mk-table">
      <thead><tr><th></th><th>have</th><th>keep</th><th>price</th>
        <th title="spare (+) or short (−)">±</th>
        <th title="traders may take spare goods away">out</th>
        <th title="traders may bring what's short">in</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <label class="mk-upgrade"><input id="mk-save" type="checkbox" ${info.saveForUpgrade ? 'checked' : ''}>
      Save for the next upgrade</label>
    <div class="tf-hint">Free traders (Trade panel, T) carry spare goods to colonies that are
      short. Keep defaults to ${info.reserveTicks} ticks of use; blank it to go back to automatic.</div>
    <div id="mk-error" style="color:#cc4444"></div>`

  const err = el.querySelector('#mk-error')
  const send = async body => {
    err.textContent = ''
    try { draw(el, planetId, await patch(planetId, body)) }
    catch (e) { err.textContent = e.message }
  }
  el.querySelectorAll('tr[data-res]').forEach(tr => {
    const res = tr.dataset.res
    const keep = tr.querySelector('.mk-keep')
    const commit = () => {
      const v = keep.value.trim()
      send({ resources: { [res]: { keep: v === '' ? null : parseFloat(v) } } })
    }
    keep.addEventListener('change', commit)
    keep.addEventListener('keydown', e => { if (e.key === 'Enter') keep.blur() })
    tr.querySelector('.mk-export').addEventListener('change', e =>
      send({ resources: { [res]: { export: e.target.checked } } }))
    tr.querySelector('.mk-import').addEventListener('change', e =>
      send({ resources: { [res]: { import: e.target.checked } } }))
  })
  el.querySelector('#mk-save').addEventListener('change', e =>
    send({ saveForUpgrade: e.target.checked }))
}
