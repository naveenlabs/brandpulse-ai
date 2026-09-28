"""
frame_cache.py — derive the interface's imagery for any report, not only the
videos that happened to be built before the interface shipped.

Why this exists
---------------
`ui_build/build_frames.py` derives the report page's imagery ahead of time and
writes it into `interface/ui/public/frames/`, which `npm run build` copies into
`interface/static/`. That covers the videos whose reports ship with the
repository, and it is the right mechanism for those: the built copy in
`interface/static/frames/` is committed, so a fresh clone with an empty `data/`
still shows the frames the pipeline actually read.

It cannot cover a video analysed *after* that build, which is every video a new
user analyses. Before this module, such a report rendered with the absence hatch
in every frame slot — a drawing that says "the facial channel saw nothing here",
which is a claim about the data. It was in fact a claim about the build, and
those two must never be confused (`ui/src/lib/frames.js` states the same rule).

So the same derivation is available at run time, from the same source frames,
with the same sizes and quality settings. Three layers, in order of preference:

  1. Pre-built and committed, via `build_frames.py`. Fast, survives an empty
     `data/`, and is what a grader sees for the shipped reports.
  2. Warmed at the end of an analysis run, by `warm()`. About 30 s on top of a
     4-9 minute pipeline, so the report is ready before anyone opens it.
  3. Derived per image on request, by `derive()`. Catches anything the first two
     missed — a report copied in by hand, a build that wiped `static/`, a run
     interrupted between saving the report and warming its frames.

The manifest is computed rather than read (`live_manifest()`), so it can never
disagree with what is actually on disk. `build_frames.py` remains the tool for
producing committed imagery and is unchanged.

Beyond that committed set, `interface/static/frames/` is a cache, not a store.
`npm run build` empties the whole of `interface/static/`, so imagery warmed
there is deleted on the next build and only the set built into
`interface/ui/public/frames/` comes back. That is not a defect and needs no fix: `_entry()` offers a second when the derived file exists **or** the 1 fps
source is still in `data/`, so the manifest keeps offering those seconds and
`derive()` reproduces each one, byte-identical, on the request that asks for it.
Observed while a real sweep ran: a warmed video sat at 3 plates of 182 after
several rebuilds, and the page drew all 182 regardless. What must never happen is
the opposite — the manifest advertising a second whose source is also gone, which
is why the two conditions are ORed rather than the derived file being trusted
alone.

A note on sizes: `ui_build/build_frames.py` imports every size and quality
below, and the report readers, from this module, so the two paths cannot
disagree. The dependency runs that way only: `ui_build/` is a build-time script
directory, not a package, and a Flask process must not depend on it.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
SERVED = ROOT / "interface" / "static" / "frames"

# ── Derivation parameters — ui_build/build_frames.py imports these ───────────
# An image derived here and one derived there are the same image; a report does
# not change appearance depending on which path produced its frames.
PLATE_WIDTH = 1440
PLATE_QUALITY = 76
WINDOW_WIDTH = 560
WINDOW_QUALITY = 70

# The HERO size, for a frame drawn full-bleed on a 2x display: a plate is sized
# for a ~760 CSS px panel and would be a nine-fold upscale there. No page draws
# one at present (the opening page's full-bleed frame was retired with
# gl/strata.js), so none is requested; the size is still derived on request and
# by build_frames.py, and the heroes are left out of git (.gitignore).
HERO_WIDTH = 2560
HERO_QUALITY = 82

# The sprite sheet: one 320px tile per segment midpoint, eight to a row. The
# report page's filmstrip currently draws from individual plates rather than
# from this, but the manifest declares it and `test_ui_documents.py` requires
# every declared video to have one, so a video warmed here must end up as
# complete as one the builder produced (build_frames.py imports these).
# Raised from 320 with the fifth interface. The tile is no longer only a
# thumbnail under a pinned timeline: the opening page scrubs it full-bleed, and
# 320 px across 2880 device px was a nine-fold upscale that looked like mush.
# 480 keeps the largest sheet in the corpus (165 seconds, 21 rows) at
# 3840x5040, inside the 8192 px texture limit every GPU here reports.
TILE_W = 480
STRIP_COLS = 8
STRIP_QUALITY = 70
STRIP_BG = (10, 11, 16)

_SIZES = {
    "p": (PLATE_WIDTH, PLATE_QUALITY),
    "w": (WINDOW_WIDTH, WINDOW_QUALITY),
    "h": (HERO_WIDTH, HERO_QUALITY),
}

_VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_\-]{11})")

# Guards against two requests deriving the same image at once, which would have
# them writing the same path concurrently. Per-process, which is all a
# single-process local prototype needs.
_derive_lock = threading.Lock()


# ── Reading a report ─────────────────────────────────────────────────────────

def video_id_of(report: dict) -> str | None:
    """The eleven-character YouTube id in a report's `video_url`, or None."""
    match = _VIDEO_ID.search(str(report.get("video_url", "")))
    return match.group(1) if match else None


