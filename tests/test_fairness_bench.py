"""
test_fairness_bench.py — the per-speaker facial cut, and the discipline round it.

Written 12 Sep 2026 with fairness_bench/.

Two jobs. The first is arithmetic: the bench's numbers must keep matching the
bench it re-cuts, because the whole claim of fairness_bench/ is that it is
facial_bench/v2 sliced differently rather than measured differently.

The second is the part a bench cannot enforce about itself — that it still
refuses the claims its own protocol forbids. A fairness bench that quietly
starts asserting a disparity it has not measured is worse than no fairness
bench, and that failure looks like success from the inside.

No browser, no network, no models.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "research" / "fairness_bench"
V2 = ROOT / "research" / "facial_bench" / "v2"
DEPLOYED = "deepface_fer"
CONSTANT = "always-NEUTRAL constant"


@pytest.fixture(scope="module")
def data() -> dict:
    path = BENCH / "per_speaker.json"
    assert path.exists(), "per_speaker.json missing — run fairness_bench/per_speaker.py"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def analysis() -> str:
    return re.sub(r"\s+", " ", (BENCH / "FAIRNESS_ANALYSIS.md").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def protocol() -> str:
    return re.sub(r"\s+", " ", (BENCH / "PROTOCOL.md").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def figures() -> dict:
    return json.loads((ROOT / "evaluation" / "ui_evidence" / "figures.json").read_text(encoding="utf-8"))


class TestItReproducesTheBenchItRecuts:
    """
    If these drift, the re-cut is measuring something else and every conclusion
    in FAIRNESS_ANALYSIS.md is about a different experiment.
    """

    def test_holdout_deployed_accuracy_matches_the_published_figure(self, data, figures):
        facial = next(c for c in figures["channels"] if c["channel"] == "facial")
        assert data["speakers"][DEPLOYED]["by_split"]["holdout"] == facial["accuracy_pct"]

    def test_holdout_constant_accuracy_matches_the_published_reference(self, data, figures):
        ref = next(r for r in figures["facial_references"] if "constant" in r["name"])
        assert data["speakers"][CONSTANT]["by_split"]["holdout"] == ref["value_pct"]

    def test_the_holdout_frame_count_matches(self, data, figures):
        ref = next(r for r in figures["facial_references"] if "constant" in r["name"])
        n = sum(s["n"] for s in data["speakers"][DEPLOYED]["per_speaker"].values()
                if s["split"] == "holdout")
        assert n == ref["n"]

    def test_it_does_not_reimplement_the_ground_truth(self):
        """
        The one thing that makes the numbers above agree. Two files that each
        implement the same mapping are two files that will quietly stop
        agreeing.
        """
        src = (BENCH / "per_speaker.py").read_text(encoding="utf-8")
        assert "import ground_truth_v2" in src
        assert "EXPRESSION_THREE" not in src, "the mapping is being re-implemented"

    def test_it_adds_no_data_of_its_own(self):
        """fairness_bench re-cuts; it does not collect."""
        for pattern in ("*.jpg", "*.png", "*.mp4", "*.wav"):
            assert not list(BENCH.glob(pattern)), f"{pattern} found in fairness_bench"

    def test_every_speaker_in_the_sample_is_accounted_for(self, data):
        sample = json.loads((V2 / "sample.json").read_text(encoding="utf-8"))
        expected = set(sample["dev_speakers"]) | set(sample["holdout_speakers"])
        assert set(data["speakers"][DEPLOYED]["per_speaker"]) == expected


class TestTheProtocolWasPreRegisteredAndKept:
    def test_the_protocol_exists_and_predates_its_results(self, protocol):
        assert "before any number in this directory was computed" in protocol

    def test_the_post_hoc_addition_is_recorded_as_an_amendment(self, protocol):
        assert "# Amendments" in protocol
        assert "A1 — 12 Sep 2026, after the primary output" in protocol
        assert "This is post-hoc and is labelled post-hoc everywhere it appears" in protocol

    def test_the_finding_rule_was_declared_in_advance(self, protocol):
        assert "the best and worst speaker's Wilson intervals do not overlap" in protocol

    def test_the_declared_rule_is_actually_applied(self, data, analysis):
        """
        The spread is 30.7 points and the intervals overlap, so by the rule the
        protocol set in advance it is NOT a finding — and the write-up has to
        say so rather than quoting the spread as though it were one.
        """
        spread = data["speakers"][DEPLOYED]["spread"]
        assert spread["intervals_disjoint"] is False
        assert "This is not a finding" in analysis
        assert "consistent with noise" in analysis

    def test_the_bench_adopts_nothing_and_says_so(self, protocol):
        assert "This bench **adopts nothing**" in protocol

    def test_monk_not_fitzpatrick_with_the_reason(self, protocol):
        assert "Monk Skin Tone Scale" in protocol
        assert "how skin responds to ultraviolet light" in protocol

    def test_the_instrument_does_not_reproduce_the_scale(self):
        """
        Transcribing ten colour values into the tool that measures colour,
        without being able to verify them, would introduce the error the bench
        is looking for.
        """
        tool = (BENCH / "monk_rating.html").read_text(encoding="utf-8")
        swatches = re.findall(r"#[0-9a-fA-F]{6}", tool)
        greys = {s.lower() for s in swatches}
        assert not (greys - {"#fafafa", "#ffffff", "#c0392b", "#fff6f5", "#f4f4f4"}), \
            f"the tool embeds colour swatches: {sorted(greys)}"
        assert "not reproduced here, on purpose" in tool


class TestItStillRefusesWhatItCannotShow:
    """The claims the protocol forbids. These are the ones that matter."""

    FORBIDDEN = (
        ("that the system is fair", "Not** that the system is fair"),
        ("that skin tone causes it", "Not** that the system is biased by skin tone"),
        ("that eight presenters generalise", "Not** that eight professional presenters represent anyone"),
    )

    @pytest.mark.parametrize("label,sentence", FORBIDDEN)
    def test_the_write_up_refuses_it(self, analysis, label, sentence):
        assert sentence in analysis, f"the write-up no longer refuses: {label}"

    def test_the_skin_tone_question_is_marked_unrun(self, analysis):
        assert "**Not run.**" in analysis
        assert not list(BENCH.glob("monk_ratings_*.json")), \
            "ratings exist — run the analysis and remove the unrun markers"

    def test_it_names_the_gap_it_leaves_open(self, analysis):
        assert "cite a skin-tone disparity it has not observed" in analysis

    def test_the_confound_is_stated(self, analysis, data):
        by_split = data["lift_post_hoc"]["mean_lift_by_split"]
        assert by_split["holdout"] < by_split["dev"]
        assert "cannot separate the two" in analysis

    def test_every_n_is_stated_beside_its_correlation(self, analysis):
        """n=8 is the whole context for a rank correlation over eight points."""
        for match in re.finditer(r"rho [−-]?0\.\d+", analysis):
            tail = analysis[match.end():match.end() + 40]
            assert "n=8" in tail or "n = 8" in tail, \
                f"a correlation is quoted without its n: {match.group(0)}"
