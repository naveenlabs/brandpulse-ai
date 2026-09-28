"""
visual_module.py — Visual channel analysis

Pipeline:
  YOLOv8   → detect_logos, a structural placeholder that nothing in the pipeline
             calls: COCO-80 has no brand classes (PROTOTYPE_FINDINGS.md §8)
  DeepFace → detect a face (FACE_DETECTOR_BACKEND) and classify its emotion per
             frame, then pool into Whisper segments (majority label, mean confidence)

Channel reliability (measured, not assumed):
  The emotion label this module produces is **worse than a constant** on this
  project's own data. Benched 03 Sep 2026 over all 77 segments of the
  ground-truth video: the channel's composite accuracy is 46.8-63.6 per cent
  against 63.6-80.5 per cent for the same detector paired with a fixed NEUTRAL
  label, and none of nine candidate emotion models beat that constant.
  `facial_bench/FACIAL_MODEL_ANALYSIS.md` has the full result and the reasoning.
  Anything consuming `facial_emotion` should weight it accordingly.

Bias caveat (mandatory on all outputs):
  DeepFace emotion recognition has documented accuracy disparities across skin
  tone and gender (Buolamwini & Gebru, 2018; Fan et al., 2023). All downstream
  outputs that incorporate facial emotion data must surface this caveat to the
  end user. The wording is scorer.BIAS_CAVEAT, which build_final_report
  attaches to every report.

Segment schema additions (added by pool_emotions_per_segment):
  {
    ...,
    "facial_emotion": {
        "dominant":    str | None,   # e.g. "happy", "disgust", None if no face
        "confidence":  float,        # mean confidence of dominant label (0–1)
        "frame_count": int,          # frames with a detected face in this window
        "reliability": float,        # FACIAL_CHANNEL_RELIABILITY, measured
    }
  }
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Face detector backend.
#
# Benched 03 Sep 2026 over all 572 frames of `data/1VjPETN3m6U/` against the
# author's own frame-by-frame review (`facial_bench/`, write-up
# `facial_bench/FACIAL_MODEL_ANALYSIS.md`). Six backends were measured; `yunet`
# is the winner under the rule pre-registered before any of them ran.
#
# Against the previous `opencv` backend, on the frame the ground truth was
# actually observed at:
#
#     backend    false positives   recall      accuracy   s/frame
#     opencv       1 of 20         47 of 57      85.7%     0.433
#     yunet        0 of 20         52 of 57      93.5%     0.062
#
# and under the pipeline's own segment pooling the hallucinated-face rate falls
# from 15 of 20 verified-faceless segments to 9 of 20. It is also **seven times
# faster**, which matters at 3840x2160.
#
# `yolov8n` scored higher overall (96.1%) but costs one false positive, which the
# pre-registered rule ranks first, and its confidences run down to 0.27 — so
# unlike `opencv` and `yunet` it would make the threshold below start rejecting
# frames, changing two things at once. See the write-up for the full table.
FACE_DETECTOR_BACKEND = "yunet"

# Minimum face_confidence returned by DeepFace below which we treat the frame
# as containing no face.  With enforce_detection=False, DeepFace always returns
# a result — even for blank frames — but face_confidence will be near 0.
#
# MEASURED 03 Sep 2026: this gate is inert for both the old and the new backend.
# Across 415 `opencv` detections the lowest confidence was 0.88, and across 386
# `yunet` detections it was 0.90 — neither backend has ever produced a value this
# threshold could reject on real footage. It is kept because a future backend or a
# different video may produce low-confidence detections, but it is **not** what
# stops non-face frames getting a label, and `PROTOTYPE_FINDINGS.md` §9's proposed
# fix of raising it was measured and does not work: the confidence has almost no
# discriminative range, and raising it far enough to remove false positives starts
# destroying real faces first.
FACE_CONFIDENCE_THRESHOLD = 0.50

# How often this channel's emotion label is right, measured on held-out speakers.
#
# 39 of 114 frames = 0.342, from `facial_bench/v2/` on 04 Sep 2026: nine emotion
# models scored against 320 purpose-collected frame labels, split by speaker, the
# holdout opened exactly once. The deployed model here is DeepFace's FER-2013 head
# (`deepface_fer`), because v2 adopted nothing — no model beat an always-NEUTRAL
# constant, and on the holdout every one of the nine fell **below** it, the best by
# 30.7 points. See `facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md` §7 and §10.
#
# Mirrors `audio_module.VOCAL_CHANNEL_RELIABILITY = 0.489`, and is lower for the
# same reason that constant is low: it is a measurement, not a target. The
# orchestrator reads it as `FACIAL_ONLY_CONFLICT_WEIGHT` to damp a conflict that
# rests on this channel alone.
#
# It is deliberately NOT used to suppress the channel entirely, even though 0.342
# is below the 0.675 an always-NEUTRAL constant scores on the same frames. The
# channel is not uninformative — the deployed model still recovers 58.8% of
# POSITIVE frames on held-out speakers — and removing a channel is a design change,
# not a weight. What the number justifies is discounting its lone testimony.
FACIAL_CHANNEL_RELIABILITY = 0.342

# ── Lazy model singletons ─────────────────────────────────────────────────────

_yolo_model = None


def _get_yolo():
    """Load YOLOv8n exactly once per process and cache."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        logger.info("Loading YOLOv8n model …")
        _yolo_model = YOLO("yolov8n.pt")  # downloads ~6 MB on first call
        logger.info("YOLOv8n ready.")
    return _yolo_model


