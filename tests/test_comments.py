"""
Tests for pipeline/comment_module.py

Pass criteria (per project spec):
  - fetch_comments: correct pagination, no author leakage, EnvironmentError on missing key
  - tabularisai: all 5 raw labels map correctly; empty text → NEUTRAL; no crash on emoji/CJK
  - aggregate_video_sentiment: correct majority vote, tie → NEUTRAL, distribution math

Model-dependent tests (classify_comment_sentiment) are skipped automatically when
transformers is not installed, so pytest never errors in a bare environment.

fetch_comments tests use unittest.mock — no real API key or network access needed.
aggregate_video_sentiment tests use only pure Python — no model download needed.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from pipeline.comment_module import (
    aggregate_video_sentiment,
    classify_comment_sentiment,
    fetch_comments,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_comment(cid: str, text: str, label: str = "POSITIVE", conf: float = 0.9) -> dict:
    return {
        "comment_id":           cid,
        "text":                 text,
        "like_count":           0,
        "published_at":         "2024-01-01",
        "sentiment_label":      label,
        "sentiment_confidence": conf,
    }


def _api_page(items: list[dict], next_page_token: str | None = None) -> dict:
    """Build a minimal fake commentThreads.list response."""
    return {
        "items": [
            {
                "id": item["id"],
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "textDisplay":  item["text"],
                            "likeCount":    item.get("likes", 0),
                            "publishedAt":  "2024-01-01T00:00:00.000Z",
                        }
                    }
                },
            }
            for item in items
        ],
        **({"nextPageToken": next_page_token} if next_page_token else {}),
    }


# ── fetch_comments ────────────────────────────────────────────────────────────

class TestFetchComments:
    """Uses unittest.mock — no API key or network access required."""

    def _mock_youtube(self, pages: list[dict]):
        """
        Return a mock youtube client whose commentThreads().list().execute()
        returns successive pages from the given list.
        """
        mock_yt = MagicMock()
        execute_mock = MagicMock(side_effect=pages)
        mock_yt.commentThreads.return_value.list.return_value.execute = execute_mock
        return mock_yt

    def test_returns_list_of_dicts(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
        page = _api_page([{"id": "c1", "text": "Great video!"}])
        mock_yt = self._mock_youtube([page])

        with patch("pipeline.comment_module.build", return_value=mock_yt):
            result = fetch_comments("dQw4w9WgXcQ", max_results=5)

        assert isinstance(result, list)
        assert len(result) == 1

    def test_result_has_required_keys(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
        page = _api_page([{"id": "c1", "text": "Hello"}])
        mock_yt = self._mock_youtube([page])

        with patch("pipeline.comment_module.build", return_value=mock_yt):
            result = fetch_comments("dQw4w9WgXcQ", max_results=5)

        assert set(result[0].keys()) == {"comment_id", "text", "like_count", "published_at"}

    def test_no_author_fields_in_result(self, monkeypatch):
        """Data minimisation: author identifiers must never appear in output."""
        monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
        page = _api_page([{"id": "c1", "text": "Hello"}])
        mock_yt = self._mock_youtube([page])

        with patch("pipeline.comment_module.build", return_value=mock_yt):
            result = fetch_comments("dQw4w9WgXcQ", max_results=5)

        for comment in result:
            assert "authorDisplayName" not in comment
            assert "authorChannelId" not in comment

    def test_paginates_until_max_results(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
        page1 = _api_page(
            [{"id": f"c{i}", "text": f"comment {i}"} for i in range(3)],
            next_page_token="TOKEN2",
        )
        page2 = _api_page(
            [{"id": f"c{i}", "text": f"comment {i}"} for i in range(3, 5)],
        )
        mock_yt = self._mock_youtube([page1, page2])

        with patch("pipeline.comment_module.build", return_value=mock_yt):
            result = fetch_comments("dQw4w9WgXcQ", max_results=10)

        assert len(result) == 5

    def test_stops_when_no_next_page_token(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
        page = _api_page([{"id": "c1", "text": "Only comment"}])
        mock_yt = self._mock_youtube([page])

        with patch("pipeline.comment_module.build", return_value=mock_yt):
            result = fetch_comments("dQw4w9WgXcQ", max_results=100)

        assert len(result) == 1

    def test_empty_video_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
        page = {"items": []}
        mock_yt = self._mock_youtube([page])

        with patch("pipeline.comment_module.build", return_value=mock_yt):
            result = fetch_comments("dQw4w9WgXcQ", max_results=10)

        assert result == []

    def test_missing_api_key_raises_environment_error(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="YOUTUBE_API_KEY"):
            fetch_comments("dQw4w9WgXcQ")


# ── classify_comment_sentiment ─────────────────────────────────────────────────

class TestResolveModelId:
    """
    Model resolution and its fallback path.

    The adopted comment-sentiment model is ~479 MB of fine-tuned weights that are not
    committed. A fresh clone will not have them, so the module must degrade to the
    public base checkpoint and log a warning rather than fail. That is the
    graceful-degradation requirement applied to model loading.
    """

    def test_uses_finetuned_weights_when_present(self, tmp_path):
        import pipeline.comment_module as cm
        (tmp_path / "config.json").write_text("{}")
        with patch.object(cm, "_FINETUNED_DIR", tmp_path):
            assert cm._resolve_model_id() == str(tmp_path)

    def test_falls_back_to_base_when_weights_missing(self, tmp_path):
        import pipeline.comment_module as cm
        with patch.object(cm, "_FINETUNED_DIR", tmp_path / "does_not_exist"):
            assert cm._resolve_model_id() == cm._BASE_MODEL_ID

    def test_falls_back_when_directory_exists_but_is_empty(self, tmp_path):
        """A directory without config.json is an incomplete download, not a model."""
        import pipeline.comment_module as cm
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch.object(cm, "_FINETUNED_DIR", empty):
            assert cm._resolve_model_id() == cm._BASE_MODEL_ID

    def test_fallback_warns(self, tmp_path, caplog):
        """The degradation must be visible in the logs, not silent."""
        import logging
        import pipeline.comment_module as cm
        with patch.object(cm, "_FINETUNED_DIR", tmp_path / "missing"):
            with caplog.at_level(logging.WARNING):
                cm._resolve_model_id()
        assert any("falling back" in r.message.lower() or "falling back" in r.getMessage().lower()
                   for r in caplog.records)


class TestClassifyCommentSentiment:
    """Model-dependent — skipped automatically when transformers is absent."""

    # Every raw label cardiffnlp/twitter-roberta-base-sentiment-latest can produce,
    # with the expected 3-class mapping. The model emits lowercase names; older
    # revisions of the same checkpoint emit LABEL_0/1/2 in the order negative,
    # neutral, positive, and both spellings must map identically.
    # Updated 28 Aug 2026 when the ten-model bench replaced the previous 5-class
    # model — see comment_bench/v2/HUMAN_GROUND_TRUTH_EVALUATION.md.
    _LABEL_CASES = [
        ("positive", "POSITIVE"),
        ("neutral",  "NEUTRAL"),
        ("negative", "NEGATIVE"),
        ("POSITIVE", "POSITIVE"),   # case-insensitive lookup
        ("Negative", "NEGATIVE"),
        ("LABEL_0",  "NEGATIVE"),   # legacy revision spelling
        ("LABEL_1",  "NEUTRAL"),
        ("LABEL_2",  "POSITIVE"),
    ]

    def _mock_pipe(self, raw_label: str, score: float = 0.95):
        """Return a callable that mimics the HuggingFace pipeline output format."""
        return MagicMock(return_value=[[{"label": raw_label, "score": score}]])

    @pytest.mark.parametrize("raw_label,expected", _LABEL_CASES)
    def test_label_mapping(self, raw_label: str, expected: str):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "test text", "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe", return_value=self._mock_pipe(raw_label)):
            result = classify_comment_sentiment(comment)

        assert result[0]["sentiment_label"] == expected

    def test_empty_text_returns_neutral(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "", "like_count": 0, "published_at": "2024-01-01"}]
        with patch("pipeline.comment_module._get_sentiment_pipe", return_value=self._mock_pipe("positive")):
            result = classify_comment_sentiment(comment)
        assert result[0]["sentiment_label"] == "NEUTRAL"
        assert result[0]["sentiment_confidence"] == 0.0

    def test_whitespace_only_returns_neutral(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "   ", "like_count": 0, "published_at": "2024-01-01"}]
        with patch("pipeline.comment_module._get_sentiment_pipe", return_value=self._mock_pipe("positive")):
            result = classify_comment_sentiment(comment)
        assert result[0]["sentiment_label"] == "NEUTRAL"

    def test_required_keys_present(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "Nice!", "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("Positive")):
            result = classify_comment_sentiment(comment)

        assert "sentiment_label" in result[0]
        assert "sentiment_confidence" in result[0]

    def test_original_keys_preserved(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "42", "text": "OK", "like_count": 7, "published_at": "2024-06-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("Neutral")):
            result = classify_comment_sentiment(comment)

        assert result[0]["comment_id"] == "42"
        assert result[0]["like_count"] == 7

    def test_emoji_does_not_crash(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "Amazing! 🔥🎉🤩", "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("positive")):
            result = classify_comment_sentiment(comment)

        assert result[0]["sentiment_label"] == "POSITIVE"

    def test_unknown_label_degrades_to_neutral(self):
        """
        A raw label outside _LABEL_MAP must fall back to NEUTRAL rather than raise.

        Guards the model-swap failure path: if the checkpoint is ever replaced by
        one with a different label vocabulary, the pipeline degrades gracefully
        instead of aborting the run (graceful-degradation requirement).
        """
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "test text", "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("Very Positive")):
            result = classify_comment_sentiment(comment)

        assert result[0]["sentiment_label"] == "NEUTRAL"

    def test_cjk_text_does_not_crash(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "不好用，很失望", "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("Negative")):
            result = classify_comment_sentiment(comment)

        assert result[0]["sentiment_label"] == "NEGATIVE"

    def test_long_text_truncated_to_512_chars(self):
        """Model must not crash on text longer than 512 chars."""
        pytest.importorskip("transformers")
        long_text = "x" * 1000
        comment = [{"comment_id": "1", "text": long_text, "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("Neutral")) as mock_pipe:
            classify_comment_sentiment(comment)
            # The pipe was called with a string of at most 512 chars
            call_args = mock_pipe.return_value.call_args[0][0]
            assert len(call_args) <= 512

    def test_confidence_between_zero_and_one(self):
        pytest.importorskip("transformers")
        comment = [{"comment_id": "1", "text": "Great!", "like_count": 0, "published_at": "2024-01-01"}]

        with patch("pipeline.comment_module._get_sentiment_pipe",
                   return_value=self._mock_pipe("Positive", score=0.87)):
            result = classify_comment_sentiment(comment)

        assert 0.0 <= result[0]["sentiment_confidence"] <= 1.0

    def test_empty_input_returns_empty_list(self):
        pytest.importorskip("transformers")
        assert classify_comment_sentiment([]) == []


# ── aggregate_video_sentiment (pure logic, no model) ─────────────────────────

class TestAggregateVideoSentiment:
    def test_empty_input_returns_neutral_defaults(self):
        result = aggregate_video_sentiment([])
        assert result["label"] == "NEUTRAL"
        assert result["confidence"] == 0.0
        assert result["comment_count"] == 0
        assert result["distribution"] == {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}

    def test_majority_positive(self):
        comments = [
            _make_comment("1", "Great!", "POSITIVE", 0.9),
            _make_comment("2", "Love it", "POSITIVE", 0.8),
            _make_comment("3", "Terrible", "NEGATIVE", 0.7),
        ]
        result = aggregate_video_sentiment(comments)
        assert result["label"] == "POSITIVE"

    def test_majority_negative(self):
        comments = [
            _make_comment("1", "Bad",      "NEGATIVE", 0.9),
            _make_comment("2", "Terrible", "NEGATIVE", 0.85),
            _make_comment("3", "OK",       "NEUTRAL",  0.6),
        ]
        result = aggregate_video_sentiment(comments)
        assert result["label"] == "NEGATIVE"

    def test_tie_resolves_to_neutral(self):
        """When POSITIVE and NEGATIVE are equal, label must be NEUTRAL."""
        comments = [
            _make_comment("1", "Great!",    "POSITIVE", 0.9),
            _make_comment("2", "Terrible!", "NEGATIVE", 0.9),
        ]
        result = aggregate_video_sentiment(comments)
        assert result["label"] == "NEUTRAL"

    def test_three_way_tie_resolves_to_neutral(self):
        comments = [
            _make_comment("1", "a", "POSITIVE", 0.8),
            _make_comment("2", "b", "NEUTRAL",  0.8),
            _make_comment("3", "c", "NEGATIVE", 0.8),
        ]
        result = aggregate_video_sentiment(comments)
        assert result["label"] == "NEUTRAL"

    def test_distribution_counts_correct(self):
        comments = [
            _make_comment("1", "a", "POSITIVE", 0.9),
            _make_comment("2", "b", "POSITIVE", 0.8),
            _make_comment("3", "c", "NEGATIVE", 0.7),
            _make_comment("4", "d", "NEUTRAL",  0.6),
        ]
        result = aggregate_video_sentiment(comments)
        assert result["distribution"]["POSITIVE"] == 2
        assert result["distribution"]["NEGATIVE"] == 1
        assert result["distribution"]["NEUTRAL"] == 1

    def test_distribution_sums_to_comment_count(self):
        comments = [
            _make_comment("1", "a", "POSITIVE", 0.9),
            _make_comment("2", "b", "NEUTRAL",  0.6),
            _make_comment("3", "c", "NEGATIVE", 0.7),
        ]
        result = aggregate_video_sentiment(comments)
        total = sum(result["distribution"].values())
        assert total == result["comment_count"]

    def test_comment_count_matches_input_length(self):
        comments = [_make_comment(str(i), "text", "POSITIVE", 0.8) for i in range(7)]
        result = aggregate_video_sentiment(comments)
        assert result["comment_count"] == 7

    def test_mean_confidence_across_all_comments(self):
        """Mean confidence is across ALL comments, not just the majority class."""
        comments = [
            _make_comment("1", "a", "POSITIVE", 0.80),
            _make_comment("2", "b", "POSITIVE", 0.60),
            _make_comment("3", "c", "NEGATIVE", 0.40),
        ]
        result = aggregate_video_sentiment(comments)
        # (0.80 + 0.60 + 0.40) / 3 = 0.60
        assert abs(result["confidence"] - 0.60) < 1e-3

    def test_confidence_between_zero_and_one(self):
        comments = [_make_comment(str(i), "text", "POSITIVE", 0.75) for i in range(5)]
        result = aggregate_video_sentiment(comments)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_required_keys_present(self):
        result = aggregate_video_sentiment([])
        assert set(result.keys()) == {"label", "confidence", "comment_count", "distribution"}

    def test_unknown_label_counted_as_neutral(self):
        """If a comment somehow has an unrecognised label, it should count as NEUTRAL."""
        comment = {
            "comment_id": "1", "text": "hmm", "like_count": 0, "published_at": "2024-01-01",
            "sentiment_label": "UNKNOWN_CLASS", "sentiment_confidence": 0.5,
        }
        result = aggregate_video_sentiment([comment])
        assert result["distribution"]["NEUTRAL"] == 1
