"""
corpus_ab.py - does the vocal-channel swap change the scores the system reports?

The bench in this directory measured the vocal channel against human ratings. It
could not answer the question that actually matters to the product, which
`CANDIDATE_MODELS.md` §9 recorded as out of scope before any result was seen:

    "Whether a better vocal channel improves the final Authenticity/Brand Health
     scores is a separate question this bench cannot answer [...] Measuring that
     properly needs a corpus re-run after adoption, and is follow-up work."

This is that follow-up. It is a controlled A/B, not a re-run: every input except
the vocal channel is computed ONCE and shared byte-for-byte across arms, so a
difference in the final score cannot come from anything else. Whisper is not
re-run, transcript sentiment is not recomputed per arm, comment sentiment is
fetched once, and the controller is called with temperature 0 and a fixed seed.

Three arms, because "before vs after" alone cannot attribute the change:

  before        speechbrain categorical  + legacy prompt + no damping
                (the pipeline exactly as deployed until 02 Sep 2026)
  after         audeering arousal        + new prompt    + damping
                (the pipeline as deployed from 02 Sep 2026)
  after_nodamp  audeering arousal        + new prompt    + NO damping
                (ablation: isolates the model/dimension swap from the damping)

  after - before        = the total effect of the change
  after_nodamp - before = the part attributable to the model and dimension swap
  after - after_nodamp  = the part attributable to the down-weighting

WHAT THIS CANNOT SEE. The corpus videos have audio only, no extracted frames, so
the facial channel is absent in all three arms. It is absent identically, so it
cannot bias the comparison, but it does mean these numbers describe a three-channel
system. Stated again in the results write-up rather than left to be discovered.

Every stage caches to disk and the run resumes where it stopped: the controller
pass is ~4 s per segment per arm and there are 1,863 segments.

    python research/vocal_bench/corpus_ab.py --prepare          # channels only, no LLM
    python research/vocal_bench/corpus_ab.py --limit 20         # pilot: 20 segments/video
    python research/vocal_bench/corpus_ab.py                    # full run
    python research/vocal_bench/corpus_ab.py --report           # score what is cached
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(BENCH))

# The comment channel needs YOUTUBE_API_KEY. app.py and main.py load .env at
# their own entry points; a bench script is neither, so it loads it here. The key
# is read from the environment and never printed, logged or cached.
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT / ".env")
except ImportError:  # pragma: no cover - python-dotenv is a project dependency
    pass

CORPUS = PROJECT / "research" / "transcript_bench" / "corpus"
DATA = PROJECT / "data"
CACHE = BENCH / "ab_cache"

ARMS = ("before", "after", "after_nodamp")

# Only two of the three arms need the controller. `after` and `after_nodamp` send
# byte-identical payloads under the same prompt, model, temperature 0 and seed 42,
# so they receive byte-identical responses; they differ only in a multiplication
# applied afterwards in `_coerce_result`. Deriving one from the other's cached raw
# response is therefore exact, not an approximation - and it removes a third of
# the run time (1,863 segments x 4 s) for no loss of evidence.
#
# It also demonstrates the property directly: if the damping were not pure
# post-processing, this could not work.
LLM_ARMS = ("before", "after_nodamp")
DERIVED_FROM = {"after": "after_nodamp"}

# Arms differ only in these three switches. Nothing else in the pipeline is
# touched, and the table is the definition of the experiment.
ARM_SPEC = {
    "before":       {"vocal": "speechbrain", "prompt": "legacy", "damping": False},
    "after":        {"vocal": "audeering",   "prompt": "new",    "damping": True},
    "after_nodamp": {"vocal": "audeering",   "prompt": "new",    "damping": False},
}


# ───────────────────────────────────────────────────────── shared channel inputs

def corpus_videos() -> list[str]:
    return sorted(p.stem for p in CORPUS.glob("*.json"))


def load_segments(video_id: str) -> list[dict]:
    """Segments exactly as transcript_bench produced them - Whisper is not re-run."""
    doc = json.loads((CORPUS / f"{video_id}.json").read_text())
    return [{"segment_id": s["segment_id"], "start_time": s["start_time"],
             "end_time": s["end_time"], "text": s["text"]} for s in doc["segments"]]


def _cached(path: Path, build):
    if path.is_file():
        return json.loads(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    value = build()
    path.write_text(json.dumps(value, indent=1))
    return value


def transcript_sentiment(video_id: str, segments: list[dict]) -> dict:
    """Computed once and shared by all arms - it is not part of the manipulation."""
    def build():
        from pipeline.audio_module import add_transcript_sentiment
        rows = [dict(s) for s in segments]
        add_transcript_sentiment(rows)
        return {str(r["segment_id"]): r["transcript_sentiment"] for r in rows}
    return _cached(CACHE / "transcript" / f"{video_id}.json", build)


def vocal_readings(video_id: str, segments: list[dict], model: str) -> dict:
    """Per-segment vocal reading from one of the two models.

    `speechbrain` reproduces the pre-swap pipeline via the bench's own historical
    copy of that code (`candidates.run_speechbrain`), sliced to the same segment
    windows the live pipeline used. `audeering` calls the live pipeline function
    directly, so the "after" arm is the deployed code path and not a restatement
    of it.
    """
    def build():
        from pipeline import audio_module as A
        audio = DATA / video_id / "audio.wav"
        if not audio.is_file():
            raise FileNotFoundError(f"no audio for {video_id}: {audio}")

        if model == "audeering":
            rows = [dict(s) for s in segments]
            A.analyse_vocal_emotion(audio, rows)
            return {str(r["segment_id"]): r["vocal_emotion"] for r in rows}

        # speechbrain: slice to a temp wav per segment, as the bench does.
        import candidates as C
        import scipy.io.wavfile as wavfile
        import tempfile, os
        d16, sr = A._load_wav_int16(audio)
        out = {}
        for s in segments:
            dur = s["end_time"] - s["start_time"]
            if dur < A.MIN_SEGMENT_DURATION_S:
                out[str(s["segment_id"])] = "unknown"
                continue
            sl = A._slice_int16(d16, sr, s["start_time"], s["end_time"])
            if len(sl) == 0:
                out[str(s["segment_id"])] = "unknown"
                continue
            fd, tmp = tempfile.mkstemp(suffix=".wav"); os.close(fd)
            try:
                wavfile.write(tmp, sr, sl)
                out[str(s["segment_id"])] = C.run_speechbrain(Path(tmp))["raw_label"] or "unknown"
            except Exception:
                out[str(s["segment_id"])] = "unknown"
            finally:
                os.unlink(tmp)
        return out
    return _cached(CACHE / f"vocal_{model}" / f"{video_id}.json", build)


def comment_sentiment(video_id: str) -> dict:
    """Video-level comment sentiment, fetched once and shared by all arms.

    Failure here is not fatal: a video with comments disabled, or an exhausted
    quota, yields the same empty dict the live pipeline degrades to, and it is
    identical across arms either way.
    """
    def build():
        try:
            from pipeline.comment_module import (
                fetch_comments, classify_comment_sentiment, aggregate_video_sentiment)
            comments = fetch_comments(video_id, max_results=100)
            if not comments:
                return {"label": "UNKNOWN", "confidence": 0.0, "_note": "no comments returned"}
            classified = classify_comment_sentiment(comments)
            return aggregate_video_sentiment(classified)
        except Exception as exc:
            return {"label": "UNKNOWN", "confidence": 0.0, "_note": f"fetch failed: {exc}"}
    return _cached(CACHE / "comments" / f"{video_id}.json", build)


# ─────────────────────────────────────────────────────────────── the controller

def _legacy_prompt(current: str) -> str:
    """The system prompt as it stood before the vocal swap.

    Derived by removing the block added on 02 Sep 2026 rather than pasted, so the
    two prompts cannot silently drift apart. The assertion is the safeguard: if
    the marker ever moves, this fails loudly instead of quietly benching the
    wrong prompt.
    """
    marker = "\n\nCHANNEL RELIABILITY."
    assert marker in current, "prompt marker missing - _legacy_prompt needs updating"
    return current.split(marker)[0]


def systematic_sample(rows: list[dict], n: int | None) -> list[dict]:
    """Take n segments evenly spaced across the video, or all of them.

    Systematic rather than "the first n". A video's opening segments are its
    intro and hook - systematically shorter, more energetic and less
    representative than its body - so truncating would bias the vocal channel's
    arousal readings, which is precisely the quantity under test.

    Evenly spaced rather than randomly sampled because it is deterministic
    without needing a seed, and it guarantees coverage of the whole timeline
    rather than merely expecting it.
    """
    if not n or n >= len(rows):
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def build_arm_segments(arm: str, segments: list[dict], ts: dict,
                       sb: dict, ad: dict) -> list[dict]:
    """Attach this arm's vocal reading to a fresh copy of the shared segments."""
    use_sb = ARM_SPEC[arm]["vocal"] == "speechbrain"
    rows = []
    for s in segments:
        key = str(s["segment_id"])
        row = dict(s)
        row["transcript_sentiment"] = ts[key]
        row["vocal_emotion"] = sb[key] if use_sb else ad[key]
        rows.append(row)
    return rows


