"""
verify_speaker_norm.py - re-derive every number in SPEAKER_NORM_RESULT.md.

Same contract as verify_ab.py and verify_claims.py: a figure that cannot be
re-derived is not evidence, and hand-copied numbers drift. Every claim in the
write-up and in the pre-registration's amendment is recomputed here from the raw
caches and compared against the value written in the document. A mismatch fails
loudly with both numbers.

Two classes of check are deliberately separated:

  * claims about the RESULT, read back from speaker_norm_results.json, which is
    what the document was written from;
  * claims re-derived FROM SCRATCH out of the caches and the ground truth, which
    is what catches a stale or hand-edited results file.

The second class is the one that matters. Both run.

    python research/vocal_bench/verify_speaker_norm.py
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(BENCH))

import ground_truth as GT      # noqa: E402
import speaker_norm as SN      # noqa: E402

_passed: list[str] = []
_failed: list[str] = []


def check(name: str, actual, expected, tol: float = 0.0) -> None:
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            ok = abs(float(actual) - float(expected)) <= tol
        except (TypeError, ValueError):
            ok = False
    else:
        ok = actual == expected
    (_passed if ok else _failed).append(
        name if ok else f"{name}: document says {expected!r}, data gives {actual!r}")


# ── fixtures ──────────────────────────────────────────────────────────────────

def _load():
    corpus = SN.load_corpus()
    arousal_of = {r["uid"]: r["arousal"] for r in corpus}
    sel = SN.load_labelled("selection", arousal_of)
    con = SN.load_labelled("confirmation", arousal_of)
    res = json.loads((BENCH / "speaker_norm_results.json").read_text())
    return corpus, sel, con, res


# ── §1 setup, and the two checks the harness itself had to pass ──────────────

def verify_setup(corpus, sel, con, res) -> None:
    check("§1 corpus segments", len(corpus), 1863)
    check("§1 usable readings", sum(1 for r in corpus if r["arousal"] is not None), 1860)
    check("§1 selection clips", len(sel), 100)
    check("§1 confirmation clips", len(con), 47)
    check("§1 speakers", len({r["speaker"] for r in sel + con}), 6)

    stats = SN.build_stats(corpus, "video_id")
    means = [s["mean"] for s in stats.values()]
    sds = [s["sd"] for s in stats.values()]
    check("§1 lowest video mean arousal", round(min(means), 4), 0.5182, tol=0.00005)
    check("§1 highest video mean arousal", round(max(means), 4), 0.6843, tol=0.00005)
    check("§1 median within-video sd", round(statistics.median(sds), 4), 0.0582, tol=0.00005)
    check("§1 spread as a multiple of sd",
          round((max(means) - min(means)) / statistics.median(sds), 2), 2.85, tol=0.005)
    check("§1 smallest video", min(s["n"] for s in stats.values()), 39)
    check("§1 largest video", max(s["n"] for s in stats.values()), 271)

    # Anchor: reproduce the published bench from the corpus cache, from scratch.
    ident = SN.Transformer("global", corpus)
    lo, hi, _ = SN.fit(sel, ident, SN.PUBLISHED_GRID)
    check("§1 anchor thresholds", (lo, hi), (0.40, 0.65))
    check("§1 anchor selection", sum(
        r["label"] == SN.apply_thresholds(r["arousal"], 0.40, 0.65) for r in sel), 60)
    check("§1 anchor confirmation", sum(
        r["label"] == SN.apply_thresholds(r["arousal"], 0.40, 0.65) for r in con), 23)

    # Monotonicity invariant, recomputed rather than read back.
    rhos = {rid: SN.within_video_rho(sel, SN.Transformer(rid, corpus))["mean"]
            for rid in SN.RULES}
    check("§1 invariant holds across all six rules", len(set(rhos.values())), 1)
    check("§1 invariant value", round(list(rhos.values())[0], 6), 0.211239, tol=0.0000005)

    check("§1 fallbacks never fired", sum(res["declared"]["fallbacks"].values()), 0)
    check("§1 MIN_GROUP_SEGMENTS", SN.MIN_GROUP_SEGMENTS, 8)
    check("§1 grid points per rule", SN.GRID_POINTS, 19)
    check("§1 every rule got the same grid size",
          {len(g) for g in res["declared"]["grids"].values()}, {19})


# ── §2 selection split ────────────────────────────────────────────────────────

SELECTION_DOC = {
    # rule:          (lo,       hi,      accuracy, wilson_lo, wilson_hi, rho,    range)
    "global":        (+0.4601, +0.6183,  60.0, 50.2, 69.1, +0.416,  2.4),
    "video_robust":  (-1.3175, +1.2098,  56.0, 46.2, 65.3, +0.246, 22.2),
    "video_z":       (-1.6683, +1.5806,  56.0, 46.2, 65.3, +0.241, 26.3),
    "video_center":  (-0.1033, +0.0489,  55.0, 45.2, 64.4, +0.240,  8.2),
    "video_rank":    (+0.0500, +0.8500,  55.0, 45.2, 64.4, +0.250, 12.2),
    "speaker_z":     (-1.6503, +1.0131,  55.0, 45.2, 64.4, +0.251, 12.2),
}


def verify_selection(corpus, sel, res) -> None:
    for rid, (lo, hi, acc, wlo, whi, rho, rng) in SELECTION_DOC.items():
        t = SN.Transformer(rid, corpus)
        f_lo, f_hi, _ = SN.fit(sel, t, t.grid(corpus))
        check(f"§2 {rid} lo", round(f_lo, 4), lo, tol=0.00005)
        check(f"§2 {rid} hi", round(f_hi, 4), hi, tol=0.00005)
        s = SN.score(sel, t, (f_lo, f_hi))
        check(f"§2 {rid} accuracy", s["accuracy"], acc, tol=0.05)
        check(f"§2 {rid} wilson lo", s["wilson95"][0], wlo, tol=0.05)
        check(f"§2 {rid} wilson hi", s["wilson95"][1], whi, tol=0.05)
        check(f"§2 {rid} rho", round(s["pooled_rho"], 3), rho, tol=0.0005)
        check(f"§2 {rid} speaker range", s["speaker_range"], rng, tol=0.05)

    check("§2 declared winner", res["declared"]["declared_winner"], "global")
    check("§2 winner is the deployed rule",
          res["declared"]["declared_winner_is_deployed_rule"], True)
    check("§2 winner is deployable", SN.RULES[res["declared"]["declared_winner"]][2], True)
    check("§2 global is the best deployable rule on selection",
          max((v[2], k) for k, v in SELECTION_DOC.items() if SN.RULES[k][2])[1], "global")


# ── §3 confirmation split ─────────────────────────────────────────────────────

CONFIRM_DOC = {
    # rule:         (correct, accuracy, wilson_lo, wilson_hi, floor_p, deployed_p, range)
    "global":       (25, 53.2, 39.2, 66.7, 0.0357, 0.6250, 39.4),
    "video_robust": (17, 36.2, 24.0, 50.5, 0.2188, 0.3075, 37.8),
    "video_z":      (16, 34.0, 22.2, 48.3, 0.4531, 0.2295, 37.8),
    "video_rank":   (16, 34.0, 22.2, 48.3, 0.5078, 0.1892, 20.5),
    "speaker_z":    (15, 31.9, 20.4, 46.2, 0.7539, 0.1338, 28.8),
    "video_center": (13, 27.7, 16.9, 41.8, 1.0000, 0.0309, 37.2),
}


def verify_confirmation(corpus, con, res) -> None:
    frozen = {r: tuple(v) for r, v in res["declared"]["fitted_thresholds"].items()}
    gold = [r["label"] for r in con]
    deployed_pred = [SN.apply_thresholds(r["arousal"], 0.40, 0.65) for r in con]

    check("§3 deployed accuracy", round(23 / 47 * 100, 1), 48.9, tol=0.05)
    check("§3 deployed vs floor p", round(SN.mcnemar_exact(
        gold, ["NEUTRAL"] * len(con), deployed_pred)["p_value"], 4), 0.0639, tol=0.00005)
    check("§3 always-NEUTRAL floor", sum(g == "NEUTRAL" for g in gold), 13)
    check("§3 oracle majority is POSITIVE",
          max(("POSITIVE", "NEUTRAL", "NEGATIVE"), key=lambda L: sum(g == L for g in gold)),
          "POSITIVE")
    check("§3 oracle majority correct", sum(g == "POSITIVE" for g in gold), 27)
    check("§3 oracle majority accuracy", round(27 / 47 * 100, 1), 57.4, tol=0.05)

    for rid, (corr, acc, wlo, whi, fp, dp, rng) in CONFIRM_DOC.items():
        s = SN.score(con, SN.Transformer(rid, corpus), frozen[rid])
        check(f"§3 {rid} correct", s["correct"], corr)
        check(f"§3 {rid} accuracy", s["accuracy"], acc, tol=0.05)
        check(f"§3 {rid} wilson lo", s["wilson95"][0], wlo, tol=0.05)
        check(f"§3 {rid} wilson hi", s["wilson95"][1], whi, tol=0.05)
        check(f"§3 {rid} vs floor p", round(s["vs_floor"]["p_value"], 4), fp, tol=0.00005)
        check(f"§3 {rid} vs deployed p", round(SN.mcnemar_exact(
            gold, deployed_pred, s["pred"])["p_value"], 4), dp, tol=0.00005)
        check(f"§3 {rid} speaker range", s["speaker_range"], rng, tol=0.05)

    # Every normalisation loses to the deployed rule, by 12.7 to 21.2 points.
    losses = sorted(round(48.9 - v[1], 1) for k, v in CONFIRM_DOC.items() if k != "global")
    check("§3 smallest loss to deployed", losses[0], 12.7, tol=0.05)
    check("§3 largest loss to deployed", losses[-1], 21.2, tol=0.05)
    check("§3 all normalisations lose", all(l > 0 for l in losses), True)
    check("§3 no rule beats the oracle majority",
          max(v[1] for v in CONFIRM_DOC.values()) < 57.4, True)

    t = SN.mcnemar_exact(gold, deployed_pred,
                         SN.score(con, SN.Transformer("global", corpus),
                                  frozen["global"])["pred"])
    check("§3 global vs deployed discordant", t["n_discordant"], 4)
    check("§3 global vs deployed min attainable p",
          round(t["min_attainable_p"], 4), 0.1250, tol=0.00005)
    check("§3 global beats deployed by 2 clips", 25 - 23, 2)

    a = res["adopt"]
    check("§3 adoption decision", a["decision"], "DO NOT ADOPT")
    check("§3 adoption not significant", a["significant_at_0.05"], False)
    check("§3 monotonicity invariant recorded", res["monotonicity_invariant"], "held")


# ── §4 the post-hoc explanation ───────────────────────────────────────────────

DIAG_DOC = {
    # split:        (clips, videos, pooled, within, wmin,   wmax,  video_level)
    "selection":    (100, 8, +0.415, +0.211, -0.149, +0.608, +0.762),
    "confirmation": (47,  4, +0.131, +0.056, -0.337, +0.471, +0.400),
    "pooled":       (147, 12, +0.386, +0.159, -0.337, +0.608, +0.790),
}

ETA_DOC = {
    # split:        (arousal|video, arousal|speaker, rating|video, rating|speaker)
    "selection":    (0.3741, 0.2664, 0.2105, 0.1757),
    "confirmation": (0.1446, 0.1446, 0.1020, 0.1020),
    "pooled":       (0.3907, 0.3283, 0.1911, 0.1702),
}

ORACLE_DOC = {"video_robust": 63.8, "video_rank": 63.8, "global": 61.7,
              "video_z": 61.7, "speaker_z": 61.7, "video_center": 57.4}

SPEAKER_DOC = {
    # speaker:            (mean arousal, global correct/n, video_z correct/n)
    "Dave2D":             (0.5982, (3, 11), (6, 11)),
    "Jeremy Fragrance":   (0.6812, (7, 12), (5, 12)),
    "ShortCircuit":       (0.5959, (8, 12), (3, 12)),
    "The Tech Chap":      (0.6843, (7, 12), (2, 12)),
}


def verify_diagnostics(corpus, sel, con, res) -> None:
    d = SN.phase_diagnose(corpus, sel, con)

    for split, (n, v, pooled, within, wmin, wmax, vlevel) in DIAG_DOC.items():
        s = d[split]
        check(f"§4.1 {split} clips", s["n_clips"], n)
        check(f"§4.1 {split} videos", s["n_videos"], v)
        check(f"§4.1 {split} pooled rho", round(s["pooled_rho"], 3), pooled, tol=0.0005)
        check(f"§4.1 {split} within-video rho",
              round(s["within_video_rho_mean"], 3), within, tol=0.0005)
        check(f"§4.1 {split} within min",
              round(s["within_video_rho_range"][0], 3), wmin, tol=0.0005)
        check(f"§4.1 {split} within max",
              round(s["within_video_rho_range"][1], 3), wmax, tol=0.0005)
        check(f"§4.1 {split} video-level rho",
              round(s["video_level_rho_arousal_vs_rating"], 3), vlevel, tol=0.0005)

    check("§4.1 within-video rho is less than half the pooled figure",
          d["pooled"]["within_video_rho_mean"] < d["pooled"]["pooled_rho"] / 2, True)

    for split, (av, asp, rv, rsp) in ETA_DOC.items():
        s = d[split]
        check(f"§4.2 {split} eta2 arousal|video",
              s["eta2_arousal_by_video"], av, tol=0.00005)
        check(f"§4.2 {split} eta2 arousal|speaker",
              s["eta2_arousal_by_speaker"], asp, tol=0.00005)
        check(f"§4.2 {split} eta2 rating|video",
              s["eta2_rating_by_video"], rv, tol=0.00005)
        check(f"§4.2 {split} eta2 rating|speaker",
              s["eta2_rating_by_speaker"], rsp, tol=0.00005)

    c = d["corpus"]
    check("§4.2 corpus segments used", c["n_segments"], 1860)
    check("§4.2 corpus eta2 arousal|video", c["eta2_arousal_by_video"], 0.3905, tol=0.00005)
    check("§4.2 corpus eta2 arousal|speaker",
          c["eta2_arousal_by_speaker"], 0.3266, tol=0.00005)
    check("§4.2 arousal is twice as video-determined as the rating",
          round(d["pooled"]["eta2_arousal_by_video"]
                / d["pooled"]["eta2_rating_by_video"], 2), 2.04, tol=0.005)

    o = d["oracle_thresholds_on_confirmation"]["by_rule"]
    for rid, best in ORACLE_DOC.items():
        check(f"§4.3 oracle {rid}", o[rid]["best_possible_accuracy"], best, tol=0.05)
    check("§4.3 normalisation ceiling above global's",
          round(max(o[r]["best_possible_accuracy"] for r in o if r != "global")
                - o["global"]["best_possible_accuracy"], 1), 2.1, tol=0.05)
    check("§4.3 best oracle over the majority class",
          round(max(v["best_possible_accuracy"] for v in o.values()) - 57.4, 1),
          6.4, tol=0.05)

    # §4.4 what the rules actually did
    frozen = {r: tuple(v) for r, v in res["declared"]["fitted_thresholds"].items()}
    g = SN.score(con, SN.Transformer("global", corpus), frozen["global"])
    z = SN.score(con, SN.Transformer("video_z", corpus), frozen["video_z"])
    check("§4.4 global predicts POSITIVE", g["pred"].count("POSITIVE"), 31)
    check("§4.4 global predicts NEGATIVE never", g["pred"].count("NEGATIVE"), 0)
    check("§4.4 video_z predicts NEUTRAL", z["pred"].count("NEUTRAL"), 39)

    vstats = SN.build_stats(corpus, "video_id")
    speaker_video = {r["speaker"]: r["video_id"] for r in con}
    for spk, (mean_a, (gc, gn), (zc, zn)) in SPEAKER_DOC.items():
        check(f"§4.4 {spk} mean arousal",
              round(vstats[speaker_video[spk]]["mean"], 4), mean_a, tol=0.00005)
        check(f"§4.4 {spk} global", (g["per_speaker"][spk]["correct"],
                                     g["per_speaker"][spk]["n"]), (gc, gn))
        check(f"§4.4 {spk} video_z", (z["per_speaker"][spk]["correct"],
                                      z["per_speaker"][spk]["n"]), (zc, zn))
    check("§4.4 each held-out speaker contributes one video",
          len(set(speaker_video.values())), 4)
    check("§4.4 video_rank pays for its narrower range",
          round(53.2 - CONFIRM_DOC["video_rank"][1], 1), 19.2, tol=0.05)


# ── §5 the correction to my own pre-registration ──────────────────────────────

VALENCE_S7 = {"Dave2D": 45.5, "Jeremy Fragrance": 41.7, "Marques Brownlee": 65.3,
              "Mrwhosetheboss": 43.1, "ShortCircuit": 16.7, "The Tech Chap": 41.7}
AROUSAL_DEPLOYED = {"Dave2D": (3, 11), "Jeremy Fragrance": (7, 12),
                    "Marques Brownlee": (32, 49), "Mrwhosetheboss": (28, 51),
                    "ShortCircuit": (6, 12), "The Tech Chap": (7, 12)}


def verify_correction(sel, con) -> None:
    """VOCAL_MODEL_ANALYSIS.md §7 is the valence reading; the deployed one is arousal."""
    import report_bench as RB

    au = json.loads((BENCH / "predictions" / "audeering-msp-dim.json").read_text())
    preds = au["predictions"]
    rows = GT.load("selection") + GT.load("confirmation")

    lo, hi, _ = RB.fit_thresholds(GT.load("selection"), preds)
    check("§5 valence thresholds", (lo, hi), (0.40, 0.80))

    v = defaultdict(lambda: [0, 0])
    for r in rows:
        p = RB.apply_thresholds(preds[r["uid"]]["valence"], lo, hi)
        v[r["channel"]][1] += 1
        v[r["channel"]][0] += (p == r["label"])
    for spk, expected in VALENCE_S7.items():
        c, n = v[spk]
        check(f"§5 valence reproduces §7 for {spk}", round(c / n * 100, 1),
              expected, tol=0.05)
    check("§5 valence pooled reproduces §7",
          round(sum(c for c, _ in v.values()) / sum(n for _, n in v.values()) * 100, 1),
          48.3, tol=0.05)

    a = defaultdict(lambda: [0, 0])
    for r in sel + con:
        p = SN.apply_thresholds(r["arousal"], 0.40, 0.65)
        a[r["speaker"]][1] += 1
        a[r["speaker"]][0] += (p == r["label"])
    accs = []
    for spk, (ec, en) in AROUSAL_DEPLOYED.items():
        c, n = a[spk]
        check(f"§5 deployed arousal for {spk}", (c, n), (ec, en))
        accs.append(c / n * 100)
    check("§5 deployed arousal pooled",
          round(sum(c for c, _ in a.values()) / sum(n for _, n in a.values()) * 100, 1),
          56.5, tol=0.05)
    check("§5 deployed arousal range", round(max(accs) - min(accs), 1), 38.0, tol=0.05)
    check("§5 the amended range differs from the pre-registered one",
          round(max(accs) - min(accs), 1) != 48.6, True)
    check("§5 the motivation survives the correction",
          round(max(accs) - min(accs), 1) > 30.0, True)

    # The amendment must actually be on file.
    prereg = (BENCH / "SPEAKER_NORM_PREREG.md").read_text()
    check("§5 amendment recorded in the pre-registration", "## Amendments" in prereg, True)
    check("§5 amendment states the corrected range", "38.0 points" in prereg, True)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    corpus, sel, con, res = _load()
    verify_setup(corpus, sel, con, res)
    verify_selection(corpus, sel, res)
    verify_confirmation(corpus, con, res)
    verify_diagnostics(corpus, sel, con, res)
    verify_correction(sel, con)

    print(f"verified   {len(_passed)}")
    print(f"FAILED     {len(_failed)}")
    for f in _failed:
        print(f"  FAIL  {f}")
    if not _failed:
        print("\nEvery claim in SPEAKER_NORM_RESULT.md re-derived from the raw data.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