def midpoint_seconds(report: dict) -> list[int]:
    """
    The whole second at the midpoint of every segment, in time order.

    Midpoint rather than start, because `pool_emotions_per_segment` pools the
    frames across the whole window (a majority label, a mean confidence), so the
    start frame is no more representative of the reading than any other -- and
    on a merged short segment the start frame can precede the speech the
    segment is actually about.
    """
    seconds: list[int] = []
    for segment in report.get("all_segments", []):
        start, end = segment.get("start_s"), segment.get("end_s")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        seconds.append(int((float(start) + float(end)) / 2))
    return seconds


def window_seconds(report: dict) -> list[int]:
    """
    Every whole second inside a FLAGGED segment.

    The report page can show the full run of frames a contested reading was
    pooled over, because "there is no face in any of them" is a claim the reader
    has to be able to check rather than take on trust. Only flagged segments,
    because that keeps the set bounded.
    """
    seconds: list[int] = []
    for segment in report.get("all_segments", []):
        if not segment.get("flagged"):
            continue
        start, end = segment.get("start_s"), segment.get("end_s")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        seconds.extend(range(int(start), int(end) + 1))
    return seconds


# ── Locating and deriving one image ──────────────────────────────────────────

def source_frame(video_id: str, second: int) -> Path | None:
    """
    The 1 fps frame for a whole second, or None when it was never extracted.

    `downloader.py` names them `frame_0000.jpg` upward, the number being the
    second. A segment midpoint can land one frame past the end of a video whose
    duration was not whole, so a miss here is expected and not an error.
    """
    candidate = DATA / video_id / "frames" / f"frame_{second:04d}.jpg"
    return candidate if candidate.is_file() else None


def derived_path(video_id: str, kind: str, second: int) -> Path:
    """Where a derived image is served from. `kind` is "p", "w" or "h"."""
    return SERVED / video_id / kind / f"{second}.jpg"


def derive(video_id: str, kind: str, second: int) -> Path | None:
    """
    Produce one derived image, or return None when its source does not exist.

    Returns the existing file immediately when it has already been derived, so
    this is safe to call on every request. Writes to a temporary name and
    renames into place, so an interrupted derivation cannot leave a truncated
    JPEG that would then be served forever as though it were valid.
    """
    if kind not in _SIZES:
        return None

    out = derived_path(video_id, kind, second)
    if out.is_file():
        return out

    source = source_frame(video_id, second)
    if source is None:
        return None

    from PIL import Image  # imported lazily: only a derivation needs Pillow

    width, quality = _SIZES[kind]
    with _derive_lock:
        if out.is_file():           # another thread won the race while we waited
            return out
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".jpg.tmp")
        try:
            with Image.open(source) as image:
                image = image.convert("RGB")
                ratio = image.height / image.width
                image.resize(
                    (width, max(1, round(width * ratio))), Image.LANCZOS
                ).save(
                    tmp, "JPEG", quality=quality, optimize=True, progressive=True
                )
            tmp.replace(out)
        except Exception:
            tmp.unlink(missing_ok=True)
            logger.exception("frame_cache: could not derive %s/%s/%s",
                             video_id, kind, second)
            return None
    return out


# ── Warming a whole video ────────────────────────────────────────────────────

def strip_path(video_id: str) -> Path:
    """Where a video's sprite sheet is served from."""
    return SERVED / video_id / "strip.jpg"


