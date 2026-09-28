"""
rater_analysis.py — the human ground truth, and how much it can be trusted.

This is the instrument-validation half of `baseline_bench`. It runs before any
system is scored and it is deliberately separable from them, because it answers a
question that has to be settled first:

    Is the ground truth this bench is about to judge five systems against
    good enough to judge anything?

If it is not — if the raters disagree at chance, or if every clip is rated the
same — then P1-P4 cannot produce an interpretable number and running them would
manufacture a result rather than measure one. PROTOCOL.md §9.5 anticipates
exactly that failure and requires it to be reported as the finding.

What is computed here, all pre-registered in PROTOCOL.md §6 unless marked:

  §5.4  ground truth h(s), and the segments dropped for too few usable ratings
  §8.3  the power floor, checked rather than assumed
  P5    the human ceiling, leave-one-rater-out
  P6    Krippendorff's alpha, and within-rater consistency on the 30 duplicates
  §8.4  the author-bias sensitivity check
  §8.5  duplicates-averaged vs first-presentation-only

  and, NOT pre-registered and labelled as such wherever quoted:
  ICC(2,k), response-style profiling, order/fatigue effects, a straight-lining
  test against a permutation null, and the diagnostic association between h(s)
  and each pipeline channel's label.

The diagnostic in that last group needs a word of justification, because it looks
like peeking at the answer. It is not, and the reason is structural: every system
in PROTOCOL.md §3 is fully specified in advance with no free parameter — same
model, same temperature, same seed, same prompt — so there is nothing left for a
look at the data to tune. The one exception is `transcript_label`, whose
label -> score mapping the protocol never fixed. That gap is reported here as a
gap and is NOT closed using these numbers; closing it that way would be fitting
on the test set. See BASELINE_RATER_ANALYSIS.md §15.

Run:  python research/baseline_bench/rater_analysis.py
Out:  baseline_bench/rater_analysis_results.json  (every number the write-up quotes)
"""

from __future__ import annotations

import collections
import json
import math
import random
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import stats  # noqa: E402

RATERS = ["rater1", "rater2", "rater3", "rater4"]
AUTHOR = "rater1"          # PROTOCOL.md §5.1 — rated first, and not blind
BLIND = ["rater2", "rater3", "rater4"]
SCALE = [1, 2, 3, 4, 5]    # 0 is "unratable" and is excluded, never treated as 0
UNRATABLE = 0
N_BOOT = 10000
SEED = 42
MIN_USABLE = 3             # PROTOCOL.md §5.4
FLOOR_TOTAL = 90           # PROTOCOL.md §8.3
FLOOR_HOLDOUT = 30


# ------------------------------------------------------------------- loading

def load():
    """Load ratings, resolve tokens to segments, and refuse to proceed on any
    integrity failure.

    The assertions are not defensive padding. Each one has a specific way of
    being false that would silently corrupt every number downstream: a rater
    sent the file from someone else's page, a page was rebuilt after being
    distributed, a token collided, an export was hand-edited. A wrong answer
    that looks right is the worst outcome available here, so this fails loudly
    instead.
    """
    tokens = json.loads((BENCH / "_tokens.json").read_text())["token_to_uid"]
    sample = json.loads((BENCH / "sample.json").read_text())
    items = {it["uid"]: it for it in sample["items"]}
    dup_uids = set(sample["duplicate_uids"])

    per_rater = {}
    for i, rn in enumerate(RATERS, start=1):
        path = BENCH / f"ratings_{rn}.json"
        doc = json.loads(path.read_text())
        assert doc["rater"] == rn, f"{path.name} declares rater {doc['rater']!r}"
        assert doc["n"] == sample["n_presentations_per_rater"], "wrong item count"
        assert doc["complete"] is True, f"{rn} did not finish"
        assert len(doc["answers"]) == doc["n"], "answers do not match n"

        # The file must match the page that rater was actually given. This is
        # the check that catches two people rating the same page.
        page = (BENCH / "pages" / f"rate_{rn}.html").read_text()
        marker = "window.__ITEMS__="
        start = page.index(marker) + len(marker)
        payload = json.loads(page[start:page.index(";</script>", start)])
        assert [(x["pid"], x["tok"]) for x in payload] == \
               [(a["pid"], a["tok"]) for a in doc["answers"]], \
               f"{rn}: ratings file does not match {rn}'s own page"

        by_uid = collections.defaultdict(list)
        for pos, a in enumerate(doc["answers"]):
            assert a["rating"] in SCALE + [UNRATABLE], f"{rn}: bad rating"
            by_uid[tokens[a["tok"]]].append((pos, a["rating"]))
        assert len(by_uid) == len(items), f"{rn}: not every segment was presented"
        repeats = {u for u, v in by_uid.items() if len(v) == 2}
        assert repeats == dup_uids, f"{rn}: duplicate set does not match sample.json"
        per_rater[rn] = dict(by_uid)

    return sample, items, dup_uids, per_rater


