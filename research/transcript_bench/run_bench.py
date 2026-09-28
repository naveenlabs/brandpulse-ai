"""
run_bench.py - score the registered candidates against the hand-labelled ground truth.

Predictions are cached to predictions/<candidate_id>__<split>.json. Re-running is
therefore free for anything already scored, and the analysis in report_bench.py can
be re-derived without touching a model. Use --force to re-score.

The sealed confirmation set requires --split confirmation to be typed explicitly and
refuses to run unless WINNER.md exists, so the holdout cannot be scored by accident
before a winner has been committed to (HOLDOUT_PROTOCOL.md Section 2).

Usage
-----
    python research/transcript_bench/run_bench.py                       # all, selection set
    python research/transcript_bench/run_bench.py --only 1.1 4.2        # a subset
    python research/transcript_bench/run_bench.py --split confirmation  # after a winner is fixed
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR))

import candidates as C           # noqa: E402
from ground_truth import load    # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("bench")

PRED_DIR = BENCH_DIR / "predictions"
WINNER_FILE = BENCH_DIR / "WINNER.md"


def prediction_path(candidate_id: str, split: str) -> Path:
    return PRED_DIR / f"{candidate_id}__{split}.json"


def score_one(entry: dict, rows: list[dict], split: str, force: bool) -> dict:
    path = prediction_path(entry["id"], split)
    if path.exists() and not force:
        logger.info("%-26s cached", entry["id"])
        return json.loads(path.read_text(encoding="utf-8"))

    logger.info("%-26s running on %d rows ...", entry["id"], len(rows))
    started = time.time()
    preds = C.run_candidate(entry, rows)
    elapsed = time.time() - started

    if len(preds) != len(rows):
        raise RuntimeError(
            f"{entry['id']} returned {len(preds)} predictions for {len(rows)} rows"
        )

    record = {
        "candidate_id": entry["id"],
        "name": entry["name"],
        "group": entry["group"],
        "model": entry["model"],
        "kind": entry["kind"],
        "split": split,
        "n_rows": len(rows),
        "elapsed_s": round(elapsed, 2),
        "seconds_per_row": round(elapsed / len(rows), 4),
        "predictions": [
            {
                "segment_uid": row["segment_uid"],
                "gold": row["gold"],
                **{k: v for k, v in pred.items() if k != "scores"},
                "scores": pred.get("scores"),
            }
            for row, pred in zip(rows, preds)
        ],
    }
    PRED_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    logger.info("%-26s done in %.1fs -> %s", entry["id"], elapsed, path.name)
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="selection", choices=["selection", "confirmation"])
    ap.add_argument("--only", nargs="*", default=None,
                    help="candidate id prefixes, e.g. 1.1 4.2")
    ap.add_argument("--force", action="store_true", help="re-score even if cached")
    args = ap.parse_args()

    if args.split == "confirmation" and not WINNER_FILE.exists():
        logger.error(
            "refusing to score the sealed confirmation set: %s does not exist. "
            "Choose and record a winner on the selection set first "
            "(HOLDOUT_PROTOCOL.md Section 2).",
            WINNER_FILE.name,
        )
        return 2

    rows = load(args.split)
    logger.info("%s set: %d rows", args.split, len(rows))

    entries = C.REGISTRY
    if args.only:
        entries = [e for e in entries if any(e["id"].startswith(p) for p in args.only)]
        if not entries:
            logger.error("no candidates matched %s", args.only)
            return 2

    failures = []
    for entry in entries:
        try:
            score_one(entry, rows, args.split, args.force)
        except Exception as exc:
            # One dead candidate must not abort a 15-candidate run.
            logger.error("%-26s FAILED: %s: %s", entry["id"], type(exc).__name__, exc)
            failures.append((entry["id"], f"{type(exc).__name__}: {exc}"))

    if failures:
        logger.warning("%d candidate(s) failed:", len(failures))
        for cid, err in failures:
            logger.warning("  %s - %s", cid, err[:160])
    logger.info("scored %d/%d", len(entries) - len(failures), len(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
