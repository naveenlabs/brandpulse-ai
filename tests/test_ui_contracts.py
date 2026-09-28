"""
test_ui_contracts.py — the interface's promise layer.

Rewritten 20 Sep 2026 with the fourth interface. It replaces the file of the
same name, which described the build retired that day.

WHY THIS FILE WAS REWRITTEN RATHER THAN PATCHED
-----------------------------------------------
Most of its assertions described a specific implementation: a `.prog` bar with
`--done` and `--each` custom properties, a `.rail__list` of nine numbered acts,
a `lib/timeline.js`, a `styles/base.css`. Those were the OLD DESIGN, and a test
that pins a design prevents the design from changing, which is the wrong way
round: appearance is a design decision and is allowed to change. It has now
changed three times.

What is NOT allowed to change is underneath, and every promise the retired file
made is still made here, re-pointed at the build that exists:

  * the interface describes the comparison the pipeline actually made
  * a channel that measured nothing is drawn as an absence, never as a value
  * the facial accuracy is never quoted without what it is worse than
  * no comment author, and no API key, can reach the page
  * untrusted text reaches the DOM through a safe sink
  * the bias caveat cannot be collapsed, hovered-for or dismissed
  * nothing on the page addresses a host other than the one serving it
  * every ending a run can reach is spoken, not only shown
  * reflow failures are allowed to surface rather than being masked
  * a control's accessible name leads with the words printed on it

One group is new. `TestTheDesignHoldsItsOwnLine` makes the design brief's ban
list mechanically enforceable, so the patterns this rebuild exists to remove
cannot drift back in unnoticed.

These read the SOURCE in ui/src/, because that is where the discipline has to
hold; test_ui_documents.py reads the built output in static/.

No browser, no network, no Ollama.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "interface" / "ui" / "src"
CONTRACT = SRC / "lib" / "contract.js"
ORCHESTRATOR = ROOT / "pipeline" / "orchestrator.py"
FIGURES = ROOT / "evaluation" / "ui_evidence" / "figures.json"
EXTRACT = ROOT / "evaluation" / "ui_evidence" / "extract_figures.py"
OUTPUTS = ROOT / "outputs"
FIXTURES = ROOT / "tests" / "fixtures"

PAGES =("opening", "report", "run", "library", "sweep")


# --------------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def orchestrator() -> str:
    return ORCHESTRATOR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def figures() -> dict:
    return json.loads(FIGURES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sources() -> dict[str, str]:
    """Every JavaScript module the interface ships, by relative path."""
    return {
        str(p.relative_to(SRC)): p.read_text(encoding="utf-8")
        for p in sorted(SRC.rglob("*.js"))
        if "_scratch" not in p.parts
    }


@pytest.fixture(scope="module")
def styles() -> dict[str, str]:
    return {
        str(p.relative_to(SRC)): p.read_text(encoding="utf-8")
        for p in sorted(SRC.rglob("*.css"))
    }


@pytest.fixture(scope="module")
def run(sources) -> str:
    return sources["pages/run.js"]


@pytest.fixture(scope="module")
def reports() -> list[dict]:
    """
    The corpus these contracts are checked against: the saved reports the
    repository ships, plus tests/fixtures/legacy_*.json, which keep a report of
    the pre-2 Sep shape (a bare vocal word, no vocal caveat) in the corpus after
    every report of that shape was deleted from outputs/. Both are committed, so
    an empty corpus is a failure, never a vacuous pass.
    """
    paths = sorted(OUTPUTS.glob("*.json")) + sorted(FIXTURES.glob("legacy_*.json"))
    corpus = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    assert any(p.parent == OUTPUTS for p in paths), "outputs/ holds no saved report"
    return corpus


def code_lines(source: str) -> list[str]:
    """
    The lines of a module that are code rather than commentary.

    A figure quoted in a doc comment is citing its source; a figure in a
    template string is being printed to a reader. Only the second kind is a
    claim, so only the second kind is policed.
    """
    out = []
    in_block = False
    for line in source.splitlines():
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*"):
            in_block = "*/" not in stripped
            continue
        if stripped.startswith(("//", "*")):
            continue
        out.append(line)
    return out


def js_object(source: str, name: str) -> dict[str, str]:
    """Pull a flat `key: "VALUE"` object literal out of a JS module."""
    match = re.search(rf"{name}\s*=\s*Object\.freeze\(\{{(.*?)\}}\)", source, re.S)
    assert match, f"{name} not found as a frozen object"
    return dict(re.findall(r"(\w+)\s*:\s*[\"'](\w+)[\"']", match.group(1)))


def py_dict(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"^{name}\s*=\s*\{{(.*?)^\}}", source, re.S | re.M)
    assert match, f"{name} not found in orchestrator.py"
    return dict(re.findall(r"[\"'](\w+)[\"']\s*:\s*[\"'](\w+)[\"']", match.group(1)))


def css_rules(sheet: str):
    """
    (selector, declarations) for every rule in a stylesheet, commentary removed.

    Deliberately naive: it does not model nesting, which is enough here because
    every rule this file asks about is flat. The selector is taken as the last
    line before the brace so that the first rule inside an @media block reports
    its own selector rather than the media prelude.
    """
    text = "\n".join(code_lines(sheet))
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selector = match.group(1).strip().splitlines()[-1].strip()
        yield selector, match.group(2)


# ------------------------------------------- the lexicon is not the interface's

# The opening page, as a reader gets it: pages/opening.js composes these
# sections (hero, seam, film, proof with its limits rail, close), so a claim the
# page makes can live in any of them.
OPENING_SECTIONS = ("pages/opening.js", "lib/hero.js", "lib/seam.js", "lib/film.js",
                    "lib/proof.js", "lib/limits.js", "lib/close.js")


def opening_page(sources):
    return "\n".join(sources[name] for name in OPENING_SECTIONS if name in sources)


class TestTheContractMirrorsThePipeline:
    """
    `contract.js` does not get to have its own opinion about what a reading
    means. If it drifts from the orchestrator, the interface is describing a
    comparison the system did not make.
    """

    def test_the_two_lexicons_are_identical(self, contract, orchestrator):
        assert js_object(contract, "VALENCE_WORDS") == py_dict(orchestrator, "_VALENCE_WORDS")

    def test_surprise_is_in_neither(self, contract, orchestrator):
        """
        Surprise is not inherently positive or negative, so the orchestrator
        excludes it and a segment whose face pooled to surprise has no facial
        valence at all. The pen lifts, exactly as it does with no face.
        """
        assert "surprise" not in js_object(contract, "VALENCE_WORDS")
        assert "surprise" not in py_dict(orchestrator, "_VALENCE_WORDS")

    def test_the_flag_threshold_is_the_orchestrators(self, contract, orchestrator):
        ours = re.search(r"CONFLICT_FLAG_THRESHOLD = ([\d.]+)", contract).group(1)
        theirs = re.search(r"CONFLICT_FLAG_THRESHOLD\s*=\s*([\d.]+)", orchestrator).group(1)
        assert float(ours) == float(theirs)

    def test_the_down_weights_the_pages_print_are_the_orchestrators(self, sources, orchestrator):
        """The facial down-weight is typed into the page text; it must be the one applied."""
        applied = {re.search(rf"{name}\s*=\s*([\d.]+)", orchestrator).group(1)
                   for name in ("FACIAL_ONLY_CONFLICT_WEIGHT", "VOCAL_ONLY_CONFLICT_WEIGHT")}
        printed = {(name, w) for name, code in sources.items() for line in code_lines(code)
                   for w in re.findall(r"down-weighted to (\d\.\d+)", line)}
        assert printed, "no page prints a down-weight, so this test checks nothing"
        assert {w for _, w in printed} <= applied, printed

    def test_the_coverage_floor_matches_the_evidence_script(self, contract):
        ours = re.search(r"CHANNEL_COVERAGE_FLOOR = ([\d.]+)", contract).group(1)
        theirs = re.search(r"CHANNEL_COVERAGE_FLOOR\s*=\s*([\d.]+)",
                           EXTRACT.read_text(encoding="utf-8")).group(1)
        assert float(ours) == float(theirs)


# --------------------------------------------- every quoted figure is measured

class TestEveryQuotedFigureIsMeasured:

    def test_channel_accuracies_match_the_evidence_file(self, contract, figures):
        by_channel = {
            ("audience" if c["channel"] == "comment" else c["channel"]): c
            for c in figures["channels"]
        }
        block = re.search(r"CHANNEL_META = Object\.freeze\(\{(.*?)\n\}\)", contract, re.S).group(1)
        for channel, entry in by_channel.items():
            found = re.search(rf"{channel}:\s*\{{(.*?)\n  \}}", block, re.S)
            assert found, f"{channel} is not in CHANNEL_META"
            quoted = re.search(r"accuracy:\s*([\d.]+)", found.group(1))
            assert quoted, f"{channel} quotes no accuracy"
            assert float(quoted.group(1)) == pytest.approx(entry["accuracy_pct"]), \
                f"{channel} quotes a figure the evidence file does not"

    def test_the_facial_reference_points_match(self, contract, figures):
        block = re.search(r"FACIAL_REFERENCES = Object\.freeze\(\{(.*?)\n\}\)",
                          contract, re.S).group(1)
        for ref in figures["facial_references"]:
            assert str(ref["value_pct"]) in block, \
                f"{ref['name']} at {ref['value_pct']} is not quoted"

    def test_the_facial_figure_is_never_quoted_without_what_it_is_worse_than(self, contract):
        """
        34.2% alone reads as a weak model. Against a constant that scores 67.5%
        it reads as what it is: a channel that is worse than saying nothing. The
        second number is what makes the first one honest, so the contract
        carries them together and cannot print one without the other.
        """
        assert "worseThanConstant" in contract
        block = re.search(r"facial:\s*\{(.*?)\n  \}", contract, re.S).group(1)
        assert "worseThanConstant" in block
        assert "67.5" in block or "always-NEUTRAL" in block

    def test_the_opening_page_says_which_reports_name_their_controller(self, sources):
        """
        Until 26 Sep 2026 the limits panel said "Every report says which one
        did", but a single report has never recorded its controller (a sweep's
        record does). The words follow what build_final_report writes.
        """
        from pipeline.scorer import build_final_report
        report = build_final_report(
            "https://youtu.be/dQw4w9WgXcQ", "Brand",
            [{"segment_id": 0, "start_time": 0.0, "end_time": 5.0, "text": "fine"}],
            [{"segment_id": 0, "start_s": 0.0, "end_s": 5.0, "conflict_score": 0.1,
              "conflict_reasons": [], "flagged": False}],
            {"label": "NEUTRAL", "confidence": 0.0, "comment_count": 0, "distribution": {}})
        records = any("controller" in key or "model" in key for key in report)
        proof = "\n".join(code_lines(sources["lib/proof.js"]))
        assert ("a single report does not yet" in proof) is (not records)

    def test_no_page_invents_an_accuracy(self, sources, figures):
        """
        A percentage printed in a template is a claim. Every one of them has to
        be a figure the evidence file actually contains, or be read from data at
        runtime rather than typed in.
        """
        known = {f"{c['accuracy_pct']}" for c in figures["channels"]}
        known |= {f"{r['value_pct']}" for r in figures["facial_references"]}
        known |= {"33.8", "98.1", "49.08", "0.62", "0.159", "0.056", "65", "251",
                  "48.9", "34.2", "67.5", "87.5", "0.342", "0.489", "0.75", "62"}
        offenders = []
        for name, code in sources.items():
            if not name.startswith("pages/"):
                continue
            for line in code_lines(code):
                for figure in re.findall(r"(?<![\w.])(\d{1,3}\.\d)%", line):
                    if figure not in known:
                        offenders.append((name, figure, line.strip()[:60]))
        assert not offenders, f"figures with no source in the evidence file: {offenders}"


# ------------------------------------------------- absence is drawn as absence

class TestAbsenceIsDrawnAsAbsence:
    """
    The single most important honesty rule in the interface. A channel that
    returned nothing for a segment must be drawn as a gap, never as a neutral
    reading, a zero, or a dash that could be mistaken for a measurement. On one
    report in this corpus 71.3% of segments carry no facial reading at all.
    """

    def test_a_channel_with_no_reading_is_omitted_not_defaulted(self, contract):
        block = re.search(r"export function segmentValences\(.*?\n\}", contract, re.S).group(0)
        assert "if (transcript) out.transcript" in block
        assert "if (facial) out.facial" in block
        assert "if (vocal) out.vocal" in block
        assert "if (audience) out.audience" in block
        assert "NEUTRAL" not in block, "a missing reading must not fall back to a value"

    def test_to_valence_returns_null_rather_than_a_default(self, contract):
        block = re.search(r"export function toValence\(.*?\n\}", contract, re.S).group(0)
        assert "|| null" in block

    def test_the_pen_lifts_instead_of_drawing_a_line(self, sources):
        """The transport skips the mark entirely rather than drawing it low."""
        transport = sources["lib/transport.js"]
        assert "if (!level) continue;" in transport
        assert "absence: the pen lifts off" in transport

    def test_a_missing_reading_is_never_mapped_to_the_middle_level(self, sources):
        transport = sources["lib/transport.js"]
        block = transport[transport.index("for (let i = 0; i < segments.length"):]
        block = block[:block.index("\n  }")]
        assert "LEVEL[level]" in block
        assert "LEVEL.NEUTRAL" not in block

    def test_the_absence_is_given_a_visible_mark_in_the_ledger(self, styles):
        """
        A gap in the trace is invisible at a glance in a table, so the ledger
        draws an absent channel as a HOLLOW mark rather than leaving the cell
        blank: a reader can see that the system looked and found nothing.
        """
        report = styles["styles/report.css"]
        assert '.le__glyphs i[data-v="none"]' in report
        rule = re.search(r'\.le__glyphs i\[data-v="none"\] \{([^}]*)\}', report).group(1)
        assert "transparent" in rule and "inset" in rule

    def test_a_gap_is_named_in_words_as_well_as_drawn(self, sources):
        """A picture of an absence is not available to a screen reader."""
        report = sources["pages/report.js"]
        assert "not measured" in report
        assert "no reading" in report

    def test_surprise_is_explained_rather_than_silently_dropped(self, contract):
        assert "surprise" in contract.lower()
        assert "not inherently positive or negative" in contract

    def test_a_confidence_that_was_never_reported_is_not_printed_as_zero(self, sources):
        report = sources["pages/report.js"]
        assert "conf != null ? confidence(conf)" in report

    def test_the_sparkline_breaks_rather_than_joining_across_a_gap(self, sources):
        """
        Joining two real points across a segment that measured nothing draws a
        line through data that does not exist.
        """
        report = sources["pages/report.js"]
        block = report[report.index("function wireSparks("):]
        block = block[:block.index("\n}")]
        assert "if (v == null) return null;" in block
        assert 'if (point == null) { open = false; continue; }' in block

    def test_the_corpus_still_contains_the_case_this_protects(self, reports, figures):
        """The guard only matters while the data can still exercise it."""
        assert figures["corpus"]["no_valence_segments"] > 0
        missing = sum(
            1 for report in reports for segment in report.get("all_segments", [])
            if not (segment.get("model_outputs") or {}).get("facial_emotion", {}).get("dominant")
        )
        assert missing > 0, "no segment in the corpus is missing a facial reading"


# ------------------------------------------------- both vocal shapes are read

class TestBothVocalShapesAreRead:
    """
    Reports saved before the 02 Sep 2026 vocal-model swap store a bare emotion
    word; later ones store a dict. Coding against either shape alone breaks the
    other. The shipped reports are all of the later shape, so the earlier one is
    kept in the corpus by tests/fixtures/legacy_report_june.json (trimmed from
    the June report committed at the repository root).
    """

    def test_both_shapes_are_actually_on_disk(self, reports):
        shapes = set()
        for report in reports:
            for segment in report.get("all_segments", []):
                vocal = (segment.get("model_outputs") or {}).get("vocal_emotion")
                if isinstance(vocal, str):
                    shapes.add("str")
                elif isinstance(vocal, dict):
                    shapes.add("dict")
        assert shapes == {"str", "dict"}, f"the corpus no longer exercises both: {shapes}"

    def test_the_reader_handles_both(self, contract):
        block = re.search(r"export function vocalLabel\(.*?\n\}", contract, re.S).group(0)
        assert 'typeof vocal === "string"' in block
        assert 'typeof vocal.label === "string"' in block

    def test_the_corpus_exercises_both_caveat_branches(self, reports):
        with_caveat = sum(1 for r in reports if r.get("vocal_caveat"))
        assert 0 < with_caveat < len(reports), \
            "every report or no report carries a vocal caveat; the branch is untested"

    def test_the_vocal_caveat_renders_when_present_and_is_skipped_when_not(self, sources):
        report = sources["pages/report.js"]
        assert "report.vocal_caveat" in report
        assert "filter(Boolean)" in report, \
            "the caveats must be filtered, not printed as empty boxes"


# --------------------------------------------- the bias caveat is undismissable

class TestTheBiasCaveatIsUndismissable:
    """
    The project requires BIAS_CAVEAT on every surface that presents a
    facial-derived score. It is not a footnote and it is not dismissible: no
    <details>, no hover, no collapse, no clip, no max-height.
    """

    def test_it_is_rendered_on_the_report(self, sources):
        assert "report.bias_caveat" in sources["pages/report.js"]

    def test_it_is_rendered_on_the_combined_report(self, sources):
        """A combined score is an average of five facial-derived ones."""
        assert "record.bias_caveat" in sources["pages/sweep.js"]

    def test_it_reaches_the_library_and_the_report_without_javascript(self):
        """
        Every word of these pages arrives through a module. A disclosure that
        depends on a script executing is not a disclosure, so Flask substitutes
        the caveats into the no-script core of every document that shows a
        facial-derived score.
        """
        ui = ROOT / "interface" / "ui"
        for name in ("report.html", "library.html", "brand.html"):
            assert "<!--BP:CAVEATS-->" in (ui / name).read_text(encoding="utf-8"), \
                f"{name} has no substitution point for the caveats"

    @pytest.mark.parametrize("sheet,selector", [
        ("styles/report.css", ".cal__caveat"),
        ("styles/sweep.css", ".cav"),
    ])
    def test_it_is_not_collapsed_clipped_or_capped_by_css(self, styles, sheet, selector):
        pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
        rule = re.search(pattern, styles[sheet])
        assert rule, f"{selector} has no rule in {sheet}"
        body = rule.group(1)
        for banned in ("max-height", "overflow: hidden", "display: none",
                       "-webkit-line-clamp", "visibility: hidden"):
            assert banned not in body, f"{selector} is {banned}"

    def test_it_is_not_behind_a_disclosure(self, sources):
        for name in ("pages/report.js", "pages/sweep.js"):
            code = sources[name]
            for match in re.finditer(r"<details.*?</details>", code, re.S):
                assert "caveat" not in match.group(0).lower(), \
                    f"{name} puts a caveat inside a <details>"

    def test_it_is_not_revealed_on_hover(self, styles):
        for name, sheet in styles.items():
            for selector, _ in css_rules(sheet):
                if ":hover" in selector and ("caveat" in selector or ".cav" in selector):
                    pytest.fail(f"{name}: {selector} reveals a caveat on hover")

    def test_every_report_on_disk_carries_one(self, reports):
        for report in reports:
            assert report.get("bias_caveat"), "a saved report has no bias caveat"

    def test_a_report_without_one_says_so_rather_than_going_quiet(self, sources):
        """
        If a report ever arrives without the text, the page states that fact
        rather than rendering nothing, because an absent disclosure and a
        disclosure-free report look identical otherwise.
        """
        for page in ("pages/report.js", "pages/sweep.js"):
            flat = re.sub(r"\s+", " ", sources[page])
            assert "carries no caveat text of its own" in flat, \
                f"{page} goes quiet when a caveat is missing"


# ------------------------------------------------------ hiding actually hides

class TestHidingActuallyHides:

    def test_the_stylesheet_forces_hidden_to_hide(self, styles):
        """
        A later rule setting `display: flex` on a class that also carries the
        attribute would otherwise win on specificity and put a hidden element
        back on screen.
        """
        chassis = styles["styles/chassis.css"]
        assert "[hidden] { display: none !important; }" in chassis

    def test_no_stylesheet_gives_hidden_a_visible_display_back(self, styles):
        offenders = []
        for name, sheet in styles.items():
            for selector, declarations in css_rules(sheet):
                subject = selector.split()[-1].strip(",")
                if subject.endswith("[hidden]") and "display: none" not in declarations:
                    offenders.append((name, selector))
        assert not offenders, f"[hidden] given a visible display: {offenders}"


# ------------------------------------------- what is taken down stops watching

class TestWhatIsTakenDownStopsWatching:
    """
    A component replaced while the page stays open must let go of the window.
    Measured 26 Sep 2026 in Chrome before these: the shelf's pointercancel
    listener and the Library's Escape handler outlived Show as a list, and the
    list's card traces went from 7 live observers to 147 after 20 order clicks
    (bounded at 14 after).
    """

    GLOBAL = re.compile(r"(window|document)\.(add|remove)EventListener\(\s*\"(\w+)\",\s*([^,)]+)")

    def test_every_global_listener_the_shelf_adds_is_removed_by_name(self, sources):
        shelf = "\n".join(code_lines(sources["lib/shelf.js"]))
        added = {(t, h.strip()) for _, verb, t, h in self.GLOBAL.findall(shelf) if verb == "add"}
        removed = {(t, h.strip()) for _, verb, t, h in self.GLOBAL.findall(shelf) if verb == "remove"}
        inline = sorted(t for t, h in added if "=>" in h or h.startswith("function"))
        assert not inline, f"an inline handler cannot be removed: {inline}"
        assert added and added <= removed, sorted(added - removed)

    def test_the_library_lets_go_of_what_it_replaces(self, sources):
        lib = "\n".join(code_lines(sources["pages/library.js"]))
        paint = lib[lib.index("function paint()"):lib.index("function wireCards()")]
        assert paint.index('clearTraces("rack")') < paint.index("host.innerHTML")
        compare = lib[lib.index("function paintCompare()"):lib.index("async function main()")]
        assert 'clearTraces("compare")' in compare
        swap = lib[lib.index("const toList = async"):]
        swap = swap[:swap.index("\n  };")]
        assert 'window.removeEventListener("keydown", onEscape, true)' in swap


# --------------------------------------- untrusted text reaches the DOM safely

class TestUntrustedTextReachesTheDomSafely:
    """
    A transcript line or an audience comment is arbitrary text from the
    internet. There are exactly two safe ways for it to reach the DOM, and this
    interface uses both:

      * escaped with esc(), for anything going into an innerHTML sink
      * assigned to .textContent, which is a text-only sink and cannot execute

    The second is stronger than the first, not weaker, so it is allowed here. A
    template literal is only an offender when its result can reach innerHTML.
    """

    UNTRUSTED = ("segment.text", "c.text", "entry.filename", "error.message",
                 "m.title", "f.title", "r.title")

    def test_there_is_exactly_one_escape_helper(self, sources):
        assert "export function esc(" in sources["lib/format.js"]

    def test_the_helper_escapes_the_characters_that_matter(self, sources):
        body = re.search(r"export function esc\(.*?\n\}", sources["lib/format.js"], re.S).group(0)
        for char in ("&amp;", "&lt;", "&gt;", "&quot;"):
            assert char in body

    @pytest.mark.parametrize("expression", UNTRUSTED)
    def test_untrusted_values_reach_the_dom_escaped_or_as_text(self, sources, expression):
        offenders = []
        for name, code in sources.items():
            for line in code_lines(code):
                for match in re.finditer(r"\$\{([^}]*)\}", line):
                    inner = match.group(1)
                    if expression not in inner:
                        continue
                    safe = ("esc(" in inner
                            or "encodeURIComponent(" in inner
                            or ".textContent" in line
                            or "CSS.escape(" in inner)
                    if not safe:
                        offenders.append((name, line.strip()[:80]))
        assert not offenders, f"untrusted text reaching an unsafe sink: {offenders}"

    def test_a_reports_stored_address_is_read_only_for_its_video_id(self, sources):
        """
        esc() makes text safe inside an attribute but not a URL safe to follow:
        a report file copied in from elsewhere could carry a javascript: address.
        Until 26 Sep 2026 the source link printed report.video_url as its href
        whenever an id could be found in it (ui_evidence/verify_hostile_files.py
        checks every page for javascript: links). The address is now read only
        to find the id, and every link to the video is built from that.
        """
        readers = sorted(name for name, code in sources.items()
                         if any("video_url" in line for line in code_lines(code)))
        assert readers == ["lib/frames.js", "pages/run.js"], readers
        assert "youtube.com/watch?v=${videoId}" in sources["pages/report.js"]

    def test_a_moments_readings_and_time_are_escaped_in_both_books(self, sources):
        """
        The written report's moment cards print each channel's reading and the
        moment's time. The combined book escaped them; until 26 Sep 2026 the
        single report's did not, and markup placed there ran script
        (ui_evidence/verify_hostile_files.py, "written report: text").
        """
        for name in ("lib/written.js", "lib/combined.js"):
            code = "\n".join(code_lines(sources[name]))
            assert "esc(m.time)" in code, name
            assert code.count("esc(v.toLowerCase())") >= 2, name

    GUARDED = {"getReport": "asReport", "getSweepMember": "asReport", "getSweep": "asSweep",
               "getReportAnalysis": "asAnalysis", "getMemberAnalysis": "asAnalysis",
               "getSweepAnalysis": "asAnalysis", "compareSweeps": "asAnalysis"}

    def test_every_saved_file_a_page_reads_is_held_to_numbers_where_it_should_be(self, sources):
        """
        Text is escaped at each sink; the numbers a page prints straight into
        attributes and style values are held to numbers once, at load
        (lib/api.js). Measured before that guard existed: markup in place of a
        segment id ran script on the report page. The browser evidence is
        ui_evidence/verify_hostile_files.py; this keeps every reader on the guard.
        """
        api = sources["lib/api.js"]
        for reader, guard in self.GUARDED.items():
            body = api[api.index(f"export const {reader} ="):]
            body = body[:body.index(";")]
            assert f".then({guard})" in body, f"{reader} does not pass through {guard}"
        others = sorted(name for name, code in sources.items()
                        if name != "lib/api.js" and any("fetch(" in line for line in code_lines(code)))
        assert not others, f"a page reads data without lib/api.js: {others}"

    def test_comment_text_is_escaped_where_it_is_rendered(self, sources):
        assert "esc(c.text)" in sources["pages/report.js"]

    def test_transcript_text_is_escaped_where_it_is_rendered(self, sources):
        assert "esc(segment.text" in sources["pages/report.js"]

    def test_a_report_with_markup_in_it_would_still_be_text(self, reports):
        """The guard only matters if the corpus can contain markup characters."""
        risky = 0
        for report in reports:
            for comment in report.get("all_comments", []):
                if any(ch in str(comment.get("text", "")) for ch in "<>&\"'"):
                    risky += 1
        assert risky > 0, "no comment in the corpus contains a markup character"


# ---------------------------------------------------------------------- privacy

class TestPrivacy:

    def test_no_comment_author_is_ever_rendered(self, sources):
        """
        Author identifiers are discarded before anything is written to disk.
        The interface must not reintroduce the idea by reading a field that
        would be there if the pipeline ever stopped discarding it.
        """
        offenders = []
        for name, code in sources.items():
            for line in code_lines(code):
                if re.search(r"\.(author|authorDisplayName|channelId|authorChannel)\b", line):
                    offenders.append((name, line.strip()[:70]))
        assert not offenders, f"an author identifier is being read: {offenders}"

    def test_the_saved_reports_carry_no_author_field(self, reports):
        for report in reports:
            for comment in report.get("all_comments", []):
                assert not any(k.lower().startswith("author") for k in comment), \
                    "a saved comment carries an author field"

    def test_the_interface_never_names_the_api_key(self, sources):
        for name, code in sources.items():
            lowered = code.lower()
            assert "youtube_api_key" not in lowered, f"{name} names the API key"
            assert "api_key" not in lowered, f"{name} names the API key"


# -------------------------------------------- nothing addresses another host

class TestNothingAddressesAnotherHost:
    """
    The product's central claim is that no pipeline data leaves the machine. An
    interface that fetched a font, a script or an image from anywhere would
    contradict that claim on every load, in front of a marker, while describing
    data sovereignty.
    """

    ALLOWED = {
        # An input's placeholder. Text shown to a reader, never requested.
        "https://www.youtube.com/watch?v=",
        # The controller's own address, printed as prose so a reader can see
        # where it is. Never fetched by the interface.
        "http://localhost:11434",
        "localhost:11434",
    }

    def test_no_shipped_code_requests_another_host(self, sources):
        offenders = []
        for name, code in sources.items():
            for line in code_lines(code):
                for url in re.findall(r"https?://[^\s\"'`)]+", line):
                    if not any(url.startswith(ok) for ok in self.ALLOWED):
                        offenders.append((name, url))
        assert not offenders, f"a request leaves this machine: {offenders}"

    def test_that_guard_would_catch_a_real_one(self):
        """The guard is only worth having if it fails on the thing it forbids."""
        line = 'const font = "https://fonts.googleapis.com/css2?family=Inter";'
        found = [u for u in re.findall(r"https?://[^\s\"'`)]+", line)]
        assert found and not any(
            u.startswith(ok) for u in found for ok in TestNothingAddressesAnotherHost.ALLOWED)

    def test_no_stylesheet_imports_from_a_font_host(self, styles):
        for name, sheet in styles.items():
            assert "@import" not in sheet, f"{name} imports a stylesheet"
            for url in re.findall(r"url\(([^)]*)\)", sheet):
                cleaned = url.strip("\"'")
                assert not cleaned.startswith("http"), f"{name} fetches {cleaned}"

    def test_every_font_is_served_from_this_repo(self, styles):
        chassis = styles["styles/chassis.css"]
        faces = re.findall(r"src: url\(\"([^\"]+)\"\)", chassis)
        assert faces, "no @font-face src found"
        for src in faces:
            assert src.startswith("/static/fonts/"), f"{src} is not served from this repo"

    def test_api_calls_are_all_relative(self, sources):
        api = sources["lib/api.js"]
        for call in re.findall(r"fetch\(([^,)]*)", api):
            cleaned = call.strip().strip("`\"'")
            assert cleaned.startswith("/"), f"a fetch is not same-origin: {call}"


# ------------------------------------------------ motion is one mechanism

class TestMotionIsOneMechanism:
    """
    Every moving thing on this interface is driven by one of two things: `t`,
    the position in the video, or one orchestrated draw-on that happens once.
    There is no scroll-triggered fade-and-slide-up on any section, which is both
    the commonest tell of a generated page and, here, decoration: nothing about
    a section arriving from below tells a reader anything about four channels
    disagreeing.
    """

    def test_the_durations_are_read_from_css_rather_than_restated(self, sources):
        """
        Two copies of a duration eventually disagree, and the copy nobody
        re-reads is the one in the JavaScript.
        """
        motion = sources["lib/motion.js"]
        assert "function cssMs(" in motion
        for token in ("--t-fast", "--t-med", "--t-slow"):
            assert token in motion, f"{token} is not read from the stylesheet"

    def test_reduced_motion_is_honoured_in_js_not_only_css(self, sources):
        motion = sources["lib/motion.js"]
        assert 'matchMedia("(prefers-reduced-motion: reduce)")' in motion
        assert "export const reduced" in motion

    def test_it_is_live_rather_than_sampled_once_at_boot(self, sources):
        """
        A reader can turn the preference on mid-session. The interface has to
        stop moving then, not at the next reload.
        """
        motion = sources["lib/motion.js"]
        assert 'QUERY.addEventListener("change"' in motion
        assert "export function onReducedChange(" in motion

    def test_everything_that_animates_consults_it(self, sources):
        """
        A module that starts a tween, a scan or a coast must check first. A page
        that animates nothing itself is not required to ask.
        """
        for name, code in sources.items():
            body = "\n".join(code_lines(code))
            animates = ("gsap." in body or "requestAnimationFrame(" in body)
            # motion.js IS the module that owns the preference. announce.js
            # defers a live-region write by one frame so a freshly created
            # region is registered before it is filled; that is a timing
            # workaround, not movement, and there is nothing to reduce.
            # pages/opening.js waits one frame so its sections are wired against a
            # laid-out document (ScrollTrigger measures heights); pages/report.js
            # waits one frame to move focus and to call openBook, which asks
            # reduced() itself (codex.js, leaf.js). Neither moves anything.
            if not animates or name in ("lib/motion.js", "lib/announce.js",
                                        "pages/opening.js", "pages/report.js"):
                continue
            # The vendored renderers import nothing from the project: they are
            # handed the preference as `still` by the caller, which asks
            # reduced(), and follow later changes through the one event
            # motion.js sends (25 Sep 2026, the Reduce motion switch).
            vendored = "props.still" in body and '"motionchange"' in body
            # motionMedia() is gsap.matchMedia with the reduced-motion conditions
            # answered by reduced() itself (motion.js), so using it is asking.
            asks = "reduced()" in body or "motionMedia(" in body
            if name == "lib/shelf.js" and not asks:
                # The room never asks because it is never built for a reader
                # who asked for less movement: the library only wants a shelf
                # when reduced() is false, and takes it down the moment that
                # changes. That promise is held here, where it is made.
                library = "\n".join(code_lines(sources["pages/library.js"]))
                assert "!reduced()" in library[library.index("function shelfPossible"):][:200], \
                    "the library would build a shelf under reduced motion"
                assert re.search(r"onReducedChange\(\(less\) => \{\s*if \(less\) toList\(", library), \
                    "the library no longer takes the shelf down when motion is reduced"
                continue
            assert asks or vendored, f"{name} animates without consulting reduced()"

    def test_the_draw_on_finishes_instantly_rather_than_being_skipped(self, sources):
        """
        Reduced motion means a still version that is COMPLETE, never a broken
        one. The trace is drawn finished on the first frame rather than not
        drawn at all.
        """
        motion = sources["lib/motion.js"]
        block = motion[motion.index("export function drawOn("):]
        block = block[:block.index("\n}")]
        assert "if (reduced())" in block
        assert "target.value = 1" in block

    def test_the_theme_sweep_is_skipped_but_the_theme_still_changes(self, sources):
        motion = sources["lib/motion.js"]
        block = motion[motion.index("export function sweepTheme("):]
        block = block[:block.index("\n}")]
        assert "if (reduced()) { apply(); return; }" in block

    def test_the_shuttle_still_works_under_reduced_motion(self, sources):
        """
        The shuttle is an INPUT, not an ornament. Disabling it would remove a
        control rather than remove movement.
        """
        transport = sources["lib/transport.js"]
        block = transport[transport.index("  function onUp("):]
        block = block[:block.index("\n  }")]
        assert "if (reduced())" in block
        assert "clock.set(clock.nearestBound" in block

    def test_every_spread_turns_including_the_fold_outs(self, sources):
        """
        The page turn is the book's one gesture between spreads. It was withheld
        whenever either side was a fold-out, so the fold-outs and the page after
        each one changed by a fade while every other page turned (noticed by the
        user, 24 Sep 2026). Reduced motion, the single-page layout and a reader
        flicking through may withhold it; the kind of page may not.
        """
        codex = sources["lib/codex.js"]
        rule = codex[codex.index("const turnable ="):]
        rule = rule[:rule.index(";")]
        assert "isFold" not in rule, "a fold-out is excluded from the turn again"
        assert "reduced()" in rule and "rapid" in rule and "wide" in rule
        assert "function halfOf(" in codex, "a fold-out's halves are cut from its one sheet"

    def test_reduced_motion_collapses_transitions_rather_than_removing_them(self, styles):
        """
        `animation: none` on a state indicator would leave a reader unable to
        tell a recording lane from a waiting one. The still version has to carry
        the same information.
        """
        run = styles["styles/run.css"]
        block = run[run.index("@media (prefers-reduced-motion: reduce)"):]
        block = block[:block.index("\n}\n\n/*")] if "\n}\n\n/*" in block else block
        assert "display: none" not in block or "rec__scan" in block, \
            "a still lane must still report its state"
        assert "background" in block, "the recording lane loses its only static cue"


# ------------------------------------------------ the run page says what it shows

class TestTheRunPageSaysWhatItShows:
    """
    A run lasts four to nine minutes. Before the live regions existed, a reader
    using a screen reader started an analysis and was never told it advanced a
    stage, finished, was cancelled, or died.
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def announce(sources):
        return sources["lib/announce.js"]

    def test_the_live_region_is_attached_outside_every_re_rendered_subtree(self, announce):
        """
        run.js replaces the whole of [data-run] on each state change, so a
        region written into that markup is destroyed and rebuilt on every
        transition. A rebuilt region announces nothing: assistive technology
        tracks the node, not the selector.
        """
        assert "document.body.appendChild(node)" in announce

    def test_the_run_page_does_not_write_a_live_region_into_its_own_markup(self, run):
        assert 'aria-live' not in run, "a region inside the re-rendered subtree"

    def test_there_are_two_regions_and_they_differ_in_urgency(self, announce):
        assert '"status", "polite"' in announce
        assert '"alert", "assertive"' in announce

    def test_the_regions_exist_before_anything_needs_to_speak(self, sources):
        """
        A live region created and filled in the same task is routinely missed,
        which is the classic way an announcement gets built and never heard.
        """
        for page in PAGES:
            assert "mountAnnouncer()" in sources[f"pages/{page}.js"], \
                f"{page} never mounts the announcer"

    def test_every_ending_the_page_can_render_is_also_spoken(self, run):
        block = run[run.index("const OUTCOMES = {"):run.index("function reportLink(")]
        rendered = set(re.findall(r"^  (\w+): \{", block, re.M))
        spoken = set(re.findall(r"^  (\w+): \{(?:[^{}]|\{[^{}]*\})*?say:", block, re.M | re.S))
        assert rendered == {"done", "partial", "cancelled", "error", "lost"}, \
            f"the set of endings changed: {rendered}"
        assert rendered == spoken, f"an ending is shown but not said: {rendered - spoken}"

    def test_every_ending_names_a_tab_state_and_an_urgency(self, run):
        block = run[run.index("const OUTCOMES = {"):run.index("function reportLink(")]
        for ending in ("done", "partial", "cancelled", "error", "lost"):
            spec = re.search(rf"  {ending}: \{{(.*?)\n  \}},", block, re.S)
            assert spec, f"{ending} is missing"
            assert "tag:" in spec.group(1), f"{ending} has no tab state"
            assert "urgent:" in spec.group(1), f"{ending} has no urgency"

    def test_the_failures_interrupt_and_the_rest_wait(self, run):
        block = run[run.index("const OUTCOMES = {"):run.index("function reportLink(")]
        urgency = dict(re.findall(r"  (\w+): \{\s*\n\s*tag: \"[^\"]*\",\s*\n\s*urgent: (\w+)", block))
        assert urgency == {"done": "false", "partial": "false", "cancelled": "false",
                           "error": "true", "lost": "true"}

    def test_the_finished_run_speaks_both_scores(self, run):
        block = run[run.index("  done: {"):run.index("  partial: {")]
        assert "authenticity_score" in block
        assert "brand_health_score" in block
        assert "bias caveat" in block

    def test_every_stage_has_a_name_that_can_be_said(self, run):
        """
        A label may be markup; `spoken` is what a live region and aria-valuetext
        are given. A reader must be given the words, not an HTML entity.
        """
        stages = run[run.index("const STAGES = ["):run.index("function setTitle(")]
        labels = re.findall(r"\n    label:", stages)
        spoken = re.findall(r"\n    spoken:", stages)
        assert len(labels) == 5, f"expected five stages, found {len(labels)}"
        assert len(spoken) == len(labels), "a stage can be shown but not said"
        said = re.findall(r'spoken: "([^"]*)"', stages)
        for entity in ("&amp;", "&rsquo;", "&mdash;", "&nbsp;", "<"):
            assert not any(entity in s for s in said), f"{entity!r} would be read aloud"

    def test_the_stage_labels_match_the_backend_stage_count(self, run):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        backend = re.search(r"_STAGES = \[(.*?)\]", app, re.S).group(1)
        assert len(re.findall(r'"', backend)) // 2 == 5
        stages = run[run.index("const STAGES = ["):run.index("function setTitle(")]
        assert len(re.findall(r"\n    label:", stages)) == 5

    def test_a_form_problem_carries_the_words_to_say_as_well_as_to_show(self, run):
        """A problem is announced, not only outlined in red."""
        block = run[run.index("  form.addEventListener(\"submit\""):]
        assert "announce(Object.values(problems).join(\" \"), { urgent: true })" in block

    def test_the_progress_never_reports_a_value_without_explaining_it(self, run):
        """
        aria-valuenow on this indicator is a stage count, which on its own is
        read as a bare number out of four. aria-valuetext is the part that
        carries.
        """
        assert 'role="progressbar"' in run
        assert 'setAttribute("aria-valuetext"' in run

    def test_queued_does_not_claim_nought_stages_complete(self, run):
        """
        "Queued" and "nought of four complete" are different states, and a
        progressbar reporting 0 while nothing has been claimed is a measurement
        that was never taken.
        """
        block = run[run.index('  const rec = root.querySelector("[data-rec]");'):]
        block = block[:block.index("const word = {")]
        assert 'removeAttribute("aria-valuenow")' in block
        assert block.count('setAttribute("aria-valuenow"') == 1

    def test_the_lanes_still_report_their_state_when_motion_is_reduced(self, styles):
        """
        The recording lane is marked by a travelling light. With motion reduced
        that light does not move, so the lane needs a static cue or a reader
        cannot tell it from one that has not started.
        """
        run = styles["styles/run.css"]
        block = run[run.index("@media (prefers-reduced-motion: reduce)"):]
        assert '.rec__lane[data-state="recording"] .rec__track' in block
        assert "background" in block

    def test_the_tab_reports_the_state_too(self, run):
        """
        The tab is the only part of this page visible while doing something
        else, and a run lasts four to nine minutes.
        """
        assert "function setTitle(" in run
        assert run.count("setTitle(") >= 4

    def test_a_stage_is_announced_on_change_and_not_on_every_poll(self, run):
        """
        The poll runs every 1.5 seconds. Announcing from it unguarded would
        repeat the same sentence some four hundred times in a long stage.
        """
        assert "if (stageIndex !== lastStage) {" in run
        assert "lastStage = stageIndex;" in run

    def test_the_aperture_is_reported_from_the_stage_rather_than_asserted(self, run):
        """
        The page claims "sealed" for most of a run. That claim has to come from
        which stage is actually running, not from a constant.
        """
        stages = run[run.index("const STAGES = ["):run.index("function setTitle(")]
        assert stages.count("reaches:") == 5, "every stage must declare whether it reaches out"
        assert stages.count("reaches: null") == 2, \
            "exactly two of the five stages are local-only"
        assert "const reaches = stage ? stage.reaches : null;" in run


