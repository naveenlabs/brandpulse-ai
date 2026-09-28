"""
report_bench.py — P1-P6 and every sensitivity run PROTOCOL.md fixes in advance.

Reads two things and computes everything from them:

  * the human ground truth, via `rater_analysis` (PROTOCOL.md §5.4)
  * the cached system responses in `cache/<system>/<uid>.json`

It makes no model call. A cached run is a permanent artefact, so every number in
`BASELINE_ANALYSIS.md` can be re-derived years from now without a working Ollama —
the property that makes `verify_claims.py` meaningful rather than decorative.

Endpoints, all pre-registered in PROTOCOL.md §6:

  P1  Spearman rho between h(s) and -c(s), bootstrap 95% CI over segments
  P2  the same on holdout speakers only — the number that counts (§4.3)
  P3  paired bootstrap of rho_four - rho_text (§8.1's primary decision)
  P4  paired bootstrap of rho_four - rho_three — the facial channel's net
      contribution in situ (RQ2)
  P5  the human ceiling, from rater_analysis
  P6  rater agreement, from rater_analysis

Sensitivity runs, PROTOCOL.md §8.4 / §8.5, none able to change the primary
decision:

  - the author's ratings dropped entirely
  - damping disabled
  - duplicates first-presentation-only
  - per-video rho, to check no single video carries the result
  - `constant` scored on the same path, which MUST return exactly 0.000

Run:  python research/baseline_bench/report_bench.py
Out:  baseline_bench/bench_results.json
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import rater_analysis as RA  # noqa: E402
import stats  # noqa: E402
import systems as SY  # noqa: E402
from pipeline import orchestrator as O  # noqa: E402

CACHE = BENCH / "cache"
N_BOOT = 10000
SEED = 42


# ── loading ───────────────────────────────────────────────────────────────────

def load_scores(probes: list[dict]) -> dict[str, dict[str, float]]:
    """{system: {uid: conflict_score}} for every system, from disk.

    The rule-based systems are computed here rather than cached: they are pure
    functions of a label already in `sample.json`, so caching them would create a
    second copy of the same fact that could go stale.
    """
    out: dict[str, dict[str, float]] = {}
    for system in SY.LLM_SYSTEMS:
        d = CACHE / system
        if not d.exists():
            continue
        scores = {}
        for probe in probes:
            f = d / f"{probe['uid']}.json"
            if f.exists():
                scores[probe["uid"]] = json.loads(f.read_text())["result"]["conflict_score"]
        if scores:
            out[system] = scores
    for system in SY.RULE_SYSTEMS:
        out[system] = {p["uid"]: SY.rule_score(system, p) for p in probes}
    return out


def load_records(system: str, probes: list[dict]) -> list[dict]:
    d = CACHE / system
    return [json.loads((d / f"{p['uid']}.json").read_text())
            for p in probes if (d / f"{p['uid']}.json").exists()]


def rescore_undamped(system: str, probes: list[dict]) -> dict[str, float]:
    """§8.5: the same cached responses, re-coerced with damping switched off.

    The raw LLM responses are unchanged — only `_coerce_result`'s down-weighting
    is bypassed, by handing it a segment with no channel labels for the weak
    channels to be sole dissenters in. That isolates the damping's contribution
    without a second 40-minute run and without any new model call.
    """
    out = {}
    by_uid = {p["uid"]: p for p in probes}
    d = CACHE / system
    for probe in probes:
        f = d / f"{probe['uid']}.json"
        if not f.exists():
            continue
        rec = json.loads(f.read_text())
        if not rec.get("ok") or rec.get("raw") is None:
            out[probe["uid"]] = rec["result"]["conflict_score"]
            continue
        seg = by_uid[probe["uid"]]["segment"]
        bare = {"segment_id": seg["segment_id"], "start_time": seg["start_time"],
                "end_time": seg["end_time"], "text": seg["text"]}
        out[probe["uid"]] = O._coerce_result(json.loads(rec["raw"]), bare,
                                             None)["conflict_score"]
    return out


# ── the metric ────────────────────────────────────────────────────────────────

def rho_for(pairs: list[tuple[float, float]]) -> float:
    """Spearman between h and -c. PROTOCOL.md §6: higher c means more conflict,
    so it should predict LOWER human genuineness; negating makes a competent
    system score positive and keeps every table pointing the same way."""
    if len(pairs) < 2:
        return 0.0
    return stats.spearman([h for h, _ in pairs], [-c for _, c in pairs])


def evaluate(scores: dict[str, float], h: dict[str, float],
             uids: list[str]) -> dict:
    pairs = [(h[u], scores[u]) for u in uids if u in scores and u in h]
    if len(pairs) < 2:
        return {"n": len(pairs), "rho": None}
    boot = stats.bootstrap_ci(pairs, rho_for, n_boot=N_BOOT, seed=SEED)
    boot.pop("dist")
    vals = [c for _, c in pairs]
    return {"n": len(pairs), "rho": boot["point"], "lo": boot["lo"],
            "hi": boot["hi"], "n_degenerate": boot["n_degenerate"],
            "distinct_values": len(set(vals)),
            "mean_score": sum(vals) / len(vals),
            "min_score": min(vals), "max_score": max(vals),
            "value_counts": dict(sorted(collections.Counter(
                round(v, 4) for v in vals).items())),
            "flag_rate": sum(1 for v in vals
                             if v >= O.CONFLICT_FLAG_THRESHOLD) / len(vals)}


def paired(a: dict[str, float], b: dict[str, float], h: dict[str, float],
           uids: list[str]) -> dict:
    """P3 / P4: bootstrap rho_a - rho_b on the SAME resamples.

    Two correlations over the same segments against the same ground truth are
    dependent. Comparing two independently bootstrapped intervals would be the
    wrong test and would almost always report "overlapping, no difference".
    """
    trip = [(h[u], a[u], b[u]) for u in uids if u in a and u in b and u in h]
    if len(trip) < 2:
        return {"n": len(trip), "point": None}
    r = stats.paired_bootstrap_diff(
        trip,
        lambda t: rho_for([(x, y) for x, y, _ in t]),
        lambda t: rho_for([(x, z) for x, _, z in t]),
        n_boot=N_BOOT, seed=SEED)
    r["n"] = len(trip)
    return r


def verdict(diff: dict) -> str:
    """PROTOCOL.md §8.1, applied mechanically so it cannot be talked around."""
    if diff.get("point") is None:
        return "no data"
    if not diff["excludes_zero"]:
        return "no detected difference"
    return "A wins" if diff["point"] > 0 else "B wins"


def main() -> int:
    probes = SY.build_probes()
    by_uid = {p["uid"]: p for p in probes}
    sample, items, dups, pr = RA.load()

    keep = [u for u in sorted(items) if RA.usable_count(pr, u) >= RA.MIN_USABLE]
    h = {u: RA.ground_truth(pr, u) for u in keep}
    h_noauthor = {u: RA.ground_truth(pr, u, RA.BLIND) for u in keep}
    h_first = {u: RA.ground_truth_first_only(pr, u) for u in keep}
    sel = [u for u in keep if items[u]["split"] == "selection"]
    hol = [u for u in keep if items[u]["split"] == "holdout"]

    scores = load_scores(probes)
    R = {"n_segments": len(keep), "n_selection": len(sel), "n_holdout": len(hol),
         "n_boot": N_BOOT, "seed": SEED,
         "controller": O.OLLAMA_MODEL, "num_ctx": O.OLLAMA_NUM_CTX,
         "flag_threshold": O.CONFLICT_FLAG_THRESHOLD,
         "systems_scored": sorted(scores)}

    # ── run health, before any correlation is quoted ──────────────────────────
    R["run_health"] = {}
    for system in SY.LLM_SYSTEMS:
        recs = load_records(system, probes)
        if not recs:
            continue
        lat = [r["seconds"] for r in recs if r.get("seconds") is not None]
        lat.sort()
        # The RAW score, before `_coerce_result` clamps or damps anything. This
        # separates what the controller actually said from what the pipeline's
        # deterministic rules did to it afterwards — which turns out to matter
        # more than the correlation itself (see BASELINE_ANALYSIS.md §5).
        raw = []
        for r in recs:
            if r.get("raw") is None:
                continue
            try:
                v = json.loads(r["raw"]).get("conflict_score")
            except Exception:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                raw.append(float(v))
        R["run_health"][system] = {
            "n": len(recs),
            "ok": sum(1 for r in recs if r["ok"]),
            "failed": sum(1 for r in recs if not r["ok"]),
            "reasons": dict(collections.Counter(
                r["reason"] for r in recs if r.get("reason"))),
            "median_seconds": stats._percentile(lat, 0.5) if lat else None,
            "total_seconds": round(sum(lat), 1) if lat else None,
            "raw_distinct_values": len(set(raw)),
            "raw_value_counts": dict(sorted(collections.Counter(raw).items())),
            "raw_modal_share": (max(collections.Counter(raw).values()) / len(raw)
                                if raw else None),
            "raw_mean": sum(raw) / len(raw) if raw else None,
        }

    # ── P1 / P2 ───────────────────────────────────────────────────────────────
    R["P1"] = {}
    for system, sc in scores.items():
        R["P1"][system] = {
            "all": evaluate(sc, h, keep),
            "selection": evaluate(sc, h, sel),
            "holdout": evaluate(sc, h, hol),
        }

    # ── which text-only prompt counts (Amendment A5) ─────────────────────────
    cands = [s for s in ("text_only_llm", "text_only_llm_anchored") if s in scores]
    best = None
    if cands:
        best = max(cands, key=lambda s: (R["P1"][s]["holdout"]["rho"] or -9))
    R["text_only_primary"] = {
        "chosen": best,
        "rule": "higher holdout rho; Amendment A5 gives the baseline its best of "
                "two pre-declared prompts, which favours the baseline",
        "holdout_rho": {s: R["P1"][s]["holdout"]["rho"] for s in cands},
        "all_rho": {s: R["P1"][s]["all"]["rho"] for s in cands},
    }

    # ── P3 / P4 ───────────────────────────────────────────────────────────────
    R["P3"] = {}
    R["P4"] = {}
    if "four_channel" in scores and best:
        for nm, ss in (("all", keep), ("selection", sel), ("holdout", hol)):
            R["P3"][nm] = paired(scores["four_channel"], scores[best], h, ss)
            R["P3"][nm]["verdict"] = verdict(R["P3"][nm])
        for s in cands:
            R["P3"][f"holdout_vs_{s}"] = paired(scores["four_channel"],
                                                scores[s], h, hol)
            R["P3"][f"holdout_vs_{s}"]["verdict"] = verdict(
                R["P3"][f"holdout_vs_{s}"])
    if "four_channel" in scores and "three_channel" in scores:
        for nm, ss in (("all", keep), ("selection", sel), ("holdout", hol)):
            R["P4"][nm] = paired(scores["four_channel"], scores["three_channel"],
                                 h, ss)
            R["P4"][nm]["verdict"] = verdict(R["P4"][nm])
        # RQ2's effective sample: the segments where the two systems were
        # actually given different payloads. On the rest the ablation is a no-op
        # and including them can only dilute the estimate toward zero.
        differ = [u for u in keep
                  if SY.payload_for("four_channel", by_uid[u])
                  != SY.payload_for("three_channel", by_uid[u])]
        R["P4"]["facial_present_only"] = paired(
            scores["four_channel"], scores["three_channel"], h, differ)
        R["P4"]["facial_present_only"]["verdict"] = verdict(
            R["P4"]["facial_present_only"])
        R["P4"]["n_payloads_differ"] = len(differ)
        R["P4"]["n_identical_scores"] = sum(
            1 for u in keep
            if scores["four_channel"].get(u) == scores["three_channel"].get(u))

    # ── P5 / P6, from the instrument ─────────────────────────────────────────
    rr = json.loads((BENCH / "rater_analysis_results.json").read_text())
    R["P5_human_ceiling"] = {
        "all": rr["ceiling"]["all"]["mean_rho"],
        "selection": rr["ceiling"]["selection"]["mean_rho"],
        "holdout": rr["ceiling"]["holdout"]["mean_rho"],
        "ci": [rr["ceiling"]["all_bootstrap_ci"]["lo"],
               rr["ceiling"]["all_bootstrap_ci"]["hi"]],
    }
    R["P6_agreement"] = {
        "alpha_ordinal": rr["alpha"]["all"]["ordinal"]["alpha"],
        "alpha_holdout": rr["alpha"]["holdout"]["ordinal"]["alpha"],
        "icc_2k": rr["icc"]["icc_2_k"],
    }
    R["fraction_of_ceiling"] = {}
    for system in R["P1"]:
        for nm in ("all", "holdout"):
            rho = R["P1"][system][nm]["rho"]
            ceil = R["P5_human_ceiling"][nm]
            R["fraction_of_ceiling"].setdefault(system, {})[nm] = (
                rho / ceil if rho is not None and ceil else None)

    # ── §3.3 the degenerate reference must score exactly zero ────────────────
    R["constant_check"] = {
        "rho_all": R["P1"]["constant"]["all"]["rho"],
        "is_zero": abs(R["P1"]["constant"]["all"]["rho"]) < 1e-12,
        "note": "PROTOCOL.md §3.3: if this is not ~0 the metric is broken and "
                "the result is void",
    }

    # ── §8.4 author dropped ───────────────────────────────────────────────────
    R["sensitivity_no_author"] = {}
    for system, sc in scores.items():
        R["sensitivity_no_author"][system] = {
            "all": evaluate(sc, h_noauthor, keep)["rho"],
            "holdout": evaluate(sc, h_noauthor, hol)["rho"],
        }
    if "four_channel" in scores and best:
        d = paired(scores["four_channel"], scores[best], h_noauthor, hol)
        d["verdict"] = verdict(d)
        R["sensitivity_no_author"]["P3_holdout"] = d

    # ── §8.5 duplicates first-only ───────────────────────────────────────────
    R["sensitivity_first_presentation"] = {
        system: {"all": evaluate(sc, h_first, keep)["rho"],
                 "holdout": evaluate(sc, h_first, hol)["rho"]}
        for system, sc in scores.items()}

    # ── §8.5 damping disabled ────────────────────────────────────────────────
    R["sensitivity_no_damping"] = {}
    for system in ("four_channel", "three_channel"):
        if system not in scores:
            continue
        und = rescore_undamped(system, probes)
        # Only uids present on BOTH sides. A partially-filled cache — or one
        # permanently failed call — must yield a smaller comparison, not a
        # KeyError that destroys the whole report.
        both = [u for u in keep if u in und and u in scores[system]]
        changed = [u for u in both if abs(und[u] - scores[system][u]) > 1e-9]
        R["sensitivity_no_damping"][system] = {
            "n_compared": len(both),
            "n_changed": len(changed),
            "rho_all_damped": R["P1"][system]["all"]["rho"],
            "rho_all_undamped": evaluate(und, h, keep)["rho"],
            "rho_holdout_damped": R["P1"][system]["holdout"]["rho"],
            "rho_holdout_undamped": evaluate(und, h, hol)["rho"],
            "mean_damped": (sum(scores[system][u] for u in both) / len(both)
                            if both else None),
            "mean_undamped": (sum(und[u] for u in both) / len(both)
                              if both else None),
        }

    # ── signal decomposition (NOT pre-registered) ────────────────────────────
    #
    # `four_channel`'s score is two things multiplied: what the controller said,
    # and what `_coerce_result`'s deterministic down-weighting did to it. If the
    # deployed system correlates with human judgement, it is worth knowing which
    # half is responsible — an LLM that emits one number on almost every segment
    # cannot be, and the damping rule is a pure function of the channel labels
    # and needs no LLM at all.
    #
    # Diagnostic only. It cannot change the §8.1 decision and is labelled as not
    # pre-registered wherever it is quoted.
    R["signal_decomposition"] = {"note": "NOT pre-registered; diagnostic"}
    for system in ("four_channel", "three_channel"):
        if system not in scores:
            continue
        und = rescore_undamped(system, probes)
        both = [u for u in keep if u in und and u in scores[system]]
        damp_flag = {u: (1.0 if abs(und[u] - scores[system][u]) > 1e-9 else 0.0)
                     for u in both}
        R["signal_decomposition"][system] = {
            "rho_deployed_all": R["P1"][system]["all"]["rho"],
            "rho_raw_llm_all": evaluate(und, h, keep)["rho"],
            "rho_damping_indicator_all": evaluate(damp_flag, h, keep)["rho"],
            "rho_deployed_holdout": R["P1"][system]["holdout"]["rho"],
            "rho_raw_llm_holdout": evaluate(und, h, hol)["rho"],
            "rho_damping_indicator_holdout": evaluate(damp_flag, h, hol)["rho"],
            "n_damped": int(sum(damp_flag.values())),
            "n_compared": len(both),
            "raw_distinct": len(set(und[u] for u in both)),
            "deployed_distinct": len(set(scores[system][u] for u in both)),
        }

    # ── §8.5 per-video ───────────────────────────────────────────────────────
    byv = collections.defaultdict(list)
    for u in keep:
        byv[items[u]["video_id"]].append(u)
    R["per_video"] = {}
    for system, sc in scores.items():
        R["per_video"][system] = {
            v: {"n": sum(1 for u in us if u in sc),
                "rho": rho_for([(h[u], sc[u]) for u in us if u in sc]),
                "channel": items[us[0]]["channel"], "split": items[us[0]]["split"]}
            for v, us in sorted(byv.items())}

    out = BENCH / "bench_results.json"
    out.write_text(json.dumps(R, indent=1, default=float))
    print(f"wrote {out.name}")
    print(f"  segments: {len(keep)} ({len(sel)} sel, {len(hol)} holdout)")
    def f(x, w=6, dp=3):
        return f"{x:+.{dp}f}".rjust(w) if isinstance(x, (int, float)) else "   n/a"

    print(f"  {'system':30s} {'rho_all':>7} {'95% CI':>18} {'rho_hold':>8} "
          f"{'distinct':>8}")
    for system in sorted(R["P1"]):
        a, ho = R["P1"][system]["all"], R["P1"][system]["holdout"]
        ci = (f"[{f(a.get('lo'))},{f(a.get('hi'))}]"
              if a.get("lo") is not None else " " * 18)
        print(f"  {system:30s} {f(a.get('rho'))} {ci:>18} {f(ho.get('rho'))} "
              f"{a.get('distinct_values', '-'):>8}")
    if R["P3"].get("holdout", {}).get("point") is not None:
        d = R["P3"]["holdout"]
        print(f"  P3 holdout (four - {best}): {f(d['point'])} "
              f"[{f(d['lo'])},{f(d['hi'])}] win={d['win_frac']:.3f} -> {d['verdict']}")
    if R["P4"].get("holdout", {}).get("point") is not None:
        d = R["P4"]["holdout"]
        print(f"  P4 holdout (four - three): {f(d['point'])} "
              f"[{f(d['lo'])},{f(d['hi'])}] -> {d['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
