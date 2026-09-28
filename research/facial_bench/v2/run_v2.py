"""
run_v2.py — run every detector and every classifier over the v2 sample.

v1 swept whole videos and pooled frames into Whisper segments. v2's unit is the
**frame**, because that is what the ground truth is collected at (PROTOCOL.md
§4–5) and what the model actually sees. So there is no pooling step here and no
segment alignment: 600 sampled frames in, one row per frame per candidate out.

The candidate set, the crop detector and the alignment flag are v1's, imported
from `facial_bench/candidates.py` unchanged (PROTOCOL.md §6). `align=True`
matches the deployed pipeline — v1 Amendment A3 records what happened the one
time this bench ran a configuration the pipeline does not.

    python run_v2.py detect                       # all six detectors
    python run_v2.py detect --detector yunet
    python run_v2.py crops                        # write crops from CROP_DETECTOR
    python run_v2.py classify                     # all nine classifiers
    python run_v2.py classify --model trpakov_vit
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
ROOT = V1.parents[1]

sys.path.insert(0, str(V1))
import candidates as C          # noqa: E402  — v1's candidate register, unchanged

DETECTIONS = HERE / "detections"
CROPS = HERE / "crops"
PREDICTIONS = HERE / "predictions"
MANIFEST = HERE / "sample.json"

ALIGN = True                    # matches pipeline/visual_module.py; see v1 Amendment A3


def load_sample() -> list[dict]:
    """The 600 unique sampled frames, de-duplicated across re-test presentations."""
    if not MANIFEST.exists():
        raise SystemExit("sample.json not found — run `python sample.py` first.")
    m = json.loads(MANIFEST.read_text())
    seen: dict[str, dict] = {}
    for p in m["presentations"]:
        if p["retest"]:
            continue
        seen[p["uid"]] = p
    return list(seen.values())


def frame_path(item: dict) -> Path:
    return ROOT / "data" / item["video_id"] / "frames" / item["frame"]


def crop_path(item: dict) -> Path:
    return CROPS / f"{item['video_id']}_{Path(item['frame']).stem}.jpg"


# ── Detection ─────────────────────────────────────────────────────────────────

def run_detector(backend: str, sample: list[dict], *, write_crops: bool = False,
                 force: bool = False) -> dict:
    out_path = DETECTIONS / f"{backend}.json"
    if out_path.exists() and not force:
        print(f"  {backend}: already done ({out_path.name}) — skipping")
        return json.loads(out_path.read_text())

    DETECTIONS.mkdir(exist_ok=True)
    if write_crops:
        CROPS.mkdir(exist_ok=True)

    rows: list[dict] = []
    started = time.time()
    for n, item in enumerate(sample, 1):
        f = frame_path(item)
        faces = C.detect(f, backend, align=ALIGN)
        # Largest region only: the pipeline keeps one label per frame.
        best = max(faces, key=lambda x: x["box"][2] * x["box"][3]) if faces else None
        rows.append({
            "uid": item["uid"],
            "video_id": item["video_id"],
            "frame": item["frame"],
            "n_faces": len(faces),
            "detected": bool(faces),
            "confidence": best["confidence"] if best else 0.0,
            "box": best["box"] if best else None,
        })
        if write_crops and best is not None:
            _save_crop(best["crop"], crop_path(item))
        if n % 50 == 0:
            rate = (time.time() - started) / n
            print(f"  {backend}: {n}/{len(sample)}  {rate:.3f}s/frame", flush=True)

    elapsed = time.time() - started
    result = {
        "backend": backend,
        "align": ALIGN,
        "n_frames": len(sample),
        "n_detected": sum(r["detected"] for r in rows),
        "seconds": round(elapsed, 1),
        "seconds_per_frame": round(elapsed / max(1, len(sample)), 4),
        "crops_written": bool(write_crops),
        "rows": rows,
    }
    out_path.write_text(json.dumps(result, indent=1))
    print(f"  {backend}: {result['n_detected']}/{len(sample)} detected, "
          f"{result['seconds_per_frame']:.3f}s/frame")
    return result


def _save_crop(crop, path: Path) -> None:
    """Write a DeepFace crop (float RGB in [0,1]) as JPEG. Same as v1."""
    import numpy as np
    from PIL import Image
    arr = np.clip(np.asarray(crop, dtype="float64"), 0.0, 1.0)
    Image.fromarray((arr * 255).astype("uint8")).save(path, quality=95)


# ── Classification ────────────────────────────────────────────────────────────

def run_classifier(name: str, sample: list[dict], *, force: bool = False) -> dict:
    out_path = PREDICTIONS / f"{name}.json"
    if out_path.exists() and not force:
        print(f"  {name}: already done — skipping")
        return json.loads(out_path.read_text())

    import numpy as np
    from PIL import Image

    PREDICTIONS.mkdir(exist_ok=True)
    clf = C.CLASSIFIERS[name]

    rows: list[dict] = []
    started = time.time()
    n_crops = 0
    for item in sample:
        cp = crop_path(item)
        if not cp.exists():
            rows.append({"uid": item["uid"], "video_id": item["video_id"],
                         "frame": item["frame"], "has_crop": False,
                         "top": None, "three": None, "raw": {}, "extra": {}})
            continue
        try:
            arr = np.asarray(Image.open(cp).convert("RGB"), dtype="uint8")
        except Exception as exc:                        # noqa: BLE001
            rows.append({"uid": item["uid"], "video_id": item["video_id"],
                         "frame": item["frame"], "has_crop": True,
                         "top": None, "three": None, "raw": {}, "extra": {},
                         "error": f"unreadable crop: {type(exc).__name__}"})
            continue
        res = clf.predict(arr)
        n_crops += 1
        rows.append({
            "uid": item["uid"], "video_id": item["video_id"], "frame": item["frame"],
            "has_crop": True, "top": res["top"], "three": res["three"],
            "raw": res["raw"], "extra": res.get("extra", {}),
            **({"error": res["error"]} if "error" in res else {}),
        })
        if n_crops % 100 == 0:
            print(f"  {name}: {n_crops} crops  "
                  f"{(time.time() - started) / n_crops:.3f}s/crop", flush=True)

    elapsed = time.time() - started
    result = {
        "model": name,
        "crop_detector": C.CROP_DETECTOR,
        "align": ALIGN,
        "n_frames": len(sample),
        "n_crops": n_crops,
        "n_failed": sum(1 for r in rows if r["has_crop"] and r["top"] is None),
        "seconds": round(elapsed, 1),
        "seconds_per_crop": round(elapsed / max(1, n_crops), 4),
        "rows": rows,
    }
    out_path.write_text(json.dumps(result, indent=1))
    print(f"  {name}: {n_crops} crops, {result['n_failed']} failed, "
          f"{result['seconds_per_crop']:.3f}s/crop")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["detect", "crops", "classify"])
    ap.add_argument("--detector", help="one backend only")
    ap.add_argument("--model", help="one classifier only")
    ap.add_argument("--force", action="store_true", help="re-run and overwrite")
    args = ap.parse_args()

    sample = load_sample()
    print(f"{len(sample)} sampled frames across "
          f"{len({s['video_id'] for s in sample})} videos\n")

    if args.stage == "crops":
        run_detector(C.CROP_DETECTOR, sample, write_crops=True, force=True)
        return 0

    if args.stage == "detect":
        backends = [args.detector] if args.detector else list(C.DETECTORS)
        for b in backends:
            run_detector(b, sample, write_crops=False, force=args.force)
        return 0

    models = [args.model] if args.model else list(C.CLASSIFIERS)
    for m in models:
        run_classifier(m, sample, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
