"""
app.py — the Flask server: the interface's pages, its JSON API, and the jobs
that run the pipeline.

  Pages     /, /run, /library, /library/<file>, /brand/<set>, /brand/<set>/<video>,
            /accessibility                                   ("Page routes" below)
  Analyses  POST /analyse/start, GET /analyse/status/<job>, GET /analyse/active,
            POST /analyse/cancel/<job>; POST /analyse runs one synchronously
  Sweeps    POST /sweep/search, /sweep/start, /sweep/cancel/<job>;
            GET /sweep/status/<job>; GET /sweeps, GET and DELETE /sweeps/<set>,
            its members, their written reports, the combined one, a comparison
  Reports   GET /reports; GET and DELETE /reports/<file>; GET /reports/<file>/analysis
  Media     /static/frames/..., /thumbnails/<video>.jpg, /evidence/figures.json

Run: flask --app app run --port 5001
     (port 5000 is held by macOS ControlCenter's AirPlay Receiver)
"""

from __future__ import annotations

# load_dotenv MUST run before pipeline imports so orchestrator.py and
# comment_module.py pick up env vars at module-level getenv() calls.
from dotenv import load_dotenv
load_dotenv()

import json
import logging
import multiprocessing
import os
import queue as queue_mod
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from html import escape
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_from_directory

from pipeline.comment_module import (
    aggregate_video_sentiment,
    classify_comment_sentiment,
    fetch_comments,
)
from pipeline import downloader, audio_module, visual_module
from pipeline import analyst, analyst_sweep, analyst_sweep_facts
from pipeline.orchestrator import OLLAMA_MODEL as ORCHESTRATOR_MODEL, run_orchestration
from pipeline.scorer import BIAS_CAVEAT, VOCAL_CAVEAT, build_final_report, model_outputs
from pipeline.scorer import json_default as _json_default

from pipeline import frame_cache, sweep

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder="interface/static", static_url_path="/static")

STATIC_DIR = Path(__file__).parent / "interface" / "static"
# Saved single reports, and beneath them the sweeps (sweep.SWEEPS) and the
# written analyses (pipeline/analyst.py: storage_path_for_*).
OUTPUTS_DIR = Path(__file__).parent / "outputs"

# No CORS headers, deliberately. Every page is served by this app, so every call
# the interface makes is same-origin, and `vite dev` reaches the API through its
# own proxy. Without these headers the browser's same-origin policy stops any
# other site open in the same browser from reading the saved reports or sending
# the DELETE that removes one, which `Access-Control-Allow-Origin: *` allowed.


# ── Background job tracking (for the web UI progress bar) ──────────────────────
# In memory, in this process: a finished job keeps its result until the server
# stops, and a restart forgets every job. Right for one local user, not for a
# shared deployment.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

_STAGES = [
    "Fetching & classifying audience comments",
    "Downloading video & analysing transcript/facial/vocal channels",
    "Scoring cross-modal conflicts (Ollama orchestrator)",
    "Computing final scores",
    "Writing the report (local model)",
]

# A bare video id (sweep.VIDEO_ID), matched with fullmatch before an id from a
# URL is joined to a path: `.` and `/` cannot match, so no traversal is expressible.
_YT_ID_ONLY_RE = sweep.VIDEO_ID


def _extract_video_id(url: str) -> str | None:
    """The 11-character video id in a YouTube address, or None (downloader's rule)."""
    return downloader.youtube_video_id(url)


# Comments fetched per video. 500 is five pages of the API's 100-per-page maximum
# and well past what the audience channel needs; an unbounded value would ask
# YouTube for as many comments as a caller cared to type.
MAX_COMMENTS_LIMIT = 500


def _max_comments(body: dict) -> tuple[int | None, str | None]:
    """`max_comments` from a request body: `(value, None)`, or `(None, reason)` for a 400."""
    try:
        value = int(body.get("max_comments", 100))
    except (TypeError, ValueError):
        return None, "max_comments must be a whole number"
    if not 1 <= value <= MAX_COMMENTS_LIMIT:
        return None, f"max_comments must be between 1 and {MAX_COMMENTS_LIMIT}"
    return value, None


def _build_segments(video_url: str, video_id: str) -> list[dict]:
    """
    Download the video, then run Whisper, the vocal and prosody readings and
    DeepFace, and return the enriched segments.

    Uses a persistent data/<video_id>/ directory (not a throwaway temp folder) so
    extracted frames remain on disk after the run — needed for manually/visually
    verifying DeepFace's facial-emotion labels against the real frame images.
    This also gets downloader.py's existing skip-if-exists caching for free on reruns.
    """
    work_dir = Path(__file__).parent / "data" / video_id
    work_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Video working directory: %s", work_dir)

    dl = downloader.run(video_url, work_dir, fps=1)
    segments = audio_module.build_audio_channel(dl["audio_path"])

    if not segments:
        raise RuntimeError("Whisper found no speech segments in this video.")

    frame_emotions = visual_module.analyse_facial_emotion(dl["frame_paths"])
    segments = visual_module.pool_emotions_per_segment(frame_emotions, segments)

    return segments


@app.post("/analyse")
def analyse():
    """
    Accept a YouTube URL + brand name, run the full pipeline, return report JSON.

    Status codes:
      200 — success, full report JSON
      400 — missing or invalid field, or an address that names no YouTube video
      500 — internal pipeline error
    """
    body: dict = request.get_json(silent=True) or {}

    # ── Validate required fields ──────────────────────────────────────────────
    for field in ("video_url", "brand_name"):
        if not body.get(field):
            return jsonify({"error": f"missing field: {field}"}), 400

    brand_name: str = body["brand_name"]
    max_comments, problem = _max_comments(body)
    if problem:
        return jsonify({"error": problem}), 400

    video_id = _extract_video_id(body["video_url"])
    if video_id is None:
        return jsonify({"error": "invalid video_url"}), 400
    video_url: str = downloader.pipeline_url(body["video_url"])

    logger.info("analyse: video_id=%s brand=%r max_comments=%d",
                video_id, brand_name, max_comments)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    try:
        # Stage 1: comments
        comments = fetch_comments(video_id, max_results=max_comments)
        classified = classify_comment_sentiment(comments)
        comment_sentiment = aggregate_video_sentiment(classified)

        # Stage 2: download, then transcript, voice and face per segment
        segments = _build_segments(video_url, video_id)

        # Stage 3: cross-modal conflict scoring via Ollama
        conflict_results = run_orchestration(segments, comment_sentiment)

        # Stage 4: final report
        report = build_final_report(
            video_url, brand_name, segments, conflict_results, comment_sentiment
        )

    except Exception as exc:
        logger.exception("Pipeline error for video_id=%s: %s", video_id, exc)
        return jsonify({"error": str(exc), "detail": type(exc).__name__}), 500

    _save_report(report, brand_name)
    frame_cache.warm(report)   # same reason as in _run_job; never raises
    return jsonify(report), 200


def _set_stage(job_id: str, stage_index: int) -> None:
    with _jobs_lock:
        _jobs[job_id]["stage_index"] = stage_index
        _jobs[job_id]["stage_label"] = _STAGES[stage_index]


def _enrich_all_segments(segments: list[dict], conflict_results: list[dict]) -> list[dict]:
    """
    Build one enriched entry per segment — flagged AND non-flagged — with the
    same per-model breakdown scorer.py already attaches to flagged_segments.

    Lets the web UI show/filter the full segment list, not just the flagged
    subset, so non-flagged segments can be spot-checked too (e.g. to confirm
    the orchestrator isn't just flagging everything indiscriminately).
    """
    segments_by_id: dict = {seg.get("segment_id"): seg for seg in segments}
    enriched_list: list[dict] = []

    for result in conflict_results:
        enriched = dict(result)
        seg = segments_by_id.get(result.get("segment_id"), {})
        enriched["text"] = seg.get("text", "")
        enriched["model_outputs"] = model_outputs(seg)
        enriched_list.append(enriched)

    return enriched_list


