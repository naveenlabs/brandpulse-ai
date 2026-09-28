"""
transcribe_corpus.py - build the transcript-bench segment corpus.

Runs Whisper over every fetched audio file using the exact configuration the
production pipeline uses, so the segments benched here are the segments
production actually produces:

  * model size from pipeline.audio_module.WHISPER_MODEL_SIZE ("base")
  * language="en", fp16=False - copied from audio_module.transcribe_audio
  * pipeline.audio_module._merge_short_segments imported and applied, not
    reimplemented, so the 3.0 s merge behaviour cannot drift from production

Two artefacts are written per video:

  raw/<vid>.json     unmerged Whisper output including avg_logprob and
                     no_speech_prob. Kept so a different merge threshold can be
                     explored later without re-transcribing (transcription is
                     the expensive step; re-running it would also risk a
                     different result and break comparability).
  corpus/<vid>.json  merged segments in the production schema, plus the
                     transcription-quality fields the bench needs.

Why avg_logprob is carried through
----------------------------------
CANDIDATE_MODELS.md threat 3: Whisper's own errors are confounded with sentiment
errors. A segment the transcriber was unsure about may be misread by every
candidate for reasons that have nothing to do with sentiment. Carrying Whisper's
confidence lets the analysis report accuracy both overall and restricted to
confidently-transcribed segments, which separates the two error sources instead
of silently conflating them.

Usage
-----
    python research/transcript_bench/transcribe_corpus.py
    python research/transcript_bench/transcribe_corpus.py --only haWvrSliMVY --force
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
PROJECT = BENCH_DIR.parents[1]
sys.path.insert(0, str(PROJECT))

from pipeline.audio_module import (  # noqa: E402
    WHISPER_MODEL_SIZE,
    _get_whisper,
    _merge_short_segments,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("transcribe")

DATA_DIR = PROJECT / "data"
RAW_DIR = BENCH_DIR / "raw"
CORPUS_DIR = BENCH_DIR / "corpus"
AUDIO_MANIFEST = BENCH_DIR / "_audio_manifest.json"
SCREEN_RESULTS = BENCH_DIR / "screen" / "_screen_results.json"
CORPUS_MANIFEST = BENCH_DIR / "_corpus_manifest.json"

MERGE_MIN_DURATION = 3.0  # matches audio_module.build_audio_channel


def transcribe_one(vid: str, audio_path: Path, force: bool) -> dict:
    raw_path = RAW_DIR / f"{vid}.json"

    if raw_path.is_file() and not force:
        logger.info("%s: cached transcript - reusing", vid)
        raw = json.loads(raw_path.read_text())
    else:
        model = _get_whisper()
        logger.info("%s: transcribing with Whisper (%s)...", vid, WHISPER_MODEL_SIZE)
        t0 = time.time()
        result = model.transcribe(str(audio_path), language="en", verbose=False, fp16=False)
        elapsed = time.time() - t0

        raw = {
            "video_id": vid,
            "whisper_model": WHISPER_MODEL_SIZE,
            "transcribe_seconds": round(elapsed, 1),
            "audio_seconds": None,
            "segments": [
                {
                    "id": int(s["id"]),
                    "start": float(s["start"]),
                    "end": float(s["end"]),
                    "text": s["text"].strip(),
                    "avg_logprob": float(s.get("avg_logprob", 0.0)),
                    "no_speech_prob": float(s.get("no_speech_prob", 0.0)),
                    "compression_ratio": float(s.get("compression_ratio", 0.0)),
                }
                for s in result.get("segments", [])
            ],
        }
        if raw["segments"]:
            raw["audio_seconds"] = round(raw["segments"][-1]["end"], 1)
        raw_path.write_text(json.dumps(raw, indent=2))
        logger.info("%s: %d raw segments in %.0fs", vid, len(raw["segments"]), elapsed)

    if not raw["segments"]:
        logger.warning("%s: zero segments - silent or non-speech audio", vid)
        return {"video_id": vid, "status": "NO_SPEECH", "raw_segments": 0, "segments": 0}

    # Production schema, then production merge.
    pipeline_form = [
        {
            "segment_id": s["id"],
            "start_time": s["start"],
            "end_time": s["end"],
            "text": s["text"],
        }
        for s in raw["segments"]
    ]
    merged = _merge_short_segments(pipeline_form, min_duration=MERGE_MIN_DURATION)

    # Re-attach transcription quality. A merged segment absorbs several raw ones,
    # so its confidence is the duration-weighted mean of its constituents and its
    # no_speech_prob is the worst (highest) of them - the pessimistic choice,
    # because one silent stretch is enough to make the text unreliable.
    for seg in merged:
        parts = [s for s in raw["segments"]
                 if s["start"] >= seg["start_time"] - 1e-6 and s["end"] <= seg["end_time"] + 1e-6]
        if not parts:
            parts = [min(raw["segments"], key=lambda s: abs(s["start"] - seg["start_time"]))]
        weights = [max(s["end"] - s["start"], 1e-6) for s in parts]
        total_w = sum(weights)
        seg["duration"] = round(seg["end_time"] - seg["start_time"], 2)
        seg["raw_segment_count"] = len(parts)
        seg["avg_logprob"] = round(
            sum(s["avg_logprob"] * w for s, w in zip(parts, weights)) / total_w, 4)
        seg["no_speech_prob"] = round(max(s["no_speech_prob"] for s in parts), 4)
        seg["word_count"] = len(seg["text"].split())

    out = {
        "video_id": vid,
        "whisper_model": raw["whisper_model"],
        "merge_min_duration": MERGE_MIN_DURATION,
        "transcribe_seconds": raw.get("transcribe_seconds"),
        "audio_seconds": raw.get("audio_seconds"),
        "raw_segment_count": len(raw["segments"]),
        "segment_count": len(merged),
        "segments": merged,
    }
    (CORPUS_DIR / f"{vid}.json").write_text(json.dumps(out, indent=2))

    durs = [s["duration"] for s in merged]
    mins = (raw.get("audio_seconds") or 0) / 60 or 1
    return {
        "video_id": vid,
        "status": "OK",
        "raw_segments": len(raw["segments"]),
        "segments": len(merged),
        "audio_min": round(mins, 1),
        "segments_per_min": round(len(merged) / mins, 1),
        "median_dur": round(statistics.median(durs), 1),
        "max_dur": round(max(durs), 1),
        "words": sum(s["word_count"] for s in merged),
        "transcribe_seconds": raw.get("transcribe_seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated video ids")
    ap.add_argument("--force", action="store_true", help="re-transcribe even if cached")
    args = ap.parse_args()

    if not AUDIO_MANIFEST.is_file():
        logger.error("run fetch_audio.py first - %s missing", AUDIO_MANIFEST)
        return 1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(AUDIO_MANIFEST.read_text())
    targets = [r for r in manifest["results"] if r.get("status") in ("OK", "CACHED")]
    if args.only:
        want = {v.strip() for v in args.only.split(",")}
        targets = [r for r in targets if r["video_id"] in want]

    titles = {}
    if SCREEN_RESULTS.is_file():
        titles = {r["video_id"]: r for r in json.loads(SCREEN_RESULTS.read_text())
                  if r.get("video_id")}

    logger.info("transcribing %d videos with Whisper '%s'", len(targets), WHISPER_MODEL_SIZE)
    rows = []
    t_start = time.time()
    for n, r in enumerate(targets, 1):
        vid = r["video_id"]
        logger.info("[%d/%d] %s", n, len(targets), vid)
        try:
            row = transcribe_one(vid, PROJECT / r["audio_path"], args.force)
        except Exception as exc:
            logger.exception("%s failed", vid)
            row = {"video_id": vid, "status": "ERROR", "error": str(exc)[:300]}
        meta = titles.get(vid, {})
        row["channel"] = meta.get("channel")
        row["title"] = meta.get("title")
        rows.append(row)

    CORPUS_MANIFEST.write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "whisper_model": WHISPER_MODEL_SIZE,
        "merge_min_duration": MERGE_MIN_DURATION,
        "wall_seconds": round(time.time() - t_start, 1),
        "videos": rows,
    }, indent=2))

    ok = [r for r in rows if r["status"] == "OK"]
    print(f"\n{'video_id':13} {'min':>5} {'raw':>5} {'segs':>5} {'s/min':>6} "
          f"{'med_s':>6} {'max_s':>6} {'words':>6}  channel")
    print("-" * 96)
    for r in sorted(ok, key=lambda x: -x["segments_per_min"]):
        print(f"{r['video_id']:13} {r['audio_min']:>5} {r['raw_segments']:>5} "
              f"{r['segments']:>5} {r['segments_per_min']:>6} {r['median_dur']:>6} "
              f"{r['max_dur']:>6} {r['words']:>6}  {str(r['channel'])[:24]}")
    if ok:
        print("-" * 96)
        print(f"{'TOTAL':13} {sum(r['audio_min'] for r in ok):>5.0f} "
              f"{sum(r['raw_segments'] for r in ok):>5} {sum(r['segments'] for r in ok):>5} "
              f"{'':>6} {'':>6} {'':>6} {sum(r['words'] for r in ok):>6}")
    for r in rows:
        if r["status"] != "OK":
            print(f"  {r['status']}: {r['video_id']} {str(r.get('error',''))[:90]}")
    print(f"\nmanifest: {CORPUS_MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
