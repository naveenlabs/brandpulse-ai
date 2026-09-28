"""
analyst_facts.py — every fact the written report states, computed without a model.

The written report (pipeline/analyst.py) has one rule it is built on: the local
model writes words and code owns facts. Everything in this module is a pure,
deterministic function of a saved report — no I/O except reading the measured
figures, no network, no model — so every number, level and sign the book prints
can be re-derived from the report file and is unit-tested
(tests/test_analyst_facts.py).

What is measured and what is a rule
-----------------------------------
Nothing here is a new measurement. The channel accuracies are read from
`evaluation/ui_evidence/figures.json`, which re-derives them from the benches.
The rest are RULES, declared in one place each and printed by the book beside what they
decide, so a reader can see why a report says what it says:

  - A lean is the mean of +1 / 0 / -1 readings with its standard error. A lean
    is only called positive or negative when its 95% interval excludes zero.
  - "The reviewer is warmer than the audience" needs the 95% interval of the
    gap between the two leans to exclude zero. No tuned margin.
  - The reading-confidence level is a table of three checks against floors the
    project already had: `sweep.MIN_COMMENTS` (30) and the coverage floor
    (0.5, `figures.json` pipeline.channel_coverage_floor), plus a majority rule.
  - The tone line's smoothing window and turning-point prominence are display
    choices for a chart, named as such.

Honest limits of the statistics, stated here once: segments next to each other
are not independent (a reviewer who is positive at 2:00 is likely positive at
2:10), so the standard errors below are optimistic, and an interval that just
excludes zero should be read as "probably", not "certainly". The two leans also
come from classifiers of different accuracy (transcript 67.8%, comments 78.7%)
that the arithmetic does not correct for.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from pipeline.orchestrator import CONFLICT_FLAG_THRESHOLD, _channel_valences, _to_valence

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = ROOT / "evaluation" / "ui_evidence" / "figures.json"

# The two-sided 95% quantile of the standard normal distribution.
Z95 = 1.959963984540054

# `sweep.MIN_COMMENTS`: the editorial floor a combined report already refuses a
# video under. Duplicated rather than imported so the pipeline does not depend on
# the sweep module; a test asserts the two agree.
MIN_COMMENTS = 30

# The majority rule for the third reading-confidence check: more than half of
# the conflict resting on the two weakest channels. Half is not tuned; it is the
# point at which "most of this score" stops being true.
WEAK_CONFLICT_MAJORITY = 0.5

# Tone line display choices (a chart, not a measurement).
TONE_WINDOW_S = 60.0
TURN_MIN_PROMINENCE = 0.2
TURN_MIN_GAP_S = 60.0
TURN_MAX = 3

VALUE = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "NEGATIVE": -1.0}
VALENCES = ("POSITIVE", "NEUTRAL", "NEGATIVE")


# ── reading the report ───────────────────────────────────────────────────────

def load_reference(path: Path = REFERENCE_PATH) -> dict:
    """
    The measured channel accuracies and the coverage floor, from figures.json.

    Returns {} when the file is missing or unreadable, and callers then report
    the accuracies as unavailable rather than printing a remembered number.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        channels = {c["channel"]: c for c in data.get("channels", []) if "channel" in c}
        return {
            "accuracy": {k: v.get("accuracy_pct") for k, v in channels.items()},
            "n": {k: v.get("n") for k, v in channels.items()},
            "source": {k: v.get("source") for k, v in channels.items()},
            "coverage_floor": (data.get("pipeline") or {}).get("channel_coverage_floor"),
        }
    except Exception:          # noqa: BLE001 - a missing reference degrades, never raises
        return {}


def segment_view(seg: dict) -> dict:
    """
    A saved-report segment in the shape the orchestrator's helpers read.

    Saved reports keep each channel's reading under `model_outputs`; the
    orchestrator reads them at the top level of a live segment. Adapting here
    lets `_channel_valences` and `_to_valence` be reused rather than rewritten,
    so the written report can never place a reading on a different side of the
    valence axis from the scorer. Handles both vocal schemas on disk (a dict
    since 02 Sep 2026, a bare word before).
    """
    seg = seg if isinstance(seg, dict) else {}
    mo = seg.get("model_outputs") if isinstance(seg.get("model_outputs"), dict) else {}
    return {
        "segment_id": seg.get("segment_id"),
        "start_time": seg.get("start_s"),
        "end_time": seg.get("end_s"),
        "text": seg.get("text") or "",
        "transcript_sentiment": mo.get("transcript_sentiment"),
        "facial_emotion": mo.get("facial_emotion"),
        "vocal_emotion": mo.get("vocal_emotion"),
    }


