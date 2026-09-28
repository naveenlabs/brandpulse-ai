"""
verify_claims.py — re-derive every number this bench publishes, from source.

The project's evidence rule (README, "Engineering rules"): "If a number is quoted anywhere, it must be traceable to a file in
this repo that produced it." This script is that traceability, in the pattern of
`../verify_claims.py`, `vocal_bench/verify_ab.py` and
`vocal_bench/verify_speaker_norm.py`.

Every claim is recomputed from raw data — `corpus.py`, `sample.json`,
`facial_labels_v2.json`, the detection and prediction files — and then the
recomputed value is required to appear **verbatim in the prose**. Both halves
matter: recomputing alone would prove the code is self-consistent, and grepping
alone would prove nothing at all. Together they prove the sentence in the write-up
came from the data on disk.

    python verify_claims.py            # all claims
    python verify_claims.py --verbose  # print every claim as it passes

Exit code 0 if every claim holds, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
ROOT = V1.parents[1]

for _p in (str(HERE), str(V1), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import corpus as CORP                                           # noqa: E402
import ground_truth_v2 as GT                                    # noqa: E402
import candidates as C                                          # noqa: E402
import report_v2 as RPT                                         # noqa: E402

ANALYSIS = HERE / "FACIAL_MODEL_ANALYSIS_V2.md"
DAMPING = HERE / "DAMPING_FIX_RESULT.md"
PROTOCOL = HERE / "PROTOCOL.md"
TOOL = HERE / "label_here.html"

PASS: list[tuple] = []
FAIL: list[tuple] = []


def check(name: str, got, want, tol: float | None = None) -> None:
    if tol is not None and isinstance(got, (int, float)) and isinstance(want, (int, float)):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    (PASS if ok else FAIL).append((name, got, want))


def check_true(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append((name, bool(condition), f"True {detail}".strip()))


def in_doc(name: str, needle: str, doc: str) -> None:
    """
    The recomputed value must appear verbatim in the write-up.

    Markdown emphasis is stripped for the second attempt, because `**95.9%**
    (417/435)` carries the same value as `95.9% (417/435)` and a check that
    failed on bold markers would be testing the typography, not the number.
    """
    ok = needle in doc or needle in doc.replace("**", "")
    (PASS if ok else FAIL).append((name, f"{needle!r} in doc", "present"))


# ── §2 corpus, sample and collection ──────────────────────────────────────────

def verify_corpus(doc: str) -> None:
    vids = CORP.VIDEOS
    frames = sum(v.frame_count() for v in vids)
    check("corpus/n_videos", len(vids), 15)
    check("corpus/n_speakers", len(CORP.speakers()), 8)
    check("corpus/n_frames", frames, 11087)
    in_doc("corpus/n_videos in doc", "15 videos, 8 speakers", doc)
    in_doc("corpus/n_frames in doc", f"**{frames:,}** frames", doc)

    per_speaker = Counter(v.speaker for v in vids)
    check("corpus/mkbhd_videos", per_speaker["Marques Brownlee"], 5)
    check("corpus/mrwhosetheboss_videos", per_speaker["Mrwhosetheboss"], 4)
    in_doc("corpus/mkbhd in doc", "5 of the 15 videos are Marques\nBrownlee", doc)

    tones = Counter(v.tone_hint for v in vids)
    negative = tones["critical"] + tones["sceptical"] + tones["disappointed"]
    check("corpus/critical", tones["critical"], 4)
    check("corpus/sceptical", tones["sceptical"], 1)
    check("corpus/disappointed", tones["disappointed"], 1)
    check("corpus/mixed", tones["mixed"], 5)
    check("corpus/positive", tones["positive"], 4)
    check("corpus/negatively_framed", negative, 6)
    in_doc("corpus/negatively_framed in doc",
           f"**{negative} of the {len(vids)} videos are framed", doc)
    in_doc("corpus/tone breakdown in doc",
           f"({tones['critical']} `critical`, {tones['sceptical']} `sceptical`,", doc)

    # Every title quoted in the write-up must be the title corpus.py records.
    for v in vids:
        if v.tone_hint in ("critical", "sceptical", "disappointed"):
            in_doc(f"corpus/title verbatim {v.video_id}", f"| {v.title} |", doc)
            in_doc(f"corpus/row {v.video_id}", f"| `{v.video_id}` |", doc)


def verify_sample(doc: str) -> None:
    m = GT.load_manifest()
    check("sample/seed", m["seed"], 20260903)
    check("sample/per_video", m["per_video"], 40)
    check("sample/n_frames", m["n_frames"], 600)
    check("sample/n_presentations", m["n_presentations"], 648)
    check("sample/n_retest", m["n_retest"], 48)
    check("sample/retest_fraction", m["n_retest"] / m["n_frames"], 0.08, tol=1e-9)
    in_doc("sample/seed in doc", "seed **20260903**", doc)
    in_doc("sample/draw in doc", "600 frames, **40 per video**", doc)
    in_doc("sample/presentations in doc",
           "648 = 600 first presentations + **48 hidden duplicates** (8%)", doc)

    # 40 frames from every video, all distinct.
    firsts = [p for p in m["presentations"] if not p["retest"]]
    per_video = Counter(p["video_id"] for p in firsts)
    check("sample/videos_covered", len(per_video), 15)
    check("sample/per_video_uniform", sorted(set(per_video.values())), [40])
    check("sample/uids_unique", len({p["uid"] for p in firsts}), 600)

    # Every re-test follows its original by at least the pre-registered gap.
    pos = {p["uid"]: i for i, p in enumerate(m["presentations"]) if not p["retest"]}
    gaps = [i - pos[p["of"]] for i, p in enumerate(m["presentations"]) if p["retest"]]
    check_true("sample/retest_gap>=60", min(gaps) >= 60, f"min gap {min(gaps)}")
    in_doc("sample/gap in doc", "at least 60 presentations after its original", doc)


def verify_collection(doc: str):
    m = GT.load_manifest()
    raw = GT.load_raw()
    v = GT.validate(raw, m)
    check("collect/n_labelled", v["n_labelled"], 646)
    check("collect/n_missing", v["n_missing"], 2)
    in_doc("collect/labelled in doc", "**646 of 648** rated", doc)

    missing = {u for u in v["missing"]}
    by_uid = {p["uid"]: p for p in m["presentations"]}
    check("collect/missing_uids", sorted(missing),
          ["SSC0RkJuBVw:frame_0102", "i63u-iAnhuk:frame_0064"])
    check_true("collect/missing_all_dev",
               all(by_uid[u]["split"] == "dev" for u in missing))
    check_true("collect/missing_none_retest",
               all(not by_uid[u]["retest"] for u in missing))
    for u in sorted(missing):
        in_doc(f"collect/missing listed {u}", f"`{u}`", doc)
    in_doc("collect/holdout complete in doc", "holdout is complete at 160/160", doc)
    in_doc("collect/missing pct in doc", "2 of 600 is 0.33%", doc)

    rows = GT._rows(raw, m)
    check("collect/first_presentations_rated", len(rows), 598)
    in_doc("collect/598 in doc", "598 first presentations were rated", doc)
    return m, raw, rows


def verify_sets(doc: str, m, raw, rows) -> None:
    counts = Counter(r["choice"] for r in rows)
    faces = GT.face_set(raw, m)
    exprs = GT.expression_set(raw, m)

    check("sets/face_set_n", len(faces), 595)
    check("sets/with_face", sum(f["has_face"] for f in faces), 344)
    check("sets/without_face", sum(not f["has_face"] for f in faces), 251)
    check("sets/face_unsure", counts["face_unsure"], 3)
    check("sets/expr_set_n", len(exprs), 320)
    check("sets/expr_unsure", counts["expr_unsure"], 24)
    check("sets/faces_minus_unreadable", 344 - counts["expr_unsure"], len(exprs))

    in_doc("sets/face row in doc", "| **595** | 344 with a face, 251 without |", doc)
    in_doc("sets/expr row in doc", "| **320** |", doc)
    in_doc("sets/face_unsure in doc", "| — excluded, `face_unsure` | 3 |", doc)
    in_doc("sets/expr_unsure in doc", "| — excluded, `expr_unsure` | 24 |", doc)

    fine = Counter(e["fine"] for e in exprs)
    three = Counter(e["three"] for e in exprs)
    for k, want in (("neutral", 196), ("happy", 102), ("surprised", 12),
                    ("sad", 6), ("angry", 4)):
        check(f"sets/fine_{k}", fine[k], want)
    check("sets/three_POSITIVE", three["POSITIVE"], 114)
    check("sets/three_NEUTRAL", three["NEUTRAL"], 196)
    check("sets/three_NEGATIVE", three["NEGATIVE"], 10)
    check("sets/pos_is_happy_plus_surprised", fine["happy"] + fine["surprised"],
          three["POSITIVE"])
    check("sets/neg_is_angry_plus_sad", fine["angry"] + fine["sad"], three["NEGATIVE"])
    check("sets/fine_sums_to_expr", sum(fine.values()), len(exprs))

    in_doc("sets/neutral in doc", "| neutral | 196 | NEUTRAL | **196** |", doc)
    in_doc("sets/happy in doc", "| happy | 102 | POSITIVE | **114** |", doc)
    in_doc("sets/negative in doc", "| sad | 6 | NEGATIVE | **10** |", doc)


def verify_per_speaker(doc: str, m, raw, rows) -> None:
    by = defaultdict(Counter)
    for r in rows:
        by[(r["split"], r["speaker"])][r["choice"]] += 1
    check("speaker/n_rows", len(by), 8)

    for (split, speaker), c in by.items():
        n = sum(c.values())
        face = sum(c[x] for x in GT.FACE_PRESENT)
        expr = sum(c[x] for x in GT.EXPRESSION_THREE)
        row = (f"| {split} | {speaker} | {n} | {face} | {c['no_face']} | {expr} | "
               f"{c['neutral']} | {c['happy']} | {c['angry']} | {c['sad']} | "
               f"{c['surprised']} |")
        in_doc(f"speaker/row {speaker}", row, doc)
        check_true(f"speaker/face+noface+unsure {speaker}",
                   face + c["no_face"] + c["face_unsure"] == n)

    boss = by[("dev", "Mrwhosetheboss")]
    dave = by[("holdout", "Dave2D")]
    check("speaker/boss_happy", boss["happy"], 46)
    check("speaker/boss_expr", sum(boss[x] for x in GT.EXPRESSION_THREE), 81)
    check("speaker/dave_happy", dave["happy"], 0)
    check("speaker/dave_expr", sum(dave[x] for x in GT.EXPRESSION_THREE), 27)
    in_doc("speaker/expressiveness claim in doc",
           "**Mrwhosetheboss is happy on 46 of 81\nreadable frames, Dave2D on 0 of 27**", doc)

    mkbhd = by[("dev", "Marques Brownlee")]
    jeremy = by[("holdout", "Jeremy Fragrance")]
    check("speaker/mkbhd_noface", mkbhd["no_face"], 109)
    check("speaker/mkbhd_n", sum(mkbhd.values()), 199)
    check("speaker/jeremy_noface", jeremy["no_face"], 3)
    in_doc("speaker/broll claim in doc",
           "faceless on 109 of 199 sampled frames, Jeremy Fragrance\non 3 of 40", doc)


# ── §3 the reliability ceiling ────────────────────────────────────────────────

def verify_ceiling(doc: str, m, raw) -> None:
    rel = GT.reliability(raw, m)
    check("ceiling/n_pairs", rel["n_pairs"], 48)
    check("ceiling/fine_agreement", rel["fine_agreement"], 0.875, tol=5e-4)
    check("ceiling/three_agreement", rel["three_agreement"], 0.875, tol=5e-4)
    check("ceiling/fine_kappa", rel["fine_kappa"], 0.804, tol=5e-4)
    check("ceiling/three_kappa", rel["three_kappa"], 0.804, tol=5e-4)
    check("ceiling/n_agree", round(rel["fine_agreement"] * rel["n_pairs"]), 42)
    check("ceiling/n_disagree", len(rel["disagreements"]), 6)

    in_doc("ceiling/fine row in doc", "| **87.5%** (42/48) | **0.804** |", doc)
    in_doc("ceiling/n_pairs in doc",
           "48 frames were shown twice, unmarked, at least 60\npresentations apart", doc)

    # Every disagreement in the table must be a disagreement in the data.
    for d in rel["disagreements"]:
        in_doc(f"ceiling/row {d['uid']}",
               f"| `{d['uid']}` | {d['speaker']} | {d['first']} | {d['second']} |", doc)

    # The claim that all six cross a three-class boundary, recomputed.
    def coarse(ch):
        if ch in GT.FACE_ABSENT:
            return "NO_FACE"
        if ch in GT.FACE_UNKNOWN:
            return "UNSURE_FACE"
        if ch == "expr_unsure":
            return "UNSURE_EXPR"
        return GT.EXPRESSION_THREE[ch]

    crossing = sum(1 for d in rel["disagreements"]
                   if coarse(d["first"]) != coarse(d["second"]))
    check("ceiling/all_cross_three_class", crossing, len(rel["disagreements"]))
    in_doc("ceiling/crossing claim in doc",
           "**every one of the six disagreements crossed a three-class boundary.**", doc)

    neutral_happy = sum(1 for d in rel["disagreements"]
                        if {d["first"], d["second"]} == {"neutral", "happy"})
    check("ceiling/neutral_happy_pairs", neutral_happy, 4)
    in_doc("ceiling/neutral_happy in doc", "**Four of six are neutral ↔ happy**", doc)

    dev_expr = GT.expression_set(raw, m, split="dev")
    const = Counter(e["three"] for e in dev_expr).most_common(1)[0][1] / len(dev_expr)
    headroom = rel["three_agreement"] - const
    check("ceiling/headroom", headroom, 0.297, tol=5e-4)
    in_doc("ceiling/headroom in doc", "29.7 points of genuine headroom", doc)


# ── §4 the split ──────────────────────────────────────────────────────────────

def verify_split(doc: str, m, raw) -> None:
    dev_sp = set(m["dev_speakers"])
    hold_sp = set(m["holdout_speakers"])
    check("split/no_speaker_overlap", sorted(dev_sp & hold_sp), [])
    check("split/holdout_speakers", len(hold_sp), 4)
    check_true("split/holdout>=3_speakers", len(hold_sp) >= 3)
    check("split/dev_speakers", sorted(dev_sp),
          ["Jon Adams", "Marques Brownlee", "Mrwhosetheboss", "Seth Fowler"])
    check("split/holdout_speakers_named", sorted(hold_sp),
          ["Dave2D", "Jeremy Fragrance", "ShortCircuit", "The Tech Chap"])

    # Contamination constraint: the two v1 videos must be in dev.
    firsts = {p["video_id"]: p["split"] for p in m["presentations"]}
    for vid in ("1VjPETN3m6U", "JpN1DQdV4G4"):
        check(f"split/forced_dev {vid}", firsts[vid], "dev")
    in_doc("split/contamination in doc",
           "**forced into dev on\ncontamination grounds, not preference**", doc)

    stats = {}
    for name in ("dev", "holdout"):
        f = GT.face_set(raw, m, split=name)
        e = GT.expression_set(raw, m, split=name)
        c = Counter(x["three"] for x in e)
        stats[name] = {
            "faces": len(f), "with": sum(x["has_face"] for x in f),
            "without": sum(not x["has_face"] for x in f), "expr": len(e),
            "pos": c["POSITIVE"], "neu": c["NEUTRAL"], "neg": c["NEGATIVE"],
            "const": max(c.values()) / len(e),
        }
    d, h = stats["dev"], stats["holdout"]
    check("split/dev_faces", d["faces"], 435)
    check("split/dev_with_face", d["with"], 225)
    check("split/dev_faceless", d["without"], 210)
    check("split/dev_expr", d["expr"], 206)
    check("split/dev_pos", d["pos"], 80)
    check("split/dev_neu", d["neu"], 119)
    check("split/dev_neg", d["neg"], 7)
    check("split/dev_constant", d["const"], 0.578, tol=5e-4)
    check("split/holdout_faces", h["faces"], 160)
    check("split/holdout_with_face", h["with"], 119)
    check("split/holdout_faceless", h["without"], 41)
    check("split/holdout_expr", h["expr"], 114)
    check("split/holdout_pos", h["pos"], 34)
    check("split/holdout_neu", h["neu"], 77)
    check("split/holdout_neg", h["neg"], 3)
    check("split/holdout_constant", h["const"], 0.675, tol=5e-4)
    check("split/expr_totals_add_up", d["expr"] + h["expr"], 320)
    check("split/face_totals_add_up", d["faces"] + h["faces"], 595)

    in_doc("split/dev row in doc",
           "| 435 | 225 | 210 | **206** | 80 | 119 | 7 | **57.8%** |", doc)
    in_doc("split/holdout row in doc",
           "| 160 | 119 | 41 | **114** | 34 | 77 | 3 | **67.5%** |", doc)

    # Stated in the doc as a fraction of the *sampled* frames, which is what the
    # pre-registered >=25% floor in PROTOCOL.md §7 was drawn against — not of the
    # smaller face-presence set, which excludes the rater's three abstentions.
    firsts = [x for x in m["presentations"] if not x["retest"]]
    frac = sum(1 for x in firsts if x["split"] == "holdout") / len(firsts)
    check("split/holdout_fraction", frac, 0.267, tol=5e-4)
    check_true("split/holdout>=25pct", frac >= 0.25, f"{frac:.3f}")
    in_doc("split/fraction in doc", "Holdout is 26.7% of the sampled frames", doc)

    check("split/dev_faceless_rate", d["without"] / d["faces"], 0.483, tol=5e-4)
    check("split/holdout_faceless_rate", h["without"] / h["faces"], 0.256, tol=5e-4)
    in_doc("split/faceless asymmetry in doc",
           "dev is 48.3% faceless (210/435),\nholdout only 25.6% (41/160)", doc)


# ── §5 Q2 ─────────────────────────────────────────────────────────────────────

def verify_q2(doc: str, m, raw, rows) -> None:
    fine = Counter(e["fine"] for e in GT.expression_set(raw, m))
    check("q2/n_anger", fine["angry"], 4)
    check("q2/n_sad", fine["sad"], 6)
    check("q2/n_negative", fine["angry"] + fine["sad"], 10)
    check("q2/negative_rate", (fine["angry"] + fine["sad"]) / 320, 0.031, tol=5e-4)

    floor = int(re.search(r"fewer than (\d+) anger\s*\n?frames", PROTOCOL.read_text()).group(1))
    check("q2/floor_from_protocol", floor, 20)
    check_true("q2/underpowered", fine["angry"] < floor, f"{fine['angry']} < {floor}")
    in_doc("q2/underpowered in doc", "**The labels contain 4.**", doc)
    in_doc("q2/rate in doc", "**10** of 320 (3.1%)", doc)
    in_doc("q2/floor in doc", "| Pre-registered floor | 20 |", doc)
    in_doc("q2/no claim in doc",
           "**Therefore no claim is made about Q2 in either direction.**", doc)

    anger = [r for r in rows if r["choice"] == "angry"]
    check("q2/anger_dev", sum(1 for r in anger if r["split"] == "dev"), 3)
    check("q2/anger_holdout", sum(1 for r in anger if r["split"] == "holdout"), 1)
    in_doc("q2/split in doc", "**4** (3 dev, 1 holdout)", doc)
    for r in anger:
        in_doc(f"q2/anger frame {r['uid']}", f"`{r['uid']}`", doc)

    # §5.1: does the framing predict where anger lands?
    tone = {v.video_id: v.tone_hint for v in CORP.VIDEOS}
    neg_framed = {vid for vid, t in tone.items()
                  if t in ("critical", "sceptical", "disappointed")}
    anger_vids = {r["video_id"] for r in anger}
    neg_vids = {r["video_id"] for r in rows if r["choice"] in ("angry", "sad")}
    check("q2/negframed_with_anger", len(neg_framed & anger_vids), 2)
    check("q2/anger_from_not_negframed", sum(1 for r in anger
                                             if r["video_id"] not in neg_framed), 2)
    check("q2/negframed_with_any_negative", len(neg_framed & neg_vids), 4)
    check("q2/negframed_without_negative",
          sorted(neg_framed - neg_vids), ["SAb4zRyxrD4", "SSC0RkJuBVw"])
    in_doc("q2/only 2 of 6 in doc",
           "Only **2 of those 6 negatively-framed videos** produced any anger frame", doc)
    in_doc("q2/2 of 4 in doc",
           "**2 of the 4 anger frames came from videos that are not negatively framed**",
           doc)
    in_doc("q2/4 of 6 in doc", "4 of\nthe 6 negatively-framed videos contributed one", doc)


# ── blinding (§2, PROTOCOL §5.4) ──────────────────────────────────────────────

def verify_blinding(doc: str) -> None:
    if not TOOL.exists():
        check_true("blinding/tool present", False, "label_here.html missing")
        return
    html = TOOL.read_text().lower()
    forbidden = ([m.lower() for m in C.CLASSIFIERS]
                 + [d.lower() for d in C.DETECTORS]
                 + [s.lower() for s in CORP.speakers()]
                 + ["holdout", "deepface", "retinaface"])
    leaks = sorted({t for t in forbidden if t in html})
    check("blinding/leaks", leaks, [])
    check("blinding/size_kb", round(TOOL.stat().st_size / 1024), 101)
    in_doc("blinding/claim in doc", "**zero leaks**", doc)


# ── §6-§10 results, re-scored from the raw detection and prediction files ──────
#
# `bench_results_v2.json` is deliberately NOT read here. Everything below is
# re-scored from `detections/*.json`, `predictions/*.json` and the labels, so a
# claim that survives is traceable to raw data rather than to a summary this bench
# also wrote.

def _pct1(x: float) -> str:
    return f"{x * 100:.1f}%"


def _p(pv: float) -> str:
    return "p<0.0001" if pv < 0.0001 else f"p={pv:.4f}"


def verify_bench_a(doc: str) -> None:
    for split in ("dev", "holdout"):
        res = RPT.score_detectors(split=split)
        n = res["n_frames"]
        in_doc(f"benchA/{split} header n",
               f"{n} frames, {res['n_faced']} with a face, {res['n_faceless']} without",
               doc)
        for name, rec in res["detectors"].items():
            correct = round(rec["accuracy"] * n)
            in_doc(f"benchA/{split}/{name} accuracy",
                   f"{_pct1(rec['accuracy'])} ({correct}/{n})", doc)
            in_doc(f"benchA/{split}/{name} ci",
                   f"{rec['accuracy_ci95'][0]*100:.1f}–{rec['accuracy_ci95'][1]*100:.1f}", doc)
            in_doc(f"benchA/{split}/{name} fp",
                   f"{rec['false_positives']}/{rec['n_faceless']}", doc)
            mc = rec.get("mcnemar_vs_deployed")
            if mc and not rec.get("baseline"):
                in_doc(f"benchA/{split}/{name} p", _p(mc["p_value"]), doc)

        # §6.1 no detector significantly beats the deployed one.
        beaters = [k for k, r in res["detectors"].items()
                   if not r.get("baseline") and r.get("mcnemar_vs_deployed")
                   and r["accuracy"] > res["detectors"]["yunet"]["accuracy"]
                   and r["mcnemar_vs_deployed"]["p_value"] < 0.05]
        check(f"benchA/{split}/none_beats_yunet", beaters, [])

        # §6.1 opencv significantly worse on both splits.
        oc = res["detectors"]["opencv"]
        check_true(f"benchA/{split}/opencv_worse",
                   oc["accuracy"] < res["detectors"]["yunet"]["accuracy"]
                   and oc["mcnemar_vs_deployed"]["p_value"] < 0.05,
                   f"p={oc['mcnemar_vs_deployed']['p_value']:.4f}")

    # §6.2 the pooled false-positive counts.
    dev = RPT.score_detectors(split="dev")["detectors"]
    hold = RPT.score_detectors(split="holdout")["detectors"]
    faceless = dev["yunet"]["n_faceless"] + hold["yunet"]["n_faceless"]
    yfp = dev["yunet"]["false_positives"] + hold["yunet"]["false_positives"]
    ofp = dev["opencv"]["false_positives"] + hold["opencv"]["false_positives"]
    check("benchA/yunet_total_fp", yfp, 0)
    check("benchA/opencv_total_fp", ofp, 65)
    check("benchA/total_faceless", faceless, 251)
    in_doc("benchA/0 of 251 in doc",
           f"**`yunet` produced zero false positives on all {faceless}", doc)
    in_doc("benchA/opencv 65 in doc", f"`opencv` produced {ofp}.", doc)

    # §6.1 speed ratios.
    mt = round(dev["mtcnn"]["seconds_per_frame"] / dev["yunet"]["seconds_per_frame"], 1)
    rf = round(dev["retinaface"]["seconds_per_frame"] / dev["yunet"]["seconds_per_frame"], 1)
    check("benchA/mtcnn_ratio", mt, 70.3)
    check("benchA/retinaface_ratio", rf, 20.7)
    in_doc("benchA/speed in doc", f"**{mt:.0f}× faster than `mtcnn`**", doc)
    in_doc("benchA/speed2 in doc", f"**{rf:.0f}× faster than `retinaface`**", doc)

    # §6.4 the gate.
    gated = RPT.score_detectors(split="dev", gate=RPT.PIPELINE_GATE)["detectors"]
    dropped = {k: v["detections_below_gate"] for k, v in gated.items()
               if v.get("detections_below_gate")}
    check("benchA/gate_drops", dropped, {"yolov8n": 2})
    check("benchA/gate_yunet_inert", gated["yunet"]["detections_below_gate"], 0)
    in_doc("benchA/gate in doc",
           "**the deployed detector loses\nno detections at all**", doc)


def verify_bench_b(doc: str) -> None:
    results = {}
    for split in ("dev", "holdout"):
        res = RPT.score_classifiers(split=split)
        results[split] = res
        n = res["n_frames"]
        cc = res["class_counts"]
        const = res["models"][res["constant_name"]]
        in_doc(f"benchB/{split} header",
               f"{n} frames: POSITIVE {cc['POSITIVE']}, NEUTRAL {cc['NEUTRAL']}, "
               f"NEGATIVE {cc['NEGATIVE']}. Constant = {_pct1(const['accuracy'])}", doc)

        for name, rec in res["models"].items():
            correct = round(rec["accuracy"] * n)
            in_doc(f"benchB/{split}/{name} accuracy",
                   f"{_pct1(rec['accuracy'])} ({correct}/{n})", doc)
            in_doc(f"benchB/{split}/{name} ci",
                   f"{rec['accuracy_ci95'][0]*100:.1f}–{rec['accuracy_ci95'][1]*100:.1f}", doc)
            in_doc(f"benchB/{split}/{name} macro_f1", f"{rec['macro_f1']:.3f}", doc)
            if rec["negative_on_neutral"]:
                in_doc(f"benchB/{split}/{name} negOnNeu",
                       f"{rec['negative_on_neutral']}/{rec['n_neutral']} "
                       f"({_pct1(rec['negative_on_neutral_rate'])})", doc)
            if name == res["constant_name"]:
                continue
            d = rec["accuracy"] - const["accuracy"]
            sign = "+" if d > 0 else "\u2212"
            in_doc(f"benchB/{split}/{name} delta", f"{sign}{abs(d)*100:.1f} pts", doc)
            in_doc(f"benchB/{split}/{name} p",
                   _p(rec["mcnemar_vs_constant"]["p_value"]), doc)

    # §7 headline: on the holdout every model is below the constant, significantly.
    hold = results["holdout"]
    hconst = hold["models"][hold["constant_name"]]
    real = {k: v for k, v in hold["models"].items() if not v.get("baseline")}
    check("benchB/holdout_models", len(real), 9)
    check_true("benchB/all_below_constant",
               all(v["accuracy"] < hconst["accuracy"] for v in real.values()))
    check_true("benchB/all_significant",
               all(v["mcnemar_vs_constant"]["p_value"] < 0.05 for v in real.values()))
    best = max(real.values(), key=lambda v: v["accuracy"])
    gap = (hconst["accuracy"] - best["accuracy"]) * 100
    check("benchB/holdout_best_gap", round(gap, 1), 30.7)
    in_doc("benchB/all below in doc",
           "**On the holdout, every one of the nine models is below a constant, and every one\nsignificantly so.**", doc)
    in_doc("benchB/best gap in doc", f"The best is {gap:.1f} points below it.", doc)

    # §8 per-class recall table.
    for split in ("dev", "holdout"):
        res = results[split]
        for name in ("deepface_fer", "trpakov_vit"):
            pc = res["models"][name]["per_class"]
            row = (f"| {name}, {split} | {_pct1(pc['POSITIVE']['recall'])} | "
                   f"**{_pct1(pc['NEUTRAL']['recall'])}** | "
                   f"{_pct1(pc['NEGATIVE']['recall'])} (n={res['models'][name]['n_negative']}) |")
            in_doc(f"benchB/perclass {name} {split}", row, doc)

    # §8 the "eight of nine invent negativity" claim.
    dev = results["dev"]
    dev_real = {k: v for k, v in dev["models"].items() if not v.get("baseline")}
    over = [k for k, v in dev_real.items() if v["negative_on_neutral_rate"] > 0.15]
    check("benchB/eight_of_nine_over_15pct", len(over), 8)
    lo = min(v["negative_on_neutral_rate"] for k, v in dev_real.items() if k in over)
    hi = max(v["negative_on_neutral_rate"] for v in dev_real.values())
    hlo = min(v["negative_on_neutral_rate"] for v in real.values())
    hhi = max(v["negative_on_neutral_rate"] for v in real.values())
    in_doc("benchB/rates range in doc",
           f"{_pct1(lo)} to {_pct1(hi)} on dev, and {_pct1(hlo)} to {_pct1(hhi)} on holdout",
           doc)

    # §8.1 the ceiling comparison.
    ceiling = GT.reliability()["three_agreement"]
    dbest = max(v["accuracy"] for v in dev_real.values())
    dconst = dev["models"][dev["constant_name"]]["accuracy"]
    captured = (dbest - dconst) / (ceiling - dconst)
    check("benchB/dev_headroom", round((ceiling - dconst) * 100, 1), 29.7)
    check("benchB/holdout_headroom", round((ceiling - hconst["accuracy"]) * 100, 1), 20.0)
    check("benchB/captured", round(captured * 100, 1), 6.5)
    in_doc("benchB/captured in doc", f"**{captured*100:.1f}%**, p=", doc)
    closest = ceiling - max(dbest, best["accuracy"])
    check("benchB/closest_to_ceiling", round(closest * 100, 1), 27.8)
    in_doc("benchB/ceiling gap in doc",
           f"**No model came within {closest*100:.1f} points of the ceiling", doc)

    # §9 the dev leader's collapse.
    t_dev = dev["models"]["trpakov_vit"]
    t_hold = hold["models"]["trpakov_vit"]
    check("benchB/trpakov_dev_c3_pass", t_dev["negative_on_neutral_rate"] <= 0.15, True)
    check("benchB/trpakov_hold_c3_fail", t_hold["negative_on_neutral_rate"] > 0.15, True)
    in_doc("benchB/collapse in doc",
           f"from **{_pct1(t_dev['negative_on_neutral_rate'])} to "
           f"{_pct1(t_hold['negative_on_neutral_rate'])}**", doc)
    ratio = t_hold["negative_on_neutral_rate"] / RPT.MAX_NEGATIVE_ON_NEUTRAL
    check("benchB/c3_ratio", round(ratio, 1), 3.3)
    in_doc("benchB/c3 ratio in doc", f"{ratio:.1f} times the limit it had just passed", doc)

    # §11 sensitivity.
    alt = RPT.score_classifiers(split="dev", mapping="surprise_neutral")
    a_best = max((v for v in alt["models"].values() if not v.get("baseline")),
                 key=lambda v: v["accuracy"])
    a_const = alt["models"][alt["constant_name"]]
    in_doc("benchB/sensitivity in doc",
           f"`trpakov_vit` {_pct1(t_dev['accuracy'])} → {_pct1(a_best['accuracy'])}, "
           f"constant {_pct1(dconst)} → {_pct1(a_const['accuracy'])}", doc)
    gap_alt = (a_best["accuracy"] - a_const["accuracy"]) * 100
    gap_pri = (t_dev["accuracy"] - dconst) * 100
    check("benchB/sensitivity_gap_stable", round(gap_alt, 1), round(gap_pri, 1))
    check("benchB/sensitivity_best_unchanged", a_best["model"], "trpakov_vit")

    # §11 no model abstained.
    for split, res in results.items():
        for name, rec in res["models"].items():
            check(f"benchB/{split}/{name} abstentions", rec["abstentions"], 0)

    return results


def verify_adoption(doc: str, results: dict) -> None:
    ad = RPT.evaluate_adoption(results["dev"], results["holdout"])
    check("adopt/nothing_adopted", ad["adopted"], [])
    check("adopt/decision", ad["decision"], "NOTHING ADOPTED")
    in_doc("adopt/decision in doc", "### **Decision: nothing is adopted.**", doc)

    # Exactly one model passed condition 3 on dev, and it is trpakov_vit.
    c3 = [k for k, v in ad["verdicts"].items() if v["c3_negative_on_neutral"]]
    check("adopt/c3_passers", c3, ["trpakov_vit"])
    # No model passed condition 1 at all.
    c1 = [k for k, v in ad["verdicts"].items() if v["c1_beats_constant_dev"]]
    check("adopt/c1_passers", c1, [])

    # The direction check: how many models would have passed a two-sided test alone.
    two_sided = [k for k, v in ad["verdicts"].items()
                 if results["dev"]["models"][k]["mcnemar_vs_constant"]["p_value"] < 0.05]
    check("adopt/two_sided_only", len(two_sided), 6)
    in_doc("adopt/direction in doc",
           f"Without the direction check, {len(two_sided)} failures\nwould have registered as passes.", doc)

    frozen = json.loads((HERE / "DEV_DECISION.json").read_text())
    check("adopt/frozen_eligible", frozen["candidates_still_eligible"], [])
    in_doc("adopt/fingerprint in doc", frozen["fingerprint"][:12], doc)
    in_doc("adopt/zero eligible in doc", "**zero candidates still eligible**", doc)

    # §12 the weight proposed for the orchestrator.
    hold_dep = results["holdout"]["models"][RPT.DEPLOYED_CLASSIFIER]
    n = results["holdout"]["n_frames"]
    correct = round(hold_dep["accuracy"] * n)
    check("adopt/facial_weight", round(hold_dep["accuracy"], 3), 0.342)
    in_doc("adopt/weight in doc", f"{correct}/{n} = **0.342**", doc)


# ── DAMPING_FIX_RESULT.md, re-derived from the caches ─────────────────────────

def verify_damping(doc: str) -> None:
    """
    Re-run the coverage and effect measurements rather than reading the results
    file this bench also wrote.

    `damping_ab` is imported here, not at the top, because it reaches into
    `vocal_bench.corpus_ab`, which binds *that* bench's `candidates` module under
    the same bare name this file already imported facial_bench's under. By the
    time this runs, `C` above is bound by reference and cannot be swapped.
    """
    import damping_ab as DAB
    from pipeline import orchestrator as ORC
    from pipeline import visual_module as VIS

    # The weight, and that it agrees in all three places it appears.
    check("damp/weight_orchestrator", ORC.FACIAL_ONLY_CONFLICT_WEIGHT, 0.342)
    check("damp/weight_visual_module", VIS.FACIAL_CHANNEL_RELIABILITY, 0.342)
    check("damp/weights_agree", ORC.FACIAL_ONLY_CONFLICT_WEIGHT,
          VIS.FACIAL_CHANNEL_RELIABILITY)
    check_true("damp/facial_damped_harder_than_vocal",
               ORC.FACIAL_ONLY_CONFLICT_WEIGHT < ORC.VOCAL_ONLY_CONFLICT_WEIGHT)
    in_doc("damp/weight in doc", "FACIAL_ONLY_CONFLICT_WEIGHT = 0.342", doc)

    # The facial channel build.
    builds = [json.loads(f.read_text())
              for f in sorted((HERE / "ab_cache_facial").glob("*.json"))]
    n_videos = len(builds)
    frames = sum(b["n_frames"] for b in builds)
    faces = sum(b["faces_detected"] for b in builds)
    seconds = sum(b["seconds"] for b in builds)
    check("damp/videos", n_videos, 12)
    check("damp/frames", frames, 9125)
    check("damp/faces", faces, 4645)
    check("damp/face_rate", round(faces / frames * 100, 1), 50.9)
    in_doc("damp/frames in doc", f"**{frames:,}** |", doc)
    in_doc("damp/faces in doc", f"**{faces:,}** ({faces/frames*100:.1f}%) |", doc)
    in_doc("damp/speed in doc",
           f"{seconds/60:.1f} min ({seconds/frames:.4f} s/frame)", doc)

    # Coverage, both denominators.
    scored = DAB.coverage(scored_only=True)["totals"]
    every = DAB.coverage(scored_only=False)["totals"]
    check("damp/scored_segments", scored["segments"], 481)
    check("damp/all_segments", every["segments"], 1863)
    check("damp/facial_scored", scored["facial"], 18)
    check("damp/facial_all", every["facial"], 53)
    check("damp/vocal4_scored", scored["vocal_with_facial"], 49)
    check("damp/vocal4_all", every["vocal_with_facial"], 211)
    check("damp/vocal3_scored", scored["vocal_without_facial"], 89)
    check("damp/vocal3_all", every["vocal_without_facial"], 396)
    check("damp/both_scored", scored["both"], 0)
    check("damp/both_all", every["both"], 0)
    check("damp/readable_scored", scored["facial_readable"], 323)
    check("damp/readable_all", every["facial_readable"], 1172)

    # The harness must reproduce vocal_bench's published figure.
    check_true("damp/reproduces_vocal_bench_89_of_481",
               scored["vocal_without_facial"] == 89 and scored["segments"] == 481)
    in_doc("damp/89 in doc", "**89 of 481 segments (18.5%)**", doc)

    for name, val, tot in (("facial_scored", scored["facial"], scored["segments"]),
                           ("facial_all", every["facial"], every["segments"]),
                           ("vocal4_scored", scored["vocal_with_facial"], scored["segments"]),
                           ("vocal4_all", every["vocal_with_facial"], every["segments"]),
                           ("vocal3_all", every["vocal_without_facial"], every["segments"]),
                           ("readable_scored", scored["facial_readable"], scored["segments"]),
                           ("readable_all", every["facial_readable"], every["segments"])):
        in_doc(f"damp/{name} pct in doc", f"({val / tot * 100:.1f}%)", doc)

    in_doc("damp/vocal_halving in doc",
           "**Adding the facial channel nearly halves the vocal rule's coverage: "
           f"{scored['vocal_without_facial']} \u2192 {scored['vocal_with_facial']}.**", doc)

    # Effect.
    eff = DAB.effect("cached")
    check("damp/effect_changed", eff["n_changed"], 0)
    check("damp/effect_before_nonzero", eff["before"]["nonzero"], 8)
    check("damp/effect_after_nonzero", eff["after"]["nonzero"], 8)
    check("damp/effect_before_flagged", eff["before"]["flagged"], 8)
    check("damp/effect_after_flagged", eff["after"]["flagged"], 8)
    check("damp/effect_mean_unchanged", eff["before"]["mean_score"],
          eff["after"]["mean_score"])
    check("damp/effect_mean", eff["before"]["mean_score"], 0.0131, tol=5e-5)
    zeros = eff["before"]["segments"] - eff["before"]["nonzero"]
    check("damp/controller_zeros", zeros, 473)
    in_doc("damp/zeros in doc",
           f"returned `conflict_score` 0.0 on {zeros} of {eff['before']['segments']}", doc)
    in_doc("damp/nothing changed in doc", "**Nothing changed. 0 segments, 0 flags.**", doc)

    # Every non-zero segment is a genuine multi-channel conflict.
    fired = 0
    nonzero = 0
    for vid in DAB.videos():
        rows = DAB.four_channel_rows(vid)
        cs = DAB.comment_sentiment(vid)
        src = json.loads(
            (DAB.AB.CACHE / f"conflict_{DAB.ARM}" / f"{vid}.json").read_text())
        for k, v in src.items():
            raw = v.get("_raw") or {}
            if float(raw.get("conflict_score") or 0.0) <= 0 or k not in rows:
                continue
            nonzero += 1
            fired += (ORC._facial_is_sole_dissenter(rows[k], cs)
                      or ORC._vocal_is_sole_dissenter(rows[k], cs))
    check("damp/nonzero_segments", nonzero, 8)
    check("damp/lone_dissenter_among_nonzero", fired, 0)
    in_doc("damp/specificity in doc", "The facial rule fires on **0 of 8**", doc)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not ANALYSIS.exists():
        print(f"{ANALYSIS.name} not found", file=sys.stderr)
        return 1
    doc = ANALYSIS.read_text()

    verify_corpus(doc)
    verify_sample(doc)
    m, raw, rows = verify_collection(doc)
    verify_sets(doc, m, raw, rows)
    verify_per_speaker(doc, m, raw, rows)
    verify_ceiling(doc, m, raw)
    verify_split(doc, m, raw)
    verify_q2(doc, m, raw, rows)
    verify_blinding(doc)
    verify_bench_a(doc)
    results = verify_bench_b(doc)
    verify_adoption(doc, results)
    if DAMPING.exists():
        verify_damping(DAMPING.read_text())

    if args.verbose:
        for name, got, want in PASS:
            print(f"  ok    {name}: {got}")
    for name, got, want in FAIL:
        print(f"  FAIL  {name}: got {got!r}, expected {want!r}")

    print(f"\n{len(PASS)} claims verified, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
