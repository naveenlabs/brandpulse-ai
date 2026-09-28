"""Screenshots for the final user evaluation (24 Sep 2026). Read-only against the app on 5001.

Every video still served from /static/frames/ is blurred on the way into the browser
(Playwright route + PIL), because downloaded video is never redistributed
(README, "Engineering rules"). Everything else is the interface exactly as built. Shots are taken
at 1512x860, devicePixelRatio 2, with reduced motion so every chart is drawn complete.
"""
import io, os, sys, urllib.parse
from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5001"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots_raw")
q = urllib.parse.quote


def blur_frames(route):
    resp = route.fetch()
    try:
        img = Image.open(io.BytesIO(resp.body())).convert("RGB")
        img = img.filter(ImageFilter.GaussianBlur(radius=max(6, img.width // 60)))
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
        route.fulfill(status=200, body=buf.getvalue(), headers={"content-type": "image/jpeg"})
    except Exception:
        route.fulfill(response=resp)


def walk(pg, prefix, theme):
    n = 1
    pg.screenshot(path=f"{OUT}/{prefix}_{theme}_s{n:02d}.png")
    while True:
        nxt = pg.query_selector("[data-cx-next]:not([disabled])")
        if not nxt or not nxt.is_visible():
            break
        nxt.click(); pg.wait_for_timeout(900); n += 1
        pg.screenshot(path=f"{OUT}/{prefix}_{theme}_s{n:02d}.png")


with sync_playwright() as pw:
    br = pw.chromium.launch()
    for theme in (sys.argv[1:] or ["bench", "field"]):
        ctx = br.new_context(viewport={"width": 1512, "height": 860}, device_scale_factor=2,
                             reduced_motion="reduce")
        ctx.add_init_script(f"try{{localStorage.setItem('brandpulse-theme','{theme}')}}catch(e){{}}")
        ctx.route("**/static/frames/**", blur_frames)
        pg = ctx.new_page()
        pg.goto(BASE + "/", wait_until="networkidle"); pg.wait_for_timeout(2000)
        pg.screenshot(path=f"{OUT}/gate_{theme}.png")
        pg.keyboard.press("Space"); pg.wait_for_timeout(9000)
        pg.screenshot(path=f"{OUT}/opening_{theme}_01.png")
        total = pg.evaluate("() => document.documentElement.scrollHeight")
        y, i = 0, 1
        while y + 860 < total and i < 16:
            y += 860; i += 1
            pg.evaluate(f"() => window.scrollTo(0, {y})"); pg.wait_for_timeout(900)
            pg.screenshot(path=f"{OUT}/opening_{theme}_{i:02d}.png")
        pg.goto(BASE + "/run", wait_until="networkidle"); pg.wait_for_timeout(2500)
        pg.screenshot(path=f"{OUT}/analyse_{theme}_video.png")
        for label in ("A product", "A brand"):
            tab = pg.get_by_text(label, exact=True)
            if tab.count():
                tab.first.click(); pg.wait_for_timeout(900)
                pg.screenshot(path=f"{OUT}/analyse_{theme}_{label.split()[1]}.png")
        pg.goto(BASE + "/library", wait_until="networkidle"); pg.wait_for_timeout(3500)
        pg.screenshot(path=f"{OUT}/library_{theme}_top.png")
        pg.evaluate("() => window.scrollTo(0, 860)"); pg.wait_for_timeout(1200)
        pg.screenshot(path=f"{OUT}/library_{theme}_rack.png")
        pg.goto(BASE + "/library/" + q("Apple (Duo).json"), wait_until="networkidle"); pg.wait_for_timeout(3000)
        walk(pg, "single_duo", theme)
        pg.goto(BASE + "/brand/sasmung-s27-ultra-half-12f4e012", wait_until="networkidle"); pg.wait_for_timeout(3000)
        walk(pg, "combined_s27", theme)
        ctx.close()
    br.close()
print(len(os.listdir(OUT)), "shots")
