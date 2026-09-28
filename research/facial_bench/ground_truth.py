"""
ground_truth.py — the human-verified label set for the facial-emotion bench.

Provenance
----------
The labels here are **not new**. They are a machine-readable transcription of the
author's own frame-by-frame visual review of all 77 segments of video
`1VjPETN3m6U`, written up in `PROTOTYPE_FINDINGS.md` §9 ("Facial Emotion Channel —
Full Frame-by-Frame Visual Verification of All 77 Segments"). That review was
carried out by the project author against the extracted frames, independently of
any model output, which is what makes it usable as ground truth here.

Two things follow from that, and both matter:

1. **It is not derived from any candidate.** §9 judged what is visible in the
   frame. DeepFace's label was recorded alongside it for comparison but never
   used to produce it. Step 2 of the bench method (README) is satisfied.

2. **Transcribing prose into class labels is interpretation, and interpretation
   can be wrong.** So every row carries the author's own words verbatim, plus a
   `tier` saying how direct the reading is, and the strict tier is always scored
   separately from the full set. Nothing here is presented as more certain than
   it is.

The anchor
----------
Every row also records the label and confidence DeepFace assigned, exactly as §9
tabulates it. `anchor_check()` re-reads those from the saved run that §9 analysed
(`outputs/Apple (Iphone 17 Pro Max - 3).json`) and refuses to hand out labels if
the transcription and the saved run disagree. A transcription error therefore
fails loudly instead of silently producing a wrong ground truth.

Tiers
-----
``explicit``   §9 gives this segment its own table row naming what is visible.
``grouped``    §9 names the segment inside a group and states the group's visible
               expression in positive terms ("neutral expression").
``inferred``   §9 names the segment inside a group but describes the expression
               only by what it is *not* ("not sad", "no fear visible"). The class
               below is the reading this bench uses; the ambiguity is real and is
               reported, never hidden.

Classes
-------
POSITIVE / NEUTRAL / NEGATIVE, the same three-class shape every other channel in
this project is scored on, so the numbers are comparable across benches.
`face_present` is tracked separately because detection and classification are two
different failures and are benched separately.
"""
from __future__ import annotations

import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]

# The saved run that §9 reviewed. Named in §9's Methodology paragraph.
ANCHOR_REPORT = ROOT / "outputs" / "Apple (Iphone 17 Pro Max - 3).json"
ANCHOR_VIDEO = "1VjPETN3m6U"

POSITIVE, NEUTRAL, NEGATIVE = "POSITIVE", "NEUTRAL", "NEGATIVE"

# ── §9 "Failure Mode A" — 15 segments, author-verified as containing no human
#    face at all. Transcribed from the table verbatim, in the document's order.
_NO_FACE: list[tuple[int, str, float, str]] = [
    (1,  "sad",      0.84, "Phone held face-down over desk, no person visible"),
    (4,  "surprise", 0.91, "Two phones lying on desk, hand only"),
    (6,  "neutral",  0.94, "Two phones held side-by-side, no face"),
    (9,  "fear",     0.52, "Phone in hand, b-roll"),
    (10, "fear",     0.84, "Phone camera bump close-up"),
    (11, "neutral",  0.74, "Phone in hand, top-down desk shot"),
    (13, "angry",    0.54, "Phone in hand, b-roll"),
    (17, "fear",     0.51, "Phone lock screen close-up"),
    (22, "sad",      0.36, "Phone in hand, b-roll"),
    (24, "neutral",  0.82, "Phone in hand, sliver of out-of-focus hair top-right, no real face"),
    (25, "neutral",  0.49, "Phone in hand, b-roll"),
    (30, "surprise", 0.53, "Phone with blank screen on desk"),
    (31, "fear",     0.58, "Phone lock screen on desk"),
    (41, "fear",     0.64, "Empty desk top-down shot"),
    (57, "fear",     0.75, "Side profile turned away, mostly out of frame"),
]

# ── §9 "Failure Mode B" — a real face is present. Individually tabulated rows.
_FACE_EXPLICIT: list[tuple[int, str, float, str, str]] = [
    (76, "angry",   0.97, POSITIVE, "Thumbs up, smiling"),
    (32, "sad",     0.72, POSITIVE, "Smiling/smirking, content expression"),
    (53, "happy",   0.82, POSITIVE, "(correctly \"happy\" 0.82)"),
    (61, "sad",     0.99, POSITIVE, "Looking at phone, content/slightly smiling"),
    (71, "sad",     0.95, POSITIVE, "Content, slight smile"),
    (0,  "sad",     0.93, NEUTRAL,  "Neutral/mildly skeptical look, not sad"),
    (21, "neutral", 0.89, POSITIVE, "Mouth open wide, eyebrows raised — looks surprised/excited"),
]

