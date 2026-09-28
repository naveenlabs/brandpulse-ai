"""
tests/test_inclusive_design.py -- the inclusive-design pass of 25 Sep 2026.

One test per fix in INCLUSIVE_DESIGN.md §4, named for what it guarantees. These
are UNIT-level, white-box contracts read off the source and the build: each
pins the property a real-browser measurement in ui_evidence/verify_ui.py found
broken, so the property cannot silently regress between browser runs. Every
one is mutated by ui_evidence/verify_tests_bite.py to show it can fail.

The contrast test is arithmetic, not a string match: it computes WCAG 2.2
relative luminance from the token values themselves.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "interface" / "ui" / "src"
UI = ROOT / "interface" / "ui"
STATIC = ROOT / "interface" / "static"


def read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def code(text: str) -> str:
    """The text with /* */ and // commentary removed: a comment that mentions
    `aria-hidden` to explain its removal is not the code applying it."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


# ------------------------------------------------------------------ A1 caveat

class TestTheLibraryStatesTheBiasCaveat:
    """A1. BIAS_CAVEAT wherever facial-derived scores are surfaced."""

    def test_both_views_carry_the_caveat_note(self):
        lib = read("pages/library.js")
        assert "function caveatNote()" in lib
        # the shelf, and both branches of the list
        assert lib.count("${caveatNote()}") >= 3

    def test_the_words_are_lifted_from_the_served_document_not_restated(self):
        note = between(read("pages/library.js"), "function caveatNote()", "\n}")
        assert '[data-fallback] .fallback__caveat' in note
        assert "IMPORTANT" not in note, "the caveat text is being restated in JS"


# ---------------------------------------------------------- A2, A3 keyboard

class TestTheKeyboardCanDoWhatThePointerCan:

    def test_each_index_entry_takes_its_volume_down(self):
        lib = read("pages/library.js")
        assert 'data-take="${esc(v.id)}"' in lib
        assert "shelf.focus(button.dataset.take)" in lib

    def test_the_list_can_delete_with_two_steps(self):
        lib = read("pages/library.js")
        assert lib.count("deleteControl({") >= 2, "a card kind has no Delete"
        control = between(lib, "function deleteControl(", "\n}")
        assert "data-del-ask" in control and "data-del-yes" in control and "data-del-no" in control
        assert "wireDeletes(root.querySelector(\".lb\"))" in lib

    def test_choosing_what_to_analyse_keeps_focus_on_the_choice(self):
        """
        The mode buttons redraw the whole form, themselves included. Measured in
        Chrome on 26 Sep 2026 before this: focus fell to the page body after
        each of the three.
        """
        wire = between(read("pages/run.js"), "function wireForm()", 'const form = root.querySelector("[data-form]");\n  if (!form)')
        click = code(wire)
        assert click.index("showForm(button.dataset.mode") < click.index(".focus()")
        assert '[data-mode="${button.dataset.mode}"]' in click

    def test_the_list_that_replaces_the_shelf_takes_focus_only_from_what_it_replaced(self):
        """
        Show as a list swaps the whole page. Measured in Chrome on 26 Sep 2026
        before this: focus fell to the page body. Focus that was elsewhere (the
        swap also follows a resize or a change to reduced motion) is not taken.
        """
        swap = code(between(read("pages/library.js"), "const toList = async", "\n  };"))
        assert "root.contains(document.activeElement)" in swap
        assert swap.index("root.contains(document.activeElement)") < swap.index("root.innerHTML")
        assert swap.index("root.innerHTML") < swap.index(".focus(")

    def test_space_is_left_to_the_control_it_is_pressed_on(self):
        shelf = read("lib/shelf.js")
        key = between(shelf, "function onKey(e)", "\n  }")
        guard = key.index("closest(ON_A_CONTROL)")
        assert guard < key.index("e.preventDefault()"), "Space is taken before the control is asked"


# ------------------------------------------------------------ A4 the menu