# ------------------------------------------------ reflow is not masked

class TestNothingMasksAReflowFailure:
    """
    `body { overflow-x: hidden }` conceals rather than solves. With it, the
    document reports no horizontal scroll however far content runs off the side,
    so every check written against scrollWidth passes trivially and a reflow
    failure vanishes instead of surfacing.
    """

    PAGE_LEVEL = {"html", "body", "html, body", "body, html", ":root", "*"}

    def test_no_stylesheet_hides_overflow_at_page_level(self, styles):
        offenders = []
        for name, sheet in styles.items():
            for selector, declarations in css_rules(sheet):
                if selector in self.PAGE_LEVEL and "overflow" in declarations:
                    offenders.append((name, selector,
                                      declarations.strip().replace("\n", " ")[:60]))
        assert not offenders, f"page-level overflow is masked: {offenders}"

    def test_the_body_rule_does_not_hide_horizontal_overflow(self, styles):
        chassis = "\n".join(code_lines(styles["styles/chassis.css"]))
        body = re.search(r"(?m)^body\s*\{(.*?)^\}", chassis, re.S)
        assert body, "no body rule found"
        assert "overflow" not in body.group(1)

    def test_long_disclosure_text_is_allowed_to_break(self, styles):
        """
        The caveats are single long sentences from pipeline/scorer.py containing
        unbroken tokens. Measured at 320px before the fix: the combined report
        ran 377px wide in a 320px viewport, and because this build refuses to
        mask overflow, it showed.
        """
        for sheet, selector in (("styles/report.css", ".cal__caveat"),
                                ("styles/sweep.css", ".cav")):
            # The class's own rule, at the start of a line -- not a compound
            # like `.sf__fn.cav`, which sits on elements the base rule already
            # covers and so inherits its overflow-wrap (25 Sep 2026).
            pattern = r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}"
            rule = re.search(pattern, styles[sheet])
            assert rule, f"{selector} has no rule in {sheet}"
            assert "overflow-wrap: anywhere" in rule.group(1), \
                f"{selector} cannot break a long token"

    @pytest.mark.parametrize("sheet", ["styles/report.css", "styles/sweep.css",
                                       "styles/library.css", "styles/run.css",
                                       "styles/film.css"])
    def test_every_surface_declares_a_narrow_layout(self, styles, sheet):
        """
        Mobile is a designed layout, not a squeeze. Each surface has to say what
        it does when there is no room rather than leaving it to chance.
        """
        # The phone breakpoint is the surface's own (the film's is 759px, where
        # its chamber stops fitting); what is required is that there is one.
        widths = [float(w) for w in re.findall(r"@media\s*\(max-width:\s*([\d.]+)px\)", styles[sheet])]
        assert any(w <= 760 for w in widths), f"{sheet} has no phone layout"


