"""
probe_candidates.py — feasibility probe for the facial-emotion bench.

Answers one question per candidate: does it load and run in THIS venv, on THIS
project's frames, and how fast?  It deliberately produces no accuracy number —
no ground truth exists yet and none is used here.  Run before the candidate
register is finalised, exactly as vocal_bench probed its candidates first.

WARNING about `probe_results.json`, added 03 Sep 2026.
    This probe ran with deepface's default `align=False` and fed whole 4K frames
    to the classifiers rather than face crops.  Amendment A3 of CANDIDATE_MODELS.md
    explains why both are wrong for measurement: alignment changes whether a face
    is found at all, and every FER candidate expects a cropped, aligned face.
    Nothing in `probe_results.json` is a result, and no number in it appears in
    FACIAL_MODEL_ANALYSIS.md.  The file is kept only as the feasibility record —
    which candidates loaded, and roughly what they cost.

Usage
-----
    python research/facial_bench/probe_candidates.py [--only detectors|classifiers|vlm]

Writes facial_bench/probe_results.json and prints a table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
DATA = ROOT / "data"

# Three fixed probe frames, chosen before any candidate ran, one per video.
# They are named here so the probe is reproducible and so the same three frames
# are used for every candidate.
PROBE_FRAMES = [
    DATA / "1VjPETN3m6U" / "frames" / "frame_0400.jpg",   # real face, mid-sentence
    DATA / "JpN1DQdV4G4" / "frames" / "frame_0300.jpg",   # product b-roll, no face
    DATA / "SAb4zRyxrD4" / "frames" / "frame_0200.jpg",   # unseen at write time
]

DETECTORS = ["opencv", "ssd", "mtcnn", "retinaface", "yunet", "centerface", "yolov8", "mediapipe", "dlib"]

CLASSIFIERS = {
    "deepface_emotion":  ("deepface", None),
    "trpakov_vit":       ("hf", "trpakov/vit-face-expression"),
    "motheecreator_vit": ("hf", "motheecreator/vit-Facial-Expression-Recognition"),
    "dima806_vit":       ("hf", "dima806/facial_emotions_image_detection"),
    "hardlyhumans_vit":  ("hf", "HardlyHumans/Facial-expression-detection"),
    "tanneru_beit_l":    ("hf", "Tanneru/Facial-Emotion-Detection-FER-RAFDB-AffectNet-BEIT-Large"),
}


def _existing_frames() -> list[Path]:
    return [f for f in PROBE_FRAMES if f.exists()]


def probe_detectors(frames: list[Path]) -> dict:
    from deepface import DeepFace
    out = {}
    for backend in DETECTORS:
        rec = {"backend": backend, "available": False, "error": None, "frames": []}
        t0 = time.perf_counter()
        try:
            for f in frames:
                t1 = time.perf_counter()
                faces = DeepFace.extract_faces(
                    img_path=str(f), detector_backend=backend,
                    enforce_detection=False, align=False,
                )
                real = [x for x in faces if x.get("confidence", 0.0) > 0]
                rec["frames"].append({
                    "frame": f.name,
                    "video": f.parent.parent.name,
                    "n_regions": len(faces),
                    "n_confident": len(real),
                    "confidences": [round(float(x.get("confidence", 0.0)), 4) for x in faces],
                    "seconds": round(time.perf_counter() - t1, 3),
                })
            rec["available"] = True
        except Exception as exc:                       # noqa: BLE001 — probe reports, never raises
            rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["total_seconds"] = round(time.perf_counter() - t0, 3)
        out[backend] = rec
        status = "ok " if rec["available"] else "FAIL"
        print(f"  [{status}] {backend:12s} {rec['total_seconds']:7.2f}s  {rec['error'] or ''}")
    return out


def probe_classifiers(frames: list[Path]) -> dict:
    out = {}
    for name, (kind, model_id) in CLASSIFIERS.items():
        rec = {"name": name, "kind": kind, "model_id": model_id,
               "available": False, "error": None, "labels": None, "frames": []}
        try:
            if kind == "deepface":
                from deepface import DeepFace
                t0 = time.perf_counter()
                DeepFace.build_model("Emotion", task="facial_attribute")
                rec["load_seconds"] = round(time.perf_counter() - t0, 2)
                for f in frames:
                    t1 = time.perf_counter()
                    res = DeepFace.analyze(img_path=str(f), actions=["emotion"],
                                           enforce_detection=False,
                                           detector_backend="opencv", silent=True)
                    best = max(res, key=lambda r: r.get("face_confidence", 0.0))
                    rec["frames"].append({
                        "frame": f.name,
                        "top": best.get("dominant_emotion"),
                        "scores": {k: round(float(v), 2) for k, v in best.get("emotion", {}).items()},
                        "seconds": round(time.perf_counter() - t1, 3),
                    })
                rec["labels"] = sorted(rec["frames"][0]["scores"]) if rec["frames"] else None
            else:
                from transformers import pipeline
                t0 = time.perf_counter()
                pipe = pipeline("image-classification", model=model_id, device=-1)
                rec["load_seconds"] = round(time.perf_counter() - t0, 2)
                rec["labels"] = [pipe.model.config.id2label[i]
                                 for i in sorted(pipe.model.config.id2label)]
                for f in frames:
                    t1 = time.perf_counter()
                    res = pipe(str(f), top_k=None)
                    rec["frames"].append({
                        "frame": f.name,
                        "top": res[0]["label"],
                        "scores": {r["label"]: round(float(r["score"]), 4) for r in res},
                        "seconds": round(time.perf_counter() - t1, 3),
                    })
            rec["available"] = True
        except Exception as exc:                       # noqa: BLE001
            rec["error"] = f"{type(exc).__name__}: {exc}"
            rec["traceback"] = traceback.format_exc()[-1200:]
        out[name] = rec
        status = "ok " if rec["available"] else "FAIL"
        print(f"  [{status}] {name:20s} labels={rec['labels']}  {rec['error'] or ''}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["detectors", "classifiers"], default=None)
    args = ap.parse_args()

    frames = _existing_frames()
    if not frames:
        print("No probe frames on disk; nothing to do.", file=sys.stderr)
        return 1
    print(f"Probe frames ({len(frames)}):")
    for f in frames:
        print(f"  {f.parent.parent.name}/{f.name}")

    results = {"probe_frames": [str(f.relative_to(ROOT)) for f in frames]}
    if args.only in (None, "detectors"):
        print("\nDetector backends:")
        results["detectors"] = probe_detectors(frames)
    if args.only in (None, "classifiers"):
        print("\nEmotion classifiers:")
        results["classifiers"] = probe_classifiers(frames)

    (BENCH / "probe_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {BENCH / 'probe_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
