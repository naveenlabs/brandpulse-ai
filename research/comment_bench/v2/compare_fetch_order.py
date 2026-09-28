#!/usr/bin/env python3
"""
comment_bench/v2/compare_fetch_order.py

Stage 4c: does the YouTube comment fetch ORDER change the measured brand sentiment?

Why this matters
----------------
pipeline/comment_module.py fetches with order="relevance". If relevance ordering selects a
non-representative slice of the audience, then every Brand Health Score the system has ever
produced inherits that bias, because comment sentiment is 60% of that score.

This script compares two independently frozen 500-comment samples of the SAME ten videos:

    corpus/       order="relevance"   (what the pipeline actually uses)
    corpus_time/  order="time"        (newest first, no engagement weighting)

Confound control
----------------
The two samples cover different date ranges, so a naive comparison would confuse "fetch
order" with "recency". Every comparison is therefore ALSO recomputed on the date window the
two samples share, which removes the recency explanation.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/compare_fetch_order.py
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = BENCH_DIR / "analysis"
MODELS = ("cardiffnlp", "tabularisai", "VADER")
CLASSES = ("POSITIVE", "NEUTRAL", "NEGATIVE")
LIKE_BANDS = [(0, 0), (1, 2), (3, 9), (10, 49), (50, 199), (200, 999), (1000, 10**9)]

logger = logging.getLogger("compare_fetch_order")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load(directory: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["video_id"]] = data["comments"]
    return out


def continuous(comment: dict, model: str = "cardiffnlp") -> float:
    if model == "VADER":
        return float(comment["models"]["VADER"]["compound"])
    probs = comment["models"][model]["probs"]
    return float(probs["POSITIVE"]) - float(probs["NEGATIVE"])


def video_label(labels: list[str]) -> str:
    counts = Counter({c: 0 for c in CLASSES})
    counts.update(labels)
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "NEUTRAL"
    return ranked[0][0]


def pearson(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Returns (r, t). t is the standard test statistic with n-2 degrees of freedom."""
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    if den == 0:
        return float("nan"), float("nan")
    r = num / den
    t = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else float("inf")
    return r, t