# ------------------------------------------------------- ratings -> quantities

def rater_value(per_rater, rn, uid):
    """One rater's value for a segment: the mean of their usable ratings for it.

    A segment presented twice to the same rater yields two ratings, and this
    averages them. Averaging first, per rater, rather than pooling all eight
    ratings of a duplicated segment, keeps every rater weighted equally — pooling
    would let a duplicated segment count a rater twice against a rater who
    marked one presentation unratable. §8.5 reports the alternative.
    """
    vals = [r for _, r in per_rater[rn][uid] if r != UNRATABLE]
    return sum(vals) / len(vals) if vals else None


def usable_count(per_rater, uid, raters=RATERS):
    """How many RATERS gave this segment at least one usable rating (§5.4)."""
    return sum(1 for rn in raters if rater_value(per_rater, rn, uid) is not None)


def ground_truth(per_rater, uid, raters=RATERS):
    """h(s): the mean over raters of each rater's value (PROTOCOL.md §5.4)."""
    vals = [rater_value(per_rater, rn, uid) for rn in raters]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def ground_truth_first_only(per_rater, uid, raters=RATERS):
    """§8.5 sensitivity: use only each rater's FIRST sight of the segment."""
    vals = []
    for rn in raters:
        pres = sorted(per_rater[rn][uid])
        if pres and pres[0][1] != UNRATABLE:
            vals.append(pres[0][1])
    return sum(vals) / len(vals) if vals else None


# ------------------------------------------------------------------- helpers

def alpha_of(per_rater, uids, metric="ordinal", raters=RATERS):
    """Krippendorff's alpha over a set of segments.

    Every usable rating is a separate value for its segment, so a duplicated
    segment contributes up to eight. That is the correct unit for alpha: it
    measures agreement between *observations*, and a rater's second look is a
    genuine second observation.
    """
    units = [[r for rn in raters for _, r in per_rater[rn][u] if r != UNRATABLE]
             for u in uids]
    return stats.krippendorff_alpha(units, metric=metric, categories=SCALE)


def loo_ceiling(per_rater, uids, raters=RATERS):
    """P5: each rater against the mean of the others, then averaged.

    This is the right form of the ceiling and a subtly different quantity from
    'agreement between raters'. It asks what a *system* would score if it were as
    good as a person, because a system is also scored against a mean of humans.
    Comparing a system's rho to a pairwise human rho instead would hold the
    system to a stricter standard than any individual human meets.
    """
    out = {}
    for rn in raters:
        others = [o for o in raters if o != rn]
        x, y = [], []
        for u in uids:
            me = rater_value(per_rater, rn, u)
            ot = [rater_value(per_rater, o, u) for o in others]
            ot = [v for v in ot if v is not None]
            if me is not None and ot:
                x.append(me)
                y.append(sum(ot) / len(ot))
        out[rn] = {"rho": stats.spearman(x, y), "pearson": stats.pearson(x, y),
                   "n": len(x)}
    out["mean_rho"] = sum(out[r]["rho"] for r in raters) / len(raters)
    return out


