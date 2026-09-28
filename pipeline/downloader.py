"""
downloader.py — Video/audio/frame acquisition

Responsibilities:
  - Download YouTube video via yt-dlp (academic use only — no redistribution)
  - Extract audio track as mono 16 kHz .wav via FFmpeg subprocess
  - Extract frames at 1 fps via OpenCV, named frame_0000.jpg, frame_0001.jpg, ...

Public API
----------
  run(url, output_dir, fps=1) -> dict
      One-shot convenience wrapper used by main.py and the Flask endpoint.
      Returns:
        {
          "video_path":  Path,
          "audio_path":  Path,
          "frames_dir":  Path,
          "frame_paths": list[Path],
          "frame_count": int,
          "duration_s":  float,
        }

  download_video(url, output_dir)  -> Path
  extract_audio(video_path, output_dir) -> Path
  extract_frames(video_path, output_dir, fps) -> list[Path]

  youtube_video_id(url) -> str | None   the one rule for YouTube addresses,
  pipeline_url(url)     -> str | None   used by app.py, main.py and this module
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

import cv2
import yt_dlp

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_ffmpeg() -> None:
    """Raise EnvironmentError if ffmpeg is not on PATH."""
    if shutil.which("ffmpeg") is None:
        raise EnvironmentError(
            "ffmpeg not found on PATH. Install it (macOS: brew install ffmpeg; "
            "Windows: winget install --id Gyan.FFmpeg -e; Linux: apt install ffmpeg), "
            "reopen the terminal and retry."
        )


# ── YouTube addresses ────────────────────────────────────────────────────────
#
# One rule for every entry point (app.py, main.py and this module), covering the
# forms the run page accepts (ui/src/pages/run.js, VIDEO_ID): watch?v=, youtu.be/,
# /shorts/ and /embed/, each followed by the 11-character id, on a YouTube host.

_YOUTUBE_HOST = re.compile(
    r"^(?:https?://)?(?:[\w-]+\.)*(?:youtube\.com|youtube-nocookie\.com|youtu\.be)/", re.I)
_ID_IN_URL = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")
# The forms download_video accepts as typed, and that every reader of a saved
# report (analyst_facts, frame_cache, ui/src/lib/frames.js) can take an id from.
_DOWNLOADABLE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]{11}")


def youtube_video_id(url: str) -> str | None:
    """The 11-character video id in a YouTube address, or None if it names none."""
    url = (url or "").strip()
    if not _YOUTUBE_HOST.match(url):
        return None
    match = _ID_IN_URL.search(url)
    return match.group(1) if match else None


def pipeline_url(url: str) -> str | None:
    """
    The address to hand the pipeline for `url`, or None if it names no video.

    An address download_video accepts is returned as typed, so a saved report
    records what was entered. Any other accepted form (/shorts/, /embed/, or a
    watch address with v= after another parameter) becomes the canonical watch
    address, which the downloader and every reader of a saved report understand.
    """
    video_id = youtube_video_id(url)
    if video_id is None:
        return None
    url = url.strip()
    match = _DOWNLOADABLE.search(url)
    if match and match.group(0).endswith(video_id):
        return url
    return f"https://www.youtube.com/watch?v={video_id}"


# ── Stage 1: Download ─────────────────────────────────────────────────────────

def download_video(url: str, output_dir: Path) -> Path:
    """
    Download the best available mp4 (video+audio) from YouTube using yt-dlp.

    The file is saved to output_dir/video.<ext>.  If a file already exists
    (same video ID / same yt-dlp template) the download is skipped so repeated
    runs during development are fast.

    Parameters
    ----------
    url        : YouTube video URL
    output_dir : Directory to save the video file

    Returns
    -------
    Path to the downloaded video file.

    Raises
    ------
    ValueError  : URL does not look like a YouTube video
    RuntimeError: yt-dlp download fails
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not _DOWNLOADABLE.search(url):
        raise ValueError(
            f"URL does not look like a valid YouTube video URL: {url!r}\n"
            "Expected format: https://www.youtube.com/watch?v=<ID>"
        )

    # yt-dlp output template — %(ext)s lets yt-dlp pick the container
    output_template = str(output_dir / "video.%(ext)s")

    ydl_opts: dict = {
        # Best single-file mp4 with both video + audio; fallback to best available
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        # Do not re-download if the file already exists
        "nooverwrites": True,
        "quiet": True,
        "no_warnings": False,
        # Embed subtitles / chapters are not needed for analysis
        "writesubtitles": False,
        "writeautomaticsub": False,
        # Restrict filename characters so paths stay safe on all OS
        "restrictfilenames": True,
    }

    logger.info("Downloading video from %s", url)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise RuntimeError(f"yt-dlp failed to download {url!r}: {exc}") from exc

    # Resolve the actual file path written by yt-dlp
    ext = info.get("ext", "mp4")
    video_path = output_dir / f"video.{ext}"

    # yt-dlp may pick an unexpected container — search for any video file
    if not video_path.exists():
        candidates = [
            p for p in output_dir.iterdir()
            if p.stem == "video" and p.suffix in {".mp4", ".mkv", ".webm", ".mov"}
        ]
        if not candidates:
            raise RuntimeError(
                f"yt-dlp completed but no video file found in {output_dir}. "
                f"Expected: {video_path}"
            )
        video_path = max(candidates, key=lambda p: p.stat().st_mtime)  # the newest

    logger.info("Video saved to %s (%.1f MB)", video_path, video_path.stat().st_size / 1e6)
    return video_path


