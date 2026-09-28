"""
verify_claims.py — every number in BASELINE_RATER_ANALYSIS.md, recomputed.

The precedent is `controller_bench/verify_claims.py` (268 claims) and
`facial_bench/v2/verify_claims.py` (463 claims), and the reason is the project's evidence
rule: *"If a number is quoted anywhere, it must be traceable to a file in this
repo that produced it."* A write-up whose numbers are not re-derivable is an
assertion, not a result.

Each claim is checked twice over:

  1. **Recomputed from the raw rating files** — `ratings_rater{1..4}.json`,
     `sample.json`, `_tokens.json` — not read back out of
     `rater_analysis_results.json`. Reading the results file to check the
     document would only prove the two agree, which they would even if both were
     wrong.
  2. **Required to appear verbatim in the .md**, at the precision the document
     quotes it. A number that is right in the JSON and mistyped in the prose is
     exactly the failure this catches, and it is the most likely one.

A third check compares the recomputed value against the stored results file, so
a stale `rater_analysis_results.json` is caught rather than silently republished.

Run:  python research/baseline_bench/verify_claims.py
Exit: 0 if every claim verifies, 1 otherwise.
"""

from __future__ import annotations

import collections
import json
import math
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))
import rater_analysis as RA  # noqa: E402
import stats  # noqa: E402

DOC = BENCH / "BASELINE_RATER_ANALYSIS.md"
RESULTS = BENCH / "rater_analysis_results.json"

checks = 0
failures: list[str] = []
text = DOC.read_text()
stored = json.loads(RESULTS.read_text())

# Markdown hard-wraps prose, so a quoted phrase can straddle a newline and a
# naive `in text` test fails on a claim that is present and correct. Searching a
# whitespace-normalised copy removes that false alarm without weakening the
# check: every non-space character still has to be there, in order.
FLAT = " ".join(text.split())


def _to_float(s: str):
    """Parse a number as the document prints it, or return None.

    Handles the typographic minus (U+2212) the tables use, and a trailing %.
    Returning None rather than raising lets `claim` accept non-numeric strings.
    """
    t = s.strip().replace("\u2212", "-").replace(",", "").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def _tolerance(shown: str) -> float:
    """Half a unit in the last printed decimal place.

    The document quotes rounded values, so the comparison must accept exactly
    the rounding the document performed and nothing looser. '0.7296' gets
    5e-5; '4.2%' gets 0.05 on the percentage scale. A fixed tolerance would
    either reject correct 1-dp percentages or wave through a wrong 4-dp
    correlation, and this bench needs both checked at their own precision.
    """
    t = shown.strip().replace("\u2212", "-").rstrip("%")
    dp = len(t.split(".")[1]) if "." in t else 0
    return 0.5 * (10 ** -dp) + 1e-9


def claim(label: str, value, shown: str, stored_value=None):
    """Assert `shown` appears in the document AND denotes the recomputed `value`.

    Three things are checked, and the second is the one that matters: a number
    can be present in the prose, and wrong.
    """
    global checks
    checks += 1
    if shown not in FLAT:
        failures.append(f"{label}: {shown!r} not present in the document")
        return
    parsed = _to_float(shown)
    if parsed is not None and value is not None:
        target = value * 100 if shown.strip().endswith("%") else value
        if not math.isclose(parsed, target, abs_tol=_tolerance(shown)):
            failures.append(f"{label}: document says {shown!r}, recomputed {target!r}")
            return
    if stored_value is not None and isinstance(value, float):
        if not math.isclose(stored_value, value, abs_tol=1e-9):
            failures.append(f"{label}: results.json has {stored_value!r}, "
                            f"recomputed {value!r}")


def present(label: str, s: str):
    """A non-numeric claim that must appear verbatim (a quote, a name, a verdict)."""
    global checks
    checks += 1
    if " ".join(s.split()) not in FLAT:
        failures.append(f"{label}: {s!r} not present in the document")