def permutation_p(groups, n_perm=20000, seed=SEED):
    """Rank-based permutation test that several groups share one distribution.

    Used for the channel diagnostics. Rank-based and mapping-free on purpose:
    it asks whether the label carries ANY information about human judgement,
    without first assuming which label ought to mean 'genuine'. Assuming the
    direction is exactly the mistake §11 of the write-up is about.
    """
    allv = [v for g in groups for v in g]
    rk = stats.ranks(allv)
    sizes = [len(g) for g in groups]

    def stat(rr):
        i, ms = 0, []
        for s in sizes:
            ms.append(sum(rr[i:i + s]) / s)
            i += s
        gm = sum(rr) / len(rr)
        return sum(s * (m - gm) ** 2 for s, m in zip(sizes, ms))

    obs = stat(rk)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        sh = rk[:]
        rng.shuffle(sh)
        if stat(sh) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)   # add-one: never reports p = 0


def longest_run(seq):
    best = cur = 1
    for x, y in zip(seq, seq[1:]):
        cur = cur + 1 if y == x else 1
        best = max(best, cur)
    return best


def main() -> int:
    sample, items, dup_uids, per_rater = load()
    R = {"protocol": "baseline_bench/PROTOCOL.md", "seed": SEED, "n_boot": N_BOOT}
    all_uids = sorted(items)

    # ---------------------------------------------------------- §5.4 + §8.3
    dropped = [u for u in all_uids if usable_count(per_rater, u) < MIN_USABLE]
    keep = [u for u in all_uids if u not in set(dropped)]
    sel = [u for u in keep if items[u]["split"] == "selection"]
    hol = [u for u in keep if items[u]["split"] == "holdout"]
    R["ground_truth"] = {
        "n_presented": len(all_uids),
        "n_dropped": len(dropped),
        "dropped": [{"uid": u, "text": items[u]["text"],
                     "channel": items[u]["channel"], "split": items[u]["split"],
                     "usable_raters": usable_count(per_rater, u),
                     "per_rater": {rn: [r for _, r in per_rater[rn][u]]
                                   for rn in RATERS}} for u in dropped],
        "n_kept": len(keep), "n_selection": len(sel), "n_holdout": len(hol),
    }
    R["power_floor"] = {
        "floor_total": FLOOR_TOTAL, "floor_holdout": FLOOR_HOLDOUT,
        "kept": len(keep), "holdout": len(hol),
        "total_met": len(keep) >= FLOOR_TOTAL,
        "holdout_met": len(hol) >= FLOOR_HOLDOUT,
        "underpowered": not (len(keep) >= FLOOR_TOTAL and len(hol) >= FLOOR_HOLDOUT),
    }

    h = {u: ground_truth(per_rater, u) for u in keep}
    for nm, ss in (("all", keep), ("selection", sel), ("holdout", hol)):
        d = stats.describe([h[u] for u in ss])
        d["distinct_values"] = len({round(h[u], 9) for u in ss})
        R.setdefault("h_distribution", {})[nm] = d

    # -------------------------------------------------- per-rater description
    R["raters"] = {}
    for rn in RATERS:
        seq = [r for u in all_uids for _, r in sorted(per_rater[rn][u])]
        # rebuild presentation order for order-effects
        flat = sorted((pos, r) for u in all_uids for pos, r in per_rater[rn][u])
        pos_u = [p for p, r in flat if r != UNRATABLE]
        val_u = [r for p, r in flat if r != UNRATABLE]
        counts = collections.Counter(r for _, r in flat)
        n_us = len(val_u)
        mean = sum(val_u) / n_us
        sd = math.sqrt(sum((x - mean) ** 2 for x in val_u) / (n_us - 1))
        ent = -sum((c / n_us) * math.log2(c / n_us)
                   for k, c in counts.items() if k != UNRATABLE and c)
        obs_run = longest_run([r for _, r in flat])
        rng = random.Random(SEED)
        pool = [r for _, r in flat]
        sims = []
        for _ in range(N_BOOT):
            sh = pool[:]
            rng.shuffle(sh)
            sims.append(longest_run(sh))
        h1 = [v for p, v in zip(pos_u, val_u) if p < 75]
        h2 = [v for p, v in zip(pos_u, val_u) if p >= 75]
        R["raters"][rn] = {
            "counts": {str(k): counts.get(k, 0) for k in [UNRATABLE] + SCALE},
            "n_unratable": counts.get(UNRATABLE, 0), "n_usable": n_us,
            "mean": mean, "sd": sd, "entropy_bits": ent,
            "pct_extreme_1_or_5": sum(1 for v in val_u if v in (1, 5)) / n_us,
            "pct_midpoint_3": sum(1 for v in val_u if v == 3) / n_us,
            "pct_negative_1_or_2": sum(1 for v in val_u if v in (1, 2)) / n_us,
            "order_rho": stats.spearman(pos_u, val_u),
            "mean_first_half": sum(h1) / len(h1), "mean_second_half": sum(h2) / len(h2),
            "longest_run": obs_run,
            "longest_run_null_mean": sum(sims) / len(sims),
            "longest_run_p": sum(1 for s in sims if s >= obs_run) / len(sims),
        }

    # -------------------------------------------- P6a: duplicate consistency
    R["within_rater"] = {}
    dups = sorted(dup_uids)
    for rn in RATERS:
        a, b, signed = [], [], []
        for u in dups:
            pres = sorted(per_rater[rn][u])
            r1, r2 = pres[0][1], pres[1][1]
            if r1 == UNRATABLE or r2 == UNRATABLE:
                continue
            a.append(r1)
            b.append(r2)
            signed.append(r2 - r1)
        R["within_rater"][rn] = {
            "n_pairs": len(a),
            "exact": sum(1 for x, y in zip(a, b) if x == y) / len(a),
            "within_1": sum(1 for x, y in zip(a, b) if abs(x - y) <= 1) / len(a),
            "rho": stats.spearman(a, b),
            "kappa_linear": stats.weighted_kappa(a, b, SCALE, "linear"),
            "kappa_quadratic": stats.weighted_kappa(a, b, SCALE, "quadratic"),
            "mad": sum(abs(x - y) for x, y in zip(a, b)) / len(a),
            "mean_signed_second_minus_first": sum(signed) / len(signed),
        }

    # ------------------------------------------------ P6b: between-rater alpha
    R["alpha"] = {}
    for nm, ss in (("all", keep), ("selection", sel), ("holdout", hol)):
        R["alpha"][nm] = {m: alpha_of(per_rater, ss, m) for m in
                          ("ordinal", "interval", "nominal")}
    boot_alpha = stats.bootstrap_ci(
        keep, lambda us: alpha_of(per_rater, us, "ordinal")["alpha"],
        n_boot=N_BOOT, seed=SEED)
    boot_alpha.pop("dist")
    R["alpha"]["all_ordinal_bootstrap_ci"] = boot_alpha

    R["pairwise"] = {}
    for i, a in enumerate(RATERS):
        for bb in RATERS[i + 1:]:
            xs = [(rater_value(per_rater, a, u), rater_value(per_rater, bb, u))
                  for u in keep]
            xs = [(x, y) for x, y in xs if x is not None and y is not None]
            va = [x for x, _ in xs]
            vb = [y for _, y in xs]
            R["pairwise"][f"{a}|{bb}"] = {
                "n": len(xs), "rho": stats.spearman(va, vb),
                "pearson": stats.pearson(va, vb),
                "mad": sum(abs(x - y) for x, y in xs) / len(xs),
                "mean_signed": sum(x - y for x, y in xs) / len(xs),
                "identical": sum(1 for x, y in xs if abs(x - y) < 1e-9) / len(xs),
            }

    # ----------------------------------------------------------- P5 + ICC
    R["ceiling"] = {}
    for nm, ss in (("all", keep), ("selection", sel), ("holdout", hol)):
        R["ceiling"][nm] = loo_ceiling(per_rater, ss)
    boot_ceil = stats.bootstrap_ci(
        keep, lambda us: loo_ceiling(per_rater, us)["mean_rho"],
        n_boot=1000, seed=SEED)          # 1000: this statistic is 4 rho's per draw
    boot_ceil.pop("dist")
    R["ceiling"]["all_bootstrap_ci"] = boot_ceil

    complete = [u for u in keep
                if all(rater_value(per_rater, rn, u) is not None for rn in RATERS)]
    M = [[rater_value(per_rater, rn, u) for rn in RATERS] for u in complete]
    R["icc"] = {"note": "NOT pre-registered; supplementary", **stats.icc_2k(M)}
    mean_pair = sum(v["rho"] for v in R["pairwise"].values()) / len(R["pairwise"])
    R["icc"]["mean_pairwise_rho"] = mean_pair
    R["icc"]["spearman_brown"] = {str(k): stats.spearman_brown(mean_pair, k)
                                  for k in (1, 2, 3, 4, 5, 6, 8, 10)}

    # -------------------------------------------------- §8.4 author sensitivity
    h3 = {u: ground_truth(per_rater, u, BLIND) for u in keep}
    both = [u for u in keep if h3[u] is not None]
    R["author_sensitivity"] = {
        "rho_h4_vs_h3": stats.spearman([h[u] for u in both], [h3[u] for u in both]),
        "pearson_h4_vs_h3": stats.pearson([h[u] for u in both], [h3[u] for u in both]),
        "mean_h4": sum(h[u] for u in both) / len(both),
        "mean_h3": sum(h3[u] for u in both) / len(both),
        "max_abs_shift": max(abs(h[u] - h3[u]) for u in both),
        "alpha_ordinal_without_author":
            alpha_of(per_rater, keep, "ordinal", BLIND)["alpha"],
        "alpha_ordinal_with_author": R["alpha"]["all"]["ordinal"]["alpha"],
        "icc_2k_without_author": stats.icc_2k(
            [[rater_value(per_rater, rn, u) for rn in BLIND] for u in keep
             if all(rater_value(per_rater, rn, u) is not None for rn in BLIND)]
        )["icc_2_k"],
        "ceiling_among_blind_only": loo_ceiling(per_rater, keep, BLIND)["mean_rho"],
    }
    dev = {}
    for rn in RATERS:
        others = [o for o in RATERS if o != rn]
        ds = []
        for u in keep:
            me = rater_value(per_rater, rn, u)
            ot = [rater_value(per_rater, o, u) for o in others]
            ot = [v for v in ot if v is not None]
            if me is not None and ot:
                ds.append(me - sum(ot) / len(ot))
        dev[rn] = {"mean_signed": sum(ds) / len(ds),
                   "mean_abs": sum(abs(x) for x in ds) / len(ds),
                   "n_ge_1p5_below": sum(1 for x in ds if x <= -1.5),
                   "n_ge_1p5_above": sum(1 for x in ds if x >= 1.5)}
    R["author_sensitivity"]["deviation_profile"] = dev

    # ----------------------------------------------------------- §8.5 duplicates
    hf = {u: ground_truth_first_only(per_rater, u) for u in keep}
    ok = [u for u in keep if hf[u] is not None]
    R["duplicate_sensitivity"] = {
        "rho_averaged_vs_first_only":
            stats.spearman([h[u] for u in ok], [hf[u] for u in ok]),
        "mean_averaged": sum(h[u] for u in ok) / len(ok),
        "mean_first_only": sum(hf[u] for u in ok) / len(ok),
        "max_abs_diff": max(abs(h[u] - hf[u]) for u in ok),
        "n_segments_changed": sum(1 for u in ok if abs(h[u] - hf[u]) > 1e-9),
    }

    # ------------------------------------------------------- disagreement map
    spread = []
    for u in keep:
        v = [rater_value(per_rater, rn, u) for rn in RATERS]
        v = [x for x in v if x is not None]
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
        spread.append({"uid": u, "sd": sd, "h": m,
                       "ratings": {rn: rater_value(per_rater, rn, u) for rn in RATERS},
                       "text": items[u]["text"], "channel": items[u]["channel"],
                       "split": items[u]["split"], "duration": items[u]["duration"],
                       "transcript": items[u]["transcript_sentiment"],
                       "vocal": items[u]["vocal_emotion"],
                       "facial": items[u]["facial_emotion"]})
    spread.sort(key=lambda d: -d["sd"])
    R["disagreement"] = {
        "sd_summary": stats.describe([s["sd"] for s in spread]),
        "n_unanimous": sum(1 for s in spread if s["sd"] == 0),
        "n_sd_ge_1": sum(1 for s in spread if s["sd"] >= 1.0),
        "most_contested": spread[:10],
        "lowest_h": sorted(spread, key=lambda d: d["h"])[:10],
        "highest_h": sorted(spread, key=lambda d: -d["h"])[:5],
    }

    # ------------------------------------------------------------ per video
    byv = collections.defaultdict(list)
    for u in keep:
        byv[items[u]["video_id"]].append(u)
    R["per_video"] = {}
    for v, us in byv.items():
        d = stats.describe([h[u] for u in us])
        R["per_video"][v] = {
            "channel": items[us[0]]["channel"], "split": items[us[0]]["split"],
            "n": len(us), "h_mean": d["mean"], "h_sd": d["sd"],
            "alpha_ordinal": alpha_of(per_rater, us, "ordinal")["alpha"],
        }

    # ------------------------------------------------------- channel diagnostic
    R["channel_diagnostic"] = {"note": "NOT pre-registered; direction not assumed"}
    for field in ("transcript_sentiment", "vocal_emotion", "facial_emotion",
                  "video_comment_sentiment"):
        byl = collections.defaultdict(list)
        for u in keep:
            byl[str(items[u][field])].append(h[u])
        groups = {L: stats.describe(v) for L, v in byl.items()}
        gs = [v for v in byl.values() if len(v) >= 2]
        R["channel_diagnostic"][field] = {
            "groups": groups,
            "n_labels": len(byl),
            "permutation_p": permutation_p(gs) if len(gs) >= 2 else None,
        }
    R["confounds"] = {}
    for field in ("duration", "rms", "facial_frame_count"):
        R["confounds"][f"rho_h_vs_{field}"] = stats.spearman(
            [items[u][field] for u in keep], [h[u] for u in keep])
    R["confounds"]["rho_h_vs_text_length"] = stats.spearman(
        [len(items[u]["text"]) for u in keep], [h[u] for u in keep])

    out = BENCH / "rater_analysis_results.json"
    out.write_text(json.dumps(R, indent=1, sort_keys=False, default=float))
    print(f"wrote {out.name}")
    print(f"  kept {len(keep)}/{len(all_uids)} segments "
          f"({len(sel)} selection, {len(hol)} holdout)")
    print(f"  alpha_ordinal = {R['alpha']['all']['ordinal']['alpha']:.4f}")
    print(f"  human ceiling = {R['ceiling']['all']['mean_rho']:.4f}")
    print(f"  ICC(2,k)      = {R['icc']['icc_2_k']:.4f}")
    print(f"  underpowered  = {R['power_floor']['underpowered']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
