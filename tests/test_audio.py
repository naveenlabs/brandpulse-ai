"""
Tests for pipeline/audio_module.py

Pass criteria (per project spec):
  - Whisper: WER ≤ 5% on English; empty segment list (no crash) on non-speech
  - SpeechBrain: correct label on standard clips; scalar features in expected range
  - All four keys (text, transcript_sentiment, vocal_emotion, pitch/energy) present
"""

from __future__ import annotations

import struct
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from pipeline.audio_module import (
    MAX_MERGE_GAP,
    SENTIMENT_MODEL_ID,
    VOCAL_CHANNEL_RELIABILITY,
    VOCAL_MODEL_ID,
    add_transcript_sentiment,
    analyse_vocal_emotion,
    build_audio_channel,
    extract_prosody,
    transcribe,
    _estimate_pitch_hz,
    _merge_short_segments,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _in_local_cache(repo_id: str) -> bool:
    """True when a Hugging Face model's files are already on this machine."""
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(repo_id, "config.json"), str)


# These run the real models and check what they say. The weights are external
# data (the first analysis downloads them), so without them the tests skip and
# say which model is missing, rather than failing on a network error.
needs_transcript_model = pytest.mark.skipif(
    not _in_local_cache(SENTIMENT_MODEL_ID),
    reason=f"model integration test: {SENTIMENT_MODEL_ID} (1.0 GB) is not in the local "
           "Hugging Face cache; the first analysis downloads it")
needs_vocal_model = pytest.mark.skipif(
    not _in_local_cache(VOCAL_MODEL_ID),
    reason=f"model integration test: {VOCAL_MODEL_ID} (631 MB) is not in the local "
           "Hugging Face cache; the first analysis downloads it")

SR = 16_000  # sample rate used throughout


def _make_wav(signal: np.ndarray, path: Path, sr: int = SR) -> Path:
    """Write a 16-bit mono WAV file and return the path."""
    int16 = (signal * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16.tobytes())
    return path


