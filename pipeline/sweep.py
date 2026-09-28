"""
sweep.py — choosing five videos about one subject, and combining what comes back.

Why this exists
---------------
The system analyses one video. It is sold as brand sentiment analysis, and one video is not a
brand. A sweep analyses five videos about one subject — a brand ("Samsung") or a single
product ("iPhone 18 Pro Max") — inside one time window, and combines them.

This module is the part with judgement in it: which five videos, and what one number over five
reports is allowed to mean. It holds no Flask and no threading, so every decision in it can be
tested without a server and without the network.

What the searching had to be built around
-----------------------------------------
Nine live `search.list` calls on 19 Sep 2026 decided the shape of `search_candidates`:

  - Ordering by view count returns old viral videos and defeats the time window entirely.
    Relevance plus `publishedAfter` returns what is being said now, which is the question.
  - A bare brand name returns news, not reviews. `q="Apple"` returned Fox and NDTV news
    clips; `q="Apple review"` returned reviews. Hence QUERY_SUFFIX, and hence the interface
    showing the query that was actually sent rather than the words that were typed.
  - `relevanceLanguage="en"` is a ranking hint, not a filter. Results included Hindi, Tamil,
    Malayalam and Filipino videos. This pipeline is English-centric — Whisper plus
    English-tuned sentiment — and "non-English transcript" is a listed failure path, so
    language is filtered afterwards on `defaultAudioLanguage`, which only `videos.list`
    returns.
  - A brand query returns the competitor's videos. `q="Samsung review"` returned
    "iPhone 18 Pro Max vs Samsung Galaxy S26 Ultra". Whether that is Samsung signal is a
    judgement no filter here can make, which is why nothing is silently dropped: every
    candidate comes back carrying the reason it was kept or refused, and a person confirms
    the five.

That last point is the rule the whole module is built on. `search_candidates` returns the
whole pool with verdicts attached. It never returns five videos and a silence.

On combining five scores
------------------------
`aggregate` reports the mean and the spread as two figures of equal standing, because on this
data the spread is the more informative of the two. Five reviews scoring 48-52 and five
scoring 10-90 both average 50 and mean entirely different things.

Two limits are structural and are carried in the returned dict so the interface cannot forget
them:

  - n = 5. `note` says so.
  - `baseline_bench/BASELINE_ANALYSIS.md` measured no system on this corpus tracking human
    authenticity judgement, every confidence interval including zero. A combined score is a
    measure of how much four channels disagreed, averaged over five videos. It is not a
    measure of whether a brand is liked, and `means_not` says that in words.

Comparability between sweeps is the caller's problem, and `controller` is carried for it: the
controller swap measured in `controller_bench/` moved mean Authenticity by 49.08 points on
byte-identical inputs, so two sweeps written by different controllers are not comparable at
all.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import re
import statistics
from datetime import datetime, timedelta, timezone

from pipeline import youtube_api

logger = logging.getLogger(__name__)

try:                                            # pragma: no cover - import guard
    from googleapiclient.discovery import build
except ImportError:                             # googleapiclient absent (bare test env)
    build = None


# ── The knobs, all in one place ──────────────────────────────────────────────

#: Time windows offered, in days back from now. One definition; the interface
#: labels them, this decides what they mean.
WINDOWS: dict[str, int] = {
    "week":  7,
    "month": 30,
    "half":  182,
    "year":  365,
}

#: Appended to whatever the user typed. Measured: without it a brand name
#: returns news coverage rather than reviews. The interface shows the result.
QUERY_SUFFIX = "review"

#: How many videos a sweep analyses. Five rather than ten because each video is
#: 4-9 minutes of pipeline on a quiet machine and 20+ on a busy one, so ten is
#: an afternoon. This is a resource limit, not a methodological one, and the
#: report should say so.
SWEEP_SIZE = 5

#: How many candidates to ask for before filtering. Roughly half survive on the
#: queries measured, so 25 reliably yields more than SWEEP_SIZE without a second
#: search (100 quota units each).
CANDIDATE_POOL = 25

#: A video needs comments for the audience channel to read anything at all, and
#: a handful of comments aggregate to noise. 30 is an editorial floor, not a
#: measured threshold, and is named as one.
MIN_COMMENTS = 30

#: 4 to 25 minutes. Below that is a Short or a news clip with no review in it;
#: above it is a stream, and Whisper plus DeepFace on an hour of video is not a
#: demonstration. `videoDuration="medium"` asks the API for 4-20; this re-checks
#: because the API's band is advisory and the upper bound here is deliberately
#: looser to keep long reviews.
MIN_DURATION_S = 240
MAX_DURATION_S = 1500

_ISO_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


# ── Small pure helpers ───────────────────────────────────────────────────────

def window_bounds(window: str, now: datetime | None = None) -> tuple[str, str | None]:
    """
    RFC-3339 `publishedAfter` and `publishedBefore` for a named window.

    `publishedBefore` is None for every window, because all four run up to now.
    The comparison view gets an earlier slice by passing `offset_days`, which is
    what makes "a month ago" a month-wide slice rather than everything since.
    """
    if window not in WINDOWS:
        raise ValueError(f"unknown window {window!r}; expected one of {sorted(WINDOWS)}")
    now = now or datetime.now(timezone.utc)
    after = now - timedelta(days=WINDOWS[window])
    return _rfc3339(after), None


def offset_problem(window: str, offset_days: int) -> str | None:
    """
    Why a window cannot end `offset_days` ago, or None when it can.

    The ending goes back at most one window-length (24 Sep 2026). "Last week,
    ending a year ago" used to be accepted, and searched a week no reader would
    call the last week; the author reported the pairing as wrong. At the limit
    the window sits directly before the one ending today -- the week before,
    the month before -- which is still the clean, no-shared-days comparison
    the ending exists for. What is given up is a short window far back (a
    launch week against the launch week a year earlier), judged acceptable.
    """
    if window not in WINDOWS:
        return f"unknown window {window!r}; expected one of {', '.join(sorted(WINDOWS))}"
    if not 0 <= offset_days <= WINDOWS[window]:
        return (f"the {window!r} window can end at most {WINDOWS[window]} days ago, "
                f"one window back; {offset_days} days was asked for")
    return None


def offset_window_bounds(window: str, offset_days: int,
                         now: datetime | None = None) -> tuple[str, str]:
    """
    A window of the same length, ending `offset_days` ago.

    "Samsung, the 6 months ending 6 months ago" has to be a slice as wide as
    "Samsung, the last 6 months", or the two are not comparable and the view is
    lying by construction. How far back it may end is `offset_problem`'s rule.
    """
    problem = offset_problem(window, offset_days)
    if problem:
        raise ValueError(problem)
    now = now or datetime.now(timezone.utc)
    end = now - timedelta(days=offset_days)
    start = end - timedelta(days=WINDOWS[window])
    return _rfc3339(start), _rfc3339(end)


def _rfc3339(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_duration(iso: str) -> int:
    """
    Seconds from an ISO-8601 duration like `PT13M34S`. 0 when unparseable.

    Zero rather than an exception: a malformed duration should cost the video
    its place in the pool, not sink the whole search.
    """
    match = _ISO_DURATION.fullmatch(str(iso or "").strip())
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def build_query(subject: str) -> str:
    """
    The string actually sent to YouTube.

    Kept as a function, and surfaced by `search_candidates` as `query_used`,
    because the interface has to show it. A reader who typed "Samsung" and got
    five videos is owed the fact that the machine searched "Samsung review".
    """
    subject = " ".join(str(subject or "").split())
    if not subject:
        raise ValueError("subject is empty")
    if subject.lower().endswith(QUERY_SUFFIX):
        return subject
    return f"{subject} {QUERY_SUFFIX}"


def _subject_terms(subject: str) -> list[str]:
    """
    The words a title must contain one of for the video to be about the subject.

    Words of three characters or fewer are dropped: they match everything, and
    "Pro" in "iPhone 18 Pro Max" would admit any video with "Pro" in the title.
    """
    return [w for w in re.split(r"\W+", str(subject).lower()) if len(w) > 3]


# ── Judging one candidate ────────────────────────────────────────────────────

def verdict_for(video: dict, subject: str) -> str:
    """
    "ok", or the reason this video is not suitable, in words a reader can act on.

    The reasons are returned rather than applied, because two of them are
    judgements a person may legitimately overrule. A video whose title does not
    name the subject may still be about it; a competitor comparison may or may
    not be signal for the brand. Only language and comment count are close to
    mechanical, and even those are shown rather than hidden.
    """
    language = str(video.get("language") or "")
    if not language:
        return "language not declared"
    if not language.lower().startswith("en"):
        return f"not English ({language})"

    comments = int(video.get("comment_count") or 0)
    if comments == 0:
        return "comments are off"
    if comments < MIN_COMMENTS:
        return f"only {comments} comments"

    duration = int(video.get("duration_s") or 0)
    if duration < MIN_DURATION_S:
        return f"too short ({duration // 60}m {duration % 60:02d}s)"
    if duration > MAX_DURATION_S:
        return f"too long ({duration // 60}m)"

    terms = _subject_terms(subject)
    title = str(video.get("title") or "").lower()
    if terms and not any(term in title for term in terms):
        return "subject not named in the title"

    return "ok"


# ── The search ───────────────────────────────────────────────────────────────

def _client():
    """The YouTube client, built the same way `pipeline/comment_module.py` does."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "YOUTUBE_API_KEY environment variable is not set. Add it to your .env file."
        )
    if build is None:
        raise ImportError(
            "google-api-python-client is not installed. "
            "Run: pip install google-api-python-client"
        )
    return build("youtube", "v3", developerKey=api_key)