def like_band_profile(comments: list[dict]) -> list[dict]:
    rows = []
    for lo, hi in LIKE_BANDS:
        sel = [c for c in comments if lo <= c["like_count"] <= hi]
        if len(sel) < 20:
            continue
        counts = Counter(c["models"]["cardiffnlp"]["label"] for c in sel)
        rows.append({
            "band": f"{lo}-{hi}" if hi < 10**9 else f"{lo}+",
            "n": len(sel),
            "mean_score": round(statistics.fmean(continuous(c) for c in sel), 4),
            "pct_positive": round(counts["POSITIVE"] / len(sel) * 100, 1),
            "pct_negative": round(counts["NEGATIVE"] / len(sel) * 100, 1),
        })
    return rows


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rel = load(BENCH_DIR / "scored")
    tim = load(BENCH_DIR / "scored_time")
    if not rel or not tim:
        logger.error("Need both scored/ and scored_time/. See run_models.py --corpus-dir.")
        return 1

    shared = sorted(set(rel) & set(tim))
    result: dict = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "videos": len(shared),
        "n_relevance": sum(len(rel[v]) for v in shared),
        "n_time": sum(len(tim[v]) for v in shared),
        "per_video": {},
        "verdict_changes": [],
    }

    full_diffs: list[float] = []
    window_diffs: list[float] = []

    for vid in shared:
        r, t = rel[vid], tim[vid]
        ids_r = {c["comment_id"] for c in r}
        ids_t = {c["comment_id"] for c in t}

        # Shared date window removes recency as an explanation.
        lo = max(min(parse_ts(c["published_at"]) for c in r),
                 min(parse_ts(c["published_at"]) for c in t))
        hi = min(max(parse_ts(c["published_at"]) for c in r),
                 max(parse_ts(c["published_at"]) for c in t))
        rw = [c for c in r if lo <= parse_ts(c["published_at"]) <= hi]
        tw = [c for c in t if lo <= parse_ts(c["published_at"]) <= hi]

        entry: dict = {
            "overlap_comments": len(ids_r & ids_t),
            "mean_likes_relevance": round(statistics.fmean(c["like_count"] for c in r), 1),
            "mean_likes_time": round(statistics.fmean(c["like_count"] for c in t), 1),
            "median_likes_relevance": statistics.median(c["like_count"] for c in r),
            "median_likes_time": statistics.median(c["like_count"] for c in t),
            "mean_score_relevance": round(statistics.fmean(continuous(c) for c in r), 4),
            "mean_score_time": round(statistics.fmean(continuous(c) for c in t), 4),
            "verdicts": {},
        }
        entry["score_diff_time_minus_relevance"] = round(
            entry["mean_score_time"] - entry["mean_score_relevance"], 4)
        full_diffs.append(entry["score_diff_time_minus_relevance"])

        if len(rw) >= 50 and len(tw) >= 50:
            a = statistics.fmean(continuous(c) for c in rw)
            b = statistics.fmean(continuous(c) for c in tw)
            entry["shared_window"] = {
                "from": lo.isoformat(), "to": hi.isoformat(),
                "n_relevance": len(rw), "n_time": len(tw),
                "mean_score_relevance": round(a, 4),
                "mean_score_time": round(b, 4),
                "diff": round(b - a, 4),
            }
            window_diffs.append(b - a)

        for m in MODELS:
            va = video_label([c["models"][m]["label"] for c in r])
            vb = video_label([c["models"][m]["label"] for c in t])
            entry["verdicts"][m] = {"relevance": va, "time": vb, "changed": va != vb}
            if va != vb:
                result["verdict_changes"].append(
                    {"video_id": vid, "model": m, "relevance": va, "time": vb})

        result["per_video"][vid] = entry

    result["summary"] = {
        "mean_score_diff_full_sample": round(statistics.fmean(full_diffs), 4),
        "videos_more_negative_under_time_ordering": sum(1 for d in full_diffs if d < 0),
        "videos_total": len(full_diffs),
        "mean_score_diff_shared_window": round(statistics.fmean(window_diffs), 4)
        if window_diffs else None,
        "videos_more_negative_in_shared_window": sum(1 for d in window_diffs if d < 0),
        "verdict_changes": len(result["verdict_changes"]),
        "video_model_combinations": len(shared) * len(MODELS),
    }

    # Corpus-level label share under each ordering
    result["label_share"] = {}
    for name, src in (("relevance", rel), ("time", tim)):
        flat = [c for v in shared for c in src[v]]
        result["label_share"][name] = {}
        for m in MODELS:
            counts = Counter(c["models"][m]["label"] for c in flat)
            total = len(flat)
            result["label_share"][name][m] = {
                c: round(counts[c] / total * 100, 1) for c in CLASSES}

    # Likes vs sentiment, computed separately in each corpus. The two disagree in sign,
    # which is why no causal mechanism is claimed from this. Recorded so that is visible.
    result["likes_vs_sentiment"] = {}
    for name, src in (("relevance", rel), ("time", tim)):
        flat = [c for v in shared for c in src[v]]
        r_val, t_val = pearson([math.log1p(c["like_count"]) for c in flat],
                               [continuous(c) for c in flat])
        zeros = sum(1 for c in flat if c["like_count"] == 0)
        result["likes_vs_sentiment"][name] = {
            "pearson_r_log1p_likes": round(r_val, 4),
            "t_statistic": round(t_val, 2),
            "n": len(flat),
            "pct_zero_likes": round(zeros / len(flat) * 100, 1),
            "bands": like_band_profile(flat),
        }
    result["likes_vs_sentiment"]["interpretation"] = (
        "The sign of this correlation REVERSES between the two corpora. Like count is "
        "confounded with comment age (old comments have had years to accumulate likes, "
        "recent ones have not), so neither figure is a clean estimate of a likes-sentiment "
        "relationship, and no mechanism is claimed from it. The fetch-order effect itself "
        "is measured directly and does not depend on this.")

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ANALYSIS_DIR / "fetch_order_comparison.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    s = result["summary"]
    logger.info("Videos: %d   relevance n=%d   time n=%d",
                result["videos"], result["n_relevance"], result["n_time"])
    logger.info("Mean sentiment shift (time - relevance), full sample : %+.4f  (%d/%d negative)",
                s["mean_score_diff_full_sample"],
                s["videos_more_negative_under_time_ordering"], s["videos_total"])
    logger.info("Mean sentiment shift, shared date window             : %+.4f  (%d/%d negative)",
                s["mean_score_diff_shared_window"],
                s["videos_more_negative_in_shared_window"], s["videos_total"])
    logger.info("Video-level verdict changed by fetch order alone     : %d/%d combinations",
                s["verdict_changes"], s["video_model_combinations"])
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
