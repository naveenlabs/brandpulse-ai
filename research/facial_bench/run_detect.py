"""
run_detect.py — Bench A: which face detector actually finds faces on this footage.

This is the half of the facial channel that `PROTOTYPE_FINDINGS.md` §9 and §12D
show is broken independently of the emotion model: DeepFace's `opencv` backend
reports confident faces on product b-roll containing no human being.

What is measured
----------------
For each detector, on every frame of a video, whether it reports a face and with
what confidence. Frame results are then pooled into Whisper segments **using the
pipeline's own rule** (`visual_module.pool_emotions_per_segment`: a segment has a
face if any frame inside its window does), so the numbers are comparable with the
ground truth, which is segment-level.

Ground truth is `ground_truth.py`, which is the author's own visual review in §9,
not a model's output.

Caching
-------
One JSON per video and detector under `detections/`. Re-running skips work that
is already on disk, matching `downloader.py`'s skip-if-exists convention. Use
`--force` to redo a detector.

Crops
-----
`--crops` additionally writes the face crop from `candidates.CROP_DETECTOR` to
`crops/<video>/`, one JPEG per detected face. Every classifier in Bench B reads
those files, so all classifiers see identical pixels and the classification
comparison is not confounded by detection.

Usage
-----
    python research/facial_bench/run_detect.py --video 1VjPETN3m6U
    python research/facial_bench/run_detect.py --video 1VjPETN3m6U --detector retinaface --crops
    python research/facial_bench/run_detect.py --all-videos --detector yunet
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

DETECTIONS = BENCH / "detections"
CROPS = BENCH / "crops"

# Videos with extracted frames on disk. The ground-truth video is first.
BENCH_VIDEOS = ["1VjPETN3m6U", "JpN1DQdV4G4", "SAb4zRyxrD4"]
GROUND_TRUTH_VIDEO = "1VjPETN3m6U"


def frames_for(video_id: str) -> list[Path]:
    d = ROOT / "data" / video_id / "frames"
    return sorted(d.glob("frame_*.jpg")) if d.is_dir() else []


def timestamp_of(frame: Path) -> float:
    """Seconds from the filename, the same rule visual_module uses (1 fps)."""
    import re
    m = re.search(r"frame_(\d+)", frame.stem)
    return float(int(m.group(1))) if m else 0.0


# Face alignment is ON, because that is what the pipeline does.
#
# `visual_module.analyse_facial_emotion` reaches the detector through
# `DeepFace.analyze`, which aligns by default. Alignment is not merely a crop
# transform in deepface: it rotates on the eye landmarks and re-detects, so it
# feeds back into whether a face is found at all. Measured 03 Sep 2026 on this
# video: with `align=False` the bench and the pipeline disagreed on 28 of 572
# frames; with `align=True` they agreed on all 28. Running the bench unaligned
# would therefore have benched something the pipeline does not run.
#
# It matters for Bench B too. Every FER candidate here is trained on aligned face
# crops, so handing them unaligned ones would handicap all of them equally and
# for no reason.
ALIGN = True


def midpoint_frames(video_id: str, frames: list[Path]) -> list[Path]:
    """
    Just the frame nearest each segment's temporal midpoint.

    77 frames instead of 572, which makes the primary Bench A metric affordable for
    a detector too slow to sweep in full (Amendment A4). A detector measured this
    way gets a complete `midpoint` score and **no** `any`-pooled score, and the
    result file records `midpoints_only` so the report cannot silently mix the two.
    """
    import ground_truth as GT
    if video_id != GT.ANCHOR_VIDEO:
        raise ValueError(
            f"midpoint frames need segment boundaries; only {GT.ANCHOR_VIDEO} has them")
    by_ts = {r["timestamp_s"]: r for r in
             ({"timestamp_s": timestamp_of(f), "path": f} for f in frames)}
    picked: dict[str, Path] = {}
    for seg in GT.load_anchor_segments().values():
        mid = (seg["start_time"] + seg["end_time"]) / 2.0
        window = [ts for ts in by_ts if seg["start_time"] <= ts < seg["end_time"]]
        if not window:
            continue
        best = min(window, key=lambda ts: abs(ts - mid))
        picked[by_ts[best]["path"].name] = by_ts[best]["path"]
    return sorted(picked.values())


def run_one(video_id: str, detector: str, *, write_crops: bool = False,
            force: bool = False, limit: int | None = None,
            midpoints_only: bool = False) -> dict:
    suffix = "__midpoints" if midpoints_only else ""
    out_path = DETECTIONS / f"{video_id}__{detector}{suffix}.json"
    if out_path.exists() and not force:
        print(f"  [cached] {video_id} / {detector}")
        return json.loads(out_path.read_text())

    frames = frames_for(video_id)
    if midpoints_only:
        frames = midpoint_frames(video_id, frames)
    if limit:
        frames = frames[:limit]
    if not frames:
        raise FileNotFoundError(f"No frames on disk for {video_id}")

    crop_dir = CROPS / video_id
    if write_crops:
        crop_dir.mkdir(parents=True, exist_ok=True)

    rows, errors = [], 0
    t0 = time.perf_counter()
    for i, f in enumerate(frames):
        t1 = time.perf_counter()
        faces = C.detect(f, detector, align=ALIGN)
        dt = time.perf_counter() - t1
        row = {
            "frame": f.name,
            "timestamp_s": timestamp_of(f),
            "n_faces": len(faces),
            "confidences": [x["confidence"] for x in faces],
            "boxes": [x["box"] for x in faces],
            "seconds": round(dt, 4),
        }
        if not faces and dt == 0.0:
            errors += 1
        if write_crops and faces:
            # Only the largest region per frame is kept: the pipeline pools one
            # dominant label per segment, so a second face would never reach the
            # report anyway, and keeping it would change what is being compared.
            best = max(faces, key=lambda x: x["box"][2] * x["box"][3])
            _save_crop(best["crop"], crop_dir / f"{f.stem}.jpg")
            row["crop"] = f"{f.stem}.jpg"
            row["crop_box"] = best["box"]
            row["crop_confidence"] = best["confidence"]
        rows.append(row)
        if (i + 1) % 100 == 0:
            done = time.perf_counter() - t0
            print(f"    {video_id}/{detector}: {i + 1}/{len(frames)} "
                  f"({done:.0f}s, {done / (i + 1):.2f}s/frame)")

    total = time.perf_counter() - t0
    result = {
        "video_id": video_id,
        "detector": detector,
        "detector_meta": C.DETECTORS.get(detector, {}),
        "n_frames": len(frames),
        "frames_with_face": sum(1 for r in rows if r["n_faces"] > 0),
        "total_detections": sum(r["n_faces"] for r in rows),
        "total_seconds": round(total, 2),
        "seconds_per_frame": round(total / len(frames), 4),
        "crops_written": bool(write_crops),
        "align": ALIGN,
        "midpoints_only": bool(midpoints_only),
        "rows": rows,
    }
    DETECTIONS.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1))
    print(f"  [done]   {video_id} / {detector}: "
          f"{result['frames_with_face']}/{result['n_frames']} frames with a face, "
          f"{result['seconds_per_frame']:.2f}s/frame")
    return result


def _save_crop(crop, path: Path) -> None:
    """Write a DeepFace crop (float RGB in [0,1]) as a JPEG."""
    import numpy as np
    from PIL import Image
    arr = np.clip(np.asarray(crop, dtype="float64"), 0.0, 1.0)
    Image.fromarray((arr * 255).astype("uint8")).save(path, quality=95)


def pool_to_segments(rows: list[dict], segments: list[dict],
                     mode: str = "any") -> dict[int, dict]:
    """
    Pool frame detections into segments.

    Two modes, and both are reported, because they answer different questions.

    ``any`` (default) — the pipeline's own rule. `visual_module.pool_emotions_per_segment`
        collects frames with start <= timestamp < end and treats the segment as
        having a face if any of them do. This is what production actually does,
        so it is the deployment-relevant number.

    ``midpoint`` — the frame nearest the temporal midpoint of the window, and only
        that frame. This is the unit the ground truth was actually observed at:
        §9's methodology states the midpoint frame was opened for every segment,
        with one or two neighbours only where it was ambiguous. Scoring at the
        midpoint compares a detector against exactly what the human looked at,
        so it is the validity-relevant number.

    The two can disagree, and where they do the disagreement is itself
    informative: a detector that is right at the midpoint but fires somewhere else
    in a long window is either catching a frame §9 never inspected or is being
    punished by the pooling rule rather than by its own error.
    """
    if mode not in ("any", "midpoint"):
        raise ValueError(f"unknown pooling mode {mode!r}; expected 'any' or 'midpoint'")
    out = {}
    for seg in segments:
        start, end = seg["start_time"], seg["end_time"]
        window = [r for r in rows if start <= r["timestamp_s"] < end]
        if mode == "midpoint" and window:
            mid = (start + end) / 2.0
            window = [min(window, key=lambda r: abs(r["timestamp_s"] - mid))]
        faced = [r for r in window if r["n_faces"] > 0]
        out[seg["segment_id"]] = {
            "segment_id": seg["segment_id"],
            "frames_in_window": len(window),
            "frames_with_face": len(faced),
            "face_present": bool(faced),
            "max_confidence": max((max(r["confidences"]) for r in faced), default=0.0),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=GROUND_TRUTH_VIDEO)
    ap.add_argument("--all-videos", action="store_true")
    ap.add_argument("--detector", default=None,
                    help="one backend; default is every backend in candidates.DETECTORS")
    ap.add_argument("--crops", action="store_true",
                    help=f"also write crops from {C.CROP_DETECTOR}")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="first N frames only, for smoke tests")
    ap.add_argument("--midpoints-only", action="store_true",
                    help="only each segment's midpoint frame (77 instead of 572); "
                         "gives a complete midpoint score and no pooled score")
    args = ap.parse_args()

    videos = BENCH_VIDEOS if args.all_videos else [args.video]
    detectors = [args.detector] if args.detector else list(C.DETECTORS)
    for d in detectors:
        if d not in C.DETECTORS:
            print(f"Unknown detector '{d}'. Known: {list(C.DETECTORS)}", file=sys.stderr)
            return 2

    print(f"Videos: {videos}\nDetectors: {detectors}\n")
    for video in videos:
        for det in detectors:
            run_one(video, det, force=args.force, limit=args.limit,
                    midpoints_only=args.midpoints_only,
                    write_crops=args.crops and det == C.CROP_DETECTOR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