def _details_entry(video_id: str, item: dict) -> dict:
    """One `videos.list` item as the fields a candidate and a sweep member carry."""
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    raw_comments = stats.get("commentCount")
    return {
        "video_id":      video_id,
        "title":         snippet.get("title", ""),
        "channel":       snippet.get("channelTitle", ""),
        "published_at":  snippet.get("publishedAt", ""),
        "duration_s":    parse_duration(item.get("contentDetails", {}).get("duration")),
        "view_count":    int(stats.get("viewCount") or 0),
        # A missing commentCount means comments are disabled, which is
        # not the same as zero comments; verdict_for reads 0 as "off".
        "comment_count": int(raw_comments) if raw_comments is not None else 0,
        "language":      snippet.get("defaultAudioLanguage")
                         or snippet.get("defaultLanguage") or "",
    }


def video_details(video_ids: list[str], *, client=None) -> dict[str, dict]:
    """
    The details the search records, for videos named by id: title, channel,
    date, length, comment count. One `videos.list` call, 1 quota unit for up to
    50 ids; no search. A video that is private or removed is absent from the
    answer rather than an error. Raises when there is no key or no client.
    """
    ids = [str(v) for v in dict.fromkeys(video_ids) if v][:50]
    if not ids:
        return {}
    youtube = client or _client()
    detail = youtube_api.execute(youtube.videos().list(
        part="snippet,contentDetails,statistics", id=",".join(ids),
    ))
    return {item["id"]: _details_entry(item["id"], item)
            for item in detail.get("items", []) if item.get("id")}


