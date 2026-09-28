"""
report_v2.py — score the v2 benches against the labels collected for them.

The unit is the **frame**, not the Whisper segment. v1 pooled frame predictions
into segments and scored the pooled result, which confounded the model's error
with the pooling rule's error (`../FACIAL_MODEL_ANALYSIS.md` §2.2). Here the
ground truth is collected at the frame and scored at the frame, so a number in
this file is a property of the model alone.

    Bench A   six detectors, on face presence over every frame the rater judged.
    Bench B   nine emotion models, three-class, over every frame the rater gave
              a readable expression.
    Ceiling   the rater against themselves on 48 hidden duplicates. No model can
              be expected to beat this, and v1 had no such number.

The arithmetic is `transcript_bench/metrics.py`, imported rather than copied:
Wilson intervals, per-class PRF, macro-F1, confusion matrices and the exact
McNemar test with `min_attainable_p` are written and unit-tested there.

PROTOCOL.md §7 says the holdout is scored once, after every dev decision is final
and written down. That is enforced here, not merely asserted: `--holdout` refuses
to run until `DEV_DECISION.json` exists, and it records the hash of the dev
results that decision was made on, so a later reader can tell whether dev was
revised afterwards.

Usage
-----
    python report_v2.py                     # dev, both benches, no holdout
    python report_v2.py --bench a
    python report_v2.py --mapping surprise_neutral
    python report_v2.py --freeze-dev        # write DEV_DECISION.json
    python report_v2.py --holdout           # only after the freeze
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
ROOT = V1.parents[1]

for _p in (str(HERE), str(V1), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import candidates as C                                          # noqa: E402
import ground_truth_v2 as GT                                    # noqa: E402
from research.transcript_bench import metrics as M              # noqa: E402

DETECTIONS = HERE / "detections"
PREDICTIONS = HERE / "predictions"
RESULTS = HERE / "bench_results_v2.json"
DEV_DECISION = HERE / "DEV_DECISION.json"

FACE, NO_FACE = "FACE", "NO_FACE"
BINARY = (FACE, NO_FACE)

ABSTAIN = "NO_PREDICTION"
SCORED_LABELS = M.LABELS + (ABSTAIN,)

# Mirrors of the deployed pipeline. Declared here rather than imported so that
# scoring does not pull DeepFace into every test run; `tests/test_facial_bench_v2.py`
# asserts these equal `pipeline.visual_module`'s, so they cannot drift silently.
DEPLOYED_DETECTOR = "yunet"          # visual_module.FACE_DETECTOR_BACKEND
PIPELINE_GATE = 0.50                 # visual_module.FACE_CONFIDENCE_THRESHOLD
DEPLOYED_CLASSIFIER = "deepface_fer"  # nothing was adopted in v1, so FER still runs

# The two mappings declared in PROTOCOL.md §5.2 before collection. Each pairs the
# rater's mapping with the models', because a sensitivity check that moved only
# one side would be comparing two different scales.
MAPPINGS: dict[str, tuple[dict, dict]] = {
    "primary": (GT.EXPRESSION_THREE, C.THREE_CLASS),
    "surprise_neutral": (GT.EXPRESSION_THREE_SURPRISE_NEUTRAL,
                         C.THREE_CLASS_SURPRISE_NEUTRAL),
}

# PROTOCOL.md §2: below this many rater-labelled anger frames, Q2 is reported as
# underpowered and no claim is made either way.
Q2_ANGER_FLOOR = 20
# PROTOCOL.md §9 condition 3.
MAX_NEGATIVE_ON_NEUTRAL = 0.15


class ProtocolError(RuntimeError):
    """Raised when an action the protocol forbids is attempted."""


# ── shared scoring ────────────────────────────────────────────────────────────

def summarise_with_abstain(gold: list[str], pred: list[str]) -> dict:
    """
    `metrics.summarise`, extended so a model that produces no label for a frame is
    counted as wrong rather than quietly dropped (PROTOCOL.md §8).

    Dropping would let a candidate raise its accuracy by declining to answer, which
    is not an improvement the pipeline can use: `visual_module` hands the
    orchestrator a `dominant` of None, and a channel with no reading is a channel
    that failed. The abstention is therefore a fourth column in the confusion
    matrix, never a gold class, and macro-F1 is still averaged over the three real
    classes so it stays comparable with v1 and with the other benches.

    Identical in rule to v1's `report_bench.summarise_with_abstain`; the test suite
    asserts the two agree on the same inputs rather than trusting this comment.
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


