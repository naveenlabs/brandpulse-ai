"""
ensemble.py - post-hoc experiments: model ensembles, and the arousal dimension.

POST-HOC. Neither experiment was pre-registered in CANDIDATE_MODELS.md. Both were
run on 02 Sep 2026 after the main bench concluded that no single model beats a
constant, to answer the fair question "did you actually try everything cheap?"

Two protections against fishing, because post-hoc work on a null result is
exactly where a false positive gets manufactured:

  1. **Every variant defined here is reported**, win or lose. The variant list is
     fixed in this file, not selected after seeing scores. Reporting only the best
     of N tries is the same error as running N experiments and quoting one.
  2. **Compositions are chosen by model family or output type, never by
     performance.** "All categorical models" is a principled group; "the three
     that happened to score well" is not, and does not appear here.

Every threshold is fitted on the SELECTION split and frozen before confirmation
is scored, exactly as in report_bench.py.

    python research/vocal_bench/ensemble.py
    python research/vocal_bench/ensemble.py --json ensemble_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR))

import ground_truth as GT  # noqa: E402
import report_bench as RB  # noqa: E402

CLASSES = ("POSITIVE", "NEUTRAL", "NEGATIVE")

CATEGORICAL = ["speechbrain-iemocap", "superb-wav2vec2-er", "dpngtm-wav2vec2",
               "emotion2vec-seed", "emotion2vec-base", "emotion2vec-large"]
DIMENSIONAL = ["audeering-msp-dim", "wavlm-msp-dim"]
EMOTION2VEC = ["emotion2vec-seed", "emotion2vec-base", "emotion2vec-large"]


# ────────────────────────────────────────────────────────────── voting helpers

def hard_vote(labels: list[str]) -> str:
    """Majority vote over three-class labels.

    Ties break toward NEUTRAL, fixed here rather than left to Counter ordering.
    NEUTRAL is the conservative choice: a split vote is not evidence of polarity,
    and breaking toward POSITIVE or NEGATIVE would invent a verdict the models
    did not collectively support.
    """
    usable = [l for l in labels if l in CLASSES]
    if not usable:
        return "UNMAPPED"
    counts = Counter(usable)
    top = max(counts.values())
    winners = [c for c in CLASSES if counts.get(c, 0) == top]
    return "NEUTRAL" if len(winners) > 1 and "NEUTRAL" in winners else winners[0]


def soft_vote(dists: list[dict[str, float]]) -> str:
    """Sum probability mass mapped into each of the three classes, take argmax.

    Uses model confidence rather than only the argmax label, so a model that was
    barely deciding contributes proportionally less than one that was certain.
    Mass on unmappable labels (`other`, `<unk>`) is discarded rather than
    redistributed - redistributing it would invent confidence.
    """
    total = {c: 0.0 for c in CLASSES}
    for dist in dists:
        for raw, prob in dist.items():
            cls = RB.map_label(raw)
            if cls:
                total[cls] += prob
    if not any(total.values()):
        return "UNMAPPED"
    return max(total, key=total.get)


# ───────────────────────────────────────────────────────────────── the variants

def build_variants(runs: dict, sel_rows: list[dict]) -> dict:
    """Every variant tried. Fixed list - nothing added or removed after scoring."""

    def cat_labels(name, uid):
        return RB.map_label(runs[name]["predictions"][uid].get("raw_label"))

    def dist(name, uid):
        return runs[name]["predictions"][uid].get("scores", {})

    def dim(name, uid, which):
        return runs[name]["predictions"][uid].get("scores", {}).get(which)

    variants: dict[str, dict] = {}

    # --- single-model dimension swaps -------------------------------------
    for model in DIMENSIONAL:
        for which in ("valence", "arousal", "dominance"):
            key = f"{model} [{which}]"
            variants[key] = {
                "kind": "threshold",
                "value": lambda uid, m=model, w=which: dim(m, uid, w),
            }

    # --- ensembles, composed by family/type, never by score ----------------
    variants["ENSEMBLE hard-vote all-8"] = {
        "kind": "vote",
        "fn": lambda uid: hard_vote(
            [cat_labels(n, uid) for n in CATEGORICAL]
            + [RB.apply_thresholds(dim(n, uid, "valence"), *TH[n]) for n in DIMENSIONAL]),
    }
    variants["ENSEMBLE hard-vote categorical-6"] = {
        "kind": "vote",
        "fn": lambda uid: hard_vote([cat_labels(n, uid) for n in CATEGORICAL]),
    }
    variants["ENSEMBLE soft-vote categorical-6"] = {
        "kind": "vote",
        "fn": lambda uid: soft_vote([dist(n, uid) for n in CATEGORICAL]),
    }
    variants["ENSEMBLE soft-vote emotion2vec-3"] = {
        "kind": "vote",
        "fn": lambda uid: soft_vote([dist(n, uid) for n in EMOTION2VEC]),
    }
    for which in ("valence", "arousal"):
        variants[f"ENSEMBLE mean-{which} dimensional-2"] = {
            "kind": "threshold",
            "value": lambda uid, w=which: (
                sum(dim(n, uid, w) for n in DIMENSIONAL) / len(DIMENSIONAL)),
        }
    return variants


TH: dict[str, tuple[float, float]] = {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    sel, con = GT.load("selection"), GT.load("confirmation")
    runs = RB.load_predictions()

    global TH
    TH = {n: RB.fit_thresholds(sel, runs[n]["predictions"])[:2] for n in DIMENSIONAL}

    variants = build_variants(runs, sel)
    inc_sel = RB.score_candidate("speechbrain-iemocap", runs["speechbrain-iemocap"],
                                 sel, surprise_neutral=False, thresholds=None)
    inc_con = RB.score_candidate("speechbrain-iemocap", runs["speechbrain-iemocap"],
                                 con, surprise_neutral=False, thresholds=None)
    wav_sel = RB.score_candidate("wavlm-msp-dim", runs["wavlm-msp-dim"], sel,
                                 surprise_neutral=False, thresholds=TH["wavlm-msp-dim"])
    wav_con = RB.score_candidate("wavlm-msp-dim", runs["wavlm-msp-dim"], con,
                                 surprise_neutral=False, thresholds=TH["wavlm-msp-dim"])

    results = {}
    for name, spec in variants.items():
        if spec["kind"] == "threshold":
            vals = {r["uid"]: {"valence": spec["value"](r["uid"])} for r in sel + con}
            lo, hi, _ = RB.fit_thresholds(sel, vals)   # fitted on SELECTION only
            pred = {r["uid"]: RB.apply_thresholds(vals[r["uid"]]["valence"], lo, hi)
                    for r in sel + con}
            fitted = (lo, hi)
        else:
            pred = {r["uid"]: spec["fn"](r["uid"]) for r in sel + con}
            fitted = None

        row = {"thresholds": fitted}
        for split, rows in (("selection", sel), ("confirmation", con)):
            gold = [r["label"] for r in rows]
            p = [pred[r["uid"]] or "UNMAPPED" for r in rows]
            floor = ["NEUTRAL"] * len(rows)
            inc = inc_sel if split == "selection" else inc_con
            acc = sum(g == q for g, q in zip(gold, p)) / len(rows)
            row[split] = {
                "accuracy": acc,
                "vs_floor_p": RB.mcnemar_exact(gold, floor, p)["p_value"],
                "floor_acc": sum(g == "NEUTRAL" for g in gold) / len(rows),
                "vs_incumbent_p": RB.mcnemar_exact(gold, inc["pred"], p)["p_value"],
                "incumbent_acc": inc["accuracy"],
            }
        results[name] = row

    # ---------------------------------------------------------------- output
    print("POST-HOC experiments: dimension swaps and ensembles")
    print("Every variant defined in this file is listed, win or lose.\n")
    print(f"{'variant':<40}{'SEL acc':>9}{'vs floor':>10}{'CON acc':>9}{'vs floor':>10}"
          f"{'beats floor':>13}")
    print("-" * 91)

    def line(name, r):
        s, c = r["selection"], r["confirmation"]
        beats = []
        if s["accuracy"] > s["floor_acc"] and s["vs_floor_p"] < 0.05:
            beats.append("sel")
        if c["accuracy"] > c["floor_acc"] and c["vs_floor_p"] < 0.05:
            beats.append("con")
        verdict = "+".join(beats) if beats else "neither"
        return (f"{name:<40}{s['accuracy']*100:>8.1f}%{s['vs_floor_p']:>10.4f}"
                f"{c['accuracy']*100:>8.1f}%{c['vs_floor_p']:>10.4f}{verdict:>13}")

    for name, r in sorted(results.items(), key=lambda x: -x[1]["selection"]["accuracy"]):
        print(line(name, r))

    print("\nReference points")
    print(f"  {'floor (always NEUTRAL)':<40}{inc_sel['n'] and 0 or 0:>0}"
          f"{results[list(results)[0]]['selection']['floor_acc']*100:>8.1f}%"
          f"{'':>10}{results[list(results)[0]]['confirmation']['floor_acc']*100:>8.1f}%")
    print(f"  {'incumbent (speechbrain)':<40}{inc_sel['accuracy']*100:>8.1f}%"
          f"{'':>10}{inc_con['accuracy']*100:>8.1f}%")
    print(f"  {'wavlm single, valence (best single)':<40}{wav_sel['accuracy']*100:>8.1f}%"
          f"{'':>10}{wav_con['accuracy']*100:>8.1f}%")

    print("\nA variant counts only if it beats the floor on BOTH splits.")
    both = [n for n, r in results.items()
            if r["selection"]["accuracy"] > r["selection"]["floor_acc"]
            and r["selection"]["vs_floor_p"] < 0.05
            and r["confirmation"]["accuracy"] > r["confirmation"]["floor_acc"]
            and r["confirmation"]["vs_floor_p"] < 0.05]
    print(f"  variants beating the floor on both splits: "
          f"{', '.join(both) if both else 'NONE'}")
    print(f"  variants tried: {len(results)} "
          f"(no multiple-comparison correction is applied to these exploratory")
    print("   p-values; with this many variants at least one crossing 0.05 by chance")
    print("   is expected, which is why 'both splits' is the bar.)")

    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