# ------------------------------------------ a control can be spoken

class TestEveryControlCanBeSpoken:
    """
    WCAG 2.5.3, Label in Name. A speech-input user operates a control by saying
    what is printed on it. If the accessible name does not contain those words
    the command fails, and it fails silently.
    """

    def test_the_transport_is_named_not_narrated(self, sources):
        """
        A name is read every time focus lands. A paragraph of keyboard help read
        on every arrow press is noise, and it leaves a speech-input user with
        nothing sayable. The keys are a DESCRIPTION.
        """
        transport = sources["lib/transport.js"]
        field = transport[transport.index('<div class="tp__field"'):]
        field = field[:field.index(">")]
        label = re.search(r'aria-label="([^"]*)"', field)
        assert label, "the transport has no accessible name"
        # Since 25 Sep 2026 the name is built on one line (so a card can carry
        # its run's name, A16) and the attribute interpolates it. Read the
        # line that builds it: the fixed words must lead with "Playhead" and
        # stay a name, whatever run name is appended to them.
        if "sliderName" in label.group(1):
            built = re.search(r"const sliderName = ([^;]+);", transport)
            assert built, "the attribute names sliderName but nothing builds it"
            words = re.sub(r"\$\{[^}]*\}", "", built.group(1))
            assert "Playhead" in words and words.strip().startswith(("label ?", "`Playhead", '"Playhead')), \
                f"the transport's name no longer leads with Playhead: {built.group(1)!r}"
            fixed = words
        else:
            fixed = label.group(1)
        assert len(fixed) < 45, f"the transport's name is a paragraph again: {fixed[:60]!r}"
        assert "arrow" not in fixed.lower()
        assert "aria-describedby" in field, "the keys are no longer described anywhere"

    def test_the_description_it_points_at_carries_the_keys(self, sources):
        transport = sources["lib/transport.js"]
        block = transport[transport.index('id="tp-how-'):]
        block = block[:block.index("</p>")]
        for key in ("arrow", "Home", "End", "Page"):
            assert key in block, f"{key} is no longer explained anywhere"

    def test_the_description_has_a_unique_id_per_transport(self, sources):
        """
        The library rack draws one transport per card. A shared id would point
        every one of them at the first description in the document.
        """
        transport = sources["lib/transport.js"]
        assert "let transportCount = 0;" in transport
        assert "const uid = (transportCount += 1);" in transport
        assert 'id="tp-how-${uid}"' in transport

    def test_controls_with_visible_words_are_not_given_a_conflicting_name(self, sources):
        """
        Where a control prints its own words, the words ARE the name. Adding an
        aria-label that does not contain them replaces what a speech-input user
        can say with something they cannot see.
        """
        offenders = []
        for name, code in sources.items():
            for match in re.finditer(r"<button[^>]*aria-label=\"([^\"]*)\"[^>]*>([^<]{2,40})<",
                                     code):
                label, visible = match.group(1), match.group(2).strip()
                visible = re.sub(r"\$\{[^}]*\}", "", visible).strip()
                if visible and visible.lower() not in label.lower():
                    offenders.append((name, label, visible))
        assert not offenders, f"an accessible name hides the visible words: {offenders}"