def _all_comments(classified: list[dict]) -> list[dict]:
    """
    Return every classified comment's text + label + confidence, so the
    aggregate distribution (e.g. "36% NEGATIVE") can be fully verified against
    every individual comment, not just a sample.
    """
    return [{
        "text":       c.get("text", ""),
        "label":      c.get("sentiment_label", "UNKNOWN"),
        "confidence": c.get("sentiment_confidence", 0.0),
        # Kept since 23 Sep 2026 so the written report can rank a topic's
        # example comments by how many people agreed with them. A count, not
        # an identifier: nothing here points at the person who wrote it.
        "like_count": c.get("like_count"),
    } for c in classified]


def _is_cancelled(job_id: str) -> bool:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return bool(job and job.get("cancel_requested"))


def _run_job(
    job_id: str, video_url: str, brand_name: str, product_name: str, max_comments: int,
    set_stage=None,
) -> None:
    """
    Run the full pipeline, updating _jobs[job_id] as it goes.

    /analyse/start runs this in its own process (_run_job_in_child), where a
    cancel kills the process, and passes a `set_stage` that also reports each
    stage to the server. The _is_cancelled() checks matter only when this runs
    in-process, as the tests run it.
    """
    set_stage = set_stage or _set_stage
    video_id = _extract_video_id(video_url)
    try:
        set_stage(job_id, 0)
        comments = fetch_comments(video_id, max_results=max_comments)
        classified = classify_comment_sentiment(comments)
        comment_sentiment = aggregate_video_sentiment(classified)

        if _is_cancelled(job_id):
            with _jobs_lock:
                _jobs[job_id]["status"] = "cancelled"
            return

        set_stage(job_id, 1)
        segments = _build_segments(video_url, video_id)

        if _is_cancelled(job_id):
            with _jobs_lock:
                _jobs[job_id]["status"] = "cancelled"
            return

        set_stage(job_id, 2)
        conflict_results = run_orchestration(
            segments, comment_sentiment, cancel_check=lambda: _is_cancelled(job_id)
        )

        if _is_cancelled(job_id):
            with _jobs_lock:
                _jobs[job_id]["status"] = "cancelled"
            return

        set_stage(job_id, 3)
        report = build_final_report(
            video_url, brand_name, segments, conflict_results, comment_sentiment
        )
        report["all_comments"] = _all_comments(classified)
        report["all_segments"] = _enrich_all_segments(segments, conflict_results)

        _save_report(report, brand_name, product_name)

        # Derive this report's imagery before declaring the job done, so the
        # report page is complete the first time it is opened rather than
        # deriving frame by frame while someone reads it. Roughly 30 s against a
        # pipeline that has already run for several minutes. It cannot fail the
        # run: warm() swallows its own errors and frames_image() re-derives on
        # request for anything missed.
        derived = frame_cache.warm(report)
        logger.info("frame_cache: derived %d images for job_id=%s", derived, job_id)

        # The written report. The scores are already saved, so nothing here can
        # fail the run: write_report_analysis() never raises, and an analysis
        # that could not be written leaves the book on its facts-only pages.
        set_stage(job_id, 4)
        report_name = _report_filename(brand_name, product_name)
        write_report_analysis(report, report_name)

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = report

    except Exception as exc:
        logger.exception("Pipeline error for job_id=%s video_id=%s: %s", job_id, video_id, exc)
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)


# ── Running an analysis in its own process ───────────────────────────────────
#
# WHY A PROCESS AND NOT A THREAD.
#
# Stop has to take effect at any stage. A thread can only be stopped
# cooperatively, by a flag checked between stages and segments, because Python
# cannot safely kill a thread mid-call: a stop pressed while Whisper was
# transcribing or DeepFace was working through frames would wait for that one
# call, tens of seconds on a real video.
#
# A process can be killed outright, so the work runs in one. Measured when this
# was chosen: `import app` costs 0.55 s and pulls in only cv2 —
# torch, whisper, deepface and transformers are all lazily loaded — so the
# spawn start-up the child pays is negligible against a run of several minutes.
#
# WHY THE WHOLE PROCESS GROUP.
#
# The pipeline shells out: yt-dlp to download and ffmpeg to extract audio.
# Those are grandchildren, and killing their parent leaves them running and
# still writing. The child therefore makes itself a session leader with
# setsid(), and cancelling signals the group, so the shell-outs die with it.
# Windows has neither setsid() nor process groups to signal: there the child
# skips setsid() and cancelling ends the process tree with `taskkill /T`.
#
# WHAT THE CHILD CANNOT DO.
#
# It has its own copy of `_jobs`, so nothing it writes there is visible here.
# It reports over a queue instead, and a watcher thread in this process turns
# those messages back into the same `_jobs` updates the interface already
# polls: the child seeds the record `_run_job` expects and hands it a
# `set_stage` that also posts each stage to the queue.
_job_procs: dict[str, tuple] = {}


def _run_job_in_child(message_queue, job_id: str, video_url: str, brand_name: str,
                      product_name: str, max_comments: int) -> None:
    """Entry point inside the spawned process: `_run_job`, reporting over `message_queue`."""
    # Its own process group, so cancelling takes ffmpeg and yt-dlp with it.
    # Absent on Windows, where _stop_child ends the tree by process id instead.
    if hasattr(os, "setsid"):
        try:
            os.setsid()
        except OSError:
            pass

    with _jobs_lock:
        _jobs[job_id] = {
            "kind": "analysis",
            "status": "running",
            "started_at": time.time(),
            "stage_index": -1,
            "stage_label": "Queued",
            "total_stages": len(_STAGES),
            "cancel_requested": False,
        }

    def _relay_stage(jid: str, stage_index: int) -> None:
        _set_stage(jid, stage_index)          # keeps the child's own record right
        message_queue.put(("stage", stage_index))

    _run_job(job_id, video_url, brand_name, product_name, max_comments,
             set_stage=_relay_stage)

    with _jobs_lock:
        job = _jobs.get(job_id, {})
        status = job.get("status", "error")
        payload = job.get("result") if status == "done" else job.get("error", "")
    message_queue.put((status, payload))


def _watch_child(job_id: str, process, message_queue) -> None:
    """
    Turn the child's messages back into this process's `_jobs` record.

    A killed process sends no verdict, so the loop also ends when it stops being
    alive — and whether that was a cancel or a crash is read from the flag the
    cancel endpoint set before doing the killing.
    """
    verdict = None
    while verdict is None:
        try:
            kind, payload = message_queue.get(timeout=0.4)
        except queue_mod.Empty:
            if not process.is_alive():
                break
            continue

        if kind == "stage":
            _set_stage(job_id, payload)
        else:
            verdict = (kind, payload)

    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        if verdict is not None:
            kind, payload = verdict
            job["status"] = kind
            if kind == "done":
                job["result"] = payload
            elif kind == "error":
                job["error"] = payload
        elif job.get("status") == "running":
            # It died without reporting. Either someone stopped it, or it was
            # killed by something else and that is an error, not a cancel.
            if job.get("cancel_requested"):
                job["status"] = "cancelled"
            else:
                job["status"] = "error"
                job["error"] = (f"The analysis process stopped unexpectedly "
                                f"(exit code {process.exitcode}).")
    _job_procs.pop(job_id, None)


def _stop_child(job_id: str) -> None:
    """
    Kill the analysis process and everything it started, at once.

    SIGTERM to the group first so a child that can exit cleanly does, then
    SIGKILL to whatever is still standing a moment later. Both go to the group
    rather than the process, because ffmpeg and yt-dlp are its children.
    Windows has no process groups or SIGKILL, so there the tree is ended by
    process id (`_end_process_tree`).
    """
    entry = _job_procs.get(job_id)
    if entry is None:
        return
    process, _ = entry
    if not process.is_alive():
        return

    if not hasattr(os, "killpg"):
        _end_process_tree(process)
        return

    try:
        group = os.getpgid(process.pid)
    except (ProcessLookupError, OSError):
        group = None

    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not process.is_alive():
            break
        try:
            if group is not None:
                os.killpg(group, sig)
            else:
                process.kill() if sig == signal.SIGKILL else process.terminate()
        except (ProcessLookupError, PermissionError, OSError):
            pass
        process.join(timeout=1.5)


