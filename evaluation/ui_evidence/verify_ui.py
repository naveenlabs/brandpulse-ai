"""
verify_ui.py — the checks that need a real browser.

Rebuilt 25 Sep 2026 for the inclusive-design pass (INCLUSIVE_DESIGN.md §5). The
12 Sep version measured the third interface and had drifted from the one that
replaced it: it read `outputs/*.json` (empty since the author deleted the single
runs on 24 Sep), seeded theme names that no longer exist (`ink`/`plate` where the
pages accept `bench`/`field`, so "both themes" measured one theme twice), never
dismissed the boot screen, and looked for selectors that were gone -- which made
several checks pass while measuring nothing (text spacing counted 0 elements on
every page). Its lessons are kept below, next to the checks they belong to.

pytest covers what can be read off the source and the build. These are the
things that can only be established by loading the pages, in real Chrome on the
real GPU (Playwright channel="chrome" + ANGLE Metal; the bundled Chromium is a
software renderer and misled every shelf measurement before 23 Sep):

   1. REQUESTS AND CONSOLE. Every request goes to the origin serving the page;
      no console errors.
   2. CONTRAST, measured on every text node against its painted ground, both
      themes, every spread of every book.
   3. KEYBOARD. Tab reaches every control, each shows a ring, none is hidden
      behind the sticky masthead (2.4.11), none is focusable while invisible.
   4. FRAME RATE while scrolling the landing's pinned film (non-functional).
   5. TRANSITIONS (a design contract, not an accessibility criterion; recorded,
      never a failure).
   6. REDUCED MOTION. Nothing loops and nothing redraws once the page settles.
   7. EVERY BOOK renders: every combined run and every one of its videos, with
      one h1, the bias caveat, and the statement to the person in the video.
   8. (merged into 1)
   9. NO SCRIPT. Every document reads with JavaScript off.
  10. RUN PAGE VOICE. Live regions, the progress bar's value text and the tab
      title across every stage and ending, against a stubbed backend.
  11. REFLOW. No text off the side and no sideways scroll, over the viewport
      matrix.
  12. LABEL IN NAME (2.5.3), both themes.
  13. SKIP LINK visible when focused from deep in the page.
  14. TEXT SPACING (1.4.12): no text clipped that was not clipped before.
  15. AXE-CORE, WCAG 2.2 A/AA rules, every page, both themes, 1440 and 390.
  16. TARGET SIZE (2.5.8): 24 CSS px, or the spacing exception.
  17. FORCED COLOURS: focus rings survive; marks drawn only as backgrounds are
      counted.
  18. VISION: screenshots under six simulated conditions (evidence for a human
      reader; not a pass/fail).
  19. SMALL TEXT: reader-facing text below 12px, at 390 and 1440.
  20. SHELF AND LIST follow the window: narrowing a loaded shelf must show the
      list, widening must bring the shelf back.
  21. PRINT: a printed book carries all of its text, legibly on white paper.
  22. MOTION SWITCH: the in-page control stops everything the OS setting stops.
  23. ONE PAGE: the linear reading carries every word the book does.
  24. KEYBOARD JOURNEYS: take a volume down, reach Delete, and press it with
      Space; the film's four parts and the boot log are readable by a screen
      reader; the Library carries the bias caveat with scripting on.

Safety: DELETE requests and run starts are intercepted and answered by the
harness, so a check can never remove a report or start a model run.

    python -m flask --app app run --port 5057 &
    python evaluation/ui_evidence/verify_ui.py                 # everything
    python evaluation/ui_evidence/verify_ui.py --only 15,19    # some checks
    python evaluation/ui_evidence/verify_ui.py --label before  # also keep a labelled copy

Writes ui_evidence/ui_measurements.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import statistics
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "ui_measurements.json"
SHOTS = HERE / "shots" / "a11y"
AXE = ROOT / "interface" / "ui" / "node_modules" / "axe-core" / "axe.min.js"
BASE = "http://127.0.0.1:5057"

THEMES = ("bench", "field")
THEME_KEY = "brandpulse-theme"
MOTION_KEY = "brandpulse-motion"

# WCAG 2.2 A and AA. axe-core tags each rule with the version that introduced
# it, so all six tags are needed to get the whole of 2.2 AA.
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"]

# The viewport matrix, INCLUSIVE_DESIGN.md §5.3. 640x400 and 320x200 are 1280x800
# at 200% and 400% zoom: zoom divides the CSS viewport, which is all a page sees.
MATRIX = [(320, 568), (360, 800), (390, 844), (844, 390), (768, 1024), (1024, 768),
          (1280, 800), (1440, 900), (1512, 982), (1920, 1080), (2560, 1440),
          (3440, 1440), (640, 400)]
QUICK_MATRIX = [(320, 568), (390, 844), (844, 390), (1024, 768), (1440, 900)]

VISION = ["protanopia", "deuteranopia", "tritanopia", "achromatopsia",
          "blurredVision", "reducedContrast"]


# --------------------------------------------------------------- the surfaces

def caveat_probe() -> str:
    """A distinctive run of words from BIAS_CAVEAT, read from scorer.py itself so
    the check cannot drift from the constant it guards."""
    src = (ROOT / "pipeline" / "scorer.py").read_text(encoding="utf-8")
    m = re.search(r'BIAS_CAVEAT = \(\s*"([^"]+)"\s*"([^"]+)"', src)
    text = (m.group(1) + m.group(2)) if m else "documented accuracy disparities"
    return "documented accuracy disparities" if "documented accuracy disparities" in text else text[12:60]


def surfaces() -> dict:
    """
    What is on disk, turned into the addresses to measure.

    Built from outputs/ every run rather than named here: the author deletes
    and adds runs, and a harness that names a file measures nothing once that
    file is gone -- which is exactly how the 12 Sep version came to crash.
    """
    sweeps, members = [], []
    for path in sorted((ROOT / "outputs" / "sweeps").glob("*/sweep.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = path.parent.name
        sweeps.append({"id": sid, "kind": data.get("subject_kind"),
                       "status": data.get("status")})
        for m in data.get("members") or []:
            vid = m.get("video_id")
            file = path.parent / "members" / f"{vid}.json"
            if not vid or m.get("analysed") is False or not file.exists():
                continue
            report = json.loads(file.read_text(encoding="utf-8"))
            segs = report.get("all_segments") or []
            members.append({"sweep": sid, "video": vid,
                            "segments": report.get("segment_count") or len(segs),
                            "longest": max((len(s.get("text") or "") for s in segs), default=0)})
    singles = sorted(p.name for p in (ROOT / "outputs").glob("*.json"))

    def pick(kind):
        own = [s for s in sweeps if s["kind"] == kind]
        done = [s for s in own if s["status"] == "done"]
        return (done or own or [None])[0]

    brand, product = pick("brand"), pick("product")
    pages = {"landing": "/", "run": "/run", "library": "/library",
             "statement": "/accessibility"}
    if brand:
        pages["brand-book"] = f"/brand/{brand['id']}"
    if product:
        pages["product-book"] = f"/brand/{product['id']}"
    biggest = max(members, key=lambda m: m["segments"], default=None)
    longest = max(members, key=lambda m: m["longest"], default=None)
    if biggest:
        pages["member-book"] = f"/brand/{biggest['sweep']}/{biggest['video']}"
    if singles:
        pages["single-book"] = "/library/" + urllib.parse.quote(singles[0])
    return {"pages": pages, "sweeps": sweeps, "members": members, "singles": singles,
            "longest": longest and f"/brand/{longest['sweep']}/{longest['video']}"}


BOOKS = ("brand-book", "product-book", "member-book", "single-book")

# What each document shows once it has finished building. The film's link on
# the landing, the rack or the shelf on the library, the bound book, the run
# form. An error or empty state counts as finished: it is a state to measure.
READY = {
    "landing": ".f-link, .state",
    "run": "[data-run] h1, .state",
    "library": "[data-bk], [data-rack] li, [data-rack-empty]:not([hidden]), .state",
    "statement": ".stmt h1",
    "book": "[data-cx-book] [data-cx-spread], .state",
}


def ready_selector(name: str) -> str:
    return READY["book"] if name.endswith("book") else READY.get(name, "main")


# ------------------------------------------------------------ the browser side

INSTRUMENT = r"""
(() => {
  /* Counts every GPU draw and every 2D paint call the page makes, so "is this
     page still animating?" is a number rather than a judgement. Installed before
     any page script runs. */
  const count = { draws: 0, paints2d: 0 };
  window.__bpCount = count;
  const wrap = (proto, names, key) => {
    if (!proto) return;
    for (const n of names) {
      const f = proto[n];
      if (typeof f !== 'function') continue;
      proto[n] = function (...a) { count[key]++; return f.apply(this, a); };
    }
  };
  wrap(window.WebGLRenderingContext && WebGLRenderingContext.prototype,
       ['drawArrays', 'drawElements'], 'draws');
  wrap(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype,
       ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced',
        'drawRangeElements'], 'draws');
  wrap(window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype,
       ['clearRect', 'fillRect', 'putImageData', 'drawImage'], 'paints2d');
})();
"""

# Shared helpers every in-page script below can call.
HELPERS = r"""
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const shown = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (n.hidden || n.inert) return false;
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    }
    return true;
  };
  const opacity = (el) => {
    let o = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) o *= Number(getComputedStyle(n).opacity);
    return o;
  };
  const ariaHidden = (el) => !!el.closest('[aria-hidden="true"]');
  const srOnly = (el) => !!el.closest('.sr-only, .visually-hidden');
  const label = (el) => norm(el.getAttribute('aria-label') || el.textContent).slice(0, 40);
  const sel = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
      + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/)[0] : '');
  const TABBABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), '
      + 'select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
