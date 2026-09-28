#!/usr/bin/env python3
"""
comment_bench/v2/fetch_corpus.py

Stage 1 of the v2 comment bench: fetch a FROZEN comment corpus.

Why this exists
---------------
PROTOTYPE_FINDINGS.md Section 5 traced the pipeline's run-to-run score instability to a
live re-fetch: between two runs of the same video the comment split moved 35/29/36 ->
36/28/36, which flipped the video-level label from NEGATIVE to NEUTRAL, which was then
injected into all 77 segment prompts. The fix is to fetch once and freeze.

Everything downstream (model scoring, label sheets, statistics) reads the frozen files in
corpus/ and never touches the YouTube API again. That makes every later result reproducible.

What is stored per comment
--------------------------
comment_id, text (display + original), like_count, reply_count, published_at, updated_at.

Author display names and channel IDs are deliberately NOT stored (README, "Engineering rules").

Usage
-----
    cd brandpulse_ai
    python research/comment_bench/v2/fetch_corpus.py               # fetch missing videos
    python research/comment_bench/v2/fetch_corpus.py --force       # re-fetch everything
    python research/comment_bench/v2/fetch_corpus.py --limit 500   # comments per video
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BENCH_DIR = Path(__file__).resolve().parent
VIDEOS_FILE = BENCH_DIR / "videos.txt"


def corpus_dir_for(order: str) -> Path:
    """relevance -> corpus/ (the primary set, matching the pipeline); time -> corpus_time/."""
    return BENCH_DIR / ("corpus" if order == "relevance" else f"corpus_{order}")

# Matches youtu.be/<id>, watch?v=<id>, /embed/<id>, /shorts/<id>
_YT_ID_RE = re.compile(r"(?:youtu\.be/|[?&]v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})")

DEFAULT_LIMIT = 500
API_PAGE_MAX = 100  # YouTube Data API v3 hard cap per commentThreads.list call
DEFAULT_ORDER = "relevance"  # matches pipeline/comment_module.py so results transfer

logger = logging.getLogger("fetch_corpus")


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    """Pull the 11-character video ID out of any common YouTube URL form."""
    match = _YT_ID_RE.search(url)
    return match.group(1) if match else None


def read_video_urls(path: Path) -> list[str]:
    """Read videos.txt, skipping blank lines and # comments."""
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def build_client(api_key: str):
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def fetch_video_metadata(youtube, video_ids: list[str]) -> dict[str, dict]:
    """One API call for up to 50 videos. Returns {video_id: metadata}."""
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        response = youtube.videos().list(
            part="snippet,statistics", id=",".join(chunk)
        ).execute()
        for item in response.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            out[item["id"]] = {
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "default_language": (
                    snippet.get("defaultAudioLanguage")
                    or snippet.get("defaultLanguage")
                    or "unknown"
                ),
                # commentCount INCLUDES replies; our fetch is top-level only, so the
                # number we actually retrieve will normally be lower. Recorded so the
                # gap is visible rather than surprising.
                "api_comment_count_incl_replies": int(stats.get("commentCount", 0))
                if stats.get("commentCount") is not None
                else None,
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)) if stats.get("likeCount") else None,
            }
    return out


