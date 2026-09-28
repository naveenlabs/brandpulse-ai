"""
ground_truth_v2.py — load, validate and summarise the collected labels.

v1's ground truth was *transcribed* out of a prose review written for another
purpose, which is why it carried a selection effect it could not remove
(`FACIAL_MODEL_ANALYSIS.md` §2.3). v2's is collected directly against a sample
drawn before any model ran, so this module's job is narrower and stricter: read
what the rater actually clicked, refuse it if it does not match the manifest, and
expose three things — the face-presence set, the expression set, and the
reliability ceiling.

Nothing here derives a label from a model. Nothing here fills a gap by inference.
A frame the rater marked unsure stays unsure, and is excluded, counted and
reported.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
MANIFEST = HERE / "sample.json"
LABELS = HERE / "facial_labels_v2.json"

POSITIVE, NEUTRAL, NEGATIVE = "POSITIVE", "NEUTRAL", "NEGATIVE"

# What each button means. PROTOCOL.md §5.1.
FACE_PRESENT = {"happy", "neutral", "angry", "sad", "surprised", "expr_unsure"}
FACE_ABSENT = {"no_face"}
FACE_UNKNOWN = {"face_unsure"}
ALL_CHOICES = FACE_PRESENT | FACE_ABSENT | FACE_UNKNOWN

# The primary mapping, declared in PROTOCOL.md §5.2 before collection.
EXPRESSION_THREE = {
    "happy": POSITIVE,
    "neutral": NEUTRAL,
    "angry": NEGATIVE,
    "sad": NEGATIVE,
    "surprised": POSITIVE,
}
# The pre-declared sensitivity check, also from §5.2.
EXPRESSION_THREE_SURPRISE_NEUTRAL = {**EXPRESSION_THREE, "surprised": NEUTRAL}


class GroundTruthError(RuntimeError):
    """Raised when the labels do not match the manifest they claim to be for."""


def load_manifest() -> dict:
    if not MANIFEST.exists():
        raise GroundTruthError("sample.json not found — run `python sample.py` first.")
    return json.loads(MANIFEST.read_text())


def load_raw(path: Path | None = None) -> dict[str, str]:
    """The rater's clicks, uid -> choice. No interpretation applied."""
    p = path or LABELS
    if not p.exists():
        raise GroundTruthError(
            f"{p.name} not found. Label with facial_bench/v2/label_here.html and "
            "export it into this directory."
        )
    payload = json.loads(p.read_text())
    return dict(payload.get("labels", payload))


def validate(raw: dict[str, str], manifest: dict | None = None) -> dict:
    """
    Check the labels against the manifest. Returns a report; raises on anything
    that would make the labels untrustworthy rather than merely incomplete.
    """
    m = manifest or load_manifest()
    known = {p["uid"] for p in m["presentations"]}

    unknown_uids = sorted(set(raw) - known)
    if unknown_uids:
        raise GroundTruthError(
            f"{len(unknown_uids)} label(s) reference uids not in the manifest, "
            f"e.g. {unknown_uids[:3]}. These labels are for a different sample."
        )
    bad_values = sorted({v for v in raw.values() if v not in ALL_CHOICES})
    if bad_values:
        raise GroundTruthError(f"unrecognised label value(s): {bad_values}")

    missing = sorted(known - set(raw))
    return {
        "n_presentations": len(known),
        "n_labelled": len(raw),
        "n_missing": len(missing),
        "missing": missing,
        "complete": not missing,
    }


def _rows(raw: dict[str, str], manifest: dict) -> list[dict]:
    """First presentations only, joined to their manifest metadata."""
    out = []
    for p in manifest["presentations"]:
        if p["retest"] or p["uid"] not in raw:
            continue
        out.append({
            "uid": p["uid"], "video_id": p["video_id"], "speaker": p["speaker"],
            "split": p["split"], "frame": p["frame"], "choice": raw[p["uid"]],
        })
    return out


def face_set(raw: dict[str, str] | None = None, manifest: dict | None = None,
             split: str | None = None) -> list[dict]:
    """
    Face-presence ground truth: one row per frame the rater could judge.

    Frames marked `face_unsure` are excluded — the rater could not tell, so
    neither a hit nor a miss can fairly be attributed to a detector on them.
    """
    m = manifest or load_manifest()
    r = raw if raw is not None else load_raw()
    rows = []
    for row in _rows(r, m):
        if row["choice"] in FACE_UNKNOWN:
            continue
        if split and row["split"] != split:
            continue
        rows.append({**row, "has_face": row["choice"] in FACE_PRESENT})
    return rows


def expression_set(raw: dict[str, str] | None = None, manifest: dict | None = None,
                   mapping: dict[str, str] | None = None,
                   split: str | None = None) -> list[dict]:
    """
    Expression ground truth: frames with a face AND a readable expression.

    `expr_unsure` is excluded for the same reason as `face_unsure`: it is a
    property of the frame, not of any model. PROTOCOL.md §8 keeps *model*
    abstentions in and scores them wrong; that is a different thing.
    """
    m = manifest or load_manifest()
    r = raw if raw is not None else load_raw()
    mp = mapping or EXPRESSION_THREE
    rows = []
    for row in _rows(r, m):
        if row["choice"] not in mp:
            continue
        if split and row["split"] != split:
            continue
        rows.append({**row, "fine": row["choice"], "three": mp[row["choice"]]})
    return rows


