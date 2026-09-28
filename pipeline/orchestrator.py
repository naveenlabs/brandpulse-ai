"""
orchestrator.py — Ollama LLM orchestration layer

Implements the HuggingGPT controller paradigm (Shen et al., NeurIPS 2023):
  - Receives structured per-segment JSON from all three domain lanes
  - Sends to locally hosted Ollama (http://localhost:11434) — never a cloud API
  - Ollama compares valence direction across 4 channels per segment and answers
    with conflict_score, channels_in_conflict, flags and a narrative
  - The stored result keeps the score (damped where one weak channel alone
    dissents), the channels and flags as `conflict_reasons`, and `flagged`; the
    narrative is not stored

Conflict scoring logic:
  - Any segment where ≥2 channels disagree in valence → conflict event
  - Per-segment score: 0.0 (full agreement) → 1.0 (all channels disagree)
  - Flag threshold: conflict_score ≥ 0.75 → potential paid promotion / inauthentic review
  - A conflict that rests on ONE weak channel alone is damped by that channel's
    measured accuracy before flagging (VOCAL_ONLY_CONFLICT_WEIGHT 0.489,
    FACIAL_ONLY_CONFLICT_WEIGHT 0.342). "Rests on that channel alone" is decided
    two ways: from the controller's own attribution, and - since 02 Sep 2026,
    because the controller's attribution was measured never to fire - from the
    pipeline's own channel labels via _vocal_is_sole_dissenter /
    _facial_is_sole_dissenter

The channels are deliberately not equally weighted any more. Each has now been
benchmarked on hand-labelled data from this project, and they differ by 30
accuracy points; treating them as interchangeable was a design assumption that
the benches disproved. See VOCAL_ONLY_CONFLICT_WEIGHT for the figures and for
what is inference rather than measurement.
"""

from __future__ import annotations

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# The controller model.
#
# ADOPTED 05 Sep 2026 by measurement, replacing `llama3.2`, which had been chosen
# once and never compared to anything. `controller_bench/` pre-registered the
# question, the candidates, the metrics and the adoption rule before any candidate
# was downloaded; `CONTROLLER_MODEL_ANALYSIS.md` is the write-up.
#
# Why the swap, in one line: on 108 payloads covering every channel configuration,
# `llama3.2` detected 8 of 62 polar disagreements (POSITIVE on one channel,
# NEGATIVE on another) and `llama3.1:8b` detected 62 of 62 — on byte-identical
# payloads under this exact prompt. On the 481 real cached corpus segments the
# same gap reproduces: 11 of 81 against 81 of 81.
#
# `llama3.2`'s failure has a specific, measured shape rather than being general
# weakness: every one of its 9 non-zero answers on the grid had a NEGATIVE
# `video_comment_sentiment`, and none had a POSITIVE or NEUTRAL one. It had
# collapsed a four-way comparison into reading one field, and because the comment
# channel is POSITIVE on all 12 corpus videos, that mechanism was switched off
# almost everywhere on real data.
#
# WHAT THIS COSTS, stated rather than discovered later:
#   - ~2.3x slower per segment (median 4.8 s against 2.1 s on the probe grid), so
#     a 1,863-segment corpus run goes from roughly 1 hour to roughly 2.5.
#   - Every score this system has previously reported changes. On the 12-video
#     corpus the mean Authenticity Score moves 96.87 -> 47.79 and Brand Health
#     97.05 -> 77.42 (`report_bench.product_scores`, Rule 7).
#
# WHAT THE BENCH DOES **NOT** ESTABLISH: that the new scores are more *accurate*.
# The reference is analytic — it measures whether a controller performs the
# comparison the system prompt specifies, computed from the controller's own
# inputs. Whether that comparison detects real inauthenticity is a separate
# question needing hand-labelled segments, and it is not answered here. The
# defensible claim is narrower and is the one made: the system now does what it
# says it does.
#
# Overridable by environment variable, so reverting is a config change and not an
# edit.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# Conflict flag threshold (per project spec)
CONFLICT_FLAG_THRESHOLD = 0.75