def valences(seg: dict, comment_sentiment: dict | None) -> dict[str, str]:
    """Every channel of a saved segment with a usable valence (orchestrator's rule)."""
    return _channel_valences(segment_view(seg), comment_sentiment)


def duration(seg: dict) -> float:
    """A segment's length in seconds, never negative, 0 for a malformed one."""
    try:
        return max(0.0, float(seg.get("end_s")) - float(seg.get("start_s")))
    except (TypeError, ValueError):
        return 0.0


def _num(value, default=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value) if math.isfinite(value) else default


def mmss(seconds) -> str:
    """Seconds as m:ss, the same rule as the interface's format.js."""
    s = _num(seconds)
    if s is None:
        return "-"
    whole = max(0, math.floor(s))
    return f"{whole // 60}:{whole % 60:02d}"


def subject_of(report: dict, filename: str | None = None) -> dict:
    """
    Brand, product and title for a report.

    app.py names a report "Brand (Product).json", so the product is read back
    from that structure; a sweep member carries its video title instead.
    """
    brand = str(report.get("brand_name") or "").strip()
    product = ""
    if filename:
        base = re.sub(r"\.json$", "", Path(filename).name, flags=re.I)
        match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", base)
        if match:
            brand = brand or match.group(1).strip()
            product = match.group(2).strip()
    return {"brand": brand, "product": product,
            "title": str(report.get("video_title") or "").strip()}


def video_id_of(report: dict) -> str | None:
    """The 11-character YouTube id in the report's URL, or None."""
    match = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})",
                      str(report.get("video_url") or ""))
    return match.group(1) if match else None


# ── leans ───────────────────────────────────────────────────────────────────

def lean_of(values: list[float], weights: list[float] | None = None) -> dict | None:
    """
    Weighted mean of +1/0/-1 readings, with a standard error.

    The standard error is the linearised one for a weighted mean with a small-
    sample correction; with equal weights it reduces exactly to s / sqrt(n)
    with the n - 1 denominator. None when there is nothing to average; `se` is
    None with a single reading.
    """
    if not values:
        return None
    weights = list(weights) if weights is not None else [1.0] * len(values)
    pairs = [(v, w) for v, w in zip(values, weights) if w > 0]
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    mean = sum(v * w for v, w in pairs) / total
    n = len(pairs)
    se = None
    if n >= 2:
        spread = sum((w * (v - mean)) ** 2 for v, w in pairs)
        se = math.sqrt(spread) / total * math.sqrt(n / (n - 1))
    return {"lean": mean, "se": se, "n": n}


def lean_call(lean: dict | None) -> str:
    """'positive' / 'negative' when the 95% interval excludes zero, else 'balanced'."""
    if not lean:
        return "unknown"
    if lean.get("se") is None:
        return "unknown"
    low = lean["lean"] - Z95 * lean["se"]
    high = lean["lean"] + Z95 * lean["se"]
    if low > 0:
        return "positive"
    if high < 0:
        return "negative"
    return "balanced"


def reviewer_lean(segments: list[dict]) -> dict:
    """
    How positive the reviewer's own words were, weighted by time spoken.

    Read from the transcript channel only (67.8% on held-out speakers). Time,
    not segment count, because a reviewer who spends four minutes praising and
    ten seconds complaining has not spoken evenly.
    """
    seconds = {v: 0.0 for v in VALENCES}
    counts = {v: 0 for v in VALENCES}
    values, weights = [], []
    unread = 0
    for seg in segments or []:
        v = valences(seg, None).get("transcript")
        if v is None:
            unread += 1
            continue
        d = duration(seg)
        seconds[v] += d
        counts[v] += 1
        values.append(VALUE[v])
        weights.append(d)
    lean = lean_of(values, weights)
    return {
        "lean": lean["lean"] if lean else None,
        "se": lean["se"] if lean else None,
        "n": lean["n"] if lean else 0,
        "call": lean_call(lean),
        "counts": counts,
        "seconds": {k: round(v, 2) for k, v in seconds.items()},
        "unread": unread,
    }


