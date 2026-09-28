"""
report_whisper.py - score every Whisper candidate against the human ground truth.

Written 31 Aug 2026, BEFORE ground_truth.json existed. Writing the scoring code
before seeing any result removes the freedom to pick a metric that flatters a
particular model after the fact. The metric, the decision rule and the bootstrap
settings all come from CANDIDATE_MODELS.md Section 3, which was fixed earlier the
same day and must not be revised now.

Usage:
    python report_whisper.py                 # full report to stdout
    python report_whisper.py --json out.json # also dump machine-readable results

Nothing here downloads or runs a model. It reads transcripts/*.json produced by
run_whisper_bench.py and ground_truth.json exported from type_here.html.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from wer import corpus_wer, wilson_interval

HERE = Path(__file__).parent
TRANSCRIPTS = HERE / "transcripts"
GROUND_TRUTH = HERE / "ground_truth.json"
CLIP_INDEX = HERE / "_clip_index.json"

INCUMBENT = "base"

# Pre-registered in CANDIDATE_MODELS.md Section 3. Do not tune these.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42
ALPHA = 0.05


class GroundTruthError(RuntimeError):
    """Ground truth is missing, incomplete, or does not match the clip index."""


# ----------------------------------------------------------------- loading


def load_clip_index() -> list[dict]:
    return json.loads(CLIP_INDEX.read_text())["clips"]


def load_ground_truth(clip_ids: list[str]) -> dict[str, str]:
    """Load the human transcripts, refusing anything partial.

    A missing or blank clip is an error rather than a skip. Silently scoring 11
    of 12 clips would change the sample without changing the reported n, which is
    exactly the kind of quiet drift the project's evidence rule exists to prevent.
    """
    if not GROUND_TRUTH.exists():
        raise GroundTruthError(
            f"{GROUND_TRUTH} not found. Type the clips in type_here.html and "
            f"click Export first - no model output can substitute for it."
        )

    payload = json.loads(GROUND_TRUTH.read_text())
    transcripts = payload.get("transcripts")
    if not isinstance(transcripts, dict):
        raise GroundTruthError("ground_truth.json has no 'transcripts' object")

    missing = [cid for cid in clip_ids if not transcripts.get(cid, "").strip()]
    if missing:
        raise GroundTruthError(
            f"{len(missing)} of {len(clip_ids)} clips are empty: {', '.join(missing)}"
        )

    unknown = set(transcripts) - set(clip_ids)
    if unknown:
        raise GroundTruthError(f"ground_truth.json has unknown clip ids: {sorted(unknown)}")

    return {cid: transcripts[cid].strip() for cid in clip_ids}


def load_transcripts() -> dict[str, dict]:
    out = {}
    for path in sorted(TRANSCRIPTS.glob("*.json")):
        data = json.loads(path.read_text())
        out[data["model"]] = data
    if not out:
        raise RuntimeError(f"no transcripts in {TRANSCRIPTS} - run run_whisper_bench.py first")
    return out


# ----------------------------------------------------------------- scoring


def score_model(run: dict, truth: dict[str, str], clip_ids: list[str]) -> dict:
    """Corpus WER for one model, plus the per-clip breakdown."""
    by_id = {c["video_id"]: c for c in run["clips"]}
    pairs, order = [], []
    for cid in clip_ids:
        if cid not in by_id:
            raise RuntimeError(f"model {run['model']} has no transcript for clip {cid}")
        pairs.append((truth[cid], by_id[cid]["text"]))
        order.append(cid)

    agg = corpus_wer(pairs)
    per_clip = {cid: c for cid, c in zip(order, agg.pop("per_clip"))}

    correct = agg["ref_words"] - agg["errors"]
    # Word accuracy can go negative when insertions exceed correct words. Wilson
    # is undefined there, so it is reported only when the count is a real
    # proportion. This is a real outcome for a hallucinating model, not a bug.
    if 0 <= correct <= agg["ref_words"]:
        lo, hi = wilson_interval(correct, agg["ref_words"])
    else:
        lo = hi = float("nan")

    return {
        "model": run["model"],
        "parameters_millions": run["parameters_millions"],
        "realtime_factor": run["realtime_factor"],
        "total_wall_s": run["total_wall_s"],
        "n_segments": sum(c["n_segments"] for c in run["clips"]),
        **agg,
        "word_accuracy": correct / agg["ref_words"] if agg["ref_words"] else 0.0,
        "word_accuracy_ci": (lo, hi),
        "per_clip": per_clip,
    }


def per_speaker_wer(scored: dict, clips: list[dict]) -> dict[str, float]:
    """Pool errors within each speaker. Shows whether a win is uniform."""
    channel_of = {c["video_id"]: c["channel"] for c in clips}
    tally: dict[str, list[int]] = {}
    for cid, counts in scored["per_clip"].items():
        errs, refs = tally.setdefault(channel_of[cid], [0, 0])
        tally[channel_of[cid]] = [errs + counts["errors"], refs + counts["ref_words"]]
    return {ch: e / n if n else 0.0 for ch, (e, n) in sorted(tally.items())}


# ----------------------------------------------------------------- bootstrap


def paired_bootstrap(a: dict, b: dict, clip_ids: list[str]) -> dict:
    """Paired bootstrap over clips for WER(a) - WER(b).

    The resampling unit is the clip, not the word, because words inside a clip
    share a speaker, a topic and a recording chain and are plainly not
    independent. Both models are scored on the same resampled clips each draw, so
    the difference is paired and clip difficulty cancels out.

    Declared in advance (CANDIDATE_MODELS.md Section 3): n=12 makes this coarse.
    A non-significant result here is a failure to detect a difference, NOT
    evidence that the two models are equivalent.

    A property worth knowing when reading the output: this test is powerful
    against a CONSISTENT difference and weak against a large but inconsistent
    one. If b beats a on all 12 clips, no resample can favour a, so even a
    fractional WER gap reads as detectable - the bootstrap has degenerated into
    a sign test at 12/12, p = 2*(1/2)^12. The per-clip win counts are returned
    alongside so a reader can see which situation they are looking at.
    """
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(clip_ids)
    pa, pb = a["per_clip"], b["per_clip"]

    observed = a["wer"] - b["wer"]

    # Per-clip direction, reported so a "significant" result can be read as
    # either a real uniform gap or an artefact of consistency at small n.
    a_better = b_better = tied = 0
    for cid in clip_ids:
        ra = pa[cid]["errors"] / pa[cid]["ref_words"] if pa[cid]["ref_words"] else 0.0
        rb = pb[cid]["errors"] / pb[cid]["ref_words"] if pb[cid]["ref_words"] else 0.0
        if ra < rb:
            a_better += 1
        elif rb < ra:
            b_better += 1
        else:
            tied += 1

    diffs = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        idx = [rng.randrange(n) for _ in range(n)]
        ea = sum(pa[clip_ids[i]]["errors"] for i in idx)
        eb = sum(pb[clip_ids[i]]["errors"] for i in idx)
        na = sum(pa[clip_ids[i]]["ref_words"] for i in idx)
        nb = sum(pb[clip_ids[i]]["ref_words"] for i in idx)
        diffs.append((ea / na if na else 0.0) - (eb / nb if nb else 0.0))

    diffs.sort()
    lo = diffs[int(ALPHA / 2 * BOOTSTRAP_RESAMPLES)]
    hi = diffs[int((1 - ALPHA / 2) * BOOTSTRAP_RESAMPLES) - 1]
    # Two-sided percentile test: does the interval exclude zero? This is the
    # pre-registered decision criterion. The p-value below is reported for
    # information and does not override it.
    crosses_zero = lo <= 0.0 <= hi

    n_le = sum(1 for d in diffs if d <= 0.0)
    n_ge = sum(1 for d in diffs if d >= 0.0)
    p_value = min(1.0, 2.0 * min(n_le, n_ge) / BOOTSTRAP_RESAMPLES)

    return {
        "observed_diff": observed,
        "ci_low": lo,
        "ci_high": hi,
        "p_value": p_value,
        "significant": not crosses_zero,
        "clips_a_better": a_better,
        "clips_b_better": b_better,
        "clips_tied": tied,
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
    }


# ----------------------------------------------------------------- decision


def apply_decision_rule(scores: list[dict], clip_ids: list[str]) -> dict:
    """The pre-registered rule, applied mechanically.

    'Adopt the fastest model whose WER is not detectably worse than the best.'

    Best = lowest corpus WER. A candidate qualifies if the paired bootstrap
    cannot distinguish it from the best. Among qualifiers, highest realtime
    factor wins. If the best model is also the fastest qualifier, it wins
    outright.
    """
    best = min(scores, key=lambda s: s["wer"])

    qualifiers = []
    for s in scores:
        if s["model"] == best["model"]:
            qualifiers.append({"model": s["model"], "test": None, "is_best": True})
            continue
        test = paired_bootstrap(s, best, clip_ids)
        if not test["significant"]:
            qualifiers.append({"model": s["model"], "test": test, "is_best": False})

    by_model = {s["model"]: s for s in scores}
    winner = max(qualifiers, key=lambda q: by_model[q["model"]]["realtime_factor"])

    return {
        "best_wer_model": best["model"],
        "best_wer": best["wer"],
        "qualifiers": qualifiers,
        "adopt": winner["model"],
        "adopt_is_best_wer": winner["model"] == best["model"],
    }


# ----------------------------------------------------------------- output


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def render(scores: list[dict], clips: list[dict], clip_ids: list[str],
           decision: dict, vs_incumbent: dict) -> str:
    lines: list[str] = []
    w = lines.append

    ref_words = scores[0]["ref_words"]
    w(f"Whisper transcription bench - {len(scores)} checkpoints")
    w(f"{len(clip_ids)} clips, {sum(c['duration_s'] for c in clips) / 60:.2f} min, "
      f"{ref_words} reference words, {len({c['channel'] for c in clips})} speakers")
    w("")

    w("WER (lower is better), sorted best first")
    w("")
    hdr = (f"{'model':<16}{'params':>8}{'WER':>9}{'sub':>6}{'del':>6}{'ins':>6}"
           f"{'segs':>6}{'xRT':>7}")
    w(hdr)
    w("-" * len(hdr))
    for s in sorted(scores, key=lambda x: x["wer"]):
        mark = " *" if s["model"] == INCUMBENT else ""
        w(f"{s['model'] + mark:<16}{s['parameters_millions']:>7.1f}M"
          f"{_pct(s['wer']):>9}{s['substitutions']:>6}{s['deletions']:>6}"
          f"{s['insertions']:>6}{s['n_segments']:>6}{s['realtime_factor']:>6.1f}x")
    w("")
    w(f"* = incumbent, currently deployed in pipeline/audio_module.py")
    w("")

    w("Word accuracy with Wilson 95% interval")
    w("  (optimistic - words within a clip are not independent; the clip-level")
    w("   bootstrap below is the honest interval)")
    w("")
    for s in sorted(scores, key=lambda x: x["wer"]):
        lo, hi = s["word_accuracy_ci"]
        ci = "n/a (insertions exceed correct words)" if lo != lo else f"[{_pct(lo)}, {_pct(hi)}]"
        w(f"  {s['model']:<16}{_pct(s['word_accuracy']):>9}  {ci}")
    w("")

    w("Per-speaker WER")
    w("")
    channels = sorted({c["channel"] for c in clips})
    w(f"{'model':<16}" + "".join(f"{ch[:13]:>15}" for ch in channels))
    w("-" * (16 + 15 * len(channels)))
    for s in sorted(scores, key=lambda x: x["wer"]):
        row = per_speaker_wer(s, clips)
        w(f"{s['model']:<16}" + "".join(f"{_pct(row.get(ch, 0.0)):>15}" for ch in channels))
    w("")

    w(f"Paired bootstrap vs incumbent ({INCUMBENT}), "
      f"{BOOTSTRAP_RESAMPLES} resamples over {len(clip_ids)} clips, seed {BOOTSTRAP_SEED}")
    w("  negative diff = candidate has LOWER WER than the incumbent")
    w("")
    w(f"{'model':<16}{'diff':>10}{'95% CI':>24}{'p':>9}{'clips won':>12}{'detect':>8}")
    w("-" * 79)
    for model, t in vs_incumbent.items():
        ci = f"[{t['ci_low'] * 100:+.2f}, {t['ci_high'] * 100:+.2f}]"
        won = f"{t['clips_a_better']}-{t['clips_b_better']}"
        if t["clips_tied"]:
            won += f"-{t['clips_tied']}t"
        w(f"{model:<16}{t['observed_diff'] * 100:>+9.2f}%{ci:>24}"
          f"{t['p_value']:>9.4f}{won:>12}{'yes' if t['significant'] else 'no':>8}")
    w("")
    w("  'clips won' = clips where the candidate beat the incumbent, then clips")
    w("  where the incumbent won, then ties. A significant result carried by a")
    w("  12-0 sweep of small per-clip gaps is a different finding from one")
    w("  carried by a large gap on a few clips - read the two columns together.")
    w("")
    w("  n=12 clips is a small number of resampling units. A 'no' means the")
    w("  difference was not detectable at this sample size - it is not evidence")
    w("  that the two models are equivalent. Declared in advance, "
      "CANDIDATE_MODELS.md Section 8.1.")
    w("")

    w("Decision rule (pre-registered): adopt the fastest model whose WER is not")
    w("detectably worse than the best.")
    w("")
    w(f"  lowest WER      : {decision['best_wer_model']} at {_pct(decision['best_wer'])}")
    w(f"  qualifiers      : {', '.join(q['model'] for q in decision['qualifiers'])}")
    w(f"  ADOPT           : {decision['adopt']}")
    if decision["adopt_is_best_wer"]:
        w("                    (also the outright most accurate)")
    w("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="also write machine-readable results here")
    args = ap.parse_args()

    clips = load_clip_index()
    clip_ids = [c["video_id"] for c in clips]

    try:
        truth = load_ground_truth(clip_ids)
    except GroundTruthError as exc:
        print(f"ground truth not usable: {exc}", file=sys.stderr)
        return 2

    runs = load_transcripts()
    scores = [score_model(runs[m], truth, clip_ids) for m in sorted(runs)]

    incumbent = next(s for s in scores if s["model"] == INCUMBENT)
    vs_incumbent = {
        s["model"]: paired_bootstrap(s, incumbent, clip_ids)
        for s in sorted(scores, key=lambda x: x["wer"])
        if s["model"] != INCUMBENT
    }

    decision = apply_decision_rule(scores, clip_ids)
    print(render(scores, clips, clip_ids, decision, vs_incumbent))

    if args.json:
        payload = {
            "clips": clip_ids,
            "reference_words": incumbent["ref_words"],
            "scores": [{k: v for k, v in s.items() if k != "per_clip"} for s in scores],
            "per_clip": {s["model"]: s["per_clip"] for s in scores},
            "vs_incumbent": vs_incumbent,
            "decision": decision,
        }
        args.json.write_text(json.dumps(payload, indent=1))
        print(f"wrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
