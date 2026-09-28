"""
speaker_norm.py - is the vocal channel's per-speaker instability removable?

Pre-registered in `SPEAKER_NORM_PREREG.md` on 02 Sep 2026, before any accuracy was
computed. Read that file first: it fixes the candidates, the grids, the protocol,
what "better" means, and the adoption rule, so that none of them can be chosen
after the fact to suit the answer.

WHAT CHANGES AND WHAT DOES NOT. No model is re-run. Every rule below reads the same
cached arousal values produced by `audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim`
during the corpus A/B (`ab_cache/vocal_audeering/`). Only the rule that turns a
continuous arousal value into POSITIVE / NEUTRAL / NEGATIVE changes. The experiment
therefore costs no GPU time and is exactly reproducible from what is already on disk.

THE ORDERING IS ENFORCED BY THE FILESYSTEM, NOT BY GOOD INTENTIONS.

    python research/vocal_bench/speaker_norm.py --phase select    # fit + declare, selection only
    python research/vocal_bench/speaker_norm.py --phase confirm   # score the held-out split
    python research/vocal_bench/speaker_norm.py                   # both, in that order

`--phase confirm` refuses to run unless `speaker_norm_selection.json` already exists,
and it reads the declared winner out of that file rather than recomputing it. The
confirmation split cannot influence which rule is on trial.

INVARIANT ASSERTED AT RUNTIME. Every rule is monotone within a video, so within-video
Spearman rho against the raw 1-5 human rating must be identical for all of them. The
harness checks this and aborts if it is not. It is the difference between "normalisation
made the thresholds comparable" and "the harness silently changed the data".
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))

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

VOCAL_CACHE = BENCH / "ab_cache" / "vocal_audeering"
CLIP_INDEX = BENCH / "_clip_index.json"
SELECTION_OUT = BENCH / "speaker_norm_selection.json"
RESULTS_OUT = BENCH / "speaker_norm_results.json"

LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")

# The published bench's grid, kept verbatim so the anchor below reproduces the
# figures already in VOCAL_MODEL_ANALYSIS.md rather than approximating them.
PUBLISHED_GRID = [round(x / 100, 2) for x in range(5, 100, 5)]
PUBLISHED_THRESHOLDS = (0.40, 0.65)      # what pipeline/audio_module.py deploys
PUBLISHED_SELECTION_CORRECT = 60          # of 100
PUBLISHED_CONFIRMATION_CORRECT = 23       # of 47

# Number of grid points every rule gets, so no rule has more freedom to overfit
# the selection split than any other. 19 = the published grid's size.
GRID_POINTS = 19

# Below this many usable segments a video cannot support a location/scale estimate
# and the rule falls back to the global thresholds. Declared, not tuned: the
# smallest video in this corpus has 39 segments, so no result here depends on it.
# It exists because production will eventually meet a very short video.
MIN_GROUP_SEGMENTS = 8


# ────────────────────────────────────────────────────────────────────── loading

def load_corpus() -> list[dict]:
    """Every cached pipeline segment, with its video and speaker.

    Segments whose arousal is None (the model returned no reading) are kept and
    marked, not dropped, so the denominator of "how much of the corpus is usable"
    stays visible.
    """
    clips = json.loads(CLIP_INDEX.read_text())["clips"]
    speaker_of = {c["video_id"]: c["channel"] for c in clips}

    rows: list[dict] = []
    for path in sorted(VOCAL_CACHE.glob("*.json")):
        video_id = path.stem
        if video_id not in speaker_of:
            raise RuntimeError(f"{video_id} has cached vocal output but no clip index entry")
        for seg_id, reading in json.loads(path.read_text()).items():
            rows.append({
                "uid": f"{video_id}_{seg_id}",
                "video_id": video_id,
                "speaker": speaker_of[video_id],
                "arousal": reading.get("arousal"),
            })
    if not rows:
        raise RuntimeError(f"no cached vocal output under {VOCAL_CACHE}")
    return rows


def load_labelled(split: str, arousal_of: dict[str, float]) -> list[dict]:
    """Human-rated clips for one split, joined to their cached arousal."""
    rows = []
    for r in GT.load(split):
        a = arousal_of.get(r["uid"])
        if a is None:
            raise RuntimeError(
                f"clip {r['uid']} is rated but has no cached arousal - the bench "
                f"and the corpus cache have diverged, refusing to score"
            )
        rows.append({**r, "speaker": r["channel"], "arousal": a})
    return rows


# ─────────────────────────────────────────────────────────────────── statistics

def percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolated percentile, p in [0, 1].

    Written out rather than taken from statistics.quantiles so the grids and the
    IQR use one definition that does not move between Python versions.
    """
    if not sorted_values:
        raise ValueError("percentile of an empty sample")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = p * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def fractional_rank(value: float, sorted_values: list[float]) -> float:
    """Mid-rank of `value` within the group, scaled to (0, 1).

    Mid-rank rather than a strict count so ties get one shared position instead of
    an order-dependent one; this data has many near-identical arousal readings.
    """
    n = len(sorted_values)
    below = bisect_left(sorted_values, value)
    at_or_below = bisect_right(sorted_values, value)
    return ((below + at_or_below) / 2) / n