def _load(dirpath: Path, key: str) -> dict[str, dict]:
    out = {}
    for path in sorted(dirpath.glob("*.json")):
        data = json.loads(path.read_text())
        out[data[key]] = data
    return out


def _rows_by_uid(data: dict) -> dict[str, dict]:
    return {r["uid"]: r for r in data["rows"]}


# ── Bench A: face presence ────────────────────────────────────────────────────

def score_detectors(split: str | None = None, gate: float = 0.0,
                    raw: dict | None = None) -> dict:
    """
    Every detector on disk against the rater's face-presence labels.

    `gate` is the confidence a detection must reach to count. 0.0 is "any face the
    backend returned"; PIPELINE_GATE reproduces `visual_module`'s operating point.
    v1 measured that gate as inert (0 of 415 detections fell below it), so both are
    reported and the difference is stated rather than assumed.
    """
    gold_rows = GT.face_set(raw=raw, split=split)
    if not gold_rows:
        raise ProtocolError(f"no face-presence ground truth for split={split!r}")
    order = [r["uid"] for r in gold_rows]
    truth = {r["uid"]: r["has_face"] for r in gold_rows}
    gold = [FACE if truth[u] else NO_FACE for u in order]

    faced = [u for u in order if truth[u]]
    faceless = [u for u in order if not truth[u]]

    out: dict[str, dict] = {}
    for backend, data in _load(DETECTIONS, "backend").items():
        rows = _rows_by_uid(data)
        seen = {u: rows[u] for u in order if u in rows}
        if len(seen) != len(order):
            # A detector that did not cover the sample cannot be compared on it.
            out[backend] = {"detector": backend, "incomplete": True,
                            "n_scored": len(seen), "n_expected": len(order)}
            continue
        pred = [FACE if (seen[u]["detected"] and seen[u]["confidence"] >= gate)
                else NO_FACE for u in order]
        by_uid = dict(zip(order, pred))

        tp = sum(1 for u in faced if by_uid[u] == FACE)
        fp = sum(1 for u in faceless if by_uid[u] == FACE)
        correct = sum(g == p for g, p in zip(gold, pred))
        out[backend] = {
            "detector": backend,
            "deployed": backend == DEPLOYED_DETECTOR,
            "v1_incumbent": bool(C.DETECTORS.get(backend, {}).get("incumbent")),
            "n_frames": len(order),
            "accuracy": correct / len(order),
            "accuracy_ci95": list(M.wilson_interval(correct, len(order))),
            "recall": tp / len(faced) if faced else 0.0,
            "recall_ci95": list(M.wilson_interval(tp, len(faced))) if faced else [0.0, 0.0],
            "true_positives": tp, "n_faced": len(faced),
            "false_positives": fp, "n_faceless": len(faceless),
            "false_positive_rate": fp / len(faceless) if faceless else 0.0,
            "false_positive_rate_ci95": (list(M.wilson_interval(fp, len(faceless)))
                                         if faceless else [0.0, 0.0]),
            "precision": tp / (tp + fp) if (tp + fp) else 0.0,
            "confusion": M.confusion_matrix(gold, pred, labels=BINARY),
            "seconds_per_frame": data.get("seconds_per_frame"),
            "detections_below_gate": sum(
                1 for u in order
                if seen[u]["detected"] and seen[u]["confidence"] < gate),
            "_pred": pred,
        }

    # Degenerate baselines, scored as candidates rather than mentioned as caveats.
    for name, const in (("always_face", FACE), ("never_face", NO_FACE)):
        pred = [const] * len(order)
        correct = sum(g == p for g, p in zip(gold, pred))
        tp = len(faced) if const == FACE else 0
        fp = len(faceless) if const == FACE else 0
        out[name] = {
            "detector": name, "baseline": True, "deployed": False,
            "v1_incumbent": False, "n_frames": len(order),
            "accuracy": correct / len(order),
            "accuracy_ci95": list(M.wilson_interval(correct, len(order))),
            "recall": tp / len(faced) if faced else 0.0,
            "recall_ci95": list(M.wilson_interval(tp, len(faced))) if faced else [0.0, 0.0],
            "true_positives": tp, "n_faced": len(faced),
            "false_positives": fp, "n_faceless": len(faceless),
            "false_positive_rate": fp / len(faceless) if faceless else 0.0,
            "false_positive_rate_ci95": (list(M.wilson_interval(fp, len(faceless)))
                                         if faceless else [0.0, 0.0]),
            "precision": tp / (tp + fp) if (tp + fp) else 0.0,
            "confusion": M.confusion_matrix(gold, pred, labels=BINARY),
            "seconds_per_frame": 0.0, "detections_below_gate": 0,
            "_pred": pred,
        }

    ref = out.get(DEPLOYED_DETECTOR)
    if ref and "_pred" in ref:
        for name, rec in out.items():
            if name == DEPLOYED_DETECTOR or "_pred" not in rec:
                continue
            rec["mcnemar_vs_deployed"] = M.mcnemar_exact(gold, ref["_pred"], rec["_pred"])

    return {"split": split or "all", "gate": gate, "n_frames": len(order),
            "n_faced": len(faced), "n_faceless": len(faceless),
            "order": order, "gold": gold, "detectors": out}


