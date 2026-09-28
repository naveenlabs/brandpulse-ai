"""
extract_figures.py — derive every figure the interface prints from real files.

Why this exists
---------------
The project's evidence rule (README, "Engineering rules") forbids any number that was not measured on this project's own
data, and the interface prints numbers. This script is the audit trail: it reads
`outputs/*.json` and the bench write-ups, recomputes every figure the UI shows,
and writes `ui_evidence/figures.json`. Nothing in `static/` may print a figure
that is not in that file.

Run it:
    python evaluation/ui_evidence/extract_figures.py

It is idempotent, reads only, and needs no model, no network and no Ollama.

Two classes of figure, deliberately kept apart
----------------------------------------------
`corpus`  — recomputed here from the saved reports in `outputs/*.json`, so it
            describes what is on disk when this runs: re-run it after adding or
            deleting a report.
`channels`— per-channel accuracies measured in the benches. This script does not
            re-run those benches; it asserts that each quoted figure still
            appears verbatim in the write-up it is attributed to, so a silently
            edited source file breaks the build rather than the claim.

A caution recorded on the corpus figures, and repeated in the UI: the saved
reports were NOT produced by one system. The controller was swapped on 05 Sep 2026
(`llama3.2` -> `llama3.1:8b`) and that choice is worth ~49 points of Authenticity on
identical inputs (controller_bench/ SS10.1). How many reports fall on each side of
that date is DERIVED here from each file's modification time rather than asserted,
because a saved report carries no timestamp of its own -- see `written_*` below,
and note that mtime is the only provenance on disk and a file copy would reset it.
Corpus figures therefore describe what is on disk. They are not a performance
claim about the current system, and the interface does not present them as one.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

# 05 Sep 2026, the day controller_bench/ closed and llama3.1:8b replaced
# llama3.2 in the orchestrator. Reports are sorted against it by file mtime.
CONTROLLER_SWAP_EPOCH = datetime(2026, 9, 5, tzinfo=timezone.utc).timestamp()

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
FIGURES = Path(__file__).resolve().parent / "figures.json"

# A channel is disclosed as thinly covered on a given report when it carries a
# usable reading on fewer than this share of that report's segments. This is an
# editorial threshold for when to warn a reader, not a measured quantity, and it
# is duplicated in ui/src/lib/contract.js as CHANNEL_COVERAGE_FLOOR. A test asserts
# the two agree.
CHANNEL_COVERAGE_FLOOR = 0.5

# The eleven-character YouTube id inside a report's video_url.
#
# `distinct_videos` counted distinct video_url *strings* until 19 Sep 2026. The
# same video saved under two URL forms — youtu.be/<id> against watch?v=<id>, or
# two different `?si=` tracking parameters — counted twice, so the figure was an
# overcount of URL spellings rather than a count of videos. On the nine reports
# on disk at the time it reported six where the truth was four. Keyed on the id,
# the number is now the number of videos.
_VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_\-]{11})")


def _video_key(video_url: str) -> str:
    """
    The video id, or the raw URL when no id can be read from it.

    Falling back to the URL keeps an unparseable entry counted as its own video
    rather than silently collapsing every such report into one bucket, which
    would undercount instead of overcounting.
    """
    match = _VIDEO_ID.search(str(video_url))
    return match.group(1) if match else str(video_url)

# Facial-emotion labels that carry no valence, mirroring pipeline/orchestrator.py
# `_VALENCE_WORDS`. "surprise" is absent from that mapping on purpose: surprise is
# not inherently positive or negative, so it is a gap, not a reading.
VALENCE_WORDS = {
    "positive": "POSITIVE", "happy": "POSITIVE",
    "neutral": "NEUTRAL",
    "negative": "NEGATIVE", "sad": "NEGATIVE", "angry": "NEGATIVE",
    "fear": "NEGATIVE", "disgust": "NEGATIVE",
}


def to_valence(raw) -> str | None:
    """Map a channel label onto POSITIVE/NEUTRAL/NEGATIVE, or None for 'no reading'."""
    if not isinstance(raw, str):
        return None
    return VALENCE_WORDS.get(raw.strip().lower())


def vocal_label(raw) -> str | None:
    """
    Read a vocal reading through both shapes the saved reports actually use.

    Eight of the nine reports store a bare emotion word ("angry"); the ninth,
    written after the 02 Sep 2026 vocal swap, stores a dict with a three-class
    `label`. Both are real and both must read.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        lab = raw.get("label")
        return lab if isinstance(lab, str) else None
    return None


