"""
ground_truth.py - load and validate the human vocal-tone ratings.

One loader, used by every consumer, so the collapse from a 5-point rating to
three classes happens in exactly one place and cannot drift between scripts.

The 5 -> 3 collapse is the one fixed in CANDIDATE_MODELS.md section 3 before any
rating was given:

    1 clearly negative, 2 slightly negative  -> NEGATIVE
    3 neutral                                -> NEUTRAL
    4 slightly positive, 5 clearly positive  -> POSITIVE
    0 can't tell                             -> EXCLUDED, counted, never guessed

`load(split)` requires an explicit split and raises rather than returning partial
data: a scorer that silently drops rows changes its own denominator without
changing the reported n.
"""

from __future__ import annotations

import json
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
RATINGS = BENCH_DIR / "vocal_ground_truth.json"
INDEX = BENCH_DIR / "_clip_index.json"

SPLITS = ("selection", "confirmation")
LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")

# Fixed in CANDIDATE_MODELS.md section 3, before rating.
RATING_TO_CLASS = {1: "NEGATIVE", 2: "NEGATIVE", 3: "NEUTRAL",
                   4: "POSITIVE", 5: "POSITIVE"}
CANT_TELL = 0


class GroundTruthError(RuntimeError):
    """Ratings are missing, incomplete, or disagree with the clip index."""


def _load_all() -> tuple[dict[str, int], dict[str, dict]]:
    if not RATINGS.is_file():
        raise GroundTruthError(
            f"{RATINGS} not found. Rate the clips in rate_here.html and click "
            f"Export - no model output can substitute for it."
        )
    payload = json.loads(RATINGS.read_text())
    ratings = payload.get("ratings")
    if not isinstance(ratings, dict):
        raise GroundTruthError("vocal_ground_truth.json has no 'ratings' object")

    clips = {c["uid"]: c for c in json.loads(INDEX.read_text())["clips"]}

    unknown = set(ratings) - set(clips)
    if unknown:
        raise GroundTruthError(f"ratings contain unknown clip ids: {sorted(unknown)[:5]}")
    missing = set(clips) - set(ratings)
    if missing:
        raise GroundTruthError(
            f"{len(missing)} of {len(clips)} clips were never rated: "
            f"{sorted(missing)[:5]}"
        )
    bad = {u: v for u, v in ratings.items() if v not in RATING_TO_CLASS and v != CANT_TELL}
    if bad:
        raise GroundTruthError(f"ratings outside 0-5: {list(bad.items())[:5]}")

    return {u: int(v) for u, v in ratings.items()}, clips


def load(split: str, include_cant_tell: bool = False) -> list[dict]:
    """Rated clips for one split.

    Rows carry the raw 1-5 rating alongside the collapsed class, because the
    ordinal information is needed for the Spearman correlation reported for the
    dimensional candidate and would be destroyed by collapsing early.
    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")

    ratings, clips = _load_all()
    rows = []
    for uid, rating in ratings.items():
        clip = clips[uid]
        if clip["split"] != split:
            continue
        if rating == CANT_TELL and not include_cant_tell:
            continue
        rows.append({
            "uid": uid,
            "video_id": clip["video_id"],
            "channel": clip["channel"],
            "split": split,
            "duration": clip["duration"],
            "rating": rating,
            "label": RATING_TO_CLASS.get(rating),  # None for can't-tell
        })
    return sorted(rows, key=lambda r: r["uid"])


def counts() -> dict:
    """Rating distribution, for reporting the sample honestly."""
    ratings, clips = _load_all()
    out: dict = {"total": len(ratings), "by_split": {}}
    for split in SPLITS:
        rows = load(split, include_cant_tell=True)
        dist = {}
        for r in rows:
            key = r["label"] or "CANT_TELL"
            dist[key] = dist.get(key, 0) + 1
        raw = {}
        for r in rows:
            raw[r["rating"]] = raw.get(r["rating"], 0) + 1
        out["by_split"][split] = {
            "n_rated": len(rows),
            "n_scorable": sum(1 for r in rows if r["label"]),
            "classes": dist,
            "raw_ratings": dict(sorted(raw.items())),
            "speakers": sorted({r["channel"] for r in rows}),
        }
    return out
