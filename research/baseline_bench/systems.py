"""
systems.py — the candidates PROTOCOL.md §3 compares, and the probes they score.

Six systems, all emitting **one score per segment in [0, 1] where higher means
less authentic**, so all six go through an identical scoring path in
`report_bench.py`. PROTOCOL.md §6 correlates human `h(s)` against `-c(s)`.

| id | what it is | channels | LLM |
|---|---|---|---|
| `four_channel` | the deployed pipeline, facial populated | T, V, F, C | yes |
| `three_channel` | the pipeline **as it actually ran** on this corpus | T, V, C | yes |
| `text_only_llm` | the baseline that threatens the design | transcript text | yes |
| `transcript_label_pos_genuine` | naive reference (Amendment A1) | T label | no |
| `transcript_label_neg_genuine` | its inverse (Amendment A1) | T label | no |
| `constant` | degenerate reference, must score rho = 0.000 | none | no |

## The three LLM systems call the production code, they do not re-implement it

`four_channel` and `three_channel` build a real enriched segment dict and hand it
to `pipeline.orchestrator.build_segment_payload` and
`pipeline.orchestrator._coerce_result` — the same functions `app.py` runs. A
bench that reimplemented the payload or the damping would be measuring the
reimplementation, and the first thing to drift would be the thing under test.
The deployed `_SYSTEM_PROMPT` is used verbatim.

## Channel values are byte-identical to controller_bench

PROTOCOL.md §4.1: transcript sentiment, vocal emotion and comments come from
`vocal_bench/ab_cache/`; §4.2: facial comes from
`facial_bench/v2/ab_cache_facial/`. Nothing is re-transcribed, no sentiment is
recomputed, no comment is re-fetched and DeepFace is not re-run.

`pitch_mean` and `energy_mean` are absent from those caches and therefore default
to 0.0 in the payload, exactly as they did in `controller_bench.corpus_probes`.
That is a property of the cached corpus, not a choice made here, and it is
identical across all three LLM systems so it cannot favour any of them.

## Why `text_only_llm` is coerced on a stripped segment (Amendment A4)

PROTOCOL.md §3.1 requires the "same parsing and coercion path". `_coerce_result`
damps a conflict that rests on one weak channel alone, and it decides that from
**the segment's own channel labels** — not from the LLM's output. Handing it the
full segment would let the text-only baseline be adjusted using vocal and facial
readings it never saw, which is multi-channel information leaking into the
single-channel control.

So `text_only_llm` runs the *same function* on *its own* inputs: a segment
carrying `segment_id`, `start_time`, `end_time` and `text`, and no comment
channel. `_channel_valences` then returns `{}`, both sole-dissenter predicates
return False, and no damping can fire. This is asserted in
`tests/test_baseline_systems.py` rather than assumed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from pipeline import orchestrator as O  # noqa: E402

AB = PROJECT / "research" / "vocal_bench" / "ab_cache"
CORPUS = PROJECT / "research" / "transcript_bench" / "corpus"
FACIAL = PROJECT / "research" / "facial_bench" / "v2" / "ab_cache_facial"
SAMPLE = BENCH / "sample.json"

LLM_SYSTEMS = ("four_channel", "three_channel", "text_only_llm",
               "text_only_llm_anchored")
RULE_SYSTEMS = ("transcript_label_pos_genuine", "transcript_label_neg_genuine",
                "constant")
ALL_SYSTEMS = LLM_SYSTEMS + RULE_SYSTEMS


# ── Probes ────────────────────────────────────────────────────────────────────

def build_probes() -> list[dict]:
    """The 120 sampled segments, rebuilt with every cached channel attached.

    Mirrors `controller_bench.run_bench.corpus_probes` deliberately rather than
    importing it: that function hardcodes `facial_emotion: "none detected"`,
    which was true when it was written (no frames existed for these videos) and
    is the very thing PROTOCOL.md §4.2 changes here. Importing it and patching
    the facial field afterwards would leave the bench one refactor away from
    silently reverting to a three-channel run.
    """
    sample = json.loads(SAMPLE.read_text())
    wanted = {(it["video_id"], str(it["segment_id"])): it
              for it in sample["items"]}

    by_video: dict[str, list] = {}
    for (vid, _sid), it in wanted.items():
        by_video.setdefault(vid, []).append(it)

    probes = []
    for vid, its in sorted(by_video.items()):
        ts = json.loads((AB / "transcript" / f"{vid}.json").read_text())
        ve = json.loads((AB / "vocal_audeering" / f"{vid}.json").read_text())
        cs = json.loads((AB / "comments" / f"{vid}.json").read_text())
        fac = json.loads((FACIAL / f"{vid}.json").read_text())["facial"]
        doc = {str(s["segment_id"]): s
               for s in json.loads((CORPUS / f"{vid}.json").read_text())["segments"]}

        for it in sorted(its, key=lambda x: x["segment_id"]):
            key = str(it["segment_id"])
            s = doc[key]
            facial = fac.get(key) or {"dominant": None, "confidence": 0.0,
                                      "frame_count": 0,
                                      "reliability": O.FACIAL_ONLY_CONFLICT_WEIGHT}
            probes.append({
                "uid": it["uid"],
                "video_id": vid,
                "segment_id": it["segment_id"],
                "split": it["split"],
                "channel": it["channel"],
                "text": s["text"],
                "segment": {
                    "segment_id": s["segment_id"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "text": s["text"],
                    "transcript_sentiment": ts[key],
                    "vocal_emotion": ve[key],
                    "facial_emotion": facial,
                },
                "comment_sentiment": cs,
                "spec": {
                    "transcript_sentiment": (ts[key] or {}).get("label"),
                    "vocal_emotion": (ve[key] or {}).get("label"),
                    "facial_emotion": facial.get("dominant"),
                    "video_comment_sentiment": (cs or {}).get("label"),
                },
            })

    # The sample is the contract. If a segment went missing from a cache the
    # bench must stop, not quietly score 119 segments and call it 120.
    if len(probes) != len(sample["items"]):
        raise SystemExit(f"rebuilt {len(probes)} probes, sample.json has "
                         f"{len(sample['items'])}")
    return probes


# ── The text-only prompt ──────────────────────────────────────────────────────

def _json_schema_block(prompt: str) -> str:
    """The deployed prompt's output-contract block, extracted verbatim.

    Shared rather than retyped so `text_only_llm` cannot drift onto a different
    JSON contract from `four_channel`. If the deployed prompt is ever edited so
    this marker moves, every LLM system fails loudly at import instead of the
    baseline quietly becoming unfair — the failure mode `controller_bench`
    Amendment A1 was written about.
    """
    marker = "IMPORTANT: You must ALWAYS return valid JSON"
    if marker not in prompt:
        raise SystemExit("orchestrator._SYSTEM_PROMPT no longer contains the "
                         "output-contract marker; systems.py needs updating")
    return prompt[prompt.index(marker):]


TEXT_ONLY_PROMPT = """You are an authenticity assessment system for brand sentiment analysis.
You receive structured JSON describing a single video segment. You are given ONE signal:
1. transcript  — the exact words the creator SAYS in this segment

