"""
verify_tests_bite.py — check that the test suite would actually fail.

A green test suite proves nothing on its own: a test that asserts something
always true is indistinguishable from a test that guards something real, right
up until the thing it guards breaks.

So this script breaks each guarded thing on purpose, one at a time, runs the
test that is supposed to catch it, and restores the file. A guard that stays
green while its subject is broken is reported as a failure of the test, not of
the code.

Nothing is left modified: every mutation is written, tested and reverted inside
a try/finally, and the script verifies the file is byte-identical afterwards.

    python evaluation/ui_evidence/verify_tests_bite.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "tests_bite.json"

# (name, file, find, replace, the test that must catch it)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("valence lexicon drifts from the pipeline",
     "interface/ui/src/lib/contract.js",
     'negative: "NEGATIVE", sad: "NEGATIVE"',
     'negative: "NEGATIVE", sad: "POSITIVE"',
     "tests/test_ui_contracts.py::TestTheContractMirrorsThePipeline::test_the_two_lexicons_are_identical"),

    ("surprise is given a valence",
     "interface/ui/src/lib/contract.js",
     'neutral: "NEUTRAL",',
     'neutral: "NEUTRAL", surprise: "NEUTRAL",',
     "tests/test_ui_contracts.py::TestTheContractMirrorsThePipeline::test_surprise_is_in_neither"),

    ("the flag threshold drifts",
     "interface/ui/src/lib/contract.js",
     "export const CONFLICT_FLAG_THRESHOLD = 0.75;",
     "export const CONFLICT_FLAG_THRESHOLD = 0.6;",
     "tests/test_ui_contracts.py::TestTheContractMirrorsThePipeline::test_the_flag_threshold_is_the_orchestrators"),

    ("a channel accuracy is edited without the evidence moving",
     "interface/ui/src/lib/contract.js",
     "accuracy: 34.2,",
     "accuracy: 64.2,",
     "tests/test_ui_contracts.py::TestEveryQuotedFigureIsMeasured::test_channel_accuracies_match_the_evidence_file"),

    ("the facial figure is quoted without what it is worse than",
     "interface/ui/src/lib/contract.js",
     'worseThanConstant: "below an always-NEUTRAL constant, which scores 67.5%",',
     "",
     "tests/test_ui_contracts.py::TestEveryQuotedFigureIsMeasured::test_the_facial_figure_is_never_quoted_without_what_it_is_worse_than"),

    ("an invented percentage is typed into a page",
     "interface/ui/src/pages/report.js",
     "<h2 class=\"t-xl\" id=\"weak-h\">Two of the four barely beat guessing.</h2>",
     "<h2 class=\"t-xl\" id=\"weak-h\">Accurate 91.4% of the time.</h2>",
     "tests/test_ui_contracts.py::TestEveryQuotedFigureIsMeasured::test_no_source_file_invents_an_accuracy"),

    ("a missing reading is defaulted to neutral",
     "interface/ui/src/lib/contract.js",
     "  if (facial) out.facial = facial;",
     '  out.facial = facial || "NEUTRAL";',
     "tests/test_ui_contracts.py::TestAbsenceIsDrawnAsAbsence::test_a_channel_with_no_reading_is_omitted_not_defaulted"),

    ("the absence loses its visible boundary",
     "interface/ui/src/styles/base.css",
     "  box-shadow: inset 0 0 0 1px var(--hairline);",
     "",
     "tests/test_ui_contracts.py::TestAbsenceIsDrawnAsAbsence::test_the_absence_is_given_a_visible_mark"),

    ("comment text stops being escaped",
     "interface/ui/src/pages/report.js",
     "<p>${esc(c.text)}</p>",
     "<p>${c.text}</p>",
     "tests/test_ui_contracts.py::TestUntrustedTextReachesTheDomEscaped::test_untrusted_values_are_escaped_at_every_interpolation"),

    ("a comment author is rendered",
     "interface/ui/src/pages/report.js",
     "<span class=\"t-micro\">${esc(c.label)}",
     "<span class=\"t-micro\">${esc(c.authorDisplayName)} ${esc(c.label)}",
     "tests/test_ui_contracts.py::TestPrivacy::test_no_comment_author_is_ever_rendered"),

    ("a module starts fetching from another host",
     "interface/ui/src/lib/api.js",
     'export const listReports = () => fetch("/reports").then(unwrap);',
     'export const listReports = () => fetch("https://cdn.example.com/reports").then(unwrap);',
     "tests/test_ui_contracts.py::TestNothingAddressesAnotherHost::test_no_shipped_code_requests_another_host"),

    ("the bias caveat is put behind a disclosure",
     "interface/ui/src/pages/report.js",
     '<div class="caveatband" data-enter="late">',
     '<details class="caveatband" data-enter="late"><summary>Bias caveat</summary>',
     "tests/test_ui_contracts.py::TestTheBiasCaveatIsUndismissable::test_it_is_not_behind_a_disclosure"),

    ("the bias caveat is clamped by CSS",
     "interface/ui/src/styles/base.css",
     ".caveatband { position: relative; z-index: 4;",
     ".caveatband { max-height: 20px; overflow: hidden; position: relative; z-index: 4;",
     "tests/test_ui_contracts.py::TestTheBiasCaveatIsUndismissable::test_it_is_not_collapsed_or_clipped_by_css"),

    ("a missing caveat goes quiet instead of saying so",
     "interface/ui/src/pages/report.js",
     '<b style="color:var(--tear)">missing.</b>',
     "",
     "tests/test_ui_contracts.py::TestTheBiasCaveatIsUndismissable::test_a_report_without_one_says_so_rather_than_going_quiet"),

    ("the JS motion durations drift from the CSS ones",
     "interface/ui/src/lib/motion.js",
     "  base: 0.32,",
     "  base: 0.5,",
     "tests/test_ui_contracts.py::TestMotionIsTokenisedNotScattered::test_the_js_durations_mirror_the_css_ones"),

    ("reduced motion stops being read in JS",
     "interface/ui/src/lib/motion.js",
     'export const reduced = () =>\n  window.matchMedia("(prefers-reduced-motion: reduce)").matches;',
     "export const reducedDisabled = () => false;\nexport const reduced = () => false;",
     "tests/test_ui_contracts.py::TestMotionIsTokenisedNotScattered::test_reduced_motion_is_honoured_in_js_not_only_css"),

    ("the entrance would hide content when the script fails",
     "interface/ui/src/styles/base.css",
     ".js.is-entered [data-enter] { opacity: 1; }",
     ".js.is-entered [data-enter] { opacity: 0.99; }",
     "tests/test_ui_contracts.py::TestMotionIsTokenisedNotScattered::test_the_entrance_reveals_everything_if_the_script_never_runs"),

    ("reduced motion cuts instead of transitioning",
     "interface/ui/src/styles/tokens.css",
     "    --d-base: 1ms;",
     "    --d-base: 0ms;",
     "tests/test_ui_contracts.py::TestMotionIsTokenisedNotScattered::test_reduced_motion_collapses_durations_rather_than_removing_transitions"),

    ("the coverage floor drifts from the evidence script",
     "interface/ui/src/lib/contract.js",
     "export const CHANNEL_COVERAGE_FLOOR = 0.5;",
     "export const CHANNEL_COVERAGE_FLOOR = 0.25;",
     "tests/test_ui_contracts.py::TestTheContractMirrorsThePipeline::test_the_coverage_floor_matches_the_evidence_script"),

    ("a vocal shape stops being read",
     "interface/ui/src/lib/contract.js",
     'if (typeof vocal === "string") return vocal;',
     "",
     "tests/test_ui_contracts.py::TestBothVocalShapesAreRead::test_the_reader_handles_both"),

    # --- the run page's voice (added 12 Sep 2026) ---------------------------
    #
    # Until these, not one mutation in this file touched an ARIA property or a
    # live region — the whole accessibility layer was guarded by tests nothing
    # had ever tried to break.

    ("the live region is written into markup that gets thrown away",
     "interface/ui/src/pages/run.js",
     '<div class="stages" data-stages>',
     '<div class="stages" data-stages aria-live="polite">',
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_run_page_does_not_write_a_live_region_into_its_own_markup"),

    ("the live region is attached inside the subtree that is re-rendered",
     "interface/ui/src/lib/announce.js",
     "document.body.appendChild(node)",
     'document.querySelector("main").appendChild(node)',
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_live_region_is_attached_outside_every_re_rendered_subtree"),

    ("the regions stop being mounted before anything renders",
     "interface/ui/src/lib/chrome.js",
     "  mountAnnouncer();",
     "",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_regions_exist_before_anything_needs_to_speak"),

    ("an ending renders but is never spoken",
     "interface/ui/src/pages/run.js",
     """  lost: {
    title: "Unknown job",
    urgent: true,""",
     """  notlost: {
    title: "Unknown job",
    urgent: true,""",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_every_ending_the_page_can_render_is_also_spoken"),

    ("a failure stops interrupting and waits its turn",
     "interface/ui/src/pages/run.js",
     """  lost: {
    title: "Unknown job",
    urgent: true,""",
     """  lost: {
    title: "Unknown job",
    urgent: false,""",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_failures_interrupt_and_the_rest_wait"),

    ("the queued bar claims nought stages complete",
     "interface/ui/src/pages/run.js",
     'prog.removeAttribute("aria-valuenow");',
     'prog.setAttribute("aria-valuenow", "0");',
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_progress_bar_never_reports_a_value_without_explaining_it"),

    ("a stage can be shown but not said",
     "interface/ui/src/pages/run.js",
     '    spoken: "computing the final scores",\n',
     "",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_every_stage_has_a_name_that_can_be_said"),

    ("an HTML entity reaches a spoken stage name",
     "interface/ui/src/pages/run.js",
     'spoken: "fetching and classifying audience comments",',
     'spoken: "fetching &amp; classifying audience comments",',
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_every_stage_has_a_name_that_can_be_said"),

    ("the finished run announces one score and not the other",
     "interface/ui/src/pages/run.js",
     "+ `out of 100. Brand health ${score(result.brand_health_score)} out of 100. `",
     "+ `out of 100. `",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_finished_run_speaks_both_scores"),

    ("the stage is re-announced on every poll",
     "interface/ui/src/pages/run.js",
     "if (index !== spokenStage) {",
     "if (true) {",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_a_stage_is_announced_on_change_and_not_on_every_poll"),

    ("the bar goes back to sweeping end to end for the whole run",
     "interface/ui/src/styles/run.css",
     ".prog i[data-now] { left: calc(var(--done, 0) * 100%);",
     ".prog[data-indeterminate] i { width: 32%; }\n.prog i[data-now] { left: calc(var(--done, 0) * 100%);",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_indeterminate_flag_is_gone_from_the_markup_and_the_stylesheet"),

    ("an injected alert role comes back alongside the live region",
     "interface/ui/src/pages/run.js",
     '<div class="banner" data-enter="item">\n          <span class="t-micro u-tear"',
     '<div class="banner" data-enter="item" role="alert">\n          <span class="t-micro u-tear"',
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_it_does_not_rely_on_an_injected_alert_role"),

    # --- reflow is not masked (added 12 Sep 2026) ---------------------------

    ("the overflow mask comes back on the body",
     "interface/ui/src/styles/base.css",
     "  text-rendering: optimizeLegibility;",
     "  text-rendering: optimizeLegibility;\n  overflow-x: hidden;",
     "tests/test_ui_contracts.py::TestNothingMasksAReflowFailure::test_the_body_rule_does_not_hide_horizontal_overflow"),

    ("the overflow mask comes back somewhere else at page level",
     "interface/ui/src/styles/tokens.css",
     ":root {",
     ":root {\n  overflow-x: hidden;",
     "tests/test_ui_contracts.py::TestNothingMasksAReflowFailure::test_no_stylesheet_hides_overflow_at_page_level"),

    ("the readout goes back to four readings abreast when narrow",
     "interface/ui/src/styles/report.css",
     "  .probe__reads { grid-template-columns: repeat(2, minmax(0, 1fr));",
     "  .probe__reads { grid-template-columns: repeat(4, auto);",
     "tests/test_ui_contracts.py::TestNothingMasksAReflowFailure::test_the_readout_stops_putting_four_readings_abreast_when_narrow"),

    ("a half-visible rail link stops scrolling into view on focus",
     "interface/ui/src/styles/report.css",
     "    scroll-padding-inline: var(--gutter);",
     "",
     "tests/test_ui_contracts.py::TestNothingMasksAReflowFailure::test_the_act_rail_scrolls_a_half_visible_link_into_view"),

    ("the channel track stops stacking when motion is reduced",
     "interface/ui/src/styles/overview.css",
     "@media (max-width: 900px), (prefers-reduced-motion: reduce) {",
     "@media (max-width: 900px) {",
     "tests/test_ui_contracts.py::TestNothingMasksAReflowFailure::test_the_channel_track_stacks_when_motion_is_reduced"),

    ("the pinned track stops checking the motion preference",
     "interface/ui/src/pages/overview.js",
     "  if (reduced() || !window.matchMedia(\"(min-width: 901px)\").matches) return;",
     "  if (!window.matchMedia(\"(min-width: 901px)\").matches) return;",
     "tests/test_ui_contracts.py::TestNothingMasksAReflowFailure::test_the_pin_itself_is_still_skipped_when_motion_is_reduced"),

    # --- a control can be spoken (added 12 Sep 2026) ------------------------

    ("the theme toggle stops naming the word on the button",
     "interface/ui/src/lib/chrome.js",
     "      `${label.textContent} \\u2014 switch to the ${next === \"plate\" ? \"paper\" : \"ink\"} theme`);",
     "      `Switch to the ${next === \"plate\" ? \"paper\" : \"ink\"} theme`);",
     "tests/test_ui_contracts.py::TestEveryControlCanBeSpoken::test_the_theme_toggle_leads_with_the_word_on_the_button"),

    ("a ledger chip's name replaces its visible words instead of leading with them",
     "interface/ui/src/pages/report.js",
     "            ? ` aria-label=\"${esc(`${view.label} ${shown} \\u2014 ${view.title}`)}\"`",
     "            ? ` aria-label=\"${esc(`${view.title}`)}\"`",
     "tests/test_ui_contracts.py::TestEveryControlCanBeSpoken::test_the_ledger_chips_lead_with_their_visible_words"),

    ("the trace goes back to being named by its instructions",
     "interface/ui/src/pages/report.js",
     'aria-label="The trace"',
     'aria-label="Inspect the trace. Use the left and right arrow keys to step through segments."',
     "tests/test_ui_contracts.py::TestEveryControlCanBeSpoken::test_the_trace_is_named_not_narrated"),

    ("the trace's keyboard instructions stop being explained anywhere",
     "interface/ui/src/pages/report.js",
     "        End for the first and last, and Enter to open a segment in full.",
     "        Step through segments.",
     "tests/test_ui_contracts.py::TestEveryControlCanBeSpoken::test_the_description_it_points_at_carries_the_keys"),

    ("the skip link goes back to being positioned against the document",
     "interface/ui/src/styles/base.css",
     ".skip-link {\n  position: fixed;",
     ".skip-link {\n  position: absolute;",
     "tests/test_ui_contracts.py::TestFocusLandsWhereItCanBeSeen::test_the_skip_link_is_fixed_to_the_viewport_not_the_document"),

    # --- the reader's own text spacing (added 12 Sep 2026) ------------------

    ("the ledger text goes back to one nowrap line",
     "interface/ui/src/styles/report.css",
     ".row__txt { color: var(--text-dim); font-family: var(--font-voice);\n            display: -webkit-box; -webkit-line-clamp: 14;",
     ".row__txt { color: var(--text-dim); font-family: var(--font-voice);\n            white-space: nowrap; text-overflow: ellipsis;",
     "tests/test_ui_contracts.py::TestTheReadersOwnSpacingCostsThemNothing::test_the_ledger_text_wraps_rather_than_running_off_its_column"),

    ("a channel name goes back to being cut instead of breaking",
     "interface/ui/src/styles/report.css",
     "  overflow-wrap: anywhere;",
     "  text-overflow: ellipsis;",
     "tests/test_ui_contracts.py::TestTheReadersOwnSpacingCostsThemNothing::test_a_channel_name_can_break_rather_than_be_cut"),

    ("the full quote starts clamping too",
     "interface/ui/src/styles/report.css",
     ".said { font-family: var(--font-voice); font-style: italic; font-weight: 340;",
     ".said { overflow: hidden; font-family: var(--font-voice); font-style: italic; font-weight: 340;",
     "tests/test_ui_contracts.py::TestTheReadersOwnSpacingCostsThemNothing::test_the_full_quote_block_does_not_clamp"),

    ("the ledger clamp is tightened back to a value that loses rows",
     "interface/ui/src/styles/report.css",
     "-webkit-line-clamp: 14;",
     "-webkit-line-clamp: 3;",
     "tests/test_ui_contracts.py::TestTheReadersOwnSpacingCostsThemNothing::test_the_ledger_text_wraps_rather_than_running_off_its_column"),

    # --- the numbers say what they mean (added 12 Sep 2026) -----------------

    ("the library stops showing the bias caveat",
     "interface/ui/src/pages/library.js",
     '<div class="caveatband" data-enter="item">',
     '<div class="notaband" data-enter="item">',
     "tests/test_ui_contracts.py::TestTheBiasCaveatIsUndismissable::test_it_is_rendered_on_the_library_too"),

    ("the library hardcodes the caveat instead of reading it off the reports",
     "interface/ui/src/pages/library.js",
     "  const biasCaveat = rows.map((r) => r.biasCaveat).find(Boolean) || null;",
     '  const biasCaveat = "Facial emotion recognition (DeepFace) has documented accuracy disparities across skin tone and gender (Buolamwini & Gebru, 2018).";',
     "tests/test_ui_contracts.py::TestTheBiasCaveatIsUndismissable::test_the_library_takes_the_words_off_the_reports"),

    ("the caveat becomes revealable on hover",
     "interface/ui/src/styles/base.css",
     ".caveatband p { color: var(--text-dim); max-width: 76rem; }",
     ".caveatband p { color: var(--text-dim); max-width: 76rem; }\n.caveatband:hover { opacity: 1; }",
     "tests/test_ui_contracts.py::TestTheBiasCaveatIsUndismissable::test_it_is_not_revealed_on_hover"),

    ("a headline score loses its plain-language line",
     "interface/ui/src/pages/report.js",
     '          <span class="score__means t-small">Mostly what the audience wrote underneath.\n            <b>Not</b> how good the product is.</span>\n',
     "",
     "tests/test_ui_contracts.py::TestTheScoresExplainThemselvesInOrdinaryWords::test_every_headline_score_carries_a_plain_sentence"),

    ("a gloss drops the half that says what the number is not",
     "interface/ui/src/pages/report.js",
     "disagreed with each other. <b>Not</b> whether anyone was honest.",
     "disagreed with each other.",
     "tests/test_ui_contracts.py::TestTheScoresExplainThemselvesInOrdinaryWords::test_each_one_says_what_the_number_is_not"),

    ("the limits move behind a disclosure",
     "interface/ui/src/pages/report.js",
     '      <div class="limits" data-enter="item" aria-labelledby="limits-h">',
     '      <div class="limits" data-enter="item" aria-labelledby="limits-h"><details><summary>Limits</summary>',
     "tests/test_ui_contracts.py::TestTheScoresExplainThemselvesInOrdinaryWords::test_the_limits_block_is_in_the_document_not_behind_an_interaction"),

    ("the limits stop naming the controller finding",
     "interface/ui/src/pages/report.js",
     "49.08 points, on byte-identical inputs",
     "a large amount, on byte-identical inputs",
     "tests/test_ui_contracts.py::TestTheScoresExplainThemselvesInOrdinaryWords::test_it_names_the_thing_a_reader_is_least_likely_to_guess"),

    # --- language, honestly (added 12 Sep 2026) -----------------------------

    ("the report's language note is deleted",
     "interface/ui/src/pages/report.js",
     '      <p class="sechead__note t-small">\n        Every quote below is Whisper&rsquo;s English transcription. The transcriber is\n        told the audio is English rather than asked, so a video in another language\n        is transcribed into English words anyway and nothing on this page would\n        show it.\n      </p>\n',
     "",
     "tests/test_ui_contracts.py::TestTheInterfaceIsHonestAboutLanguage::test_the_report_says_it_where_the_quotes_are"),

    ("the overview's English-only limit is deleted",
     "interface/ui/src/pages/overview.js",
     '      <div class="wrong__row">\n        <div><h3>It assumes the video is in English.</h3></div>\n        <p class="t-small">\n          The transcriber is not asked what language it is hearing. It is told:\n          <code>audio_module.py</code> calls Whisper with <code>language=&quot;en&quot;</code>\n          fixed. A video in any other language is transcribed into English words\n          anyway, every channel downstream reads that text, and nothing in the run\n          reports that it happened. There is no detection step to fail, which is\n          why this is written down here rather than handled at runtime — and why\n          no part of a report claims to know what language was spoken.\n        </p>\n      </div>\n',
     "",
     "tests/test_ui_contracts.py::TestTheInterfaceIsHonestAboutLanguage::test_the_overview_states_it_with_its_other_limits"),

    ("a language is invented for every quoted segment",
     "interface/ui/src/pages/report.js",
     '    <span class="row__txt t-small">${esc(segment.text || "\u2014")}</span>',
     '    <span class="row__txt t-small" lang="en">${esc(segment.text || "\u2014")}</span>',
     "tests/test_ui_contracts.py::TestTheInterfaceIsHonestAboutLanguage::test_the_report_does_not_invent_a_language_for_a_quote"),

    # --- the person being scored (added 12 Sep 2026) ------------------------

    ("the standing statement moves away from the face",
     "interface/ui/src/pages/report.js",
     '    <div class="standing" data-enter="late" aria-labelledby="standing-h">',
     '    <div class="elsewhere" data-enter="late" aria-labelledby="standing-h">',
     "tests/test_ui_contracts.py::TestTheScoredPersonHasStanding::test_the_statement_sits_with_the_face_not_in_a_footnote"),

    ("the facial figure beside the face loses what it is worse than",
     "interface/ui/src/pages/report.js",
     "          ${CHANNEL_META.facial.worseThanConstant}. Its characteristic error is",
     "          a low figure. Its characteristic error is",
     "tests/test_ui_contracts.py::TestTheScoredPersonHasStanding::test_it_quotes_the_facial_accuracy_where_the_face_is"),

    ("the appeal route is claimed to exist",
     "interface/ui/src/pages/report.js",
     "          appeal route in this build, because there is no server and no account \u2014",
     "          appeal process, reachable from the menu \u2014",
     "tests/test_ui_contracts.py::TestTheScoredPersonHasStanding::test_it_offers_a_route_and_is_honest_that_there_is_not_one_here"),

    ("the statement stops saying the number is not about the person",
     "interface/ui/src/pages/report.js",
     "          <b>None of these numbers is a finding about them.</b> They measure how far",
     "          <b>How this video scored.</b> These measure how far",
     "tests/test_ui_contracts.py::TestTheScoredPersonHasStanding::test_it_says_what_the_numbers_are_not"),

    ("the video URL is printed on the page",
     "interface/ui/src/pages/report.js",
     "  const videoId = isMember ? source.videoId : videoIdOf(report);",
     "  const videoId = isMember ? source.videoId : videoIdOf(report); const shown = report.video_url;",
     "tests/test_ui_contracts.py::TestTheScoredPersonHasStanding::test_the_video_url_never_reaches_a_report_page"),

    # --- governance documents (added 12 Sep 2026) ---------------------------
    #
    # Prose cannot guard itself. These break the link between a document and the
    # file whose number it quotes, which is how a stakeholder analysis rots:
    # not by being wrong when written, but by staying still while the code moves.

    ("the inclusion analysis drifts from the deployed transcriber",
     "pipeline/audio_module.py",
     'WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")',
     'WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")',
     "tests/test_governance.py::TestEveryFigureInTheAnalysisStillHolds::test_the_deployed_whisper_model"),

    ("the comments stop being relevance-ordered without the analysis noticing",
     "pipeline/comment_module.py",
     '            order="relevance",',
     '            order="time",',
     "tests/test_governance.py::TestEveryFigureInTheAnalysisStillHolds::test_the_comment_ordering"),

    ("the report adds the scored creator as a stakeholder and the analysis goes stale",
     "final_report/source/content_b.py",
     "Secondary users are agencies and market-research firms",
     "The creator in the video is also a stakeholder. Secondary users are agencies and market-research firms",
     "tests/test_governance.py::TestEveryFigureInTheAnalysisStillHolds::test_the_report_still_omits_the_people_it_scores"),

    ("the consent record stops saying the participants are named",
     "evaluation/user_pilot/CONSENT.md",
     "| Their first names in the **submitted report** | **Yes** \u2014 in the August draft "
     "(body text, appendix headings A.1, A.2, A.3) and in the September report "
     "(Appendix A). The report is not in this repository |",
     "| Their first names in the **submitted report** | No |",
     "tests/test_governance.py::TestTheConsentRecordStaysAccurate::test_the_document_matches_reality_in_both_directions"),

    ("the new instrument is cited before it has been run",
     "evaluation/user_pilot/PILOT_QUESTIONS_V2.md",
     "**Status: written 12 Sep 2026. NOT YET RUN.**",
     "**Status: written 12 Sep 2026. Complete.**",
     "tests/test_governance.py::TestTheArtefactsExistAndAreReachable::test_the_new_instrument_is_marked_unrun"),

    # --- the fairness bench (added 12 Sep 2026) -----------------------------
    #
    # The failure mode a fairness bench has is asserting a disparity it has not
    # measured, and that failure looks like success from the inside. These break
    # the refusals rather than the arithmetic.

    ("the write-up starts claiming the system is not biased by skin tone",
     "research/fairness_bench/FAIRNESS_ANALYSIS.md",
     "- **Not** that the system is biased by skin tone. Q2 is unrun.",
     "- The system shows no skin-tone bias.",
     "tests/test_fairness_bench.py::TestItStillRefusesWhatItCannotShow::test_the_write_up_refuses_it[that skin tone causes it-Not** that the system is biased by skin tone]"),

    ("the overlapping spread is quoted as a finding after all",
     "research/fairness_bench/FAIRNESS_ANALYSIS.md",
     "**This is not a finding, and `PROTOCOL.md` \u00a75.3 said so in advance.**",
     "**This is a 30.7-point disparity across speakers.**",
     "tests/test_fairness_bench.py::TestTheProtocolWasPreRegisteredAndKept::test_the_declared_rule_is_actually_applied"),

    ("the bench re-implements the ground-truth mapping instead of importing it",
     "research/fairness_bench/per_speaker.py",
     "import ground_truth_v2 as GT          # noqa: E402  (path set above)",
     "EXPRESSION_THREE = {'happy': 'POSITIVE'}  # re-implemented",
     "tests/test_fairness_bench.py::TestItReproducesTheBenchItRecuts::test_it_does_not_reimplement_the_ground_truth"),

    ("the rating tool embeds an unverified colour scale",
     "research/fairness_bench/monk_rating.html",
     '  .scale button { width: 54px; height: 54px;',
     '  .s1{background:#f6ede4}.s10{background:#292420}\n  .scale button { width: 54px; height: 54px;',
     "tests/test_fairness_bench.py::TestTheProtocolWasPreRegisteredAndKept::test_the_instrument_does_not_reproduce_the_scale"),

    ("the uncited-disparity admission is removed",
     "research/fairness_bench/FAIRNESS_ANALYSIS.md",
     "**Until it runs, this project continues to cite a skin-tone disparity it has not\nobserved on its own data.**",
     "The caveat is supported by the evidence in this directory.",
     "tests/test_fairness_bench.py::TestItStillRefusesWhatItCannotShow::test_it_names_the_gap_it_leaves_open"),
    # ── sweeps, 19 Sep 2026 ────────────────────────────────────────────────
    # Five contracts added with the brand and product modes. Each one exists
    # because the thing it guards was got wrong at least once while building
    # them, which is the only evidence that a guard is load-bearing.

    ("a fifth ending renders but is never spoken",
     "interface/ui/src/pages/run.js",
     "  partial: {\n    title: \"Partly finished\",",
     "  partialX: {\n    title: \"Partly finished\",",
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_every_ending_the_page_can_render_is_also_spoken"),

    ("a live region is written into the run page's own markup",
     "interface/ui/src/pages/run.js",
     '<p class="t-data" data-chosen></p>',
     '<p class="t-data" data-chosen aria-live="polite"></p>',
     "tests/test_ui_contracts.py::TestTheRunPageSaysWhatItShows::test_the_run_page_does_not_write_a_live_region_into_its_own_markup"),

    ("the combined report stops saying what it is not",
     "interface/static/brand.html",
     "It is <strong>not</strong> a\n        measure of whether the brand is liked",
     "It is a\n        measure of whether the brand is liked",
     "tests/test_ui_routes.py::TestTheCombinedReportDocument::test_the_no_script_core_says_what_a_combined_score_is_not"),

    ("the combined report's caveat is hard-coded instead of substituted",
     "interface/static/brand.html",
     "<!--BP:CAVEATS-->",
     "<p>IMPORTANT: Facial emotion recognition (DeepFace) has documented "
     "accuracy disparities across skin tone and gender.</p>",
     "tests/test_ui_routes.py::TestTheCombinedReportDocument::test_the_bias_caveat_reaches_it_without_javascript"),

    ("a page module stops consulting reduced motion",
     "interface/ui/src/pages/brand.js",
     "import { entrance, reduced, revealOnScroll, startScroll }",
     "import { entrance, revealOnScroll, startScroll }",
     "tests/test_ui_contracts.py::TestMotionIsTokenisedNotScattered::test_every_page_consults_it"),

    # --- the chart vocabulary, and the way into a member report ---------------

    ("a chart names a colour instead of reading the theme",
     "interface/ui/src/lib/charts.js",
     "ctx.fillStyle = over ? palette.tear : palette.text;",
     'ctx.fillStyle = over ? "#F44336" : "#BBDEFB";',
     "tests/test_ui_contracts.py::TestTheChartsSayWhereTheirNumbersCameFrom::test_no_chart_hardcodes_a_colour"),

    ("the undamped score is divided back out instead of read",
     "interface/ui/src/lib/contract.js",
     "    const before = Number(match[3]);",
     "    const before = Number(match[4]) / Number(match[5]);",
     "tests/test_ui_contracts.py::TestTheChartsSayWhereTheirNumbersCameFrom::test_the_damping_figures_are_read_and_not_divided_back_out"),

    ("a channel pair that never disagreed is dropped from the grid",
     "interface/ui/src/lib/contract.js",
     "    pairs: [...pairs.entries()].map(([key, count]) => {",
     "    pairs: [...pairs.entries()].filter((p) => p.count > 0).map(([key, count]) => {",
     "tests/test_ui_contracts.py::TestTheChartsSayWhereTheirNumbersCameFrom::test_the_grid_keeps_a_pair_that_never_disagreed"),

    ("a member row stops being a link",
     "interface/ui/src/pages/brand.js",
     '<a class="bitem__open" href="${href}">',
     '<span class="bitem__open">',
     "tests/test_ui_contracts.py::TestAMemberOfASweepCanActuallyBeOpened::test_the_row_offers_a_real_link"),

    ("the member link is taken out of the tab order",
     "interface/ui/src/styles/brand.css",
     ".bitem__open { color: inherit; text-decoration: none; }",
     ".bitem__open { display: contents; color: inherit; }",
     "tests/test_ui_contracts.py::TestAMemberOfASweepCanActuallyBeOpened::test_the_link_is_not_hidden_from_the_tab_order"),

    ("the report page forgets it can show a sweep member",
     "interface/ui/src/pages/report.js",
     '      kind: "member",',
     '      kind: "report",',
     "tests/test_ui_contracts.py::TestAMemberOfASweepCanActuallyBeOpened::test_the_report_page_knows_both_of_its_addresses"),

    ("the comparison quotes the gap between means as clearance",
     "interface/ui/src/pages/brand.js",
     "  const clearance = Math.max(left.min, right.min) - Math.min(left.max, right.max);",
     "  const clearance = gap;",
     "tests/test_ui_contracts.py::TestTheComparisonDoesNotOverstateItself::test_clearance_is_measured_between_the_sets_not_the_means"),

    ("the comparison goes back to assuming five videos a side",
     "interface/ui/src/pages/brand.js",
     "`videos can establish.`,",
     "`videos can establish. Ask what these ten videos show.`,",
     "tests/test_ui_contracts.py::TestTheComparisonDoesNotOverstateItself::test_it_counts_the_videos_it_actually_has"),

    ("the combined report starts printing the analysed video's URL",
     "interface/ui/src/pages/brand.js",
     "  const man = await manifest();",
     "  const man = await manifest(); const shown = record.video_url;",
     "tests/test_ui_contracts.py::TestTheScoredPersonHasStanding::test_the_video_url_never_reaches_a_report_page"),

    ("an unvoiced segment is drawn as a pitch of zero",
     "interface/ui/src/pages/report.js",
     '    if (key === "pitch" && value === 0) value = null;',
     "    // pitch zero is fine",
     "tests/test_ui_contracts.py::TestAbsenceIsNotDrawnAsAValue::test_an_unvoiced_segment_is_not_plotted_as_zero_hertz"),

    ("the page paraphrases the pipeline instead of quoting it",
     "interface/ui/src/pages/brand.js",
     "                 summary.means_not || \"\")}",
     "                 \"\")}",
     "tests/test_ui_contracts.py::TestTheComparisonDoesNotOverstateItself::test_the_pipelines_own_wording_reaches_the_reader"),


    # --- the inclusive-design pass, 25 Sep 2026 (INCLUSIVE_DESIGN.md) ---
    ('A1 the library caveat leaves one view',
     'interface/ui/src/pages/library.js',
     '${caveatNote()}',
     '',
     'tests/test_inclusive_design.py::TestTheLibraryStatesTheBiasCaveat::test_both_views_carry_the_caveat_note'),

    ('A2 an index entry stops taking its volume down',
     'interface/ui/src/pages/library.js',
     'shelf.focus(button.dataset.take)',
     'void 0',
     'tests/test_inclusive_design.py::TestTheKeyboardCanDoWhatThePointerCan::test_each_index_entry_takes_its_volume_down'),

    ('A2 the list loses its Delete wiring',
     'interface/ui/src/pages/library.js',
     'wireDeletes(root.querySelector(".lb"));',
     '',
     'tests/test_inclusive_design.py::TestTheKeyboardCanDoWhatThePointerCan::test_the_list_can_delete_with_two_steps'),

    ('A3 Space is taken at the window again',
     'interface/ui/src/lib/shelf.js',
     'if (t && t.closest && t.closest(ON_A_CONTROL)) return;',
     '',
     'tests/test_inclusive_design.py::TestTheKeyboardCanDoWhatThePointerCan::test_space_is_left_to_the_control_it_is_pressed_on'),

    ('A4 the closed menu is only transparent',
     'interface/ui/src/styles/chassis.css',
     '    visibility: hidden;\n    transition: opacity var(--t-med)',
     '    transition: opacity var(--t-med)',
     'tests/test_inclusive_design.py::TestTheClosedMenuIsHidden::test_the_closed_panel_is_hidden_not_just_transparent'),

    ('A5 the film hides its beats again',
     'interface/ui/src/lib/film.js',
     "beats.forEach((beat, i) => beat.classList.toggle('is-current', stacked || i === active));",
     "beats.forEach((beat, i) => { beat.classList.toggle('is-current', stacked || i === active); beat.setAttribute('aria-hidden', String(i !== active)); });",
     'tests/test_inclusive_design.py::TestTheFilmIsReadableAndFits::test_no_beat_is_removed_from_the_accessibility_tree'),

    ('R2 the film pins on every screen',
     'interface/ui/src/lib/film.js',
     'stacked = !context.conditions.fits || wordsOverflow;',
     'stacked = false;',
     'tests/test_inclusive_design.py::TestTheFilmIsReadableAndFits::test_the_film_pins_only_where_it_fits'),

    ('1.4.12 the film clips words that do not fit',
     'interface/ui/src/lib/film.js',
     "if (!stacked && !wordsOverflow && overflowing()) { wordsOverflow = true; mm.rebuild(); }",
     '',
     'tests/test_inclusive_design.py::TestTheFilmIsReadableAndFits::test_words_that_do_not_fit_stack_the_film'),

    ('A6 a modifier key dismisses the boot screen',
     'interface/ui/src/lib/boot.js',
     'if (MODIFIERS.includes(event.key) || event.ctrlKey || event.altKey || event.metaKey) return;',
     '',
     'tests/test_inclusive_design.py::TestTheBootScreenCanBeRead::test_a_modifier_or_a_chord_does_not_dismiss_it'),

    ('A6 the boot screen times a keyboard reader out',
     'interface/ui/src/lib/boot.js',
     '      if (byKeys) return;\n',
     '',
     'tests/test_inclusive_design.py::TestTheBootScreenCanBeRead::test_a_keyboard_reader_is_not_timed_out'),

    ('A6 the boot screen loses its control',
     'interface/ui/src/lib/boot.js',
     ' aria-describedby="boot-log"',
     '',
     'tests/test_inclusive_design.py::TestTheBootScreenCanBeRead::test_it_has_a_control_described_by_the_log'),

    ('A7 the page invents an appeal route',
     'interface/ui/src/pages/report.js',
     'There is no way to contest a reading in this build.',
     'Readings can be contested.',
     'tests/test_inclusive_design.py::TestTheReportSaysWhoItIsAbout::test_the_person_in_the_video_is_addressed'),

    ('A7 one book loses the standing spread',
     'interface/ui/src/pages/report.js',
     'spread({ key: "standing", verso: cannotTellPage(), recto: standingPage() })',
     'spread({ key: "standing-gone", verso: "", recto: "" })',
     'tests/test_inclusive_design.py::TestTheReportSaysWhoItIsAbout::test_both_books_carry_the_spread_and_the_face_points_to_it'),

    ('A7 what the numbers cannot tell is dropped',
     'interface/ui/src/pages/report.js',
     'Whether anyone was honest.',
     'Whether.',
     'tests/test_inclusive_design.py::TestTheReportSaysWhoItIsAbout::test_what_the_numbers_cannot_tell_you_is_back'),

    ('I1 reduced() stops hearing the switch',
     'interface/ui/src/lib/motion.js',
     'const chosenOff = () => document.documentElement.dataset.motion === "off";',
     'const chosenOff = () => false;',
     'tests/test_inclusive_design.py::TestReduceMotionIsOneMechanism::test_reduced_answers_to_the_system_or_the_switch'),

    ('I1 the switch overrules the system',
     'interface/ui/src/lib/chrome.js',
     '    if (reducedBySystem()) {\n      announce("Motion is reduced by your system setting, so the page keeps it reduced.");\n      return;\n    }\n',
     '',
     'tests/test_inclusive_design.py::TestReduceMotionIsOneMechanism::test_the_masthead_offers_it_and_respects_the_system'),

    ('I1 a document forgets the switch before first paint',
     'interface/ui/run.html',
     'if (localStorage.getItem("brandpulse-motion") === "off") {',
     'if (false) {',
     'tests/test_inclusive_design.py::TestReduceMotionIsOneMechanism::test_every_document_applies_it_before_first_paint[run.html]'),

    ('I1 a renderer stops following the switch',
     'interface/ui/src/lib/ribbonfield.js',
     'window.addEventListener("motionchange", onMotion);',
     '',
     'tests/test_inclusive_design.py::TestReduceMotionIsOneMechanism::test_vendored_renderers_follow_it_live'),

    ('I2 one page hides chapters again',
     'interface/ui/src/lib/codex.js',
     'c.hidden = !all && c !== ch;',
     'c.hidden = c !== ch;',
     'tests/test_inclusive_design.py::TestTheBookReadsAsOnePage::test_one_page_shows_every_chapter'),

    ('R5 printing keeps the dark paper',
     'interface/ui/src/lib/codex.js',
     '    if (printing.theme !== "field") applyTheme("field", { persist: false });\n    wide = isWide();\n    fit();\n    paint();',
     '    wide = isWide();\n    fit();\n    paint();',
     'tests/test_inclusive_design.py::TestTheBookReadsAsOnePage::test_printing_is_the_one_page_reading_on_paper'),

    ('A9 the field edge falls under 3:1',
     'interface/ui/src/styles/tokens.css',
     '  --edge-ctl: #66727A;',
     '  --edge-ctl: #364146;',
     'tests/test_inclusive_design.py::TestInputsCanBeSeen::test_the_field_edge_is_three_to_one_on_every_ground[bench]'),

    ('R3 the phone rule reaches the compact trace',
     'interface/ui/src/styles/transport.css',
     '.tp:not(.tp--compact) { --id-w: 4.5rem; --lane-h: 40px; }',
     '.tp { --id-w: 4.5rem; --lane-h: 40px; }',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_the_phone_trace_rule_spares_the_compact_trace'),

    ('A15 a wrong field is not marked invalid',
     'interface/ui/src/pages/run.js',
     'input.replace("<input ", \'<input aria-invalid="true" \')',
     'input',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_a_field_with_a_problem_says_so_to_assistive_technology'),

    ('A11 marks vanish under forced colours',
     'interface/ui/src/styles/chassis.css',
     '    background-color: CanvasText;',
     '    background-color: transparent;',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_forced_colours_keep_the_marks_that_carry_a_reading'),

    ("A12 the library's state heading is an h2 again",
     'interface/ui/src/pages/library.js',
     '<h1 class="t-l">${esc(heading)}</h1>',
     '<h2 class="t-l">${esc(heading)}</h2>',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_an_error_or_empty_state_is_the_pages_first_heading[pages/library.js]'),

    ('A10 the fallback timer runs on after the bundle',
     'interface/ui/src/lib/chrome.js',
     '  clearTimeout(window.__bpFallback);\n  /* A bundle that arrived',
     '  /* A bundle that arrived',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_the_fallback_timer_stops_when_the_bundle_runs'),

    ('A13 the ledger has no Tab stop',
     'interface/ui/src/pages/report.js',
     'if (stop) stop.tabIndex = 0;',
     '',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_the_ledger_is_one_tab_stop'),

    ("A14 the grid's arrow keys turn the page",
     'interface/ui/src/lib/codex.js',
     '[data-transport], [role=slider], [data-ledger], [role=grid], [role=tablist]',
     '[data-transport], [role=slider], [data-ledger]',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_a_grid_keeps_its_own_arrow_keys'),

    ('A17 an overflowing page is not focusable',
     'interface/ui/src/lib/codex.js',
     '        body.tabIndex = 0;\n',
     '',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_a_page_that_scrolls_can_be_scrolled_from_the_keyboard'),

    ('R7 the small targets lose their hit area',
     'interface/ui/src/styles/chassis.css',
     '.member a, #film .f-bottom a, #film .f-link { display: inline-flex; align-items: center; min-height: 24px; }',
     '.member a, #film .f-bottom a, #film .f-link { display: inline-flex; align-items: center; min-height: 16px; }',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_small_targets_get_a_24px_hit_area'),

    ('R1 the library stops following the window',
     'interface/ui/src/pages/library.js',
     'const fits = window.matchMedia(SHELF_FITS);',
     'const fits = window.matchMedia("(min-width: 0px)");',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_the_library_follows_the_window'),

    ('the scanner is imported into the product',
     'interface/ui/src/lib/format.js',
     '/* format.js — every string this interface prints from a number.',
     'import "axe-core";\n/* format.js — every string this interface prints from a number.',
     'tests/test_inclusive_design.py::TestSmallerGuarantees::test_the_accessibility_scanner_never_ships'),

    # ── Engineering review, 26 Sep 2026 ──────────────────────────────────────
    ('the setup template switches the rejected controller back on',
     '.env.example',
     '# OLLAMA_MODEL=llama3.1:8b',
     'OLLAMA_MODEL=llama3.2',
     'tests/test_setup_contracts.py::test_the_controller_the_example_documents_is_the_adopted_one'),

    ('every site is granted the API again',
     'app.py',
     'STATIC_DIR = Path(__file__).parent / "interface" / "static"\n',
     'STATIC_DIR = Path(__file__).parent / "interface" / "static"\n\n\n@app.after_request\ndef _cors(r):\n'
     '    r.headers["Access-Control-Allow-Origin"] = "*"\n    return r\n',
     'tests/test_ui_routes.py::TestNoOtherSiteIsGrantedTheApi::test_a_cross_origin_read_carries_no_permission'),

    ('the server goes back to its own narrower address rule',
     'app.py',
     '    return downloader.youtube_video_id(url)',
     '    m = re.search(r"(?:v=|youtu\\.be/)([A-Za-z0-9_\\-]{11})", url)\n    return m.group(1) if m else None',
     'tests/test_youtube_addresses.py::TestTheRoutesUseTheRule::test_analyse_accepts_a_shorts_address_and_downloads_the_watch_form'),

    ('a shorts address reaches the downloader as typed',
     'app.py',
     '    video_url: str = downloader.pipeline_url(body["video_url"])',
     '    video_url: str = body["video_url"]',
     'tests/test_youtube_addresses.py::TestTheRoutesUseTheRule::test_analyse_accepts_a_shorts_address_and_downloads_the_watch_form'),

    ('max_comments goes unchecked on /analyse',
     'app.py',
     '    max_comments, problem = _max_comments(body)\n    if problem:\n        return jsonify({"error": problem}), 400\n',
     '    max_comments, problem = int(body.get("max_comments", 100)), None\n',
     'tests/test_request_validation.py::test_a_bad_max_comments_is_a_400_on_every_route[lots-whole number-/analyse]'),

    ('python app.py starts the debugger again',
     'app.py',
     '    app.run(port=5001)',
     '    app.run(debug=True)',
     'tests/test_setup_contracts.py::test_python_app_py_serves_on_5001_without_the_debugger'),

    ('the model installer stops checking hashes',
     'models/install_comment_model.py',
     '        bad = problems(folder, want)\n        if bad:\n            raise InstallError(f"{folder} is not the adopted model: "',
     '        bad = []\n        if bad:\n            raise InstallError(f"{folder} is not the adopted model: "',
     'tests/test_model_install.py::test_a_tampered_file_is_refused_and_nothing_is_installed'),

    ('an archive entry is written under its own path',
     'models/install_comment_model.py',
     '            with z.open(info) as src, open(into / base, "wb") as dst:',
     '            with z.open(info) as src, open(into / info.filename, "wb") as dst:',
     'tests/test_model_install.py::test_an_archive_writes_only_the_expected_names_inside_the_target'),

    # --- the engineering review, 26 Sep 2026: each fix, undone, must be caught ---

    ("a YouTube refusal carries the API key out of the comment fetch",
     "pipeline/comment_module.py",
     "response = youtube_api.execute(youtube.commentThreads().list(**request_kwargs))",
     "response = youtube.commentThreads().list(**request_kwargs).execute()",
     "tests/test_youtube_api.py::TestEveryCallerIsCovered::test_comments_disabled_reaches_the_caller_without_the_key"),

    ("a YouTube refusal carries the API key out of the video search",
     "pipeline/sweep.py",
     "found = youtube_api.execute(youtube.search().list(**search_kwargs))",
     "found = youtube.search().list(**search_kwargs).execute()",
     "tests/test_youtube_api.py::TestEveryCallerIsCovered::test_an_exhausted_quota_on_the_search_reaches_the_caller_without_the_key"),

    ("a finished run no longer names the file its report was saved under",
     "app.py",
     '            response["report_file"] = job.get("report_file")\n',
     "",
     "tests/test_job_process.py::test_a_finished_run_names_the_file_its_report_was_saved_under"),

    ("the run page tells a single run's reader to wait for the stop",
     "interface/ui/src/pages/run.js",
     ': "Stopping ends the run at once. Nothing is written to the outputs "',
     ': "Stopping is checked between stages, so it is not instant. Nothing is written to the outputs "',
     "tests/test_job_process.py::test_the_run_page_says_only_a_five_video_run_stops_at_its_next_checkpoint"),

    ("choosing what to analyse drops keyboard focus",
     "interface/ui/src/pages/run.js",
     "      if (chosen) chosen.focus();\n",
     "",
     "tests/test_inclusive_design.py::TestTheKeyboardCanDoWhatThePointerCan::test_choosing_what_to_analyse_keeps_focus_on_the_choice"),

    ("Show as a list drops keyboard focus",
     "interface/ui/src/pages/library.js",
     "    const hadFocus = root.contains(document.activeElement);",
     "    const hadFocus = false;",
     "tests/test_inclusive_design.py::TestTheKeyboardCanDoWhatThePointerCan::test_the_list_that_replaces_the_shelf_takes_focus_only_from_what_it_replaced"),

    ("the shelf leaves a window listener behind when it is taken down",
     "interface/ui/src/lib/shelf.js",
     '      window.removeEventListener("pointercancel", onCancel);\n',
     "",
     "tests/test_ui_contracts.py::TestWhatIsTakenDownStopsWatching::test_every_global_listener_the_shelf_adds_is_removed_by_name"),

    ("the list's card traces outlive a repaint",
     "interface/ui/src/pages/library.js",
     '  clearTraces("rack");\n',
     "",
     "tests/test_ui_contracts.py::TestWhatIsTakenDownStopsWatching::test_the_library_lets_go_of_what_it_replaces"),

    ("a report is read without the number guard",
     "interface/ui/src/lib/api.js",
     "fetch(`/reports/${encodeURIComponent(filename)}`).then(unwrap).then(asReport);",
     "fetch(`/reports/${encodeURIComponent(filename)}`).then(unwrap);",
     "tests/test_ui_contracts.py::TestUntrustedTextReachesTheDomSafely::test_every_saved_file_a_page_reads_is_held_to_numbers_where_it_should_be"),

    ("a moment's time is printed unescaped",
     "interface/ui/src/lib/written.js",
     '<span class="t-time">${esc(m.time)}</span>',
     '<span class="t-time">${m.time}</span>',
     "tests/test_ui_contracts.py::TestUntrustedTextReachesTheDomSafely::test_a_moments_readings_and_time_are_escaped_in_both_books"),

    ("the source link follows a report's stored address",
     "interface/ui/src/pages/report.js",
     'videoUrl: videoId ? `https://www.youtube.com/watch?v=${videoId}` : "",',
     'videoUrl: report.video_url || "",',
     "tests/test_ui_contracts.py::TestUntrustedTextReachesTheDomSafely::test_a_reports_stored_address_is_read_only_for_its_video_id"),

    ("the opening film prefers a report the repository does not ship",
     "interface/ui/src/pages/opening.js",
     '"Apple (iPhone 18 Pro Max).json",',
     '"Samsung (Ultra 25).json",',
     "tests/test_ui_contracts.py::test_the_opening_film_prefers_reports_the_repository_ships"),

    ("the opening page claims every report names its controller",
     "interface/ui/src/lib/proof.js",
     "A combined\n      report records which one did; a single report does not yet.",
     "Every report\n      says which one did.",
     "tests/test_ui_contracts.py::TestEveryQuotedFigureIsMeasured::test_the_opening_page_says_which_reports_name_their_controller"),

    ("the boot screen prints a down-weight the pipeline does not apply",
     "interface/ui/src/gl/crt.js",
     "down-weighted to 0.342 and reported",
     "down-weighted to 0.300 and reported",
     "tests/test_ui_contracts.py::TestTheContractMirrorsThePipeline::test_the_down_weights_the_pages_print_are_the_orchestrators"),

    ("the dry run crashes on a report that is not there",
     "write_analysis.py",
     '        if not report_path.is_file():\n            print(f"missing: {report_path}")\n            failures += 1\n            continue\n        report = json.loads(report_path.read_text(encoding="utf-8"))\n        sizer = Sizer()',
     '        report = json.loads(report_path.read_text(encoding="utf-8"))\n        sizer = Sizer()',
     "tests/test_analyst_sweep.py::TestTheCommandLine::test_the_dry_run_names_a_missing_report_and_fails_instead_of_raising"),

    ("the command line prints a traceback when YouTube refuses",
     "main.py",
     "    except (ValueError, YouTubeAPIError) as exc:",
     "    except ValueError as exc:",
     "tests/test_cli.py::test_youtube_refusing_the_comments_is_one_error_line_not_a_traceback"),

]

# Mutations against the BUILT output, which must be rebuilt to take effect.
BUILD_MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("a font host appears in a document",
     "interface/static/index.html",
     "<head>",
     '<head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">',
     "tests/test_ui_documents.py::TestNothingLeavesThisMachine::test_no_built_file_names_a_foreign_host"),

    ("the favicon becomes a request",
     "interface/static/index.html",
     '<link rel="icon" href="data:image/svg+xml',
     '<link rel="icon" href="/favicon.ico"><link rel="unused" href="data:image/svg+xml',
     "tests/test_ui_documents.py::TestNothingLeavesThisMachine::test_the_favicon_is_inline_rather_than_a_request"),

    ("the skip link stops being first",
     "interface/static/report.html",
     '<a class="skip-link" href="#main">Skip to the report</a>',
     '<button>Something else</button><a class="skip-link" href="#main">Skip</a>',
     "tests/test_ui_documents.py::TestTheDocumentsAreWellFormed::test_each_offers_a_skip_link_as_the_first_focusable_thing"),

    ("a document loses its language",
     "interface/static/run.html",
     '<html lang="en"',
     "<html",
     "tests/test_ui_documents.py::TestTheDocumentsAreWellFormed::test_each_declares_a_language"),
]


def run(node_id: str) -> str:
    """
    "passed", "failed", or "error".

    Only pytest's exit code 1 means a test ran and failed. Until 25 Sep 2026 any
    non-zero code counted, so exit 4 -- pytest could not find the test id at all
    -- was scored as CAUGHT: a mutation "caught" by a test that never ran. The
    same trap was found once before (19-20 Sep) and had come back.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", node_id, "-q", "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    # 4: pytest could not find the test id; 5: it collected nothing.
    return {0: "passed", 1: "failed", 4: "missing", 5: "missing"}.get(result.returncode, "error")


def bite(name: str, relative: str, find: str, replace: str, node_id: str) -> dict:
    path = ROOT / relative
    if not path.exists():
        return {"mutation": name, "status": "SKIPPED", "reason": f"{relative} no longer exists"}
    original = path.read_text(encoding="utf-8")
    if find not in original:
        return {"mutation": name, "status": "SKIPPED",
                "reason": f"anchor not found in {relative}"}
    # The guard must pass on the unbroken file first. A test that already fails
    # would "catch" every mutation thrown at it, and the suite carries known
    # failures, so without this a red test could be reported as a working guard.
    before = run(node_id)
    if before == "missing":
        return {"mutation": name, "file": relative, "test": node_id.split("::")[-1],
                "status": "SKIPPED", "reason": "the guarding test no longer exists"}
    if before != "passed":
        return {"mutation": name, "file": relative, "test": node_id.split("::")[-1],
                "status": "UNGUARDED",
                "reason": f"the guarding test is {before} before anything is broken"}
    try:
        path.write_text(original.replace(find, replace, 1), encoding="utf-8")
        outcome = run(node_id)
    finally:
        path.write_text(original, encoding="utf-8")
        assert path.read_text(encoding="utf-8") == original, f"failed to restore {relative}"
    status = {"failed": "CAUGHT", "passed": "MISSED", "error": "ERROR", "missing": "ERROR"}[outcome]
    return {"mutation": name, "file": relative, "test": node_id.split("::")[-1],
            "status": status}


def main() -> int:
    print(f"Breaking {len(MUTATIONS) + len(BUILD_MUTATIONS)} guarded things, "
          f"one at a time.\n")

    results = []
    for mutation in MUTATIONS + BUILD_MUTATIONS:
        outcome = bite(*mutation)
        results.append(outcome)
        mark = {"CAUGHT": "caught   ", "MISSED": "MISSED   ", "SKIPPED": "skipped  ",
                "ERROR": "ERROR    ", "UNGUARDED": "UNGUARDED"}[outcome["status"]]
        print(f"  {mark} {outcome['mutation']}")
        if outcome.get("reason"):
            print(f"            {outcome['reason']}")

    by = {s: [r for r in results if r["status"] == s]
          for s in ("CAUGHT", "MISSED", "SKIPPED", "ERROR", "UNGUARDED")}

    OUT.write_text(json.dumps({
        "generated_by": "ui_evidence/verify_tests_bite.py",
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results), "caught": len(by["CAUGHT"]),
        "missed": len(by["MISSED"]), "skipped": len(by["SKIPPED"]),
        "errors": len(by["ERROR"]), "unguarded": len(by["UNGUARDED"]),
        "results": results,
    }, indent=2) + "\n", encoding="utf-8")

    print(f"\n{len(by['CAUGHT'])} of {len(results)} mutations caught by the test that guards them")
    for status, words in (("SKIPPED", "skipped (the code they target has moved or gone)"),
                          ("ERROR", "errored (pytest could not run the guarding test)"),
                          ("UNGUARDED", "unguarded (the guarding test fails before any mutation)")):
        if by[status]:
            print(f"{len(by[status])} {words}")
    bad = by["MISSED"] + by["ERROR"] + by["UNGUARDED"]
    if bad:
        print(f"\n{len(bad)} guards that do not bite:")
        for r in bad:
            print(f"  - {r['status']}: {r['mutation']}  ({r.get('test', '')})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