def audience_lean(comments: list[dict]) -> dict:
    """How positive the comments were, one comment one vote (comment model, 78.7%)."""
    counts = {v: 0 for v in VALENCES}
    values = []
    for c in comments or []:
        v = _to_valence((c or {}).get("label"))
        if v is None:
            continue
        counts[v] += 1
        values.append(VALUE[v])
    lean = lean_of(values)
    return {
        "lean": lean["lean"] if lean else None,
        "se": lean["se"] if lean else None,
        "n": lean["n"] if lean else 0,
        "call": lean_call(lean),
        "counts": counts,
    }


def compare(first: dict, second: dict) -> dict:
    """
    The gap between two leans and whether it is distinguishable from zero.

    `call` is 'first_warmer', 'second_warmer' or 'no_clear_difference' by the
    95% interval of the gap, and 'unknown' when either side has no standard
    error. The two sides are treated as independent samples.
    """
    a, b = (first or {}).get("lean"), (second or {}).get("lean")
    sa, sb = (first or {}).get("se"), (second or {}).get("se")
    if a is None or b is None or sa is None or sb is None:
        return {"gap": None if a is None or b is None else a - b,
                "se": None, "low": None, "high": None, "call": "unknown"}
    gap = a - b
    se = math.sqrt(sa ** 2 + sb ** 2)
    low, high = gap - Z95 * se, gap + Z95 * se
    if low > 0:
        call = "first_warmer"
    elif high < 0:
        call = "second_warmer"
    else:
        call = "no_clear_difference"
    return {"gap": gap, "se": se, "low": low, "high": high, "call": call}


def agreement(reviewer: dict, audience: dict) -> dict:
    """Reviewer against audience, with the calls named for what they mean."""
    out = compare(reviewer, audience)
    out["call"] = {"first_warmer": "reviewer_warmer",
                   "second_warmer": "audience_warmer"}.get(out["call"], out["call"])
    return out


# ── coverage and reading confidence ──────────────────────────────────────────

def coverage(segments: list[dict], comment_sentiment: dict | None) -> dict:
    """Per channel: segments read, total and share (the interface's own rule)."""
    total = len(segments or [])
    out = {}
    for channel in ("transcript", "facial", "vocal"):
        read = sum(1 for s in segments or [] if valences(s, None).get(channel))
        out[channel] = {"read": read, "total": total,
                        "share": (read / total) if total else 0.0}
    has = 1 if _to_valence((comment_sentiment or {}).get("label")) else 0
    out["comment"] = {"read": total * has, "total": total, "share": float(has)}
    return out


def weak_conflict_share(segments: list[dict], comment_sentiment: dict | None) -> dict:
    """
    How much of the conflict does NOT come from the two strongest channels.

    A segment's conflict is "strong-driven" when the transcript and the comment
    channel — the two measured best on held-out data — both read it and
    disagree with each other. Every other conflicted segment's disagreement
    rests on the face or the voice (34.2% and 48.9%). Weighted by conflict
    score, because that is what the Authenticity Score is built from.
    """
    weak = total = 0.0
    for seg in segments or []:
        c = _num(seg.get("conflict_score"), 0.0) or 0.0
        if c <= 0:
            continue
        total += c
        v = valences(seg, comment_sentiment)
        strong = ("transcript" in v and "comment" in v and v["transcript"] != v["comment"])
        if not strong:
            weak += c
    return {"weak": round(weak, 4), "total": round(total, 4),
            "share": (weak / total) if total > 0 else None}


# What no single report can promise, carried with every level so the book
# cannot print a coverage level without it. Figures from
# baseline_bench/BASELINE_ANALYSIS.md §0 (Spearman rho against hand ratings).
CEILING = {
    "text": ("No score in this system has been shown to track human judgement of "
             "authenticity. On 119 hand-rated segments the four-channel design scored "
             "rho = +0.0575 (95% CI -0.1282 to +0.2364); people agreed with each other "
             "at rho = +0.8038."),
    "n": 119, "rho": 0.0575, "ci": [-0.1282, 0.2364], "human_rho": 0.8038,
    "source": "baseline_bench/BASELINE_ANALYSIS.md",
}