# ── CORRECTION to §9, found 03 Sep 2026 by this file's anchor check ───────────
# §9 lists segment 39 in its "fear (0.40–0.70)" row. The saved run labels segment
# 39 **angry**, confidence 0.4646. Two independent facts in §9 itself settle which
# row is right:
#   - §9's angry row states the range "0.46–0.95". The angry group as listed spans
#     0.5277–0.9523; only adding segment 39 (0.4646) produces the stated 0.46.
#   - §9's fear row states "0.40–0.70". Removing segment 39 leaves 0.3999–0.7023,
#     which is exactly that range.
# Segment 39 therefore belongs to the angry group and is placed there below. Both
# rows describe a neutral visible expression, so the ground-truth class is
# unchanged; only the tier improves, from "inferred" to "grouped". The correction
# is recorded here and in CANDIDATE_MODELS.md rather than edited silently into §9.

# ── §9 Failure Mode B — the three grouped rows. `claimed` is a range in the
#    document, so only the group's label family is transcribed and the anchor
#    check verifies the family rather than a point confidence.
_FACE_GROUPS: list[tuple[list[int], str, str, str, str]] = [
    ([3, 26, 34, 35, 36, 39, 42, 43, 44, 51, 55, 56, 59, 63, 66, 72, 73],
     "angry", NEUTRAL, "grouped",
     "Normal mid-sentence talking, neutral expression, hand gestures — no anger visible"),
    ([14, 15, 19, 20, 27, 29, 38, 47, 50, 52, 54, 58, 69, 74, 75],
     "sad", NEUTRAL, "inferred",
     "Normal talking, often animated/enthusiastic gesturing — not sad"),
    ([33, 37, 40, 46, 62],
     "fear", NEUTRAL, "inferred",
     "Normal talking, holding phone near face — no fear visible"),
]

# §9's own four-category tally, quoted so the derived set can be checked against it.
SECTION9_TALLY = {
    "correct_no_face": 5,
    "false_positive": 15,
    "match": 11,
    "mismatch": 46,
    "total": 77,
    "accuracy": 16 / 77,
}


# ── Derived from §9's four-category tally, not from any model ────────────────
# §9 partitions all 77 segments into exactly four categories and gives a count for
# each. Two of those counts carry information about segments §9 never tabulates
# individually, and it is sound to use it:
#
#   "Correct no face" (5). Defined as: DeepFace reported no face AND the frame
#   genuinely has no human face. The saved run contains exactly 5 segments with no
#   label, so those 5 segments are the 5, and each is author-verified faceless.
#   `anchor_check()` enforces the count, so this stops being sound the moment the
#   run stops matching.
#
#   "Match" (11) and "Mismatch" (46). Both definitions open with "A real face is
#   present". Every segment that is neither correct-no-face nor false-positive is
#   therefore author-verified as containing a real face, whatever its expression.
#
# This gives complete face-presence ground truth over all 77 segments, which is
# what the detector bench needs. It gives **no** expression label: for a "match"
# segment the only expression evidence is that §9 judged DeepFace's own label
# reasonable, and using that would define the ground truth by the incumbent being
# right. Those segments carry expression=None and are excluded from the
# classification bench. The bias that would have introduced is the reason.


def _face_present_only(segs_in_run: dict[int, dict]) -> list[dict]:
    """The segments with a verified face but no verified expression."""
    described = {r["segment_id"] for r in _described_rows()}
    no_label = {sid for sid, s in segs_in_run.items() if s["dominant"] is None}
    rows = []
    for sid in sorted(set(segs_in_run) - described - no_label):
        rows.append({
            "video_id": ANCHOR_VIDEO, "segment_id": sid,
            "face_present": True, "expression": None,
            "claimed_label": segs_in_run[sid]["dominant"],
            "claimed_confidence": segs_in_run[sid]["confidence"],
            "tier": "derived", "group": "face_untabulated",
            "quote": "\u00a79 categories 'Match' and 'Mismatch', both defined as "
                     "'A real face is present'",
        })
    return rows