# Context window requested from Ollama, in tokens.
#
# Added 05 Sep 2026, from a measurement made while building `controller_bench/`.
# Left unset, Ollama sizes the KV cache from the model's ADVERTISED maximum, not
# from the prompt it is about to receive. On this machine that made `llama3.1:8b`
# request **23 GB** for a 700-token prompt, against 16 GB of unified memory, and
# the run went to swap: throughput collapsed and the box became unusable. The
# 3B incumbent never showed the problem because its KV cache is small enough to
# fit anyway, which is exactly why this went unnoticed until a larger model was
# tried.
#
# 4096 is not a guess. The longest payload this pipeline has ever built, measured
# over all 481 cached corpus segments, is **154 tokens**; the system prompt is
# ~522. 4096 is a 5.8x margin over the largest prompt observed, and no payload
# the pipeline can construct comes close to it — segment text is bounded by
# Whisper's own segmentation.
#
# This CANNOT change any result for a prompt that fits, and every prompt fits. It
# changes the memory Ollama reserves, nothing else. It also makes the footprint
# identical across controllers, which is what let `controller_bench` compare
# eight models on equal terms rather than on their advertised context lengths.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

# ── Vocal channel down-weighting ──────────────────────────────────────────────
#
# The four channels are NOT equally trustworthy. Three-class accuracy of each
# deployed channel model, measured on this project's own hand-labelled data, on
# held-out speakers or videos in every case so the figures are comparable:
#
#   comment sentiment      78.7%  (118/150)  comment_bench/v2/holdout/HOLDOUT_RESULT.md
#   transcript sentiment   67.8%  (199 segs) transcript_bench/WINNER.md §7
#   vocal emotion          48.9%  (23/47)    vocal_bench/VOCAL_MODEL_ANALYSIS.md §5b
#   facial emotion         34.2%  (39/114)   facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md
#
# The two weakest, vocal and facial, are damped here (the facial weight is below).
# Damping the others without a measured reason would be tuning, not evidence.
#
# A conflict that rests on the vocal channel alone is therefore roughly a coin
# flip, and letting it drive a flag at full strength inflates the flag rate and
# deflates the Authenticity Score. `PROTOTYPE_FINDINGS.md` §11 measured that
# effect from the other direction: correcting channel inputs by hand moved the
# Authenticity Score from 26.55 to 80.57 and flagged segments from 33/77 to 0/77.
#
# So when the controller attributes a conflict to the vocal channel and nothing
# else, the resulting score is multiplied by this weight.
#
# The value is the channel's measured held-out accuracy (23 of 47 clips), not a
# tuning knob. The reasoning: if the sole evidence for a conflict is a reading
# that is correct with probability p, the expected strength of that evidence is
# p times its nominal strength.
#
# REASONABLE INFERENCE, not a verified fact. Three-class accuracy is a proxy for
# "this specific conflict is real", and the two are not identical — a wrong
# reading can still land on the wrong side of the same disagreement. It is
# defensible and it is traceable to a measurement; it is not derived from first
# principles. Its effect on the final scores is measured directly in
# vocal_bench/CORPUS_AB_RESULT.md rather than assumed.
VOCAL_ONLY_CONFLICT_WEIGHT = 0.489

# Names the controller has been observed to use for the vocal channel, plus the
# payload key it is actually given. Matched after lowercasing and stripping
# separators, because models are inconsistent about "vocal_emotion" vs
# "vocal emotion" vs "vocalProsody".
_VOCAL_CHANNEL_ALIASES = frozenset({
    "vocalemotion", "vocalprosody", "vocal", "voice", "prosody",
    "speechbrainemotion", "vocaltone", "tone", "audio", "vocalsentiment",
})


