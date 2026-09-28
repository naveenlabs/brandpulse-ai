#!/usr/bin/env python3
"""
comment_bench/v2/analyse_all_models.py

Final stage of the v2 comment bench: evaluate ALL TEN candidate models against the human
ground truth, on one frozen corpus, with identical inputs and identical statistics.

Sampling discipline (labels/_sample_manifest.json)
--------------------------------------------------
  Sample A  n=300  30 per video, random          -> the ONLY unbiased accuracy estimate
  Sample B  n=50   three-way model disagreements -> diagnostic; enriched with hard cases

Sample A and Sample B are reported separately and never pooled into a headline figure.
A pooled "all 350" figure is also computed because it was explicitly asked for, but it is
labelled as pessimistic: a seventh of it is a set selected precisely because models fail
on it, so it understates real-world accuracy.

Usage:  python research/comment_bench/v2/analyse_all_models.py
Writes: analysis/all_models_analysis.json
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent
LABELS = BENCH / "labels"
ANALYSIS = BENCH / "analysis"
SCORED = BENCH / "scored"
SCORED_EXTRA = BENCH / "scored_extra"

LABEL_SET = ("POSITIVE", "NEUTRAL", "NEGATIVE")

# Display order: incumbent + v1 candidates first, then the seven added later.
MODEL_ORDER = [
    "cardiffnlp", "tabularisai", "VADER",
    "j-hartmann", "bertweet", "cardiffnlp_original", "cardiffnlp_xlm",
    "distilbert_student", "nlptown", "siebert",
]

PRETTY = {
    "cardiffnlp": "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "tabularisai": "tabularisai/multilingual-sentiment-analysis",
    "VADER": "VADER (rule-based lexicon)",
    "j-hartmann": "j-hartmann/sentiment-roberta-large-english-3-classes",
    "bertweet": "finiteautomata/bertweet-base-sentiment-analysis",
    "cardiffnlp_original": "cardiffnlp/twitter-roberta-base-sentiment",
    "cardiffnlp_xlm": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    "distilbert_student": "lxyuan/distilbert-base-multilingual-cased-sentiments-student",
    "nlptown": "nlptown/bert-base-multilingual-uncased-sentiment",
    "siebert": "siebert/sentiment-roberta-large-english",
}


# ------------------------------------------------------------------ statistics

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


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in LABEL_SET)
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def prf(truth: list[str], pred: list[str]) -> dict:
    out = {}
    for lab in LABEL_SET:
        tp = sum(1 for t, p in zip(truth, pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(truth, pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(truth, pred) if t == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    out["macro_f1"] = sum(out[l]["f1"] for l in LABEL_SET) / 3
    return out


def confusion(truth: list[str], pred: list[str]) -> dict:
    m = {t: {p: 0 for p in LABEL_SET} for t in LABEL_SET}
    for t, p in zip(truth, pred):
        m[t][p] += 1
    return m


# ------------------------------------------------------------------ loading

def _comment_list(doc: dict) -> list[dict]:
    for v in doc.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "comment_id" in v[0]:
            return v
    raise KeyError("no comment list found")


def load_predictions() -> tuple[dict, dict, dict]:
    """Return (labels, meta, video_of) keyed by comment_id -> {model: LABEL}."""
    preds: dict[str, dict[str, str]] = defaultdict(dict)
    video_of: dict[str, str] = {}
    titles: dict[str, str] = {}

    for d in (SCORED, SCORED_EXTRA):
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            vid = doc["video_id"]
            titles[vid] = doc.get("video_title") or vid
            for c in _comment_list(doc):
                cid = c["comment_id"]
                video_of[cid] = vid
                for name, rec in c["models"].items():
                    preds[cid][name] = rec["label"].strip().upper()
    return preds, titles, video_of


def main() -> None:
    manifest = json.loads((LABELS / "_sample_manifest.json").read_text())
    sample_a = set(manifest["sample_a_accuracy"]["comment_ids"])
    sample_b = set(manifest["sample_b_diagnostic"]["comment_ids"])

    human = {}
    for r in csv.DictReader((LABELS / "label_sheet_rater1.csv").open()):
        col = "label_POSITIVE_NEUTRAL_NEGATIVE"
        human[r["comment_id"]] = r[col].strip().upper()

    preds, titles, video_of = load_predictions()

    present = [m for m in MODEL_ORDER
               if any(m in preds[c] for c in list(preds)[:50])]
    missing = [m for m in MODEL_ORDER if m not in present]

    report: dict = {
        "generated_at": "2026-08-28",
        "models_evaluated": present,
        "models_missing": missing,
        "corpus_comments_scored": len(preds),
        "ground_truth": "labels/label_sheet_rater1.csv (350 human labels)",
        "seed": manifest["seed"],
    }

    def evaluate(ids: set[str], name: str, note: str) -> dict:
        ids = sorted(i for i in ids if i in human and i in preds)
        truth = [human[i] for i in ids]
        block = {"n": len(ids), "note": note,
                 "truth_distribution": dict(Counter(truth))}
        for m in present:
            pred = [preds[i].get(m, "NEUTRAL") for i in ids]
            k = sum(1 for t, p in zip(truth, pred) if t == p)
            lo, hi = wilson(k, len(ids))
            block[m] = {
                "model_id": PRETTY[m],
                "correct": k,
                "wrong": len(ids) - k,
                "n": len(ids),
                "accuracy": k / len(ids),
                "ci95": [lo, hi],
                "kappa_vs_human": cohen_kappa(truth, pred),
                "per_class": prf(truth, pred),
                "confusion_truth_by_pred": confusion(truth, pred),
                "pred_distribution": dict(Counter(pred)),
            }
        block["ranking"] = sorted(present, key=lambda m: -block[m]["accuracy"])
        report[name] = block
        return block

    a = evaluate(sample_a, "sample_a_accuracy",
                 "Unbiased random sample. THE headline accuracy figure.")
    b = evaluate(sample_b, "sample_b_diagnostic",
                 "Enriched with three-way model disagreements. Diagnostic only, "
                 "NOT an accuracy estimate.")
    pooled = evaluate(sample_a | sample_b, "pooled_350_pessimistic",
                      "All 350 human labels pooled. PESSIMISTIC: one seventh of these "
                      "were selected because models disagreed, so this understates "
                      "field accuracy. Reported because it was explicitly requested; "
                      "sample_a_accuracy is the figure to quote.")

    # ---- McNemar: every model against the Sample A winner
    ids_a = sorted(i for i in sample_a if i in human and i in preds)
    truth_a = [human[i] for i in ids_a]
    champion = a["ranking"][0]
    champ_pred = [preds[i].get(champion, "NEUTRAL") for i in ids_a]
    mc = {}
    for m in present:
        if m == champion:
            continue
        p = [preds[i].get(m, "NEUTRAL") for i in ids_a]
        bb = sum(1 for t, x, y in zip(truth_a, champ_pred, p) if x == t and y != t)
        cc = sum(1 for t, x, y in zip(truth_a, champ_pred, p) if x != t and y == t)
        mc[f"{champion}_vs_{m}"] = {
            "champion_only_correct": bb,
            "challenger_only_correct": cc,
            "discordant": bb + cc,
            "p_value_exact": mcnemar_exact(bb, cc),
            "significant_at_0.05": mcnemar_exact(bb, cc) < 0.05,
        }
    report["mcnemar_vs_champion"] = {"champion": champion, "pairs": mc}

    # ---- video-level net sentiment error (what the Brand Health Score consumes)
    byv = defaultdict(list)
    for i in ids_a:
        byv[video_of[i]].append(i)

    def net(labels: list[str]) -> float:
        c = Counter(labels)
        return 100 * (c["POSITIVE"] - c["NEGATIVE"]) / len(labels)

    vid = {}
    for m in present:
        errs, flips = [], 0
        for v, vids in byv.items():
            h = net([human[i] for i in vids])
            p = net([preds[i].get(m, "NEUTRAL") for i in vids])
            errs.append(abs(p - h))
            if (p > 0) != (h > 0) and abs(h) > 2:
                flips += 1
        agg_h = net([human[i] for i in ids_a])
        agg_p = net([preds[i].get(m, "NEUTRAL") for i in ids_a])
        vid[m] = {"mae_pts": sum(errs) / len(errs), "sign_flips": flips,
                  "videos": len(byv), "aggregate_net": agg_p,
                  "aggregate_error_pts": agg_p - agg_h}
    report["video_level_sample_a"] = {
        "human_aggregate_net": net([human[i] for i in ids_a]), "per_model": vid}

    (ANALYSIS / "all_models_analysis.json").write_text(json.dumps(report, indent=2))
    print("written: analysis/all_models_analysis.json\n")

    # ------------------------------------------------------------- console
    print("=" * 78)
    print(f"SAMPLE A (n={a['n']}) — unbiased accuracy vs human ground truth")
    print("=" * 78)
    print("truth:", a["truth_distribution"], "\n")
    print(f"{'model':24s}{'right':>7s}{'wrong':>7s}{'acc':>8s}{'95% CI':>16s}{'kappa':>8s}{'mF1':>7s}")
    for m in a["ranking"]:
        d = a[m]
        ci = f"[{100*d['ci95'][0]:.1f},{100*d['ci95'][1]:.1f}]"
        print(f"{m:24s}{d['correct']:7d}{d['wrong']:7d}{100*d['accuracy']:7.1f}%{ci:>16s}"
              f"{d['kappa_vs_human']:8.3f}{d['per_class']['macro_f1']:7.3f}")

    print(f"\n{'-'*78}\nPOOLED 350 (pessimistic — includes the 50 hard cases)\n{'-'*78}")
    print(f"{'model':24s}{'right':>7s}{'wrong':>7s}{'acc':>8s}")
    for m in pooled["ranking"]:
        d = pooled[m]
        print(f"{m:24s}{d['correct']:7d}{d['wrong']:7d}{100*d['accuracy']:7.1f}%")

    print(f"\n{'-'*78}\nMcNEMAR vs champion ({champion}), Sample A\n{'-'*78}")
    for k, v in sorted(mc.items(), key=lambda kv: kv[1]["p_value_exact"]):
        flag = "SIG" if v["significant_at_0.05"] else "ns "
        print(f"  {flag} {k:52s} {v['champion_only_correct']:3d}/{v['challenger_only_correct']:3d}"
              f"  p={v['p_value_exact']:.3g}")

    print(f"\n{'-'*78}\nNEGATIVE class (brand-monitoring critical), Sample A\n{'-'*78}")
    print(f"{'model':24s}{'prec':>8s}{'recall':>8s}{'F1':>8s}")
    for m in sorted(present, key=lambda x: -a[x]['per_class']['NEGATIVE']['f1']):
        d = a[m]["per_class"]["NEGATIVE"]
        print(f"{m:24s}{d['precision']:8.3f}{d['recall']:8.3f}{d['f1']:8.3f}")

    print(f"\n{'-'*78}\nVIDEO-LEVEL (feeds Brand Health Score), Sample A\n{'-'*78}")
    print(f"human aggregate net = {report['video_level_sample_a']['human_aggregate_net']:+.1f}\n")
    print(f"{'model':24s}{'MAE pts':>9s}{'flips':>7s}{'net':>8s}{'err':>8s}")
    for m in sorted(present, key=lambda x: vid[x]['mae_pts']):
        d = vid[m]
        print(f"{m:24s}{d['mae_pts']:9.1f}{d['sign_flips']:4d}/10{d['aggregate_net']:+8.1f}"
              f"{d['aggregate_error_pts']:+8.1f}")

    if missing:
        print("\n  WARNING — not scored:", missing)


if __name__ == "__main__":
    main()
