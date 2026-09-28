> **Status, 25 Sep 2026:** every P0 and P1 item and all four features are built, tested and
> measured. The complete browser run records **0 failures** (`ui_evidence/ui_measurements.json`)
> against **92** before (`ui_evidence/ui_measurements.before.json`). Results item by item in §7,
> the WCAG 2.2 record in §8, trade-offs in §9. Not yet run: the VoiceOver, keyboard and phone
> script (`ui_evidence/SCREENREADER_SCRIPT.md`).

# Inclusive design, accessibility, responsiveness and testing

This document records the inclusive-design review completed on 25 September 2026. It preserves
the scope, methods, measured results and remaining limitations of that work.

---

## 1. Context

**Objective.** Improve inclusive design, accessibility and responsive behaviour without removing
the interface's defining visual experiences, and evaluate the result with recognised accessibility
and software-testing methods.

**Standards and methods.** The review combined inclusive-design principles, WCAG 2.2 AA,
informed-consent requirements and layered software testing.

| Source | Application | Section |
|---|---|---|
| Microsoft Inclusive Design (2016) | Persona spectrum across permanent, temporary and situational needs | §2, §3 |
| WCAG 2.2 (W3C, 2023) | Level A and AA criteria across pages, themes and viewports | §5, §8 |
| Software testing practice | Unit, integration, system and acceptance checks; verification and validation; explicit exit criteria | §5 |
| Research ethics | Informed consent, data minimisation and protection of participant records | §1, §9 |

**Starting point.** The 12 September build contained B1–B11 (no-script core, run-page voice, reflow,
label-in-name, skip link, text spacing, plain-language glosses, English-only notice, statement to
the scored person, governance docs, fairness bench Q1); `ui_evidence/verify_ui.py` (14 checks);
`verify_tests_bite.py` (mutations); `INCLUSION_ANALYSIS.md`; `SCREENREADER_SCRIPT.md` (not run);
pytest UI contracts (`test_ui_contracts.py` 125, `test_ui_documents.py` 32, `test_ui_routes.py` 40).
Evaluation evidence comprised the August pilot (n=3, screenshots) and the 24 September final
evaluation (n=5, screenshots;
4 laptop / **1 phone with low vision**; **D4: 4 of 5 found text too small or faint; D5: 3 of 5
wanted a motion-off switch**). The motion request had not previously been implemented or formally
declined.

**Reason for the review.** The existing evidence predated the gate, boot, film, shelf, book,
combined reports and the 24 September cohesion pass. The source audit on 25 September found that:
- the harness **cannot run** (reads `outputs/*.json`, now empty), seeds theme names that no longer
  exist (`ink/plate` vs `bench/field` → "both themes" measured one theme twice), never dismisses
  the boot screen, and several checks pass vacuously (text spacing measured 0 elements);
- `verify_tests_bite.py` scores any non-zero pytest exit as CAUGHT (incl. exit 4, unknown test id)
  and targets 9 classes and 4 files that no longer exist;
- **two B-features are gone** (library bias caveat with JS on — a hard constraint of the project; the
  statement to the person in the video) and several have regressed (list below);

**Scope decisions.** No new participants were recruited, so the two completed studies were reused
and their coverage limits were recorded. axe-core was added only as a development dependency. A
VoiceOver, keyboard and phone script was prepared for manual developer testing. The book remained
the default reading experience, with "Read as one page" added as an optional view.

**Constraints.** The gate, CRT boot, film, shelf, book and proof count-up were retained, while each
was made skippable, operable and supported by an accessible alternative. Renaming Authenticity,
removing the face channel, replacing the book with scrolling, adding a yes/no verdict and changing
the Brand Health formula were outside this review's scope. The backend, scoring and stored data
remained unchanged. Tests intercepted DELETE requests so that no saved report could be removed.

---

## 2. The three paradigms, applied here

| Paradigm | What it means for BrandPulse | Outcome |
|---|---|---|
| **Inclusive design** | Every core task works across the persona spectrum (§3); one change can serve several needs through the motion switch, one-page view and list view. | Implemented |
| **Born-accessible** | Accessibility acts as a **gate in the build workflow**: axe and custom checks cover every page, theme and viewport; pytest contracts protect each fix; mutations demonstrate that the checks detect regressions. | Implemented |
| **Radical inclusion** | The scored creator and comment authors were not consulted, and no disabled user participated in co-design. The statement to the person in the video was restored, an accessibility statement with known exceptions was published, and the governance required for deployment was documented. These measures do not constitute radical inclusion. | Partially addressed; not achieved |