def _end_process_tree(process) -> None:
    """
    Windows: end the analysis process and everything it started, at once.

    `taskkill /T` takes the children (ffmpeg, yt-dlp's ffmpeg) with it, and /F
    is needed because a console process ignores the polite request. If taskkill
    cannot run, the process itself is still killed; its children then finish
    on their own.
    """
    try:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        pass
    if process.is_alive():
        process.kill()
    process.join(timeout=1.5)


@app.post("/analyse/start")
def analyse_start():
    """
    Start the pipeline in its own process and return a job_id immediately.

    The web UI polls GET /analyse/status/<job_id> to track progress and fetch the
    final report once status == "done".
    """
    body: dict = request.get_json(silent=True) or {}

    for field in ("video_url", "brand_name", "product_name"):
        if not body.get(field):
            return jsonify({"error": f"missing field: {field}"}), 400

    brand_name: str = body["brand_name"]
    product_name: str = body["product_name"]
    max_comments, problem = _max_comments(body)
    if problem:
        return jsonify({"error": problem}), 400

    video_id = _extract_video_id(body["video_url"])
    if video_id is None:
        return jsonify({"error": "invalid video_url"}), 400
    video_url: str = downloader.pipeline_url(body["video_url"])

    report_file = _report_filename(brand_name, product_name)
    if (OUTPUTS_DIR / report_file).exists():
        return jsonify({
            "error": f"A report named \"{report_file}\" already exists. "
                     f"Use a different brand/product name, or rename/delete the existing file."
        }), 409

    # One job at a time, enforced here and not only by the page (which asks
    # /analyse/active once, at load): overlapping runs compete for CPU and race
    # on the loaded model singletons, and a sweep holds the machine for an hour.
    job_id, blocker = _claim_worker({
        "kind": "analysis",
        "status": "running",
        "started_at": time.time(),
        "stage_index": -1,
        "stage_label": "Queued",
        "total_stages": len(_STAGES),
        "cancel_requested": False,
        # The name the report is saved under, so the finished page can link to
        # it: the report itself does not carry the product name.
        "report_file": report_file,
    })
    if blocker is not None:
        return jsonify({
            "error": "This machine is already analysing something. One run at a "
                     "time: overlapping runs compete for CPU and race on the "
                     "loaded models.",
            "active": blocker,
        }), 409

    # spawn, not fork: fork is unsafe on macOS alongside the frameworks this
    # pipeline loads, and Python already defaults away from it there.
    context = multiprocessing.get_context("spawn")
    message_queue = context.Queue()
    process = context.Process(
        target=_run_job_in_child,
        args=(message_queue, job_id, video_url, brand_name, product_name, max_comments),
        daemon=True,
    )
    process.start()
    _job_procs[job_id] = (process, message_queue)

    threading.Thread(
        target=_watch_child,
        args=(job_id, process, message_queue),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


@app.get("/analyse/active")
def analyse_active():
    """
    Report whether any job is currently running.

    Used by the web UI on page load (so a refresh can reconnect to a job still
    in progress) and before starting a new analysis (to block concurrent runs —
    overlapping jobs compete for CPU and can race on lazy-loaded model singletons).
    """
    with _jobs_lock:
        for job_id, job in _jobs.items():
            if job["status"] == "running":
                return jsonify({
                    "active":      True,
                    "job_id":      job_id,
                    "stage_index": job["stage_index"],
                    "stage_label": job["stage_label"],
                    # Which kind, so a reload reconnects to the right poller and
                    # the right screen. A sweep polled as a single analysis would
                    # lose its second register and never see `partial`.
                    "kind":        job.get("kind", "analysis"),
                    "sweep_id":    job.get("sweep_id", ""),
                    "subject":     job.get("subject", ""),
                    "started_at":  job.get("started_at"),
                }), 200

    return jsonify({"active": False}), 200


@app.post("/analyse/cancel/<job_id>")
def analyse_cancel(job_id: str):
    """
    Stop a running analysis at once, whatever stage it is in.

    The analysis runs in its own process group, so the stop is a signal rather
    than a request: the analysis and the ffmpeg or yt-dlp it started end
    together. The flag is set first, because the watcher thread reads it to tell
    a process that was stopped from one that crashed.

    A sweep runs in a thread and stops cooperatively at its next checkpoint, so
    it is refused here and stopped with /sweep/cancel/<job_id>: marking it
    cancelled from here would free the machine while the sweep still ran.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "unknown job_id"}), 404
        if job.get("kind") == "sweep":
            return jsonify({"error": "a sweep is stopped with /sweep/cancel/<job_id>"}), 400
        if job["status"] != "running":
            return jsonify({"error": f"job is not running (status={job['status']})"}), 400
        job["cancel_requested"] = True

    _stop_child(job_id)

    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None and job["status"] == "running":
            job["status"] = "cancelled"

    return jsonify({"cancelling": True}), 200


@app.get("/analyse/status/<job_id>")
def analyse_status(job_id: str):
    """Return current stage/progress for a running job, or the final report once done."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "unknown job_id"}), 404
        response = {
            "status":       job["status"],
            "stage_index":  job["stage_index"],
            "stage_label":  job["stage_label"],
            "total_stages": job["total_stages"],
        }
        if job["status"] == "done":
            response["result"] = job["result"]
            response["report_file"] = job.get("report_file")
        elif job["status"] == "error":
            response["error"] = job["error"]

    return jsonify(response), 200


@app.get("/reports")
def list_reports():
    """List previously saved reports from outputs/, most recent first."""
    if not OUTPUTS_DIR.exists():
        return jsonify([]), 200

    files = sorted(
        OUTPUTS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    reports = []
    for f in files:
        # Older reports were named <brand>_<date>_<time>.json; current ones are
        # "Brand (Product).json" (_report_filename), whose whole stem is the name.
        stem = f.stem
        parts = stem.rsplit("_", 2)
        brand_name = parts[0] if len(parts) == 3 else stem
        timestamp = "_".join(parts[1:]) if len(parts) == 3 else ""
        reports.append({
            "filename":   f.name,
            "brand_name": brand_name,
            "timestamp":  timestamp,
            # `timestamp` is parsed from the filename, which no longer carries
            # one (see _report_filename), so it is "" for current reports and
            # stays only for API compatibility. The date the Library prints is
            # `saved_at`: the file's mtime, the same fact the sort uses.
            "saved_at":   f.stat().st_mtime,
        })

    return jsonify(reports), 200


def _current_caveats(report: dict) -> dict:
    """
    A saved report with its caveats as they stand now.

    A caveat states a channel's measured limits; it is not a result of the run,
    yet every report carries the copy current when it was saved. Serving the
    current constant keeps old reports, and the no-script core (_caveat_block),
    in step when a measurement changes the statement. Without this the vocal
    caveat went on calling the voice "the weakest of the four" for weeks after
    facial_bench/v2 measured the face below it. A report saved without a caveat
    is left without one; nothing is added.
    """
    for key, text in (("bias_caveat", BIAS_CAVEAT), ("vocal_caveat", VOCAL_CAVEAT)):
        if report.get(key):
            report[key] = text
    return report


def _report_path(filename: str) -> Path | None:
    """
    The saved report `filename` names, or None when it could name anything else.

    The resolved path must sit DIRECTLY inside outputs/ and end in .json, so no
    `..`, absolute path or subdirectory is reachable -- including
    outputs/sweeps, whose files resolve one level deeper and have their own
    routes. Every route that takes a report filename goes through this.
    """
    outputs_dir = OUTPUTS_DIR.resolve()
    requested = (outputs_dir / filename).resolve()
    if requested.parent != outputs_dir or not requested.name.endswith(".json"):
        return None
    return requested


@app.get("/reports/<filename>")
def get_report(filename: str):
    """Return the JSON content of one saved report by filename."""
    requested = _report_path(filename)
    if requested is None:
        return jsonify({"error": "invalid filename"}), 400

    if not requested.exists():
        return jsonify({"error": "report not found"}), 404

    with open(requested, "r", encoding="utf-8") as f:
        report = json.load(f)

    return jsonify(_current_caveats(report)), 200


@app.delete("/reports/<filename>")
def delete_report(filename: str):
    """
    Delete one saved report. Permanent: there is no trash and no undo.

    The same traversal check as the reader above (`_report_path`), with more at
    stake. It also means this route cannot reach a sweep: a sweep's files sit
    one level deeper and are refused here; DELETE /sweeps/<id> removes a sweep
    with its members.

    Nothing else is touched. The frames under static/frames/<video id>/ are
    shared — several reports can be drawn from one video — so deleting one run
    must not blank another run's cover.
    """
    requested = _report_path(filename)
    if requested is None:
        return jsonify({"error": "invalid filename"}), 400

    if not requested.exists():
        return jsonify({"error": "report not found"}), 404

    requested.unlink()
    # The written report goes with the report it was written about.
    analysis_path = analyst.storage_path_for_report(requested.name)
    if analysis_path.is_file():
        analysis_path.unlink()
    logger.info("Deleted report %s", requested.name)
    return jsonify({"deleted": requested.name, "kind": "report"}), 200


# ── The written report ────────────────────────────────────────────────────────
#
# Stored beside each report (pipeline/analyst.py: storage_path_for_*), never in
# it. Until one has been written, the routes below compute the facts layer live
# -- no model, no network, nothing written -- so every book has its charts,
# coverage and signs from the start, and only the written pages wait.

def write_report_analysis(report: dict, filename: str) -> None:
    """Write the analysis of a saved single report. Never raises."""
    try:
        result = analyst.analyse_report(report, filename=filename)
        report_path = OUTPUTS_DIR / filename
        analyst.save(analyst.storage_path_for_report(filename), result, report_path)
        logger.info("analysis written for %s: %s", filename, result["status"])
    except Exception as exc:        # noqa: BLE001 - the report is saved; this is extra
        logger.warning("analysis not written for %s: %s", filename, type(exc).__name__)


def write_member_analysis(report: dict, sweep_id: str, video_id: str) -> None:
    """Write the analysis of a sweep member. Never raises."""
    try:
        result = analyst.analyse_report(report)
        analyst.save(analyst.storage_path_for_member(sweep_id, video_id), result,
                     sweep.member_path(sweep_id, video_id))
        logger.info("analysis written for %s/%s: %s", sweep_id, video_id, result["status"])
    except Exception as exc:        # noqa: BLE001 - the member is saved; this is extra
        logger.warning("analysis not written for %s/%s: %s", sweep_id, video_id,
                       type(exc).__name__)


def _member_analysis_missing(sweep_id: str, video_id: str) -> bool:
    """True when a member has no written report, or one about a different file."""
    stored = analyst.load(analyst.storage_path_for_member(sweep_id, video_id),
                          sweep.member_path(sweep_id, video_id))
    return stored is None or bool(stored.get("stale"))


def _sweep_bundles(sweep_id: str, record: dict) -> list[dict]:
    """Each selected video with its report and written report (analyst_sweep.load_bundles)."""
    return analyst_sweep.load_bundles(sweep_id, record, sweep.sweep_dir(sweep_id) / "members")


def write_sweep_analysis(sweep_id: str) -> None:
    """Write the combined report of a finished sweep, from its members' own. Never raises."""
    try:
        record_path = sweep.sweep_path(sweep_id)
        record = sweep.read_json(record_path)
        if record is None:
            return
        bundles = _sweep_bundles(sweep_id, record)
        result = analyst_sweep.analyse_sweep(record, bundles)
        analyst_sweep.save(analyst_sweep.storage_path_for_sweep(sweep_id), result,
                           analyst_sweep.sweep_ref(sweep_id, record_path, bundles))
        logger.info("combined analysis written for %s: %s", sweep_id, result["status"])
    except Exception as exc:        # noqa: BLE001 - the sweep is saved; this is extra
        logger.warning("combined analysis not written for %s: %s", sweep_id, type(exc).__name__)


@app.get("/reports/<filename>/analysis")
def get_report_analysis(filename: str):
    """The written report for one saved report, or its facts computed live."""
    requested = _report_path(filename)
    if requested is None:
        return jsonify({"error": "invalid filename"}), 400
    if not requested.exists():
        return jsonify({"error": "report not found"}), 404
    stored = analyst.load(analyst.storage_path_for_report(requested.name), requested)
    if stored is not None:
        return jsonify(stored), 200
    with open(requested, "r", encoding="utf-8") as f:
        report = json.load(f)
    return jsonify(analyst.facts_only(report, requested.name)), 200


# ── One worker at a time ─────────────────────────────────────────────────────

def _claim_worker(job: dict) -> tuple[str, dict | None]:
    """
    Register a new job, but only if nothing else is running.

    Overlapping runs compete for CPU and race on the lazily loaded model
    singletons. The page's own check (`activeJob()` in run.js, once at load) is
    advisory, since two tabs can both pass it, so the rule is enforced here. The
    check and the insert happen under one lock, so two simultaneous requests
    cannot both find the machine idle.

    Returns `(job_id, None)` when the claim succeeded, or `("", blocker)` naming
    the job already running.
    """
    with _jobs_lock:
        for existing_id, existing in _jobs.items():
            if existing.get("status") == "running":
                return "", {
                    "job_id":      existing_id,
                    "kind":        existing.get("kind", "analysis"),
                    "stage_label": existing.get("stage_label", ""),
                    "subject":     existing.get("subject", ""),
                }
        job_id = uuid.uuid4().hex
        _jobs[job_id] = job
        return job_id, None


def _run_sweep_job(job_id: str, sweep_id: str, subject: str, window: str,
                   offset_days: int, selection: list[dict], selection_context: dict,
                   max_comments: int) -> None:
    """
    Analyse the confirmed videos one at a time, then combine them.

    Sequential, never parallel, for the reason `_claim_worker` records. Each
    video runs the ordinary four stages through the ordinary functions — nothing
    in `pipeline/` is touched or duplicated — and is written as an ordinary
    report, so the existing report page renders a member with no changes.

    Two behaviours matter more than the rest:

    **It resumes.** A member already on disk is skipped. A sweep interrupted by
    a crash, a restart or a cancel picks up where it stopped instead of spending
    another hour reproducing reports that are already correct.

    **One dead video does not lose the others.** A failure is recorded with its
    reason and the loop continues. This is the pipeline's graceful-degradation
    rule applied one level up: losing 50 minutes of finished work because the
    fifth video was region-locked would be the worst possible reading of it. A
    sweep that finishes three of five is reported as `partial` — neither a
    success nor a failure, which is what it is.
    """
    _look_up_missing_details(sweep_id, selection)
    titles = {entry["video_id"]: entry.get("title", "") for entry in selection}
    video_ids = [entry["video_id"] for entry in selection]

    members: dict[str, dict] = sweep.existing_members(sweep_id, video_ids)
    failed: list[dict] = []

    if members:
        logger.info("sweep %s: resuming, %d of %d members already on disk",
                    sweep_id, len(members), len(video_ids))

    try:
        for index, video_id in enumerate(video_ids):
            with _jobs_lock:
                job = _jobs[job_id]
                job["video_index"] = index
                job["video_title"] = titles.get(video_id, video_id)
                job["done"] = sorted(members)
                job["failed"] = list(failed)

            if video_id in members:
                # Resumed after an interruption: a member finished before it
                # may have stopped before its written report did.
                if not _is_cancelled(job_id) and _member_analysis_missing(sweep_id, video_id):
                    _set_stage(job_id, 4)
                    write_member_analysis(members[video_id], sweep_id, video_id)
                continue

            if _is_cancelled(job_id):
                _finish_sweep(job_id, sweep_id, subject, window, offset_days,
                              selection, selection_context, members, failed,
                              status="cancelled")
                return

            video_url = f"https://youtu.be/{video_id}"
            try:
                _set_stage(job_id, 0)
                comments = fetch_comments(video_id, max_results=max_comments)
                classified = classify_comment_sentiment(comments)
                comment_sentiment = aggregate_video_sentiment(classified)

                if _is_cancelled(job_id):
                    _finish_sweep(job_id, sweep_id, subject, window, offset_days,
                                  selection, selection_context, members, failed,
                                  status="cancelled")
                    return

                _set_stage(job_id, 1)
                segments = _build_segments(video_url, video_id)

                _set_stage(job_id, 2)
                conflict_results = run_orchestration(
                    segments, comment_sentiment,
                    cancel_check=lambda: _is_cancelled(job_id),
                )

                if _is_cancelled(job_id):
                    _finish_sweep(job_id, sweep_id, subject, window, offset_days,
                                  selection, selection_context, members, failed,
                                  status="cancelled")
                    return

                _set_stage(job_id, 3)
                report = build_final_report(
                    video_url, subject, segments, conflict_results, comment_sentiment
                )
                report["all_comments"] = _all_comments(classified)
                report["all_segments"] = _enrich_all_segments(segments, conflict_results)
                report["video_title"] = titles.get(video_id, "")
                report["sweep_id"] = sweep_id

                sweep.write_json(sweep.member_path(sweep_id, video_id), report,
                                 default=_json_default)
                members[video_id] = report
                frame_cache.warm(report)

                # The member's written report; its failure is not the member's.
                _set_stage(job_id, 4)
                write_member_analysis(report, sweep_id, video_id)

            except Exception as exc:                      # noqa: BLE001 - see docstring
                logger.exception("sweep %s: video %s failed", sweep_id, video_id)
                failed.append({
                    "video_id": video_id,
                    "title":    titles.get(video_id, ""),
                    "reason":   str(exc) or type(exc).__name__,
                    "detail":   type(exc).__name__,
                })

        status = "done" if len(members) == len(video_ids) else "partial"
        if not members:
            status = "error"
        _finish_sweep(job_id, sweep_id, subject, window, offset_days, selection,
                      selection_context, members, failed, status=status)

    except Exception as exc:
        logger.exception("sweep %s collapsed: %s", sweep_id, exc)
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)


def _look_up_missing_details(sweep_id: str, selection: list[dict]) -> None:
    """
    Fill the titles, channels and dates a start request did not carry.

    The page sends the search result back with the choice, and the server files
    what it was sent. A start without it (an older cached page, or a hand-made
    request) would be saved with every title blank, and every page of the book
    would name its videos by id. One `videos.list` call, 1 quota unit, fills
    them. Its failure costs the titles, never the sweep.
    """
    missing = [entry["video_id"] for entry in selection if not entry.get("title")]
    if not missing:
        return
    try:
        filled = sweep.fill_blank_details(selection, sweep.video_details(missing))
        logger.info("sweep %s: details looked up for %d of %d untitled videos",
                    sweep_id, len(filled), len(missing))
    except Exception as exc:        # noqa: BLE001 - quota, network, no key: all degrade
        logger.warning("sweep %s: details lookup failed for %d videos: %s",
                       sweep_id, len(missing), type(exc).__name__)


def _finish_sweep(job_id: str, sweep_id: str, subject: str, window: str,
                  offset_days: int, selection: list[dict], selection_context: dict,
                  members: dict, failed: list, *, status: str) -> None:
    """
    Write `sweep.json` and close the job.

    Written even for a cancelled or partial sweep, because three finished
    reports and a record of why the other two are missing is a result, and
    losing it on the way out would be the thing this whole design avoids.
    """
    # Anything the start lookup could not fill (offline, quota), the members'
    # written reports may have, from their own lookup. Read from disk.
    sweep.fill_blank_details(selection, analyst_sweep.written_video_details(
        sweep_id, [e["video_id"] for e in selection if not e.get("title")]))

    ordered = [members[entry["video_id"]] for entry in selection
               if entry["video_id"] in members]

    # Read off the job rather than threaded through as a parameter: this
    # function has four call sites inside _run_sweep_job and a parameter would
    # be four chances to drop it on the partial and cancelled paths, which are
    # exactly the paths that must not lose a record.
    with _jobs_lock:
        subject_kind = (_jobs.get(job_id) or {}).get("subject_kind", "")

    record = {
        "sweep_id":      sweep_id,
        "subject":       subject,
        "subject_kind":  subject_kind,
        "window":        window,
        "offset_days":   offset_days,
        "status":        status,
        "controller":    ORCHESTRATOR_MODEL,
        "finished_at":   time.time(),
        "summary":       sweep.aggregate(ordered),
        "members": [
            {
                "video_id":           entry["video_id"],
                "title":              entry.get("title", ""),
                "channel":            entry.get("channel", ""),
                "published_at":       entry.get("published_at", ""),
                "duration_s":         entry.get("duration_s", 0),
                "comment_count":      entry.get("comment_count", 0),
                "authenticity_score": (members.get(entry["video_id"]) or {}).get("authenticity_score"),
                "brand_health_score": (members.get(entry["video_id"]) or {}).get("brand_health_score"),
                "analysed":           entry["video_id"] in members,
            }
            for entry in selection
        ],
        "failed":    failed,
        # Provenance. The interface prints all of this: which query was actually
        # sent, which window, and every candidate that was refused with its
        # reason — so a reader can judge the selection rather than trust it.
        "selection": selection_context,
        "bias_caveat":  BIAS_CAVEAT,
        "vocal_caveat": VOCAL_CAVEAT,
    }
    sweep.write_json(sweep.sweep_path(sweep_id), record, default=_json_default)

    # The combined written report, from the members' own. The job stays
    # running while it is written so the page keeps showing progress; a
    # cancelled sweep skips it (write_analysis.py can write it later).
    if status in ("done", "partial"):
        with _jobs_lock:
            _jobs[job_id]["phase"] = "combined"
            _jobs[job_id]["stage_label"] = "Writing the combined report (local model)"
        write_sweep_analysis(sweep_id)

    with _jobs_lock:
        job = _jobs[job_id]
        job["status"] = status
        job["sweep_id"] = sweep_id
        job["done"] = sorted(members)
        job["failed"] = list(failed)
        job["result"] = record

    logger.info("sweep %s finished: %s, %d of %d members, %d failed",
                sweep_id, status, len(members), len(selection), len(failed))


# ── Sweeps: five videos about one subject ────────────────────────────────────

@app.post("/sweep/search")
def sweep_search():
    """
    Find candidate videos for a subject, each carrying the reason it was kept
    or refused. No analysis is started; nothing is written.

    Body: {"subject": str, "window": "week"|"month"|"half"|"year",
           "offset_days": int (optional, for the comparison view)}

    This is a separate step from starting a sweep on purpose. The searching was
    measured before it was designed (`sweep.py` header): a brand query returns
    the competitor's videos, and whether "iPhone 18 Pro Max vs Samsung Galaxy
    S26 Ultra" is Samsung signal is a judgement no rule in this codebase can
    make. Rather than guess it silently and spend an hour of pipeline on the
    answer, the candidates are shown with their verdicts and a person confirms
    five. One extra click buys an auditable selection.
    """
    body: dict = request.get_json(silent=True) or {}

    subject = str(body.get("subject") or "").strip()
    if not subject:
        return jsonify({"error": "missing field: subject"}), 400
    if len(subject) > 120:
        return jsonify({"error": "subject is too long"}), 400

    window = str(body.get("window") or "month")
    if window not in sweep.WINDOWS:
        return jsonify({
            "error": f"unknown window {window!r}; "
                     f"expected one of {', '.join(sorted(sweep.WINDOWS))}"
        }), 400

    try:
        offset_days = int(body.get("offset_days") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "offset_days must be a whole number of days"}), 400
    problem = sweep.offset_problem(window, offset_days)
    if problem:
        return jsonify({"error": problem}), 400

    try:
        result = sweep.search_candidates(subject, window, offset_days=offset_days)
    except EnvironmentError as exc:
        # No API key. A configuration problem, not a bad request, and the
        # message already says which variable is missing.
        logger.error("sweep search: %s", exc)
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        # Quota exhausted, network down, YouTube 5xx. The caller gets the shape
        # of the failure rather than a stack trace, and the log keeps the rest.
        logger.exception("sweep search failed for subject=%r window=%r", subject, window)
        return jsonify({"error": f"the video search failed: {exc}",
                        "detail": type(exc).__name__}), 502

    return jsonify(result), 200


