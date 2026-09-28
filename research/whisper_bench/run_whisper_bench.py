#!/usr/bin/env python3
"""
run_whisper_bench.py - transcribe the evaluation clips with every registered checkpoint.

Runs no scoring. Ground truth is typed by a human separately and must not exist yet
for this to be valid, so this script deliberately never reads it. Transcripts are
cached to transcripts/<model>.json and scored later by report_whisper.py.

Disk discipline
---------------
15.34 GB of checkpoints against ~21 GB free. Each model is downloaded, run, and its
weights deleted before the next is fetched, so peak usage stays near 3 GB. Pass
--keep to retain weights (only sensible for the adopted model).

Decoding parameters are pinned to what the pipeline actually uses
(pipeline/audio_module.transcribe): language="en", fp16=False. Anything else would
measure a configuration the project does not run.

Usage
-----
    python research/whisper_bench/run_whisper_bench.py
    python research/whisper_bench/run_whisper_bench.py --only base base.en
    python research/whisper_bench/run_whisper_bench.py --keep --only large-v3
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
CLIPS = BENCH / "clips"
OUT = BENCH / "transcripts"
INDEX = BENCH / "_clip_index.json"

# The 12 unique checkpoints from CANDIDATE_MODELS.md Section 4, in ascending size
# so a disk or time problem surfaces on a cheap model rather than an expensive one.
REGISTRY = [
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "large-v3-turbo",
    "medium", "medium.en",
    "large-v1", "large-v2", "large-v3",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("whisper-bench")


def cache_path(name: str) -> Path:
    import whisper.__init__ as W
    return Path.home() / ".cache" / "whisper" / W._MODELS[name].split("/")[-1]


def free_gb() -> float:
    return shutil.disk_usage("/").free / 1e9


def run_model(name: str, clips: list[dict], keep: bool) -> dict:
    import torch
    import whisper

    out_path = OUT / f"{name}.json"
    if out_path.exists():
        logger.info("%-16s cached, skipping", name)
        return json.loads(out_path.read_text())

    logger.info("%-16s loading (disk free %.1f GB) ...", name, free_gb())
    t0 = time.time()
    model = whisper.load_model(name)
    load_s = time.time() - t0

    n_params = sum(p.numel() for p in model.parameters())
    logger.info("%-16s loaded in %.1fs | %.1fM parameters", name, load_s, n_params / 1e6)

    results, total_audio, total_wall = [], 0.0, 0.0
    for clip in clips:
        wav = CLIPS / f"{clip['video_id']}.wav"
        t0 = time.time()
        # Same call signature as pipeline/audio_module.transcribe().
        r = model.transcribe(str(wav), language="en", fp16=False)
        wall = time.time() - t0

        results.append({
            "video_id": clip["video_id"],
            "channel": clip["channel"],
            "duration_s": clip["duration_s"],
            "wall_s": round(wall, 3),
            "text": r["text"].strip(),
            "n_segments": len(r.get("segments", [])),
            "segments": [
                {"start": round(s["start"], 3), "end": round(s["end"], 3),
                 "text": s["text"].strip()}
                for s in r.get("segments", [])
            ],
        })
        total_audio += clip["duration_s"]
        total_wall += wall
        logger.info("  %-16s %-14s %5.1fs audio in %5.1fs (%.1fx)",
                    name, clip["video_id"], clip["duration_s"], wall,
                    clip["duration_s"] / wall if wall else 0)

    record = {
        "model": name,
        "parameters": n_params,
        "parameters_millions": round(n_params / 1e6, 1),
        "load_seconds": round(load_s, 2),
        "total_audio_s": round(total_audio, 1),
        "total_wall_s": round(total_wall, 1),
        "realtime_factor": round(total_audio / total_wall, 2) if total_wall else None,
        "decode": {"language": "en", "fp16": False},
        "clips": results,
    }
    OUT.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(record, indent=1))
    logger.info("%-16s DONE  %.1fx realtime  -> %s", name, record["realtime_factor"],
                out_path.name)

    # Release before deleting weights, or the file stays mapped.
    del model
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

    if not keep:
        p = cache_path(name)
        if p.exists():
            size = p.stat().st_size / 1e9
            p.unlink()
            logger.info("%-16s weights deleted (%.2f GB freed, %.1f GB free)",
                        name, size, free_gb())
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--keep", action="store_true",
                    help="do not delete weights after running")
    args = ap.parse_args()

    clips = json.loads(INDEX.read_text())["clips"]
    logger.info("%d clips, %.1f min of audio", len(clips),
                sum(c["duration_s"] for c in clips) / 60)

    names = args.only if args.only else REGISTRY
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        logger.error("not in the register: %s", unknown)
        return 2

    failures = []
    for name in names:
        try:
            run_model(name, clips, args.keep)
        except Exception as exc:
            # One dead checkpoint must not abort a 12-model run.
            logger.error("%-16s FAILED: %s: %s", name, type(exc).__name__, exc)
            failures.append((name, f"{type(exc).__name__}: {exc}"))

    if failures:
        logger.warning("%d model(s) failed:", len(failures))
        for n, e in failures:
            logger.warning("  %s - %s", n, e[:160])
    logger.info("completed %d/%d", len(names) - len(failures), len(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