---

## 3. Persona spectrum (Microsoft 2016)

| Ability | Permanent | Temporary | Situational | The interface must… |
|---|---|---|---|---|
| **Touch** | one arm, motor impairment, switch user | broken wrist, RSI | phone in one hand, trackpad on a train | do every action by keyboard; need no drag/hover/precision; targets ≥ 24 px |
| **See** | blind (screen reader), low vision (200–400% zoom), colour-vision deficiency | cataract, migraine | sunlight, projector, split screen | expose structure and names; text for every chart; 4.5:1 text / 3:1 non-text in both themes; never colour alone; reflow at 320; survive forced colours |
| **Hear** | deaf | ear infection | open office | carry no information by sound (the product is silent — 1.2.x N/A, stated) |
| **Speak** | voice-control user | laryngitis | accent under voice control | name every control starting with its visible words (2.5.3); never require speech |
| **Cognition** (added) | dyslexia, ADHD, low domain literacy | tiredness, stress | a rushed manager, second language | plain-language glosses; motion can be stopped; a linear one-page reading; errors say how to fix |

---

## 4. Defects and fixes

Priority: **P0** = hard constraint, or a persona is blocked from a core task; **P1** = WCAG 2.2 AA
failure with a workaround, or a user-study pattern; **P2** = polish, deferred before higher-priority
work. Every item was re-measured in Phase 0; any item that did not reproduce would have been
withdrawn and logged.

### 4.A Accessibility (WCAG 2.2 AA)

| # | Pri | Defect (evidence) | Implemented change |
|---|---|---|---|
| A1 | P0 | **Library bias caveat gone with JS on** (hard constraint). Scores at `library.js:264-272, 936-942`; `hasCaveat` computed, unused (`:111`) | Caveat band on both shelf and list views, from the served `_caveat_block` text; pytest + verify check |
| A2 | P0 | **Keyboard cannot take a volume down or delete**: pick is `pointerdown` on an `aria-hidden` canvas (`shelf.js:1566`); delete only on the desk (`library.js:722`); list view has no delete | `.bk__index` entries become buttons that open the desk (same code path as a pick); list cards get Delete with the same two-step confirm |
| A3 | P0 | **Space hijacked at window level** while a volume is out (`shelf.js:1577-1580`) — desk buttons can't be pressed with Space | Handle Space only when focus is on the body/stage, never on a control |
| A4 | P0 | **Invisible but focusable menu below 900 px** (`chassis.css:585-607`: opacity + pointer-events only) — every page, incl. 200% zoom on a laptop | Closed panel `visibility:hidden` (delayed for the fade) / `inert`; `aria-expanded` on the toggle |
| A5 | P0 | **Film hides beats 2–4 from assistive tech unless scrolled** (`film.js:158-164, 171-173`) — incl. the facial-accuracy disclosure and "Open this analysis" | All beats readable in order by AT; focus entering a non-current beat scrolls the pin to it; unpinned stacked beats where R2 applies |
| A6 | P1 | **Boot: unfocused modal, any key (incl. modifier keys a screen reader uses) dismisses it, auto-leaves 1.6 s after typing** (`boot.js:41-43, 101, 116-120`) | Focus a real "Continue" button described by the log; ignore modifier-only keys; every log fact (model list) also on the landing so nothing is lost when it leaves |
| A7 | P1 | **Removed**: statement to the person in the video (B9) and "what these numbers cannot tell you" (B7), despite both being documented product requirements | Restore both in the book (limits page + a one-line pointer by the face plate), within the one-screen layout |
| A8 | P1 | **Endless decorative motion, no in-page pause** (2.2.2): hero `hero.css:50,54`, film/seam/proof backgrounds, run optics `run-scene.css:429-446`; **D5: 3 of 5 asked for a motion switch** | **Motion switch** (§4.I, I1) |
| A9 | P1 | **Input/control borders 1.16–2.30:1** (1.4.11) (`run.css:92-101`, `chassis.css:468, 904`) | New `--edge-ctl` token ≥ 3:1 in both themes for inputs and control outlines |
| A10 | P1 | **Fallback timer cleared only after all fetches**; on the shelf path the "needs JavaScript" text + second h1 can stay on screen (`library.js:642, 654`) | Clear `__bpFallback` when the module starts (as B1 did) and remove the fallback node on mount |
| A11 | P1 | No forced-colours handling anywhere; background-drawn bars vanish | `@media (forced-colors: active)` for bars/marks (borders or `forced-color-adjust`), `Highlight` focus rings |
| A12 | P1 | Heading gaps: error/empty states only `h2` (`report.js:90`, `sweep.js:80`, `library.js:65`, `opening.js:155`, `run.js:1182`); wide book has no h1 after spread 1 (`codex.js:300`) | h1 in every state; persistent visually-hidden h1 (report title) in the book bar |
| A13 | P1 | Segment-table rows never Tab-reachable (`report.js:863`) | Roving tabindex (first row 0) |
| A14 | P1 | Theme-matrix edge keys turn the page (`sweep.js:832`, `codex.js:746`) | preventDefault at edges; codex ignores keys from `[role=grid]` |
| A15 | P2 | No `aria-invalid` on the run form (`run.js:1052`) | Set/clear with the error |
| A16 | P2 | Duplicate "Playhead" slider names (`transport.js:251`); compare strip speaks twice (`library.js:367`+`496`); proof tabpanel is a live region re-reading the chart (`proof.js:404`) | Name = "Playhead, <title>"; one announcer; short announcement instead of live panel |
| A17 | P2 | `.cx__body` scroll region not focusable (Safari keyboard scroll) | `tabindex=0` + `role=region` + label only when it overflows |
| A18 | P2 | Source link opens a new tab silently (`report.js:175`) | "(opens in a new tab)" in its name |

