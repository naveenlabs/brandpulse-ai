"""
report_bench.py - turn cached predictions into the comparison table and apply the
pre-registered decision rule.

Reads predictions/*.json. Runs no models, so it is cheap to re-run and its output
is fully reproducible from the cached prediction files.

The decision rule is CANDIDATE_MODELS.md Section 3, fixed before any result was
seen. It is implemented here rather than applied by hand so that the winner is a
computed consequence of the rule, not a judgement call made after looking at the
table.

Usage
-----
    python research/transcript_bench/report_bench.py
    python research/transcript_bench/report_bench.py --split confirmation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR))

import metrics                    # noqa: E402
from candidates import REGISTRY   # noqa: E402

PRED_DIR = BENCH_DIR / "predictions"
INCUMBENT = "0.1_sst2_incumbent"

# The incumbent's confidence cut-off, swept for candidate 0.2 (the ablation).
SWEEP = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.99]


def load_predictions(split: str) -> dict[str, dict]:
    out = {}
    for entry in REGISTRY:
        path = PRED_DIR / f"{entry['id']}__{split}.json"
        if path.exists():
            out[entry["id"]] = json.loads(path.read_text(encoding="utf-8"))
    return out


def usable(record: dict) -> tuple[list[str], list[str], int]:
    """Gold/pred pairs, dropping parse failures and reporting how many there were.

    A generative model that fails to answer is not scored as if it had answered.
    The failure count is reported next to its accuracy so the denominator is
    visible rather than quietly reduced.
    """
    gold, pred, failed = [], [], 0
    for p in record["predictions"]:
        if p["label"] is None:
            failed += 1
            continue
        gold.append(p["gold"])
        pred.append(p["label"])
    return gold, pred, failed


def threshold_sweep(record: dict) -> list[dict]:
    """Candidate 0.2 - re-threshold the incumbent's own cached scores.

    Costs nothing: same forward passes, different cut-off. Separates 'the model is
    wrong' from 'the threshold is wrong'.
    """
    rows = []
    for threshold in SWEEP:
        gold, pred = [], []
        for p in record["predictions"]:
            scores = p["scores"] or {}
            if not scores:
                gold.append(p["gold"])
                pred.append("NEUTRAL")
                continue
            best = max(scores, key=scores.__getitem__)
            label = "NEUTRAL" if scores[best] < threshold else best.upper()
            gold.append(p["gold"])
            pred.append(label)
        s = metrics.summarise(gold, pred)
        rows.append({
            "threshold": threshold,
            "accuracy": s["accuracy"],
            "macro_f1": s["macro_f1"],
            "neutral_recall": s["neutral_recall"],
            "neutral_precision": s["per_class"]["NEUTRAL"]["precision"],
            "neutral_predicted": s["neutral_predicted"],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="selection",
                    choices=["selection", "confirmation"])
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    records = load_predictions(args.split)
    if INCUMBENT not in records:
        print(f"incumbent {INCUMBENT} not scored on {args.split}; run run_bench.py first")
        return 2

    by_name = {e["id"]: e for e in REGISTRY}
    inc_gold, inc_pred, _ = usable(records[INCUMBENT])
    inc = metrics.summarise(inc_gold, inc_pred)

    results = []
    for cid, record in records.items():
        gold, pred, failed = usable(record)
        s = metrics.summarise(gold, pred)
        # McNemar is only meaningful on identically-indexed items, so it is
        # computed on the rows both classifiers actually answered.
        inc_by_uid = {p["segment_uid"]: p["label"]
                      for p in records[INCUMBENT]["predictions"]}
        paired_gold, paired_a, paired_b = [], [], []
        for p in record["predictions"]:
            if p["label"] is None:
                continue
            other = inc_by_uid.get(p["segment_uid"])
            if other is None:
                continue
            paired_gold.append(p["gold"])
            paired_a.append(p["label"])
            paired_b.append(other)
        mc = metrics.mcnemar_exact(paired_gold, paired_a, paired_b)
        results.append({
            "id": cid,
            "group": by_name[cid]["group"],
            "name": by_name[cid]["name"],
            "n_scored": s["n"],
            "parse_failures": failed,
            "seconds_per_row": record["seconds_per_row"],
            **{k: s[k] for k in ("accuracy", "accuracy_ci95", "macro_f1",
                                 "neutral_recall", "neutral_predicted")},
            "neutral_precision": s["per_class"]["NEUTRAL"]["precision"],
            "neutral_f1": s["per_class"]["NEUTRAL"]["f1"],
            "positive_f1": s["per_class"]["POSITIVE"]["f1"],
            "negative_f1": s["per_class"]["NEGATIVE"]["f1"],
            "mcnemar_vs_incumbent": mc,
            "confusion": s["confusion"],
        })

    results.sort(key=lambda r: (-r["neutral_recall"], -r["accuracy"]))

    print(f"\n{'='*104}")
    print(f"TRANSCRIPT BENCH - {args.split.upper()} SET"
          f"   (incumbent accuracy {inc['accuracy']:.3f}, "
          f"NEUTRAL recall {inc['neutral_recall']:.3f})")
    print(f"{'='*104}")
    print(f"{'candidate':28} {'grp':>3} {'n':>4} {'NEUT-R':>7} {'NEUT-P':>7} "
          f"{'acc':>6} {'95% CI':>15} {'mF1':>6} {'p(McN)':>8} {'s/row':>7}")
    print("-" * 104)
    for r in results:
        ci = f"[{r['accuracy_ci95'][0]:.3f},{r['accuracy_ci95'][1]:.3f}]"
        star = " *" if r["id"] == INCUMBENT else "  "
        p = r["mcnemar_vs_incumbent"]["p_value"]
        print(f"{r['id'][:27]:28}{star[-1]}{r['group']:>3} {r['n_scored']:>4} "
              f"{r['neutral_recall']:>7.3f} {r['neutral_precision']:>7.3f} "
              f"{r['accuracy']:>6.3f} {ci:>15} {r['macro_f1']:>6.3f} "
              f"{p:>8.4f} {r['seconds_per_row']:>7.3f}")
    print("-" * 104)
    print("* = incumbent.  NEUT-R = NEUTRAL recall (PRIMARY METRIC).  "
          "p(McN) = exact McNemar vs incumbent.")

    fails = [r for r in results if r["parse_failures"]]
    if fails:
        print("\nParse failures (excluded from that model's denominator):")
        for r in fails:
            print(f"  {r['id']:28} {r['parse_failures']} of "
                  f"{r['parse_failures'] + r['n_scored']}")

    # Candidate 0.2 - the ablation.
    print(f"\n{'='*104}")
    print("CANDIDATE 0.2 - INCUMBENT THRESHOLD SWEEP (ablation: is it the model or the constant?)")
    print(f"{'='*104}")
    print(f"{'threshold':>10} {'NEUT pred':>10} {'NEUT-R':>8} {'NEUT-P':>8} "
          f"{'accuracy':>9} {'macro-F1':>9}")
    print("-" * 104)
    for row in threshold_sweep(records[INCUMBENT]):
        mark = "  <- production" if row["threshold"] == 0.70 else ""
        print(f"{row['threshold']:>10.2f} {row['neutral_predicted']:>10} "
              f"{row['neutral_recall']:>8.3f} {row['neutral_precision']:>8.3f} "
              f"{row['accuracy']:>9.3f} {row['macro_f1']:>9.3f}{mark}")

    if args.json_out:
        payload = {
            "split": args.split,
            "incumbent": INCUMBENT,
            "results": results,
            "threshold_sweep": threshold_sweep(records[INCUMBENT]),
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
