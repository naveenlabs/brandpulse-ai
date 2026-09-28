"""
corpus.py — the 15-video facial corpus, and who is in each video.

Every field below was read from YouTube via `yt-dlp --skip-download --print` on
03 Sep 2026 and pasted here verbatim. Nothing is inferred, and nothing is
remembered from an earlier session.

`speaker` is the on-screen reviewer, taken from the uploading channel. It is the
unit the dev/holdout split is drawn on, NOT the video: five of these videos are
Marques Brownlee and four are Mrwhosetheboss, so a split drawn on videos would
put the same face on both sides and the holdout would be contaminated.
`vocal_bench/SPEAKER_NORM_RESULT.md` established held-out *speakers* as the
standard for this project; this follows it.

`tone_hint` records the title's own framing. It is a *sampling* aid — it is why
we expect this corpus to contain genuine criticism, where the v1 corpus contained
none (`FACIAL_MODEL_ANALYSIS.md` §2.1: zero NEGATIVE ground-truth labels). It is
never used as a label, and never as evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"


@dataclass(frozen=True)
class Video:
    video_id: str
    speaker: str
    title: str
    duration_s: int
    height: int
    tone_hint: str          # from the title only; never a label
    in_v1: bool             # was this video part of the first facial bench?

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def dir(self) -> Path:
        return DATA / self.video_id

    @property
    def frames_dir(self) -> Path:
        return self.dir / "frames"

    def frame_count(self) -> int:
        if not self.frames_dir.is_dir():
            return 0
        return len(list(self.frames_dir.glob("frame_*.jpg")))


VIDEOS: tuple[Video, ...] = (
    # ── already on disk before 03 Sep 2026 ───────────────────────────────────
    Video("1VjPETN3m6U", "Jon Adams", "iPhone 17 Pro Max 6 months later // The GOOD and the BAD",
          572, 2160, "mixed", True),
    Video("JpN1DQdV4G4", "Seth Fowler", "Does It Work? Nike MIND 001 Mule Review & On Feet",
          827, 2160, "mixed", True),
    Video("SAb4zRyxrD4", "Marques Brownlee", "Samsung Galaxy S25/Ultra Impressions: What Happened?",
          563, 1920, "critical", False),
    # ── audio-only until 03 Sep 2026; video downloaded for this bench ────────
    Video("0jHtyF_rCqU", "Mrwhosetheboss", "Xiaomi 17 Pro Max review - Apple are you seeing this!?",
          776, 1920, "positive", False),
    Video("32slGhAH3Xc", "Mrwhosetheboss", "Samsung Z Flip 5 - Biggest Upgrade Ever.",
          621, 1920, "positive", False),
    Video("4KbrxIpQgkM", "Marques Brownlee", "Nothing Phone 3 Review: They Lied!",
          937, 1920, "critical", False),
    Video("5VMckmQneCk", "Mrwhosetheboss", "Samsung S25 Ultra Review - Things just got Messy.",
          954, 1920, "critical", False),
    Video("Gvvo6vUpJRc", "Marques Brownlee", "AirPods Max Review: Luxury Listening!",
          925, 1920, "positive", False),
    Video("Kk-RKpTAXmA", "ShortCircuit", "Can they LEGALLY say this?? - Sony WH-1000XM6",
          704, 1920, "critical", False),
    Video("Rlw_CI7pOKg", "The Tech Chap", "MacBook Air M5 Review - Forget the Neo!",
          765, 1920, "mixed", False),
    Video("SSC0RkJuBVw", "Mrwhosetheboss", "Apple Vision Pro - Is it worth $3500?",
          770, 1920, "sceptical", False),
    Video("haWvrSliMVY", "Jeremy Fragrance", "BEFORE YOU BUY - Bleu De Chanel in 2021 | Jeremy Fragrance",
          280, 1080, "positive", False),
    Video("i63u-iAnhuk", "Marques Brownlee", "Pixel 10/Pro Review: Good News and Bad News!",
          1219, 1920, "mixed", False),
    Video("q0aFOxT6TNw", "Marques Brownlee", "iPhone 17 Pro Review: Paradox in a Box!",
          741, 1920, "mixed", False),
    Video("vOhuf18b-g8", "Dave2D", "Samsung Fold 7 - Why Don't I Love This More??",
          433, 2160, "disappointed", False),
)

BY_ID = {v.video_id: v for v in VIDEOS}


def speakers() -> dict[str, list[Video]]:
    """Videos grouped by on-screen reviewer, insertion-ordered."""
    out: dict[str, list[Video]] = {}
    for v in VIDEOS:
        out.setdefault(v.speaker, []).append(v)
    return out


def needs_download() -> list[Video]:
    """Videos with no frames extracted yet."""
    return [v for v in VIDEOS if v.frame_count() == 0]


def summary() -> str:
    lines = [
        f"{len(VIDEOS)} videos, {len(speakers())} speakers, "
        f"{sum(v.duration_s for v in VIDEOS) / 60:.1f} min total",
        "",
        f"{'video_id':<14}{'speaker':<20}{'dur':>6}{'frames':>8}  tone",
    ]
    for v in VIDEOS:
        lines.append(
            f"{v.video_id:<14}{v.speaker:<20}{v.duration_s:>5}s{v.frame_count():>8}  {v.tone_hint}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