def _sine(freq_hz: float, duration_s: float, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def _silence(duration_s: float, sr: int = SR) -> np.ndarray:
    return np.zeros(int(sr * duration_s), dtype=np.float32)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def silence_wav(tmp_path):
    sig = _silence(2.0)
    return _make_wav(sig, tmp_path / "silence.wav")


@pytest.fixture()
def sine_wav(tmp_path):
    """2-second 200 Hz sine wave — clear voiced pitch."""
    sig = _sine(200.0, 2.0)
    return _make_wav(sig, tmp_path / "sine200.wav")


@pytest.fixture()
def dummy_segments():
    """Minimal segment list that satisfies downstream function inputs."""
    return [
        {
            "segment_id": 0,
            "start_time": 0.0,
            "end_time": 2.0,
            "text": "This product is absolutely amazing, I love it",
        },
        {
            "segment_id": 1,
            "start_time": 2.0,
            "end_time": 4.0,
            "text": "Honestly this is terrible and I hate it",
        },
    ]


# ── Pitch estimation (pure numpy, no model required) ─────────────────────────

class TestEstimatePitchHz:
    def test_detects_200hz_sine(self):
        sig = _sine(200.0, 0.5)
        pitch = _estimate_pitch_hz(sig, SR)
        # Allow ±20 Hz tolerance
        assert abs(pitch - 200.0) < 20.0, f"Expected ~200 Hz, got {pitch:.1f} Hz"

    def test_silence_returns_zero(self):
        sig = _silence(0.5)
        assert _estimate_pitch_hz(sig, SR) == 0.0

    def test_very_short_returns_zero(self):
        sig = _sine(200.0, 0.01)  # 10 ms — below lag_max * 2 threshold
        assert _estimate_pitch_hz(sig, SR) == 0.0


# ── add_transcript_sentiment (HuggingFace model required) ────────────────────

class TestAddTranscriptSentiment:
    @needs_transcript_model
    def test_adds_sentiment_key_to_each_segment(self, dummy_segments):
        pytest.importorskip("transformers")
        result = add_transcript_sentiment(dummy_segments)
        for seg in result:
            assert "transcript_sentiment" in seg
            assert "label" in seg["transcript_sentiment"]
            assert "confidence" in seg["transcript_sentiment"]

    @needs_transcript_model
    def test_positive_text_labelled_positive(self, dummy_segments):
        pytest.importorskip("transformers")
        result = add_transcript_sentiment([dummy_segments[0]])
        label = result[0]["transcript_sentiment"]["label"]
        assert label in ("POSITIVE", "NEUTRAL"), f"Unexpected label: {label}"

    @needs_transcript_model
    def test_negative_text_labelled_negative(self, dummy_segments):
        pytest.importorskip("transformers")
        result = add_transcript_sentiment([dummy_segments[1]])
        label = result[0]["transcript_sentiment"]["label"]
        assert label in ("NEGATIVE", "NEUTRAL"), f"Unexpected label: {label}"

    def test_empty_text_gets_neutral(self):
        # Empty text is decided without the model, so the model is not loaded here.
        seg = [{"segment_id": 0, "start_time": 0.0, "end_time": 1.0, "text": ""}]
        with patch("pipeline.audio_module._get_sentiment_pipe", return_value=MagicMock()) as pipe:
            result = add_transcript_sentiment(seg)
        pipe.return_value.assert_not_called()
        assert result[0]["transcript_sentiment"]["label"] == "NEUTRAL"

    @needs_transcript_model
    def test_confidence_between_zero_and_one(self, dummy_segments):
        pytest.importorskip("transformers")
        result = add_transcript_sentiment(dummy_segments)
        for seg in result:
            conf = seg["transcript_sentiment"]["confidence"]
            assert 0.0 <= conf <= 1.0, f"Confidence out of range: {conf}"


# ── extract_prosody (pyAudioAnalysis + autocorrelation — no model download) ──

class TestExtractProsody:
    def test_adds_required_keys(self, sine_wav, dummy_segments):
        pytest.importorskip("pyAudioAnalysis")
        result = extract_prosody(sine_wav, dummy_segments)
        for seg in result:
            assert "pitch_mean" in seg
            assert "energy_mean" in seg
            assert "spectral_centroid" in seg

    def test_pitch_mean_is_float(self, sine_wav, dummy_segments):
        pytest.importorskip("pyAudioAnalysis")
        result = extract_prosody(sine_wav, dummy_segments)
        for seg in result:
            assert isinstance(seg["pitch_mean"], float)

    def test_energy_mean_non_negative(self, sine_wav, dummy_segments):
        pytest.importorskip("pyAudioAnalysis")
        result = extract_prosody(sine_wav, dummy_segments)
        for seg in result:
            assert seg["energy_mean"] >= 0.0

    def test_spectral_centroid_non_negative(self, sine_wav, dummy_segments):
        pytest.importorskip("pyAudioAnalysis")
        result = extract_prosody(sine_wav, dummy_segments)
        for seg in result:
            assert seg["spectral_centroid"] >= 0.0

    def test_silence_gives_zero_energy(self, silence_wav, dummy_segments):
        pytest.importorskip("pyAudioAnalysis")
        result = extract_prosody(silence_wav, dummy_segments)
        for seg in result:
            assert seg["energy_mean"] < 0.01, f"Expected near-zero energy, got {seg['energy_mean']}"

    def test_missing_file_raises(self, tmp_path, dummy_segments):
        pytest.importorskip("pyAudioAnalysis")
        with pytest.raises(FileNotFoundError):
            extract_prosody(tmp_path / "nonexistent.wav", dummy_segments)


# ── analyse_vocal_emotion (audeering dimensional — model download required) ──
#
# Rewritten 02 Sep 2026 with the channel swap. These are integration tests: they
# download and run the real model on real audio. The unit-level tests of the same
# function - thresholds, failure paths, the refusal to coerce unknown to NEUTRAL -
# live in tests/test_vocal_channel.py with the forward pass mocked, and run in
# about a second.

class TestAnalyseVocalEmotion:
    @needs_vocal_model
    def test_adds_vocal_emotion_key(self, sine_wav, dummy_segments):
        pytest.importorskip("transformers")
        result = analyse_vocal_emotion(sine_wav, dummy_segments)
        for seg in result:
            assert "vocal_emotion" in seg
            assert isinstance(seg["vocal_emotion"], dict)

    @needs_vocal_model
    def test_emotion_is_known_label(self, sine_wav, dummy_segments):
        pytest.importorskip("transformers")
        valid = {"POSITIVE", "NEUTRAL", "NEGATIVE", "unknown"}
        result = analyse_vocal_emotion(sine_wav, dummy_segments)
        for seg in result:
            assert seg["vocal_emotion"]["label"] in valid, \
                f"Unexpected label: {seg['vocal_emotion']['label']}"

    @needs_vocal_model
    def test_a_real_reading_carries_all_three_dimensions(self, sine_wav, dummy_segments):
        """Valence is stored even though arousal drives the label.

        It is what makes the "we were reading the wrong dimension" finding
        auditable on live pipeline output rather than only on bench clips.
        """
        pytest.importorskip("transformers")
        result = analyse_vocal_emotion(sine_wav, dummy_segments)
        read = [s["vocal_emotion"] for s in result if s["vocal_emotion"]["label"] != "unknown"]
        if not read:
            pytest.skip("no segment long enough for a reading in this fixture")
        for ve in read:
            for dim in ("arousal", "valence", "dominance"):
                assert 0.0 <= ve[dim] <= 1.0
            assert ve["reliability"] == VOCAL_CHANNEL_RELIABILITY

    def test_missing_file_raises(self, tmp_path, dummy_segments):
        pytest.importorskip("transformers")
        with pytest.raises(FileNotFoundError):
            analyse_vocal_emotion(tmp_path / "nonexistent.wav", dummy_segments)


# ── transcribe (Whisper — model download required) ────────────────────────────

class TestTranscribe:
    def test_returns_list(self, silence_wav):
        pytest.importorskip("whisper")
        result = transcribe(silence_wav)
        assert isinstance(result, list)

    def test_no_crash_on_silence(self, silence_wav):
        pytest.importorskip("whisper")
        result = transcribe(silence_wav)
        # Should return empty list, not raise
        assert result == [] or isinstance(result, list)

    def test_each_segment_has_required_keys(self, silence_wav):
        pytest.importorskip("whisper")
        result = transcribe(silence_wav)
        for seg in result:
            assert "segment_id" in seg
            assert "start_time" in seg
            assert "end_time" in seg
            assert "text" in seg

    def test_missing_file_raises(self, tmp_path):
        pytest.importorskip("whisper")
        with pytest.raises(FileNotFoundError):
            transcribe(tmp_path / "nonexistent.wav")


# ── _merge_short_segments ─────────────────────────────────────────────────────


def _seg(sid: int, start: float, end: float, text: str = "x") -> dict:
    return {"segment_id": sid, "start_time": start, "end_time": end, "text": text}


class TestMergeShortSegments:
    """
    Segment boundaries are the spine of the whole pipeline: every channel attaches
    to them, so a defect here corrupts all four channels at once. These tests pin
    the merge invariants rather than any particular output length.
    """

    def test_empty_input_returns_empty(self):
        assert _merge_short_segments([]) == []

    def test_single_segment_is_returned_unchanged(self):
        out = _merge_short_segments([_seg(0, 0.0, 1.0, "only")])
        assert len(out) == 1
        assert out[0]["text"] == "only"

    def test_long_segments_are_not_merged(self):
        segs = [_seg(0, 0.0, 10.0, "a"), _seg(1, 10.0, 20.0, "b")]
        out = _merge_short_segments(segs, min_duration=3.0)
        assert len(out) == 2

    def test_short_segment_merges_into_previous(self):
        segs = [_seg(0, 0.0, 1.0, "hello"), _seg(1, 1.0, 5.0, "world")]
        out = _merge_short_segments(segs, min_duration=3.0)
        assert len(out) == 1
        assert out[0]["text"] == "hello world"
        assert out[0]["end_time"] == 5.0

    def test_run_of_short_segments_does_not_collapse_into_one_block(self):
        """
        Regression, 31 Aug 2026. The previous implementation tested the arriving
        segment's duration instead of the accumulator's, so an unbroken run of
        sub-threshold segments appended without limit. On the real corpus that
        produced a single 121-second, 435-word segment out of 65 Whisper segments.
        Twenty contiguous 1-second segments must not become one 20-second block.
        """
        segs = [_seg(i, float(i), float(i + 1)) for i in range(20)]
        out = _merge_short_segments(segs, min_duration=3.0)
        assert len(out) > 1, "run of short segments collapsed into a single block"
        assert all(s["end_time"] - s["start_time"] <= 6.0 for s in out)

    def test_every_segment_but_the_last_reaches_min_duration(self):
        segs = [_seg(i, i * 0.5, (i + 1) * 0.5) for i in range(30)]
        out = _merge_short_segments(segs, min_duration=3.0)
        for s in out[:-1]:
            assert s["end_time"] - s["start_time"] >= 3.0

    def test_does_not_merge_across_a_long_silence(self):
        """A 21 s intro gap in the corpus was being bridged. Silence is a boundary."""
        segs = [_seg(0, 0.0, 1.0, "intro"), _seg(1, 22.0, 24.0, "body")]
        out = _merge_short_segments(segs, min_duration=3.0, max_gap=MAX_MERGE_GAP)
        assert len(out) == 2
        assert out[0]["text"] == "intro"
        assert out[1]["text"] == "body"

    def test_merges_across_a_small_gap(self):
        segs = [_seg(0, 0.0, 1.0, "a"), _seg(1, 1.5, 4.0, "b")]
        out = _merge_short_segments(segs, min_duration=3.0, max_gap=2.0)
        assert len(out) == 1

    def test_short_tail_is_folded_back(self):
        segs = [_seg(0, 0.0, 5.0, "body"), _seg(1, 5.0, 5.5, "tail")]
        out = _merge_short_segments(segs, min_duration=3.0)
        assert len(out) == 1
        assert out[0]["text"] == "body tail"

    def test_short_tail_after_long_silence_is_left_alone(self):
        segs = [_seg(0, 0.0, 5.0, "body"), _seg(1, 30.0, 30.5, "outro")]
        out = _merge_short_segments(segs, min_duration=3.0, max_gap=MAX_MERGE_GAP)
        assert len(out) == 2

    def test_segment_ids_are_renumbered_contiguously(self):
        segs = [_seg(7, 0.0, 1.0), _seg(8, 1.0, 2.0), _seg(9, 2.0, 9.0)]
        out = _merge_short_segments(segs, min_duration=3.0)
        assert [s["segment_id"] for s in out] == list(range(len(out)))

    def test_input_segments_are_not_mutated(self):
        segs = [_seg(0, 0.0, 1.0, "a"), _seg(1, 1.0, 5.0, "b")]
        before = [dict(s) for s in segs]
        _merge_short_segments(segs, min_duration=3.0)
        assert segs == before


# ── Three-class transcript sentiment (adopted 31 Aug 2026) ────────────────────
#
# The pre-existing TestAddTranscriptSentiment class above runs the real model and
# asserts only that the label is one of two acceptable values. Those assertions
# hold under both the old two-class-plus-threshold construction and the new
# three-class one, so they cannot detect a regression in this logic.
#
# These tests mock the model and pin the behaviour that actually changed. Each is
# verified to fail against the previous implementation; the reason is noted where
# it is not obvious.

class _FakePipe:
    """Stands in for the HF text-classification pipeline.

    Returns a fixed score distribution so the mapping logic is tested, never the
    model. Matches the real pipeline's shape: a list containing one list of
    {"label", "score"} dicts.
    """

    def __init__(self, scores: dict[str, float]):
        self.scores = scores

    def __call__(self, text):
        return [[{"label": k, "score": v} for k, v in self.scores.items()]]


@pytest.fixture
def sentiment_segment():
    return [{"segment_id": 0, "start_time": 0.0, "end_time": 4.0, "text": "some words here"}]


class TestThreeClassTranscriptSentiment:
    def test_native_neutral_is_returned_as_neutral(self, monkeypatch, sentiment_segment):
        # Old code emitted the raw label "neutral" (lowercase, unnormalised).
        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe",
            lambda: _FakePipe({"negative": 0.10, "neutral": 0.80, "positive": 0.10}),
        )
        out = add_transcript_sentiment(sentiment_segment)
        assert out[0]["transcript_sentiment"]["label"] == "NEUTRAL"
        assert out[0]["transcript_sentiment"]["confidence"] == pytest.approx(0.80)

    def test_low_confidence_positive_stays_positive(self, monkeypatch, sentiment_segment):
        # THE regression test for this change. Winning score 0.55 is below the old
        # 0.70 cut-off, so the previous implementation relabelled this NEUTRAL with
        # confidence 0.45. It must now stay POSITIVE with its own probability.
        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe",
            lambda: _FakePipe({"negative": 0.20, "neutral": 0.25, "positive": 0.55}),
        )
        out = add_transcript_sentiment(sentiment_segment)
        assert out[0]["transcript_sentiment"]["label"] == "POSITIVE"
        assert out[0]["transcript_sentiment"]["confidence"] == pytest.approx(0.55)

    def test_low_confidence_negative_stays_negative(self, monkeypatch, sentiment_segment):
        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe",
            lambda: _FakePipe({"negative": 0.52, "neutral": 0.28, "positive": 0.20}),
        )
        out = add_transcript_sentiment(sentiment_segment)
        assert out[0]["transcript_sentiment"]["label"] == "NEGATIVE"

    def test_confidence_is_winning_probability_not_its_complement(self, monkeypatch, sentiment_segment):
        # The old NEUTRAL branch reported 1 - best_score. Nothing may do that now.
        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe",
            lambda: _FakePipe({"negative": 0.05, "neutral": 0.60, "positive": 0.35}),
        )
        out = add_transcript_sentiment(sentiment_segment)
        assert out[0]["transcript_sentiment"]["confidence"] == pytest.approx(0.60)
        assert out[0]["transcript_sentiment"]["confidence"] != pytest.approx(0.40)

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("LABEL_0", "NEGATIVE"), ("LABEL_1", "NEUTRAL"), ("LABEL_2", "POSITIVE"),
            ("NEG", "NEGATIVE"), ("NEU", "NEUTRAL"), ("POS", "POSITIVE"),
            ("positive", "POSITIVE"), ("Negative", "NEGATIVE"),
        ],
    )
    def test_label_aliases_normalise(self, monkeypatch, sentiment_segment, raw, expected):
        # Verified 31 Aug 2026 that heads disagree on this: cardiffnlp orders its
        # labels negative/neutral/positive while lxyuan orders them the other way,
        # and the older cardiffnlp release emits LABEL_0/1/2.
        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe",
            lambda: _FakePipe({raw: 0.9, "other": 0.1}),
        )
        out = add_transcript_sentiment([dict(sentiment_segment[0])])
        assert out[0]["transcript_sentiment"]["label"] == expected

    def test_unmapped_label_degrades_to_neutral_and_logs_error(
        self, monkeypatch, caplog, sentiment_segment
    ):
        # A misconfigured SENTIMENT_MODEL_ID must not corrupt the channel silently.
        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe",
            lambda: _FakePipe({"5 stars": 0.9, "1 star": 0.1}),
        )
        with caplog.at_level("ERROR"):
            out = add_transcript_sentiment(sentiment_segment)
        assert out[0]["transcript_sentiment"]["label"] == "NEUTRAL"
        assert out[0]["transcript_sentiment"]["confidence"] == 0.0
        assert "unmapped label" in caplog.text

    def test_model_exception_degrades_without_raising(self, monkeypatch, sentiment_segment):
        # Graceful degradation: one bad segment must not abort a run.
        class _Boom:
            def __call__(self, text):
                raise RuntimeError("model exploded")

        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe", lambda: _Boom()
        )
        out = add_transcript_sentiment(sentiment_segment)
        assert out[0]["transcript_sentiment"] == {"label": "NEUTRAL", "confidence": 0.0}

    def test_all_segments_processed_when_one_fails(self, monkeypatch):
        calls = {"n": 0}

        class _FlakyPipe:
            def __call__(self, text):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RuntimeError("transient failure")
                return [[{"label": "positive", "score": 0.9}]]

        monkeypatch.setattr(
            "pipeline.audio_module._get_sentiment_pipe", lambda: _FlakyPipe()
        )
        segs = [
            {"segment_id": i, "start_time": float(i), "end_time": i + 1.0, "text": "x y z"}
            for i in range(3)
        ]
        out = add_transcript_sentiment(segs)
        assert [s["transcript_sentiment"]["label"] for s in out] == [
            "POSITIVE", "NEUTRAL", "POSITIVE"
        ]

    def test_model_id_is_the_adopted_winner(self):
        # Guards against an accidental revert of the bench's decision.
        from pipeline import audio_module

        assert audio_module.SENTIMENT_MODEL_ID == (
            "cardiffnlp/twitter-xlm-roberta-base-sentiment"
        )
        assert not hasattr(audio_module, "NEUTRAL_CONFIDENCE_THRESHOLD"), (
            "the confidence threshold was removed by the transcript bench, not retuned"
        )


