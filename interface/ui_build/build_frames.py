"""
build_frames.py — derive this interface's imagery from the frames on disk.

Why this exists
---------------
`data/<video_id>/frames/` holds the actual frames the pipeline analysed, one per
second, extracted by `pipeline/downloader.py` at 1 fps. They are the only honest
imagery this project has: no stock photograph, no illustration, no generated
picture, no external request. They are the real face the facial channel was
reading at the exact second it disagreed with the words being spoken.

They are also 3840x2160 and roughly 650 KB each: 2.0 GB across the four videos
behind the nine reports saved when this was written. They cannot be served as
they are.

This script derives three products the interface can actually reach, and writes
them into `ui/public/frames/`, which `npm run build` copies into `static/`:

  <video_id>/p/<second>.jpg   a PLATE: one frame per segment midpoint, wide
                              enough to be shown at full scale rather than as a
                              thumbnail. This is the image the report page
                              contemplates, and the texture the divergence
                              shader samples.
  <video_id>/strip.jpg        a SPRITE GRID of every plate second, so scrubbing
                              the timeline moves through the face without
                              issuing one request per segment. A grid rather
                              than a single row because a 136-segment row at
                              this tile size would exceed the ~32767 px that
                              browsers will decode.
  manifest.json               what exists, so the interface asks for nothing
                              that is not on disk, and can draw the absence
                              honestly when a video has not been derived.

Only segment midpoints are derived, not every second, because the segment is
this system's unit of analysis ("segments are the spine", README, "Engineering rules")
and the midpoint frame is representative of the window the facial channel
pooled over. For those same nine reports that was 336 unique frames against
7,043 on disk.

`data/` is gitignored and these downloads are analysis-only. The derived images
live only in this repo and are only ever served by a local Flask process.

Run it (no network, no model, no Ollama):
    python interface/ui_build/build_frames.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
DATA = ROOT / "data"
FRAMES_OUT = ROOT / "interface" / "ui" / "public" / "frames"

# The sizes, qualities and report readers are frame_cache.py's. That module is
# what the running server derives with, and it stays self-contained (a Flask
# process must not depend on this build-time folder), so this script takes them
# from it rather than keeping a second copy: an image built here and one derived
# on request are the same image by construction. Until 26 Sep 2026 both files
# carried their own copies, and a test checked that they still agreed.
sys.path.insert(0, str(ROOT))
from pipeline.frame_cache import (  # noqa: E402
    HERO_QUALITY, HERO_WIDTH, PLATE_QUALITY, PLATE_WIDTH, STRIP_COLS, STRIP_QUALITY,
    TILE_W, WINDOW_QUALITY, WINDOW_WIDTH, midpoint_seconds, report_files, source_frame,
    video_id_of, window_seconds,
)


def build_window(video_id: str, seconds: list[int], skip: set[int]) -> list[int]:
    """
    Derive the smaller window frames, at WINDOW_WIDTH, for a flagged span.

    Skips any second that already has a full-size plate, so the midpoint frame
    is never stored twice.
    """
    out_dir = FRAMES_OUT / video_id / "w"
    resolved: list[int] = []
    for second in sorted(set(seconds) - skip):
        source = source_frame(video_id, second)
        if source is None:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image = image.convert("RGB")
            ratio = image.height / image.width
            image.resize((WINDOW_WIDTH, max(1, round(WINDOW_WIDTH * ratio))), Image.LANCZOS) \
                 .save(out_dir / f"{second}.jpg", "JPEG",
                       quality=WINDOW_QUALITY, optimize=True, progressive=True)
        resolved.append(second)
    return resolved


def build_video(video_id: str, seconds: list[int]) -> dict | None:
    """
    Derive every plate and the sprite grid for one video.

    Returns the manifest entry, or None when `data/<video_id>/frames/` is absent
    entirely — in which case the interface is told the video has no imagery and
    says so, rather than requesting files that will 404.
    """
    frames_dir = DATA / video_id / "frames"
    if not frames_dir.is_dir():
        print(f"  {video_id}: no data/{video_id}/frames/ — skipped")
        return None

    plate_dir = FRAMES_OUT / video_id / "p"
    plate_dir.mkdir(parents=True, exist_ok=True)
    hero_dir = FRAMES_OUT / video_id / "h"
    hero_dir.mkdir(parents=True, exist_ok=True)

    wanted = sorted(set(seconds))
    resolved: list[int] = []
    hero_seconds: list[int] = []
    tiles: list[Image.Image] = []
    tile_h = 0
    plate_w = 0
    plate_h = 0
    hero_w = 0
    hero_h = 0

    for second in wanted:
        source = source_frame(video_id, second)
        if source is None:
            continue

        with Image.open(source) as image:
            image = image.convert("RGB")
            width, height = image.size
            ratio = height / width

            plate = image.resize(
                (PLATE_WIDTH, max(1, round(PLATE_WIDTH * ratio))),
                Image.LANCZOS,
            )
            plate.save(plate_dir / f"{second}.jpg", "JPEG",
                       quality=PLATE_QUALITY, optimize=True, progressive=True)
            plate_w, plate_h = plate.size

            # The hero. Only derived where the source is genuinely larger than
            # the target: upscaling a frame to 2560 would cost the disk and
            # give a reader nothing, and the opening page can fall back to the
            # plate for a video that was never shot that big.
            if width >= HERO_WIDTH:
                hero = image.resize(
                    (HERO_WIDTH, max(1, round(HERO_WIDTH * ratio))), Image.LANCZOS)
                hero.save(hero_dir / f"{second}.jpg", "JPEG",
                          quality=HERO_QUALITY, optimize=True, progressive=True)
                hero_w, hero_h = hero.size
                hero.close()
                hero_seconds.append(second)

            tile_h = max(1, round(TILE_W * ratio))
            tiles.append(image.resize((TILE_W, tile_h), Image.LANCZOS))

        resolved.append(second)

    if not resolved:
        print(f"  {video_id}: no midpoint second had a frame on disk — skipped")
        return None

    rows = (len(tiles) + STRIP_COLS - 1) // STRIP_COLS
    strip = Image.new("RGB", (TILE_W * STRIP_COLS, tile_h * rows), (10, 11, 16))
    for index, tile in enumerate(tiles):
        strip.paste(tile, ((index % STRIP_COLS) * TILE_W, (index // STRIP_COLS) * tile_h))
        tile.close()
    strip.save(FRAMES_OUT / video_id / "strip.jpg", "JPEG",
               quality=STRIP_QUALITY, optimize=True, progressive=True)

    print(f"  {video_id}: {len(resolved)} plates at {plate_w}x{plate_h}, "
          f"{len(hero_seconds)} heroes at {hero_w}x{hero_h}, "
          f"sprite {strip.size[0]}x{strip.size[1]} ({STRIP_COLS}x{rows} tiles)")

    entry_hero = ({"w": hero_w, "h": hero_h, "seconds": hero_seconds}
                  if hero_seconds else None)

    return {
        "seconds": resolved,
        **({"hero": entry_hero} if entry_hero else {}),
        "plate": {"w": plate_w, "h": plate_h},
        "tile": {"w": TILE_W, "h": tile_h},
        "strip": {"cols": STRIP_COLS, "rows": rows,
                  "w": strip.size[0], "h": strip.size[1]},
    }


def main() -> int:
    if not OUTPUTS.is_dir():
        print("outputs/ not found — nothing to derive", file=sys.stderr)
        return 1

    # Every saved report, the members of five-video sets included: the same list
    # the server's live manifest reads.
    reports = report_files()
    wanted: dict[str, set[int]] = {}
    windows: dict[str, set[int]] = {}
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        video_id = video_id_of(report)
        if video_id is None:
            print(f"  {path.name}: no video id in video_url — skipped", file=sys.stderr)
            continue
        wanted.setdefault(video_id, set()).update(midpoint_seconds(report))
        windows.setdefault(video_id, set()).update(window_seconds(report))

    if FRAMES_OUT.exists():
        shutil.rmtree(FRAMES_OUT)
    FRAMES_OUT.mkdir(parents=True)

    print(f"Deriving imagery for {len(wanted)} videos from {len(reports)} reports")

    videos: dict[str, dict] = {}
    for video_id in sorted(wanted):
        entry = build_video(video_id, sorted(wanted[video_id]))
        if entry is not None:
            window = build_window(video_id, sorted(windows.get(video_id, set())),
                                  set(entry["seconds"]))
            entry["window_seconds"] = window
            entry["window_width"] = WINDOW_WIDTH
            videos[video_id] = entry
            print(f"  {video_id}: + {len(window)} window frames at {WINDOW_WIDTH}px")

    manifest = {
        "generated_by": "ui_build/build_frames.py",
        "note": (
            "One frame per segment midpoint, derived from data/<video_id>/frames/, "
            "which pipeline/downloader.py extracted at 1 fps from the analysed "
            "video. Nothing here is stock imagery, nothing is generated, and "
            "nothing is fetched from off this machine at page load."
        ),
        "plate_quality": PLATE_QUALITY,
        "videos": videos,
    }
    (FRAMES_OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    total = sum(f.stat().st_size for f in FRAMES_OUT.rglob("*") if f.is_file())
    plates = sum(1 for _ in FRAMES_OUT.rglob("p/*.jpg"))
    print(f"\n{plates} plates, {len(videos)} sprites, {total / 1e6:.1f} MB "
          f"into {FRAMES_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