def corpus_figures() -> dict:
    """Recompute every corpus-level figure from outputs/*.json."""
    paths = sorted(OUTPUTS.glob("*.json"))
    if not paths:
        raise SystemExit("no reports in outputs/ — nothing to derive")

    reports, videos = [], set()
    segments = comments = flagged = 0
    # Two different absences, counted separately because they mean different
    # things and conflating them would overstate the detector's failure rate:
    #   no_face      — DeepFace found no face at all (`dominant` is null)
    #   no_valence   — no usable POSITIVE/NEUTRAL/NEGATIVE reading. This is
    #                  no_face PLUS every frame pooled to "surprise", which the
    #                  orchestrator excludes from the valence axis on purpose.
    # The timeline draws a gap for no_valence; the coverage warning quotes it.
    no_face = no_valence = surprise = 0
    auth, health = [], []
    channel_readings = {"transcript": 0, "facial": 0, "vocal": 0}

    for path in paths:
        with open(path, encoding="utf-8") as fh:
            rep = json.load(fh)

        segs = rep.get("all_segments") or []
        n_no_face = n_no_valence = 0
        for seg in segs:
            mo = seg.get("model_outputs") or {}
            fe = mo.get("facial_emotion") or {}
            dominant = fe.get("dominant")
            if dominant is None:
                n_no_face += 1
            elif str(dominant).strip().lower() == "surprise":
                surprise += 1
            if to_valence(dominant) is None:
                n_no_valence += 1
            else:
                channel_readings["facial"] += 1
            if to_valence((mo.get("transcript_sentiment") or {}).get("label")):
                channel_readings["transcript"] += 1
            if to_valence(vocal_label(mo.get("vocal_emotion"))):
                channel_readings["vocal"] += 1

        segments += len(segs)
        no_face += n_no_face
        no_valence += n_no_valence
        flagged += len(rep.get("flagged_segments") or [])
        comments += len(rep.get("all_comments") or [])
        auth.append(rep.get("authenticity_score"))
        health.append(rep.get("brand_health_score"))
        videos.add(_video_key(rep.get("video_url", "")))

        # A saved report carries no timestamp, so the file's own mtime is the
        # only provenance there is. Recorded, and labelled as what it is.
        written_at = path.stat().st_mtime
        reports.append({
            "filename": path.name,
            "brand_name": rep.get("brand_name"),
            "written_at": round(written_at, 3),
            "written_after_controller_swap": written_at >= CONTROLLER_SWAP_EPOCH,
            "segments": len(segs),
            "no_face_segments": n_no_face,
            "no_valence_segments": n_no_valence,
            "no_face_share": round(n_no_face / len(segs), 4) if segs else None,
            "flagged": len(rep.get("flagged_segments") or []),
            "authenticity_score": rep.get("authenticity_score"),
            "brand_health_score": rep.get("brand_health_score"),
            "has_vocal_caveat": "vocal_caveat" in rep,
            "vocal_emotion_shape": (
                "dict" if segs and isinstance(
                    (segs[0].get("model_outputs") or {}).get("vocal_emotion"), dict
                ) else "str"
            ),
        })

    worst = max(reports, key=lambda r: r["no_face_share"] or 0)
    after_swap = sum(1 for r in reports if r["written_after_controller_swap"])

    return {
        "report_count": len(reports),
        "distinct_videos": len(videos),
        "segments_total": segments,
        "comments_total": comments,
        "controller_calls_total": segments,   # one Ollama call per segment
        "no_face_segments": no_face,
        "no_face_share_pct": round(100 * no_face / segments, 1),
        "surprise_segments": surprise,
        "no_valence_segments": no_valence,
        "no_valence_share_pct": round(100 * no_valence / segments, 1),
        "worst_no_face_report": worst["filename"],
        "worst_no_face_share_pct": round(100 * worst["no_face_share"], 1),
        "best_no_face_share_pct": round(
            100 * min(r["no_face_share"] for r in reports), 1
        ),
        "flagged_total": flagged,
        "authenticity_min": min(auth),
        "authenticity_max": max(auth),
        "brand_health_min": min(health),
        "brand_health_max": max(health),
        "largest_report_segments": max(r["segments"] for r in reports),
        "channel_readings": channel_readings,
        "reports": reports,
        "written_after_controller_swap": after_swap,
        "written_before_controller_swap": len(reports) - after_swap,
        "provenance_basis": "file modification time in outputs/",
        "caution": (
            f"Descriptive of the {len(reports)} runs saved on disk, not a performance "
            f"claim. By file date {len(reports) - after_swap} predate the 05 Sep 2026 "
            f"controller swap and {after_swap} postdate it; controller_bench/ measured "
            "that swap at ~49 points of Authenticity on byte-identical channel inputs."
        ),
    }