# ── Bench B: expression ───────────────────────────────────────────────────────

def score_classifiers(split: str | None = None, mapping: str = "primary",
                      raw: dict | None = None) -> dict:
    """
    Every emotion model on disk against the rater's expression labels.

    A frame the rater could read but the crop detector missed is an abstention and
    is scored wrong (PROTOCOL.md §8), because that is exactly what the pipeline
    experiences: no crop, no reading, no channel.
    """
    if mapping not in MAPPINGS:
        raise ProtocolError(f"unknown mapping {mapping!r}; declared: {sorted(MAPPINGS)}")
    gold_map, model_map = MAPPINGS[mapping]

    gold_rows = GT.expression_set(raw=raw, mapping=gold_map, split=split)
    if not gold_rows:
        raise ProtocolError(f"no expression ground truth for split={split!r}")
    order = [r["uid"] for r in gold_rows]
    gold = [r["three"] for r in gold_rows]
    fine = {r["uid"]: r["fine"] for r in gold_rows}
    neutral_uids = [u for u, g in zip(order, gold) if g == M.LABELS[1]]
    anger_uids = [u for u in order if fine[u] == "angry"]
    negative_uids = [u for u, g in zip(order, gold) if g == "NEGATIVE"]

    def block(pred: list[str], meta: dict) -> dict:
        by_uid = dict(zip(order, pred))
        neg_on_neutral = sum(1 for u in neutral_uids if by_uid[u] == "NEGATIVE")
        anger_hits = sum(1 for u in anger_uids if by_uid[u] == "NEGATIVE")
        neg_hits = sum(1 for u in negative_uids if by_uid[u] == "NEGATIVE")
        return {
            **meta,
            **summarise_with_abstain(gold, pred),
            "negative_on_neutral": neg_on_neutral,
            "n_neutral": len(neutral_uids),
            "negative_on_neutral_rate": (neg_on_neutral / len(neutral_uids)
                                         if neutral_uids else 0.0),
            "anger_recall": anger_hits / len(anger_uids) if anger_uids else None,
            "anger_hits": anger_hits, "n_anger": len(anger_uids),
            "negative_recall": neg_hits / len(negative_uids) if negative_uids else None,
            "n_negative": len(negative_uids),
            "_pred": pred,
        }

    out: dict[str, dict] = {}
    for model, data in _load(PREDICTIONS, "model").items():
        rows = _rows_by_uid(data)
        pred = []
        for u in order:
            r = rows.get(u)
            top = r.get("top") if r else None
            pred.append(C.to_three(top, model_map) or ABSTAIN)
        spec = C.CLASSIFIERS.get(model)
        out[model] = block(pred, {
            "model": model,
            "deployed": model == DEPLOYED_CLASSIFIER,
            "published": getattr(spec, "published", None),
            "training_data": getattr(spec, "training_data", None),
            "seconds_per_crop": data.get("seconds_per_crop"),
            "n_crops": data.get("n_crops"),
        })

    for label in M.LABELS:
        out[f"always_{label}"] = block([label] * len(order),
                                       {"model": f"always_{label}", "baseline": True,
                                        "deployed": False})

    counts = {lab: gold.count(lab) for lab in M.LABELS}
    majority = max(counts, key=lambda k: counts[k])
    ref_name = f"always_{majority}"
    ref = out[ref_name]
    for name, rec in out.items():
        if name == ref_name:
            continue
        rec["mcnemar_vs_constant"] = M.mcnemar_exact(gold, ref["_pred"], rec["_pred"])
        rec["beats_constant"] = rec["accuracy"] > ref["accuracy"]

    return {"split": split or "all", "mapping": mapping, "n_frames": len(order),
            "class_counts": counts, "majority_class": majority,
            "constant_name": ref_name, "n_anger": len(anger_uids),
            "order": order, "gold": gold, "models": out}