def reading_confidence(report: dict, reference: dict | None = None) -> dict:
    """
    How well this video was covered: well / partly / thinly.

    Deliberately NOT "high / medium / low confidence". On the twelve reports
    saved when this was written (23 Sep 2026) every one passed every check below,
    and printing "High confidence" twelve times over a score the baseline bench
    found tracks no human judgement
    (CEILING) would be the most misleading word in the book. What these checks
    can honestly say is how much evidence the reading rests on; the ceiling is
    returned beside it and the book prints both.

      1. Enough comments to read the audience: n >= MIN_COMMENTS.
      2. The reviewer's words were read: transcript coverage >= the floor.
      3. The conflict rests mostly on the stronger channels:
         weak_conflict_share <= WEAK_CONFLICT_MAJORITY (passes when no
         segment conflicted at all).

    Thinly covered when 1 or 2 fails; partly when only 3 fails; well when all
    pass; unknown when the coverage floor could not be read.
    """
    reference = reference if reference is not None else load_reference()
    floor = _num((reference or {}).get("coverage_floor"))
    segments = report.get("all_segments") or []
    comments = report.get("all_comments") or []
    cs = report.get("comment_sentiment") or {}
    cov = coverage(segments, cs)
    n_comments = sum(1 for c in comments if _to_valence((c or {}).get("label")))
    weak = weak_conflict_share(segments, cs)

    checks = [
        {"id": "comments", "label": "Enough comments to read the audience",
         "value": n_comments, "target": MIN_COMMENTS, "unit": "comments",
         "passed": n_comments >= MIN_COMMENTS, "core": True},
        {"id": "transcript", "label": "The reviewer's words were read",
         "value": round(cov["transcript"]["share"], 4), "target": floor,
         "unit": "share", "core": True,
         "passed": None if floor is None else cov["transcript"]["share"] >= floor},
        {"id": "weak_conflict", "label": "The conflict rests mostly on the stronger channels",
         "value": None if weak["share"] is None else round(weak["share"], 4),
         "target": WEAK_CONFLICT_MAJORITY, "unit": "share",
         "passed": True if weak["share"] is None else weak["share"] <= WEAK_CONFLICT_MAJORITY,
         "core": False, "no_conflict": weak["share"] is None},
    ]
    if any(c["core"] and c["passed"] is False for c in checks):
        level = "thinly_covered"
    elif any(c["passed"] is None for c in checks):
        level = "unknown"
    elif all(c["passed"] for c in checks):
        level = "well_covered"
    else:
        level = "partly_covered"

    accuracy = (reference or {}).get("accuracy") or {}
    return {
        "level": level,
        "checks": checks,
        "coverage": cov,
        "weak_conflict": weak,
        "accuracy": {k: accuracy.get(k) for k in ("comment", "transcript", "vocal", "facial")},
        "means_not": "How much evidence this reading rests on. Not whether the verdict "
                     "is right, and not whether anyone in the video was honest.",
        "ceiling": CEILING,
    }


# ── the tone line ────────────────────────────────────────────────────────────

def tone_series(segments: list[dict], window_s: float = TONE_WINDOW_S) -> dict:
    """
    The reviewer's tone over time: raw per segment, and smoothed.

    Raw is the transcript valence (+1/0/-1) times its confidence, or None when
    the transcript was not read. Smoothed averages every read segment inside a
    window centred on each segment's midpoint, weighted by how much of it
    overlaps the window, so a long segment counts for more than a short one.
    """
    rows = []
    for seg in segments or []:
        v = valences(seg, None).get("transcript")
        ts = (segment_view(seg).get("transcript_sentiment") or {})
        conf = _num(ts.get("confidence") if isinstance(ts, dict) else None)
        conf = 1.0 if conf is None else max(0.0, min(1.0, conf))
        start, end = _num(seg.get("start_s"), 0.0), _num(seg.get("end_s"), 0.0)
        rows.append({"seg": seg.get("segment_id"), "start": start, "end": max(start, end),
                     "raw": None if v is None else round(VALUE[v] * conf, 4)})

    half = window_s / 2.0
    points = []
    for row in rows:
        mid = (row["start"] + row["end"]) / 2.0
        lo, hi = mid - half, mid + half
        num = den = 0.0
        for other in rows:
            if other["raw"] is None:
                continue
            overlap = min(hi, other["end"]) - max(lo, other["start"])
            if overlap > 0:
                num += other["raw"] * overlap
                den += overlap
        points.append({**row, "t": round(mid, 2),
                       "smooth": round(num / den, 4) if den > 0 else None})
    return {"window_s": window_s, "points": points, "turns": turning_points(points)}