@app.post("/sweep/start")
def sweep_start():
    """
    Begin analysing the confirmed videos. Returns immediately with a job id.

    Body: {"subject", "window", "offset_days", "video_ids": [...],
           "candidates": [...] (the search result, for provenance)}

    The `video_ids` are the ones a person confirmed, not the ones the search
    suggested — those can differ, and which five were actually analysed is
    recorded in `sweep.json` either way.
    """
    body: dict = request.get_json(silent=True) or {}

    subject = str(body.get("subject") or "").strip()
    if not subject:
        return jsonify({"error": "missing field: subject"}), 400

    window = str(body.get("window") or "month")
    if window not in sweep.WINDOWS:
        return jsonify({"error": f"unknown window {window!r}"}), 400

    try:
        offset_days = int(body.get("offset_days") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "offset_days must be a whole number of days"}), 400
    # The search refuses these; a start must too, or a hand-made request could
    # file a sweep under an ending the search would never have produced.
    problem = sweep.offset_problem(window, offset_days)
    if problem:
        return jsonify({"error": problem}), 400

    raw_ids = body.get("video_ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"error": "choose at least one video"}), 400
    if len(raw_ids) > sweep.SWEEP_SIZE:
        return jsonify({
            "error": f"a sweep analyses at most {sweep.SWEEP_SIZE} videos; "
                     f"{len(raw_ids)} were chosen"
        }), 400

    video_ids: list[str] = []
    for raw in raw_ids:
        if not _YT_ID_ONLY_RE.fullmatch(str(raw)):
            return jsonify({"error": f"not a video id: {raw!r}"}), 400
        if raw not in video_ids:                 # the same video twice is one video
            video_ids.append(str(raw))

    # Candidate metadata, when the caller sent it back, so the sweep can record
    # what was chosen and what was refused. A caller that sends none still works
    # — the sweep simply has thinner provenance.
    by_id = {c.get("video_id"): c for c in (body.get("candidates") or [])
             if isinstance(c, dict)}
    selection = [dict(by_id.get(vid) or {}, video_id=vid) for vid in video_ids]
    selection_context = {
        "query_used":       body.get("query_used", ""),
        "published_after":  body.get("published_after", ""),
        "published_before": body.get("published_before"),
        "considered":       len(by_id) or len(video_ids),
        "rejected": [
            {"video_id": c.get("video_id"), "title": c.get("title", ""),
             "verdict": c.get("verdict", "")}
            for c in (body.get("candidates") or [])
            if isinstance(c, dict) and c.get("verdict") not in (None, "ok")
        ],
    }

    sweep_id = sweep.sweep_id_for(subject, window, offset_days, video_ids)

    # Already finished? Hand back the existing sweep rather than spending
    # another hour reproducing it.
    existing = sweep.read_json(sweep.sweep_path(sweep_id))
    if existing and existing.get("status") in ("done", "partial"):
        return jsonify({"sweep_id": sweep_id, "job_id": None,
                        "already_finished": True}), 200

    max_comments, problem = _max_comments(body)
    if problem:
        return jsonify({"error": problem}), 400

    # Which framing the sweep was started from. The mechanism is the same for
    # both (see run.js), but the Library shelves brand and product sweeps
    # separately. Absent or unrecognised it stays empty rather than being
    # guessed, and the sweep is shown as unfiled.
    subject_kind = str(body.get("subject_kind") or "").strip().lower()
    if subject_kind not in ("", "brand", "product"):
        return jsonify({"error": "subject_kind must be 'brand' or 'product'"}), 400

    job_id, blocker = _claim_worker({
        "kind":        "sweep",
        "status":      "running",
        "started_at":  time.time(),
        "subject":     subject,
        "subject_kind": subject_kind,
        "sweep_id":    sweep_id,
        "stage_index": -1,
        "stage_label": "Queued",
        "total_stages": len(_STAGES),
        "video_index": 0,
        "video_total": len(video_ids),
        "video_title": "",
        "done":        [],
        "failed":      [],
        "cancel_requested": False,
    })
    if blocker is not None:
        return jsonify({
            "error": "This machine is already analysing something. "
                     "One run at a time: overlapping runs compete for CPU and "
                     "race on the loaded models.",
            "active": blocker,
        }), 409

    threading.Thread(
        target=_run_sweep_job,
        args=(job_id, sweep_id, subject, window, offset_days, selection,
              selection_context, max_comments),
        daemon=True,
    ).start()

    return jsonify({"sweep_id": sweep_id, "job_id": job_id}), 202


@app.get("/sweep/status/<job_id>")
def sweep_status(job_id: str):
    """
    Progress of a running sweep.

    Carries two registers rather than one: which video of how many, and which of
    the per-video stages inside it. `_STAGES` stays the per-video list --
    flattening it to one list per sweep would make the stage names meaningless and
    break the contract that ties them, by index, to `run.js`.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "unknown job_id"}), 404
        payload = {
            "kind":         job.get("kind", "sweep"),
            "status":       job["status"],
            "sweep_id":     job.get("sweep_id", ""),
            "subject":      job.get("subject", ""),
            "stage_index":  job.get("stage_index", -1),
            "stage_label":  job.get("stage_label", ""),
            "total_stages": job.get("total_stages", len(_STAGES)),
            "video_index":  job.get("video_index", 0),
            "video_total":  job.get("video_total", 0),
            "video_title":  job.get("video_title", ""),
            "phase":        job.get("phase", "videos"),
            "started_at":   job.get("started_at"),
            "done":         list(job.get("done") or []),
            "failed":       list(job.get("failed") or []),
        }
        if job["status"] in ("done", "partial", "cancelled") and job.get("result"):
            payload["result"] = job["result"]
        if job["status"] == "error":
            payload["error"] = job.get("error", "")
    return jsonify(payload), 200


@app.post("/sweep/cancel/<job_id>")
def sweep_cancel(job_id: str):
    """
    Ask a sweep to stop at its next checkpoint.

    Cooperative, unlike `/analyse/cancel`: a sweep runs in a thread, which checks
    the flag between stages and videos. Members already written stay on disk and
    the sweep is closed with what it has, so cancelling after three videos keeps
    three reports rather than discarding an hour.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "unknown job_id"}), 404
        if job["status"] != "running":
            return jsonify({"error": f"job is not running (status={job['status']})"}), 400
        job["cancel_requested"] = True
    return jsonify({"cancelling": True}), 200


