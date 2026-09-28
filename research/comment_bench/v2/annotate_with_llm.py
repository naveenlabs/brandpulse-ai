#!/usr/bin/env python3
"""
comment_bench/v2/annotate_with_llm.py

Stage 4d: annotate the corpus with the project's own local LLM (Ollama / llama3.2).

What this is, and what it is NOT
--------------------------------
This produces a REFERENCE ANNOTATION, not ground truth. llama3.2 is a language model
judging text, the same category of thing as the models under test. Agreement with it is
therefore not accuracy and must never be reported as such.

Its value is established only once human labels exist: if llama3.2 agrees with the human
raters at a high kappa, its full-corpus annotation becomes a usable proxy for the ~4,500
comments no human will ever label. If agreement is poor, that is itself a reportable
result about LLM-as-annotator, and the annotation is discarded.

Why the local model rather than a cloud one
-------------------------------------------
Project rule (README, "Engineering rules"): the LLM is local-only, http://localhost:11434. No pipeline data
leaves the machine. Using llama3.2 also means the annotator is the SAME model that already
acts as the orchestration controller, which makes the result directly relevant to the
project's own architecture rather than a detached side experiment.

Determinism
-----------
temperature 0, seed 42, pinned model tag. Resumable: existing results are reloaded and only
missing comments are sent, so an interrupted run costs nothing.

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/annotate_with_llm.py                  # full corpus
    python research/comment_bench/v2/annotate_with_llm.py --limit 40       # quick trial
    python research/comment_bench/v2/annotate_with_llm.py --model gemma3:4b
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import urllib.error
import urllib.request

BENCH_DIR = Path(__file__).resolve().parent
SCORED_DIR = BENCH_DIR / "scored"
OUT_DIR = BENCH_DIR / "analysis"

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"
VALID = {"POSITIVE", "NEUTRAL", "NEGATIVE"}
MAX_CHARS = 1200
REQUEST_TIMEOUT = 60

# Mirrors labels/GUIDELINES.md so the LLM is judged against the same rubric as the humans.
SYSTEM_RULES = """You label YouTube comment sentiment for a brand-monitoring system.

Reply with EXACTLY ONE WORD: POSITIVE, NEUTRAL, or NEGATIVE. No punctuation, no explanation.

Rules:
1. Judge the commenter's attitude toward the product or the video. Not their mood, not
   whether they are polite.
2. Praise for the video or the creator counts as POSITIVE.
3. A plain question asking for information is NEUTRAL, even if it sounds keen.
4. If a comment mixes praise and criticism, pick the side the commenter lands on. Use
   NEUTRAL only if genuinely balanced.
5. Label sarcasm by its intended meaning, not its literal words.
6. Complaints about YouTube itself, such as ads, are NEGATIVE.
7. Jokes with no evaluation in them are NEUTRAL.
8. If a commenter prefers a competitor over the reviewed product, that is NEGATIVE.
9. If you genuinely cannot decide, answer NEUTRAL."""


logger = logging.getLogger("annotate_with_llm")


def call_ollama(text: str, model: str) -> tuple[str | None, str | None]:
    """
    Ask the local model for one label. Returns (label, error).

    Never raises: an unreachable Ollama, a timeout, or an unparseable reply all return
    (None, reason) so a single bad comment cannot abort a multi-thousand-comment run.
    """
    payload = {
        "model": model,
        "prompt": f"{SYSTEM_RULES}\n\nComment:\n\"\"\"\n{text[:MAX_CHARS]}\n\"\"\"\n\nLabel:",
        "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_predict": 5},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return None, f"unreachable: {exc.reason}"
    except TimeoutError:
        return None, "timeout"
    except Exception as exc:
        return None, f"error: {exc}"

    raw = (body.get("response") or "").strip().upper()
    for candidate in VALID:
        if candidate in raw:
            return candidate, None
    return None, f"unparseable: {raw[:40]!r}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Annotate the corpus with a local LLM.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="Annotate only the first N (trial).")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    comments: list[dict] = []
    for path in sorted(p for p in SCORED_DIR.glob("*.json") if not p.name.startswith("_")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for c in data["comments"]:
            comments.append({"comment_id": c["comment_id"], "video_id": data["video_id"],
                             "text": c["text"]})
    if args.limit:
        comments = comments[: args.limit]
    if not comments:
        logger.error("No scored comments found. Run run_models.py first.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = args.model.replace(":", "_").replace("/", "_")
    out_path = args.out or (OUT_DIR / f"llm_annotation_{tag}.json")

    # Resume: reload anything already annotated so an interrupted run costs nothing.
    done: dict[str, str] = {}
    if out_path.exists():
        prior = json.loads(out_path.read_text(encoding="utf-8"))
        done = {k: v for k, v in prior.get("labels", {}).items() if v in VALID}
        logger.info("Resuming: %d already annotated.", len(done))

    todo = [c for c in comments if c["comment_id"] not in done]
    logger.info("Model %s | %d to annotate (%d total, %d done)",
                args.model, len(todo), len(comments), len(done))

    failures: dict[str, str] = {}
    started = time.perf_counter()

    for i, comment in enumerate(todo, start=1):
        label, error = call_ollama(comment["text"], args.model)
        if label is None:
            failures[comment["comment_id"]] = error or "unknown"
            if error and error.startswith("unreachable"):
                logger.error("Ollama unreachable (%s). Stopping; progress is saved.", error)
                break
        else:
            done[comment["comment_id"]] = label

        if i % 100 == 0 or i == len(todo):
            rate = i / (time.perf_counter() - started)
            remaining = (len(todo) - i) / rate if rate else 0
            logger.info("  %d/%d  %.1f/s  ~%.0f min left  failures=%d",
                        i, len(todo), rate, remaining / 60, len(failures))
            _save(out_path, args.model, done, failures, comments)

    _save(out_path, args.model, done, failures, comments)
    elapsed = time.perf_counter() - started
    logger.info("Done. %d labelled, %d failed, %.1f min, %.1f ms/comment.",
                len(done), len(failures), elapsed / 60,
                elapsed / max(len(todo), 1) * 1000)
    logger.info("Wrote %s", out_path)
    return 0


def _save(path: Path, model: str, labels: dict, failures: dict, comments: list[dict]) -> None:
    path.write_text(json.dumps({
        "model": model,
        "annotator_type": "local_llm",
        "is_ground_truth": False,
        "note": ("Reference annotation only. This is a language model judging text and its "
                 "agreement with the models under test is NOT accuracy. Validate against "
                 "human labels before relying on it."),
        "options": {"temperature": 0, "seed": 42},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_size": len(comments),
        "labelled": len(labels),
        "failed": len(failures),
        "labels": labels,
        "failures": failures,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
