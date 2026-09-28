#!/usr/bin/env python3
"""
comment_bench/v2/make_browsable.py

Produce a human-readable CSV of what each model predicted, for eyeballing.

Contamination guard
-------------------
Every comment that appears in a labelling sheet is EXCLUDED. If a rater sees what a model
predicted for a comment they are about to label, their label is no longer independent and
the ground truth is compromised. This file therefore cannot be used to peek.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/make_browsable.py
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
MODELS = ("cardiffnlp", "tabularisai", "VADER")

logger = logging.getLogger("make_browsable")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    manifest_path = BENCH_DIR / "labels" / "_sample_manifest.json"
    excluded: set[str] = set()
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        excluded = (set(m["sample_a_accuracy"]["comment_ids"])
                    | set(m["sample_b_diagnostic"]["comment_ids"]))
    else:
        logger.warning("No sample manifest found; nothing will be excluded.")

    rows = []
    for path in sorted((BENCH_DIR / "scored").glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        title = (data.get("video_title") or "")[:40]
        for c in data["comments"]:
            if c["comment_id"] in excluded:
                continue
            labels = {m: c["models"][m]["label"] for m in MODELS}
            cf = c["models"]["cardiffnlp"]["probs"]
            rows.append({
                "video": title,
                "likes": c["like_count"],
                "replies": c["reply_count"],
                "text": " ".join(c["text"].split()),
                "cardiffnlp": labels["cardiffnlp"],
                "tabularisai": labels["tabularisai"],
                "VADER": labels["VADER"],
                "all_agree": "yes" if len(set(labels.values())) == 1 else "no",
                "how_many_differ": len(set(labels.values())),
                "cardiff_POS": round(cf["POSITIVE"], 3),
                "cardiff_NEU": round(cf["NEUTRAL"], 3),
                "cardiff_NEG": round(cf["NEGATIVE"], 3),
                "cardiff_confidence": round(max(cf.values()), 3),
            })

    # Most interesting first: full disagreement, then partial, then unanimous.
    rows.sort(key=lambda r: (-r["how_many_differ"], -r["likes"]))

    out = BENCH_DIR / "analysis" / "browse_model_predictions.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    disagree = sum(1 for r in rows if r["all_agree"] == "no")
    logger.info("Wrote %s", out)
    logger.info("  %d comments (%d excluded because they are in a labelling sheet)",
                len(rows), len(excluded))
    logger.info("  %d rows where the models disagree, sorted to the top", disagree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