class TestTheClosedMenuIsHidden:

    def test_the_closed_panel_is_hidden_not_just_transparent(self):
        chassis = read("styles/chassis.css")
        phone = chassis[chassis.index("@media (max-width: 899px) {\n  .masthead { position: sticky; }"):]
        closed = between(phone, "  .navpanel {", "\n  }")
        assert "visibility: hidden" in closed
        opened = between(phone, "  .navtoggle:checked ~ .navpanel {", "\n  }")
        assert "visibility: visible" in opened

    def test_the_toggle_is_named_on_the_control_itself(self):
        chrome = read("lib/chrome.js")
        assert '<input class="navtoggle" type="checkbox" id="nav-open" aria-label="Menu">' in chrome
        assert not re.search(r'<label class="burger"[^>]*aria-label', chrome)


# ------------------------------------------------------------ A5, R2 the film

class TestTheFilmIsReadableAndFits:

    def test_no_beat_is_removed_from_the_accessibility_tree(self):
        film = read("lib/film.js")
        render = code(between(film, "function render()", "\n  }\n  function resize"))
        assert "aria-hidden" not in render and ".inert" not in render
        css = read("styles/film.css")
        beat = re.search(r"#film \.f-beat \{([^}]*)\}", css).group(1)
        assert "visibility" not in beat, "the beats are hidden from assistive technology again"

    def test_the_readings_are_faded_never_hidden(self):
        film = read("lib/film.js")
        assert "evidence.style.visibility" not in film

    def test_the_film_pins_only_where_it_fits(self):
        film = read("lib/film.js")
        assert re.search(r"fits: '\(min-width: 760px\) and \(min-height: 640px\)", film)
        assert "stacked = !context.conditions.fits" in film
        assert "#film.film--chamber.film--stacked" in read("styles/film.css")

    def test_words_that_do_not_fit_stack_the_film(self):
        """WCAG 1.4.12: a reader's own text spacing made three beats run 30 to
        140 px past the chamber, which clips. Words that stop fitting stack the
        film, whatever made them stop fitting."""
        film = read("lib/film.js")
        assert "stacked = !context.conditions.fits || wordsOverflow;" in film
        assert "wordsOverflow = true; mm.rebuild();" in film
        assert "watchWords.observe(el)" in film


# ------------------------------------------------------------ A6 the boot

class TestTheBootScreenCanBeRead:

    def test_it_has_a_control_described_by_the_log(self):
        boot = read("lib/boot.js")
        assert 'data-boot-go aria-describedby="boot-log"' in boot
        assert 'id="boot-log"' in boot
        assert "go.focus(" in boot

    def test_a_modifier_or_a_chord_does_not_dismiss_it(self):
        boot = read("lib/boot.js")
        on_key = between(boot, "onKey = (event) => {", "\n  };")
        assert "MODIFIERS.includes(event.key)" in on_key
        assert "event.ctrlKey || event.altKey || event.metaKey" in on_key

    def test_a_keyboard_reader_is_not_timed_out(self):
        boot = read("lib/boot.js")
        typed = between(boot, "onTyped() {", "\n    },")
        assert "if (byKeys) return;" in typed


# ------------------------------------------------ A7 the pages that were lost

class TestTheReportSaysWhoItIsAbout:

    def test_the_person_in_the_video_is_addressed(self):
        report = read("pages/report.js")
        page = between(report, "function standingPage()", "\n}")
        assert "data-standing" in page
        assert "There is no way to contest a reading in this build." in page
        for owed in ("a named person to contact", "the right to see the frames",
                     "a way to have a reading struck"):
            assert owed in page, f"no longer names what a deployment owes: {owed}"
        # the facial figure is quoted with what it is worse than, from the contract
        assert "CHANNEL_META.facial.accuracy" in page and "FACIAL_REFERENCES.constant.value" in page

    def test_both_books_carry_the_spread_and_the_face_points_to_it(self):
        report = read("pages/report.js")
        assert report.count('spread({ key: "standing", verso: cannotTellPage(), recto: standingPage() })') == 2
        assert 'data-cx-xref="standing"' in report

    def test_what_the_numbers_cannot_tell_you_is_back(self):
        page = between(read("pages/report.js"), "function cannotTellPage()", "\n}")
        assert "data-cannot-tell" in page
        assert "Whether anyone was honest." in page


# ------------------------------------------------------ I1 the motion switch