def orchestrate_arm(arm: str, video_id: str, rows: list[dict], cs: dict,
                    limit: int | None) -> dict:
    """Run the controller over one arm of one video, resuming from cache."""
    from pipeline import orchestrator as O

    path = CACHE / f"conflict_{arm}" / f"{video_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = json.loads(path.read_text()) if path.is_file() else {}

    spec = ARM_SPEC[arm]
    original_prompt = O._SYSTEM_PROMPT
    original_weight = O.VOCAL_ONLY_CONFLICT_WEIGHT
    if spec["prompt"] == "legacy":
        O._SYSTEM_PROMPT = _legacy_prompt(original_prompt)
    if not spec["damping"]:
        # 1.0 is the identity, i.e. exactly the pre-swap behaviour: the damping
        # branch still runs but changes nothing, so the ablation isolates the
        # weight and not the surrounding code path.
        O.VOCAL_ONLY_CONFLICT_WEIGHT = 1.0

    target = systematic_sample(rows, limit)
    try:
        for i, row in enumerate(target):
            key = str(row["segment_id"])
            if key in done:
                continue
            payload_seg = row
            if spec["prompt"] == "legacy":
                # The legacy payload had no vocal_reliability key at all. Dropping
                # it keeps the "before" arm a faithful reproduction rather than the
                # new payload with one field blanked.
                payload_seg = dict(row)
            result = _analyse(O, payload_seg, cs, drop_reliability=(spec["prompt"] == "legacy"))
            done[key] = result
            if i % 20 == 0:
                path.write_text(json.dumps(done, indent=1))
    finally:
        O._SYSTEM_PROMPT = original_prompt
        O.VOCAL_ONLY_CONFLICT_WEIGHT = original_weight
        path.write_text(json.dumps(done, indent=1))
    return done