### 4.R Responsive / screen size

| # | Pri | Defect (evidence) | Implemented change |
|---|---|---|---|
| R1 | P0 | **Library goes blank** when a loaded shelf is narrowed/zoomed below 900 or an iPad is rotated (`library.js:131, 522`; `shelf.css:406`) | `matchMedia` listener swaps shelf ⇄ list, reusing the reduced-motion swap (`library.js:1117-1133`); shelf also needs height ≥ 600 (R16) |
| R2 | P1 | **Film pins on every screen** (`film.js:201-205`); at 844×390 readings + "Skip sequence" are out of view for 4.8 screens | Pin only when the viewport is tall enough (as `proof.js:933`, `seam.js:340` already do); else stacked; skip link sticky |
| R3 | P1 | Transport compact rule overridden ≤ 860 (`transport.css:203` vs `:222`) → wrong lanes, marks offset 72 px | Scope the phone rule `:not(.tp--compact)`; contract test |
| R4 | P1 | Run page phone rules dead (`run-scene.css:647` over `run.css:498`; `:71-76` over `:492`) → two 136 px columns at 320 | Move overrides after the scene rules; one column ≤ 720 |
| R5 | P1 | **Books do not print**: only the visible chapter prints; dark paper prints pale-on-white (`codex.js:307`, `leaf.css:32`); film/seam lack proof's `beforeprint` un-pin | Print = the one-page view's layout on light paper; `beforeprint`/`afterprint` on film + seam |
| R6 | P1 | Compare strip unbounded, fixed at bottom (`library.css:165-183`) | `max-height: 50svh; overflow:auto`; safe-area padding |
| R7 | P1 | Targets < 24 px (2.5.8): `.sgx__dot` 14, `.vt__sort` ~14, film skip/`.f-link` 17–25 | ≥ 24 px hit area without changing the drawn size |
| R8 | P1 | Chart text 3–7 px on phones (`setcharts.js:108,180`, `charts.js:65,110`) | Phone rules: fewer, larger labels (as `analysis.css:308`); text/table equivalent stays |
| R9 | P1 | Information only in `title=` tooltips (`combined.js:294,298`, `written.js:139,142,367`) | Words in the page (legend / visually-hidden text) |
| R10 | P1 | Reader text below the project's own 12.5 px floor (hero 6–10, close 8, run-scene 8–9, combined 8.5–9.5, sweep 9.5); boot CRT ~6.9 px at 320 — **D4: 4 of 5** | Reader-needed text ≥ `--t-note`; decoration marked `aria-hidden`; CRT font floored; rem where text must follow the browser font setting |
| R11 | P2 | No `env(safe-area-inset-*)` despite `viewport-fit=cover` | Pad the four fixed elements |
| R12 | P2 | Opening masthead misaligned > 2100 px (`chassis.css:319` vs `636`) | Constrain the inner row to the page frame |
| R13 | P2 | Breakpoint edge overlaps at exactly 760/860/1100 (mixed 899/900) | Normalise to the five real breakpoints; map in the `tokens.css` header |

