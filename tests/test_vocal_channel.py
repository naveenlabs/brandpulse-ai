"""
Tests for the vocal channel as it was rebuilt on 02 Sep 2026.

Three things changed together and each is tested separately, because they can
fail independently:

  1. the MODEL          speechbrain categorical -> audeering dimensional
  2. the DIMENSION      valence -> arousal, with thresholds frozen from the bench
  3. the WEIGHTING      a conflict resting on this channel alone is damped

The arithmetic is tested for real; only the model forward pass is mocked. What is
deliberately NOT mocked is `_coerce_result`, `classify_arousal` or the damping
rule - those are the logic this change introduced, and mocking them would leave
the change untested.

The frozen thresholds are pinned here on purpose. If someone re-tunes them on
pipeline data, that silently destroys the only out-of-sample evidence the channel
has (48.9% on held-out speakers), and a test failure is the right way to find out.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from pipeline import audio_module as A
from pipeline import orchestrator as O
from pipeline import scorer as S


# ── 1. The frozen configuration ───────────────────────────────────────────────

class TestFrozenBenchValues:
    """These constants are measurements, not settings. They are pinned."""

    def test_thresholds_are_the_ones_fitted_on_the_selection_split(self):
        assert (A.AROUSAL_LOW, A.AROUSAL_HIGH) == (0.40, 0.65)

    def test_the_pipeline_reads_arousal_not_valence(self):
        # The substantive half of the change. Swapping the model while still
        # reading valence would have reproduced the original defect.
        assert A.VOCAL_DIMENSION == "arousal"

    def test_reliability_is_the_measured_holdout_accuracy(self):
        # 23 of 47 scorable confirmation clips.
        assert A.VOCAL_CHANNEL_RELIABILITY == pytest.approx(23 / 47, abs=5e-4)

    def test_damping_weight_equals_the_channel_reliability(self):
        # The damping is justified as "weight the evidence by how often the
        # channel is right". If these two ever diverge, that justification is
        # no longer what the code does.
        assert O.VOCAL_ONLY_CONFLICT_WEIGHT == A.VOCAL_CHANNEL_RELIABILITY


# ── 2. Reading the dimension ──────────────────────────────────────────────────

class TestClassifyArousal:
    @pytest.mark.parametrize("value,expected", [
        (0.00, "NEGATIVE"), (0.39, "NEGATIVE"),
        (0.40, "NEUTRAL"),  (0.50, "NEUTRAL"), (0.6499, "NEUTRAL"),
        (0.65, "POSITIVE"), (1.00, "POSITIVE"),
    ])
    def test_bands_are_half_open_and_ordered_low_to_high(self, value, expected):
        assert A.classify_arousal(value) == expected

    def test_edges_match_the_bench_implementation_exactly(self):
        # report_bench.apply_thresholds is lower-edge-inclusive on both bands.
        # A mismatch here would mean the deployed thresholds are not the ones
        # the 48.9% was measured with.
        assert A.classify_arousal(A.AROUSAL_LOW) == "NEUTRAL"
        assert A.classify_arousal(A.AROUSAL_HIGH) == "POSITIVE"

    def test_missing_value_is_unknown_never_neutral(self):
        assert A.classify_arousal(None) == "unknown"


class TestUnknownReading:
    def test_a_failed_reading_is_not_coerced_to_neutral(self):
        # Coercing an absent measurement to NEUTRAL is the exact defect
        # transcript_bench found in the deployed transcript channel: it
        # manufactures a confident reading out of a failure.
        assert A._unknown_vocal("model_error")["label"] == "unknown"

    def test_a_failed_reading_carries_zero_reliability(self):
        assert A._unknown_vocal("model_error")["reliability"] == 0.0

    def test_the_reason_survives_for_diagnosis(self):
        assert A._unknown_vocal("segment_too_short")["reason"] == "segment_too_short"

    @pytest.mark.parametrize("field", ["arousal", "valence", "dominance"])
    def test_dimensions_are_none_not_zero(self, field):
        # 0.0 is a legal arousal value meaning "very low energy". Using it as the
        # missing marker would make a failure indistinguishable from a real
        # reading, and would classify as NEGATIVE.
        assert A._unknown_vocal("model_error")[field] is None


class TestAnalyseVocalEmotion:
    """Model forward pass mocked; slicing, thresholding and failure paths real."""

    @staticmethod
    def _segments():
        return [
            {"segment_id": 0, "start_time": 0.0, "end_time": 5.0},
            {"segment_id": 1, "start_time": 5.0, "end_time": 5.2},   # too short
            {"segment_id": 2, "start_time": 5.2, "end_time": 10.0},
        ]

    @staticmethod
    def _patched(monkeypatch, tmp_path, outputs):
        import numpy as np
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")  # existence is all the code checks before loading
        monkeypatch.setattr(A, "_load_wav_int16",
                            lambda p: (np.zeros(16000 * 12, dtype=np.int16), 16000))

        class Proc:
            def __call__(self, data, sampling_rate):
                return {"input_values": [np.zeros(len(data), dtype=np.float32)]}

        calls = {"n": 0}

        def model(_tensor):
            # A torch tensor, not a bare array: the production path calls
            # .numpy() on the result, and a mock that skips that would let a
            # real type error through unnoticed.
            import torch
            i = calls["n"]; calls["n"] += 1
            return torch.tensor([list(outputs[i])], dtype=torch.float32)

        monkeypatch.setattr(A, "_get_vocal_model", lambda: (Proc(), model))
        return wav

    def test_arousal_drives_the_label_and_all_dimensions_are_kept(
            self, monkeypatch, tmp_path):
        # (arousal, dominance, valence) - the checkpoint's fixed output order.
        wav = self._patched(monkeypatch, tmp_path, [(0.80, 0.5, 0.20), (0.30, 0.5, 0.90)])
        segs = self._segments()
        A.analyse_vocal_emotion(wav, segs)

        # High arousal with LOW valence still reads POSITIVE, and low arousal with
        # HIGH valence still reads NEGATIVE. That is the whole point of the swap:
        # if these came out the other way round, valence is still in charge.
        assert segs[0]["vocal_emotion"]["label"] == "POSITIVE"
        assert segs[0]["vocal_emotion"]["valence"] == pytest.approx(0.20)
        assert segs[2]["vocal_emotion"]["label"] == "NEGATIVE"
        assert segs[2]["vocal_emotion"]["valence"] == pytest.approx(0.90)

    def test_short_segments_are_skipped_not_guessed(self, monkeypatch, tmp_path):
        wav = self._patched(monkeypatch, tmp_path, [(0.8, 0.5, 0.2), (0.3, 0.5, 0.9)])
        segs = self._segments()
        A.analyse_vocal_emotion(wav, segs)
        assert segs[1]["vocal_emotion"]["label"] == "unknown"
        assert segs[1]["vocal_emotion"]["reason"] == "segment_too_short"

    def test_a_model_failure_degrades_that_segment_only(self, monkeypatch, tmp_path):
        import numpy as np
        wav = tmp_path / "audio.wav"; wav.write_bytes(b"")
        monkeypatch.setattr(A, "_load_wav_int16",
                            lambda p: (np.zeros(16000 * 12, dtype=np.int16), 16000))

        class Proc:
            def __call__(self, data, sampling_rate):
                return {"input_values": [np.zeros(len(data), dtype=np.float32)]}

        state = {"n": 0}

        def flaky(_tensor):
            import torch
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("simulated inference failure")
            return torch.tensor([[0.80, 0.5, 0.2]], dtype=torch.float32)

        monkeypatch.setattr(A, "_get_vocal_model", lambda: (Proc(), flaky))
        segs = self._segments()
        A.analyse_vocal_emotion(wav, segs)   # must not raise

        assert segs[0]["vocal_emotion"]["label"] == "unknown"
        assert segs[0]["vocal_emotion"]["reason"] == "model_error"
        assert segs[2]["vocal_emotion"]["label"] == "POSITIVE"   # run continued

    def test_missing_audio_raises_rather_than_returning_junk(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            A.analyse_vocal_emotion(tmp_path / "absent.wav", self._segments())


# ── 3. Channel-name matching ──────────────────────────────────────────────────

class TestVocalChannelMatching:
    @pytest.mark.parametrize("name", [
        "vocal_emotion", "vocal emotion", "vocalEmotion", "VOCAL_EMOTION",
        "vocal_prosody", "voice", "prosody", "speechbrain_emotion", "tone",
    ])
    def test_recognises_the_names_a_controller_actually_uses(self, name):
        assert O._conflict_rests_only_on_vocal([name])

    @pytest.mark.parametrize("channels", [
        ["transcript_sentiment"],
        ["vocal_emotion", "transcript_sentiment"],
        ["vocal_emotion", "facial_emotion"],
    ])
    def test_a_conflict_involving_another_channel_is_not_vocal_only(self, channels):
        assert not O._conflict_rests_only_on_vocal(channels)

    def test_no_attribution_is_not_treated_as_vocal_attribution(self):
        # An empty list means the controller named nothing, not that it named the
        # vocal channel. Damping it would silently discount conflicts found in the
        # other three channels.
        assert not O._conflict_rests_only_on_vocal([])

    @pytest.mark.parametrize("value", [None, "vocal_emotion", {"a": 1}, 42])
    def test_malformed_attributions_do_not_trigger_damping(self, value):
        assert not O._conflict_rests_only_on_vocal(value)


# ── 4. The damping itself ─────────────────────────────────────────────────────

class TestDamping:
    SEG = {"segment_id": 7, "start_time": 1.0, "end_time": 9.0}

    def test_a_vocal_only_conflict_is_scaled_by_the_channel_reliability(self):
        out = O._coerce_result(
            {"conflict_score": 0.90, "channels_in_conflict": ["vocal_emotion"]}, self.SEG)
        assert out["conflict_score"] == pytest.approx(
            round(0.90 * O.VOCAL_ONLY_CONFLICT_WEIGHT, 4))

    def test_damping_can_pull_a_segment_back_under_the_flag_threshold(self):
        # This is the behaviour that matters: a flagged segment is DOUBLE-weighted
        # in compute_authenticity_score, so an unflagged 0.90 and a flagged 0.90
        # are not remotely the same thing.
        assert 0.90 >= O.CONFLICT_FLAG_THRESHOLD
        out = O._coerce_result(
            {"conflict_score": 0.90, "channels_in_conflict": ["vocal_emotion"]}, self.SEG)
        assert out["flagged"] is False

    def test_a_stale_flagged_boolean_is_overridden_when_damping_applies(self):
        # The controller formed `flagged` against the undamped score. Trusting it
        # would move the number in the report but not the weighting in the score,
        # which is most of the effect.
        out = O._coerce_result(
            {"conflict_score": 0.90, "flagged": True,
             "channels_in_conflict": ["vocal_emotion"]}, self.SEG)
        assert out["flagged"] is False

    def test_an_explicit_flag_is_still_honoured_when_damping_does_not_apply(self):
        out = O._coerce_result(
            {"conflict_score": 0.10, "flagged": True,
             "channels_in_conflict": ["transcript_sentiment"]}, self.SEG)
        assert out["flagged"] is True
        assert out["conflict_score"] == pytest.approx(0.10)

    def test_a_multi_channel_conflict_is_never_damped(self):
        out = O._coerce_result(
            {"conflict_score": 0.90,
             "channels_in_conflict": ["vocal_emotion", "facial_emotion"]}, self.SEG)
        assert out["conflict_score"] == pytest.approx(0.90)
        assert out["flagged"] is True

    def test_a_zero_score_is_left_alone(self):
        out = O._coerce_result(
            {"conflict_score": 0.0, "channels_in_conflict": ["vocal_emotion"]}, self.SEG)
        assert out["conflict_score"] == 0.0
        assert not any("downweighted" in r for r in out["conflict_reasons"])

    def test_the_damping_is_recorded_in_the_reasons_with_both_numbers(self):
        out = O._coerce_result(
            {"conflict_score": 0.80, "channels_in_conflict": ["vocal_emotion"]}, self.SEG)
        note = [r for r in out["conflict_reasons"] if "vocal_channel_downweighted" in r]
        assert len(note) == 1
        # Auditable after the fact: the undamped value is not thrown away.
        assert "0.8000" in note[0] and str(O.VOCAL_ONLY_CONFLICT_WEIGHT) in note[0]

    def test_damping_never_pushes_a_score_out_of_range(self):
        for raw in (0.0, 0.01, 0.5, 1.0, 5.0, -3.0):
            out = O._coerce_result(
                {"conflict_score": raw, "channels_in_conflict": ["vocal"]}, self.SEG)
            assert 0.0 <= out["conflict_score"] <= 1.0


# ── 5. The payload the controller receives ────────────────────────────────────

class TestPayload:
    @staticmethod
    def _segment(vocal):
        return {"segment_id": 3, "start_time": 0.0, "end_time": 8.0,
                "text": "it is fine", "transcript_sentiment":
                    {"label": "NEUTRAL", "confidence": 0.6},
                "vocal_emotion": vocal, "pitch_mean": 140.0, "energy_mean": 0.02}

    def test_the_label_and_arousal_both_reach_the_controller(self):
        p = O.build_segment_payload(self._segment(
            {"label": "POSITIVE", "arousal": 0.712, "valence": 0.4,
             "dominance": 0.5, "reliability": 0.489}))
        assert p["vocal_emotion"] == "POSITIVE (arousal 0.71)"
        assert p["vocal_reliability"] == 0.489

    def test_a_legacy_string_segment_still_orchestrates(self):
        # Segment JSON written before 02 Sep 2026 must not crash the orchestrator.
        p = O.build_segment_payload(self._segment("angry"))
        assert p["vocal_emotion"] == "angry"

    def test_a_legacy_segment_reports_no_reliability_rather_than_a_made_up_one(self):
        assert O.build_segment_payload(self._segment("angry"))["vocal_reliability"] == 0.0

    @pytest.mark.parametrize("vocal", [None, {}, "", 42])
    def test_a_missing_or_malformed_reading_degrades_to_unknown(self, vocal):
        p = O.build_segment_payload(self._segment(vocal))
        assert p["vocal_emotion"] in ("unknown", "42")
        assert p["vocal_reliability"] == 0.0

    def test_an_unknown_reading_carries_no_fabricated_arousal(self):
        p = O.build_segment_payload(self._segment(
            {"label": "unknown", "arousal": None, "reliability": 0.0}))
        assert p["vocal_emotion"] == "unknown"

    def test_the_system_prompt_tells_the_controller_the_channel_is_weak(self):
        # The deterministic damping is the guarantee; this is the belt to its
        # braces. If the paragraph is dropped, corpus_ab.py's "before" arm also
        # silently stops being a valid control.
        assert "CHANNEL RELIABILITY." in O._SYSTEM_PROMPT
        assert "vocal_reliability" in O._SYSTEM_PROMPT


# ── 6. What the report says about all this ────────────────────────────────────

class TestReportSurfacesTheLimitation:
    @staticmethod
    def _report():
        segments = [{"segment_id": 0, "start_time": 0.0, "end_time": 5.0,
                     "text": "great phone",
                     "transcript_sentiment": {"label": "POSITIVE", "confidence": 0.9},
                     "vocal_emotion": {"label": "NEGATIVE", "arousal": 0.2,
                                       "valence": 0.5, "dominance": 0.5,
                                       "reliability": 0.489}}]
        conflicts = [{"segment_id": 0, "conflict_score": 0.9, "flagged": True,
                      "conflict_reasons": []}]
        return S.build_final_report("u", "b", segments, conflicts,
                                    {"label": "POSITIVE", "confidence": 0.8})

    def test_every_report_carries_the_vocal_caveat(self):
        assert self._report()["vocal_caveat"] == S.VOCAL_CAVEAT

    def test_every_report_carries_the_commercial_licence_restriction(self):
        # BrandPulse is framed as a B2B product and the adopted checkpoint is
        # CC-BY-NC-SA-4.0. A reader must not have to discover that themselves.
        assert self._report()["vocal_licence_note"] == S.VOCAL_LICENCE_NOTE

    def test_the_facial_bias_caveat_is_not_displaced_by_the_new_one(self):
        assert self._report()["bias_caveat"] == S.BIAS_CAVEAT

    def test_the_caveat_states_the_measured_number_not_a_vague_warning(self):
        assert "48.9%" in S.VOCAL_CAVEAT and "34.0%" in S.VOCAL_CAVEAT

    def test_flagged_segments_expose_the_full_vocal_reading(self):
        outputs = self._report()["flagged_segments"][0]["model_outputs"]
        assert outputs["vocal_emotion"]["label"] == "NEGATIVE"
        assert outputs["vocal_emotion"]["arousal"] == 0.2

    def test_a_segment_with_no_vocal_reading_still_reports(self):
        segments = [{"segment_id": 0, "start_time": 0.0, "end_time": 5.0, "text": "x"}]
        conflicts = [{"segment_id": 0, "conflict_score": 0.9, "flagged": True}]
        rep = S.build_final_report("u", "b", segments, conflicts, {})
        assert rep["flagged_segments"][0]["model_outputs"]["vocal_emotion"]["label"] == "unknown"


# ── 7. End to end through analyse_segment, Ollama mocked ──────────────────────

class TestAnalyseSegmentIntegration:
    SEG = {"segment_id": 1, "start_time": 0.0, "end_time": 6.0, "text": "solid phone",
           "transcript_sentiment": {"label": "POSITIVE", "confidence": 0.91},
           "vocal_emotion": {"label": "NEGATIVE", "arousal": 0.22, "valence": 0.55,
                             "dominance": 0.5, "reliability": 0.489},
           "pitch_mean": 150.0, "energy_mean": 0.03}

    def test_damping_applies_through_the_real_call_path(self):
        raw = json.dumps({"conflict_score": 0.85, "flags": ["POTENTIAL_PAID_PROMOTION"],
                          "channels_in_conflict": ["vocal_emotion"]})
        with patch.object(O, "_call_ollama", return_value=raw):
            out = O.analyse_segment(self.SEG, {"label": "POSITIVE", "confidence": 0.7})
        assert out["conflict_score"] == pytest.approx(round(0.85 * 0.489, 4))
        assert out["flagged"] is False
        assert "POTENTIAL_PAID_PROMOTION" in out["conflict_reasons"]

    def test_an_unreachable_controller_still_returns_a_result(self):
        with patch.object(O, "_call_ollama", side_effect=OSError("connection refused")):
            out = O.analyse_segment(self.SEG, {})
        assert out["conflict_score"] == 0.0
        assert out["flagged"] is False


# ── 8. The deployed code still reproduces the bench's numbers ─────────────────

class TestDeployedCodeReproducesTheBench:
    """The claim "48.9% on held-out speakers" is about the DEPLOYED thresholds.

    Everything else in this file tests the code in isolation. This tests the one
    thing that isolation cannot: that the constants shipped in audio_module still
    reproduce, on the bench's own hand-rated data, the figures quoted for them in
    VOCAL_MODEL_ANALYSIS.md, the module comments, VOCAL_CAVEAT and the report.

    It re-derives them through `pipeline.audio_module.classify_arousal` rather than
    the bench's `apply_thresholds`, so a divergence between the two implementations
    fails here instead of silently invalidating every quoted number.

    Skipped rather than failed when the bench artefacts are absent - a fresh clone
    has the code but not the 150 rated clips.
    """

    @staticmethod
    def _load():
        import sys
        from pathlib import Path
        bench = Path(__file__).resolve().parent.parent / "research" / "vocal_bench"
        if not (bench / "vocal_ground_truth.json").is_file():
            pytest.skip("vocal_bench ground truth not present")
        sys.path.insert(0, str(bench))
        import ground_truth as GT
        import report_bench as RB
        try:
            return GT, RB.load_predictions()["audeering-msp-dim"]["predictions"]
        except (KeyError, FileNotFoundError):
            pytest.skip("vocal_bench predictions not present")

    def _accuracy(self, split):
        GT, pred = self._load()
        rows = GT.load(split)
        correct = sum(A.classify_arousal(pred[r["uid"]]["scores"]["arousal"]) == r["label"]
                      for r in rows)
        return correct, len(rows)

    def test_selection_split_is_still_60_of_100(self):
        assert self._accuracy("selection") == (60, 100)

    def test_confirmation_split_is_still_23_of_47(self):
        # This is the number VOCAL_CHANNEL_RELIABILITY, the damping weight and
        # the caveat text are all derived from.
        assert self._accuracy("confirmation") == (23, 47)

    def test_the_reliability_constant_matches_what_it_claims_to_measure(self):
        correct, total = self._accuracy("confirmation")
        assert A.VOCAL_CHANNEL_RELIABILITY == pytest.approx(correct / total, abs=5e-4)

    def test_the_caveats_quoted_percentage_matches_the_measurement(self):
        correct, total = self._accuracy("confirmation")
        assert f"{100 * correct / total:.1f}%" in S.VOCAL_CAVEAT