#: What a sweep records about each video it analyses, beside the scores. The
#: search result is the source; `fill_blank_details` fills what a start request
#: left out.
DETAIL_FIELDS = ("title", "channel", "published_at", "duration_s", "comment_count")


def fill_blank_details(entries: list[dict], found: dict[str, dict]) -> list[str]:
    """
    Copy details into the entries that lack them, in place; return the ids that
    gained any. Never overwrites: what the search recorded, and a person read
    before choosing, wins over any later lookup. Added 24 Sep 2026, after a
    brand sweep started without its search result was saved with every title
    blank, and every page of its book named the videos by id.
    """
    filled = []
    for entry in entries:
        extra = found.get(entry.get("video_id")) or {}
        gained = [f for f in DETAIL_FIELDS if not entry.get(f) and extra.get(f)]
        for field in gained:
            entry[field] = extra[field]
        if gained:
            filled.append(entry["video_id"])
    return filled


def search_candidates(subject: str, window: str = "month", *,
                      offset_days: int = 0,
                      pool: int = CANDIDATE_POOL,
                      client=None,
                      now: datetime | None = None) -> dict:
    """
    Find and judge candidate videos for one subject. Nothing is silently dropped.

    Returns
    -------
    {
      "subject":     what was typed,
      "query_used":  what was actually searched,
      "window":      the named window,
      "published_after" / "published_before": the bounds sent,
      "candidates":  [{video_id, title, channel, published_at, duration_s,
                       view_count, comment_count, language, verdict, suggested}, ...]
                     in API relevance order, every one judged,
      "suggested":   the video_ids pre-selected for the reader, up to SWEEP_SIZE,
      "eligible":    how many passed,
    }

    `client` is injectable so the tests never touch the network.
    """
    query = build_query(subject)
    if offset_days:
        after, before = offset_window_bounds(window, offset_days, now=now)
    else:
        after, before = window_bounds(window, now=now)

    youtube = client or _client()

    search_kwargs = dict(
        part="snippet", q=query, type="video", order="relevance",
        publishedAfter=after, maxResults=max(1, min(int(pool), 50)),
        relevanceLanguage="en", videoDuration="medium",
    )
    if before:
        search_kwargs["publishedBefore"] = before

    found = youtube_api.execute(youtube.search().list(**search_kwargs))
    ids = [
        item["id"]["videoId"]
        for item in found.get("items", [])
        if isinstance(item.get("id"), dict) and item["id"].get("videoId")
    ]

    candidates: list[dict] = []
    if ids:
        # One videos.list for the whole page: 1 quota unit, and the only source
        # of defaultAudioLanguage, commentCount and duration, none of which
        # search.list returns.
        by_id = video_details(ids, client=youtube)
        for video_id in ids:                     # preserve relevance order
            if video_id not in by_id:            # deleted between the two calls
                continue
            entry = dict(by_id[video_id])
            entry["verdict"] = verdict_for(entry, subject)
            candidates.append(entry)

    suggested: list[str] = []
    for entry in candidates:
        if entry["verdict"] == "ok" and len(suggested) < SWEEP_SIZE:
            suggested.append(entry["video_id"])
        entry["suggested"] = entry["video_id"] in suggested

    logger.info("sweep search %r: %d candidates, %d eligible, %d suggested",
                query, len(candidates), sum(c["verdict"] == "ok" for c in candidates),
                len(suggested))

    return {
        "subject":          " ".join(str(subject).split()),
        "query_used":       query,
        "window":           window,
        "offset_days":      offset_days,
        "published_after":  after,
        "published_before": before,
        "candidates":       candidates,
        "suggested":        suggested,
        "eligible":         sum(1 for c in candidates if c["verdict"] == "ok"),
    }


