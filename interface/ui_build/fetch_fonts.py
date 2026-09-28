"""
fetch_fonts.py — vendor this interface's typefaces into ui/public/fonts/.

Why this exists
---------------
The product's whole claim is that no pipeline data ever leaves the machine. A
page that fetched its own typefaces from a font host would contradict that claim
on every load, in front of a marker, while describing data sovereignty. So every
family is downloaded once at build time, subset, converted to woff2 and
committed. `flask run` then serves them from this repo and the browser makes no
external request at all. A test asserts no third-party host is named anywhere in
the built interface.

Two families, two speakers, both SIL Open Font License 1.1
----------------------------------------------------------
  Archivo     [wdth 62-125, wght 100-900]  THE INSTRUMENT. Everything the
              + matching italic            machine says: headings, labels,
                                           prose, every measured number, every
                                           timecode.

  Newsreader  [opsz 6-72, wght 200-800]    THE HUMAN AND THE EDITORIAL VOICE.
              + matching italic            Words a person said or wrote
                                           (transcript captions, audience
                                           comments), and the book's titles and
                                           editorial lines (tokens.css, TYPE).

An earlier version kept the serif to what a person said and never set it at
display size; the book's titles now use it too.

Why Archivo's width axis matters enough to keep
-----------------------------------------------
`wdth` is used, not decorative: timecode and dense readouts are set narrow
(78-84) and headings wider (96-108). An earlier version also encoded how far
each channel was trusted, with the facial channel pinned at 72; that encoding
is gone, and no rule sets 72 now.

Subsetting therefore must not desubroutinize or drop variation axes, and the
`tnum` and `zero` features have to survive: measurements are set on tabular
figures with a slashed zero so a column of readouts aligns and a nought cannot
be misread as a letter.

There is deliberately no monospace family. Timecode is Archivo at wdth 78 with
tabular figures, which aligns just as well and avoids the generated-design tell
of a monospace face used for small data labels.

Run it (needs network; build-time only):
    python interface/ui_build/fetch_fonts.py

Idempotent: re-downloads, re-subsets and overwrites. The licences are written
alongside the fonts because redistributing an OFL font without its licence text
is a licence violation, and this repo is a submitted artefact.
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "interface" / "ui" / "public" / "fonts"
RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# The characters this interface can actually print: Latin-1 for the transcripts
# and the comments, typographic quotes and dashes for the prose, the arithmetic
# and measurement signs used in the readouts, and NBSP. Anything outside this set
# renders as .notdef, so widening it is a deliberate act rather than an oversight.
UNICODES = ",".join([
    "U+0020-007E",   # basic latin
    "U+00A0-00FF",   # latin-1 supplement (accented words in real comments)
    "U+0131",        # dotless i
    "U+0152-0153",   # OE ligatures
    "U+2010-2015",   # hyphens and dashes
    "U+2018-201A",   # single quotes
    "U+201C-201E",   # double quotes
    "U+2026",        # ellipsis
    "U+2032-2033",   # prime, double prime
    "U+2212",        # true minus
    "U+00D7",        # multiplication sign
    "U+2190-2193",   # arrows, used by the keyboard hints
    "U+00B1",        # plus-minus, used by the confidence intervals
    "U+03BA",        # kappa, quoted from the facial bench's agreement figure
])

FAMILIES = [
    {
        "dir": "archivo",
        "files": [
            ("Archivo[wdth,wght].ttf", "archivo-var.woff2"),
            ("Archivo-Italic[wdth,wght].ttf", "archivo-var-italic.woff2"),
        ],
        "licence": "OFL-Archivo.txt",
    },
    # Sora was listed here until 24 Sep 2026. It set three display lines (the
    # opening hero, the closing plate, the Analyse title) and nothing else;
    # the cohesion pass set those in Archivo like every other heading, so the
    # build is back to two families and Sora is no longer fetched or shipped.
    {
        "dir": "newsreader",
        "files": [
            ("Newsreader[opsz,wght].ttf", "newsreader-var.woff2"),
            ("Newsreader-Italic[opsz,wght].ttf", "newsreader-var-italic.woff2"),
        ],
        "licence": "OFL-Newsreader.txt",
    },
]

# Files from an earlier build of this interface. They are deleted rather than
# left behind: a committed font nothing references is dead weight in a submitted
# artefact, and tests/test_ui_documents.py asserts every font on disk is both
# referenced and licensed.
RETIRED = [
    "bricolage-var.woff2", "plex-sans-var.woff2",
    "plex-mono-400.woff2", "plex-mono-600.woff2",
    "source-serif-var.woff2", "source-serif-var-italic.woff2",
    "OFL-BricolageGrotesque.txt", "OFL-IBMPlexSans.txt",
    "OFL-IBMPlexMono.txt", "OFL-SourceSerif4.txt",
]


def download(url: str, target: Path) -> None:
    """Fetch one file, failing loudly rather than leaving a truncated font behind."""
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            target.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise SystemExit(f"could not fetch {url}: {exc}") from exc


def subset(source: Path, target: Path) -> None:
    """
    Subset to UNICODES and convert to woff2, keeping every variation axis.

    `--flavor=woff2` rather than a separate compression pass, and no
    `--desubroutinize`, so the variable axes survive: Archivo is useless on this
    interface without its width axis, and Newsreader without its optical size.

    `tnum` and `zero` are named explicitly because every measured figure on this
    interface is set on tabular numerals with a slashed zero.
    """
    subprocess.run(
        [
            sys.executable, "-m", "fontTools.subset", str(source),
            f"--unicodes={UNICODES}",
            "--layout-features=kern,liga,calt,tnum,lnum,zero,frac,case,ordn",
            "--flavor=woff2",
            f"--output-file={target}",
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    scratch = FONT_DIR / "_ttf"
    scratch.mkdir(exist_ok=True)

    removed = 0
    for name in RETIRED:
        stale = FONT_DIR / name
        if stale.exists():
            stale.unlink()
            removed += 1
    if removed:
        print(f"  removed {removed} file(s) from the previous build\n")

    total = 0
    for family in FAMILIES:
        base = f"{RAW}/{family['dir']}"

        licence_target = FONT_DIR / family["licence"]
        download(f"{base}/OFL.txt", licence_target)
        print(f"  {family['licence']}")

        for upstream, output in family["files"]:
            ttf = scratch / upstream
            download(f"{base}/{urllib.parse.quote(upstream)}", ttf)
            woff2 = FONT_DIR / output
            subset(ttf, woff2)
            size = woff2.stat().st_size
            total += size
            print(f"  {output:32s} {size / 1024:6.1f} KB")
            ttf.unlink()

    for leftover in scratch.iterdir():
        leftover.unlink()
    scratch.rmdir()

    print(f"\n{total / 1024:.1f} KB of typefaces into {FONT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