# ── _load_wav_int16: every sample format lands in the int16 range ───────────────

class TestLoadWavInt16:
    """
    The pipeline's own audio is 16-bit PCM and must pass through untouched. Until
    26 Sep 2026 other formats were "converted" by dividing by 32767, which turned
    a float WAV into silence and overflowed 32-bit audio.
    """

    @staticmethod
    def _write(tmp_path, data, name="x.wav"):
        from scipy.io import wavfile
        path = tmp_path / name
        wavfile.write(str(path), SR, data)
        return path

    def test_int16_mono_is_returned_unchanged(self, tmp_path):
        from pipeline.audio_module import _load_wav_int16
        data = (np.sin(np.linspace(0, 40, SR)) * 20000).astype(np.int16)
        out, sr = _load_wav_int16(self._write(tmp_path, data))
        assert sr == SR and out.dtype == np.int16
        assert np.array_equal(out, data)

    def test_int16_stereo_is_averaged_as_before(self, tmp_path):
        from pipeline.audio_module import _load_wav_int16
        left = np.full(100, 1000, dtype=np.int16)
        right = np.full(100, 3001, dtype=np.int16)
        out, _ = _load_wav_int16(self._write(tmp_path, np.stack([left, right], axis=1)))
        assert out.dtype == np.int16 and set(out.tolist()) == {2000}

    def test_float_audio_keeps_its_level(self, tmp_path):
        from pipeline.audio_module import _load_wav_int16
        data = (0.5 * np.sin(np.linspace(0, 40, SR))).astype(np.float32)
        out, _ = _load_wav_int16(self._write(tmp_path, data))
        assert out.dtype == np.int16
        assert 16000 < int(np.abs(out).max()) <= 16384        # half scale, not silence

    def test_int32_audio_is_scaled_not_wrapped(self, tmp_path):
        from pipeline.audio_module import _load_wav_int16
        data = np.array([2 ** 30, -(2 ** 30), 0], dtype=np.int32)
        out, _ = _load_wav_int16(self._write(tmp_path, data))
        assert out.tolist() == [16384, -16384, 0]

    def test_unsigned_8_bit_audio_is_centred(self, tmp_path):
        from pipeline.audio_module import _load_wav_int16
        out, _ = _load_wav_int16(self._write(tmp_path, np.array([128, 255, 0], dtype=np.uint8)))
        assert out.tolist() == [0, 32512, -32768]
