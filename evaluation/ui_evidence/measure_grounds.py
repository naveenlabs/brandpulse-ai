"""
measure_grounds.py — does a lit background still clear the contrast floor?

Why this exists
---------------
Two sections gained an animated ground on 22 Sep 2026: the Data Pixel Arc
behind #film and the Predictive Arc behind the limits rail.
Later the same day #proof became one pinned screen, which stood its reading
column still in front of the Portal Field instead of scrolling it past, so that
column's type is measured here too.
Both put light under type that was previously sitting on flat --screen, and
the result has to be honest about legibility rather than merely pretty. `brightness`, `opacity` and the CSS masks on those two grounds
were set by this script, not by eye.

What it measures
----------------
For every text element listed in TARGETS, in both themes:

  1. read the element's own computed colour and font size;
  2. hide the text and screenshot, so what is captured is the ground the
     glyphs actually sit on, fully composited -- canvas, mask, section tint,
     grain plate and all;
  3. difference that against a shot with the text showing, to find the pixels
     the glyphs actually cover, and compute the WCAG 2.1 contrast ratio
     against the text colour at those pixels only -- keeping the WORST one.

The worst pixel is the number reported. A mean would hide exactly the failure
this is looking for: a small bright cluster under one word. The glyph mask
matters as much: these elements' boxes are much wider than their text, and
measuring the whole box reports the ground under empty space as though
something had to be read on it.

The floor is 4.5:1, or 3:1 where WCAG's large-text rule applies (>= 24px, or
>= 18.66px bold). Both are checked against the element's real computed size
rather than an assumed one.

What it does NOT measure
------------------------
The grounds animate. This samples one frame per target, at whatever phase the
loop happens to be in when the shot is taken, so a peak that lasts two frames
can be missed. The animation is slow (speed 0.55 and 0.6) and the arcs move by
translation rather than by pulsing in brightness, so the frame-to-frame
variation is small, but this is a sample and not a bound and must not be
written up as one.

Run it (Ollama not needed; nothing here touches the pipeline):
    python -m flask --app app run --port 5057 &
    python evaluation/ui_evidence/measure_grounds.py

Writes ui_evidence/ground_contrast.json and prints a table. Exit code is 1 if
any target is below its floor, so it can be used as a gate.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "ground_contrast.json"
BASE = "http://127.0.0.1:5057"
VIEWPORT = {"width": 1440, "height": 900}

# (section, selector, the scroll fraction that puts it on screen, a label)
# The chamber shows one .f-beat at a time and hides the rest at opacity 0,
# so every beat-local target is scoped to the CURRENT one. Measuring
# ".f-eyebrow" unscoped measures beat 1's copy while beat 2 is on screen,
# which is how the first run of this script produced four false failures.
TARGETS = [
    ("film", ".f-beat.is-current .f-eyebrow", 0.26, "eyebrow, 10px"),
    ("film", ".f-beat.is-current .f-body", 0.26, "body copy"),
    ("film", ".f-beat.is-current .f-invitation", 0.26, "invitation, 11px"),
    ("film", ".f-bottom", 0.26, "transport rule, 10px"),
    ("film", ".f-beat.is-current .f-aside", 0.33, "aside, 11px"),
    ("film", ".f-coordinate--b", 0.33, "coordinate, 8px"),
    # 22 Sep 2026: #proof became one pinned screen and the rail became its
    # third movement, so a fraction of the DOCUMENT no longer finds the rail --
    # it moves whenever anything above it changes length, and all six of these
    # came back "not on screen" the first time this was run afterwards. These
    # fractions are now read against the proof pin itself; see scroll_to().
    #
    # The rail shows one .la-reading at a time and hides the rest at opacity 0,
    # so an unscoped .la-claim is panel 01's whether or not panel 01 is up --
    # the same trap the film targets carry .is-current for. Tying the fraction
    # to whichever panel happens to be current was tried and broke the moment
    # the storyboard's beats were retuned, so `{cur}` is resolved AFTER the
    # scroll, from the numeral the rail itself is showing. Whatever panel this
    # fraction lands on, the selector follows it.
    ("limits", ".la-header h3", 0.62, "rail heading"),
    ("limits", ".la-art__note", 0.62, "art note, 8px"),
    ("limits", "{cur} .la-claim", 0.62, "claim, 15px"),
    ("limits", "{cur} .la-body", 0.62, "body, 12px"),
    ("limits", "{cur} .la-location", 0.62, "location, 9px"),
    ("limits", ".la-footer", 0.62, "footer, 9px"),

    # The reading column. It used to scroll past the Portal Field's arc as an
    # ordinary document; locked, it stands still in front of it for two whole
    # movements, so every line of it is now type on a lit ground and belongs in
    # this gate. 0.06 is the ledger, 0.30 the bench.
    ("proof", ".proof__h", 0.06, "section heading"),
    ("proof", ".proof__lede", 0.06, "lede"),
    ("proof", ".ledger__label", 0.06, "ledger label, 13px"),
    ("proof", ".ledger__note", 0.06, "ledger note, 11px"),
    ("proof", ".bench__tab", 0.30, "resting tab"),
    ("proof", ".chart__axis", 0.30, "axis label, 11px"),
    ("proof", ".bar__name", 0.30, "bar name"),
    ("proof", ".bar__note", 0.30, "bar note, 11px"),
]

# Both of these are movements of one pinned section, so both are anchored to
# that pin rather than to the document.
PINNED = {"limits", "proof"}

SCROLL_TO = """({ section, frac, pinned }) => {
  if (pinned) {
    const proof = document.querySelector('#proof');
    const spacer = proof.closest('.pin-spacer') || proof;
    const box = spacer.getBoundingClientRect();
    const top = box.top + scrollY;
    /* The spacer is the screen plus the scroll; the scroll is what a fraction
       through the storyboard means. */
    const span = Math.max(0, box.height - innerHeight);
    window.scrollTo(0, Math.round(top + span * frac));
    return;
  }
  window.scrollTo(0, Math.round(document.body.scrollHeight * frac));
}"""

THEMES = ("bench", "field")

# Run with --baseline to hide both grounds and measure the same targets on the
# flat sections they replaced. That is the only way to attribute a reading to
# this change rather than to something that was already there, and both
# numbers are reported side by side.
HIDE_GROUNDS = "#film .f-field, #proof .la-field { display: none !important; }"


def srgb_to_lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(r: float, g: float, b: float) -> float:
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def contrast(a: tuple, b: tuple) -> float:
    la, lb = luminance(*a[:3]), luminance(*b[:3])
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_rgb(value: str) -> tuple[int, int, int]:
    nums = [float(n) for n in re.findall(r"[\d.]+", value)]
    return (int(nums[0]), int(nums[1]), int(nums[2]))


def floor_for(size_px: float, weight: str) -> float:
    """WCAG 2.1 1.4.3: large text is >=24px, or >=18.66px when bold."""
    bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 700)
    large = size_px >= 24 or (bold and size_px >= 18.66)
    return 3.0 if large else 4.5


def main() -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    baseline = "--baseline" in sys.argv
    rows = []

    with sync_playwright() as play:
        browser = play.chromium.launch(args=["--enable-unsafe-swiftshader"])
        for theme in THEMES:
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            page.goto(BASE + "/", wait_until="networkidle")
            # The CRT boot gate covers the viewport on every visit; Escape is
            # one of its three documented ways out (lib/gate.js).
            for _ in range(12):
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                if page.evaluate("!document.querySelector('.gate,[data-gate]') "
                                 "|| document.querySelector('.gate,[data-gate]')"
                                 ".getBoundingClientRect().height === 0"):
                    break
            if baseline:
                page.add_style_tag(content=HIDE_GROUNDS)
            page.evaluate(
                "t => { document.documentElement.dataset.theme = t;"
                "       window.dispatchEvent(new Event('themechange')); }", theme)
            page.wait_for_timeout(1500)

            for section, selector, frac, label in TARGETS:
                page.evaluate(SCROLL_TO, {"section": section, "frac": frac,
                                          "pinned": section in PINNED})
                page.wait_for_timeout(1800)

                # Resolve {cur} against the panel the rail is actually showing.
                if "{cur}" in selector:
                    shown = page.evaluate(
                        "() => document.querySelector('.la-index')?.textContent")
                    try:
                        which = int(str(shown).strip()) - 1
                    except (TypeError, ValueError):
                        which = 0
                    selector = selector.replace(
                        "{cur}", f'.la-reading[data-reading="{which}"]')

                info = page.evaluate(
                    """sel => {
                        const el = document.querySelector(sel);
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        if (r.width < 2 || r.height < 2) return null;
                        if (r.bottom <= 0 || r.top >= innerHeight) return null;
                        /* Anything the reader cannot see cannot have a
                           contrast problem, and measuring it invents one. */
                        if (el.checkVisibility && !el.checkVisibility(
                              { opacityProperty: true, visibilityProperty: true,
                                contentVisibilityAuto: true })) return null;
                        const cs = getComputedStyle(el);
                        return { x: r.x, y: r.y, w: r.width, h: r.height,
                                 color: cs.color, size: parseFloat(cs.fontSize),
                                 weight: cs.fontWeight };
                    }""", selector)
                if not info:
                    rows.append({"theme": theme, "section": section,
                                 "selector": selector, "label": label,
                                 "status": "not on screen"})
                    continue

                # Two shots of the same viewport: one as the reader sees
                # it, one with this element's glyphs hidden and everything
                # behind them untouched. The pixels that DIFFER between them
                # are where the glyphs are; the ground is then read from the
                # hidden shot at exactly those pixels and nowhere else.
                #
                # This is the whole reason the first version of this script
                # reported nine failures that the grounds had not caused. It
                # measured the element's BOX, and these boxes are far wider
                # than their text -- .f-invitation's is 734px wide carrying
                # about 250px of words -- so the empty remainder was sitting
                # over the orbit canvas and reporting its rings as though a
                # glyph were on them.
                lit = page.screenshot()
                page.evaluate("sel => { const e = document.querySelector(sel);"
                              " e.dataset.bpWas = e.style.visibility;"
                              " e.style.visibility = 'hidden'; }", selector)
                page.wait_for_timeout(120)
                bare = page.screenshot()
                page.evaluate("sel => { const e = document.querySelector(sel);"
                              " e.style.visibility = e.dataset.bpWas || ''; }", selector)

                left = max(0, int(info["x"]))
                top = max(0, int(info["y"]))
                right = min(VIEWPORT["width"], int(info["x"] + info["w"]))
                bottom = min(VIEWPORT["height"], int(info["y"] + info["h"]))
                if right - left < 2 or bottom - top < 2:
                    rows.append({"theme": theme, "section": section,
                                 "selector": selector, "label": label,
                                 "status": "clipped out of view"})
                    continue

                box = (left, top, right, bottom)
                a = Image.open(io.BytesIO(lit)).convert("RGB").crop(box)
                b = Image.open(io.BytesIO(bare)).convert("RGB").crop(box)
                ink = parse_rgb(info["color"])

                # A pixel counts as glyph if hiding the text changed it at
                # all beyond capture noise. The grounds animate between the
                # two shots, so the threshold is well above zero; 18/255 is
                # comfortably under the difference a glyph makes and
                # comfortably over one frame of a ground moving at speed 0.6.
                ax, bx = a.load(), b.load()
                worst = None
                worst_px = None
                glyphs = 0
                for yy in range(a.height):
                    for xx in range(a.width):
                        pa, pb = ax[xx, yy], bx[xx, yy]
                        if (abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])
                                + abs(pa[2] - pb[2])) < 18:
                            continue
                        glyphs += 1
                        c = contrast(ink, pb)
                        if worst is None or c < worst:
                            worst, worst_px = c, pb

                if not glyphs or worst is None:
                    rows.append({"theme": theme, "section": section,
                                 "selector": selector, "label": label,
                                 "status": "no glyph pixels found"})
                    continue

                need = floor_for(info["size"], str(info["weight"]))
                rows.append({
                    "theme": theme, "section": section, "selector": selector,
                    "label": label, "font_px": round(info["size"], 1),
                    "weight": info["weight"], "ink": list(ink),
                    "worst_ground": list(worst_px), "worst_contrast": round(worst, 2),
                    "floor": need, "pass": worst >= need,
                    "glyph_pixels": glyphs,
                    "status": "measured",
                })
            page.close()
        browser.close()

    out = OUT.with_name("ground_contrast_baseline.json") if baseline else OUT
    out.write_text(json.dumps(
        {"viewport": VIEWPORT, "grounds": "hidden" if baseline else "mounted",
         "rows": rows}, indent=2))

    print(f"\n{'theme':6} {'section':7} {'target':22} {'px':>5} {'worst':>7} "
          f"{'floor':>6}  result")
    print("-" * 72)
    failures = 0
    for r in rows:
        if r["status"] != "measured":
            print(f"{r['theme']:6} {r['section']:7} {r['label']:22} {'':>5} "
                  f"{'':>7} {'':>6}  {r['status']}")
            continue
        ok = "pass" if r["pass"] else "FAIL"
        if not r["pass"]:
            failures += 1
        print(f"{r['theme']:6} {r['section']:7} {r['label']:22} "
              f"{r['font_px']:>5} {r['worst_contrast']:>7} {r['floor']:>6}  {ok}")
    print(f"\n{len(rows)} targets, {failures} below floor "
          f"({'grounds hidden' if baseline else 'grounds mounted'}) -> {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