# -------------------------------------------- the focused thing is on screen

class TestFocusLandsWhereItCanBeSeen:

    def test_the_skip_link_is_fixed_to_the_viewport_not_the_document(self, styles):
        """
        Absolute put it at the top of the DOCUMENT. Tabbing past the last
        control wraps focus back to the skip link, and from 6,000px down that
        meant a 6,000px journey to reach it.
        """
        chassis = "\n".join(code_lines(styles["styles/chassis.css"]))
        rule = re.search(r"\.skip-link \{(.*?)\}", chassis, re.S)
        assert rule, "the skip link has no rule"
        assert "position: fixed" in rule.group(1)

    def test_nothing_removes_an_outline_without_replacing_it(self, styles):
        offenders = []
        for name, sheet in styles.items():
            for selector, declarations in css_rules(sheet):
                if re.search(r"outline:\s*(none|0)", declarations):
                    if ":focus-visible" in selector or "focus:not(:focus-visible)" in selector:
                        continue
                    # `X:focus { outline: none }` beside `X:focus-visible { outline: ... }`
                    # is the same guarantee written the other way round: no ring
                    # for a pointer, a real one for the keyboard.
                    base = selector.replace(":focus", "")
                    if any(sel.strip() == f"{base}:focus-visible" and re.search(r"outline:\s*\d", decl)
                           for sel, decl in css_rules(sheet)):
                        continue
                    offenders.append((name, selector))
        assert not offenders, f"an outline is removed with nothing put back: {offenders}"

    def test_a_focus_style_is_defined_once_for_everything(self, styles):
        chassis = styles["styles/chassis.css"]
        assert ":focus-visible {" in chassis
        rule = re.search(r":focus-visible \{([^}]*)\}", chassis).group(1)
        assert "outline" in rule and "var(--focus)" in rule

    def test_anything_scrolled_to_clears_the_sticky_masthead(self, styles):
        """
        A heading jumped to that lands underneath the masthead reads as the page
        having scrolled to the wrong place.
        """
        chassis = styles["styles/chassis.css"]
        assert "scroll-margin-top" in chassis


