#!/usr/bin/env python3
"""
comment_bench/run_bench.py — standalone comment-model comparison

Compares 3 sentiment models on real YouTube comments across multiple videos:
  1. tabularisai (current production model — reuses pipeline.comment_module as-is)
  2. VADER (rule-based, fast, no download)
  3. cardiffnlp/twitter-roberta-base-sentiment-latest (transformer, one-time download)

Does NOT touch the real pipeline (app.py / main.py) or modify any production code.
Does NOT download video/audio/frames — comments only, via the existing fetch_comments().

Usage:
    python research/comment_bench/run_bench.py

Reads video URLs from comment_bench/video_urls.txt (one per line, # = comment).

Outputs (all in comment_bench/):
  per_video/<video_id>.json   — summary + disagreement highlights + full per-comment detail
  all_results.json            — every video's full result combined into one file
  friend_rating_sample.csv    — ~120 random comments, blank column for human labels
  accuracy_report.json        — filled in by score_against_ground_truth.py after rating
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

# Run with brandpulse_ai/ as the working directory so `pipeline.*` imports resolve.
sys.path.insert(0, str(Path(__file__).parents[2]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[2] / ".env")

from pipeline.comment_module import fetch_comments, classify_comment_sentiment

try:
    from googleapiclient.discovery import build as _yt_build
except ImportError:
    _yt_build = None

BENCH_DIR = Path(__file__).parent
PER_VIDEO_DIR = BENCH_DIR / "per_video"
PER_VIDEO_DIR.mkdir(exist_ok=True)

_YT_ID_RE = re.compile(r"(?:(?:v=)|(?:youtu\.be/))([A-Za-z0-9_\-]{11})")


def fetch_video_title(video_id: str) -> str | None:
    """One cheap API call to get the real video title, for human-readable filenames."""
    if _yt_build is None:
        return None
    import os
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return None
    try:
        youtube = _yt_build("youtube", "v3", developerKey=api_key)
        response = youtube.videos().list(part="snippet", id=video_id).execute()
        items = response.get("items", [])
        if not items:
            return None
        return items[0]["snippet"]["title"]
    except Exception as exc:
        # The type only: a googleapiclient error's text quotes the request URL,
        # which carries the API key (pipeline/youtube_api.py).
        print(f"  Could not fetch title for {video_id}: {type(exc).__name__}")
        return None


def safe_filename(text: str, max_len: int = 80) -> str:
    """Strip filename-illegal characters, cross-platform, and cap length."""
    cleaned = re.sub(r'[\\/:*?"<>|]+', "", text).strip()
    return cleaned[:max_len].strip()

_CARDIFF_MODEL_ID = "cardiffnlp/twitter-roberta-base-sentiment-latest"

MODELS = ["tabularisai", "VADER", "cardiffnlp"]
_LABEL_KEY = {"tabularisai": "sentiment_label", "VADER": "vader_label", "cardiffnlp": "cardiff_label"}
_CONF_KEY = {"tabularisai": "sentiment_confidence", "VADER": "vader_confidence", "cardiffnlp": "cardiff_confidence"}


def extract_video_id(url: str) -> str | None:
    match = _YT_ID_RE.search(url)
    return match.group(1) if match else None


def read_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


# ── Model 2: VADER ────────────────────────────────────────────────────────────

_vader_analyzer = None


def _get_vader():
    global _vader_analyzer
    if _vader_analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _vader_analyzer = SentimentIntensityAnalyzer()
    return _vader_analyzer


def classify_with_vader(comments: list[dict]) -> list[dict]:
    """Standard VADER thresholds: compound >=0.05 pos, <=-0.05 neg, else neutral."""
    analyzer = _get_vader()
    out = []
    for c in comments:
        text = c.get("text", "").strip()
        if not text:
            out.append({**c, "vader_label": "NEUTRAL", "vader_confidence": 0.0})
            continue
        scores = analyzer.polarity_scores(text)
        compound = scores["compound"]
        if compound >= 0.05:
            label = "POSITIVE"
        elif compound <= -0.05:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"
        out.append({**c, "vader_label": label, "vader_confidence": round(abs(compound), 4)})
    return out


# ── Model 3: cardiffnlp roberta ───────────────────────────────────────────────

_cardiff_pipe = None

_CARDIFF_LABEL_MAP = {
    "negative": "NEGATIVE", "neutral": "NEUTRAL", "positive": "POSITIVE",
    "label_0": "NEGATIVE", "label_1": "NEUTRAL", "label_2": "POSITIVE",
}


def _get_cardiff_pipe():
    global _cardiff_pipe
    if _cardiff_pipe is None:
        from transformers import pipeline as hf_pipeline
        print(f"  Loading {_CARDIFF_MODEL_ID} (one-time download if not cached)...")
        _cardiff_pipe = hf_pipeline(
            "text-classification", model=_CARDIFF_MODEL_ID, top_k=1, truncation=True,
        )
    return _cardiff_pipe


def classify_with_cardiffnlp(comments: list[dict]) -> list[dict]:
    pipe = _get_cardiff_pipe()
    out = []
    for c in comments:
        text = c.get("text", "").strip()[:512]
        if not text:
            out.append({**c, "cardiff_label": "NEUTRAL", "cardiff_confidence": 0.0})
            continue
        try:
            result = pipe(text)
            top = result[0][0] if isinstance(result[0], list) else result[0]
            raw_label = top["label"].lower()
            label = _CARDIFF_LABEL_MAP.get(raw_label, "NEUTRAL")
            conf = round(float(top["score"]), 4)
        except Exception as exc:
            print(f"  cardiffnlp failed on comment {c.get('comment_id', '?')}: {exc}")
            label, conf = "NEUTRAL", 0.0
        out.append({**c, "cardiff_label": label, "cardiff_confidence": conf})
    return out


# ── Analysis layer — this is what makes the output "in-depth" not just labels ──

def build_video_summary(comments: list[dict]) -> dict:
    """Per-video, at-a-glance stats: distribution, agreement, confidence."""
    n = len(comments)
    distribution = {m: {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0} for m in MODELS}
    confidences: dict[str, list[float]] = {m: [] for m in MODELS}

    for c in comments:
        for m in MODELS:
            label = c.get(_LABEL_KEY[m], "NEUTRAL")
            if label in distribution[m]:
                distribution[m][label] += 1
            confidences[m].append(float(c.get(_CONF_KEY[m], 0.0) or 0.0))

    pairs = [("tabularisai", "VADER"), ("tabularisai", "cardiffnlp"), ("VADER", "cardiffnlp")]
    pairwise_agreement = {}
    for a, b in pairs:
        agree = sum(1 for c in comments if c.get(_LABEL_KEY[a]) == c.get(_LABEL_KEY[b]))
        pct = round(agree / n * 100, 1) if n else 0.0
        pairwise_agreement[f"{a}_vs_{b}"] = f"{pct}%"

    all_agree = sum(
        1 for c in comments
        if len({c.get(_LABEL_KEY[m]) for m in MODELS}) == 1
    )
    all_disagree = sum(
        1 for c in comments
        if len({c.get(_LABEL_KEY[m]) for m in MODELS}) == 3
    )

    mean_confidence = {
        m: round(sum(confidences[m]) / len(confidences[m]), 4) if confidences[m] else 0.0
        for m in MODELS
    }

    return {
        "comment_count": n,
        "label_distribution": distribution,
        "pairwise_agreement": pairwise_agreement,
        "all_three_agree_count": all_agree,
        "all_three_agree_pct": round(all_agree / n * 100, 1) if n else 0.0,
        "all_three_disagree_count": all_disagree,
        "all_three_disagree_pct": round(all_disagree / n * 100, 1) if n else 0.0,
        "mean_confidence": mean_confidence,
    }


def build_disagreement_highlights(comments: list[dict], max_examples: int = 10) -> list[dict]:
    """The comments all 3 models disagreed on — good exhibit material for the report."""
    highlights = []
    for c in comments:
        labels = {m: c.get(_LABEL_KEY[m]) for m in MODELS}
        if len(set(labels.values())) == 3:
            highlights.append({
                "comment_id": c.get("comment_id"),
                "text": c.get("text", ""),
                **labels,
            })
    return highlights[:max_examples]


# ── Per-video pipeline ─────────────────────────────────────────────────────────

def find_existing(video_id: str) -> Path | None:
    """
    Match any existing per_video file for this ID, regardless of title prefix.
    Plain substring check, not glob — glob's `[...]` is a character class, not a
    literal bracket, so a glob pattern here would silently match the wrong files.
    """
    marker = f"[{video_id}].json"
    for p in PER_VIDEO_DIR.glob("*.json"):
        if p.name.endswith(marker):
            return p
    return None


def process_video(video_id: str, video_url: str = "") -> dict:
    existing = find_existing(video_id)
    if existing is not None:
        print(f"  {video_id}: already done, skipping (delete {existing.name} to redo)")
        return json.loads(existing.read_text())

    print(f"  {video_id}: looking up video title...")
    title = fetch_video_title(video_id)
    label = f"'{title}'" if title else video_id
    print(f"  {video_id}: {label}")

    print(f"  {video_id}: fetching comments...")
    comments = fetch_comments(video_id, max_results=100)
    print(f"  {video_id}: {len(comments)} comments fetched")

    print(f"  {video_id}: running tabularisai (current production model)...")
    comments = classify_comment_sentiment(comments)

    print(f"  {video_id}: running VADER...")
    comments = classify_with_vader(comments)

    print(f"  {video_id}: running cardiffnlp...")
    comments = classify_with_cardiffnlp(comments)

    summary = build_video_summary(comments)
    highlights = build_disagreement_highlights(comments)

    result = {
        "video_id": video_id,
        "video_title": title,
        "video_url": video_url,
        "summary": summary,
        "disagreement_highlights": highlights,
        "comments": comments,
    }

    # Human-readable filename: "Title Here [videoId].json" — falls back to just the ID
    # if the title lookup failed, so a bad API call never blocks saving results.
    name_part = safe_filename(title) if title else "untitled"
    out_path = PER_VIDEO_DIR / f"{name_part} [{video_id}].json"

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"  {video_id}: {summary['all_three_agree_pct']}% full agreement, "
          f"{summary['all_three_disagree_pct']}% total disagreement -> {out_path.name}")
    return result


def main() -> None:
    urls_path = BENCH_DIR / "video_urls.txt"
    urls = read_urls(urls_path)
    if not urls:
        print(f"No video URLs found in {urls_path}. Add 10-12 real YouTube URLs, one per line.")
        sys.exit(1)

    print(f"Found {len(urls)} video URL(s).\n")

    all_video_results: dict[str, dict] = {}
    for i, url in enumerate(urls, 1):
        video_id = extract_video_id(url)
        if video_id is None:
            print(f"[{i}/{len(urls)}] Could not parse video ID from: {url} — skipping")
            continue
        print(f"[{i}/{len(urls)}] {video_id} ({url})")
        try:
            result = process_video(video_id, video_url=url)
            all_video_results[video_id] = result
        except Exception as exc:
            print(f"  {video_id}: FAILED — {exc}")
        print()

    combined_path = BENCH_DIR / "all_results.json"
    combined_path.write_text(json.dumps(all_video_results, indent=2, ensure_ascii=False))
    total_comments = sum(r["summary"]["comment_count"] for r in all_video_results.values())
    print(f"Combined results -> {combined_path} ({total_comments} comments across {len(all_video_results)} videos)")

    # Friend-rating sample: ~120 random comments, text only, blank human_label column
    all_flat = [
        {"video_id": vid, "comment_id": c.get("comment_id"), "text": c.get("text", "")}
        for vid, result in all_video_results.items()
        for c in result["comments"]
        if c.get("text", "").strip()
    ]
    random.seed(42)  # reproducible sample
    sample_size = min(120, len(all_flat))
    sample = random.sample(all_flat, sample_size)

    sample_path = BENCH_DIR / "friend_rating_sample.csv"
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write("video_id,comment_id,text,human_label(POSITIVE/NEUTRAL/NEGATIVE)\n")
        for row in sample:
            text_escaped = row["text"].replace('"', '""').replace("\n", " ")
            f.write(f'{row["video_id"]},{row["comment_id"]},"{text_escaped}",\n')

    print(f"Friend-rating sample -> {sample_path} ({sample_size} comments, last column left blank)")
    print("\nDone. Next: have your friend fill in the human_label column, then run score_against_ground_truth.py")


if __name__ == "__main__":
    main()