def _correct_no_face(segs_in_run: dict[int, dict]) -> list[dict]:
    """The 5 segments §9 counts as correctly reporting no face."""
    rows = []
    for sid in sorted(sid for sid, s in segs_in_run.items() if s["dominant"] is None):
        rows.append({
            "video_id": ANCHOR_VIDEO, "segment_id": sid,
            "face_present": False, "expression": None,
            "claimed_label": None, "claimed_confidence": None,
            "tier": "derived", "group": "correct_no_face",
            "quote": "\u00a79 category 'Correct no face': DeepFace correctly reported "
                     "no face and the frame genuinely has no human face",
        })
    return rows


def _described_rows() -> list[dict]:
    """Build the rows §9 describes in prose. Pure data assembly, no I/O."""
    rows: list[dict] = []
    for seg, claimed, conf, quote in _NO_FACE:
        rows.append({
            "video_id": ANCHOR_VIDEO, "segment_id": seg,
            "face_present": False, "expression": None,
            "claimed_label": claimed, "claimed_confidence": conf,
            "tier": "explicit", "group": "no_face", "quote": quote,
        })
    for seg, claimed, conf, expr, quote in _FACE_EXPLICIT:
        rows.append({
            "video_id": ANCHOR_VIDEO, "segment_id": seg,
            "face_present": True, "expression": expr,
            "claimed_label": claimed, "claimed_confidence": conf,
            "tier": "explicit", "group": "face_explicit", "quote": quote,
        })
    for segs, claimed, expr, tier, quote in _FACE_GROUPS:
        for seg in segs:
            rows.append({
                "video_id": ANCHOR_VIDEO, "segment_id": seg,
                "face_present": True, "expression": expr,
                "claimed_label": claimed, "claimed_confidence": None,
                "tier": tier, "group": f"face_group_{claimed}", "quote": quote,
            })
    rows.sort(key=lambda r: r["segment_id"])
    return rows


def _rows(segs_in_run: dict[int, dict] | None = None) -> list[dict]:
    """
    Every ground-truth row.

    Without the run, only the rows §9 describes in prose. With it, also the two
    groups derived from §9's tally, which need the run to identify the segments.
    """
    rows = _described_rows()
    if segs_in_run is not None:
        rows = rows + _correct_no_face(segs_in_run) + _face_present_only(segs_in_run)
        rows.sort(key=lambda r: r["segment_id"])
    return rows


def load_anchor_segments() -> dict[int, dict]:
    """Read the saved run §9 analysed, keyed by segment_id."""
    if not ANCHOR_REPORT.exists():
        raise FileNotFoundError(
            f"Anchor report missing: {ANCHOR_REPORT}. §9's ground truth cannot be "
            f"verified without the run it was derived from."
        )
    data = json.loads(ANCHOR_REPORT.read_text())
    out = {}
    for seg in data["all_segments"]:
        fe = (seg.get("model_outputs") or {}).get("facial_emotion") or {}
        out[int(seg["segment_id"])] = {
            "segment_id": int(seg["segment_id"]),
            "start_time": float(seg["start_s"]),
            "end_time": float(seg["end_s"]),
            "dominant": fe.get("dominant"),
            "confidence": fe.get("confidence"),
            "frame_count": fe.get("frame_count"),
            "text": seg.get("text", ""),
        }
    return out