"""

CONTRAST_SCRIPT = r"""
() => {
  const srgb = (c) => { c /= 255; return c <= 0.04045 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = ([r,g,b]) => 0.2126*srgb(r) + 0.7152*srgb(g) + 0.0722*srgb(b);
  /* getComputedStyle hands back color(srgb 0-1 ...) for colours that went
     through color-mix(). Read as 0-255 that turned near-white into near-black
     and reported the report's "Bias caveat" label at 3.13:1 when it is 5.69:1.
     Rescaled only when every channel is <= 1 and one is fractional. */
  const parse = (s) => {
    const v = (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    if (v.length === 3 && v.every((c) => c <= 1) && v.some((c) => !Number.isInteger(c))) return v.map((c) => c * 255);
    return v;
  };
  const alpha = (s) => { const p = (s.match(/[\d.]+/g)||[]); return /^color|rgba/.test(s) && p.length>3 ? Number(p[3]) : 1; };
  /* The painted ground: the nearest ancestor at least 90% opaque. A full
     composite of every translucent layer was tried on 12 Sep and collected
     layers outside the text's own backdrop (1 false failure became 24); at 0.9
     the layer behind contributes at most a tenth, which cannot move a ratio
     across the AA line. */
  const bgOf = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && bg !== 'transparent' && alpha(bg) >= 0.9) return parse(bg);
    }
    return parse(getComputedStyle(document.body).backgroundColor);
  };
  const out = []; const seen = new Set();
  for (const el of document.querySelectorAll('p,span,a,li,h1,h2,h3,h4,b,strong,em,small,dd,dt,button,label,input,td,th,blockquote,figcaption,caption,summary')) {
    const text = (el.textContent || '').trim();
    if (!text || el.children.length > 0) continue;
    const box = el.getBoundingClientRect();
    if (box.width < 4 || box.height < 4) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) < 0.5) continue;
    if (el.closest('[hidden], [aria-hidden="true"], .sr-only')) continue;
    const fg = parse(cs.color), bg = bgOf(el);
    const l1 = lum(fg), l2 = lum(bg);
    const ratio = (Math.max(l1,l2) + 0.05) / (Math.min(l1,l2) + 0.05);
    const size = parseFloat(cs.fontSize), weight = Number(cs.fontWeight) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const key = `${cs.color}|${bg.join(',')}|${Math.round(size)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ sample: text.slice(0,42), color: cs.color, bg: `rgb(${bg.map(Math.round).join(',')})`,
               size, large, ratio: Math.round(ratio*100)/100, passes: ratio >= (large ? 3 : 4.5) });
  }
  return out;
}
"""

FOCUS_READ = r"""() => {""" + HELPERS + r"""
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  const b = el.getBoundingClientRect();
  const vh = window.innerHeight, vw = window.innerWidth;
  const h = Math.max(0, Math.min(b.bottom, vh) - Math.max(b.top, 0));
  const w = Math.max(0, Math.min(b.right, vw) - Math.max(b.left, 0));
  const cs = getComputedStyle(el);
  const ring = !(cs.outlineStyle === 'none' || cs.outlineWidth === '0px')
            || (cs.boxShadow && cs.boxShadow !== 'none');
  /* Obscured (2.4.11): the element under the focused one's centre is something
     that is neither it nor inside it -- the sticky masthead, a fixed strip. */
  let obscured = false;
  if (h > 1 && w > 1) {
    const cx = Math.min(vw - 1, Math.max(0, b.left + b.width / 2));
    const cy = Math.min(vh - 1, Math.max(0, b.top + b.height / 2));
    const top = document.elementFromPoint(cx, cy);
    obscured = !!top && top !== el && !el.contains(top) && !top.contains(el)
      && !!top.closest('.masthead, [data-compare], .cmp, .cx__bar, header');
  }
  return { el: sel(el), label: label(el), top: Math.round(b.top),
           onScreen: h > 1 && w > 1, ring, obscured,
           ringSurvivesForcedColors: !(cs.outlineStyle === 'none' || cs.outlineWidth === '0px'),
           faint: opacity(el) < 0.1 || !shown(el) };
}"""

# Every tabbable control, focused in turn and read while focused: is the thing
# the keyboard is on actually visible? This is the check the 12 Sep keyboard
# pass could not make, because it tested size and never opacity -- and the
# closed mobile menu is exactly a set of links at opacity 0.
FOCUS_INVISIBLE = r"""() => {""" + HELPERS + r"""
  const out = []; let n = 0;
  const before = document.activeElement;
  for (const el of document.querySelectorAll(TABBABLE)) {
    if (!shown(el) || el.closest('[inert]')) continue;
    const r0 = el.getBoundingClientRect();
    if (r0.width === 0 && r0.height === 0 && getComputedStyle(el).position !== 'fixed') continue;
    el.focus({ preventScroll: true });
    if (document.activeElement !== el) continue;
    n++;
    const r = el.getBoundingClientRect();
    if (opacity(el) < 0.1 || r.width < 1 || r.height < 1) out.push({ el: sel(el), label: label(el), opacity: Math.round(opacity(el)*100)/100 });
  }
  if (before && before.focus) before.focus({ preventScroll: true });
  return { tabbable: n, invisible: out };
}"""

REFLOW = r"""() => {""" + HELPERS + r"""
  /* Geometry, not scrollX: `body{overflow-x:hidden}` once made every
     scroll-based test pass by definition. Only text-carrying elements count --
     a photograph cropped by its frame loses nothing. */
  const de = document.documentElement, vw = de.clientWidth;
  const scrollerAbove = (el) => {
    for (let p = el.parentElement; p && p !== de; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll)/.test(cs.overflowX) && p.scrollWidth - p.clientWidth > 1) return p;
    }
    return null;
  };
  const lost = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
    if (ariaHidden(el) || srOnly(el) || el.closest('[hidden]')) continue;
    const text = norm(el.textContent);
    if (!text) continue;
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2 || b.right <= vw + 1) continue;
    if (scrollerAbove(el)) continue;
    lost.push({ el: sel(el), text: text.slice(0, 34), over: Math.round(b.right - vw) });
  }
  de.scrollLeft = 9999; const canScrollX = Math.round(de.scrollLeft); de.scrollLeft = 0;
  return { vw, canScrollX, lost: lost.slice(0, 12), lostCount: lost.length };
}"""

SMALL_TEXT = r"""() => {""" + HELPERS + r"""
  /* Reader-facing text below 11.5 CSS px, the smallest size the type system
     defines (--t-micro, tokens.css; --t-note 12.5px is its floor for running
     notes). Text from 11.5 up to 12.5 is counted separately and recorded, not
     failed: it is the system's own micro label size. Decoration is exempt when
     it is marked aria-hidden, which is also the honest test of "decoration". */
  const out = []; let n = 0, micro = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length && [...el.childNodes].every((c) => c.nodeType !== 3 || !c.nodeValue.trim())) continue;
    const text = norm([...el.childNodes].filter((c) => c.nodeType === 3).map((c) => c.nodeValue).join(' '));
    if (!text || !shown(el) || ariaHidden(el) || srOnly(el)) continue;
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2 || opacity(el) < 0.3) continue;
    n++;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size < 11.5) out.push({ el: sel(el), size: Math.round(size * 10) / 10, text: text.slice(0, 30) });
    else if (size < 12.5) micro++;
  }
  const svg = [];
  for (const t of document.querySelectorAll('svg text')) {
    if (!shown(t) || ariaHidden(t)) continue;
    const r = t.getBoundingClientRect();
    if (r.height > 0 && r.height < 10) svg.push({ text: norm(t.textContent).slice(0, 20), px: Math.round(r.height * 10) / 10 });
  }
  return { measured: n, micro, small: out.slice(0, 20), smallCount: out.length,
           svgSmall: svg.slice(0, 10), svgSmallCount: svg.length };
}"""

TARGET_SIZE = r"""() => {""" + HELPERS + r"""
  /* 2.5.8: a target is at least 24x24 CSS px, or a 24px circle centred on it
     overlaps no other target. Inline links inside a sentence are exempt, as the
     criterion says. */
  const targets = [];
  for (const el of document.querySelectorAll('a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [role="slider"], [role="tab"], label[for]')) {
    if (!shown(el) || opacity(el) < 0.1 || ariaHidden(el)) continue;
    let r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (r.bottom < 0 || r.top > innerHeight * 6) continue;
    /* A control's <label> is part of its target: a click on the label
       activates the control. Measure the two together. */
    for (const l of (el.labels || [])) {
      const lr = l.getBoundingClientRect();
      if (lr.width < 1 || lr.height < 1) continue;
      const left = Math.min(r.left, lr.left), top = Math.min(r.top, lr.top);
      r = new DOMRect(left, top, Math.max(r.right, lr.right) - left, Math.max(r.bottom, lr.bottom) - top);
    }
    const cs = getComputedStyle(el);
    const inline = cs.display === 'inline' && el.parentElement
      && norm(el.parentElement.textContent).length > norm(el.textContent).length + 12;
    targets.push({ el, r, inline });
  }
  const small = [];
  for (const t of targets) {
    if (t.inline || (t.r.width >= 24 && t.r.height >= 24)) continue;
    const cx = t.r.left + t.r.width / 2, cy = t.r.top + t.r.height / 2;
    /* A label and the control it labels are one target, not two that clash. */
    const same = (a, b) => (a.control && a.control === b) || (b.control && b.control === a);
    const clash = targets.some((o) => o !== t && !o.el.contains(t.el) && !t.el.contains(o.el)
      && !same(o.el, t.el) && (() => {
      const nx = Math.max(o.r.left, Math.min(cx, o.r.right)), ny = Math.max(o.r.top, Math.min(cy, o.r.bottom));
      return Math.hypot(nx - cx, ny - cy) < 12;
    })());
    if (clash) small.push({ el: sel(t.el), label: label(t.el), w: Math.round(t.r.width), h: Math.round(t.r.height) });
  }
  return { measured: targets.length, failing: small };
}"""

ANIMATING = r"""() => {""" + HELPERS + r"""
  const loops = document.getAnimations().filter((a) => a.playState === 'running'
    && a.effect && a.effect.getComputedTiming && a.effect.getComputedTiming().iterations === Infinity
    && a.effect.target && shown(a.effect.target));
  return { infinite: loops.length,
           which: [...new Set(loops.map((a) => sel(a.effect.target)))].slice(0, 12),
           draws: window.__bpCount ? window.__bpCount.draws : null,
           paints2d: window.__bpCount ? window.__bpCount.paints2d : null };
}"""


# --------------------------------------------------------------- the harness

class Harness:
    def __init__(self, browser, only: set[int] | None, quick: bool):
        self.browser = browser
        self.only = only
        self.quick = quick
        self.surf = surfaces()
        self.pages = self.surf["pages"]
        self.caveat = caveat_probe()
        self.results: dict = {
            "generated_by": "ui_evidence/verify_ui.py",
            "measured_at": dt.datetime.now().isoformat(timespec="seconds"),
            "base": BASE,
            "renderer": None,
            "surfaces": self.pages,
        }
        self.failures: list[str] = []

    # -- plumbing ------------------------------------------------------------

    def wants(self, n: int) -> bool:
        return not self.only or n in self.only

    def fail(self, check: str, message: str) -> None:
        self.failures.append(f"[{check}] {message}")

    def context(self, *, width=1440, height=900, theme="bench", reduced=False,
                motion_off=False, js=True, blur=False, forced=False, **extra):
        ctx = self.browser.new_context(
            viewport={"width": width, "height": height},
            reduced_motion="reduce" if reduced else "no-preference",
            forced_colors="active" if forced else "none",
            java_script_enabled=js, **extra)
        seed = f"try{{localStorage.setItem('{THEME_KEY}','{theme}');"
        seed += (f"localStorage.setItem('{MOTION_KEY}','off');" if motion_off
                 else f"localStorage.removeItem('{MOTION_KEY}');")
        seed += "}catch(e){}"
        ctx.add_init_script(seed)
        ctx.add_init_script(INSTRUMENT)
        ctx.route(re.compile(r".*/(reports|sweeps)/.*"), self._guard)
        ctx.route(re.compile(r".*/(analyse|sweep)/start.*"), self._no_runs)
        if blur:
            ctx.route("**/static/frames/**", _blur_frames)
        return ctx

    @staticmethod
    def _guard(route):
        """Nothing this harness does can delete a report."""
        if route.request.method == "DELETE":
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"deleted": "verify-ui-intercepted"}))
        else:
            route.continue_()

    @staticmethod
    def _no_runs(route):
        """Nor start a model run."""
        route.fulfill(status=503, content_type="application/json",
                      body=json.dumps({"error": "verify_ui: runs are not started by the harness"}))

    def open(self, ctx, name: str, *, path: str | None = None, settle=900, intro=True):
        """Load a surface, get past the gate and the boot screen, wait until built."""
        page = ctx.new_page()
        page.goto(BASE + (path or self.pages[name]), wait_until="domcontentloaded")
        if intro:
            pass_intro(page)
        try:
            page.wait_for_selector(ready_selector(name), state="attached", timeout=20000)
        except Exception:
            self.fail("load", f"{name} never finished building ({path or self.pages[name]})")
        page.wait_for_timeout(settle)
        return page

    def book_spreads(self, page, fn, cap=80) -> int:
        """Call fn(page, i) on every spread of a book, turning with its own Next."""
        i = 0
        fn(page, i)
        while i < cap:
            nxt = page.query_selector("[data-cx-next]:not([disabled])")
            if not nxt or not nxt.is_visible():
                break
            nxt.click()
            page.wait_for_timeout(260)
            i += 1
            fn(page, i)
        return i + 1

    # -- the checks ------------------------------------------------------------

    def c1_requests_console(self):
        out = {}
        ctx = self.context()
        for name in self.pages:
            page = ctx.new_page()
            console: list[str] = []
            foreign: list[str] = []
            page.on("console", lambda m, c=console: c.append(f"{m.type}: {m.text}")
                    if m.type == "error" else None)
            page.on("pageerror", lambda e, c=console: c.append(f"pageerror: {e}"))
            page.on("request", lambda r, f=foreign: f.append(r.url) if not (
                r.url.startswith(BASE) or r.url.startswith(("data:", "blob:"))) else None)
            page.goto(BASE + self.pages[name], wait_until="domcontentloaded")
            pass_intro(page)
            try:
                page.wait_for_selector(ready_selector(name), state="attached", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1200)
            if not self.results["renderer"]:
                self.results["renderer"] = page.evaluate("""() => { try {
                  const g = document.createElement('canvas').getContext('webgl');
                  const d = g.getExtension('WEBGL_debug_renderer_info');
                  return g.getParameter(d.UNMASKED_RENDERER_WEBGL); } catch (e) { return 'none'; } }""")
            out[name] = {"foreign_requests": foreign, "console_errors": console}
            if foreign:
                self.fail("1 requests", f"{name} requested {foreign[:3]}")
            if console:
                self.fail("1 console", f"{name}: {console[:2]}")
            page.close()
        ctx.close()
        self.results["requests_console"] = out
        print(f"  1  requests/console: {sum(len(v['foreign_requests']) for v in out.values())} "
              f"foreign, {sum(len(v['console_errors']) for v in out.values())} errors "
              f"over {len(out)} pages")

    def c2_contrast(self):
        out: dict = {}
        worst: list = []
        for theme in THEMES:
            ctx = self.context(theme=theme, reduced=True)
            for name in self.pages:
                page = self.open(ctx, name)
                samples: list = []
                if name in BOOKS:
                    spreads = self.book_spreads(page, lambda p, i: samples.extend(p.evaluate(CONTRAST_SCRIPT)))
                else:
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(500)
                    samples.extend(page.evaluate(CONTRAST_SCRIPT))
                    spreads = None
                uniq = {(s["color"], s["bg"], round(s["size"])): s for s in samples}.values()
                bad = [s for s in uniq if not s["passes"]]
                out.setdefault(theme, {})[name] = {
                    "pairs": len(uniq), "failing": len(bad), "spreads": spreads,
                    "min_ratio": min((s["ratio"] for s in uniq), default=None),
                    "worst": sorted(bad, key=lambda s: s["ratio"])[:5]}
                if not uniq:
                    self.fail("2 contrast", f"{theme}/{name}: measured nothing")
                for s in bad:
                    worst.append((theme, name, s))
                page.close()
            ctx.close()
        for theme, name, s in sorted(worst, key=lambda t: t[2]["ratio"])[:25]:
            self.fail("2 contrast", f"{theme}/{name}: {s['ratio']}:1 at {s['size']:.1f}px "
                      f"{s['color']} on {s['bg']} {s['sample']!r}")
        self.results["contrast"] = out
        for theme in THEMES:
            pairs = sum(v["pairs"] for v in out[theme].values())
            bad = sum(v["failing"] for v in out[theme].values())
            low = min((v["min_ratio"] for v in out[theme].values() if v["min_ratio"]), default=None)
            print(f"  2  contrast {theme}: {pairs} pairs, {bad} below AA, lowest {low}")

    def c3_keyboard(self):
        out: dict = {}
        for width, height in ((1440, 900), (390, 844)):
            ctx = self.context(width=width, height=height, reduced=True)
            for name in self.pages:
                page = self.open(ctx, name)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(300)
                stops, no_ring, off, obscured, faint = 0, [], [], [], []
                for _ in range(45):
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(60)
                    state = page.evaluate(FOCUS_READ)
                    if not state:
                        continue
                    stops += 1
                    if not state["ring"]:
                        no_ring.append(state)
                    if state["faint"]:
                        faint.append(state)
                    elif not state["onScreen"]:
                        off.append(state)
                    if state["obscured"]:
                        obscured.append(state)
                inv = page.evaluate(FOCUS_INVISIBLE)
                key = f"{name}@{width}"
                out[key] = {"stops": stops, "without_ring": no_ring[:5], "off_screen": off[:5],
                            "obscured": obscured[:5], "focused_while_invisible": faint[:5],
                            "tabbable": inv["tabbable"], "invisible_tabbables": inv["invisible"][:10],
                            "invisible_count": len(inv["invisible"])}
                if not stops:
                    self.fail("3 keyboard", f"{key}: Tab reached nothing")
                if no_ring:
                    self.fail("3 keyboard", f"{key}: {len(no_ring)} stops without a ring, "
                              f"first {no_ring[0]['el']} {no_ring[0]['label']!r}")
                if off:
                    self.fail("3 keyboard", f"{key}: {len(off)} stops off screen, first "
                              f"{off[0]['el']} {off[0]['label']!r}")
                if obscured:
                    self.fail("3 keyboard", f"{key}: {len(obscured)} stops hidden behind a fixed "
                              f"bar (2.4.11), first {obscured[0]['el']} {obscured[0]['label']!r}")
                if inv["invisible"]:
                    self.fail("3 keyboard", f"{key}: {len(inv['invisible'])} controls take focus "
                              f"while invisible, first {inv['invisible'][0]['el']} "
                              f"{inv['invisible'][0]['label']!r}")
                page.close()
            ctx.close()
        self.results["keyboard"] = out
        print("  3  keyboard: " + ", ".join(
            f"{k} {v['stops']}st/{v['invisible_count']}inv/{len(v['obscured'])}obs"
            for k, v in out.items()))

    def c4_frame_rate(self):
        ctx = self.context()
        page = self.open(ctx, "landing", settle=1500)
        page.evaluate("""() => { window.__frames = []; let last = performance.now();
          const tick = (t) => { window.__frames.push(t - last); last = t; requestAnimationFrame(tick); };
          requestAnimationFrame(tick); }""")
        for _ in range(80):
            page.mouse.wheel(0, 90)
            page.wait_for_timeout(16)
        page.wait_for_timeout(400)
        deltas = page.evaluate("window.__frames.filter(d => d > 0 && d < 400)")
        if deltas:
            fps = [1000 / d for d in deltas]
            self.results["frame_rate"] = {
                "surface": "landing film, scrolled", "frames": len(deltas),
                "median_fps": round(statistics.median(fps), 1),
                "p5_fps": round(sorted(fps)[max(0, len(fps) // 20)], 1),
                "worst_frame_ms": round(max(deltas), 1),
                "note": "headless Chrome paces at 60 Hz; a regression signal, not the panel's rate"}
            print(f"  4  frame rate (landing film): median {self.results['frame_rate']['median_fps']}"
                  f" fps, worst frame {self.results['frame_rate']['worst_frame_ms']} ms")
        page.close()
        ctx.close()

    def c5_transitions(self):
        out = {"total": 0, "transitioning": 0}
        ctx = self.context()
        for name in self.pages:
            page = self.open(ctx, name)
            f = page.evaluate("""() => { let t = 0, m = 0;
              for (const el of document.querySelectorAll('a,button,input,select,textarea,summary,[tabindex]')) {
                const b = el.getBoundingClientRect(); if (b.width < 2 || b.height < 2) continue;
                t++; if (Math.max(...getComputedStyle(el).transitionDuration.split(',').map(parseFloat)) > 0) m++; }
              return [t, m]; }""")
            out["total"] += f[0]
            out["transitioning"] += f[1]
            page.close()
        ctx.close()
        self.results["transitions"] = {**out, "note": "design contract; never a failure"}
        print(f"  5  transitions: {out['transitioning']}/{out['total']} (recorded only)")

    def c6_reduced_motion(self):
        out = {}
        for mode in ("os", "switch"):
            ctx = (self.context(reduced=True) if mode == "os"
                   else self.context(motion_off=True))
            for name in self.pages:
                page = self.open(ctx, name, settle=1800)
                if name == "landing":
                    page.mouse.wheel(0, 1800)
                    page.wait_for_timeout(1200)
                a = page.evaluate(ANIMATING)
                page.wait_for_timeout(2000)
                b = page.evaluate(ANIMATING)
                pinned = page.evaluate("document.querySelectorAll('.pin-spacer').length")
                row = {"infinite_animations": b["infinite"], "looping": b["which"],
                       "gpu_draws_per_s": (b["draws"] - a["draws"]) / 2 if a["draws"] is not None else None,
                       "paints2d_per_s": (b["paints2d"] - a["paints2d"]) / 2 if a["paints2d"] is not None else None,
                       "pinned_sections": pinned}
                out[f"{mode}/{name}"] = row
                if row["infinite_animations"]:
                    self.fail("6 motion", f"{mode}/{name}: {row['infinite_animations']} endless "
                              f"animations still running: {row['looping'][:4]}")
                if row["gpu_draws_per_s"]:
                    self.fail("6 motion", f"{mode}/{name}: still drawing {row['gpu_draws_per_s']} "
                              f"GPU frames a second after settling")
                page.close()
            ctx.close()
        # The same pages with motion allowed, for the before/after column: what
        # the motion switch has to stop.
        ctx = self.context()
        for name in ("landing", "library", "run"):
            page = self.open(ctx, name, settle=1800)
            a = page.evaluate(ANIMATING)
            page.wait_for_timeout(2000)
            b = page.evaluate(ANIMATING)
            out[f"motion-on/{name}"] = {"infinite_animations": b["infinite"],
                                        "gpu_draws_per_s": (b["draws"] - a["draws"]) / 2}
            page.close()
        ctx.close()
        self.results["reduced_motion"] = out
        print("  6  motion: " + ", ".join(
            f"{k} {v['infinite_animations']}loops/{v['gpu_draws_per_s']}draws"
            for k, v in out.items()))

    def c7_books(self):
        out = {}
        ctx = self.context(reduced=True)
        targets = [f"/brand/{s['id']}" for s in self.surf["sweeps"]]
        targets += [f"/brand/{m['sweep']}/{m['video']}" for m in self.surf["members"]]
        targets += ["/library/" + urllib.parse.quote(s) for s in self.surf["singles"]]
        for path in targets:
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e, x=errors: x.append(str(e)))
            page.on("console", lambda m, x=errors: x.append(m.text) if m.type == "error" else None)
            page.goto(BASE + path, wait_until="domcontentloaded")
            try:
                page.wait_for_selector(READY["book"], state="attached", timeout=20000)
            except Exception:
                errors.append("never built")
            page.wait_for_timeout(500)
            probe = self.caveat
            info = page.evaluate("""(probe) => {
              const book = document.querySelector('[data-cx-book]');
              const all = book ? book.textContent : '';
              return { chapters: document.querySelectorAll('[data-cx-chapter]').length,
                       spreads: document.querySelectorAll('[data-cx-spread]').length,
                       h1: [...document.querySelectorAll('h1')].filter(h => !h.closest('[hidden]')).length,
                       caveat: all.includes(probe),
                       standing: !!document.querySelector('[data-standing]')
                                 && (document.querySelector('[data-standing]').textContent || '').length > 80,
                       cannotTell: !!document.querySelector('[data-cannot-tell]') };
            }""", probe)
            out[path] = {**info, "errors": errors[:3]}
            problems = [k for k in ("caveat", "standing") if not info[k]]
            if not info["chapters"]:
                problems.append("no chapters")
            if info["h1"] != 1:
                problems.append(f"{info['h1']} h1")
            if errors:
                problems.append(f"errors {errors[:2]}")
            is_member = path.count("/") >= 3
            if not is_member and "standing" in problems:
                problems.remove("standing")   # the statement is about one person's face
            if problems:
                self.fail("7 books", f"{path}: {', '.join(problems)}")
            page.close()
        ctx.close()
        self.results["books"] = out
        print(f"  7  books: {len(out)} rendered, "
              f"{sum(1 for v in out.values() if v['caveat'])} with the bias caveat, "
              f"{sum(1 for v in out.values() if v['standing'])} with the statement to the person")

    def c9_no_script(self):
        out = {}
        ctx = self.context(js=False)
        for name, path in self.pages.items():
            page = ctx.new_page()
            # "load", not "domcontentloaded": innerText depends on the stylesheets,
            # and read before they apply it counted CSS-hidden text (79 extra
            # characters on one page in one run of 26 Sep 2026).
            page.goto(BASE + path, wait_until="load")
            info = page.evaluate("""(probe) => {
              const main = document.querySelector('main');
              const text = (main ? main.innerText : '').replace(/\\s+/g, ' ').trim();
              return { h1: document.querySelectorAll('h1').length, chars: text.length,
                       links: document.querySelectorAll('main a[href]').length,
                       caveat: (document.body.innerText || '').includes(probe) }; }""", self.caveat)
            out[name] = info
            if info["h1"] != 1:
                self.fail("9 no-script", f"{name} has {info['h1']} h1")
            if info["chars"] < 400:
                self.fail("9 no-script", f"{name} renders {info['chars']} characters")
            if not info["links"]:
                self.fail("9 no-script", f"{name} offers no way onward")
            # Pages that show no facial-derived score carry no caveat: the run
            # form, the landing (its figures are accuracies), the statement.
            if name not in ("run", "landing", "statement") and not info["caveat"]:
                self.fail("9 no-script", f"{name} carries no bias caveat")
            page.close()
        ctx.close()
        self.results["no_script"] = out
        print("  9  no script: " + ", ".join(f"{n} {i['chars']}ch" for n, i in out.items()))

    def c10_run_voice(self):
        sequence = [
            {"status": "running", "stage_index": -1, "total_stages": 4, "stage_label": "Queued"},
            {"status": "running", "stage_index": 0, "total_stages": 4, "stage_label": "a"},
            {"status": "running", "stage_index": 1, "total_stages": 4, "stage_label": "b"},
            {"status": "running", "stage_index": 2, "total_stages": 4, "stage_label": "c"},
            {"status": "running", "stage_index": 3, "total_stages": 4, "stage_label": "d"},
        ]
        endings = {
            "done": (200, {"status": "done", "stage_index": 3, "total_stages": 4, "stage_label": "d",
                           "result": {"authenticity_score": 61.18, "brand_health_score": 66.05,
                                      "segment_count": 94, "flagged_segments": [1] * 11,
                                      "bias_caveat": "IMPORTANT: stubbed."}}),
            "cancelled": (200, {"status": "cancelled", "stage_index": 1, "total_stages": 4,
                                "stage_label": "x"}),
            "error": (200, {"status": "error", "stage_index": 2, "total_stages": 4,
                            "stage_label": "x", "error": "Ollama unreachable at http://localhost:11434"}),
            "lost": (404, {"error": "unknown job_id"}),
        }
        read = """() => { const p = document.getElementById('bp-live-polite'),
            a = document.getElementById('bp-live-alert'), r = document.querySelector('[data-rec]');
          return { polite: p ? p.textContent.trim() : null, alert: a ? a.textContent.trim() : null,
                   title: document.title, role: r ? r.getAttribute('role') : null,
                   valuenow: r ? r.getAttribute('aria-valuenow') : null,
                   valuetext: r ? r.getAttribute('aria-valuetext') : null,
                   regions: document.querySelectorAll('#bp-live-polite, #bp-live-alert').length,
                   outside: p ? !p.closest('[data-run]') : null }; }"""

        def job(body, status=200):
            return lambda route: route.fulfill(status=status, content_type="application/json",
                                               body=json.dumps(body))

        voice: dict = {"stages": [], "endings": {}}
        ctx = self.context()
        page = ctx.new_page()
        cursor = {"i": 0}
        page.route("**/analyse/active", job({"active": True, "job_id": "verify",
                                             "stage_index": -1, "stage_label": "Queued"}))
        page.route("**/analyse/status/**", lambda route: job(sequence[cursor["i"]])(route))
        page.goto(BASE + "/run", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        for i in range(len(sequence)):
            cursor["i"] = i
            page.wait_for_timeout(1900)
            voice["stages"].append({**page.evaluate(read), "stage_index": sequence[i]["stage_index"]})
        page.close()
        for name, (code, body) in endings.items():
            page = ctx.new_page()
            page.route("**/analyse/active", job({"active": True, "job_id": name,
                                                 "stage_index": 1, "stage_label": "x"}))
            page.route("**/analyse/status/**", job(body, code))
            page.goto(BASE + "/run", wait_until="domcontentloaded")
            page.wait_for_timeout(3600)
            voice["endings"][name] = page.evaluate(read)
            page.close()
        ctx.close()
        base_title = "Analyse — BrandPulse"
        said = [s["polite"] for s in voice["stages"]]
        for i, s in enumerate(voice["stages"]):
            where = f"stage_index {s['stage_index']}"
            if not s["polite"]:
                self.fail("10 run voice", f"{where} announced nothing")
            if s["regions"] != 2 or not s["outside"]:
                self.fail("10 run voice", f"{where}: live regions wrong ({s['regions']})")
            if s["role"] != "progressbar" or not s["valuetext"]:
                self.fail("10 run voice", f"{where}: progress bar has no value text")
            if s["stage_index"] < 0 and s["valuenow"] is not None:
                self.fail("10 run voice", "queued claims a stage count")
            if s["stage_index"] >= 0 and s["valuenow"] != str(s["stage_index"]):
                self.fail("10 run voice", f"{where} reports aria-valuenow {s['valuenow']}")
            if s["title"] == base_title:
                self.fail("10 run voice", f"{where} left the tab title unchanged")
            if i and said[i] == said[i - 1]:
                self.fail("10 run voice", f"{where} repeated the previous announcement")
        for name, s in voice["endings"].items():
            if not (s["alert"] if name in ("error", "lost") else s["polite"]):
                self.fail("10 run voice", f"the {name} ending announced nothing")
        self.results["run_voice"] = voice
        print(f"  10 run voice: {len(voice['stages'])} stages, {len(voice['endings'])} endings read")

    def c11_reflow_matrix(self):
        out = {}
        matrix = QUICK_MATRIX if self.quick else MATRIX
        for width, height in matrix:
            for reduced in (True, False):
                ctx = self.context(width=width, height=height, reduced=reduced)
                for name in self.pages:
                    page = self.open(ctx, name, settle=700)
                    page.keyboard.press("End")
                    page.wait_for_timeout(500)
                    r = page.evaluate(REFLOW)
                    key = f"{name}@{width}x{height}{'' if reduced else '+motion'}"
                    out[key] = r
                    # Lost text is judged with layouts final (reduced motion): a
                    # scroll-driven track legitimately extends past the edge
                    # mid-animation. Sideways scroll is judged in both.
                    if reduced and r["lostCount"]:
                        w = max(r["lost"], key=lambda x: x["over"])
                        self.fail("11 reflow", f"{key}: {r['lostCount']} text elements off the "
                                  f"side, worst +{w['over']}px {w['el']} {w['text']!r}")
                    if r["canScrollX"]:
                        self.fail("11 reflow", f"{key}: the page scrolls sideways by {r['canScrollX']}px")
                    page.close()
                ctx.close()
        self.results["reflow"] = out
        bad = sum(1 for v in out.values() if v["lostCount"] or v["canScrollX"])
        print(f"  11 reflow: {len(out)} page/viewport/motion combinations, {bad} with a problem")

    def c12_label_in_name(self):
        script = r"""() => {""" + HELPERS + r"""
          const vis = (el) => { let out = '';
            const walk = (n) => { if (n.nodeType === 3) { out += n.nodeValue; return; }
              if (n.nodeType !== 1 || n.getAttribute('aria-hidden') === 'true') return;
              const cs = getComputedStyle(n); if (cs.display === 'none' || cs.visibility === 'hidden') return;
              if (n.classList.contains('sr-only')) return; for (const c of n.childNodes) walk(c); };
            for (const c of el.childNodes) walk(c); return norm(out); };
          const acc = (el) => { const by = el.getAttribute('aria-labelledby');
            if (by) return norm(by.split(/\s+/).map((i) => (document.getElementById(i) || {}).textContent || '').join(' '));
            return norm(el.getAttribute('aria-label') || ''); };
          const out = [];
          for (const el of document.querySelectorAll('a[href],button,summary,[role="button"],[role="link"],[role="tab"]')) {
            if (!shown(el)) continue;
            const v = vis(el), n = acc(el);
            if (!v || !n) continue;
            out.push({ visible: v, name: n, leads: n.toLowerCase().startsWith(v.toLowerCase()),
                       contains: n.toLowerCase().includes(v.toLowerCase()) });
          }
          return out; }"""
        out = {}
        for theme in THEMES:
            ctx = self.context(theme=theme, reduced=True)
            for name in self.pages:
                page = self.open(ctx, name)
                rows = page.evaluate(script)
                out[f"{theme}/{name}"] = {"checked": len(rows),
                                          "failing": [r for r in rows if not r["leads"]]}
                for r in rows:
                    if not r["contains"]:
                        self.fail("12 label-in-name", f"{theme}/{name}: {r['visible']!r} not in {r['name'][:60]!r}")
                    elif not r["leads"]:
                        self.fail("12 label-in-name", f"{theme}/{name}: {r['name'][:50]!r} does not "
                                  f"lead with {r['visible']!r}")
                page.close()
            ctx.close()
        self.results["label_in_name"] = out
        print(f"  12 label in name: {sum(v['checked'] for v in out.values())} overridden names, "
              f"{sum(len(v['failing']) for v in out.values())} not leading with the visible words")

    def c13_skip_link(self):
        out = {}
        ctx = self.context()
        for name in self.pages:
            page = self.open(ctx, name, settle=1500)
            page.evaluate("window.scrollTo(0, Math.min(6000, document.body.scrollHeight - innerHeight))")
            page.wait_for_timeout(600)
            # A real keypress from the top of the tab order, not link.focus(): the
            # 12 Sep check called focus() and measured a state no reader creates.
            read = """() => { const a = document.activeElement;
              const b = a.getBoundingClientRect();
              return { isSkip: a.classList.contains('skip-link'), text: (a.textContent||'').trim(),
                       visible: b.bottom > 0 && b.top < innerHeight && b.height > 1,
                       top: Math.round(b.top), scrollY: Math.round(scrollY) }; }"""
            # The landing's intro hands focus to <main> when it leaves, which is
            # what the skip link itself does -- so there the first Tab rightly
            # goes into the content, and the link is reached going backwards.
            handed = page.evaluate("document.activeElement && document.activeElement.id === 'main'")
            page.evaluate("document.activeElement && document.activeElement.blur()")
            page.keyboard.press("Tab")
            page.wait_for_timeout(700)
            state = page.evaluate(read)
            back = 0
            while not state["isSkip"] and back < 40:
                page.keyboard.press("Shift+Tab")
                page.wait_for_timeout(120)
                back += 1
                state = page.evaluate(read)
            if state["isSkip"]:
                page.wait_for_timeout(600)
                state = page.evaluate(read)
            state.update({"intro_focused_main": bool(handed), "reached_backwards_after": back})
            out[name] = state
            if not state["isSkip"]:
                self.fail("13 skip link", f"{name}: no skip link reachable by keyboard")
            elif back and not handed:
                self.fail("13 skip link", f"{name}: the skip link is not the first Tab stop")
            elif not state["visible"]:
                self.fail("13 skip link", f"{name}: skip link focused but not on screen (top {state['top']})")
            page.close()
        ctx.close()
        self.results["skip_link"] = out
        print(f"  13 skip link: visible when focused on {sum(1 for v in out.values() if v['isSkip'] and v['visible'])} of {len(out)}")

    def c14_text_spacing(self):
        css = ("*, *::before, *::after { line-height: 1.5 !important; letter-spacing: 0.12em !important;"
               " word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }")
        # A text element is clipped when part of it lies outside an ancestor
        # that hides overflow (hidden or clip). An ancestor that SCROLLS loses
        # nothing -- the book's pages scroll inside themselves -- and an element
        # with visible overflow paints outside its box. Keyed by position in the
        # document so before and after compare the same elements.
        read = r"""() => {""" + HELPERS + r"""
          const clips = (el) => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
              const cs = getComputedStyle(p);
              if (/(hidden|clip)/.test(cs.overflowX + cs.overflowY)) {
                const a = el.getBoundingClientRect(), b = p.getBoundingClientRect();
                if (a.right > b.right + 1 || a.bottom > b.bottom + 1 || a.left < b.left - 1 || a.top < b.top - 1) return sel(p);
              } } return null; };
          const out = {}; let i = 0, n = 0;
          for (const el of document.querySelectorAll('body *')) {
            i++;
            if (el.children.length || !norm(el.textContent)) continue;
            if (!shown(el) || ariaHidden(el) || srOnly(el) || el.closest('[hidden]')) continue;
            const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
            n++;
            const c = clips(el); if (c) out[i] = [sel(el), c, norm(el.textContent).slice(0, 30)];
          }
          return { measured: n, clipped: out }; }"""
        out = {}
        ctx = self.context(reduced=True)
        targets = dict(self.pages)
        if self.surf["longest"]:
            targets["member-longest-segment"] = self.surf["longest"]
        for name, path in targets.items():
            page = self.open(ctx, name if name in self.pages else "member-book", path=path)
            lost_all: list = []
            measured = [0]

            def once(p, i):
                before = p.evaluate(read)
                tag = p.add_style_tag(content=css)
                # Long enough for a layout that responds to its own words not
                # fitting (the film restacks) to have done so.
                p.wait_for_timeout(400)
                after = p.evaluate(read)
                tag.evaluate("t => t.remove()")
                measured[0] += after["measured"]
                for k, v in after["clipped"].items():
                    if k not in before["clipped"]:
                        lost_all.append({"spread": i, "el": v[0], "clipper": v[1], "text": v[2]})

            if name in BOOKS or name.startswith("member"):
                self.book_spreads(page, once, cap=60)
            else:
                once(page, 0)
            out[name] = {"measured": measured[0], "lost": lost_all[:10], "lostCount": len(lost_all)}
            if not measured[0]:
                self.fail("14 text spacing", f"{name}: measured nothing")
            if lost_all:
                self.fail("14 text spacing", f"{name}: {len(lost_all)} text elements clipped by the "
                          f"1.4.12 override, first {lost_all[0]}")
            page.close()
        ctx.close()
        self.results["text_spacing"] = out
        print("  14 text spacing: " + ", ".join(f"{n} {v['measured']}/{v['lostCount']}" for n, v in out.items()))

    def c15_axe(self):
        if not AXE.exists():
            self.fail("15 axe", f"axe-core is not installed at {AXE}")
            return
        out: dict = {}
        totals: dict = {}
        for theme in THEMES:
            for width, height in ((1440, 900), (390, 844)):
                ctx = self.context(theme=theme, width=width, height=height, reduced=True)
                for name in self.pages:
                    page = self.open(ctx, name)
                    found: dict = {}

                    def scan(p, i):
                        p.add_script_tag(path=str(AXE))
                        for v in p.evaluate("""async (tags) => {
                            const r = await axe.run(document, { runOnly: { type: 'tag', values: tags },
                                                                resultTypes: ['violations'] });
                            return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help,
                              nodes: v.nodes.length, where: v.nodes.slice(0, 3).map(n => n.target.join(' ')) })); }""",
                                              AXE_TAGS):
                            row = found.setdefault(v["id"], {**v, "spreads": 0, "nodes": 0})
                            row["nodes"] += v["nodes"]
                            row["spreads"] += 1

                    if name in BOOKS:
                        self.book_spreads(page, scan, cap=60)
                    else:
                        scan(page, 0)
                    key = f"{theme}/{name}@{width}"
                    out[key] = sorted(found.values(), key=lambda v: v["id"])
                    for v in found.values():
                        totals.setdefault(v["impact"] or "unknown", set()).add(v["id"])
                        if v["impact"] in ("critical", "serious"):
                            self.fail("15 axe", f"{key}: {v['impact']} {v['id']} on {v['nodes']} "
                                      f"nodes ({v['help']}) e.g. {v['where'][:1]}")
                    page.close()
                ctx.close()
        self.results["axe"] = {"tags": AXE_TAGS, "by_page": out,
                               "rules_by_impact": {k: sorted(v) for k, v in totals.items()}}
        print("  15 axe: " + ", ".join(f"{k} {len(v)} rules" for k, v in totals.items()) or "  15 axe: 0 violations")

    def c16_target_size(self):
        out = {}
        for width, height in ((1440, 900), (390, 844)):
            ctx = self.context(width=width, height=height, reduced=True)
            for name in self.pages:
                page = self.open(ctx, name)
                failing: list = []
                measured = [0]

                def once(p, i):
                    r = p.evaluate(TARGET_SIZE)
                    measured[0] += r["measured"]
                    failing.extend(r["failing"])

                if name in BOOKS:
                    self.book_spreads(page, once, cap=60)
                else:
                    once(page, 0)
                uniq = {(f["el"], f["label"]): f for f in failing}
                key = f"{name}@{width}"
                out[key] = {"measured": measured[0], "failing": list(uniq.values())[:12],
                            "failingCount": len(uniq)}
                for f in list(uniq.values())[:6]:
                    self.fail("16 target size", f"{key}: {f['el']} {f['label']!r} {f['w']}x{f['h']}px")
                page.close()
            ctx.close()
        self.results["target_size"] = out
        print("  16 target size: " + ", ".join(f"{k} {v['failingCount']}" for k, v in out.items()))

    def c17_forced_colors(self):
        out = {}
        ctx = self.context(forced=True, reduced=True)
        for name in self.pages:
            page = self.open(ctx, name)
            lost = []
            for _ in range(30):
                page.keyboard.press("Tab")
                s = page.evaluate(FOCUS_READ)
                if s and not s["ringSurvivesForcedColors"]:
                    lost.append(s)
            marks = page.evaluate(r"""() => {""" + HELPERS + r"""
              /* A mark drawn only as a background colour: no text, no border, no
                 image. Forced colours replace backgrounds, so it vanishes. */
              let n = 0; const which = new Set();
              for (const el of document.querySelectorAll('body *')) {
                if (!shown(el) || norm(el.textContent) || el.children.length) continue;
                const cs = getComputedStyle(el), r = el.getBoundingClientRect();
                if (r.width < 2 || r.height < 2 || cs.forcedColorAdjust === 'none') continue;
                if (el.tagName === 'CANVAS' || el.tagName === 'IMG' || el.closest('svg')) continue;
                const bw = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderLeftWidth);
                if (bw === 0 && cs.backgroundImage === 'none' && !/(0, 0, 0, 0)|transparent/.test(cs.backgroundColor)) { n++; which.add(sel(el)); }
              }
              return { count: n, which: [...which].slice(0, 12) }; }""")
            out[name] = {"ring_lost": lost[:5], "ring_lost_count": len(lost), "background_only_marks": marks}
            if lost:
                self.fail("17 forced colours", f"{name}: {len(lost)} focus rings disappear, first {lost[0]['el']}")
            page.close()
        ctx.close()
        self.results["forced_colors"] = out
        print("  17 forced colours: " + ", ".join(
            f"{n} {v['ring_lost_count']}rings/{v['background_only_marks']['count']}marks" for n, v in out.items()))

    def c18_vision(self):
        SHOTS.mkdir(parents=True, exist_ok=True)
        made = []
        ctx = self.context(reduced=True, blur=True, width=1440, height=900)
        for name in [n for n in ("landing", "library", "member-book", "brand-book") if n in self.pages]:
            page = self.open(ctx, name, settle=1200)
            if name == "landing":
                page.evaluate("document.getElementById('proof') && document.getElementById('proof').scrollIntoView()")
                page.wait_for_timeout(600)
            cdp = ctx.new_cdp_session(page)
            for kind in ["none"] + VISION:
                cdp.send("Emulation.setEmulatedVisionDeficiency", {"type": kind})
                page.wait_for_timeout(250)
                path = SHOTS / f"vision-{name}-{kind}.png"
                page.screenshot(path=str(path))
                made.append(str(path.relative_to(ROOT)))
            page.close()
        ctx.close()
        self.results["vision"] = {"screenshots": made,
                                  "note": "for a human reader; stills blurred"}
        print(f"  18 vision: {len(made)} screenshots in {SHOTS.relative_to(ROOT)}")

    def c19_small_text(self):
        out = {}
        for width, height in ((390, 844), (1440, 900)):
            ctx = self.context(width=width, height=height, reduced=True)
            for name in self.pages:
                page = self.open(ctx, name)
                acc = {"measured": 0, "micro": 0, "small": [], "svg": []}

                def once(p, i):
                    r = p.evaluate(SMALL_TEXT)
                    acc["measured"] += r["measured"]
                    acc["micro"] += r["micro"]
                    acc["small"].extend(r["small"])
                    acc["svg"].extend(r["svgSmall"])

                if name in BOOKS:
                    self.book_spreads(page, once, cap=60)
                else:
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(300)
                    once(page, 0)
                uniq = {(s["el"], s["size"]): s for s in acc["small"]}
                svg = {(s["text"], s["px"]): s for s in acc["svg"]}
                key = f"{name}@{width}"
                out[key] = {"measured": acc["measured"], "micro_11_5_to_12_5": acc["micro"], "small": list(uniq.values())[:12],
                            "smallCount": len(uniq), "svgSmall": list(svg.values())[:8],
                            "svgSmallCount": len(svg)}
                if uniq:
                    worst = min(uniq.values(), key=lambda s: s["size"])
                    self.fail("19 small text", f"{key}: {len(uniq)} reader-facing styles under 11.5px, "
                              f"smallest {worst['size']}px {worst['el']} {worst['text']!r}")
                if svg:
                    worst = min(svg.values(), key=lambda s: s["px"])
                    self.fail("19 small text", f"{key}: {len(svg)} chart labels under 10px, "
                              f"smallest {worst['px']}px {worst['text']!r}")
                page.close()
            ctx.close()
        self.results["small_text"] = out
        print("  19 small text: " + ", ".join(f"{k} {v['smallCount']}+{v['svgSmallCount']}svg" for k, v in out.items()))

    def c20_shelf_follows_window(self):
        ctx = self.context(width=1440, height=900)
        page = self.open(ctx, "library", settle=2500)
        state = """() => { const bk = document.querySelector('[data-bk]');
          const shelfShown = !!bk && getComputedStyle(bk).display !== 'none' && bk.getBoundingClientRect().height > 50;
          const cards = [...document.querySelectorAll('[data-rack] li, .sw__one')].filter(li => li.getBoundingClientRect().height > 10).length;
          const text = (document.querySelector('main') || document.body).innerText.replace(/\\s+/g,' ').trim().length;
          const offer = document.querySelector('[data-view-shelf]');
          const offersShelf = !!offer && !offer.hidden && offer.getBoundingClientRect().height > 0;
          return { shelfShown, cards, text, offersShelf }; }"""
        steps = {"1440 at load": page.evaluate(state)}
        page.set_viewport_size({"width": 800, "height": 900})
        page.wait_for_timeout(1500)
        steps["narrowed to 800"] = page.evaluate(state)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.wait_for_timeout(2500)
        steps["widened to 1440"] = page.evaluate(state)
        page.set_viewport_size({"width": 1024, "height": 430})
        page.wait_for_timeout(1500)
        steps["landscape phone 1024x430"] = page.evaluate(state)
        page.close()
        ctx.close()
        self.results["shelf_follows_window"] = steps
        narrow = steps["narrowed to 800"]
        if not narrow["cards"]:
            self.fail("20 shelf/list", f"narrowing a loaded shelf to 800px leaves {narrow['text']} characters and no list")
        wide = steps["widened to 1440"]
        if steps["1440 at load"]["shelfShown"] and not (wide["shelfShown"] or wide.get("offersShelf")):
            self.fail("20 shelf/list", "widening back to 1440 neither brings the shelf back nor offers it")
        print("  20 shelf/list: " + "; ".join(f"{k}: shelf={v['shelfShown']} cards={v['cards']}" for k, v in steps.items()))

    def c21_print(self):
        # What a reader would get on paper, against what the book holds. Both
        # sides count the same thing: leaf text a sighted reader can see --
        # not aria-hidden, not screen-reader-only, not an SVG <title> -- and
        # not hidden by its own control's state (a collapsed "show more", an
        # empty state). What the BOOK hides for pagination (a chapter or spread
        # not on the desk) is exactly what printing must not lose, so it counts.
        count = r"""(printing) => {""" + HELPERS + r"""
          const book = document.querySelector('[data-cx-book]');
          if (!book) return { chars: 0, worst: 99 };
          const lum = (s) => { const v = (s.match(/[\d.]+/g)||[]).slice(0,3).map(Number)
            .map(c => (c <= 1 && !Number.isInteger(c)) ? c*255 : c).map(c => { c/=255; return c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4); });
            return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]; };
          const ownHidden = (el) => { for (let n = el; n && n !== book; n = n.parentElement)
              if (n.hidden && !n.matches('[data-cx-chapter], [data-cx-spread]')) return true; return false; };
          const keepsBackground = (el) => { for (let n = el; n && n.nodeType === 1; n = n.parentElement)
              if (getComputedStyle(n).printColorAdjust === 'exact') return true; return false; };
          let chars = 0, worst = 99, where = '';
          for (const el of book.querySelectorAll('*')) {
            if (el.children.length || el.closest('svg') || ariaHidden(el) || srOnly(el) || ownHidden(el)) continue;
            const t = norm(el.textContent); if (!t) continue;
            if (printing) {
              if (!shown(el)) continue;
              const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
              if (!keepsBackground(el)) {
                /* Printed on white: browsers drop page backgrounds by default. */
                const ratio = 1.05 / (lum(getComputedStyle(el).color) + 0.05);
                if (ratio < worst) { worst = ratio; where = sel(el) + ' ' + t.slice(0, 24); }
              }
            }
            chars += t.length;
          }
          return { chars, worst: Math.round(worst * 100) / 100, where }; }"""
        out = {}
        ctx = self.context(reduced=True)
        for name in [n for n in BOOKS if n in self.pages]:
            page = self.open(ctx, name)
            total = page.evaluate(count, False)["chars"]
            # A real print fires beforeprint, which is where the book lays
            # itself out for paper; emulating the print medium alone does not.
            page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
            page.emulate_media(media="print")
            page.wait_for_timeout(700)
            info = page.evaluate(count, True)
            share = round(info["chars"] / total, 3) if total else 0
            out[name] = {"bookChars": total, "printedChars": info["chars"], "share": share,
                         "worstOnWhite": info["worst"], "worstWhere": info["where"]}
            if share < 0.98:
                self.fail("21 print", f"{name}: printing carries {share:.0%} of the book's text")
            if info["worst"] < 4.5:
                self.fail("21 print", f"{name}: printed text as low as {info['worst']}:1 on white "
                          f"paper ({info['where']})")
            page.close()
        ctx.close()
        self.results["print"] = out
        print("  21 print: " + ", ".join(f"{n} {v['share']:.0%} of text, worst {v['worstOnWhite']}:1" for n, v in out.items()))

    def c22_motion_switch(self):
        ctx = self.context()
        page = self.open(ctx, "landing", settle=1500)
        found = page.evaluate("""() => { const b = [...document.querySelectorAll('button')]
            .find(b => /^motion/i.test((b.textContent || '').trim()) || b.hasAttribute('data-motion-toggle'));
          return b ? { text: b.textContent.trim(), pressed: b.getAttribute('aria-pressed') } : null; }""")
        self.results["motion_switch"] = {"control": found}
        if not found:
            self.fail("22 motion switch", "no motion control on the page")
        page.close()
        ctx.close()
        print(f"  22 motion switch: control {'present' if found else 'absent'} (effect measured by check 6 'switch/')")

    def c23_one_page(self):
        out = {}
        ctx = self.context(reduced=True)
        for name in [n for n in BOOKS if n in self.pages]:
            page = self.open(ctx, name)
            words = page.evaluate("(document.querySelector('[data-cx-book]')||{}).textContent.replace(/\\s+/g,' ').trim().length")
            page.close()
            path = self.pages[name] + "?read=page"
            page = self.open(ctx, name, path=path)
            info = page.evaluate(r"""() => {""" + HELPERS + r"""
              const book = document.querySelector('[data-cx-book]');
              const hidden = book ? [...book.querySelectorAll('[data-cx-chapter]')].filter(c => !shown(c)).length : -1;
              return { linear: document.documentElement.dataset.read === 'page', hiddenChapters: hidden,
                       chars: book ? book.textContent.replace(/\s+/g, ' ').trim().length : 0,
                       h1: [...document.querySelectorAll('h1')].filter(shown).length }; }""")
            out[name] = {"bookChars": words, **info}
            if not info["linear"]:
                self.fail("23 one page", f"{name}: ?read=page does not give the one-page reading")
            elif info["hiddenChapters"]:
                self.fail("23 one page", f"{name}: {info['hiddenChapters']} chapters hidden in the one-page reading")
            page.close()
        ctx.close()
        self.results["one_page"] = out
        print("  23 one page: " + ", ".join(f"{n} linear={v['linear']}" for n, v in out.items()))

    def c24_journeys(self):
        out: dict = {}
        # (a) The Library states the bias caveat with scripting on (README, "Engineering rules").
        for width, height, label in ((1440, 900, "shelf"), (390, 844, "list")):
            ctx = self.context(width=width, height=height)
            page = self.open(ctx, "library", settle=2500)
            visible = page.evaluate("""(probe) => { const m = document.querySelector('main');
                return !!m && m.innerText.includes(probe); }""", self.caveat)
            out[f"library caveat ({label})"] = visible
            if not visible:
                self.fail("24 journeys", f"library ({label}): the bias caveat is not on the page with scripting on")
            # (b) Delete is reachable and pressable from the keyboard.
            reach = {"deleteReached": False, "spaceConfirms": False, "stops": 0}
            for _ in range(80):
                page.keyboard.press("Tab")
                page.wait_for_timeout(40)
                reach["stops"] += 1
                name = page.evaluate("(document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.textContent) || '').trim()")
                if re.match(r"^(Take|Open the desk for|Take down)", name or ""):
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(900)
                if re.match(r"^Delete\b", name or ""):
                    reach["deleteReached"] = True
                    page.keyboard.press("Space")
                    page.wait_for_timeout(500)
                    reach["spaceConfirms"] = page.evaluate("""() => /permanently/i.test((document.activeElement && document.activeElement.textContent) || '')""")
                    page.keyboard.press("Escape")
                    break
            out[f"keyboard delete ({label})"] = reach
            if not reach["deleteReached"]:
                self.fail("24 journeys", f"library ({label}): Delete is not reachable by keyboard in {reach['stops']} Tab stops")
            elif not reach["spaceConfirms"]:
                self.fail("24 journeys", f"library ({label}): Space on Delete does not ask to confirm")
            page.close()
            ctx.close()
        # (c) The film's four parts and its link are all in the accessibility tree.
        ctx = self.context()
        page = self.open(ctx, "landing", settle=1500)
        tree = page.locator("#film").aria_snapshot() if page.locator("#film").count() else ""
        film = {"beats": sum(1 for t in ("A second.", "The words.", "Nothing hidden.") if t in tree)
                + (1 if ("splits here" in tree or "Accounted for" in tree) else 0),
                "link": "Open this analysis" in tree,
                "facialDisclosure": "Facial accuracy" in tree}
        out["film in the accessibility tree"] = film
        if film["beats"] < 4 or not film["link"] or not film["facialDisclosure"]:
            self.fail("24 journeys", f"film: a screen reader reaches {film['beats']} of 4 parts, link={film['link']}, "
                      f"facial disclosure={film['facialDisclosure']}")
        page.close()
        # (d) The boot screen: focus is inside it, and a modifier key alone does not dismiss it.
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="domcontentloaded")
        boot: dict = {"shown": False}
        try:
            page.wait_for_selector("[data-gate]", state="attached", timeout=5000)
            page.keyboard.press("Escape")
            page.wait_for_selector("[data-boot]", state="attached", timeout=5000)
            page.wait_for_timeout(300)
            boot["shown"] = True
            boot["focusInside"] = page.evaluate("!!(document.activeElement && document.activeElement.closest('[data-boot]'))")
            page.keyboard.press("Shift")
            page.keyboard.press("Control")
            page.wait_for_timeout(400)
            # Leaving fades first (.is-going), so "still there" means not leaving.
            boot["survivesModifierKeys"] = page.locator("[data-boot]:not(.is-going)").count() > 0
        except Exception as exc:
            boot["error"] = str(exc)[:80]
        out["boot screen"] = boot
        if boot.get("shown") and not boot.get("focusInside"):
            self.fail("24 journeys", "boot screen: focus is not inside the dialog")
        if boot.get("shown") and not boot.get("survivesModifierKeys"):
            self.fail("24 journeys", "boot screen: pressing Shift or Control alone dismisses it")
        page.close()
        ctx.close()
        self.results["journeys"] = out
        print("  24 journeys: " + "; ".join(f"{k}: {v}" for k, v in out.items()))

    CHECKS = {1: c1_requests_console, 2: c2_contrast, 3: c3_keyboard, 4: c4_frame_rate,
              5: c5_transitions, 6: c6_reduced_motion, 7: c7_books, 9: c9_no_script,
              10: c10_run_voice, 11: c11_reflow_matrix, 12: c12_label_in_name,
              13: c13_skip_link, 14: c14_text_spacing, 15: c15_axe, 16: c16_target_size,
              17: c17_forced_colors, 18: c18_vision, 19: c19_small_text,
              20: c20_shelf_follows_window, 21: c21_print, 22: c22_motion_switch,
              23: c23_one_page, 24: c24_journeys}

    def run(self) -> None:
        print(f"surfaces: {json.dumps(self.pages)}")
        for n, fn in self.CHECKS.items():
            if not self.wants(n):
                continue
            try:
                fn(self)
            except Exception as exc:     # one broken check must not hide the rest
                self.fail(f"{n} harness", f"{fn.__name__} crashed: {type(exc).__name__}: {str(exc)[:200]}")
                print(f"  {n} CRASHED: {type(exc).__name__}: {str(exc)[:200]}")


def pass_intro(page) -> dict:
    """
    Take down the gate and the boot screen, through their real exits.

    Escape rather than a bypass flag, so a gate or boot screen that stopped
    being dismissable fails here instead of being quietly skipped. Only the
    opening document raises either one; every other address returns at once.
    """
    seen = {"gate": False, "boot": False}
    if page.locator("[data-opening]").count() == 0:
        return seen
    try:
        page.wait_for_selector("[data-gate]", state="attached", timeout=4000)
        seen["gate"] = True
        page.keyboard.press("Escape")
        page.wait_for_selector("[data-gate]", state="detached", timeout=6000)
    except Exception:
        pass
    try:
        page.wait_for_selector("[data-boot]", state="attached", timeout=2500)
        seen["boot"] = True
        page.keyboard.press("Escape")
        page.wait_for_selector("[data-boot]", state="detached", timeout=6000)
    except Exception:
        pass
    return seen


def _blur_frames(route):
    """Video stills are blurred on the way into the browser (README, "Engineering rules")."""
    from PIL import Image, ImageFilter
    resp = route.fetch()
    try:
        img = Image.open(io.BytesIO(resp.body())).convert("RGB")
        img = img.filter(ImageFilter.GaussianBlur(radius=max(6, img.width // 60)))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        route.fulfill(status=200, body=buf.getvalue(), headers={"content-type": "image/jpeg"})
    except Exception:
        route.fulfill(response=resp)


def main() -> int:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated check numbers")
    ap.add_argument("--quick", action="store_true", help="5 viewports instead of 13")
    ap.add_argument("--label", default="", help="also write ui_measurements.<label>.json")
    args = ap.parse_args()
    only = {int(x) for x in args.only.split(",") if x.strip()} or None

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True, args=[
                "--headless=new", "--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"])
        except Exception:
            browser = p.chromium.launch(args=["--enable-unsafe-swiftshader"])
        h = Harness(browser, only, args.quick)
        h.run()
        browser.close()

    h.results["failures"] = h.failures
    h.results["failure_count_by_check"] = {}
    for f in h.failures:
        key = f.split("]")[0].strip("[")
        h.results["failure_count_by_check"][key] = h.results["failure_count_by_check"].get(key, 0) + 1
    text = json.dumps(h.results, indent=2, default=str) + "\n"
    if only:
        # A partial run updates only the checks it ran.
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
        old.update({k: v for k, v in h.results.items() if k not in ("failures", "failure_count_by_check")})
        old.setdefault("partial_runs", []).append({"at": h.results["measured_at"], "checks": sorted(only),
                                                   "failures": h.failures})
        text = json.dumps(old, indent=2, default=str) + "\n"
    OUT.write_text(text, encoding="utf-8")
    if args.label:
        (HERE / f"ui_measurements.{args.label}.json").write_text(
            json.dumps(h.results, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    if h.failures:
        print(f"\n{len(h.failures)} FAILURES:")
        for f in h.failures:
            print("  -", f)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
