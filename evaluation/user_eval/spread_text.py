"""Dump the visible text of chosen book spreads, for the answer key. Read-only."""
import urllib.parse
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:5001"
books = {"single": ("/library/" + urllib.parse.quote("Apple (Duo).json"), [1, 4, 8, 18, 19, 20, 21]),
         "combined": ("/brand/sasmung-s27-ultra-half-12f4e012", [1, 3, 4, 8, 9, 13, 14])}
TXT = """() => { const s = [...document.querySelectorAll('[data-cx-spread]')].filter(e => !e.closest('[hidden]') && e.getBoundingClientRect().width > 0 && getComputedStyle(e).visibility !== 'hidden');
  return s.map(e => e.innerText).join('\\n----\\n'); }"""
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1512, "height": 860}, reduced_motion="reduce")
    for name, (path, want) in books.items():
        pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(2500)
        n = 1
        while True:
            if n in want:
                print(f"\n######## {name} spread {n}\n" + pg.evaluate(TXT)[:3500])
            nxt = pg.query_selector("[data-cx-next]:not([disabled])")
            if not nxt or not nxt.is_visible() or n >= max(want): break
            nxt.click(); pg.wait_for_timeout(700); n += 1
    br.close()
