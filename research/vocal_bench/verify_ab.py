"""
verify_ab.py - re-derive every number in CORPUS_AB_RESULT.md from the raw data.

Same purpose as whisper_bench/verify_claims.py and vocal_bench/verify_claims.py:
a figure that cannot be re-derived is not evidence, and hand-copied numbers drift.
Every claim below is recomputed from the caches and compared against the value
written in the document. A mismatch fails loudly with both numbers.

Claims that depend on the controller pass are skipped, not faked, while that pass
is still running. Skipped is reported separately from passed so a partial run can
never be mistaken for a clean one.

NOTE, 02 Sep 2026. The §3.2 checks below verify the down-weighting as it stood
when the A/B ran - keyed on the controller's own attribution, firing on nothing.
That trigger was replaced later the same day and the replacement fires on 89 of
the same 481 segments (DAMPING_FIX_RESULT.md, verified by verify_damping_fix.py).
These checks read the CACHED pre-fix arms in ab_cache/, which is why they still
pass and should: they verify a historical measurement, not current behaviour.

    python research/vocal_bench/verify_ab.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(BENCH))

CLASSES = ("NEGATIVE", "NEUTRAL", "POSITIVE")

_passed: list[str] = []
_failed: list[str] = []
_skipped: list[str] = []


def check(name: str, actual, expected, tol: float = 0.0) -> None:
    if isinstance(expected, float) or isinstance(actual, float):
        ok = abs(float(actual) - float(expected)) <= tol
    else:
        ok = actual == expected
    (_passed if ok else _failed).append(
        name if ok else f"{name}: document says {expected!r}, data gives {actual!r}")


def skip(name: str, why: str) -> None:
    _skipped.append(f"{name} ({why})")


# ── the corpus itself ─────────────────────────────────────────────────────────

def verify_corpus() -> dict:
    import corpus_ab as AB

    videos = AB.corpus_videos()
    check("§1 videos", len(videos), 12)

    segs = {v: AB.load_segments(v) for v in videos}
    total = sum(len(s) for s in segs.values())
    check("§1 segments", total, 1863)

    audio = sum(json.loads((AB.CORPUS / f"{v}.json").read_text())["audio_seconds"]
                for v in videos)
    check("§1 audio minutes", round(audio / 60, 1), 152.3, tol=0.05)

    check("§1 controller calls", total * len(AB.LLM_ARMS), 3726)

    # clips and corpus describe the same material
    clips = json.loads((BENCH / "_clip_index.json").read_text())["clips"]
    check("§1 clips drawn only from the corpus",
          set(c["video_id"] for c in clips) <= set(videos), True)
    check("§1 no corpus video unrepresented",
          sorted(set(videos) - {c["video_id"] for c in clips}), [])
    check("§1 speakers", len({c["channel"] for c in clips}), 6)
    return segs


# ── §2 divergence ─────────────────────────────────────────────────────────────

def verify_divergence(segs: dict) -> None:
    import corpus_ab as AB

    shared = {}
    for vid, rows in segs.items():
        sb = AB.CACHE / "vocal_speechbrain" / f"{vid}.json"
        ad = AB.CACHE / "vocal_audeering" / f"{vid}.json"
        if not (sb.is_file() and ad.is_file()):
            skip("§2 divergence", "channel caches incomplete")
            return
        shared[vid] = (rows, None, json.loads(sb.read_text()),
                       json.loads(ad.read_text()), None)

    div = AB.channel_divergence(shared)
    check("§2 n", div["n"], 1863)
    for label, expected in (("NEGATIVE", 776), ("NEUTRAL", 1003),
                            ("POSITIVE", 81), ("unknown", 3)):
        check(f"§2 before {label}", div["before"].get(label, 0), expected)
    for label, expected in (("NEGATIVE", 14), ("NEUTRAL", 1464),
                            ("POSITIVE", 382), ("unknown", 3)):
        check(f"§2 after {label}", div["after"].get(label, 0), expected)

    check("§2 changed", div["n_changed"], 965)
    check("§2 changed pct", round(100 * div["n_changed"] / div["n"], 1), 51.8, tol=0.05)

    for move, expected in (("NEGATIVE -> NEUTRAL", 565), ("NEGATIVE -> POSITIVE", 210),
                           ("NEUTRAL -> POSITIVE", 135), ("POSITIVE -> NEUTRAL", 42),
                           ("NEUTRAL -> NEGATIVE", 11), ("POSITIVE -> NEGATIVE", 2)):
        check(f"§2 {move}", div["changed"].get(move, 0), expected)

    away = sum(n for m, n in div["changed"].items() if m.startswith("NEGATIVE"))
    check("§2 moves away from NEGATIVE", away, 775)
    check("§2 moves away pct", round(100 * away / div["n_changed"], 1), 80.3, tol=0.05)

    # percentages of the corpus
    check("§2 before NEGATIVE pct",
          round(100 * div["before"]["NEGATIVE"] / div["n"], 1), 41.7, tol=0.05)
    check("§2 after NEGATIVE pct",
          round(100 * div["after"]["NEGATIVE"] / div["n"], 1), 0.8, tol=0.05)

    _verify_distribution(div)


def _verify_distribution(div: dict) -> None:
    """The human-vs-model distribution table and its total variation distances."""
    import ground_truth as GT
    from collections import Counter

    human = Counter()
    for split in ("selection", "confirmation"):
        human.update(r["label"] for r in GT.load(split))
    hn = sum(human.values())
    check("§2 human n", hn, 147)

    H = {c: human[c] / hn for c in CLASSES}
    check("§2 human NEGATIVE pct", round(100 * H["NEGATIVE"], 1), 15.0, tol=0.05)
    check("§2 human NEUTRAL pct", round(100 * H["NEUTRAL"], 1), 42.9, tol=0.05)
    check("§2 human POSITIVE pct", round(100 * H["POSITIVE"], 1), 42.2, tol=0.05)

    def scorable(d):
        n = sum(d.get(c, 0) for c in CLASSES)
        return {c: d.get(c, 0) / n for c in CLASSES}, n

    B, nb = scorable(div["before"])
    A, na = scorable(div["after"])
    check("§2 scorable n", nb, 1860)
    check("§2 scorable n both arms", na, nb)

    tvd = lambda P: sum(abs(P[c] - H[c]) for c in CLASSES) / 2
    check("§2 TVD before", round(tvd(B), 4), 0.3782, tol=5e-5)
    check("§2 TVD after", round(tvd(A), 4), 0.3585, tol=5e-5)
    check("§2 TVD change", round(tvd(A) - tvd(B), 4), -0.0197, tol=5e-5)

    # "over-called by 2.8x" / "under-calls by 19x"
    check("§2 before over-call factor",
          round(B["NEGATIVE"] / H["NEGATIVE"], 1), 2.8, tol=0.05)
    check("§2 after under-call factor",
          round(H["NEGATIVE"] / A["NEGATIVE"]), 20, tol=0.5)


# ── §5 verified facts ─────────────────────────────────────────────────────────

def verify_deployed_code_reproduces_bench() -> None:
    """The claim the whole adoption rests on: the DEPLOYED thresholds give 60/100, 23/47."""
    import ground_truth as GT
    import report_bench as RB
    from pipeline.audio_module import (
        classify_arousal, VOCAL_CHANNEL_RELIABILITY, AROUSAL_LOW, AROUSAL_HIGH,
        VOCAL_DIMENSION)
    from pipeline.orchestrator import VOCAL_ONLY_CONFLICT_WEIGHT

    check("§5 AROUSAL_LOW frozen", AROUSAL_LOW, 0.40)
    check("§5 AROUSAL_HIGH frozen", AROUSAL_HIGH, 0.65)
    check("§5 dimension is arousal", VOCAL_DIMENSION, "arousal")

    try:
        pred = RB.load_predictions()["audeering-msp-dim"]["predictions"]
    except (KeyError, FileNotFoundError):
        skip("§5 bench reproduction", "vocal_bench predictions absent")
        return

    for split, exp_correct, exp_n in (("selection", 60, 100), ("confirmation", 23, 47)):
        rows = GT.load(split)
        correct = sum(classify_arousal(pred[r["uid"]]["scores"]["arousal"]) == r["label"]
                      for r in rows)
        check(f"§5 {split} correct", correct, exp_correct)
        check(f"§5 {split} n", len(rows), exp_n)

    check("§5 reliability = 23/47", round(VOCAL_CHANNEL_RELIABILITY, 4),
          round(23 / 47, 4), tol=5e-4)
    check("§5 damping weight = reliability",
          VOCAL_ONLY_CONFLICT_WEIGHT, VOCAL_CHANNEL_RELIABILITY)


def verify_duration_transfer(segs: dict) -> None:
    """CORPUS_AB_RESULT.md §5: 99.7% of pipeline segments sit inside the bench clip range."""
    clips = json.loads((BENCH / "_clip_index.json").read_text())["clips"]
    lo = min(c["duration"] for c in clips)
    hi = max(c["duration"] for c in clips)
    durs = [s["end_time"] - s["start_time"] for rows in segs.values() for s in rows]
    inside = sum(1.5 <= d <= 15.0 for d in durs)
    check("§5 clip min duration >= 1.5", lo >= 1.5, True)
    check("§5 clip max duration <= 15.0", hi <= 15.0, True)
    check("§5 segments inside clip range pct",
          round(100 * inside / len(durs), 1), 99.7, tol=0.05)


# ── §3 the controller result ──────────────────────────────────────────────────

def verify_headline(segs: dict) -> None:
    """§3: the pooled table, the decomposition, and the per-video consistency."""
    from math import comb

    res = BENCH / "ab_results.json"
    if not res.is_file():
        skip("§3 headline", "ab_results.json not written yet")
        return
    t = json.loads(res.read_text())
    if "_pooled" not in t:
        skip("§3 headline", "run incomplete, no pooled block")
        return

    g = t["_pooled"]
    check("§3 segments scored", g["before"]["n_segments"], 479)
    for arm, auth, health, flagged, mean_c, nz in (
            ("before", 70.76, 86.60, 69, 0.2309, 232),
            ("after", 97.45, 97.28, 8, 0.0131, 8),
            ("after_nodamp", 97.45, 97.28, 8, 0.0131, 8)):
        check(f"§3 {arm} authenticity", g[arm]["authenticity"], auth, tol=5e-3)
        check(f"§3 {arm} brand health", g[arm]["brand_health"], health, tol=5e-3)
        check(f"§3 {arm} flagged", g[arm]["n_flagged"], flagged)
        check(f"§3 {arm} mean conflict", g[arm]["mean_conflict"], mean_c, tol=5e-5)
        check(f"§3 {arm} non-zero conflicts", g[arm]["nonzero_conflict"], nz)
        check(f"§3 {arm} damped", g[arm]["damped"], 0)

    b, a, nd = (g[k]["authenticity"] for k in ("before", "after", "after_nodamp"))
    check("§3 total delta", round(a - b, 2), 26.69, tol=5e-3)
    check("§3 model+dimension delta", round(nd - b, 2), 26.69, tol=5e-3)
    check("§3 down-weighting delta", round(a - nd, 2), 0.00, tol=5e-3)

    # §3.1 per-video consistency
    vids = [k for k in t if not k.startswith("_")]
    check("§3.1 videos", len(vids), 12)
    d = [t[v]["after"]["authenticity"] - t[v]["before"]["authenticity"] for v in vids]
    up = sum(1 for x in d if x > 0)
    check("§3.1 videos improved", up, 12)
    p_sign = 2 * sum(comb(len(d), k) for k in range(up, len(d) + 1)) / 2 ** len(d)
    check("§3.1 sign test p", round(p_sign, 6), 0.000488, tol=5e-7)
    check("§3.1 mean delta", round(sum(d) / len(d), 2), 26.69, tol=5e-3)
    check("§3.1 min delta", round(min(d), 2), 4.15, tol=5e-3)
    check("§3.1 max delta", round(max(d), 2), 47.62, tol=5e-3)

    # §3.3 flag rates
    check("§3.3 before flag rate pct",
          round(100 * g["before"]["n_flagged"] / g["before"]["n_segments"], 1), 14.4, tol=0.05)
    check("§3.3 after flag rate pct",
          round(100 * g["after"]["n_flagged"] / g["after"]["n_segments"], 1), 1.7, tol=0.05)


def verify_damping_diagnosis() -> None:
    """§3.2: the attribution counts that explain why the damping never fired."""
    import glob
    from pipeline.orchestrator import _conflict_rests_only_on_vocal

    counts = {}
    for arm in ("before", "after_nodamp"):
        files = glob.glob(str(BENCH / "ab_cache" / f"conflict_{arm}" / "*.json"))
        if not files:
            skip(f"§3.2 {arm} attribution", "no cached responses")
            return
        present = nonempty = scored = vocal_only = total = 0
        for f in files:
            for _k, r in json.loads(Path(f).read_text()).items():
                raw = r.get("_raw")
                if not isinstance(raw, dict):
                    continue
                total += 1
                if "channels_in_conflict" not in raw:
                    continue
                present += 1
                ch = raw["channels_in_conflict"]
                if isinstance(ch, list) and ch:
                    nonempty += 1
                    if r["conflict_score"] > 0:
                        scored += 1
                        if _conflict_rests_only_on_vocal(ch):
                            vocal_only += 1
        counts[arm] = (total, present, nonempty, scored, vocal_only)

    tb, pb, nb, sb, vb = counts["before"]
    check("§3.2 before responses", tb, 496)
    check("§3.2 before carrying attribution", pb, 0)
    check("§3.2 before named channels", nb, 0)
    check("§3.2 before vocal-only conflicts", vb, 0)

    ta, pa, na, sa, va = counts["after_nodamp"]
    check("§3.2 after responses", ta, 481)
    check("§3.2 after carrying attribution", pa, 481)
    check("§3.2 after named channels", na, 265)
    check("§3.2 after named AND scored > 0", sa, 8)
    check("§3.2 after vocal-only conflicts", va, 0)
    check("§3.2 attributions accompanying a zero score", na - sa, 257)


def verify_scores(segs: dict) -> None:
    """The damping must be pure post-processing, and the arms must agree where it did not fire.

    Checked against the run's declared scope (40 segments per video, evenly
    sampled) rather than the full corpus, because that is what was run.
    """
    import corpus_ab as AB

    res = BENCH / "ab_results.json"
    if not res.is_file():
        skip("§3 arm equivalence", "ab_results.json not written yet")
        return
    t = json.loads(res.read_text())
    vids = [k for k in t if not k.startswith("_")]
    if not vids:
        skip("§3 arm equivalence", "no per-video results")
        return

    from pipeline.orchestrator import _conflict_rests_only_on_vocal

    mismatched = compared = differing = 0
    for vid in vids:
        nd_p = AB.CACHE / "conflict_after_nodamp" / f"{vid}.json"
        af_p = AB.CACHE / "conflict_after" / f"{vid}.json"
        if not (nd_p.is_file() and af_p.is_file()):
            skip("§3 arm equivalence", f"cache missing for {vid}")
            return
        nd = json.loads(nd_p.read_text())
        af = json.loads(af_p.read_text())
        for k, a in af.items():
            src = nd.get(k)
            if src is None:
                continue
            compared += 1
            raw = src.get("_raw")
            should_damp = (isinstance(raw, dict)
                           and src["conflict_score"] > 0
                           and _conflict_rests_only_on_vocal(raw.get("channels_in_conflict")))
            differs = a["conflict_score"] != src["conflict_score"]
            if differs != should_damp:
                mismatched += 1
            if differs:
                differing += 1

    check("§3 damping is pure post-processing", mismatched, 0)
    # §3.2 measured the damping firing on nothing, so the two arms must be identical.
    check("§3.2 arms differ on zero segments", differing, 0)
    check("§3 segments compared across arms", compared > 0, True)


def main() -> int:
    segs = verify_corpus()
    verify_divergence(segs)
    verify_deployed_code_reproduces_bench()
    verify_duration_transfer(segs)
    verify_headline(segs)
    verify_damping_diagnosis()
    verify_scores(segs)

    print(f"verified   {len(_passed)}")
    print(f"skipped    {len(_skipped)}")
    print(f"FAILED     {len(_failed)}")
    for s in _skipped:
        print(f"  SKIP  {s}")
    for f in _failed:
        print(f"  FAIL  {f}")
    if not _failed and not _skipped:
        print("\nEvery claim in CORPUS_AB_RESULT.md re-derived from the raw data.")
    elif not _failed:
        print("\nEvery re-derivable claim checks out; skipped claims await the controller pass.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
