"""
run_classify.py — Bench B: which emotion model reads this footage correctly.

Every candidate is run on the **same crop files** written by `run_detect.py
--crops`, so two candidates differing on a segment differ because of the model and
not because they were shown different pixels. That separation is the whole point
of splitting the bench in two (`CANDIDATE_MODELS.md` §1.1).

The full probability distribution is stored for every crop, not just the argmax.
`pipeline/visual_module.py` keeps only `dominant_emotion` and discards the rest;
`CANDIDATE_MODELS.md` §5.2 asks whether anger is present in the distribution and
being thrown away by that choice, and the question is unanswerable without keeping
it.

Caching
-------
One JSON per video and candidate under `predictions/`. Re-running skips finished
work; `--force` redoes it.

Usage
-----
    python research/facial_bench/run_classify.py --video 1VjPETN3m6U
    python research/facial_bench/run_classify.py --video 1VjPETN3m6U --model dan_affectnet8
    python research/facial_bench/run_classify.py --all-videos
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))

import candidates as C                                          # noqa: E402
from run_detect import BENCH_VIDEOS, GROUND_TRUTH_VIDEO         # noqa: E402

CROPS = BENCH / "crops"
PREDICTIONS = BENCH / "predictions"


def crops_for(video_id: str) -> list[Path]:
    d = CROPS / video_id
    return sorted(d.glob("frame_*.jpg")) if d.is_dir() else []


def timestamp_of(crop: Path) -> float:
    import re
    m = re.search(r"frame_(\d+)", crop.stem)
    return float(int(m.group(1))) if m else 0.0


def run_one(video_id: str, model: str, *, force: bool = False,
            limit: int | None = None) -> dict:
    out_path = PREDICTIONS / f"{video_id}__{model}.json"
    if out_path.exists() and not force:
        print(f"  [cached] {video_id} / {model}")
        return json.loads(out_path.read_text())

    from PIL import Image
    import numpy as np

    crops = crops_for(video_id)
    if limit:
        crops = crops[:limit]
    if not crops:
        raise FileNotFoundError(
            f"No crops for {video_id}. Run: run_detect.py --video {video_id} --crops")

    cand = C.CLASSIFIERS[model]
    rows, failures = [], 0
    t0 = time.perf_counter()
    for i, path in enumerate(crops):
        t1 = time.perf_counter()
        try:
            arr = np.asarray(Image.open(path).convert("RGB"), dtype="uint8")
        except Exception as exc:                        # noqa: BLE001
            # A truncated or unreadable crop must cost one row, not the sweep.
            # Same rule the pipeline follows: one failed item degrades, never
            # aborts. Recorded as a failure so it cannot pass as an abstention.
            res = {"raw": {}, "top": None, "three": None, "extra": {},
                   "error": f"crop unreadable: {type(exc).__name__}: {exc}"}
        else:
            res = cand.predict(arr)
        dt = time.perf_counter() - t1
        if res.get("error"):
            failures += 1
        rows.append({
            "crop": path.name,
            "timestamp_s": timestamp_of(path),
            "top": res["top"],
            "three": res["three"],
            "raw": res["raw"],
            "extra": res["extra"],
            "error": res.get("error"),
            "seconds": round(dt, 4),
        })
        if (i + 1) % 100 == 0:
            done = time.perf_counter() - t0
            print(f"    {video_id}/{model}: {i + 1}/{len(crops)} "
                  f"({done:.0f}s, {done / (i + 1):.3f}s/crop)")

    total = time.perf_counter() - t0
    result = {
        "video_id": video_id,
        "model": model,
        "model_meta": {
            "source": cand.source, "licence": cand.licence,
            "training_data": cand.training_data, "published": cand.published,
            "n_classes": cand.n_classes, "incumbent": cand.incumbent,
            "extras": list(cand.extras),
        },
        "crop_detector": C.CROP_DETECTOR,
        "n_crops": len(crops),
        "failures": failures,
        "total_seconds": round(total, 2),
        "seconds_per_crop": round(total / len(crops), 4),
        "rows": rows,
    }
    PREDICTIONS.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1))
    print(f"  [done]   {video_id} / {model}: {len(crops)} crops, "
          f"{failures} failures, {result['seconds_per_crop']:.3f}s/crop")
    return result


def pool_to_segments(rows: list[dict], segments: list[dict],
                     mapping: dict[str, str] | None = None) -> dict[int, dict]:
    """
    Pool crop-level predictions into segments using the pipeline's own rule.

    `visual_module.pool_emotions_per_segment` takes frames with
    start <= timestamp < end, majority-votes the dominant label, and averages the
    confidence of the frames agreeing with it. That is reproduced exactly, so
    Bench B measures classifiers and not a different pooling policy. The pooling
    itself is a documented suspect (`CANDIDATE_MODELS.md` §8.5) and is held fixed
    on purpose.
    """
    from collections import Counter

    out = {}
    for seg in segments:
        start, end = seg["start_time"], seg["end_time"]
        window = [r for r in rows
                  if start <= r["timestamp_s"] < end and r["top"] is not None]
        if not window:
            out[seg["segment_id"]] = {
                "segment_id": seg["segment_id"], "dominant": None, "three": None,
                "confidence": 0.0, "frame_count": 0, "mass": {},
            }
            continue
        counts = Counter(r["top"] for r in window)
        dominant, _ = counts.most_common(1)[0]
        agreeing = [r["raw"].get(dominant, 0.0) for r in window if r["top"] == dominant]
        # Mean probability per class across every frame in the window, kept so
        # §5.2 can ask where anger sits when it is not the argmax.
        classes = sorted({k for r in window for k in r["raw"]})
        mass = {k: round(sum(r["raw"].get(k, 0.0) for r in window) / len(window), 6)
                for k in classes}
        out[seg["segment_id"]] = {
            "segment_id": seg["segment_id"],
            "dominant": dominant,
            "three": C.to_three(dominant, mapping),
            "confidence": round(sum(agreeing) / len(agreeing), 4) if agreeing else 0.0,
            "frame_count": len(window),
            "mass": mass,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=GROUND_TRUTH_VIDEO)
    ap.add_argument("--all-videos", action="store_true")
    ap.add_argument("--model", default=None,
                    help="one candidate; default is every candidate")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    videos = BENCH_VIDEOS if args.all_videos else [args.video]
    models = [args.model] if args.model else list(C.CLASSIFIERS)
    for m in models:
        if m not in C.CLASSIFIERS:
            print(f"Unknown model '{m}'. Known: {list(C.CLASSIFIERS)}", file=sys.stderr)
            return 2

    print(f"Videos: {videos}\nModels: {models}\nCrops from: {C.CROP_DETECTOR}\n")
    for video in videos:
        for model in models:
            run_one(video, model, force=args.force, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