Checked and not changed: CRT flicker is 8 rad/s ≈ **1.27 Hz at ±2.8%** luminance (`gl/crt.js:213`),
under WCAG 2.3.1's 3/s and 10% thresholds; gate ripples, run pulses (0.36 / 0.56 Hz) likewise.

### 4.I Inclusive features (one solution, many personas)

| # | Pri | Feature | Serves | How (reuse) |
|---|---|---|---|---|
| I1 | P1 | **Motion switch** "Motion on / off" beside the theme buttons | vestibular, migraine, ADHD, slow laptop, D5 (3 of 5), 2.2.2 | One mechanism: `motion.js` `reduced()` also reads `html[data-motion="off"]` and fires its existing change listeners; a small PostCSS rule in `vite.config.js` (no new dependency — Vite bundles PostCSS) emits every `@media (prefers-reduced-motion: reduce)` block a second time under `:root[data-motion="off"]`; pre-paint inline script like the theme; stored per viewer (try/catch). Default follows the OS. The proof count-up stays on when motion is on. |
| I2 | P1 | **"Read as one page"** | screen reader, 400% zoom, print, cognition, slow machines | `wireCodex(host, { linear: true })` via `?read=page`: every chapter shown, the existing < 1100 px single-column layout at any width, contents become in-page anchors, no turns; same DOM, so no second copy of the report. Linked from the book bar; also the print layout (R5). |
| I3 | P1 | **"Show as a list"** toggle on the shelf | screen reader, keyboard, low-power GPU, anyone who prefers lists | Exposes the existing list view to everyone; remembered per viewer |
| I4 | P2 | **Accessibility statement** page (`/accessibility`, static, footer link) | everyone; the radical-inclusion gap made visible | WCAG 2.2 AA status, how it was tested, known exceptions, the statement to the person in the video |

---

## 5. Test plan

### 5.1 Objectives and outcomes
- **O1 Verification.** Every page, both themes, every viewport meets WCAG 2.2 AA, or each exception is named with a reason.
- **O2 Verification.** No sideways scroll or lost text from 320 to 3440 px, at 200% zoom, or under the 1.4.12 spacing override.
- **O3 Validation.** Each §3 persona can: open a report, read both scores and what they are not, find the bias caveat, start and follow a run, compare two sets.
- **O4 Reliability.** Every fix is pinned by a test **shown to fail** when the fix is reverted.

### 5.2 Levels

| L4 level | Covers | Box | How | V&V |
|---|---|---|---|---|
| **Unit** | Source contracts for every fix (caveat in library, menu hidden when closed, Space scoped, motion attr read by `reduced()`, CSS rule order R3/R4, no `title=`-only info, targets ≥ 24 px in CSS, forced-colors block present, axe never shipped in `static/`) | White | pytest `tests/test_ui_contracts.py`, `test_ui_documents.py` | Verification |
| **Integration** | Flask serves each document with caveats substituted; `/accessibility` served; no-script core readable | Grey | pytest `test_ui_routes.py` + harness check 9 | Verification |
| **System** | Real Chrome (GPU) over the matrix: axe-core WCAG 2.2 AA; keyboard journeys; focus visible + not obscured; reflow; text spacing; target size; reduced motion + motion switch; forced colours; simulated protanopia/deuteranopia/tritanopia/achromatopsia/blur/low contrast (CDP); print; one-page parity; foreign requests; console; frame rate | Black | `ui_evidence/verify_ui.py` (repaired + extended) | Verification |
| **Acceptance** | Persona tasks: (a) the two completed studies re-read against §3 (D4, D5, P5 counted, never quoted); (b) a manual VoiceOver run of the revised script; (c) a keyboard-only and phone walkthrough. These are developer checks, not user findings. | Black | `ui_evidence/SCREENREADER_SCRIPT.md` (rewritten, parts added) | Validation |
| **Non-functional** | Performance (frame rate with the new features), security (foreign requests, escaping), usability (the studies) | Black | existing checks | Both |

### 5.3 Matrix
Pages: landing (gate + boot, then page), Library shelf, Library list, combined book (brand and
product), member book, one-page view, run page (idle, 4 stages, 4 endings via stubbed job states),
error/empty states. Viewports: 320×568, 360×800, 390×844, 844×390, 768×1024, 1024×768, 1280×800,
1440×900, 1512×982, 1920×1080, 2560×1440, 3440×1440; 1280 at 200% and 400%. Preferences: both
themes; reduced motion; motion switch off; forced colours; contrast more; six vision emulations; print.