@app.get("/sweeps")
def sweeps_list():
    """Every sweep on disk, newest first."""
    return jsonify(sweep.list_sweeps()), 200


@app.get("/sweeps/<sweep_id>/members/<video_id>")
def sweeps_member(sweep_id: str, video_id: str):
    """
    One member report of a sweep, in the ordinary report shape.

    Kept out of sweep.json deliberately: five full reports with every segment and
    every comment is several megabytes, and the combined page needs only each
    one's conflict profile. Both ids are validated by `sweep.member_path` before
    they reach the filesystem.
    """
    try:
        report = sweep.read_json(sweep.member_path(sweep_id, video_id))
    except ValueError:
        return jsonify({"error": "invalid sweep or video id"}), 400
    if report is None:
        return jsonify({"error": "member not found"}), 404
    return jsonify(_current_caveats(report)), 200


@app.get("/sweeps/<sweep_id>/members/<video_id>/analysis")
def sweeps_member_analysis(sweep_id: str, video_id: str):
    """A sweep member's written report, or its facts computed live."""
    try:
        member = sweep.member_path(sweep_id, video_id)
    except ValueError:
        return jsonify({"error": "invalid sweep or video id"}), 400
    report = sweep.read_json(member)
    if report is None:
        return jsonify({"error": "member not found"}), 404
    stored = analyst.load(analyst.storage_path_for_member(sweep_id, video_id), member)
    if stored is not None:
        return jsonify(stored), 200
    return jsonify(analyst.facts_only(report)), 200


