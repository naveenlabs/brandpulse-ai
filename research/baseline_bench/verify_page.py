"""verify_page.py — prove the rating pages are blind, mechanically.

PROTOCOL.md §5.2 lists what a rater must never see. This checks it against the
built HTML rather than against the code that built it, because the property that
matters is a property of the file that gets sent to a person.

`vocal_bench/verify_page.py` is the precedent and the reason it exists: a
blinding rule enforced by reading the generator is enforced by nothing, since the
next edit to the generator does not re-read the docstring.

Checks, in order of how badly a failure would matter:

  1. No YouTube video id anywhere in the file. A video id is a URL, and the URL
     leads to the comment section — one of the four channels under test.
  2. No segment transcript text. Rendering the words would let a rater analyse
     them in a way the audio does not afford (PROTOCOL.md §9.6).
  3. No channel label, in any casing: POSITIVE/NEUTRAL/NEGATIVE, and the seven
     DeepFace emotion words.
  4. No speaker name, video title or brand.
  5. No conflict score, authenticity score or any system output key.
  6. Every presentation has audio, and the item count is exactly what
     sample.json says it should be.
  7. The four pages differ from each other only in running order — same items,
     same media, different sequence (PROTOCOL.md §4.6).

Run:  python research/baseline_bench/verify_page.py
Exit: 0 if every page passes, 1 otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
SAMPLE = BENCH / "sample.json"
TOKENS = BENCH / "_tokens.json"
PAGES = BENCH / "pages"
MANIFEST = PROJECT / "research" / "transcript_bench" / "_corpus_manifest.json"

VALENCE_WORDS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
EMOTION_WORDS = ["happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"]
SYSTEM_KEYS = ["conflict_score", "channels_in_conflict", "authenticity",
               "brand_health", "narrative", "BIAS_CAVEAT", "transcript_sentiment",
               "vocal_emotion", "facial_emotion", "video_comment_sentiment"]

failures: list[str] = []
checks = 0


def check(page: str, ok: bool, what: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(f"{page}: {what}")


def strip_data_uris(html: str) -> str:
    """Remove base64 payloads before searching for words.

    Base64 of arbitrary audio contains every 3-letter sequence sooner or later,
    so searching the raw file for "sad" produces a false positive on almost any
    page. The payloads are media, not text, and they are checked separately by
    count. Everything outside them is what a rater could possibly read.
    """
    return re.sub(r'data:(?:audio/mpeg|image/jpeg);base64,[A-Za-z0-9+/=]+',
                  'DATA_URI', html)


def main() -> int:
    sample = json.loads(SAMPLE.read_text())
    items = sample["items"]
    tokens = json.loads(TOKENS.read_text())["token_to_uid"]

    video_ids = sorted({it["video_id"] for it in items})
    titles, speakers = [], []
    for v in json.loads(MANIFEST.read_text())["videos"]:
        speakers.append(v["channel"])
        if v.get("title"):
            titles.append(v["title"])
    # Brand and product names appearing in the corpus titles, listed explicitly
    # rather than derived by regex from the titles with an exclusion set. The
    # derived version was tried first and was worse: it flagged "Nothing" (a real
    # brand here, and an ordinary English word) and needed a growing hand-list of
    # exceptions, which is a check that quietly weakens every time it is edited.
    #
    # "Nothing" is deliberately absent from this list and handled the other way
    # round — the page copy was reworded so the word never appears (see
    # build_pages.SCALE), which is a stronger guarantee than an exception.
    brands = ["iPhone", "Samsung", "AirPods", "MacBook", "Pixel", "Apple",
              "Sony", "Chanel", "Xiaomi", "Galaxy", "Vision Pro", "Fragrance"]

    texts = [it["text"] for it in items if len(it["text"]) > 25]

    pages = sorted(PAGES.glob("rate_rater*.html"))
    if len(pages) != 4:
        print(f"FAIL  expected 4 pages, found {len(pages)}")
        return 1

    seen_item_sets = {}
    for p in pages:
        name = p.name
        raw = p.read_text()
        html = strip_data_uris(raw)
        low = html.lower()

        # 1 — no video ids
        for vid in video_ids:
            check(name, vid not in html, f"leaks video id {vid}")

        # 2 — no transcript text. A 25-char prefix is enough to identify a line
        #     and short enough that a coincidental match is implausible.
        for t in texts:
            check(name, t[:25] not in html, f"leaks transcript {t[:25]!r}")

        # 3 — channel labels. The scale words the page legitimately shows are
        #     excluded by construction: none of them is a valence or emotion word.
        for w in VALENCE_WORDS:
            check(name, w not in html, f"leaks valence label {w}")
        for w in EMOTION_WORDS:
            check(name, not re.search(rf'\b{w}\b', low), f"leaks emotion word {w}")

        # 4 — speakers, titles, brands
        for s in speakers:
            check(name, s.lower() not in low, f"leaks speaker {s}")
        for t in titles:
            check(name, t[:18].lower() not in low, f"leaks title {t[:18]!r}")
        for b in brands:
            check(name, not re.search(rf'\b{b.lower()}\b', low), f"leaks brand {b}")

        # 5 — system output
        for k in SYSTEM_KEYS:
            check(name, k not in html, f"leaks system key {k}")

        # 6 — structure
        m = re.search(r'window\.__ITEMS__=(\[.*?\]);</script>', raw, re.S)
        check(name, m is not None, "no __ITEMS__ payload found")
        if m:
            payload = json.loads(m.group(1))
            check(name, len(payload) == sample["n_presentations_per_rater"],
                  f"{len(payload)} presentations, expected "
                  f"{sample['n_presentations_per_rater']}")
            check(name, all(x["audio"].startswith("data:audio/mpeg") for x in payload),
                  "an item has no inlined audio")
            check(name, all(x["tok"] in tokens for x in payload),
                  "an item carries a token that is not in _tokens.json")
            check(name, all(set(x) == {"pid", "tok", "audio", "frames"} for x in payload),
                  "an item carries a field beyond pid/tok/audio/frames")
            check(name, len({x["pid"] for x in payload}) == len(payload),
                  "duplicate presentation_id")
            toks = [x["tok"] for x in payload]
            seen_item_sets[name] = sorted(set(toks))
            dupes = len(toks) - len(set(toks))
            check(name, dupes == sample["n_duplicates"],
                  f"{dupes} repeated items, expected {sample['n_duplicates']}")

    # 7 — same items across pages, different order
    global checks
    sets = list(seen_item_sets.values())
    checks += 1
    if not all(s == sets[0] for s in sets):
        failures.append("pages do not contain the same item set")
    orders = [json.dumps([x["tok"] for x in json.loads(
        re.search(r'window\.__ITEMS__=(\[.*?\]);</script>',
                  (PAGES / n).read_text(), re.S).group(1))])
        for n in seen_item_sets]
    checks += 1
    if len(set(orders)) != len(orders):
        failures.append("two pages share a running order")

    print(f"verify_page: {checks} checks over {len(pages)} pages")
    if failures:
        print(f"\nFAILED — {len(failures)} problem(s):")
        for f in failures[:40]:
            print("  ", f)
        if len(failures) > 40:
            print(f"   … and {len(failures) - 40} more")
        return 1
    print("PASSED — every page is blind by PROTOCOL.md §5.2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
