"""
Tests for pipeline/visual_module.py

Pass criteria (per project spec):
  - YOLOv8: detects expected class in 100% of positive frames; no crash on empty/bad frames
  - DeepFace: returns emotion dict when face present; no-face dict (no crash) when absent
  - pool_emotions_per_segment: correct majority-vote logic, graceful empty-window handling

Model-dependent tests (YOLOv8, DeepFace) require the packages installed and are
skipped automatically when the imports are absent, so pytest never errors in a
bare environment.

Pool / timestamp tests use no models at all — they run immediately.
"""

from __future__ import annotations

import struct
import tempfile
import wave
from pathlib import Path

import pytest

from pipeline.visual_module import (
    FACE_CONFIDENCE_THRESHOLD,
    FACE_DETECTOR_BACKEND,
    FACIAL_CHANNEL_RELIABILITY,
    _timestamp_from_path,
    analyse_facial_emotion,
    detect_logos,
    pool_emotions_per_segment,
)


class TestAdoptedDetectorBackend:
    """
    The face detector was chosen by measurement on 03 Sep 2026, not by default.

    `facial_bench/` scored six backends over all 572 frames of the ground-truth
    video against the author's own review; `yunet` won under the rule
    pre-registered before any of them ran. These tests exist so the constant
    cannot drift back to a default without someone deciding to.
    """

    def test_the_benched_winner_is_what_the_pipeline_runs(self):
        assert FACE_DETECTOR_BACKEND == "yunet"

    def test_the_superseded_backend_is_not_hard_coded_anywhere(self):
        src = Path(__file__).resolve().parent.parent / "pipeline" / "visual_module.py"
        body = src.read_text()
        assert 'detector_backend="opencv"' not in body
        assert "detector_backend=FACE_DETECTOR_BACKEND" in body

    def test_the_confidence_gate_is_unchanged_by_the_swap(self):
        # Measured: opencv's lowest confidence on this footage was 0.88 and
        # yunet's 0.90, so the gate is inert for both and the swap does not
        # silently change two things at once.
        assert FACE_CONFIDENCE_THRESHOLD == 0.50


# ── Helpers ───────────────────────────────────────────────────────────────────

def _solid_jpeg(path: Path, width: int = 64, height: int = 64,
                color: tuple[int, int, int] = (128, 200, 100)) -> Path:
    """
    Write a solid-colour JPEG using only stdlib + numpy (no Pillow required).
    Falls back to Pillow if available for a real JPEG header.
    Returns path.
    """
    try:
        from PIL import Image
        img = Image.new("RGB", (width, height), color)
        img.save(str(path), "JPEG")
    except ImportError:
        import numpy as np
        import cv2
        arr = np.full((height, width, 3), color[::-1], dtype=np.uint8)  # BGR
        cv2.imwrite(str(path), arr)
    return path


def _make_frame(tmp_path: Path, index: int,
                color: tuple[int, int, int] = (128, 200, 100)) -> Path:
    """Create a synthetic frame_{index:04d}.jpg at tmp_path."""
    p = tmp_path / f"frame_{index:04d}.jpg"
    _solid_jpeg(p, color=color)
    return p


# ── Timestamp helper (no models needed) ──────────────────────────────────────

class TestTimestampFromPath:
    def test_standard_naming(self, tmp_path):
        p = tmp_path / "frame_0042.jpg"
        assert _timestamp_from_path(p) == 42.0

    def test_zero_index(self, tmp_path):
        p = tmp_path / "frame_0000.jpg"
        assert _timestamp_from_path(p) == 0.0

    def test_large_index(self, tmp_path):
        p = tmp_path / "frame_0599.jpg"
        assert _timestamp_from_path(p) == 599.0

    def test_unexpected_name_defaults_zero(self, tmp_path):
        p = tmp_path / "random_name.jpg"
        assert _timestamp_from_path(p) == 0.0


# ── pool_emotions_per_segment (pure logic, no models) ────────────────────────

