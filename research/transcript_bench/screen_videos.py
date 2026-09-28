"""
screen_videos.py - pre-download suitability screen for the transcript bench.

Why this exists
---------------
The twelve videos in comment_bench/v2/ were selected for *comment volume*. This
channel needs something different: continuous human speech. PROTOTYPE_FINDINGS
already shows what happens when that assumption fails - the Nike video yielded
2.1 segments/min against Samsung's 10.1, and one single 211-second "segment"
that no sentiment label can honestly describe.

Downloading twelve videos to discover that is wasteful. YouTube publishes
caption tracks, and those are a few kilobytes each. This script fetches metadata
and captions only, and derives three speech-density measures that predict
segment yield before a single byte of audio is downloaded.

Measures
--------
words_per_min    Speech rate. Talking-head review content typically runs
                 130-180 wpm. Advertising with music runs far lower.
speech_coverage  Union of caption cue intervals divided by video duration.
                 How much of the runtime actually contains speech.
max_gap_s        Longest continuous stretch with no caption cue. A proxy for
                 the monster-segment failure: Whisper splits on pauses, so a
                 long speechless stretch is what produces an unratable segment.

Caching: every network result is written to screen/ and reused.

Usage
-----
    python research/transcript_bench/screen_videos.py
    python research/transcript_bench/screen_videos.py --urls-file some_list.txt
    python research/transcript_bench/screen_videos.py --refresh
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("screen")

BENCH_DIR = Path(__file__).resolve().parent
SCREEN_DIR = BENCH_DIR / "screen"
COMMENT_BENCH = BENCH_DIR.parent / "comment_bench" / "v2"

DEFAULT_LISTS = [COMMENT_BENCH / "videos.txt", COMMENT_BENCH / "videos_holdout.txt"]

# Thresholds. Derived from this project's own measured data, not from literature:
# Samsung 10.1 seg/min and Apple 8.1 seg/min were usable; Nike at 2.1 seg/min was
# not. These cut-offs are set to separate those observed cases with margin, and
# are recorded here so the decision is reproducible rather than eyeballed.
MIN_WORDS_PER_MIN = 90.0
MIN_SPEECH_COVERAGE = 0.55
MAX_ACCEPTABLE_GAP_S = 45.0


def read_urls(list_paths: list[Path]) -> list[str]:
    """Read one-URL-per-line files, ignoring blanks and # comments."""
    urls: list[str] = []
    for p in list_paths:
        if not p.is_file():
            logger.warning("list not found, skipping: %s", p)
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url)
    if not m:
        raise ValueError(f"cannot extract video id from {url!r}")
    return m.group(1)