# ── Combining what came back ─────────────────────────────────────────────────

def _spread_verdict(values: list[float]) -> str:
    """
    Whether five reviews agree with each other, in words rather than a statistic.

    The bands are editorial, chosen so the sentence changes when the picture
    changes, and they are described as editorial wherever they are printed. The
    numbers they describe are measured; the adjective is not.
    """
    if len(values) < 2:
        return "only one video, so there is nothing to agree or disagree about"
    span = max(values) - min(values)
    if span < 10:
        return "these videos broadly agree with each other"
    if span < 25:
        return "these videos differ noticeably from each other"
    return "these videos disagree sharply with each other"


def aggregate(members: list[dict]) -> dict:
    """
    Combine finished member reports into one summary.

    `members` are ordinary report dicts, the same shape `scorer.build_final_report`
    produces — nothing here reaches into the pipeline, which stays frozen.

    The mean and the spread are returned as equals. So is `means_not`, because a
    combined score that travels without it is the exact misreading this project
    spends a chapter warning about.
    """
    usable = [m for m in members if isinstance(m, dict)]
    auth = [float(m["authenticity_score"]) for m in usable
            if isinstance(m.get("authenticity_score"), (int, float))]
    health = [float(m["brand_health_score"]) for m in usable
              if isinstance(m.get("brand_health_score"), (int, float))]

    segments = sum(len(m.get("all_segments") or []) for m in usable)
    flagged = sum(len(m.get("flagged_segments") or []) for m in usable)
    comments = sum(len(m.get("all_comments") or []) for m in usable)

    distribution: dict[str, int] = {}
    for member in usable:
        for label, n in ((member.get("comment_sentiment") or {}).get("distribution") or {}).items():
            distribution[label] = distribution.get(label, 0) + int(n or 0)

    return {
        "video_count":   len(usable),
        "authenticity":  _summarise(auth),
        "brand_health":  _summarise(health),
        "segments_total": segments,
        "flagged_total":  flagged,
        "flagged_share":  (flagged / segments) if segments else None,
        "comments_total": comments,
        "comment_distribution": distribution,
        "spread_verdict": _spread_verdict(auth),
        "note": (
            f"Mean of {len(usable)} videos. Too few to generalise from, and the "
            f"range matters more than the average."
        ),
        "means_not": (
            "This is how much the four channels disagreed with each other, averaged "
            "across these videos. It is not a measure of whether the brand is liked, "
            "and not a measure of whether anyone was honest."
        ),
    }