class TestPoolEmotionsPerSegment:
    """These tests use hand-crafted frame_emotions dicts — no model download."""

    def _seg(self, sid: int, start: float, end: float) -> dict:
        return {"segment_id": sid, "start_time": start, "end_time": end, "text": "test"}

    def test_facial_emotion_key_added_to_every_segment(self):
        frame_emotions = [
            {"frame": "frame_0001.jpg", "timestamp_s": 1.0, "dominant_emotion": "happy", "confidence": 0.8},
        ]
        segs = [self._seg(0, 0.0, 5.0)]
        result = pool_emotions_per_segment(frame_emotions, segs)
        assert "facial_emotion" in result[0]

    def test_majority_vote_selects_most_frequent_emotion(self):
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 0.5, "dominant_emotion": "happy",   "confidence": 0.9},
            {"frame": "f1.jpg", "timestamp_s": 1.5, "dominant_emotion": "happy",   "confidence": 0.8},
            {"frame": "f2.jpg", "timestamp_s": 2.5, "dominant_emotion": "disgust", "confidence": 0.7},
        ]
        segs = [self._seg(0, 0.0, 3.0)]
        result = pool_emotions_per_segment(frame_emotions, segs)
        assert result[0]["facial_emotion"]["dominant"] == "happy"

    def test_mean_confidence_of_dominant_only(self):
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 0.5, "dominant_emotion": "happy", "confidence": 0.80},
            {"frame": "f1.jpg", "timestamp_s": 1.5, "dominant_emotion": "happy", "confidence": 0.60},
            {"frame": "f2.jpg", "timestamp_s": 2.5, "dominant_emotion": "sad",   "confidence": 0.95},
        ]
        segs = [self._seg(0, 0.0, 3.0)]
        result = pool_emotions_per_segment(frame_emotions, segs)
        fe = result[0]["facial_emotion"]
        assert fe["dominant"] == "happy"
        # Mean of 0.80 and 0.60 only (sad excluded)
        assert abs(fe["confidence"] - 0.70) < 1e-3

    def test_no_face_in_window_returns_none(self):
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 10.0, "dominant_emotion": "happy", "confidence": 0.9},
        ]
        segs = [self._seg(0, 0.0, 5.0)]  # window [0, 5) — no frames inside
        result = pool_emotions_per_segment(frame_emotions, segs)
        fe = result[0]["facial_emotion"]
        assert fe["dominant"] is None
        assert fe["confidence"] == 0.0
        assert fe["frame_count"] == 0

    def test_frames_with_none_emotion_ignored(self):
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 1.0, "dominant_emotion": None,    "confidence": 0.0},
            {"frame": "f1.jpg", "timestamp_s": 2.0, "dominant_emotion": "angry", "confidence": 0.75},
        ]
        segs = [self._seg(0, 0.0, 3.0)]
        result = pool_emotions_per_segment(frame_emotions, segs)
        fe = result[0]["facial_emotion"]
        assert fe["dominant"] == "angry"
        assert fe["frame_count"] == 1  # only the frame with a real detection

    def test_all_frames_none_emotion_returns_empty(self):
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 1.0, "dominant_emotion": None, "confidence": 0.0},
            {"frame": "f1.jpg", "timestamp_s": 2.0, "dominant_emotion": None, "confidence": 0.0},
        ]
        segs = [self._seg(0, 0.0, 3.0)]
        result = pool_emotions_per_segment(frame_emotions, segs)
        assert result[0]["facial_emotion"]["dominant"] is None

    def test_frame_exactly_at_end_time_excluded(self):
        """[start, end) window — end_time frame must NOT be included."""
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 3.0, "dominant_emotion": "happy", "confidence": 0.9},
        ]
        segs = [self._seg(0, 0.0, 3.0)]  # end_time == 3.0, frame at 3.0 excluded
        result = pool_emotions_per_segment(frame_emotions, segs)
        assert result[0]["facial_emotion"]["dominant"] is None

    def test_multiple_segments_independent(self):
        frame_emotions = [
            {"frame": "f0.jpg", "timestamp_s": 1.0, "dominant_emotion": "happy",   "confidence": 0.9},
            {"frame": "f1.jpg", "timestamp_s": 6.0, "dominant_emotion": "disgust", "confidence": 0.8},
        ]
        segs = [self._seg(0, 0.0, 3.0), self._seg(1, 5.0, 8.0)]
        result = pool_emotions_per_segment(frame_emotions, segs)
        assert result[0]["facial_emotion"]["dominant"] == "happy"
        assert result[1]["facial_emotion"]["dominant"] == "disgust"

    def test_returns_same_list_object(self):
        """pool_emotions_per_segment modifies in-place."""
        segs = [self._seg(0, 0.0, 5.0)]
        returned = pool_emotions_per_segment([], segs)
        assert returned is segs

    def test_facial_emotion_dict_has_required_keys(self):
        segs = [self._seg(0, 0.0, 5.0)]
        result = pool_emotions_per_segment([], segs)
        fe = result[0]["facial_emotion"]
        assert set(fe.keys()) == {"dominant", "confidence", "frame_count",
                                  "reliability"}

    def test_reliability_is_attached_whether_or_not_a_face_was_found(self):
        # Mirrors the vocal channel (tests/test_audio.py). The orchestrator damps
        # a conflict resting on this channel alone by exactly this figure, so the
        # segment must carry it in both branches - a segment with no face is still
        # a segment this channel reported on.
        empty = pool_emotions_per_segment([], [self._seg(0, 0.0, 5.0)])
        assert empty[0]["facial_emotion"]["reliability"] == FACIAL_CHANNEL_RELIABILITY
        assert empty[0]["facial_emotion"]["dominant"] is None

        frames = [{"frame": "f0.jpg", "timestamp_s": 1.0,
                   "dominant_emotion": "happy", "confidence": 0.9}]
        faced = pool_emotions_per_segment(frames, [self._seg(0, 0.0, 5.0)])
        assert faced[0]["facial_emotion"]["reliability"] == FACIAL_CHANNEL_RELIABILITY
        assert faced[0]["facial_emotion"]["dominant"] == "happy"