# Each channel figure, the file it came from, and the exact string that must
# still appear in that file for the figure to be quotable.
CHANNEL_SOURCES = [
    {
        "channel": "comment", "label": "Audience comments",
        "model": "cardiffnlp XLM-RoBERTa, fine-tuned",
        "accuracy_pct": 78.7, "n": 150, "correct": 118,
        "basis": "two videos neither model was trained on",
        "source": "comment_bench/v2/holdout/HOLDOUT_RESULT.md",
        "must_contain": ["78.67%", "(118/150)"],
    },
    {
        "channel": "transcript", "label": "Transcript sentiment",
        "model": "cardiffnlp XLM-RoBERTa",
        "accuracy_pct": 67.8, "n": 199, "correct": None,
        "basis": "199 segments, 4 speakers that played no part in selection",
        "source": "transcript_bench/WINNER.md",
        "must_contain": ["0.678", "199 segments"],
    },
    {
        "channel": "vocal", "label": "Vocal prosody",
        "model": "audeering wav2vec2, read on arousal",
        "accuracy_pct": 48.9, "n": 47, "correct": 23,
        "basis": "held-out speakers",
        "source": "vocal_bench/VOCAL_MODEL_ANALYSIS.md",
        "must_contain": ["48.9%", "23/47"],
    },
    {
        "channel": "facial", "label": "Facial emotion",
        "model": "DeepFace FER-2013 head",
        "accuracy_pct": 34.2, "n": 114, "correct": 39,
        "basis": "held-out speakers",
        "source": "facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md",
        "must_contain": ["34.2%", "(39/114)"],
    },
]

# Two reference points the facial figure is meaningless without.
FACIAL_REFERENCES = [
    {
        "name": "always-NEUTRAL constant", "value_pct": 67.5, "n": 114, "correct": 77,
        "source": "facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md",
        "must_contain": ["67.5%", "(77/114)"],
    },
    {
        "name": "human ceiling", "value_pct": 87.5, "n": 48, "correct": 42,
        "note": "48 hidden duplicate frames, Cohen's kappa 0.804",
        "source": "facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md",
        "must_contain": ["87.5%", "(42/48)", "0.804"],
    },
]


# The controller swap, as the one comparison on the overview page that a shared
# axis is honest for. Every other pair of numbers there was measured on a
# different task; these four were measured on byte-identical payloads under the
# same prompt, which is what makes the four bars mean the same thing.
#
# The column is "polar detected" in both tables of CONTROLLER_MODEL_ANALYSIS.md
# (SS9 grid, SS12 real segments). It is NOT the flag rate, and the two must not
# be conflated: `rule_baseline` detects 62/62 and flags 0/62, which is the
# unreachable-threshold finding recorded separately in PAGE_CLAIMS.
#
# Stored as fractions, not percentages. The page draws the bar from the ratio
# and prints the fraction, so no rounded percentage is asserted that the
# write-up does not itself state.
CONTROLLER_REFERENCES = [
    {
        "model": "llama3.2", "role": "replaced 05 Sep 2026",
        "probe": "constructed polar probes", "detected": 8, "total": 62,
        "source": "controller_bench/CONTROLLER_MODEL_ANALYSIS.md",
        "must_contain": ["8 of 62", "12.9%"],
    },
    {
        "model": "llama3.1:8b", "role": "adopted 05 Sep 2026",
        "probe": "constructed polar probes", "detected": 62, "total": 62,
        "source": "controller_bench/CONTROLLER_MODEL_ANALYSIS.md",
        "must_contain": ["62 of 62"],
    },
    {
        "model": "llama3.2", "role": "replaced 05 Sep 2026",
        "probe": "real cached segments", "detected": 11, "total": 81,
        "source": "controller_bench/CONTROLLER_MODEL_ANALYSIS.md",
        "must_contain": ["11 of 81"],
    },
    {
        "model": "llama3.1:8b", "role": "adopted 05 Sep 2026",
        "probe": "real cached segments", "detected": 81, "total": 81,
        "source": "controller_bench/CONTROLLER_MODEL_ANALYSIS.md",
        "must_contain": ["81 of 81"],
    },
]