class TestReduceMotionIsOneMechanism:

    def test_reduced_answers_to_the_system_or_the_switch(self):
        motion = read("lib/motion.js")
        assert 'document.documentElement.dataset.motion === "off"' in motion
        assert "QUERY.matches || chosenOff()" in motion
        assert "new CustomEvent(MOTION_EVENT" in motion

    def test_the_masthead_offers_it_and_respects_the_system(self):
        chrome = read("lib/chrome.js")
        assert "data-motion-toggle" in chrome and 'aria-pressed="${reduced()}"' in chrome
        click = between(chrome, 'motionBtn.addEventListener("click", () => {', "\n  });")
        assert click.index("reducedBySystem()") < click.index("setMotionOff("), \
            "the switch can overrule the operating system"

    @pytest.mark.parametrize("page", ["index.html", "library.html", "report.html", "brand.html", "run.html"])
    def test_every_document_applies_it_before_first_paint(self, page):
        head = (UI / page).read_text(encoding="utf-8").split("</script>")[0]
        assert 'localStorage.getItem("brandpulse-motion") === "off"' in head

    def test_the_css_is_re_emitted_under_the_attribute(self):
        config = (UI / "vite.config.js").read_text(encoding="utf-8")
        assert "motionSwitch()" in config and 'data-motion="off"' in config

    def test_the_build_carries_it(self):
        css = "".join(p.read_text(encoding="utf-8") for p in (STATIC / "assets").glob("*.css"))
        if not css:
            pytest.skip("static/ has not been built")
        assert len(re.findall(r'data-motion=(?:"off"|off)\]', css)) >= 20

    def test_vendored_renderers_follow_it_live(self):
        for module in ("lib/ribbonfield.js", "lib/portalfield.js",
                       "lib/datapixelarc.js", "lib/predictivearc.js"):
            src = read(module)
            assert 'window.addEventListener("motionchange", onMotion)' in src, module
            assert 'window.removeEventListener("motionchange", onMotion)' in src, module


# ------------------------------------------------- I2, R5 one page and print

class TestTheBookReadsAsOnePage:

    def test_one_page_shows_every_chapter(self):
        codex = read("lib/codex.js")
        paint = between(codex, "function paint()", "\n  }")
        assert "const all = readsAsPage();" in paint
        assert "c.hidden = !all &&" in paint

    @pytest.mark.parametrize("page", ["report.html", "brand.html"])
    def test_the_request_is_applied_before_first_paint(self, page):
        head = (UI / page).read_text(encoding="utf-8").split("</script>")[0]
        assert 'document.documentElement.dataset.read = "page"' in head

    def test_printing_is_the_one_page_reading_on_paper(self):
        codex = read("lib/codex.js")
        before = between(codex, 'window.addEventListener("beforeprint", () => {', "\n  });")
        assert 'root.dataset.read = "page"' in before
        assert 'applyTheme("field", { persist: false })' in before
        assert 'window.addEventListener("afterprint"' in codex


# ------------------------------------------------------ A9 input boundaries