# ── analyse_facial_emotion (DeepFace — model download required) ───────────────

class TestAnalyseFacialEmotion:
    def test_returns_one_dict_per_frame(self, tmp_path):
        pytest.importorskip("deepface")
        frames = [_make_frame(tmp_path, i) for i in range(3)]
        result = analyse_facial_emotion(frames)
        assert len(result) == 3

    def test_no_crash_on_blank_frame(self, tmp_path):
        """Solid-colour frame has no face — must return None, not raise."""
        pytest.importorskip("deepface")
        frame = _make_frame(tmp_path, 0, color=(128, 128, 128))
        result = analyse_facial_emotion([frame])
        assert len(result) == 1
        assert result[0]["dominant_emotion"] is None
        assert result[0]["confidence"] == 0.0

    def test_no_crash_on_missing_frame(self, tmp_path):
        pytest.importorskip("deepface")
        missing = tmp_path / "frame_0099.jpg"
        result = analyse_facial_emotion([missing])
        assert result[0]["dominant_emotion"] is None

    def test_each_result_has_required_keys(self, tmp_path):
        pytest.importorskip("deepface")
        frame = _make_frame(tmp_path, 5)
        result = analyse_facial_emotion([frame])
        for r in result:
            assert "frame" in r
            assert "timestamp_s" in r
            assert "dominant_emotion" in r
            assert "confidence" in r

    def test_timestamp_extracted_from_filename(self, tmp_path):
        pytest.importorskip("deepface")
        frame = _make_frame(tmp_path, 7)
        result = analyse_facial_emotion([frame])
        assert result[0]["timestamp_s"] == 7.0

    def test_empty_frames_returns_empty_list(self):
        pytest.importorskip("deepface")
        result = analyse_facial_emotion([])
        assert result == []

    def test_confidence_between_zero_and_one(self, tmp_path):
        pytest.importorskip("deepface")
        frame = _make_frame(tmp_path, 0)
        result = analyse_facial_emotion([frame])
        for r in result:
            assert 0.0 <= r["confidence"] <= 1.0


# ── detect_logos (YOLOv8 — model download required) ──────────────────────────

class TestDetectLogos:
    def test_returns_list(self, tmp_path):
        pytest.importorskip("ultralytics")
        frame = _make_frame(tmp_path, 0)
        result = detect_logos([frame], brand_name="person")
        assert isinstance(result, list)

    def test_no_crash_on_blank_frame(self, tmp_path):
        """Blank frame should return empty list, not raise."""
        pytest.importorskip("ultralytics")
        frame = _make_frame(tmp_path, 0)
        result = detect_logos([frame], brand_name="nike")
        assert result == []

    def test_no_crash_on_missing_frame(self, tmp_path):
        pytest.importorskip("ultralytics")
        missing = tmp_path / "frame_0099.jpg"
        result = detect_logos([missing], brand_name="person")
        assert isinstance(result, list)

    def test_detection_dict_has_required_keys(self, tmp_path):
        """If any detection is returned, it must have all required keys."""
        pytest.importorskip("ultralytics")
        frame = _make_frame(tmp_path, 0)
        result = detect_logos([frame], brand_name="person")
        for det in result:
            assert "frame" in det
            assert "timestamp_s" in det
            assert "label" in det
            assert "confidence" in det

    def test_empty_frames_returns_empty(self):
        pytest.importorskip("ultralytics")
        result = detect_logos([], brand_name="person")
        assert result == []

    def test_confidence_between_zero_and_one(self, tmp_path):
        pytest.importorskip("ultralytics")
        frame = _make_frame(tmp_path, 0)
        result = detect_logos([frame], brand_name="person")
        for det in result:
            assert 0.0 <= det["confidence"] <= 1.0
