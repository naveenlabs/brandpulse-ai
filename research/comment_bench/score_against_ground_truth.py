#!/usr/bin/env python3
"""
comment_bench/score_against_ground_truth.py

Run AFTER the friend has filled in the human_label column in friend_rating_sample.csv.

Scores tabularisai / VADER / cardiffnlp against the friend's real labels on that sample,
and prints + saves a simple accuracy table — this is what goes in Chapter 5.

Usage:
    python research/comment_bench/score_against_ground_truth.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

BENCH_DIR = Path(__file__).parent


def main() -> None:
    sample_path = BENCH_DIR / "friend_rating_sample.csv"
    results_path = BENCH_DIR / "all_results.json"

    if not sample_path.exists():
        print(f"Missing {sample_path} — run run_bench.py first.")
        return
    if not results_path.exists():
        print(f"Missing {results_path} — run run_bench.py first.")
        return

    all_results = json.loads(results_path.read_text())
    # Flatten to comment_id -> full comment record (with all 3 model labels)
    by_id: dict[str, dict] = {}
    for video_id, result in all_results.items():
        for c in result["comments"]:
            by_id[str(c.get("comment_id"))] = c

    rows = list(csv.DictReader(open(sample_path, encoding="utf-8")))
    human_col = "human_label(POSITIVE/NEUTRAL/NEGATIVE)"

    counts = {"tabularisai": 0, "VADER": 0, "cardiffnlp": 0}
    rated = 0
    skipped_unrated = 0
    skipped_missing = 0

    for row in rows:
        human = row.get(human_col, "").strip().upper()
        if not human:
            skipped_unrated += 1
            continue
        if human not in {"POSITIVE", "NEUTRAL", "NEGATIVE"}:
            print(f"  Warning: unrecognised human_label '{human}' for comment {row['comment_id']} — skipping")
            skipped_unrated += 1
            continue

        comment = by_id.get(row["comment_id"])
        if comment is None:
            skipped_missing += 1
            continue

        rated += 1
        if comment.get("sentiment_label") == human:
            counts["tabularisai"] += 1
        if comment.get("vader_label") == human:
            counts["VADER"] += 1
        if comment.get("cardiff_label") == human:
            counts["cardiffnlp"] += 1

    if rated == 0:
        print(f"No rated comments found. Fill in the '{human_col}' column in {sample_path} first.")
        print(f"({skipped_unrated} still blank, {skipped_missing} not matched to results)")
        return

    print(f"Scored against {rated} human-rated comments ({skipped_unrated} still blank, skipped).\n")

    report = {"rated_comment_count": rated, "accuracy": {}}
    print(f"{'Model':<15} {'Correct':>8} {'Accuracy':>10}")
    print("-" * 35)
    for model, correct in sorted(counts.items(), key=lambda kv: -kv[1]):
        acc = round(correct / rated * 100, 1)
        report["accuracy"][model] = {"correct": correct, "total": rated, "accuracy_pct": acc}
        print(f"{model:<15} {correct:>8} {acc:>9}%")

    winner = max(counts, key=counts.get)
    report["winner"] = winner
    print(f"\nWinner: {winner}")

    out_path = BENCH_DIR / "accuracy_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