# Every other figure the overview page prints, and the file it is traceable to.
# These are not corpus statistics and this script does not re-run the benches
# that produced them; it asserts the figure still appears in the write-up it is
# attributed to, so a claim cannot outlive its evidence. Together with
# CHANNEL_SOURCES and FACIAL_REFERENCES this covers every number on the page.
PAGE_CLAIMS = [
    {
        "claim": "facial channel calls 33.8% of verified-neutral held-out frames NEGATIVE",
        "source": "facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md",
        "must_contain": ["33.8%"],
    },
    {
        "claim": "yunet: 98.1% on unseen faces, 0 false positives on 251 faceless frames",
        "source": "facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md",
        "must_contain": ["98.1%", "0 of 251"],
    },
    {
        "claim": "vocal channel within-video rank correlation +0.159 over 147 clips",
        "source": "vocal_bench/SPEAKER_NORM_RESULT.md",
        "must_contain": ["+0.159"],
    },
    {
        "claim": "a perfect implementation of the scoring rule flags 0 of 62 polar probes",
        "source": "controller_bench/CONTROLLER_MODEL_ANALYSIS.md",
        "must_contain": ["0 of 62"],
    },
    {
        "claim": "the controller swap moved mean Authenticity by 49.08 points",
        "source": "controller_bench/CONTROLLER_MODEL_ANALYSIS.md",
        "must_contain": ["49.08"],
    },
    # Until 26 Sep 2026 a sixth entry checked a Brandwatch figure (60-75%)
    # against a planning document outside this repository. Only the retired
    # landing page printed it, and without that document a clean
    # checkout could not run this script at all.
]


def verify_sources(entries: list[dict]) -> list[str]:
    """Fail loudly if a quoted figure no longer appears in the file it cites."""
    problems = []
    for entry in entries:
        path = ROOT / "research" / entry["source"]
        if not path.exists():
            problems.append(f"{entry['source']}: file missing")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in entry["must_contain"]:
            if needle not in text:
                problems.append(f"{entry['source']}: {needle!r} no longer present")
    return problems


def pipeline_constants() -> dict:
    """Read the live constants out of the pipeline rather than restating them."""
    orch = (ROOT / "pipeline" / "orchestrator.py").read_text(encoding="utf-8")

    def const(name: str) -> str:
        match = re.search(rf"^{name}\s*=\s*([0-9.]+)", orch, re.M)
        if not match:
            raise SystemExit(f"could not read {name} from pipeline/orchestrator.py")
        return match.group(1)

    return {
        "conflict_flag_threshold": float(const("CONFLICT_FLAG_THRESHOLD")),
        "vocal_only_conflict_weight": float(const("VOCAL_ONLY_CONFLICT_WEIGHT")),
        "facial_only_conflict_weight": float(const("FACIAL_ONLY_CONFLICT_WEIGHT")),
        "ollama_model": re.search(r'OLLAMA_MODEL.*?"([^"]+)"\)', orch).group(1),
        "ollama_base_url": re.search(r'OLLAMA_BASE_URL.*?"(http[^"]+)"\)', orch).group(1),
        "channel_coverage_floor": CHANNEL_COVERAGE_FLOOR,
    }


def test_count() -> int:
    """Count the tests that exist, by collecting them rather than trusting a
    remembered number. Recorded in figures.json; no page prints it (the retired
    landing page did, as "tests passing", which only a full run licenses)."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True,
    )
    match = re.search(r"^(\d+) tests? collected", out.stdout, re.M)
    if not match:
        match = re.search(r"(\d+) tests? collected", out.stdout)
    if not match:
        raise SystemExit("could not count tests via pytest --collect-only")
    return int(match.group(1))


def main() -> int:
    problems = verify_sources(
        CHANNEL_SOURCES + FACIAL_REFERENCES + CONTROLLER_REFERENCES + PAGE_CLAIMS
    )
    if problems:
        print("SOURCE VERIFICATION FAILED:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    figures = {
        "generated_by": "ui_evidence/extract_figures.py",
        "corpus": corpus_figures(),
        "channels": CHANNEL_SOURCES,
        "facial_references": FACIAL_REFERENCES,
        "controller_references": CONTROLLER_REFERENCES,
        "page_claims": PAGE_CLAIMS,
        "pipeline": pipeline_constants(),
        "test_count": test_count(),
    }

    FIGURES.write_text(json.dumps(figures, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {FIGURES.relative_to(ROOT)}")
    print(f"  {figures['test_count']} tests collected")
    c = figures["corpus"]
    print(f"  {c['report_count']} reports · {c['segments_total']} segments · "
          f"{c['comments_total']} comments")
    print(f"  no face on {c['no_face_segments']} segments ({c['no_face_share_pct']}%); "
          f"no usable valence on {c['no_valence_segments']} ({c['no_valence_share_pct']}%) "
          f"— the difference is {c['surprise_segments']} 'surprise' segments")
    quoted = (len(CHANNEL_SOURCES) + len(FACIAL_REFERENCES)
              + len(CONTROLLER_REFERENCES) + len(PAGE_CLAIMS))
    print(f"  {quoted} quoted "
          f"figures verified against the files they are attributed to")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