@app.get("/sweeps/<sweep_id>/analysis")
def sweeps_analysis(sweep_id: str):
    """
    The combined written report, or the combined facts computed live
    (`status: "facts-only"`: no model, no network, nothing written) until one
    has been written. A stored one is marked stale when the sweep or any
    member's written report has changed since.
    """
    try:
        record_path = sweep.sweep_path(sweep_id)
        stored_path = analyst_sweep.storage_path_for_sweep(sweep_id)
    except ValueError:
        return jsonify({"error": "invalid sweep id"}), 400
    record = sweep.read_json(record_path)
    if record is None:
        return jsonify({"error": "sweep not found"}), 404
    bundles = _sweep_bundles(sweep_id, record)
    stored = analyst_sweep.load(stored_path, analyst_sweep.sweep_ref(sweep_id, record_path, bundles))
    if stored is not None:
        # Out of date: the figures are recomputed from the files as they are
        # now (no model, milliseconds), so every figure on every page is
        # current; the themes and the words stay as written, and say so.
        if stored.get("stale"):
            stored["facts"] = analyst_sweep_facts.compute_sweep_facts(record, bundles)
        return jsonify(stored), 200
    return jsonify(analyst_sweep.facts_only(record, bundles)), 200


def _same_subject(a: dict, b: dict) -> bool:
    norm = lambda r: " ".join(str(r.get("subject") or "").split()).lower()   # noqa: E731
    return norm(a) == norm(b)


