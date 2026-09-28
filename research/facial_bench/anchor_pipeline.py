"""
anchor_pipeline.py — prove the bench's incumbent is the pipeline's incumbent.

Every number this bench reports about `deepface_fer` and `opencv` is only
meaningful if they behave here the way they behave in production. This script
does not re-implement anything: it calls `pipeline.visual_module` directly, on the
same frames, with the same segment boundaries, and checks that it reproduces the
saved run `PROTOTYPE_FINDINGS.md` §9 reviewed.

It is a **system test** in the project's testing vocabulary — the real module,
the real frames, the real segment windows, no mocks — and it is the anchor that
licenses the rest of the bench, in the same way `vocal_bench` had to reproduce its
published thresholds from cache before it was allowed to score anything.

Two things are checked:

  1. `analyse_facial_emotion` + `pool_emotions_per_segment` reproduce the stored
     `facial_emotion.dominant` for all 77 segments.
  2. The stored confidences match to 4 decimal places.

Any mismatch is reported per segment. A partial match is still useful information
— DeepFace's own weights or OpenCV's cascade may have moved since June — so the
script reports the agreement rate rather than only pass/fail, and the write-up
quotes whatever it actually finds.

Usage
-----
    python research/facial_bench/anchor_pipeline.py
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

import ground_truth as GT                                       # noqa: E402
from run_detect import frames_for                               # noqa: E402

OUT = BENCH / "anchor_pipeline.json"


def main() -> int:
    from pipeline.visual_module import (
        FACE_CONFIDENCE_THRESHOLD, analyse_facial_emotion, pool_emotions_per_segment,
    )

    stored = GT.load_anchor_segments()
    frames = frames_for(GT.ANCHOR_VIDEO)
    if not frames:
        print(f"No frames for {GT.ANCHOR_VIDEO}", file=sys.stderr)
        return 1

    print(f"Re-running pipeline.visual_module over {len(frames)} frames "
          f"of {GT.ANCHOR_VIDEO} (FACE_CONFIDENCE_THRESHOLD={FACE_CONFIDENCE_THRESHOLD}) …")
    t0 = time.perf_counter()
    frame_emotions = analyse_facial_emotion(frames)
    elapsed = time.perf_counter() - t0

    segments = [{"segment_id": s["segment_id"], "start_time": s["start_time"],
                 "end_time": s["end_time"]} for s in stored.values()]
    segments.sort(key=lambda s: s["segment_id"])
    pool_emotions_per_segment(frame_emotions, segments)

    rows, label_hits, conf_hits = [], 0, 0
    for seg in segments:
        sid = seg["segment_id"]
        got = seg["facial_emotion"]
        want = stored[sid]
        label_ok = got["dominant"] == want["dominant"]
        conf_ok = (
            want["confidence"] is not None
            and abs(float(got["confidence"]) - float(want["confidence"])) < 1e-4
        ) if got["dominant"] is not None else (want["dominant"] is None)
        label_hits += label_ok
        conf_hits += conf_ok
        rows.append({
            "segment_id": sid,
            "stored_label": want["dominant"], "rerun_label": got["dominant"],
            "stored_confidence": want["confidence"], "rerun_confidence": got["confidence"],
            "stored_frames": want["frame_count"], "rerun_frames": got["frame_count"],
            "label_match": label_ok, "confidence_match": conf_ok,
        })

    n = len(rows)
    faces = sum(1 for f in frame_emotions if f["dominant_emotion"] is not None)
    result = {
        "video_id": GT.ANCHOR_VIDEO,
        "n_frames": len(frames),
        "frames_with_face": faces,
        "seconds": round(elapsed, 1),
        "seconds_per_frame": round(elapsed / len(frames), 4),
        "face_confidence_threshold": FACE_CONFIDENCE_THRESHOLD,
        "n_segments": n,
        "label_matches": label_hits,
        "label_agreement": round(label_hits / n, 4),
        "confidence_matches": conf_hits,
        "confidence_agreement": round(conf_hits / n, 4),
        "mismatches": [r for r in rows if not r["label_match"]],
        "rows": rows,
        "frame_level": [
            {"frame": f["frame"].rsplit("/", 1)[-1], "timestamp_s": f["timestamp_s"],
             "dominant_emotion": f["dominant_emotion"], "confidence": f["confidence"]}
            for f in frame_emotions
        ],
    }
    OUT.write_text(json.dumps(result, indent=1))

    print(f"\nFrames with a detected face: {faces}/{len(frames)}")
    print(f"Segment labels reproduced:   {label_hits}/{n} ({100 * label_hits / n:.1f}%)")
    print(f"Confidences reproduced:      {conf_hits}/{n} ({100 * conf_hits / n:.1f}%)")
    print(f"Runtime: {elapsed:.0f}s ({elapsed / len(frames):.3f}s/frame at 4K)")
    if result["mismatches"]:
        print(f"\n{len(result['mismatches'])} segment(s) differ from the saved run:")
        for r in result["mismatches"][:20]:
            print(f"  seg {r['segment_id']:2d}: stored {r['stored_label']}"
                  f"({r['stored_confidence']}) -> rerun {r['rerun_label']}"
                  f"({r['rerun_confidence']})")
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
