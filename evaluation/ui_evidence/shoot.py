"""
shoot.py — photograph every surface, both displays, desktop and phone.

    python -m flask --app app run --port 5057 &
    python evaluation/ui_evidence/shoot.py

Writes ui_evidence/shots/. Nothing here is part of pytest: it needs a browser
and it writes to the working tree.

Rewritten 20 Sep 2026 with the fourth interface. Five surfaces rather than
four, because the combined report is now a document of its own rather than a
variant of the single report, and the two displays are BENCH and FIELD.

It also fails loudly on a console error. A surface that renders a picture and
throws while doing it is not a surface that works, and a screenshot alone
cannot tell the difference.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(__file__).resolve().parent / "shots"
BASE = "http://127.0.0.1:5057"

WIDTHS = {"desktop": (1440, 900), "phone": (390, 844)}
DISPLAYS = ("bench", "field")

# Panels of the report worth their own frame, by the anchor the page exposes.
ACTS = ["moment", "weak", "coverage", "measures", "audience", "ledger"]


def first_sweep() -> str | None:
    """Any sweep on disk, so the combined report has something real to draw."""
    for path in sorted((ROOT / "outputs" / "sweeps").glob("*/sweep.json")):
        return json.loads(path.read_text(encoding="utf-8"))["sweep_id"]
    return None


def main() -> int:
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(exist_ok=True)
    reports = sorted(p.name for p in (ROOT / "outputs").glob("*.json"))
    if not reports:
        print("no reports in outputs/", file=sys.stderr)
        return 1

    def faceless_share(name: str) -> float:
        report = json.loads((ROOT / "outputs" / name).read_text(encoding="utf-8"))
        segments = report["all_segments"]
        if not segments:
            return 0.0
        missing = sum(
            1 for s in segments
            if not (s.get("model_outputs") or {}).get("facial_emotion", {}).get("dominant"))
        return missing / len(segments)

    # The report with the thinnest facial coverage is the one worth
    # photographing: it is where the absences have to be visible. The fullest
    # is photographed as the ordinary case. Both are chosen from what is on
    # disk: until 26 Sep 2026 the ordinary case was a report named here by
    # hand, deleted on 24 Sep, so every "report" shot was a 404 page.
    thin = max(reports, key=faceless_share)
    full = min(reports, key=faceless_share)
    sweep_id = first_sweep()

    pages = {
        "opening": "/",
        "run": "/run",
        "library": "/library",
        "report": "/library/" + urllib.parse.quote(full),
        "report-thin": "/library/" + urllib.parse.quote(thin),
    }
    if sweep_id:
        pages["sweep"] = f"/brand/{urllib.parse.quote(sweep_id)}"

    problems: dict[str, list[str]] = {}
    count = 0

    with sync_playwright() as play:
        browser = play.chromium.launch(args=["--enable-unsafe-swiftshader"])

        def shoot(page, name: str, full: bool = False) -> None:
            nonlocal count
            page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=full)
            count += 1

        for display in DISPLAYS:
            for device, (width, height) in WIDTHS.items():
                for name, path in pages.items():
                    page = browser.new_page(viewport={"width": width, "height": height},
                                            device_scale_factor=2)
                    key = f"{name}-{display}-{device}"
                    page.on("pageerror", lambda e, k=key: problems.setdefault(k, []).append(str(e)))
                    page.on("console", lambda m, k=key: (
                        problems.setdefault(k, []).append(m.text) if m.type == "error" else None))

                    page.goto(BASE + path, wait_until="networkidle")
                    page.evaluate(f"localStorage.setItem('brandpulse-theme','{display}')")
                    page.reload(wait_until="networkidle")
                    page.wait_for_timeout(2600)
                    shoot(page, key)

                    # The report gets one frame per panel, at desktop width only.
                    if name == "report" and device == "desktop":
                        for act in ACTS:
                            found = page.evaluate(
                                f"""(() => {{ const el = document.querySelector('[data-act="{act}"]');
                                    if (!el) return false; el.scrollIntoView(); return true; }})()""")
                            if not found:
                                continue
                            page.wait_for_timeout(900)
                            shoot(page, f"act-{act}-{display}")
                    page.close()

        # Reduced motion, full page, so the still state can be looked at as a
        # design rather than inferred. It has to be COMPLETE, not degraded.
        for display in DISPLAYS:
            page = browser.new_page(viewport={"width": 1440, "height": 900},
                                    device_scale_factor=2, reduced_motion="reduce")
            page.goto(BASE + pages["report"], wait_until="networkidle")
            page.evaluate(f"localStorage.setItem('brandpulse-theme','{display}')")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2600)
            shoot(page, f"reduced-{display}", full=False)
            page.close()

        # The narrowest width the interface claims to work at.
        for name, path in pages.items():
            page = browser.new_page(viewport={"width": 320, "height": 720},
                                    device_scale_factor=2)
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(2400)
            overflow = page.evaluate(
                "document.documentElement.scrollWidth > window.innerWidth + 1")
            if overflow:
                problems.setdefault(f"{name}-320", []).append(
                    "horizontal overflow at 320px")
            shoot(page, f"{name}-320")
            page.close()

        browser.close()

    print(f"{count} frames into {SHOTS.relative_to(ROOT)}")
    if problems:
        print("\nsurfaces that reported a problem:", file=sys.stderr)
        for key, messages in problems.items():
            for message in messages:
                print(f"  {key}: {message}", file=sys.stderr)
        return 1
    print("no console errors, no page errors, no overflow at 320px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