def build_strip(video_id: str, seconds: list[int]) -> dict | None:
    """
    The sprite sheet for one video, or None when no source frame exists.

    Built from the same 1 fps frames as the plates, at TILE_W, eight to a row.
    Returns the geometry the manifest declares so a reader of the manifest can
    address a tile without opening the image.

    Skipped when the file already exists: this is the expensive part of warming
    a video and it does not change once written.
    """
    out = strip_path(video_id)
    sources = [(s, source_frame(video_id, s)) for s in sorted(set(seconds))]
    sources = [(s, p) for s, p in sources if p is not None]
    if not sources:
        return None

    rows = (len(sources) + STRIP_COLS - 1) // STRIP_COLS
    from PIL import Image

    with _derive_lock:
        if out.is_file():
            try:
                with Image.open(out) as existing:
                    tile_h = existing.height // rows if rows else 0
                    return {"cols": STRIP_COLS, "rows": rows,
                            "w": existing.width, "h": existing.height,
                            "tile": {"w": TILE_W, "h": tile_h}}
            except Exception:
                logger.debug("frame_cache: unreadable sprite %s, rebuilding", out,
                             exc_info=True)

        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".jpg.tmp")
        try:
            tiles = []
            tile_h = 0
            for _, source in sources:
                with Image.open(source) as image:
                    image = image.convert("RGB")
                    tile_h = max(1, round(TILE_W * image.height / image.width))
                    tiles.append(image.resize((TILE_W, tile_h), Image.LANCZOS))
            sheet = Image.new("RGB", (TILE_W * STRIP_COLS, tile_h * rows), STRIP_BG)
            for index, tile in enumerate(tiles):
                sheet.paste(tile, ((index % STRIP_COLS) * TILE_W,
                                   (index // STRIP_COLS) * tile_h))
                tile.close()
            sheet.save(tmp, "JPEG", quality=STRIP_QUALITY, optimize=True,
                       progressive=True)
            tmp.replace(out)
            return {"cols": STRIP_COLS, "rows": rows,
                    "w": sheet.size[0], "h": sheet.size[1],
                    "tile": {"w": TILE_W, "h": tile_h}}
        except Exception:
            tmp.unlink(missing_ok=True)
            logger.exception("frame_cache: could not build the sprite for %s", video_id)
            return None


def warm(report: dict) -> int:
    """
    Derive every image one report needs, and return how many were produced.

    Called at the end of an analysis run, where roughly 30 seconds on top of a
    4-9 minute pipeline is not worth optimising and guarantees the report is
    complete the first time it is opened. Never raises: imagery is not worth
    failing a finished analysis over, and `derive()` remains as the fallback.

    The sprite is built last, so an interruption costs the cheap artefact rather
    than the expensive one, and so a partially warmed video still serves every
    plate it managed to derive.
    """
    video_id = video_id_of(report)
    if video_id is None or not (DATA / video_id / "frames").is_dir():
        return 0

    plates = set(midpoint_seconds(report))
    made = 0
    try:
        for second in sorted(plates):
            if derive(video_id, "p", second) is not None:
                made += 1
        for second in sorted(set(window_seconds(report)) - plates):
            if derive(video_id, "w", second) is not None:
                made += 1
        if build_strip(video_id, sorted(plates)) is not None:
            made += 1
    except Exception:
        logger.exception("frame_cache: warming %s stopped early", video_id)
    return made


# ── The manifest ─────────────────────────────────────────────────────────────

def _entry(video_id: str, wanted: set[int], windows_wanted: set[int]) -> dict | None:
    """
    One manifest entry, listing only seconds that will actually resolve.

    A second is listed when its image has already been derived, or when the 1 fps
    source frame is on disk and `derive()` can therefore produce it on request.
    Anything else is omitted, which is what makes the page draw the absence
    hatch — the one rule `frames.js` states: never offer a URL for a frame that
    does not exist, because a broken image reads as a claim about the data.

    `wanted` and `windows_wanted` are unions across every report of this video,
    because several reports can share one video — six of the nine shipped
    reports are runs of `1VjPETN3m6U` — and they do not flag the same segments.
    Taking one report's seconds would hide window frames that exist on disk.
    """
    def resolvable(kind: str, second: int) -> bool:
        return (derived_path(video_id, kind, second).is_file()
                or source_frame(video_id, second) is not None)

    plates = sorted(s for s in wanted if resolvable("p", s))
    if not plates:
        return None

    seen = set(plates)
    windows = sorted(s for s in windows_wanted
                     if s not in seen and resolvable("w", s))

    entry: dict = {"seconds": plates,
                   "window_seconds": windows,
                   "window_width": WINDOW_WIDTH}

    # The hero, on the same terms as everything else here: a second is offered
    # only when the image is already derived, or the 1 fps source frame is on
    # disk for `derive()` to make it from. Heroes are deliberately NOT pre-built
    # for every video -- that came to 131 MB across six videos, when the opening
    # page draws one -- so most of these resolve through the on-demand path the
    # first time they are asked for, and are cached to disk from then on.
    heroes = sorted(s for s in plates if resolvable("h", s))
    if heroes:
        hero_entry: dict = {"seconds": heroes, "w": HERO_WIDTH, "h": 0}
        sample_hero = next((derived_path(video_id, "h", s) for s in heroes
                            if derived_path(video_id, "h", s).is_file()), None)
        if sample_hero is not None:
            try:
                from PIL import Image
                with Image.open(sample_hero) as image:
                    hero_entry["w"] = image.width
                    hero_entry["h"] = image.height
            except Exception:
                logger.debug("frame_cache: could not size %s", sample_hero,
                             exc_info=True)
        entry["hero"] = hero_entry

    # Plate geometry, read from a real derived file where one exists. The report
    # page uses it only for aspect ratio, and videos here are 16:9, but it is
    # measured rather than assumed so a differently shaped source stays correct.
    sample = next((derived_path(video_id, "p", s) for s in plates
                   if derived_path(video_id, "p", s).is_file()), None)
    if sample is not None:
        try:
            from PIL import Image
            with Image.open(sample) as image:
                entry["plate"] = {"w": image.width, "h": image.height}
        except Exception:
            logger.debug("frame_cache: could not size %s", sample, exc_info=True)

    # The sprite is declared only when the file is actually on disk, for the same
    # reason a second is: the manifest must never advertise something a request
    # would 404 on. A video warmed but not yet stripped simply has no `strip`,
    # and `frames.js:stripInfo` already returns null for that case.
    strip = strip_path(video_id)
    if strip.is_file():
        rows = (len(plates) + STRIP_COLS - 1) // STRIP_COLS
        try:
            from PIL import Image
            with Image.open(strip) as sheet:
                entry["tile"] = {"w": TILE_W,
                                 "h": (sheet.height // rows) if rows else 0}
                entry["strip"] = {"cols": STRIP_COLS, "rows": rows,
                                  "w": sheet.width, "h": sheet.height}
        except Exception:
            logger.debug("frame_cache: could not size %s", strip, exc_info=True)
    return entry


def report_files() -> list[Path]:
    """
    Every report on this machine: the single runs, and every sweep member.

    `outputs/*.json` does not recurse, which is exactly why sweeps were put
    under `outputs/sweeps/` — it keeps them out of `extract_figures.py` and out
    of the corpus figures the final report quotes. The manifest is the one place
    that has to see both: a sweep member's frames are derived by `warm()` like
    any other report's, and a manifest that did not list them would have the
    combined page draw the absence hatch over frames that are on disk. That is
    the same defect this module was written to remove, one directory deeper.
    """
    files = sorted(OUTPUTS.glob("*.json"))
    sweeps = OUTPUTS / "sweeps"
    if sweeps.is_dir():
        files += sorted(sweeps.glob("*/members/*.json"))
    return files


def live_manifest() -> dict:
    """
    Build the manifest from what is on disk right now.

    Computed rather than stored, for the reason `/evidence/figures.json` is
    served rather than copied: one source of truth, with no second copy that can
    drift. A report saved thirty seconds ago appears here without a rebuild.
    """
    # Union every report's seconds per video before resolving any of them, for
    # the reason given in _entry: reports share videos and flag different
    # segments, so one report's view of a video is incomplete.
    wanted: dict[str, set[int]] = {}
    windows: dict[str, set[int]] = {}
    if OUTPUTS.is_dir():
        for path in report_files():
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                logger.warning("frame_cache: could not read %s", path.name)
                continue
            video_id = video_id_of(report)
            if video_id is None:
                continue
            wanted.setdefault(video_id, set()).update(midpoint_seconds(report))
            windows.setdefault(video_id, set()).update(window_seconds(report))

    videos: dict[str, dict] = {}
    for video_id in sorted(wanted):
        entry = _entry(video_id, wanted[video_id], windows.get(video_id, set()))
        if entry is not None:
            videos[video_id] = entry

    return {
        "generated_by": "frame_cache.live_manifest()",
        "note": (
            "Computed at request time from outputs/ and the 1 fps frames "
            "pipeline/downloader.py extracted into data/<video_id>/frames/. A "
            "second is listed only when its image exists or can be derived from "
            "a frame on disk. Nothing here is stock imagery, nothing is "
            "generated, and nothing is fetched from off this machine."
        ),
        "plate_quality": PLATE_QUALITY,
        "videos": videos,
    }
