#!/usr/bin/env python3
"""
comment_bench/v2/analyse_unlabelled.py

Stage 4a: every analysis that can be done BEFORE human labels exist.

None of these are accuracy claims. Accuracy requires ground truth and is computed in
stage 4b. What can be measured without labels is how the models behave relative to each
other and to the pipeline that consumes them, which turns out to be a great deal:

  1. Corpus-level label distribution per model
  2. Pairwise inter-model agreement (Cohen's kappa)
  3. Video-level verdict under each model - does the brand verdict depend on model choice?
  4. Verdict stability under resampling (bootstrap) at n=100 vs n=500
     -> directly tests the PROTOTYPE_FINDINGS Section 5 root cause
  5. Like-weighted vs unweighted aggregation
  6. Temporal sentiment drift
  7. tabularisai's 5-class -> 3-class collapse: how much information it discards
  8. VADER threshold sensitivity

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/analyse_unlabelled.py
"""

from __future__ import annotations

import json
import logging
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
SCORED_DIR = BENCH_DIR / "scored"
CORPUS_DIR = BENCH_DIR / "corpus"
ANALYSIS_DIR = BENCH_DIR / "analysis"

MODELS = ("cardiffnlp", "tabularisai", "VADER")
CLASSES = ("POSITIVE", "NEUTRAL", "NEGATIVE")
SEED = 42
BOOTSTRAP_B = 2000

logger = logging.getLogger("analyse_unlabelled")


# ── Loading ───────────────────────────────────────────────────────────────────

def load() -> tuple[list[dict], dict[str, dict]]:
    comments: list[dict] = []
    meta: dict[str, dict] = {}
    for path in sorted(p for p in SCORED_DIR.glob("*.json") if not p.name.startswith("_")):
        data = json.loads(path.read_text(encoding="utf-8"))
        vid = data["video_id"]
        meta[vid] = {"title": data.get("video_title"), "n": data["comment_count"]}
        for c in data["comments"]:
            c["video_id"] = vid
            comments.append(c)
    # video publish dates come from the frozen corpus, not the scored files
    for path in sorted(p for p in CORPUS_DIR.glob("*.json") if not p.name.startswith("_")):
        data = json.loads(path.read_text(encoding="utf-8"))
        vid = data["video_id"]
        if vid in meta:
            meta[vid]["published_at"] = (data.get("metadata") or {}).get("published_at")
    return comments, meta


# ── Statistics helpers ────────────────────────────────────────────────────────

def cohens_kappa(a: list[str], b: list[str], classes=CLASSES) -> float:
    """Cohen's kappa for two raters over the same items."""
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum((ca[c] / n) * (cb[c] / n) for c in classes)
    if expected == 1.0:
        return float("nan")
    return (observed - expected) / (1 - expected)


def video_label(labels: list[str]) -> tuple[str, int, float]:
    """
    Replicate pipeline aggregate_video_sentiment(): majority vote, ties to NEUTRAL.

    Returns (label, margin_in_comments, margin_as_fraction).
    """
    counts = Counter({c: 0 for c in CLASSES})
    counts.update(labels)
    ranked = counts.most_common()
    top_label, top_n = ranked[0]
    second_n = ranked[1][1] if len(ranked) > 1 else 0
    if top_n == second_n:
        return "NEUTRAL", 0, 0.0
    total = max(len(labels), 1)
    return top_label, top_n - second_n, (top_n - second_n) / total


def weighted_video_label(labels: list[str], weights: list[float]) -> tuple[str, float]:
    """Majority vote with per-comment weights, ties to NEUTRAL."""
    totals = {c: 0.0 for c in CLASSES}
    for label, w in zip(labels, weights):
        totals[label] = totals.get(label, 0.0) + w
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    if len(ranked) > 1 and math.isclose(ranked[0][1], ranked[1][1]):
        return "NEUTRAL", 0.0
    grand = sum(totals.values()) or 1.0
    return ranked[0][0], (ranked[0][1] - ranked[1][1]) / grand


