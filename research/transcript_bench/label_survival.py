"""
label_survival.py - how many of the 599 transcript labels survive a Whisper swap?

Written 01 Sep 2026, when the pipeline moved from Whisper `base` to
`large-v3-turbo` (whisper_bench/WHISPER_MODEL_ANALYSIS.md section 6).

The problem: the 599 hand labels in labels/transcript_label_sheet.csv were rated
against segments produced by `base`. A different Whisper model produces different
text and different boundaries, so some labels no longer describe any segment the
system actually produces.

Before this script, the re-labelling cost was an INFERENCE - "roughly a quarter,
extrapolated from boundary agreement on 12 clips". The project log flagged it as
unmeasured and said it must not be quoted as measured. This measures it.

Two questions, deliberately kept apart
--------------------------------------
An earlier version of this script asked only the first and reported its answer as
"labels needing rework". That was misleading and is corrected here: a boundary
moving is NOT the same as a label becoming wrong.

  Q1 BOUNDARIES - does the labelled passage still line up with ONE new segment?
     Answers "can labels be mapped 1:1 onto the new segmentation".

  Q2 CONTENT - do the labelled passage's WORDS still appear in the transcript at
     all, anywhere, ignoring where the cuts fall?
     Answers "is the label still describing real speech from this video".

Q2 is the one that decides whether re-labelling is needed, because the bench
loads its ground truth from labels/transcript_label_sheet.csv as (text, label)
pairs - verified: ground_truth.py never reads corpus/. The labels are a
self-contained dataset. Q1 only tells us how far the deployed segmentation has
drifted from the segmentation the sample was drawn from.

Method for Q1
-------------
Labels are matched on TEXT, not on segment id, because ids are assigned per run
and carry no meaning across models. For each labelled row, the best-matching
segment in the new corpus for that same video is found by difflib similarity on
normalised text, and the row is placed in one of four bands:

    identical   >= 0.99   text is the same; the label transfers with no doubt
    near        >= 0.90   trivial wording change (e.g. "Savash" -> "Sauvage");
                          sentiment cannot plausibly have flipped
    shifted     >= 0.60   boundary moved or wording changed materially;
                          needs a human to re-read it
    lost        <  0.60   no counterpart; needs re-labelling from scratch

The 0.90 and 0.60 cut-offs are a judgement call, not a derived constant. The full
similarity distribution is printed so the bands can be re-drawn by anyone who
disagrees, and the headline is always reported with the bands shown.

    python label_survival.py
    python label_survival.py --old corpus_base --new corpus
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
SHEET = BENCH_DIR / "labels" / "transcript_label_sheet.csv"
MANIFEST = BENCH_DIR / "_sheet_manifest.json"

IDENTICAL, NEAR, SHIFTED = 0.99, 0.90, 0.60


def norm(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Deliberately simpler than the WER normaliser: the question here is whether a
    human would consider this the same passage, not whether two ASR outputs
    agree token for token.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def load_labels() -> list[dict]:
    meta = {r["segment_uid"]: r for r in json.loads(MANIFEST.read_text())["rows"]}
    rows = []
    with SHEET.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            uid = row["segment_uid"]
            m = meta[uid]
            rows.append({
                "uid": uid,
                "video_id": m["video_id"],
                "channel": m["channel"],
                "split": m["split"],
                "label": row["label_POSITIVE_NEUTRAL_NEGATIVE"].strip(),
                "text": row["TEXT_TO_RATE"].strip(),
            })
    return rows


def load_corpus(directory: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted(directory.glob("*.json")):
        d = json.loads(f.read_text())
        out[d["video_id"]] = d["segments"]
    if not out:
        raise SystemExit(f"no corpus JSON in {directory}")
    return out


def best_match(text: str, segments: list[dict]) -> tuple[float, str]:
    target = norm(text)
    best, best_text = 0.0, ""
    for seg in segments:
        r = SequenceMatcher(None, target, norm(seg["text"])).ratio()
        if r > best:
            best, best_text = r, seg["text"]
    return best, best_text


def content_coverage(text: str, segments: list[dict]) -> float:
    """Q2: fraction of the labelled passage's words still present, in order.

    Matched against the WHOLE video transcript rather than any single segment, so
    a moved boundary cannot register as lost content. Coverage is one-sided on
    purpose - extra surrounding words in the transcript are irrelevant, only
    whether the labelled wording is still there.
    """
    target = norm(text).split()
    if not target:
        return 0.0
    doc = norm(" ".join(s["text"] for s in segments)).split()
    sm = SequenceMatcher(None, target, doc, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / len(target)


def content_band(c: float) -> str:
    if c >= 0.95:
        return "intact"
    if c >= 0.80:
        return "mostly"
    return "changed"


def band(score: float) -> str:
    if score >= IDENTICAL:
        return "identical"
    if score >= NEAR:
        return "near"
    if score >= SHIFTED:
        return "shifted"
    return "lost"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--old", default="corpus_base", help="pre-swap corpus dir")
    ap.add_argument("--new", default="corpus", help="post-swap corpus dir")
    ap.add_argument("--examples", type=int, default=6)
    args = ap.parse_args()

    labels = load_labels()
    new = load_corpus(BENCH_DIR / args.new)
    old_dir = BENCH_DIR / args.old
    old = load_corpus(old_dir) if old_dir.is_dir() else None

    old_model = new_model = "?"
    if old:
        old_model = json.loads(next(old_dir.glob("*.json")).read_text())["whisper_model"]
    new_model = json.loads(next((BENCH_DIR / args.new).glob("*.json")).read_text())["whisper_model"]

    print(f"Label survival: {old_model} -> {new_model}")
    print(f"{len(labels)} labels across {len({r['video_id'] for r in labels})} videos\n")

    results = []
    for row in labels:
        segs = new.get(row["video_id"], [])
        score, matched = best_match(row["text"], segs)
        cov = content_coverage(row["text"], segs)
        results.append({**row, "score": score, "matched": matched, "band": band(score),
                        "coverage": cov, "content_band": content_band(cov)})

    # Sanity control: the same labels matched against the corpus they came from
    # must score ~1.0. If they do not, the matcher is broken and every number
    # below is meaningless.
    if old:
        ctrl = [best_match(r["text"], old.get(r["video_id"], []))[0] for r in labels]
        lo = min(ctrl)
        print(f"control (labels vs their own {old_model} corpus): "
              f"min similarity {lo:.3f}, mean {sum(ctrl) / len(ctrl):.3f}")
        if lo < 0.95:
            print("  WARNING: control did not reproduce - treat results below as unreliable")
        print()

    counts = Counter(r["band"] for r in results)
    order = ["identical", "near", "shifted", "lost"]
    print(f"{'band':<12}{'labels':>8}{'share':>9}   meaning")
    print("-" * 74)
    meaning = {
        "identical": "aligns with one new segment exactly",
        "near": "aligns; wording changed trivially",
        "shifted": "passage now split across segments differently",
        "lost": "no single new segment covers it",
    }
    for b in order:
        n = counts.get(b, 0)
        print(f"{b:<12}{n:>8}{n / len(results) * 100:>8.1f}%   {meaning[b]}")

    reusable = counts.get("identical", 0) + counts.get("near", 0)
    rework = counts.get("shifted", 0) + counts.get("lost", 0)
    print("-" * 74)
    print(f"{'ALIGNED':<12}{reusable:>8}{reusable / len(results) * 100:>8.1f}%")
    print(f"{'MOVED':<12}{rework:>8}{rework / len(results) * 100:>8.1f}%")
    print("\n  NOTE: 'MOVED' means the cut points shifted, NOT that the label is\n"
          "  wrong. See the content check below, which is the one that matters.\n")

    by_split: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_split[r["split"]][r["band"]] += 1
    print(f"{'split':<14}{'n':>5}" + "".join(f"{b:>11}" for b in order) + f"{'reusable':>11}")
    print("-" * 76)
    for split in ("selection", "confirmation"):
        c = by_split[split]
        n = sum(c.values())
        ok = c.get("identical", 0) + c.get("near", 0)
        print(f"{split:<14}{n:>5}" + "".join(f"{c.get(b, 0):>11}" for b in order)
              + f"{ok / n * 100:>10.1f}%")
    print()

    cb = Counter(r["content_band"] for r in results)
    mean_cov = sum(r["coverage"] for r in results) / len(results)
    print("Q2 CONTENT - do the labelled words still appear anywhere in the transcript?")
    print("     (this is the question that decides whether re-labelling is needed)\n")
    cmeaning = {"intact": "wording unchanged", "mostly": "minor wording drift",
                "changed": "wording genuinely different"}
    for b in ("intact", "mostly", "changed"):
        print(f"  {b:<10}{cb.get(b, 0):>5}{cb.get(b, 0) / len(results) * 100:>7.1f}%"
              f"   {cmeaning[b]}")
    print(f"\n  mean word coverage: {mean_cov:.3f}")
    worst_content = sorted(results, key=lambda r: r["coverage"])[:4]
    print("\n  labels whose wording genuinely changed:")
    for r in worst_content:
        print(f"    [{r['coverage']:.2f}] {r['text'][:88]}")
    print()

    print("Q1 similarity distribution (segment alignment):")
    buckets = Counter()
    for r in results:
        buckets[min(int(r["score"] * 10) / 10, 1.0)] += 1
    for k in sorted(buckets, reverse=True):
        bar = "#" * max(1, round(buckets[k] / len(results) * 60))
        print(f"  {k:.1f}-{min(k + 0.1, 1.0):.1f}  {buckets[k]:>4}  {bar}")
    print()

    worst = sorted(results, key=lambda r: r["score"])[:args.examples]
    print(f"{args.examples} worst-matching labels:")
    for r in worst:
        print(f"\n  [{r['score']:.2f}] {r['uid']}  ({r['label']})")
        print(f"    labelled: {r['text'][:110]}")
        print(f"    now     : {r['matched'][:110] or '(no match)'}")

    out = BENCH_DIR / "label_survival.json"
    out.write_text(json.dumps({
        "old_model": old_model, "new_model": new_model,
        "n_labels": len(results),
        "thresholds": {"identical": IDENTICAL, "near": NEAR, "shifted": SHIFTED},
        "bands": dict(counts),
        "content_bands": dict(cb),
        "mean_content_coverage": round(mean_cov, 4),
        "reusable": reusable, "rework": rework,
        "by_split": {k: dict(v) for k, v in by_split.items()},
        "rows": [{k: r[k] for k in ("uid", "split", "label", "score", "band",
                                     "coverage", "content_band")}
                 for r in results],
    }, indent=1))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