# ── Adoption rule (PROTOCOL.md §9) ────────────────────────────────────────────

def evaluate_adoption(dev: dict, holdout: dict | None = None) -> dict:
    """
    The four conditions, applied exactly as written before any result was seen.

    Condition 1 is read as *significantly better*, not merely *significantly
    different*: McNemar is two-sided, so a model that loses to the constant at
    p < 0.05 satisfies the test and fails the intent. The direction check is
    explicit here so that reading cannot be lost.
    """
    ref = dev["constant_name"]
    verdicts: dict[str, dict] = {}
    for name, rec in dev["models"].items():
        if rec.get("baseline"):
            continue
        mc = rec["mcnemar_vs_constant"]
        c1 = bool(rec["beats_constant"] and mc["p_value"] < 0.05)
        c2 = rec["macro_f1"] > dev["models"][ref]["macro_f1"]
        c3 = rec["negative_on_neutral_rate"] <= MAX_NEGATIVE_ON_NEUTRAL
        c4: bool | None = None
        h = None
        if holdout is not None and name in holdout["models"]:
            h = holdout["models"][name]
            c4 = bool(h["beats_constant"] and h["mcnemar_vs_constant"]["p_value"] < 0.05)
        verdicts[name] = {
            "c1_beats_constant_dev": c1,
            "c1_p": mc["p_value"], "c1_min_attainable_p": mc["min_attainable_p"],
            "c1_accuracy": rec["accuracy"], "c1_constant_accuracy": dev["models"][ref]["accuracy"],
            "c2_macro_f1": c2,
            "c2_model_macro_f1": rec["macro_f1"],
            "c2_constant_macro_f1": dev["models"][ref]["macro_f1"],
            "c3_negative_on_neutral": c3,
            "c3_rate": rec["negative_on_neutral_rate"],
            "c3_limit": MAX_NEGATIVE_ON_NEUTRAL,
            "c4_repeats_on_holdout": c4,
            "c4_p": h["mcnemar_vs_constant"]["p_value"] if h else None,
            "adopt": bool(c1 and c2 and c3 and c4 is True),
        }
    adopted = [n for n, v in verdicts.items() if v["adopt"]]
    return {
        "constant": ref,
        "holdout_scored": holdout is not None,
        "verdicts": verdicts,
        "adopted": adopted,
        "decision": (adopted[0] if len(adopted) == 1 else
                     "NOTHING ADOPTED" if not adopted else
                     f"{len(adopted)} models qualified: {adopted}"),
    }


# ── Q2 (PROTOCOL.md §2) ───────────────────────────────────────────────────────