@app.get("/sweeps/<sweep_id>/compare/<other_id>")
def sweeps_compare(sweep_id: str, other_id: str):
    """
    Two sweeps of one subject held against each other, computed live and never
    stored (analyst_sweep_facts.period_facts): whether their windows overlap,
    which videos are the same, how much those moved when read twice, each
    measure's range in both, and -- when both have a combined written report --
    which themes changed. Two different subjects are not compared at all.
    """
    try:
        a_path, b_path = sweep.sweep_path(sweep_id), sweep.sweep_path(other_id)
    except ValueError:
        return jsonify({"error": "invalid sweep id"}), 400
    if sweep_id == other_id:
        return jsonify({"error": "a sweep cannot be compared with itself"}), 400
    a, b = sweep.read_json(a_path), sweep.read_json(b_path)
    if a is None or b is None:
        return jsonify({"error": "sweep not found"}), 404
    if not _same_subject(a, b):
        return jsonify({"comparable": False,
                        "reason": "They are about different subjects."}), 200
    a_bundles, b_bundles = _sweep_bundles(sweep_id, a), _sweep_bundles(other_id, b)

    def themes(sid, path, bundles):
        stored = analyst_sweep.load(analyst_sweep.storage_path_for_sweep(sid),
                                    analyst_sweep.sweep_ref(sid, path, bundles))
        if not stored or stored.get("stale"):
            return None
        return (stored.get("reading") or {}).get("themes") or None

    out = analyst_sweep_facts.period_facts(
        a, [analyst_sweep_facts.video_row(x) for x in a_bundles],
        b, [analyst_sweep_facts.video_row(x) for x in b_bundles],
        themes(sweep_id, a_path, a_bundles), themes(other_id, b_path, b_bundles))
    out["comparable"] = True
    return jsonify(out), 200


@app.get("/sweeps/<sweep_id>")
def sweeps_read(sweep_id: str):
    """One combined sweep report."""
    try:
        record = sweep.read_json(sweep.sweep_path(sweep_id))
    except ValueError:
        return jsonify({"error": "invalid sweep id"}), 400
    if record is None:
        return jsonify({"error": "sweep not found"}), 404
    return jsonify(_current_caveats(record)), 200


@app.delete("/sweeps/<sweep_id>")
def delete_sweep(sweep_id: str):
    """
    Delete one sweep and the member reports inside it. Permanent, no undo.

    A sweep is a directory — `sweep.json` beside a `members/` folder holding one
    report per video — so deleting the sweep IS deleting its videos: the book
    goes, and what is inside it goes with it. It reaches nothing else. A sweep's members are its own copies, keyed by
    video id inside its own directory, so two sweeps that cover the same video
    each hold their own file and deleting one cannot gut the other. Standalone
    reports in outputs/ are a different store again and are never touched.

    `sweep_dir` does the path check and refuses any id that could resolve
    outside outputs/sweeps/, which matters more here than anywhere else in this
    file: this is the only route that removes a directory tree.

    Refused while that sweep is running. The job writes members into this
    directory as it finishes each video, and deleting underneath a live writer
    leaves a half-removed tree and a job writing into nothing.
    """
    try:
        directory = sweep.sweep_dir(sweep_id)
    except ValueError:
        return jsonify({"error": "invalid sweep id"}), 400

    if not directory.is_dir():
        return jsonify({"error": "sweep not found"}), 404

    with _jobs_lock:
        for job in _jobs.values():
            if job.get("status") == "running" and job.get("sweep_id") == sweep_id:
                return jsonify({
                    "error": "This sweep is still running. Stop it before deleting it.",
                }), 409

    members = directory / "members"
    member_count = len(list(members.glob("*.json"))) if members.is_dir() else 0

    shutil.rmtree(directory)
    logger.info("Deleted sweep %s and its %d member report(s)", sweep_id, member_count)
    return jsonify({
        "deleted": sweep_id, "kind": "sweep", "members_deleted": member_count,
    }), 200


# ── Page routes ───────────────────────────────────────────────────────────────
#
# The interface's documents, one address each, all real navigable pages so the
# back button, middle-click and long-press behave. `/reports`, `/sweeps` and
# `/analyse` are API paths, so the pages have their own:
#
#   /                              what the system is, how it reads, what it measured
#   /run                           start an analysis and watch it run
#   /library                       the saved reports and five-video sets
#   /library/<filename>            one saved report, read in full
#   /brand/<sweep_id>              the combined report of a five-video set
#   /brand/<sweep_id>/<video_id>   one video of a set, as a full report
#   /accessibility                 the accessibility statement
#
# Every page loads its CSS and JS from Flask's /static/ mount by absolute path,
# so a page one level deep resolves them exactly as one at the root does.


def _page(name: str):
    """
    Serve one of the interface's four documents.

    `interface/static/` is the committed output of `npm run build` in
    `interface/ui/`. Flask serves it as-is: there is no dev server in the
    demonstration path, because this is shown at an exam on a laptop and must
    not need a second process.
    """
    return send_from_directory(STATIC_DIR, name)


@app.get("/")
def overview():
    """The front door — what the system measures and where it is weak."""
    return _page("index.html")


@app.get("/run")
def run_page():
    """Start an analysis, watch its four stages, cancel it."""
    return _page("run.html")


@app.get("/accessibility")
def accessibility_page():
    """
    The accessibility statement: how far WCAG 2.2 AA is met, how that was
    checked, what does not work yet, and who the reports are about. Static
    and complete without JavaScript (INCLUSIVE_DESIGN.md I4).
    """
    return _page("accessibility.html")


@app.get("/library")
def library_page():
    """
    Every saved report and five-video set. It lists facial-derived scores, so
    it carries the caveats without JavaScript (_page_with_caveats).
    """
    return _page_with_caveats("library.html")


def _page_with_caveats(name: str) -> Response:
    """
    Serve an interface document with the caveats written into its no-script core.

    Every word of a report arrives through JavaScript, so a page served straight
    off disk shows a reader without scripting no caveat at all (measured 12 Sep
    2026: 79 characters inside <main>). The project requires BIAS_CAVEAT on
    every surface that presents a facial-derived score, and a disclosure that
    depends on a script running is not one. Read per request, not cached, so a
    rebuilt static/ is picked up without restarting Flask.
    """
    document = (STATIC_DIR / name).read_text(encoding="utf-8")
    return Response(document.replace("<!--BP:CAVEATS-->", _caveat_block()),
                    mimetype="text/html")


def _caveat_block() -> str:
    """
    The caveat markup substituted into the report document's no-script core.

    Built from the constants in pipeline/scorer.py rather than written into the
    HTML, so the disclosure a reader sees without JavaScript is character-for-
    character the one attached to every report. Two copies of this text would
    eventually disagree, and the one in the HTML would be the copy nobody
    re-reads.

    escape() because these are constants, not user input — the escaping is
    there so that editing scorer.py can never inject markup into a page, not
    because any current value needs it.
    """
    return (
        '<div class="fallback__caveat">'
        "<h2>Facial emotion &mdash; bias caveat</h2>"
        f"<p>{escape(BIAS_CAVEAT)}</p>"
        "</div>"
        '<div class="fallback__caveat">'
        "<h2>Vocal prosody &mdash; reliability caveat</h2>"
        f"<p>{escape(VOCAL_CAVEAT)}</p>"
        "</div>"
    )


