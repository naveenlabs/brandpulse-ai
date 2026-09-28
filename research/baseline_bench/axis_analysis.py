"""axis_analysis.py — is the human construct the same axis the pipeline measures?

**Post-hoc. NOT pre-registered.** Declared in `PROTOCOL.md` Amendment A6, written
after P1 returned null and after the author stated, in plain terms, what the four
raters were actually judging: *whether the speaker means what they are saying*,
with the positive/negative direction of the content explicitly irrelevant.

That is a claim about the construct, and until it is measured it is an anecdote.
This module measures it. Nothing here changes any pre-registered result; P1-P6
stand exactly as reported in `BASELINE_ANALYSIS.md`.

The argument is built in two halves, because either half alone is weak:

  Half 1 — the system faithfully implements its own design. Its conflict score
           tracks the cross-channel valence disagreement it was built to detect.
           So the null result is not an implementation bug.

  Half 2 — that quantity does not predict human sincerity judgement, and neither
           does any other function of the four channel labels. An oracle with
           perfect knowledge of every label, fitted on this data and honestly
           cross-validated, is bounded well below the human ceiling.

Together those say: the pipeline works, and measures a different axis. That is a
statement about the architecture's premise, not about any checkpoint in it, and
it cannot be fixed by a better prompt, a better model, or a better threshold.

Run:  python axis_analysis.py            (writes axis_results.json)
"""

from __future__ import annotations

import collections
import itertools
import json
import pathlib
import random
import sys

import math

import stats
from rater_analysis import (MIN_USABLE, N_BOOT, SEED, ground_truth, load,
                            permutation_p, usable_count)

BENCH = pathlib.Path(__file__).resolve().parent
OUT = BENCH / "axis_results.json"

N_FOLDS = 10        # A4 cross-validation
N_SHUFFLE = 1000    # A4 null band
N_SPLITS = 500      # A4 repeated train/test splits
N_RESTARTS = 60     # A4 ordering search when exhaustive is infeasible
EXHAUSTIVE_MAX = 8  # groups; 8! = 40,320 orderings