def q2_status(n_anger_collected: int, n_anger_split: int | None = None,
              split: str | None = None) -> dict:
    """
    Whether the anger question is answerable on the labels actually collected.

    The floor was fixed before collection precisely so that this call could not be
    made after seeing which answer it would give.

    It is applied to **all** collected anger frames, not to one split's share.
    PROTOCOL.md §2 says "if the collected labels contain fewer than 20 anger
    frames", and a split holds only part of the collection: applying the floor per
    split would make Q2 look differently powered depending on which half is being
    scored, which is not what was pre-registered. The split's own count is carried
    alongside because per-class recall is reported per split.
    """
    return {
        "n_anger_frames": n_anger_collected,
        "n_anger_in_split": n_anger_split,
        "split": split,
        "floor": Q2_ANGER_FLOOR,
        "underpowered": n_anger_collected < Q2_ANGER_FLOOR,
        "verdict": ("UNDERPOWERED — no claim is made either way (PROTOCOL.md §2)"
                    if n_anger_collected < Q2_ANGER_FLOOR else "answerable"),
    }


def n_anger_collected(raw: dict | None = None) -> int:
    """Anger frames across the whole collection, both splits — what §2's floor means."""
    return sum(1 for r in GT.expression_set(raw=raw) if r["fine"] == "angry")


# ── holdout gate (PROTOCOL.md §7) ─────────────────────────────────────────────

def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _dev_fingerprint(dev_a: dict, dev_b: dict, adoption: dict) -> str:
    return _digest({
        "a": {k: v.get("accuracy") for k, v in dev_a["detectors"].items()},
        "b": {k: v.get("accuracy") for k, v in dev_b["models"].items()},
        "verdicts": {k: {c: v[c] for c in v if c.startswith(("c1", "c2", "c3"))}
                     for k, v in adoption["verdicts"].items()},
    })


def freeze_dev(dev_a: dict, dev_b: dict, adoption: dict) -> dict:
    """Write the dev decision to disk. Until this exists, the holdout stays sealed."""
    payload = {
        "frozen_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "fingerprint": _dev_fingerprint(dev_a, dev_b, adoption),
        "constant": adoption["constant"],
        "dev_conditions_1_to_3": {
            k: {c: v[c] for c in ("c1_beats_constant_dev", "c2_macro_f1",
                                  "c3_negative_on_neutral")}
            for k, v in adoption["verdicts"].items()},
        "candidates_still_eligible": [
            k for k, v in adoption["verdicts"].items()
            if v["c1_beats_constant_dev"] and v["c2_macro_f1"] and v["c3_negative_on_neutral"]],
        "note": "Holdout unscored at the time of writing. PROTOCOL.md §7.",
    }
    DEV_DECISION.write_text(json.dumps(payload, indent=1))
    return payload


def require_frozen_dev() -> dict:
    if not DEV_DECISION.exists():
        raise ProtocolError(
            "the holdout is sealed until the dev decision is written down "
            "(PROTOCOL.md §7). Run `python report_v2.py --freeze-dev` first.")
    return json.loads(DEV_DECISION.read_text())


# ── printing ──────────────────────────────────────────────────────────────────

def _pct(x: float | None) -> str:
    return "  —  " if x is None else f"{x * 100:5.1f}%"


def print_bench_a(res: dict) -> None:
    print(f"\nBENCH A — face presence, {res['split']} split, gate {res['gate']:.2f}")
    print(f"  {res['n_frames']} frames · {res['n_faced']} with a face · "
          f"{res['n_faceless']} without\n")
    print(f"  {'detector':<14}{'acc':>7} {'95% CI':>15}  {'recall':>7} {'FP rate':>8}"
          f" {'prec':>7} {'s/frame':>8}  vs deployed")
    rows = sorted(res["detectors"].values(),
                  key=lambda r: -r.get("accuracy", -1))
    for r in rows:
        if r.get("incomplete"):
            print(f"  {r['detector']:<14}  incomplete ({r['n_scored']}/{r['n_expected']})")
            continue
        tag = "  ← deployed" if r["deployed"] else ("  (baseline)" if r.get("baseline") else "")
        mc = r.get("mcnemar_vs_deployed")
        p = f"p={mc['p_value']:.4f} (n={mc['n_discordant']})" if mc else "—"
        lo, hi = r["accuracy_ci95"]
        print(f"  {r['detector']:<14}{_pct(r['accuracy'])} [{lo*100:5.1f},{hi*100:5.1f}]"
              f"  {_pct(r['recall'])} {_pct(r['false_positive_rate'])} {_pct(r['precision'])}"
              f" {(r['seconds_per_frame'] or 0):8.3f}  {p}{tag}")


