"""
fetch_audio.py - audio-only acquisition for the audio-channel benches.

Downloads the bestaudio stream for each bench video and converts it to the exact
format the production pipeline uses: mono 16 kHz signed 16-bit PCM WAV. The
conversion flags are copied from pipeline/downloader.py:extract_audio so the
bench operates on bit-identical input to production.

Output location is data/<video_id>/audio.wav - the pipeline's own convention.
Three consequences, all deliberate:
  * pipeline.downloader.extract_audio() skips extraction when audio.wav exists,
    so a later full run reuses these files rather than re-deriving them;
  * the vocal-emotion bench reads the same paths, so this download happens once
    for both audio channels;
  * re-running this script is free for anything already fetched.

Video is never downloaded. The transcript and vocal channels need no frames, and
downloading ~700 MB of video per item to extract ~25 MB of audio would be waste.

Usage
-----
    python research/transcript_bench/fetch_audio.py
    python research/transcript_bench/fetch_audio.py --only q0aFOxT6TNw,5VMckmQneCk
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_audio")

BENCH_DIR = Path(__file__).resolve().parent
PROJECT = BENCH_DIR.parents[1]
DATA_DIR = PROJECT / "data"
SCREEN_RESULTS = BENCH_DIR / "screen" / "_screen_results.json"
MANIFEST = BENCH_DIR / "_audio_manifest.json"

# Copied verbatim from pipeline/downloader.py:extract_audio. If that changes,
# this must change with it or the bench stops measuring production behaviour.
FFMPEG_AUDIO_ARGS = ["-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1"]


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        raise EnvironmentError(f"{tool} not found on PATH")


def _tool_version(tool: str, args: list[str]) -> str:
    try:
        out = subprocess.run([tool, *args], capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).splitlines()[0][:80]
    except Exception:
        return "unknown"


def fetch_one(url: str, vid: str) -> dict:
    """Download audio and convert to 16 kHz mono WAV. Skips work already done."""
    out_dir = DATA_DIR / vid
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / "audio.wav"

    if wav.is_file() and wav.stat().st_size > 0:
        logger.info("%s: audio.wav present (%.1f MB) - skipping",
                    vid, wav.stat().st_size / 1e6)
        return {"video_id": vid, "url": url, "audio_path": str(wav.relative_to(PROJECT)),
                "size_bytes": wav.stat().st_size, "status": "CACHED"}

    t0 = time.time()
    tmp_tpl = str(out_dir / "_bestaudio.%(ext)s")
    proc = subprocess.run(
        ["yt-dlp", "-f", "bestaudio/best", "--no-warnings", "-o", tmp_tpl, url],
        capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0:
        return {"video_id": vid, "url": url, "status": "DOWNLOAD_FAILED",
                "error": (proc.stderr or "").strip()[-400:]}

    downloaded = [p for p in out_dir.glob("_bestaudio.*") if p.suffix != ".part"]
    if not downloaded:
        return {"video_id": vid, "url": url, "status": "DOWNLOAD_FAILED",
                "error": "yt-dlp reported success but produced no file"}
    src = downloaded[0]

    conv = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), *FFMPEG_AUDIO_ARGS, str(wav)],
        capture_output=True, text=True, timeout=1800,
    )
    src.unlink(missing_ok=True)

    if conv.returncode != 0 or not wav.is_file():
        return {"video_id": vid, "url": url, "status": "CONVERT_FAILED",
                "error": (conv.stderr or "").strip()[-400:]}

    elapsed = time.time() - t0
    logger.info("%s: %.1f MB in %.1fs", vid, wav.stat().st_size / 1e6, elapsed)
    return {"video_id": vid, "url": url, "audio_path": str(wav.relative_to(PROJECT)),
            "size_bytes": wav.stat().st_size, "seconds": round(elapsed, 1),
            "status": "OK"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated video ids to fetch")
    args = ap.parse_args()

    _require("yt-dlp")
    _require("ffmpeg")

    if not SCREEN_RESULTS.is_file():
        logger.error("run screen_videos.py first - %s missing", SCREEN_RESULTS)
        return 1

    rows = json.loads(SCREEN_RESULTS.read_text())
    targets = [r for r in rows if r.get("status") in ("PASS", "NO_CAPTIONS")]
    if args.only:
        want = {v.strip() for v in args.only.split(",")}
        targets = [r for r in targets if r["video_id"] in want]

    logger.info("fetching audio for %d videos into %s", len(targets), DATA_DIR)

    results = []
    for n, r in enumerate(targets, 1):
        logger.info("[%d/%d] %s - %s", n, len(targets), r["video_id"],
                    str(r.get("title"))[:50])
        try:
            results.append(fetch_one(r["url"], r["video_id"]))
        except Exception as exc:
            results.append({"video_id": r["video_id"], "url": r["url"],
                            "status": "ERROR", "error": str(exc)[:300]})

    MANIFEST.write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "yt_dlp_version": _tool_version("yt-dlp", ["--version"]),
        "ffmpeg_version": _tool_version("ffmpeg", ["-version"]),
        "ffmpeg_audio_args": FFMPEG_AUDIO_ARGS,
        "results": results,
    }, indent=2))

    ok = [r for r in results if r["status"] in ("OK", "CACHED")]
    bad = [r for r in results if r["status"] not in ("OK", "CACHED")]
    total_mb = sum(r.get("size_bytes", 0) for r in ok) / 1e6
    print(f"\n{len(ok)}/{len(results)} audio files ready, {total_mb:.0f} MB total")
    for r in bad:
        print(f"  {r['status']:16} {r['video_id']}: {str(r.get('error',''))[:100]}")
    print(f"manifest: {MANIFEST}")
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
