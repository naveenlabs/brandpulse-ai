"""
The YouTube API key never appears in an error.

googleapiclient puts the key in every request URL, and its HttpError quotes
the URL. Before pipeline/youtube_api.py, a refused call (comments disabled,
quota exhausted, a private video) would have carried the key into the server
log, the job status the run page shows, and a sweep's saved sweep.json.

These tests use a real client built from the library's bundled discovery
document and answered by its own HttpMockSequence, so the error is the one the
library really raises, with the key really in its URL. Nothing reaches the
network or spends quota.
"""

from __future__ import annotations

import ast
import json
import logging
import traceback
from pathlib import Path

import pytest

googleapiclient = pytest.importorskip("googleapiclient")
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import HttpMockSequence  # noqa: E402

from pipeline import sweep  # noqa: E402
from pipeline import comment_module, youtube_api  # noqa: E402
from pipeline.youtube_api import YouTubeAPIError, execute, redact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEY = "AIzaTEST-not-a-real-key-0123456789abc"


def _refusal(status: int, message: str, reason: str) -> tuple[dict, bytes]:
    body = {"error": {"code": status, "message": message,
                      "errors": [{"message": message, "domain": "youtube", "reason": reason}]}}
    return {"status": str(status)}, json.dumps(body).encode()


COMMENTS_DISABLED = _refusal(
    403, "The video identified by the videoId parameter has disabled comments.", "commentsDisabled")
QUOTA_EXCEEDED = _refusal(
    403, "The request cannot be completed because you have exceeded your quota.", "quotaExceeded")


def _client(*answers):
    return build("youtube", "v3", developerKey=KEY, static_discovery=True,
                 http=HttpMockSequence(list(answers)))


def _everywhere_it_could_show(exc: BaseException) -> str:
    """The text a person or a log could see: str, repr and the printed traceback."""
    return "\n".join([str(exc), repr(exc), *traceback.format_exception(exc)])


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", KEY)


class TestTheLibraryReallyLeaksIt:
    """The premise, measured: without execute(), the raw error carries the key."""

    def test_a_raw_http_error_quotes_the_key(self):
        request = _client(COMMENTS_DISABLED).commentThreads().list(part="snippet", videoId="abcdefghijk")
        with pytest.raises(Exception) as caught:
            request.execute()
        assert KEY in str(caught.value)


class TestExecute:
    def test_a_refusal_is_described_by_status_message_and_reason_without_the_key(self):
        request = _client(COMMENTS_DISABLED).commentThreads().list(part="snippet", videoId="abcdefghijk")
        with pytest.raises(YouTubeAPIError) as caught:
            execute(request)
        err = caught.value
        assert err.status == 403 and err.reasons == ("commentsDisabled",)
        assert "403" in str(err) and "disabled comments" in str(err) and "commentsDisabled" in str(err)
        assert KEY not in _everywhere_it_could_show(err)

    def test_the_original_error_is_not_chained_into_a_printed_traceback(self):
        request = _client(QUOTA_EXCEEDED).search().list(part="snippet", q="x")
        with pytest.raises(YouTubeAPIError) as caught:
            execute(request)
        assert caught.value.__suppress_context__ is True
        assert "HttpError" not in "".join(traceback.format_exception(caught.value))

    def test_a_success_is_returned_unchanged(self):
        request = _client(({"status": "200"}, b'{"items": [1, 2]}')).search().list(part="snippet", q="x")
        assert execute(request) == {"items": [1, 2]}

    def test_an_error_without_the_key_is_re_raised_as_it_was(self):
        timeout = TimeoutError("timed out")

        class Request:
            def execute(self):
                raise timeout

        with pytest.raises(TimeoutError) as caught:
            execute(Request())
        assert caught.value is timeout

    def test_any_other_error_that_quotes_the_key_is_redacted(self):
        class Request:
            def execute(self):
                raise OSError(f"connection reset fetching https://x/?a=1&key={KEY}")

        with pytest.raises(YouTubeAPIError) as caught:
            execute(Request())
        assert KEY not in _everywhere_it_could_show(caught.value)
        assert "connection reset" in str(caught.value)

    @pytest.mark.parametrize("text", [f"?key={KEY}", f"a&key={KEY}&alt=json", f"plain {KEY} text"])
    def test_redact_removes_the_key_in_a_url_or_bare(self, text):
        assert KEY not in redact(text) and "<redacted>" in redact(text)


