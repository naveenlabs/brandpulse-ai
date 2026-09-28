"""
ground_truth.py - the single loader for the hand-labelled transcript ground truth.

Every scoring script in this bench reads its labels through here, so that the
selection/confirmation split is enforced by code rather than by memory.

The split is defined in HOLDOUT_PROTOCOL.md Section 2 and was fixed before any
label was entered. `load()` therefore requires the caller to name the split it
wants. There is deliberately no "give me everything" default: asking for the
sealed set has to be a thing someone typed on purpose.

Usage
-----
    from ground_truth import load, LABELS

    rows = load("selection")            # 400 rows, freely inspectable
    rows = load("confirmation")         # 199 rows, sealed until a winner is fixed
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
SHEET = BENCH_DIR / "labels" / "transcript_label_sheet.csv"
MANIFEST = BENCH_DIR / "_sheet_manifest.json"
CORPUS_DIR = BENCH_DIR / "corpus"

LABEL_COLUMN = "label_POSITIVE_NEUTRAL_NEGATIVE"
LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")
SPLITS = ("selection", "confirmation")


class GroundTruthError(RuntimeError):
    """Raised when the sheet and the manifest disagree, or a label is unusable."""


def _read_manifest() -> dict[str, dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {row["segment_uid"]: row for row in manifest["rows"]}


def load(split: str) -> list[dict]:
    """Return the labelled rows for one split, validated.

    Raises GroundTruthError rather than returning partial data: a bench that
    silently drops unlabelled rows would quietly change its own denominator.
    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")

    meta = _read_manifest()
    with SHEET.open(encoding="utf-8") as fh:
        sheet = list(csv.DictReader(fh))

    if len(sheet) != len(meta):
        raise GroundTruthError(
            f"sheet has {len(sheet)} rows, manifest has {len(meta)}"
        )

    rows: list[dict] = []
    for record in sheet:
        uid = record["segment_uid"]
        if uid not in meta:
            raise GroundTruthError(f"row {record['row']}: uid {uid!r} not in manifest")

        label = record[LABEL_COLUMN].strip().upper()
        if not label:
            raise GroundTruthError(f"row {record['row']} ({uid}) is unlabelled")
        if label not in LABELS:
            raise GroundTruthError(
                f"row {record['row']} ({uid}): label {record[LABEL_COLUMN]!r} "
                f"is not one of {LABELS}"
            )

        entry = meta[uid]
        if entry["split"] != split:
            continue

        rows.append(
            {
                "row": int(record["row"]),
                "segment_uid": uid,
                "video_id": entry["video_id"],
                "channel": entry["channel"],
                "split": entry["split"],
                "start_time": entry["start_time"],
                "duration": entry["duration"],
                "word_count": entry["word_count"],
                "text": record["TEXT_TO_RATE"],
                "context_before": record["context_before_DO_NOT_RATE"],
                "context_after": record["context_after_DO_NOT_RATE"],
                "gold": label,
            }
        )

    if not rows:
        raise GroundTruthError(f"no rows found for split {split!r}")
    return rows
