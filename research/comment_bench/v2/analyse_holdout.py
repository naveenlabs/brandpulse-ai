#!/usr/bin/env python3
"""
comment_bench/v2/analyse_holdout.py

Evaluate the base and fine-tuned models against the 150 held-out human labels.

Decision rule is fixed in holdout/HOLDOUT_PROTOCOL.md, written before any label existed.
Primary metric: NEGATIVE recall. Everything else is secondary and non-decisive.

Usage:  python research/comment_bench/v2/analyse_holdout.py
Writes: analysis/holdout_analysis.json
"""
from __future__ import annotations

import csv, json, math
from collections import Counter, defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent
LABELS = ["NEGATIVE", "NEUTRAL", "POSITIVE"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def prf(truth, pred):
    out = {}
    for lab in LABELS:
        tp = sum(1 for t, p in zip(truth, pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(truth, pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(truth, pred) if t == lab and p != lab)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        out[lab] = {"precision": pr, "recall": rc,
                    "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0,
                    "support": tp + fn, "tp": tp, "fp": fp, "fn": fn}
    out["macro_f1"] = sum(out[l]["f1"] for l in LABELS) / 3
    return out


def main():
    human = {}
    for r in csv.DictReader((BENCH / "holdout/holdout_label_sheet.csv").open()):
        human[r["comment_id"]] = r["label_POSITIVE_NEUTRAL_NEGATIVE"].strip().upper()

    P = {p["comment_id"]: p for p in
         json.loads((BENCH / "holdout/_holdout_predictions.json").read_text())["predictions"]}

    ids = sorted(human)
    truth = [human[i] for i in ids]
    base = [P[i]["base"] for i in ids]
    ft = [P[i]["finetuned"] for i in ids]
    n = len(ids)

    rep = {"n": n, "truth_distribution": dict(Counter(truth)),
           "note": "Near-domain generalisation test. Decision rule in holdout/HOLDOUT_PROTOCOL.md."}

    print(f"HELD-OUT SET  n={n}   truth: {dict(Counter(truth))}\n")
    print("=" * 70)
    print("PRIMARY METRIC (pre-registered): NEGATIVE recall")
    print("=" * 70)
    neg_idx = [k for k, t in enumerate(truth) if t == "NEGATIVE"]
    kb = sum(1 for k in neg_idx if base[k] == "NEGATIVE")
    kf = sum(1 for k in neg_idx if ft[k] == "NEGATIVE")
    b_only = sum(1 for k in neg_idx if base[k] == "NEGATIVE" and ft[k] != "NEGATIVE")
    f_only = sum(1 for k in neg_idx if base[k] != "NEGATIVE" and ft[k] == "NEGATIVE")
    p_neg = mcnemar(b_only, f_only)
    print(f"  base       {kb}/{len(neg_idx)} = {kb/len(neg_idx):.3f}")
    print(f"  fine-tuned {kf}/{len(neg_idx)} = {kf/len(neg_idx):.3f}")
    print(f"  change     {(kf-kb)/len(neg_idx):+.3f}")
    print(f"  McNemar    base-only={b_only} ft-only={f_only}  p={p_neg:.4f}  "
          f"{'SIGNIFICANT' if p_neg < 0.05 else 'not significant'}")
    print(f"\n  For reference, the same metric on the original 350-comment test set:")
    print(f"    base 0.493 -> fine-tuned 0.672  (+0.179, p=0.0118, n=67 negatives)")
    rep["primary_negative_recall"] = {
        "n_negatives": len(neg_idx), "base_correct": kb, "finetuned_correct": kf,
        "base_recall": kb / len(neg_idx), "finetuned_recall": kf / len(neg_idx),
        "delta": (kf - kb) / len(neg_idx),
        "mcnemar": {"only_base": b_only, "only_finetuned": f_only,
                    "p_value_exact": p_neg, "significant": p_neg < 0.05},
        "original_test_set_for_comparison": {"base_recall": 0.493, "finetuned_recall": 0.672,
                                             "delta": 0.179, "p": 0.0118, "n_negatives": 67},
    }

    print("\n" + "=" * 70)
    print("SECONDARY METRICS (reported, not decisive)")
    print("=" * 70)
    for name, pred in (("base", base), ("fine-tuned", ft)):
        k = sum(1 for t, p in zip(truth, pred) if t == p)
        lo, hi = wilson(k, n)
        m = prf(truth, pred)
        print(f"  {name:11s} acc {k:3d}/{n} = {100*k/n:5.2f}%  CI[{100*lo:.1f},{100*hi:.1f}]  "
              f"macroF1={m['macro_f1']:.3f}")
        rep[name.replace("-", "_")] = {
            "correct": k, "accuracy": k / n, "ci95": [lo, hi],
            "per_class": m, "pred_distribution": dict(Counter(pred))}
    ab = sum(1 for t, x, y in zip(truth, base, ft) if x == t and y != t)
    af = sum(1 for t, x, y in zip(truth, base, ft) if x != t and y == t)
    p_acc = mcnemar(ab, af)
    kb_a = sum(1 for t, p in zip(truth, base) if t == p)
    kf_a = sum(1 for t, p in zip(truth, ft) if t == p)
    print(f"  accuracy delta {100*(kf_a-kb_a)/n:+.2f} pts | McNemar base-only={ab} ft-only={af} "
          f"p={p_acc:.4f} {'SIG' if p_acc<0.05 else 'not significant'}")
    rep["accuracy_comparison"] = {"delta_pts": 100 * (kf_a - kb_a) / n,
                                  "mcnemar": {"only_base": ab, "only_finetuned": af,
                                              "p_value_exact": p_acc, "significant": p_acc < 0.05}}

    print(f"\n  {'class':10s}{'base P':>8s}{'base R':>8s}{'base F1':>9s}   "
          f"{'ft P':>7s}{'ft R':>7s}{'ft F1':>8s}{'support':>9s}")
    for lab in LABELS:
        b = rep["base"]["per_class"][lab]; f = rep["fine_tuned"]["per_class"][lab]
        print(f"  {lab:10s}{b['precision']:8.3f}{b['recall']:8.3f}{b['f1']:9.3f}   "
              f"{f['precision']:7.3f}{f['recall']:7.3f}{f['f1']:8.3f}{b['support']:9d}")

    print(f"\n  predicted: base {dict(Counter(base))}")
    print(f"             ft   {dict(Counter(ft))}")
    print(f"             truth {dict(Counter(truth))}")

    # false alarms - the cost side
    fa_b = sum(1 for t, p in zip(truth, base) if t != "NEGATIVE" and p == "NEGATIVE")
    fa_f = sum(1 for t, p in zip(truth, ft) if t != "NEGATIVE" and p == "NEGATIVE")
    print(f"\n  false complaint alarms: base {fa_b} -> fine-tuned {fa_f}")
    rep["false_negative_alarms"] = {"base": fa_b, "finetuned": fa_f}

    # video level
    print("\n" + "=" * 70)
    print("VIDEO-LEVEL (2 videos only - indicative)")
    print("=" * 70)
    byv = defaultdict(list)
    for k, i in enumerate(ids):
        byv[P[i]["video_id"]].append(k)
    def net(ls):
        c = Counter(ls); return 100 * (c["POSITIVE"] - c["NEGATIVE"]) / len(ls)
    vids = {}
    for v, ks in sorted(byv.items()):
        h = net([truth[k] for k in ks]); b = net([base[k] for k in ks]); f = net([ft[k] for k in ks])
        print(f"  {v}  human {h:+6.1f} | base {b:+6.1f} (err {b-h:+5.1f}) | "
              f"ft {f:+6.1f} (err {f-h:+5.1f})")
        vids[v] = {"human_net": h, "base_net": b, "finetuned_net": f,
                   "base_error": b - h, "finetuned_error": f - h, "n": len(ks)}
    mae_b = sum(abs(v["base_error"]) for v in vids.values()) / len(vids)
    mae_f = sum(abs(v["finetuned_error"]) for v in vids.values()) / len(vids)
    print(f"  MAE: base {mae_b:.1f} pts -> fine-tuned {mae_f:.1f} pts")
    rep["video_level"] = {"per_video": vids, "mae_base": mae_b, "mae_finetuned": mae_f}

    (BENCH / "analysis/holdout_analysis.json").write_text(json.dumps(rep, indent=2))
    print("\nwritten: analysis/holdout_analysis.json")


if __name__ == "__main__":
    main()