# ---------------------------------- the scores explain themselves in plain words

class TestTheScoresExplainThemselvesInOrdinaryWords:
    """
    A number at 40px is read as a verdict unless something beside it says
    otherwise. Both scores measure cross-channel disagreement and neither is a
    finding about honesty, and that has to be on the page rather than in a
    footnote.
    """

    def test_the_report_says_what_the_scores_are_not(self, sources):
        report = sources["pages/report.js"]
        assert "Neither is a finding about whether anyone was" in report
        assert "neither is comparable between videos" in report.lower()

    def test_the_combined_report_says_a_mean_is_not_a_measurement(self, sources):
        sweep = sources["pages/sweep.js"]
        assert "means_not" in sweep, "the pipeline's own wording is not surfaced"

    def test_the_combined_report_leads_with_the_range_not_the_average(self, sources):
        sweep = sources["pages/sweep.js"]
        assert "The average is the least informative number here" in sweep
        assert "spread_verdict" in sweep

    def test_the_opening_page_states_the_controller_sensitivity(self, sources):
        """
        Swapping only the controller moved mean Authenticity across this corpus
        by 49.08 points. A score is, to a first approximation, a claim about
        which local model is installed, and the page says so.
        """
        # The landing is assembled by pages/opening.js from its sections; the
        # statement lives in the proof and limits sections it composes, so the
        # page is read as the reader gets it (25 Sep 2026).
        assert "49.08" in opening_page(sources)

    def test_the_comparison_refuses_rather_than_overstating(self, sources):
        sweep = sources["pages/sweep.js"]
        block = sweep[sweep.index("function separable("):]
        block = block[:block.index("\n}")]
        assert "controller" in block, "a controller change is not checked"
        assert "49.08" in block
        assert "subject" in block, "two different subjects are not checked"

    def test_a_refusal_is_a_designed_screen_rather_than_an_error(self, sources):
        sweep = sources["pages/sweep.js"]
        assert "cannot honestly be compared" in sweep
        assert "Both are still readable on their own" in sweep