def fetch_metadata(url: str, vid: str, refresh: bool) -> dict:
    """yt-dlp -J, cached to screen/<vid>_meta.json."""
    cache = SCREEN_DIR / f"{vid}_meta.json"
    if cache.is_file() and not refresh:
        return json.loads(cache.read_text())

    proc = subprocess.run(
        ["yt-dlp", "-J", "--skip-download", "--no-warnings", url],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        return {"_error": (proc.stderr or "yt-dlp failed").strip()[:300]}

    full = json.loads(proc.stdout)
    # Keep only what the screen needs. The full dump is megabytes of format lists
    # and carries uploader identifiers we have no reason to retain.
    slim = {
        "id": full.get("id"),
        "title": full.get("title"),
        "channel": full.get("channel"),
        "duration": full.get("duration"),
        "language": full.get("language"),
        "categories": full.get("categories"),
        "has_manual_en": any(k.startswith("en") for k in (full.get("subtitles") or {})),
        "auto_en_keys": [k for k in (full.get("automatic_captions") or {}) if k.startswith("en")],
    }
    cache.write_text(json.dumps(slim, indent=2))
    return slim


def fetch_captions(url: str, vid: str, prefer_manual: bool, refresh: bool) -> Path | None:
    """Download the English caption track as VTT. Returns the file path or None."""
    existing = sorted(SCREEN_DIR.glob(f"{vid}.*.vtt"))
    if existing and not refresh:
        return existing[0]

    flag = "--write-subs" if prefer_manual else "--write-auto-subs"
    proc = subprocess.run(
        ["yt-dlp", "--skip-download", flag, "--sub-langs", "en.*,en",
         "--sub-format", "vtt", "--no-warnings",
         "-o", str(SCREEN_DIR / f"{vid}.%(ext)s"), url],
        capture_output=True, text=True, timeout=180,
    )
    found = sorted(SCREEN_DIR.glob(f"{vid}.*.vtt"))
    if not found and prefer_manual:
        return fetch_captions(url, vid, prefer_manual=False, refresh=refresh)
    if not found:
        logger.warning("no captions for %s: %s", vid, (proc.stderr or "")[:160])
        return None
    return found[0]


_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
_TAG = re.compile(r"<[^>]+>")


def _secs(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: Path) -> tuple[list[tuple[float, float]], int]:
    """
    Return (cue intervals, unique word count).

    Auto-captions repeat text across rolling cues, so words are counted from the
    de-duplicated set of cue lines rather than from every line, which would
    inflate the count roughly twofold.
    """
    intervals: list[tuple[float, float]] = []
    seen_lines: set[str] = set()
    words = 0

    lines = path.read_text(errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = _TS.search(lines[i])
        if not m:
            i += 1
            continue
        start = _secs(*m.groups()[:4])
        end = _secs(*m.groups()[4:])
        if end > start:
            intervals.append((start, end))
        i += 1
        while i < len(lines) and lines[i].strip() and not _TS.search(lines[i]):
            text = _TAG.sub("", lines[i]).strip()
            if text and text not in seen_lines:
                seen_lines.add(text)
                words += len(text.split())
            i += 1
    return intervals, words


def merge(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Union of overlapping cue intervals - rolling captions overlap heavily."""
    if not intervals:
        return []
    out = [list(x) for x in sorted(intervals)]
    merged = [out[0]]
    for s, e in out[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(a, b) for a, b in merged]


def screen_one(url: str, refresh: bool) -> dict:
    vid = video_id(url)
    meta = fetch_metadata(url, vid, refresh)
    row: dict = {"video_id": vid, "url": url}

    if "_error" in meta:
        return {**row, "status": "UNAVAILABLE", "reason": meta["_error"]}

    row.update({
        "title": meta.get("title"),
        "channel": meta.get("channel"),
        "duration_s": meta.get("duration"),
        "language": meta.get("language"),
        "categories": meta.get("categories"),
    })

    vtt = fetch_captions(url, vid, prefer_manual=meta.get("has_manual_en", False), refresh=refresh)
    if vtt is None:
        return {**row, "status": "NO_CAPTIONS",
                "reason": "no English caption track; cannot screen without downloading"}

    intervals, words = parse_vtt(vtt)
    dur = float(meta.get("duration") or 0)
    if dur <= 0 or not intervals:
        return {**row, "status": "NO_CAPTIONS", "reason": "empty caption track or unknown duration"}

    merged = merge(intervals)
    speech_s = sum(e - s for s, e in merged)

    gaps = [merged[0][0]] + [merged[k + 1][0] - merged[k][1] for k in range(len(merged) - 1)]
    gaps.append(max(0.0, dur - merged[-1][1]))

    row.update({
        "caption_kind": "manual" if meta.get("has_manual_en") else "auto",
        "words": words,
        "words_per_min": round(words / (dur / 60), 1),
        "speech_coverage": round(speech_s / dur, 3),
        "max_gap_s": round(max(gaps), 1),
    })

    fails = []
    if row["words_per_min"] < MIN_WORDS_PER_MIN:
        fails.append(f"speech rate {row['words_per_min']} wpm < {MIN_WORDS_PER_MIN}")
    if row["speech_coverage"] < MIN_SPEECH_COVERAGE:
        fails.append(f"speech coverage {row['speech_coverage']:.0%} < {MIN_SPEECH_COVERAGE:.0%}")
    if row["max_gap_s"] > MAX_ACCEPTABLE_GAP_S:
        fails.append(f"longest speechless gap {row['max_gap_s']}s > {MAX_ACCEPTABLE_GAP_S}s")
    if (meta.get("language") or "en") and not str(meta.get("language") or "en").startswith("en"):
        fails.append(f"language is {meta.get('language')}, corpus is English")

    row["status"] = "PASS" if not fails else "FAIL"
    row["reason"] = "; ".join(fails) if fails else "continuous English speech"
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urls-file", type=Path, action="append",
                    help="video list file; repeatable. Defaults to both comment-bench lists.")
    ap.add_argument("--refresh", action="store_true", help="ignore cache and refetch")
    ap.add_argument("--out", type=Path, default=BENCH_DIR / "screen" / "_screen_results.json")
    args = ap.parse_args()

    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    lists = args.urls_file or DEFAULT_LISTS
    urls = read_urls(lists)
    if not urls:
        logger.error("no URLs found in %s", lists)
        return 1

    logger.info("screening %d videos (metadata + captions only, no audio)", len(urls))
    rows = []
    for n, url in enumerate(urls, 1):
        logger.info("[%d/%d] %s", n, len(urls), url)
        try:
            rows.append(screen_one(url, args.refresh))
        except Exception as exc:
            rows.append({"url": url, "status": "ERROR", "reason": str(exc)[:200]})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2))

    print(f"\n{'video_id':13} {'st':4} {'min':>5} {'wpm':>6} {'cov':>5} {'gap':>6}  channel / title")
    print("-" * 108)
    for r in rows:
        st = {"PASS": "OK", "FAIL": "FAIL", "NO_CAPTIONS": "?", "UNAVAILABLE": "GONE"}.get(r["status"], "ERR")
        dur = f"{(r.get('duration_s') or 0)/60:.1f}" if r.get("duration_s") else "-"
        print(f"{r.get('video_id','-'):13} {st:4} {dur:>5} "
              f"{r.get('words_per_min','-'):>6} {r.get('speech_coverage','-'):>5} "
              f"{r.get('max_gap_s','-'):>6}  {str(r.get('channel'))[:22]:22} {str(r.get('title'))[:36]}")

    npass = sum(1 for r in rows if r["status"] == "PASS")
    print(f"\n{npass}/{len(rows)} pass. Full detail: {args.out}")
    for r in rows:
        if r["status"] != "PASS":
            print(f"  {r['status']:12} {r.get('video_id','-')}: {r.get('reason','')[:88]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