def _analyse(O, segment: dict, cs: dict, drop_reliability: bool) -> dict:
    """orchestrator.analyse_segment, with the one payload edit the arms need.

    Reimplemented here rather than called, because the "before" arm must send the
    exact payload the pre-swap pipeline sent and `analyse_segment` has no seam for
    removing a key. Everything else - the call, the parse, the coercion, the
    fallbacks - is the production function, imported not copied.
    """
    try:
        payload = O.build_segment_payload(segment)
    except Exception:
        return O._safe_fallback(segment, "payload_error")
    if drop_reliability:
        payload.pop("vocal_reliability", None)

    c = cs or {}
    payload["video_comment_sentiment"] = (
        f"{c.get('label', 'UNKNOWN')} ({float(c.get('confidence', 0.0) or 0.0):.2f})")

    try:
        raw = O._call_ollama(json.dumps(payload))
    except Exception:
        out = O._safe_fallback(segment, "parse_error")
        out["_raw"] = None
        return out
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        out = O._safe_fallback(segment, "parse_error")
        out["_raw"] = raw
        return out
    out = O._coerce_result(data, segment)
    # The controller's own JSON is kept so a derived arm can be re-coerced under a
    # different damping weight without calling the model again, and so any figure
    # in the write-up can be traced back to what the model actually said.
    out["_raw"] = data
    return out


# ─────────────────────────────────────────────────── input-level divergence

# The pre-swap pipeline handed the controller a bare IEMOCAP word and left it to
# infer a valence direction unprompted. This is that inference made explicit, so
# the two arms' vocal readings can be compared in one vocabulary. It is the same
# mapping vocal_bench/report_bench.py scored the incumbent under, so the
# divergence below is measured on the same terms as the 34.0% figure.
_LEGACY_TO_CLASS = {
    "happy": "POSITIVE", "neutral": "NEUTRAL",
    "angry": "NEGATIVE", "sad": "NEGATIVE", "unknown": "unknown",
}


def channel_divergence(shared: dict) -> dict:
    """How often do the two vocal models actually disagree, before any LLM runs?

    This is worth measuring separately because it bounds everything downstream: if
    the two arms hand the controller the same reading on nearly every segment, no
    difference in the final score is possible, and a null result would then say
    nothing about the swap. Reported whatever it shows.
    """
    from collections import Counter
    before, after, changed, total = Counter(), Counter(), Counter(), 0
    for _vid, (segs, _ts, sb, ad, _cs) in shared.items():
        for seg in segs:
            k = str(seg["segment_id"])
            b = _LEGACY_TO_CLASS.get(str(sb[k]).lower(), "unknown")
            a = ad[k]["label"] if isinstance(ad[k], dict) else "unknown"
            before[b] += 1
            after[a] += 1
            if a != b:
                changed[f"{b} -> {a}"] += 1
            total += 1
    return {"n": total, "before": dict(before), "after": dict(after),
            "changed": dict(changed.most_common()),
            "n_changed": sum(changed.values())}


