"""
report_bench.py - score every vocal-emotion candidate against the human ratings.

Applies the metric, the label mapping and the decision rule fixed in
CANDIDATE_MODELS.md sections 3 and 4 on 01 Sep 2026, before any rating was given
and before any candidate had seen a project clip.

Metric arithmetic is imported from transcript_bench/metrics.py rather than
reimplemented. It is the same three-class problem on the same corpus, that module
already carries 31 unit tests, and a second copy could drift from the first.

    python research/vocal_bench/report_bench.py
    python research/vocal_bench/report_bench.py --confirm      # score the holdout ONCE
    python research/vocal_bench/report_bench.py --surprise-neutral   # sensitivity check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
PROJECT = BENCH_DIR.parents[1]
# transcript_bench ALSO defines a ground_truth module. Import metrics from it by
# explicit file location rather than by putting its directory on sys.path, so
# this bench's own ground_truth.py can never be shadowed. (It was, once: the
# first version put transcript_bench first and silently loaded the wrong loader.)
import importlib.util

sys.path.insert(0, str(BENCH_DIR))
import ground_truth as GT  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "transcript_metrics", PROJECT / "research" / "transcript_bench" / "metrics.py")
_metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_metrics)
accuracy = _metrics.accuracy
confusion_matrix = _metrics.confusion_matrix
macro_f1 = _metrics.macro_f1
mcnemar_exact = _metrics.mcnemar_exact
per_class_prf = _metrics.per_class_prf
wilson_interval = _metrics.wilson_interval

PRED_DIR = BENCH_DIR / "predictions"
INCUMBENT = "speechbrain-iemocap"
ALPHA = 0.05

# Fixed in CANDIDATE_MODELS.md section 3, before any model output was seen.
LABEL_MAP = {
    "angry": "NEGATIVE", "sad": "NEGATIVE", "disgust": "NEGATIVE",
    "disgusted": "NEGATIVE", "fear": "NEGATIVE", "fearful": "NEGATIVE",
    "neutral": "NEUTRAL", "calm": "NEUTRAL",
    "happy": "POSITIVE", "surprise": "POSITIVE", "surprised": "POSITIVE",
}
# Deliberately NOT in the map. These are recorded as unmapped rather than
# coerced to NEUTRAL - coercing them is precisely the defect transcript_bench
# found in the deployed transcript channel.
UNMAPPABLE = {"other", "unknown", "<unk>", "unk", None}

# Threshold grid for the dimensional candidate. Fitted on selection only, then
# frozen before confirmation is touched (CANDIDATE_MODELS.md section 3).
GRID = [round(x / 100, 2) for x in range(5, 100, 5)]

# Confusion-matrix axes. UNMAPPED can be predicted but can never be a gold label,
# so it is a column and not a class: including it in macro-F1 would invent a
# fourth class that no human rating can ever match.
CONF_LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE", "UNMAPPED")


def map_label(raw: str | None, surprise_neutral: bool = False) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key in UNMAPPABLE:
        return None
    if surprise_neutral and key in ("surprise", "surprised"):
        return "NEUTRAL"
    return LABEL_MAP.get(key)


def load_predictions() -> dict[str, dict]:
    out = {}
    for f in sorted(PRED_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        out[d["candidate"]] = d
    if not out:
        raise SystemExit(f"no predictions in {PRED_DIR} - run run_bench.py first")
    return out


# ─────────────────────────────────────────────────────────── dimensional models

def apply_thresholds(valence: float | None, lo: float, hi: float) -> str | None:
    if valence is None:
        return None
    if valence < lo:
        return "NEGATIVE"
    if valence < hi:
        return "NEUTRAL"
    return "POSITIVE"


def fit_thresholds(rows: list[dict], preds: dict) -> tuple[float, float, float]:
    """Grid-search (lo, hi) maximising three-class accuracy on the given rows.

    Ties are broken toward the WIDEST neutral band, because a wider band is the
    more conservative choice: it commits to a polarity less often. Without an
    explicit tie-break the winner would depend on dict iteration order.
    """
    best = (0.0, 0.0, -1.0)
    for lo in GRID:
        for hi in GRID:
            if hi <= lo:
                continue
            gold, pred = [], []
            for r in rows:
                p = apply_thresholds(preds[r["uid"]].get("valence"), lo, hi)
                gold.append(r["label"])
                pred.append(p or "UNMAPPED")
            acc = accuracy(gold, pred)
            if acc > best[2] or (acc == best[2] and (hi - lo) > (best[1] - best[0])):
                best = (lo, hi, acc)
    return best


# ─────────────────────────────────────────────────────────────────── baselines

def baseline_predictions(rows: list[dict], kind: str, fitted: str | None = None) -> list[str]:
    if kind == "always-neutral":
        return ["NEUTRAL"] * len(rows)
    if kind == "majority":
        return [fitted] * len(rows)
    raise ValueError(kind)


# ────────────────────────────────────────────────────────────────── correlation

def spearman(a: list[float], b: list[float]) -> float:
    """Spearman rho with average ranks for ties.

    Written out rather than imported so the bench keeps working if scipy is not
    present, and so tie handling is visible: this data has heavy ties (many
    clips rated 3), and tie handling changes the answer materially.
    """
    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


# ──────────────────────────────────────────────────────────────────── scoring

def score_candidate(name: str, run: dict, rows: list[dict], *,
                    surprise_neutral: bool, thresholds: tuple[float, float] | None
                    ) -> dict:
    preds = run["predictions"]
    gold, pred, unmapped = [], [], 0

    for r in rows:
        p = preds.get(r["uid"], {})
        if run["kind"] == "dimensional":
            lab = apply_thresholds(p.get("valence"), *thresholds) if thresholds else None
        else:
            lab = map_label(p.get("raw_label"), surprise_neutral)
        if lab is None:
            unmapped += 1
            lab = "UNMAPPED"          # counts as an error, never as NEUTRAL
        gold.append(r["label"])
        pred.append(lab)

    acc = accuracy(gold, pred)
    correct = sum(1 for g, p in zip(gold, pred) if g == p)
    lo, hi = wilson_interval(correct, len(gold))

    # Secondary: accuracy restricted to clips the model could actually label.
    # Separates "declined to decide" from "decided wrongly".
    cov_pairs = [(g, p) for g, p in zip(gold, pred) if p != "UNMAPPED"]
    cov_acc = (sum(1 for g, p in cov_pairs if g == p) / len(cov_pairs)
               if cov_pairs else 0.0)

    return {
        "candidate": name,
        "kind": run["kind"],
        "licence": run["licence"],
        "incumbent": run.get("incumbent", False),
        "n": len(rows),
        "accuracy": acc,
        "accuracy_ci": (lo, hi),
        "macro_f1": macro_f1(gold, pred),
        "per_class": per_class_prf(gold, pred),
        # UNMAPPED is a 4th COLUMN only: it is a possible prediction but never a
        # gold class. macro_f1 and per_class_prf stay on the 3 real classes, where
        # an unmapped prediction correctly fails to be a hit and lowers recall.
        "confusion": confusion_matrix(gold, pred, CONF_LABELS),
        "unmapped": unmapped,
        "coverage": 1 - unmapped / len(rows),
        "coverage_accuracy": cov_acc,
        "realtime_factor": run.get("realtime_factor"),
        "n_failed": run.get("n_failed", 0),
        "thresholds": thresholds,
        "gold": gold,
        "pred": pred,
    }


def _pct(x):
    return f"{x * 100:.1f}%"


def render(scored: list[dict], rows: list[dict], split: str,
           vs_inc: dict, alpha_corrected: float, extras: dict) -> str:
    L, w = [], None
    L.append(f"Vocal emotion bench - {split} split")
    dist = {}
    for r in rows:
        dist[r["label"]] = dist.get(r["label"], 0) + 1
    L.append(f"{len(rows)} scorable clips, {len({r['channel'] for r in rows})} speakers "
             f"| gold: " + ", ".join(f"{k} {v}" for k, v in sorted(dist.items())))
    L.append("")

    hdr = (f"{'candidate':<22}{'acc':>7}{'95% CI':>16}{'macroF1':>9}"
           f"{'cover':>7}{'unmap':>7}{'xRT':>7}")
    L.append(hdr)
    L.append("-" * len(hdr))
    for s in sorted(scored, key=lambda x: -x["accuracy"]):
        mark = " *" if s["incumbent"] else ""
        ci = f"[{_pct(s['accuracy_ci'][0])},{_pct(s['accuracy_ci'][1])}]"
        rt = f"{s['realtime_factor']:.1f}x" if s["realtime_factor"] else "-"
        L.append(f"{s['candidate'] + mark:<22}{_pct(s['accuracy']):>7}{ci:>16}"
                 f"{s['macro_f1']:>9.3f}{_pct(s['coverage']):>7}{s['unmapped']:>7}{rt:>7}")
    L.append("")
    L.append("* = incumbent (deployed in pipeline/audio_module.py)")
    L.append("  cover = share of clips the model gave a mappable label to.")
    L.append("  unmapped predictions count as ERRORS, never coerced to NEUTRAL.")
    L.append("")

    L.append(f"Exact McNemar vs incumbent ({INCUMBENT})")
    L.append(f"  Bonferroni-corrected alpha = {alpha_corrected:.5f} "
             f"({ALPHA} / {len(vs_inc)} comparisons)")
    L.append("")
    h2 = f"{'candidate':<22}{'acc diff':>10}{'b':>5}{'c':>5}{'p':>11}{'signif':>9}"
    L.append(h2)
    L.append("-" * len(h2))
    for name, t in vs_inc.items():
        L.append(f"{name:<22}{t['acc_diff'] * 100:>+9.1f}%{t['b']:>5}{t['c']:>5}"
                 f"{t['p_value']:>11.5f}{'YES' if t['significant'] else 'no':>9}")
    L.append("")
    L.append("  b = incumbent right / candidate wrong; c = candidate right / incumbent wrong.")
    L.append(f"  Minimum attainable p at these counts is shown where it limits the test.")
    L.append("")

    for key, block in extras.items():
        L.append(block)

    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirm", action="store_true",
                    help="score the held-out speakers (use ONCE, after selection)")
    ap.add_argument("--surprise-neutral", action="store_true",
                    help="sensitivity check: map surprise to NEUTRAL instead of POSITIVE")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    split = "confirmation" if args.confirm else "selection"
    rows = GT.load(split)
    sel_rows = GT.load("selection")
    runs = load_predictions()

    # Thresholds for dimensional candidates are ALWAYS fitted on selection,
    # never on confirmation, whichever split is being scored.
    thresholds: dict[str, tuple[float, float]] = {}
    for name, run in runs.items():
        if run["kind"] == "dimensional":
            lo, hi, fit_acc = fit_thresholds(sel_rows, run["predictions"])
            thresholds[name] = (lo, hi)

    scored = [
        score_candidate(n, r, rows, surprise_neutral=args.surprise_neutral,
                        thresholds=thresholds.get(n))
        for n, r in runs.items()
    ]

    # Baselines
    maj = max(set(r["label"] for r in sel_rows),
              key=[r["label"] for r in sel_rows].count)
    gold = [r["label"] for r in rows]
    for kind, fitted in (("always-neutral", None), ("majority", maj)):
        pred = baseline_predictions(rows, kind, fitted)
        correct = sum(1 for g, p in zip(gold, pred) if g == p)
        lo, hi = wilson_interval(correct, len(gold))
        scored.append({
            "candidate": f"BASELINE {kind}", "kind": "baseline", "licence": "-",
            "incumbent": False, "n": len(rows),
            "accuracy": accuracy(gold, pred), "accuracy_ci": (lo, hi),
            "macro_f1": macro_f1(gold, pred), "per_class": per_class_prf(gold, pred),
            "confusion": confusion_matrix(gold, pred, CONF_LABELS),
            "unmapped": 0, "coverage": 1.0,
            "coverage_accuracy": accuracy(gold, pred), "realtime_factor": None,
            "n_failed": 0, "thresholds": None, "gold": gold, "pred": pred,
        })

    inc = next(s for s in scored if s["candidate"] == INCUMBENT)
    others = [s for s in scored if s["candidate"] != INCUMBENT]
    vs_inc = {}
    for s in sorted(others, key=lambda x: -x["accuracy"]):
        t = mcnemar_exact(s["gold"], inc["pred"], s["pred"])
        t["acc_diff"] = s["accuracy"] - inc["accuracy"]
        t["significant"] = t["p_value"] < ALPHA / len(others)
        vs_inc[s["candidate"]] = t

    extras = {}

    # Confusion matrix for the incumbent and the leader - the shape of the
    # failure matters more than the headline number.
    lead = max((s for s in scored if s["kind"] != "baseline"),
               key=lambda x: x["accuracy"])
    for s in (inc, lead):
        if s["candidate"] in extras:
            continue
        lines = [f"Confusion matrix - {s['candidate']}"
                 f"{'  (incumbent)' if s['incumbent'] else '  (best candidate)'}",
                 "  rows = human rating, cols = model", ""]
        cols = ["POSITIVE", "NEUTRAL", "NEGATIVE", "UNMAPPED"]
        lines.append("           " + "".join(f"{c[:8]:>10}" for c in cols))
        for g in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
            row = s["confusion"].get(g, {})
            lines.append(f"  {g:<9}" + "".join(f"{row.get(c, 0):>10}" for c in cols))
        lines.append("")
        pc = s["per_class"]
        lines.append(f"  {'class':<10}{'prec':>8}{'recall':>8}{'F1':>8}{'support':>9}")
        for cls in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
            m = pc.get(cls, {})
            lines.append(f"  {cls:<10}{m.get('precision', 0):>8.3f}"
                         f"{m.get('recall', 0):>8.3f}{m.get('f1', 0):>8.3f}"
                         f"{m.get('support', 0):>9}")
        lines.append("")
        extras[s["candidate"]] = "\n".join(lines)

    # Dimensional extras: fitted thresholds and rank correlation against the
    # raw 1-5 rating, which uses ordinal detail the 3-class collapse discards.
    for name, run in runs.items():
        if run["kind"] != "dimensional":
            continue
        lo, hi = thresholds[name]
        vals, rats = [], []
        for r in rows:
            v = run["predictions"].get(r["uid"], {}).get("valence")
            if v is not None:
                vals.append(v)
                rats.append(r["rating"])
        rho = spearman(vals, rats)
        extras[f"dim-{name}"] = "\n".join([
            f"Dimensional candidate: {name}",
            f"  thresholds fitted on SELECTION only, frozen: "
            f"valence < {lo} -> NEGATIVE, < {hi} -> NEUTRAL, else POSITIVE",
            f"  grid: {GRID[0]} to {GRID[-1]} step 0.05",
            f"  Spearman rho vs raw 1-5 rating on {split}: {rho:.3f}  (n={len(vals)})",
            "  rho uses the full ordinal rating and needs no thresholds, so it is",
            "  the threshold-free view of the same model.",
            "",
        ])

    alpha_c = ALPHA / len(others)
    print(render(scored, rows, split, vs_inc, alpha_c, extras))

    if args.json:
        args.json.write_text(json.dumps({
            "split": split, "n": len(rows),
            "surprise_neutral": args.surprise_neutral,
            "alpha_corrected": alpha_c,
            "thresholds": {k: list(v) for k, v in thresholds.items()},
            "scored": [{k: v for k, v in s.items() if k not in ("gold", "pred")}
                       for s in scored],
            "vs_incumbent": vs_inc,
        }, indent=1))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