Your task:
- Judge, from the words alone, how likely it is that the creator is NOT being genuine here
  — that the segment is scripted marketing copy, undisclosed promotion, sarcasm, or
  over-sold enthusiasm the creator does not mean.
- Assign a conflict_score from 0.0 (clearly sincere, the creator means what they say)
  to 1.0 (clearly not genuine).
- Generate a concise plain-English narrative (2-3 sentences) explaining your judgement.

Use the full range of the scale. A plain descriptive statement with nothing promotional
about it should score near 0.0.

Leave `channels_in_conflict` as an empty list: only one channel is available to you.

""" + _json_schema_block(O._SYSTEM_PROMPT)


# A SECOND text-only prompt, declared before any full run (Amendment A5).
#
# A two-probe smoke test showed the first prompt returning 0.8 on "The USB-C
# cable. And a little insert, which has the case." — a plain descriptive
# sentence. A baseline that calls everything promotional has no variance, would
# score rho ~ 0 for a trivial reason, and beating it would prove nothing.
# PROTOCOL.md §3.1 requires this baseline to be STRONG, so a degenerate one is a
# threat to the primary comparison's validity, not a convenient result.
#
# The fix that would be cheating is to keep re-wording the prompt until the
# baseline behaves. The fix used instead: fix TWO prompts in advance, run both,
# and let the baseline's BEST result be the one `four_channel` has to beat.
#
# This is declared after seeing two probes and before seeing any distribution,
# and it can only ever help the baseline — the side that threatens this
# project's design — so it cannot be a thumb on the scale for the incumbent.
#
# The difference is calibration, not capability: explicit anchors and a stated
# base rate. No wording here was chosen by looking at a score distribution.
TEXT_ONLY_ANCHORED_PROMPT = """You are an authenticity assessment system for brand sentiment analysis.
You receive structured JSON describing a single video segment. You are given ONE signal:
1. transcript  — the exact words the creator SAYS in this segment

Your task: judge, from the words alone, how likely it is that the creator is NOT being
genuine here — scripted marketing copy, undisclosed promotion, sarcasm, or over-sold
enthusiasm they do not mean.

