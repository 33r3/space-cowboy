/**
 * Notifications: a badge with the unread count (polled) and a panel
 * listing the latest, toggled with N. Opening it marks them read.
 */

const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

export class Notifications {
  constructor(panel, list, badge) {
    this.panel = panel
    this.list = list
    this.badge = badge
    this.items = []
    badge.addEventListener('click', () => this.toggle())
    this.refresh()
    setInterval(() => this.refresh(), 30_000)
  }

  async refresh() {
    try {
      this.items = await fetch('/api/notifications').then(r => r.json())
    } catch { return }
    const unread = this.items.filter(n => !n.read).length
    this.badge.textContent = unread ? `✉ ${unread}` : '✉'
    this.badge.classList.toggle('unread', unread > 0)
    if (this.panel.style.display === 'block') this.render()
  }

  render() {
    this.list.innerHTML = this.items.map(n =>
      `<div class="note${n.read ? '' : ' unread'}">` +
      `<span class="note-time">${new Date(n.timestamp).toLocaleString()}</span><br>` +
      `${esc(n.message)}</div>`
    ).join('') || '<div style="color:#445566">Nothing yet.</div>'
  }

  async toggle() {
    const open = this.panel.style.display !== 'block'
    this.panel.style.display = open ? 'block' : 'none'
    if (!open) return
    this.render()
    if (this.items.some(n => !n.read)) {
      await fetch('/api/notifications/read', { method: 'POST' })
      this.refresh()
    }
  }
}