# ------------------------------------------ the interface is honest about language

class TestTheInterfaceIsHonestAboutLanguage:
    """
    `audio_module.py` calls Whisper with `language="en"` fixed. A video in any
    other language is transcribed into English words anyway and nothing in the
    run reports that it happened. There is no detection step to fail, which is
    why it is written down rather than handled.
    """

    def test_the_limitation_is_stated_where_a_reader_will_see_it(self, sources):
        opening = opening_page(sources)
        assert "English" in opening
        assert 'language="en"' in opening

    def test_it_is_in_the_no_script_core_as_well(self):
        index = (ROOT / "interface" / "ui" / "index.html").read_text(encoding="utf-8")
        assert "English-only" in index


# --------------------------------------- a member of a sweep can be opened

class TestAMemberOfASweepCanActuallyBeOpened:
    """
    A sweep writes five complete reports, and for a long time nothing could open
    one: the combined page listed them as inert rows.
    """

    def test_the_row_offers_a_real_link(self, sources):
        sweep = sources["pages/sweep.js"]
        assert "/brand/${encodeURIComponent(record.sweep_id)}/${encodeURIComponent(m.video_id)}" in sweep

    def test_the_report_page_reads_that_address_back(self, sources):
        report = sources["pages/report.js"]
        block = report[report.index("function sourceFromPath("):]
        block = block[:block.index("\n}")]
        assert "brand" in block and "member" in block

    def test_a_member_that_failed_is_not_a_link_to_nothing(self, sources):
        sweep = sources["pages/sweep.js"]
        block = sweep[sweep.index("${members.map((m, i) => {"):]
        block = block[:block.index("</ul>")]
        assert "const ok = m.analysed !== false;" in block
        assert "ok\n                ? `<a href=" in block or "ok ? `<a href=" in block or \
               "${ok" in block, "a failed member must not be a link"

    def test_the_member_says_which_of_how_many_it_is(self, sources):
        report = sources["pages/report.js"]
        assert "Video ${context.index} of ${context.total}" in report

    def test_the_way_back_and_sideways_both_exist(self, sources):
        report = sources["pages/report.js"]
        block = report[report.index("function memberBar("):]
        block = block[:block.index("\n}")]
        assert "Back to the combined report" in block
        assert "context.prev" in block and "context.next" in block