# The same correction for the facial channel, added 04 Sep 2026.
#
# 0.342 is `visual_module.FACIAL_CHANNEL_RELIABILITY`: 39 of 114 held-out frames,
# from `facial_bench/v2/`. That bench collected 320 frame-level expression labels
# against a pre-registered protocol, split them by speaker, and scored nine emotion
# models. Nothing was adopted. On the holdout **every** model scored below an
# always-NEUTRAL constant, the deployed one by 33.3 points, and it calls 33.8% of
# verified-neutral frames NEGATIVE (FACIAL_MODEL_ANALYSIS_V2.md §7-§8).
#
# That last figure is why this damping matters more than the accuracy figure alone
# suggests: the channel's characteristic error is manufacturing negativity on a
# presenter who is simply talking, and manufactured negativity is exactly what
# becomes a cross-channel conflict, then a flag, then a depressed Authenticity
# Score for a video that did nothing wrong.
#
# REASONABLE INFERENCE, not a verified fact — the same caveat as the vocal weight
# above, and for the same reason: three-class accuracy is a proxy for "this
# specific conflict is real", not a measurement of it.
FACIAL_ONLY_CONFLICT_WEIGHT = 0.342

_FACIAL_CHANNEL_ALIASES = frozenset({
    "facialemotion", "facial", "face", "facialexpression", "expression",
    "visual", "faceemotion", "facialsentiment", "deepface", "vision",
})


def _normalise_channel(name: object) -> str:
    """Lowercase and strip separators so channel names compare robustly."""
    return "".join(c for c in str(name).lower() if c.isalnum())


def _conflict_rests_only_on_vocal(channels: object) -> bool:
    """True when every channel the controller named in conflict is the vocal one.

    An empty list returns False: no attribution is not the same as attributing
    the conflict to the vocal channel, and damping an unattributed conflict would
    silently discount conflicts the controller found in the other three channels.

    MEASURED TO BE INERT ON `llama3.2`, the controller until 05 Sep 2026. It
    populated `channels_in_conflict` but decoupled it from its own score: across 481 raw
    responses it named at least one channel 265 times, and only 8 of those carried
    a score above 0.0 (vocal_bench/CORPUS_AB_RESULT.md §3.2). This path fired on
    0 of 479 segments. It is kept because a more compliant controller would make
    it work and it costs nothing, but it is not what protects the score. That is
    `_vocal_is_sole_dissenter` below.
    """
    return _conflict_rests_only_on(channels, _VOCAL_CHANNEL_ALIASES)


def _conflict_rests_only_on_facial(channels: object) -> bool:
    """True when every channel the controller named in conflict is the facial one.

    Same contract, same inertness caveat, as `_conflict_rests_only_on_vocal`: on
    `llama3.2` the controller's attribution did not track its own score, so this
    is not what protects the number. `_facial_is_sole_dissenter` is.
    """
    return _conflict_rests_only_on(channels, _FACIAL_CHANNEL_ALIASES)


def _conflict_rests_only_on(channels: object, aliases: frozenset[str]) -> bool:
    """Shared body for the two predicates above. One rule, two alias sets."""
    if not isinstance(channels, list) or not channels:
        return False
    normalised = {_normalise_channel(c) for c in channels}
    return normalised.issubset(aliases)


# ── The deterministic replacement for the rule above ──────────────────────────
#
# Added 02 Sep 2026 after measuring that the controller-attribution path never
# fires. This one reads the channel labels the pipeline already holds, so it does
# not depend on the controller answering a question about itself. It is a pure
# function of the segment, and it is unit-tested in both directions.

# DeepFace's emotion vocabulary, and the IEMOCAP words the pre-02-Sep vocal
# channel emitted, collapsed to the three-way valence the other channels use.
#
# `surprise` is deliberately absent. It is genuinely valence-ambiguous - a
# surprised face accompanies delight and dismay equally - and an unknown reading
# is never coerced. A channel whose reading cannot be placed
# on the valence axis is excluded from the agreement test rather than guessed at,
# which makes the rule fire less often, never more.
#
# The interface draws from the same lexicon: ui/src/lib/contract.js mirrors it,
# surprise excluded, and tests/test_ui_contracts.py checks the two are identical.
_VALENCE_WORDS = {
    "positive": "POSITIVE", "happy": "POSITIVE",
    "neutral": "NEUTRAL",
    "negative": "NEGATIVE", "sad": "NEGATIVE", "angry": "NEGATIVE",
    "fear": "NEGATIVE", "disgust": "NEGATIVE",
}

