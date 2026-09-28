#!/usr/bin/env python3
"""
main.py — BrandPulse AI CLI entry point

Usage:
    python main.py --url <youtube_url> --brand <brand_name> [--output outputs/report.json]

Example:
    python main.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --brand "Nike"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pipeline.downloader import pipeline_url, run as downloader_run, youtube_video_id
from pipeline.visual_module import analyse_facial_emotion, pool_emotions_per_segment
from pipeline.audio_module import build_audio_channel
from pipeline.comment_module import fetch_comments, classify_comment_sentiment, aggregate_video_sentiment
from pipeline.orchestrator import run_orchestration, CONFLICT_FLAG_THRESHOLD
from pipeline.scorer import build_final_report, json_default
from pipeline.youtube_api import YouTubeAPIError


DATA_DIR = Path(__file__).parent / "data"
OUTPUTS_DIR = Path(__file__).parent / "outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BrandPulse AI — cross-modal brand sentiment & influencer authenticity analyser"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="YouTube video URL to analyse",
    )
    parser.add_argument(
        "--brand",
        required=True,
        help="Brand name to detect in video (e.g. 'Nike', 'Samsung')",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUTS_DIR / "report.json"),
        help="Path to write the JSON report (default: outputs/report.json)",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=100,
        help="Maximum number of YouTube comments to fetch (default: 100)",
    )
    return parser.parse_args()


def extract_video_id(url: str) -> str:
    """The 11-character YouTube video id in `url` (pipeline/downloader.py's rule)."""
    video_id = youtube_video_id(url)
    if video_id is None:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    return video_id


def run_pipeline(url: str, brand_name: str, max_comments: int) -> dict:
    """
    Execute the full 4-channel cross-modal pipeline on a single YouTube video.

    Stages:
      1. Download video + extract audio + extract frames
      2. [VISUAL]  DeepFace facial emotion per frame → majority label per segment
      3. [AUDIO]   Whisper large-v3-turbo transcription → segment boundaries
                   Dimensional vocal emotion per segment (audeering, read on arousal)
                   pyAudioAnalysis prosodic features per segment
      4. [TEXT]    Fetch comments → fine-tuned cardiffnlp sentiment → video-level aggregate
      5. [ORCHESTRATE] Ollama LLM conflict scoring per segment
      6. [SCORE]   Authenticity Score + Brand Health Score + final report
    """
    video_id = extract_video_id(url)
    url = pipeline_url(url)
    video_dir = DATA_DIR / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  BrandPulse AI — analysing video: {video_id}")
    print(f"  Brand: {brand_name}")
    print(f"{'='*60}\n")

    # ── Stage 1: Data collection ────────────────────────────────────────────
    print("[1/6] Downloading video, extracting audio and frames...")
    media = downloader_run(url, video_dir, fps=1)
    frames = media["frame_paths"]
    audio_path = media["audio_path"]
    print(f"      → {media['frame_count']} frames, {media['duration_s']:.0f}s video\n")

    # ── Stage 2: Visual channel ─────────────────────────────────────────────
    print("[2/6] Visual channel — facial emotion (DeepFace)...")
    frame_emotions = analyse_facial_emotion(frames)
    print(f"      → {len(frame_emotions)} frames analysed\n")

    # ── Stage 3: Audio channel ──────────────────────────────────────────────
    print("[3/6] Audio channel — Whisper + audeering vocal emotion + pyAudioAnalysis...")
    segments = build_audio_channel(audio_path)
    print(f"      → {len(segments)} transcript segments created\n")

    # Pool facial emotions into segment windows (requires segments from Whisper)
    segments = pool_emotions_per_segment(frame_emotions, segments)

    # ── Stage 4: Text / comment channel ────────────────────────────────────
    print("[4/6] Comment channel — fetching and classifying comments...")
    raw_comments = fetch_comments(video_id, max_results=max_comments)
    classified_comments = classify_comment_sentiment(raw_comments)
    comment_sentiment = aggregate_video_sentiment(classified_comments)
    print(f"      → {comment_sentiment['comment_count']} comments analysed")
    print(f"      → Video-level sentiment: {comment_sentiment['label']} "
          f"({comment_sentiment['confidence']:.2f})\n")

    # ── Stage 5: Orchestration ──────────────────────────────────────────────
    print("[5/6] Orchestrating — Ollama LLM conflict scoring...")
    conflict_results = run_orchestration(segments, comment_sentiment)
    flagged = [r for r in conflict_results if r.get("conflict_score", 0) >= CONFLICT_FLAG_THRESHOLD]
    print(f"      → {len(flagged)} segment(s) flagged (conflict ≥ {CONFLICT_FLAG_THRESHOLD})\n")

    # ── Stage 6: Scoring ────────────────────────────────────────────────────
    print("[6/6] Computing final scores...")
    report = build_final_report(
        video_url=url,
        brand_name=brand_name,
        segments=segments,
        conflict_results=conflict_results,
        comment_sentiment=comment_sentiment,
    )

    return report


def main() -> None:
    args = parse_args()

    try:
        report = run_pipeline(
            url=args.url,
            brand_name=args.brand,
            max_comments=args.max_comments,
        )
    except (ValueError, YouTubeAPIError) as exc:
        # A bad address, or YouTube refusing the comments (disabled, quota):
        # expected failures, so one line rather than a traceback.
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    # Write report to disk
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=json_default))

    # Print summary to stdout
    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    print(f"  Influencer Authenticity Score : {report['authenticity_score']:.1f} / 100")
    print(f"  Brand Health Score            : {report['brand_health_score']:.1f} / 100")
    print(f"  Flagged segments              : {len(report['flagged_segments'])}")
    print(f"\n  Full report written to: {output_path}")
    print("\n  ⚠  BIAS CAVEAT:")
    print(f"  {report['bias_caveat']}\n")


if __name__ == "__main__":
    main()