def print_bench_b(res: dict, ceiling: dict | None = None) -> None:
    counts = "  ".join(f"{k}={v}" for k, v in res["class_counts"].items())
    print(f"\nBENCH B — expression, {res['split']} split, mapping '{res['mapping']}'")
    print(f"  {res['n_frames']} frames · {counts}")
    print(f"  constant compared against: {res['constant_name']}\n")
    print(f"  {'model':<20}{'acc':>7} {'95% CI':>15}  {'macroF1':>8} {'NEG/neutral':>12}"
          f" {'abst':>5}  vs constant")
    rows = sorted(res["models"].values(), key=lambda r: -r["accuracy"])
    for r in rows:
        tag = "  ← deployed" if r.get("deployed") else ("  (baseline)" if r.get("baseline") else "")
        mc = r.get("mcnemar_vs_constant")
        if mc:
            arrow = "+" if r.get("beats_constant") else "-"
            p = f"{arrow} p={mc['p_value']:.4f} (n={mc['n_discordant']})"
        else:
            p = "—"
        lo, hi = r["accuracy_ci95"]
        print(f"  {r['model']:<20}{_pct(r['accuracy'])} [{lo*100:5.1f},{hi*100:5.1f}]"
              f"  {r['macro_f1']:8.3f} {r['negative_on_neutral']:>4}/{r['n_neutral']:<7}"
              f" {r['abstentions']:>5}  {p}{tag}")
    if ceiling and ceiling.get("n_pairs"):
        c = ceiling["three_agreement"]
        print(f"\n  rater self-agreement (ceiling): {c*100:.1f}% on "
              f"{ceiling['n_pairs']} hidden duplicates")
        over = [r["model"] for r in rows if r["accuracy"] > c and not r.get("baseline")]
        print(f"  models above the ceiling: {over or 'none'}")