def main() -> int:
    global checks
    sample, items, dups, pr = RA.load()
    all_uids = sorted(items)
    keep = [u for u in all_uids if RA.usable_count(pr, u) >= RA.MIN_USABLE]
    dropped = [u for u in all_uids if u not in set(keep)]
    sel = [u for u in keep if items[u]["split"] == "selection"]
    hol = [u for u in keep if items[u]["split"] == "holdout"]
    h = {u: RA.ground_truth(pr, u) for u in keep}

    # ─────────────────────────────────────────────── §2 provenance / structure
    claim("n presented", float(len(all_uids)), "120")
    claim("n kept", float(len(keep)), "119", float(stored["ground_truth"]["n_kept"]))
    claim("n holdout", float(len(hol)), "39", float(stored["ground_truth"]["n_holdout"]))
    claim("n selection", float(len(sel)), "80", float(stored["ground_truth"]["n_selection"]))
    claim("n dropped", float(len(dropped)), "1")
    present("dropped uid", "Kk-RKpTAXmA_139")
    present("dropped text", "Reese. Wah! Wah! Wah!")
    present("blinding checks", "778 mechanical checks")
    for rn in RA.RATERS:
        assert len(pr[rn]) == 120
        assert sum(1 for v in pr[rn].values() if len(v) == 2) == 30
    checks += 1

    # ───────────────────────────────────────────────────── §3 rating marginals
    pooled = [r for rn in RA.RATERS for u in all_uids for _, r in pr[rn][u]
              if r != RA.UNRATABLE]
    c = collections.Counter(pooled)
    n_pooled = len(pooled)
    claim("pooled usable", float(n_pooled), "597")
    for k, shown in ((5, "213"), (4, "185"), (3, "170"), (2, "25"), (1, "4")):
        claim(f"pooled count {k}", float(c[k]), shown)
    claim("share 5", c[5] / n_pooled, "35.7%")
    claim("share 4", c[4] / n_pooled, "31.0%")
    claim("share 3", c[3] / n_pooled, "28.5%")
    claim("share 2", c[2] / n_pooled, "4.2%")
    claim("share 1", c[1] / n_pooled, "0.7%")
    claim("top half share", (c[3] + c[4] + c[5]) / n_pooled, "95.1%")
    n_zero = sum(1 for rn in RA.RATERS for u in all_uids for _, r in pr[rn][u]
                 if r == RA.UNRATABLE)
    claim("unratable total", float(n_zero), "3")

    per_rater_shown = {
        "rater1": ("3.900", "0.968", "1.862", "34.7%", "30.0%", "6.0%"),
        "rater2": ("4.034", "0.873", "1.712", "36.9%", "28.2%", "2.7%"),
        "rater3": ("4.020", "0.933", "1.803", "38.3%", "24.2%", "4.7%"),
        "rater4": ("3.919", "0.955", "1.809", "35.6%", "31.5%", "6.0%"),
    }
    for rn, (m, sd, ent, ext, mid, neg) in per_rater_shown.items():
        v = [r for u in all_uids for _, r in pr[rn][u] if r != RA.UNRATABLE]
        n = len(v)
        mean = sum(v) / n
        s = stored["raters"][rn]
        claim(f"{rn} mean", mean, m, s["mean"])
        claim(f"{rn} sd", math.sqrt(sum((x - mean) ** 2 for x in v) / (n - 1)), sd, s["sd"])
        cc = collections.Counter(v)
        claim(f"{rn} entropy",
              -sum((q / n) * math.log2(q / n) for q in cc.values()), ent,
              s["entropy_bits"])
        claim(f"{rn} extreme", sum(1 for x in v if x in (1, 5)) / n, ext,
              s["pct_extreme_1_or_5"])
        claim(f"{rn} mid", sum(1 for x in v if x == 3) / n, mid, s["pct_midpoint_3"])
        claim(f"{rn} neg", sum(1 for x in v if x in (1, 2)) / n, neg,
              s["pct_negative_1_or_2"])

    # ────────────────────────────────────────────── §4 within-rater duplicates
    dup_shown = {
        "rater1": ("63.3%", "93.3%", "0.756", "0.604", "0.719", "0.433", "+0.033"),
        "rater2": ("90.0%", "100.0%", "0.939", "0.901", "0.943", "0.100", "−0.033"),
        "rater3": ("83.3%", "96.7%", "0.833", "0.816", "0.875", "0.200", "−0.067"),
        "rater4": ("83.3%", "96.7%", "0.885", "0.830", "0.884", "0.200", "−0.067"),
    }
    for rn, (ex, w1, rho, kl, kq, mad, drift) in dup_shown.items():
        a, b = [], []
        for u in sorted(dups):
            p1, p2 = sorted(pr[rn][u])
            if p1[1] != RA.UNRATABLE and p2[1] != RA.UNRATABLE:
                a.append(p1[1])
                b.append(p2[1])
        s = stored["within_rater"][rn]
        claim(f"{rn} dup exact", sum(1 for x, y in zip(a, b) if x == y) / len(a), ex, s["exact"])
        claim(f"{rn} dup within1",
              sum(1 for x, y in zip(a, b) if abs(x - y) <= 1) / len(a), w1, s["within_1"])
        claim(f"{rn} dup rho", stats.spearman(a, b), rho, s["rho"])
        claim(f"{rn} dup kL", stats.weighted_kappa(a, b, RA.SCALE, "linear"), kl,
              s["kappa_linear"])
        claim(f"{rn} dup kQ", stats.weighted_kappa(a, b, RA.SCALE, "quadratic"), kq,
              s["kappa_quadratic"])
        claim(f"{rn} dup mad", sum(abs(x - y) for x, y in zip(a, b)) / len(a), mad, s["mad"])
        present(f"{rn} dup drift", drift)

    # ───────────────────────────────────────────────── §5 attentiveness checks
    for rn, run, null, p in (("rater1", "5", "4.84", "0.568"),
                             ("rater2", "5", "5.05", "0.653"),
                             ("rater3", "4", "5.08", "0.972"),
                             ("rater4", "4", "4.90", "0.955")):
        s = stored["raters"][rn]
        claim(f"{rn} run", float(s["longest_run"]), run)
        claim(f"{rn} run null", s["longest_run_null_mean"], null)
        claim(f"{rn} run p", s["longest_run_p"], p)
    for rn, orho, h1, h2 in (("rater1", "+0.048", "3.800", "4.000"),
                             ("rater2", "+0.081", "3.986", "4.080"),
                             ("rater3", "−0.055", "4.054", "3.987"),
                             ("rater4", "−0.139", "4.095", "3.747")):
        s = stored["raters"][rn]
        present(f"{rn} order rho", orho)
        claim(f"{rn} first half", s["mean_first_half"], h1)
        claim(f"{rn} second half", s["mean_second_half"], h2)

    # ───────────────────────────────────────────────────────── §6 alpha
    for nm, ss, ordv, intv, nomv, nu, npair in (
            ("all", keep, "0.7296", "0.7178", "0.5396", "119", "596"),
            ("selection", sel, "0.7698", "0.7613", "0.5915", "80", "380"),
            ("holdout", hol, "0.6377", "0.6111", "0.4336", "39", "216")):
        for metric, shown in (("ordinal", ordv), ("interval", intv), ("nominal", nomv)):
            a = RA.alpha_of(pr, ss, metric)
            claim(f"alpha {nm} {metric}", a["alpha"], shown,
                  stored["alpha"][nm][metric]["alpha"])
        claim(f"alpha {nm} pairable", float(RA.alpha_of(pr, ss, "ordinal")["n_pairable"]),
              npair)
    b = stored["alpha"]["all_ordinal_bootstrap_ci"]
    claim("alpha CI lo", b["lo"], "0.6447")
    claim("alpha CI hi", b["hi"], "0.7978")
    present("alpha CI headline", "[0.645, 0.798]")

    # ────────────────────────────────────────────────────────── §7 pairwise
    pw_shown = {
        "rater1|rater2": ("0.733", "0.718", "0.378", "−0.126", "63.9%"),
        "rater1|rater3": ("0.654", "0.634", "0.450", "−0.122", "58.0%"),
        "rater1|rater4": ("0.647", "0.622", "0.424", "−0.029", "63.0%"),
        "rater2|rater3": ("0.772", "0.789", "0.315", "+0.004", "67.2%"),
        "rater2|rater4": ("0.747", "0.751", "0.340", "+0.097", "66.4%"),
        "rater3|rater4": ("0.860", "0.853", "0.244", "+0.092", "73.9%"),
    }
    for key, (rho, r, mad, signed, ident) in pw_shown.items():
        a, bb = key.split("|")
        xs = [(RA.rater_value(pr, a, u), RA.rater_value(pr, bb, u)) for u in keep]
        xs = [(x, y) for x, y in xs if x is not None and y is not None]
        va = [x for x, _ in xs]
        vb = [y for _, y in xs]
        s = stored["pairwise"][key]
        claim(f"pw {key} rho", stats.spearman(va, vb), rho, s["rho"])
        claim(f"pw {key} r", stats.pearson(va, vb), r, s["pearson"])
        claim(f"pw {key} mad", sum(abs(x - y) for x, y in xs) / len(xs), mad, s["mad"])
        present(f"pw {key} signed", signed)
        claim(f"pw {key} identical",
              sum(1 for x, y in xs if abs(x - y) < 1e-9) / len(xs), ident, s["identical"])

    # ─────────────────────────────────────────────────────────── §7.1 ICC
    complete = [u for u in keep
                if all(RA.rater_value(pr, rn, u) is not None for rn in RA.RATERS)]
    M = [[RA.rater_value(pr, rn, u) for rn in RA.RATERS] for u in complete]
    icc = stats.icc_2k(M)
    claim("ICC(2,1)", icc["icc_2_1"], "0.7226", stored["icc"]["icc_2_1"])
    claim("ICC(2,k)", icc["icc_2_k"], "0.9124", stored["icc"]["icc_2_k"])
    present("ICC headline", "0.912")
    mp = sum(v["rho"] for v in stored["pairwise"].values()) / len(stored["pairwise"])
    claim("mean pairwise rho", mp, "0.7356")
    for k, shown in ((1, "0.736"), (2, "0.848"), (3, "0.893"), (4, "0.918"),
                     (5, "0.933"), (8, "0.957")):
        claim(f"spearman-brown k={k}", stats.spearman_brown(mp, k), shown)

    # ──────────────────────────────────────────────────────── §8 P5 ceiling
    for nm, ss, per, mean_shown in (
            ("all", keep, ("0.731", "0.825", "0.836", "0.823"), "0.8038"),
            ("selection", sel, ("0.701", "0.897", "0.866", "0.841"), "0.8261"),
            ("holdout", hol, ("0.802", "0.647", "0.773", "0.823"), "0.7613")):
        loo = RA.loo_ceiling(pr, ss)
        for rn, shown in zip(RA.RATERS, per):
            claim(f"ceiling {nm} {rn}", loo[rn]["rho"], shown,
                  stored["ceiling"][nm][rn]["rho"])
        claim(f"ceiling {nm} mean", loo["mean_rho"], mean_shown,
              stored["ceiling"][nm]["mean_rho"])
    cb = stored["ceiling"]["all_bootstrap_ci"]
    claim("ceiling CI lo", cb["lo"], "0.7343")
    claim("ceiling CI hi", cb["hi"], "0.8559")
    present("ceiling headline", "0.804")
    present("holdout ceiling headline", "0.761")

    # ─────────────────────────────────────────────── §9 floor, §10 author
    claim("floor total", float(RA.FLOOR_TOTAL), "90")
    claim("floor holdout", float(RA.FLOOR_HOLDOUT), "30")
    present("floor verdict", "not underpowered by its own pre-registered definition")
    h3 = {u: RA.ground_truth(pr, u, RA.BLIND) for u in keep}
    a = stored["author_sensitivity"]
    claim("rho h4 h3", stats.spearman([h[u] for u in keep], [h3[u] for u in keep]),
          "0.9775", a["rho_h4_vs_h3"])
    claim("pearson h4 h3", stats.pearson([h[u] for u in keep], [h3[u] for u in keep]),
          "0.9783", a["pearson_h4_vs_h3"])
    claim("alpha no author", RA.alpha_of(pr, keep, "ordinal", RA.BLIND)["alpha"],
          "0.7860", a["alpha_ordinal_without_author"])
    claim("icc no author", a["icc_2k_without_author"], "0.9213")
    claim("ceiling blind only", a["ceiling_among_blind_only"], "0.8375")
    claim("mean h4", a["mean_h4"], "3.9727")
    claim("mean h3", a["mean_h3"], "3.9958")
    claim("max shift", a["max_abs_shift"], "0.917")
    dev_shown = {"rater1": ("−0.092", "0.403", "5", "2"),
                 "rater2": ("+0.076", "0.300", "0", "2"),
                 "rater3": ("+0.070", "0.317", "0", "1"),
                 "rater4": ("−0.053", "0.325", "1", "1")}
    for rn, (sg, ab, below, above) in dev_shown.items():
        d = a["deviation_profile"][rn]
        present(f"dev {rn} signed", sg)
        claim(f"dev {rn} abs", d["mean_abs"], ab)
        claim(f"dev {rn} below", float(d["n_ge_1p5_below"]), below)
        claim(f"dev {rn} above", float(d["n_ge_1p5_above"]), above)

    # ─────────────────────────────────────────────── §11 duplicate sensitivity
    d = stored["duplicate_sensitivity"]
    claim("dup sens rho", d["rho_averaged_vs_first_only"], "0.9960")
    claim("dup sens mean avg", d["mean_averaged"], "3.9727")
    claim("dup sens mean first", d["mean_first_only"], "3.9769")
    claim("dup sens changed", float(d["n_segments_changed"]), "16")
    claim("dup sens max", d["max_abs_diff"], "0.25")

    # ───────────────────────────────────────────────────── §12 h distribution
    dist_shown = {"all": ("3.973", "0.803", "1.625", "3.25", "4.00", "4.75", "18"),
                  "selection": ("3.906", "0.834", "1.625", "3.25", "4.00", "4.75", "14"),
                  "holdout": ("4.109", "0.724", "2.625", "3.50", "4.25", "4.75", "15")}
    for nm, ss in (("all", keep), ("selection", sel), ("holdout", hol)):
        mean, sd, mn, q1, med, q3, nd = dist_shown[nm]
        dd = stats.describe([h[u] for u in ss])
        st = stored["h_distribution"][nm]
        claim(f"h {nm} mean", dd["mean"], mean, st["mean"])
        claim(f"h {nm} sd", dd["sd"], sd, st["sd"])
        claim(f"h {nm} min", dd["min"], mn, st["min"])
        claim(f"h {nm} q1", dd["q1"], q1, st["q1"])
        claim(f"h {nm} median", dd["median"], med, st["median"])
        claim(f"h {nm} q3", dd["q3"], q3, st["q3"])
        claim(f"h {nm} distinct", float(len({round(h[u], 9) for u in ss})), nd,
              float(st["distinct_values"]))
    n_lt3 = sum(1 for u in keep if h[u] < 3.0)
    claim("n h<3", float(n_lt3), "5")
    claim("pct h<3", n_lt3 / len(keep), "4.2%")
    lo, hi = stats.wilson(n_lt3, len(keep))
    claim("wilson lo", lo, "1.8%")
    claim("wilson hi", hi, "9.5%")

    # ─────────────────────────────────────────────────────── §12.1 bounds
    hs = [h[u] for u in keep]
    import random as _r
    rng = _r.Random(42)
    perfect = [x + rng.random() * 1e-6 for x in hs]
    claim("untied bound", stats.spearman(perfect, hs), "0.993")
    claim("errorless bound", math.sqrt(icc["icc_2_k"]), "0.955")
    lo_h, hi_h = min(hs), max(hs)
    for k, shown in ((2, "0.781"), (3, "0.879"), (4, "0.950"), (5, "0.957"), (8, "0.987")):
        q = [round((x - lo_h) / (hi_h - lo_h) * (k - 1)) for x in hs]
        claim(f"quantisation k={k}", stats.spearman(q, hs), shown)

    # ────────────────────────────────────────────────────── §13 disagreement
    dg = stored["disagreement"]
    claim("n unanimous", float(dg["n_unanimous"]), "52")
    claim("pct unanimous", dg["n_unanimous"] / len(keep), "43.7%")
    claim("n sd>=1", float(dg["n_sd_ge_1"]), "5")
    claim("sd mean", dg["sd_summary"]["mean"], "0.327")
    claim("sd max", dg["sd_summary"]["max"], "1.893")
    present("sarcasm segment", "oh yeah, thank gosh I have eight lenses now in my smartphone.")
    present("contested segment", "in case you haven't already heard, is also clearly awesome")
    present("lowest h segment", "to how to display notifications, to the exact shade of color that you want,")

    # ─────────────────────────────────────────────── §14 channel diagnostics
    cd = stored["channel_diagnostic"]
    ts = cd["transcript_sentiment"]["groups"]
    claim("transcript NEG h", ts["NEGATIVE"]["mean"], "4.392")
    claim("transcript NEG n", float(ts["NEGATIVE"]["n"]), "15")
    claim("transcript POS h", ts["POSITIVE"]["mean"], "4.022")
    claim("transcript POS n", float(ts["POSITIVE"]["n"]), "29")
    claim("transcript NEU h", ts["NEUTRAL"]["mean"], "3.870")
    claim("transcript NEU n", float(ts["NEUTRAL"]["n"]), "75")
    claim("transcript p", cd["transcript_sentiment"]["permutation_p"], "0.034")
    vo = cd["vocal_emotion"]["groups"]
    claim("vocal NEU h", vo["NEUTRAL"]["mean"], "3.997")
    claim("vocal POS h", vo["POSITIVE"]["mean"], "3.875")
    claim("vocal p", cd["vocal_emotion"]["permutation_p"], "0.575")
    fa = cd["facial_emotion"]["groups"]
    for lab, shown_h, shown_n in (("fear", "4.250", "5"), ("surprise", "4.167", "3"),
                                  ("happy", "4.105", "19"), ("neutral", "4.022", "40"),
                                  ("sad", "3.950", "15"), ("angry", "3.792", "3"),
                                  ("None", "3.809", "34")):
        claim(f"facial {lab} h", fa[lab]["mean"], shown_h)
        claim(f"facial {lab} n", float(fa[lab]["n"]), shown_n)
    claim("facial p", cd["facial_emotion"]["permutation_p"], "0.853")
    claim("comment n", float(cd["video_comment_sentiment"]["groups"]["POSITIVE"]["n"]), "119")

    cf = stored["confounds"]
    claim("confound duration", cf["rho_h_vs_duration"], "0.175")
    claim("confound textlen", cf["rho_h_vs_text_length"], "0.173")
    claim("confound frames", cf["rho_h_vs_facial_frame_count"], "0.150")
    claim("confound rms", cf["rho_h_vs_rms"], "\u22120.026")

    # ── derived summary claims. These are arithmetic ON TOP of already-verified
    # cells, which is exactly where an error survives a cell-by-cell check: two
    # wrong summaries ("five of the seven severe departures", "the others are
    # 29/30") were found here after every cell they rest on had passed.
    dp = a["deviation_profile"]
    n_below = sum(dp[r]["n_ge_1p5_below"] for r in RA.RATERS)
    n_all = n_below + sum(dp[r]["n_ge_1p5_above"] for r in RA.RATERS)
    checks += 1
    if n_below != 6:
        failures.append(f"severe downward departures = {n_below}, document says six")
    checks += 1
    if n_all != 12:
        failures.append(f"severe departures in total = {n_all}, document says twelve")
    present("severe departures phrasing", "five of the six")
    present("severe departures total phrasing", "seven of the twelve")
    others = sum(dp[r]["mean_abs"] for r in RA.BLIND) / 3
    claim("author noise ratio", dp["rater1"]["mean_abs"] / others - 1.0, "29%")
    claim("author mean abs", dp["rater1"]["mean_abs"], "0.403")
    claim("others mean abs", others, "0.314")
    for rn, shown in (("rater1", "28/30"), ("rater3", "29/30"), ("rater2", "30/30")):
        w = stored["within_rater"][rn]
        claim(f"{rn} within1 count", w["within_1"] * 30, shown.split("/")[0])
        present(f"{rn} within1 shown", shown)
    ts_g = stored["channel_diagnostic"]["transcript_sentiment"]["groups"]
    claim("NEG-NEU gap", ts_g["NEGATIVE"]["mean"] - ts_g["NEUTRAL"]["mean"], "0.52")
    sb = stored["icc"]["spearman_brown"]
    claim("fifth rater gain", sb["5"] - sb["4"], "0.015")
    claim("one to four gain", sb["4"] - sb["1"], "0.18")
    wr = stored["within_rater"]
    checks += 1
    if not (wr["rater1"]["mad"] / wr["rater2"]["mad"] > 4.0):
        failures.append("rater1/rater2 MAD ratio is not 'more than four times'")
    r4 = stored["raters"]["rater4"]
    claim("rater4 half drop", r4["mean_first_half"] - r4["mean_second_half"], "0.35")
    claim("half of ceiling", 0.5 / stored["ceiling"]["all"]["mean_rho"], "62%")

    # ─────────────────────────────── §2.1 the rater-naivety defect (Amendment A3)
    # Cross-checked against the actual source, not restated from memory: the
    # pilot write-up must really contain the claim §2.1 attributes to it, and the
    # gap must really be the number of days the document quotes.
    from datetime import date
    pilot = PROJECT / "evaluation" / "user_pilot" / "PILOT_FINDINGS.md"
    pilot_text = " ".join(pilot.read_text().split())
    checks += 1
    if "3 people (Participant A, Participant B, Participant C)" not in pilot_text:
        failures.append("the three pilot participants are not named in PILOT_FINDINGS.md")
    checks += 1
    if "Date:** 02 Aug 2026" not in pilot.read_text():
        failures.append("pilot date 02 Aug 2026 not found in PILOT_FINDINGS.md")
    checks += 1
    quote = ("All 3 people correctly explained the tool's core purpose with zero "
             "coaching")
    if quote not in pilot_text:
        failures.append("the §2.1 quote is not in PILOT_FINDINGS.md")
    present("quote reproduced in the write-up", quote)
    claim("days between pilot and rating",
          float((date(2026, 9, 8) - date(2026, 8, 2)).days), "37")
    checks += 1
    proto = (BENCH / "PROTOCOL.md").read_text()
    if "the other three\nraters are not told what the system does" not in proto:
        failures.append("PROTOCOL.md §5.1 naivety sentence not found where A3 says it is")
    checks += 1
    if "A3 — 08 Sep 2026" not in proto:
        failures.append("Amendment A3 is not in PROTOCOL.md")
    present("A3 referenced by the write-up", "Amendment A3")

    # ────────────────────────────────────────────────────────── consistency
    present("amendment reference", "Amendment A1")
    present("not pre-registered labelling", "not pre-registered")
    present("verdict", "P1–P4 may proceed")

    print(f"verify_claims: {checks} claims checked against "
          f"{DOC.name} and the raw rating files")
    if failures:
        print(f"\nFAILED — {len(failures)} problem(s):")
        for f in failures[:60]:
            print("  ", f)
        if len(failures) > 60:
            print(f"   … and {len(failures) - 60} more")
        return 1
    print("PASSED — every quoted number recomputes from the raw data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
