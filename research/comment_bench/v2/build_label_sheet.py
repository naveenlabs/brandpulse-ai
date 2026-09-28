#!/usr/bin/env python3
"""
comment_bench/v2/build_label_sheet.py

Stage 3 of the v2 comment bench: draw the human-labelling samples.

Sampling design
---------------
Two samples are drawn, and they are NEVER pooled when reporting accuracy.

  Sample A - ACCURACY (n=300, 30 per video, simple random within video)
      An unbiased estimate of how each model performs on the corpus. Equal draw per
      video by design: the 500-per-video fetch cap exists so no single video decides
      the result, and the sample inherits that. This is the only sample any headline
      accuracy figure may be computed on.

  Sample B - DIAGNOSTIC (n=50, drawn from three-way model disagreements)
      Deliberately enriched with hard cases to characterise HOW each model fails.
      Accuracy on Sample B is meaningless by construction and must never be quoted as
      a headline number. It exists for the failure taxonomy only.

  Rater-2 overlap (n=100, drawn from Sample A)
      Labelled independently by a second person to compute Cohen's kappa. Drawn from
      Sample A so that inter-rater agreement is measured on the same distribution the
      accuracy claim rests on.

Blindness
---------
The sheets contain the comment text and nothing else. No model predictions, no
confidence values, no agreement flags. Ground truth is never derived from, or primed
by, the models under test (step 2 of the bench method, README).

Reproducibility
---------------
Fixed seed. Re-running reproduces identical samples. The manifest records exactly which
comment_id landed in which sample and why.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/build_label_sheet.py
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
SCORED_DIR = BENCH_DIR / "scored"
LABELS_DIR = BENCH_DIR / "labels"

SEED = 42
PER_VIDEO_ACCURACY = 30      # Sample A: 30 x 10 videos = 300
DIAGNOSTIC_N = 50            # Sample B
OVERLAP_N = 100              # rater-2 subset of Sample A
MODELS = ("cardiffnlp", "tabularisai", "VADER")

HUMAN_COL = "label_POSITIVE_NEUTRAL_NEGATIVE"

logger = logging.getLogger("build_label_sheet")


def normalise(text: str) -> str:
    """Fold whitespace and unicode form so near-identical spam collapses together."""
    return unicodedata.normalize("NFKC", " ".join(text.split())).strip().lower()


def load_scored() -> list[dict]:
    files = sorted(p for p in SCORED_DIR.glob("*.json") if not p.name.startswith("_"))
    if not files:
        raise FileNotFoundError(f"No scored files in {SCORED_DIR}. Run run_models.py first.")
    out: list[dict] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for comment in data["comments"]:
            comment["video_id"] = data["video_id"]
            out.append(comment)
    return out


def is_labelable(comment: dict) -> bool:
    """Exclude anything a human cannot meaningfully rate."""
    text = comment.get("text", "").strip()
    return len(text) >= 2


def write_sheet(path: Path, rows: list[dict]) -> None:
    """
    Write a blind labelling CSV: row number, comment id, text, blank label column.

    Deliberately a plain CSV with no comment preamble. Spreadsheet applications treat
    leading '#' lines as data rows, which pushes the real header down and breaks sorting
    and filtering. The instructions live in GUIDELINES.md instead.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", "comment_id", "text", HUMAN_COL])
        for i, comment in enumerate(rows, start=1):
            writer.writerow([i, comment["comment_id"], comment["text"], ""])


def main() -> int:
    parser = argparse.ArgumentParser(description="Draw the v2 human-labelling samples.")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing sheets (destroys any labelling in progress).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    rater1_path = LABELS_DIR / "label_sheet_rater1.csv"
    if rater1_path.exists() and not args.force:
        logger.error("%s already exists. Refusing to overwrite labelling work.", rater1_path.name)
        logger.error("Pass --force only if you are certain no labels have been entered.")
        return 1

    rng = random.Random(args.seed)
    comments = load_scored()
    logger.info("Loaded %d scored comments.", len(comments))

    labelable = [c for c in comments if is_labelable(c)]
    logger.info("Labelable (text >= 2 chars): %d", len(labelable))

    # Deduplicate by normalised text so identical spam is not labelled repeatedly.
    seen: set[str] = set()
    unique: list[dict] = []
    for comment in labelable:
        key = normalise(comment["text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(comment)
    logger.info("Unique by normalised text: %d (removed %d duplicates)",
                len(unique), len(labelable) - len(unique))

    by_video: dict[str, list[dict]] = {}
    for comment in unique:
        by_video.setdefault(comment["video_id"], []).append(comment)

    # ── Sample A: accuracy ────────────────────────────────────────────────────
    sample_a: list[dict] = []
    for vid in sorted(by_video):
        pool = sorted(by_video[vid], key=lambda c: c["comment_id"])  # deterministic order
        take = min(PER_VIDEO_ACCURACY, len(pool))
        if take < PER_VIDEO_ACCURACY:
            logger.warning("  %s has only %d unique comments, taking all.", vid, take)
        sample_a.extend(rng.sample(pool, take))
    logger.info("Sample A (accuracy): %d", len(sample_a))

    # ── Sample B: three-way disagreement, excluding anything already in A ─────
    in_a = {c["comment_id"] for c in sample_a}
    three_way = [
        c for c in unique
        if c["comment_id"] not in in_a
        and len({c["models"][m]["label"] for m in MODELS}) == 3
    ]
    take_b = min(DIAGNOSTIC_N, len(three_way))
    sample_b = rng.sample(sorted(three_way, key=lambda c: c["comment_id"]), take_b)
    logger.info("Sample B (diagnostic): %d drawn from %d three-way disagreements",
                len(sample_b), len(three_way))

    # ── Rater-2 overlap: subset of A ──────────────────────────────────────────
    overlap = rng.sample(sorted(sample_a, key=lambda c: c["comment_id"]),
                         min(OVERLAP_N, len(sample_a)))
    logger.info("Rater-2 overlap: %d (subset of Sample A)", len(overlap))

    # ── Write sheets ──────────────────────────────────────────────────────────
    rater1_rows = sample_a + sample_b
    rng.shuffle(rater1_rows)     # break any video / difficulty ordering effect
    write_sheet(rater1_path, rater1_rows)

    rater2_rows = list(overlap)
    rng.shuffle(rater2_rows)     # different order from rater 1, independently judged
    write_sheet(LABELS_DIR / "label_sheet_rater2.csv", rater2_rows)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "corpus_total": len(comments),
        "labelable": len(labelable),
        "unique_after_dedup": len(unique),
        "sample_a_accuracy": {
            "n": len(sample_a),
            "per_video": PER_VIDEO_ACCURACY,
            "comment_ids": sorted(c["comment_id"] for c in sample_a),
        },
        "sample_b_diagnostic": {
            "n": len(sample_b),
            "drawn_from_three_way_disagreements": len(three_way),
            "comment_ids": sorted(c["comment_id"] for c in sample_b),
        },
        "rater2_overlap": {
            "n": len(overlap),
            "drawn_from": "sample_a",
            "comment_ids": sorted(c["comment_id"] for c in overlap),
        },
    }
    (LABELS_DIR / "_sample_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("\n%s", "-" * 78)
    logger.info("Rater 1 sheet : %s  (%d rows)", rater1_path.name, len(rater1_rows))
    logger.info("Rater 2 sheet : label_sheet_rater2.csv  (%d rows)", len(rater2_rows))
    logger.info("Manifest      : _sample_manifest.json")
    logger.info("\nNeither sheet contains model predictions. Labelling is blind by design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
