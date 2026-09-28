"""Governance checks for research and inclusion documentation.

These checks verify that required artefacts exist, quantitative inclusion claims
remain aligned with their source data, and the consent record accurately states
the August pilot's limitations and pseudonymisation status.

Participant names are stored only in ``user_pilot/participants.local.txt`` and
are excluded from version control. Checks requiring private research records or
report source skip when those local files are unavailable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "evaluation" / "user_pilot"
CONSENT = PILOT / "CONSENT.md"
INSTRUMENT_V2 = PILOT / "PILOT_QUESTIONS_V2.md"
INSTRUMENT_V1 = PILOT / "PILOT_QUESTIONS.md"
ANALYSIS = ROOT / "docs" / "INCLUSION_ANALYSIS.md"

# The three people who took part on 02 Aug 2026. Local only: never in the repository.
NAMES_FILE = PILOT / "participants.local.txt"
PARTICIPANTS = tuple(
    line.strip() for line in NAMES_FILE.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
) if NAMES_FILE.exists() else ()
# Both report generations. The August draft is content_*.py and the September
# report is final_*.py; a check that watched only one would go quiet the moment
# the other became the live document.
_SRC = ROOT / "final_report" / "source"
REPORT_SOURCE = sorted([*_SRC.glob("content_*.py"), *_SRC.glob("final_*.py")])

needs_names = pytest.mark.skipif(
    not PARTICIPANTS, reason="the pilot participants' names are kept off the repository "
                             "(user_pilot/participants.local.txt is local only)")
needs_report = pytest.mark.skipif(
    not _SRC.exists(), reason="final_report/ is kept off the public repository")


@pytest.fixture(scope="module")
def consent() -> str:
    return CONSENT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def analysis() -> str:
    """Whitespace-normalised: the document is hard-wrapped, so a sentence that
    reads as one line is three lines in the file."""
    return re.sub(r"\s+", " ", ANALYSIS.read_text(encoding="utf-8"))


class TestTheArtefactsExistAndAreReachable:
    @pytest.mark.parametrize("path", [CONSENT, INSTRUMENT_V2, ANALYSIS])
    def test_it_exists_and_is_not_a_stub(self, path):
        assert path.exists(), f"{path.name} is missing"
        assert len(path.read_text(encoding="utf-8")) > 2000, f"{path.name} is a stub"

    def test_the_superseded_instrument_is_kept_and_says_so(self):
        """
        The August instrument is the record of what those three were actually
        asked. Overwriting it would destroy that; a pointer is enough.
        """
        v1 = INSTRUMENT_V1.read_text(encoding="utf-8")
        assert "Superseded" in v1
        assert "PILOT_QUESTIONS_V2.md" in v1
        assert "CONSENT.md" in v1

    def test_the_new_instrument_is_marked_unrun(self):
        """
        An unexecuted instrument must remain clearly distinguished from evidence.
        """
        v2 = INSTRUMENT_V2.read_text(encoding="utf-8")
        assert "NOT YET RUN" in v2
        assert not (PILOT / "RESPONSES_V2.md").exists(), \
            "responses exist; update the instrument status and record the findings"


class TestTheConsentRecordStaysAccurate:
    """
    CONSENT.md states that the three August participants are named in the
    submitted report. That is true today. These keep the document and the
    repository in step whichever way it changes.
    """

    @staticmethod
    def _named_in_report() -> set[str]:
        found = set()
        for path in REPORT_SOURCE:
            text = path.read_text(encoding="utf-8")
            found |= {name for name in PARTICIPANTS if name in text}
        return found

    @needs_report
    def test_the_report_source_exists_to_check(self):
        assert REPORT_SOURCE, "no report source found; this check cannot run"

    @needs_names
    @needs_report
    def test_the_document_matches_reality_in_both_directions(self, consent):
        named = self._named_in_report()
        # Pinned to the claim, not to one filename, so adding a second report
        # generation cannot silently take the check out of service.
        claims_named = "Their first names in the **submitted report** | **Yes**" in consent
        if named:
            assert claims_named, (
                f"{sorted(named)} are still named in the report source but "
                f"CONSENT.md no longer says so")
        else:
            assert not claims_named, (
                "the participants have been pseudonymised — update CONSENT.md, "
                "which still records them as named")

    @needs_names
    def test_the_participants_are_named_nowhere_in_the_repository(self):
        """
        The public repository carries pseudonyms only. Every text file a reader
        can open is checked, except the two folders kept off it.
        """
        kept_off = {"final_report", "report_drafts", "_retired_ui", "node_modules",
                    ".git", "venv", ".venv", "__pycache__"}
        pattern = re.compile(r"\b(" + "|".join(map(re.escape, PARTICIPANTS)) + r")\b")
        found = []
        for path in ROOT.rglob("*"):
            if path.suffix not in {".md", ".py", ".js", ".html", ".csv", ".txt"} \
                    or path == NAMES_FILE or kept_off & set(path.relative_to(ROOT).parts):
                continue
            if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                found.append(str(path.relative_to(ROOT)))
        assert not found, f"a pilot participant is named in {found}"

    def test_it_says_the_repository_is_pseudonymised(self, consent):
        flat = re.sub(r"\s+", " ", consent)
        assert "pseudonymised as **Participant A, Participant B and Participant C**" in flat

    def test_it_records_the_lapse_rather_than_starting_from_today(self, consent):
        assert "August 2026 pilot consent record" in consent
        for absent in ("Information sheet given", "Consent recorded",
                       "Withdrawal terms stated", "Retention period agreed"):
            assert absent in consent, f"the record does not cover {absent!r}"

    def test_it_records_retrospective_confirmation(self, consent):
        assert "Retrospective confirmation, 12 September 2026" in consent
        assert "No written confirmation was collected" in re.sub(r"\s+", " ", consent)

    def test_it_states_what_kind_of_consent_this_actually_is(self, consent):
        flat = re.sub(r"\s+", " ", consent)
        assert "retrospective verbal confirmation reported by the researcher" in flat
        assert "without a dated written response from each participant" in flat

    def test_the_template_it_was_adapted_from_is_named(self, consent):
        assert "Sample-Consent-Forms.docx" in consent


class TestEveryFigureInTheAnalysisStillHolds:
    """
    Each of these re-derives a number from the file that produced it. A
    stakeholder document that has drifted from the code is worse than none,
    because it reads as though it had been checked.
    """

    def test_the_face_crop_count(self, analysis):
        crops = list((ROOT / "research" / "facial_bench" / "v2" / "crops").glob("*"))
        stated = int(re.search(r"\*\*(\d+) aligned face crops\*\*", analysis).group(1))
        assert stated == len(crops), \
            f"the analysis says {stated} crops, there are {len(crops)}"

    def test_the_deployed_whisper_model(self, analysis):
        audio = (ROOT / "pipeline" / "audio_module.py").read_text(encoding="utf-8")
        deployed = re.search(r'WHISPER_MODEL_SIZE = os\.getenv\([^,]+,\s*"([^"]+)"',
                             audio).group(1)
        # Backticked, not bare. A bare substring test passes on any model whose
        # name is also an ordinary English word — "small" appears in this
        # document already, in "Corpus small, English, professional presenters".
        assert f"`{deployed}`" in analysis, \
            f"the analysis does not name the deployed model, {deployed}"

    def test_the_comment_ordering(self, analysis):
        comments = (ROOT / "pipeline" / "comment_module.py").read_text(encoding="utf-8")
        assert 'order="relevance"' in comments, \
            "comments are no longer relevance-ordered; the analysis says they are"
        assert 'order="relevance"' in analysis

    @needs_report
    def test_the_report_still_omits_the_people_it_scores(self, analysis):
        """
        §2.1 quotes the report's own stakeholder sentence. If creators or
        comment authors are ever added there, this analysis needs rewriting
        rather than quietly becoming unfair to the report.
        """
        design = (ROOT / "final_report" / "source" / "content_b.py").read_text(encoding="utf-8")
        section = design[design.index("3.1 Domain and Users"):][:3000]
        for missing in ("creator", "comment author", "the person in the video"):
            assert missing not in section.lower(), \
                f"§3.1 now mentions {missing!r}; INCLUSION_ANALYSIS.md §2 is out of date"

    def test_it_does_not_attribute_a_taxonomy_to_a_lecture(self, analysis):
        assert "uses measured inequalities from this project's own evaluation" in analysis
        assert "generic bias taxonomy" in analysis

    def test_it_says_which_disparity_is_cited_rather_than_measured(self, analysis):
        """The distinction this whole project turns on."""
        assert "cites a disparity it has not observed" in analysis
        assert "Not measured here:" in analysis
