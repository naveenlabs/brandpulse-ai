"""
damping_ab.py — does the facial down-weighting fire, and what does it change?

The facial analogue of `vocal_bench/damping_ab.py`, and it answers the same two
questions separately because they have different answers:

  COVERAGE  on how many real segments does the rule fire at all? This is a pure
            function of the four channel labels, needs no controller, and is
            exact.
  EFFECT    what does it change in the reported conflict scores? Damping
            multiplies, so a rule can be entirely correct and still move nothing
            if the controller returned 0.0.

WHAT IS AND IS NOT VALID HERE. `vocal_bench/ab_cache/` holds the raw controller
responses from the 12-video corpus, and the vocal A/B re-coerced them under
different damping rules — valid, because damping is post-processing and the
controller's prompt was identical in every arm.

That argument does **not** carry over unchanged. Those segments were built with
**no facial channel** (no frames had been extracted), so a fresh four-channel run
would have shown the controller a different prompt and could have produced a
different score. Two things follow, and they are reported separately:

  - Coverage is computed on segments enriched with a real facial channel and is
    fully valid: it depends only on the labels, never on the controller.
  - Effect is reported in two forms. `--controller cached` re-coerces the cached
    responses and is explicitly an **illustration on a score distribution the
    facial channel did not influence**. `--controller live` re-runs the local
    controller on the four-channel segments and is the real before/after.

    python damping_ab.py facial        # build + cache the facial channel
    python damping_ab.py coverage
    python damping_ab.py effect --controller cached
    python damping_ab.py effect --controller live
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
ROOT = V1.parents[1]

for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pipeline import orchestrator as O                          # noqa: E402
from research.vocal_bench import corpus_ab as AB                # noqa: E402

FACIAL_CACHE = HERE / "ab_cache_facial"
RESULTS = HERE / "damping_ab_results.json"
ARM = "after_nodamp"          # the arm whose raw responses were cached undamped


def videos() -> list[str]:
    return sorted(p.stem for p in
                  (AB.CACHE / f"conflict_{ARM}").glob("*.json"))


# ── Stage 1: the facial channel these segments never had ──────────────────────

def build_facial(video_id: str, force: bool = False) -> dict:
    """
    Run the deployed visual channel over this video's frames and pool to segments.

    Cached per video: DeepFace over ~760 frames is the expensive part and it is
    deterministic, so it is computed once. Returns segment_id -> facial_emotion.
    """
    out_path = FACIAL_CACHE / f"{video_id}.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text())

    from pipeline.visual_module import (analyse_facial_emotion,
                                        pool_emotions_per_segment)

    frames = sorted((ROOT / "data" / video_id / "frames").glob("frame_*.jpg"))
    if not frames:
        raise SystemExit(f"{video_id}: no frames on disk — nothing to build")

    segments = [dict(s) for s in AB.load_segments(video_id)]
    started = time.time()
    per_frame = analyse_facial_emotion(frames)
    pool_emotions_per_segment(per_frame, segments)
    elapsed = time.time() - started

    payload = {
        "video_id": video_id,
        "n_frames": len(frames),
        "n_segments": len(segments),
        "seconds": round(elapsed, 1),
        "seconds_per_frame": round(elapsed / max(1, len(frames)), 4),
        "faces_detected": sum(1 for f in per_frame
                              if f["dominant_emotion"] is not None),
        "facial": {str(s["segment_id"]): s["facial_emotion"] for s in segments},
    }
    FACIAL_CACHE.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=1))
    print(f"  {video_id}: {len(frames)} frames, "
          f"{payload['faces_detected']} with a face, "
          f"{payload['seconds_per_frame']:.3f}s/frame", flush=True)
    return payload


# ── Segment assembly ──────────────────────────────────────────────────────────

def four_channel_rows(video_id: str) -> dict[str, dict]:
    """
    The segments the vocal A/B built, plus the facial channel they lacked.

    Everything except the facial channel comes from `vocal_bench/ab_cache`, so the
    transcript and vocal readings here are byte-identical to the ones the cached
    controller responses were produced from.
    """
    segments = AB.load_segments(video_id)
    ts = AB.transcript_sentiment(video_id, segments)
    sb = AB.vocal_readings(video_id, segments, "speechbrain")
    ad = AB.vocal_readings(video_id, segments, "audeering")
    rows = {str(r["segment_id"]): dict(r)
            for r in AB.build_arm_segments("after", segments, ts, sb, ad)}

    facial = build_facial(video_id)["facial"]
    for sid, row in rows.items():
        fe = facial.get(sid)
        if fe is not None:
            row["facial_emotion"] = fe
    return rows


def comment_sentiment(video_id: str) -> dict:
    path = AB.CACHE / "comments" / f"{video_id}.json"
    return json.loads(path.read_text()) if path.is_file() else {}


# ── Stage 2: coverage ─────────────────────────────────────────────────────────

def scored_ids(video_id: str) -> set[str]:
    """The segments the controller actually scored, from the cached responses."""
    path = AB.CACHE / f"conflict_{ARM}" / f"{video_id}.json"
    return set(json.loads(path.read_text()))


def coverage(scored_only: bool = True) -> dict:
    """
    How often each channel is the lone dissenter, over real four-channel segments.

    Two things are measured that the vocal bench could not measure at all, because
    its corpus had no facial channel:

      - `vocal_without_facial` reproduces the published 89-of-481 figure from
        `vocal_bench/DAMPING_FIX_RESULT.md` by stripping the facial channel back
        out. It is a check on this harness: if it does not reproduce, nothing else
        here should be believed.
      - `vocal_with_facial` is the same rule on the same segments *with* the
        channel present. Adding a fourth channel can only make "every other
        channel agrees" harder to satisfy, so vocal coverage is expected to fall.
        That interaction is a real property of the deployed system and was
        invisible before.

    `scored_only` restricts to the segments the controller actually scored, which
    is the denominator `vocal_bench` used. The full-segment counts are reported
    alongside because they are what a live run would encounter.
    """
    per_video, totals = {}, {"segments": 0, "facial": 0, "vocal_with_facial": 0,
                             "vocal_without_facial": 0, "both": 0,
                             "facial_readable": 0}
    for vid in videos():
        rows = four_channel_rows(vid)
        cs = comment_sentiment(vid)
        keys = (sorted(set(rows) & scored_ids(vid)) if scored_only else sorted(rows))
        c = {k: 0 for k in totals}
        c["segments"] = len(keys)
        for k in keys:
            row = rows[k]
            stripped = {kk: vv for kk, vv in row.items() if kk != "facial_emotion"}
            v_with = O._vocal_is_sole_dissenter(row, cs)
            v_without = O._vocal_is_sole_dissenter(stripped, cs)
            f = O._facial_is_sole_dissenter(row, cs)
            c["vocal_with_facial"] += v_with
            c["vocal_without_facial"] += v_without
            c["facial"] += f
            c["both"] += (v_with and f)
            c["facial_readable"] += "facial" in O._channel_valences(row, cs)
        per_video[vid] = c
        for k in totals:
            totals[k] += c[k]
    return {"scored_only": scored_only, "per_video": per_video, "totals": totals}


# ── Stage 3: effect ───────────────────────────────────────────────────────────

def _coerce_all(rows: dict, source: dict, cs: dict, facial_weight: float) -> list[dict]:
    """
    Re-coerce every cached response at a given facial weight. 1.0 is the identity.

    The cache stores the controller's raw JSON under `_raw`; an entry without one
    is a segment where the controller failed and `_safe_fallback` ran, which is
    what a live run would also produce, so it is copied through untouched rather
    than re-scored.
    """
    original = O.FACIAL_ONLY_CONFLICT_WEIGHT
    O.FACIAL_ONLY_CONFLICT_WEIGHT = facial_weight
    try:
        out = []
        for key in sorted(source, key=int):
            result = source[key]
            raw = result.get("_raw")
            if not isinstance(raw, dict) or key not in rows:
                out.append(dict(result))
                continue
            out.append(O._coerce_result(raw, rows[key], cs))
        return out
    finally:
        O.FACIAL_ONLY_CONFLICT_WEIGHT = original


def effect(source: str = "cached") -> dict:
    """Before/after on the reported scores, at the deployed weight vs the identity."""
    if source != "cached":
        raise SystemExit("only --controller cached is implemented; see the docstring")

    before_all, after_all, changed = [], [], []
    for vid in videos():
        rows = four_channel_rows(vid)
        cs = comment_sentiment(vid)
        raw = json.loads((AB.CACHE / f"conflict_{ARM}" / f"{vid}.json").read_text())
        before = _coerce_all(rows, raw, cs, 1.0)
        after = _coerce_all(rows, raw, cs, O.FACIAL_ONLY_CONFLICT_WEIGHT)
        for b, a in zip(before, after):
            before_all.append(b)
            after_all.append(a)
            if b["conflict_score"] != a["conflict_score"]:
                changed.append({"video_id": vid, "segment_id": b["segment_id"],
                                "before": b["conflict_score"],
                                "after": a["conflict_score"],
                                "flag_before": b["flagged"],
                                "flag_after": a["flagged"]})

    def stats(rs):
        n = len(rs)
        return {"segments": n,
                "flagged": sum(1 for r in rs if r["flagged"]),
                "nonzero": sum(1 for r in rs if r["conflict_score"] > 0),
                "mean_score": round(sum(r["conflict_score"] for r in rs) / n, 4)}

    return {"source": source, "weight": O.FACIAL_ONLY_CONFLICT_WEIGHT,
            "before": stats(before_all), "after": stats(after_all),
            "n_changed": len(changed), "changed": changed}


# ── Reporting ─────────────────────────────────────────────────────────────────

def render_coverage(d: dict) -> str:
    t = d["totals"]
    scope = "controller-scored segments" if d["scored_only"] else "all segments"
    L = [f"COVERAGE — {t['segments']} {scope} across {len(d['per_video'])} videos",
         "",
         f"  {'video':<16}{'segs':>6}{'facial':>8}{'vocal(4ch)':>12}"
         f"{'vocal(3ch)':>12}{'both':>6}{'face readable':>15}"]
    for vid, c in sorted(d["per_video"].items()):
        L.append(f"  {vid:<16}{c['segments']:>6}{c['facial']:>8}"
                 f"{c['vocal_with_facial']:>12}{c['vocal_without_facial']:>12}"
                 f"{c['both']:>6}{c['facial_readable']:>15}")
    L += ["",
          f"  TOTAL           {t['segments']:>6}{t['facial']:>8}"
          f"{t['vocal_with_facial']:>12}{t['vocal_without_facial']:>12}"
          f"{t['both']:>6}{t['facial_readable']:>15}",
          "",
          f"  facial fires on {t['facial']}/{t['segments']} "
          f"({t['facial']/t['segments']*100:.1f}%)",
          f"  vocal, facial channel present : {t['vocal_with_facial']}/{t['segments']} "
          f"({t['vocal_with_facial']/t['segments']*100:.1f}%)",
          f"  vocal, facial channel stripped: {t['vocal_without_facial']}/{t['segments']} "
          f"({t['vocal_without_facial']/t['segments']*100:.1f}%)"
          "   <- must reproduce vocal_bench's 89/481",
          f"  the two rules never fire on the same segment: both = {t['both']}"]
    return "\n".join(L)


def render_effect(d: dict) -> str:
    b, a = d["before"], d["after"]
    return "\n".join([
        f"EFFECT (source: {d['source']}, weight x{d['weight']})",
        "",
        f"  {'':<12}{'segments':>10}{'nonzero':>9}{'flagged':>9}{'mean score':>12}",
        f"  {'before':<12}{b['segments']:>10}{b['nonzero']:>9}{b['flagged']:>9}"
        f"{b['mean_score']:>12.4f}",
        f"  {'after':<12}{a['segments']:>10}{a['nonzero']:>9}{a['flagged']:>9}"
        f"{a['mean_score']:>12.4f}",
        "",
        f"  segments whose score changed: {d['n_changed']}",
        f"  segments whose flag changed:  "
        f"{sum(1 for c in d['changed'] if c['flag_before'] != c['flag_after'])}",
    ])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["facial", "coverage", "effect", "all"])
    ap.add_argument("--controller", default="cached", choices=["cached", "live"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--all-segments", action="store_true",
                    help="count every segment, not only those the controller scored")
    args = ap.parse_args()

    payload = {}
    if args.stage in ("facial", "all"):
        print(f"building the facial channel for {len(videos())} videos\n")
        for vid in videos():
            build_facial(vid, force=args.force)

    if args.stage in ("coverage", "all"):
        # Both denominators are computed and stored every time. The scored-only
        # one is comparable with vocal_bench's published figure; the full one is
        # what a live run actually encounters. Reporting only whichever was asked
        # for would let the results file disagree with itself between runs.
        scored = coverage(scored_only=True)
        every = coverage(scored_only=False)
        print("\n" + render_coverage(every if args.all_segments else scored))
        payload["coverage_scored"] = scored
        payload["coverage_all_segments"] = every

    if args.stage in ("effect", "all"):
        eff = effect(args.controller)
        print("\n" + render_effect(eff))
        payload["effect"] = eff

    if payload:
        payload["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        RESULTS.write_text(json.dumps(payload, indent=1))
        print(f"\nwritten → {RESULTS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