# How many other channels must carry a usable reading before the vocal channel
# can be called a lone dissenter.
#
# Two, not one. With a single comparator, "the others agree" is vacuously true and
# a disagreement is a coin flip between two channels rather than one voice
# breaking a consensus - and the damping constant is derived from the vocal
# channel's accuracy alone, so it is only the right correction when the vocal
# channel is the thing in doubt. Damping raises the Authenticity Score, so the
# conservative error is to damp too rarely.
#
# Both settings WERE measured, on 977 cached controller responses, and came out
# identical: every segment in that corpus has exactly two other readable channels,
# because no frames were extracted (no facial channel) and comment sentiment
# resolved for all 12 videos. The corpus cannot separate 1 from 2, so this value
# rests on the reasoning above and not on a measurement. Recorded as such in
# vocal_bench/DAMPING_FIX_RESULT.md §4 rather than presented as validated.
MIN_CORROBORATING_CHANNELS = 2


def _to_valence(raw: object) -> str | None:
    """Map any channel's label onto POSITIVE / NEUTRAL / NEGATIVE, or None.

    None means "this channel has no usable reading" and is returned for absent
    values, empty strings, the literal "unknown", and any word not on the valence
    axis. It is never silently turned into NEUTRAL - a channel that declined to
    answer must stay distinguishable from one that answered "neutral".
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _VALENCE_WORDS.get(raw.strip().lower())


def _channel_valences(segment: dict, comment_sentiment: dict | None) -> dict[str, str]:
    """Every channel of this segment that has a usable valence, keyed by name.

    Channels with no reading are omitted rather than defaulted, so the caller can
    tell three agreeing channels from one agreeing channel and two silences.
    Never raises: a malformed segment yields fewer channels, not an exception.
    """
    out: dict[str, str] = {}

    ts = segment.get("transcript_sentiment")
    if isinstance(ts, dict):
        v = _to_valence(ts.get("label"))
        if v:
            out["transcript"] = v

    fe = segment.get("facial_emotion")
    if isinstance(fe, dict):
        v = _to_valence(fe.get("dominant"))
        if v:
            out["facial"] = v

    ve = segment.get("vocal_emotion")
    if isinstance(ve, dict):
        v = _to_valence(ve.get("label"))
    else:
        v = _to_valence(ve)          # pre-02-Sep segments stored a bare string
    if v:
        out["vocal"] = v

    if isinstance(comment_sentiment, dict):
        v = _to_valence(comment_sentiment.get("label"))
        if v:
            out["comment"] = v

    return out


def _vocal_is_sole_dissenter(segment: dict,
                             comment_sentiment: dict | None = None) -> bool:
    """True when the vocal channel is the only channel breaking a consensus.

    All of these must hold:
      1. the vocal channel has a usable reading;
      2. at least MIN_CORROBORATING_CHANNELS other channels do too;
      3. those other channels all agree with one another;
      4. the vocal reading differs from what they agree on.

    Removing the vocal reading would then remove the disagreement entirely, which
    is precisely the case where the conflict rests on a channel measured at 48.9%
    accuracy. If the other channels disagree among themselves the conflict does
    not rest on the vocal channel and nothing is damped.
    """
    return _is_sole_dissenter(segment, comment_sentiment, "vocal")


def _facial_is_sole_dissenter(segment: dict,
                              comment_sentiment: dict | None = None) -> bool:
    """True when the facial channel is the only channel breaking a consensus.

    Identical rule to `_vocal_is_sole_dissenter`, applied to the channel measured
    at 34.2% on held-out speakers (FACIAL_ONLY_CONFLICT_WEIGHT).

    The two cannot both be true of the same segment: if the vocal channel is the
    lone dissenter then every other channel agrees, which includes the facial one,
    so the facial channel is not dissenting. That is asserted in the tests rather
    than left as a claim.
    """
    return _is_sole_dissenter(segment, comment_sentiment, "facial")


def _is_sole_dissenter(segment: dict, comment_sentiment: dict | None,
                       channel: str) -> bool:
    """Shared body for the two predicates above. One rule, any channel name."""
    labels = _channel_valences(segment, comment_sentiment)
    mine = labels.get(channel)
    if mine is None:
        return False
    others = {name: v for name, v in labels.items() if name != channel}
    if len(others) < MIN_CORROBORATING_CHANNELS:
        return False
    consensus = set(others.values())
    if len(consensus) != 1:
        return False
    return mine not in consensus

_SYSTEM_PROMPT = """You are a cross-modal conflict detection system for brand sentiment analysis.
You receive structured JSON describing a single video segment with signals from four independent channels:
1. transcript_sentiment  — what the creator SAYS (text NLP)
2. facial_emotion        — what the creator's FACE shows (computer vision)
3. vocal_prosody         — how the creator SOUNDS (audio features)
4. comment_sentiment     — what the AUDIENCE wrote in response (text NLP, video-level)

