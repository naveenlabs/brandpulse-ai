#!/usr/bin/env python3
"""
comment_bench/v2/holdout_prepare.py

Score the held-out videos with BOTH the base and the fine-tuned model, and build a
blind labelling sheet.

Why this exists
---------------
The fine-tuned model was trained on 1,000 comments drawn from the ten videos in
videos.txt. Its measured +3.00 points and its significant NEGATIVE-recall gain are
therefore both from videos whose vocabulary, products and commenter register it has
seen. This stage tests whether that transfers to videos it has seen nothing from.

Scope of the test, stated precisely
-----------------------------------
Both held-out videos are phone reviews, the same category as eight of the ten training
videos. This measures NEAR-domain generalisation: unseen videos, familiar category. It
does NOT measure cross-category transfer, and no claim of that kind may be made from it.

Contamination control
---------------------
Verified before sampling: 0 shared comment_ids with the training corpus. Comments whose
text appears verbatim in the training corpus are dropped, as are duplicates within the
held-out set itself.

Blindness
---------
The label sheet contains row, comment_id and text only. Model predictions are written to
a SEPARATE file the rater never opens.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/holdout_prepare.py
    python research/comment_bench/v2/holdout_prepare.py --per-video 100 --force
"""

from __future__ import annotations

import argparse
import csv
import json
import glob
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path(__file__).resolve().parent
HOLDOUT_CORPUS = BENCH / "corpus_holdout"
TRAIN_CORPUS = BENCH / "corpus"
FINETUNED = BENCH / "finetuned"
OUT_DIR = BENCH / "holdout"

BASE_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
CLASSES = ["NEGATIVE", "NEUTRAL", "POSITIVE"]
SEED = 42
PER_VIDEO = 75
MAX_LEN = 128
HUMAN_COL = "label_POSITIVE_NEUTRAL_NEGATIVE"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("holdout_prepare")


def norm(t: str) -> str:
    return " ".join(t.split()).lower()


def load_corpus(d: Path) -> list[dict]:
    rows = []
    for f in sorted(p for p in d.glob("*.json") if not p.name.startswith("_")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        title = (doc.get("metadata") or {}).get("title") or doc["video_id"]
        for c in doc["comments"]:
            rows.append({"comment_id": c["comment_id"], "video_id": doc["video_id"],
                         "video_title": title, "text": c["text"]})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-video", type=int, default=PER_VIDEO)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    sheet_path = OUT_DIR / "holdout_label_sheet.csv"
    if sheet_path.exists() and not args.force:
        logger.error("%s exists. --force to regenerate (DISCARDS entered labels).", sheet_path)
        return 1
    if not FINETUNED.exists():
        logger.error("No fine-tuned model at %s. Run finetune_cardiffnlp.py first.", FINETUNED)
        return 1

    held = load_corpus(HOLDOUT_CORPUS)
    train = load_corpus(TRAIN_CORPUS)
    train_ids = {r["comment_id"] for r in train}
    train_texts = {norm(r["text"]) for r in train}

    overlap = len(train_ids & {r["comment_id"] for r in held})
    if overlap:
        logger.error("CONTAMINATION: %d held-out comments appear in the training corpus", overlap)
        return 1
    logger.info("held-out: %d comments, 0 comment_id overlap with training corpus", len(held))

    # ---- score every held-out comment with both models
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    device = torch.device("mps" if torch.backends.mps.is_available()
                          else "cuda" if torch.cuda.is_available() else "cpu")
    texts = [r["text"] for r in held]

    def score(model_path: str | Path, tag: str) -> list[dict]:
        tok = AutoTokenizer.from_pretrained(str(model_path))
        mdl = AutoModelForSequenceClassification.from_pretrained(str(model_path)).to(device).eval()
        id2 = mdl.config.id2label
        order = [id2[i].lower() for i in range(len(id2))]
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), 32):
                enc = tok(texts[i:i + 32], truncation=True, max_length=MAX_LEN,
                          padding=True, return_tensors="pt").to(device)
                probs = mdl(**enc).logits.softmax(-1).cpu()
                for row in probs:
                    d = {order[j].upper(): round(float(row[j]), 6) for j in range(len(order))}
                    out.append({"label": max(d, key=d.get), "probs": d})
        del mdl
        if device.type == "mps":
            torch.mps.empty_cache()
        logger.info("scored %d comments with %s", len(out), tag)
        return out

    base = score(BASE_MODEL, "base")
    ft = score(FINETUNED, "fine-tuned")

    preds_path = OUT_DIR / "_holdout_predictions.json"
    preds_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_model": BASE_MODEL,
        "finetuned_model": str(FINETUNED.relative_to(BENCH.parent.parent)),
        "n": len(held),
        "note": "Rater must not open this file. Written separately to keep labelling blind.",
        "predictions": [
            {"comment_id": r["comment_id"], "video_id": r["video_id"],
             "text": r["text"], "base": b["label"], "finetuned": f["label"],
             "base_probs": b["probs"], "finetuned_probs": f["probs"]}
            for r, b, f in zip(held, base, ft)
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("predictions -> %s", preds_path.name)

    # ---- build the blind label sheet
    seen = set(train_texts)
    pool: dict[str, list[dict]] = {}
    drop_dup = 0
    for r in held:
        t = norm(r["text"])
        if not t or t in seen:
            drop_dup += 1
            continue
        seen.add(t)
        pool.setdefault(r["video_id"], []).append(r)
    logger.info("dropped %d blank/duplicate; pool %s",
                drop_dup, {k: len(v) for k, v in pool.items()})

    rng = random.Random(SEED)
    sel = []
    for vid in sorted(pool):
        rows = sorted(pool[vid], key=lambda r: r["comment_id"])
        sel.extend(rng.sample(rows, min(args.per_video, len(rows))))
    rng.shuffle(sel)

    with sheet_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "comment_id", "text", HUMAN_COL])
        for i, r in enumerate(sel, 1):
            w.writerow([i, r["comment_id"], r["text"], ""])

    (OUT_DIR / "_holdout_manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "near-domain generalisation test for the fine-tuned model",
        "scope_note": ("Both videos are phone reviews, the same category as 8 of the 10 "
                       "training videos. Tests unseen videos in a familiar category. "
                       "Does NOT test cross-category transfer."),
        "seed": SEED, "per_video": args.per_video, "n": len(sel),
        "videos": sorted({r["video_id"] for r in sel}),
        "video_titles": {r["video_id"]: r["video_title"] for r in sel},
        "comment_id_overlap_with_training": 0,
        "dropped_blank_or_duplicate": drop_dup,
        "comment_ids": [r["comment_id"] for r in sel],
    }, indent=2), encoding="utf-8")

    assert not ({r["comment_id"] for r in sel} & train_ids), "CONTAMINATION"
    logger.info("label sheet -> %s (%d rows)", sheet_path, len(sel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