def turning_points(points: list[dict], max_turns: int = TURN_MAX,
                   min_prominence: float = TURN_MIN_PROMINENCE,
                   min_gap_s: float = TURN_MIN_GAP_S) -> list[dict]:
    """
    The most prominent peaks and dips of the smoothed tone, interior only.

    Prominence is the usual topographic one: how far a peak stands above the
    higher of the two lowest points between it and anything taller on either
    side (mirrored for dips). The strongest are kept, at most `max_turns`, no
    two closer than `min_gap_s`, earliest first.
    """
    series = [(i, p["t"], p["smooth"]) for i, p in enumerate(points) if p.get("smooth") is not None]
    if len(series) < 3:
        return []
    ys = [y for _, _, y in series]
    found = []
    for k in range(1, len(series) - 1):
        y = ys[k]
        for kind, sign in (("peak", 1.0), ("dip", -1.0)):
            s = [sign * v for v in ys]
            if not (s[k] > s[k - 1] and s[k] >= s[k + 1]):
                continue
            left = s[k]
            for j in range(k - 1, -1, -1):
                if s[j] > s[k]:
                    break
                left = min(left, s[j])
            right = s[k]
            for j in range(k + 1, len(s)):
                if s[j] > s[k]:
                    break
                right = min(right, s[j])
            prominence = s[k] - max(left, right)
            if prominence >= min_prominence:
                idx, t, _ = series[k]
                found.append({"seg": points[idx]["seg"], "t": t, "kind": kind,
                              "smooth": y, "prominence": round(prominence, 4)})
    found.sort(key=lambda f: (-f["prominence"], f["t"]))
    kept = []
    for f in found:
        if all(abs(f["t"] - k["t"]) >= min_gap_s for k in kept):
            kept.append(f)
        if len(kept) == max_turns:
            break
    return sorted(kept, key=lambda f: f["t"])


# ── moments ──────────────────────────────────────────────────────────────────

def top_moments(segments: list[dict], comment_sentiment: dict | None, k: int = 3) -> list[dict]:
    """
    The k segments with the highest conflict score, earliest first on a tie.

    The same order as the ledger's "Most conflict first", so the three the
    written report discusses are the first three a reader would find there.
    Segments with no conflict are never included.
    """
    ranked = sorted(
        (s for s in segments or [] if (_num(s.get("conflict_score"), 0.0) or 0.0) > 0),
        key=lambda s: (-(_num(s.get("conflict_score"), 0.0) or 0.0), _num(s.get("start_s"), 0.0)))
    out = []
    for s in ranked[:k]:
        reasons = [str(r) for r in s.get("conflict_reasons") or []]
        out.append({
            "seg": s.get("segment_id"),
            "start": _num(s.get("start_s"), 0.0),
            "end": _num(s.get("end_s"), 0.0),
            "time": mmss(s.get("start_s")),
            "conflict": _num(s.get("conflict_score"), 0.0),
            "flagged": bool(s.get("flagged")),
            "damped": any("_channel_downweighted" in r for r in reasons),
            "valences": valences(s, comment_sentiment),
            "text": s.get("text") or "",
        })
    return out


# ── commercial-interest signs ────────────────────────────────────────────────
#
# Wording, not proof. A hit says these words were spoken or written; the book
# shows the exact quote beside every one so a reader can judge a false positive
# ("LeBron is sponsored by Nike" matches `sponsored by` and is not a sponsor
# read). Patterns are case-insensitive and anchored on word boundaries because
# Whisper's casing and punctuation are not reliable.

SPEECH_PATTERNS = (
    ("sponsored_by", "sponsorship", r"\bsponsored\s+by\b"),
    ("todays_sponsor", "sponsorship", r"\b(?:today'?s|our)\s+sponsor\b"),
    ("for_sponsoring", "sponsorship", r"\bfor\s+sponsoring\b"),
    ("brought_to_you", "sponsorship", r"\bbrought\s+to\s+you\s+by\b"),
    ("paid_partnership", "sponsorship", r"\bpaid\s+(?:partnership|promotion)\b"),
    ("in_partnership", "sponsorship", r"\bin\s+partnership\s+with\b"),
    ("promo_code", "discount_code", r"\b(?:promo|discount|coupon)\s+code\b"),
    ("use_code", "discount_code", r"\buse\s+(?:my\s+|the\s+|our\s+)?code\b"),
    ("percent_off", "discount_code", r"\b\d{1,2}\s*(?:%|percent)\s+off\b"),
    ("affiliate", "affiliate", r"\baffiliate\b"),
    ("commission", "affiliate", r"\b(?:earn|make|get)s?\s+(?:a\s+)?(?:small\s+)?commission\b"),
    ("sent_me", "gifted", r"\b(?:sent|gave|gifted|provided|loaned)\s+(?:me|us)\s+"
                          r"(?:this|these|them|it|the|a\s+pair|a\s+review)\b"),
    ("review_unit", "gifted", r"\breview\s+(?:unit|sample|sample\s+unit)\b"),
)

