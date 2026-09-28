"""
comment_module.py — Comment / text channel analysis

Pipeline:
  YouTube Data API v3  → fetch top comments (relevance-ordered, paginated)
  cardiffnlp (fine-tuned on 1,000 project-labelled comments) → classify each comment
  aggregate_video_sentiment → video-level 3-class label + confidence

Design notes:
  - Comment sentiment is a VIDEO-LEVEL signal only.  Comments are posted hours or
    days after the video and cannot be aligned to Whisper segments.
  - Author identifiers (authorDisplayName, authorChannelId) are never stored:
    data minimisation requirement.
  - The sentiment model is a HuggingFace classifier, not a generative LLM, so
    it does NOT violate the local-only LLM policy (Ollama).
  - Model choice is evidence-based, not assumed: ten candidates were benchmarked
    against 350 hand-labelled comments on 28 Aug 2026. See
    comment_bench/v2/HUMAN_GROUND_TRUTH_EVALUATION.md.
  - Text is truncated to 512 chars before inference; the model has a 512-subword
    limit and will silently truncate longer inputs at the tokeniser level anyway,
    but explicit truncation keeps behaviour predictable.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from pathlib import Path

from pipeline import youtube_api

logger = logging.getLogger(__name__)

# Module-level import so tests can patch pipeline.comment_module.build
try:
    from googleapiclient.discovery import build
except ImportError:  # googleapiclient not installed (bare test environment)
    build = None  # type: ignore[assignment]

# ── Constants ─────────────────────────────────────────────────────────────────

# Model selection history, all measured on this project's own data:
#
#   28 Aug 2026  Ten-model bench against 350 hand-labelled comments. cardiffnlp scored
#                71.3% (n=300) vs the previous tabularisai model's 55.7%, beating 8 of
#                9 challengers at p < 0.05 (exact McNemar). tabularisai was rejected
#                because it inverted the sign of the video-level verdict that feeds 60%
#                of the Brand Health Score (+21.3 human vs -1.7 predicted), and its
#                22-language capacity is unused on a 99.5% Latin-script corpus.
#                -> comment_bench/v2/HUMAN_GROUND_TRUTH_EVALUATION.md
#
#   30 Aug 2026  cardiffnlp fine-tuned on 1,000 further hand-labelled comments, then
#                validated on two videos it had seen nothing from: 69.3% -> 78.7%
#                (p = 0.0066) and NEGATIVE recall 0.368 -> 0.632, fixing 5 missed
#                complaints and breaking none. Adopted.
#                -> comment_bench/v2/FINETUNE_RESULT.md
#                -> comment_bench/v2/holdout/HOLDOUT_RESULT.md
#
# The fine-tuned weights (499 MB) are not committed; models/install_comment_model.py
# installs them (models/README.md). If the directory is absent the module falls back
# to the public base checkpoint and logs a warning, so a fresh clone still runs - it
# simply runs the weaker model until the weights are installed.
_BASE_MODEL_ID = "cardiffnlp/twitter-roberta-base-sentiment-latest"
_FINETUNED_DIR = Path(__file__).resolve().parent.parent / "models" / "comment_sentiment_ft"


def _resolve_model_id() -> str:
    """Prefer the adopted fine-tuned weights; fall back to the public base checkpoint."""
    if (_FINETUNED_DIR / "config.json").is_file():
        return str(_FINETUNED_DIR)
    logger.warning(
        "Fine-tuned weights not found at %s - falling back to the base model %s. "
        "Comment sentiment will be measurably weaker (78.7%% -> 69.3%% on the held-out "
        "set). Install them with models/install_comment_model.py (models/README.md).",
        _FINETUNED_DIR, _BASE_MODEL_ID,
    )
    return _BASE_MODEL_ID


_MODEL_ID = _resolve_model_id()

# Raw 3-class label → project class. This model emits lowercase labels; older
# revisions of the same checkpoint emit LABEL_0/1/2 in the order negative, neutral,
# positive, so both spellings are accepted and lookup is case-folded.
_LABEL_MAP: dict[str, str] = {
    "negative": "NEGATIVE",
    "neutral":  "NEUTRAL",
    "positive": "POSITIVE",
    "label_0":  "NEGATIVE",
    "label_1":  "NEUTRAL",
    "label_2":  "POSITIVE",
}

# ── Lazy singleton ────────────────────────────────────────────────────────────

_sentiment_pipe = None


def _get_sentiment_pipe():
    global _sentiment_pipe
    if _sentiment_pipe is None:
        from transformers import pipeline
        logger.info("Loading sentiment model: %s …", _MODEL_ID)
        _sentiment_pipe = pipeline(
            task="text-classification",
            model=_MODEL_ID,
            top_k=1,
        )
        logger.info("Sentiment model ready.")
    return _sentiment_pipe


# ── Stage 1: Fetch comments from YouTube Data API v3 ─────────────────────────

def fetch_comments(video_id: str, max_results: int = 100) -> list[dict]:
    """
    Fetch top comments for a YouTube video via the YouTube Data API v3.

    Parameters
    ----------
    video_id    : 11-character YouTube video ID
    max_results : Maximum number of comments to retrieve (default 100)

    Returns
    -------
    List of comment dicts — NO author identifiers (data minimisation):
      [{"comment_id": str, "text": str, "like_count": int, "published_at": str}, ...]

    Raises
    ------
    EnvironmentError                   if YOUTUBE_API_KEY is not set
    youtube_api.YouTubeAPIError        on API-level errors (comments disabled, quota
                                       exceeded, etc.), described without the key
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "YOUTUBE_API_KEY environment variable is not set. "
            "Add it to your .env file."
        )

    if build is None:
        raise ImportError(
            "google-api-python-client is not installed. "
            "Run: pip install google-api-python-client"
        )

    youtube = build("youtube", "v3", developerKey=api_key)

    comments: list[dict] = []
    page_token: str | None = None
    page_size = min(max_results, 100)  # API maximum per request is 100

    logger.info("Fetching up to %d comments for video %s …", max_results, video_id)

    while len(comments) < max_results:
        remaining = max_results - len(comments)
        fetch_size = min(page_size, remaining)

        request_kwargs: dict = dict(
            part="snippet",
            videoId=video_id,
            textFormat="plainText",
            order="relevance",
            maxResults=fetch_size,
        )
        if page_token:
            request_kwargs["pageToken"] = page_token

        response = youtube_api.execute(youtube.commentThreads().list(**request_kwargs))

        items = response.get("items", [])
        if not items:
            break

        for item in items[: max_results - len(comments)]:
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id":   item["id"],
                "text":         snippet.get("textDisplay", ""),
                "like_count":   int(snippet.get("likeCount", 0)),
                "published_at": snippet.get("publishedAt", ""),
                # authorDisplayName and authorChannelId deliberately omitted
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info("fetch_comments: retrieved %d comments.", len(comments))
    return comments


