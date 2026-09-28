"""
One rule for YouTube addresses (pipeline/downloader.py), shared by the server,
the CLI and the downloader, and agreeing with the run page.

Until 26 Sep 2026 there were three rules. The run page accepted /shorts/ and
/embed/ addresses that the server refused with 400; and the server accepted
`watch?feature=share&v=<id>`, which the downloader then refused at stage 2,
after the comments had already been fetched and classified.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline import downloader

ROOT = Path(__file__).resolve().parent.parent
ID = "dQw4w9WgXcQ"

ACCEPTED_AS_TYPED = [
    f"https://www.youtube.com/watch?v={ID}",
    f"https://youtu.be/{ID}",
    f"https://youtu.be/{ID}?si=abcdef",
    f"https://m.youtube.com/watch?v={ID}&t=30s",
    f"www.youtube.com/watch?v={ID}",
]
ACCEPTED_AND_REWRITTEN = [
    f"https://www.youtube.com/shorts/{ID}",
    f"https://www.youtube.com/embed/{ID}?start=4",
    f"https://www.youtube-nocookie.com/embed/{ID}",
    f"https://www.youtube.com/watch?feature=share&v={ID}",
]
REFUSED = [
    "https://example.com/not-a-video",
    f"https://example.com/watch?v={ID}",          # an id, but not on YouTube
    f"https://vimeo.com/123?v={ID}",
    "https://www.youtube.com/watch?v=short",
    "",
]


@pytest.mark.parametrize("url", ACCEPTED_AS_TYPED + ACCEPTED_AND_REWRITTEN)
def test_every_accepted_form_yields_the_id(url):
    assert downloader.youtube_video_id(url) == ID


@pytest.mark.parametrize("url", REFUSED)
def test_an_address_that_names_no_youtube_video_is_refused(url):
    assert downloader.youtube_video_id(url) is None
    assert downloader.pipeline_url(url) is None


@pytest.mark.parametrize("url", ACCEPTED_AS_TYPED)
def test_a_downloadable_address_is_kept_as_typed(url):
    """A saved report records the address the reader entered."""
    assert downloader.pipeline_url(url) == url.strip()


@pytest.mark.parametrize("url", ACCEPTED_AND_REWRITTEN)
def test_other_forms_become_the_canonical_watch_address(url):
    assert downloader.pipeline_url(url) == f"https://www.youtube.com/watch?v={ID}"


@pytest.mark.parametrize("url", ACCEPTED_AS_TYPED + ACCEPTED_AND_REWRITTEN)
def test_the_downloader_accepts_whatever_the_pipeline_is_given(url, tmp_path):
    """download_video must never refuse an address the server has accepted."""
    fake = MagicMock()
    fake.__enter__.return_value.extract_info.side_effect = RuntimeError("stop before the network")
    with patch.object(downloader.yt_dlp, "YoutubeDL", return_value=fake):
        with pytest.raises(RuntimeError, match="stop before the network"):
            downloader.download_video(downloader.pipeline_url(url), tmp_path)
    fake.__enter__.return_value.extract_info.assert_called_once()


def _run_page_pattern() -> re.Pattern:
    """The run page's own VIDEO_ID regex, read from its source and compiled here."""
    source = (ROOT / "interface" / "ui" / "src" / "pages" / "run.js").read_text(encoding="utf-8")
    literal = re.search(r"const VIDEO_ID = /(.+)/;", source).group(1)
    return re.compile(literal.replace("\\/", "/"))


@pytest.mark.parametrize("url", ACCEPTED_AS_TYPED + ACCEPTED_AND_REWRITTEN)
def test_what_the_run_page_accepts_the_server_accepts(url):
    """
    The page validates before it sends. An address it lets through must not be
    refused by the server, which is the drift this file exists to stop.
    """
    assert _run_page_pattern().search(url), "the page itself refuses this form"
    assert downloader.youtube_video_id(url) == ID


@pytest.fixture()
def client():
    import app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


class TestTheRoutesUseTheRule:
    def test_analyse_accepts_a_shorts_address_and_downloads_the_watch_form(self, client):
        from tests.test_app import _EMPTY_COMMENT_SENTIMENT
        with patch("app.fetch_comments", return_value=[]), \
             patch("app.classify_comment_sentiment", return_value=[]), \
             patch("app.aggregate_video_sentiment", return_value=_EMPTY_COMMENT_SENTIMENT), \
             patch("app.run_orchestration", return_value=[]), \
             patch("app._build_segments", return_value=[]) as build, \
             patch("app._save_report"), patch("app.frame_cache.warm"):
            response = client.post("/analyse", json={
                "video_url": f"https://www.youtube.com/shorts/{ID}", "brand_name": "Acme"})
        assert response.status_code == 200
        build.assert_called_once_with(f"https://www.youtube.com/watch?v={ID}", ID)
        assert response.get_json()["video_url"] == f"https://www.youtube.com/watch?v={ID}"

    def test_analyse_start_hands_the_child_the_downloadable_address(self, client):
        import app as app_module
        before = dict(app_module._jobs)
        context = MagicMock()
        try:
            with patch("app.multiprocessing.get_context", return_value=context), \
                 patch("app.threading.Thread"):
                response = client.post("/analyse/start", json={
                    "video_url": f"https://www.youtube.com/embed/{ID}",
                    "brand_name": "Zz Probe", "product_name": "Never Saved"})
            assert response.status_code == 202
            args = context.Process.call_args.kwargs["args"]
            assert args[2] == f"https://www.youtube.com/watch?v={ID}"
        finally:
            app_module._jobs.clear()
            app_module._jobs.update(before)
            app_module._job_procs.clear()

    def test_analyse_start_still_refuses_a_non_youtube_address(self, client):
        response = client.post("/analyse/start", json={
            "video_url": f"https://example.com/watch?v={ID}",
            "brand_name": "B", "product_name": "P"})
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid video_url"


def test_an_unexpected_container_resolves_to_the_newest_video_file(tmp_path):
    """
    When yt-dlp reports an extension it did not write, download_video falls back
    to the video.* files present, and must take the newest one. It took the last
    by name until 26 Sep 2026 (.webm over a fresher .mp4).
    """
    import os
    old, new = tmp_path / "video.webm", tmp_path / "video.mp4"
    old.write_bytes(b"old"); new.write_bytes(b"new")
    os.utime(old, (1_000_000, 1_000_000)); os.utime(new, (2_000_000, 2_000_000))
    fake = MagicMock()
    fake.__enter__.return_value.extract_info.return_value = {"ext": "mkv"}
    with patch.object(downloader.yt_dlp, "YoutubeDL", return_value=fake):
        assert downloader.download_video(f"https://youtu.be/{ID}", tmp_path) == new
