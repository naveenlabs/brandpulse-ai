"""
report_bench.py — score both benches against the ground truth and print the tables.

Bench A  detectors, on face presence over all 77 segments.
Bench B  emotion models, three-class, on the 44 segments with a verified expression.
Bench C  the Q6 analysis: where anger actually goes. Needs no ground truth and runs
         over every video with predictions on disk.

The scoring arithmetic is `transcript_bench/metrics.py`, imported rather than
copied: Wilson intervals, per-class precision/recall/F1, macro-F1, confusion
matrices and the exact McNemar test with `min_attainable_p` are already written
and unit-tested there, and duplicating them would create two things to keep right.

Usage
-----
    python research/facial_bench/report_bench.py                 # everything
    python research/facial_bench/report_bench.py --bench a
    python research/facial_bench/report_bench.py --bench c --all-videos
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(ROOT))

import candidates as C                                          # noqa: E402
import ground_truth as GT                                       # noqa: E402
import run_classify as RC                                       # noqa: E402
import run_detect as RD                                         # noqa: E402
from research.transcript_bench import metrics as M              # noqa: E402

DETECTIONS = BENCH / "detections"
PREDICTIONS = BENCH / "predictions"
RESULTS = BENCH / "bench_results.json"

FACE, NO_FACE = "FACE", "NO_FACE"
BINARY = (FACE, NO_FACE)


ABSTAIN = "NO_PREDICTION"
SCORED_LABELS = M.LABELS + (ABSTAIN,)


def summarise_with_abstain(gold: list[str], pred: list[str]) -> dict:
    """
    `metrics.summarise`, extended so a model that produces no label for a segment
    is counted as wrong rather than quietly dropped.

    Dropping would let a candidate raise its accuracy by abstaining, which is not
    an improvement the pipeline can use: `visual_module` hands the orchestrator a
    `dominant` of None, and a channel with no reading is a channel that failed.
    The abstention is therefore a fourth column in the confusion matrix, never a
    gold class, and macro-F1 is still averaged over the three real classes so it
    stays comparable with `transcript_bench` and `vocal_bench`.
    """
    n = len(gold)
    if n == 0:
        raise ValueError("cannot summarise an empty sample")
    correct = sum(g == p for g, p in zip(gold, pred))
    lo, hi = M.wilson_interval(correct, n)
    prf = M.per_class_prf(gold, pred, labels=SCORED_LABELS)
    return {
        "n": n,
        "accuracy": correct / n,
        "accuracy_ci95": [lo, hi],
        "macro_f1": sum(prf[c]["f1"] for c in M.LABELS) / len(M.LABELS),
        "per_class": {c: prf[c] for c in SCORED_LABELS},
        "confusion": M.confusion_matrix(gold, pred, labels=SCORED_LABELS),
        "abstentions": sum(1 for p in pred if p == ABSTAIN),
    }


# ── Bench A ───────────────────────────────────────────────────────────────────

def score_detectors(video_id: str, min_confidence: float = 0.0,
                    mode: str = "any") -> dict:
    """
    Score every detector with a results file against face-presence ground truth.

    min_confidence is the gate applied to a detection before it counts. 0.0 means
    "any detection the backend returns", which is what `candidates.detect` already
    filters to. `visual_module.FACE_CONFIDENCE_THRESHOLD` is 0.50, so passing 0.50
    reproduces the pipeline's operating point exactly.
    """
    gold_rows = GT.detection_set()
    gold_by_id = {r["segment_id"]: r for r in gold_rows}
    segments = [{"segment_id": r["segment_id"], "start_time": r["start_time"],
                 "end_time": r["end_time"]} for r in gold_rows]
    segments.sort(key=lambda s: s["segment_id"])
    order = [s["segment_id"] for s in segments]
    gold = [FACE if gold_by_id[i]["face_present"] else NO_FACE for i in order]

    out: dict[str, dict] = {}
    for path in sorted(DETECTIONS.glob(f"{video_id}__*.json")):
        data = json.loads(path.read_text())
        partial = bool(data.get("midpoints_only"))
        if partial and mode != "midpoint":
            # A midpoints-only sweep contains one frame per segment, so pooling it
            # with the "any" rule would produce a number that looks like a pooled
            # score and is really the midpoint score under another name. Skipped
            # rather than silently mislabelled (Amendment A4).
            continue
        # Re-express each frame as detected/not at this gate before pooling.
        gated = [{**r, "n_faces": sum(1 for c in r["confidences"] if c >= min_confidence)}
                 for r in data["rows"]]
        pooled = RD.pool_to_segments(gated, segments, mode)
        pred = [FACE if pooled[i]["face_present"] else NO_FACE for i in order]

        faceless = [i for i in order if gold_by_id[i]["face_present"] is False]
        faced = [i for i in order if gold_by_id[i]["face_present"] is True]
        fp = sum(1 for i in faceless if pooled[i]["face_present"])
        tp = sum(1 for i in faced if pooled[i]["face_present"])

        correct = sum(g == p for g, p in zip(gold, pred))
        lo, hi = M.wilson_interval(correct, len(gold))
        fp_lo, fp_hi = M.wilson_interval(fp, len(faceless))
        rec_lo, rec_hi = M.wilson_interval(tp, len(faced))
        key = data["detector"] + (" (midpoints only)" if partial else "")
        out[key] = {
            "detector": data["detector"],
            "midpoints_only": partial,
            "incumbent": bool(C.DETECTORS.get(data["detector"], {}).get("incumbent")),
            "n_segments": len(gold),
            "false_positives": fp, "n_faceless": len(faceless),
            "false_positive_rate": fp / len(faceless),
            "false_positive_rate_ci95": [fp_lo, fp_hi],
            "recall": tp / len(faced), "recall_ci95": [rec_lo, rec_hi],
            "true_positives": tp, "n_faced": len(faced),
            "precision": tp / (tp + fp) if (tp + fp) else 0.0,
            "accuracy": correct / len(gold), "accuracy_ci95": [lo, hi],
            "confusion": M.confusion_matrix(gold, pred, labels=BINARY),
            "seconds_per_frame": data["seconds_per_frame"],
            "frames_with_face": sum(1 for r in gated if r["n_faces"] > 0),
            "n_frames": data["n_frames"],
            "_pred": pred,
        }

    # Degenerate baselines, scored as candidates rather than mentioned as caveats.
    for name, const in (("always_face", FACE), ("never_face", NO_FACE)):
        pred = [const] * len(gold)
        correct = sum(g == p for g, p in zip(gold, pred))
        lo, hi = M.wilson_interval(correct, len(gold))
        n_faceless = sum(1 for g in gold if g == NO_FACE)
        n_faced = len(gold) - n_faceless
        fp = n_faceless if const == FACE else 0
        tp = n_faced if const == FACE else 0
        out[name] = {
            "detector": name, "incumbent": False, "baseline": True,
            "n_segments": len(gold),
            "false_positives": fp, "n_faceless": n_faceless,
            "false_positive_rate": fp / n_faceless,
            "false_positive_rate_ci95": list(M.wilson_interval(fp, n_faceless)),
            "recall": tp / n_faced, "recall_ci95": list(M.wilson_interval(tp, n_faced)),
            "true_positives": tp, "n_faced": n_faced,
            "precision": tp / (tp + fp) if (tp + fp) else 0.0,
            "accuracy": correct / len(gold), "accuracy_ci95": [lo, hi],
            "confusion": M.confusion_matrix(gold, pred, labels=BINARY),
            "seconds_per_frame": 0.0,
            "_pred": pred,
        }

    inc = next((k for k, v in out.items()
                if v.get("incumbent") and not v.get("midpoints_only")), None)
    if inc:
        for name, rec in out.items():
            if name == inc:
                continue
            rec["mcnemar_vs_incumbent"] = M.mcnemar_exact(
                gold, out[inc]["_pred"], rec["_pred"])
            rec["mcnemar_recall_vs_incumbent"] = M.mcnemar_exact(
                [g for g in gold if g == FACE],
                [p for g, p in zip(gold, out[inc]["_pred"]) if g == FACE],
                [p for g, p in zip(gold, rec["_pred"]) if g == FACE])
    return {"video_id": video_id, "gold": gold, "order": order,
            "min_confidence": min_confidence, "pooling": mode,
            "detectors": out}


# ── Bench B ───────────────────────────────────────────────────────────────────

def score_classifiers(video_id: str, strict_only: bool = False,
                      mapping: dict[str, str] | None = None) -> dict:
    gold_rows = GT.expression_set(strict_only=strict_only)
    gold_by_id = {r["segment_id"]: r for r in gold_rows}
    all_rows = GT.detection_set()
    segments = [{"segment_id": r["segment_id"], "start_time": r["start_time"],
                 "end_time": r["end_time"]} for r in all_rows]
    segments.sort(key=lambda s: s["segment_id"])

    order = sorted(gold_by_id)
    gold = [gold_by_id[i]["expression"] for i in order]

    out: dict[str, dict] = {}
    for path in sorted(PREDICTIONS.glob(f"{video_id}__*.json")):
        data = json.loads(path.read_text())
        pooled = RC.pool_to_segments(data["rows"], segments, mapping)
        pred, unmapped, nopred = [], 0, 0
        for i in order:
            p = pooled[i]
            if p["three"] is None:
                nopred += 1
                if p["dominant"] is not None:
                    unmapped += 1
                pred.append(ABSTAIN)
            else:
                pred.append(p["three"])
        out[data["model"]] = {
            "model": data["model"],
            "incumbent": bool(data["model_meta"].get("incumbent")),
            "meta": data["model_meta"],
            "seconds_per_crop": data["seconds_per_crop"],
            "no_prediction": nopred, "unmapped": unmapped,
            **summarise_with_abstain(gold, pred),
            "_pred": pred,
        }

    for name, const in (("always_neutral", "NEUTRAL"),
                        ("always_positive", "POSITIVE"),
                        ("always_negative", "NEGATIVE")):
        pred = [const] * len(gold)
        out[name] = {"model": name, "incumbent": False, "baseline": True,
                     "meta": {}, "seconds_per_crop": 0.0,
                     "no_prediction": 0, "unmapped": 0,
                     **summarise_with_abstain(gold, pred), "_pred": pred}

    inc = next((k for k, v in out.items() if v.get("incumbent")), None)
    if inc:
        for name, rec in out.items():
            if name != inc:
                rec["mcnemar_vs_incumbent"] = M.mcnemar_exact(
                    gold, out[inc]["_pred"], rec["_pred"])
    if "always_neutral" in out:
        for name, rec in out.items():
            if name != "always_neutral":
                rec["mcnemar_vs_always_neutral"] = M.mcnemar_exact(
                    gold, out["always_neutral"]["_pred"], rec["_pred"])
    return {"video_id": video_id, "n": len(gold), "strict_only": strict_only,
            "gold": gold, "order": order,
            "gold_distribution": {c: gold.count(c) for c in M.LABELS},
            "classifiers": out}


# ── Bench E — the composite the channel actually produces ────────────────────

def end_to_end(video_id: str, mapping: dict[str, str] | None = None) -> dict:
    """
    Score the whole channel over all 77 segments, the way §9 scores it.

    Amendment A5: the 44-segment expression table is selected on the incumbent's
    errors and cannot rank the incumbent fairly. This metric is not, because it
    covers every segment §9 reviewed and asks the question §9 asks — for each
    segment, does the channel return the right thing?

      - a segment with no human face is right if the channel returns no label;
      - a segment with a verified expression is right if the label matches;
      - the 13 segments with a verified face but no verified expression are
        **unknown**, so the score is an interval, not a point.

    §9's own figure for the deployed channel is 16 of 77, 20.8 per cent, and this
    reproduces exactly that quantity, so every candidate is directly comparable to
    a number already published in this project.

    Two kinds of arm are scored:

      `opencv+deepface_fer`  the deployed channel, taken from the pipeline anchor,
                             so it is the real product and not a reconstruction;
      `retinaface+<model>`   each candidate, on the crops the crop detector cut.

    The arms differ in detector as well as classifier, which is stated rather than
    hidden: a candidate's gain over the incumbent here is a gain from the pair, and
    Bench A and Bench B are what separate the two contributions.
    """
    gold_rows = GT.detection_set()
    gold = {r["segment_id"]: r for r in gold_rows}
    segments = sorted(
        [{"segment_id": r["segment_id"], "start_time": r["start_time"],
          "end_time": r["end_time"]} for r in gold_rows],
        key=lambda s: s["segment_id"])
    order = [s["segment_id"] for s in segments]

    def outcomes(labels: dict[int, str | None]) -> list[str]:
        """
        Per-segment right/wrong, over the 64 segments whose answer is known.

        The 13 unknown segments are dropped rather than guessed, so a McNemar
        between two arms is computed only where both have a defined answer.
        """
        out_ = []
        for sid in order:
            g = gold[sid]
            if g["face_present"] and g["expression"] is None:
                continue
            got = labels.get(sid)
            want = None if not g["face_present"] else g["expression"]
            out_.append("RIGHT" if got == want else "WRONG")
        return out_

    def score(labels: dict[int, str | None], arm: str, detector: str,
              model: str) -> dict:
        right = wrong = unknown = 0
        false_face = missed_face = wrong_label = 0
        for sid in order:
            g = gold[sid]
            got = labels.get(sid)
            if not g["face_present"]:
                if got is None:
                    right += 1
                else:
                    wrong += 1
                    false_face += 1
            elif g["expression"] is None:
                unknown += 1
            elif got is None:
                wrong += 1
                missed_face += 1
            elif got == g["expression"]:
                right += 1
            else:
                wrong += 1
                wrong_label += 1
        n = len(order)
        lo, hi = right / n, (right + unknown) / n
        return {
            "arm": arm, "detector": detector, "model": model,
            "n_segments": n, "right": right, "wrong": wrong, "unknown": unknown,
            "accuracy_lower": lo, "accuracy_upper": hi,
            "accuracy_lower_ci95": list(M.wilson_interval(right, n)),
            "accuracy_upper_ci95": list(M.wilson_interval(right + unknown, n)),
            "false_face": false_face, "missed_face": missed_face,
            "wrong_label": wrong_label,
            "_outcomes": outcomes(labels),
        }

    out: dict[str, dict] = {}

    # The deployed channel, straight from the pipeline anchor.
    anchor_path = BENCH / "anchor_pipeline.json"
    if anchor_path.exists():
        rows = json.loads(anchor_path.read_text())["rows"]
        labels = {r["segment_id"]: C.to_three(r["rerun_label"], mapping)
                  if r["rerun_label"] else None for r in rows}
        out["deployed"] = score(labels, "opencv + deepface_fer (deployed)",
                                "opencv", C.INCUMBENT)
        out["deployed"]["source"] = "anchor_pipeline.json"

    # Each candidate, on the crop detector's crops.
    for path in sorted(PREDICTIONS.glob(f"{video_id}__*.json")):
        data = json.loads(path.read_text())
        pooled = RC.pool_to_segments(data["rows"], segments, mapping)
        labels = {sid: pooled[sid]["three"] for sid in order}
        arm = f"{data['crop_detector']} + {data['model']}"
        out[data["model"]] = score(labels, arm, data["crop_detector"], data["model"])

    # Degenerate arms. A constant label on top of the best detector is the real
    # floor for the end-to-end question: the channel still has to decide face or
    # no-face, which the 44-segment always-NEUTRAL baseline never has to do.
    # transcript_bench and vocal_bench both found the deployed model losing to a
    # constant, so it is scored here as a candidate, not mentioned as a caveat.
    det_path = DETECTIONS / f"{video_id}__{C.CROP_DETECTOR}.json"
    if det_path.exists():
        det = json.loads(det_path.read_text())
        pooled_det = RD.pool_to_segments(det["rows"], segments, "any")
        for const in ("NEUTRAL", "POSITIVE", "NEGATIVE"):
            labels = {sid: (const if pooled_det[sid]["face_present"] else None)
                      for sid in order}
            name = f"constant_{const.lower()}"
            out[name] = score(labels, f"{C.CROP_DETECTOR} + always-{const}",
                              C.CROP_DETECTOR, name)
            out[name]["baseline"] = True

    # Every arm against the constant floor. The comparison runs on right/wrong per
    # segment rather than on labels, because the arms are being compared on whether
    # the channel got the segment right, which is the question the product asks.
    floor = "constant_neutral"
    if floor in out:
        allright = ["RIGHT"] * len(out[floor]["_outcomes"])
        for name, rec in out.items():
            if name == floor or name.startswith("_"):
                continue
            rec["mcnemar_vs_constant"] = M.mcnemar_exact(
                allright, out[floor]["_outcomes"], rec["_outcomes"])

    # §9's own published figure, as the reference point.
    out["_section9"] = {
        "arm": "§9's published figure for the deployed channel",
        "right": 16, "n_segments": 77, "accuracy": 16 / 77,
    }
    return out


def render_end_to_end(res: dict) -> str:
    ref = res.get("_section9", {})
    L = ["BENCH E — the whole channel over all 77 segments (§9's own composite)",
         f"  §9 reports the deployed channel at {ref.get('right')}/{ref.get('n_segments')} "
         f"= {_pct(ref.get('accuracy', 0))}",
         f"  {'arm':40s} {'right':>6s} {'accuracy range':>18s} "
         f"{'false face':>9s} {'wrong lbl':>8s}  vs always-NEUTRAL"]
    rows = [(k, v) for k, v in res.items() if not k.startswith("_")]
    for name, r in sorted(rows, key=lambda kv: (kv[1].get("baseline", False),
                                                -kv[1]["accuracy_lower"])):
        mark = " b" if r.get("baseline") else "  "
        mc = _mcnemar_str(r.get("mcnemar_vs_constant"), "— the floor —")
        L.append(f"  {r['arm']:38s}{mark}{r['right']:3d}/77 "
                 f"{_pct(r['accuracy_lower'])}-{_pct(r['accuracy_upper']):>7s} "
                 f"{r['false_face']:6d}/20 {r['wrong_label']:5d}/44  {mc}")
    L.append("  range = the 13 segments with a verified face but no verified "
             "expression counted all-wrong to all-right")
    L.append("  b = degenerate baseline: the crop detector plus a constant label")
    return "\n".join(L)


# ── Bench C — where anger goes. No ground truth needed. ───────────────────────

def anger_analysis(video_ids: list[str]) -> dict:
    """
    Per-candidate label behaviour on real face crops.

    Reports, per video and per candidate:
      argmax_counts     how often each class wins
      mean_mass         mean probability assigned to each class over all crops
      anger_rank2       crops where anger is second, not first
      anger_mass_when_not_top   how much probability anger still carries
    Nothing here is scored against ground truth; it answers
    `CANDIDATE_MODELS.md` §5.2 and §5.5, which are about behaviour, not accuracy.
    """
    from collections import Counter

    ANGER = {"angry", "anger"}
    out: dict[str, dict] = {}
    for video_id in video_ids:
        per_model = {}
        for path in sorted(PREDICTIONS.glob(f"{video_id}__*.json")):
            data = json.loads(path.read_text())
            rows = [r for r in data["rows"] if r["top"] is not None]
            if not rows:
                continue
            counts = Counter(r["top"] for r in rows)
            three = Counter(r["three"] for r in rows)
            classes = sorted({k for r in rows for k in r["raw"]})
            mass = {k: sum(r["raw"].get(k, 0.0) for r in rows) / len(rows) for k in classes}
            anger_keys = [k for k in classes if k in ANGER]
            rank2, mass_not_top, n_not_top = 0, 0.0, 0
            for r in rows:
                if not anger_keys:
                    continue
                a = max(r["raw"].get(k, 0.0) for k in anger_keys)
                ranked = sorted(r["raw"].items(), key=lambda kv: -kv[1])
                if ranked and ranked[0][0] not in ANGER:
                    n_not_top += 1
                    mass_not_top += a
                    if len(ranked) > 1 and ranked[1][0] in ANGER:
                        rank2 += 1
            per_model[data["model"]] = {
                "n_crops": len(rows),
                "argmax_counts": dict(counts),
                "argmax_share": {k: v / len(rows) for k, v in counts.items()},
                "three_counts": {k: v for k, v in three.items()},
                "mean_mass": {k: round(v, 6) for k, v in mass.items()},
                "anger_rank2": rank2,
                "anger_rank2_share": rank2 / n_not_top if n_not_top else 0.0,
                "anger_mean_mass_when_not_top": (mass_not_top / n_not_top) if n_not_top else 0.0,
                "n_not_top": n_not_top,
                "has_anger_class": bool(anger_keys),
            }
        if per_model:
            out[video_id] = per_model
    return out


# ── Bench A2 — detector disagreement inside faceless windows ─────────────────

# Four frames were opened and looked at on 03 Sep 2026 to test the hypothesis this
# function encodes. They are recorded here with what was seen, because the
# conclusion below rests on them and an unrecorded spot check is not evidence.
# This is a spot check, not part of §9's review: §9 remains the only human-labelled
# ground truth in this bench, and none of these four observations is used as a
# label anywhere.
INSPECTED_FRAMES = {
    "frame_0291.jpg": {"agreement": "unanimous", "segment": 41,
                       "section9_says": "Empty desk top-down shot",
                       "observed": "a large, clear, front-facing human face"},
    "frame_0176.jpg": {"agreement": "unanimous", "segment": 25,
                       "section9_says": "Phone in hand, b-roll",
                       "observed": "a large, clear human face holding a phone"},
    "frame_0059.jpg": {"agreement": "opencv only", "segment": 9,
                       "section9_says": "Phone in hand, b-roll",
                       "observed": "a phone held over a desk, no human face; the triple "
                                   "camera-lens cluster is visible"},
    "frame_0108.jpg": {"agreement": "opencv only", "segment": 17,
                       "section9_says": "Phone lock screen close-up",
                       "observed": "a phone lock screen held over a desk, no human face"},
}


# A spot check on the ground truth itself, not on any model. §9 is one person's
# review and this bench rests entirely on it, so its most extreme claim was opened
# and looked at. Recorded for the same reason as above: an unrecorded check is not
# evidence.
GROUND_TRUTH_SPOT_CHECKS = {
    "frame_0569.jpg": {
        "segment": 76,
        "section9_says": "Thumbs up, smiling — the single most contradictory case",
        "incumbent_label": "angry (0.9684)",
        "observed": "a thumbs-up gesture and a warm, mildly smiling expression; "
                    "nothing resembling anger",
        "verdict": "§9's ground truth holds; the incumbent's label is plainly wrong",
    },
}


def disagreement_analysis(video_id: str, min_confidence: float = 0.0) -> dict:
    """
    Separate genuine hallucinations from faces the ground truth never inspected.

    Bench A's pooled numbers say every detector fires inside roughly the same
    share of author-verified faceless windows (15-18 per cent of the frames in
    them). That is suspicious: if the incumbent's Haar cascade were the cause, the
    stronger detectors should fire far less.

    The resolution is that §9's ground truth is **segment-level, observed at the
    midpoint**. Its own methodology says the midpoint frame was opened for every
    segment with one or two neighbours only where it was ambiguous. A segment that
    is b-roll at its midpoint can still cut back to the talking head before it
    ends, and a detector firing there is right while the segment label says
    otherwise.

    So this splits detections inside faceless windows by how many detectors agree:

      unanimous     every detector fires. Most likely a real face outside the
                    frames §9 inspected. Two were opened and both were real faces.
      incumbent-only  only `opencv` fires. Most likely a genuine hallucination.
                    Two were opened and neither contained a human face.
      split         some subset fires. Ambiguous; reported, not interpreted.

    The consequence for the bench is stated plainly in the write-up: **midpoint
    pooling is the valid comparison** for Bench A, and the pooled figures overstate
    every detector's error, the incumbent's included.
    """
    gold_rows = GT.detection_set()
    gold = {r["segment_id"]: r for r in gold_rows}
    faceless = {i for i, r in gold.items() if not r["face_present"]}

    det: dict[str, dict[str, dict]] = {}
    for path in sorted(DETECTIONS.glob(f"{video_id}__*.json")):
        d = json.loads(path.read_text())
        det[d["detector"]] = {r["frame"]: r for r in d["rows"]}
    if not det:
        return {}
    names = sorted(det)
    incumbent = next((n for n in names
                      if C.DETECTORS.get(n, {}).get("incumbent")), None)

    def fires(name: str, frame: str) -> bool:
        r = det[name].get(frame)
        return bool(r) and any(c >= min_confidence for c in r["confidences"])

    ref = det[names[0]]
    buckets = {"unanimous": [], "incumbent_only": [], "split": []}
    n_in_window = 0
    for frame, row in sorted(ref.items()):
        sid = next((i for i in faceless
                    if gold[i]["start_time"] <= row["timestamp_s"] < gold[i]["end_time"]),
                   None)
        if sid is None:
            continue
        n_in_window += 1
        hits = [n for n in names if fires(n, frame)]
        if not hits:
            continue
        entry = {"frame": frame, "segment_id": sid, "detectors": hits,
                 "section9_quote": gold[sid]["quote"]}
        if len(hits) == len(names):
            buckets["unanimous"].append(entry)
        elif incumbent and hits == [incumbent]:
            buckets["incumbent_only"].append(entry)
        else:
            buckets["split"].append(entry)

    return {
        "video_id": video_id,
        "detectors_compared": names,
        "incumbent": incumbent,
        "frames_in_faceless_windows": n_in_window,
        "counts": {k: len(v) for k, v in buckets.items()},
        "no_detector_fires": n_in_window - sum(len(v) for v in buckets.values()),
        "buckets": buckets,
        "inspected": INSPECTED_FRAMES,
        "ground_truth_spot_checks": GROUND_TRUTH_SPOT_CHECKS,
    }


# ── Label-order check for the card-declared taxonomy ─────────────────────────

def label_order_check(video_id: str, model: str = "tanneru_beit_large",
                      min_agreement: int = 5) -> dict:
    """
    Test empirically that a model's class order is what its card says it is.

    `tanneru_beit_large` publishes `LABEL_0 … LABEL_6` in `config.json` and names
    the real order only in its README. `candidates.TANNERU_LABELS` uses that order.
    If the card is wrong, every prediction from this candidate is a permutation of
    the truth and its score is meaningless — so the claim is checked rather than
    trusted, as `CANDIDATE_MODELS.md` §4.2 commits to.

    The test needs no ground truth. On crops where at least `min_agreement` of the
    other candidates produce the same three-class reading, that consensus is a
    strong prior for what the face shows. If the card's order is correct, this
    model should agree with the consensus far above chance. If the order were
    permuted, agreement would collapse towards chance (about a third for three
    classes) while the model's *internal* confidence stayed high — the signature
    of a systematically mislabelled output.

    Reported as agreement with consensus, alongside the same figure for every
    other candidate, so "far above chance" is calibrated against models whose
    class order is not in question rather than against an arbitrary number.
    """
    from collections import Counter

    preds: dict[str, dict[str, str]] = {}
    for path in sorted(PREDICTIONS.glob(f"{video_id}__*.json")):
        data = json.loads(path.read_text())
        preds[data["model"]] = {r["crop"]: r["three"] for r in data["rows"]
                                if r["three"] is not None}
    if model not in preds or len(preds) < min_agreement + 1:
        return {}

    crops = set.intersection(*(set(v) for v in preds.values()))
    consensus: dict[str, str] = {}
    for crop in crops:
        votes = Counter(preds[m][crop] for m in preds if m != model)
        label, n = votes.most_common(1)[0]
        if n >= min_agreement:
            consensus[crop] = label

    out = {"video_id": video_id, "model_under_test": model,
           "crops_compared": len(crops), "consensus_crops": len(consensus),
           "min_agreement": min_agreement, "agreement": {}}
    if not consensus:
        return out
    for m, rows in preds.items():
        hits = sum(1 for crop, lab in consensus.items() if rows.get(crop) == lab)
        out["agreement"][m] = {
            "agree": hits, "n": len(consensus), "rate": hits / len(consensus),
            "is_model_under_test": m == model,
        }
    # The consensus excludes the model under test, so its own agreement is not
    # self-fulfilling. Every other model is scored against a consensus that does
    # include it, which biases *their* rates upward — stated so the comparison is
    # read as a floor for the model under test, not a like-for-like ranking.
    out["note"] = ("consensus is computed from the other candidates only for the "
                   "model under test; the remaining rows are self-inclusive and "
                   "therefore optimistic")
    return out


# ── Bench D — the dimensional arm ─────────────────────────────────────────────

def valence_analysis(video_id: str) -> dict:
    """
    Does a continuous valence separate the classes better than a 7-way argmax?

    `CANDIDATE_MODELS.md` Q4 asks whether the categorical framing is itself the
    problem, and §3.6 forbids fitting a valence threshold on the scored set. So
    this reports a **threshold-free** statistic instead: the probability that a
    randomly chosen POSITIVE segment carries a higher valence than a randomly
    chosen NEUTRAL one. That is the area under the ROC curve, computed here by its
    rank definition with ties counted as half, which needs no fitted parameter and
    therefore cannot overfit the sample it is measured on.

    0.5 means the valence carries no usable ordering. 1.0 means it orders the two
    classes perfectly. It is a descriptive result: §3.6 makes the dimensional arm
    ineligible for adoption on this sample size, and that stands whatever comes out.
    """
    gold_rows = GT.expression_set()
    gold_by_id = {r["segment_id"]: r["expression"] for r in gold_rows}
    all_rows = GT.detection_set()
    segments = sorted(
        [{"segment_id": r["segment_id"], "start_time": r["start_time"],
          "end_time": r["end_time"]} for r in all_rows],
        key=lambda s: s["segment_id"])

    out: dict[str, dict] = {}
    for path in sorted(PREDICTIONS.glob(f"{video_id}__*.json")):
        data = json.loads(path.read_text())
        extras = [k for k in (data["model_meta"].get("extras") or [])]
        if "valence" not in extras:
            continue
        by_seg: dict[int, list[float]] = {}
        for seg in segments:
            start, end = seg["start_time"], seg["end_time"]
            vals = [r["extra"]["valence"] for r in data["rows"]
                    if start <= r["timestamp_s"] < end
                    and isinstance(r.get("extra"), dict) and "valence" in r["extra"]]
            if vals:
                by_seg[seg["segment_id"]] = vals

        pos = [sum(v) / len(v) for i, v in by_seg.items() if gold_by_id.get(i) == "POSITIVE"]
        neu = [sum(v) / len(v) for i, v in by_seg.items() if gold_by_id.get(i) == "NEUTRAL"]
        out[data["model"]] = {
            "model": data["model"],
            "n_positive": len(pos), "n_neutral": len(neu),
            "mean_valence_positive": (sum(pos) / len(pos)) if pos else None,
            "mean_valence_neutral": (sum(neu) / len(neu)) if neu else None,
            "auc_positive_over_neutral": auc(pos, neu),
            "coverage": len(by_seg),
        }
    return out


def auc(positive: list[float], negative: list[float]) -> float | None:
    """
    P(a random positive scores above a random negative), ties counted as half.

    The rank definition of ROC AUC. Kept as a plain double loop rather than a
    ranking trick because the samples here are tens of items, and a readable
    definition is worth more than the speed.
    """
    if not positive or not negative:
        return None
    wins = 0.0
    for a in positive:
        for b in negative:
            wins += 1.0 if a > b else (0.5 if a == b else 0.0)
    return wins / (len(positive) * len(negative))


# ── Rendering ─────────────────────────────────────────────────────────────────

def _mcnemar_str(mc: dict | None, fallback: str = "— incumbent —") -> str:
    """
    Render a McNemar result with its direction.

    `b` counts items the reference got right and this candidate got wrong, `c` the
    reverse, so c > b means this candidate is ahead. Showing the direction matters:
    a small p-value alone says the two differ, not which one is better, and this
    bench has candidates that are significantly *worse* than the incumbent.
    """
    if not mc:
        return fallback
    if mc["n_discordant"] == 0:
        return "identical predictions"
    arrow = "better" if mc["c"] > mc["b"] else ("worse" if mc["c"] < mc["b"] else "tied")
    return (f"{arrow} p={mc['p_value']:.4f} "
            f"(min {mc['min_attainable_p']:.3f}, n={mc['n_discordant']})")


def _pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def render_detectors(res: dict) -> str:
    L = [f"BENCH A — face detection, {res['video_id']}, "
         f"{len(res['gold'])} segments "
         f"(pooling: {res['pooling']}, gate: confidence >= {res['min_confidence']})",
         f"{'detector':22s} {'FPR (20 faceless)':>18s} {'recall (57 faces)':>18s} "
         f"{'accuracy':>9s} {'95% CI':>16s} {'s/frame':>8s}  McNemar"]
    rows = sorted(res["detectors"].items(),
                  key=lambda kv: (kv[1].get("baseline", False), kv[1]["false_positive_rate"]))
    for name, r in rows:
        mcs = _mcnemar_str(r.get("mcnemar_vs_incumbent"))
        flag = " *" if r.get("incumbent") else ("  b" if r.get("baseline") else "  ")
        L.append(f"{name:22s}{flag}"
                 f"{r['false_positives']:3d}/{r['n_faceless']:<2d} {_pct(r['false_positive_rate'])} "
                 f"{r['true_positives']:3d}/{r['n_faced']:<2d} {_pct(r['recall'])} "
                 f"{_pct(r['accuracy'])} "
                 f"[{r['accuracy_ci95'][0]:.3f},{r['accuracy_ci95'][1]:.3f}] "
                 f"{r['seconds_per_frame']:7.3f}  {mcs}")
    L.append("  * incumbent    b degenerate baseline")
    return "\n".join(L)


def render_classifiers(res: dict) -> str:
    L = [f"BENCH B — emotion classification, {res['video_id']}, n={res['n']}"
         f"{' (strict tier only)' if res['strict_only'] else ''}, "
         f"gold {res['gold_distribution']}",
         f"{'model':22s} {'acc':>7s} {'95% CI':>16s} {'macroF1':>8s} "
         f"{'NEG invented':>13s} {'s/crop':>7s}  McNemar vs always-NEUTRAL"]
    rows = sorted(res["classifiers"].items(),
                  key=lambda kv: (kv[1].get("baseline", False), -kv[1]["accuracy"]))
    n_neutral = res["gold_distribution"].get("NEUTRAL", 0)
    for name, r in rows:
        mcs = _mcnemar_str(r.get("mcnemar_vs_always_neutral"), "— the floor —")
        neg_on_neutral = sum(1 for g, p in zip(res["gold"], r["_pred"])
                             if g == "NEUTRAL" and p == "NEGATIVE")
        flag = " *" if r.get("incumbent") else ("  b" if r.get("baseline") else "  ")
        L.append(f"{name:22s}{flag}{_pct(r['accuracy'])} "
                 f"[{r['accuracy_ci95'][0]:.3f},{r['accuracy_ci95'][1]:.3f}] "
                 f"{r['macro_f1']:8.4f} {neg_on_neutral:6d}/{n_neutral:<3d}  "
                 f"{r['seconds_per_crop']:6.3f}  {mcs}")
    L.append("  * incumbent    b degenerate baseline")
    L.append("  'NEG invented' = verified-neutral segments the model calls NEGATIVE")
    L.append("  the incumbent comparison is omitted on purpose: this sample is selected on")
    L.append("  its errors (CANDIDATE_MODELS.md A5), so the floor is the meaningful bar")
    return "\n".join(L)


def render_disagreement(res: dict) -> str:
    c = res["counts"]
    L = [f"BENCH A2 — detections inside author-verified faceless windows, {res['video_id']}",
         f"  detectors compared: {res['detectors_compared']}",
         f"  frames in those windows        : {res['frames_in_faceless_windows']}",
         f"  no detector fires              : {res['no_detector_fires']}",
         f"  all detectors fire (unanimous) : {c['unanimous']}   "
         f"-> likely real faces outside the frames §9 inspected",
         f"  incumbent ({res['incumbent']}) only        : {c['incumbent_only']}   "
         f"-> likely genuine hallucinations",
         f"  split decision                 : {c['split']}   -> ambiguous",
         "  frames opened and looked at (a spot check, not part of §9):"]
    for frame, info in res["inspected"].items():
        L.append(f"    {frame} [{info['agreement']}] §9: \"{info['section9_says']}\"")
        L.append(f"      observed: {info['observed']}")
    return "\n".join(L)


def render_label_order(res: dict) -> str:
    L = [f"LABEL-ORDER CHECK — is {res['model_under_test']}'s card-declared class order real?",
         f"  consensus crops (>= {res['min_agreement']} other candidates agree): "
         f"{res['consensus_crops']} of {res['crops_compared']}",
         f"  {'model':22s} {'agrees with consensus':>22s}"]
    for name, r in sorted(res["agreement"].items(), key=lambda kv: -kv[1]["rate"]):
        mark = " <- under test" if r["is_model_under_test"] else ""
        L.append(f"  {name:22s} {r['agree']:6d}/{r['n']:<4d} {_pct(r['rate']):>8s}{mark}")
    L.append(f"  {res['note']}")
    return "\n".join(L)


def render_valence(res: dict) -> str:
    L = ["BENCH D — the dimensional arm (threshold-free, descriptive only)",
         f"  {'model':22s} {'mean val POS':>13s} {'mean val NEU':>13s} "
         f"{'AUC':>7s} {'coverage':>9s}"]
    for name, r in sorted(res.items()):
        mp = "n/a" if r["mean_valence_positive"] is None else f"{r['mean_valence_positive']:.4f}"
        mn = "n/a" if r["mean_valence_neutral"] is None else f"{r['mean_valence_neutral']:.4f}"
        a = "n/a" if r["auc_positive_over_neutral"] is None else f"{r['auc_positive_over_neutral']:.4f}"
        L.append(f"  {name:22s} {mp:>13s} {mn:>13s} {a:>7s} "
                 f"{r['coverage']:5d}/77")
    L.append("  AUC 0.5 = the valence carries no usable ordering; 1.0 = perfect ordering")
    return "\n".join(L)


def render_anger(res: dict) -> str:
    L = ["BENCH C — where anger goes (no ground truth used)"]
    for video, models in res.items():
        L.append(f"\n  {video}")
        L.append(f"  {'model':22s} {'n':>5s} {'top-1 anger':>12s} {'top-1 sad':>10s} "
                 f"{'top-1 happy':>12s} {'anger mass':>11s} {'anger 2nd':>10s}")
        for name, r in sorted(models.items()):
            def share(*keys):
                return sum(r["argmax_share"].get(k, 0.0) for k in keys)
            L.append(f"  {name:22s} {r['n_crops']:5d} "
                     f"{_pct(share('angry', 'anger')):>12s} "
                     f"{_pct(share('sad', 'sadness')):>10s} "
                     f"{_pct(share('happy', 'happiness')):>12s} "
                     f"{sum(r['mean_mass'].get(k, 0.0) for k in ('angry', 'anger')):11.4f} "
                     f"{_pct(r['anger_rank2_share']):>10s}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", choices=["a", "b", "c", "all"], default="all")
    ap.add_argument("--video", default=RD.GROUND_TRUTH_VIDEO)
    ap.add_argument("--all-videos", action="store_true")
    ap.add_argument("--min-confidence", type=float, default=0.0)
    args = ap.parse_args()

    chk = GT.anchor_check()
    print(f"Ground-truth anchor: {'PASS' if chk['ok'] else 'FAIL'}  "
          f"({chk['rows_total']} segments, {chk['faceless_segments']} faceless)")
    if not chk["ok"]:
        for p in chk["problems"]:
            print("  !", p)
        return 1
    print()

    results: dict = {"anchor": chk}
    if args.bench in ("a", "all"):
        dis = disagreement_analysis(args.video, args.min_confidence)
        if dis:
            print(render_disagreement(dis)); print()
            results["bench_a_disagreement"] = dis
        for mode in ("midpoint", "any"):
            a = score_detectors(args.video, args.min_confidence, mode)
            print(render_detectors(a)); print()
            results[f"bench_a_{mode}"] = a
    if args.bench in ("b", "all"):
        b = score_classifiers(args.video)
        print(render_classifiers(b)); print()
        results["bench_b"] = b
        bs = score_classifiers(args.video, strict_only=True)
        results["bench_b_strict"] = bs
        bn = score_classifiers(args.video, mapping=C.THREE_CLASS_SURPRISE_NEUTRAL)
        results["bench_b_surprise_neutral"] = bn
        lo = label_order_check(args.video)
        if lo.get("agreement"):
            print(render_label_order(lo)); print()
        results["label_order_check"] = lo
        e = end_to_end(args.video)
        if e:
            print(render_end_to_end(e)); print()
        results["bench_e_end_to_end"] = e
        d = valence_analysis(args.video)
        if d:
            print(render_valence(d)); print()
        results["bench_d_valence"] = d
    if args.bench in ("c", "all"):
        videos = RD.BENCH_VIDEOS if args.all_videos else [args.video]
        c = anger_analysis(videos)
        print(render_anger(c)); print()
        results["bench_c"] = c

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if not k.startswith("_")}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o

    RESULTS.write_text(json.dumps(strip(results), indent=1))
    print(f"Wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