DESCRIPTION_PATTERNS = (
    ("hashtag_ad", "disclosure", r"(?<![\w#])#(?:ad|advert|sponsored|paidpartnership)\b"),
    ("sponsored_by", "disclosure", r"\bsponsored\s+by\b"),
    ("paid_partnership", "disclosure", r"\bpaid\s+(?:partnership|promotion)\b"),
    ("in_partnership", "disclosure", r"\bin\s+partnership\s+with\b"),
    ("brought_to_you", "disclosure", r"\bbrought\s+to\s+you\s+by\b"),
    ("affiliate", "affiliate", r"\baffiliate\b"),
    ("commission", "affiliate", r"\bcommission\b"),
    ("amazon_associate", "affiliate", r"\bas\s+an\s+amazon\s+associate\b"),
    ("amzn_link", "affiliate", r"\bamzn\.to/"),
    ("amazon_tag", "affiliate", r"\bamazon\.[a-z.]+/\S*[?&]tag="),
    ("affiliate_network", "affiliate",
     r"\b(?:geni\.us|shareasale\.com|awin1\.com|click\.linksynergy\.com|go\.skimresources\.com)\b"),
    ("promo_code", "discount_code", r"\b(?:promo|discount|coupon)\s+code\b"),
    ("use_code", "discount_code", r"\buse\s+(?:my\s+|the\s+)?code\b"),
    ("percent_off", "discount_code", r"\b\d{1,2}\s*%\s*off\b"),
    ("review_unit", "gifted", r"\breview\s+(?:unit|sample)\b"),
    ("provided_by", "gifted", r"\b(?:provided|sent|gifted|loaned)\s+(?:by|to\s+me)\b"),
)

_URL = re.compile(r"https?://([^/\s]+)\S*", re.I)


def _mask_urls(text: str) -> str:
    """A URL is reduced to its host: the host is the evidence, the path is not."""
    return _URL.sub(lambda m: f"{m.group(1)}/…", text)


def _scan(text: str, patterns) -> list[dict]:
    hits = []
    for pid, category, pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.I):
            hits.append({"pattern": pid, "category": category, "match": m.group(0),
                         "at": m.start()})
    return hits


def sponsor_wording(segments: list[dict]) -> list[dict]:
    """Every sponsor-, code-, affiliate- or gift-wording hit in the speech."""
    out = []
    for seg in segments or []:
        text = seg.get("text") or ""
        for hit in _scan(text, SPEECH_PATTERNS):
            out.append({"seg": seg.get("segment_id"), "time": mmss(seg.get("start_s")),
                        "category": hit["category"], "pattern": hit["pattern"],
                        "match": hit["match"]})
    return out


def description_signs(description: str | None) -> list[dict] | None:
    """
    Disclosure, affiliate, discount and gift wording in a video's description.

    None when the description was not fetched ("not checked"), [] when it was
    and nothing matched. Only the hits are kept, each with a short context in
    which any URL is reduced to its host; the description itself is not stored.
    """
    if description is None:
        return None
    text = str(description)
    out = []
    for hit in _scan(text, DESCRIPTION_PATTERNS):
        lo, hi = max(0, hit["at"] - 50), min(len(text), hit["at"] + len(hit["match"]) + 50)
        context = _mask_urls(re.sub(r"\s+", " ", text[lo:hi])).strip()
        out.append({"category": hit["category"], "pattern": hit["pattern"],
                    "match": _mask_urls(hit["match"]), "context": context})
    return out


PAID_TITLE = "Signs of a commercial interest or a mismatch"
PAID_DISCLAIMER = ("These are signs, not proof. A creator can disclose a sponsor and still "
                   "review honestly, and an undisclosed deal would leave none of these marks.")


