"""
candidates.py — the controller registry and the one call path they all share.

Fairness in this bench is enforced structurally rather than promised. Every LLM
candidate goes through the same four production functions —
`build_segment_payload`, `_SYSTEM_PROMPT`, `_call_ollama`, `_coerce_result` — and
the ONLY thing that varies between candidates is the string in
`orchestrator.OLLAMA_MODEL`. There is no per-model prompt, no per-model parser and
no per-model retry. A model is credited or penalised for exactly what the deployed
pipeline would make of its answer.

Three properties of the deployed path are worth naming, because they are
deliberately inherited rather than worked around:

  format="json"      Ollama constrains generation to valid JSON. A model that
                     would otherwise emit prose is helped by this, equally, and
                     it is what production does.
  temperature 0      with seed 42. G2 gates on the determinism this is supposed
                     to buy; PROTOTYPE_FINDINGS.md §5 is why it is a gate.
  never raises       `_coerce_result` maps a malformed answer onto a 0.0 score
                     rather than an exception, so an unparseable response is
                     scored as the pipeline would score it: as no conflict.

The three non-LLM references (`rule_baseline`, `always_zero`, `always_flag`) skip
Ollama but land in the same result dict, so they are scored by the same code.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import reference as R  # noqa: E402
from pipeline import orchestrator as O  # noqa: E402

# ── The registry ──────────────────────────────────────────────────────────────
#
# `tag` is the exact Ollama identifier, pinned. `params` and `licence` are filled
# from `ollama show` at run time (probe_registry.py) rather than typed from
# memory: verify, do not remember.

LLM_CANDIDATES = {
    "llama3.2":      {"tag": "llama3.2:latest",     "note": "incumbent"},
    "llama3.1_8b":   {"tag": "llama3.1:8b",         "note": "same family, 2.5x params"},
    "qwen2.5_7b":    {"tag": "qwen2.5:7b-instruct", "note": "instruct, structured output"},
    "qwen3_8b":      {"tag": "qwen3:8b",            "note": "newer generation"},
    "mistral_7b":    {"tag": "mistral:7b",          "note": "named in the work plan"},
    "gemma3_4b":     {"tag": "gemma3:4b",           "note": "nearest size peer"},
    "phi4_mini":     {"tag": "phi4-mini:latest",    "note": "reasoning-dense size peer"},
    "granite3.3_8b": {"tag": "granite3.3:8b",       "note": "enterprise structured output"},
}

REFERENCE_CANDIDATES = ("rule_baseline", "always_zero", "always_flag")

ALL_CANDIDATES = tuple(LLM_CANDIDATES) + REFERENCE_CANDIDATES

# Excluded, with the reason, so the write-up quotes this table rather than prose.
# `constraint` exclusions are not quality judgements and are never reported as
# such (PROTOCOL.md §3.3, §9.2).
EXCLUSIONS = {
    "gpt-oss:20b-cloud":      ("constraint", "proxied to ollama.com; the project's hard constraint forbids any "
                                             "pipeline call leaving the machine"),
    "deepseek-v3.1:671b-cloud": ("constraint", "proxied to ollama.com; same hard constraint"),
    "qwen3-coder:480b-cloud": ("constraint", "proxied to ollama.com; same hard constraint"),
    "qwen3-coder:30b":        ("measured", "18.6 GB against 16 GB unified memory, and "
                                           "code-tuned rather than instruction-tuned; "
                                           "throughput measured in G4 before exclusion"),
}


def is_reference(name: str) -> bool:
    return name in REFERENCE_CANDIDATES


# ── The shared call path ──────────────────────────────────────────────────────

def _predict_reference(name: str, probe: dict) -> dict:
    if name == "rule_baseline":
        return R.rule_baseline(probe["spec"])
    if name == "always_zero":
        return R.constant_baseline(0.0)(probe["spec"])
    if name == "always_flag":
        return R.constant_baseline(1.0)(probe["spec"])
    raise KeyError(name)


def run_probe(name: str, probe: dict, system_prompt: str | None = None) -> dict:
    """Run one candidate on one probe. Never raises.

    Returns
    -------
    {
      "probe_id":       str,
      "raw":            dict | None,   # the model's own JSON, unmodified
      "parsed":         bool,          # did valid JSON come back
      "conflict_score": float,         # after _coerce_result, damping disabled
      "channels":       list[str],     # the model's channels_in_conflict, raw
      "flags":          list[str],
      "narrative":      str,
      "latency_s":      float,
      "error":          str | None,
    }

    `conflict_score` is taken from the production `_coerce_result` and not from
    the raw JSON, because the production value is the one that reaches the scorer
    and therefore the user. The raw JSON is kept alongside so that any divergence
    between what a model said and what the pipeline made of it stays visible.
    """
    t0 = time.perf_counter()

    if is_reference(name):
        raw = _predict_reference(name, probe)
        coerced = O._coerce_result(raw, probe["segment"], probe["comment_sentiment"])
        return {
            "probe_id": probe["probe_id"], "raw": raw, "parsed": True,
            "conflict_score": coerced["conflict_score"],
            "channels": list(raw.get("channels_in_conflict") or []),
            "flags": list(raw.get("flags") or []),
            "narrative": raw.get("narrative", ""),
            "latency_s": round(time.perf_counter() - t0, 4), "error": None,
        }

    spec = LLM_CANDIDATES[name]
    prev_model, prev_prompt = O.OLLAMA_MODEL, O._SYSTEM_PROMPT
    O.OLLAMA_MODEL = spec["tag"]
    if system_prompt is not None:
        O._SYSTEM_PROMPT = system_prompt
    try:
        payload = O.build_segment_payload(probe["segment"])
        cs = probe["comment_sentiment"] or {}
        payload["video_comment_sentiment"] = (
            f"{cs.get('label', 'UNKNOWN')} ({float(cs.get('confidence', 0.0) or 0.0):.2f})")
        text = O._call_ollama(json.dumps(payload))
    except Exception as exc:
        return {"probe_id": probe["probe_id"], "raw": None, "parsed": False,
                "conflict_score": 0.0, "channels": [], "flags": [], "narrative": "",
                "latency_s": round(time.perf_counter() - t0, 4),
                "error": f"{type(exc).__name__}: {exc}"[:300]}
    finally:
        O.OLLAMA_MODEL, O._SYSTEM_PROMPT = prev_model, prev_prompt

    latency = round(time.perf_counter() - t0, 4)

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("non-object JSON")
    except Exception as exc:
        # Scored exactly as production scores it: a fallback, 0.0, not flagged.
        return {"probe_id": probe["probe_id"], "raw": None, "parsed": False,
                "conflict_score": 0.0, "channels": [], "flags": [], "narrative": "",
                "latency_s": latency, "error": f"unparseable: {exc}"[:300]}

    coerced = O._coerce_result(data, probe["segment"], probe["comment_sentiment"])
    return {
        "probe_id": probe["probe_id"], "raw": data, "parsed": True,
        "conflict_score": coerced["conflict_score"],
        "channels": data.get("channels_in_conflict")
        if isinstance(data.get("channels_in_conflict"), list) else [],
        "flags": data.get("flags") if isinstance(data.get("flags"), list) else [],
        "narrative": str(data.get("narrative", ""))[:2000],
        "latency_s": latency, "error": None,
    }


class DampingDisabled:
    """Context manager that neutralises both channel down-weightings.

    PROTOCOL.md §6: damping is a deliberate post-hoc correction applied AFTER the
    controller answers. Leaving it on would score each model on a number the
    pipeline has already modified, and would systematically advantage models whose
    answers happen to trip the sole-dissenter rule. 1.0 is the identity, so the
    branch still executes and only its arithmetic is removed — the ablation
    isolates the weight, not the surrounding code path.
    """

    def __enter__(self):
        self._v = O.VOCAL_ONLY_CONFLICT_WEIGHT
        self._f = O.FACIAL_ONLY_CONFLICT_WEIGHT
        O.VOCAL_ONLY_CONFLICT_WEIGHT = 1.0
        O.FACIAL_ONLY_CONFLICT_WEIGHT = 1.0
        return self

    def __exit__(self, *exc):
        O.VOCAL_ONLY_CONFLICT_WEIGHT = self._v
        O.FACIAL_ONLY_CONFLICT_WEIGHT = self._f
        return False


def available_tags() -> set[str]:
    """Model tags Ollama currently has locally. Empty set if it is unreachable."""
    import requests
    try:
        r = requests.get(f"{O.OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        return {m["name"] for m in r.json().get("models", [])}
    except Exception:
        return set()


def missing_candidates() -> list[str]:
    """Registry entries Ollama does not have. Checked before a run, not during."""
    have = available_tags()
    return [n for n, s in LLM_CANDIDATES.items() if s["tag"] not in have]