Calibrate against this scale. Most segments of an ordinary product review are sincere;
reserve high scores for segments that give you a positive reason for suspicion.

  0.0  clearly sincere — plain description, factual statement, ordinary narration,
       neutral commentary, or straightforward criticism
  0.25 mildly enthusiastic in a way that still sounds like the creator's own view
  0.5  genuinely ambiguous — could be sincere, could be sold
  0.75 strong promotional language, superlatives stacked, reads like ad copy
  1.0  clearly not genuine — sarcasm, or unmistakable undisclosed-promotion phrasing

Describing a product's features is NOT by itself promotional; it is what a review is.
Criticism is evidence of sincerity, not against it.

Leave `channels_in_conflict` as an empty list: only one channel is available to you.

""" + _json_schema_block(O._SYSTEM_PROMPT)


# ── Payload builders ──────────────────────────────────────────────────────────

def payload_for(system: str, probe: dict) -> dict:
    """The exact JSON body sent to Ollama for this system and segment."""
    if system == "four_channel":
        p = O.build_segment_payload(probe["segment"])
        cs = probe["comment_sentiment"] or {}
        p["video_comment_sentiment"] = (f"{cs.get('label', 'UNKNOWN')} "
                                        f"({float(cs.get('confidence', 0.0) or 0.0):.2f})")
        return p
    if system == "three_channel":
        # The pipeline as it actually ran on this corpus: no frames had been
        # extracted, so the facial channel reported "none detected".
        seg = dict(probe["segment"])
        seg["facial_emotion"] = {"dominant": None, "confidence": 0.0}
        p = O.build_segment_payload(seg)
        cs = probe["comment_sentiment"] or {}
        p["video_comment_sentiment"] = (f"{cs.get('label', 'UNKNOWN')} "
                                        f"({float(cs.get('confidence', 0.0) or 0.0):.2f})")
        return p
    if system in ("text_only_llm", "text_only_llm_anchored"):
        seg = probe["segment"]
        return {
            "segment_id": seg["segment_id"],
            "start_s": float(seg["start_time"]),
            "end_s": float(seg["end_time"]),
            "transcript": seg["text"],
        }
    raise KeyError(system)


def prompt_for(system: str) -> str:
    if system in ("four_channel", "three_channel"):
        return O._SYSTEM_PROMPT
    if system == "text_only_llm":
        return TEXT_ONLY_PROMPT
    if system == "text_only_llm_anchored":
        return TEXT_ONLY_ANCHORED_PROMPT
    raise KeyError(system)


def coerce_for(system: str, data: dict, probe: dict) -> dict:
    """Normalise one raw LLM response through the production coercion path."""
    if system == "four_channel":
        return O._coerce_result(data, probe["segment"], probe["comment_sentiment"])
    if system == "three_channel":
        seg = dict(probe["segment"])
        seg["facial_emotion"] = {"dominant": None, "confidence": 0.0}
        return O._coerce_result(data, seg, probe["comment_sentiment"])
    if system in ("text_only_llm", "text_only_llm_anchored"):
        # See the module docstring: the same function, on this system's own
        # inputs, so no damping can fire on channels it never saw.
        seg = probe["segment"]
        stripped = {"segment_id": seg["segment_id"],
                    "start_time": seg["start_time"],
                    "end_time": seg["end_time"],
                    "text": seg["text"]}
        return O._coerce_result(data, stripped, None)
    raise KeyError(system)


# ── The systems that need no LLM ──────────────────────────────────────────────

# Amendment A1: the protocol never fixed transcript_label's direction, and the
# association between transcript sentiment and human judgement had already been
# measured when the gap was found. Choosing a direction then would have been
# fitting on the test set, so both are run and both are reported.
POS_GENUINE = {"POSITIVE": 0.0, "NEUTRAL": 0.5, "NEGATIVE": 1.0}
NEG_GENUINE = {"POSITIVE": 1.0, "NEUTRAL": 0.5, "NEGATIVE": 0.0}


def rule_score(system: str, probe: dict) -> float:
    """Conflict score for a system that makes no model call."""
    if system == "constant":
        return 0.0
    label = probe["spec"]["transcript_sentiment"]
    table = POS_GENUINE if system == "transcript_label_pos_genuine" else NEG_GENUINE
    if system not in ("transcript_label_pos_genuine",
                      "transcript_label_neg_genuine"):
        raise KeyError(system)
    # An unreadable label is 0.5 — no information, the middle of the scale —
    # rather than 0.0, which would be a claim of sincerity the channel did not make.
    return table.get(label, 0.5)