### 5.4 Metrics
Defects found / fixed / deferred by priority and **by technique** (axe, custom check, source
reading, study) = defect detection by technique; axe violations before → after by impact; WCAG
coverage — of **55 A/AA criteria**, how many tested automatically / manually / N/A / untested;
mutation score; pytest counts before this review (1,953 passed / 38 failed / 9 skipped).

### 5.5 Exit criteria
1. 0 axe critical/serious on every page × theme at 1440 and 390.
2. 0 sideways scroll, 0 lost text across the viewport matrix.
3. Every §4 fix has a unit contract test and a caught mutation.
4. pytest: no new failures against 1,953 / 38.
5. Every AA criterion has a status; each open failure is documented as a named exception.
6. The manual VoiceOver script is completed, or its outstanding status is reported.

---

## 6. Verification (end to end)
```bash
cd interface/ui && npm run build && cd ../..        # interface/static/ rebuilt
python -m flask --app app run --port 5057 &         # a second server, beside the one in use
python evaluation/ui_evidence/verify_ui.py                     # the real-browser checks -> ui_measurements.json
python evaluation/ui_evidence/verify_tests_bite.py             # every new contract caught when its fix is reverted
python -m pytest
```
The remaining manual step uses VoiceOver with `ui_evidence/SCREENREADER_SCRIPT.md` and records
what is announced.

---

## 7. Results, item by item (25 Sep 2026)

Every item re-measured in Phase 0 reproduced; none was withdrawn. "Guarded by"
names the contract test in `tests/test_inclusive_design.py` (each one shown to
fail by a mutation in `ui_evidence/verify_tests_bite.py`) and the browser check in
`ui_evidence/verify_ui.py` that measures it.

