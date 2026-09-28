"""
acquire.py — download video + extract 1 fps frames for the whole facial corpus.

Twelve of the fifteen corpus videos were downloaded audio-only for the vocal
bench, so `data/<id>/` holds `audio.wav` and nothing else. This script fills in
the missing half using the *pipeline's own* `downloader` functions rather than a
reimplementation, so the frames this bench scores are byte-for-byte the frames
the deployed pipeline would score. (`FACIAL_MODEL_ANALYSIS.md` Amendment A3 is
the reason that matters: benching a configuration the pipeline does not run
invalidated an entire sweep once already.)

Disk policy
-----------
The volume is at 96 per cent capacity, and 4K frames cost ~0.8 MB each. So after
frames are extracted and verified, `video.mp4` is deleted **for videos this
script downloaded**, because:

  - `audio.wav` already exists for all twelve and is not re-derived here;
  - `frames/` is verified non-empty and correctly counted before any delete;
  - the mp4 has no other consumer in this project;
  - it is reproducible with one command.

Videos already on disk before this script ran are never touched.

Run:  python acquire.py            # all pending
      python acquire.py --keep-video
      python acquire.py --only <video_id>
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pipeline import downloader          # noqa: E402  (path set above)

import corpus                            # noqa: E402

MIN_FREE_GB = 8.0        # refuse to start another video below this
LOG = Path(__file__).parent / "acquire_log.txt"


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def dir_size_mb(path: Path) -> float:
    if not path.is_dir():
        return 0.0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def video_file(d: Path) -> Path | None:
    for suffix in (".mp4", ".mkv", ".webm", ".mov"):
        p = d / f"video{suffix}"
        if p.exists():
            return p
    return None


def acquire_one(v: corpus.Video, keep_video: bool, log: logging.Logger) -> dict:
    """Download + extract one video. Returns a result record; never raises."""
    started = time.time()
    rec: dict = {"video_id": v.video_id, "speaker": v.speaker, "ok": False}

    pre_existing = video_file(v.dir) is not None
    if v.frame_count() > 0:
        rec.update(ok=True, skipped=True, frames=v.frame_count())
        log.info("%s — %d frames already present, skipping", v.video_id, rec["frames"])
        return rec

    if free_gb(v.dir.parent) < MIN_FREE_GB:
        rec["error"] = f"only {free_gb(v.dir.parent):.1f} GB free, below {MIN_FREE_GB} GB floor"
        log.error("%s — %s", v.video_id, rec["error"])
        return rec

    try:
        log.info("%s — downloading (%s, %ds)", v.video_id, v.speaker, v.duration_s)
        path = downloader.download_video(v.url, v.dir)
        rec["video_mb"] = round(path.stat().st_size / 1e6, 1)
        log.info("%s — downloaded %.1f MB, extracting frames", v.video_id, rec["video_mb"])

        frames = downloader.extract_frames(path, v.dir, fps=1)
        rec["frames"] = len(frames)
        rec["frames_mb"] = round(dir_size_mb(v.frames_dir), 1)

        # Verification gate: frames must exist, be numerous, and roughly match
        # the video's own duration before anything is deleted.
        expected = v.duration_s
        if rec["frames"] < 1:
            raise RuntimeError("frame extraction produced no files")
        ratio = rec["frames"] / expected
        rec["frame_ratio"] = round(ratio, 3)
        if not (0.90 <= ratio <= 1.10):
            log.warning(
                "%s — %d frames for a %ds video (ratio %.3f); keeping video.mp4 for inspection",
                v.video_id, rec["frames"], expected, ratio,
            )
            keep_this = True
        else:
            keep_this = keep_video or pre_existing

        audio_ok = (v.dir / "audio.wav").exists()
        rec["audio_present"] = audio_ok
        if not audio_ok:
            log.info("%s — no audio.wav, extracting it before any cleanup", v.video_id)
            downloader.extract_audio(path, v.dir)
            rec["audio_present"] = (v.dir / "audio.wav").exists()

        if not keep_this and rec["audio_present"]:
            size = path.stat().st_size / 1e6
            path.unlink()
            rec["video_deleted_mb"] = round(size, 1)
            log.info("%s — deleted video.mp4, reclaimed %.1f MB", v.video_id, size)
        else:
            rec["video_deleted_mb"] = 0.0

        rec["ok"] = True
        rec["seconds"] = round(time.time() - started, 1)
        log.info(
            "%s — done: %d frames, %.1f MB, %.0fs, %.1f GB free",
            v.video_id, rec["frames"], rec["frames_mb"], rec["seconds"], free_gb(v.dir.parent),
        )
    except Exception as exc:                     # noqa: BLE001 — must not abort the batch
        rec["error"] = f"{type(exc).__name__}: {exc}"
        log.exception("%s — FAILED: %s", v.video_id, exc)

    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-video", action="store_true",
                    help="do not delete video.mp4 after frame extraction")
    ap.add_argument("--only", help="acquire a single video id")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.FileHandler(LOG), logging.StreamHandler(sys.stdout)],
    )
    log = logging.getLogger("acquire")
    logging.getLogger("pipeline.downloader").setLevel(logging.INFO)

    todo = [corpus.BY_ID[args.only]] if args.only else corpus.needs_download()
    if not todo:
        log.info("Nothing to do — every corpus video already has frames.")
        return 0

    log.info(
        "Acquiring %d video(s), %.1f min of footage, %.1f GB free at start",
        len(todo), sum(v.duration_s for v in todo) / 60, free_gb(corpus.DATA),
    )

    results = [acquire_one(v, args.keep_video, log) for v in todo]

    ok = [r for r in results if r.get("ok")]
    bad = [r for r in results if not r.get("ok")]
    log.info("=" * 68)
    log.info("Acquired %d/%d. %d frames total, %.1f GB free.",
             len(ok), len(results),
             sum(r.get("frames", 0) for r in ok), free_gb(corpus.DATA))
    for r in bad:
        log.error("  FAILED %s — %s", r["video_id"], r.get("error"))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