def anchor_check() -> dict:
    """
    Verify the transcription against the saved run before any label is used.

    Only the rows §9 describes in prose are checked. The derived rows take their
    `claimed_label` from the run itself, so checking those would be a no-op.

    Checks, in order:
      1. the run has exactly the 77 segments §9 reviewed;
      2. every transcribed `claimed_label` equals the run's stored label;
      3. every transcribed `claimed_confidence` equals the run's stored value;
      4. the run has exactly as many unlabelled segments as §9's "correct no face"
         count, which is what makes the derivation in `_correct_no_face` sound;
      5. the four category counts §9 reports sum to the segment total, and the
         derived partition reproduces them.

    Returns a dict of the checks. Raises nothing — the caller decides.
    """
    segs = load_anchor_segments()
    described = _described_rows()
    problems: list[str] = []

    if len(segs) != SECTION9_TALLY["total"]:
        problems.append(f"segment count {len(segs)} != {SECTION9_TALLY['total']}")

    for r in described:
        sid = r["segment_id"]
        if sid not in segs:
            problems.append(f"segment {sid} transcribed but absent from the run")
            continue
        got = segs[sid]["dominant"]
        if got != r["claimed_label"]:
            problems.append(
                f"segment {sid}: §9 records '{r['claimed_label']}', run has '{got}'")
        want_conf = r["claimed_confidence"]
        if want_conf is not None:
            got_conf = segs[sid]["confidence"]
            if got_conf is None or abs(float(got_conf) - want_conf) > 0.005:
                problems.append(
                    f"segment {sid}: §9 records confidence {want_conf}, run has {got_conf}")

    none_count = sum(1 for s in segs.values() if s["dominant"] is None)
    if none_count != SECTION9_TALLY["correct_no_face"]:
        problems.append(
            f"run has {none_count} segments with no label; §9 reports "
            f"{SECTION9_TALLY['correct_no_face']} correct-no-face")

    tally_sum = (SECTION9_TALLY["correct_no_face"] + SECTION9_TALLY["false_positive"]
                 + SECTION9_TALLY["match"] + SECTION9_TALLY["mismatch"])
    if tally_sum != SECTION9_TALLY["total"]:
        problems.append(f"§9 category counts sum to {tally_sum}, not {SECTION9_TALLY['total']}")

    rows = _rows(segs)
    if len({r["segment_id"] for r in rows}) != len(rows):
        problems.append("a segment is labelled twice")
    if len(rows) != SECTION9_TALLY["total"]:
        problems.append(f"face-presence coverage is {len(rows)}, not {SECTION9_TALLY['total']}")
    n_no_face = sum(1 for r in rows if not r["face_present"])
    expect_no_face = SECTION9_TALLY["correct_no_face"] + SECTION9_TALLY["false_positive"]
    if n_no_face != expect_no_face:
        problems.append(f"{n_no_face} faceless segments derived; §9 implies {expect_no_face}")

    return {
        "ok": not problems,
        "problems": problems,
        "segments_in_run": len(segs),
        "rows_described": len(described),
        "rows_total": len(rows),
        "no_label_segments": none_count,
        "faceless_segments": n_no_face,
    }


def load(strict_only: bool = False, require_anchor: bool = True) -> list[dict]:
    """
    Return the ground-truth rows, joined to the run's segment timings.

    strict_only    keep only tier == "explicit" — the rows §9 individually
                   tabulates. Use for the conservative reading of the
                   classification bench.
    require_anchor refuse to return anything if the anchor check fails.
    """
    check = anchor_check()
    if require_anchor and not check["ok"]:
        raise ValueError(
            "Ground-truth anchor check failed; refusing to return labels:\n  "
            + "\n  ".join(check["problems"]))
    segs = load_anchor_segments()
    rows = []
    for r in _rows(segs):
        if strict_only and r["tier"] != "explicit":
            continue
        s = segs.get(r["segment_id"])
        if s is None:
            continue
        rows.append({**r, "start_time": s["start_time"], "end_time": s["end_time"],
                     "frame_count": s["frame_count"], "text": s["text"]})
    return rows


def detection_set(**kw) -> list[dict]:
    """Rows usable by the detector bench: every segment, face present or not."""
    return load(**kw)


def expression_set(strict_only: bool = False, **kw) -> list[dict]:
    """
    Rows usable by the classification bench.

    A segment qualifies only if §9 states a real face is present **and** describes
    the visible expression. Segments whose only expression evidence is that §9
    judged DeepFace's label reasonable are excluded, because that would define the
    ground truth by the incumbent being right.
    """
    return [r for r in load(strict_only=strict_only, **kw)
            if r["face_present"] and r["expression"] is not None]


def segments_without_expression() -> list[int]:
    """Segments with verified face presence but no verified expression."""
    segs = load_anchor_segments()
    return sorted(r["segment_id"] for r in _rows(segs)
                  if r["face_present"] and r["expression"] is None)


def summary() -> dict:
    segs = load_anchor_segments()
    rows = _rows(segs)
    by_tier: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for r in rows:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
        if not r["face_present"]:
            key = "NO_FACE"
        elif r["expression"] is None:
            key = "FACE_expression_unknown"
        else:
            key = str(r["expression"])
        by_class[key] = by_class.get(key, 0) + 1
    return {
        "video_id": ANCHOR_VIDEO,
        "total_segments": SECTION9_TALLY["total"],
        "face_presence_labels": len(rows),
        "expression_labels": len(expression_set()),
        "expression_labels_strict": len(expression_set(strict_only=True)),
        "by_tier": by_tier,
        "by_class": by_class,
        "source": "PROTOTYPE_FINDINGS.md §9",
    }


if __name__ == "__main__":
    chk = anchor_check()
    print("Anchor check:", "PASS" if chk["ok"] else "FAIL")
    for p_ in chk["problems"]:
        print("  !", p_)
    print(json.dumps({"anchor": chk, "summary": summary(),
                      "no_expression_label": segments_without_expression()}, indent=2))
