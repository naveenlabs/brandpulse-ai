"""
Evaluate the three comment-sentiment models against the human ground-truth labels
produced by rater 1.

Design constraints this script honours (see labels/_sample_manifest.json):

  Sample A (n=300, 30 per video, random)  -> the ONLY set from which an unbiased
                                             accuracy estimate may be quoted.
  Sample B (n=50, drawn from three-way    -> diagnostic only. Enriched with hard
             model disagreements)            cases by construction, so its accuracy
                                             is a lower bound, not an estimate.

Sample A and Sample B are NEVER pooled. Doing so would import the enrichment bias
of B into the headline number.

Usage:  python analyse_human_ground_truth.py
Writes: analysis/human_ground_truth_analysis.json
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

BENCH = Path(__file__).resolve().parent
LABELS = BENCH / "labels"
ANALYSIS = BENCH / "analysis"
SCORED = BENCH / "scored"

LABEL_SET = ("POSITIVE", "NEUTRAL", "NEGATIVE")
MODELS = ("cardiffnlp", "tabularisai", "VADER")


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Correct near 0 and 1, unlike the normal approximation."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    halfw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - halfw, centre + halfw)


def mcnemar_exact(b: int, c: int) -> float:
    """
    Two-sided exact McNemar test on the discordant pairs only.

    b = items system 1 got right and system 2 got wrong
    c = items system 1 got wrong and system 2 got right

    Under H0 each discordant item is a fair coin, so b ~ Binomial(b+c, 0.5).
    Exact binomial is used rather than the chi-square approximation because
    b+c is small here (tens, not thousands).
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Chance-corrected agreement between two labellings of the same items."""
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in LABEL_SET)
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def prf(truth: list[str], pred: list[str]) -> dict:
    """Per-class precision / recall / F1, plus macro-F1."""
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


# ---------------------------------------------------------------- data loading

def load_label_sheet(path: Path) -> dict[str, str]:
    rows = list(csv.DictReader(path.open()))
    col = next(c for c in rows[0] if c.startswith("label"))
    return {r["comment_id"]: r[col].strip().upper() for r in rows}


def load_predictions() -> dict[str, dict[str, str]]:
    """Each scored comment's model labels, and the confidence (top class probability,
    rounded to 4 places) of the two models that give one."""
    preds: dict[str, dict[str, str]] = {}
    for path in sorted(p for p in SCORED.glob("*.json") if not p.name.startswith("_")):
        for c in json.loads(path.read_text(encoding="utf-8"))["comments"]:
            row = {m: c["models"][m]["label"] for m in MODELS}
            row["cardiff_conf"] = str(round(max(c["models"]["cardiffnlp"]["probs"].values()), 4))
            row["tabularisai_conf"] = str(round(max(c["models"]["tabularisai"]["probs"].values()), 4))
            preds[c["comment_id"]] = row
    return preds


def main() -> None:
    manifest = json.loads((LABELS / "_sample_manifest.json").read_text())
    sample_a = set(manifest["sample_a_accuracy"]["comment_ids"])
    sample_b = set(manifest["sample_b_diagnostic"]["comment_ids"])
    overlap = set(manifest["rater2_overlap"]["comment_ids"])

    human = load_label_sheet(LABELS / "label_sheet_rater1.csv")
    rater2 = load_label_sheet(LABELS / "label_sheet_rater2.csv")

    preds = load_predictions()

    report: dict = {
        "generated_at": "2026-08-28",
        "ground_truth": "labels/label_sheet_rater1.csv (350 human labels)",
        "corpus_total": manifest["corpus_total"],
        "seed": manifest["seed"],
    }

    # ---------- inter-rater reliability -----------------------------------
    ov_ids = sorted(i for i in overlap if i in human and i in rater2)
    a_lab = [human[i] for i in ov_ids]
    b_lab = [rater2[i] for i in ov_ids]
    n_ov = len(ov_ids)
    agree = sum(1 for x, y in zip(a_lab, b_lab) if x == y)
    lo_ov, hi_ov = wilson(agree, n_ov)
    counter_a, counter_b = Counter(a_lab), Counter(b_lab)
    pe = sum((counter_a[l] / n_ov) * (counter_b[l] / n_ov) for l in LABEL_SET)
    report["inter_rater"] = {
        "overlap_n": n_ov,
        "agree": agree,
        "raw_agreement": agree / n_ov,
        "agreement_ci95": [lo_ov, hi_ov],
        "expected_by_chance_pe": pe,
        "cohens_kappa": cohen_kappa(a_lab, b_lab),
        "rater1_distribution": dict(counter_a),
        "rater2_distribution": dict(counter_b),
        "note": (
            "Second rater worked from the blank sheet independently, different row order, "
            "no discussion, no AI assistance. The high kappa is attributable to a "
            "deliberately prescriptive 10-rule rubric (labels/GUIDELINES.md) fixed before "
            "labelling began; it should be reported with that explanation. Perfect "
            "agreement means the overlap set yields no data on which items are ambiguous."
        ),
    }
    # model accuracy restricted to the double-rated subset (strongest ground truth)
    double = {}
    for sysname in MODELS:
        k = sum(1 for i in ov_ids if preds[i][sysname].strip().upper() == human[i])
        lo_d, hi_d = wilson(k, n_ov)
        double[sysname] = {"correct": k, "n": n_ov, "accuracy": k / n_ov,
                           "ci95": [lo_d, hi_d]}
    report["double_rated_subset_accuracy"] = double

    # ---------- accuracy, Sample A (the headline set) ---------------------
    def evaluate(ids: set[str], name: str) -> dict:
        ids = sorted(i for i in ids if i in human and i in preds)
        truth = [human[i] for i in ids]
        block: dict = {"n": len(ids), "truth_distribution": dict(Counter(truth))}
        for sysname in MODELS:
            pred = [preds[i][sysname].strip().upper() for i in ids]
            k = sum(1 for t, p in zip(truth, pred) if t == p)
            lo, hi = wilson(k, len(ids))
            block[sysname] = {
                "correct": k,
                "n": len(ids),
                "accuracy": k / len(ids),
                "ci95": [lo, hi],
                "kappa_vs_human": cohen_kappa(truth, pred),
                "per_class": prf(truth, pred),
                "confusion_truth_by_pred": confusion(truth, pred),
                "pred_distribution": dict(Counter(pred)),
            }
        # pairwise exact McNemar between every system
        pairs = {}
        for i, s1 in enumerate(MODELS):
            for s2 in MODELS[i + 1:]:
                p1 = [preds[x][s1].strip().upper() for x in ids]
                p2 = [preds[x][s2].strip().upper() for x in ids]
                b = sum(1 for t, a, c in zip(truth, p1, p2) if a == t and c != t)
                c_ = sum(1 for t, a, c in zip(truth, p1, p2) if a != t and c == t)
                pairs[f"{s1}_vs_{s2}"] = {
                    "only_first_correct": b,
                    "only_second_correct": c_,
                    "discordant": b + c_,
                    "p_value_exact": mcnemar_exact(b, c_),
                }
        block["mcnemar_pairwise"] = pairs
        report[name] = block
        return block

    a = evaluate(sample_a, "sample_a_accuracy")
    b = evaluate(sample_b, "sample_b_diagnostic")

    # ---------- calibration: is model confidence informative? -------------
    conf_col = {"cardiffnlp": "cardiff_conf", "tabularisai": "tabularisai_conf"}
    calib = {}
    ids_a = sorted(i for i in sample_a if i in human and i in preds)
    for m, col in conf_col.items():
        right, wrong = [], []
        for i in ids_a:
            try:
                c = float(preds[i][col])
            except (ValueError, KeyError):
                continue
            (right if preds[i][m].strip().upper() == human[i] else wrong).append(c)
        calib[m] = {
            "mean_conf_when_correct": sum(right) / len(right) if right else None,
            "n_correct": len(right),
            "mean_conf_when_wrong": sum(wrong) / len(wrong) if wrong else None,
            "n_wrong": len(wrong),
            "separation": (sum(right) / len(right) - sum(wrong) / len(wrong))
            if right and wrong else None,
        }
    report["calibration_sample_a"] = calib

    out = ANALYSIS / "human_ground_truth_analysis.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"written: {out}")

    # ---------------------------------------------------------- console
    print("\n" + "=" * 70)
    print("SAMPLE A (n=%d) — unbiased accuracy vs human ground truth" % a["n"])
    print("=" * 70)
    print("truth distribution:", a["truth_distribution"])
    for s in MODELS:
        d = a[s]
        print(f"  {s:12s} {d['correct']:3d}/{d['n']}  {100*d['accuracy']:5.1f}%  "
              f"CI[{100*d['ci95'][0]:.1f},{100*d['ci95'][1]:.1f}]  "
              f"k={d['kappa_vs_human']:.3f}  macroF1={d['per_class']['macro_f1']:.3f}")
    print("\n  NEGATIVE recall (the adoption-critical metric):")
    for s in MODELS:
        pc = a[s]["per_class"]["NEGATIVE"]
        print(f"    {s:12s} recall={pc['recall']:.3f}  precision={pc['precision']:.3f}  "
              f"F1={pc['f1']:.3f}  support={pc['support']}")
    print("\n  McNemar (exact, two-sided):")
    for k, v in a["mcnemar_pairwise"].items():
        star = "  SIGNIFICANT" if v["p_value_exact"] < 0.05 else ""
        print(f"    {k:28s} {v['only_first_correct']:3d} vs {v['only_second_correct']:3d}"
              f"  p={v['p_value_exact']:.4g}{star}")

    print("\n" + "=" * 70)
    print("SAMPLE B (n=%d) — DIAGNOSTIC ONLY, enriched with hard cases" % b["n"])
    print("=" * 70)
    for s in MODELS:
        d = b[s]
        print(f"  {s:12s} {d['correct']:3d}/{d['n']}  {100*d['accuracy']:5.1f}%")

    print("\n  Calibration (Sample A):")
    for m, c in calib.items():
        if c["separation"] is not None:
            print(f"    {m:12s} correct={c['mean_conf_when_correct']:.3f}  "
                  f"wrong={c['mean_conf_when_wrong']:.3f}  "
                  f"separation={c['separation']:+.3f}")


if __name__ == "__main__":
    main()