@app.get("/brand/<sweep_id>")
def brand_page(sweep_id: str):
    """
    The combined report for one sweep.

    Serves the same document whatever the id: the page reads the id back off
    the path and fetches the sweep itself, as the report page does. A combined
    score averages facial-derived ones, so it carries the caveats too.
    """
    return _page_with_caveats("brand.html")


@app.get("/brand/<sweep_id>/<video_id>")
def sweep_member_page(sweep_id: str, video_id: str):
    """
    One video of a sweep, as a full report.

    It lives under /brand/<sweep_id>/ rather than /library/ on purpose: a member
    is one of five, run under one controller on one day by one stated rule, and
    the page says so and links back. Nesting it keeps that relationship in the
    address, and avoids /library/<path:filename>, whose `path` converter would
    swallow a two-segment tail.

    Nothing derived from the request reaches the filesystem here: the page reads
    the ids back off the path, and both are validated where they are used, in
    `sweep.member_path` behind GET /sweeps/<id>/members/<id>.
    """
    return _page_with_caveats("report.html")


@app.get("/library/<path:filename>")
def report_page(filename: str):
    """
    One saved report.

    The filename is carried in the path so a report is linkable, reloadable and
    shareable, but this route never reads it: the page fetches the report from
    GET /reports/<filename>, where the traversal check lives.
    """
    return _page_with_caveats("report.html")


@app.get("/evidence/figures.json")
def evidence_figures():
    """
    Serve evaluation/ui_evidence/figures.json to the interface.

    Every figure the overview prints comes from this file, which
    evaluation/ui_evidence/extract_figures.py re-derives from outputs/ and the
    research write-ups. Serving it rather than copying it into interface/static/
    keeps one source of truth: there is no second copy to drift.

    One fixed filename, so there is no path for a caller to traverse.
    """
    return send_from_directory(Path(__file__).parent / "evaluation" / "ui_evidence", "figures.json")


@app.get("/static/frames/manifest.json")
def frames_manifest():
    """
    The report page's imagery index, computed from disk at request time.

    `ui_build/build_frames.py` also writes a manifest, listing the videos it
    derived imagery for before the interface shipped. That file is necessarily
    stale the moment a new video is analysed, and a stale manifest makes the
    report page draw the absence hatch — which reads as "the facial channel saw
    nothing here", a claim about the data rather than about the build.

    Computing it instead means it can never disagree with what is on disk, for
    the same reason /evidence/figures.json is served rather than copied. This
    route is registered on the static path deliberately, so the interface needs
    no change and the built file remains a valid fallback for anyone serving
    static/ without Flask.
    """
    return jsonify(frame_cache.live_manifest())


# The casting table shows videos that have not been downloaded, so there is no
# derived frame to draw them with — the only picture that exists yet is
# YouTube's own thumbnail.
_THUMBS_DIR = Path(__file__).parent / "data" / "_thumbnails"
_THUMB_SOURCE = "https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
_THUMB_TIMEOUT_S = 6


@app.get("/thumbnails/<video_id>.jpg")
def candidate_thumbnail(video_id: str):
    """
    One candidate's thumbnail, fetched once and then served from disk.

    A route rather than an <img> pointed at YouTube because the interface makes
    no request to any origin but this server; `ui_evidence/verify_ui.py` checks
    that on every page, and the report states it as a property. The server
    reaching YouTube is not new (the search that produced these candidates just
    did), and no analysis data leaves: this sends a video id and receives a JPEG.

    `video_id` is matched against the YouTube id shape before it reaches either
    the filesystem or the network, so it can neither traverse out of data/ nor
    steer the request at a host of someone else's choosing.

    A failure is not an error here. The card is drawn with its own artwork
    behind this image and reads perfectly without it, so an unreachable
    thumbnail returns 404 and the page simply shows what it already had.
    """
    if not _YT_ID_ONLY_RE.fullmatch(video_id):
        return jsonify({"error": "not found"}), 404

    cached = _THUMBS_DIR / f"{video_id}.jpg"
    if not cached.exists():
        try:
            import requests

            response = requests.get(
                _THUMB_SOURCE.format(video_id=video_id),
                timeout=_THUMB_TIMEOUT_S,
            )
            # YouTube answers a missing thumbnail with a placeholder image
            # rather than a plain 404, so the type is checked as well as status.
            if response.status_code != 200 or not response.headers.get(
                    "Content-Type", "").startswith("image/"):
                return jsonify({"error": "not found"}), 404

            _THUMBS_DIR.mkdir(parents=True, exist_ok=True)
            # Written beside the target and moved into place, so a request that
            # dies midway cannot leave a half-file that every later request
            # then serves as though it were whole.
            partial = cached.with_suffix(".part")
            partial.write_bytes(response.content)
            partial.replace(cached)
        except Exception as exc:                 # network, DNS, timeout, disk
            logger.info("thumbnail %s unavailable: %s", video_id, exc)
            return jsonify({"error": "not found"}), 404

    return send_from_directory(
        cached.parent, cached.name,
        max_age=60 * 60 * 24 * 30,               # it never changes for an id
    )


@app.get("/static/frames/<video_id>/<kind>/<int:second>.jpg")
def frames_image(video_id: str, kind: str, second: int):
    """
    One derived frame, produced on demand when it does not already exist.

    The last of the three layers described in frame_cache: pre-built imagery
    covers the shipped reports, warming covers every new analysis, and this
    covers whatever is left — a report copied in by hand, a build that emptied
    static/, a run interrupted between saving the report and warming it.

    Deriving one image takes roughly 0.15 s and is cached to disk, so the cost
    is paid once per frame and never on a second view.

    `video_id` is matched against the YouTube id shape and `kind` against the
    three known sizes before either reaches the filesystem, so neither can be
    used to traverse out of data/ or static/.
    """
    if kind not in ("p", "w", "h") or not _YT_ID_ONLY_RE.fullmatch(video_id):
        return jsonify({"error": "not found"}), 404
    if not 0 <= second <= 86_400:          # a day of video; nothing legitimate exceeds it
        return jsonify({"error": "not found"}), 404

    path = frame_cache.derive(video_id, kind, second)
    if path is None:
        # No source frame for this second. A 404 is correct and the page already
        # handles it: the manifest will not have offered this second at all.
        return jsonify({"error": "not found"}), 404
    return send_from_directory(path.parent, path.name)


@app.get("/landing")
def landing_redirect():
    """The landing page's former address."""
    return redirect("/", code=308)


@app.get("/app")
def instrument_redirect():
    """
    The retired instrument's address.

    It was a single page that both started a run and displayed the result. Those
    are now two surfaces, and the one a visitor to /app wanted is /run.
    """
    return redirect("/run", code=308)


def _sanitize_filename_part(text: str) -> str:
    """Strip characters illegal in filenames (cross-platform); keep spaces intact."""
    return re.sub(r'[\\/:*?"<>|]+', "", text).strip()


def _report_filename(brand_name: str, product_name: str = "") -> str:
    """
    Build the report filename as "Brand (Product).json" — no timestamp, so the
    name stays clean and predictable. Falls back to "Brand.json" if no product
    name is given (e.g. the legacy synchronous /analyse endpoint).
    """
    safe_brand = _sanitize_filename_part(brand_name)
    safe_product = _sanitize_filename_part(product_name)
    if safe_product:
        return f"{safe_brand} ({safe_product}).json"
    return f"{safe_brand}.json"


def _save_report(report: dict, brand_name: str, product_name: str = "") -> None:
    """
    Save analysis report to outputs/ folder as a JSON file.

    Writes to a temporary file first and renames it into place only once the
    full dump succeeds — so a crash or interruption mid-write can never leave
    a truncated, corrupt report at the final filename.
    """
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filename = _report_filename(brand_name, product_name)
    output_path = OUTPUTS_DIR / filename
    tmp_path = output_path.with_suffix(".json.tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=_json_default)

    tmp_path.replace(output_path)
    logger.info("Report saved: %s", output_path)


if __name__ == "__main__":
    # Same address as `flask --app app run --port 5001` (port 5000 is held by
    # macOS's AirPlay Receiver). No debugger: it executes code sent to it.
    app.run(port=5001)
