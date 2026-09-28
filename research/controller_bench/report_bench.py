"""
report_bench.py — score what is cached. Runs no model, calls no network.

Separated from `run_bench.py` on purpose: scoring must be re-runnable, cheap and
deterministic, so that a metric can be re-derived, checked and argued about
without spending four hours of inference to see the argument through.

    python research/controller_bench/report_bench.py                 # everything
    python research/controller_bench/report_bench.py --stage grid
    python research/controller_bench/report_bench.py --json          # machine-readable

Every metric here is defined in PROTOCOL.md §5.2, fixed before any candidate ran.
Nothing is computed that was not declared, and nothing declared is omitted —
including the ones that make the LLMs look bad and the one that makes the rule
baseline look bad.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
for p in (str(PROJECT), str(BENCH)):
    if p not in sys.path:
        sys.path.insert(0, p)

import candidates as C  # noqa: E402
import probes as P  # noqa: E402
import reference as R  # noqa: E402
import stats as S  # noqa: E402

CACHE = BENCH / "cache"

# G1-G4, PROTOCOL.md §8.
GATE_PARSE_RATE = 0.95
GATE_LATENCY_MULTIPLE = 3.0
INCUMBENT = "llama3.2"


def _load(stage: str, name: str, tag: str = "") -> dict | None:
    path = CACHE / stage / f"{name}{tag}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _probes_by_id(suite: list[dict]) -> dict[str, dict]:
    return {p["probe_id"]: p for p in suite}


# ── Grid scoring ──────────────────────────────────────────────────────────────

def score_grid(name: str, stage: str = "grid", tag: str = "") -> dict | None:
    """P1-P4 plus the gate inputs, for one candidate on the configuration grid."""
    runs = _load(stage, name, tag)
    if not runs:
        return None
    by_id = _probes_by_id(P.probe_suite())
    ids = sorted(set(runs) & set(by_id))
    if not ids:
        return None

    ref_any, ref_polar, ref_score, model_score = [], [], [], []
    jac, hallucinated, parsed, latencies = [], 0, 0, []
    flags_emitted = 0

    for pid in ids:
        run = runs[pid]
        val = R.channel_valences(by_id[pid]["spec"])
        ra, rp, rs = R.ref_any(val), R.ref_polar(val), R.ref_score(val)
        ref_any.append(ra)
        ref_polar.append(rp)
        ref_score.append(rs)
        model_score.append(float(run.get("conflict_score") or 0.0))
        parsed += bool(run.get("parsed"))
        if run.get("error") is None:
            latencies.append(float(run.get("latency_s") or 0.0))
        if run.get("flags"):
            flags_emitted += 1

        named = R.normalise_channels(run.get("channels"))
        if ra:
            jac.append(R.jaccard(named, R.ref_channels_in_conflict(val)))
        # A channel named in conflict that has NO readable valence in this payload
        # cannot be in conflict with anything. `llama3.2` was observed naming
        # `facial_emotion` on 264 of 481 corpus responses whose payload reads
        # "none detected"; this counts the same failure on the grid.
        hallucinated += len(named - set(val))

    pred_any = [s > 0.0 for s in model_score]
    n = len(ids)
    polar_ids = [i for i, rp in enumerate(ref_polar) if rp]
    polar_hits = sum(1 for i in polar_ids if model_score[i] > 0.0)
    agree_ids = [i for i, ra in enumerate(ref_any) if not ra]
    agree_false = sum(1 for i in agree_ids if model_score[i] > 0.0)

    p3_mean, p3_lo, p3_hi = S.mean_ci(jac) if jac else (0.0, 0.0, 0.0)
    return {
        "candidate": name,
        "n": n,
        "P1_mcc": S.mcc(ref_any, pred_any),
        "P2_spearman": S.spearman(model_score, ref_score),
        "P3_jaccard": p3_mean, "P3_ci": (p3_lo, p3_hi), "P3_n": len(jac),
        "P4_polar_detect": polar_hits / len(polar_ids) if polar_ids else 0.0,
        "P4_k": polar_hits, "P4_n": len(polar_ids),
        "P4_ci": S.wilson(polar_hits, len(polar_ids)),
        "confusion": S.confusion(ref_any, pred_any),
        "false_alarm_on_agreement": agree_false, "n_agreement": len(agree_ids),
        "zero_rate": sum(1 for s in model_score if s == 0.0) / n,
        "distinct_scores": sorted({round(s, 4) for s in model_score}),
        "mean_score": sum(model_score) / n,
        "parse_rate": parsed / n,
        "flags_emitted": flags_emitted,
        "hallucinated_channels": hallucinated,
        "median_latency_s": statistics.median(latencies) if latencies else None,
        "_pred_any": pred_any, "_ref_any": ref_any, "_ids": ids,
    }


def score_incongruence(name: str, sound_only: bool = False) -> dict | None:
    """P5: detection on the incongruent items, minus the 12 controls' alarms.

    `sound_only` restricts the positives to the 19 items whose hand-assigned
    transcript label the deployed classifier actually reproduces (PROTOCOL.md
    Amendment A2). Both readings are reported; neither answers Q4, which the
    pre-registered floor of 20 declares underpowered at 19.
    """
    runs = _load("incongruence", name)
    if not runs:
        return None
    by_id = _probes_by_id(P.incongruence_suite())
    ids = sorted(set(runs) & set(by_id))
    if not ids:
        return None

    pos = [i for i in ids if by_id[i]["expected_conflict"]
           and not (sound_only and i in P.UNSOUND_ITEMS)]
    neg = [i for i in ids if not by_id[i]["expected_conflict"]]

    def score(i):
        return float(runs[i].get("conflict_score") or 0.0)

    hit = sum(1 for i in pos if score(i) > 0.0)
    fa = sum(1 for i in neg if score(i) > 0.0)
    flags_pos = sum(1 for i in pos if runs[i].get("flags"))
    flags_neg = sum(1 for i in neg if runs[i].get("flags"))
    return {
        "candidate": name, "sound_only": sound_only,
        "n_pos": len(pos), "n_neg": len(neg),
        "hits": hit, "hit_rate": hit / len(pos) if pos else 0.0,
        "hit_ci": S.wilson(hit, len(pos)),
        "false_alarms": fa, "fa_rate": fa / len(neg) if neg else 0.0,
        "fa_ci": S.wilson(fa, len(neg)),
        "P5": (hit / len(pos) if pos else 0.0) - (fa / len(neg) if neg else 0.0),
        "mcc": S.mcc([by_id[i]["expected_conflict"] for i in ids],
                     [score(i) > 0.0 for i in ids]),
        "flags_on_incongruent": flags_pos, "flags_on_control": flags_neg,
        "mean_score_pos": sum(score(i) for i in pos) / len(pos) if pos else 0.0,
        "mean_score_neg": sum(score(i) for i in neg) / len(neg) if neg else 0.0,
    }


def score_corpus(name: str) -> dict | None:
    """The same reference applied to the 481 real cached segments.

    Reported for external validity only. PROTOCOL.md §4.2: the channel labels here
    come from models measured at 48.9-78.7% accuracy, so a controller that
    disagrees with them may be right, and no adoption decision rests on this.
    """
    import run_bench
    runs = _load("corpus", name)
    if not runs:
        return None
    by_id = _probes_by_id(run_bench.corpus_probes())
    ids = sorted(set(runs) & set(by_id))
    if not ids:
        return None

    ref_any, ref_polar, ref_score, model_score, flagged = [], [], [], [], 0
    for pid in ids:
        val = R.channel_valences(by_id[pid]["spec"])
        ref_any.append(R.ref_any(val))
        ref_polar.append(R.ref_polar(val))
        ref_score.append(R.ref_score(val))
        s = float(runs[pid].get("conflict_score") or 0.0)
        model_score.append(s)
        flagged += s >= 0.75

    polar_ids = [i for i, rp in enumerate(ref_polar) if rp]
    hits = sum(1 for i in polar_ids if model_score[i] > 0.0)
    n = len(ids)
    return {
        "candidate": name, "n": n,
        "P1_mcc": S.mcc(ref_any, [s > 0.0 for s in model_score]),
        "P2_spearman": S.spearman(model_score, ref_score),
        "polar_detect": hits / len(polar_ids) if polar_ids else 0.0,
        "polar_k": hits, "polar_n": len(polar_ids),
        "polar_ci": S.wilson(hits, len(polar_ids)),
        "zero_rate": sum(1 for s in model_score if s == 0.0) / n,
        "mean_score": sum(model_score) / n,
        "flagged": flagged, "flag_rate": flagged / n,
        "distinct_scores": sorted({round(s, 4) for s in model_score})[:14],
        "median_latency_s": statistics.median(
            [float(runs[i]["latency_s"]) for i in ids if runs[i].get("error") is None]
            or [0.0]),
    }


# ── Is the flag threshold even reachable? ─────────────────────────────────────
#
# This was not a planned analysis. It fell out of the grid: `rule_baseline` — a
# perfect implementation of the task the system prompt specifies — flags **0 of 62**
# polar configurations at CONFLICT_FLAG_THRESHOLD. That is worth a closed-form
# answer rather than an observation, because if the threshold is unreachable then
# every flag this system has ever raised came from a controller NOT following the
# spec.
#
# The answer is definition-dependent and is reported as such. What is NOT
# definition-dependent is the pigeonhole argument: the prompt describes 1.0 as
# "all channels disagree", and with four channels drawn from three valence levels
# at least two must share a valence, so the top of the scale is unattainable
# whatever the formula.

def _spec_readings() -> dict:
    """Four plausible readings of "0.0 full agreement -> 1.0 all channels disagree".

    The deployed prompt fixes the two endpoints and says nothing about the middle,
    so a controller has to pick a reading. These are the four a competent reader
    might pick; the first is the one this bench pre-registered.
    """
    import itertools as _it
    from collections import Counter as _C

    def pairwise(vs):
        ps = list(_it.combinations(vs, 2))
        return sum(R.POLAR_WEIGHT if (a != b and R.NEUTRAL not in (a, b))
                   else (R.ADJACENT_WEIGHT if a != b else 0.0)
                   for a, b in ps) / len(ps)

    def pairwise_unweighted(vs):
        ps = list(_it.combinations(vs, 2))
        return sum(1 for a, b in ps if a != b) / len(ps)

    def distinct_normalised(vs):
        # (distinct - 1) / (n - 1), NOT distinct/n. The raw ratio gives 0.25 for
        # four agreeing channels, which contradicts the prompt's own endpoint of
        # "0.0 (full agreement)" and so is not a valid reading of it at all. The
        # unit test caught that; this is the normalisation that satisfies both
        # endpoints.
        return (len(set(vs)) - 1) / (len(vs) - 1) if len(vs) > 1 else 0.0

    def dissent_fraction(vs):
        return 1 - _C(vs).most_common(1)[0][1] / len(vs)

    return {
        "pairwise (this bench, pre-registered)": pairwise,
        "pairwise, unweighted": pairwise_unweighted,
        "distinct valences, normalised": distinct_normalised,
        "fraction dissenting from the mode": dissent_fraction,
    }


def threshold_reachability() -> dict:
    """Max attainable conflict_score per reading and per channel count.

    Pure arithmetic over the 3^n valence assignments. No model, no cache.
    """
    import itertools as _it
    from pipeline.orchestrator import CONFLICT_FLAG_THRESHOLD as T
    levels = (R.POSITIVE, R.NEUTRAL, R.NEGATIVE)
    out = {"threshold": T, "readings": {}}
    for name, f in _spec_readings().items():
        row = {}
        for n in (2, 3, 4):
            best = max(f(c) for c in _it.product(levels, repeat=n))
            row[n] = {"max": best, "reaches": best >= T}
        out["readings"][name] = row
    return out


def print_threshold_reachability() -> None:
    tr = threshold_reachability()
    print(f"\n=== Is CONFLICT_FLAG_THRESHOLD = {tr['threshold']} reachable "
          f"under the prompt's own scale? ===\n")
    print(f"{'reading of the scale':<38}{'n=2':>16}{'n=3':>16}{'n=4':>16}")
    for name, row in tr["readings"].items():
        cells = []
        for n in (2, 3, 4):
            d = row[n]
            cells.append(f"{d['max']:.3f} {'ok' if d['reaches'] else 'NO'}")
        print(f"{name:<38}" + "".join(f"{c:>16}" for c in cells))
    print("\n  'NO' = the threshold is mathematically unattainable at that channel count.")
    print("  Definition-independent: the prompt calls 1.0 \"all channels disagree\"; with")
    print("  four channels and three valence levels, two must always share a valence, so")
    print("  the top of the scale cannot be reached whatever formula is used.")


# ── Two diagnostics that name the failure rather than only measuring it ───────

def channel_marginals(name: str) -> dict:
    """Mean conflict score by the value of each channel, over the grid.

    A controller doing the task it was given should be roughly SYMMETRIC: what
    matters is whether the four labels agree, not which particular channel happens
    to be carrying the odd one out. A large marginal on exactly one channel is the
    signature of a controller that has collapsed a four-way comparison into
    reading one field.

    This is what named the incumbent's failure. Every non-zero answer it gave on
    the grid has `video_comment_sentiment == NEGATIVE`, and its marginal for that
    channel is the only non-zero one.
    """
    runs = _load("grid", name)
    if not runs:
        return {}
    by_id = _probes_by_id(P.probe_suite())
    ids = sorted(set(runs) & set(by_id))
    out: dict[str, dict[str, dict]] = {}
    for chan in R.CHANNELS:
        levels: dict[str, list[float]] = {}
        for i in ids:
            levels.setdefault(str(by_id[i]["spec"][chan]), []).append(
                float(runs[i].get("conflict_score") or 0.0))
        out[chan] = {
            lvl: {"n": len(v), "mean": sum(v) / len(v),
                  "n_nonzero": sum(1 for x in v if x > 0.0)}
            for lvl, v in sorted(levels.items())
        }
    return out


def text_sensitivity(name: str) -> dict:
    """Does the same channel configuration get the same answer on real segments?

    The corpus contains only 8 distinct channel configurations across 481
    segments, so most configurations recur many times with DIFFERENT transcript
    text, different prosody numbers and different timings. At temperature 0 with a
    fixed seed, a controller that is genuinely comparing the four labels should
    answer identically within a configuration; every within-configuration
    difference is the controller responding to something that is not the labels.

    Reported as the number of configurations that produced more than one distinct
    score, and the fraction of segments sitting on a minority answer. It is a
    diagnostic, not a fault: reading the transcript may be the RIGHT thing to do
    (see the incongruence suite). What it is not is comparing four labels.
    """
    import run_bench
    runs = _load("corpus", name)
    if not runs:
        return {}
    by_id = _probes_by_id(run_bench.corpus_probes())
    groups: dict[tuple, list[float]] = {}
    for pid, run in runs.items():
        if pid not in by_id:
            continue
        key = tuple(sorted(by_id[pid]["spec"].items()))
        groups.setdefault(key, []).append(float(run.get("conflict_score") or 0.0))

    split, minority, total = 0, 0, 0
    for scores in groups.values():
        total += len(scores)
        counts = Counter(round(x, 4) for x in scores)
        if len(counts) > 1:
            split += 1
            minority += len(scores) - counts.most_common(1)[0][1]
    return {
        "n_configurations": len(groups),
        "n_configurations_with_more_than_one_answer": split,
        "n_segments": total,
        "n_on_a_minority_answer": minority,
        "minority_rate": minority / total if total else 0.0,
    }


# ── Rule 7: what each controller does to the numbers the product reports ──────

def product_scores(name: str) -> dict | None:
    """Authenticity and Brand Health per video, from this controller's answers.

    Step 7 of the bench method (README) requires that an adopted winner be re-run over the corpus with
    the before/after reported. Because the corpus stage runs every candidate, this
    is available for all of them, not only a winner — which is more useful: it
    shows how much of the reported score is a property of the *system* and how much
    is a property of one arbitrary model choice, the exact question
    the project's work plan asked.

    The production `scorer.build_final_report` does the arithmetic. Damping is
    whatever the current module constants say, applied by `_coerce_result` at run
    time — that is deliberate: this function reports what the deployed system would
    actually print, not a bench-conditioned variant.
    """
    import run_bench
    from pipeline.scorer import build_final_report
    runs = _load("corpus", name)
    if not runs:
        return None
    by_id = {p["probe_id"]: p for p in run_bench.corpus_probes()}

    per_video: dict[str, dict] = {}
    for pid, run in runs.items():
        if pid not in by_id:
            continue
        per_video.setdefault(by_id[pid]["video_id"], {"segs": [], "res": [],
                                                      "cs": by_id[pid]["comment_sentiment"]})
        v = per_video[by_id[pid]["video_id"]]
        v["segs"].append(by_id[pid]["segment"])
        v["res"].append({
            "segment_id": by_id[pid]["segment"]["segment_id"],
            "start_s": by_id[pid]["segment"]["start_time"],
            "end_s": by_id[pid]["segment"]["end_time"],
            "conflict_score": float(run.get("conflict_score") or 0.0),
            "conflict_reasons": [],
            "flagged": float(run.get("conflict_score") or 0.0) >= 0.75,
        })

    rows = []
    for vid, v in sorted(per_video.items()):
        rep = build_final_report(f"https://youtu.be/{vid}", "controller-bench",
                                 v["segs"], v["res"], v["cs"])
        rows.append({"video_id": vid,
                     "authenticity": rep["authenticity_score"],
                     "brand_health": rep["brand_health_score"],
                     "n_segments": len(v["res"]),
                     "n_flagged": len(rep["flagged_segments"])})
    if not rows:
        return None
    n = len(rows)
    return {
        "candidate": name, "n_videos": n,
        "mean_authenticity": sum(r["authenticity"] for r in rows) / n,
        "mean_brand_health": sum(r["brand_health"] for r in rows) / n,
        "total_flagged": sum(r["n_flagged"] for r in rows),
        "total_segments": sum(r["n_segments"] for r in rows),
        "per_video": rows,
    }


# ── Robustness of the metrics themselves ──────────────────────────────────────
#
# Three checks that no result in this bench should survive without. They cost no
# inference — every one is a recomputation over cached responses — and each
# targets a specific way the headline could be an artefact of a reporting choice
# rather than a property of the models.

ADJACENT_WEIGHTS = (0.25, 0.5, 0.75)
P1_THRESHOLDS = (0.0, 0.25, 0.5)


def sensitivity_adjacent_weight(name: str) -> dict:
    """Does P2's ranking depend on the one free parameter in the reference?

    `reference.ADJACENT_WEIGHT` = 0.5 was declared before any run (PROTOCOL.md
    §5.1) but it is still a choice. If a candidate's Spearman rho moved materially
    when it changed, P2 would be measuring the choice rather than the model.
    """
    runs = _load("grid", name)
    if not runs:
        return {}
    by_id = _probes_by_id(P.probe_suite())
    ids = sorted(set(runs) & set(by_id))
    out = {}
    original = R.ADJACENT_WEIGHT
    try:
        for w in ADJACENT_WEIGHTS:
            R.ADJACENT_WEIGHT = w
            ref = [R.ref_score(R.channel_valences(by_id[i]["spec"])) for i in ids]
            mod = [float(runs[i].get("conflict_score") or 0.0) for i in ids]
            out[w] = S.spearman(mod, ref)
    finally:
        R.ADJACENT_WEIGHT = original
    return out


def sensitivity_p1_threshold(name: str) -> dict:
    """Does P1 depend on treating ANY non-zero score as a detection?

    P1 binarises at `score > 0`. A controller that answered 0.05 to everything
    would score well on that and be useless in production, where nothing happens
    below CONFLICT_FLAG_THRESHOLD. Recomputing P1 at higher thresholds shows
    whether a candidate's detections are substantive or nominal.
    """
    runs = _load("grid", name)
    if not runs:
        return {}
    by_id = _probes_by_id(P.probe_suite())
    ids = sorted(set(runs) & set(by_id))
    gold = [R.ref_any(R.channel_valences(by_id[i]["spec"])) for i in ids]
    mod = [float(runs[i].get("conflict_score") or 0.0) for i in ids]
    return {t: S.mcc(gold, [m > t for m in mod]) for t in P1_THRESHOLDS}


def detection_at_flag_threshold(name: str) -> dict:
    """The product-relevant number: polar conflicts that would actually be FLAGGED.

    `scorer.compute_authenticity_score` double-weights a flagged segment and
    nothing else in the system reacts to `conflict_score` at all. So a controller
    that answers 0.3 on a genuine polar conflict has, as far as the delivered
    product is concerned, answered 0.0. P4 counts detections at `> 0` because that
    is the diagnostic quantity; this counts them at
    `>= CONFLICT_FLAG_THRESHOLD`, which is the operational one, and the gap
    between the two is itself worth reporting.
    """
    from pipeline.orchestrator import CONFLICT_FLAG_THRESHOLD
    runs = _load("grid", name)
    if not runs:
        return {}
    by_id = _probes_by_id(P.probe_suite())
    ids = sorted(set(runs) & set(by_id))
    polar = [i for i in ids
             if R.ref_polar(R.channel_valences(by_id[i]["spec"]))]
    agree = [i for i in ids
             if not R.ref_any(R.channel_valences(by_id[i]["spec"]))]

    def sc(i):
        return float(runs[i].get("conflict_score") or 0.0)

    k = sum(1 for i in polar if sc(i) >= CONFLICT_FLAG_THRESHOLD)
    fa = sum(1 for i in agree if sc(i) >= CONFLICT_FLAG_THRESHOLD)
    return {
        "threshold": CONFLICT_FLAG_THRESHOLD,
        "flagged_polar": k, "n_polar": len(polar),
        "rate": k / len(polar) if polar else 0.0,
        "ci": S.wilson(k, len(polar)),
        "flagged_on_agreement": fa, "n_agreement": len(agree),
    }


# ── Head-to-head and the adoption rule ────────────────────────────────────────

def head_to_head(a: dict, b: dict) -> dict:
    """Exact McNemar on the paired grid probes, on the P1 decision.

    Pairs where both models get the same answer carry no information about a
    difference and are dropped by the test, not by this function.
    """
    ids = [i for i in a["_ids"] if i in set(b["_ids"])]
    ia = {pid: k for k, pid in enumerate(a["_ids"])}
    ib = {pid: k for k, pid in enumerate(b["_ids"])}
    a_only = b_only = 0
    for pid in ids:
        ga = a["_ref_any"][ia[pid]]
        ra = a["_pred_any"][ia[pid]] == ga
        rb = b["_pred_any"][ib[pid]] == ga
        a_only += ra and not rb
        b_only += rb and not ra
    return {"n_paired": len(ids), **S.mcnemar_verdict(a_only, b_only)}


def evaluate_adoption(grids: dict, incs: dict, latency_ref: float | None) -> dict:
    """Apply PROTOCOL.md §8 exactly as written, and show every condition.

    Nothing here is decided at report time. The four conditions, the gates and the
    tie-break were fixed before any candidate ran; this function only evaluates
    them and prints which ones each candidate failed.
    """
    inc_ref = incs.get(INCUMBENT)
    base = grids.get(INCUMBENT)
    rows = []
    for name, g in grids.items():
        if name == INCUMBENT or C.is_reference(name):
            continue
        i = incs.get(name)
        h2h = head_to_head(g, base) if base else None
        lat_ok = (latency_ref is None or g["median_latency_s"] is None
                  or g["median_latency_s"] <= GATE_LATENCY_MULTIPLE * latency_ref)
        cond = {
            "G1_parse": g["parse_rate"] >= GATE_PARSE_RATE,
            "G4_latency": bool(lat_ok),
            # PROTOCOL.md §8 condition 2 reads "beats the incumbent on **P1**,
            # with an exact McNemar test ... p < 0.05 in the challenger's
            # favour" — that is a CONJUNCTION, and the first half was missing
            # here until the full grid exposed it. `always_flag` passes the
            # McNemar (it agrees with `ref_any` on 102 of 108 probes simply by
            # never abstaining) while scoring MCC 0.000, and `gemma3_4b` does the
            # same. Testing only the McNemar would let a model that is
            # significantly better at a BINARY decision be adopted while being no
            # better, or worse, on the metric the rule names.
            #
            # This is a correction to the code to make it faithful to the
            # pre-registered rule, not a change to the rule.
            "C2_beats_P1": bool(h2h and h2h["better"]
                                and base and g["P1_mcc"] > base["P1_mcc"]),
            "C3_no_P2_regression": bool(base and g["P2_spearman"] >= base["P2_spearman"] - 0.05),
            "C4_no_P5_regression": bool(
                i and inc_ref and i["P5"] >= inc_ref["P5"] - 1e-9),
        }
        rows.append({
            "candidate": name, "conditions": cond,
            "qualifies": all(cond.values()),
            "P1": g["P1_mcc"], "P2": g["P2_spearman"],
            "P5": i["P5"] if i else None,
            "mcnemar": h2h,
        })
    winners = [r for r in rows if r["qualifies"]]
    winners.sort(key=lambda r: (-r["P1"], -(r["P5"] or 0.0)))
    return {"rows": rows, "winner": winners[0]["candidate"] if winners else None,
            "n_qualifying": len(winners)}


# ── Printing ──────────────────────────────────────────────────────────────────

def _pct(x): return "   —" if x is None else f"{x:6.1%}"
def _f(x, w=6, p=3): return "  —" if x is None else f"{x:{w}.{p}f}"


def print_grid(grids: dict) -> None:
    print("\n=== Bench A — configuration grid, 108 probes "
          "(P1 primary; ties to reference rows are by construction) ===\n")
    print(f"{'candidate':<15}{'P1 MCC':>8}{'P2 rho':>8}{'P3 Jac':>8}"
          f"{'P4 polar':>10}{'zero':>7}{'FA/agree':>9}{'parse':>7}"
          f"{'lat s':>7}{'flags':>7}{'halluc':>7}")
    order = sorted(grids.values(), key=lambda g: -g["P1_mcc"])
    for g in order:
        mark = " *" if C.is_reference(g["candidate"]) else ""
        print(f"{g['candidate'] + mark:<15}{g['P1_mcc']:>8.3f}{g['P2_spearman']:>8.3f}"
              f"{g['P3_jaccard']:>8.3f}"
              f"{g['P4_k']:>5}/{g['P4_n']:<4}{g['zero_rate']:>7.1%}"
              f"{g['false_alarm_on_agreement']:>5}/{g['n_agreement']:<3}"
              f"{g['parse_rate']:>7.0%}"
              f"{'   —' if g['median_latency_s'] is None else format(g['median_latency_s'], '>7.1f')}"
              f"{g['flags_emitted']:>7}{g['hallucinated_channels']:>7}")
    print("\n  * reference, not a competitor. rule_baseline scores P1/P2 = 1.000 by "
          "construction (PROTOCOL.md §3.2).")


def print_incongruence(incs: dict) -> None:
    print("\n=== Bench B — incongruence suite, 24 incongruent + 12 control ===\n")
    print(f"{'candidate':<15}{'hits':>10}{'hit rate':>10}{'false al.':>11}"
          f"{'P5':>8}{'MCC':>8}{'flags+':>8}{'flags-':>8}")
    for i in sorted(incs.values(), key=lambda x: -x["P5"]):
        mark = " *" if C.is_reference(i["candidate"]) else ""
        print(f"{i['candidate'] + mark:<15}{i['hits']:>6}/{i['n_pos']:<3}"
              f"{i['hit_rate']:>10.1%}{i['false_alarms']:>7}/{i['n_neg']:<3}"
              f"{i['P5']:>8.3f}{i['mcc']:>8.3f}"
              f"{i['flags_on_incongruent']:>8}{i['flags_on_control']:>8}")


def print_corpus(corp: dict) -> None:
    print("\n=== Bench C — 481 real cached segments (external validity only) ===\n")
    print(f"{'candidate':<15}{'P1 MCC':>8}{'P2 rho':>8}{'polar':>12}"
          f"{'zero':>8}{'flag rate':>11}{'lat s':>8}")
    for c in sorted(corp.values(), key=lambda x: -x["P1_mcc"]):
        mark = " *" if C.is_reference(c["candidate"]) else ""
        print(f"{c['candidate'] + mark:<15}{c['P1_mcc']:>8.3f}{c['P2_spearman']:>8.3f}"
              f"{c['polar_k']:>6}/{c['polar_n']:<5}{c['zero_rate']:>8.1%}"
              f"{c['flag_rate']:>11.1%}{c['median_latency_s']:>8.1f}")


def print_adoption(ad: dict) -> None:
    print("\n=== Adoption rule (PROTOCOL.md §8, fixed before any run) ===\n")
    print(f"{'candidate':<15}{'G1':>5}{'G4':>5}{'C2 P1':>7}{'C3 P2':>7}{'C4 P5':>7}"
          f"{'  McNemar p':>12}{'  verdict':>12}")
    for r in sorted(ad["rows"], key=lambda r: -r["P1"]):
        c = r["conditions"]
        def m(x): return "  ok" if x else "  no"
        p = r["mcnemar"]["p"] if r["mcnemar"] else None
        # A tiny p renders as "0.0000" under %.4f, which reads as exactly zero.
        ptxt = "—" if p is None else ("< 0.0001" if p < 0.0001 else f"{p:.4f}")
        print(f"{r['candidate']:<15}{m(c['G1_parse']):>5}{m(c['G4_latency']):>5}"
              f"{m(c['C2_beats_P1']):>7}{m(c['C3_no_P2_regression']):>7}"
              f"{m(c['C4_no_P5_regression']):>7}"
              f"{ptxt:>12}"
              f"{'  QUALIFIES' if r['qualifies'] else '  —':>12}")
    print(f"\n  winner: {ad['winner'] or 'NONE — nothing is adopted'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("grid", "incongruence", "corpus",
                                        "ablation", "all"), default="all")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    grids = {n: g for n in C.ALL_CANDIDATES if (g := score_grid(n))}
    incs = {n: i for n in C.ALL_CANDIDATES if (i := score_incongruence(n))}
    corp = {n: c for n in C.ALL_CANDIDATES if (c := score_corpus(n))}
    lat_ref = grids.get(INCUMBENT, {}).get("median_latency_s")
    ad = evaluate_adoption(grids, incs, lat_ref) if INCUMBENT in grids else None

    if args.json:
        print(json.dumps({
            "grid": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                     for k, v in grids.items()},
            "incongruence": incs, "corpus": corp, "adoption": ad,
        }, indent=1, default=str))
        return 0

    if args.stage in ("grid", "all") and grids:
        print_grid(grids)
    if args.stage in ("incongruence", "all") and incs:
        print_incongruence(incs)
    if args.stage in ("corpus", "all") and corp:
        print_corpus(corp)
    if args.stage in ("ablation", "all"):
        rows = {}
        for n in C.LLM_CANDIDATES:
            base, rev = score_grid(n), score_grid(n, "ablation", "_revised")
            if base and rev:
                rows[n] = (base, rev)
        if rows:
            print("\n=== Prompt ablation (Q2) — deployed prompt vs revised ===\n")
            print(f"{'candidate':<15}{'P1 dep':>9}{'P1 rev':>9}{'Δ P1':>8}"
                  f"{'P4 dep':>9}{'P4 rev':>9}")
            for n, (b, r) in sorted(rows.items(), key=lambda kv: -(kv[1][1]["P1_mcc"])):
                print(f"{n:<15}{b['P1_mcc']:>9.3f}{r['P1_mcc']:>9.3f}"
                      f"{r['P1_mcc'] - b['P1_mcc']:>+8.3f}"
                      f"{b['P4_polar_detect']:>9.1%}{r['P4_polar_detect']:>9.1%}")
    if args.stage in ("corpus", "all") and corp:
        prod = {n: v for n in C.ALL_CANDIDATES if (v := product_scores(n))}
        if prod:
            print("\n=== Rule 7 — what each controller does to the reported scores ===\n")
            print(f"{'candidate':<15}{'Authenticity':>14}{'Brand Health':>14}"
                  f"{'flagged':>12}{'videos':>8}")
            for v in sorted(prod.values(), key=lambda x: -x["mean_authenticity"]):
                print(f"{v['candidate']:<15}{v['mean_authenticity']:>14.2f}"
                      f"{v['mean_brand_health']:>14.2f}"
                      f"{v['total_flagged']:>7}/{v['total_segments']:<4}"
                      f"{v['n_videos']:>8}")
    if args.stage in ("grid", "all") and grids:
        print("\n=== Robustness — does the headline survive the reporting choices? ===\n")
        print(f"{'candidate':<15}{'P2 w=.25':>10}{'P2 w=.50':>10}{'P2 w=.75':>10}"
              f"{'P1 >0':>8}{'P1 >.25':>9}{'P1 >.5':>8}{'flagged polar':>15}")
        for n in sorted(grids, key=lambda k: -grids[k]["P1_mcc"]):
            sw = sensitivity_adjacent_weight(n)
            st = sensitivity_p1_threshold(n)
            ft = detection_at_flag_threshold(n)
            print(f"{n:<15}"
                  f"{sw.get(0.25, 0):>10.3f}{sw.get(0.5, 0):>10.3f}{sw.get(0.75, 0):>10.3f}"
                  f"{st.get(0.0, 0):>8.3f}{st.get(0.25, 0):>9.3f}{st.get(0.5, 0):>8.3f}"
                  f"{ft.get('flagged_polar', 0):>9}/{ft.get('n_polar', 0):<5}")
    if args.stage in ("grid", "all"):
        print_threshold_reachability()
    if args.stage in ("grid", "all") and grids:
        print("\n=== Channel marginals — is the controller symmetric across channels? ===\n")
        print(f"{'candidate':<15}" + "".join(f"{c.split('_')[0][:10]:>18}  " for c in R.CHANNELS))
        print(f"{'':<15}" + "".join(f"{'POS / NEU / NEG':>18}  " for _ in R.CHANNELS))
        for n in sorted(grids, key=lambda k: -grids[k]["P1_mcc"]):
            m = channel_marginals(n)
            cells = []
            for c in R.CHANNELS:
                lv = m.get(c, {})
                cells.append(" / ".join(
                    f"{lv.get(k, {}).get('mean', 0):.2f}"
                    for k in (("happy", "neutral", "sad") if c == "facial_emotion"
                              else ("POSITIVE", "NEUTRAL", "NEGATIVE"))))
            print(f"{n:<15}" + "".join(f"{x:>18}  " for x in cells))
        print("\n  facial column reads happy/neutral/sad; "
              "'none detected' has no valence and is omitted.")
    if args.stage in ("corpus", "all") and corp:
        print("\n=== Text sensitivity — same four labels, different transcript ===\n")
        print(f"{'candidate':<15}{'configs':>9}{'configs split':>15}"
              f"{'segs on minority':>19}{'rate':>8}")
        for n in sorted(corp, key=lambda k: -corp[k]["P1_mcc"]):
            t = text_sensitivity(n)
            if t:
                print(f"{n:<15}{t['n_configurations']:>9}"
                      f"{t['n_configurations_with_more_than_one_answer']:>15}"
                      f"{t['n_on_a_minority_answer']:>13}/{t['n_segments']:<5}"
                      f"{t['minority_rate']:>8.1%}")
    if args.stage == "all" and ad:
        print_adoption(ad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
