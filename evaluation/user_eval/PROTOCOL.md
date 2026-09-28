# Final user evaluation: protocol and answer key

**Written 24 September 2026, before any response was received.** The answer key and scoring
rules were fixed in advance to prevent retrospective adjustment to the responses.

## What this is

A remote, unmoderated, screenshot-based evaluation of the interface as built on 24 Sep 2026.
Five participants known to the researcher completed one web form distributed as a
single self-contained file, `BrandPulse_Evaluation.html` (3.54 MB, every screenshot embedded;
built from `form/` by `build_single.py`). It needs no server and no account. The form
holds 18 screenshots and 52 questions: 47 counted and 5 optional (S3, M6, D3b and D4b are
follow-ups; A4 is optional because it is sensitive). Answers are not collected
automatically. Each participant used "Copy my answers" to return their response to the
researcher. Individual responses are stored privately outside version control.

**Study selection.** `user_pilot/PILOT_QUESTIONS_V2.md` specifies a live, observed session
with keyboard-only and think-aloud tasks, but that study was not run. The completed remote
study measures **comprehension** and **preference** from screenshots. It does not measure
interaction or operation because participants did not click, turn pages or use the keyboard.

## Screenshots

- Taken by `take_shots.py` from the running app (port 5001): 1512×860 CSS px at devicePixelRatio 2,
  dark theme. Book spreads were taken with reduced motion, so every chart is fully drawn.
  The opening page and library shelf were taken with motion on (reduced motion swaps the 3D
  shelf for a grid).
- Saved as WebP q82 in `form/img/`, 2.62 MB for all 18.
- **Every video still served from `/static/frames/` is blurred** (Gaussian, radius = width/60) on
  its way into the browser, because downloaded video is never redistributed (README, "Engineering rules").
  Participants are told this. Nothing else was altered.
- Reports shown:
  - `Apple (Duo).json`, the single-video book (six spreads)
  - `sasmung-s27-ultra-half-12f4e012`, the combined product book (seven spreads)
  - the Analyse page (One video and A product tabs), the library shelf, and the opening page

## Wording reused, so rounds can be compared

| Here | Source | Compared with |
|---|---|---|
| R1 | V2 C1 (August Q1, "dashboard" → "this") | August answers, qualitatively |
| R2 | V2 B1 | none: V2 was never run |
| R13 | V2 B3, adapted for a screenshot (the page is named) | none |
| R14 | V2 B5 as multiple choice | none |
| O1 | August Q2 / V2 C2, verbatim | August Finding 2 |
| O2 | August Q3 / V2 C3, verbatim | August Finding 4 |
| O3 | August Q4, verbatim | August mean 3.67 / 5, n = 3 (`user_pilot/PILOT_FINDINGS.md`) |
| R5 | new, targets August Finding 1 (Authenticity vs Brand health confusion) | 2 of 3 in August |
| R10 | new, targets August Finding 3 ("explain why", 3 of 3 in August) | 3 of 3 in August |

## Answer key: the 17 comprehension items

Each key is traceable to text on the screenshot the question shows. That text was extracted from
the live page by `spread_text.py` on 24 Sep 2026.

| Item | Key | Source (what the screenshot says) |
|---|---|---|
| S1 | c) A product | Product tab: "It finds five recent reviews of the same thing" (`03-analyse-product`) |
| L1 | a) Click its book | Shelf hint: "Click a volume to take it down" (`04-library`) |
| R3 | b) Agreement of the four readings | "Both scores measure how far four independent readings of the same moment disagreed with each other. Neither is a finding about whether anyone was telling the truth" (`05`) |
| R4 | b) 60% comments, 40% Authenticity | "60% audience comment sentiment and 40% Authenticity." (`05`) |
| R6 | b) Design | Design 0:33, the longest bar; Price 0:17 is next (`06`) |
| R7 | b) Not enough to be sure | "Few comments on a topic means a wide interval, so most topics show no clear difference." (`06`) |
| R8 | a) Mostly positive | 63 positive, 15 neutral, 22 negative (`07`) |
| R9 | a) Words negative; voice and comments positive | 0:40 card: "The words read negative, but the voice and comments read positive." (`08`) |
| R11 | b) None found, not proof | "0 of 5 checked signs are present … These are signs, not proof." (`09`) |
| R12 | a) Evidence the reading rests on | "How much evidence this reading rests on. Not whether the verdict is right" (`09`) |
| R14 | b) The face | Facial 34.2% (the lowest), below vocal 48.9%, transcript 67.8% and comments 78.7% (`10`) |
| M1 | a) Positive in 4 of 5 | "Reviewers' words: 4 of 5 lean positive" (`11`) |
| M2 | b) Reviewer warmer in 4 of 5 | "the reviewer is measurably warmer than the audience in 4 and there is no clear difference in 1" (`11`) |
| M3 | d) 05 | Audience column −0.03, −0.06, −0.07, −0.20, −0.27; video 05 is −0.27 (`12`) |
| M7 | a) Performance and Display | "Reviewers agree on Performance (praised in 2 of 3) and Display (praised in 2 of 2)" (`15`) |
| M9 | b) A near-tie that tipped; the leans held | "Comments read negative, then positive, on a near-tie." and "The leans kept their calls in 3 of 3" (`16`) |
| M10 | b) 1 of 5 | "The creator declared a paid promotion … 1 of 5" (`17`) |

**Scoring, fixed now:**
- An item is correct only when the key is chosen.
- "Not sure" is counted separately, as neither right nor wrong. It is reported, because it shows
  where the design leaves people unable to answer.
- R14 answered "c) The voice" is scored wrong but reported, since vocal is the second weakest.
- A participant's comprehension score is correct / 17.
- Report the per-item correct count out of 5, and the median across participants. Do not report
  a bare mean, and do not report a percentage without n.

**What counts as a finding:** the rule in `user_pilot/PILOT_FINDINGS.md`. One person is an
opinion; **2 or more of 5, independently, is a pattern**. An item that 2 or more people get wrong,
or answer "Not sure", marks a design problem on that page.

**Likert items (F2, S2, R5, R10, R15, M4, M5, M8, O3, O4):** report each person's value and the
median. With n = 5, no interval or test is meaningful, so none is computed.

## Known limits

- **Participants:** five friends of the author, so favourable bias is likely. None is known to use
  assistive technology. A4 is self-reported and optional.
- **Screenshots only:** no interaction, keyboard use, page turns, motion or loading states are tested.
- **Cueing:** multiple-choice options can cue answers. Open recall questions come before the
  matching multiple choice where it matters (R2 before R3, R13 before R14).
- **Themes:** all screenshots are the dark theme, except the D1/D2 pair.
- **Blurred stills** may change how the covers and the moment cards are perceived.
- **Two known interface faults are visible in the screenshots and were not fixed before the study**
  (24 Sep accessibility audit):
  - the grey small labels on the dark book paper are 4.32:1, below the WCAG 4.5:1 floor
  - the combined book's "The videos" fold-out scrolls the page sideways at 200% zoom

  D4 ("too small or too faint") may pick up the first.

## Data handling and analysis

- Responses were recorded verbatim under identifiers P1–P5 and are retained privately.
  Names are stored separately and are not included in the repository.
- Aggregate scores were calculated using the answer key above and are published in
  `SCORES.md`.
- Findings and resulting interface changes are documented in
  `user_pilot/PILOT_FINDINGS.md` and `CHANGES_AFTER_EVALUATION.md`.
