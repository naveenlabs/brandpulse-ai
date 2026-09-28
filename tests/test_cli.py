"""
main.py, the command-line entry point: system tests with the models mocked.

The download, the four channels and the controller are replaced at main.py's
import boundary, as test_app.py does for the Flask routes; the scoring
arithmetic and the report file are real.
"""

from __future__ import annotations

import json
import sys

import pytest

import main as M
from pipeline.scorer import BIAS_CAVEAT
from pipeline.youtube_api import YouTubeAPIError


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    seen = {}

    def download(url, video_dir, fps):
        seen["url"], seen["video_dir"] = url, video_dir
        return {"frame_paths": [], "audio_path": video_dir / "audio.wav",
                "frame_count": 0, "duration_s": 5.0}

    monkeypatch.setattr(M, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(M, "downloader_run", download)
    monkeypatch.setattr(M, "analyse_facial_emotion", lambda frames: [])
    monkeypatch.setattr(M, "build_audio_channel", lambda audio: [
        {"segment_id": 0, "start_time": 0.0, "end_time": 5.0, "text": "fine"}])
    monkeypatch.setattr(M, "pool_emotions_per_segment", lambda emotions, segments: segments)
    monkeypatch.setattr(M, "fetch_comments", lambda video_id, max_results: [])
    monkeypatch.setattr(M, "classify_comment_sentiment", lambda comments: [])
    monkeypatch.setattr(M, "run_orchestration", lambda segments, sentiment: [
        {"segment_id": 0, "start_s": 0.0, "end_s": 5.0, "conflict_score": 0.1,
         "conflict_reasons": [], "flagged": False}])
    return seen


def _main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["main.py", *argv])
    M.main()


def test_a_run_writes_the_report_and_prints_the_caveat(pipeline, monkeypatch, tmp_path, capsys):
    out = tmp_path / "out" / "report.json"
    _main(monkeypatch, "--url", "https://youtu.be/dQw4w9WgXcQ", "--brand", "Nike", "--output", str(out))
    report = json.loads(out.read_text())
    assert report["brand_name"] == "Nike" and report["bias_caveat"] == BIAS_CAVEAT
    assert 0 <= report["authenticity_score"] <= 100
    assert pipeline["video_dir"].name == "dQw4w9WgXcQ"
    printed = capsys.readouterr().out
    assert "BIAS CAVEAT" in printed and str(out) in printed


def test_an_address_the_downloader_cannot_take_is_sent_as_the_watch_address(
        pipeline, monkeypatch, tmp_path):
    _main(monkeypatch, "--url", "https://www.youtube.com/shorts/dQw4w9WgXcQ", "--brand", "Nike",
          "--output", str(tmp_path / "r.json"))
    assert pipeline["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_an_address_with_no_video_id_is_one_error_line(pipeline, monkeypatch, capsys):
    with pytest.raises(SystemExit) as stopped:
        _main(monkeypatch, "--url", "https://example.com/nothing", "--brand", "Nike")
    assert stopped.value.code == 1
    assert "[ERROR] Could not extract video ID" in capsys.readouterr().err


def test_youtube_refusing_the_comments_is_one_error_line_not_a_traceback(
        pipeline, monkeypatch, tmp_path, capsys):
    def refused(video_id, max_results):
        raise YouTubeAPIError("YouTube API error 403: comments are disabled (commentsDisabled)",
                              403, ("commentsDisabled",))

    monkeypatch.setattr(M, "fetch_comments", refused)
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit) as stopped:
        _main(monkeypatch, "--url", "https://youtu.be/dQw4w9WgXcQ", "--brand", "Nike",
              "--output", str(out))
    assert stopped.value.code == 1
    assert "[ERROR] YouTube API error 403" in capsys.readouterr().err
    assert not out.exists()