def _lum(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


class TestInputsCanBeSeen:
    """A9. WCAG 1.4.11: the boundary of a field is 3:1 against every ground."""

    @pytest.mark.parametrize("theme", ["bench", "field"])
    def test_the_field_edge_is_three_to_one_on_every_ground(self, theme):
        tokens = read("styles/tokens.css")
        start = tokens.index(":root,\n[data-theme=\"bench\"]") if theme == "bench" \
            else tokens.index("[data-theme=\"field\"] {")
        block = tokens[start:tokens.index("}", start)]
        value = lambda name: re.search(rf"--{name}:\s*(#[0-9A-Fa-f]{{6}})", block).group(1)
        edge = value("edge-ctl")
        for ground in ("body", "panel", "screen"):
            assert _ratio(edge, value(ground)) >= 3.0, f"{theme} --edge-ctl on --{ground}"

    def test_the_run_fields_use_it(self):
        run = read("styles/run.css")
        rule = between(run, ".fld input {", "}")
        assert "var(--edge-ctl)" in rule


# ------------------------------------------------------------- the rest

class TestSmallerGuarantees:

    def test_the_library_follows_the_window(self):
        lib = read("pages/library.js")
        assert "const fits = window.matchMedia(SHELF_FITS);" in lib
        on_fit = between(lib, "const onFit = () => {", "\n  };")
        assert "toList(" in on_fit

    def test_the_phone_trace_rule_spares_the_compact_trace(self):
        css = read("styles/transport.css")
        phone = css[css.index("@media (max-width: 860px) {"):]
        assert ".tp:not(.tp--compact) { --id-w: 4.5rem; --lane-h: 40px; }" in phone

    def test_a_field_with_a_problem_says_so_to_assistive_technology(self):
        field = between(read("pages/run.js"), "function field(", "\n}")
        assert 'aria-invalid="true"' in field

    def test_forced_colours_keep_the_marks_that_carry_a_reading(self):
        css = read("styles/chassis.css")
        block = css[css.index("@media (forced-colors: active) {"):]
        assert "background-color: CanvasText" in block and ".bar__fill" in block

    @pytest.mark.parametrize("page", ["pages/report.js", "pages/sweep.js", "pages/library.js"])
    def test_an_error_or_empty_state_is_the_pages_first_heading(self, page):
        src = read(page)
        assert '<h1 class="t-l">${esc(heading)}</h1>' in src

    def test_the_fallback_timer_stops_when_the_bundle_runs(self):
        mount_all = between(read("lib/chrome.js"), "export function mountAll(", "\n}")
        assert mount_all.index("clearTimeout(window.__bpFallback)") < mount_all.index("mountMasthead(")

    def test_the_ledger_is_one_tab_stop(self):
        mark = between(read("pages/report.js"), "function mark(segment) {", "\n  }")
        assert "stop.tabIndex = 0" in mark

    def test_a_grid_keeps_its_own_arrow_keys(self):
        owned = between(read("lib/codex.js"), "const owned = (t) => {", "\n  };")
        assert "[role=grid]" in owned

    def test_a_page_that_scrolls_can_be_scrolled_from_the_keyboard(self):
        mark = between(read("lib/codex.js"), "function markScrollers()", "\n  }\n")
        assert "body.tabIndex = 0" in mark and 'setAttribute("role", "region")' in mark

    def test_small_targets_get_a_24px_hit_area(self):
        css = read("styles/chassis.css")
        block = css[css.index("--- target size (WCAG 2.5.8"):]
        assert "min-height: 24px" in block and "width: max(24px, 100%)" in block

    def test_the_accessibility_scanner_never_ships(self):
        package = json.loads((UI / "package.json").read_text(encoding="utf-8"))
        assert "axe-core" in package.get("devDependencies", {})
        assert "axe-core" not in package.get("dependencies", {})
        for source in SRC.rglob("*.js"):
            assert not re.search(r"(import|require)[^;\n]*axe-core", source.read_text(encoding="utf-8")), \
                f"{source.relative_to(ROOT)} imports the scanner into the product"
        built = list((STATIC / "assets").glob("*.js"))
        assert not any("axe.run(" in p.read_text(encoding="utf-8") for p in built)


# ------------------------------------------------ I4 the accessibility statement

class TestTheAccessibilityStatement:
    """I4. A statement is only honest if it is reachable, complete without
    JavaScript, and says what does not work as plainly as what does."""

    DOC = UI / "accessibility.html"

    def test_it_is_a_well_formed_document(self):
        html = self.DOC.read_text(encoding="utf-8")
        assert '<html lang="en"' in html
        assert 'name="viewport"' in html and "user-scalable" not in html
        assert html.count("<main") == 1 and html.count("<h1") == 1
        body = html[html.index("<body>"):]
        first = re.search(r"<(a|button|input)\b[^>]*>", body).group(0)
        assert 'class="skip-link"' in first

    def test_it_reads_without_javascript(self):
        html = self.DOC.read_text(encoding="utf-8")
        main = html[html.index("<main"):html.index("</main>")]
        assert "data-fallback" not in main, "the statement would be hidden once scripts run"
        assert len(re.sub(r"<[^>]+>", " ", main).split()) > 300

    def test_it_says_what_does_not_work_and_who_it_is_about(self):
        html = self.DOC.read_text(encoding="utf-8")
        assert "partially conforms" in html
        assert "No disabled person has tested this." in html
        assert "none of them can contest a reading" in html

    def test_it_is_in_the_same_place_on_every_page(self):
        assert '["/accessibility", "Accessibility"]' in read("lib/chrome.js")

    def test_it_is_built_and_served(self):
        config = (UI / "vite.config.js").read_text(encoding="utf-8")
        assert 'statement: resolve(import.meta.dirname, "accessibility.html")' in config
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        assert '@app.get("/accessibility")' in app