# ────────────────────────────────────────────────────────────────────── scoring

def derive_arm(arm: str, video_id: str, rows: list[dict]) -> None:
    """Re-coerce a source arm's cached raw responses under this arm's damping.

    No controller call. The source arm ran with VOCAL_ONLY_CONFLICT_WEIGHT = 1.0
    (the identity), so re-coercing the same raw JSON with the real weight yields
    exactly what a separate run would have produced.

    A segment whose raw response was never captured (an unreachable controller, or
    unparseable output) has no JSON to re-coerce; its source-arm fallback is copied
    through unchanged, which is what the live pipeline would also have produced.
    """
    from pipeline import orchestrator as O

    src = CACHE / f"conflict_{DERIVED_FROM[arm]}" / f"{video_id}.json"
    if not src.is_file():
        return
    source = json.loads(src.read_text())
    by_id = {str(r["segment_id"]): r for r in rows}

    out = {}
    for key, result in source.items():
        raw = result.get("_raw")
        if not isinstance(raw, dict) or key not in by_id:
            out[key] = result
            continue
        coerced = O._coerce_result(raw, by_id[key])
        coerced["_raw"] = raw
        out[key] = coerced

    dst = CACHE / f"conflict_{arm}" / f"{video_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1))


def score_arm(arm: str, video_id: str, rows: list[dict], cs: dict) -> dict | None:
    from pipeline.scorer import build_final_report

    path = CACHE / f"conflict_{arm}" / f"{video_id}.json"
    if not path.is_file():
        return None
    done = json.loads(path.read_text())
    ids = {str(r["segment_id"]) for r in rows}
    results = [done[k] for k in sorted(done, key=int) if k in ids]
    if not results:
        return None
    scored_ids = {r["segment_id"] for r in results}
    segs = [r for r in rows if r["segment_id"] in scored_ids]
    rep = build_final_report(f"https://youtu.be/{video_id}", "corpus-ab", segs, results, cs)
    return {
        "authenticity": rep["authenticity_score"],
        "brand_health": rep["brand_health_score"],
        "n_segments": len(results),
        "n_flagged": len(rep["flagged_segments"]),
        "mean_conflict": round(sum(r["conflict_score"] for r in results) / len(results), 4),
        "nonzero_conflict": sum(1 for r in results if r["conflict_score"] > 0),
        "damped": sum(1 for r in results
                      if any("vocal_channel_downweighted" in str(x)
                             for x in r.get("conflict_reasons", []))),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int,
                    help="segments per video per arm, sampled evenly across the "
                         "video rather than truncated (see systematic_sample)")
    ap.add_argument("--prepare", action="store_true", help="channels only, no controller")
    ap.add_argument("--report", action="store_true", help="score what is cached, run nothing")
    ap.add_argument("--videos", nargs="*", help="restrict to these video ids")
    ap.add_argument("--json", type=Path, help="write the results table here")
    args = ap.parse_args()

    videos = args.videos or corpus_videos()
    print(f"corpus: {len(videos)} videos\n")

    shared, started = {}, time.time()
    for vid in videos:
        segs = load_segments(vid)
        ts = transcript_sentiment(vid, segs)
        sb = vocal_readings(vid, segs, "speechbrain")
        ad = vocal_readings(vid, segs, "audeering")
        cs = comment_sentiment(vid)
        shared[vid] = (segs, ts, sb, ad, cs)
        print(f"  {vid}  {len(segs):4d} segs  comments={cs.get('label','?'):8s}"
              f" ({cs.get('confidence',0):.2f})")
    print(f"\nchannel inputs ready in {time.time()-started:.0f}s")

    div = channel_divergence(shared)
    print(f"\nVOCAL READING, before vs after ({div['n']} segments)")
    print(f"  before (speechbrain, mapped): {div['before']}")
    print(f"  after  (audeering, arousal) : {div['after']}")
    print(f"  segments whose reading changed: {div['n_changed']} "
          f"({100*div['n_changed']/div['n']:.1f}%)")
    for move, n in div["changed"].items():
        print(f"    {move:24s} {n:5d}")

    if args.prepare:
        if args.json:
            args.json.write_text(json.dumps({"_divergence": div}, indent=1))
            print(f"\nwrote {args.json}")
        return 0

    if not args.report:
        total = sum(min(len(shared[v][0]), args.limit or 10**9) for v in videos) * len(LLM_ARMS)
        print(f"\ncontroller pass: up to {total} calls (~{total*4/3600:.1f} h at 4 s/call)\n")
        for arm in LLM_ARMS:
            for vid in videos:
                segs, ts, sb, ad, cs = shared[vid]
                rows = build_arm_segments(arm, segs, ts, sb, ad)
                t = time.time()
                orchestrate_arm(arm, vid, rows, cs, args.limit)
                print(f"  [{arm:12s}] {vid}  {time.time()-t:6.0f}s", flush=True)

        for arm in DERIVED_FROM:
            for vid in videos:
                segs, ts, sb, ad, cs = shared[vid]
                derive_arm(arm, vid, build_arm_segments(arm, segs, ts, sb, ad))
            print(f"  [{arm:12s}] derived from {DERIVED_FROM[arm]}, no controller calls")

    # ------------------------------------------------------------------ report
    if args.report:
        for arm in DERIVED_FROM:
            for vid in videos:
                segs, ts, sb, ad, cs = shared[vid]
                derive_arm(arm, vid, build_arm_segments(arm, segs, ts, sb, ad))

    table = {}
    for vid in videos:
        segs, ts, sb, ad, cs = shared[vid]
        table[vid] = {}
        for arm in ARMS:
            rows = systematic_sample(build_arm_segments(arm, segs, ts, sb, ad),
                                     args.limit)
            s = score_arm(arm, vid, rows, cs)
            if s:
                table[vid][arm] = s

    print("\n" + "=" * 100)
    print("PER-VIDEO — authenticity / brand health / flagged")
    print("=" * 100)
    hdr = f"{'video':14}{'n':>5}"
    for a in ARMS:
        hdr += f"{a[:12]:>16}"
    print(hdr)
    for vid, arms in table.items():
        if len(arms) < len(ARMS):
            continue
        n = arms["before"]["n_segments"]
        line = f"{vid:14}{n:5d}"
        for a in ARMS:
            line += f"{arms[a]['authenticity']:9.2f}/{arms[a]['n_flagged']:<6d}"
        print(line)

    complete = {v: a for v, a in table.items() if len(a) == len(ARMS)}
    if complete:
        print("\n" + "=" * 100)
        print(f"POOLED across {len(complete)} videos, "
              f"{sum(a['before']['n_segments'] for a in complete.values())} segments")
        print("=" * 100)
        print(f"{'arm':14}{'auth':>9}{'health':>9}{'flagged':>9}{'mean conf':>11}"
              f"{'nonzero':>9}{'damped':>8}")
        agg = {}
        for arm in ARMS:
            rows = [a[arm] for a in complete.values()]
            n = sum(r["n_segments"] for r in rows)
            agg[arm] = {
                "authenticity": round(sum(r["authenticity"] for r in rows) / len(rows), 2),
                "brand_health": round(sum(r["brand_health"] for r in rows) / len(rows), 2),
                "n_flagged": sum(r["n_flagged"] for r in rows),
                "n_segments": n,
                "mean_conflict": round(
                    sum(r["mean_conflict"] * r["n_segments"] for r in rows) / n, 4),
                "nonzero_conflict": sum(r["nonzero_conflict"] for r in rows),
                "damped": sum(r["damped"] for r in rows),
            }
            g = agg[arm]
            print(f"{arm:14}{g['authenticity']:9.2f}{g['brand_health']:9.2f}"
                  f"{g['n_flagged']:9d}{g['mean_conflict']:11.4f}"
                  f"{g['nonzero_conflict']:9d}{g['damped']:8d}")

        b, a, nd = agg["before"], agg["after"], agg["after_nodamp"]
        print("\nDecomposition of the change in Authenticity Score:")
        print(f"  total          after - before        = {a['authenticity']-b['authenticity']:+.2f}")
        print(f"  model+dimension after_nodamp - before = {nd['authenticity']-b['authenticity']:+.2f}")
        print(f"  down-weighting  after - after_nodamp  = {a['authenticity']-nd['authenticity']:+.2f}")
        table["_pooled"] = agg
    table["_divergence"] = div

    if args.json:
        args.json.write_text(json.dumps(table, indent=1))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