# ── Stage 2: Audio extraction ─────────────────────────────────────────────────

def extract_audio(video_path: Path, output_dir: Path) -> Path:
    """
    Extract audio from video as a mono 16 kHz PCM WAV file using FFmpeg.

    16 kHz mono is the format Whisper and the audeering vocal model expect.
    If audio.wav already exists it is not re-created.

    Parameters
    ----------
    video_path : Path to the downloaded video file
    output_dir : Directory to write audio.wav

    Returns
    -------
    Path to audio.wav

    Raises
    ------
    EnvironmentError : ffmpeg not on PATH
    FileNotFoundError: video_path does not exist
    RuntimeError     : ffmpeg subprocess returns non-zero exit code
    """
    _require_ffmpeg()

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "audio.wav"

    if audio_path.exists():
        logger.info("Audio already extracted at %s — skipping", audio_path)
        return audio_path

    # WRITTEN BESIDE THE TARGET AND RENAMED ONLY ON SUCCESS.
    #
    # Stopping a run is now a kill of the whole process group (see app.py), and
    # ffmpeg dies with it. Writing straight to audio.wav would then leave a
    # truncated file at the final name — and the skip-if-exists check above
    # would treat it as a complete extraction on the next run, so Whisper would
    # transcribe a fragment of the video with nothing anywhere saying so. A
    # rename is atomic, so the final name only ever appears complete.
    partial_path = audio_path.with_name(audio_path.name + ".part")
    partial_path.unlink(missing_ok=True)

    cmd = [
        "ffmpeg",
        "-y",                     # overwrite if somehow exists
        "-i", str(video_path),
        "-vn",                    # no video
        "-acodec", "pcm_s16le",   # 16-bit PCM
        "-ar", "16000",           # 16 kHz, the rate Whisper and the vocal model take
        "-ac", "1",               # mono
        # The container, stated rather than inferred. ffmpeg picks the muxer
        # from the output file's extension, and the partial name below ends in
        # .part, which it does not recognise: without this it refuses the job
        # outright with "Unable to choose an output format". pcm_s16le in a wav
        # container is what the .wav extension was selecting anyway, so the
        # bytes written are unchanged.
        "-f", "wav",
        str(partial_path),
    ]

    logger.info("Extracting audio: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        partial_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg audio extraction failed (exit {result.returncode}):\n"
            f"STDERR: {result.stderr}"
        )

    partial_path.replace(audio_path)
    logger.info("Audio saved to %s (%.1f MB)", audio_path, audio_path.stat().st_size / 1e6)
    return audio_path


# ── Stage 3: Frame extraction ─────────────────────────────────────────────────