def bootstrap_flip_rate(labels: list[str], n: int, b: int, rng: random.Random) -> dict:
    """
    Resample `n` labels with replacement `b` times and record how often the resulting
    video-level verdict differs from the verdict on the full set.

    This measures how fragile the video-level label is to small changes in which
    comments happen to be fetched - the exact failure documented in
    PROTOTYPE_FINDINGS.md Section 5.
    """
    if not labels:
        return {"n": n, "flip_rate": None, "verdicts": {}}
    truth, _, _ = video_label(labels)
    verdicts = Counter()
    for _ in range(b):
        sample = [labels[rng.randrange(len(labels))] for _ in range(n)]
        verdicts[video_label(sample)[0]] += 1
    flips = b - verdicts[truth]
    return {
        "n": n,
        "reference_verdict": truth,
        "flip_rate": round(flips / b, 4),
        "verdicts": {k: v for k, v in verdicts.most_common()},
    }


def continuous_score(comment: dict, model: str) -> float:
    """P(positive) - P(negative), a continuous sentiment value in [-1, 1]."""
    if model == "VADER":
        return float(comment["models"]["VADER"]["compound"])
    probs = comment["models"][model]["probs"]
    return float(probs["POSITIVE"]) - float(probs["NEGATIVE"])


# ── Analyses ──────────────────────────────────────────────────────────────────

