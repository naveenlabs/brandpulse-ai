"""
scorer.py — the final scores, and the report they are saved in

  - Influencer Authenticity Score (0–100):
      100 − (weighted mean conflict score × 100); flagged segments count twice.
  - Brand Health Score (0–100):
      comment sentiment (60 %) blended with the authenticity score (40 %).
  - build_final_report(): the saved report, which always carries BIAS_CAVEAT,
    VOCAL_CAVEAT and VOCAL_LICENCE_NOTE.
  - json_default(): the `default=` every report dump uses.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

BIAS_CAVEAT = (
    "IMPORTANT: Facial emotion recognition (DeepFace) has documented accuracy "
    "disparities across skin tone and gender (Buolamwini & Gebru, 2018; Fan et al., 2023). "
    "Authenticity scores informed by facial data should be interpreted with this limitation in mind."
)

# Added 02 Sep 2026 alongside the vocal-channel swap. BIAS_CAVEAT names a
# limitation established in the literature; this one names a limitation measured
# here, on this project's own data, and every number in it is traceable to
# vocal_bench/.
#
# It is surfaced on every report for the same reason BIAS_CAVEAT is: a reader who
# sees only the headline score cannot otherwise tell that one of the four inputs
# is close to a coin flip. Burying that in the JSON would make the report look
# more confident than the evidence supports.
#
# 24 Sep 2026: "the weakest of the four" was true when this was written and
# stopped being true on 04 Sep, when facial_bench/v2 measured the facial channel
# at 34.2% on held-out speakers. The book prints both on facing pages, and in the
# final user evaluation two of five readers then named the voice, or nothing, as
# the least reliable channel (user_eval/SCORES.md, R14).
VOCAL_CAVEAT = (
    "IMPORTANT: The vocal emotion channel is the second weakest of the four, after "
    "facial emotion, and is explicitly down-weighted. Benchmarked on 150 hand-rated clips from 6 speakers "
    "(vocal_bench/), the adopted model scores 48.9% three-class accuracy on held-out "
    "speakers - better than the model it replaced, which at 34.0% was significantly "
    "worse than always guessing NEUTRAL (p = 0.0070), but still not reliably better "
    "than that constant. No model tested beat it. Conflicts attributed to the vocal "
    "channel alone are damped accordingly, and per-segment claims should not rest on "
    "this channel. Read the within-video figure, not the headline: this report "
    "compares segments inside one video, and the channel's rank correlation with "
    "human judgement measured within a video is +0.159 across 147 clips and +0.056 "
    "on unseen speakers (vocal_bench/SPEAKER_NORM_RESULT.md). Most of its apparent "
    "accuracy is a between-video effect that says more about the speaker's habitual "
    "energy than about any individual moment."
)

# Licence status of the adopted vocal checkpoint, carried on the report because a
# B2B prototype's deployability is part of its result, not a detail of its build.
VOCAL_LICENCE_NOTE = (
    "The adopted vocal model (audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim) "
    "is licensed CC-BY-NC-SA-4.0 and may not be used commercially. Every configuration "
    "measured in vocal_bench/ that showed usable signal was non-commercially licensed; "
    "the permissively-licensed alternatives measured at the bottom of every table. "
    "A commercial deployment would need to ship without this channel or replace it."
)


def compute_authenticity_score(conflict_results: list[dict]) -> float:
    """
    Compute Influencer Authenticity Score from per-segment conflict results.

    Formula: 100 − (weighted_mean_conflict × 100)
      weight = 2.0 if segment is flagged, else 1.0

    Returns float in [0.0, 100.0] rounded to 2 decimal places.
    """
    if not conflict_results:
        return 100.0

    total_weight = 0.0
    weighted_sum = 0.0

    for result in conflict_results:
        score = result.get("conflict_score", 0.0)
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            score = 0.0
        score = float(score)

        flagged = result.get("flagged", False)
        weight = 2.0 if flagged is True else 1.0

        weighted_sum += score * weight
        total_weight += weight

    weighted_mean = weighted_sum / total_weight if total_weight > 0.0 else 0.0
    raw = 100.0 - (weighted_mean * 100.0)
    result_score = max(0.0, min(100.0, raw))

    logger.debug(
        "compute_authenticity_score: weighted_mean=%.4f → %.2f",
        weighted_mean, result_score,
    )
    return round(result_score, 2)


def compute_brand_health_score(
    comment_sentiment: dict,
    authenticity_score: float,
) -> float:
    """
    Compute Brand Health Score from comment sentiment + authenticity score.

    Formula:
      comment_score = conf × 100  (POSITIVE)
                    = conf × 50   (NEUTRAL)
                    = 0.0         (NEGATIVE)
                    = 50.0        (unknown / empty)
      brand_health = (comment_score × 0.6) + (authenticity_score × 0.4)

    Returns float in [0.0, 100.0] rounded to 2 decimal places.
    """
    if not comment_sentiment:
        comment_score = 50.0
    else:
        label = comment_sentiment.get("label", "")
        conf = float(comment_sentiment.get("confidence", 0.0) or 0.0)

        if label == "POSITIVE":
            comment_score = conf * 100.0
        elif label == "NEUTRAL":
            comment_score = conf * 50.0
        elif label == "NEGATIVE":
            comment_score = 0.0
        else:
            comment_score = 50.0

    raw = (comment_score * 0.6) + (float(authenticity_score) * 0.4)
    result_score = max(0.0, min(100.0, raw))

    logger.debug(
        "compute_brand_health_score: comment_score=%.2f auth=%.2f → %.2f",
        comment_score, authenticity_score, result_score,
    )
    return round(result_score, 2)


def model_outputs(seg: dict) -> dict:
    """
    One segment's per-channel readings, as a saved report stores them beside the
    controller's conflict score (in `flagged_segments` and `all_segments`). A
    channel with no reading gets an explicit empty value, never a default guess.
    """
    return {
        "transcript_sentiment": seg.get(
            "transcript_sentiment", {"label": "UNKNOWN", "confidence": 0.0}
        ),
        "facial_emotion": seg.get(
            "facial_emotion", {"dominant": None, "confidence": 0.0}
        ),
        "vocal_emotion": seg.get(
            "vocal_emotion",
            {"label": "unknown", "arousal": None, "reliability": 0.0},
        ),
        "pitch_mean_hz": seg.get("pitch_mean", 0.0),
        "energy_mean": seg.get("energy_mean", 0.0),
    }


def build_final_report(
    video_url: str,
    brand_name: str,
    segments: list[dict],
    conflict_results: list[dict],
    comment_sentiment: dict,
) -> dict:
    """
    Assemble the final JSON-serialisable report dict.

    Returns
    -------
    {
      "video_url":           str,
      "brand_name":          str,
      "authenticity_score":  float,      # 0–100
      "brand_health_score":  float,      # 0–100
      "segment_count":       int,
      "flagged_segments":    list[dict], # flagged conflict results enriched with "text"
      "comment_sentiment":   dict,       # pass-through from aggregate_video_sentiment()
      "bias_caveat":         str,        # facial-emotion limitation (from the literature)
      "vocal_caveat":        str,        # vocal-channel limitation (measured here)
      "vocal_licence_note":  str,        # commercial-use restriction on the vocal model
    }
    """
    authenticity_score = compute_authenticity_score(conflict_results)
    brand_health_score = compute_brand_health_score(comment_sentiment, authenticity_score)

    # Build a segment_id → segment lookup for enrichment
    segments_by_id: dict = {seg.get("segment_id"): seg for seg in segments}

    flagged_segments: list[dict] = []
    for result in conflict_results:
        if result.get("flagged") is True:
            enriched = dict(result)
            seg = segments_by_id.get(result.get("segment_id"), {})
            enriched["text"] = seg.get("text", "")
            enriched["model_outputs"] = model_outputs(seg)
            flagged_segments.append(enriched)

    report = {
        "video_url":          video_url,
        "brand_name":         brand_name,
        "authenticity_score": authenticity_score,
        "brand_health_score": brand_health_score,
        "segment_count":      len(segments),
        "flagged_segments":   flagged_segments,
        "comment_sentiment":  comment_sentiment,
        "bias_caveat":        BIAS_CAVEAT,
        "vocal_caveat":       VOCAL_CAVEAT,
        "vocal_licence_note": VOCAL_LICENCE_NOTE,
    }

    logger.info(
        "build_final_report: brand=%r auth=%.2f health=%.2f flagged=%d/%d",
        brand_name, authenticity_score, brand_health_score,
        len(flagged_segments), len(conflict_results),
    )
    return report


def json_default(obj):
    """
    `default=` for json.dump of a report: numpy scalars (float32, int64, ...) that
    leak out of model outputs, DeepFace's especially, become Python numbers.
    Without it one stray value fails the dump part-way through the report.
    """
    if hasattr(obj, "item"):  # every numpy scalar implements .item()
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