# Valence, the axis every channel in this pipeline actually reports. The three
# sentiment channels are already three-way; the facial channel's seven FER
# classes are collapsed onto the same axis so that "do the channels agree?" is a
# question about one quantity rather than four incommensurable ones -- which is
# exactly the reduction the controller prompt asks the LLM to perform in prose.
VALENCE = {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": -1}

# `surprise` is the only judgement call here: it is high-arousal and unsigned.
# It is mapped +1 in the primary run and 0 in a sensitivity run (§A5), and it
# occurs on 3 of 119 segments, so it cannot carry a result either way.
FACIAL_VALENCE = {"happy": 1, "surprise": 1, "neutral": 0,
                  "sad": -1, "fear": -1, "angry": -1, "disgust": -1}
FACIAL_VALENCE_ALT = dict(FACIAL_VALENCE, surprise=0)


# --------------------------------------------------------------- construction

def build_rows(items, per_rater, facial_map=FACIAL_VALENCE):
    """One row per scorable segment, carrying h, the channel labels, and c.

    A segment is scorable on exactly the P1 rule (PROTOCOL.md §5.4): at least
    MIN_USABLE raters gave it a usable rating. The same 119 segments as P1, so
    every number here is directly comparable to one already reported.
    """
    rows = []
    for uid, it in items.items():
        if usable_count(per_rater, uid) < MIN_USABLE:
            continue
        h = ground_truth(per_rater, uid)
        if h is None:
            continue

        cache = BENCH / "cache" / "four_channel" / f"{uid}.json"
        if not cache.exists():
            continue
        rec = json.loads(cache.read_text())

        # Provenance: the labels the raters' clips were built from and the
        # labels the controller was shown must be the same labels. If a page or
        # a payload was rebuilt from a different pipeline run, every number
        # below is comparing two different worlds and must not be produced.
        pay = rec["payload"]
        assert pay["transcript_sentiment"].split(" (")[0] == it["transcript_sentiment"]
        assert pay["vocal_emotion"].split(" (")[0] == it["vocal_emotion"]
        pay_face = pay["facial_emotion"]
        face = it["facial_emotion"]
        assert (pay_face == "none detected") == (face is None), uid
        if face is not None:
            assert pay_face.split(" (")[0] == face, uid
        assert pay["video_comment_sentiment"].split(" (")[0] == \
               it["video_comment_sentiment"]

        vt = VALENCE[it["transcript_sentiment"]]
        vv = VALENCE[it["vocal_emotion"]]
        vf = facial_map[face] if face is not None else None
        vc = VALENCE[it["video_comment_sentiment"]]

        rows.append({
            "uid": uid,
            "split": it["split"],
            "h": h,
            "c": rec["result"]["conflict_score"],
            "c_raw": json.loads(rec["raw"]).get("conflict_score"),
            "t_label": it["transcript_sentiment"],
            "v_label": it["vocal_emotion"],
            "f_label": face,
            "vt": vt, "vv": vv, "vf": vf, "vc": vc,
            # What the controller was actually shown, in valence terms. The
            # facial channel is absent, not zero, when no face was detected --
            # "no evidence" and "neutral evidence" are different inputs and
            # collapsing them would manufacture agreement that was never there.
            "seen": [x for x in (vt, vv, vf, vc) if x is not None],
        })
    return rows


def disagreement(row):
    """Population SD of the valences the controller was shown.

    This is the quantity the architecture is built to detect, expressed as one
    number: zero when every channel agrees, larger as they spread apart. It is
    computed from the pipeline's own labels and involves no LLM, so correlating
    it against the LLM's score asks a clean question -- did the controller
    detect the thing it was asked to detect?
    """
    xs = row["seen"]
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def n_distinct(row):
    return len(set(row["seen"]))


# -------------------------------------------------------------------- helpers

def rho(rows, f, g):
    a = [f(r) for r in rows]
    b = [g(r) for r in rows]
    return stats.spearman(a, b)


def rho_ci(rows, f, g, n_boot=N_BOOT):
    d = stats.bootstrap_ci(rows, lambda rs: rho(rs, f, g), n_boot=n_boot, seed=SEED)
    return {"rho": d["point"], "lo": d["lo"], "hi": d["hi"],
            "n": d["n"], "n_degenerate": d["n_degenerate"],
            "excludes_zero": bool(d["lo"] > 0 or d["hi"] < 0)}


def paired(rows, fa, fb, target=lambda r: r["h"], n_boot=N_BOOT):
    """Difference of two dependent Spearman correlations, same resamples."""
    d = stats.paired_bootstrap_diff(
        rows,
        lambda rs: rho(rs, target, fa),
        lambda rs: rho(rs, target, fb),
        n_boot=n_boot, seed=SEED)
    return {k: d[k] for k in ("point", "lo", "hi", "n", "win_frac", "excludes_zero")}


# ------------------------------------------------------------ A4: the oracle

def _group_means(rows, key):
    tot, cnt = collections.defaultdict(float), collections.Counter()
    for r in rows:
        tot[key(r)] += r["h"]
        cnt[key(r)] += 1
    return {k: tot[k] / cnt[k] for k in tot}, sum(tot.values()) / len(rows)


def _cv_predictions(rows, key, n_folds, seed):
    """K-fold out-of-sample predictions from a function of the channel labels.

    Each segment is predicted by the mean h of the segments that share its
    label-tuple **in the other folds**, so the prediction never sees its own
    value. A label-tuple absent from the training folds falls back to the
    training mean, which is the only honest answer for an unseen combination.

    Leave-one-out is NOT used here, and the reason is measured rather than
    asserted: with group means, the LOO prediction for segment i is
    (S_g - h_i)/(n_g - 1), a strictly *decreasing* function of h_i, so within
    every group the LOO predictions are perfectly rank-reversed against the
    truth. On these group sizes that artefact alone produces rho = -0.3755 on
    pure noise (`null_loo` below re-derives it on this data). K-fold does not
    have the defect because a test point is never in its own training set.
    """
    idx = list(range(len(rows)))
    random.Random(seed).shuffle(idx)
    folds = [idx[i::n_folds] for i in range(n_folds)]
    pred = {}
    for f in folds:
        test = set(f)
        train = [rows[i] for i in idx if i not in test]
        means, gm = _group_means(train, key)
        for i in f:
            pred[rows[i]["uid"]] = means.get(key(rows[i]), gm)
    return pred


def _loo_predictions(rows, key):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    total = sum(r["h"] for r in rows)
    pred = {}
    for r in rows:
        others = [m for m in groups[key(r)] if m["uid"] != r["uid"]]
        pred[r["uid"]] = (sum(m["h"] for m in others) / len(others) if others
                          else (total - r["h"]) / (len(rows) - 1))
    return pred


def _repeated_split(rows, key, n_train, n_splits, seed, shuffle_h=False):
    """Repeated disjoint train/test splits -- the one estimator here with no bias.

    A test segment's prediction is computed only from training segments, and the
    training set is chosen without reference to any test value, so the
    prediction cannot depend on the segment's own h through any path. K-fold
    still couples them weakly (a fold's members are removed from each other's
    training group mean, so an unusually high-h fold lowers its own prediction)
    and leave-one-out couples them maximally. `null_*` below measures all three
    biases on this data rather than arguing about them.

    Reported as a distribution over splits, not a single number, because one
    39-segment test set on 3 label groups is a high-variance estimate.
    """
    rng = random.Random(seed)
    hs = [r["h"] for r in rows]
    out = []
    for _ in range(n_splits):
        work = rows
        if shuffle_h:
            sh = hs[:]
            rng.shuffle(sh)
            work = [dict(r, h=v) for r, v in zip(rows, sh)]
        idx = list(range(len(work)))
        rng.shuffle(idx)
        train = [work[i] for i in idx[:n_train]]
        test = [work[i] for i in idx[n_train:]]
        means, gm = _group_means(train, key)
        r = stats.spearman([t["h"] for t in test],
                           [means.get(key(t), gm) for t in test])
        if r is not None and r == r:
            out.append(r)
    out.sort()
    return {"mean": sum(out) / len(out),
            "median": stats._percentile(out, 0.5),
            "lo": stats._percentile(out, 0.025),
            "hi": stats._percentile(out, 0.975),
            "n_splits": len(out),
            "n_train": n_train, "n_test": len(rows) - n_train}


def _null_band(rows, key, predictor, n_shuffle, seed):
    """Distribution of the estimator under H0: labels carry no information.

    The label-tuples are held fixed and h is permuted across segments, so any
    correlation that survives is a property of the estimator rather than of the
    data. An estimator worth using has a null band centred on zero.
    """
    rng = random.Random(seed)
    hs = [r["h"] for r in rows]
    out = []
    for _ in range(n_shuffle):
        sh = hs[:]
        rng.shuffle(sh)
        perm = [dict(r, h=v) for r, v in zip(rows, sh)]
        pred = predictor(perm)
        out.append(stats.spearman([r["h"] for r in perm],
                                  [pred[r["uid"]] for r in perm]))
    out.sort()
    return {"mean": sum(out) / len(out),
            "lo": stats._percentile(out, 0.025),
            "hi": stats._percentile(out, 0.975),
            "n_shuffle": len(out)}


def eta_upper_bound(rows, key):
    """Provable upper bound on Spearman rho for ANY function of the labels.

    Spearman is Pearson on ranks, so for a predictor that is constant within a
    label-group it equals Pearson(R, Q) where R is the rank vector of h and Q is
    some group-constant vector. Maximising a Pearson correlation against a
    group-constant vector is exactly the correlation ratio: the maximum is
    sqrt(between-group variance of R / total variance of R), attained at
    Q_g = mean rank within g.

    This is a bound, not an achieved value: the predictor's own *ranks* are what
    enter the correlation, and the mid-rank vector induced by an ordering is not
    generally proportional to the group mean ranks. So the true achievable
    maximum sits at or below this, and `best_ordering` below finds where.

    The bound covers every possible rule -- every prompt, every LLM, every
    threshold, every future model -- provided it reads only these labels.
    """
    R = stats.ranks([r["h"] for r in rows])
    rbar = sum(R) / len(R)
    total = sum((x - rbar) ** 2 for x in R)
    if total <= 0:
        return float("nan")
    groups = collections.defaultdict(list)
    for i, r in enumerate(rows):
        groups[key(r)].append(i)
    between = sum(len(ix) * ((sum(R[i] for i in ix) / len(ix)) - rbar) ** 2
                  for ix in groups.values())
    return (between / total) ** 0.5


def best_ordering(rows, key, restarts=N_RESTARTS, seed=SEED):
    """Largest Spearman actually achievable by a rule over the labels.

    Exhaustive over all orderings when there are few enough groups; otherwise
    seeded pairwise-swap local search from the mean-rank ordering plus random
    restarts. Reported alongside `eta_upper_bound`, which brackets it from
    above, so the two together say where the ceiling is without either being
    asserted on faith.
    """
    h = [r["h"] for r in rows]
    R = stats.ranks(h)
    groups = collections.defaultdict(list)
    for i, r in enumerate(rows):
        groups[key(r)].append(i)
    ks = list(groups)
    n = len(rows)

    def rho_of(order):
        pred = [0.0] * n
        for pos, k in enumerate(order):
            for i in groups[k]:
                pred[i] = float(pos)
        return stats.spearman(h, pred)

    by_rank = sorted(ks, key=lambda k: sum(R[i] for i in groups[k]) / len(groups[k]))
    means, _ = _group_means(rows, key)
    best = max(rho_of(by_rank),
               stats.spearman(h, [means[key(r)] for r in rows]))

    if len(ks) <= EXHAUSTIVE_MAX:
        best = max(best, max(rho_of(list(p)) for p in itertools.permutations(ks)))
        return {"rho": best, "method": "exhaustive", "n_orderings_or_restarts":
                math.factorial(len(ks))}

    rng = random.Random(seed)
    for t in range(restarts):
        order = by_rank[:] if t == 0 else ks[:]
        if t:
            rng.shuffle(order)
        cur, improved = rho_of(order), True
        while improved:
            improved = False
            for a in range(len(order)):
                for b in range(a + 1, len(order)):
                    order[a], order[b] = order[b], order[a]
                    v = rho_of(order)
                    if v > cur + 1e-12:
                        cur, improved = v, True
                    else:
                        order[a], order[b] = order[b], order[a]
        best = max(best, cur)
    return {"rho": best, "method": f"local-search x{restarts}",
            "n_orderings_or_restarts": restarts}


def oracle(rows, key, n_folds=N_FOLDS, seed=SEED, n_shuffle=N_SHUFFLE):
    """Best predictor that is a function of the channel labels alone.

    `rho_in_sample` fits and evaluates on the same 119 points. It is optimistic
    by construction, and that is exactly why it is useful: no function of these
    labels -- no prompt, no LLM, no threshold, no future model reading the same
    four channels -- can beat it on this data, because any such function must
    emit one value per label-tuple and the group mean is the value that
    maximises the fit. It is a hard ceiling, not an estimate.

    `rho_cv` is the honest out-of-sample estimate, and `rho_split` repeats it on
    the protocol's own selection/holdout partition so the number is comparable
    with P1 and P3 rather than being a fourth way of cutting the data.
    """
    groups = collections.defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    means, _ = _group_means(rows, key)

    cv = _cv_predictions(rows, key, n_folds, seed)
    loo = _loo_predictions(rows, key)

    # Protocol's own split, where it is populated on both sides.
    sel = [r for r in rows if r["split"] == "selection"]
    hold = [r for r in rows if r["split"] == "holdout"]
    if sel and hold:
        sm, sgm = _group_means(sel, key)
        split_rho = stats.spearman(
            [r["h"] for r in hold],
            [sm.get(key(r), sgm) for r in hold])
        n_unseen = sum(1 for r in hold if key(r) not in sm)
    else:
        split_rho, n_unseen = float("nan"), 0

    n_train = len(sel) if (sel and hold) else max(2, round(len(rows) * 2 / 3))
    sizes = [len(v) for v in groups.values()]
    cv_ci = stats.bootstrap_ci(
        rows, lambda rs: stats.spearman([r["h"] for r in rs],
                                        [cv[r["uid"]] for r in rs]),
        n_boot=N_BOOT, seed=SEED)
    return {
        "n_groups": len(groups),
        "n_singletons": sum(1 for s in sizes if s == 1),
        "largest_group": max(sizes),
        "group_means": {str(k): round(v, 4) for k, v in sorted(means.items(),
                                                               key=lambda kv: str(kv[0]))},
        "rho_in_sample": stats.spearman(
            [r["h"] for r in rows], [means[key(r)] for r in rows]),
        "eta_upper_bound": eta_upper_bound(rows, key),
        "best_ordering": best_ordering(rows, key, seed=seed),
        "rho_cv": cv_ci["point"],
        "cv_lo": cv_ci["lo"], "cv_hi": cv_ci["hi"],
        "cv_excludes_zero": bool(cv_ci["lo"] > 0 or cv_ci["hi"] < 0),
        "rho_split_holdout": split_rho,
        "n_holdout_unseen_tuples": n_unseen,
        "rho_loo_BIASED": stats.spearman(
            [r["h"] for r in rows], [loo[r["uid"]] for r in rows]),
        "repeated_split": _repeated_split(rows, key, n_train, N_SPLITS, seed),
        "null_repeated_split": _repeated_split(rows, key, n_train, N_SPLITS,
                                               seed, shuffle_h=True),
        "null_cv": _null_band(rows, key,
                              lambda rs: _cv_predictions(rs, key, n_folds, seed),
                              n_shuffle, seed),
        "null_loo": _null_band(rows, key, lambda rs: _loo_predictions(rs, key),
                               n_shuffle, seed),
    }


# ------------------------------------------------------------------- the run

def analyse(rows, label="primary"):
    out = {"label": label, "n": len(rows)}

    # --- A1. Signed valence vs "took a position" -------------------------
    # The user's claim, made testable: if raters were tracking valence, the
    # signed value predicts h. If they were tracking commitment -- does this
    # person mean it -- then |valence| predicts h and the sign does not.
    a1 = {}
    for name, sig, mag, subset in (
        ("transcript", lambda r: r["vt"], lambda r: abs(r["vt"]), rows),
        ("vocal", lambda r: r["vv"], lambda r: abs(r["vv"]), rows),
        ("facial", lambda r: r["vf"], lambda r: abs(r["vf"]),
         [r for r in rows if r["vf"] is not None]),
    ):
        a1[name] = {
            "n": len(subset),
            "signed": rho_ci(subset, lambda r: r["h"], sig),
            "absolute": rho_ci(subset, lambda r: r["h"], mag),
            "absolute_minus_signed": paired(subset, mag, sig),
        }
    out["A1_signed_vs_absolute"] = a1

    # --- A2. Direction, among segments that took a position --------------
    committed = [r for r in rows if r["t_label"] in ("POSITIVE", "NEGATIVE")]
    pos = [r["h"] for r in committed if r["t_label"] == "POSITIVE"]
    neg = [r["h"] for r in committed if r["t_label"] == "NEGATIVE"]
    neu = [r["h"] for r in rows if r["t_label"] == "NEUTRAL"]
    out["A2_direction"] = {
        "n_positive": len(pos), "mean_h_positive": sum(pos) / len(pos),
        "n_negative": len(neg), "mean_h_negative": sum(neg) / len(neg),
        "n_neutral": len(neu), "mean_h_neutral": sum(neu) / len(neu),
        "p_positive_vs_negative": permutation_p([pos, neg]),
        "p_committed_vs_neutral": permutation_p([pos + neg, neu]),
        "mean_h_committed": sum(pos + neg) / len(pos + neg),
    }

    # --- A3. Does the controller detect the disagreement it was built for?
    out["A3_faithfulness"] = {
        "rho_c_vs_disagreement": rho_ci(rows, lambda r: r["c"], disagreement),
        "rho_c_raw_vs_disagreement": rho_ci(rows, lambda r: r["c_raw"], disagreement),
        "rho_c_vs_n_distinct": rho_ci(rows, lambda r: r["c"], n_distinct),
        "rho_h_vs_disagreement": rho_ci(rows, lambda r: r["h"], disagreement),
        "rho_h_vs_n_distinct": rho_ci(rows, lambda r: r["h"], n_distinct),
        "disagreement_distribution": dict(sorted(collections.Counter(
            round(disagreement(r), 4) for r in rows).items())),
    }

    # --- A4. The ceiling on any system reading only these channels -------
    out["A4_oracle"] = {
        "transcript": oracle(rows, lambda r: (r["t_label"],)),
        "transcript_vocal": oracle(rows, lambda r: (r["t_label"], r["v_label"])),
        "all_channels": oracle(rows, lambda r: (r["t_label"], r["v_label"],
                                                r["f_label"])),
        "disagreement_only": oracle(rows, lambda r: (round(disagreement(r), 4),)),
    }
    return out


def main() -> int:
    sample, items, dup_uids, per_rater = load()
    rows = build_rows(items, per_rater)
    if len(rows) != 119:
        print(f"WARNING: {len(rows)} scorable rows, P1 reported 119", file=sys.stderr)

    result = {
        "provenance": {
            "pre_registered": False,
            "amendment": "A6",
            "n_scorable": len(rows),
            "n_boot": N_BOOT,
            "seed": SEED,
            "valence_map": VALENCE,
            "facial_valence_map": FACIAL_VALENCE,
        },
        "primary": analyse(rows, "primary"),
    }

    # --- A5. Sensitivity: the one arbitrary mapping decision --------------
    alt = build_rows(items, per_rater, facial_map=FACIAL_VALENCE_ALT)
    result["A5_sensitivity_surprise_neutral"] = analyse(alt, "surprise=0")

    # Holdout, for comparability with P1/P3 which report it separately.
    hold = [r for r in rows if r["split"] == "holdout"]
    result["holdout"] = analyse(hold, "holdout")

    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.name}  ({len(rows)} segments, {len(hold)} holdout)")

    p = result["primary"]
    print("\n--- A1 signed vs absolute valence, against h ---")
    for name, d in p["A1_signed_vs_absolute"].items():
        print(f"  {name:11s} n={d['n']:3d}  signed {d['signed']['rho']:+.4f} "
              f"[{d['signed']['lo']:+.4f},{d['signed']['hi']:+.4f}]   "
              f"|val| {d['absolute']['rho']:+.4f} "
              f"[{d['absolute']['lo']:+.4f},{d['absolute']['hi']:+.4f}]   "
              f"diff {d['absolute_minus_signed']['point']:+.4f} "
              f"[{d['absolute_minus_signed']['lo']:+.4f},"
              f"{d['absolute_minus_signed']['hi']:+.4f}]")

    a2 = p["A2_direction"]
    print("\n--- A2 direction ---")
    print(f"  POSITIVE n={a2['n_positive']:3d} mean h={a2['mean_h_positive']:.4f}")
    print(f"  NEGATIVE n={a2['n_negative']:3d} mean h={a2['mean_h_negative']:.4f}")
    print(f"  NEUTRAL  n={a2['n_neutral']:3d} mean h={a2['mean_h_neutral']:.4f}")
    print(f"  POS vs NEG        p={a2['p_positive_vs_negative']:.4f}")
    print(f"  committed vs NEU  p={a2['p_committed_vs_neutral']:.4f}")

    a3 = p["A3_faithfulness"]
    print("\n--- A3 is the controller faithful to its own design? ---")
    for k in ("rho_c_vs_disagreement", "rho_c_raw_vs_disagreement",
              "rho_c_vs_n_distinct", "rho_h_vs_disagreement",
              "rho_h_vs_n_distinct"):
        d = a3[k]
        print(f"  {k:30s} {d['rho']:+.4f} [{d['lo']:+.4f},{d['hi']:+.4f}] "
              f"{'*' if d['excludes_zero'] else ''}")

    print("\n--- A4 ceiling on any function of the channel labels ---")
    for k, d in p["A4_oracle"].items():
        print(f"  {k:20s} groups={d['n_groups']:3d} sing={d['n_singletons']:3d}  "
              f"ETA {d['eta_upper_bound']:+.4f} >= best {d['best_ordering']['rho']:+.4f} "
              f"({d['best_ordering']['method']}) >= group-mean {d['rho_in_sample']:+.4f}")
        print(f"  {'':20s} "
              f"CV {d['rho_cv']:+.4f} [{d['cv_lo']:+.4f},{d['cv_hi']:+.4f}]"
              f"{'*' if d['cv_excludes_zero'] else ' '}  "
              f"split {d['rho_split_holdout']:+.4f}")
        rs, nrs = d["repeated_split"], d["null_repeated_split"]
        print(f"  {'':20s} SPLIT x{rs['n_splits']} mean {rs['mean']:+.4f} "
              f"[{rs['lo']:+.4f},{rs['hi']:+.4f}]  vs null {nrs['mean']:+.4f} "
              f"[{nrs['lo']:+.4f},{nrs['hi']:+.4f}]")
        print(f"  {'':20s} null(CV) {d['null_cv']['mean']:+.4f} "
              f"[{d['null_cv']['lo']:+.4f},{d['null_cv']['hi']:+.4f}]   "
              f"LOO {d['rho_loo_BIASED']:+.4f} vs null(LOO) "
              f"{d['null_loo']['mean']:+.4f} "
              f"[{d['null_loo']['lo']:+.4f},{d['null_loo']['hi']:+.4f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