def fetch_top_level_comments(youtube, video_id: str, limit: int,
                             order: str) -> tuple[list[dict], str | None]:
    """
    Fetch up to `limit` top-level comments, relevance-ordered.

    Returns (comments, error). On any API failure the comments collected so far are
    returned together with an error string, so one dead video never aborts the run.
    """
    from googleapiclient.errors import HttpError

    comments: list[dict] = []
    page_token: str | None = None

    while len(comments) < limit:
        remaining = limit - len(comments)
        request_kwargs: dict = dict(
            part="snippet",
            videoId=video_id,
            textFormat="plainText",
            order=order,
            maxResults=min(API_PAGE_MAX, remaining),
        )
        if page_token:
            request_kwargs["pageToken"] = page_token

        try:
            response = youtube.commentThreads().list(**request_kwargs).execute()
        except HttpError as exc:
            reason = ""
            try:
                reason = json.loads(exc.content.decode())["error"]["errors"][0]["reason"]
            except Exception:
                reason = str(exc.status_code if hasattr(exc, "status_code") else exc)
            logger.error("  API error on %s: %s", video_id, reason)
            return comments, reason
        except Exception as exc:  # network, auth, anything else
            logger.error("  Unexpected error on %s: %s", video_id, exc)
            return comments, str(exc)

        items = response.get("items", [])
        if not items:
            break

        for item in items[: limit - len(comments)]:
            thread = item["snippet"]
            snippet = thread["topLevelComment"]["snippet"]
            comments.append({
                "comment_id": item["id"],
                "text": snippet.get("textDisplay", ""),
                "text_original": snippet.get("textOriginal", ""),
                "like_count": int(snippet.get("likeCount", 0)),
                "reply_count": int(thread.get("totalReplyCount", 0)),
                "published_at": snippet.get("publishedAt", ""),
                "updated_at": snippet.get("updatedAt", ""),
                # authorDisplayName / authorChannelId deliberately omitted: never stored
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return comments, None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and freeze the v2 comment corpus.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Top-level comments per video (default {DEFAULT_LIMIT}).")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch videos already present in the target corpus directory.")
    parser.add_argument("--order", choices=("relevance", "time"), default=DEFAULT_ORDER,
                        help="YouTube comment ordering. 'relevance' matches the pipeline; "
                             "'time' gives an unbiased chronological sample for drift analysis.")
    parser.add_argument("--videos-file", type=Path, default=None,
                        help="Alternative URL list. Defaults to videos.txt. Used to fetch a "
                             "held-out set without disturbing the frozen primary corpus.")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Alternative output directory, relative to the bench folder. "
                             "Defaults to the directory implied by --order.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    load_dotenv(Path.cwd() / ".env")
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("YOUTUBE_API_KEY not set. Add it to brandpulse_ai/.env and retry.")
        return 1

    videos_file = args.videos_file or VIDEOS_FILE
    urls = read_video_urls(videos_file)
    video_ids: list[str] = []
    for url in urls:
        vid = extract_video_id(url)
        if vid is None:
            logger.warning("Could not parse a video ID from: %s", url)
            continue
        if vid in video_ids:
            logger.warning("Duplicate video ID %s ignored.", vid)
            continue
        video_ids.append(vid)

    if not video_ids:
        logger.error("No usable video IDs in %s", videos_file)
        return 1

    corpus_dir = (BENCH_DIR / args.out_dir) if args.out_dir else corpus_dir_for(args.order)
    manifest_path = corpus_dir / "_manifest.json"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Fetch order: %s  ->  %s", args.order, corpus_dir.name)
    youtube = build_client(api_key)

    logger.info("Fetching metadata for %d videos ...", len(video_ids))
    metadata = fetch_video_metadata(youtube, video_ids)
    missing = [v for v in video_ids if v not in metadata]
    for vid in missing:
        logger.error("Video not returned by API (private, removed or region-locked): %s", vid)

    fetched_at = datetime.now(timezone.utc).isoformat()
    manifest: dict = {
        "created_at": fetched_at,
        "fetch_order": args.order,
        "requested_limit_per_video": args.limit,
        "videos": [],
    }

    for vid in video_ids:
        out_path = corpus_dir / f"{vid}.json"

        if out_path.exists() and not args.force:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            logger.info("SKIP  %s  (already frozen, %d comments)",
                        vid, len(existing.get("comments", [])))
            manifest["videos"].append(_manifest_row(existing))
            continue

        meta = metadata.get(vid)
        if meta is None:
            manifest["videos"].append({
                "video_id": vid, "title": None, "fetched": 0,
                "error": "video_not_found",
            })
            continue

        logger.info("FETCH %s  %s", vid, meta["title"][:60])
        comments, error = fetch_top_level_comments(youtube, vid, args.limit, args.order)

        if error and not comments:
            logger.error("  -> failed with no comments (%s)", error)
        else:
            logger.info("  -> %d top-level comments (API reports %s incl. replies)",
                        len(comments), meta["api_comment_count_incl_replies"])

        record = {
            "schema_version": 2,
            "video_id": vid,
            "video_url": f"https://youtu.be/{vid}",
            "fetched_at": fetched_at,
            "fetch_order": args.order,
            "requested_limit": args.limit,
            "fetched_count": len(comments),
            "error": error,
            "metadata": meta,
            "comments": comments,
        }
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest["videos"].append(_manifest_row(record))

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(row.get("fetched", 0) for row in manifest["videos"])
    short = [r for r in manifest["videos"] if r.get("fetched", 0) < args.limit]

    logger.info("\n%s", "-" * 78)
    logger.info("Frozen corpus: %d comments across %d videos -> %s",
                total, len(manifest["videos"]), corpus_dir)
    if short:
        logger.info("Videos below the %d target:", args.limit)
        for row in short:
            logger.info("  %s  %d  (%s)", row["video_id"], row.get("fetched", 0),
                        row.get("error") or "fewer top-level comments available")
    logger.info("Manifest -> %s", manifest_path)
    return 0


def _manifest_row(record: dict) -> dict:
    meta = record.get("metadata") or {}
    return {
        "video_id": record.get("video_id"),
        "title": meta.get("title"),
        "channel": meta.get("channel_title"),
        "language": meta.get("default_language"),
        "fetched": record.get("fetched_count", len(record.get("comments", []))),
        "api_comment_count_incl_replies": meta.get("api_comment_count_incl_replies"),
        "fetched_at": record.get("fetched_at"),
        "error": record.get("error"),
    }


if __name__ == "__main__":
    sys.exit(main())
