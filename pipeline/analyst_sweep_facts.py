"""
analyst_sweep_facts.py — what several videos say together, computed without a model.

The combined written report (pipeline/analyst_sweep.py) is built on the same
rule as the single one: the model writes words and code owns facts. Everything
here is a pure, deterministic function of saved files — the sweep record, its
member reports, and each member's written report where one exists — with no
network and no model, so every figure, call and rank the combined book prints
can be re-derived and is unit-tested (tests/test_analyst_sweep_facts.py).

The input is one "bundle" per selected video:

    {"n": 1-based place in the sweep, "entry": the sweep record's member row,
     "report": the member report or None, "analysis": its stored written report
     or None, "stale": whether that was written about a different report file}

What the set is compared on, and why
------------------------------------
Seven videos appeared in two sweeps read days apart (measured 23 Sep 2026;
R1 in analyst/ANALYST_EVALUATION.md). Their reviewer and audience LEANS moved by at most
0.047 and 0.07, and every call stayed the same, 7 of 7. Their SCORES did not:
one video's Brand health went from 79.29 to 15.96 on almost the same comments,
because the comment label is a majority vote and it was a near-tie. So the set
is compared on the leans, which carry intervals; the scores are carried as
ranges with near-ties marked, never as the basis for a call.

The rules, each declared once and printed by the book beside what it decides
----------------------------------------------------------------------------
  - Consensus of calls: `all`, `all_but_one` (at least CONSENSUS_MIN videos),
    `split`, or `too_few` below CONSENSUS_MIN readable videos.
  - A theme row: `agreed` when every video that takes a side takes the same one
    and at least two do; `mostly` when one video dissents from at least three;
    `split` otherwise; `neutral` when nobody takes a side; `too_few` when fewer
    than two take a side.
  - The odd one out: a video whose lean is at least ODD_DISTANCE from the median
    of the others AND whose own 95% interval excludes that median.
  - A change between periods is called only when the two periods' ranges do not
    overlap.

None of these is tuned on this data. CONSENSUS_MIN is the smallest number of
videos for which "all but one" still means more than one; ODD_DISTANCE is a
quarter of the -1..+1 scale; the rest have no threshold at all.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import datetime, timezone

from pipeline import analyst_facts as F
from pipeline import analyst_verify as V
from pipeline.scorer import compute_brand_health_score

# `contract.js` AGGREGATE_TIE_MARGIN: when the top two comment classes are this
# close, the plurality label is not reported as a verdict. Duplicated rather
# than read at runtime so the pipeline does not depend on the interface; a test
# asserts the two agree.
AGGREGATE_TIE_MARGIN = 0.05

# The smallest set for which "all but one" still leaves more than one voice.
CONSENSUS_MIN = 3

# The odd one out: a quarter of the -1..+1 lean scale from the others' median.
ODD_DISTANCE = 0.5

CALLS = ("positive", "balanced", "negative", "unknown")
AGREEMENT_CALLS = ("reviewer_warmer", "audience_warmer", "no_clear_difference", "unknown")
SIGN_IDS = ("S1", "S2", "S3", "S4", "S5")
MOMENT_WORDS = 45
SIGN_EVIDENCE = 3
QUESTIONS_PER_VIDEO = 2

RULES = {
    "consensus": ("A call is shared by the set when every video that could be read has it, "
                  "or all but one when at least three could be read."),
    "theme": ("A theme is agreed on when every video that takes a side on it takes the same one "
              "and at least two do; mostly, when one video dissents from at least three; split, "
              "otherwise."),
    "odd": ("A video stands apart when its lean is at least 0.5 from the median of the others, "
            "a quarter of the scale, and its own 95% interval does not include that median. Only "
            "videos with enough comments, or enough of the words read, take part."),
    "period": ("A change between two periods is called only when their ranges do not overlap. "
               "Otherwise it is within the spread."),
}


# ── small pieces ─────────────────────────────────────────────────────────────

def near_tie(distribution: dict | None, confidence=None, authenticity=None) -> dict | None:
    """
    Whether the comment label was a near-tie (the interface's aggregateIsNearTie).

    `swing` is how far Brand health would move if the label flipped to the
    runner-up with Authenticity held fixed, computed by the scorer's own
    function rather than restated here. None when there is nothing to rank.
    """
    counts = {str(k): int(v or 0) for k, v in (distribution or {}).items()}
    total = sum(counts.values())
    if not total or len(counts) < 2:
        return None
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    margin = (ranked[0][1] - ranked[1][1]) / total
    swing = None
    conf, auth = F._num(confidence), F._num(authenticity)
    if conf is not None and auth is not None:
        first = compute_brand_health_score({"label": ranked[0][0], "confidence": conf}, auth)
        second = compute_brand_health_score({"label": ranked[1][0], "confidence": conf}, auth)
        swing = round(abs(first - second), 2)
    return {"near_tie": margin <= AGGREGATE_TIE_MARGIN, "margin": margin,
            "top": list(ranked[0]), "second": list(ranked[1]), "total": total, "swing": swing}


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _range(values: list[float]) -> dict:
    if not values:
        return {"min": None, "median": None, "max": None, "n": 0}
    return {"min": min(values), "median": _median(values), "max": max(values), "n": len(values)}


def _cut(text: str, n: int) -> str:
    parts = str(text or "").split()
    return " ".join(parts[:n]) + (" …" if len(parts) > n else "")


def facts_of(bundle: dict) -> dict | None:
    """A member's facts: its stored ones when current, else computed live from its report."""
    a = bundle.get("analysis")
    if a and a.get("facts") and not bundle.get("stale"):
        return a["facts"]
    if bundle.get("report"):
        return F.compute_facts(bundle["report"])
    return None


def written_status(bundle: dict) -> str:
    a = bundle.get("analysis")
    if not a or not a.get("written"):
        return "facts-only"
    if bundle.get("stale"):
        return "stale"
    return "complete" if a.get("status") == "complete" else "partial"


# ── one row per video ────────────────────────────────────────────────────────

def _sign_row(signs: dict) -> dict:
    out = {"present": signs.get("present", 0), "checked": signs.get("checked", 0), "signs": []}
    for s in signs.get("signs") or []:
        ev = s.get("evidence") or {}
        short = {}
        for key, value in ev.items():
            short[key] = value[:SIGN_EVIDENCE] if isinstance(value, list) else value
        out["signs"].append({"id": s.get("id"), "kind": s.get("kind"), "state": s.get("state"),
                             "name": s.get("name"), "evidence": short})
    return out


def _tone_row(tone: dict, duration: float) -> dict:
    """The tone line on a percent-of-video axis, so five videos share one scale."""
    dur = duration if duration and duration > 0 else None
    pct = (lambda t: round(100.0 * t / dur, 2)) if dur else (lambda t: None)
    return {"duration_s": duration,
            "points": [{"p": pct(p["t"]), "v": p["smooth"]} for p in tone.get("points") or []],
            "turns": [{"p": pct(t["t"]), "v": t["smooth"], "kind": t["kind"], "seg": t["seg"]}
                      for t in tone.get("turns") or []]}


def video_row(bundle: dict) -> dict:
    """Everything the set compares, for one video."""
    entry = bundle.get("entry") or {}
    base = {"n": bundle["n"], "video_id": entry.get("video_id"),
            "title": entry.get("title") or (bundle.get("report") or {}).get("video_title") or "",
            "channel": entry.get("channel") or "", "published_at": entry.get("published_at") or "",
            "duration_s": entry.get("duration_s"), "comment_count": entry.get("comment_count")}
    facts = facts_of(bundle)
    if facts is None:
        return {**base, "analysed": False, "reason": bundle.get("reason") or "not analysed"}
    report = bundle.get("report") or {}
    cs = report.get("comment_sentiment") or {}
    a = bundle.get("analysis") or {}
    written = a.get("written") if not bundle.get("stale") else None
    moment = None
    if facts.get("moments"):
        m = facts["moments"][0]
        note = next((x["text"] for x in (written or {}).get("moment_notes") or [] if x.get("seg") == m["seg"]),
                    None)
        moment = {"seg": m["seg"], "time": m["time"], "start": m["start"], "end": m["end"],
                  "conflict": m["conflict"],
                  "flagged": m["flagged"], "damped": m["damped"], "valences": m["valences"],
                  "text": _cut(m["text"], MOMENT_WORDS), "note": note}
    confidence = facts.get("confidence") or {}
    return {
        **base, "analysed": True, "written": written_status(bundle),
        "scores": facts["scores"],
        "comments": {"read": facts["comments"]["n"], "distribution": facts["comments"]["distribution"],
                     "label": facts["comments"]["label"]},
        "near_tie": near_tie(facts["comments"]["distribution"], cs.get("confidence"),
                             facts["scores"].get("authenticity")),
        "reviewer": {k: facts["reviewer"].get(k) for k in ("lean", "se", "n", "call")},
        "audience": {k: facts["audience"].get(k) for k in ("lean", "se", "n", "call", "counts")},
        "agreement": {k: facts["agreement"].get(k) for k in ("gap", "low", "high", "call")},
        "coverage": confidence.get("level", "unknown"),
        "coverage_failed": [c["label"] for c in confidence.get("checks") or [] if c.get("passed") is False],
        "coverage_failed_ids": [c["id"] for c in confidence.get("checks") or [] if c.get("passed") is False],
        "signs": _sign_row(facts.get("signs") or {}),
        "moment": moment,
        "tone": _tone_row(facts.get("tone") or {}, facts.get("duration_s") or 0.0),
        "segments": facts.get("segments"), "flagged": facts.get("flagged"),
        "verdict": ({"text": written["verdict"]["text"], "source": written["verdict"]["source"]}
                    if written and written.get("verdict") else None),
    }


# ── the set ──────────────────────────────────────────────────────────────────

def consensus(calls: list[str]) -> dict:
    """The consensus rule over one kind of call (RULES['consensus'])."""
    readable = [c for c in calls if c and c != "unknown"]
    n = len(readable)
    if n < CONSENSUS_MIN:
        return {"label": "too_few", "call": None, "count": 0, "of": n}
    ranked = Counter(readable).most_common()
    top, k = ranked[0]
    tied = len(ranked) > 1 and ranked[1][1] == k
    if k == n:
        return {"label": "all", "call": top, "count": k, "of": n}
    if k == n - 1 and not tied:
        return {"label": "all_but_one", "call": top, "count": k, "of": n}
    return {"label": "split", "call": None if tied else top, "count": k, "of": n}


def odd_one_out(rows: list[dict]) -> dict | None:
    """
    The video that stands furthest apart on either lean (RULES['odd']), or None.

    Only the leans are used: re-reading the same video moved them by at most
    0.07 while it moved Brand health by 63 points, so a video that "stands
    apart" on a score may only have been read on a different day.

    A lean only takes part where the single-video coverage check for it
    passed: the audience with at least MIN_COMMENTS comments, the reviewer
    with the transcript read above the coverage floor. Two comments that
    agree have an interval of zero width, and would otherwise "stand apart"
    with certainty.
    """
    best = None
    floor = {"reviewer": "transcript", "audience": "comments"}
    for dim in ("reviewer", "audience"):
        pts = [(r["n"], r[dim]["lean"], r[dim]["se"]) for r in rows
               if r.get("analysed") and r[dim].get("lean") is not None and r[dim].get("se") is not None
               and floor[dim] not in (r.get("coverage_failed_ids") or [])]
        if len(pts) < CONSENSUS_MIN:
            continue
        for n, lean, se in pts:
            others = [x[1] for x in pts if x[0] != n]
            med = _median(others)
            low, high = lean - F.Z95 * se, lean + F.Z95 * se
            distance = abs(lean - med)
            if distance >= ODD_DISTANCE and (med < low or med > high):
                cand = {"n": n, "dimension": dim, "lean": lean, "se": se, "low": low, "high": high,
                        "others_median": med, "others": sorted(others), "distance": distance}
                if best is None or distance > best["distance"] + 1e-12:
                    best = cand
    if best is not None:
        row = next(r for r in rows if r["n"] == best["n"])
        best["video_id"], best["title"] = row["video_id"], row["title"]
    return best


def set_coverage(rows: list[dict]) -> dict:
    """How much evidence the set rests on: well / partly / thinly, beside the ceiling."""
    analysed = [r for r in rows if r.get("analysed")]
    levels = [r["coverage"] for r in analysed]
    thin = sum(1 for lv in levels if lv == "thinly_covered")
    unknown = sum(1 for lv in levels if lv == "unknown")
    readable = len(analysed) - thin
    if readable - unknown >= CONSENSUS_MIN:
        covered = True
    elif readable >= CONSENSUS_MIN:
        covered = None
    else:
        covered = False
    checks = [
        {"id": "videos", "label": "Enough videos to compare", "value": len(analysed),
         "target": CONSENSUS_MIN, "passed": len(analysed) >= CONSENSUS_MIN, "core": True},
        {"id": "covered", "label": "Enough of them covered well enough to read",
         "value": readable - unknown, "target": CONSENSUS_MIN, "passed": covered, "core": True},
        {"id": "none_thin", "label": "No video thinly covered", "value": thin, "target": 0,
         "passed": thin == 0, "core": False},
    ]
    if any(c["core"] and c["passed"] is False for c in checks):
        level = "thinly_covered"
    elif any(c["passed"] is None for c in checks):
        level = "unknown"
    elif all(c["passed"] for c in checks):
        level = "well_covered"
    else:
        level = "partly_covered"
    return {"level": level, "checks": checks,
            "videos": [{"n": r["n"], "level": r["coverage"], "failed": r["coverage_failed"]} for r in analysed],
            "means_not": ("How much evidence this set rests on. Not whether any verdict is right, "
                          "and not whether anyone in these videos was honest."),
            "ceiling": F.CEILING}


def set_signs(rows: list[dict]) -> dict:
    """Each of the five signs, counted over the videos."""
    analysed = [r for r in rows if r.get("analysed")]
    out = []
    for sid in SIGN_IDS:
        states = {}
        meta = {}
        for r in analysed:
            s = next((x for x in r["signs"]["signs"] if x["id"] == sid), None)
            states[r["n"]] = s["state"] if s else "not_checked"
            if s and not meta:
                meta = {"name": s["name"], "kind": s["kind"]}
        counted = Counter(states.values())
        out.append({"id": sid, **meta, "states": states,
                    "present": counted.get("present", 0), "absent": counted.get("absent", 0),
                    "not_checked": counted.get("not_checked", 0),
                    "present_in": [n for n, st in states.items() if st == "present"]})
    return {"title": F.PAID_TITLE, "disclaimer": F.PAID_DISCLAIMER, "signs": out,
            "videos": len(analysed)}


def questions_across(bundles: list[dict], k: int = QUESTIONS_PER_VIDEO) -> list[dict]:
    """The questions each audience asked, the first k per video, most-liked first."""
    from pipeline import analyst as A     # the one shared rule; analyst does not import this module
    out = []
    for b in bundles:
        report = b.get("report")
        if not report:
            continue
        a = b.get("analysis") or {}
        found = ((a.get("reading") or {}).get("questions") if not b.get("stale") else None)
        found = found if found is not None else A.questions_asked(report.get("all_comments") or [])
        for q in found[:k]:
            out.append({"n": b["n"], "i": q["i"], "quote": q["quote"]})
    return out


def about_reviewers(bundles: list[dict]) -> list[dict]:
    """What each audience said about the reviewer, from the member topics that are about them."""
    out = []
    for b in bundles:
        a = b.get("analysis") or {}
        if b.get("stale"):
            continue
        for t in (a.get("reading") or {}).get("topics") or []:
            if not V.is_meta_topic(t.get("name")):
                continue
            aud = t.get("audience") or {}
            if not aud.get("comments"):
                continue
            ex = (aud.get("examples") or [None])[0]
            out.append({"n": b["n"], "name": t["name"], "comments": aud["comments"],
                        "counts": aud.get("counts"), "call": aud.get("call"),
                        "example": ({"i": ex["i"], "quote": ex["quote"]} if ex else None)})
    return out


def compute_sweep_facts(record: dict, bundles: list[dict]) -> dict:
    """The whole deterministic layer for one sweep, in one JSON-safe dict."""
    rows = [video_row(b) for b in bundles]
    analysed = [r for r in rows if r.get("analysed")]
    audience_counts = {v: 0 for v in F.VALENCES}
    for r in analysed:
        for v in F.VALENCES:
            audience_counts[v] += int((r["audience"].get("counts") or {}).get(v, 0) or 0)
    return {
        "subject": {"subject": record.get("subject", ""), "kind": record.get("subject_kind", ""),
                    "window": record.get("window", ""), "offset_days": record.get("offset_days", 0)},
        "videos": rows,
        "set": {
            "selected": len(rows), "analysed": len(analysed), "failed": len(rows) - len(analysed),
            "reviewer_calls": {c: sum(1 for r in analysed if r["reviewer"]["call"] == c) for c in CALLS},
            "audience_calls": {c: sum(1 for r in analysed if r["audience"]["call"] == c) for c in CALLS},
            "agreement_calls": {c: sum(1 for r in analysed if r["agreement"]["call"] == c)
                                for c in AGREEMENT_CALLS},
            "reviewer_consensus": consensus([r["reviewer"]["call"] for r in analysed]),
            "audience_consensus": consensus([r["audience"]["call"] for r in analysed]),
            "agreement_consensus": consensus([r["agreement"]["call"] for r in analysed]),
            "reviewer_range": _range([r["reviewer"]["lean"] for r in analysed if r["reviewer"]["lean"] is not None]),
            "audience_range": _range([r["audience"]["lean"] for r in analysed if r["audience"]["lean"] is not None]),
            "near_ties": [r["n"] for r in analysed if (r.get("near_tie") or {}).get("near_tie")],
            "written": {s: sum(1 for r in analysed if r["written"] == s)
                        for s in ("complete", "partial", "stale", "facts-only")},
        },
        "audience": {"counts": audience_counts, "comments": sum(audience_counts.values())},
        "questions": questions_across(bundles),
        "about_reviewers": about_reviewers(bundles),
        "odd_one_out": odd_one_out(rows),
        "coverage": set_coverage(rows),
        "signs": set_signs(rows),
        "scores": {"authenticity": (record.get("summary") or {}).get("authenticity"),
                   "brand_health": (record.get("summary") or {}).get("brand_health")},
        "rules": RULES,
    }


# ── themes across the videos ─────────────────────────────────────────────────

def cell_stance(stances: dict) -> str:
    """One video's stance on a theme, from its claims' stances."""
    praise, crit = stances.get("praise", 0), stances.get("criticism", 0)
    mixed, neutral = stances.get("mixed", 0), stances.get("neutral", 0)
    if praise > crit:
        return "praise"
    if crit > praise:
        return "criticism"
    if praise or mixed:
        return "mixed"
    if neutral:
        return "neutral"
    return "silent"


def row_label(talked: int, a: int, b: int) -> tuple[str, str | None]:
    """RULES['theme'] over one row: (label, the side it leans to or None)."""
    polar = a + b
    if polar == 0:
        return ("neutral" if talked >= 2 else "too_few"), None
    if polar < 2:
        return "too_few", None
    side = "first" if a > b else "second" if b > a else None
    if min(a, b) == 0:
        return "agreed", side
    if min(a, b) == 1 and max(a, b) >= CONSENSUS_MIN:
        return "mostly", side
    return "split", None


def _pick_quote(claims: list[dict], stance: str) -> dict | None:
    want = {"praise": ("praise",), "criticism": ("criticism",), "mixed": ("mixed", "praise", "criticism"),
            "neutral": ("neutral",)}.get(stance, ())
    for kind in want:
        pool = sorted((c for c in claims if c.get("stance") == kind), key=lambda c: (c.get("start") or 0.0))
        if pool:
            c = pool[0]
            return {k: c.get(k) for k in ("seg", "seg_end", "time", "quote", "claim", "stance") if k in c}
    return None


def theme_cell(bundle: dict, topic_ids: list[str]) -> dict:
    """One video's reading of one theme, rebuilt from its own claims and comment tags."""
    reading = (bundle.get("analysis") or {}).get("reading") or {}
    comments = (bundle.get("report") or {}).get("all_comments") or []
    topics = {t["id"]: t for t in reading.get("topics") or []}
    chosen = [topics[t] for t in topic_ids if t in topics]
    names = {t["name"] for t in chosen}
    claims = [c for c in reading.get("claims") or [] if c.get("topic") in set(topic_ids)]
    stances = Counter(c.get("stance") for c in claims)
    stance = cell_stance(stances)
    seconds = {v: 0.0 for v in F.VALENCES}
    for t in chosen:
        for v, x in ((t.get("reviewer") or {}).get("seconds") or {}).items():
            if v in seconds:
                seconds[v] += float(x or 0.0)
    tagged = sorted(int(i) for i, ns in (reading.get("comment_tags") or {}).items()
                    if str(i).isdigit() and int(i) < len(comments) and any(x in names for x in ns or []))
    counts = {v: 0 for v in F.VALENCES}
    values = []
    for i in tagged:
        v = F._to_valence((comments[i] or {}).get("label"))
        if v:
            counts[v] += 1
            values.append(F.VALUE[v])
    lean = F.lean_of(values)
    examples = [ex for t in chosen for ex in (t.get("audience") or {}).get("examples") or []
                if ex.get("i") in set(tagged)]
    examples.sort(key=lambda ex: (-(ex.get("likes") if isinstance(ex.get("likes"), int) else -1), ex["i"]))
    call = F.lean_call(lean)
    return {
        "n": bundle["n"], "topics": [t["id"] for t in chosen], "stance": stance,
        "claims": {s: stances.get(s, 0) for s in ("praise", "criticism", "mixed", "neutral")},
        "seconds": {v: round(x, 2) for v, x in seconds.items()},
        "quote": _pick_quote(claims, stance),
        "audience": {"comments": len(tagged), "counts": counts,
                     "lean": lean["lean"] if lean else None, "se": lean["se"] if lean else None,
                     "call": call,
                     "example": ({"i": examples[0]["i"], "quote": examples[0]["quote"],
                                  "label": examples[0].get("label")} if examples else None)},
        "pushback": ((stance == "praise" and call == "negative")
                     or (stance == "criticism" and call == "positive")),
    }


def theme_matrix(themes: list[dict], bundles: list[dict]) -> list[dict]:
    """
    Themes by videos. `themes` is [{"id": "H0", "name": ..., "refs": ["V1T0", ...]}],
    the grouping P5 produced and verified. A video with no written report of its
    own has no topics, and its cell says so rather than reading as silent.
    """
    by_n = {b["n"]: b for b in bundles if b.get("report")}
    out = []
    for theme in themes:
        mine: dict[int, list[str]] = {}
        for ref in theme.get("refs") or []:
            m = re.fullmatch(r"V(\d+)(T\d+)", str(ref))
            if m:
                mine.setdefault(int(m.group(1)), []).append(m.group(2))
        cells, aspects = [], set()
        for n, b in sorted(by_n.items()):
            written = b.get("analysis") and not b.get("stale") and (b["analysis"].get("reading") or {}).get("topics")
            if not written:
                cells.append({"n": n, "status": "not_written"})
                continue
            cell = theme_cell(b, mine.get(n, []))
            cells.append(cell)
            for t in (b["analysis"]["reading"]["topics"]):
                if t["id"] in mine.get(n, []):
                    aspects.update(t.get("aspects") or [])
        read = [c for c in cells if c.get("status") != "not_written"]
        talked = sum(1 for c in read if c["stance"] != "silent")
        praise = sum(1 for c in read if c["stance"] == "praise")
        crit = sum(1 for c in read if c["stance"] == "criticism")
        label, side = row_label(talked, praise, crit)
        a_talked = sum(1 for c in read if c["audience"]["comments"])
        a_pos = sum(1 for c in read if c["audience"]["call"] == "positive")
        a_neg = sum(1 for c in read if c["audience"]["call"] == "negative")
        a_label, a_side = row_label(a_talked, a_pos, a_neg)
        odd = None
        if label == "mostly":
            minority = "criticism" if side == "first" else "praise"
            odd = next(({"n": c["n"], "stance": minority} for c in read if c["stance"] == minority), None)
        out.append({
            "id": theme.get("id"), "name": theme["name"], "refs": list(theme.get("refs") or []),
            "aspects": sorted(aspects), "cells": cells,
            "reviewer": {"talked": talked, "praise_in": praise, "criticism_in": crit,
                         "mixed_in": sum(1 for c in read if c["stance"] == "mixed"),
                         "neutral_in": sum(1 for c in read if c["stance"] == "neutral"),
                         "label": label,
                         "side": {"first": "praise", "second": "criticism"}.get(side)},
            "audience": {"talked": a_talked, "positive_in": a_pos, "negative_in": a_neg,
                         "balanced_in": sum(1 for c in read if c["audience"]["call"] == "balanced"),
                         "comments": sum(c["audience"]["comments"] for c in read),
                         "counts": {v: sum(c["audience"]["counts"][v] for c in read) for v in F.VALENCES},
                         "label": a_label,
                         "side": {"first": "positive", "second": "negative"}.get(a_side)},
            "pushback": [c["n"] for c in read if c["pushback"]],
            "odd": odd,
            "weight": sum(sum(c["claims"].values()) + c["audience"]["comments"] for c in read),
        })
    out.sort(key=lambda r: (-r["reviewer"]["talked"], -r["weight"], r["name"].lower()))
    return out


# ── two periods ──────────────────────────────────────────────────────────────

def _instant(value) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def window_of(record: dict) -> dict:
    """
    The publication window a sweep searched: from `published_after` to
    `published_before`, or, for a window that ran up to the day it was
    searched, to when the sweep finished (the search itself is not timed, so
    the end is approximate by the length of the run, and says so).
    """
    sel = record.get("selection") or {}
    start = _instant(sel.get("published_after"))
    end = _instant(sel.get("published_before"))
    approx = False
    if end is None:
        end = _instant(record.get("finished_at"))
        approx = end is not None
    return {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
            "end_is_run_time": approx, "_start": start, "_end": end}


def windows_overlap(a: dict, b: dict, tolerance_days: float = 1.0) -> dict:
    """Days in common, and whether one window sits inside the other."""
    if not all((a["_start"], a["_end"], b["_start"], b["_end"])):
        return {"known": False, "overlap_days": None, "nested": None, "disjoint": None}
    lo, hi = max(a["_start"], b["_start"]), min(a["_end"], b["_end"])
    days = max(0.0, (hi - lo).total_seconds() / 86400.0)
    tol = tolerance_days * 86400.0

    def inside(x, y):
        return ((x["_start"] - y["_start"]).total_seconds() >= -tol
                and (y["_end"] - x["_end"]).total_seconds() >= -tol)
    return {"known": True, "overlap_days": round(days, 1), "nested": inside(a, b) or inside(b, a),
            "disjoint": days == 0.0}


def _norm_theme(name: str) -> str:
    return re.sub(r"^(?:about\s+)?(?:the\s+)", "", " ".join(str(name or "").casefold().split()))


def align_themes(a: list[dict], b: list[dict]) -> list[tuple[int, int]]:
    """
    Pairs of (index in a, index in b) for themes that mean the same thing:
    the same normalised name, else aspect sets overlapping by Jaccard >= 0.5.
    One-to-one, best overlap first.
    """
    pairs, used_a, used_b = [], set(), set()
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if j not in used_b and i not in used_a and _norm_theme(x["name"]) == _norm_theme(y["name"]):
                pairs.append((i, j))
                used_a.add(i)
                used_b.add(j)
    scored = []
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if i in used_a or j in used_b:
                continue
            sx, sy = set(x.get("aspects") or []), set(y.get("aspects") or [])
            if sx and sy:
                jac = len(sx & sy) / len(sx | sy)
                if jac >= 0.5:
                    scored.append((-jac, i, j))
    for _, i, j in sorted(scored):
        if i not in used_a and j not in used_b:
            pairs.append((i, j))
            used_a.add(i)
            used_b.add(j)
    return sorted(pairs)


MEASURES = (("reviewer", "lean"), ("audience", "lean"), ("authenticity", "score"),
            ("brand_health", "score"))


def _measure(row: dict, key: str):
    if key in ("reviewer", "audience"):
        return row[key].get("lean")
    return (row.get("scores") or {}).get(key)


def period_facts(a_record: dict, a_rows: list[dict], b_record: dict, b_rows: list[dict],
                 a_themes: list[dict] | None = None, b_themes: list[dict] | None = None) -> dict:
    """
    Two sweeps of one subject held against each other. `a` is the book being
    read, `b` the other period. Nothing is refused here that the page does not
    refuse itself; what this adds is what the page could not see: whether the
    windows overlap, which videos are the same, and how much those moved when
    read twice.
    """
    wa, wb = window_of(a_record), window_of(b_record)
    overlap = windows_overlap(wa, wb)
    a_by = {r["video_id"]: r for r in a_rows if r.get("analysed")}
    b_by = {r["video_id"]: r for r in b_rows if r.get("analysed")}
    shared_ids = [v for v in a_by if v in b_by]

    shared = []
    max_delta = {k: None for k, _ in MEASURES}
    unchanged = 0
    for vid in shared_ids:
        ra, rb = a_by[vid], b_by[vid]
        delta = {}
        for key, _ in MEASURES:
            va, vb = _measure(ra, key), _measure(rb, key)
            delta[key] = None if va is None or vb is None else vb - va
            if delta[key] is not None:
                cur = max_delta[key]
                max_delta[key] = abs(delta[key]) if cur is None else max(cur, abs(delta[key]))
        same = (ra["reviewer"]["call"] == rb["reviewer"]["call"]
                and ra["audience"]["call"] == rb["audience"]["call"])
        unchanged += int(same)

        def side(r):
            return {"n": r["n"], "reviewer": r["reviewer"]["lean"], "audience": r["audience"]["lean"],
                    "reviewer_call": r["reviewer"]["call"], "audience_call": r["audience"]["call"],
                    "authenticity": r["scores"].get("authenticity"),
                    "brand_health": r["scores"].get("brand_health"),
                    "label": r["comments"].get("label"), "distribution": r["comments"].get("distribution"),
                    "near_tie": (r.get("near_tie") or {}).get("near_tie", False),
                    "comments": r["comments"].get("read")}
        shared.append({"video_id": vid, "title": ra["title"], "a": side(ra), "b": side(rb),
                       "delta": delta, "calls_same": same,
                       "label_changed": ra["comments"].get("label") != rb["comments"].get("label")})

    measures = []
    for key, kind in MEASURES:
        va = [(r["n"], _measure(r, key), r["video_id"]) for r in a_rows
              if r.get("analysed") and _measure(r, key) is not None]
        vb = [(r["n"], _measure(r, key), r["video_id"]) for r in b_rows
              if r.get("analysed") and _measure(r, key) is not None]
        xa, xb = [v for _, v, _ in va], [v for _, v, _ in vb]
        if len(xa) < 2 or len(xb) < 2:
            call = "too_few"
        elif max(xa) < min(xb) or max(xb) < min(xa):
            call = "moved"
        else:
            call = "within_spread"
        measures.append({"key": key, "kind": kind,
                         "a": [{"n": n, "v": v, "video_id": vid} for n, v, vid in va],
                         "b": [{"n": n, "v": v, "video_id": vid} for n, v, vid in vb],
                         "a_range": _range(xa), "b_range": _range(xb),
                         "change": (_median(xb) - _median(xa)) if xa and xb else None,
                         "call": call, "read_twice": max_delta[key]})

    themes = None
    if a_themes is not None and b_themes is not None:
        pairs = align_themes(a_themes, b_themes)
        ma, mb = {i for i, _ in pairs}, {j for _, j in pairs}
        themes = {
            "matched": [{"a": _theme_brief(a_themes[i]), "b": _theme_brief(b_themes[j])} for i, j in pairs],
            "only_a": [_theme_brief(t) for i, t in enumerate(a_themes) if i not in ma],
            "only_b": [_theme_brief(t) for j, t in enumerate(b_themes) if j not in mb],
        }

    return {
        "a": {"sweep_id": a_record.get("sweep_id"), "window": a_record.get("window"),
              "offset_days": a_record.get("offset_days", 0),
              "dates": {k: v for k, v in wa.items() if not k.startswith("_")},
              "videos": len(a_by), "controller": a_record.get("controller")},
        "b": {"sweep_id": b_record.get("sweep_id"), "window": b_record.get("window"),
              "offset_days": b_record.get("offset_days", 0),
              "dates": {k: v for k, v in wb.items() if not k.startswith("_")},
              "videos": len(b_by), "controller": b_record.get("controller")},
        "overlap": overlap,
        "shared": {"n": len(shared), "videos": shared, "max_delta": max_delta,
                   "calls_unchanged": unchanged},
        "only_a": [{"n": r["n"], "title": r["title"]} for v, r in a_by.items() if v not in b_by],
        "only_b": [{"n": r["n"], "title": r["title"]} for v, r in b_by.items() if v not in a_by],
        "measures": measures,
        "themes": themes,
        "rule": RULES["period"],
    }


def _theme_brief(t: dict) -> dict:
    r = t.get("reviewer") or {}
    return {"id": t.get("id"), "name": t.get("name"), "talked": r.get("talked", 0),
            "praise_in": r.get("praise_in", 0), "criticism_in": r.get("criticism_in", 0),
            "label": r.get("label"), "videos": len(t.get("cells") or [])}
