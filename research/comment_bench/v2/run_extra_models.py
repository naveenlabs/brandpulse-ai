#!/usr/bin/env python3
"""
comment_bench/v2/run_extra_models.py

Stage 2b of the v2 comment bench: score the seven additional candidate models over the
same frozen corpus already used by run_models.py, and store their FULL output
distributions.

Why a separate script
---------------------
run_models.py already produced scored/*.json for cardiffnlp, tabularisai and VADER, and
that output is referenced by analyses already written up. Re-running it to add models
would invalidate nothing but risks disturbing a verified artefact for no benefit. This
script writes to scored_extra/ instead; the analysis stage merges the two.

The seven candidates, and why each is here
------------------------------------------
  j-hartmann/sentiment-roberta-large-english-3-classes
      RoBERTa-large, native 3-class, English-only. The strongest prior candidate: the
      corpus is 99.5% Latin-script, so an English-only model gives up nothing and a
      large model has more capacity than the incumbent base model.

  finiteautomata/bertweet-base-sentiment-analysis
      BERTweet, pre-trained on social-media text specifically. Domain match to YouTube
      comment register (emoji, abbreviation, informal punctuation).

  cardiffnlp/twitter-roberta-base-sentiment
      The ORIGINAL version of the current winner. Included as an ablation: the project
      should be able to show that "-latest" is actually better, not merely newer.

  cardiffnlp/twitter-xlm-roberta-base-sentiment
      The multilingual sibling of the winner, same lab and training recipe. Isolates the
      cost of multilingual capacity on an English corpus.

  lxyuan/distilbert-base-multilingual-cased-sentiments-student
      A distilled student model. Tests whether a small fast model is good enough, which
      matters because the pipeline runs locally.

  nlptown/bert-base-multilingual-uncased-sentiment
      5-star ordinal output. Listed in the project roadmap's original bench table and
      never tested. Requires a 5->3 collapse, same shape of problem as tabularisai.

  siebert/sentiment-roberta-large-english
      TWO-class only, no neutral. Included deliberately as a predicted loser: the project
      already carries a 2-class model with a 0.70 "neutral hack" in the transcript
      channel, and this quantifies what that hack costs on data where a third of the
      items are genuinely neutral.

Determinism
-----------
All models are deterministic forward passes with no sampling. Re-running on the same
frozen corpus reproduces the output exactly. Resolved commit hashes are recorded.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/run_extra_models.py
    python research/comment_bench/v2/run_extra_models.py --force
    python research/comment_bench/v2/run_extra_models.py --limit 40     # smoke test
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
CORPUS_DIR = BENCH_DIR / "corpus"
SCORED_DIR = BENCH_DIR / "scored_extra"

CLASSES = ("NEGATIVE", "NEUTRAL", "POSITIVE")
MAX_TOKENS = 512
BATCH_SIZE = 32

# Threshold used to synthesise a NEUTRAL band for 2-class models. 0.70 is not chosen
# here: it is the value pipeline/comment_module.py's sibling transcript channel already
# uses for DistilBERT SST-2, reused so the comparison reflects the project's real rule.
TWO_CLASS_NEUTRAL_THRESHOLD = 0.70

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_extra_models")


# ── Model specifications ──────────────────────────────────────────────────────
# kind: "map3"  -> native 3-class, raw label mapped directly
#       "stars" -> 5-star ordinal, collapsed 1,2->NEG 3->NEU 4,5->POS
#       "two"   -> 2-class, NEUTRAL synthesised below TWO_CLASS_NEUTRAL_THRESHOLD

MODELS: dict[str, dict] = {
    "j-hartmann": {
        "model_id": "j-hartmann/sentiment-roberta-large-english-3-classes",
        "kind": "map3",
        "map": {"negative": "NEGATIVE", "neutral": "NEUTRAL", "positive": "POSITIVE"},
    },
    "bertweet": {
        "model_id": "finiteautomata/bertweet-base-sentiment-analysis",
        "kind": "map3",
        "map": {"neg": "NEGATIVE", "neu": "NEUTRAL", "pos": "POSITIVE"},
    },
    "cardiffnlp_original": {
        "model_id": "cardiffnlp/twitter-roberta-base-sentiment",
        "kind": "map3",
        # documented order for this checkpoint: 0=negative, 1=neutral, 2=positive
        "map": {"label_0": "NEGATIVE", "label_1": "NEUTRAL", "label_2": "POSITIVE"},
    },
    "cardiffnlp_xlm": {
        "model_id": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
        "kind": "map3",
        "map": {"negative": "NEGATIVE", "neutral": "NEUTRAL", "positive": "POSITIVE"},
    },
    "distilbert_student": {
        "model_id": "lxyuan/distilbert-base-multilingual-cased-sentiments-student",
        "kind": "map3",
        "map": {"negative": "NEGATIVE", "neutral": "NEUTRAL", "positive": "POSITIVE"},
    },
    "nlptown": {
        "model_id": "nlptown/bert-base-multilingual-uncased-sentiment",
        "kind": "stars",
        "map": {
            "1 star": "NEGATIVE", "2 stars": "NEGATIVE",
            "3 stars": "NEUTRAL",
            "4 stars": "POSITIVE", "5 stars": "POSITIVE",
        },
    },
    "siebert": {
        "model_id": "siebert/sentiment-roberta-large-english",
        "kind": "two",
        "map": {"negative": "NEGATIVE", "positive": "POSITIVE"},
    },
}


def _device():
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return 0
    except Exception:
        pass
    return -1


def _resolved_revision(model_id: str) -> str | None:
    try:
        from transformers import AutoConfig
        cfg = AutoConfig.from_pretrained(model_id)
        return getattr(cfg, "_commit_hash", None)
    except Exception:
        return None


# One constructed pipeline per model, reused across all videos. Without this the
# script pays a full model load for every (video, model) pair - 70 loads for a
# 10-video corpus and 7 models, which dominates total runtime.
_PIPELINE_CACHE: dict[str, object] = {}


def _get_pipeline(model_id: str, device):
    if model_id not in _PIPELINE_CACHE:
        from transformers import pipeline as hf_pipeline
        logger.info("loading %s ...", model_id)
        _PIPELINE_CACHE[model_id] = hf_pipeline(
            "text-classification",
            model=model_id,
            top_k=None,
            truncation=True,
            max_length=MAX_TOKENS,
            device=device,
            batch_size=BATCH_SIZE,
        )
    return _PIPELINE_CACHE[model_id]


def _distributions(model_id: str, texts: list[str], device) -> list[dict[str, float]]:
    pipe = _get_pipeline(model_id, device)
    return [{e["label"]: float(e["score"]) for e in res} for res in pipe(texts)]


def score_model(name: str, spec: dict, texts: list[str], device) -> list[dict]:
    """Return one record per input text: mapped label, 3-class probs, and raw output."""
    dists = _distributions(spec["model_id"], texts, device)
    kind, mapping = spec["kind"], spec["map"]
    out: list[dict] = []

    for dist in dists:
        raw = {k: round(float(v), 6) for k, v in dist.items()}
        probs = {c: 0.0 for c in CLASSES}
        for raw_label, score in dist.items():
            mapped = mapping.get(raw_label.lower()) or mapping.get(raw_label)
            if mapped is None:
                logger.warning("[%s] unmapped label %r, ignored", name, raw_label)
                continue
            probs[mapped] += score

        if kind == "two":
            # No neutral class exists. Emit NEUTRAL when the winning class is not
            # confident enough, mirroring the project's existing DistilBERT rule.
            top = max(probs, key=probs.get)
            label = top if probs[top] >= TWO_CLASS_NEUTRAL_THRESHOLD else "NEUTRAL"
        else:
            label = max(probs, key=probs.get)

        rec = {"label": label, "probs": {k: round(v, 6) for k, v in probs.items()}}
        if kind in ("stars", "two"):
            rec["raw"] = raw          # not reconstructable from the collapsed 3-class
        out.append(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-score existing files")
    ap.add_argument("--limit", type=int, default=None, help="score only N comments/video")
    ap.add_argument("--models", default=None, help="comma-separated subset of model keys")
    args = ap.parse_args()

    # "_manifest.json" and any other underscore-prefixed file is bench metadata,
    # not a per-video corpus file.
    corpus_files = sorted(f for f in CORPUS_DIR.glob("*.json") if not f.name.startswith("_"))
    if not corpus_files:
        logger.error("No corpus files in %s. Run fetch_corpus.py first.", CORPUS_DIR)
        return 1

    selected = list(MODELS) if not args.models else [m.strip() for m in args.models.split(",")]
    unknown = [m for m in selected if m not in MODELS]
    if unknown:
        logger.error("Unknown model keys: %s", unknown)
        return 1

    SCORED_DIR.mkdir(parents=True, exist_ok=True)
    device = _device()
    logger.info("Device: %s | models: %s", device, selected)

    revisions = {m: _resolved_revision(MODELS[m]["model_id"]) for m in selected}
    timings: dict[str, float] = {}

    for cf in corpus_files:
        out_path = SCORED_DIR / cf.name
        if out_path.exists() and not args.force:
            logger.info("skip (exists): %s", cf.name)
            continue

        corpus = json.loads(cf.read_text(encoding="utf-8"))
        comments = corpus["comments"][: args.limit] if args.limit else corpus["comments"]
        texts = [c["text"] for c in comments]
        logger.info("%s — %d comments", cf.stem, len(texts))

        per_model: dict[str, list[dict]] = {}
        for name in selected:
            t0 = time.time()
            per_model[name] = score_model(name, MODELS[name], texts, device)
            dt = time.time() - t0
            timings[name] = timings.get(name, 0.0) + dt
            logger.info("   %-22s %6.1fs  (%.1f comments/s)", name, dt, len(texts) / dt)

        record = {
            "schema_version": 1,
            "video_id": corpus["video_id"],
            "video_title": corpus.get("video_title"),
            "corpus_fetched_at": corpus.get("fetched_at"),
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "models": {
                name: {"model_id": MODELS[name]["model_id"],
                       "kind": MODELS[name]["kind"],
                       "revision": revisions[name]}
                for name in selected
            },
            "two_class_neutral_threshold": TWO_CLASS_NEUTRAL_THRESHOLD,
            "comments": [
                {
                    "comment_id": c["comment_id"],
                    "text": c["text"],
                    "models": {name: per_model[name][i] for name in selected},
                }
                for i, c in enumerate(comments)
            ],
        }
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("   -> %s", out_path.name)

    logger.info("Total inference time per model:")
    for name, dt in sorted(timings.items(), key=lambda kv: -kv[1]):
        logger.info("   %-22s %7.1fs", name, dt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
