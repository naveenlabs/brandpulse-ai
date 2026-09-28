"""sample.py — draw the rating sample and cut its media.

PROTOCOL.md §4. Everything here is fixed by the protocol and by SEED; running it
twice produces the same 120 segments.

What it does, in order:

  1. Loads the 481 cached corpus segments — the same source
     `controller_bench/run_bench.corpus_probes()` uses, so the channel values in
     this bench are byte-identical to that one's.
  2. Filters to the duration window (§4.4).
  3. Draws 10 per video, seeded, NOT stratified on any model output (§4.4).
  4. Cuts each segment's audio to a small mono MP3.
  5. Pulls up to FILMSTRIP_N frames spanning the segment and downscales them.
  6. Rejects near-silent segments and reports the count.
  7. Writes sample.json — the manifest every later stage reads.

The media is deliberately small. Three of the four raters receive a single
self-contained HTML file (build_pages.py inlines this media as data URIs), and a
file nobody can open or send is not a rating tool.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

DATA = PROJECT / "data"
CORPUS = PROJECT / "research" / "transcript_bench" / "corpus"
MANIFEST = PROJECT / "research" / "transcript_bench" / "_corpus_manifest.json"
AB_CACHE = PROJECT / "research" / "vocal_bench" / "ab_cache"
FACIAL_CACHE = PROJECT / "research" / "facial_bench" / "v2" / "ab_cache_facial"

CLIPS = BENCH / "clips"
STRIPS = BENCH / "strips"
SAMPLE = BENCH / "sample.json"

# ── Fixed by PROTOCOL.md §4. Changing any of these invalidates the sample. ────
SEED = 42
PER_VIDEO = 10                 # §4.4 — 10 x 12 videos = 120
N_DUPLICATES = 30              # §4.5 — hidden repeats
MIN_DUR, MAX_DUR = 1.5, 15.0   # §4.4
SILENCE_RMS = 0.005            # §4.4
RATER_SEEDS = (42, 43, 44, 45)  # §4.6 — one running order per rater

# Media budget. Not in the protocol: these affect file size, not the sample.
FILMSTRIP_N = 4
FRAME_WIDTH = 420
FRAME_QUALITY = 60
AUDIO_BITRATE = "32k"

SELECTION_CHANNELS = {"Marques Brownlee", "Mrwhosetheboss"}  # §4.3

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("sample")


# ── Loading ───────────────────────────────────────────────────────────────────

def speaker_map() -> dict[str, str]:
    return {v["video_id"]: v["channel"]
            for v in json.loads(MANIFEST.read_text())["videos"]}


def corpus_segments() -> list[dict]:
    """The 481 cached segments, with every channel value attached.

    Mirrors `controller_bench/run_bench.corpus_probes()` deliberately rather than
    importing it: that module's `facial_emotion` is hardcoded to "none detected"
    (correctly, for what it was measuring), and this bench needs the real facial
    values from `facial_bench/v2/`. Everything else is read from the same files.
    """
    speakers = speaker_map()
    facial: dict[str, dict] = {}
    for f in sorted(FACIAL_CACHE.glob("*.json")):
        d = json.loads(f.read_text())
        facial[d["video_id"]] = d["facial"]

    out = []
    for cf in sorted((AB_CACHE / "conflict_after_nodamp").glob("*.json")):
        vid = cf.stem
        wanted = set(json.loads(cf.read_text()))
        ts = json.loads((AB_CACHE / "transcript" / f"{vid}.json").read_text())
        ve = json.loads((AB_CACHE / "vocal_audeering" / f"{vid}.json").read_text())
        cs = json.loads((AB_CACHE / "comments" / f"{vid}.json").read_text())
        doc = json.loads((CORPUS / f"{vid}.json").read_text())
        for s in doc["segments"]:
            key = str(s["segment_id"])
            if key not in wanted:
                continue
            v = ve[key]
            fac = (facial.get(vid, {}) or {}).get(key) or {}
            channel = speakers[vid]
            out.append({
                "uid": f"{vid}_{key}",
                "video_id": vid,
                "segment_id": s["segment_id"],
                "channel": channel,
                "split": ("selection" if channel in SELECTION_CHANNELS
                          else "holdout"),
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "duration": s["duration"],
                "text": s["text"],
                # Channel values — used by run_bench, NEVER shown to a rater.
                "transcript_sentiment": (ts[key] or {}).get("label"),
                "vocal_emotion": v.get("label") if isinstance(v, dict) else v,
                "facial_emotion": fac.get("dominant"),
                "facial_confidence": fac.get("confidence", 0.0),
                "facial_frame_count": fac.get("frame_count", 0),
                "video_comment_sentiment": (cs or {}).get("label"),
            })
    return out


# ── Media ─────────────────────────────────────────────────────────────────────

def rms(path: Path) -> float:
    import numpy as np
    import soundfile as sf
    data, _ = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return float(np.sqrt(np.mean(data ** 2))) if len(data) else 0.0


def cut_audio(seg: dict, wav: Path, mp3: Path) -> bool:
    """WAV first (for the RMS check), then a small MP3 for the page."""
    src = DATA / seg["video_id"] / "audio.wav"
    if not src.is_file():
        logger.warning("%s: no audio.wav", seg["video_id"])
        return False
    base = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
            "-ss", f"{seg['start_time']:.3f}", "-t", f"{seg['duration']:.3f}",
            "-i", str(src), "-vn", "-ac", "1"]
    if subprocess.run(base + ["-acodec", "pcm_s16le", "-ar", "16000", str(wav)],
                      capture_output=True).returncode != 0:
        return False
    return subprocess.run(base + ["-b:a", AUDIO_BITRATE, str(mp3)],
                          capture_output=True).returncode == 0


def filmstrip(seg: dict, dest_dir: Path) -> list[str]:
    """Up to FILMSTRIP_N downscaled frames spanning the segment.

    Frames are extracted at 1 fps by `downloader.py` and named by their second
    index, so the frames covering [start, end) are exactly those indices. A
    segment with no frames on disk returns an empty list, which is a real state
    (`facial_bench/v2/` verified 251 genuinely faceless frames) and not an error.
    """
    src_dir = DATA / seg["video_id"] / "frames"
    lo, hi = int(seg["start_time"]), int(seg["end_time"])
    available = [i for i in range(lo, hi + 1)
                 if (src_dir / f"frame_{i:04d}.jpg").is_file()]
    if not available:
        return []
    if len(available) <= FILMSTRIP_N:
        picked = available
    else:
        step = (len(available) - 1) / (FILMSTRIP_N - 1)
        picked = [available[round(k * step)] for k in range(FILMSTRIP_N)]
        picked = sorted(set(picked))

    names = []
    for i in picked:
        out = dest_dir / f"{seg['uid']}_{i:04d}.jpg"
        if not out.is_file():
            r = subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                 "-i", str(src_dir / f"frame_{i:04d}.jpg"),
                 "-vf", f"scale={FRAME_WIDTH}:-2",
                 "-q:v", str(int(31 - FRAME_QUALITY * 0.3)), str(out)],
                capture_output=True)
            if r.returncode != 0:
                continue
        names.append(out.name)
    return names


# ── Sampling ──────────────────────────────────────────────────────────────────

def draw(pool: list[dict], per_video: int, rng: random.Random) -> list[dict]:
    """`per_video` segments from each video. Balanced on video, nothing else."""
    by_video: dict[str, list[dict]] = {}
    for s in pool:
        by_video.setdefault(s["video_id"], []).append(s)
    picked = []
    for vid in sorted(by_video):
        segs = sorted(by_video[vid], key=lambda s: s["segment_id"])
        rng.shuffle(segs)
        take = segs[:per_video]
        if len(take) < per_video:
            logger.warning("%s: only %d eligible segments, wanted %d",
                           vid, len(take), per_video)
        picked.extend(take)
    return picked


def build_orders(items: list[dict], dup_uids: list[str]) -> dict[str, list[dict]]:
    """One running order per rater (§4.6), each from its own seed.

    Every rater sees the same 150 presentations — the 120 unique items plus the
    30 duplicated ones — in a different order. `presentation_id` is unique within
    a rater; `uid` is the segment, and two presentations sharing a uid are the
    hidden duplicate pair.
    """
    orders = {}
    for n, seed in enumerate(RATER_SEEDS, start=1):
        rng = random.Random(seed)
        presentations = [dict(it, rep=0) for it in items]
        by_uid = {it["uid"]: it for it in items}
        presentations += [dict(by_uid[u], rep=1) for u in dup_uids]
        rng.shuffle(presentations)
        for i, p in enumerate(presentations):
            p["presentation_id"] = i
        orders[f"rater{n}"] = presentations
    return orders


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-video", type=int, default=PER_VIDEO)
    ap.add_argument("--duplicates", type=int, default=N_DUPLICATES)
    args = ap.parse_args()

    CLIPS.mkdir(exist_ok=True)
    STRIPS.mkdir(exist_ok=True)

    everything = corpus_segments()
    logger.info("corpus: %d segments across %d videos",
                len(everything), len({s['video_id'] for s in everything}))

    eligible = [s for s in everything if MIN_DUR <= s["duration"] <= MAX_DUR]
    logger.info("eligible on duration [%.1f, %.1f]: %d (dropped %d)",
                MIN_DUR, MAX_DUR, len(eligible), len(everything) - len(eligible))

    rng = random.Random(SEED)
    chosen = draw(eligible, args.per_video, rng)
    logger.info("drawn: %d", len(chosen))

    kept, rejected_silent, rejected_cut = [], 0, 0
    for seg in chosen:
        wav = CLIPS / f"{seg['uid']}.wav"
        mp3 = CLIPS / f"{seg['uid']}.mp3"
        if not cut_audio(seg, wav, mp3):
            rejected_cut += 1
            continue
        level = rms(wav)
        wav.unlink(missing_ok=True)          # the WAV was only for the RMS check
        if level < SILENCE_RMS:
            logger.info("  drop %s: near-silent (rms %.4f)", seg["uid"], level)
            mp3.unlink(missing_ok=True)
            rejected_silent += 1
            continue
        seg["rms"] = round(level, 5)
        seg["audio"] = mp3.name
        seg["frames"] = filmstrip(seg, STRIPS)
        kept.append(seg)

    logger.info("kept %d (%d near-silent, %d uncuttable)",
                len(kept), rejected_silent, rejected_cut)

    # Hidden duplicates: drawn from the kept set with a separate, declared stream
    # so that adding or removing a duplicate cannot reshuffle the main sample.
    dup_rng = random.Random(SEED + 1)
    dup_uids = sorted(s["uid"] for s in kept)
    dup_rng.shuffle(dup_uids)
    dup_uids = sorted(dup_uids[:args.duplicates])

    orders = build_orders(kept, dup_uids)
    n_frames = sum(len(s["frames"]) for s in kept)
    no_frames = sum(1 for s in kept if not s["frames"])

    SAMPLE.write_text(json.dumps({
        "protocol": "baseline_bench/PROTOCOL.md §4",
        "seed": SEED,
        "per_video": args.per_video,
        "duration_window": [MIN_DUR, MAX_DUR],
        "silence_rms_floor": SILENCE_RMS,
        "selection_channels": sorted(SELECTION_CHANNELS),
        "rater_seeds": list(RATER_SEEDS),
        "filmstrip_n": FILMSTRIP_N,
        "n_corpus": len(everything),
        "n_eligible": len(eligible),
        "n_drawn": len(chosen),
        "n_kept": len(kept),
        "n_rejected_silent": rejected_silent,
        "n_rejected_uncuttable": rejected_cut,
        "n_duplicates": len(dup_uids),
        "n_presentations_per_rater": len(kept) + len(dup_uids),
        "n_frames_total": n_frames,
        "n_items_without_frames": no_frames,
        "duplicate_uids": dup_uids,
        "items": kept,
        "orders": {k: [{"presentation_id": p["presentation_id"],
                        "uid": p["uid"], "rep": p["rep"]} for p in v]
                   for k, v in orders.items()},
    }, indent=1))

    logger.info("wrote %s", SAMPLE.name)
    for split in ("selection", "holdout"):
        n = [s for s in kept if s["split"] == split]
        logger.info("  %-9s %3d segments, %d videos, %d speakers",
                    split, len(n), len({s['video_id'] for s in n}),
                    len({s['channel'] for s in n}))
    logger.info("  %d frames extracted, %d items with no frame at all",
                n_frames, no_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
