"""
make_grain.py — generate the interface's grain tile.

A 180x180 tileable monochrome noise PNG, written to ui/public/grain.png.

Why generated rather than an SVG feTurbulence filter: feTurbulence is
re-rasterised by the compositor on some browsers when the layer it sits on
changes, which shows up as a frame-rate cost on exactly the pinned, scrubbed
sections this interface leans on. A static tile is painted once and costs
nothing per frame.

Deterministic (fixed seed), so rebuilding does not produce a different grain
and a diff on this file always means the parameters changed.

Run:  python interface/ui_build/make_grain.py
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "interface" / "ui" / "public" / "grain.png"
SIZE = 180
SEED = 20260911


def main() -> int:
    random.seed(SEED)
    image = Image.new("L", (SIZE, SIZE))
    # A tight band around mid-grey: the tile is composited at 2.8-4.0% opacity,
    # so a full 0-255 spread would read as dirt rather than as grain.
    image.putdata([random.randint(96, 160) for _ in range(SIZE * SIZE)])
    image.convert("RGB").save(TARGET, "PNG", optimize=True)
    print(f"{TARGET.relative_to(ROOT)}  {SIZE}x{SIZE}  {TARGET.stat().st_size / 1024:.1f} KB  seed {SEED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
