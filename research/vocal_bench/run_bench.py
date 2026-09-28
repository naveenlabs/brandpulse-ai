"""
run_bench.py - run every candidate over the 150 clips and cache its predictions.

Predictions are cached to predictions/<candidate>.json so scoring, mapping
changes and sensitivity checks never require re-running a model. Re-running is
also the only way to introduce nondeterminism, so caching protects
reproducibility as well as time.

This script does no scoring and never opens the ground truth. Keeping generation
and evaluation in separate processes means a model's output cannot be influenced,
even accidentally, by what the ratings say.

    python research/vocal_bench/run_bench.py                     # all candidates
    python research/vocal_bench/run_bench.py --only audeering-msp-dim
    python research/vocal_bench/run_bench.py --force             # ignore cache
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
CLIPS = BENCH_DIR / "clips"
INDEX = BENCH_DIR / "_clip_index.json"
PRED_DIR = BENCH_DIR / "predictions"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("vocal")


def main() -> int:
    from candidates import REGISTRY

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated candidate names")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    PRED_DIR.mkdir(exist_ok=True)
    clips = sorted(json.loads(INDEX.read_text())["clips"], key=lambda c: c["order"])
    wanted = args.only.split(",") if args.only else list(REGISTRY)

    for name in wanted:
        if name not in REGISTRY:
            logger.error("unknown candidate %r", name)
            return 2
        spec = REGISTRY[name]
        out_path = PRED_DIR / f"{name}.json"
        if out_path.is_file() and not args.force:
            logger.info("%-22s cached - skipping", name)
            continue

        logger.info("%-22s running on %d clips ...", name, len(clips))
        preds, failures, t0 = {}, 0, time.time()
        for i, c in enumerate(clips, 1):
            wav = CLIPS / f"{c['uid']}.wav"
            try:
                preds[c["uid"]] = spec["fn"](wav)
            except Exception as exc:
                # A failing clip is recorded, never silently dropped and never
                # coerced to a neutral guess: graceful degradation must stay
                # visible in the numbers (README, "Engineering rules").
                failures += 1
                logger.warning("  %s failed on %s: %s", name, c["uid"], str(exc)[:120])
                preds[c["uid"]] = {"raw_label": None, "scores": {}, "valence": None,
                                   "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            if i % 50 == 0:
                logger.info("  %d/%d", i, len(clips))

        elapsed = time.time() - t0
        audio_s = sum(c["duration"] for c in clips)
        out_path.write_text(json.dumps({
            "candidate": name,
            "kind": spec["kind"],
            "licence": spec["licence"],
            "note": spec["note"],
            "incumbent": spec.get("incumbent", False),
            "n_clips": len(clips),
            "n_failed": failures,
            "wall_seconds": round(elapsed, 1),
            "audio_seconds": round(audio_s, 1),
            "realtime_factor": round(audio_s / elapsed, 2) if elapsed else None,
            "predictions": preds,
        }, indent=1))
        logger.info("%-22s done in %.0fs (%.1fx realtime), %d failures -> %s",
                    name, elapsed, audio_s / elapsed if elapsed else 0,
                    failures, out_path.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
