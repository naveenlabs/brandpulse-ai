#!/usr/bin/env python3
"""
comment_bench/v2/build_training_sheet.py

Build the fine-tuning TRAINING label sheet: 1,000 comments, 100 per video, drawn at
random from the frozen corpus.

Contamination control (the point of this script)
-----------------------------------------------
The 350 comments in labels/label_sheet_rater1.csv are the project's ONLY held-out
test set. Every accuracy figure in HUMAN_GROUND_TRUTH_EVALUATION.md is measured on
them. If any of them appears in training data, that number stops meaning anything.

This script therefore excludes, by comment_id:
  * all 300 Sample A comments
  * all 50 Sample B comments
and additionally drops blank comments and exact duplicate texts, so the model is not
trained on the same string twice (or on a string that also appears in the test set
under a different id).

Why a random draw, not an enriched one
--------------------------------------
Sample B was deliberately enriched with hard cases because its job is diagnosis.
Training data has the opposite requirement: it must match the real distribution.
Over-representing ambiguous comments teaches the model that ambiguity is common,
when roughly a third of the feed is neutral and most of it is not borderline.

Determinism
-----------
Seed 42, matching build_label_sheet.py, so the draw is reproducible and the manifest
records exactly which comments were selected.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/build_training_sheet.py
    python research/comment_bench/v2/build_training_sheet.py --per-video 150 --force
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BENCH_DIR / "corpus"
LABELS_DIR = BENCH_DIR / "labels"
TRAIN_DIR = BENCH_DIR / "train"

SEED = 42
PER_VIDEO = 100
HUMAN_COL = "label_POSITIVE_NEUTRAL_NEGATIVE"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_training_sheet")


def _norm(text: str) -> str:
    """Whitespace-collapsed, case-folded form, for duplicate detection."""
    return " ".join(text.split()).lower()


def load_corpus() -> list[dict]:
    rows: list[dict] = []
    for f in sorted(p for p in CORPUS_DIR.glob("*.json") if not p.name.startswith("_")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for c in doc["comments"]:
            rows.append({
                "comment_id": c["comment_id"],
                "video_id": doc["video_id"],
                "video_title": doc.get("video_title") or doc["video_id"],
                "text": c["text"],
            })
    return rows


def held_out_ids() -> set[str]:
    """Every comment_id that must never appear in training data."""
    manifest = json.loads((LABELS_DIR / "_sample_manifest.json").read_text())
    ids = set(manifest["sample_a_accuracy"]["comment_ids"])
    ids |= set(manifest["sample_b_diagnostic"]["comment_ids"])
    # Belt and braces: also read the sheets themselves, in case they ever diverge
    # from the manifest.
    for name in ("label_sheet_rater1.csv", "label_sheet_rater2.csv"):
        p = LABELS_DIR / name
        if p.exists():
            ids |= {r["comment_id"] for r in csv.DictReader(p.open())}
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-video", type=int, default=PER_VIDEO)
    ap.add_argument("--force", action="store_true", help="overwrite an existing sheet")
    args = ap.parse_args()

    out_csv = TRAIN_DIR / "train_sheet.csv"
    if out_csv.exists() and not args.force:
        logger.error("%s already exists. Use --force to regenerate "
                     "(this DISCARDS any labels already entered).", out_csv)
        return 1

    corpus = load_corpus()
    excluded = held_out_ids()
    logger.info("corpus: %d comments | held-out (test set): %d", len(corpus), len(excluded))

    # Exclude the test set, blanks, and duplicate texts.
    seen: set[str] = set()
    # Seed the duplicate filter with the held-out texts too, so a training comment
    # that merely repeats a test comment's wording is also dropped.
    for r in corpus:
        if r["comment_id"] in excluded:
            seen.add(_norm(r["text"]))

    pool: dict[str, list[dict]] = {}
    dropped_dupe = dropped_blank = 0
    for r in corpus:
        if r["comment_id"] in excluded:
            continue
        t = _norm(r["text"])
        if not t:
            dropped_blank += 1
            continue
        if t in seen:
            dropped_dupe += 1
            continue
        seen.add(t)
        pool.setdefault(r["video_id"], []).append(r)

    logger.info("dropped: %d blank, %d duplicate text", dropped_blank, dropped_dupe)
    logger.info("pool: %d comments across %d videos",
                sum(len(v) for v in pool.values()), len(pool))

    short = {v: len(rs) for v, rs in pool.items() if len(rs) < args.per_video}
    if short:
        logger.error("videos with fewer than %d available: %s", args.per_video, short)
        return 1

    rng = random.Random(SEED)
    selected: list[dict] = []
    for vid in sorted(pool):
        rows = sorted(pool[vid], key=lambda r: r["comment_id"])   # stable before sampling
        selected.extend(rng.sample(rows, args.per_video))

    rng.shuffle(selected)   # interleave videos so the rater does not label one video in a block

    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "comment_id", "text", HUMAN_COL])
        for i, r in enumerate(selected, 1):
            w.writerow([i, r["comment_id"], r["text"], ""])

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "fine-tuning training labels (NOT a test set)",
        "seed": SEED,
        "per_video": args.per_video,
        "n": len(selected),
        "corpus_total": len(corpus),
        "excluded_test_ids": len(excluded),
        "dropped_blank": dropped_blank,
        "dropped_duplicate_text": dropped_dupe,
        "overlap_with_test_set": 0,
        "comment_ids": [r["comment_id"] for r in selected],
    }
    (TRAIN_DIR / "_train_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Hard assertion rather than a comment: contamination must be impossible.
    assert not ({r["comment_id"] for r in selected} & excluded), "TEST SET CONTAMINATION"

    logger.info("wrote %s (%d rows)", out_csv, len(selected))
    logger.info("wrote %s", TRAIN_DIR / "_train_manifest.json")
    logger.info("verified: 0 overlap with the %d held-out test comments", len(excluded))
    return 0


if __name__ == "__main__":
    sys.exit(main())
