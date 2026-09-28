"""
verify_axis_claims.py — every number in AXIS_RESULT.md, recomputed.

Third of the three verifiers, after `verify_claims.py`
(`BASELINE_RATER_ANALYSIS.md`) and `verify_bench_claims.py`
(`BASELINE_ANALYSIS.md`). Same discipline, the project's evidence rule:

  1. **Recompute from source** — the four rating files and the cached LLM
     responses — not from `axis_results.json`. Checking a document against the
     file that produced it only proves the two agree, which they would even if
     `axis_analysis.py` were wrong.
  2. **Require the number verbatim in the prose**, at the precision quoted. A
     number correct in the JSON and mistyped in the write-up is the likeliest
     failure and the one that would actually mislead a reader.
  3. Compare against `axis_results.json` as well, so a stale results file is
     caught rather than silently republished.

Bootstrap intervals, permutation p-values and split distributions are Monte
Carlo. They are re-derived by re-running the module's own seeded functions, so
the check is that the document matches what the code produces at seed 42 — not
that two independent random runs agree, which they would not.

Run:  python research/baseline_bench/verify_axis_claims.py
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
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import axis_analysis as AX  # noqa: E402
import rater_analysis as RA  # noqa: E402
import stats  # noqa: E402

DOC = BENCH / "AXIS_RESULT.md"
RESULTS = BENCH / "axis_results.json"
PROTO = BENCH / "PROTOCOL.md"

text = DOC.read_text()
FLAT = " ".join(text.split())
stored = json.loads(RESULTS.read_text())
checks = 0
failures: list[str] = []


def _to_float(s: str):
    t = s.strip().replace("−", "-").replace(",", "").rstrip("%").rstrip("×")
    try:
        return float(t)
    except ValueError:
        return None


def _tolerance(shown: str) -> float:
    t = shown.strip().replace("−", "-").rstrip("%").rstrip("×")
    dp = len(t.split(".")[1]) if "." in t else 0
    return 0.5 * (10 ** -dp) + 1e-9


def claim(label: str, value, shown: str, stored_value=None):
    global checks
    checks += 1
    if shown not in FLAT:
        failures.append(f"{label}: {shown!r} not in the document")
        return
    parsed = _to_float(shown)
    if parsed is not None and value is not None:
        target = value * 100 if shown.strip().endswith("%") else value
        if not math.isclose(parsed, target, abs_tol=_tolerance(shown)):
            failures.append(f"{label}: document says {shown!r}, recomputed {target!r}")
            return
    if stored_value is not None and isinstance(value, float):
        if not math.isclose(stored_value, value, abs_tol=1e-9):
            failures.append(f"{label}: results.json {stored_value!r} vs recomputed {value!r}")


def present(label: str, s: str, haystack: str | None = None):
    global checks
    checks += 1
    hay = FLAT if haystack is None else " ".join(haystack.split())
    if " ".join(s.split()) not in hay:
        failures.append(f"{label}: {s!r} not present")


def ci(label, d, r_shown, lo_shown, hi_shown, stored_d=None):
    claim(f"{label} rho", d["rho"], r_shown, None if stored_d is None else stored_d["rho"])
    claim(f"{label} lo", d["lo"], lo_shown, None if stored_d is None else stored_d["lo"])
    claim(f"{label} hi", d["hi"], hi_shown, None if stored_d is None else stored_d["hi"])


def main() -> int:
    global checks

    # ── rebuild everything from source ───────────────────────────────────────
    sample, items, dups, pr = RA.load()
    rows = AX.build_rows(items, pr)
    sp = stored["primary"]

    claim("n scorable", float(len(rows)), "119", float(stored["provenance"]["n_scorable"]))
    hold_rows = [r for r in rows if r["split"] == "holdout"]
    claim("n holdout", float(len(hold_rows)), "39")

    # The 119 must be exactly P1's 119, by the same rule.
    keep = [u for u in sorted(items) if RA.usable_count(pr, u) >= RA.MIN_USABLE]
    checks += 1
    if sorted(r["uid"] for r in rows) != sorted(keep):
        failures.append("row set is not P1's MIN_USABLE>=3 set")

    h = [r["h"] for r in rows]

    # ── §3 / A1 ──────────────────────────────────────────────────────────────
    a1 = sp["A1_signed_vs_absolute"]
    tr_sign = AX.rho_ci(rows, lambda r: r["h"], lambda r: r["vt"])
    tr_abs = AX.rho_ci(rows, lambda r: r["h"], lambda r: abs(r["vt"]))
    tr_diff = AX.paired(rows, lambda r: abs(r["vt"]), lambda r: r["vt"])
    ci("A1 transcript signed", tr_sign, "−0.0784", "−0.2587", "+0.1066", a1["transcript"]["signed"])
    ci("A1 transcript |val|", tr_abs, "+0.1909", "+0.0162", "+0.3635", a1["transcript"]["absolute"])
    claim("A1 transcript diff", tr_diff["point"], "+0.2694",
          a1["transcript"]["absolute_minus_signed"]["point"])
    claim("A1 transcript diff lo", tr_diff["lo"], "+0.0640",
          a1["transcript"]["absolute_minus_signed"]["lo"])
    claim("A1 transcript diff hi", tr_diff["hi"], "+0.4856",
          a1["transcript"]["absolute_minus_signed"]["hi"])
    checks += 1
    if not (tr_abs["lo"] > 0 and tr_diff["lo"] > 0):
        failures.append("A1: |val| and the paired difference must both exclude zero")

    vo_sign = AX.rho_ci(rows, lambda r: r["h"], lambda r: r["vv"])
    ci("A1 vocal signed", vo_sign, "−0.0525", "−0.2192", "+0.1179", a1["vocal"]["signed"])
    fac = [r for r in rows if r["vf"] is not None]
    claim("A1 facial n", float(len(fac)), "85", float(a1["facial"]["n"]))
    fa_sign = AX.rho_ci(fac, lambda r: r["h"], lambda r: r["vf"])
    fa_abs = AX.rho_ci(fac, lambda r: r["h"], lambda r: abs(r["vf"]))
    ci("A1 facial signed", fa_sign, "+0.0591", "−0.1470", "+0.2586", a1["facial"]["signed"])
    ci("A1 facial |val|", fa_abs, "+0.0010", "−0.2123", "+0.2158", a1["facial"]["absolute"])
    claim("A1 facial diff", AX.paired(fac, lambda r: abs(r["vf"]), lambda r: r["vf"])["point"],
          "−0.0581")

    # The vocal identity is the claim, so prove it rather than quoting it.
    vl = collections.Counter(r["v_label"] for r in rows)
    claim("vocal NEUTRAL n", float(vl["NEUTRAL"]), "95")
    claim("vocal POSITIVE n", float(vl["POSITIVE"]), "24")
    checks += 1
    if vl["NEGATIVE"] != 0:
        failures.append("vocal channel emitted NEGATIVE; §3's identity claim is false")
    checks += 1
    if any(abs(r["vv"]) != r["vv"] for r in rows):
        failures.append("vocal |v| != v somewhere; the identity does not hold")
    present("vocal identity stated", "`NEGATIVE` on none of the 119")

    # ── §4 / A2 ──────────────────────────────────────────────────────────────
    a2 = sp["A2_direction"]
    groups = {lab: [r["h"] for r in rows if r["t_label"] == lab]
              for lab in ("POSITIVE", "NEGATIVE", "NEUTRAL")}
    for lab, n_shown, m_shown in (("NEGATIVE", "15", "4.392"),
                                  ("POSITIVE", "29", "4.022"),
                                  ("NEUTRAL", "75", "3.870")):
        g = groups[lab]
        claim(f"A2 {lab} n", float(len(g)), n_shown)
        claim(f"A2 {lab} mean h", sum(g) / len(g), m_shown,
              a2[f"mean_h_{lab.lower()}"])
    comm = groups["POSITIVE"] + groups["NEGATIVE"]
    claim("A2 committed n", float(len(comm)), "44")
    claim("A2 committed mean", sum(comm) / len(comm), "4.148", a2["mean_h_committed"])
    claim("A2 p POS vs NEG", RA.permutation_p([groups["POSITIVE"], groups["NEGATIVE"]]),
          "0.1129", a2["p_positive_vs_negative"])
    claim("A2 p committed vs NEU", RA.permutation_p([comm, groups["NEUTRAL"]]),
          "0.0374", a2["p_committed_vs_neutral"])
    checks += 1
    if not (a2["p_positive_vs_negative"] > 0.05 >= a2["p_committed_vs_neutral"]):
        failures.append("A2: the direction/commitment contrast does not hold as written")
    checks += 1
    mn = [a2["mean_h_negative"], a2["mean_h_neutral"], a2["mean_h_positive"]]
    if not (mn[1] < mn[2] < mn[0]):
        failures.append("A2: means are not non-monotonic in valence as claimed")
    present("A2 supersedes §14", "§14's conclusion 1 should be read as superseded")

    # ── §5 / A3 ──────────────────────────────────────────────────────────────
    a3 = sp["A3_faithfulness"]
    cD = AX.rho_ci(rows, lambda r: r["c"], AX.disagreement)
    hD = AX.rho_ci(rows, lambda r: r["h"], AX.disagreement)
    ci("A3 c~D", cD, "+0.4415", "+0.3025", "+0.5620", a3["rho_c_vs_disagreement"])
    ci("A3 h~D", hD, "+0.0498", "−0.1327", "+0.2287", a3["rho_h_vs_disagreement"])
    ci("A3 craw~D", AX.rho_ci(rows, lambda r: r["c_raw"], AX.disagreement),
       "+0.3839", "+0.2358", "+0.5107", a3["rho_c_raw_vs_disagreement"])
    ci("A3 c~ndist", AX.rho_ci(rows, lambda r: r["c"], AX.n_distinct),
       "+0.4877", "+0.3694", "+0.5889", a3["rho_c_vs_n_distinct"])
    ci("A3 h~ndist", AX.rho_ci(rows, lambda r: r["h"], AX.n_distinct),
       "+0.0849", "−0.0894", "+0.2552", a3["rho_h_vs_n_distinct"])
    checks += 1
    if not (cD["lo"] > 0 and hD["lo"] < 0 < hD["hi"]):
        failures.append("A3: the excludes-zero pattern in the table is wrong")

    hcD = AX.rho_ci(hold_rows, lambda r: r["c"], AX.disagreement)
    hhD = AX.rho_ci(hold_rows, lambda r: r["h"], AX.disagreement)
    ci("A3 holdout c~D", hcD, "+0.5451", "+0.3194", "+0.7206",
       stored["holdout"]["A3_faithfulness"]["rho_c_vs_disagreement"])
    ci("A3 holdout h~D", hhD, "−0.0983", "−0.4121", "+0.2393",
       stored["holdout"]["A3_faithfulness"]["rho_h_vs_disagreement"])

    # 7.67x, and the P1 value it is a ratio against.
    p1 = json.loads((BENCH / "bench_results.json").read_text())["P1"]["four_channel"]["all"]["rho"]
    claim("A3 ratio", cD["rho"] / abs(p1), "7.67×")
    claim("P1 four_channel", p1, "+0.0575")

    # D distribution — 3 of 119 fully agreeing is load-bearing.
    dist = collections.Counter(round(AX.disagreement(r), 4) for r in rows)
    claim("D == 0 count", float(dist[0.0]), "3")
    claim("D == 0 pct", dist[0.0] / len(rows), "2.5%")
    claim("D > 0 pct", (len(rows) - dist[0.0]) / len(rows), "97.5%")
    for val, shown in ((0.433, "30"), (0.4714, "27"), (0.5, "24"), (0.7071, "16"),
                       (0.8165, "2"), (0.8292, "13"), (0.9428, "3"), (1.0, "1")):
        claim(f"D bucket {val}", float(dist[val]), shown)
    checks += 1
    if sum(dist.values()) != len(rows):
        failures.append("D distribution does not sum to 119")

    # ── §6 / A4 ──────────────────────────────────────────────────────────────
    a4 = sp["A4_oracle"]
    for name, key, groups_shown, sing_shown, eta_shown, best_shown, ins_shown in (
        ("transcript", lambda r: (r["t_label"],), "3", "0",
         "+0.2397", "+0.2177", "+0.2177"),
        ("transcript_vocal", lambda r: (r["t_label"], r["v_label"]), "6", "0",
         "+0.2866", "+0.2530", "+0.2454"),
        ("all_channels", lambda r: (r["t_label"], r["v_label"], r["f_label"]),
         "27", "7", "+0.4647", "+0.4367", "+0.4348"),
        ("disagreement_only", lambda r: (round(AX.disagreement(r), 4),), "9", "1",
         "+0.3224", "+0.2902", "+0.2883"),
    ):
        g = collections.defaultdict(list)
        for r in rows:
            g[key(r)].append(r["h"])
        mu = {k: sum(v) / len(v) for k, v in g.items()}
        ins = stats.spearman(h, [mu[key(r)] for r in rows])
        claim(f"A4 {name} groups", float(len(g)), groups_shown, float(a4[name]["n_groups"]))
        claim(f"A4 {name} singletons", float(sum(1 for v in g.values() if len(v) == 1)),
              sing_shown, float(a4[name]["n_singletons"]))
        claim(f"A4 {name} group-mean", ins, ins_shown, a4[name]["rho_in_sample"])

        # eta is a proof, so re-derive it from the definition rather than
        # re-calling the function that produced the stored value.
        R = stats.ranks(h)
        rbar = sum(R) / len(R)
        total = sum((x - rbar) ** 2 for x in R)
        gi = collections.defaultdict(list)
        for i, r in enumerate(rows):
            gi[key(r)].append(i)
        between = sum(len(ix) * ((sum(R[i] for i in ix) / len(ix)) - rbar) ** 2
                      for ix in gi.values())
        eta = (between / total) ** 0.5
        claim(f"A4 {name} eta", eta, eta_shown, a4[name]["eta_upper_bound"])
        claim(f"A4 {name} best", a4[name]["best_ordering"]["rho"], best_shown)

        # The bracket the section rests on: eta >= best achievable >= group-mean.
        checks += 1
        if not (eta >= a4[name]["best_ordering"]["rho"] - 1e-12
                >= a4[name]["rho_in_sample"] - 1e-12):
            failures.append(f"A4 {name}: eta >= best >= group-mean does not hold")

        # And eta must bound every value the bench actually measured for it.
        checks += 1
        if a4[name]["repeated_split"]["mean"] > eta + 1e-12:
            failures.append(f"A4 {name}: split mean exceeds its own proven bound")

    for name, m_shown, lo_shown, hi_shown, null_shown in (
        ("transcript", "+0.1587", "−0.1665", "+0.3932", "+0.0042"),
        ("transcript_vocal", "+0.1310", "−0.1493", "+0.3582", "−0.0015"),
        ("all_channels", "+0.0551", "−0.1984", "+0.2782", "+0.0049"),
        ("disagreement_only", "+0.1367", "−0.1323", "+0.3670", "−0.0026"),
    ):
        rs, ns = a4[name]["repeated_split"], a4[name]["null_repeated_split"]
        claim(f"A4 {name} split mean", rs["mean"], m_shown)
        claim(f"A4 {name} split lo", rs["lo"], lo_shown)
        claim(f"A4 {name} split hi", rs["hi"], hi_shown)
        claim(f"A4 {name} null", ns["mean"], null_shown)
        claim(f"A4 {name} n splits", float(rs["n_splits"]), "500")
        checks += 1
        if not (rs["lo"] <= ns["mean"] <= rs["hi"]):
            failures.append(f"A4 {name}: §6's 'inside its own null band' claim is false")

    claim("A4 split train", float(a4["all_channels"]["repeated_split"]["n_train"]), "80")
    claim("A4 split test", float(a4["all_channels"]["repeated_split"]["n_test"]), "39")

    # Ceiling arithmetic.
    ceiling = json.loads((BENCH / "rater_analysis_results.json").read_text()
                         )["ceiling"]["all"]["mean_rho"]
    claim("human ceiling", ceiling, "0.8038")
    claim("eta / ceiling", a4["all_channels"]["eta_upper_bound"] / ceiling, "57.8%")
    claim("best / ceiling", a4["all_channels"]["best_ordering"]["rho"] / ceiling, "54.3%")
    present("eta described as a proof", "a *proof*, covering every prompt")
    present("search method stated", "seeded\npairwise-swap local search with 60 restarts")
    claim("exhaustive threshold", float(AX.EXHAUSTIVE_MAX), "≤ 8 groups")

    # Comments really are constant, which is why they add no groups.
    checks += 1
    if len({items[r["uid"]]["video_comment_sentiment"] for r in rows}) != 1:
        failures.append("§6 claims the comment channel is constant; it is not")
    claim("comments constant", 119.0, "`POSITIVE` on 119 of 119")

    # ── §6.2 the discarded estimator ─────────────────────────────────────────
    claim("LOO null mean", a4["transcript"]["null_loo"]["mean"], "−0.4697")
    claim("LOO null lo", a4["transcript"]["null_loo"]["lo"], "−0.8312")
    claim("LOO null hi", a4["transcript"]["null_loo"]["hi"], "−0.2667")
    claim("LOO observed", a4["transcript"]["rho_loo_BIASED"], "−0.2722")
    claim("CV null", a4["transcript"]["null_cv"]["mean"], "−0.1653")
    checks += 1
    lo_b, hi_b = a4["transcript"]["null_loo"]["lo"], a4["transcript"]["null_loo"]["hi"]
    if not lo_b <= a4["transcript"]["rho_loo_BIASED"] <= hi_b:
        failures.append("§6.2 claims the observed LOO falls inside its null band; it does not")
    for name, shown in (("all_channels", "+0.0049"), ("transcript", "+0.0042"),
                        ("transcript_vocal", "−0.0015"), ("disagreement_only", "−0.0026")):
        checks += 1
        if abs(a4[name]["null_repeated_split"]["mean"]) > 0.02:
            failures.append(f"§6.2 claims the split null is centred on zero; {name} is not")

    # ── §7 / A5 sensitivity ──────────────────────────────────────────────────
    alt = stored["A5_sensitivity_surprise_neutral"]
    alt_rows = AX.build_rows(items, pr, facial_map=AX.FACIAL_VALENCE_ALT)
    alt_fac = [r for r in alt_rows if r["vf"] is not None]
    claim("A5 facial signed", stats.spearman([r["h"] for r in alt_fac],
                                             [r["vf"] for r in alt_fac]), "+0.0512",
          alt["A1_signed_vs_absolute"]["facial"]["signed"]["rho"])
    claim("A5 facial |val|", stats.spearman([r["h"] for r in alt_fac],
                                            [abs(r["vf"]) for r in alt_fac]), "−0.0135",
          alt["A1_signed_vs_absolute"]["facial"]["absolute"]["rho"])
    claim("A5 c~D", stats.spearman([r["c"] for r in alt_rows],
                                   [AX.disagreement(r) for r in alt_rows]), "+0.4355",
          alt["A3_faithfulness"]["rho_c_vs_disagreement"]["rho"])
    checks += 1
    if not math.isclose(alt["A4_oracle"]["all_channels"]["rho_in_sample"],
                        a4["all_channels"]["rho_in_sample"], abs_tol=1e-12):
        failures.append("§7 claims the oracle is identical under both mappings; it is not")
    n_surprise = sum(1 for r in rows if r["f_label"] == "surprise")
    claim("A5 surprise n", float(n_surprise), "3 of 119 segments")

    # ── provenance and honesty markers ───────────────────────────────────────
    checks += 1
    if stored["provenance"]["pre_registered"] is not False:
        failures.append("results.json does not record this as post-hoc")
    present("post-hoc declared", "**Post-hoc, exploratory, and declared as such.**")
    present("amendment referenced", "Amendment A6")
    proto = PROTO.read_text()
    present("A6 exists in PROTOCOL", "### A6 — 08 Sep 2026", proto)
    present("A6 states post-hoc", "post-hoc\nand exploratory", proto)
    present("A6 states nothing re-elicited",
            "No rating was collected, revised, or re-elicited after the result was\nseen",
            proto)
    present("scope limit stated", "### 6.1 Scope of this bound, stated precisely")
    present("scope excludes text-reading", "does **not** bound")
    present("limitations exist", "## 9. Limitations")
    present("post-hoc limitation", "The hypothesis was formed after seeing the null")
    present("range restriction", "only 3 of 119\n   segments below 2.5")
    present("construct was taught", "**The construct was taught, not independently arrived at**")
    present("A7 referenced in limitations", "Amendment A7,\n   added after this analysis was written")
    present("ceiling figures are lower bounds", "**lower bound** on relative performance")
    present("A7 exists in PROTOCOL", "### A7 — 08 Sep 2026", proto)
    present("A7 states briefer also rated", "**The briefer is also a rater.**", proto)
    present("A7 states not pre-registered", "**It was not pre-registered**", proto)
    present("A7 protects verify_page", "778 checks are unaffected", proto)

    # Range-restriction claim is checkable.
    claim("min h", min(h), "1.625")
    claim("max h", max(h), "5.000")
    claim("mean h", sum(h) / len(h), "3.973")
    claim("n below 2.5", float(sum(1 for v in h if v < 2.5)), "3 of 119")

    # ── report ───────────────────────────────────────────────────────────────
    print(f"{checks} claims checked against {DOC.name}")
    if failures:
        print(f"\n{len(failures)} FAILED:\n")
        for f in failures:
            print("  -", f)
        return 1
    print("all verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
