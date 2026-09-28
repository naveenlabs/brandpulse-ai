"""
Tests for app.py — Flask /analyse endpoint

All tests use Flask's test client — no real network, no YouTube API key,
no Ollama process required.

Mocking strategy:
  - fetch_comments          → patched at app.fetch_comments
  - classify_comment_sentiment → patched at app.classify_comment_sentiment
  - aggregate_video_sentiment  → patched at app.aggregate_video_sentiment
  - run_orchestration       → patched at app.run_orchestration

build_final_report and scorer functions run for real (pure arithmetic,
no external dependencies).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app import app as flask_app


# ── Fixtures ──────────────────────────────────────────────────────────────────

VALID_WATCH_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VALID_SHORT_URL = "https://youtu.be/dQw4w9WgXcQ"
INVALID_URL     = "https://example.com/not-youtube"

_EMPTY_COMMENT_SENTIMENT = {
    "label":         "NEUTRAL",
    "confidence":    0.0,
    "comment_count": 0,
    "distribution":  {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
}

REQUIRED_REPORT_KEYS = {
    "video_url", "brand_name", "authenticity_score", "brand_health_score",
    "segment_count", "flagged_segments", "comment_sentiment", "bias_caveat",
}


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


_STUB_SEGMENTS = [
    {"start": 0.0,  "end": 5.0,  "text": "This phone is amazing.",  "sentiment": "POSITIVE", "vocal_emotion": "happy",   "facial_emotion": "happy",   "pitch_mean": 180.0, "energy_mean": 0.06},
    {"start": 5.0,  "end": 10.0, "text": "The camera is decent.",   "sentiment": "NEUTRAL",  "vocal_emotion": "neutral", "facial_emotion": "neutral", "pitch_mean": 160.0, "energy_mean": 0.04},
    {"start": 10.0, "end": 15.0, "text": "Battery life is awful.",  "sentiment": "NEGATIVE", "vocal_emotion": "sad",     "facial_emotion": "sad",     "pitch_mean": 140.0, "energy_mean": 0.03},
]


def _pipeline_mocks(
    comments: list = None,
    classified: list = None,
    sentiment: dict = None,
    conflict_results: list = None,
    segments: list = None,
):
    """Return a context-manager stack that patches all pipeline functions."""
    return (
        patch("app.fetch_comments",              return_value=comments or []),
        patch("app.classify_comment_sentiment",  return_value=classified or []),
        patch("app.aggregate_video_sentiment",   return_value=sentiment or _EMPTY_COMMENT_SENTIMENT),
        patch("app.run_orchestration",           return_value=conflict_results or []),
        patch("app._build_segments",             return_value=segments or _STUB_SEGMENTS),
        patch("app._save_report",                return_value=None),
    )


def _post(client, body: dict):
    return client.post(
        "/analyse",
        data=json.dumps(body),
        content_type="application/json",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAnalyseEndpoint:
    def test_valid_body_returns_200(self, client):
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        assert resp.status_code == 200

    def test_valid_body_returns_all_required_keys(self, client):
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        data = resp.get_json()
        assert REQUIRED_REPORT_KEYS.issubset(set(data.keys()))

    def test_missing_video_url_returns_400(self, client):
        resp = _post(client, {"brand_name": "Acme"})
        assert resp.status_code == 400
        assert "video_url" in resp.get_json()["error"]

    def test_missing_brand_name_returns_400(self, client):
        resp = _post(client, {"video_url": VALID_WATCH_URL})
        assert resp.status_code == 400
        assert "brand_name" in resp.get_json()["error"]

    def test_watch_url_returns_200(self, client):
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        assert resp.status_code == 200

    def test_short_url_returns_200(self, client):
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_SHORT_URL, "brand_name": "Acme"})
        assert resp.status_code == 200

    def test_invalid_url_returns_400(self, client):
        resp = _post(client, {"video_url": INVALID_URL, "brand_name": "Acme"})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid video_url"

    def test_environment_error_returns_500(self, client):
        with patch("app.fetch_comments", side_effect=EnvironmentError("YOUTUBE_API_KEY not set")):
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        assert resp.status_code == 500
        body = resp.get_json()
        assert "error" in body

    def test_video_url_passed_through_to_report(self, client):
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Nike"})
        data = resp.get_json()
        assert data["video_url"] == VALID_WATCH_URL
        assert data["brand_name"] == "Nike"

    def test_max_comments_default_100(self, client):
        """fetch_comments must be called with max_results=100 when not supplied."""
        fc = patch("app.fetch_comments", return_value=[])
        cc = patch("app.classify_comment_sentiment", return_value=[])
        av = patch("app.aggregate_video_sentiment", return_value=_EMPTY_COMMENT_SENTIMENT)
        ro = patch("app.run_orchestration", return_value=[])
        bs = patch("app._build_segments", return_value=_STUB_SEGMENTS)
        sr = patch("app._save_report", return_value=None)
        with fc as mock_fc, cc, av, ro, bs, sr:
            _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        mock_fc.assert_called_once_with("dQw4w9WgXcQ", max_results=100)

    def test_max_comments_custom(self, client):
        """max_comments from request body is forwarded to fetch_comments."""
        fc = patch("app.fetch_comments", return_value=[])
        cc = patch("app.classify_comment_sentiment", return_value=[])
        av = patch("app.aggregate_video_sentiment", return_value=_EMPTY_COMMENT_SENTIMENT)
        ro = patch("app.run_orchestration", return_value=[])
        bs = patch("app._build_segments", return_value=_STUB_SEGMENTS)
        sr = patch("app._save_report", return_value=None)
        with fc as mock_fc, cc, av, ro, bs, sr:
            _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme", "max_comments": 50})
        mock_fc.assert_called_once_with("dQw4w9WgXcQ", max_results=50)

    def test_segment_count_from_stub_segments(self, client):
        """The stub provides 3 segments — segment_count must be 3."""
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        assert resp.get_json()["segment_count"] == 3

    def test_pipeline_error_returns_500(self, client):
        with patch("app.run_orchestration", side_effect=RuntimeError("Ollama down")):
            fc = patch("app.fetch_comments", return_value=[])
            cc = patch("app.classify_comment_sentiment", return_value=[])
            av = patch("app.aggregate_video_sentiment", return_value=_EMPTY_COMMENT_SENTIMENT)
            bs = patch("app._build_segments", return_value=_STUB_SEGMENTS)
            sr = patch("app._save_report", return_value=None)
            with fc, cc, av, bs, sr:
                resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        assert resp.status_code == 500
        body = resp.get_json()
        assert "error" in body
        assert "detail" in body

    def test_empty_body_returns_400(self, client):
        resp = _post(client, {})
        assert resp.status_code == 400

    def test_content_type_is_json(self, client):
        fc, cc, av, ro, bs, sr = _pipeline_mocks()
        with fc, cc, av, ro, bs, sr:
            resp = _post(client, {"video_url": VALID_WATCH_URL, "brand_name": "Acme"})
        assert "application/json" in resp.content_type