def paid_signs(report: dict, agreement_: dict, video_meta: dict | None) -> dict:
    """
    Five warning signs, each present / absent / not_checked, with its evidence.

    S1-S3 are facts about what the creator said or published. S4-S5 are
    inferences from this system's own readings and are labelled as such. The
    YouTube paid-promotion label is set by the creator and defaults to off
    (YouTube Data API, paidProductPlacementDetails), so "off" is recorded as
    "not declared", never as "not sponsored".
    """
    segments = report.get("all_segments") or []
    meta = video_meta if isinstance(video_meta, dict) else {}
    fetched = bool(meta.get("fetched"))
    desc_hits = meta.get("description_hits") if fetched else None
    label = meta.get("has_paid_product_placement") if fetched else None

    def by(cats):
        return [h for h in (desc_hits or []) if h.get("category") in cats]

    disclosure = by({"disclosure"})
    if not fetched:
        s1 = "not_checked"
    elif label is True or disclosure:
        s1 = "present"
    else:
        s1 = "absent"

    speech = sponsor_wording(segments)
    s2 = "present" if speech else ("absent" if segments else "not_checked")

    commerce = by({"affiliate", "discount_code", "gifted"})
    s3 = "not_checked" if not fetched else ("present" if commerce else "absent")

    call = (agreement_ or {}).get("call")
    s4 = ("not_checked" if call in (None, "unknown")
          else "present" if call == "reviewer_warmer" else "absent")

    cs = report.get("comment_sentiment") or {}
    positive_flagged = [s.get("segment_id") for s in segments
                        if s.get("flagged") and valences(s, cs).get("transcript") == "POSITIVE"]
    controller_flag = [s.get("segment_id") for s in segments
                       if any("POTENTIAL_PAID_PROMOTION" in str(r)
                              for r in s.get("conflict_reasons") or [])]
    s5 = "present" if (positive_flagged or controller_flag) else ("absent" if segments else "not_checked")

    signs = [
        {"id": "S1", "kind": "fact", "state": s1,
         "name": "The creator declared a paid promotion",
         "evidence": {"label": label, "description": disclosure}},
        {"id": "S2", "kind": "fact", "state": s2,
         "name": "Sponsor, code, affiliate or gift wording in what was said",
         "evidence": {"speech": speech}},
        {"id": "S3", "kind": "fact", "state": s3,
         "name": "Affiliate links, discount codes or a gifted unit in the description",
         "evidence": {"description": commerce}},
        {"id": "S4", "kind": "inference", "state": s4,
         "name": "The reviewer was measurably warmer than the audience",
         "evidence": {"agreement": agreement_}},
        {"id": "S5", "kind": "inference", "state": s5,
         "name": "Positive words at moments the controller flagged",
         "evidence": {"positive_flagged": positive_flagged, "controller_flag": controller_flag}},
    ]
    checked = [s for s in signs if s["state"] != "not_checked"]
    return {"title": PAID_TITLE, "disclaimer": PAID_DISCLAIMER, "signs": signs,
            "present": sum(1 for s in signs if s["state"] == "present"),
            "checked": len(checked)}


# ── everything at once ───────────────────────────────────────────────────────

def compute_facts(report: dict, video_meta: dict | None = None,
                  reference: dict | None = None) -> dict:
    """The whole deterministic layer for one report, in one JSON-safe dict."""
    reference = reference if reference is not None else load_reference()
    segments = report.get("all_segments") or []
    comments = report.get("all_comments") or []
    cs = report.get("comment_sentiment") or {}
    reviewer = reviewer_lean(segments)
    audience = audience_lean(comments)
    agree = agreement(reviewer, audience)
    return {
        "scores": {"authenticity": _num(report.get("authenticity_score")),
                   "brand_health": _num(report.get("brand_health_score"))},
        "segments": len(segments),
        "flagged": sum(1 for s in segments if s.get("flagged")),
        "threshold": CONFLICT_FLAG_THRESHOLD,
        "duration_s": max((_num(s.get("end_s"), 0.0) for s in segments), default=0.0),
        "comments": {"n": len(comments), "distribution": dict(cs.get("distribution") or {}),
                     "label": cs.get("label")},
        "reviewer": reviewer,
        "audience": audience,
        "agreement": agree,
        "confidence": reading_confidence(report, reference),
        "tone": tone_series(segments),
        "moments": top_moments(segments, cs),
        "signs": paid_signs(report, agree, video_meta),
    }