# ── Reliability (PROTOCOL.md §5.3) ────────────────────────────────────────────

def cohens_kappa(a: list[str], b: list[str]) -> float:
    """
    Cohen's kappa for two ratings of the same items.

    Returns 0.0 when both ratings are the same single category, where kappa is
    undefined (pe == 1): chance agreement is already total, so no agreement
    beyond chance can be demonstrated. Reported as such, never as 1.0.
    """
    if len(a) != len(b):
        raise ValueError("rating lists must be the same length")
    n = len(a)
    if n == 0:
        raise ValueError("no pairs to score")

    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if pe >= 1.0:
        return 0.0
    return (po - pe) / (1 - pe)


def retest_pairs(raw: dict[str, str] | None = None,
                 manifest: dict | None = None) -> list[dict]:
    """Both labels for every re-test frame the rater completed twice."""
    m = manifest or load_manifest()
    r = raw if raw is not None else load_raw()
    pairs = []
    for p in m["presentations"]:
        if not p["retest"]:
            continue
        first_uid, second_uid = p["of"], p["uid"]
        if first_uid in r and second_uid in r:
            pairs.append({
                "uid": first_uid, "video_id": p["video_id"], "speaker": p["speaker"],
                "first": r[first_uid], "second": r[second_uid],
                "agree": r[first_uid] == r[second_uid],
            })
    return pairs


def reliability(raw: dict[str, str] | None = None, manifest: dict | None = None,
                mapping: dict[str, str] | None = None) -> dict:
    """
    The ceiling. How often does the rater agree with themselves on the same image?

    Reported at two granularities, because they answer different questions:
      - `fine`  : the eight buttons as clicked — how stable is the taxonomy?
      - `three` : after mapping to POSITIVE/NEUTRAL/NEGATIVE — how stable is the
                  signal the system actually consumes? This is the number that
                  bounds what any model can be expected to score.
    """
    pairs = retest_pairs(raw, manifest)
    if not pairs:
        return {"n_pairs": 0, "note": "no completed re-test pairs"}

    mp = mapping or EXPRESSION_THREE

    def coarse(choice: str) -> str:
        if choice in FACE_ABSENT:
            return "NO_FACE"
        if choice in FACE_UNKNOWN:
            return "UNSURE_FACE"
        if choice == "expr_unsure":
            return "UNSURE_EXPR"
        return mp[choice]

    fa = [p["first"] for p in pairs]
    fb = [p["second"] for p in pairs]
    ta = [coarse(p["first"]) for p in pairs]
    tb = [coarse(p["second"]) for p in pairs]

    n = len(pairs)
    return {
        "n_pairs": n,
        "fine_agreement": sum(x == y for x, y in zip(fa, fb)) / n,
        "fine_kappa": cohens_kappa(fa, fb),
        "three_agreement": sum(x == y for x, y in zip(ta, tb)) / n,
        "three_kappa": cohens_kappa(ta, tb),
        "disagreements": [p for p in pairs if not p["agree"]],
    }


# ── Summary ───────────────────────────────────────────────────────────────────

def summary(raw: dict[str, str] | None = None, manifest: dict | None = None) -> str:
    m = manifest or load_manifest()
    r = raw if raw is not None else load_raw()
    v = validate(r, m)

    faces = face_set(r, m)
    exprs = expression_set(r, m)
    fine = Counter(e["fine"] for e in exprs)
    three = Counter(e["three"] for e in exprs)
    rel = reliability(r, m)

    lines = [
        f"labelled {v['n_labelled']}/{v['n_presentations']} presentations"
        + ("" if v["complete"] else f"  ({v['n_missing']} missing)"),
        "",
        f"face-presence set : {len(faces)} frames "
        f"({sum(f['has_face'] for f in faces)} with a face, "
        f"{sum(not f['has_face'] for f in faces)} without)",
        f"expression set    : {len(exprs)} frames",
        "",
        "  " + "  ".join(f"{k}={fine[k]}" for k in
                         ("neutral", "happy", "angry", "sad", "surprised") if fine[k]),
        "  " + "  ".join(f"{k}={three[k]}" for k in (POSITIVE, NEUTRAL, NEGATIVE) if three[k]),
        "",
    ]
    for name in ("dev", "holdout"):
        e = expression_set(r, m, split=name)
        f = face_set(r, m, split=name)
        lines.append(f"{name:<8} faces {len(f):>4}   expressions {len(e):>4}")

    if rel["n_pairs"]:
        lines += [
            "",
            f"re-test: {rel['n_pairs']} pairs · "
            f"fine {rel['fine_agreement']:.1%} (k={rel['fine_kappa']:.3f}) · "
            f"three-class {rel['three_agreement']:.1%} (k={rel['three_kappa']:.3f})",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
