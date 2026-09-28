# User evaluation findings

**Date:** 02 Aug 2026. **Method:** 3 people (Participant A, Participant B, Participant C), reviewed 7 real
screenshots of the dashboard (Apple = high-conflict example, Nike = low-conflict contrast
case), answered four questions independently, with no coaching. Individual responses are
held privately; the findings below retain the anonymised quotations used in the analysis.

**Analysis rule:** an observation was classified as a recurring pattern when at least two
participants raised it independently without seeing each other's responses. Single-participant
observations are reported separately.

---

## Observed strengths

All three participants identified the tool's intended purpose without coaching: comparing
spoken words, facial expression and vocal delivery, then cross-checking those readings against
audience comments. All three also distinguished the lower-scoring Apple example from the
higher-scoring Nike example before the scores were explained.

---

## Cross-cutting findings (2 or more people, independently)

### Finding 1 — Authenticity vs. Brand Health: unclear how they differ (Participant B + Participant C)

Two participants independently found the distinction between Authenticity and Brand Health
unclear. One focused on the similarity between the two score names; the other could not
distinguish Brand Health from the audience sentiment result.

### Finding 2 — Status badges and confidence numbers are unlabeled (Participant B + Participant C, Participant A adjacent)

Two participants could not distinguish the three segment-status labels or interpret the
decimal values beside emotion and sentiment labels. A third participant also found the term
"cross-channel conflict" difficult to interpret. The information was present, but its meaning
was not sufficiently explained in context.

### Finding 3 — Everyone wants to know *why*, not just the number (Participant A + Participant B + Participant C — unanimous, 3/3)

All three participants independently requested an explanation of the evidence behind the
score. Their requests covered channel contributions, the strongest examples and direct links
to the moments that produced the largest disagreements. Addressing this required a dedicated
evidence view rather than a small wording change.

### Finding 4 — Sponsorship-disclosure context is missing (Participant A + Participant C)

Two participants requested sponsorship context, including whether the video declared paid
promotion. This required an additional data source, such as the video's paid-promotion
declaration or description, rather than a layout-only change.

---

## Single-person observations (noted, not acted on)

- One participant found the first view too dense and questioned DeepFace's reliability after
  reading the facial-emotion caveat.
- One participant questioned whether 100 sampled comments represented the full audience. This
  concerns the sampling method rather than the interface.

These observations did not meet the two-participant threshold and were therefore retained
without being treated as recurring findings.

---

## Rating

Participant A 4/5, Participant B 3/5 and Participant C 4/5: **mean 3.67/5** for the
three-person pilot. The small sample limits generalisation.

---

## Interface changes following the pilot (2 August 2026)

Findings 1 and 2 share the same root cause (real information, not enough inline
explanation) and are both small, contained fixes: add plain-language microcopy, no new
data, no new layout, no logic changes. Finding 3 (the unanimous "explain why" result) is
the larger requirement because it required a new evidence view rather than a contained
wording change.

**Changed in `static/index.html`:**

1. Added a one-line, factually-grounded subtitle under each score card:
   - Authenticity: *"Do the 4 signals — words, face, voice, comments — agree with each
     other?"*
   - Brand Health: *"Overall reception: 60% comment sentiment + 40% authenticity"*
     (matches `scorer.py`'s actual formula exactly — not a simplification that drifts from
     the real calculation)
2. Added one caption line above the segment list explaining the three status badges
   (Flagged / Below threshold / No conflict) and that bracketed numbers are model
   confidence (0–1) — answers Participant B's and Participant C's exact confusion in one place, without
   cluttering every individual segment card.

**Before/after screenshots:** see `screenshots/08_after_fix_authenticity_labels.png` and
`screenshots/09_after_fix_segment_legend.png` — same Apple report, same views as the
original pilot screenshots, allowing a direct before-and-after comparison.

**Verification:** full 162-test suite re-run after the change — still 162 passed (this was
a static-HTML/JS-only change, no Python touched, but re-verified anyway).

## Subsequent implementation addressing Finding 3

Finding 3 required a larger change than the initial wording fixes. A bounded implementation
was subsequently built using data already produced by the pipeline, without changing
`scorer.py` or the orchestrator:

