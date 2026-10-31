"""Browser smoke test of the planet panel's terraforming section.

    uvicorn --factory server.app:create_app --port 8765   (on a scratch DB)
    python tools/ui_smoke.py OUT_DIR [URL]

Opens the homeworld from the colony list, starts a cooling project,
stops it, opens notifications; prints what it saw and any JS errors,
and saves ui1.png / ui2.png in OUT_DIR. Needs `playwright install chromium`.
"""
import sys
from playwright.sync_api import sync_playwright
out = sys.argv[1]
url = sys.argv[2] if len(sys.argv) > 2 else 'http://127.0.0.1:8765/'
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1400, 'height': 900})
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2500)
    pg.keyboard.press('l')
    pg.wait_for_timeout(500)
    pg.click('.cl-zoom-btn')
    pg.keyboard.press('l')
    pg.wait_for_timeout(800)
    pg.mouse.move(700, 450); pg.wait_for_timeout(300)
    pg.mouse.click(700, 450)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{out}/ui1.png')
    print('panel title:', pg.inner_text('#colony-panel-title'))
    print('hab line:', pg.inner_text('#cp-hab-line'))
    print('terraform:', pg.inner_text('#colony-panel-terraform')[:400])
    pg.select_option('#tf-lever', 'temperature')
    pg.fill('#tf-target', '-20')
    pg.wait_for_timeout(200)
    print('hint:', pg.inner_text('#tf-hint'))
    pg.click('#tf-start')
    pg.wait_for_timeout(1500)
    print('after start:', pg.inner_text('#colony-panel-terraform')[:300])
    pg.screenshot(path=f'{out}/ui2.png')
    pg.click('.tf-stop')
    pg.wait_for_timeout(1000)
    print('after stop:', pg.inner_text('#colony-panel-terraform')[:200])
    pg.keyboard.press('n'); pg.wait_for_timeout(800)
    print('notes:', pg.inner_text('#notes-panel'))
    print('errors:', errors)
    b.close()