def _summarise(values: list[float]) -> dict:
    """Mean, range and standard deviation, or nulls when there is nothing to summarise."""
    if not values:
        return {"mean": None, "min": None, "max": None, "spread": None,
                "stdev": None, "values": []}
    return {
        "mean":   round(statistics.fmean(values), 2),
        "min":    round(min(values), 2),
        "max":    round(max(values), 2),
        "spread": round(max(values) - min(values), 2),
        # Population rather than sample: these five videos are the whole thing
        # being described, not a sample drawn from a larger population of
        # reviews. stdev of one value is 0, not undefined.
        "stdev":  round(statistics.pstdev(values), 2),
        "values": [round(v, 2) for v in values],
    }


# ── Storage ──────────────────────────────────────────────────────────────────
#
# Deliberately not in `outputs/`. `ui_evidence/extract_figures.py` globs
# `outputs/*.json`, which does not recurse, and those figures feed the library,
# the overview and 254 verified claims in the final report. Five more reports per
# sweep landing in that glob would move every corpus figure on every run. Under
# `outputs/sweeps/` the existing corpus is untouched and nothing needs changing
# to keep it that way.
#
# Member reports use the ordinary report schema, unchanged, so the existing
# report page renders one with no work at all.

ROOT = pathlib.Path(__file__).resolve().parents[1]
SWEEPS = ROOT / "outputs" / "sweeps"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """A filesystem-safe, readable fragment of a subject name."""
    slug = _SLUG_STRIP.sub("-", str(text).lower()).strip("-")
    return slug[:48] or "subject"


