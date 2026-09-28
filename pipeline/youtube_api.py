"""
youtube_api.py — YouTube Data API errors, described without the API key.

googleapiclient puts the API key in every request URL as a query parameter
(`...&key=<key>&alt=json`), and the text of its HttpError quotes that URL. An
error raised unchanged would carry the key into the server log, into the job
status the run page shows, and into a sweep's saved `sweep.json`. Every
`.execute()` the application makes goes through `execute()` here, which
re-raises a refused call as `YouTubeAPIError`, with the status, YouTube's own
message and its reason codes, and without the URL.

`pipeline/analyst.py:fetch_video_meta` is the one call that does not: it never
raises, and records only the error's type name.
"""

from __future__ import annotations

import os
import re

_KEY_PARAM = re.compile(r"([?&]key=)[^&\s\"'>]+")
_REDACTED = "<redacted>"


class YouTubeAPIError(RuntimeError):
    """A refused or failed YouTube Data API call, described without the request URL."""

    def __init__(self, message: str, status: int | None = None, reasons: tuple[str, ...] = ()):
        super().__init__(message)
        self.status = status
        self.reasons = reasons


def redact(text: str) -> str:
    """`text` with any `key=` query value, and the configured key itself, removed."""
    text = _KEY_PARAM.sub(r"\1" + _REDACTED, text)
    key = os.environ.get("YOUTUBE_API_KEY")
    return text.replace(key, _REDACTED) if key else text


def _reason_codes(exc: Exception) -> tuple[str, ...]:
    details = getattr(exc, "error_details", None)
    if not isinstance(details, list):
        return ()
    return tuple(d["reason"] for d in details if isinstance(d, dict) and d.get("reason"))


def execute(request):
    """
    `request.execute()`, with an HTTP error re-raised as YouTubeAPIError.

    Any other error (a timeout, no network) is re-raised unchanged unless its
    text contains the key, in which case it too becomes a YouTubeAPIError. The
    original is not chained (`from None`), so a logged traceback does not print
    it either.
    """
    try:
        return request.execute()
    except Exception as exc:  # noqa: BLE001 - re-raised below, in every case
        status = getattr(getattr(exc, "resp", None), "status", None)
        text = str(exc)
        if status is None and redact(text) == text:
            raise
        reasons = _reason_codes(exc)
        if status is None:
            message = f"YouTube API call failed: {redact(text)}"
        else:
            said = redact(str(getattr(exc, "reason", "") or "")).strip()
            message = f"YouTube API error {status}" + (f": {said}" if said else "")
            if reasons:
                message += f" ({', '.join(reasons)})"
        raise YouTubeAPIError(message, status, reasons) from None
