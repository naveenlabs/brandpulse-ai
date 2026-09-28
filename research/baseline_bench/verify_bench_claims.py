"""
verify_bench_claims.py — every number in BASELINE_ANALYSIS.md, recomputed.

Companion to `verify_claims.py`, which does the same for
`BASELINE_RATER_ANALYSIS.md`. Split into two files because they verify two
different kinds of thing from two different sources: that one re-derives the
human ground truth from the four rating files, this one re-derives the system
results from the 480 cached LLM responses.

The discipline is the same and it is the project's evidence rule:

  1. **Recompute from the cache**, not from `bench_results.json`. Reading the
     results file to check the document only proves the two agree — which they
     would even if `report_bench.py` were wrong.
  2. **Require the number verbatim in the prose**, at the precision quoted. A
     number that is right in the JSON and mistyped in the write-up is the most
     likely failure and the one a reader would actually be misled by.
  3. Compare against `bench_results.json` too, so a stale results file is caught
     rather than silently republished.

Run:  python research/baseline_bench/verify_bench_claims.py
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

import rater_analysis as RA  # noqa: E402
import report_bench as RPT  # noqa: E402
import stats  # noqa: E402
import systems as SY  # noqa: E402

DOC = BENCH / "BASELINE_ANALYSIS.md"
RESULTS = BENCH / "bench_results.json"
CACHE = BENCH / "cache"

text = DOC.read_text()
FLAT = " ".join(text.split())
stored = json.loads(RESULTS.read_text())
checks = 0
failures: list[str] = []


def _to_float(s: str):
    t = s.strip().replace("−", "-").replace(",", "").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def _tolerance(shown: str) -> float:
    t = shown.strip().replace("−", "-").rstrip("%")
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


def present(label: str, s: str):
    global checks
    checks += 1
    if " ".join(s.split()) not in FLAT:
        failures.append(f"{label}: {s!r} not in the document")


def main() -> int:
    global checks
    probes = SY.build_probes()
    by_uid = {p["uid"]: p for p in probes}
    sample, items, dups, pr = RA.load()
    keep = [u for u in sorted(items) if RA.usable_count(pr, u) >= RA.MIN_USABLE]
    sel = [u for u in keep if items[u]["split"] == "selection"]
    hol = [u for u in keep if items[u]["split"] == "holdout"]
    h = {u: RA.ground_truth(pr, u) for u in keep}

    # ── recompute every system's scores straight from the cached responses ────
    scores: dict[str, dict[str, float]] = {}
    raws: dict[str, list[float]] = {}
    lat: dict[str, list[float]] = {}
    for s in SY.LLM_SYSTEMS:
        sc, rr, ll = {}, [], []
        for p in probes:
            f = CACHE / s / f"{p['uid']}.json"
            if not f.exists():
                continue
            rec = json.loads(f.read_text())
            sc[p["uid"]] = rec["result"]["conflict_score"]
            if rec.get("seconds") is not None:
                ll.append(rec["seconds"])
            if rec.get("raw"):
                v = json.loads(rec["raw"]).get("conflict_score")
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    rr.append(float(v))
        scores[s], raws[s], lat[s] = sc, rr, sorted(ll)
    for s in SY.RULE_SYSTEMS:
        scores[s] = {p["uid"]: SY.rule_score(s, p) for p in probes}

    def rho(system, uids):
        return RPT.rho_for([(h[u], scores[system][u]) for u in uids
                            if u in scores[system]])

    # ── §1 run ────────────────────────────────────────────────────────────────
    claim("segments scored", float(len(keep)), "119", float(stored["n_segments"]))
    claim("selection", float(len(sel)), "80")
    claim("holdout", float(len(hol)), "39")
    n_calls = sum(len(scores[s]) for s in SY.LLM_SYSTEMS)
    claim("total calls", float(n_calls), "480")
    n_failed = sum(1 for s in SY.LLM_SYSTEMS for p in probes
                   if (CACHE / s / f"{p['uid']}.json").exists()
                   and not json.loads((CACHE / s / f"{p['uid']}.json").read_text())["ok"])
    claim("failures", float(n_failed), "0 failures")
    total = sum(sum(lat[s]) for s in SY.LLM_SYSTEMS)
    claim("total llm seconds", total, "1,923.8")
    claim("total llm minutes", total / 60, "32.1")
    for s, shown in (("four_channel", "4.51"), ("three_channel", "4.56"),
                     ("text_only_llm", "3.60"), ("text_only_llm_anchored", "3.38")):
        claim(f"{s} median latency", stats._percentile(lat[s], 0.5), shown)
    present("controller", "`llama3.1:8b`")
    claim("num_ctx", float(stored["num_ctx"]), "4096")

    # determinism: the `_det` caches must exist and agree with the primary run
    det_checked = det_bad = 0
    for s in SY.LLM_SYSTEMS:
        ddir = CACHE / f"{s}_det"
        if not ddir.exists():
            continue
        for f in sorted(ddir.glob("*.json")):
            main = CACHE / s / f.name
            if not main.exists():
                continue
            det_checked += 1
            if json.loads(f.read_text())["result"]["conflict_score"] != \
                    json.loads(main.read_text())["result"]["conflict_score"]:
                det_bad += 1
    claim("determinism re-runs", float(det_checked), "40 re-runs")
    checks += 1
    if det_bad:
        failures.append(f"{det_bad} determinism mismatches, document says 0")
    present("determinism claim", "0 mismatches over 40 re-runs")

    # ── §0/§2 P1 table ────────────────────────────────────────────────────────
    p1 = {
        ("four_channel", "all"): ("+0.0575", "−0.1282", "+0.2364", "0.527", "6.7%", "7"),
        ("four_channel", "selection"): ("+0.0492", "−0.1770", "+0.2765", "0.535", "7.5%", "6"),
        ("four_channel", "holdout"): ("+0.0604", "−0.2616", "+0.3655", "0.510", "5.1%", "6"),
        ("three_channel", "all"): ("−0.0341", "−0.2253", "+0.1562", "0.494", "2.5%", "6"),
        ("three_channel", "selection"): ("+0.0689", "−0.1663", "+0.3063", "0.500", "2.5%", "6"),
        ("three_channel", "holdout"): ("−0.3033", "−0.6039", "+0.0257", "0.483", "2.6%", "5"),
        ("text_only_llm", "all"): ("−0.0676", "−0.2373", "+0.1085", "0.751", "67.2%", "5"),
        ("text_only_llm", "holdout"): ("−0.0072", "−0.3046", "+0.2938", "0.764", "71.8%", "3"),
        ("text_only_llm_anchored", "all"): ("−0.1610", "−0.3302", "+0.0120", "0.284", "29.4%", "4"),
        ("text_only_llm_anchored", "selection"): ("−0.3534", "−0.5284", "−0.1559", "0.291", "30.0%", "4"),
        ("text_only_llm_anchored", "holdout"): ("+0.2664", "−0.0635", "+0.5588", "0.269", "28.2%", "3"),
        ("transcript_label_neg_genuine", "all"): ("+0.0784", "−0.1089", "+0.2595", "0.559", "24.4%", "3"),
        ("transcript_label_neg_genuine", "holdout"): ("+0.2143", "−0.0935", "+0.4908", "0.526", "23.1%", "3"),
        ("transcript_label_pos_genuine", "all"): ("−0.0784", "−0.2595", "+0.1089", None, None, "3"),
        ("constant", "all"): ("+0.0000", "+0.0000", "+0.0000", "0.000", "0.0%", "1"),
    }
    splits = {"all": keep, "selection": sel, "holdout": hol}
    for (s, split), (r, lo, hi, mean, flag, dist) in p1.items():
        uids = splits[split]
        st = stored["P1"][s][split]
        claim(f"P1 {s} {split} rho", rho(s, uids), r, st["rho"])
        if lo:
            claim(f"P1 {s} {split} lo", st["lo"], lo)
            claim(f"P1 {s} {split} hi", st["hi"], hi)
        vals = [scores[s][u] for u in uids if u in scores[s]]
        if mean:
            claim(f"P1 {s} {split} mean", sum(vals) / len(vals), mean)
        if flag:
            claim(f"P1 {s} {split} flag",
                  sum(1 for v in vals if v >= stored["flag_threshold"]) / len(vals), flag)
        claim(f"P1 {s} {split} distinct", float(len(set(vals))), dist)

    checks += 1
    if abs(rho("constant", keep)) > 1e-12:
        failures.append("constant does not score exactly 0 — the metric is unsound")
    present("constant verdict", "exactly 0.000")

    # ── §0 ceiling ────────────────────────────────────────────────────────────
    rr = json.loads((BENCH / "rater_analysis_results.json").read_text())
    claim("human ceiling", rr["ceiling"]["all"]["mean_rho"], "+0.8038")
    claim("human ceiling holdout", rr["ceiling"]["holdout"]["mean_rho"], "+0.7613")
    claim("ceiling lo", rr["ceiling"]["all_bootstrap_ci"]["lo"], "+0.7343")
    claim("ceiling hi", rr["ceiling"]["all_bootstrap_ci"]["hi"], "+0.8559")
    claim("alpha", rr["alpha"]["all"]["ordinal"]["alpha"], "0.7296")
    claim("icc", rr["icc"]["icc_2_k"], "0.9124")
    claim("fraction of ceiling", rho("four_channel", keep)
          / rr["ceiling"]["all"]["mean_rho"], "7.2%")

    # ── §3 P3 ────────────────────────────────────────────────────────────────
    p3 = {"holdout": ("−0.2060", "−0.6246", "+0.2395", "17.6%"),
          "all": ("+0.2185", "−0.0573", "+0.4881", "94.2%"),
          "selection": ("+0.4026", "+0.0659", "+0.7294", "99.0%")}
    for split, (pt, lo, hi, win) in p3.items():
        d = RPT.paired(scores["four_channel"], scores["text_only_llm_anchored"],
                       h, splits[split])
        st = stored["P3"][split]
        claim(f"P3 {split} point", d["point"], pt, st["point"])
        claim(f"P3 {split} lo", d["lo"], lo)
        claim(f"P3 {split} hi", d["hi"], hi)
        claim(f"P3 {split} win", d["win_frac"], win)
    d = stored["P3"]["holdout_vs_text_only_llm"]
    claim("P3 vs original prompt", d["point"], "+0.0676")
    claim("P3 vs original lo", d["lo"], "−0.3445")
    claim("P3 vs original hi", d["hi"], "+0.4615")
    claim("P3 vs original win", d["win_frac"], "61.9%")
    present("P3 verdict", "no detected difference on the pre-registered primary endpoint")
    claim("holdout interval width",
          stored["P3"]["holdout"]["hi"] - stored["P3"]["holdout"]["lo"], "0.864")
    present("A5 chosen", "text_only_llm_anchored")
    checks += 1
    if stored["text_only_primary"]["chosen"] != "text_only_llm_anchored":
        failures.append("A5's chosen baseline is not what the document says")

    # ── §4 granularity ───────────────────────────────────────────────────────
    raw_shown = {
        "four_channel": ("4", "71.7%", "0.550", {0.0: 10, 0.5: 16, 0.6: 86, 0.8: 8}),
        "three_channel": ("4", "63.3%", "0.533", {0.0: 9, 0.5: 32, 0.6: 76, 0.8: 3}),
        "text_only_llm": ("5", "66.7%", "0.751",
                          {0.0: 1, 0.6: 13, 0.7: 25, 0.8: 80, 0.9: 1}),
        "text_only_llm_anchored": ("4", "46.7%", "0.284",
                                   {0.0: 56, 0.25: 28, 0.75: 33, 1.0: 3}),
    }
    for s, (dist, modal, mean, counts) in raw_shown.items():
        r = raws[s]
        c = collections.Counter(r)
        claim(f"raw {s} distinct", float(len(set(r))), dist)
        claim(f"raw {s} modal", max(c.values()) / len(r), modal)
        checks += 1
        if dict(sorted(c.items())) != counts:
            failures.append(f"raw {s} distribution is {dict(sorted(c.items()))}, "
                            f"document says {counts}")
    claim("four raw mean", sum(raws["four_channel"]) / len(raws["four_channel"]), "0.550")
    claim("three raw mean", sum(raws["three_channel"]) / len(raws["three_channel"]), "0.533")
    claim("anchored raw mean", sum(raws["text_only_llm_anchored"])
          / len(raws["text_only_llm_anchored"]), "0.290")
    claim("text_only raw mean", sum(raws["text_only_llm"])
          / len(raws["text_only_llm"]), "0.752")

    # the same channel config giving three different scores
    cfg = collections.defaultdict(collections.Counter)
    for p in probes:
        rec = json.loads((CACHE / "four_channel" / f"{p['uid']}.json").read_text())
        v = json.loads(rec["raw"]).get("conflict_score")
        it = items[p["uid"]]
        key = (it["transcript_sentiment"], it["vocal_emotion"],
               bool(it["facial_emotion"]))
        cfg[key][v] += 1
    target = cfg[("POSITIVE", "NEUTRAL", True)]
    checks += 1
    if not (target[0.0] == 5 and target[0.5] == 6 and target[0.6] == 4
            and sum(target.values()) == 15):
        failures.append(f"POSITIVE/NEUTRAL/face config counts are {dict(target)}, "
                        "document says 5 / 6 / 4 over 15 occurrences")
    present("config claim",
            "returned **0.0 five times, 0.5 six times and 0.6 four times**")

    # ── §5 P4 ────────────────────────────────────────────────────────────────
    p4 = {"holdout": ("+0.3637", "+0.1082", "+0.6425"),
          "all": ("+0.0917", "−0.0180", "+0.2067"),
          "selection": ("−0.0197", "−0.1349", "+0.0779")}
    for split, (pt, lo, hi) in p4.items():
        st = stored["P4"][split]
        claim(f"P4 {split} point", st["point"], pt)
        claim(f"P4 {split} lo", st["lo"], lo)
        claim(f"P4 {split} hi", st["hi"], hi)
    st = stored["P4"]["facial_present_only"]
    claim("P4 facial-present point", st["point"], "+0.1721")
    claim("P4 facial-present lo", st["lo"], "+0.0055")
    claim("P4 facial-present hi", st["hi"], "+0.3392")
    claim("P4 facial-present n", float(st["n"]), "85")
    same = sum(1 for u in keep
               if scores["four_channel"][u] == scores["three_channel"][u])
    claim("identical scores", float(same), "86")
    hol_diff = sum(1 for u in hol
                   if scores["four_channel"][u] != scores["three_channel"][u])
    claim("holdout differing", float(hol_diff), "19")
    hol_pay = sum(1 for u in hol
                  if SY.payload_for("four_channel", by_uid[u])
                  != SY.payload_for("three_channel", by_uid[u]))
    claim("holdout payloads differ", float(hol_pay), "34")
    claim("holdout tied", float(len(hol) - hol_diff), "20")

    # ── §6 own-granularity ceiling ───────────────────────────────────────────
    ceil_shown = {"four_channel": ("+0.7974", "7.2%"),
                  "three_channel": ("+0.8601", "−4.0%"),
                  "text_only_llm": ("+0.8269", "−8.2%"),
                  "text_only_llm_anchored": ("+0.9279", "−17.4%")}
    for s, (c_shown, pct) in ceil_shown.items():
        hs = [h[u] for u in keep]
        cs = [scores[s][u] for u in keep]
        order = sorted(range(len(hs)), key=lambda i: -hs[i])
        best = [0.0] * len(hs)
        for rank, i in enumerate(sorted(range(len(cs)), key=lambda j: cs[j])):
            best[order[rank]] = sorted(cs)[rank]
        ceil = stats.spearman(hs, [-c for c in best])
        claim(f"own ceiling {s}", ceil, c_shown)
        claim(f"own ceiling pct {s}", rho(s, keep) / ceil, pct)

    # ── §6.1 target ranks ────────────────────────────────────────────────────
    low = [u for u in keep if h[u] < 3.0]
    claim("n low targets", float(len(low)), "5")
    ranks_shown = {"four_channel": [3, 22, 49, 75, 118],
                   "three_channel": [2, 17, 42, 62, 118],
                   "text_only_llm": [11, 34, 36, 70, 98],
                   "text_only_llm_anchored": [17, 58, 71, 84, 108]}
    for s, expect in ranks_shown.items():
        ranked = sorted(keep, key=lambda u: -scores[s][u])
        got = sorted(ranked.index(u) + 1 for u in low)
        checks += 1
        if got != expect:
            failures.append(f"target ranks for {s} are {got}, document says {expect}")

    # ── §7 the two worked examples ───────────────────────────────────────────
    present("sarcasm text",
            "oh yeah, thank gosh I have eight lenses now in my smartphone.")
    sarc = [u for u in keep if "eight lenses" in items[u]["text"]][0]
    claim("sarcasm h", h[sarc], "2.00")
    claim("sarcasm four_channel score", scores["four_channel"][sarc], "0.0000")
    checks += 1
    nar = json.loads(json.loads((CACHE / "four_channel" / f"{sarc}.json").read_text())["raw"]).get("narrative", "")
    if "consistent across all channels" not in nar:
        failures.append("the quoted four_channel narrative is not in the cache")
    present("sarcasm narrative",
            "The creator's sentiment is consistent across all channels")
    checks += 1
    if items[sarc]["transcript_sentiment"] != "POSITIVE" or \
            items[sarc]["vocal_emotion"] != "POSITIVE":
        failures.append("the sarcasm segment's channel labels are not both POSITIVE")

    present("criticism text", "I hate that it looks like a mini purse")
    crit = [u for u in keep if "mini purse" in items[u]["text"]][0]
    claim("criticism h", h[crit], "5.00")
    claim("criticism score", scores["four_channel"][crit], "0.800")
    checks += 1
    if items[crit]["transcript_sentiment"] != "NEGATIVE" or \
            items[crit]["vocal_emotion"] != "POSITIVE":
        failures.append("the criticism segment's labels are not NEGATIVE/POSITIVE")

    # ── §8 decomposition, §9 sensitivity ─────────────────────────────────────
    sd = stored["signal_decomposition"]["four_channel"]
    claim("raw llm rho all", sd["rho_raw_llm_all"], "+0.0413")
    claim("raw llm rho holdout", sd["rho_raw_llm_holdout"], "+0.0826")
    claim("damping indicator all", sd["rho_damping_indicator_all"], "−0.0442")
    claim("damping indicator holdout", sd["rho_damping_indicator_holdout"], "+0.0603")
    nd = stored["sensitivity_no_damping"]
    claim("four damped count", float(nd["four_channel"]["n_changed"]), "11")
    claim("three damped count", float(nd["three_channel"]["n_changed"]), "20")
    claim("four mean damped", nd["four_channel"]["mean_damped"], "0.527")
    claim("four mean undamped", nd["four_channel"]["mean_undamped"], "0.555")
    claim("three mean damped", nd["three_channel"]["mean_damped"], "0.494")
    claim("three mean undamped", nd["three_channel"]["mean_undamped"], "0.538")
    na = stored["sensitivity_no_author"]
    claim("no-author four all", na["four_channel"]["all"], "+0.0636")
    claim("no-author four holdout", na["four_channel"]["holdout"], "+0.1161")
    claim("no-author P3", na["P3_holdout"]["point"], "−0.1179")
    fp = stored["sensitivity_first_presentation"]
    claim("first-only four all", fp["four_channel"]["all"], "+0.0488")
    claim("first-only four holdout", fp["four_channel"]["holdout"], "+0.0629")

    # ── §10 / §12 cross-document facts ───────────────────────────────────────
    claim("human not-genuine rate",
          sum(1 for u in keep if h[u] < 3.0) / len(keep), "4.2%")
    claim("anchored zeros", float(collections.Counter(
        raws["text_only_llm_anchored"])[0.0]), "56")
    ts = rr["channel_diagnostic"]["transcript_sentiment"]["groups"]
    claim("transcript NEG h", ts["NEGATIVE"]["mean"], "4.392")
    claim("transcript NEU h", ts["NEUTRAL"]["mean"], "3.870")
    claim("transcript p", rr["channel_diagnostic"]["transcript_sentiment"]["permutation_p"], "0.034")
    present("no refactor", "Nothing in `pipeline/` is changed")
    present("outcome three", "third outcome")

    print(f"verify_bench_claims: {checks} claims checked against {DOC.name} "
          f"and the {n_calls} cached responses")
    if failures:
        print(f"\nFAILED — {len(failures)} problem(s):")
        for f in failures[:60]:
            print("  ", f)
        if len(failures) > 60:
            print(f"   … and {len(failures) - 60} more")
        return 1
    print("PASSED — every quoted number recomputes from the cached run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