# --------------------------------------- the design holds its own line

class TestTheDesignHoldsItsOwnLine:
    """
    NEW, 20 Sep 2026.

    The build this replaces hit at least six of the patterns its own design
    brief banned, and nothing caught it, because nothing was looking. These
    make the ban list mechanical so it cannot drift back in unnoticed.

    This is the one group in this file that IS about appearance. It is here
    because each of these is a specific, checkable thing the design decided
    against, not a matter of taste that might change with the next rebuild.
    """

    def test_no_all_caps_labels(self, styles):
        """
        A tracked-out ALL-CAPS eyebrow above every heading is the commonest tell
        of a generated page. There are none in this build; labels are sentence
        case.
        """
        offenders = []
        for name, sheet in styles.items():
            for selector, declarations in css_rules(sheet):
                if "text-transform" in declarations and "uppercase" in declarations:
                    offenders.append((name, selector))
        assert not offenders, f"an ALL-CAPS label: {offenders}"

    def test_no_middle_dot_meta_strings(self, sources):
        """
        `A · B · C` joined with middle dots. This build uses a hairline rule as
        a separator, because a rule is a separator and a punctuation mark
        pressed into service as one is the tell.
        """
        offenders = []
        for name, code in sources.items():
            for line in code_lines(code):
                if "·" in line or "&middot;" in line:
                    offenders.append((name, line.strip()[:60]))
        assert not offenders, f"a middle-dot meta string: {offenders}"

    def test_no_arrow_glyph_appended_to_a_control(self, sources):
        offenders = []
        for name, code in sources.items():
            for line in code_lines(code):
                if re.search(r"(→|&rarr;|&#8594;)", line):
                    offenders.append((name, line.strip()[:60]))
        assert not offenders, f"an arrow glyph in a control: {offenders}"

    def test_no_offset_blurred_drop_shadow(self, styles):
        """
        The soft grey shadow under every card. Depth here comes from a matte
        chassis against a lit screen plus one machined hairline. `box-shadow` is
        used only for inset rules and for a ring in the ground colour, neither
        of which is elevation.
        """
        offenders = []
        for name, sheet in styles.items():
            for match in re.finditer(r"box-shadow:\s*([^;]+);", sheet):
                value = match.group(1).strip()
                if value in ("none",) or value.startswith("inset"):
                    continue
                numbers = re.findall(r"-?[\d.]+px", value)
                # A ring is offset 0 0 with a spread; a drop shadow has a blur.
                if len(numbers) >= 3 and numbers[2] != "0px":
                    offenders.append((name, value[:50]))
        assert not offenders, f"a blurred drop shadow: {offenders}"

    def test_there_is_no_monospace_family(self, styles):
        """
        A monospace face for small data labels is a named tell. Timecode here is
        the interface face at width 78 on tabular figures, which aligns just as
        well and leaves the build at two families.
        """
        tokens = "\n".join(code_lines(styles["styles/tokens.css"]))
        assert "monospace" not in tokens, "a monospace family was declared"
        assert re.search(r"--f-\w+:", tokens), "no font tokens found"
        families = re.findall(r"--f-(\w+):", tokens)
        assert len(families) == 2, f"expected two families, found {families}"

    def test_measured_figures_are_never_animated_through_values_they_never_had(self, sources):
        """
        Geometry may grow, draw and sweep. A NUMBER appears at its true value.
        A count-up walks a measured figure through values it never held, which
        on this project is the difference between a chart and a slot machine.

        One exception, by the owner's decision: the opening page's proof counts
        up (decided 24 Sep 2026). It is held to
        the conditions checked in the next test; any other count-up fails here.
        """
        offenders = []
        for name, code in sources.items():
            if name == "lib/proof.js":
                continue
            for line in code_lines(code):
                if re.search(r"data-countup|countUp|animateNumber|tweenNumber", line):
                    offenders.append((name, line.strip()[:60]))
        assert not offenders, f"a measured figure is being animated: {offenders}"

    def test_the_one_count_up_never_hides_the_true_value(self, sources):
        """
        The proof's count-up paints only an aria-hidden run, so assistive
        technology reads the true figure; shows the final figure at once under
        reduced motion; and ends on the exact stored string, not a tweened float.
        """
        proof = sources["lib/proof.js"]
        block = proof[proof.index("function countUp("):]
        block = block[:block.index("\n}")]
        assert 'host.querySelector("[aria-hidden]")' in block
        assert "if (reduced()) { run.textContent = final; return null; }" in block
        assert "onComplete: () => { run.textContent = final; }" in block

    def test_a_bar_carries_its_true_value_before_anything_animates_it(self, sources, styles):
        """
        A bar whose width exists only inside a ScrollTrigger is empty when the
        trigger does not fire. The markup carries the real value and the tween
        starts from zero, so the honest state is the default.

        The opening page's bars are drawn by lib/proof.js since the fourth
        interface (opening.js composes the sections and draws none): each bar
        carries its value as `--ratio`, which proof.css turns into the fill's
        width, and the tween only scales that fill from zero.
        """
        proof = sources["lib/proof.js"]
        assert '<li class="bar" style="--i:${index};--ratio:${' in proof
        assert "width: calc(var(--ratio) * 100%);" in styles["styles/proof.css"]
        # The rationale lives next to the tween, so the next person to touch it
        # knows why the markup carries the value.
        block = proof[proof.index("function playChart("):]
        assert any(phrase in block for phrase in
                   ("never withheld", "true value", "true length"))

    def test_the_width_axis_is_used_for_trust_rather_than_decoration(self, styles):
        """
        The typeface's width axis encodes how much the instrument trusts a
        reading. The facial channel is set narrow everywhere it appears, because
        it scores 34.2% against a constant's 67.5%.
        """
        tokens = styles["styles/tokens.css"]
        assert "--w-trust-hi" in tokens and "--w-trust-lo" in tokens
        transport = styles["styles/transport.css"]
        assert 'data-channel="facial"' in transport
        assert "var(--w-trust-lo)" in transport

    def test_one_saturated_colour_and_it_is_bound_to_conflict(self, styles):
        """
        `--tear` is the only saturated colour in the interface and it appears
        only where a measured conflict score puts it. A report with no flagged
        segments draws none of it.
        """
        transport = styles["styles/transport.css"]
        block = transport[transport.index(".tp__flags i {"):]
        block = block[:block.index("}")]
        assert "var(--tear)" in block
        js = (SRC / "lib" / "transport.js").read_text(encoding="utf-8")
        assert "const flagged = segments.filter((s) => s.flagged);" in js, \
            "the flag columns must come from measured data"


def test_the_opening_film_prefers_reports_the_repository_ships(sources):
    """
    Until 26 Sep 2026 none of the preferred names existed (two deleted, one
    renamed), so the film fell back to the newest file, which in a fresh clone
    is arbitrary. A shipped report that is missing must fail, not fall back.
    """
    block = sources["pages/opening.js"]
    block = block[block.index("const PREFERRED = ["):]
    names = re.findall(r'"([^"]+\.json)"', block[:block.index("];")])
    assert names, "the film has no preferred report"
    missing = [n for n in names if not (ROOT / "outputs" / n).is_file()]
    assert not missing, f"preferred for the opening film but not in outputs/: {missing}"


