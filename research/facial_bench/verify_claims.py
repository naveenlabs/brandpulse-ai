"""
verify_claims.py — re-derive every number this bench publishes, from source.

The project's evidence rule (README, "Engineering rules"): "If a number is quoted anywhere, it must be traceable to a file in
this repo that produced it." This script is that traceability, in the pattern
already used by `vocal_bench/verify_claims.py`, `verify_ab.py`,
`verify_speaker_norm.py` and `verify_damping_fix.py`.

Each claim is re-computed from raw data — the saved run, the detection files, the
prediction files, `PROTOTYPE_FINDINGS.md` itself — and compared against the value
written in `FACIAL_MODEL_ANALYSIS.md` and `CANDIDATE_MODELS.md`. Nothing is read
back from a summary file that this bench also wrote, except where the check is
explicitly that the summary agrees with the raw data.

    python research/facial_bench/verify_claims.py            # all claims
    python research/facial_bench/verify_claims.py --verbose  # print every claim

Exit code 0 if every claim holds, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(ROOT))

import candidates as C                                          # noqa: E402
import ground_truth as GT                                       # noqa: E402
import report_bench as RB                                       # noqa: E402
import run_detect as RD                                         # noqa: E402
from research.transcript_bench import metrics as M              # noqa: E402

FINDINGS = ROOT / "docs" / "PROTOTYPE_FINDINGS.md"
ANALYSIS = BENCH / "FACIAL_MODEL_ANALYSIS.md"
REGISTER = BENCH / "CANDIDATE_MODELS.md"

PASS, FAIL = [], []


def check(name: str, got, want, tol: float | None = None) -> None:
    if tol is not None and isinstance(got, (int, float)) and isinstance(want, (int, float)):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    (PASS if ok else FAIL).append((name, got, want))


def check_true(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append((name, condition, f"True {detail}".strip()))


def text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


# ── Group 1: the ground truth ────────────────────────────────────────────────

def verify_ground_truth() -> None:
    chk = GT.anchor_check()
    check_true("anchor check passes", chk["ok"], str(chk["problems"]))
    check("segments in the saved run", chk["segments_in_run"], 77)
    check("face-presence labels", chk["rows_total"], 77)
    check("faceless segments", chk["faceless_segments"], 20)
    check("segments with no stored label", chk["no_label_segments"], 5)

    rows = GT.load()
    check("segments with a verified face", sum(1 for r in rows if r["face_present"]), 57)
    expr = GT.expression_set()
    check("expression labels", len(expr), 44)
    check("expression labels, strict tier", len(GT.expression_set(strict_only=True)), 7)
    check("expression NEUTRAL", sum(1 for r in expr if r["expression"] == "NEUTRAL"), 38)
    check("expression POSITIVE", sum(1 for r in expr if r["expression"] == "POSITIVE"), 6)
    check("expression NEGATIVE", sum(1 for r in expr if r["expression"] == "NEGATIVE"), 0)
    check("face verified, expression unknown", len(GT.segments_without_expression()), 13)

    t = GT.SECTION9_TALLY
    check("§9 categories sum to the segment total",
          t["correct_no_face"] + t["false_positive"] + t["match"] + t["mismatch"], t["total"])
    check("§9 reported accuracy", round(t["accuracy"], 4), round(16 / 77, 4))

    floor = RB.summarise_with_abstain([r["expression"] for r in expr],
                                      ["NEUTRAL"] * len(expr))
    check("always-NEUTRAL floor", round(floor["accuracy"], 4), round(38 / 44, 4))


# ── Group 2: the §9 correction (Amendment A1) ────────────────────────────────

def verify_section9_correction() -> None:
    segs = GT.load_anchor_segments()
    check("segment 39 label in the saved run", segs[39]["dominant"], "angry")
    check("segment 39 confidence", round(float(segs[39]["confidence"]), 4), 0.4646)

    angry = [3, 26, 34, 35, 36, 39, 42, 43, 44, 51, 55, 56, 59, 63, 66, 72, 73]
    fear = [33, 37, 40, 46, 62]
    conf = {i: float(segs[i]["confidence"]) for i in angry + fear}
    check("angry group minimum with segment 39",
          round(min(conf[i] for i in angry), 2), 0.46)
    check("angry group maximum", round(max(conf[i] for i in angry), 2), 0.95)
    check("angry group minimum without segment 39",
          round(min(conf[i] for i in angry if i != 39), 4), 0.5277)
    check("fear group minimum without segment 39",
          round(min(conf[i] for i in fear), 2), 0.40)
    check("fear group maximum without segment 39",
          round(max(conf[i] for i in fear), 2), 0.70)

    body = text(FINDINGS)
    check_true("§9 lists segment 39 in the angry row",
               "| 3, 26, 34, 35, 36, 39, 42," in body)
    check_true("§9 no longer lists segment 39 in the fear row",
               "| 33, 37, 40, 46, 62 |" in body and "| 33, 37, 39, 40, 46, 62 |" not in body)
    check_true("the correction is dated in §9", "Correction, 03 Sep 2026" in body)
    check_true("the correction is recorded as Amendment A1 in the register",
               "### A1 — 03 Sep 2026" in text(REGISTER))


# ── Group 2b: the incumbent's label distribution on the ground-truth video ───

def verify_incumbent_distribution() -> None:
    """
    §1.2 of the register contrasts this video's label mix with §12D's second video.
    Both halves are re-derived: this one from the saved run, the other from the
    numbers §12D publishes, checked against the document text itself.
    """
    segs = GT.load_anchor_segments()
    from collections import Counter
    dist = Counter(s["dominant"] for s in segs.values())
    check("saved run: total segments", sum(dist.values()), 77)
    check("saved run: 'angry' segments", dist["angry"], 20)
    check("saved run: 'sad' segments", dist["sad"], 25)
    check("saved run: 'happy' segments", dist["happy"], 1)
    check("saved run: 'fear' segments", dist["fear"], 11)
    check("saved run: 'neutral' segments", dist["neutral"], 13)
    check("saved run: 'surprise' segments", dist["surprise"], 2)
    check("saved run: segments with no label", dist[None], 5)
    check("share of segments labelled angry", round(20 / 77, 3), 0.260)
    check("share of segments labelled happy", round(1 / 77, 3), 0.013)

    # The second video's figures are quoted from §12D, not recomputed here — the
    # per-frame output that section analysed was never persisted. Checking the
    # document still contains them stops a quoted number drifting from its source.
    body = text(FINDINGS)
    check_true("§12D's 37.2% sad-on-real-faces figure is in the document",
               "37.2%" in body)
    check_true("§12D's 341 real-face frames are in the document", "341 frames" in body)
    check_true("§12D's angry count of 1 is in the document", "angry 1 (0.3%)" in body)


# ── Group 3: the incumbent's confidence gate ─────────────────────────────────

def verify_confidence_gate() -> None:
    path = BENCH / "detections" / f"{GT.ANCHOR_VIDEO}__opencv.json"
    if not path.exists():
        return
    d = json.loads(path.read_text())
    conf = [c for r in d["rows"] for c in r["confidences"]]
    check("opencv detections on the ground-truth video", len(conf), 415)
    check("opencv frames with a face", d["frames_with_face"], 363)
    check("lowest opencv face confidence", round(min(conf), 4), 0.8800)
    check("highest opencv face confidence", round(max(conf), 4), 1.0100)
    check_true("opencv's 'confidence' is not a probability: it exceeds 1",
               max(conf) > 1.0)

    from pipeline.visual_module import FACE_CONFIDENCE_THRESHOLD
    check("the pipeline's face-confidence gate", FACE_CONFIDENCE_THRESHOLD, 0.50)
    check("detections the gate rejects",
          sum(1 for c in conf if c < FACE_CONFIDENCE_THRESHOLD), 0)
    check_true("the gate is inert: the lowest confidence is above it",
               min(conf) > FACE_CONFIDENCE_THRESHOLD)

    # §9's proposed fix 1 was to raise this threshold. Measured effect of doing so.
    gold = {r["segment_id"]: r for r in GT.detection_set()}
    segs = sorted([{"segment_id": r["segment_id"], "start_time": r["start_time"],
                    "end_time": r["end_time"]} for r in gold.values()],
                  key=lambda x: x["segment_id"])
    faceless = [i for i, g in gold.items() if not g["face_present"]]
    faced = [i for i, g in gold.items() if g["face_present"]]

    def at(gate: float) -> tuple[int, int]:
        gated = [{**r, "n_faces": sum(1 for c in r["confidences"] if c >= gate)}
                 for r in d["rows"]]
        pooled = RD.pool_to_segments(gated, segs, "any")
        return (sum(1 for i in faceless if pooled[i]["face_present"]),
                sum(1 for i in faced if pooled[i]["face_present"]))

    check("at the deployed gate: false positives, recall", at(0.50), (15, 57))
    check("raising the gate to 0.94", at(0.94), (14, 57))
    check("raising the gate to 0.96", at(0.96), (11, 48))
    check("raising the gate to 0.98", at(0.98), (6, 25))

    # The sweep reproduces §9's own false-positive set exactly, segment for
    # segment — not merely the same count. This is what validates both the
    # harness and the derived correct-no-face group in ground_truth.py.
    pooled = RD.pool_to_segments(d["rows"], segs, "any")
    fired = sorted(i for i in faceless if pooled[i]["face_present"])
    tabulated = sorted(i for i in faceless if gold[i]["group"] == "no_face")
    derived = sorted(i for i in faceless if gold[i]["group"] == "correct_no_face")
    check("opencv fires on exactly §9's tabulated false positives", fired, tabulated)
    check("§9's tabulated false positives", len(tabulated), 15)
    check("opencv fires on none of §9's correct-no-face segments",
          [i for i in derived if pooled[i]["face_present"]], [])
    check("§9's correct-no-face segments", derived, [16, 49, 64, 65, 68])


# ── Group 4: Bench A ─────────────────────────────────────────────────────────

def _bench_a(mode: str) -> dict:
    return RB.score_detectors(GT.ANCHOR_VIDEO, 0.0, mode)


def verify_bench_a() -> None:
    if not list((BENCH / "detections").glob(f"{GT.ANCHOR_VIDEO}__*.json")):
        return
    for mode in ("midpoint", "any"):
        res = _bench_a(mode)
        for name, r in res["detectors"].items():
            if r.get("baseline"):
                continue
            check(f"[{mode}] {name}: FPR denominator", r["n_faceless"], 20)
            check(f"[{mode}] {name}: recall denominator", r["n_faced"], 57)
            check(f"[{mode}] {name}: accuracy is consistent with its confusion matrix",
                  round(r["accuracy"], 6),
                  round((r["true_positives"] + (20 - r["false_positives"])) / 77, 6))
        check(f"[{mode}] always-face accuracy",
              round(res["detectors"]["always_face"]["accuracy"], 6), round(57 / 77, 6))
        check(f"[{mode}] never-face accuracy",
              round(res["detectors"]["never_face"]["accuracy"], 6), round(20 / 77, 6))


# The Bench A tables in FACIAL_MODEL_ANALYSIS.md §6.1 and §6.2, as written.
BENCH_A_MIDPOINT = {
    #                       FP/20, recall/57, accuracy, s/frame
    "mtcnn (midpoints only)": (0, 54, 0.961, 4.637),
    "yolov8n":                (1, 55, 0.961, 0.113),
    "retinaface":             (1, 54, 0.948, 1.137),
    "yunet":                  (0, 52, 0.935, 0.062),
    "opencv":                 (1, 47, 0.857, 0.433),
    "ssd":                    (0, 29, 0.636, 0.077),
}
BENCH_A_POOLED = {
    "ssd":        (8, 56, 0.883),
    "yolov8n":    (9, 57, 0.883),
    "yunet":      (9, 56, 0.870),
    "retinaface": (9, 56, 0.870),
    "opencv":     (15, 57, 0.805),
}


def verify_bench_a_tables() -> None:
    if not list((BENCH / "detections").glob(f"{GT.ANCHOR_VIDEO}__*.json")):
        return
    mid = RB.score_detectors(GT.ANCHOR_VIDEO, 0.0, "midpoint")["detectors"]
    for name, (fp, rec, acc, sec) in BENCH_A_MIDPOINT.items():
        if name not in mid:
            continue
        check(f"[midpoint] {name}: false positives", mid[name]["false_positives"], fp)
        check(f"[midpoint] {name}: recall", mid[name]["true_positives"], rec)
        check(f"[midpoint] {name}: accuracy", round(mid[name]["accuracy"], 3), acc, tol=0.0006)
        check(f"[midpoint] {name}: seconds per frame",
              mid[name]["seconds_per_frame"], sec, tol=0.001)

    pooled = RB.score_detectors(GT.ANCHOR_VIDEO, 0.0, "any")["detectors"]
    for name, (fp, rec, acc) in BENCH_A_POOLED.items():
        if name not in pooled:
            continue
        check(f"[any] {name}: false positives", pooled[name]["false_positives"], fp)
        check(f"[any] {name}: recall", pooled[name]["true_positives"], rec)
        check(f"[any] {name}: accuracy", round(pooled[name]["accuracy"], 3), acc, tol=0.0006)

    check_true("mtcnn has no pooled score, by design",
               "mtcnn (midpoints only)" in mid and
               not any(k.startswith("mtcnn") for k in pooled))

    # §6.1's claim that the four leaders are indistinguishable.
    gold = RB.score_detectors(GT.ANCHOR_VIDEO, 0.0, "midpoint")["gold"]
    leaders = [n for n in ("mtcnn (midpoints only)", "yolov8n", "retinaface", "yunet")
               if n in mid]
    import itertools
    for a, b in itertools.combinations(leaders, 2):
        mc = M.mcnemar_exact(gold, mid[a]["_pred"], mid[b]["_pred"])
        check_true(f"{a} and {b} are not distinguishable", mc["p_value"] >= 0.05,
                   f"p={mc['p_value']:.4f}")
    for name in leaders:
        mc = mid[name].get("mcnemar_vs_incumbent")
        check_true(f"{name} is better than the incumbent, not worse", mc["c"] >= mc["b"])


def verify_disagreement() -> None:
    res = RB.disagreement_analysis(GT.ANCHOR_VIDEO)
    if not res:
        return
    c = res["counts"]
    total = sum(c.values()) + res["no_detector_fires"]
    check("disagreement buckets account for every frame in a faceless window",
          total, res["frames_in_faceless_windows"])
    check_true("the incumbent is identified", res["incumbent"] == "opencv")
    check_true("every inspected frame is recorded with what was seen",
               all(v.get("observed") for v in res["inspected"].values()))
    for frame in res["inspected"]:
        check_true(f"{frame} exists on disk",
                   (ROOT / "data" / GT.ANCHOR_VIDEO / "frames" / frame).exists())

    # The ground-truth spot check must name a frame that really is the midpoint of
    # the segment it claims, and the incumbent label quoted must be the stored one.
    segs = GT.load_anchor_segments()
    for frame, info in res.get("ground_truth_spot_checks", {}).items():
        sid = info["segment"]
        mid = (segs[sid]["start_time"] + segs[sid]["end_time"]) / 2
        check(f"{frame} is the midpoint frame of segment {sid}",
              f"frame_{round(mid):04d}.jpg", frame)
        check(f"segment {sid}: quoted incumbent label",
              f"{segs[sid]['dominant']} ({segs[sid]['confidence']})",
              info["incumbent_label"])
        check_true(f"{frame} exists on disk",
                   (ROOT / "data" / GT.ANCHOR_VIDEO / "frames" / frame).exists())


# ── Group 5: Bench B and the candidate register ──────────────────────────────

def verify_bench_b() -> None:
    if not list((BENCH / "predictions").glob(f"{GT.ANCHOR_VIDEO}__*.json")):
        return
    res = RB.score_classifiers(GT.ANCHOR_VIDEO)
    check("Bench B sample size", res["n"], 44)
    check("Bench B gold distribution", res["gold_distribution"],
          {"POSITIVE": 6, "NEUTRAL": 38, "NEGATIVE": 0})
    check("always-NEUTRAL baseline accuracy",
          round(res["classifiers"]["always_neutral"]["accuracy"], 6), round(38 / 44, 6))
    for name, r in res["classifiers"].items():
        n_right = sum(1 for g, p in zip(res["gold"], r["_pred"]) if g == p)
        check(f"{name}: accuracy matches its own predictions",
              round(r["accuracy"], 6), round(n_right / 44, 6))


def verify_register() -> None:
    reg = text(REGISTER)
    check_true("the register exists", bool(reg))
    # The register's §4.2 table names every candidate, the incumbent in bold.
    table = re.findall(r"^\| \*{0,2}`([a-z0-9_]+)`\*{0,2} \|", reg, re.M)
    check("candidates named in the register's candidate table",
          len(set(table) & set(C.CLASSIFIERS)), len(C.CLASSIFIERS))
    check("classifiers defined in code", len(C.CLASSIFIERS), 9)
    check("detectors defined in code", len(C.DETECTORS), 6)
    for name in C.CLASSIFIERS:
        check_true(f"{name} appears in the register", name in reg)
    for name in C.DETECTORS:
        check_true(f"detector {name} appears in the register", name in reg)
    for name in C.EXCLUDED_DETECTORS:
        check_true(f"excluded detector {name} is documented", name in reg)
    check_true("the zero-NEGATIVE limitation is stated before the results",
               "0 NEGATIVE" in reg or "zero NEGATIVE" in reg)
    check_true("the surprise mapping is declared as a judgement call",
               "judgement call" in reg and "surprise" in reg)


# ── Group 5b: the taxonomy every candidate shares ────────────────────────────

# Every candidate's class list, taken from its own config, source or model card.
# Written out rather than introspected so the check is against a fixed record and
# a silent upstream relabelling fails here instead of changing a published number.
CANDIDATE_LABELS = {
    "deepface_fer":       ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"],
    "trpakov_vit":        ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"],
    "motheecreator_vit":  ["anger", "disgust", "fear", "happy", "neutral", "sad", "surprise"],
    "dima806_vit":        ["sad", "disgust", "angry", "neutral", "fear", "surprise", "happy"],
    "hardlyhumans_vit":   ["anger", "contempt", "disgust", "fear", "happy", "neutral", "sad", "surprise"],
    "tanneru_beit_large": ["anger", "disgust", "fear", "happy", "neutral", "sad", "surprise"],
    "dan_affectnet8":     ["neutral", "happy", "sad", "surprise", "fear", "disgust", "anger", "contempt"],
    "emotieffnet_b0_va":  ["anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"],
    "emotieffnet_b2":     ["anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"],
}

# The eight concepts those eleven strings denote.
CONCEPTS = {"anger", "contempt", "disgust", "fear", "happiness", "neutral",
            "sadness", "surprise"}


def verify_taxonomy() -> None:
    check("candidates with a recorded label set",
          sorted(CANDIDATE_LABELS), sorted(C.CLASSIFIERS))
    union = sorted({lab for labs in CANDIDATE_LABELS.values() for lab in labs})
    check("distinct label strings across every candidate", len(union), 11)
    check("the union of every candidate's classes", union,
          ["anger", "angry", "contempt", "disgust", "fear", "happiness", "happy",
           "neutral", "sad", "sadness", "surprise"])

    # Eleven strings, eight concepts: angry/anger, sad/sadness and happy/happiness
    # are the same class spelled differently.
    normalised = {"angry": "anger", "sad": "sadness", "happy": "happiness"}
    concepts = {normalised.get(lab, lab) for lab in union}
    check("distinct emotion concepts across every candidate", concepts, CONCEPTS)
    check("distinct emotion concepts, count", len(concepts), 8)

    for word in ("frustration", "frustrated", "disappointment", "disappointed",
                 "confusion", "boredom"):
        check_true(f"no candidate can emit '{word}'", word not in union)
        check_true(f"'{word}' has no three-class mapping", C.to_three(word) is None)

    for name, labs in CANDIDATE_LABELS.items():
        check(f"{name}: class count matches the register",
              len(labs), C.CLASSIFIERS[name].n_classes)
        unmapped = [lab for lab in labs if C.to_three(lab) is None]
        check(f"{name}: every class maps to a three-class value", unmapped, [])


# ── Group 6: the pipeline-fidelity anchor ────────────────────────────────────

def verify_pipeline_anchor() -> None:
    path = BENCH / "anchor_pipeline.json"
    if not path.exists():
        return
    d = json.loads(path.read_text())
    check("anchor ran over every frame", d["n_frames"], 572)
    check("anchor segment count", d["n_segments"], 77)
    check("anchor agreement is consistent with its own rows",
          d["label_matches"], sum(1 for r in d["rows"] if r["label_match"]))
    check("anchor mismatch list is consistent",
          len(d["mismatches"]), d["n_segments"] - d["label_matches"])
    check("anchor agreement rate",
          round(d["label_agreement"], 4), round(d["label_matches"] / d["n_segments"], 4))
    check("anchor reproduced every segment label", d["label_matches"], 77)
    check("anchor reproduced every confidence", d["confidence_matches"], 77)

    # The bench's own opencv sweep must find a face on exactly the frames the
    # pipeline does. This is the check that licenses calling the bench's opencv
    # row "the incumbent" (Amendment A3).
    sweep = BENCH / "detections" / f"{GT.ANCHOR_VIDEO}__opencv.json"
    if sweep.exists():
        sd = json.loads(sweep.read_text())
        check_true("the sweep aligns, as the pipeline does", sd.get("align") is True)
        check("bench and pipeline agree on frames with a face",
              sd["frames_with_face"], d["frames_with_face"])
        bench_frames = {r["frame"] for r in sd["rows"] if r["n_faces"] > 0}
        pipe_frames = {r["frame"] for r in d["frame_level"]
                       if r["dominant_emotion"] is not None}
        check("bench and pipeline agree frame by frame",
              len(bench_frames ^ pipe_frames), 0)


# ── Group 6b: the composite reproduces §9's own headline figure ──────────────

def verify_end_to_end() -> None:
    res = RB.end_to_end(GT.ANCHOR_VIDEO)
    dep = res.get("deployed")
    if not dep:
        return
    check("deployed arm: segments scored", dep["n_segments"], 77)
    check("deployed arm: unknown segments", dep["unknown"], 13)
    check("deployed arm: right + wrong + unknown", 
          dep["right"] + dep["wrong"] + dep["unknown"], 77)
    check("deployed arm: false faces on verified-faceless segments",
          dep["false_face"], 15)
    check("deployed arm: segments right", dep["right"], 6)

    # §9's own published 16/77 must fall inside the interval, and it must fall at
    # exactly the point where 10 of the 13 unknowns are right — because §9 counts
    # 11 matches, of which one (segment 53) is already inside the labelled set.
    lo, hi = dep["accuracy_lower"], dep["accuracy_upper"]
    s9 = res["_section9"]["accuracy"]
    check_true("§9's 16/77 falls inside the deployed arm's interval", lo <= s9 <= hi)
    check("§9's figure equals the deployed arm plus 10 of the 13 unknowns",
          dep["right"] + 10, res["_section9"]["right"])
    check("§9's unlabelled matches", GT.SECTION9_TALLY["match"] - 1, 10)
    check("§9's headline accuracy", round(s9, 4), round(16 / 77, 4))

    # The 44-segment table is selected on the incumbent's errors (Amendment A5).
    # Its incumbent figure is recorded so the write-up cannot quote it as accuracy
    # without the caveat, and so the bias's size stays visible.
    expr = GT.expression_set()
    gold = [r["expression"] for r in expr]
    stored = GT.load_anchor_segments()
    pred = [C.to_three(stored[r["segment_id"]]["dominant"]) or RB.ABSTAIN
            for r in expr]
    inc = RB.summarise_with_abstain(gold, pred)
    check("selected-sample incumbent accuracy", round(inc["accuracy"], 4),
          round(1 / 44, 4))
    neg_on_neutral = sum(1 for g, p in zip(gold, pred)
                         if g == "NEUTRAL" and p == "NEGATIVE")
    check("incumbent calls every verified-neutral segment NEGATIVE",
          neg_on_neutral, 38)
    check_true("the selection effect is recorded as an amendment",
               "### A5 — 03 Sep 2026" in text(REGISTER))


# ── Group 6c: Bench B, the adoption, and the anger analysis ──────────────────

# Each candidate's own published headline figure, as its card or repository states
# it. Recorded here so §7.1's rank correlation is checkable against a fixed record.
PUBLISHED = {
    "deepface_fer": 57.40, "trpakov_vit": 71.16, "motheecreator_vit": 84.34,
    "dima806_vit": 90.92, "hardlyhumans_vit": 92.20, "tanneru_beit_large": 73.57,
    "dan_affectnet8": 62.09, "emotieffnet_b0_va": 61.93, "emotieffnet_b2": 63.03,
}


def _spearman(a: list[float], b: list[float]) -> float:
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    den = (sum((x - ma) ** 2 for x in ra) * sum((x - mb) ** 2 for x in rb)) ** 0.5
    return num / den if den else 0.0


def verify_bench_b_detail() -> None:
    if len(list((BENCH / "predictions").glob(f"{GT.ANCHOR_VIDEO}__*.json"))) < 9:
        return
    res = RB.score_classifiers(GT.ANCHOR_VIDEO)["classifiers"]
    check("classifiers scored", len([k for k, v in res.items() if not v.get("baseline")]), 9)

    quoted = {
        "trpakov_vit": 0.795, "deepface_fer": 0.568, "emotieffnet_b0_va": 0.182,
        "motheecreator_vit": 0.182, "dan_affectnet8": 0.136, "emotieffnet_b2": 0.136,
        "tanneru_beit_large": 0.136, "dima806_vit": 0.091, "hardlyhumans_vit": 0.045,
        "always_neutral": 0.864,
    }
    for name, want in quoted.items():
        check(f"Bench B accuracy: {name}", round(res[name]["accuracy"], 3), want, tol=0.0006)

    check_true("no candidate beats the always-NEUTRAL floor",
               all(res[n]["accuracy"] < res["always_neutral"]["accuracy"]
                   for n in PUBLISHED))
    best = max(PUBLISHED, key=lambda n: res[n]["accuracy"])
    check("the best candidate", best, "trpakov_vit")
    check_true("the best candidate is not detectably worse than the floor",
               res[best]["mcnemar_vs_always_neutral"]["p_value"] >= 0.05)
    for name in PUBLISHED:
        if name == best:
            continue
        check_true(f"{name} is significantly worse than the floor",
                   res[name]["mcnemar_vs_always_neutral"]["p_value"] < 0.05)

    # §7.1 — the published ranking does not predict the measured one.
    names = sorted(PUBLISHED)
    rho = _spearman([PUBLISHED[n] for n in names],
                    [res[n]["accuracy"] for n in names])
    check("Spearman, published vs measured", round(rho, 4), -0.6214, tol=0.0001)
    check_true("the correlation is negative, not merely weak", rho < 0)

    # §9.3 — inventing NEGATIVE on verified-neutral segments.
    full = RB.score_classifiers(GT.ANCHOR_VIDEO)
    gold = full["gold"]
    def invented(model: str) -> int:
        return sum(1 for g, p in zip(gold, full["classifiers"][model]["_pred"])
                   if g == "NEUTRAL" and p == "NEGATIVE")
    check("trpakov invents NEGATIVE on verified-neutral segments", invented("trpakov_vit"), 3)
    check("deepface on good crops invents NEGATIVE", invented("deepface_fer"), 14)
    check("hardlyhumans invents NEGATIVE", invented("hardlyhumans_vit"), 22)


def verify_adoption() -> None:
    path = BENCH / "adopt_rerun.json"
    if not path.exists():
        return
    d = json.loads(path.read_text())
    from pipeline.visual_module import FACE_DETECTOR_BACKEND
    check("the adopted backend", FACE_DETECTOR_BACKEND, "yunet")
    check("the rerun measured the adopted backend", d["after"]["backend"], FACE_DETECTOR_BACKEND)
    check("before: segments right", d["before"]["right"], 6)
    check("after: segments right", d["after"]["right"], 11)
    check("before: false faces", d["before"]["false_face"], 15)
    check("after: false faces", d["after"]["false_face"], 9)
    check("before: wrong labels", d["before"]["wrong_label"], 43)
    check("after: wrong labels", d["after"]["wrong_label"], 44)
    check("after: seconds per frame", d["after"]["seconds_per_frame"], 0.0989, tol=0.0001)
    check("segments whose label changed", len(d["segments_changed"]), 24)
    check("adoption McNemar p", round(d["mcnemar_after_vs_before"]["p_value"], 4), 0.1250)
    check_true("the adoption is not statistically significant, and the write-up says so",
               d["mcnemar_after_vs_before"]["p_value"] >= 0.05
               and "not statistically significant" in text(ANALYSIS))
    check_true("the false-positive reduction is real",
               d["after"]["false_face"] < d["before"]["false_face"])
    check_true("the deviation from the rule is declared",
               "### A6 — 03 Sep 2026" in text(REGISTER))


def verify_anger() -> None:
    res = RB.anger_analysis([GT.ANCHOR_VIDEO]).get(GT.ANCHOR_VIDEO)
    if not res or len(res) < 9:
        return
    def share(model: str, *keys) -> float:
        return sum(res[model]["argmax_share"].get(k, 0.0) for k in keys)

    check("incumbent: top-1 anger", round(100 * share("deepface_fer", "angry", "anger"), 1), 12.6)
    check("incumbent: top-1 sad", round(100 * share("deepface_fer", "sad", "sadness"), 1), 25.4)
    check_true("sadness beats anger for the incumbent",
               share("deepface_fer", "sad", "sadness") > share("deepface_fer", "angry", "anger"))
    check("incumbent: anger ranked second when not first",
          round(100 * res["deepface_fer"]["anger_rank2_share"], 1), 94.5)

    angers = {m: share(m, "angry", "anger") for m in res}
    sads = {m: share(m, "sad", "sadness") for m in res}
    check("lowest top-1 anger across candidates", round(100 * min(angers.values()), 1), 2.4)
    check("highest top-1 anger across candidates", round(100 * max(angers.values()), 1), 22.5)
    check("lowest top-1 sad across candidates", round(100 * min(sads.values()), 1), 5.8)
    check("highest top-1 sad across candidates", round(100 * max(sads.values()), 1), 46.6)
    check_true("every candidate saw the same number of crops",
               len({r["n_crops"] for r in res.values()}) == 1)
    check("crops every candidate was scored on",
          next(iter(res.values()))["n_crops"], 414)

    # §7.2 — tanneru is degenerate, not mislabelled.
    check("tanneru's dominant class share",
          round(100 * res["tanneru_beit_large"]["argmax_share"].get("surprise", 0.0), 1), 84.5)


# ── Group 7: the write-up quotes what was measured ───────────────────────────

def verify_analysis_numbers() -> None:
    body = text(ANALYSIS)
    if not body:
        return
    check_true("the write-up names the ground-truth source", "§9" in body)
    check_true("the write-up states the sample sizes", "44" in body and "77" in body)
    check_true("the write-up states the zero-NEGATIVE limitation",
               "NEGATIVE" in body and ("zero" in body or "no NEGATIVE" in body))
    check_true("the write-up reports both pooling modes",
               "midpoint" in body and "any" in body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    for fn in (verify_ground_truth, verify_section9_correction,
               verify_incumbent_distribution, verify_confidence_gate,
               verify_bench_a, verify_bench_a_tables, verify_disagreement, verify_bench_b, verify_register,
               verify_taxonomy, verify_end_to_end, verify_bench_b_detail,
               verify_adoption, verify_anger,
               verify_pipeline_anchor, verify_analysis_numbers):
        fn()

    if args.verbose:
        for name, got, want in PASS:
            print(f"  ok   {name}: {got}")
    for name, got, want in FAIL:
        print(f"  FAIL {name}: got {got!r}, expected {want!r}")

    print(f"\n{len(PASS)} claims verified, {len(FAIL)} failed.")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
