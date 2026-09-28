#!/usr/bin/env python3
"""
whisper_bench/cut_clips.py - cut the WER evaluation sample from the corpus audio.

Design decisions
----------------
Clips are aligned to existing segment boundaries.
    Whisper cuts on pauses, so segment edges are natural silences. Cutting there
    means no clip starts or ends mid-word, which would otherwise be transcribed
    differently by every model for reasons that have nothing to do with accuracy.

One contiguous clip per video, not scattered sentences.
    The rater types continuously, and surrounding context is what makes an unclear
    word recoverable. Twelve clips across twelve videos also covers all six
    speakers rather than over-weighting whoever happens to talk fastest.

The first 30 seconds of every video is skipped.
    Intros carry music beds and channel idents, which measure a different thing.

Seeded and reproducible: the same seed gives the same clips.

Usage
-----
    python research/whisper_bench/cut_clips.py
    python research/whisper_bench/cut_clips.py --seconds 40 --seed 42
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = Path(__file__).resolve().parent
CORPUS = ROOT / "research" / "transcript_bench" / "corpus"
MANIFEST = ROOT / "research" / "transcript_bench" / "_corpus_manifest.json"
CLIPS = BENCH / "clips"
DATA = ROOT / "data"

SKIP_INTRO_S = 30.0
SEED = 42

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("clips")


def pick_run(segments: list[dict], target_s: float, rng: random.Random) -> list[dict]:
    """Choose a contiguous run of segments totalling at least target_s seconds."""
    eligible = [i for i, s in enumerate(segments) if s["start_time"] >= SKIP_INTRO_S]
    if not eligible:
        raise ValueError("no segments after the intro skip")

    # Only consider starts that leave enough audio to reach the target.
    last_end = segments[-1]["end_time"]
    starts = [i for i in eligible if last_end - segments[i]["start_time"] >= target_s]
    if not starts:
        starts = eligible[:1]

    start = rng.choice(starts)
    run = []
    for seg in segments[start:]:
        run.append(seg)
        if run[-1]["end_time"] - run[0]["start_time"] >= target_s:
            break
    return run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    manifest = {v["video_id"]: v for v in json.loads(MANIFEST.read_text())["videos"]}
    CLIPS.mkdir(exist_ok=True)
    rng = random.Random(args.seed)

    index = []
    for path in sorted(CORPUS.glob("*.json")):
        vid = path.stem
        segments = json.loads(path.read_text())["segments"]
        audio = DATA / vid / "audio.wav"
        if not audio.exists():
            logger.error("%s: audio.wav missing, skipped", vid)
            continue

        run = pick_run(segments, args.seconds, rng)
        start, end = run[0]["start_time"], run[-1]["end_time"]
        out = CLIPS / f"{vid}.wav"

        # Re-encode rather than stream-copy: the sample must be bit-identical in
        # format to what the pipeline feeds Whisper (16 kHz mono PCM).
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(audio), "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(out),
        ]
        subprocess.run(cmd, check=True)

        meta = manifest.get(vid, {})
        index.append({
            "video_id": vid,
            "channel": meta.get("channel", "unknown"),
            "title": meta.get("title", ""),
            "clip_start_s": round(start, 3),
            "clip_end_s": round(end, 3),
            "duration_s": round(end - start, 3),
            "n_segments": len(run),
            "reference_word_count_whisper_base": sum(
                len(s["text"].split()) for s in run
            ),
        })
        logger.info("%s  %5.1fs  %2d segments  (%s)",
                    vid, end - start, len(run), meta.get("channel", "?"))

    total = sum(c["duration_s"] for c in index)
    payload = {
        "seed": args.seed,
        "target_seconds": args.seconds,
        "skip_intro_s": SKIP_INTRO_S,
        "n_clips": len(index),
        "total_seconds": round(total, 1),
        "total_minutes": round(total / 60, 2),
        "clips": index,
    }
    (BENCH / "_clip_index.json").write_text(json.dumps(payload, indent=1))
    logger.info("%d clips, %.1f min total -> %s",
                len(index), total / 60, BENCH / "_clip_index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
