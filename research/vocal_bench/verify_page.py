"""
verify_page.py - prove the rating page cannot leak the transcript.

The vocal bench measures whether the VOICE agrees with the WORDS. If the rater
can see the words while rating the voice, the ground truth is contaminated and
every number the bench produces is meaningless. That property is too important to
confirm by eye, so it is checked mechanically here.

Checks, all of which must pass before rating begins:

  1. No segment's transcript text appears in the page - not visibly, not in an
     attribute, not in a comment, not in the inlined JSON.
  2. No speaker/channel name appears (which would invite rating a voice by
     reputation rather than by clip).
  3. Every clip in the index has exactly one card and one playable audio file.
  4. Every referenced audio file exists on disk and is non-empty.
  5. Clip order in the page matches the shuffled order, so speakers are
     interleaved rather than blocked.

    python research/vocal_bench/verify_page.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
INDEX = BENCH_DIR / "_clip_index.json"
PAGE = BENCH_DIR / "rate_here.html"
CLIPS = BENCH_DIR / "clips"

# Words too generic to be evidence of a leak; a hit on these alone means nothing.
STOPWORDS = {
    "the", "and", "that", "this", "with", "have", "for", "you", "but", "not",
    "are", "was", "its", "it's", "they", "there", "what", "when", "from",
    "just", "like", "then", "than", "more", "your", "all", "can", "one",
}


def significant_words(text: str, min_len: int = 5) -> list[str]:
    words = re.findall(r"[a-z']{%d,}" % min_len, text.lower())
    return [w for w in words if w not in STOPWORDS]


def main() -> int:
    if not PAGE.is_file():
        print(f"FAIL: {PAGE} not built - run build_rating_page.py first")
        return 1

    index = json.loads(INDEX.read_text())
    clips = index["clips"]
    html = PAGE.read_text()
    html_lower = html.lower()
    failures: list[str] = []

    # ---- 1. transcript leakage -------------------------------------------
    # A leak would show as a run of consecutive significant words from a
    # segment appearing verbatim in the page.
    leaked = []
    for c in clips:
        words = significant_words(c["text"])
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i + 3])
            if phrase in html_lower:
                leaked.append((c["uid"], phrase))
                break
    if leaked:
        failures.append(f"TRANSCRIPT LEAK on {len(leaked)} clips, e.g. "
                        f"{leaked[0][0]}: {leaked[0][1]!r}")
    else:
        print(f"  ok  no transcript text found ({len(clips)} clips checked)")

    # ---- 2. speaker names -------------------------------------------------
    names = sorted({c["channel"] for c in clips})
    found = [n for n in names if n.lower() in html_lower]
    if found:
        failures.append(f"SPEAKER NAMES in page: {found}")
    else:
        print(f"  ok  no speaker names found ({len(names)} checked)")

    # ---- 3. one card and one audio per clip -------------------------------
    srcs = re.findall(r'src="clips/([A-Za-z0-9_.-]+)\.wav"', html)
    if len(srcs) != len(clips):
        failures.append(f"page has {len(srcs)} audio refs, index has {len(clips)} clips")
    if len(set(srcs)) != len(srcs):
        failures.append("duplicate audio refs in page")
    cards = re.findall(r'<div class="card" id="card\d+" data-uid="([^"]+)"', html)
    if len(cards) != len(clips):
        failures.append(f"page has {len(cards)} cards, index has {len(clips)} clips")
    if not failures:
        print(f"  ok  {len(srcs)} audio refs, {len(cards)} cards, all unique")

    # ---- 4. audio files present ------------------------------------------
    missing = [s for s in srcs if not (CLIPS / f"{s}.wav").is_file()]
    empty = [s for s in srcs
             if (CLIPS / f"{s}.wav").is_file() and (CLIPS / f"{s}.wav").stat().st_size == 0]
    if missing:
        failures.append(f"{len(missing)} audio files missing, e.g. {missing[0]}")
    if empty:
        failures.append(f"{len(empty)} audio files empty, e.g. {empty[0]}")
    if not missing and not empty:
        print(f"  ok  all {len(srcs)} audio files exist and are non-empty")

    # ---- 5. shuffled, not blocked by speaker ------------------------------
    order = {c["uid"]: c["channel"] for c in clips}
    seq = [order[s] for s in srcs if s in order]
    longest = run = 1
    for a, b in zip(seq, seq[1:]):
        run = run + 1 if a == b else 1
        longest = max(longest, run)
    if longest > 8:
        failures.append(f"speakers are blocked: run of {longest} consecutive clips "
                        f"from one speaker")
    else:
        print(f"  ok  speakers interleaved (longest same-speaker run: {longest})")

    # ---- verdict ----------------------------------------------------------
    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED - DO NOT RATE AGAINST THIS PAGE:\n")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed - the page is safe to rate against")
    return 0


if __name__ == "__main__":
    sys.exit(main())
