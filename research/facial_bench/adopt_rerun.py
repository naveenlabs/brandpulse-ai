"""
adopt_rerun.py — the before/after the adoption owes (step 7 of the bench method, README).

Bench A is a bench. This runs the **real pipeline** with the adopted detector over
the same 572 frames and scores it with the same composite Bench E uses, so the
adoption is reported as a change to the product rather than as a table.

"Before" is `anchor_pipeline.json`, which is the `opencv` configuration and was
verified to reproduce the saved June run exactly (77/77 labels, 77/77
confidences). "After" is whatever `visual_module.FACE_DETECTOR_BACKEND` is now.

    python research/facial_bench/adopt_rerun.py

Writes facial_bench/adopt_rerun.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(ROOT))

import candidates as C                                          # noqa: E402
import ground_truth as GT                                       # noqa: E402
from run_detect import frames_for                               # noqa: E402
from research.transcript_bench import metrics as M              # noqa: E402

BEFORE = BENCH / "anchor_pipeline.json"
OUT = BENCH / "adopt_rerun.json"


def composite(labels: dict[int, str | None], gold: dict[int, dict]) -> dict:
    """Bench E's composite, kept here in one place so both arms use it."""
    right = wrong = unknown = 0
    false_face = missed_face = wrong_label = 0
    outcomes = []
    for sid, g in sorted(gold.items()):
        got = labels.get(sid)
        if not g["face_present"]:
            if got is None:
                right += 1
                outcomes.append("RIGHT")
            else:
                wrong += 1
                false_face += 1
                outcomes.append("WRONG")
        elif g["expression"] is None:
            unknown += 1
        elif got is None:
            wrong += 1
            missed_face += 1
            outcomes.append("WRONG")
        elif got == g["expression"]:
            right += 1
            outcomes.append("RIGHT")
        else:
            wrong += 1
            wrong_label += 1
            outcomes.append("WRONG")
    n = len(gold)
    return {"right": right, "wrong": wrong, "unknown": unknown, "n_segments": n,
            "accuracy_lower": right / n, "accuracy_upper": (right + unknown) / n,
            "accuracy_lower_ci95": list(M.wilson_interval(right, n)),
            "false_face": false_face, "missed_face": missed_face,
            "wrong_label": wrong_label, "outcomes": outcomes}


def main() -> int:
    from pipeline.visual_module import (
        FACE_CONFIDENCE_THRESHOLD, FACE_DETECTOR_BACKEND,
        analyse_facial_emotion, pool_emotions_per_segment,
    )

    if not BEFORE.exists():
        print(f"Missing {BEFORE}; run anchor_pipeline.py first.", file=sys.stderr)
        return 1

    gold = {r["segment_id"]: r for r in GT.detection_set()}
    segments = sorted(
        [{"segment_id": r["segment_id"], "start_time": r["start_time"],
          "end_time": r["end_time"]} for r in gold.values()],
        key=lambda s: s["segment_id"])

    before = json.loads(BEFORE.read_text())
    before_labels = {r["segment_id"]: C.to_three(r["rerun_label"])
                     if r["rerun_label"] else None for r in before["rows"]}
    before_score = composite(before_labels, gold)

    frames = frames_for(GT.ANCHOR_VIDEO)
    print(f"Re-running the pipeline with FACE_DETECTOR_BACKEND={FACE_DETECTOR_BACKEND!r} "
          f"over {len(frames)} frames …")
    t0 = time.perf_counter()
    frame_emotions = analyse_facial_emotion(frames)
    elapsed = time.perf_counter() - t0
    pool_emotions_per_segment(frame_emotions, segments)
    after_labels = {s["segment_id"]: C.to_three(s["facial_emotion"]["dominant"])
                    if s["facial_emotion"]["dominant"] else None for s in segments}
    after_score = composite(after_labels, gold)

    allright = ["RIGHT"] * len(before_score["outcomes"])
    mc = M.mcnemar_exact(allright, before_score["outcomes"], after_score["outcomes"])

    result = {
        "video_id": GT.ANCHOR_VIDEO,
        "n_frames": len(frames),
        "face_confidence_threshold": FACE_CONFIDENCE_THRESHOLD,
        "before": {"backend": "opencv", "seconds_per_frame": before["seconds_per_frame"],
                   "frames_with_face": before["frames_with_face"], **before_score},
        "after": {"backend": FACE_DETECTOR_BACKEND,
                  "seconds_per_frame": round(elapsed / len(frames), 4),
                  "frames_with_face": sum(1 for f in frame_emotions
                                          if f["dominant_emotion"] is not None),
                  **after_score},
        "mcnemar_after_vs_before": mc,
        "segments_changed": [
            {"segment_id": sid, "before": before_labels.get(sid),
             "after": after_labels.get(sid),
             "gold": (None if not gold[sid]["face_present"] else gold[sid]["expression"])}
            for sid in sorted(gold) if before_labels.get(sid) != after_labels.get(sid)
        ],
    }
    OUT.write_text(json.dumps(result, indent=1))

    b, a = result["before"], result["after"]
    print(f"\n{'':22s} {'before (opencv)':>16s} {'after (' + a['backend'] + ')':>16s}")
    for key, label in (("right", "segments right /77"),
                       ("false_face", "false faces /20"),
                       ("missed_face", "missed faces /57"),
                       ("wrong_label", "wrong labels /44"),
                       ("frames_with_face", "frames with a face"),
                       ("seconds_per_frame", "seconds per frame")):
        print(f"{label:22s} {b[key]:>16} {a[key]:>16}")
    print(f"{'accuracy range':22s} "
          f"{100 * b['accuracy_lower']:6.1f}-{100 * b['accuracy_upper']:5.1f}%  "
          f"{100 * a['accuracy_lower']:9.1f}-{100 * a['accuracy_upper']:5.1f}%")
    print(f"\nMcNemar after vs before: p={mc['p_value']:.4f} "
          f"(b={mc['b']}, c={mc['c']}, min attainable {mc['min_attainable_p']:.4f})")
    print(f"Segments whose label changed: {len(result['segments_changed'])}")
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