# DeepFace handles its own internal model caching via deepface.modules.modeling,
# so no explicit singleton is needed here — the TF model is loaded once per
# process and reused automatically.


# ── Helpers ───────────────────────────────────────────────────────────────────

def _timestamp_from_path(frame_path: Path) -> float:
    """
    Derive timestamp in seconds from a frame filename.

    Filenames are produced by downloader.extract_frames() at 1 fps:
      frame_0000.jpg → 0 s
      frame_0042.jpg → 42 s

    Falls back to 0.0 if the filename doesn't match the expected pattern.
    """
    match = re.search(r"frame_(\d+)", frame_path.stem)
    if match:
        return float(int(match.group(1)))
    logger.warning("Could not parse timestamp from filename %s; defaulting to 0.0", frame_path.name)
    return 0.0


# ── Stage 1: Logo / product detection ────────────────────────────────────────

def detect_logos(frames: list[Path], brand_name: str) -> list[dict]:
    """
    Run YOLOv8n on each frame and return detections that loosely match brand_name.

    LIMITATION — COCO placeholder:
        YOLOv8n is pre-trained on COCO-80, which contains everyday object classes
        (person, car, bottle, …) but NO brand-specific classes (Nike, Samsung, …).
        The substring match below serves as a structural placeholder:
          - It will produce real detections if brand_name matches a COCO class
            (e.g. brand_name="bottle" for product-on-shelf analysis).
          - For actual brand-logo detection a fine-tuned YOLO model trained on
            brand-specific imagery is required (PROTOTYPE_FINDINGS.md §8).
        No stage of the pipeline calls this function; its tests keep it working.

    Parameters
    ----------
    frames     : Sorted list of frame Paths produced by downloader.extract_frames()
    brand_name : Brand to search for (case-insensitive substring match vs COCO labels)

    Returns
    -------
    List of detection dicts:
      [{"frame": str, "timestamp_s": float, "label": str, "confidence": float}, ...]
    Empty list if no matches found.
    """
    if not frames:
        return []

    model = _get_yolo()
    brand_lower = brand_name.lower()
    detections: list[dict] = []

    for frame_path in frames:
        frame_path = Path(frame_path)
        if not frame_path.exists():
            logger.warning("Frame not found, skipping: %s", frame_path)
            continue

        timestamp_s = _timestamp_from_path(frame_path)

        try:
            results = model(str(frame_path), verbose=False)
        except Exception as exc:
            logger.warning("YOLOv8 inference failed on %s: %s", frame_path.name, exc)
            continue

        if not results:
            continue

        result = results[0]
        class_names: dict[int, str] = result.names  # {id: label}

        for box in result.boxes:
            class_id = int(box.cls[0])
            label = class_names.get(class_id, "unknown")
            confidence = float(box.conf[0])

            if brand_lower in label.lower():
                detections.append({
                    "frame":       str(frame_path),
                    "timestamp_s": timestamp_s,
                    "label":       label,
                    "confidence":  round(confidence, 4),
                })
                logger.debug(
                    "Logo match @ %.0fs — label=%s conf=%.2f", timestamp_s, label, confidence
                )

    logger.info(
        "detect_logos: %d detections across %d frames for brand '%s'.",
        len(detections), len(frames), brand_name,
    )
    return detections


# ── Stage 2: Facial emotion per frame ────────────────────────────────────────

