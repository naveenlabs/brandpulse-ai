#!/usr/bin/env python3
"""
comment_bench/v2/finetune_cardiffnlp.py

Fine-tune the adopted comment-sentiment model on 1,000 hand-labelled training comments
and test it on the 350 held-out human labels.

The question this answers
-------------------------
cardiffnlp/twitter-roberta-base-sentiment-latest scores 71.3% on Sample A off the shelf.
It is already fine-tuned on ~124M tweets. Does 1,000 in-domain YouTube comments improve
it, or is the off-the-shelf model already at the ceiling this data supports?

Both answers are results. A null result is written up as a null result.

Data discipline
---------------
  train/train_sheet.csv   1,000 comments, hand-labelled, disjoint from the test set
      -> 800 train / 200 validation  (stratified, seed 42)
  labels/label_sheet_rater1.csv   350 comments
      -> TEST ONLY. Never seen during training, never used for early stopping,
         never used to pick a hyperparameter.

Validation comes out of the 1,000, not the 350. Using the test set to decide when to
stop training would leak it and make the final number meaningless.

No new dependencies: a plain PyTorch loop rather than pulling in datasets/accelerate.

Determinism
-----------
Seeds fixed for python, numpy and torch. Note that MPS kernels are not bit-reproducible
in the way CPU CUDA-free runs are, so a re-run may differ in the last decimal; the
selection decision is not sensitive at that resolution.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/finetune_cardiffnlp.py
    python research/comment_bench/v2/finetune_cardiffnlp.py --epochs 6 --lr 1e-5
    python research/comment_bench/v2/finetune_cardiffnlp.py --install   # also install for the pipeline
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path(__file__).resolve().parent
LABELS = BENCH / "labels"
TRAIN = BENCH / "train"
ANALYSIS = BENCH / "analysis"
OUT_DIR = BENCH / "finetuned"

BASE_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
CLASSES = ["NEGATIVE", "NEUTRAL", "POSITIVE"]
C2I = {c: i for i, c in enumerate(CLASSES)}
SEED = 42
# Token-length audit over all 1,350 labelled comments (train + test):
#   median 23, p90 73, p95 102, p99 201, max 464.
# 128 covers 96.5% of comments in full and halves activation memory versus 256,
# which is what made this trainable on MPS. The ~3.5% longer comments are
# truncated; the baseline is recomputed at the same length so the before/after
# comparison stays like-for-like.
MAX_LEN = 128
HUMAN_COL = "label_POSITIVE_NEUTRAL_NEGATIVE"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("finetune")


# ------------------------------------------------------------------ metrics

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def macro_f1(truth: list[str], pred: list[str]) -> float:
    fs = []
    for lab in CLASSES:
        tp = sum(1 for t, p in zip(truth, pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(truth, pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(truth, pred) if t == lab and p != lab)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        fs.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return sum(fs) / 3


def per_class(truth: list[str], pred: list[str]) -> dict:
    out = {}
    for lab in CLASSES:
        tp = sum(1 for t, p in zip(truth, pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(truth, pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(truth, pred) if t == lab and p != lab)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        out[lab] = {"precision": pr, "recall": rc,
                    "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0,
                    "support": tp + fn}
    return out


# ------------------------------------------------------------------ data

def read_sheet(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    for r in csv.DictReader(path.open()):
        col = next(c for c in r if c.startswith("label"))
        lab = r[col].strip().upper()
        if lab in C2I:
            rows.append((r["comment_id"], r["text"], lab))
    return rows


def stratified_split(rows, frac_val: float, seed: int):
    by = {}
    for r in rows:
        by.setdefault(r[2], []).append(r)
    rng = random.Random(seed)
    train, val = [], []
    for lab in sorted(by):
        items = sorted(by[lab], key=lambda x: x[0])
        rng.shuffle(items)
        n_val = int(round(len(items) * frac_val))
        val.extend(items[:n_val])
        train.extend(items[n_val:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--max-len", type=int, default=MAX_LEN)
    ap.add_argument("--device", default="auto", choices=["auto", "mps", "cpu", "cuda"],
                    help="'cpu' is slower but immune to the MPS fragmentation that "
                         "aborts training on this machine at larger batch/length")
    ap.add_argument("--install", action="store_true",
                    help="after saving, install the weights where the pipeline loads them "
                         "(models/comment_sentiment_ft/), as a retrained model")
    ap.add_argument("--force", action="store_true",
                    help="with --install: replace an existing model folder (kept aside)")
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

    train_rows = read_sheet(TRAIN / "train_sheet.csv")
    test_rows = read_sheet(LABELS / "label_sheet_rater1.csv")
    test_ids = {r[0] for r in test_rows}
    assert not ({r[0] for r in train_rows} & test_ids), "TEST SET CONTAMINATION"
    logger.info("train sheet: %d | test sheet: %d | overlap: 0", len(train_rows), len(test_rows))

    tr, va = stratified_split(train_rows, args.val_frac, SEED)
    logger.info("split -> train %d, val %d", len(tr), len(va))
    logger.info("train dist %s", dict(Counter(r[2] for r in tr)))
    logger.info("val   dist %s", dict(Counter(r[2] for r in va)))

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)

    class DS(Dataset):
        def __init__(self, rows): self.rows = rows
        def __len__(self): return len(self.rows)
        def __getitem__(self, i):
            _, text, lab = self.rows[i]
            return text, C2I[lab]

    def collate(batch):
        texts = [b[0] for b in batch]
        labs = torch.tensor([b[1] for b in batch])
        enc = tok(texts, truncation=True, max_length=max_len,
                  padding=True, return_tensors="pt")
        return enc, labs

    g = torch.Generator(); g.manual_seed(SEED)
    dl_tr = DataLoader(DS(tr), batch_size=args.batch_size, shuffle=True,
                       collate_fn=collate, generator=g)
    dl_va = DataLoader(DS(va), batch_size=32, shuffle=False, collate_fn=collate)

    # The base checkpoint's label order is negative, neutral, positive - identical to
    # CLASSES - so the classification head is reused rather than reinitialised.
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL).to(device)
    id2label = model.config.id2label
    logger.info("base head order: %s", id2label)
    assert [id2label[i].lower() for i in range(3)] == [c.lower() for c in CLASSES], \
        "label order mismatch - head cannot be reused as-is"

    def free():
        """MPS fragments badly across epochs; release the cache between phases."""
        if device.type == "mps":
            torch.mps.empty_cache()
        elif device.type == "cuda":
            torch.cuda.empty_cache()

    @torch.no_grad()
    def predict(rows: list[tuple[str, str, str]]) -> list[str]:
        model.eval()
        out = []
        for i in range(0, len(rows), 32):
            chunk = rows[i:i + 32]
            enc = tok([r[1] for r in chunk], truncation=True, max_length=max_len,
                      padding=True, return_tensors="pt").to(device)
            logits = model(**enc).logits
            out.extend(CLASSES[j] for j in logits.argmax(-1).tolist())
            del enc, logits
        free()
        return out

    # ---- baseline: the off-the-shelf model, before any training
    base_test_pred = predict(test_rows)
    base_val_pred = predict(va)
    truth_test = [r[2] for r in test_rows]
    base_acc = sum(1 for t, p in zip(truth_test, base_test_pred) if t == p) / len(truth_test)
    logger.info("BASE model on the 350: %.4f | val macro-F1 %.4f",
                base_acc, macro_f1([r[2] for r in va], base_val_pred))

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(dl_tr) * args.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=args.lr, total_steps=total_steps, pct_start=0.1, anneal_strategy="linear")
    lossf = torch.nn.CrossEntropyLoss()

    truth_val = [r[2] for r in va]
    ckpt_path = BENCH / ".best_ckpt.pt"
    best = {"macro_f1": macro_f1(truth_val, base_val_pred), "epoch": 0, "saved": False}
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
        vf1 = macro_f1(truth_val, vpred)
        vacc = sum(1 for t, p in zip(truth_val, vpred) if t == p) / len(va)
        logger.info("epoch %d | train loss %.4f | val acc %.4f | val macro-F1 %.4f",
                    ep, tot / len(dl_tr), vacc, vf1)
        history.append({"epoch": ep, "val_macro_f1": vf1, "val_acc": vacc,
                        "train_loss": tot / len(dl_tr)})
        if vf1 > best["macro_f1"]:
            torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, ckpt_path)
            best = {"macro_f1": vf1, "epoch": ep, "saved": True}
            free()

    logger.info("best epoch by VALIDATION macro-F1: %d (%.4f)", best["epoch"], best["macro_f1"])
    if best["saved"]:
        model.load_state_dict(torch.load(ckpt_path, map_location="cpu"))
        model.to(device)
        ckpt_path.unlink(missing_ok=True)
    else:
        logger.warning("no epoch beat the untrained baseline on validation; "
                       "the base model is kept as the final model")

    # ---- test, once, on data never used for training or model selection
    ft_test_pred = predict(test_rows)

    man = json.loads((LABELS / "_sample_manifest.json").read_text())
    sample_a = set(man["sample_a_accuracy"]["comment_ids"])

    def block(ids: set[str] | None, name: str) -> dict:
        idx = [i for i, r in enumerate(test_rows) if ids is None or r[0] in ids]
        t = [truth_test[i] for i in idx]
        bp = [base_test_pred[i] for i in idx]
        fp = [ft_test_pred[i] for i in idx]
        kb = sum(1 for x, y in zip(t, bp) if x == y)
        kf = sum(1 for x, y in zip(t, fp) if x == y)
        b_only = sum(1 for x, y, z in zip(t, bp, fp) if y == x and z != x)
        f_only = sum(1 for x, y, z in zip(t, bp, fp) if y != x and z == x)
        p = mcnemar_exact(b_only, f_only)
        r = {
            "n": len(idx),
            "base": {"correct": kb, "accuracy": kb / len(idx),
                     "ci95": list(wilson(kb, len(idx))),
                     "macro_f1": macro_f1(t, bp), "per_class": per_class(t, bp),
                     "pred_distribution": dict(Counter(bp))},
            "finetuned": {"correct": kf, "accuracy": kf / len(idx),
                          "ci95": list(wilson(kf, len(idx))),
                          "macro_f1": macro_f1(t, fp), "per_class": per_class(t, fp),
                          "pred_distribution": dict(Counter(fp))},
            "delta_pts": 100 * (kf - kb) / len(idx),
            "mcnemar": {"only_base_correct": b_only, "only_finetuned_correct": f_only,
                        "p_value_exact": p, "significant_at_0.05": p < 0.05},
        }
        print(f"\n=== {name} (n={len(idx)}) ===")
        print(f"  base       {kb:3d}/{len(idx)} = {100*kb/len(idx):5.2f}%  macroF1={macro_f1(t,bp):.3f}")
        print(f"  fine-tuned {kf:3d}/{len(idx)} = {100*kf/len(idx):5.2f}%  macroF1={macro_f1(t,fp):.3f}")
        print(f"  delta      {100*(kf-kb)/len(idx):+.2f} pts")
        print(f"  McNemar    base-only={b_only} ft-only={f_only}  p={p:.4f}  "
              f"{'SIGNIFICANT' if p < 0.05 else 'not significant'}")
        return r

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_model": BASE_MODEL,
        "seed": SEED,
        "hyperparameters": {"epochs": args.epochs, "lr": args.lr,
                            "batch_size": args.batch_size, "max_len": max_len,
                            "val_frac": args.val_frac, "optimizer": "AdamW",
                            "weight_decay": 0.01, "scheduler": "OneCycleLR"},
        "train_n": len(tr), "val_n": len(va), "test_n": len(test_rows),
        "test_contamination_check": 0,
        "best_epoch_by_validation": best["epoch"],
        "best_val_macro_f1": best["macro_f1"],
        "history": history,
        "sample_a_300": block(sample_a, "SAMPLE A (headline, unbiased)"),
        "pooled_350": block(None, "POOLED 350 (pessimistic)"),
    }
    # Per-item predictions are always written. Without them any follow-up analysis
    # (per-class significance, error inspection) would require a full retrain.
    report["predictions"] = [
        {"comment_id": r[0], "truth": r[2],
         "base": bp, "finetuned": fp,
         "in_sample_a": r[0] in sample_a}
        for r, bp, fp in zip(test_rows, base_test_pred, ft_test_pred)
    ]
    ANALYSIS.mkdir(exist_ok=True)
    (ANALYSIS / "finetune_result.json").write_text(json.dumps(report, indent=2))
    print(f"\nwritten: analysis/finetune_result.json")

    # Weights are saved as a candidate either way, so the result is reproducible and
    # inspectable. Saving is NOT adoption - pipeline/comment_module.py is unchanged
    # by this script.
    OUT_DIR.mkdir(exist_ok=True)
    model.save_pretrained(OUT_DIR); tok.save_pretrained(OUT_DIR)
    print(f"\ncandidate weights saved to {OUT_DIR} (saving is not adoption)")

    if args.install:
        # The installer lives beside the folder it fills; loaded by path because
        # models/ is not a package.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "install_comment_model", BENCH.parents[2] / "models" / "install_comment_model.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        try:
            installer.install_from(OUT_DIR, exact=False, force=args.force)
        except installer.InstallError as exc:
            print(f"not installed: {exc}", file=sys.stderr)
            return 1

    a = report["sample_a_300"]
    if a["mcnemar"]["significant_at_0.05"] and a["finetuned"]["accuracy"] > a["base"]["accuracy"]:
        print("VERDICT: fine-tuned model beats the base model significantly on Sample A.")
    else:
        print(f"VERDICT: accuracy gain {a['delta_pts']:+.2f} pts is NOT significant "
              f"(p={a['mcnemar']['p_value_exact']:.4f}). "
              "See per-class results before deciding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