class TestTheOpeningGateCannotBecomeALockedDoor:
    """
    The landing page opens behind a full-screen water gate. Everything here
    exists because the failure mode is not "the effect looks wrong", it is "the
    examiner never reaches the project at all".
    """

    def test_only_the_opening_page_raises_it(self, sources):
        """
        Every visit to "/" gets the gate and no other address ever does. A
        marker who opens a report directly wants the report, not a performance,
        and a gate over /library would sit between them and the evidence.
        """
        importers = [name for name, code in sources.items()
                     if "gate.js" in code and not name.endswith("lib/gate.js")]
        assert importers == ["pages/opening.js"], \
            f"the gate is reachable from {importers}, not the opening page alone"

    def test_it_offers_three_independent_ways_out(self, sources):
        """
        Click, Escape, and a timer that runs whether or not anything else works.
        They are independent on purpose: the timer does not depend on a
        listener, and the listeners do not depend on the timer.
        """
        gate = sources["lib/gate.js"]
        body = "\n".join(code_lines(gate))
        assert 'addEventListener("click"' in body
        assert '"Escape"' in body
        assert "setTimeout(dismiss" in body

    def test_the_timer_runs_even_if_the_page_behind_never_reports_ready(self, sources):
        """
        The hold normally starts when the document behind is built. If that call
        never arrives -- a fetch that hangs, a module that throws -- a ceiling
        starts it anyway. Without this, one failed request is a permanently
        locked door.
        """
        gate = sources["lib/gate.js"]
        body = "\n".join(code_lines(gate))
        assert "CEILING_MS" in body
        assert "setTimeout(startHold, CEILING_MS)" in body

    def test_an_effect_that_cannot_run_means_no_gate_at_all(self, sources):
        """
        No WebGL2, no float render target, or a shader that will not compile:
        mountElemental returns null and mountGate returns null with it, so the
        page shows immediately. A gate is never drawn over a canvas that failed.
        """
        elemental = sources["gl/elemental.js"]
        gate = sources["lib/gate.js"]
        assert "if (!panel || !panel.ok)" in elemental
        assert "return null;" in elemental
        assert "if (!water) return null;" in gate

    def test_its_fade_reads_the_shared_duration_rather_than_copying_it(self, sources):
        """
        Same contract as the rest of the interface: a duration lives in
        tokens.css and is read, never restated. A literal here would drift from
        the stylesheet that actually performs the fade.
        """
        gate = sources["lib/gate.js"]
        body = "\n".join(code_lines(gate))
        assert "MS.slow" in body
        assert "const FADE_MS" not in body, "the fade duration has been hardcoded again"

    def test_the_borrowed_shader_keeps_its_attribution(self, sources):
        """
        The water effect is ported from ThreeUI's elemental-water, not written
        here. This is a graded submission, so the provenance travels with the
        code and is not left to a commit message. Removing it would make the
        file claim authorship it does not have.
        """
        elemental = sources["gl/elemental.js"]
        assert "PROVENANCE" in elemental
        assert "threeui.com/source-code/elemental-water.json" in elemental
        assert "7a6871fe99fa" in elemental, "the pinned source revision is gone"

    def test_the_mark_does_not_claim_to_encode_measurements(self, sources):
        """
        The mark is four bars of unequal reach. Only two of the four channel
        reliabilities have ever been measured here, so a mark presented as a
        chart of four would be asserting two figures that do not exist. The file
        has to say the lengths are compositional.
        """
        elemental = sources["gl/elemental.js"]
        # Everything above the path string: the rationale has to sit with the
        # mark it governs, not somewhere else in the file.
        head = elemental[:elemental.index("export const MARK")]
        assert "COMPOSITIONAL" in head.upper(), \
            "the mark's lengths must be declared compositional, not measured"
        assert "0.342" in head and "0.489" in head, \
            "the two reliabilities that DO exist should be named, so the gap is visible"


# ------------------------------------- the combined written report (23 Sep 2026)

class TestTheCombinedWrittenReport:
    """
    The combined book's written pages (lib/combined.js, lib/setcharts.js,
    styles/combined.css) and what they changed elsewhere. The build-wide
    design tests above already fail on older files, so these hold the new
    files to the same lines on their own, where a regression cannot hide
    behind an old failure.
    """

    NEW_JS = ("lib/combined.js", "lib/setcharts.js")

    def test_no_middle_dots_arrows_or_count_ups(self, sources):
        for name in self.NEW_JS:
            for line in code_lines(sources[name]):
                assert "·" not in line and "&middot;" not in line, f"{name}: a middle dot"
                assert not re.search(r"(→|&rarr;|&#8594;)", line), f"{name}: an arrow glyph"
                assert not re.search(r"countUp|animateNumber|tweenNumber|data-countup", line), \
                    f"{name}: a measured figure animated"

    def test_the_stylesheet_holds_the_design_line(self, styles):
        sheet = styles["styles/combined.css"]
        for selector, declarations in css_rules(sheet):
            assert not ("text-transform" in declarations and "uppercase" in declarations), selector
        for match in re.finditer(r"box-shadow:\s*([^;]+);", sheet):
            value = match.group(1).strip()
            numbers = re.findall(r"-?[\d.]+px", value)
            assert value.startswith("inset") or len(numbers) < 3 or numbers[2] == "0px", value
        assert "@media (prefers-reduced-motion: reduce)" in sheet

    def test_untrusted_text_is_escaped_where_it_is_printed(self, sources):
        """A title, quote, comment, note or theme name printed into markup goes through esc()."""
        # The property printed, not one it is read through: c.quote.seg is a number.
        risky = re.compile(r"\.(title|quote|text|said|channel|note|product|reason|name|match|context)\b(?!\s*\.)")
        for name in self.NEW_JS:
            # Only a line that writes markup prints into it; a label built on
            # its own line is escaped where it is printed (aria-label="${esc(label)}").
            for line in (ln for ln in code_lines(sources[name]) if "<" in ln or '="' in ln):
                for m in re.finditer(r"\$\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", line):
                    expr = m.group(1)
                    if risky.search(expr) and "esc(" not in expr and "=>" not in expr:
                        assert re.search(r"\b(?:rowWords|leanMini|said|setChips|source|consensusWords)\(", expr), \
                            f"{name}: unescaped ${{{expr[:70]}}}"

    def test_the_page_that_animates_consults_reduced_motion(self, sources):
        sweep = sources["pages/sweep.js"]
        assert "Flip.getState" in sweep and "reduced()" in sweep

    def test_the_near_tie_and_the_same_video_read_twice_are_explained(self, sources):
        combined = sources["lib/combined.js"]
        assert "near-tie" in combined
        assert "The same video, read twice" in combined
        assert "79.29" in combined and "15.96" in combined, "the measured swing is quoted with its source"

    def test_the_agreement_sentence_is_code_not_model(self, sources):
        """Whether reviewers and audiences agree is written by code from the counts."""
        assert "export function codeAgreement(" in sources["lib/combined.js"]

    def test_the_run_page_can_search_an_earlier_period(self, sources):
        run = sources["pages/run.js"]
        assert run.count("offset_days: Number(values.offset || 0)") == 2, \
            "both the search and the start must carry where the window ends"
        assert 'new URLSearchParams(window.location.search)' in run

    def test_the_start_carries_the_search_result_so_videos_keep_their_titles(self, sources):
        """
        24 Sep 2026: the Huawei brand sweep was saved with every title blank,
        because the start no longer sent the search result back, and every page
        of its book named the five videos by id.
        """
        run = sources["pages/run.js"]
        start = run[run.index("await sweepStart({"):]
        start = start[:start.index("});")]
        for field in ("candidates: result.candidates", "query_used: result.query_used",
                      "published_after: result.published_after",
                      "published_before: result.published_before"):
            assert field in start, f"the start no longer sends {field.split(':')[0]}"
        assert "started.already_finished" in run, \
            "the same five again should open their book, not wait on a job that does not exist"

    def test_a_single_video_book_cites_its_source_by_name_not_id(self, sources):
        """The title page's source line read "YouTube, 8EThb_Wm-_U" until 24 Sep 2026."""
        report = sources["pages/report.js"]
        assert "${esc(t.videoId)}</a>" not in report
        assert "analysis.video_meta.title" in report, "a single run's name comes from YouTube's own answer"

    def test_an_ending_cannot_go_further_back_than_its_window(self, sources):
        """
        24 Sep 2026: "last week, ending a year ago" was on offer. The run page
        greys out what sweep.offset_problem refuses, measured in the same days.
        """
        from pipeline import sweep
        run = sources["pages/run.js"]
        block = run[run.index("const WINDOWS = ["):]
        block = block[:block.index("];")]
        days = {k: int(v) for k, v in re.findall(r'\["(\w+)", "[^"]*", (\d+)\]', block)}
        assert days == sweep.WINDOWS, "the run page and sweep.py disagree on a window's length"
        assert '["7", "A week ago"]' in run, "a week can still be held against the week before"
        assert "function endingFits(" in run and "fitEndings(form" in run
        assert "endingFits(win, asked)" in run, "a pre-filled link is held to the rule too"
        combined = sources["lib/combined.js"]
        links = combined[combined.index("export function earlierLinks("):]
        links = links[:links.index("\n}\n")]
        assert "182" not in links, "a fixed six-months-back link breaks the rule for a week or a month"

    def test_the_library_names_a_period_with_its_ending(self, sources):
        assert "function periodOf(" in sources["pages/library.js"]

    def test_a_member_book_opens_at_the_moment_or_comment_it_was_sent_to(self, sources):
        report = sources["pages/report.js"]
        assert 'query.get("at")' in report and 'query.get("c")' in report
        assert "openEvidence(deep)" in report
