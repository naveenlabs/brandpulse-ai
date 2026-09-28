"""
verify_damping_fix.py - re-derive every number in DAMPING_FIX_RESULT.md.

Same contract as verify_ab.py, verify_claims.py and verify_speaker_norm.py: a
figure that cannot be re-derived is not evidence, and hand-copied numbers drift.

Two classes of check, kept separate:

  * claims read back from damping_ab_results.json, which is what the document was
    written from;
  * claims recomputed FROM SCRATCH out of the caches and the live orchestrator,
    which is what catches a stale or hand-edited results file.

The second class also re-derives the OLD rule's 0-of-N result, because the whole
document rests on the claim that the replacement changed something.

    python research/vocal_bench/verify_damping_fix.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(BENCH))

import damping_ab as D                       # noqa: E402
from pipeline import orchestrator as O       # noqa: E402

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


def _results() -> dict:
    path = BENCH / "damping_ab_results.json"
    if not path.is_file():
        raise RuntimeError(f"{path.name} not found - run damping_ab.py first")
    return json.loads(path.read_text())


# ── §1 what was broken, re-derived from the raw responses ────────────────────

def verify_the_defect() -> None:
    """The old rule really does fire on nothing. Recomputed, not quoted."""
    for arm, segments in (("after_nodamp", 481), ("before", 496)):
        n = fires = named = named_with_score = 0
        for path in sorted((D.CACHE / f"conflict_{arm}").glob("*.json")):
            for result in json.loads(path.read_text()).values():
                raw = result.get("_raw")
                if not isinstance(raw, dict):
                    continue
                n += 1
                cic = raw.get("channels_in_conflict")
                if isinstance(cic, list) and cic:
                    named += 1
                    if float(raw.get("conflict_score") or 0.0) > 0.0:
                        named_with_score += 1
                if O._conflict_rests_only_on_vocal(cic):
                    fires += 1
        check(f"§1 {arm} raw responses", n, segments)
        check(f"§1 {arm} old rule fires", fires, 0)
        if arm == "after_nodamp":
            check("§1 controller named a channel", named, 265)
            check("§1 attributions carrying a zero score", named - named_with_score, 257)
            check("§1 attributions carrying a score above zero", named_with_score, 8)


# ── §2 the three conservative decisions inside the new rule ──────────────────

def verify_rule_semantics() -> None:
    check("§2 surprise is off the valence axis", O._to_valence("surprise"), None)
    check("§2 unknown is not neutral", O._to_valence("unknown"), None)
    check("§2 neutral is a position", O._to_valence("neutral"), "NEUTRAL")

    seg = {"transcript_sentiment": {"label": "POSITIVE"},
           "vocal_emotion": {"label": "NEGATIVE"},
           "facial_emotion": {"dominant": "happy"}}
    check("§2 fires when vocal alone dissents", O._vocal_is_sole_dissenter(seg), True)

    split = dict(seg, facial_emotion={"dominant": "sad"})
    check("§2 silent when the others disagree", O._vocal_is_sole_dissenter(split), False)

    # The document claims the two triggers are ORed and that conflict_reasons
    # records which fired, as [attributed], [structural] or [attributed+structural].
    # This was checked until 12 Sep 2026 by grepping orchestrator.py for the
    # phrase "attributed or structural". That was a proxy for the property, and
    # it went stale the moment the facial channel arrived on 04 Sep and the two
    # single-channel branches were refactored into _trigger_name(). The behaviour
    # never changed; the needle did. It is now driven instead of read.
    def _note(raw, segment):
        notes = [r for r in O._coerce_result(dict(raw), segment)["conflict_reasons"]
                 if "vocal_channel_downweighted" in r]
        return notes[0] if len(notes) == 1 else ""

    dissent = {"segment_id": 1,
               "transcript_sentiment": {"label": "POSITIVE"},
               "vocal_emotion": {"label": "NEGATIVE"},
               "facial_emotion": {"dominant": "happy"}}
    damped = round(0.90 * O.VOCAL_ONLY_CONFLICT_WEIGHT, 4)

    attributed_only = {"conflict_score": 0.90, "channels_in_conflict": ["vocal_emotion"]}
    structural_only = {"conflict_score": 0.90, "channels_in_conflict": []}

    check("§2 attributed trigger alone damps",
          O._coerce_result(dict(attributed_only), {"segment_id": 1})["conflict_score"],
          damped)
    check("§2 attributed trigger alone is named",
          "[attributed]" in _note(attributed_only, {"segment_id": 1}), True)
    check("§2 structural trigger alone damps",
          O._coerce_result(dict(structural_only), dissent)["conflict_score"], damped)
    check("§2 structural trigger alone is named",
          "[structural]" in _note(structural_only, dissent), True)
    check("§2 both triggers are still ORed",
          "[attributed+structural]" in _note(attributed_only, dissent), True)
    check("§2 deployed minimum", O.MIN_CORROBORATING_CHANNELS, 2)
    check("§2 damping weight is the channel's measured accuracy",
          O.VOCAL_ONLY_CONFLICT_WEIGHT, 0.489)


# ── §3 and §4 coverage, recomputed ───────────────────────────────────────────

COVERAGE_DOC = {"after_nodamp": (481, 89, 18.5), "before": (496, 126, 25.4)}


def verify_coverage(res: dict) -> None:
    for arm, (segments, fires, pct) in COVERAGE_DOC.items():
        for setting in ("min1", "min2"):
            c = res[arm]["coverage"][setting]
            check(f"§3 {arm} {setting} segments", c["segments"], segments)
            check(f"§3 {arm} {setting} fires", c["fires"], fires)
            check(f"§3 {arm} {setting} fires pct", c["fires_pct"], pct, tol=0.05)
            check(f"§4 {arm} {setting} mean corroborators",
                  c["mean_corroborating_channels"], 2.000, tol=0.0005)
        check(f"§4 {arm} min1 and min2 are indistinguishable",
              res[arm]["coverage"]["min1"]["fires"],
              res[arm]["coverage"]["min2"]["fires"])

    check("§5.1 no firing lands on a non-zero score in the deployed arm",
          res["after_nodamp"]["coverage"]["min2"]["fires_on_a_nonzero_score"], 0)
    check("§5.2 firings landing on a non-zero score in the before arm",
          res["before"]["coverage"]["min2"]["fires_on_a_nonzero_score"], 17)

    # Recomputed from scratch through the live rule, not read back.
    for arm, (_, fires, _) in COVERAGE_DOC.items():
        total = sum(D.coverage(v, 2, arm)["fires"] for v in D.videos(arm))
        check(f"§3 {arm} fires, recomputed live", total, fires)


# ── §5 the effect on the reported scores ─────────────────────────────────────

TOTALS_DOC = {
    "after_nodamp": {
        "nodamp":          (97.45, 97.28, 8, 0, 0.0131),
        "attributed":      (97.45, 97.28, 8, 0, 0.0131),
        "structural_min1": (97.45, 97.28, 8, 0, 0.0131),
        "structural_min2": (97.45, 97.28, 8, 0, 0.0131),
    },
    "before": {
        "nodamp":          (70.68, 86.57, 70, 0, 0.2263),
        "attributed":      (70.68, 86.57, 70, 0, 0.2263),
        "structural_min1": (71.20, 86.78, 70, 17, 0.2205),
        "structural_min2": (71.20, 86.78, 70, 17, 0.2205),
    },
}


def verify_effect(res: dict) -> None:
    for arm, variants in TOTALS_DOC.items():
        for var, (auth, health, flagged, damped, mean) in variants.items():
            t = res[arm]["totals"][var]
            check(f"§5 {arm} {var} authenticity", t["authenticity"], auth, tol=0.005)
            check(f"§5 {arm} {var} brand health", t["brand_health"], health, tol=0.005)
            check(f"§5 {arm} {var} flagged", t["flagged"], flagged)
            check(f"§5 {arm} {var} damped", t["damped"], damped)
            check(f"§5 {arm} {var} mean conflict", t["mean_conflict"], mean, tol=0.00005)

    check("§5.1 deployed arm authenticity delta",
          res["after_nodamp"]["deltas"]["structural_min2"]["authenticity"], 0.0, tol=0.005)
    check("§5.1 deployed arm ceiling",
          res["after_nodamp"]["totals"]["nodamp"]["nonzero"], 8)
    check("§5.1 deployed arm segments unable to move",
          res["after_nodamp"]["totals"]["nodamp"]["segments"] - 8, 473)

    b = res["before"]["deltas"]["structural_min2"]
    check("§5.2 before arm authenticity delta", b["authenticity"], 0.52, tol=0.005)
    check("§5.2 before arm brand health delta", b["brand_health"], 0.21, tol=0.005)
    check("§5.2 before arm flagged delta", b["flagged"], 0)
    check("§5.2 before arm videos changed", b["videos_changed"], 7)
    check("§5.2 before arm ceiling", res["before"]["totals"]["nodamp"]["nonzero"], 235)
    check("§5.2 the old rule moves nothing on either arm",
          [res[a]["deltas"]["attributed"]["authenticity"] for a in TOTALS_DOC], [0.0, 0.0])

    per = res["before"]["per_video"]
    changed = [round(per[v]["score"]["structural_min2"]["authenticity"]
                     - per[v]["score"]["nodamp"]["authenticity"], 2)
               for v in res["before"]["videos"]]
    moved = [c for c in changed if c]
    check("§5.2 videos that moved", len(moved), 7)
    check("§5.2 smallest per-video gain", min(moved), 0.31, tol=0.005)
    check("§5.2 largest per-video gain", max(moved), 1.57, tol=0.005)

    # Every damped segment, recomputed: same before/after values, none flagged.
    base, new = {}, {}
    for v in D.videos("before"):
        for r in D.recoerce(v, "nodamp", "before"):
            base[(v, r["segment_id"])] = r
        for r in D.recoerce(v, "structural_min2", "before"):
            new[(v, r["segment_id"])] = r
    damped = [k for k in new
              if any("downweighted" in x for x in new[k]["conflict_reasons"])]
    check("§5.2 damped segments, recomputed", len(damped), 17)
    check("§5.2 every damped score was 0.3300",
          {round(base[k]["conflict_score"], 4) for k in damped}, {0.33})
    check("§5.2 every damped score became 0.1614",
          {round(new[k]["conflict_score"], 4) for k in damped}, {0.1614})
    check("§5.2 damping is exactly the weight",
          round(0.33 * O.VOCAL_ONLY_CONFLICT_WEIGHT, 4), 0.1614, tol=0.00005)
    check("§5.2 no damped segment was flagged beforehand",
          sum(1 for k in damped if base[k]["flagged"]), 0)
    check("§5.2 no segment crossed the flag threshold",
          sum(1 for k in new if base[k]["flagged"] != new[k]["flagged"]), 0)
    check("§5.2 all 17 sit below the flag threshold",
          all(base[k]["conflict_score"] < O.CONFLICT_FLAG_THRESHOLD for k in damped), True)
    check("§5.2 the trigger recorded is the structural one",
          all("[structural]" in " ".join(new[k]["conflict_reasons"]) for k in damped), True)


# ── §6 the controller's own behaviour ────────────────────────────────────────

DISTINCT_DOC = {
    "before": (496, 9, [(0.0, 261, 52.6), (0.33, 163, 32.9), (0.75, 21, 4.2)]),
    "after_nodamp": (481, 3, [(0.0, 473, 98.3), (0.8, 6, 1.2), (0.75, 2, 0.4)]),
}


def verify_controller(_: dict) -> None:
    for arm, (n_expected, distinct, top) in DISTINCT_DOC.items():
        counts: Counter = Counter()
        for path in sorted((D.CACHE / f"conflict_{arm}").glob("*.json")):
            for result in json.loads(path.read_text()).values():
                raw = result.get("_raw") or {}
                counts[float(raw.get("conflict_score") or 0.0)] += 1
        n = sum(counts.values())
        check(f"§6 {arm} responses", n, n_expected)
        check(f"§6 {arm} distinct scores", len(counts), distinct)
        for value, count, pct in top:
            check(f"§6 {arm} score {value} count", counts[value], count)
            check(f"§6 {arm} score {value} share", round(counts[value] / n * 100, 1),
                  pct, tol=0.05)


def main() -> int:
    res = _results()
    verify_the_defect()
    verify_rule_semantics()
    verify_coverage(res)
    verify_effect(res)
    verify_controller(res)

    print(f"verified   {len(_passed)}")
    print(f"FAILED     {len(_failed)}")
    for f in _failed:
        print(f"  FAIL  {f}")
    if not _failed:
        print("\nEvery claim in DAMPING_FIX_RESULT.md re-derived from the raw data.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
