"""
Tests for pipeline/orchestrator.py

Pass criteria (per project spec):
  - build_segment_payload: all four channels surfaced; KeyError-safe; facial "none detected"
  - analyse_segment: clamps score to [0,1]; defaults missing fields; never raises
  - run_orchestration: one result per segment, order preserved, isolates failures

NONE of these tests require a running Ollama process:
  - analyse_segment tests mock pipeline.orchestrator._call_ollama
  - run_orchestration tests mock pipeline.orchestrator.analyse_segment
  - build_segment_payload tests are pure Python

The pooled segment schema uses facial_emotion["dominant"] (see visual_module.
pool_emotions_per_segment), NOT "dominant_emotion" — fixtures below match that.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from pipeline import orchestrator as orchestrator_module

from pipeline.orchestrator import (
    CONFLICT_FLAG_THRESHOLD,
    analyse_segment,
    build_segment_payload,
    run_orchestration,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _segment(
    sid: int = 0,
    start: float = 0.0,
    end: float = 10.0,
    ts_label: str = "POSITIVE",
    ts_conf: float = 0.95,
    vocal: dict | str | None = None,
    facial_dominant: str | None = "happy",
    facial_conf: float = 0.88,
) -> dict:
    facial = (
        {"dominant": None, "confidence": 0.0, "frame_count": 0}
        if facial_dominant is None
        else {"dominant": facial_dominant, "confidence": facial_conf, "frame_count": 3}
    )
    return {
        "segment_id":           sid,
        "start_time":           start,
        "end_time":             end,
        "text":                 "This product is incredible",
        "transcript_sentiment": {"label": ts_label, "confidence": ts_conf},
        # Schema of 02 Sep 2026: a dict, not a bare IEMOCAP word. The default is
        # a plausible real reading - high arousal, so the label is POSITIVE.
        "vocal_emotion":        vocal if vocal is not None else {
            "label": "POSITIVE", "arousal": 0.72, "valence": 0.55,
            "dominance": 0.58, "reliability": 0.489},
        "pitch_mean":           155.0,
        "energy_mean":          0.030,
        "spectral_centroid":    1900.0,
        "facial_emotion":       facial,
    }


COMMENT_SENTIMENT = {
    "label": "NEGATIVE",
    "confidence": 0.85,
    "comment_count": 50,
    "distribution": {"POSITIVE": 5, "NEUTRAL": 10, "NEGATIVE": 35},
}


def _ollama_response(**kwargs) -> str:
    """Serialise a dict the way _call_ollama would return it (a JSON string)."""
    return json.dumps(kwargs)


# ── build_segment_payload (pure Python) ───────────────────────────────────────

class TestBuildSegmentPayload:
    REQUIRED_KEYS = {
        "segment_id", "start_s", "end_s", "transcript", "transcript_sentiment",
        "vocal_emotion", "vocal_reliability", "pitch_mean_hz", "energy_mean",
        "facial_emotion",
    }

    def test_all_required_keys_present(self):
        payload = build_segment_payload(_segment())
        assert set(payload.keys()) == self.REQUIRED_KEYS

    def test_transcript_sentiment_formatted(self):
        payload = build_segment_payload(_segment(ts_label="POSITIVE", ts_conf=0.92))
        assert payload["transcript_sentiment"] == "POSITIVE (0.92)"

    def test_facial_emotion_present_formatted(self):
        payload = build_segment_payload(_segment(facial_dominant="happy", facial_conf=0.78))
        assert payload["facial_emotion"] == "happy (0.78)"

    def test_facial_emotion_none_is_none_detected(self):
        payload = build_segment_payload(_segment(facial_dominant=None))
        assert payload["facial_emotion"] == "none detected"

    def test_vocal_emotion_formatted_with_its_arousal(self):
        payload = build_segment_payload(_segment(vocal={
            "label": "NEGATIVE", "arousal": 0.18, "valence": 0.6,
            "dominance": 0.4, "reliability": 0.489}))
        assert payload["vocal_emotion"] == "NEGATIVE (arousal 0.18)"

    def test_a_pre_2026_09_02_segment_still_orchestrates(self):
        """Backwards compatibility with segment JSON written before the swap.

        Such a segment has no reliability figure, so it reports 0.0 rather than
        being given the current model's - the reading did not come from the
        current model.
        """
        payload = build_segment_payload(_segment(vocal="angry"))
        assert payload["vocal_emotion"] == "angry"
        assert payload["vocal_reliability"] == 0.0

    def test_time_bounds_carried_through(self):
        payload = build_segment_payload(_segment(start=10.0, end=20.0))
        assert payload["start_s"] == 10.0
        assert payload["end_s"] == 20.0

    def test_missing_facial_emotion_key_is_safe(self):
        """A segment with no facial_emotion key must not raise."""
        seg = _segment()
        del seg["facial_emotion"]
        payload = build_segment_payload(seg)
        assert payload["facial_emotion"] == "none detected"

    def test_missing_transcript_sentiment_key_is_safe(self):
        seg = _segment()
        del seg["transcript_sentiment"]
        payload = build_segment_payload(seg)
        assert payload["transcript_sentiment"] == "UNKNOWN (0.00)"

    def test_missing_text_defaults_empty(self):
        seg = _segment()
        del seg["text"]
        payload = build_segment_payload(seg)
        assert payload["transcript"] == ""

    def test_missing_pitch_defaults_zero(self):
        seg = _segment()
        del seg["pitch_mean"]
        payload = build_segment_payload(seg)
        assert payload["pitch_mean_hz"] == 0.0


# ── analyse_segment (mock _call_ollama — no Ollama process) ───────────────────

class TestAnalyseSegment:
    REQUIRED_KEYS = {
        "segment_id", "start_s", "end_s",
        "conflict_score", "conflict_reasons", "flagged",
    }

    def test_valid_response_returns_all_keys(self):
        resp = _ollama_response(conflict_score=0.3, channels_in_conflict=[], flags=[])
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert set(result.keys()) == self.REQUIRED_KEYS

    def test_segment_id_and_bounds_preserved(self):
        resp = _ollama_response(conflict_score=0.3)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(sid=7, start=10.0, end=20.0), COMMENT_SENTIMENT)
        assert result["segment_id"] == 7
        assert result["start_s"] == 10.0
        assert result["end_s"] == 20.0

    def test_score_clamped_above_one(self):
        resp = _ollama_response(conflict_score=1.7)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_score"] == 1.0

    def test_score_clamped_below_zero(self):
        resp = _ollama_response(conflict_score=-0.5)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_score"] == 0.0

    def test_missing_score_defaults_zero(self):
        resp = _ollama_response(channels_in_conflict=["facial"], flags=[])
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_score"] == 0.0

    def test_non_numeric_score_defaults_zero(self):
        resp = _ollama_response(conflict_score="high")
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_score"] == 0.0

    def test_bool_score_treated_as_invalid(self):
        """True is an int subclass — must NOT be accepted as a score of 1.0."""
        resp = _ollama_response(conflict_score=True)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_score"] == 0.0

    def test_flagged_recomputed_when_missing_high(self):
        resp = _ollama_response(conflict_score=0.8)  # no "flagged" key
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["flagged"] is True

    def test_flagged_recomputed_when_missing_low(self):
        resp = _ollama_response(conflict_score=0.2)  # no "flagged" key
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["flagged"] is False

    def test_flagged_true_at_threshold(self):
        resp = _ollama_response(conflict_score=CONFLICT_FLAG_THRESHOLD)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["flagged"] is True

    def test_explicit_flagged_boolean_respected(self):
        resp = _ollama_response(conflict_score=0.2, flagged=True)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["flagged"] is True

    def test_conflict_reasons_explicit_list(self):
        resp = _ollama_response(conflict_score=0.7, conflict_reasons=["face vs text"])
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_reasons"] == ["face vs text"]

    def test_conflict_reasons_default_empty_list(self):
        resp = _ollama_response(conflict_score=0.1)  # no reasons / channels / flags
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_reasons"] == []

    def test_conflict_reasons_derived_from_system_prompt_schema(self):
        """The locked _SYSTEM_PROMPT emits channels_in_conflict + flags, not conflict_reasons."""
        resp = _ollama_response(
            conflict_score=0.7,
            channels_in_conflict=["facial_emotion", "transcript_sentiment"],
            flags=["POTENTIAL_PAID_PROMOTION"],
        )
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        reasons = result["conflict_reasons"]
        assert any("facial_emotion" in r for r in reasons)
        assert "POTENTIAL_PAID_PROMOTION" in reasons

    def test_ollama_raises_returns_fallback(self):
        with patch("pipeline.orchestrator._call_ollama", side_effect=ConnectionError("down")):
            result = analyse_segment(_segment(sid=3), COMMENT_SENTIMENT)
        assert result["conflict_score"] == 0.0
        assert result["flagged"] is False
        assert result["conflict_reasons"] == ["parse_error"]
        assert result["segment_id"] == 3

    def test_malformed_json_returns_fallback(self):
        with patch("pipeline.orchestrator._call_ollama", return_value="not json at all {{"):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_reasons"] == ["parse_error"]
        assert result["conflict_score"] == 0.0

    def test_non_object_json_returns_fallback(self):
        """A JSON array (not an object) must fall back rather than crash."""
        with patch("pipeline.orchestrator._call_ollama", return_value="[1, 2, 3]"):
            result = analyse_segment(_segment(), COMMENT_SENTIMENT)
        assert result["conflict_reasons"] == ["parse_error"]

    def test_comment_sentiment_included_in_payload(self):
        """The video-level comment sentiment must be sent to the LLM."""
        captured = {}

        def _capture(user_content: str) -> str:
            captured["content"] = user_content
            return _ollama_response(conflict_score=0.0)

        with patch("pipeline.orchestrator._call_ollama", side_effect=_capture):
            analyse_segment(_segment(), COMMENT_SENTIMENT)

        sent = json.loads(captured["content"])
        assert "video_comment_sentiment" in sent
        assert sent["video_comment_sentiment"] == "NEGATIVE (0.85)"

    def test_never_raises_on_empty_comment_sentiment(self):
        resp = _ollama_response(conflict_score=0.0)
        with patch("pipeline.orchestrator._call_ollama", return_value=resp):
            result = analyse_segment(_segment(), {})
        assert result["conflict_score"] == 0.0


# ── run_orchestration (mock analyse_segment) ──────────────────────────────────

class TestRunOrchestration:
    def test_one_result_per_segment(self):
        segs = [_segment(sid=i) for i in range(4)]
        fake = lambda seg, cs: {"segment_id": seg["segment_id"], "start_s": 0.0,
                                "end_s": 1.0, "conflict_score": 0.1,
                                "conflict_reasons": [], "flagged": False}
        with patch("pipeline.orchestrator.analyse_segment", side_effect=fake):
            results = run_orchestration(segs, COMMENT_SENTIMENT)
        assert len(results) == 4

    def test_order_preserved(self):
        segs = [_segment(sid=i) for i in range(5)]
        fake = lambda seg, cs: {"segment_id": seg["segment_id"], "start_s": 0.0,
                                "end_s": 1.0, "conflict_score": 0.1,
                                "conflict_reasons": [], "flagged": False}
        with patch("pipeline.orchestrator.analyse_segment", side_effect=fake):
            results = run_orchestration(segs, COMMENT_SENTIMENT)
        assert [r["segment_id"] for r in results] == [0, 1, 2, 3, 4]

    def test_empty_segments_returns_empty(self):
        assert run_orchestration([], COMMENT_SENTIMENT) == []

    def test_exception_isolated_rest_continue(self):
        segs = [_segment(sid=0), _segment(sid=1), _segment(sid=2)]

        def _flaky(seg, cs):
            if seg["segment_id"] == 1:
                raise RuntimeError("boom")
            return {"segment_id": seg["segment_id"], "start_s": 0.0, "end_s": 1.0,
                    "conflict_score": 0.1, "conflict_reasons": [], "flagged": False}

        with patch("pipeline.orchestrator.analyse_segment", side_effect=_flaky):
            results = run_orchestration(segs, COMMENT_SENTIMENT)

        assert len(results) == 3
        # The failed segment yields a fallback, not a missing entry
        assert results[1]["segment_id"] == 1
        assert results[1]["conflict_reasons"] == ["orchestration_error"]
        assert results[1]["flagged"] is False
        # Neighbours are unaffected
        assert results[0]["segment_id"] == 0
        assert results[2]["segment_id"] == 2


# ── The request body actually sent to Ollama ──────────────────────────────────
#
# Added 05 Sep 2026 with `OLLAMA_NUM_CTX`. These options are the whole
# reproducibility and footprint contract of the controller, and until now none of
# them was asserted anywhere: `temperature`/`seed` were added to fix the
# run-to-run swing in PROTOTYPE_FINDINGS.md §5, and `num_ctx` was added after
# `controller_bench` measured `llama3.1:8b` reserving 23 GB on a 16 GB machine for
# a ~700-token prompt. A silent regression on any of them would be invisible until
# a corpus run produced different scores.


def _sent_request():
    """Capture the body `_call_ollama` posts, without a network call."""
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "{}"}}

    def _spy(url, json=None, timeout=None):
        captured.update(url=url, body=json, timeout=timeout)
        return _Resp()

    with patch("pipeline.orchestrator.requests.post", side_effect=_spy):
        orchestrator_module._call_ollama("{}")
    return captured


def test_sends_temperature_zero_and_a_fixed_seed():
    opts = _sent_request()["body"]["options"]
    assert opts["temperature"] == 0
    assert opts["seed"] == 42


def test_sends_a_bounded_context_window():
    opts = _sent_request()["body"]["options"]
    assert opts["num_ctx"] == orchestrator_module.OLLAMA_NUM_CTX
    assert orchestrator_module.OLLAMA_NUM_CTX == 4096


def test_context_window_comfortably_exceeds_the_largest_real_prompt():
    # Largest payload measured over all 481 cached corpus segments is 154 tokens;
    # the system prompt is ~522. A 4x margin over their sum is the floor this
    # constant must keep, so shrinking it later fails here rather than in a run.
    approx = (len(orchestrator_module._SYSTEM_PROMPT) / 3.5) + 154
    assert orchestrator_module.OLLAMA_NUM_CTX > 4 * approx


def test_enforces_json_mode_and_no_streaming():
    body = _sent_request()["body"]
    assert body["format"] == "json"
    assert body["stream"] is False


def test_posts_to_the_local_endpoint_only():
    url = _sent_request()["url"]
    assert url.startswith(orchestrator_module.OLLAMA_BASE_URL)
    assert "localhost" in url or "127.0.0.1" in url, (
        "the controller must never call a remote endpoint")
