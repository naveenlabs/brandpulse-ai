"""
candidates.py - the sixteen registered candidates for the transcript bench.

Each entry maps one pre-registered candidate in CANDIDATE_MODELS.md Section 5 to
a callable that turns segment rows into three-class predictions. Nothing here
chooses a winner; that is report_bench.py's job under the rule fixed in Section 3.

Two things are deliberate:

Label order is read from each model's own config, never assumed.
    Verified 31 Aug 2026: cardiffnlp orders its head negative/neutral/positive
    while lxyuan orders it positive/neutral/negative. Assuming a shared order
    would silently invert one of them and the bench would report confident
    nonsense. `_normalise_label` maps whatever the config says onto the three
    canonical names and raises on anything it does not recognise.

Unparseable generative output is recorded, never coerced.
    A model whose reply cannot be read is charged a parse failure and predicts
    nothing. Coercing it to NEUTRAL would inflate this bench's primary metric.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("candidates")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(model_id: str) -> str:
    """Local checkpoints are registered by repo-relative path; the Hub ids are not."""
    local = PROJECT_ROOT / model_id
    return str(local) if local.is_dir() else model_id

LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")
OLLAMA_URL = "http://localhost:11434/api/chat"   # local only - the project's hard constraint

# The incumbent's rule, replicated exactly from pipeline/audio_module.py.
NEUTRAL_CONFIDENCE_THRESHOLD = 0.70

# Maps every label string these models actually emit onto the canonical three.
_LABEL_ALIASES = {
    "POSITIVE": "POSITIVE", "POS": "POSITIVE", "LABEL_2": "POSITIVE",
    "NEGATIVE": "NEGATIVE", "NEG": "NEGATIVE", "LABEL_0": "NEGATIVE",
    "NEUTRAL": "NEUTRAL", "NEU": "NEUTRAL", "LABEL_1": "NEUTRAL",
}


def _normalise_label(raw: str) -> str:
    key = raw.strip().upper()
    if key not in _LABEL_ALIASES:
        raise ValueError(f"unrecognised model label {raw!r}")
    return _LABEL_ALIASES[key]


# ── Shared HF plumbing ────────────────────────────────────────────────────────

_pipes: dict[str, object] = {}


def _get_pipe(model_id: str):
    """Load once, reuse. Same construction as the production pipeline."""
    if model_id not in _pipes:
        from transformers import pipeline as hf_pipeline

        logger.info("loading %s", model_id)
        _pipes[model_id] = hf_pipeline(
            "text-classification",
            model=_resolve(model_id),
            top_k=None,
            truncation=True,
            max_length=512,
        )
    return _pipes[model_id]


def _score_all(model_id: str, texts: list[str]) -> list[dict[str, float]]:
    """Return the full label->score distribution for each text."""
    pipe = _get_pipe(model_id)
    out = []
    for text in texts:
        results = pipe(text)[0]
        out.append({r["label"]: float(r["score"]) for r in results})
    return out


# ── Group 0 - baselines and controls ──────────────────────────────────────────

def run_two_class_with_threshold(
    model_id: str, texts: list[str], threshold: float = NEUTRAL_CONFIDENCE_THRESHOLD
) -> list[dict]:
    """The incumbent construction: a two-class head plus a confidence cut-off.

    Replicates audio_module.add_transcript_sentiment() exactly, including its
    empty-text short circuit and its `confidence = 1 - best` for the manufactured
    NEUTRAL. Used for candidate 0.1 (SST-2), 0.2 (SST-2 swept) and 3.1 (siebert).
    """
    preds = []
    for text, scores in zip(texts, _score_all(model_id, texts)):
        if not text.strip():
            preds.append({"label": "NEUTRAL", "confidence": 1.0, "scores": {}})
            continue
        best_label = max(scores, key=scores.__getitem__)
        best_score = scores[best_label]
        if best_score < threshold:
            label, confidence = "NEUTRAL", 1.0 - best_score
        else:
            label, confidence = _normalise_label(best_label), best_score
        preds.append({"label": label, "confidence": confidence, "scores": scores})
    return preds


def run_vader(texts: list[str]) -> list[dict]:
    """Rule-based floor. Standard compound thresholds from the VADER paper."""
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    analyser = SentimentIntensityAnalyzer()
    preds = []
    for text in texts:
        s = analyser.polarity_scores(text)
        compound = s["compound"]
        if compound >= 0.05:
            label = "POSITIVE"
        elif compound <= -0.05:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"
        preds.append({"label": label, "confidence": abs(compound), "scores": s})
    return preds


# ── Groups 1, 6 - native three-class heads ────────────────────────────────────

def run_three_class(model_id: str, texts: list[str]) -> list[dict]:
    preds = []
    for scores in _score_all(model_id, texts):
        best = max(scores, key=scores.__getitem__)
        preds.append(
            {
                "label": _normalise_label(best),
                "confidence": scores[best],
                "scores": scores,
            }
        )
    return preds


# ── Group 2 - star-rating head ────────────────────────────────────────────────

_STAR_TO_LABEL = {1: "NEGATIVE", 2: "NEGATIVE", 3: "NEUTRAL", 4: "POSITIVE", 5: "POSITIVE"}


def run_star_rating(model_id: str, texts: list[str]) -> list[dict]:
    """nlptown emits '1 star' .. '5 stars'. 3 stars is a principled middle band.

    Collapsing on the argmax star rather than on an expected-value calculation:
    the model's own most-likely rating is the comparable quantity, and an
    expectation would introduce a second free parameter this bench has not
    pre-registered.
    """
    preds = []
    for scores in _score_all(model_id, texts):
        best = max(scores, key=scores.__getitem__)
        stars = int(re.match(r"(\d)", best).group(1))
        preds.append(
            {
                "label": _STAR_TO_LABEL[stars],
                "confidence": scores[best],
                "scores": scores,
                "stars": stars,
            }
        )
    return preds


# ── Group 4 - zero-shot NLI ───────────────────────────────────────────────────

# Fixed in CANDIDATE_MODELS.md Section 8 before any scoring run. Do not tune.
ZEROSHOT_TEMPLATE = "In this sentence, the reviewer is {}."
ZEROSHOT_LABELS = {
    "praising or recommending the product": "POSITIVE",
    "describing the product without giving a verdict": "NEUTRAL",
    "criticising or complaining about the product": "NEGATIVE",
}


def run_zero_shot(model_id: str, texts: list[str]) -> list[dict]:
    from transformers import pipeline as hf_pipeline

    key = f"zs::{model_id}"
    if key not in _pipes:
        logger.info("loading zero-shot %s", model_id)
        _pipes[key] = hf_pipeline("zero-shot-classification", model=_resolve(model_id))
    pipe = _pipes[key]

    hypotheses = list(ZEROSHOT_LABELS)
    preds = []
    for text in texts:
        result = pipe(
            text,
            candidate_labels=hypotheses,
            hypothesis_template=ZEROSHOT_TEMPLATE,
            multi_label=False,
        )
        top = result["labels"][0]
        preds.append(
            {
                "label": ZEROSHOT_LABELS[top],
                "confidence": float(result["scores"][0]),
                "scores": {
                    ZEROSHOT_LABELS[lab]: float(sc)
                    for lab, sc in zip(result["labels"], result["scores"])
                },
            }
        )
    return preds


# ── Group 5 - local generative models ─────────────────────────────────────────

# Fixed in CANDIDATE_MODELS.md Section 8 before any scoring run. Do not tune.
LLM_SYSTEM = (
    "You are a sentiment annotator for spoken product-review transcripts. "
    "Reply with one word only."
)

LLM_USER = """Decide the reviewer's attitude to the product in the SENTENCE below.