| # | Status | Before → after (measured) | Guarded by |
|---|---|---|---|
| A1 | Fixed | Library caveat with scripting on: absent (shelf and list) → present in both | `TestTheLibraryStatesTheBiasCaveat`; check 24 |
| A2 | Fixed | Delete reachable by keyboard: no, in 80 Tab stops → yes, 15 stops (shelf) and 4 (list) | `TestTheKeyboardCanDoWhatThePointerCan`; check 24 |
| A3 | Fixed | Space on the desk's buttons: turned the volume → confirms Delete | same; check 24 |
| A4 | Fixed | Controls focusable while invisible at 390px: 6 per page → 0 on all 7 pages | `TestTheClosedMenuIsHidden`; check 3 |
| A5 | Fixed | Film parts in the accessibility tree: 1 of 4, no link, no disclosure → 4 of 4, both | `TestTheFilmIsReadableAndFits`; check 24 |
| A6 | Fixed | Boot: focus inside the dialog no → yes; no timer for a keyboard reader | `TestTheBootScreenCanBeRead`; check 24 |
| A7 | Fixed | Books with the statement to the person in the video: 0 of 27 → 27 of 27 | `TestTheReportSaysWhoItIsAbout`; check 7 |
| A8/I1 | Built | Endless animations / GPU draws per second with Reduce motion on: landing 8 / 60, run 5 / 0, Library 0 / 5,400 (motion on) → 0 / 0 on all 7 pages | `TestReduceMotionIsOneMechanism`; checks 6, 22 |
| A9 | Fixed | Run-field edge: 1.57–2.30:1 → 3.22–4.02:1 on every ground (computed) | `TestInputsCanBeSeen` |
| A10 | Fixed | Fallback timer cleared when the bundle runs, not after every read | `test_the_fallback_timer_stops_when_the_bundle_runs` |
| A11 | Built | Forced colours: focus rings lost 0 → 0; meaning-carrying marks now drawn in CanvasText; background-only marks on the opening page 41 → 34, all decorative | `test_forced_colours_keep_the_marks…`; check 17 |
| A12 | Fixed | Error and empty states lead with h1 | `test_an_error_or_empty_state_is_the_pages_first_heading` |
| A13 | Fixed | Ledger rows: no Tab stop → one roving stop | `test_the_ledger_is_one_tab_stop` |
| A14 | Fixed | Arrow keys in the theme grid no longer turn the page | `test_a_grid_keeps_its_own_arrow_keys` |
| A15 | Fixed | Invalid run fields carry `aria-invalid` | `test_a_field_with_a_problem…` |
| A16 | Fixed | Timelines named per run; compare strip and proof panel no longer speak twice | `TestEveryControlCanBeSpoken` (updated) |
| A17 | Fixed | axe `scrollable-region-focusable` (serious): 2 nodes → 0 | `test_a_page_that_scrolls…`; check 15 |
| A18 | Fixed | The source link says it opens a new tab | — (text) |
| R1 | Fixed | Library narrowed to 800px after loading: 0 characters, no list → the list, 6 sets; 1024x430 → list | `test_the_library_follows_the_window`; check 20 |
| R2 | Fixed | Film pinned only where it fits; stacked below | `test_the_film_pins_only_where_it_fits`; check 11 |
| R3 | Fixed | Compact trace no longer takes the phone lanes | `test_the_phone_trace_rule_spares_the_compact_trace` |
| R4 | Fixed | Run page at 320: 6 text elements off the side → 0; reflow across all 182 combinations → 0 problems | check 11 |
| R5 | Fixed | Printed report: only the spread on the desk, lowest 1.19:1 on paper → 99–100% of the book's text, lowest 5.98:1 | `test_printing_is_the_one_page_reading_on_paper`; check 21 |
| R6 | Fixed | Compare strip at most half the window | — (CSS) |
| R7 | Fixed | Targets under 24px: 3 (at 390) → 0 on all pages at both widths | `test_small_targets_get_a_24px_hit_area`; check 16 |
| R8 | Fixed | Chart labels drawn under 10px: up to 7 per page → 0 on every page at 390 and 1440 | check 19 |
| R9 | Fixed | The near-tie mark has words for screen readers; the visible key already existed | — |
| R10 | Fixed | Reader-facing styles under 11.5px: up to 28 per page (smallest 7–8px) → 0 on every page at 390 and 1440 | check 19 |
| R11 | Built | Safe-area padding on the fixed bars | — (CSS) |
| R12 | Fixed | Opening masthead held to the 2100px frame | — (CSS) |
| R13 | Cut | Breakpoint normalisation (P2); the edge overlaps are recorded, not fixed | — |
| I2 | Built | `?read=page` shows every chapter: no → yes on all three books | `TestTheBookReadsAsOnePage`; check 23 |
| I3 | Built | Show as a list / Show as a shelf, remembered per browser | check 20 |
| I4 | Built | `/accessibility`, in the menu of every page, complete without JavaScript (3,328 characters) | `TestTheAccessibilityStatement`; checks 9, 15 |
| 1.4.12 film | Fixed (found late) | Under the text-spacing override three film beats ran 30–140 px past the chamber at 1280x800 and 1440x900 (measured once the beats were no longer hidden from the check) → the film restacks when its words stop fitting; 0 lost on 5,962 elements | `test_words_that_do_not_fit_stack_the_film`; check 14 |

---

## 8. WCAG 2.2 A and AA — the conformance record (25 Sep 2026)

All 55 success criteria at levels A and AA. **Method**: V = automated in a real
browser (`verify_ui.py` check number, e.g. V15 is the axe-core scan), U =
unit/source contract (`tests/test_inclusive_design.py` and the older UI
contracts), C = computed (arithmetic from the source), M = manual and still
pending through `SCREENREADER_SCRIPT.md`, — = not applicable, with the reason.
**Status** is limited to the available evidence: *Pass* means every recorded measurement
passes; it is not a certification.

