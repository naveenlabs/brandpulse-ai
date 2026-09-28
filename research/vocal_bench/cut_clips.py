"""
cut_clips.py - sample segments from the corpus and cut them to WAV for rating.

The evaluation sample for the vocal-emotion bench. Segments are drawn from the
same 12-video corpus the transcript bench used, re-transcribed with
`large-v3-turbo` on 01 Sep 2026, so the clips are exactly the segments the
deployed pipeline now produces.

Sampling rules, fixed before any clip was cut
---------------------------------------------
* Speaker split matches transcript_bench exactly. Marques Brownlee and
  Mrwhosetheboss form the selection set; Dave2D, Jeremy Fragrance, ShortCircuit
  and The Tech Chap are held out. Reusing the same split means the holdout
  speakers stay unseen across every bench in this project, so nothing learned on
  one channel can leak into another's holdout.
* Duration window 1.5-15.0 s. Below 1.5 s the models have too little audio to be
  meaningful (audio_module already refuses under MIN_SEGMENT_DURATION_S); above
  15 s exceeds the documented input limit of the WavLM candidate. Measured on the
  corpus: this window keeps the large majority of segments.
* Random within video, seeded (42). Deliberately NOT stratified by any model's
  output - sampling on the incumbent's predictions would bias the test set
  toward or away from its own failure modes.
* Segments whose audio is silent or near-silent are rejected, because a rater
  cannot judge tone from silence and the label would be noise.

Usage
-----
    python research/vocal_bench/cut_clips.py
    python research/vocal_bench/cut_clips.py --n-selection 100 --n-confirmation 50
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
PROJECT = BENCH_DIR.parents[1]
CORPUS_DIR = PROJECT / "research" / "transcript_bench" / "corpus"
DATA_DIR = PROJECT / "data"
CLIPS_DIR = BENCH_DIR / "clips"
INDEX = BENCH_DIR / "_clip_index.json"

SEED = 42
MIN_DUR = 1.5
MAX_DUR = 15.0
SILENCE_RMS = 0.005  # below this the segment carries no ratable voice

SELECTION_CHANNELS = {"Marques Brownlee", "Mrwhosetheboss"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("cut")


def load_segments() -> list[dict]:
    """Every eligible segment across the corpus, with its channel attached."""
    channels = {
        v["video_id"]: v["channel"]
        for v in json.loads(
            (PROJECT / "research" / "transcript_bench" / "_corpus_manifest.json").read_text()
        )["videos"]
    }
    out = []
    for f in sorted(CORPUS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        vid = d["video_id"]
        for seg in d["segments"]:
            if MIN_DUR <= seg["duration"] <= MAX_DUR:
                out.append({
                    "video_id": vid,
                    "channel": channels[vid],
                    "segment_id": seg["segment_id"],
                    "start_time": seg["start_time"],
                    "end_time": seg["end_time"],
                    "duration": seg["duration"],
                    # Kept in the index for later analysis ONLY. It is never shown
                    # to the rater - see build_rating_page.py.
                    "text": seg["text"],
                })
    return out


def rms(path: Path) -> float:
    import numpy as np
    import soundfile as sf
    data, _ = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return float(np.sqrt(np.mean(data ** 2))) if len(data) else 0.0


def cut(seg: dict, dest: Path) -> bool:
    src = DATA_DIR / seg["video_id"] / "audio.wav"
    if not src.is_file():
        logger.warning("%s: no audio.wav", seg["video_id"])
        return False
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
        "-ss", f"{seg['start_time']:.3f}",
        "-t", f"{seg['duration']:.3f}",
        "-i", str(src),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        logger.warning("ffmpeg failed on %s: %s", dest.name, r.stderr.decode()[:120])
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-selection", type=int, default=100)
    ap.add_argument("--n-confirmation", type=int, default=50)
    args = ap.parse_args()

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    segments = load_segments()
    logger.info("%d eligible segments (%.1f-%.1fs)", len(segments), MIN_DUR, MAX_DUR)

    pools = {"selection": [], "confirmation": []}
    for s in segments:
        key = "selection" if s["channel"] in SELECTION_CHANNELS else "confirmation"
        pools[key].append(s)
    for k, v in pools.items():
        logger.info("  %s pool: %d segments, %d speakers",
                    k, len(v), len({x["channel"] for x in v}))

    rng = random.Random(SEED)
    chosen: list[dict] = []
    for split, want in (("selection", args.n_selection),
                        ("confirmation", args.n_confirmation)):
        pool = pools[split]
        # Spread across videos rather than letting one long video dominate.
        by_video: dict[str, list[dict]] = {}
        for s in pool:
            by_video.setdefault(s["video_id"], []).append(s)
        for v in by_video.values():
            rng.shuffle(v)

        picked, vids, i = [], sorted(by_video), 0
        while len(picked) < want and any(by_video.values()):
            v = vids[i % len(vids)]
            if by_video[v]:
                s = by_video[v].pop()
                s["split"] = split
                picked.append(s)
            i += 1
        chosen.extend(picked)
        logger.info("  %s: picked %d from %d videos", split, len(picked), len(by_video))

    kept, rejected = [], 0
    for n, seg in enumerate(chosen):
        uid = f"{seg['video_id']}_{seg['segment_id']}"
        dest = CLIPS_DIR / f"{uid}.wav"
        if not cut(seg, dest):
            rejected += 1
            continue
        level = rms(dest)
        if level < SILENCE_RMS:
            logger.info("  dropping %s: near-silent (rms %.4f)", uid, level)
            dest.unlink(missing_ok=True)
            rejected += 1
            continue
        seg["uid"] = uid
        seg["rms"] = round(level, 5)
        kept.append(seg)

    # Shuffle the rating order so the rater never hears one speaker in a block,
    # which would let a drifting impression of that voice colour every clip.
    rng.shuffle(kept)
    for i, s in enumerate(kept):
        s["order"] = i

    INDEX.write_text(json.dumps({
        "seed": SEED, "min_duration": MIN_DUR, "max_duration": MAX_DUR,
        "silence_rms_floor": SILENCE_RMS,
        "selection_channels": sorted(SELECTION_CHANNELS),
        "n_clips": len(kept), "n_rejected": rejected,
        "total_seconds": round(sum(s["duration"] for s in kept), 1),
        "clips": kept,
    }, indent=1))

    total = sum(s["duration"] for s in kept)
    logger.info("cut %d clips (%d rejected), %.1f min of audio -> %s",
                len(kept), rejected, total / 60, CLIPS_DIR)
    for split in ("selection", "confirmation"):
        n = [s for s in kept if s["split"] == split]
        logger.info("  %s: %d clips, %d speakers, %d videos", split, len(n),
                    len({s['channel'] for s in n}), len({s['video_id'] for s in n}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