POSITIVE - the reviewer praises or recommends the product.
NEGATIVE - the reviewer criticises or complains about the product.
NEUTRAL  - the reviewer describes, explains, asks a question, or makes an
           aside, without giving a verdict. Most narration is NEUTRAL.

Judge only the SENTENCE. The CONTEXT is there to make a fragment readable and
must not be rated.

CONTEXT BEFORE: {context_before}
SENTENCE: {text}
CONTEXT AFTER: {context_after}

Answer with exactly one word: POSITIVE, NEGATIVE, or NEUTRAL."""


def _parse_llm_reply(reply: str) -> str | None:
    """Find the label in a one-word reply, tolerating punctuation and casing.

    Returns None when no single unambiguous label is present. None is a parse
    failure and is counted as such; it is never turned into NEUTRAL.
    """
    found = {lab for lab in LABELS if re.search(rf"\b{lab}\b", reply.upper())}
    return found.pop() if len(found) == 1 else None


def run_ollama(model: str, rows: list[dict], timeout: int = 120) -> list[dict]:
    """Score each row with a locally-resident Ollama model.

    Network calls go to localhost only. A per-row failure is recorded and the run
    continues, matching the pipeline's graceful-degradation rule: one bad segment
    must not abort the experiment.
    """
    import requests

    preds = []
    for i, row in enumerate(rows):
        prompt = LLM_USER.format(
            context_before=row["context_before"] or "(none)",
            text=row["text"],
            context_after=row["context_after"] or "(none)",
        )
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": LLM_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "seed": 42,
                        "num_predict": 8,
                        "top_p": 1.0,
                    },
                },
                timeout=timeout,
            )
            response.raise_for_status()
            reply = response.json()["message"]["content"]
            label = _parse_llm_reply(reply)
        except Exception as exc:
            logger.warning("ollama %s row %d failed: %s", model, i, exc)
            reply, label = "", None

        preds.append(
            {
                "label": label,
                "confidence": None,
                "raw_reply": reply.strip()[:120],
                "parse_failed": label is None,
            }
        )
    return preds


# ── The register ──────────────────────────────────────────────────────────────
#
# `kind` selects the runner; `model` is the identifier it receives.

REGISTRY: list[dict] = [
    # Group 0 - baselines and controls
    {"id": "0.1_sst2_incumbent", "group": 0, "kind": "two_class",
     "model": "distilbert-base-uncased-finetuned-sst-2-english",
     "name": "DistilBERT SST-2 + 0.70 rule (incumbent)"},
    {"id": "0.3_vader", "group": 0, "kind": "vader", "model": None,
     "name": "VADER (rule-based floor)"},

    # Group 1 - native three-class
    {"id": "1.1_cardiffnlp_latest", "group": 1, "kind": "three_class",
     "model": "cardiffnlp/twitter-roberta-base-sentiment-latest",
     "name": "cardiffnlp twitter-roberta latest"},
    {"id": "1.2_cardiffnlp_original", "group": 1, "kind": "three_class",
     "model": "cardiffnlp/twitter-roberta-base-sentiment",
     "name": "cardiffnlp twitter-roberta original"},
    {"id": "1.3_jhartmann_large", "group": 1, "kind": "three_class",
     "model": "j-hartmann/sentiment-roberta-large-english-3-classes",
     "name": "j-hartmann RoBERTa-large 3-class"},
    {"id": "1.4_bertweet", "group": 1, "kind": "three_class",
     "model": "finiteautomata/bertweet-base-sentiment-analysis",
     "name": "BERTweet base sentiment"},
    {"id": "1.5_cardiffnlp_xlm", "group": 1, "kind": "three_class",
     "model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
     "name": "cardiffnlp XLM-RoBERTa multilingual"},
    {"id": "1.6_lxyuan_distil", "group": 1, "kind": "three_class",
     "model": "lxyuan/distilbert-base-multilingual-cased-sentiments-student",
     "name": "lxyuan distilbert multilingual student"},

    # Group 2 - review domain
    {"id": "2.1_nlptown_stars", "group": 2, "kind": "star",
     "model": "nlptown/bert-base-multilingual-uncased-sentiment",
     "name": "nlptown 5-star review model"},

    # Group 3 - two-class control
    {"id": "3.1_siebert_control", "group": 3, "kind": "two_class",
     "model": "siebert/sentiment-roberta-large-english",
     "name": "siebert RoBERTa-large + 0.70 rule (control)"},

    # Group 4 - zero-shot NLI
    {"id": "4.1_deberta_zeroshot", "group": 4, "kind": "zero_shot",
     "model": "MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
     "name": "DeBERTa-v3 zero-shot v2.0"},
    {"id": "4.2_bart_mnli", "group": 4, "kind": "zero_shot",
     "model": "facebook/bart-large-mnli",
     "name": "BART-large MNLI zero-shot"},

    # Group 5 - local generative
    {"id": "5.1_llama32", "group": 5, "kind": "ollama", "model": "llama3.2:latest",
     "name": "llama3.2 (project controller LLM)"},
    {"id": "5.2_gemma3_4b", "group": 5, "kind": "ollama", "model": "gemma3:4b",
     "name": "gemma3:4b"},

    # Group 6 - transfer test
    {"id": "6.1_comment_ft", "group": 6, "kind": "three_class",
     "model": "models/comment_sentiment_ft",
     "name": "our comment-channel fine-tune (transfer)"},
]


def run_candidate(entry: dict, rows: list[dict]) -> list[dict]:
    """Dispatch one registry entry over the labelled rows."""
    texts = [r["text"] for r in rows]
    kind = entry["kind"]
    if kind == "two_class":
        return run_two_class_with_threshold(entry["model"], texts)
    if kind == "vader":
        return run_vader(texts)
    if kind == "three_class":
        return run_three_class(entry["model"], texts)
    if kind == "star":
        return run_star_rating(entry["model"], texts)
    if kind == "zero_shot":
        return run_zero_shot(entry["model"], texts)
    if kind == "ollama":
        return run_ollama(entry["model"], rows)
    raise ValueError(f"unknown candidate kind {kind!r}")