# ── Stage 2: Classify each comment ───────────────────────────────────────────

def classify_comment_sentiment(comments: list[dict]) -> list[dict]:
    """
    Run the adopted comment-sentiment model on each comment.

    The model emits three classes directly, so no collapse is needed:
      positive → POSITIVE
      neutral  → NEUTRAL
      negative → NEGATIVE

    Parameters
    ----------
    comments : Output of fetch_comments()

    Returns
    -------
    Same list with two extra keys per dict:
      {"sentiment_label": str, "sentiment_confidence": float}
    """
    if not comments:
        return []

    pipe = _get_sentiment_pipe()
    results: list[dict] = []

    for comment in comments:
        text = comment.get("text", "").strip()

        if not text:
            results.append({
                **comment,
                "sentiment_label":      "NEUTRAL",
                "sentiment_confidence": 0.0,
            })
            continue

        # 512 characters, well inside RoBERTa's 512-token limit (module docstring)
        truncated = text[:512]

        try:
            output = pipe(truncated)
            # pipeline with top_k=1 returns [[{"label": ..., "score": ...}]]
            top = output[0][0] if output and output[0] else None
        except Exception as exc:
            logger.warning(
                "Sentiment inference failed for comment %s: %s",
                comment.get("comment_id", "?"), exc,
            )
            top = None

        if top is None:
            results.append({
                **comment,
                "sentiment_label":      "NEUTRAL",
                "sentiment_confidence": 0.0,
            })
            continue

        raw_label = top["label"]
        mapped_label = _LABEL_MAP.get(raw_label.lower(), "NEUTRAL")
        if raw_label.lower() not in _LABEL_MAP:
            logger.warning("Unknown sentiment label '%s'; defaulting to NEUTRAL.", raw_label)

        results.append({
            **comment,
            "sentiment_label":      mapped_label,
            "sentiment_confidence": round(float(top["score"]), 4),
        })

    logger.info("classify_comment_sentiment: %d comments classified.", len(results))
    return results


# ── Stage 3: Aggregate to video-level signal ──────────────────────────────────

def aggregate_video_sentiment(classified_comments: list[dict]) -> dict:
    """
    Collapse per-comment sentiment into a single video-level signal.

    Majority label wins; ties resolve to NEUTRAL.
    Mean confidence is computed across ALL comments (not just the majority class).

    Parameters
    ----------
    classified_comments : Output of classify_comment_sentiment()

    Returns
    -------
    {
      "label":         str,   # POSITIVE | NEUTRAL | NEGATIVE
      "confidence":    float, # mean sentiment_confidence across all comments
      "comment_count": int,
      "distribution":  {"POSITIVE": int, "NEUTRAL": int, "NEGATIVE": int},
    }
    """
    if not classified_comments:
        return {
            "label":         "NEUTRAL",
            "confidence":    0.0,
            "comment_count": 0,
            "distribution":  {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
        }

    distribution: dict[str, int] = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    confidences: list[float] = []

    for comment in classified_comments:
        label = comment.get("sentiment_label", "NEUTRAL")
        if label in distribution:
            distribution[label] += 1
        else:
            distribution["NEUTRAL"] += 1
        confidences.append(float(comment.get("sentiment_confidence", 0.0)))

    # Majority vote — detect tie by comparing top two counts
    counts = Counter(distribution)
    top_two = counts.most_common(2)
    if len(top_two) >= 2 and top_two[0][1] == top_two[1][1]:
        majority_label = "NEUTRAL"
    else:
        majority_label = top_two[0][0]

    mean_confidence = round(sum(confidences) / len(confidences), 4)

    result: dict = {
        "label":         majority_label,
        "confidence":    mean_confidence,
        "comment_count": len(classified_comments),
        "distribution":  distribution,
    }

    logger.info(
        "aggregate_video_sentiment: %s (conf=%.2f) from %d comments — dist=%s",
        majority_label, mean_confidence, len(classified_comments), distribution,
    )
    return result