| SC | Level | Name | Status | Method | Evidence / reason |
|---|---|---|---|---|---|
| 1.1.1 | A | Non-text content | Pass | V15, U | axe `image-alt`, `svg-img-alt`, `role-img-alt`; charts are `role="img"` with a data summary; decoration `aria-hidden` |
| 1.2.1 | A | Audio-only and video-only | N/A | — | The interface plays no audio or video; it shows still frames |
| 1.2.2 | A | Captions (prerecorded) | N/A | — | No media playback |
| 1.2.3 | A | Audio description or media alternative | N/A | — | No media playback |
| 1.2.4 | AA | Captions (live) | N/A | — | No live media |
| 1.2.5 | AA | Audio description (prerecorded) | N/A | — | No media playback |
| 1.3.1 | A | Info and relationships | Pass | V15, V24, U | Landmarks, one h1 per state (A12), table captions and `th scope`, film beats in the tree (A5) |
| 1.3.2 | A | Meaningful sequence | Pass | V24, M | Film read in order (check 24); one-page reading gives the book's order |
| 1.3.3 | A | Sensory characteristics | Pass | U | Instructions name controls by their words, not by shape or place |
| 1.3.4 | AA | Orientation | Pass | V11 | 844x390 and 390x844 both reflow; nothing locks orientation |
| 1.3.5 | AA | Identify input purpose | N/A | — | No field collects personal data (URL, brand, product, subject) |
| 1.4.1 | A | Use of colour | Pass (sim.) | V18, U | Channels carry shape as well as colour; screenshots under six simulated conditions; not validated with a CVD user |
| 1.4.2 | A | Audio control | N/A | — | No audio |
| 1.4.3 | AA | Contrast (minimum) | Pass | V2, V15 | 179 pairs per theme on every spread, 0 below AA, lowest 4.53 (dark) / 4.62 (light) |
| 1.4.4 | AA | Resize text | Pass | V11 | 640x400 (1280 at 200%) and 320 (400%): no loss |
| 1.4.5 | AA | Images of text | Pass | U | No text is rendered as an image; the boot log's canvas has the same text in the DOM |
| 1.4.10 | AA | Reflow | Pass | V11, V20 | 13 viewports x 7 pages x 2 motion states; shelf gives way to the list below 900x600 |
| 1.4.11 | AA | Non-text contrast | Pass | C, U | Input edge 3.22-4.02:1 on every ground (A9, computed in the test); control borders with text rely on the text |
| 1.4.12 | AA | Text spacing | Pass | V14 | Override applied on every spread; 0 elements newly clipped |
| 1.4.13 | AA | Content on hover or focus | Pass | U | No custom hover/focus popups; `title`-only information removed (R9) |
| 2.1.1 | A | Keyboard | Pass | V3, V24, U | Take down, desk, Delete by keyboard (A2); ledger one Tab stop (A13); scroll regions focusable (A17) |
| 2.1.2 | A | No keyboard trap | Pass | V24, U | Gate and boot trap focus deliberately with Escape/Enter/Continue exits |
| 2.1.4 | A | Character key shortcuts | N/A | — | No single-character shortcuts (arrows and Space only on focused controls) |
| 2.2.1 | A | Timing adjustable | Pass | U | Boot screen waits for a keyboard reader (A6); gate content is not lost |
| 2.2.2 | A | Pause, stop, hide | Pass | V6, V22 | Reduce motion switch stops every loop: 0 infinite animations, 0 GPU draws/s on every page |
| 2.3.1 | A | Three flashes or below | Pass | C | CRT flicker 1.27 Hz at 2.8%; ripples 0.5-1.9 s; pulses 0.36/0.56 Hz |
| 2.4.1 | A | Bypass blocks | Pass | V13 | Skip link first and visible on all 7 pages |
| 2.4.2 | A | Page titled | Pass | U | Every document and state sets a title |
| 2.4.3 | A | Focus order | Pass | V3, V24 | Focus follows the desk and returns to its entry; boot focus inside |
| 2.4.4 | A | Link purpose (in context) | Pass | V15 | axe `link-name`; new-tab link says so (A18) |
| 2.4.5 | AA | Multiple ways | Pass | U | Masthead nav, Library index, chapter contents, one-page view |
| 2.4.6 | AA | Headings and labels | Pass | V15, U | Named timelines per run (A16); state headings |
| 2.4.7 | AA | Focus visible | Pass | V3, V17 | 0 stops without a ring; 0 controls focusable while invisible (A4) |
| 2.4.11 | AA | Focus not obscured (minimum) | Pass | V3 | 0 focused elements covered by a fixed bar at 1440 and 390 |
| 2.5.1 | A | Pointer gestures | Pass | U | Drag to turn a volume has click and button alternatives |
| 2.5.2 | A | Pointer cancellation | Pass | U | Actions fire on click (up-event); the shelf's pick is a pointerdown with nothing destructive on it |
| 2.5.3 | A | Label in name | Pass | V12 | Every overridden name leads with its visible words, both themes |
| 2.5.4 | A | Motion actuation | N/A | — | Nothing responds to device motion |
| 2.5.7 | AA | Dragging movements | Pass | U | Every drag has a single-pointer alternative |
| 2.5.8 | AA | Target size (minimum) | Pass | V16 | 0 targets under 24px without spacing, 1440 and 390 |
| 3.1.1 | A | Language of page | Pass | U | `lang="en"` on every document |
| 3.1.2 | AA | Language of parts | Pass (limited) | U | All content is English; the product states it reads English only |
| 3.2.1 | A | On focus | Pass | M | Focus never changes context; film focus scrolls within the page |
| 3.2.2 | A | On input | Pass | U | Filters, sort and toggles change the view, not the page |
| 3.2.3 | AA | Consistent navigation | Pass | U | One masthead mounted by chrome.js on every page |
| 3.2.4 | AA | Consistent identification | Pass | U | Same names for the same controls throughout |
| 3.2.6 | A | Consistent help | Pass | U | Accessibility statement in the same place on every page (I4) |
| 3.3.1 | A | Error identification | Pass | V10, U | Text error at the field, `aria-invalid` (A15), announced |
| 3.3.2 | A | Labels or instructions | Pass | U | Every field labelled with a hint by `aria-describedby` |
| 3.3.3 | AA | Error suggestion | Pass | U | Each error says how to fix it |
| 3.3.4 | AA | Error prevention (data) | Pass | U | Deleting is two steps and says it cannot be undone |
| 3.3.7 | A | Redundant entry | N/A | — | No multi-step form asks for the same thing twice |
| 3.3.8 | AA | Accessible authentication | N/A | — | No sign-in |
| 4.1.2 | A | Name, role, value | Pass | V15, V10 | axe `aria-*` rules 0 violations; progress bar value text |
| 4.1.3 | AA | Status messages | Pass | V10, U | Live regions for runs, filters, desk, deletes; no double announcements (A16) |