class TestEveryCallerIsCovered:
    def test_comments_disabled_reaches_the_caller_without_the_key(self, monkeypatch):
        monkeypatch.setattr(comment_module, "build", lambda *a, **k: _client(COMMENTS_DISABLED))
        with pytest.raises(YouTubeAPIError) as caught:
            comment_module.fetch_comments("abcdefghijk", max_results=5)
        assert "commentsDisabled" in str(caught.value)
        assert KEY not in _everywhere_it_could_show(caught.value)

    def test_an_exhausted_quota_on_the_search_reaches_the_caller_without_the_key(self):
        with pytest.raises(YouTubeAPIError) as caught:
            sweep.search_candidates("Samsung", "month", client=_client(QUOTA_EXCEEDED))
        assert "quotaExceeded" in str(caught.value)
        assert KEY not in _everywhere_it_could_show(caught.value)

    def test_the_details_lookup_reaches_the_caller_without_the_key(self):
        with pytest.raises(YouTubeAPIError) as caught:
            sweep.video_details(["abcdefghijk"], client=_client(QUOTA_EXCEEDED))
        assert KEY not in _everywhere_it_could_show(caught.value)

    def test_the_search_route_neither_answers_nor_logs_the_key(self, monkeypatch, caplog):
        import app as app_module
        monkeypatch.setattr(sweep, "_client", lambda: _client(QUOTA_EXCEEDED))
        app_module.app.config.update(TESTING=True)
        with caplog.at_level(logging.ERROR):
            response = app_module.app.test_client().post(
                "/sweep/search", json={"subject": "Samsung", "window": "month"})
        assert response.status_code == 502
        assert "quotaExceeded" in response.get_json()["error"]
        assert KEY not in response.get_data(as_text=True)
        logged = "\n".join(caplog.text.splitlines()
                           + [logging.Formatter().formatException(r.exc_info)
                              for r in caplog.records if r.exc_info])
        assert "quotaExceeded" in logged and KEY not in logged

    def test_a_single_run_neither_reports_nor_logs_the_key(self, monkeypatch, caplog):
        import app as app_module
        monkeypatch.setattr(comment_module, "build", lambda *a, **k: _client(COMMENTS_DISABLED))
        monkeypatch.setattr(app_module, "fetch_comments", comment_module.fetch_comments)
        job_id = "zz-key-test"
        app_module._jobs[job_id] = {"status": "running", "stage": 0}
        try:
            with caplog.at_level(logging.ERROR):
                app_module._run_job(job_id, "https://youtu.be/abcdefghijk", "Brand", "Thing", 5)
            job = app_module._jobs[job_id]
            assert job["status"] == "error" and "commentsDisabled" in job["error"]
            assert KEY not in json.dumps(job)
            logged = "\n".join([caplog.text] + [logging.Formatter().formatException(r.exc_info)
                                                for r in caplog.records if r.exc_info])
            assert KEY not in logged
        finally:
            app_module._jobs.pop(job_id, None)


def test_no_application_code_calls_execute_directly():
    """
    Every `.execute()` goes through youtube_api.execute(). The one exception,
    analyst.fetch_video_meta, never raises and records only the error's type
    name (tested in test_analyst_pipeline.py).
    """
    allowed = {("pipeline/youtube_api.py", "execute"), ("pipeline/analyst.py", "fetch_video_meta")}
    files = [ROOT / n for n in ("app.py", "main.py", "write_analysis.py")]
    files += sorted((ROOT / "pipeline").glob("*.py"))
    found = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "execute" and not node.args):
                    found.append((path.relative_to(ROOT).as_posix(), fn.name))
    assert found, "the scan found nothing, so it is not scanning"
    assert set(found) <= allowed, sorted(set(found) - allowed)