def sweep_id_for(subject: str, window: str, offset_days: int,
                 video_ids: list[str]) -> str:
    """
    A stable id for one subject, window and set of videos.

    Deterministic on purpose: asking for the same five videos twice must resolve
    to the same directory, so a sweep interrupted after three videos resumes
    rather than starting an hour of work again. The hash is over the *sorted*
    ids, so the same five confirmed in a different order are the same sweep.

    The readable prefix is for a person looking at the directory; the hash is
    what makes it unique.
    """
    digest = hashlib.sha256("|".join(sorted(video_ids)).encode("utf-8")).hexdigest()[:8]
    stem = f"{slugify(subject)}-{window}"
    if offset_days:
        stem = f"{stem}-{int(offset_days)}d"
    return f"{stem}-{digest}"


def sweep_dir(sweep_id: str) -> pathlib.Path:
    """The directory for one sweep. Refuses anything that could escape SWEEPS."""
    safe = str(sweep_id or "")
    if not safe or "/" in safe or "\\" in safe or safe.startswith("."):
        raise ValueError(f"unsafe sweep id {sweep_id!r}")
    resolved = (SWEEPS / safe).resolve()
    if resolved.parent != SWEEPS.resolve():
        raise ValueError(f"unsafe sweep id {sweep_id!r}")
    return resolved


# A bare YouTube video id. `.` and `/` cannot match, so an id that passes can be
# joined to a path without traversal. app.py uses the same constant.
VIDEO_ID = re.compile(r"[A-Za-z0-9_\-]{11}")


def member_path(sweep_id: str, video_id: str) -> pathlib.Path:
    if not VIDEO_ID.fullmatch(str(video_id or "")):
        raise ValueError(f"not a video id: {video_id!r}")
    return sweep_dir(sweep_id) / "members" / f"{video_id}.json"


def sweep_path(sweep_id: str) -> pathlib.Path:
    return sweep_dir(sweep_id) / "sweep.json"


def write_json(path: pathlib.Path, payload: dict, default=None) -> None:
    """
    Write atomically: a crash mid-write must not leave a truncated JSON file
    that later reads as a corrupt report. Same discipline as `app._save_report`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=default)
    tmp.replace(path)


def read_json(path: pathlib.Path) -> dict | None:
    """The parsed file, or None when it is absent or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def existing_members(sweep_id: str, video_ids: list[str]) -> dict[str, dict]:
    """
    Member reports already on disk, keyed by video id.

    This is what makes a sweep resumable. A run that died after three videos
    finds three here and analyses two, rather than spending an hour repeating
    work whose output is already correct.
    """
    found: dict[str, dict] = {}
    for video_id in video_ids:
        try:
            report = read_json(member_path(sweep_id, video_id))
        except ValueError:
            continue
        if report is not None:
            found[video_id] = report
    return found


def list_sweeps() -> list[dict]:
    """
    Every finished or partial sweep on disk, newest first.

    Unreadable directories are skipped rather than raising: one bad sweep must
    not empty the library.
    """
    if not SWEEPS.is_dir():
        return []
    rows: list[dict] = []
    for path in SWEEPS.glob("*/sweep.json"):
        record = read_json(path)
        if not isinstance(record, dict):
            logger.warning("sweep: could not read %s", path)
            continue
        rows.append({
            "sweep_id":     record.get("sweep_id", path.parent.name),
            "subject":      record.get("subject", ""),
            # "brand", "product", or "" for a sweep run before the framing was
            # recorded. The library shelves on this and shows "" as unfiled.
            "subject_kind": record.get("subject_kind", ""),
            "window":       record.get("window", ""),
            "offset_days":  record.get("offset_days", 0),
            "status":       record.get("status", ""),
            "video_count":  (record.get("summary") or {}).get("video_count", 0),
            "authenticity": ((record.get("summary") or {}).get("authenticity") or {}).get("mean"),
            "brand_health": ((record.get("summary") or {}).get("brand_health") or {}).get("mean"),
            "controller":   record.get("controller", ""),
            "finished_at":  record.get("finished_at", 0),
        })
    rows.sort(key=lambda r: r.get("finished_at") or 0, reverse=True)
    return rows