1. **"Why This Score" card** — auto-generated one-line verdict (e.g. *"Flagged: 41 of 77
   moments (53%) show signals disagreeing, most often involving Words"*) plus a 4-channel
   disagreement tally (Words / Face / Voice / Comments), providing the requested concise
   explanation at the top of the report.
2. **"Biggest Disagreements" card** — the 3 highest-conflict segments surfaced automatically
   at the top, exposing the strongest examples without requiring a sequential search through
   all 77 segments.

**Bug fixed while building this:** the orchestrator's own system prompt names each channel
two different ways (`vocal_prosody` vs. the payload's `vocal_emotion`; `comment_sentiment`
vs. `video_comment_sentiment`) — the LLM echoes both when reporting `channels_in_conflict`,
so a naive tally silently split "Voice" into two smaller, separate bars. Fixed by mapping
both variants to one canonical label before counting. This exposed an inconsistency in the
orchestrator's prompt vocabulary rather than a presentation-only defect.

**Not implemented:** a true weighted "% of score contributed by each
channel" — the tally above counts *how often* a channel disagrees, not how much it moved
the final number. That needs real attribution logic against `scorer.py`'s actual weighting
and remains future work.

**Verification:** 162/162 tests still passing. Screenshots:
`screenshots/10_why_this_score_apple.png` (high-conflict case) and
`screenshots/11_why_this_score_nike.png` (low-conflict case) — same two reports as the
original pilot screenshots, so before/after is a direct comparison.

---

## Final evaluation, 24 Sep 2026 — n = 5

**Method:** the remote screenshot form in `user_eval/` (`PROTOCOL.md`: 18 screenshots, 52
questions, answer key fixed before any response). Individual responses are stored privately.
**Scores:** `user_eval/SCORES.md`, generated by `user_eval/score.py`.
Three people (P1, P2, P4) also took the August pilot; P3 and P5 are new. Four used a laptop
and reported no reading difficulty. **P5 used a phone and reported low vision** (A3, A4). The
screenshots are 1512 px laptop captures, so on a phone they shrink, and P5's answers are
partly about the study format, not the interface's own phone layout, which was not tested.
**P5 declined quotation (C0.2)**, so P5's free text is withheld from the research record and is
counted below by topic, never quoted. The pattern rule is unchanged: 2 or more of 5,
independently. This round measures **reading**, not operation: nobody clicked anything.

### What was measured

- **Comprehension is high, except for one reader.** Median **16 of 17** keyed items correct
  (16, 17, 16, 16, 13). **Two items meet the protocol's problem rule:**
  - **R7**, "no clear difference" (P1 Not sure, P5 wrong). A third person (P2, O1) asked
    why camera says "no clear difference" when its two marks are far apart. So 3 of 5 had
    trouble with that phrase.
  - **R14**, the least reliable channel (P4 "the voice", P5 Not sure). The page facing it
    calls vocal "the weakest of the four" (defect 2 below), and P2 reported that
    contradiction. So 3 of 5 were affected by that spread. That the stale sentence caused
    the wrong answer is an inference, but a direct one.

  P5 scored lowest and answered R3 "the reviewer was only about half honest": the misreading
  the page exists to prevent. P5's R2, written before R3, also took the meaning from the
  name. Independently, P3 said the name "Authenticity" invites that misreading. So **2 of 5**
  tie the name to honesty. Caution: the distractors were weak, so the multiple choice
  probably flatters understanding (inference).
- **Trust and intent to use are low.** R15 trust: 2, 2, 1, 3, 3 (median 2). O4 would use it:
  2, 3, 2, 4, 3 (median 3). The reasons given were a verified bug (P2), the measured
  ρ = +0.0575 against human ratings (P3), and unexplained numbers (P5, by topic). Calling the
  low trust *calibrated* is an inference, not a measurement.
- **Against August:** O3 ease of understanding 3, 3, 3, 4, 2 (median 3), against August 4, 3,
  4 (mean 3.67, median 4, n = 3). The three returning people rated 3, 3, 4 now. The artefact
  differs (7 dashboard screenshots then, 18 screenshots of a 46-page book now), so this is not
  a like-for-like drop. **August Finding 1 is not closed:** R5 was 2, 4, 3, 4, 2, so 2 of 5
  still can't tell Authenticity from Brand health, as in August (2 of 3). R3 and R4 were
  4 of 5 and 5 of 5. **August Finding 4 (sponsorship) is not closed** either; see (c).

### Defects the participants found, each verified against the code or data

| # | Found by | What | Verified |
|---|---|---|---|
| 1 | P2 (and P3's R9 "Not sure") | Moment notes at 0:05 and 0:40 misstate the channels. | `outputs/analysis/Apple (Duo).json`: seg 1 is transcript NEUTRAL, vocal NEUTRAL, comment POSITIVE, no facial; its note says "the face and voice read positive". Seg 7 is vocal NEUTRAL; its note says the voice read positive. `verifier.by_field.moment_note` kept 3 of 3: `analyst_verify` does not check a note's channel claims against the labels. This breaks the written report's rule that code owns facts. |
| 2 | P2; R14 above | Page 42 calls vocal "the weakest of the four"; page 41 shows facial at 34.2%, below vocal at 48.9%. | `VOCAL_CAVEAT`, `pipeline/scorer.py:34`, written 02 Sep, before `facial_bench/v2` (04 Sep). |
| 3 | P4 | All five S27 videos score Brand health about 16 while the same book calls 4 of 5 audiences balanced. | Members' Brand health 15.58–17.43, each exactly 0.4 × Authenticity: every video's comment label is NEGATIVE (confidence 0.95–0.97), so the 60% comment part is 0. The lean is balanced because its 95% interval includes zero. Same mechanism as the 15.96 → 79.29 jump (R1, `analyst/ANALYST_EVALUATION.md`). P5 answered M9, about that jump, "Not sure". |
| 4 | P2 | Page 41's last paragraph is cut off mid-sentence. | Screenshot `10-report-limits`. |
| 5 | P2, P3 | Hatching on the "05 leans negative" tile runs over its words. | Screenshot `11-set-overview`. |
| 6 | P3 | The headline "Nobody lies in the words. So this reads four other things." lists the words as the first of the four. | `ui/src/lib/hero.js:59-60`. |
| 7 | P3 | The Analyse panel says "04 channels · 01 perspective" and "One subject" on the product tab too. | Fixed text, `ui/src/pages/run.js:199,208`. |
| 8 | P2 | "sasmung" on the book and the shelf. | The sweep's title is the typed query (`sasmung-s27-ultra-half-12f4e012`). A data typo, not a code fault. |

### Patterns (2+ of 5, independently)

- **(a) The first screen reads as a lie detector:** P1, P3, P4 (3 of 5, F1). P5 could not say
  what the tool does. Only P2 described it as intended. The report then corrects most readers
  (R2, R3), but not P5. Defect 6 is the likely cause (inference).
- **(b) They want a plain bottom line at the top:** P1 (traffic light), P2, P4, P5 (4 of 5).
  This pulls against the measured result: with ρ = +0.0575, an honesty verdict would claim
  what the system cannot measure. What can be said at the top, in plain words, is how well
  covered the reading is, whether the readings agreed, and whether sponsorship was declared.
- **(c) Put sponsorship first, and compare sponsored with unsponsored:** P2, P3, P4 (3 of 5).
  P4: video 03 declared a paid promotion and it only appears on page 28. This repeats August
  Finding 4.
- **(d) Unexplained numbers and jargon on the overview:** conflict 0.600, threshold 0.750 and
  "controller" (P3, P4, P5); "controller" alone (P3, P5); ρ and the comment confidence
  figures (P5). P1 skipped the small writing and read only the two big numbers.
- **(e) The themes grid is hard to read:** M8 1, 2, 2, 3, 2 (median 2, 4 of 5 at 2 or below).
  There are too many symbol kinds, told apart by shade alone (P3). The key is on the other
  page, and the side box stays empty until you hover (P1).
- **(f) Text too small or faint:** D4 4 of 5. Grey notes (P1, P2, P5), cover numbers (P2, P3,
  P5), the hatched tile (P2, P3). This matches the 24 Sep audit's 4.32:1 contrast fault. P5's
  case is compounded by the phone.
- **(g) The scatter chart:** M5 2, 3, 4, 3, 1 (median 3). The points are squashed into the
  middle (P2, P3), and it is unclear which side of the diagonal means what (P1, P2). P5 could
  not tell what it shows.
- **(h) "the local model's verdict did not pass the checks" reads as a failure:** P2, P4.
- **(i) "The room" is unclear:** P1, P3.
- **(j) 'A brand' vs 'A product' is unclear:** P2, P4. Partly a study artefact, because the
  screenshots showed two of the three tabs (P2 says so).
- **Split, no pattern:** book 2 (P4, P5), scrolling page 2 (P2, P3), no preference 1 (P1, who
  lost their place). Shelf helpful 3 (P1, P4, P5), plain list would do 2. Light easier to
  read 3 of 5 (P1, P4, P5). Want a motion-off switch 3 of 5 (P1, P3, P5).
- **Liked most:** honesty about limits (P2, P3); the look (P1); the side-by-side table (P4);
  the page of real comments with their labels (P5, by topic).

**One person each (noted, not acted on):** drop the decimals (P3); drop the face channel
(P3); "Ollama" is jargon (P2); the start button is not visible on the product tab (P4); what
an eleven-character video id is, and whether brand and product are required (P5, by topic);
a comment P5 read as positive was classified negative (the comment model measured 78.7%, so
errors are expected); "15%, needs no more than 50%" beside a label about the stronger
channels reads backwards (P3; the value is the weak channels' share, `analyst_facts.py:389`).
**Renaming Authenticity** has now come from 2 of 5 (P3 proposed it; P5 misread the name).
That meets the pattern rule. No decision on the score's name has been recorded, so this is
open. Renaming it would affect every report, the scorer and the terminology used throughout
the project.

### Invalid item

**R9 is invalid as registered.** Its key is the 0:40 note's own sentence, which is false
(defect 1). The correct reading, "words negative, voice neutral, comments positive", was not
an option. `SCORES.md` reports R9 both ways and flags it. The key has not been changed.

### What changed because of this (24 Sep 2026, same day)

The implementation addressed the verified defects, wording and chart issues. Renaming
Authenticity, removing the face channel, replacing the book, adding a yes/no verdict and
changing the Brand Health formula remained outside the chosen scope. The decision record is
`user_eval/CHANGES_AFTER_EVALUATION.md`.

- **Defect 1, and what it hid.** A new check compares every reading a moment note
  names with the moment's labels. Over all 46 stored notes it dropped **34**: 22
  gave a reading to a channel that was not read at that moment, 11 gave the wrong
  reading, 1 did both. Both books now print the readings in a sentence built by
  code wherever a note is dropped.
- **Defect 2.** `VOCAL_CAVEAT` now calls the voice "the second weakest of the four,
  after facial emotion", and saved reports are served the current text. This is
  the page behind R14.
- **Defect 3.** The table key explains the ~16: a negative majority label adds
  nothing, leaving Brand health at 0.4 × Authenticity.
- **Defects 4 to 7.**
  - Page 41 fits whole.
  - The hatched tile's words sit on clear plates.
  - The headline and the Analyse panel no longer contradict themselves.
- **Patterns (a), (b), (d), (h):** an "In short" note on each title page, plain
  words on the overview, and "the audience" for "the room".
- **(c):** the combined book's In short names the videos that declared a paid
  promotion.
- **(e):** the key sits beside the themes grid, and neutral is a shape, not a
  shade.
- **(f):** brighter greys on the dark pages (7.69:1 and 5.65:1), and larger scores
  on the shelf covers.
- **(g):** the scatter's scale bug is fixed (±0.75 → ±0.5 for S27), with tinted
  halves and clear labels.
- **R7:** a bold first line under the topic chart says what "no clear difference"
  means.

**Not re-tested with people.** Whether R7 and R14 now pass needs the two pages
shown to readers again; until then these are changes made because of the
findings, not improvements shown to work.