def analyse(comments: list[dict], meta: dict[str, dict]) -> dict:
    rng = random.Random(SEED)
    by_video: dict[str, list[dict]] = defaultdict(list)
    for c in comments:
        by_video[c["video_id"]].append(c)

    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "bootstrap_iterations": BOOTSTRAP_B,
        "corpus": {"videos": len(by_video), "comments": len(comments)},
    }

    # 1. Corpus-level distribution
    out["label_distribution"] = {}
    for m in MODELS:
        counts = Counter(c["models"][m]["label"] for c in comments)
        total = sum(counts.values())
        out["label_distribution"][m] = {
            c: {"n": counts[c], "pct": round(counts[c] / total * 100, 1)} for c in CLASSES
        }

    # 2. Pairwise inter-model agreement
    out["inter_model_agreement"] = {}
    for i, m1 in enumerate(MODELS):
        for m2 in MODELS[i + 1:]:
            a = [c["models"][m1]["label"] for c in comments]
            b = [c["models"][m2]["label"] for c in comments]
            raw = sum(1 for x, y in zip(a, b) if x == y) / len(a)
            out["inter_model_agreement"][f"{m1} vs {m2}"] = {
                "raw_agreement_pct": round(raw * 100, 1),
                "cohens_kappa": round(cohens_kappa(a, b), 3),
            }
    three = sum(1 for c in comments if len({c["models"][m]["label"] for m in MODELS}) == 1)
    out["inter_model_agreement"]["all_three_agree_pct"] = round(three / len(comments) * 100, 1)

    # 3 + 4 + 5. Per-video verdict, stability, weighting
    out["per_video"] = {}
    verdict_table: dict[str, dict[str, str]] = {}
    for vid, group in sorted(by_video.items()):
        entry: dict = {"title": meta[vid]["title"], "n": len(group), "models": {}}
        verdict_table[vid] = {}
        for m in MODELS:
            labels = [c["models"][m]["label"] for c in group]
            label, margin_n, margin_frac = video_label(labels)
            verdict_table[vid][m] = label

            like_w = [1.0 + math.log1p(c["like_count"]) for c in group]
            like_label, like_margin = weighted_video_label(labels, like_w)

            entry["models"][m] = {
                "verdict": label,
                "margin_comments": margin_n,
                "margin_fraction": round(margin_frac, 4),
                "distribution": {c: labels.count(c) for c in CLASSES},
                "mean_continuous_score": round(
                    statistics.fmean(continuous_score(c, m) for c in group), 4),
                "like_weighted_verdict": like_label,
                "like_weighted_changes_verdict": like_label != label,
                "stability": {
                    "at_n_100": bootstrap_flip_rate(labels, 100, BOOTSTRAP_B, rng),
                    "at_n_500": bootstrap_flip_rate(labels, min(500, len(labels)),
                                                    BOOTSTRAP_B, rng),
                },
            }
        out["per_video"][vid] = entry

    # 3b. Does the brand verdict depend on which model is used?
    disagreeing = [v for v, row in verdict_table.items() if len(set(row.values())) > 1]
    out["verdict_depends_on_model"] = {
        "videos_where_models_disagree_on_verdict": len(disagreeing),
        "videos_total": len(verdict_table),
        "detail": {v: verdict_table[v] for v in sorted(verdict_table)},
    }

    # 6. Temporal drift
    out["temporal_drift"] = {}
    for vid, group in sorted(by_video.items()):
        published = meta[vid].get("published_at")
        if not published:
            continue
        try:
            t0 = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            continue
        aged: list[tuple[float, dict]] = []
        for c in group:
            try:
                t = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            aged.append(((t - t0).total_seconds() / 86400.0, c))
        if len(aged) < 40:
            continue
        aged.sort(key=lambda pair: pair[0])
        q = len(aged) // 4
        quartiles = [aged[0:q], aged[q:2 * q], aged[2 * q:3 * q], aged[3 * q:]]
        out["temporal_drift"][vid] = {
            "title": meta[vid]["title"],
            "days_span": round(aged[-1][0] - aged[0][0], 1),
            "quartiles": [
                {
                    "quartile": i + 1,
                    "n": len(chunk),
                    "median_age_days": round(statistics.median(d for d, _ in chunk), 1),
                    "mean_score_cardiffnlp": round(
                        statistics.fmean(continuous_score(c, "cardiffnlp") for _, c in chunk), 4),
                    "pct_negative_cardiffnlp": round(
                        sum(1 for _, c in chunk
                            if c["models"]["cardiffnlp"]["label"] == "NEGATIVE")
                        / len(chunk) * 100, 1),
                }
                for i, chunk in enumerate(quartiles) if chunk
            ],
        }

    # 7. tabularisai 5-class collapse
    raw_counts = Counter()
    for c in comments:
        raw = c["models"]["tabularisai"]["raw_5class"]
        raw_counts[max(raw, key=raw.get)] += 1
    total = sum(raw_counts.values())
    out["tabularisai_5class"] = {
        "argmax_distribution": {k: {"n": v, "pct": round(v / total * 100, 1)}
                                for k, v in raw_counts.most_common()},
        "note": ("Very Negative and Negative both collapse to NEGATIVE in the pipeline; "
                 "Very Positive and Positive both collapse to POSITIVE. The split shows "
                 "how much intensity information the 5->3 rule discards."),
    }

    # 8. VADER threshold sensitivity
    compounds = [c["models"]["VADER"]["compound"] for c in comments]
    out["vader_threshold_sweep"] = {}
    for thr in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50):
        pos = sum(1 for x in compounds if x >= thr)
        neg = sum(1 for x in compounds if x <= -thr)
        neu = len(compounds) - pos - neg
        out["vader_threshold_sweep"][f"{thr:.2f}"] = {
            "POSITIVE": round(pos / len(compounds) * 100, 1),
            "NEUTRAL": round(neu / len(compounds) * 100, 1),
            "NEGATIVE": round(neg / len(compounds) * 100, 1),
        }
    out["vader_threshold_sweep"]["note"] = (
        "Label share only. Which threshold is BEST cannot be determined without ground "
        "truth; that is computed in stage 4b once labels exist.")

    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    comments, meta = load()
    if not comments:
        logger.error("No scored comments found. Run run_models.py first.")
        return 1
    logger.info("Analysing %d comments across %d videos ...", len(comments), len(meta))

    result = analyse(comments, meta)
    out_path = ANALYSIS_DIR / "unlabelled_analysis.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
