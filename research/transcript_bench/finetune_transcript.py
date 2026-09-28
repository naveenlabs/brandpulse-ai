#!/usr/bin/env python3
"""
transcript_bench/finetune_transcript.py

Fine-tune the adopted transcript-sentiment model on the 400 hand-labelled selection
segments and test it once on the 199 speaker-disjoint confirmation segments.

The question this answers
-------------------------
cardiffnlp/twitter-xlm-roberta-base-sentiment scores 0.647 on the selection set and
0.678 on the confirmation set off the shelf. It was trained on tweets. Do 400 in-domain
*spoken transcript* segments improve it, or is 400 too few to move a 278M-parameter
model?

Both answers are results. A null result is written up as a null result. The comparable
experiment on the comment channel had 1,000 training rows and gained +9.4 points on
held-out videos; this one has 400, so a smaller gain - or none - is the expectation.

Method is copied from comment_bench/v2/finetune_cardiffnlp.py rather than reinvented.
Differences are only those the data forces, and are noted below.

Data discipline
---------------
  selection set   400 segments, 2 speakers (MKBHD, Mrwhosetheboss)
      -> 320 train / 80 validation, stratified, seed 42
  confirmation    199 segments, 4 speakers that appear nowhere in training
      -> TEST ONLY. Never trained on, never used for early stopping, never used to
         pick a hyperparameter.

Validation comes out of the 400, not the 199. Using the test set to decide when to stop
would leak it and make the final number meaningless.

Declared honestly: the 199 confirmation segments were already used once, to confirm the
base model's selection-set win (WINNER.md Section 7). This is their second use. They were
not used to *choose* anything either time, so they remain an unbiased estimate of this
model's accuracy, but repeated reuse of a holdout erodes that guarantee and the count of
uses is therefore recorded rather than forgotten.

Differences from the comment version
------------------------------------
  max_len 64, not 128. Token audit over all 599 labelled segments: median 23, p95 34,
  max 57. 64 covers 100% of segments with no truncation at all, so unlike the comment
  run there is no truncation caveat on the comparison.

Usage
-----
    cd brandpulse_ai
    python research/transcript_bench/finetune_transcript.py
    python research/transcript_bench/finetune_transcript.py --epochs 8 --lr 1e-5
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))

import metrics                     # noqa: E402
from ground_truth import load      # noqa: E402

OUT_DIR = BENCH / "finetuned"
ANALYSIS = BENCH / "analysis"

BASE_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
CLASSES = ["NEGATIVE", "NEUTRAL", "POSITIVE"]
C2I = {c: i for i, c in enumerate(CLASSES)}
SEED = 42
MAX_LEN = 64   # covers 100% of labelled segments; see module docstring

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("finetune")


def stratified_split(rows: list[dict], frac_val: float, seed: int):
    """Split preserving class balance, ordered by uid first so it is seed-reproducible."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["gold"], []).append(r)
    rng = random.Random(seed)
    train, val = [], []
    for lab in sorted(by):
        items = sorted(by[lab], key=lambda x: x["segment_uid"])
        rng.shuffle(items)
        n_val = int(round(len(items) * frac_val))
        val.extend(items[:n_val])
        train.extend(items[n_val:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--max-len", type=int, default=MAX_LEN)
    ap.add_argument("--device", default="auto", choices=["auto", "mps", "cpu", "cuda"])
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--tune-only", action="store_true",
                    help="select on validation and stop. The test set is never "
                         "loaded or scored, so hyperparameters can be compared "
                         "without spending a use of the holdout.")
    args = ap.parse_args()

    import numpy as np
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

    if args.device == "auto":
        dev = ("mps" if torch.backends.mps.is_available()
               else "cuda" if torch.cuda.is_available() else "cpu")
    else:
        dev = args.device
    device = torch.device(dev)
    max_len = args.max_len
    logger.info("device: %s | max_len: %d | batch: %d", device, max_len, args.batch_size)

    train_pool = load("selection")
    test_rows = load("confirmation")

    # Speaker-level, not just segment-level: the whole point of the split.
    train_speakers = {r["channel"] for r in train_pool}
    test_speakers = {r["channel"] for r in test_rows}
    assert not (train_speakers & test_speakers), "SPEAKER CONTAMINATION"
    assert not ({r["segment_uid"] for r in train_pool}
                & {r["segment_uid"] for r in test_rows}), "SEGMENT CONTAMINATION"
    logger.info("train pool %d (%s) | test %d (%s) | speaker overlap: none",
                len(train_pool), ", ".join(sorted(train_speakers)),
                len(test_rows), ", ".join(sorted(test_speakers)))

    tr, va = stratified_split(train_pool, args.val_frac, SEED)
    logger.info("split -> train %d, val %d", len(tr), len(va))
    logger.info("train dist %s", dict(Counter(r["gold"] for r in tr)))
    logger.info("val   dist %s", dict(Counter(r["gold"] for r in va)))

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)

    class DS(Dataset):
        def __init__(self, rows): self.rows = rows
        def __len__(self): return len(self.rows)
        def __getitem__(self, i):
            r = self.rows[i]
            return r["text"], C2I[r["gold"]]

    def collate(batch):
        texts = [b[0] for b in batch]
        labs = torch.tensor([b[1] for b in batch])
        enc = tok(texts, truncation=True, max_length=max_len,
                  padding=True, return_tensors="pt")
        return enc, labs

    g = torch.Generator(); g.manual_seed(SEED)
    dl_tr = DataLoader(DS(tr), batch_size=args.batch_size, shuffle=True,
                       collate_fn=collate, generator=g)

    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL).to(device)
    id2label = model.config.id2label
    logger.info("base head order: %s", id2label)
    assert [id2label[i].lower() for i in range(3)] == [c.lower() for c in CLASSES], \
        "label order mismatch - head cannot be reused as-is"

    def free():
        if device.type == "mps":
            torch.mps.empty_cache()
        elif device.type == "cuda":
            torch.cuda.empty_cache()

    @torch.no_grad()
    def predict(rows: list[dict]) -> list[str]:
        model.eval()
        out = []
        for i in range(0, len(rows), 32):
            chunk = rows[i:i + 32]
            enc = tok([r["text"] for r in chunk], truncation=True, max_length=max_len,
                      padding=True, return_tensors="pt").to(device)
            logits = model(**enc).logits
            out.extend(CLASSES[j] for j in logits.argmax(-1).tolist())
            del enc, logits
        free()
        return out

    truth_test = [r["gold"] for r in test_rows]
    truth_val = [r["gold"] for r in va]

    # ---- baseline: the off-the-shelf model, before any training
    base_val_pred = predict(va)
    if args.tune_only:
        base_test_pred, base = None, None
        logger.info("tune-only: the 199-segment test set will NOT be scored")
    else:
        base_test_pred = predict(test_rows)
        base = metrics.summarise(truth_test, base_test_pred)
        logger.info("BASE on the 199: acc %.4f | NEUTRAL recall %.4f | macro-F1 %.4f",
                    base["accuracy"], base["neutral_recall"], base["macro_f1"])

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(dl_tr) * args.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=args.lr, total_steps=total_steps,
        pct_start=0.1, anneal_strategy="linear")
    lossf = torch.nn.CrossEntropyLoss()

    ckpt = BENCH / ".best_ckpt.pt"
    best = {"macro_f1": metrics.macro_f1(truth_val, base_val_pred),
            "epoch": 0, "saved": False}
    logger.info("epoch 0 (untrained baseline) val macro-F1 = %.4f", best["macro_f1"])
    history = [{"epoch": 0, "val_macro_f1": best["macro_f1"], "train_loss": None}]

    for ep in range(1, args.epochs + 1):
        model.train()
        tot = 0.0
        for enc, labs in dl_tr:
            enc = {k: v.to(device) for k, v in enc.items()}
            labs = labs.to(device)
            opt.zero_grad()
            loss = lossf(model(**enc).logits, labs)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            step_loss = loss.item()
            opt.step(); sched.step()
            tot += step_loss
            del enc, labs, loss
        free()
        vpred = predict(va)
        vf1 = metrics.macro_f1(truth_val, vpred)
        vacc = metrics.accuracy(truth_val, vpred)
        vnr = metrics.per_class_prf(truth_val, vpred)["NEUTRAL"]["recall"]
        logger.info("epoch %d | loss %.4f | val acc %.4f | val NEUT-R %.4f | val macro-F1 %.4f",
                    ep, tot / len(dl_tr), vacc, vnr, vf1)
        history.append({"epoch": ep, "val_macro_f1": vf1, "val_acc": vacc,
                        "val_neutral_recall": vnr, "train_loss": tot / len(dl_tr)})
        if vf1 > best["macro_f1"]:
            torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, ckpt)
            best = {"macro_f1": vf1, "epoch": ep, "saved": True}
            free()

    logger.info("best epoch by VALIDATION macro-F1: %d (%.4f)",
                best["epoch"], best["macro_f1"])
    if best["saved"]:
        model.load_state_dict(torch.load(ckpt, map_location="cpu"))
        model.to(device)
        ckpt.unlink(missing_ok=True)
    else:
        logger.warning("no epoch beat the untrained baseline on validation; "
                       "the base model is kept as the final model")

    if args.tune_only:
        logger.info("TUNE-ONLY RESULT | lr=%g epochs=%d | best val macro-F1 %.4f at epoch %d "
                    "(untrained baseline %.4f)",
                    args.lr, args.epochs, best["macro_f1"], best["epoch"],
                    history[0]["val_macro_f1"])
        return 0

    # ---- test, once, on speakers never seen in training or model selection
    ft_test_pred = predict(test_rows)
    ft = metrics.summarise(truth_test, ft_test_pred)
    mc = metrics.mcnemar_exact(truth_test, ft_test_pred, base_test_pred)

    logger.info("FINE-TUNED on the 199: acc %.4f | NEUTRAL recall %.4f | macro-F1 %.4f",
                ft["accuracy"], ft["neutral_recall"], ft["macro_f1"])
    logger.info("McNemar vs base: b=%d c=%d p=%.6g", mc["b"], mc["c"], mc["p_value"])

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_model": BASE_MODEL,
        "hyperparameters": {"epochs": args.epochs, "lr": args.lr,
                            "batch_size": args.batch_size, "max_len": max_len,
                            "val_frac": args.val_frac, "seed": SEED,
                            "device": str(device)},
        "data": {"train": len(tr), "val": len(va), "test": len(test_rows),
                 "train_speakers": sorted(train_speakers),
                 "test_speakers": sorted(test_speakers),
                 "holdout_use_count": 2},
        "best_epoch": best["epoch"],
        "history": history,
        "base_test": base,
        "finetuned_test": ft,
        "mcnemar_ft_vs_base": mc,
        "test_predictions": [
            {"segment_uid": r["segment_uid"], "channel": r["channel"],
             "gold": r["gold"], "base": b, "finetuned": f}
            for r, b, f in zip(test_rows, base_test_pred, ft_test_pred)
        ],
    }
    ANALYSIS.mkdir(exist_ok=True)
    # Named by config so a second run does not silently overwrite the first's evidence.
    out_json = ANALYSIS / f"finetune_lr{args.lr:g}_ep{args.epochs}.json"
    out_json.write_text(json.dumps(report, indent=1))
    logger.info("wrote %s", out_json)

    if best["saved"]:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(out)
        tok.save_pretrained(out)
        logger.info("saved fine-tuned model to %s", out)
    else:
        logger.info("nothing saved - base model was not improved on validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
