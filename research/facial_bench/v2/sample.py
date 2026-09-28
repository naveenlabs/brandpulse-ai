"""
sample.py — draw the labelling sample and the dev/holdout split.

Everything here is fixed by PROTOCOL.md §4 and §7 and by the seed. Run it once;
it refuses to overwrite an existing manifest, because a sample redrawn after
labels exist is not a sample any more.

    python sample.py            # draw, write sample.json
    python sample.py --show     # print the realised split without writing
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import corpus

SEED = 20260903                 # PROTOCOL.md §11
PER_VIDEO = 40                  # §4
RETEST_FRACTION = 0.08          # §4
RETEST_MIN_GAP = 60             # presentations between a frame and its re-test
HOLDOUT_MIN_SPEAKERS = 3        # §7
HOLDOUT_MIN_FRACTION = 0.25     # §7
FORCED_DEV = ("1VjPETN3m6U", "JpN1DQdV4G4")     # §7, contamination

MANIFEST = Path(__file__).parent / "sample.json"


def split_speakers() -> tuple[list[str], list[str]]:
    """
    Dev/holdout split over *speakers*, per PROTOCOL.md §7.

    Deterministic given SEED. Videos already analysed in v1 force their speaker
    into dev; the remaining speakers are shuffled and taken into the holdout
    until both the speaker-count and frame-share floors are met.
    """
    by_speaker = corpus.speakers()
    forced = {corpus.BY_ID[v].speaker for v in FORCED_DEV}

    eligible = sorted(s for s in by_speaker if s not in forced)
    rng = random.Random(SEED)
    rng.shuffle(eligible)

    total_frames = len(corpus.VIDEOS) * PER_VIDEO
    holdout: list[str] = []
    for speaker in eligible:
        held = sum(len(by_speaker[s]) for s in holdout) * PER_VIDEO
        if len(holdout) >= HOLDOUT_MIN_SPEAKERS and held >= HOLDOUT_MIN_FRACTION * total_frames:
            break
        holdout.append(speaker)

    dev = [s for s in by_speaker if s not in holdout]
    return dev, holdout


def draw() -> dict:
    """Draw the full manifest. Pure function of SEED and what is on disk."""
    dev_speakers, holdout_speakers = split_speakers()
    rng = random.Random(SEED)

    items: list[dict] = []
    missing: list[str] = []

    for v in corpus.VIDEOS:
        frames = sorted(v.frames_dir.glob("frame_*.jpg"))
        if len(frames) < PER_VIDEO:
            missing.append(f"{v.video_id} has {len(frames)} frames, need {PER_VIDEO}")
            continue
        chosen = rng.sample(frames, PER_VIDEO)
        for p in sorted(chosen):
            items.append({
                "uid": f"{v.video_id}:{p.stem}",
                "video_id": v.video_id,
                "frame": p.name,
                "path": f"../../data/{v.video_id}/frames/{p.name}",
                "speaker": v.speaker,
                "split": "holdout" if v.speaker in holdout_speakers else "dev",
                "retest": False,
            })

    if missing:
        raise SystemExit("Frames not ready:\n  " + "\n  ".join(missing))

    # Presentation order, shuffled across videos (§4)
    order = list(items)
    rng.shuffle(order)

    # Re-test subset (§4, §5.3): a copy re-inserted at least RETEST_MIN_GAP later.
    #
    # Candidates are drawn only from the head of the order. A frame shown near
    # the end leaves no room for the gap, and appending its re-test anyway would
    # silently produce pairs a few dozen apart — which measures short-term recall,
    # not the consistency §5.3 claims to measure. Restricting the pool keeps the
    # guarantee exact: insertions only ever lengthen the list ahead of an
    # original, so room available at draw time cannot be taken away later.
    n_retest = round(len(items) * RETEST_FRACTION)
    eligible = order[:len(order) - RETEST_MIN_GAP]
    if len(eligible) < n_retest:
        raise SystemExit(
            f"cannot place {n_retest} re-tests with a {RETEST_MIN_GAP}-frame gap "
            f"in {len(order)} presentations"
        )
    retest_items = rng.sample(eligible, n_retest)
    presentations = list(order)
    for it in retest_items:
        first = presentations.index(it)
        lo = first + RETEST_MIN_GAP
        pos = rng.randint(lo, len(presentations))
        copy = dict(it)
        copy["retest"] = True
        copy["uid"] = it["uid"] + "#r"
        copy["of"] = it["uid"]
        presentations.insert(pos, copy)

    return {
        "seed": SEED,
        "per_video": PER_VIDEO,
        "n_frames": len(items),
        "n_presentations": len(presentations),
        "n_retest": n_retest,
        "dev_speakers": dev_speakers,
        "holdout_speakers": holdout_speakers,
        "presentations": presentations,
    }


def describe(m: dict) -> str:
    by_speaker = corpus.speakers()
    lines = [
        f"seed {m['seed']} · {m['n_frames']} frames · "
        f"{m['n_presentations']} presentations ({m['n_retest']} re-tests)",
        "",
        "DEV      " + ", ".join(
            f"{s} ({len(by_speaker[s])}v)" for s in m["dev_speakers"]),
        "HOLDOUT  " + ", ".join(
            f"{s} ({len(by_speaker[s])}v)" for s in m["holdout_speakers"]),
        "",
    ]
    dev_n = sum(1 for p in m["presentations"] if p["split"] == "dev" and not p["retest"])
    hold_n = sum(1 for p in m["presentations"] if p["split"] == "holdout" and not p["retest"])
    lines.append(f"dev frames {dev_n} ({dev_n / m['n_frames']:.1%})   "
                 f"holdout frames {hold_n} ({hold_n / m['n_frames']:.1%})")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="print without writing")
    args = ap.parse_args()

    if MANIFEST.exists() and not args.show:
        raise SystemExit(
            f"{MANIFEST.name} already exists. A sample redrawn after labelling "
            "is not a sample. Delete it deliberately if you really mean to."
        )

    m = draw()
    print(describe(m))
    if not args.show:
        MANIFEST.write_text(json.dumps(m, indent=1))
        print(f"\nwrote {MANIFEST.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
