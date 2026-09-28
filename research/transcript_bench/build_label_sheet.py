"""
build_label_sheet.py - construct the human-labelling sheet for the transcript bench.

Design decisions, all pre-registered in CANDIDATE_MODELS.md and HOLDOUT_PROTOCOL.md:

Speaker-disjoint split.
    The corpus has twelve videos but only six speakers: Marques Brownlee x4 and
    Mrwhosetheboss x4 account for eight of them. Splitting by video alone would
    put the same voice, vocabulary and delivery on both sides, so a "held-out"
    video would not be held out in any meaningful sense. The split is therefore
    by *speaker*: the two high-volume channels form the selection set, and the
    four single-video channels form the confirmation set. This yields exactly the
    8/4 split intended, and the confirmation set carries four unseen speakers
    rather than two seen ones - a stronger generalisation claim, not a weaker one.

One shuffled sheet, not two.
    Selection and confirmation rows are interleaved and shuffled into a single
    file. If the rater could tell which rows were the "real test", effort might
    differ between them. They cannot. The mapping lives in the manifest, which the
    rater never opens.

Context without contamination.
    Whisper cuts on pauses, so a segment frequently starts mid-clause. The
    preceding and following segment are shown as context. Only the middle segment
    is rated. Context is drawn from the full corpus including segments that are
    themselves unratable or unsampled - it is reading material, not data.

Unratable segments are excluded, not silently labelled.
    Criteria are fixed here and applied before sampling. See UNRATABLE_REASONS.

Usage
-----
    python research/transcript_bench/build_label_sheet.py
    python research/transcript_bench/build_label_sheet.py --per-video 50 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("sheet")

BENCH_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BENCH_DIR / "corpus"
LABELS_DIR = BENCH_DIR / "labels"
SCREEN_RESULTS = BENCH_DIR / "screen" / "_screen_results.json"

# Speaker-disjoint split. Channel names as reported by yt-dlp on 30 Aug 2026.
SELECTION_CHANNELS = {"Marques Brownlee", "Mrwhosetheboss"}

# Unratable criteria, fixed before sampling.
#
# no_speech_prob was trialled as a third criterion and REJECTED on evidence
# (31 Aug 2026). It is computed per 30-second Whisper decoding window, not per
# segment: measured across the corpus, a mean of 9.8 consecutive segments share
# each distinct value, in runs spanning 25-30 s. Excluding on it therefore drops
# speech in blocks irrespective of individual segment quality - it removed 21 of
# 49 segments from haWvrSliMVY, including clean sentences such as "Fourth thing
# you should know, really important". The field is still recorded on every
# segment for sensitivity analysis, but it is a window-level signal and is not
# used to exclude.
MIN_WORDS = 4          # below this there is not enough text to carry a sentiment
MAX_DURATION = 20.0    # a span this long is a music bed or montage, not an utterance

SEED = 42


def unratable_reason(seg: dict) -> str | None:
    if seg["word_count"] < MIN_WORDS:
        return f"under {MIN_WORDS} words"
    if seg["duration"] > MAX_DURATION:
        return f"duration {seg['duration']:.1f}s > {MAX_DURATION}s"
    return None


def load_corpus() -> dict[str, list[dict]]:
    corpus: dict[str, list[dict]] = {}
    for f in sorted(CORPUS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        corpus[d["video_id"]] = d["segments"]
    return corpus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-video", type=int, default=50)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=LABELS_DIR / "transcript_label_sheet.csv")
    args = ap.parse_args()

    if not CORPUS_DIR.is_dir():
        logger.error("run transcribe_corpus.py first")
        return 1

    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    corpus = load_corpus()
    channels = {r["video_id"]: r.get("channel")
                for r in json.loads(SCREEN_RESULTS.read_text()) if r.get("video_id")}

    rng = random.Random(args.seed)
    selected: list[dict] = []
    stats: list[dict] = []

    for vid, segs in sorted(corpus.items()):
        channel = channels.get(vid) or "unknown"
        split = "selection" if channel in SELECTION_CHANNELS else "confirmation"

        eligible, excluded = [], []
        for i, s in enumerate(segs):
            reason = unratable_reason(s)
            (excluded if reason else eligible).append((i, s, reason))

        take = min(args.per_video, len(eligible))
        picked = rng.sample(eligible, take)

        for idx, seg, _ in picked:
            selected.append({
                "segment_uid": f"{vid}:{seg['segment_id']}",
                "video_id": vid,
                "channel": channel,
                "split": split,
                "start_time": seg["start_time"],
                "duration": seg["duration"],
                "word_count": seg["word_count"],
                "context_before": segs[idx - 1]["text"] if idx > 0 else "",
                "text": seg["text"],
                "context_after": segs[idx + 1]["text"] if idx + 1 < len(segs) else "",
            })

        stats.append({"video_id": vid, "channel": channel, "split": split,
                      "total": len(segs), "eligible": len(eligible),
                      "excluded": len(excluded), "sampled": take})

    # Interleave the two splits so the rater cannot tell them apart.
    rng.shuffle(selected)

    uids = [r["segment_uid"] for r in selected]
    assert len(uids) == len(set(uids)), "duplicate segment in sheet"
    sel_vids = {r["video_id"] for r in selected if r["split"] == "selection"}
    con_vids = {r["video_id"] for r in selected if r["split"] == "confirmation"}
    assert not (sel_vids & con_vids), "SPLIT LEAKAGE: a video appears in both sets"
    sel_ch = {r["channel"] for r in selected if r["split"] == "selection"}
    con_ch = {r["channel"] for r in selected if r["split"] == "confirmation"}
    assert not (sel_ch & con_ch), "SPEAKER LEAKAGE: a channel appears in both sets"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "segment_uid", "context_before_DO_NOT_RATE",
                    "TEXT_TO_RATE", "context_after_DO_NOT_RATE",
                    "label_POSITIVE_NEUTRAL_NEGATIVE"])
        for n, r in enumerate(selected, 1):
            w.writerow([n, r["segment_uid"], r["context_before"], r["text"],
                        r["context_after"], ""])

    manifest = BENCH_DIR / "_sheet_manifest.json"
    manifest.write_text(json.dumps({
        "seed": args.seed,
        "per_video": args.per_video,
        "unratable_criteria": {"min_words": MIN_WORDS,
                               "max_duration_s": MAX_DURATION,
                               "no_speech_prob": "rejected - window-level statistic"},
        "selection_channels": sorted(SELECTION_CHANNELS),
        "row_count": len(selected),
        "per_video_stats": stats,
        "rows": [{k: r[k] for k in ("segment_uid", "video_id", "channel", "split",
                                    "start_time", "duration", "word_count")}
                 for r in selected],
    }, indent=2))

    print(f"\n{'video_id':13} {'split':13} {'total':>6} {'elig':>5} {'excl':>5} {'take':>5}  channel")
    print("-" * 86)
    for s in sorted(stats, key=lambda x: (x["split"], x["video_id"])):
        print(f"{s['video_id']:13} {s['split']:13} {s['total']:>6} {s['eligible']:>5} "
              f"{s['excluded']:>5} {s['sampled']:>5}  {s['channel']}")
    n_sel = sum(1 for r in selected if r["split"] == "selection")
    n_con = len(selected) - n_sel
    print("-" * 86)
    print(f"selection    : {n_sel:4} rows, {len(sel_vids)} videos, {len(sel_ch)} speakers")
    print(f"confirmation : {n_con:4} rows, {len(con_vids)} videos, {len(con_ch)} speakers")
    print(f"TOTAL        : {len(selected):4} rows")
    print(f"\nsheet    : {args.out}")
    print(f"manifest : {manifest}  (rater must not open this)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
