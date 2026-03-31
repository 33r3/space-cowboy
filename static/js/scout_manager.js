export class ScoutManager {
  _scouts = []

  async init() {
    await this.refresh()
  }

  async refresh() {
    const data = await fetch('/api/scouts').then(r => r.json())
    this._scouts = data
  }

  async launchScout(sourcePlanetId, starId, destWorldX, destWorldY) {
    const parts      = starId.split(':')
    const chunkParts = parts[0].split(',')
    const cx         = parseInt(chunkParts[0])
    const cy         = parseInt(chunkParts[1])
    const index      = parseInt(parts[1])

    const res = await fetch('/api/scouts', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        sourcePlanetId,
        destStarCx:    cx,
        destStarCy:    cy,
        destStarIndex: index,
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error ?? 'Scout launch failed')
    this._scouts.push(data)
    return data
  }

  get scouts() { return this._scouts }
  get arrivedScouts() { return this._scouts.filter(s => s.status === 'arrived') }
}
