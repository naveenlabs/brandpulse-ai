#!/usr/bin/env python3
"""
comment_bench/v2/run_models.py

Stage 2 of the v2 comment bench: run all candidate models over the frozen corpus and
store their FULL output distributions, not just the winning label.

Why full distributions
----------------------
The v1 bench stored only the top label and its confidence. That makes two very different
predictions indistinguishable:

    POSITIVE 0.82 / NEUTRAL 0.15 / NEGATIVE 0.03   (model is sure)
    POSITIVE 0.40 / NEUTRAL 0.35 / NEGATIVE 0.25   (model effectively guessed)

Both were recorded as "POSITIVE". Storing the whole distribution lets the analysis stage
ask whether a model is *confidently* wrong (dangerous, the pipeline trusts it) or merely
uncertain (recoverable, we can flag it), without re-running inference.

Two further values are captured that cannot be reconstructed later:

  * tabularisai's raw 5-class probabilities, before the project's 5->3 collapse. The
    collapse rule in pipeline/comment_module.py has never been tested; keeping the raw
    output lets alternative rules be evaluated for free.
  * VADER's signed compound score, before the +/-0.05 threshold. v1 stored abs(compound),
    which discarded the sign and made threshold tuning impossible.

Determinism
-----------
All three models are deterministic forward passes with no sampling, so re-running this
script on the same frozen corpus reproduces the output exactly. Resolved model revisions
are recorded in the output for reproducibility.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/run_models.py
    python research/comment_bench/v2/run_models.py --force      # re-score existing files
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
DEFAULT_CORPUS_DIR = BENCH_DIR / "corpus"
DEFAULT_SCORED_DIR = BENCH_DIR / "scored"

CARDIFF_MODEL_ID = "cardiffnlp/twitter-roberta-base-sentiment-latest"
TABULARISAI_MODEL_ID = "tabularisai/multilingual-sentiment-analysis"

CLASSES = ("NEGATIVE", "NEUTRAL", "POSITIVE")

# cardiffnlp raw label -> project class
CARDIFF_LABEL_MAP = {
    "negative": "NEGATIVE", "neutral": "NEUTRAL", "positive": "POSITIVE",
    "label_0": "NEGATIVE", "label_1": "NEUTRAL", "label_2": "POSITIVE",
}

# tabularisai raw 5-class label -> project class.
# Identical to _LABEL_MAP in pipeline/comment_module.py, kept in sync deliberately.
TABULARISAI_LABEL_MAP = {
    "Very Positive": "POSITIVE",
    "Positive":      "POSITIVE",
    "Neutral":       "NEUTRAL",
    "Negative":      "NEGATIVE",
    "Very Negative": "NEGATIVE",
}

VADER_THRESHOLD = 0.05  # standard published threshold; swept in the analysis stage
MAX_TOKENS = 512
BATCH_SIZE = 32

logger = logging.getLogger("run_models")


# ── Device selection ──────────────────────────────────────────────────────────

def pick_device() -> int | str:
    """Prefer Apple MPS, then CUDA, else CPU. Returns a transformers device argument."""
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return 0
    return -1


# ── Model runners ─────────────────────────────────────────────────────────────

def _resolved_revision(model_id: str) -> str | None:
    """Best-effort resolution of the cached commit hash, for reproducibility."""
    try:
        from transformers import AutoConfig
        cfg = AutoConfig.from_pretrained(model_id)
        return getattr(cfg, "_commit_hash", None)
    except Exception:
        return None


def _hf_distributions(model_id: str, texts: list[str], device) -> list[dict[str, float]]:
    """
    Run a HuggingFace text-classification model and return the full label->probability
    map for every input. Order of the returned list matches `texts`.
    """
    from transformers import pipeline as hf_pipeline

    pipe = hf_pipeline(
        "text-classification",
        model=model_id,
        top_k=None,            # return every class, not just the argmax
        truncation=True,
        max_length=MAX_TOKENS,
        device=device,
        batch_size=BATCH_SIZE,
    )

    out: list[dict[str, float]] = []
    results = pipe(texts)
    for res in results:
        # top_k=None yields a list of {"label": ..., "score": ...} per input
        out.append({entry["label"]: float(entry["score"]) for entry in res})
    return out


def score_cardiffnlp(texts: list[str], device) -> list[dict]:
    dists = _hf_distributions(CARDIFF_MODEL_ID, texts, device)
    scored = []
    for dist in dists:
        probs = {CLASSES[i]: 0.0 for i in range(3)}
        for raw_label, score in dist.items():
            mapped = CARDIFF_LABEL_MAP.get(raw_label.lower())
            if mapped:
                probs[mapped] += score
        label = max(probs, key=probs.get)
        scored.append({"label": label, "probs": {k: round(v, 6) for k, v in probs.items()}})
    return scored


def score_tabularisai(texts: list[str], device) -> list[dict]:
    dists = _hf_distributions(TABULARISAI_MODEL_ID, texts, device)
    scored = []
    for dist in dists:
        raw = {k: round(float(v), 6) for k, v in dist.items()}
        probs = {c: 0.0 for c in CLASSES}
        for raw_label, score in dist.items():
            mapped = TABULARISAI_LABEL_MAP.get(raw_label)
            if mapped is None:
                logger.warning("Unknown tabularisai label %r, ignored.", raw_label)
                continue
            probs[mapped] += score
        label = max(probs, key=probs.get)
        scored.append({
            "label": label,
            "probs": {k: round(v, 6) for k, v in probs.items()},
            "raw_5class": raw,          # cannot be recovered without re-running
        })
    return scored


def score_vader(texts: list[str]) -> list[dict]:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    scored = []
    for text in texts:
        if not text.strip():
            scored.append({
                "label": "NEUTRAL",
                "compound": 0.0,
                "components": {"pos": 0.0, "neu": 1.0, "neg": 0.0},
            })
            continue
        s = analyzer.polarity_scores(text)
        compound = float(s["compound"])
        if compound >= VADER_THRESHOLD:
            label = "POSITIVE"
        elif compound <= -VADER_THRESHOLD:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"
        scored.append({
            "label": label,
            "compound": round(compound, 6),     # SIGNED, unlike v1
            "components": {
                "pos": round(float(s["pos"]), 6),
                "neu": round(float(s["neu"]), 6),
                "neg": round(float(s["neg"]), 6),
            },
        })
    return scored


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Score the frozen v2 corpus with all models.")
    parser.add_argument("--force", action="store_true", help="Re-score videos already present.")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR,
                        help="Frozen corpus directory to read.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_SCORED_DIR,
                        help="Directory to write scored output to.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    corpus_dir, scored_dir = args.corpus_dir, args.out_dir
    corpus_files = sorted(p for p in corpus_dir.glob("*.json") if not p.name.startswith("_"))
    if not corpus_files:
        logger.error("No frozen corpus found in %s. Run fetch_corpus.py first.", corpus_dir)
        return 1

    scored_dir.mkdir(parents=True, exist_ok=True)
    device = pick_device()
    logger.info("Device: %s", device)

    revisions = {
        CARDIFF_MODEL_ID: _resolved_revision(CARDIFF_MODEL_ID),
        TABULARISAI_MODEL_ID: _resolved_revision(TABULARISAI_MODEL_ID),
    }

    grand_total = 0
    timings: dict[str, float] = {}

    for path in corpus_files:
        video = json.loads(path.read_text(encoding="utf-8"))
        vid = video["video_id"]
        out_path = scored_dir / f"{vid}.json"

        if out_path.exists() and not args.force:
            logger.info("SKIP  %s (already scored)", vid)
            continue

        comments = video.get("comments", [])
        if not comments:
            logger.warning("SKIP  %s (no comments in corpus)", vid)
            continue

        texts = [c.get("text", "") or "" for c in comments]
        logger.info("SCORE %s  %d comments  %s",
                    vid, len(texts), (video.get("metadata") or {}).get("title", "")[:45])

        t0 = time.perf_counter()
        cardiff = score_cardiffnlp(texts, device)
        t1 = time.perf_counter()
        tabularisai = score_tabularisai(texts, device)
        t2 = time.perf_counter()
        vader = score_vader(texts)
        t3 = time.perf_counter()

        timings["cardiffnlp"] = timings.get("cardiffnlp", 0.0) + (t1 - t0)
        timings["tabularisai"] = timings.get("tabularisai", 0.0) + (t2 - t1)
        timings["VADER"] = timings.get("VADER", 0.0) + (t3 - t2)

        scored_comments = []
        for comment, c_res, t_res, v_res in zip(comments, cardiff, tabularisai, vader):
            scored_comments.append({
                "comment_id": comment["comment_id"],
                "text": comment["text"],
                "like_count": comment["like_count"],
                "reply_count": comment["reply_count"],
                "published_at": comment["published_at"],
                "models": {
                    "cardiffnlp": c_res,
                    "tabularisai": t_res,
                    "VADER": v_res,
                },
            })

        record = {
            "schema_version": 2,
            "video_id": vid,
            "video_title": (video.get("metadata") or {}).get("title"),
            "corpus_fetched_at": video.get("fetched_at"),
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "models": {
                "cardiffnlp": {"model_id": CARDIFF_MODEL_ID, "revision": revisions[CARDIFF_MODEL_ID]},
                "tabularisai": {"model_id": TABULARISAI_MODEL_ID, "revision": revisions[TABULARISAI_MODEL_ID]},
                "VADER": {"model_id": "vaderSentiment", "threshold": VADER_THRESHOLD},
            },
            "comment_count": len(scored_comments),
            "comments": scored_comments,
        }
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        grand_total += len(scored_comments)
        logger.info("  -> %s", out_path.name)

    logger.info("\n%s", "-" * 78)
    logger.info("Scored %d comments -> %s", grand_total, scored_dir)
    if timings and grand_total:
        logger.info("Inference cost (this run):")
        for model, secs in timings.items():
            logger.info("  %-12s %7.1f s total   %6.1f ms/comment",
                        model, secs, secs / grand_total * 1000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