def group_stats(values: list[float]) -> dict:
    ordered = sorted(values)
    q25 = percentile(ordered, 0.25)
    q75 = percentile(ordered, 0.75)
    return {
        "n": len(ordered),
        "mean": statistics.mean(ordered),
        "sd": statistics.pstdev(ordered),
        "median": percentile(ordered, 0.50),
        "iqr": q75 - q25,
        "sorted": ordered,
    }


def build_stats(corpus: list[dict], key: str) -> dict[str, dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in corpus:
        if row["arousal"] is not None:
            grouped[row[key]].append(row["arousal"])
    return {g: group_stats(v) for g, v in grouped.items()}


# ──────────────────────────────────────────────────────────────────────── rules

def _identity(a, _stats):
    return a


def _center(a, s):
    return a - s["mean"]


def _zscore(a, s):
    return None if s["sd"] == 0 else (a - s["mean"]) / s["sd"]


def _robust(a, s):
    return None if s["iqr"] == 0 else (a - s["median"]) / s["iqr"]


def _rank(a, s):
    return fractional_rank(a, s["sorted"])


# id -> (transform, grouping key or None for the global rule, deployable?)
RULES: dict[str, tuple] = {
    "global":       (_identity, None,      True),
    "video_center": (_center,   "video_id", True),
    "video_z":      (_zscore,   "video_id", True),
    "video_robust": (_robust,   "video_id", True),
    "video_rank":   (_rank,     "video_id", True),
    "speaker_z":    (_zscore,   "speaker",  False),   # oracle, not deployable
}

DEPLOYED_RULE = "global"


class Transformer:
    """One rule, bound to the group statistics it needs.

    Falls back to the raw arousal value when a group is too small or degenerate,
    which is the same graceful-degradation contract the rest of the pipeline
    follows: an unusable statistic downgrades the rule, it never raises.
    """

    def __init__(self, rule_id: str, corpus: list[dict]):
        fn, key, deployable = RULES[rule_id]
        self.rule_id = rule_id
        self.fn = fn
        self.key = key
        self.deployable = deployable
        self.stats = build_stats(corpus, key) if key else {}
        self.fallbacks = 0

    def __call__(self, row: dict) -> float | None:
        a = row["arousal"]
        if a is None:
            return None
        if self.key is None:
            return a
        s = self.stats.get(row[self.key])
        if s is None or s["n"] < MIN_GROUP_SEGMENTS:
            self.fallbacks += 1
            return a
        out = self.fn(a, s)
        if out is None:
            self.fallbacks += 1
            return a
        return out

    def grid(self, corpus: list[dict]) -> list[float]:
        """GRID_POINTS evenly spaced percentiles of this rule's transformed values.

        Computed over the whole corpus, never over the labelled clips, and never
        using the human ratings - so the grid itself leaks nothing.
        """
        vals = sorted(v for v in (self(r) for r in corpus) if v is not None)
        step = 1.0 / (GRID_POINTS + 1)
        return [percentile(vals, step * (i + 1)) for i in range(GRID_POINTS)]


# ───────────────────────────────────────────────────────────────────── fitting

def apply_thresholds(value: float | None, lo: float, hi: float) -> str | None:
    if value is None:
        return None
    if value < lo:
        return "NEGATIVE"
    if value < hi:
        return "NEUTRAL"
    return "POSITIVE"


def fit(rows: list[dict], transform, grid: list[float]) -> tuple[float, float, float]:
    """Grid-search (lo, hi) maximising three-class accuracy on `rows`.

    Ties break toward the widest neutral band, matching report_bench.fit_thresholds
    exactly: a wider band commits to a polarity less often, and without an explicit
    rule the winner would depend on iteration order.
    """
    gold = [r["label"] for r in rows]
    vals = [transform(r) for r in rows]
    best = (0.0, 0.0, -1.0)
    for lo in grid:
        for hi in grid:
            if hi <= lo:
                continue
            pred = [apply_thresholds(v, lo, hi) or "UNMAPPED" for v in vals]
            acc = accuracy(gold, pred)
            if acc > best[2] or (acc == best[2] and (hi - lo) > (best[1] - best[0])):
                best = (lo, hi, acc)
    if best[2] < 0:
        raise RuntimeError("grid produced no valid (lo, hi) pair")
    return best


# ───────────────────────────────────────────────────────────────────── scoring

def spearman(a: list[float], b: list[float]) -> float:
    """Spearman rho with average ranks for ties. Same implementation as the
    published bench (report_bench.spearman); duplicated rather than imported so
    this harness has no import-time dependency on that script's module state."""
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


def within_video_rho(rows: list[dict], transform) -> dict:
    """Spearman rho computed inside each video, then averaged over videos.

    The invariant of section 4 of the pre-registration: this must be identical for
    every rule, because every rule is monotone within a video.
    """
    by_video: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_video[r["video_id"]].append(r)
    per = {}
    for vid, rs in sorted(by_video.items()):
        if len(rs) < 3:
            continue
        per[vid] = round(spearman([transform(r) for r in rs], [r["rating"] for r in rs]), 6)
    return {"per_video": per,
            "mean": round(statistics.mean(per.values()), 6) if per else None}


def score(rows: list[dict], transform, thresholds: tuple[float, float]) -> dict:
    gold = [r["label"] for r in rows]
    pred = [apply_thresholds(transform(r), *thresholds) or "UNMAPPED" for r in rows]
    correct = sum(g == p for g, p in zip(gold, pred))
    lo, hi = wilson_interval(correct, len(gold))

    by_speaker = defaultdict(lambda: [0, 0])
    for r, g, p in zip(rows, gold, pred):
        by_speaker[r["speaker"]][1] += 1
        by_speaker[r["speaker"]][0] += (g == p)
    speakers = {s: {"correct": c, "n": n, "accuracy": round(c / n * 100, 1)}
                for s, (c, n) in sorted(by_speaker.items())}
    accs = [v["accuracy"] for v in speakers.values()]

    floor = ["NEUTRAL"] * len(rows)
    return {
        "n": len(rows),
        "correct": correct,
        "accuracy": round(correct / len(rows) * 100, 1),
        "wilson95": [round(lo * 100, 1), round(hi * 100, 1)],
        "macro_f1": round(macro_f1(gold, pred), 4),
        "per_class": {k: {m: round(x, 4) if isinstance(x, float) else x
                          for m, x in v.items()}
                      for k, v in per_class_prf(gold, pred).items()},
        "confusion": confusion_matrix(gold, pred),
        "vs_floor": mcnemar_exact(gold, floor, pred),
        "per_speaker": speakers,
        "speaker_range": round(max(accs) - min(accs), 1) if accs else None,
        "pooled_rho": round(spearman([transform(r) for r in rows],
                                     [r["rating"] for r in rows]), 6),
        "within_video_rho": within_video_rho(rows, transform),
        "pred": pred,
        "gold": gold,
    }


# ─────────────────────────────────────────────────────────────────── the phases

def anchor_check(corpus: list[dict], sel: list[dict], con: list[dict]) -> dict:
    """Reproduce the published figures before trusting anything else here.

    If the corpus cache and the bench predictions had drifted, every number below
    would be quietly wrong. Aborting is the only acceptable behaviour.
    """
    ident = Transformer("global", corpus)
    lo, hi, _ = fit(sel, ident, PUBLISHED_GRID)
    sel_correct = sum(r["label"] == apply_thresholds(r["arousal"], *PUBLISHED_THRESHOLDS)
                      for r in sel)
    con_correct = sum(r["label"] == apply_thresholds(r["arousal"], *PUBLISHED_THRESHOLDS)
                      for r in con)
    ok = ((lo, hi) == PUBLISHED_THRESHOLDS
          and sel_correct == PUBLISHED_SELECTION_CORRECT
          and con_correct == PUBLISHED_CONFIRMATION_CORRECT)
    if not ok:
        raise RuntimeError(
            f"anchor failed: refitted {(lo, hi)} vs published {PUBLISHED_THRESHOLDS}; "
            f"selection {sel_correct}/{len(sel)} vs {PUBLISHED_SELECTION_CORRECT}/100; "
            f"confirmation {con_correct}/{len(con)} vs {PUBLISHED_CONFIRMATION_CORRECT}/47. "
            f"The corpus cache no longer reproduces the bench - fix that before scoring."
        )
    return {
        "refitted_thresholds": [lo, hi],
        "published_thresholds": list(PUBLISHED_THRESHOLDS),
        "selection": f"{sel_correct}/{len(sel)}",
        "confirmation": f"{con_correct}/{len(con)}",
        "passed": True,
    }


def phase_select(corpus, sel, con) -> dict:
    transformers = {rid: Transformer(rid, corpus) for rid in RULES}
    grids = {rid: t.grid(corpus) for rid, t in transformers.items()}

    fitted, selection = {}, {}
    for rid, t in transformers.items():
        lo, hi, acc = fit(sel, t, grids[rid])
        fitted[rid] = [lo, hi]
        selection[rid] = score(sel, t, (lo, hi))

    # Deployable rules only. The oracle is measured, never declared the winner.
    deployable = [r for r in RULES if RULES[r][2]]
    winner = max(deployable, key=lambda r: (selection[r]["accuracy"], r == DEPLOYED_RULE))

    # Where two rules coincide by construction, say so rather than presenting them
    # as independent evidence.
    coincident = []
    for a in RULES:
        for b in RULES:
            if a < b and selection[a]["pred"] == selection[b]["pred"]:
                coincident.append([a, b, "selection"])

    return {
        "anchor": anchor_check(corpus, sel, con),
        "grid_points": GRID_POINTS,
        "grids": {r: [round(x, 6) for x in g] for r, g in grids.items()},
        "fitted_thresholds": {r: [round(x, 6) for x in v] for r, v in fitted.items()},
        "fallbacks": {r: t.fallbacks for r, t in transformers.items()},
        "selection": selection,
        "declared_winner": winner,
        "declared_winner_is_deployed_rule": winner == DEPLOYED_RULE,
        "coincident_rules": coincident,
        "corpus_segments": len(corpus),
        "corpus_usable": sum(1 for r in corpus if r["arousal"] is not None),
    }


def phase_confirm(corpus, con, declared: dict) -> dict:
    transformers = {rid: Transformer(rid, corpus) for rid in RULES}
    fitted = {r: tuple(v) for r, v in declared["fitted_thresholds"].items()}

    confirmation = {rid: score(con, transformers[rid], fitted[rid]) for rid in RULES}

    gold = confirmation[DEPLOYED_RULE]["gold"]
    deployed_pred = [apply_thresholds(r["arousal"], *PUBLISHED_THRESHOLDS) or "UNMAPPED"
                     for r in con]
    vs_deployed = {
        rid: mcnemar_exact(gold, deployed_pred, confirmation[rid]["pred"])
        for rid in RULES
    }

    # The invariant from section 4 of the pre-registration.
    baseline_rho = confirmation[DEPLOYED_RULE]["within_video_rho"]["per_video"]
    for rid, res in confirmation.items():
        if res["within_video_rho"]["per_video"] != baseline_rho:
            raise RuntimeError(
                f"monotonicity invariant violated by {rid}: within-video rho changed. "
                f"Every rule is monotone within a video, so this is a harness bug."
            )

    winner = declared["declared_winner"]
    beat_deployed = (confirmation[winner]["correct"]
                     > PUBLISHED_CONFIRMATION_CORRECT)
    significant = vs_deployed[winner]["p_value"] < 0.05
    coincident = [[a, b, "confirmation"] for a in RULES for b in RULES
                  if a < b and confirmation[a]["pred"] == confirmation[b]["pred"]]

    majority = max(LABELS, key=lambda L: sum(g == L for g in gold))
    majority_correct = sum(g == majority for g in gold)

    return {
        "confirmation": confirmation,
        "vs_deployed_mcnemar": vs_deployed,
        "deployed_baseline": {
            "thresholds": list(PUBLISHED_THRESHOLDS),
            "correct": PUBLISHED_CONFIRMATION_CORRECT,
            "n": len(con),
            "accuracy": round(PUBLISHED_CONFIRMATION_CORRECT / len(con) * 100, 1),
        },
        "oracle_majority_baseline": {
            "label": majority,
            "correct": majority_correct,
            "n": len(gold),
            "accuracy": round(majority_correct / len(gold) * 100, 1),
            "note": "chosen with knowledge of the held-out split's own distribution; "
                    "an oracle, reported as a reference not as a baseline any real "
                    "system could reach",
        },
        "coincident_rules": coincident,
        "monotonicity_invariant": "held",
        "adopt": {
            "winner": winner,
            "beat_deployed_on_confirmation": beat_deployed,
            "mcnemar_p": vs_deployed[winner]["p_value"],
            "min_attainable_p": vs_deployed[winner]["min_attainable_p"],
            "significant_at_0.05": significant,
            "decision": "ADOPT" if (beat_deployed and significant) else "DO NOT ADOPT",
        },
    }


# ─────────────────────────────────────────────────────────── explanatory phase

def eta_squared(values: list[float], groups: list[str]) -> float:
    """Share of a variable's total variance that lies BETWEEN groups.

    Written out rather than pulled from a stats package so the definition is
    visible: SS_between / SS_total on the raw values, groups unweighted beyond
    their own size. 0.0 means the group a segment came from tells you nothing
    about its value; 1.0 means it tells you everything.
    """
    if len(values) != len(groups):
        raise ValueError("values and groups must be the same length")
    if len(values) < 2:
        raise ValueError("variance decomposition needs at least two observations")
    grand = statistics.mean(values)
    ss_total = sum((v - grand) ** 2 for v in values)
    if ss_total == 0:
        return 0.0
    by_group: dict[str, list[float]] = defaultdict(list)
    for v, g in zip(values, groups):
        by_group[g].append(v)
    ss_between = sum(len(vs) * (statistics.mean(vs) - grand) ** 2
                     for vs in by_group.values())
    return ss_between / ss_total


def phase_diagnose(corpus: list[dict], sel: list[dict], con: list[dict]) -> dict:
    """POST-HOC. Not pre-registered. Why did removing the speaker offset hurt?

    The pre-registration predicted that if the model carried within-speaker signal
    plus a between-speaker offset, removing the offset would help. It did the
    opposite on both splits. That leaves one obvious explanation to test: the
    between-video offset is not nuisance, it carries a large share of whatever
    ordinal signal the channel has, so removing it removes signal.

    Everything below is descriptive and reported as exploratory. None of it was
    used to choose a candidate, fit a threshold, or make the adoption decision -
    those were all settled before this function was written.
    """
    out: dict = {"status": "post-hoc, exploratory, not pre-registered"}

    for split, rows in (("selection", sel), ("confirmation", con), ("pooled", sel + con)):
        arousal = [r["arousal"] for r in rows]
        rating = [float(r["rating"]) for r in rows]
        videos = [r["video_id"] for r in rows]
        speakers = [r["speaker"] for r in rows]

        # Video-level: does a video's mean arousal track its mean human rating?
        by_video: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for r in rows:
            by_video[r["video_id"]].append((r["arousal"], float(r["rating"])))
        v_ids = sorted(by_video)
        v_arousal = [statistics.mean(a for a, _ in by_video[v]) for v in v_ids]
        v_rating = [statistics.mean(g for _, g in by_video[v]) for v in v_ids]

        ident = Transformer("global", corpus)
        out[split] = {
            "n_clips": len(rows),
            "n_videos": len(v_ids),
            "pooled_rho": round(spearman(arousal, rating), 4),
            "within_video_rho_mean": within_video_rho(rows, ident)["mean"],
            "within_video_rho_range": [
                round(min(within_video_rho(rows, ident)["per_video"].values()), 4),
                round(max(within_video_rho(rows, ident)["per_video"].values()), 4),
            ],
            "video_level_rho_arousal_vs_rating": round(spearman(v_arousal, v_rating), 4)
            if len(v_ids) > 2 else None,
            "eta2_arousal_by_video": round(eta_squared(arousal, videos), 4),
            "eta2_arousal_by_speaker": round(eta_squared(arousal, speakers), 4),
            "eta2_rating_by_video": round(eta_squared(rating, videos), 4),
            "eta2_rating_by_speaker": round(eta_squared(rating, speakers), 4),
        }

    # Is the failure the METHOD, or only the transfer of selection-fitted
    # thresholds? Refit each rule on the confirmation split itself and report the
    # best accuracy it could possibly have reached there. This is an ORACLE: it
    # uses the held-out labels to choose its own thresholds, so no honest
    # procedure could achieve it. It cannot and did not change the adoption
    # decision, which was recorded before this was written. It exists to tell two
    # different failures apart.
    oracle = {}
    for rid in RULES:
        t = Transformer(rid, corpus)
        lo, hi, acc = fit(con, t, t.grid(corpus))
        oracle[rid] = {
            "thresholds": [round(lo, 6), round(hi, 6)],
            "best_possible_accuracy": round(acc * 100, 1),
            "best_possible_correct": round(acc * len(con)),
        }
    out["oracle_thresholds_on_confirmation"] = {
        "warning": "fitted ON the held-out split using its own labels; an upper "
                   "bound, not an achievable score",
        "n": len(con),
        "by_rule": oracle,
    }

    # Per-speaker accuracy of the DEPLOYED rule (arousal at 0.40 / 0.65) across
    # both splits. VOCAL_MODEL_ANALYSIS.md section 7 reports the same breakdown
    # for the VALENCE reading, which is not what the pipeline deploys; this is the
    # arousal equivalent. See the amendment in SPEAKER_NORM_PREREG.md.
    deployed = defaultdict(lambda: [0, 0])
    for r in sel + con:
        pred = apply_thresholds(r["arousal"], *PUBLISHED_THRESHOLDS)
        deployed[r["speaker"]][1] += 1
        deployed[r["speaker"]][0] += (pred == r["label"])
    rows_d = {s: {"correct": c, "n": n, "accuracy": round(c / n * 100, 1)}
              for s, (c, n) in sorted(deployed.items())}
    accs_d = [v["accuracy"] for v in rows_d.values()]
    out["deployed_rule_per_speaker_both_splits"] = {
        "reading": "arousal",
        "thresholds": list(PUBLISHED_THRESHOLDS),
        "by_speaker": rows_d,
        "pooled_accuracy": round(sum(v["correct"] for v in rows_d.values())
                                 / sum(v["n"] for v in rows_d.values()) * 100, 1),
        "range_points": round(max(accs_d) - min(accs_d), 1),
    }

    # The same decomposition on every cached segment, labelled or not. Uses no
    # ratings, so it describes the model's output on the whole corpus rather than
    # on the 147 clips a human happened to rate.
    usable = [r for r in corpus if r["arousal"] is not None]
    out["corpus"] = {
        "n_segments": len(usable),
        "eta2_arousal_by_video": round(
            eta_squared([r["arousal"] for r in usable],
                        [r["video_id"] for r in usable]), 4),
        "eta2_arousal_by_speaker": round(
            eta_squared([r["arousal"] for r in usable],
                        [r["speaker"] for r in usable]), 4),
    }
    return out


# ──────────────────────────────────────────────────────────────────────── main

def _render_select(d: dict) -> str:
    a = d["anchor"]
    L = ["",
         "SELECTION SPLIT - 100 clips, 2 speakers, thresholds fitted here and frozen",
         "-" * 84,
         f"anchor: refit {a['refitted_thresholds']} == published "
         f"{a['published_thresholds']},  sel {a['selection']},  con {a['confirmation']}"
         f"   PASS",
         "",
         f"{'rule':<14} {'thresholds':>21} {'acc':>7} {'95% CI':>14} "
         f"{'rho':>7} {'spk range':>10}"]
    for rid, s in d["selection"].items():
        lo, hi = d["fitted_thresholds"][rid]
        ci = f"[{s['wilson95'][0]:.1f},{s['wilson95'][1]:.1f}]"
        tag = "" if RULES[rid][2] else "  (oracle)"
        L.append(f"{rid:<14} {lo:>+10.4f} /{hi:>+9.4f} {s['accuracy']:>6.1f}% "
                 f"{ci:>14} {s['pooled_rho']:>7.3f} {s['speaker_range']:>9.1f}{tag}")
    L += ["",
          f"DECLARED WINNER (deployable rules only): {d['declared_winner']}",
          f"written to {SELECTION_OUT.name} before the holdout is touched",
          ""]
    return "\n".join(L)


def _render_confirm(d: dict, declared: dict) -> str:
    L = ["", "CONFIRMATION SPLIT - 47 clips, 4 unseen speakers, scored once",
         "-" * 78,
         f"deployed rule (0.40 / 0.65): "
         f"{d['deployed_baseline']['correct']}/{d['deployed_baseline']['n']} = "
         f"{d['deployed_baseline']['accuracy']}%",
         f"always-NEUTRAL floor and oracle majority "
         f"({d['oracle_majority_baseline']['label']}): "
         f"{d['oracle_majority_baseline']['correct']}/"
         f"{d['oracle_majority_baseline']['n']} = "
         f"{d['oracle_majority_baseline']['accuracy']}%",
         "",
         f"{'rule':<14} {'acc':>7} {'95% CI':>14} {'vs floor p':>11} "
         f"{'vs deployed p':>14} {'rho':>7} {'spk range':>10}"]
    for rid, s in d["confirmation"].items():
        lo, hi = s["wilson95"]
        tag = "  <-- declared" if rid == declared["declared_winner"] else (
            "  (oracle)" if not RULES[rid][2] else "")
        L.append(f"{rid:<14} {s['accuracy']:>6.1f}% {f'[{lo:.1f},{hi:.1f}]':>14} "
                 f"{s['vs_floor']['p_value']:>11.4f} "
                 f"{d['vs_deployed_mcnemar'][rid]['p_value']:>14.4f} "
                 f"{s['pooled_rho']:>7.3f} {s['speaker_range']:>9.1f}{tag}")
    a = d["adopt"]
    L += ["",
          f"monotonicity invariant: {d['monotonicity_invariant']}",
          f"ADOPTION: {a['decision']}  "
          f"(winner {a['winner']}, beat deployed = {a['beat_deployed_on_confirmation']}, "
          f"McNemar p = {a['mcnemar_p']:.4f}, "
          f"min attainable p = {a['min_attainable_p']:.4f})", ""]
    return "\n".join(L)


def _render_diagnose(d: dict) -> str:
    L = ["", "POST-HOC DIAGNOSTICS - exploratory, not pre-registered",
         "-" * 84,
         f"{'split':<13} {'clips':>6} {'vids':>5} {'pooled rho':>11} "
         f"{'within-vid rho':>15} {'within range':>21} {'video-level rho':>16}"]
    for split in ("selection", "confirmation", "pooled"):
        s = d[split]
        rng = f"[{s['within_video_rho_range'][0]:+.3f}, {s['within_video_rho_range'][1]:+.3f}]"
        vl = "n/a" if s["video_level_rho_arousal_vs_rating"] is None else \
            f"{s['video_level_rho_arousal_vs_rating']:+.3f}"
        L.append(f"{split:<13} {s['n_clips']:>6} {s['n_videos']:>5} "
                 f"{s['pooled_rho']:>+11.3f} {s['within_video_rho_mean']:>+15.3f} "
                 f"{rng:>21} {vl:>16}")
    L += ["",
          "variance decomposition - share of total variance lying BETWEEN groups",
          f"{'split':<13} {'arousal|video':>14} {'arousal|speaker':>16} "
          f"{'rating|video':>13} {'rating|speaker':>15}"]
    for split in ("selection", "confirmation", "pooled"):
        s = d[split]
        L.append(f"{split:<13} {s['eta2_arousal_by_video']:>14.3f} "
                 f"{s['eta2_arousal_by_speaker']:>16.3f} "
                 f"{s['eta2_rating_by_video']:>13.3f} "
                 f"{s['eta2_rating_by_speaker']:>15.3f}")
    c = d["corpus"]
    L += ["",
          f"all {c['n_segments']} cached segments, no ratings used: "
          f"arousal|video {c['eta2_arousal_by_video']:.3f}, "
          f"arousal|speaker {c['eta2_arousal_by_speaker']:.3f}",
          ""]
    o = d["oracle_thresholds_on_confirmation"]
    L += [f"ORACLE upper bound - thresholds refit ON the holdout ({o['warning']})",
          f"{'rule':<14} {'best possible':>14} {'thresholds':>24}"]
    for rid, v in o["by_rule"].items():
        th = f"{v['thresholds'][0]:+.4f} / {v['thresholds'][1]:+.4f}"
        L.append(f"{rid:<14} {v['best_possible_accuracy']:>13.1f}% {th:>24}")
    dp = d["deployed_rule_per_speaker_both_splits"]
    L += ["",
          f"deployed rule ({dp['reading']} at {dp['thresholds'][0]} / "
          f"{dp['thresholds'][1]}) per speaker, both splits, 147 clips:"]
    for s, v in dp["by_speaker"].items():
        L.append(f"  {s:<20} {v['accuracy']:>5.1f}%  ({v['correct']}/{v['n']})")
    L += [f"  {'pooled':<20} {dp['pooled_accuracy']:>5.1f}%   "
          f"range {dp['range_points']:.1f} points", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", choices=("select", "confirm", "diagnose", "both"),
                default="both")
    args = ap.parse_args()

    corpus = load_corpus()
    arousal_of = {r["uid"]: r["arousal"] for r in corpus}
    sel = load_labelled("selection", arousal_of)
    con = load_labelled("confirmation", arousal_of)

    if args.phase in ("select", "both"):
        declared = phase_select(corpus, sel, con)
        SELECTION_OUT.write_text(json.dumps(declared, indent=2, sort_keys=True))
        print(_render_select(declared))

    if args.phase in ("confirm", "both"):
        if not SELECTION_OUT.is_file():
            print(f"refusing to score the holdout: {SELECTION_OUT.name} does not exist. "
                  f"Run --phase select first.", file=sys.stderr)
            return 2
        declared = json.loads(SELECTION_OUT.read_text())
        result = phase_confirm(corpus, con, declared)
        result["diagnostics"] = phase_diagnose(corpus, sel, con)
        RESULTS_OUT.write_text(json.dumps(
            {"declared": declared, **result}, indent=2, sort_keys=True))
        print(_render_confirm(result, declared))
        print(_render_diagnose(result["diagnostics"]))
        print(f"written: {RESULTS_OUT.name}")

    if args.phase == "diagnose":
        if not RESULTS_OUT.is_file():
            print(f"run --phase confirm first: {RESULTS_OUT.name} does not exist.",
                  file=sys.stderr)
            return 2
        payload = json.loads(RESULTS_OUT.read_text())
        payload["diagnostics"] = phase_diagnose(corpus, sel, con)
        RESULTS_OUT.write_text(json.dumps(payload, indent=2, sort_keys=True))
        print(_render_diagnose(payload["diagnostics"]))
        print(f"written: {RESULTS_OUT.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