Your task:
- Compare the emotional valence direction (POSITIVE / NEUTRAL / NEGATIVE) of each channel
- Identify which channels disagree and explain why this is significant
- Assign a conflict_score from 0.0 (full agreement) to 1.0 (all channels disagree)
- Generate a concise plain-English narrative (2–3 sentences) explaining the conflict

CHANNEL RELIABILITY. The channels are not equally reliable, and each payload states the
vocal channel's measured accuracy in `vocal_reliability`. The vocal channel is correct on
fewer than half of held-out samples. Treat it as weak supporting evidence only. Do NOT
raise a high conflict_score when the vocal channel is the only channel that disagrees;
a disagreement between the transcript, facial and comment channels is far stronger
evidence than anything the vocal channel reports on its own.

List every channel you consider to be in conflict in `channels_in_conflict`, using the
exact key names from the payload. This field is read programmatically.

IMPORTANT: You must ALWAYS return valid JSON in exactly this schema. Never return freeform text.
{
  "segment_id": <int>,
  "conflict_score": <float 0.0–1.0>,
  "channels_in_conflict": [<list of channel name strings>],
  "flags": [<list of flag strings, e.g. "POTENTIAL_PAID_PROMOTION", "SARCASM_DETECTED">],
  "narrative": "<plain English explanation>"
}"""


def build_segment_payload(segment: dict) -> dict:
    """
    Extract the four channels from a fully-enriched segment into a clean,
    human-readable payload for the LLM prompt.

    A fully-enriched segment carries:
      - transcript_sentiment : {"label": str, "confidence": float}  (text NLP)
      - facial_emotion       : {"dominant": str|None, "confidence": float, ...} (vision)
      - vocal_emotion        : {"label": str, "arousal": float, "reliability": float}
      - pitch_mean / energy_mean / spectral_centroid : float        (audio features)

    All lookups are KeyError-safe: a segment missing any channel still yields a
    valid payload with sensible defaults so orchestration never aborts.

    Returns
    -------
    {
      "segment_id": int,
      "start_s": float,
      "end_s": float,
      "transcript": str,
      "transcript_sentiment": str,   # "POSITIVE (0.92)"
      "vocal_emotion": str,          # "POSITIVE (arousal 0.71)" | "unknown"
      "vocal_reliability": float,    # measured accuracy of the vocal channel
      "pitch_mean_hz": float,
      "energy_mean": float,
      "facial_emotion": str,         # "happy (0.78)" | "none detected"
    }
    """
    # Transcript sentiment → "LABEL (0.00)"
    ts = segment.get("transcript_sentiment") or {}
    ts_label = ts.get("label", "UNKNOWN")
    ts_conf = float(ts.get("confidence", 0.0) or 0.0)
    transcript_sentiment = f"{ts_label} ({ts_conf:.2f})"

    # Facial emotion → "dominant (0.00)" or "none detected"
    fe = segment.get("facial_emotion") or {}
    fe_dominant = fe.get("dominant")
    if fe_dominant is None:
        facial_emotion = "none detected"
    else:
        fe_conf = float(fe.get("confidence", 0.0) or 0.0)
        facial_emotion = f"{fe_dominant} ({fe_conf:.2f})"

    # Vocal emotion -> "LABEL (arousal 0.00)" or "unknown", plus its reliability.
    # A dict is expected (schema of 02 Sep 2026). A bare string is accepted so
    # that segment JSON written by an earlier version of the pipeline still
    # orchestrates rather than crashing; such a segment has no reliability
    # figure, so it reports 0.0 and is treated as unmeasured.
    ve = segment.get("vocal_emotion")
    if isinstance(ve, dict):
        ve_label = ve.get("label", "unknown")
        arousal = ve.get("arousal")
        vocal_emotion = (f"{ve_label} (arousal {float(arousal):.2f})"
                         if isinstance(arousal, (int, float)) and not isinstance(arousal, bool)
                         else str(ve_label))
        vocal_reliability = float(ve.get("reliability", 0.0) or 0.0)
    elif isinstance(ve, str) and ve:
        vocal_emotion, vocal_reliability = ve, 0.0
    else:
        vocal_emotion, vocal_reliability = "unknown", 0.0

    return {
        "segment_id":           segment.get("segment_id"),
        "start_s":              float(segment.get("start_time", 0.0) or 0.0),
        "end_s":                float(segment.get("end_time", 0.0) or 0.0),
        "transcript":           segment.get("text", ""),
        "transcript_sentiment": transcript_sentiment,
        "vocal_emotion":        vocal_emotion,
        "vocal_reliability":    round(vocal_reliability, 3),
        "pitch_mean_hz":        float(segment.get("pitch_mean", 0.0) or 0.0),
        "energy_mean":          float(segment.get("energy_mean", 0.0) or 0.0),
        "facial_emotion":       facial_emotion,
    }


def _safe_fallback(segment: dict, reason: str) -> dict:
    """Conflict result used whenever the LLM call or parse cannot be trusted."""
    return {
        "segment_id":       segment.get("segment_id"),
        "start_s":          float(segment.get("start_time", 0.0) or 0.0),
        "end_s":            float(segment.get("end_time", 0.0) or 0.0),
        "conflict_score":   0.0,
        "conflict_reasons": [reason],
        "flagged":          False,
    }


def _trigger_name(attributed: bool, structural: bool) -> str:
    """Which of the two triggers fired, for the audit line in `conflict_reasons`."""
    return "+".join(t for t, fired in (("attributed", attributed),
                                       ("structural", structural)) if fired)


def _coerce_result(data: dict, segment: dict,
                   comment_sentiment: dict | None = None) -> dict:
    """
    Validate and normalise the raw LLM JSON into the canonical conflict result.

    The locked _SYSTEM_PROMPT asks the model for
      {conflict_score, channels_in_conflict, flags, narrative}
    so this coercion maps that schema (plus any stray keys) onto the contract
    {conflict_score, conflict_reasons, flagged} while defending against missing
    or malformed fields.  Never raises.
    """
    # conflict_score: must be a real number (bool is an int subclass — exclude it)
    raw_score = data.get("conflict_score")
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        score = 0.0
    else:
        score = float(raw_score)
    score = max(0.0, min(1.0, score))  # clamp to [0.0, 1.0]

    # conflict_reasons: prefer the explicit key, else derive from the system-prompt
    # schema (channels_in_conflict + flags), else empty list.
    reasons = data.get("conflict_reasons")
    if isinstance(reasons, list):
        reasons = [str(r) for r in reasons]
    else:
        derived: list[str] = []
        cic = data.get("channels_in_conflict")
        if isinstance(cic, list):
            derived.extend(f"channels_in_conflict: {c}" for c in cic)
        flags = data.get("flags")
        if isinstance(flags, list):
            derived.extend(str(f) for f in flags)
        reasons = derived

    # Down-weight a conflict that rests on ONE weak channel alone. The vocal
    # channel is correct on 48.9% of held-out samples and the facial channel on
    # 34.2% (see the two weights above), so at full strength either can push a
    # segment over CONFLICT_FLAG_THRESHOLD on evidence no better than a coin flip -
    # and a flagged segment is double-weighted in the Authenticity Score, so the
    # error compounds.
    #
    # Two independent triggers per channel, ORed, because they fail in different
    # ways.
    #
    #   attributed  the controller said the conflict was that channel's. Measured
    #               to fire on 0 of 479 segments with llama3.2, which is why the
    #               second trigger exists. Kept: it costs nothing and a more
    #               compliant controller would make it work.
    #   structural  the pipeline's own four channel labels say that channel is the
    #               lone dissenter. Depends on no model's self-report, is a pure
    #               function of the segment, and is unit-tested both ways.
    #
    # Which channel and which trigger fired is recorded in the reasons, so a run
    # can be audited without re-deriving it.
    cic = data.get("channels_in_conflict")
    v_attributed = _conflict_rests_only_on_vocal(cic)
    v_structural = _vocal_is_sole_dissenter(segment, comment_sentiment)
    f_attributed = _conflict_rests_only_on_facial(cic)
    f_structural = _facial_is_sole_dissenter(segment, comment_sentiment)

    candidates: list[tuple[str, float, str]] = []
    if v_attributed or v_structural:
        candidates.append(("vocal", VOCAL_ONLY_CONFLICT_WEIGHT,
                           _trigger_name(v_attributed, v_structural)))
    if f_attributed or f_structural:
        candidates.append(("facial", FACIAL_ONLY_CONFLICT_WEIGHT,
                           _trigger_name(f_attributed, f_structural)))

    weak_channel_only = bool(candidates)
    if weak_channel_only and score > 0.0:
        # If both channels fire they are contradicting each other - only one
        # channel can be the lone dissenter - so the two weights are NOT
        # multiplied. Multiplying would treat contradictory attributions as
        # independent evidence and damp by 0.167 on the strength of a
        # disagreement about which channel is at fault. The smaller weight is
        # applied once instead: smaller rather than larger because the documented
        # failure mode of this pipeline is over-flagging (PROTOTYPE_FINDINGS.md
        # §11 moved 33/77 flagged segments to 0/77 by correcting channel inputs
        # by hand), so the conservative error is to damp too much.
        channel, weight, trigger = min(candidates, key=lambda c: c[1])
        undamped = score
        score = round(score * weight, 4)
        reasons = reasons + [
            f"{channel}_channel_downweighted[{trigger}]: {undamped:.4f} -> {score:.4f} "
            f"(x{weight}, measured channel accuracy)"
        ]

    # flagged: trust an explicit boolean, otherwise recompute from the score.
    #
    # The exception is a damped score. There, any boolean the controller supplied
    # was formed against the undamped score and is stale, so `flagged` is always
    # recomputed. Without this the damping would move the number the report shows
    # but not the double-weighting in compute_authenticity_score, which is most of
    # its effect.
    flagged = data.get("flagged")
    if weak_channel_only or not isinstance(flagged, bool):
        flagged = score >= CONFLICT_FLAG_THRESHOLD

    return {
        "segment_id":       segment.get("segment_id"),
        "start_s":          float(segment.get("start_time", 0.0) or 0.0),
        "end_s":            float(segment.get("end_time", 0.0) or 0.0),
        "conflict_score":   round(score, 4),
        "conflict_reasons": reasons,
        "flagged":          flagged,
    }


def analyse_segment(segment: dict, comment_sentiment: dict) -> dict:
    """
    Score cross-modal conflict for one segment via the local Ollama LLM.

    Pipeline:
      1. Build the per-segment payload (4 channels) + video-level comment sentiment.
      2. Serialise to JSON and send to Ollama (format="json" enforced upstream).
      3. Parse and normalise the response into the canonical conflict result.

    Never raises — any failure (unreachable Ollama, malformed JSON, missing keys)
    yields a safe fallback result so a single bad segment cannot abort the run.

    Returns
    -------
    {
      "segment_id": int,
      "start_s": float,
      "end_s": float,
      "conflict_score": float,        # 0.0–1.0
      "conflict_reasons": list[str],
      "flagged": bool,                # conflict_score >= CONFLICT_FLAG_THRESHOLD
    }
    """
    try:
        payload = build_segment_payload(segment)
    except Exception as exc:  # pragma: no cover — build is KeyError-safe
        logger.warning("Failed to build payload for segment %s: %s",
                       segment.get("segment_id"), exc)
        return _safe_fallback(segment, "payload_error")

    # Attach the video-level comment channel in the same "LABEL (0.00)" format.
    cs = comment_sentiment or {}
    cs_label = cs.get("label", "UNKNOWN")
    cs_conf = float(cs.get("confidence", 0.0) or 0.0)
    payload["video_comment_sentiment"] = f"{cs_label} ({cs_conf:.2f})"

    user_content = json.dumps(payload)

    try:
        raw = _call_ollama(user_content)
    except Exception as exc:
        logger.warning("Ollama call failed for segment %s: %s",
                       segment.get("segment_id"), exc)
        return _safe_fallback(segment, "parse_error")

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM returned non-object JSON")
    except Exception as exc:
        logger.warning("Could not parse Ollama JSON for segment %s: %s",
                       segment.get("segment_id"), exc)
        return _safe_fallback(segment, "parse_error")

    return _coerce_result(data, segment, comment_sentiment)


def _call_ollama(user_content: str) -> str:
    """POST to Ollama /api/chat and return the assistant message string."""
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "format": "json",
        # temperature=0 + a fixed seed make the conflict_score reproducible
        # across repeated runs on the same video. Without this, Ollama's default
        # sampling randomness caused authenticity/brand health scores to vary by
        # 10-20+ points between identical re-runs (observed empirically).
        "options": {
            "temperature": 0,
            "seed": 42,
            # See OLLAMA_NUM_CTX. Bounds the KV cache so a larger controller
            # cannot silently reserve more memory than the machine has.
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=body,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def run_orchestration(
    segments: list[dict],
    comment_sentiment: dict,
    cancel_check=None,
) -> list[dict]:
    """
    Run Ollama conflict analysis over every segment, sequentially.

    Ollama is single-threaded, so segments are processed in order rather than in
    parallel.  analyse_segment() is already failure-proof; the extra try/except
    here is defence-in-depth so an unexpected error on one segment still yields a
    fallback result and the rest of the run continues.

    cancel_check : optional zero-arg callable returning True if the caller wants
        to stop early (e.g. a user-requested cancel from the web UI). Checked
        between segments — this is the finest-grained cancellation point in the
        pipeline. Returns whatever partial results were computed so far.

    Returns one conflict result per input segment, in the same order (or fewer,
    if cancelled partway through).
    """
    results: list[dict] = []
    total = len(segments)

    for index, segment in enumerate(segments, start=1):
        if cancel_check is not None and cancel_check():
            logger.info("run_orchestration: cancelled after %d/%d segments.", len(results), total)
            break
        logger.debug("Orchestrating segment %d/%d …", index, total)
        try:
            result = analyse_segment(segment, comment_sentiment)
        except Exception as exc:  # pragma: no cover — analyse_segment is failure-proof
            logger.warning("Unexpected error orchestrating segment %s: %s",
                           segment.get("segment_id"), exc)
            result = _safe_fallback(segment, "orchestration_error")
        results.append(result)

    flagged_count = sum(1 for r in results if r.get("flagged"))
    logger.info(
        "run_orchestration: %d/%d segments processed, %d flagged (threshold %.2f).",
        len(results), total, flagged_count, CONFLICT_FLAG_THRESHOLD,
    )
    return results