**Count**: 55 criteria — 44 pass on the evidence here, 11 not applicable (7 media or
device, 1.3.5, 2.1.4, 3.3.7, 3.3.8). Four passes carry a limit that is stated in
the row (1.4.1 simulated only, 3.1.2 English only, and the two that depend on the
manual script, 1.3.2 and 3.2.1, where the automated evidence is partial).
**Not claimed**: that the interface *conforms* — conformance would need the manual
script run and disabled users; see §2 and the accessibility statement.

---

## 9. Trade-offs

The following trade-offs are evaluated against the project's measured evidence.

**Born-accessible vs radical inclusion, as practised here.** Born-accessible is
what a developer can do alone: the harness, the contract tests and the fixes above
are all of that kind, and they are measured. Radical inclusion transfers power to
the people a system acts upon, and here that is the reviewer in the video and the
comment authors — none of whom was consulted. It was *not achieved*. The gap is
stated on every report and in the accessibility statement.

| Traded | Against | What was decided, and the evidence |
|---|---|---|
| Motion as part of the design (gate, CRT boot, film, shelf, count-up) | Vestibular safety, attention, slow machines | Kept every signature piece, made each skippable and still under one switch. Measured: with motion on, 8 endless animations and 60 GPU draws/s on the landing, 5,400 draws/s on the Library; with Reduce motion, 0 and 0 on all seven pages. 3 of 5 evaluation participants asked for the switch. |
| A book that fits one screen | Larger type | The book's 11.5px micro labels are the type system's floor and stay; raising them risks spreads that overflow. The one-page reading is the large-text path, and zoom to 400% reflows. Stated as a known limitation. |
| Delivery schedule | Co-design with disabled users | No new participants were recruited during the final implementation period. Automated developer checks were completed, while co-design with disabled users remains an explicit limitation. |
| Automated checks (cheap, repeatable) | Manual and human testing (slow, costly) | 23 real-browser checks and 52 contract tests run in minutes on every change; the VoiceOver, keyboard and phone script was prepared but had not been run when this record was completed. |
| No new dependencies | A standard WCAG scanner | axe-core added as a dev-only tool, asserted never to ship (a test fails if any product file imports it). |

**External benchmarks used.** WCAG 2.2 level AA (W3C, 2023) as the criteria,
§8 above; axe-core 4.13.0's WCAG 2.2 A/AA rule set as the automated reference;
the Microsoft Inclusive Design persona spectrum (2016) as the design brief, §3.

**Mobile form inputs (the run page).** Each field has a visible label and a hint
bound by `aria-describedby`; the address field is `type="url" inputmode="url"`
so phones offer a URL keyboard; brand and product capitalise words; fields are
48px tall; an error replaces the hint at the field, marks it `aria-invalid`, moves
focus to it and is announced; the Brand and Product fields stack to one column on
small phones (R4).

**Mobile text.** Nothing below the 11.5px floor where a reader needs it (R10); the
viewport never blocks zoom; every page reflows at 320 CSS px with no sideways
scroll across 13 window sizes; long titles and caveat tokens break rather than
overflow; chart labels are enlarged on phones and every chart has a text
equivalent (R8).