def extract_frames(video_path: Path, output_dir: Path, fps: int = 1) -> list[Path]:
    """
    Extract frames from video at the given fps using OpenCV.

    Frames are written as JPEG files named frame_0000.jpg, frame_0001.jpg, ...
    into output_dir/frames/.  If frames already exist the extraction is skipped.

    Parameters
    ----------
    video_path : Path to the video file
    output_dir : Parent directory; frames go into output_dir/frames/
    fps        : Frames per second to extract (default 1 — one frame per second)

    Returns
    -------
    Sorted list of Paths to extracted JPEG frames.

    Raises
    ------
    FileNotFoundError: video_path does not exist
    RuntimeError     : OpenCV cannot open the video, or extraction fails mid-way
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    frames_dir = Path(output_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Skip extraction if frames already exist — but only if the set is whole.
    #
    # The same hazard as the audio above, and a quieter one: frames are written
    # one at a time, so a run stopped part-way leaves a real directory of real
    # frames covering only the first part of the video. The check below would
    # have reused them, and the facial channel would have read a fraction of
    # the video while every count on the report said otherwise.
    #
    # The marker is written before the first frame and removed after the last,
    # so its presence means "interrupted". Directories extracted before this
    # existed have no marker and are still skipped, which is why the test is
    # for the marker rather than for a count.
    marker = frames_dir / ".extracting"
    existing = sorted(frames_dir.glob("frame_*.jpg"))

    if existing and not marker.exists():
        logger.info(
            "Frames already extracted (%d found in %s) — skipping",
            len(existing), frames_dir,
        )
        return existing

    if marker.exists():
        logger.info(
            "A previous frame extraction in %s was interrupted (%d partial "
            "frames) — discarding them and extracting again",
            frames_dir, len(existing),
        )
        for stale in existing:
            stale.unlink(missing_ok=True)

    marker.touch()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video file: {video_path}")

    try:
        video_fps: float = cap.get(cv2.CAP_PROP_FPS)
        total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if video_fps <= 0:
            raise RuntimeError(
                f"OpenCV reported invalid FPS ({video_fps}) for {video_path}. "
                "The video file may be corrupted."
            )

        # Extract one frame every <frame_interval> video frames
        frame_interval = max(1, round(video_fps / fps))
        logger.info(
            "Video FPS=%.2f, extracting every %d frame(s) → ~%d frames total",
            video_fps, frame_interval, total_frames // frame_interval,
        )

        frame_paths: list[Path] = []
        video_frame_idx = 0   # position in the raw video frame stream
        saved_idx = 0         # sequential index for the output filenames

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if video_frame_idx % frame_interval == 0:
                filename = frames_dir / f"frame_{saved_idx:04d}.jpg"
                ok = cv2.imwrite(
                    str(filename),
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 95],
                )
                if not ok:
                    raise RuntimeError(f"OpenCV failed to write frame: {filename}")
                frame_paths.append(filename)
                saved_idx += 1

            video_frame_idx += 1

    finally:
        cap.release()

    if not frame_paths:
        raise RuntimeError(
            f"No frames were extracted from {video_path}. "
            "The video may have no video track, or be extremely short."
        )

    marker.unlink(missing_ok=True)
    logger.info("%d frames saved to %s", len(frame_paths), frames_dir)
    return sorted(frame_paths)


# ── Public one-shot wrapper ───────────────────────────────────────────────────

def run(url: str, output_dir: Path, fps: int = 1) -> dict:
    """
    Download a YouTube video and extract audio + frames in one call.

    This is the entry point used by main.py and app.py.

    Parameters
    ----------
    url        : YouTube video URL
    output_dir : Root directory for this video's data
    fps        : Frame extraction rate (default 1 fps)

    Returns
    -------
    dict with keys:
      video_path  : Path  — downloaded video file
      audio_path  : Path  — extracted 16 kHz mono WAV
      frames_dir  : Path  — directory containing JPEG frames
      frame_paths : list[Path] — sorted list of frame file paths
      frame_count : int   — number of extracted frames
      duration_s  : float — video duration in seconds (from frame count / fps)
    """
    output_dir = Path(output_dir)

    video_path = download_video(url, output_dir)
    audio_path = extract_audio(video_path, output_dir)
    frame_paths = extract_frames(video_path, output_dir, fps=fps)

    # Approximate duration from extracted frame count and requested fps
    duration_s = len(frame_paths) / fps if fps > 0 else 0.0

    return {
        "video_path": video_path,
        "audio_path": audio_path,
        "frames_dir": output_dir / "frames",
        "frame_paths": frame_paths,
        "frame_count": len(frame_paths),
        "duration_s": duration_s,
    }
