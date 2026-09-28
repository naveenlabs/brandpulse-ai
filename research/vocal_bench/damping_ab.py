"""
damping_ab.py - does the rewritten vocal down-weighting actually fire, and what
does it change?

BACKGROUND. `CORPUS_AB_RESULT.md` §3.2 measured the original down-weighting firing
on **0 of 479 segments**. It asked the controller which channels it thought were in
conflict; llama3.2 answers that question but decouples it from its own score, so
the rule had nothing to act on. The trigger was rewritten on 02 Sep 2026 to read
the pipeline's own channel labels instead (`orchestrator._vocal_is_sole_dissenter`).
This measures the rewrite.

NO CONTROLLER CALLS. The A/B cached every raw controller response in
`ab_cache/conflict_after_nodamp/`. Damping is pure post-processing applied inside
`_coerce_result`, so re-coercing those same responses under a different rule
reproduces exactly what a fresh run would have produced - the same property
`corpus_ab.derive_arm` already relies on, and `verify_ab.py` already checks. This
script therefore costs seconds, not the eight hours the original A/B took.

FOUR VARIANTS, one shared set of raw responses:

  nodamp            weight 1.0, the identity - the baseline both others move from
  attributed        the original rule: the controller's own attribution only
  structural_min1   the new rule, one corroborating channel required
  structural_min2   the new rule, two corroborating channels required (proposed)

TWO SEPARATE QUESTIONS, reported separately because they have different answers:

  1. COVERAGE - on how many segments does the rule fire at all? This is what the
     0-of-479 defect was about, and it is measured over every segment.
  2. EFFECT - what does it change in the reported scores? This is bounded by
     something outside the rule's control: llama3.2 returned conflict_score 0.0
     for 473 of 481 segments, and damping multiplies. A rule can be entirely
     correct and still move nothing here.

    python research/vocal_bench/damping_ab.py
    python research/vocal_bench/damping_ab.py --json damping_ab_results.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(BENCH))

CACHE = BENCH / "ab_cache"
RESULTS_OUT = BENCH / "damping_ab_results.json"

# Which cached arm's raw controller responses to re-coerce.
#
#   after_nodamp  the deployed configuration (audeering + the current prompt).
#                 The arm that matters, but llama3.2 scored 473 of its 481
#                 segments at exactly 0.0, so it can show coverage and almost no
#                 score effect.
#   before        the pre-swap configuration (speechbrain + the legacy prompt).
#                 Not what is deployed, but its 496 responses include 232 with a
#                 non-zero score, so it is the only cached arena where a damping
#                 rule has enough to act on for its effect to be visible at all.
#
# Both are real cached controller output. Neither is simulated.
SOURCE_ARMS = ("after_nodamp", "before")
DEFAULT_ARM = "after_nodamp"

# variant -> (vocal weight, minimum corroborating channels or None to disable the
#             structural trigger entirely)
VARIANTS: dict[str, tuple[float, int | None]] = {
    "nodamp":          (1.0,   None),
    "attributed":      (0.489, None),
    "structural_min1": (0.489, 1),
    "structural_min2": (0.489, 2),
}
BASELINE = "nodamp"
PROPOSED = "structural_min2"

# Disabling the structural trigger without deleting the code path: a segment can
# never have this many other channels, so the rule is reachable but unsatisfiable.
# Preferred over monkeypatching the function, which would stop testing the real one.
_STRUCTURAL_OFF = 99


def videos(source_arm: str) -> list[str]:
    return sorted(p.stem for p in (CACHE / f"conflict_{source_arm}").glob("*.json"))


def load_rows(video_id: str, arm: str) -> dict[str, dict]:
    """Enriched segments for one video, exactly as that A/B arm built them.

    Rebuilt through corpus_ab so the channel wiring cannot drift between the two
    scripts; the caches it reads are the ones the A/B already wrote. The arm
    decides which vocal model's readings are attached, which is what the damping
    rule reads, so it must match the arm whose responses are being re-coerced.
    """
    import corpus_ab as AB

    arm_key = "before" if arm == "before" else "after"
    segments = AB.load_segments(video_id)
    ts = AB.transcript_sentiment(video_id, segments)
    ad = AB.vocal_readings(video_id, segments, "audeering")
    # `sb` is unused by the "after" arm but build_arm_segments takes both; the
    # cached speechbrain readings are read rather than recomputed.
    sb = AB.vocal_readings(video_id, segments, "speechbrain")
    rows = AB.build_arm_segments(arm_key, segments, ts, sb, ad)
    return {str(r["segment_id"]): r for r in rows}


def comment_sentiment(video_id: str) -> dict:
    path = CACHE / "comments" / f"{video_id}.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def recoerce(video_id: str, variant: str, arm: str) -> list[dict]:
    """Re-coerce one video's cached raw responses under one variant's rule."""
    from pipeline import orchestrator as O

    weight, min_corroborating = VARIANTS[variant]
    source = json.loads((CACHE / f"conflict_{arm}" / f"{video_id}.json").read_text())
    rows = load_rows(video_id, arm)
    cs = comment_sentiment(video_id)

    old_weight = O.VOCAL_ONLY_CONFLICT_WEIGHT
    old_min = O.MIN_CORROBORATING_CHANNELS
    O.VOCAL_ONLY_CONFLICT_WEIGHT = weight
    O.MIN_CORROBORATING_CHANNELS = (_STRUCTURAL_OFF if min_corroborating is None
                                    else min_corroborating)
    try:
        out = []
        for key in sorted(source, key=int):
            result = source[key]
            raw = result.get("_raw")
            if not isinstance(raw, dict) or key not in rows:
                # No raw JSON to re-coerce: the source arm's fallback is what the
                # live pipeline would also have produced. Copied through unchanged.
                out.append({**result, "_source_score": result["conflict_score"]})
                continue
            coerced = O._coerce_result(raw, rows[key], cs)
            coerced["_source_score"] = float(raw.get("conflict_score") or 0.0)
            out.append(coerced)
        return out
    finally:
        O.VOCAL_ONLY_CONFLICT_WEIGHT = old_weight
        O.MIN_CORROBORATING_CHANNELS = old_min


def coverage(video_id: str, min_corroborating: int, arm: str) -> dict:
    """How often the structural rule fires, over EVERY segment.

    Independent of the controller's score, because coverage is a property of the
    channel labels alone. This is the number the 0-of-479 defect was about.
    """
    from pipeline import orchestrator as O

    rows = load_rows(video_id, arm)
    cs = comment_sentiment(video_id)
    source = json.loads((CACHE / f"conflict_{arm}" / f"{video_id}.json").read_text())

    old_min = O.MIN_CORROBORATING_CHANNELS
    O.MIN_CORROBORATING_CHANNELS = min_corroborating
    try:
        fires = nonzero_fires = n = corroborators = 0
        for key in sorted(source, key=int):
            if key not in rows:
                continue
            n += 1
            others = O._channel_valences(rows[key], cs)
            corroborators += len([k for k in others if k != "vocal"])
            if O._vocal_is_sole_dissenter(rows[key], cs):
                fires += 1
                raw = source[key].get("_raw") or {}
                if float(raw.get("conflict_score") or 0.0) > 0.0:
                    nonzero_fires += 1
        return {"n": n, "fires": fires, "fires_on_a_nonzero_score": nonzero_fires,
                "mean_corroborators": round(corroborators / n, 3) if n else 0.0}
    finally:
        O.MIN_CORROBORATING_CHANNELS = old_min


def score(video_id: str, results: list[dict], arm: str) -> dict:
    from pipeline.scorer import build_final_report

    rows = load_rows(video_id, arm)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    segs = [rows[str(r["segment_id"])] for r in clean if str(r["segment_id"]) in rows]
    report = build_final_report(
        f"https://youtu.be/{video_id}", "damping-ab", segs, clean,
        comment_sentiment(video_id))
    scores = [r["conflict_score"] for r in results]
    return {
        "authenticity": report["authenticity_score"],
        "brand_health": report["brand_health_score"],
        "flagged": sum(1 for r in results if r["flagged"]),
        "n": len(results),
        "mean_conflict": round(statistics.mean(scores), 4) if scores else 0.0,
        "nonzero": sum(1 for s in scores if s > 0),
        "damped": sum(1 for r in results
                      if any("downweighted" in x for x in r["conflict_reasons"])),
    }


def run(arm: str) -> dict:
    vids = videos(arm)
    if not vids:
        raise RuntimeError(f"no cached responses under {CACHE / f'conflict_{arm}'}")

    per_video: dict[str, dict] = {}
    for v in vids:
        per_video[v] = {
            "score": {var: score(v, recoerce(v, var, arm), arm) for var in VARIANTS},
            "coverage": {f"min{m}": coverage(v, m, arm) for m in (1, 2)},
        }

    totals: dict[str, dict] = {}
    for var in VARIANTS:
        rows = [per_video[v]["score"][var] for v in vids]
        n = sum(r["n"] for r in rows)
        totals[var] = {
            "videos": len(rows),
            "segments": n,
            "authenticity": round(statistics.mean(r["authenticity"] for r in rows), 2),
            "brand_health": round(statistics.mean(r["brand_health"] for r in rows), 2),
            "flagged": sum(r["flagged"] for r in rows),
            "damped": sum(r["damped"] for r in rows),
            "nonzero": sum(r["nonzero"] for r in rows),
            "mean_conflict": round(
                sum(r["mean_conflict"] * r["n"] for r in rows) / n, 4),
        }

    cov = {}
    for m in (1, 2):
        rows = [per_video[v]["coverage"][f"min{m}"] for v in vids]
        n = sum(r["n"] for r in rows)
        fires = sum(r["fires"] for r in rows)
        cov[f"min{m}"] = {
            "segments": n,
            "fires": fires,
            "fires_pct": round(fires / n * 100, 1) if n else 0.0,
            "fires_on_a_nonzero_score": sum(r["fires_on_a_nonzero_score"] for r in rows),
            "mean_corroborating_channels": round(
                sum(r["mean_corroborators"] * r["n"] for r in rows) / n, 3) if n else 0.0,
        }

    deltas = {}
    for var in VARIANTS:
        if var == BASELINE:
            continue
        deltas[var] = {
            "authenticity": round(totals[var]["authenticity"]
                                  - totals[BASELINE]["authenticity"], 2),
            "brand_health": round(totals[var]["brand_health"]
                                  - totals[BASELINE]["brand_health"], 2),
            "flagged": totals[var]["flagged"] - totals[BASELINE]["flagged"],
            "videos_changed": sum(
                1 for v in vids
                if per_video[v]["score"][var]["authenticity"]
                != per_video[v]["score"][BASELINE]["authenticity"]),
        }

    return {"source_arm": arm, "videos": vids, "per_video": per_video,
            "totals": totals, "coverage": cov, "deltas": deltas,
            "baseline": BASELINE, "proposed": PROPOSED}


def render(d: dict) -> str:
    L = ["", f"SOURCE ARM: {d['source_arm']}  ({len(d['videos'])} videos)",
         "",
         "COVERAGE - does the rule fire at all? (independent of the score)",
         "-" * 78,
         f"{'setting':<16} {'segments':>9} {'fires':>7} {'fires %':>9} "
         f"{'on a nonzero score':>19} {'mean corroborators':>19}"]
    for k, c in d["coverage"].items():
        L.append(f"{k:<16} {c['segments']:>9} {c['fires']:>7} {c['fires_pct']:>8.1f}% "
                 f"{c['fires_on_a_nonzero_score']:>19} "
                 f"{c['mean_corroborating_channels']:>19.3f}")
    L += ["",
          "The original rule fired on 0 of 479 (CORPUS_AB_RESULT.md §3.2).",
          "",
          "EFFECT ON THE REPORTED SCORES",
          "-" * 78,
          f"{'variant':<18} {'authenticity':>13} {'brand health':>13} "
          f"{'flagged':>8} {'damped':>7} {'mean conflict':>14}"]
    for var, t in d["totals"].items():
        tag = "  <-- baseline" if var == d["baseline"] else (
            "  <-- proposed" if var == d["proposed"] else "")
        L.append(f"{var:<18} {t['authenticity']:>13.2f} {t['brand_health']:>13.2f} "
                 f"{t['flagged']:>8} {t['damped']:>7} {t['mean_conflict']:>14.4f}{tag}")
    L += ["", f"{'vs baseline':<18} {'d auth':>13} {'d health':>13} {'d flagged':>8} "
              f"{'videos changed':>22}"]
    for var, x in d["deltas"].items():
        L.append(f"{var:<18} {x['authenticity']:>+13.2f} {x['brand_health']:>+13.2f} "
                 f"{x['flagged']:>+8} {x['videos_changed']:>22}")
    t = d["totals"][d["baseline"]]
    L += ["",
          f"CEILING: {t['nonzero']} of {t['segments']} segments carry a conflict score "
          f"above 0.0.",
          "Damping multiplies, so no rule can change the other "
          f"{t['segments'] - t['nonzero']}.",
          ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=SOURCE_ARMS + ("both",), default="both",
                    help="which cached arm's raw responses to re-coerce")
    ap.add_argument("--json", type=Path, default=RESULTS_OUT,
                    help="write the full result here")
    args = ap.parse_args()

    arms = SOURCE_ARMS if args.arm == "both" else (args.arm,)
    out = {}
    for arm in arms:
        result = run(arm)
        out[arm] = result
        print(render(result))
    args.json.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"written: {args.json.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