def print_adoption(ad: dict, q2: dict) -> None:
    print(f"\nADOPTION RULE (PROTOCOL.md §9) — constant = {ad['constant']}")
    print(f"  {'model':<20}{'C1 sig>c':>9}{'C2 F1':>7}{'C3 neg':>8}{'C4 hold':>9}   verdict")
    for name, v in sorted(ad["verdicts"].items()):
        def mark(x): return " yes" if x is True else ("  no" if x is False else "   —")
        print(f"  {name:<20}{mark(v['c1_beats_constant_dev']):>9}{mark(v['c2_macro_f1']):>7}"
              f"{mark(v['c3_negative_on_neutral']):>8}{mark(v['c4_repeats_on_holdout']):>9}"
              f"   {'ADOPT' if v['adopt'] else ''}")
    print(f"\n  DECISION: {ad['decision']}"
          + ("" if ad["holdout_scored"] else "   (dev only — holdout not yet scored)"))
    split_note = ("" if q2["n_anger_in_split"] is None else
                  f" ({q2['n_anger_in_split']} in the {q2['split']} split)")
    print(f"\nQ2 (anger): {q2['n_anger_frames']} anger frames collected{split_note}, "
          f"floor {q2['floor']} → {q2['verdict']}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", choices=["a", "b", "all"], default="all")
    ap.add_argument("--mapping", choices=sorted(MAPPINGS), default="primary")
    ap.add_argument("--gate", type=float, default=0.0)
    ap.add_argument("--freeze-dev", action="store_true",
                    help="write DEV_DECISION.json and seal the dev decision")
    ap.add_argument("--holdout", action="store_true",
                    help="score the holdout (requires DEV_DECISION.json)")
    args = ap.parse_args()

    ceiling = GT.reliability()
    payload: dict = {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
                     "ceiling": {k: v for k, v in ceiling.items() if k != "disagreements"},
                     "align": True, "crop_detector": C.CROP_DETECTOR}

    dev_a = dev_b = None
    if args.bench in ("a", "all"):
        dev_a = score_detectors(split="dev", gate=args.gate)
        print_bench_a(dev_a)
        if args.gate == 0.0:
            gated = score_detectors(split="dev", gate=PIPELINE_GATE)
            moved = {k: v["detections_below_gate"] for k, v in gated["detectors"].items()
                     if v.get("detections_below_gate")}
            print(f"\n  at the pipeline gate ({PIPELINE_GATE:.2f}): "
                  f"{'detections dropped: ' + str(moved) if moved else 'no detection changes'}")
            payload["bench_a_dev_pipeline_gate"] = _strip(gated)
        payload["bench_a_dev"] = _strip(dev_a)

    if args.bench in ("b", "all"):
        dev_b = score_classifiers(split="dev", mapping=args.mapping)
        print_bench_b(dev_b, ceiling)
        payload["bench_b_dev"] = _strip(dev_b)
        alt = "surprise_neutral" if args.mapping == "primary" else "primary"
        sens = score_classifiers(split="dev", mapping=alt)
        payload["bench_b_dev_sensitivity"] = _strip(sens)
        print(f"\n  sensitivity ('{alt}' mapping): best model "
              f"{max((r for r in sens['models'].values() if not r.get('baseline')), key=lambda r: r['accuracy'])['model']} "
              f"at {_pct(max(r['accuracy'] for r in sens['models'].values() if not r.get('baseline')))}"
              f", constant {_pct(sens['models'][sens['constant_name']]['accuracy'])}")

    if dev_b is not None:
        q2 = q2_status(n_anger_collected(), dev_b["n_anger"], "dev")
        hold_a = hold_b = None
        if args.holdout:
            frozen = require_frozen_dev()
            hold_a = score_detectors(split="holdout", gate=args.gate)
            hold_b = score_classifiers(split="holdout", mapping=args.mapping)
            print_bench_a(hold_a)
            print_bench_b(hold_b, ceiling)
            payload["bench_a_holdout"] = _strip(hold_a)
            payload["bench_b_holdout"] = _strip(hold_b)
            payload["dev_decision"] = frozen
            payload["dev_unchanged_since_freeze"] = None  # filled below

        adoption = evaluate_adoption(dev_b, hold_b)
        print_adoption(adoption, q2)
        payload["adoption"] = adoption
        payload["q2"] = q2

        if args.holdout:
            fp = _dev_fingerprint(dev_a, dev_b, adoption) if dev_a else None
            same = (fp == payload["dev_decision"]["fingerprint"]) if fp else None
            payload["dev_unchanged_since_freeze"] = same
            if same is False:
                print("\n  WARNING: dev results differ from the frozen decision. "
                      "PROTOCOL.md §7 — the holdout is burned and this must be reported.")
        elif args.freeze_dev:
            if dev_a is None:
                raise ProtocolError("--freeze-dev needs both benches; drop --bench")
            frozen = freeze_dev(dev_a, dev_b, adoption)
            print(f"\n  dev decision frozen → {DEV_DECISION.name} "
                  f"({frozen['fingerprint'][:12]}…). Holdout may now be scored once.")

    RESULTS.write_text(json.dumps(payload, indent=1, default=str))
    print(f"\nwritten → {RESULTS.name}")
    return 0


def _strip(res: dict) -> dict:
    """Drop the per-frame prediction vectors from what gets persisted."""
    inner = "detectors" if "detectors" in res else "models"
    return {**res, inner: {k: {kk: vv for kk, vv in v.items() if kk != "_pred"}
                           for k, v in res[inner].items()}}


if __name__ == "__main__":
    raise SystemExit(main())