def analyse_facial_emotion(frames: list[Path]) -> list[dict]:
    """
    Run DeepFace.analyze() on each frame and return per-frame emotion results.

    Uses enforce_detection=False so frames with no face do not raise an exception.
    When face_confidence < FACE_CONFIDENCE_THRESHOLD the frame is treated as
    containing no detectable face — though see that constant: on real footage it
    has never rejected anything, and the detector backend is what actually
    controls the false-positive rate.

    Bias caveat: see module docstring and scorer.BIAS_CAVEAT.

    Parameters
    ----------
    frames : Sorted list of frame Paths (1 fps, frame_NNNN.jpg naming)

    Returns
    -------
    List of per-frame dicts:
      {
        "frame":            str,
        "timestamp_s":      float,
        "dominant_emotion": str | None,   # None when no face detected
        "confidence":       float,        # 0.0 when no face detected
      }
    Always returns one dict per input frame — never raises.
    """
    from deepface import DeepFace  # deferred: TF import is slow

    results: list[dict] = []

    for frame_path in frames:
        frame_path = Path(frame_path)
        timestamp_s = _timestamp_from_path(frame_path)

        base = {"frame": str(frame_path), "timestamp_s": timestamp_s}

        if not frame_path.exists():
            logger.warning("Frame not found, skipping: %s", frame_path)
            results.append({**base, "dominant_emotion": None, "confidence": 0.0})
            continue

        try:
            analysis = DeepFace.analyze(
                img_path=str(frame_path),
                actions=["emotion"],
                enforce_detection=False,
                detector_backend=FACE_DETECTOR_BACKEND,
                silent=True,
            )
        except Exception as exc:
            logger.warning("DeepFace failed on %s: %s", frame_path.name, exc)
            results.append({**base, "dominant_emotion": None, "confidence": 0.0})
            continue

        # analysis is a list; take the highest-confidence face if multiple found
        if not analysis:
            results.append({**base, "dominant_emotion": None, "confidence": 0.0})
            continue

        best = max(analysis, key=lambda r: r.get("face_confidence", 0.0))
        face_conf = best.get("face_confidence", 0.0)

        if face_conf < FACE_CONFIDENCE_THRESHOLD:
            # DeepFace returned a result but is not confident a real face exists
            logger.debug("No confident face at %.0fs (face_confidence=%.2f).", timestamp_s, face_conf)
            results.append({**base, "dominant_emotion": None, "confidence": 0.0})
            continue

        dominant = best.get("dominant_emotion", "neutral")
        # emotion scores are 0–100 percentages; normalise to 0–1
        emotion_scores: dict[str, float] = best.get("emotion", {})
        raw_conf = emotion_scores.get(dominant, 0.0)
        # DeepFace returns numpy.float32 here — cast to native float so the
        # report stays JSON-serialisable downstream (json.dump cannot encode
        # numpy scalar types).
        confidence = round(float(raw_conf) / 100.0, 4)

        results.append({
            **base,
            "dominant_emotion": dominant,
            "confidence":       confidence,
        })
        logger.debug("Face @ %.0fs → %s (%.2f)", timestamp_s, dominant, confidence)

    logger.info(
        "analyse_facial_emotion: %d/%d frames had a detected face.",
        sum(1 for r in results if r["dominant_emotion"] is not None),
        len(results),
    )
    return results


# ── Stage 3: Pool frame emotions into Whisper segments ───────────────────────

def pool_emotions_per_segment(
    frame_emotions: list[dict],
    segments: list[dict],
) -> list[dict]:
    """
    Assign a facial_emotion summary to each Whisper segment.

    For each segment window [start_time, end_time):
      1. Collect all frame_emotions whose timestamp_s falls inside the window.
      2. Filter to frames where a face was actually detected (dominant_emotion is not None).
      3. Majority vote → dominant label.
      4. Mean confidence across frames that share the dominant label.
      5. If zero faces in window → {"dominant": None, "confidence": 0.0, "frame_count": 0}.
    Every summary also carries "reliability": FACIAL_CHANNEL_RELIABILITY.

    Modifies segments in-place; returns the same list.

    Parameters
    ----------
    frame_emotions : Output of analyse_facial_emotion()
    segments       : Output of audio_module.transcribe() (or later stages)

    Returns
    -------
    The same segments list with "facial_emotion" key added to each dict.
    """
    for seg in segments:
        start = seg["start_time"]
        end   = seg["end_time"]

        # Frames whose timestamp falls in [start, end)
        window_frames = [
            fe for fe in frame_emotions
            if start <= fe["timestamp_s"] < end
        ]

        # Only frames with a confirmed face
        faced_frames = [
            fe for fe in window_frames
            if fe["dominant_emotion"] is not None
        ]

        if not faced_frames:
            seg["facial_emotion"] = {
                "dominant":    None,
                "confidence":  0.0,
                "frame_count": 0,
                "reliability": FACIAL_CHANNEL_RELIABILITY,
            }
            logger.debug(
                "Segment %d [%.1f–%.1f s]: no face detections.",
                seg["segment_id"], start, end,
            )
            continue

        # Majority vote across detected emotions in this window
        emotion_counts = Counter(fe["dominant_emotion"] for fe in faced_frames)
        dominant_emotion, _ = emotion_counts.most_common(1)[0]

        # Mean confidence of frames that agree with the dominant label
        matching = [
            fe["confidence"] for fe in faced_frames
            if fe["dominant_emotion"] == dominant_emotion
        ]
        mean_confidence = round(sum(matching) / len(matching), 4) if matching else 0.0

        seg["facial_emotion"] = {
            "dominant":    dominant_emotion,
            "confidence":  mean_confidence,
            "frame_count": len(faced_frames),
            "reliability": FACIAL_CHANNEL_RELIABILITY,
        }
        logger.debug(
            "Segment %d [%.1f–%.1f s]: dominant=%s conf=%.2f faces=%d",
            seg["segment_id"], start, end,
            dominant_emotion, mean_confidence, len(faced_frames),
        )

    return segments
