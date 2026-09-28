# After the final user evaluation: what changed, and why

**24 Sep 2026.** What the final evaluation changed, in one place. Every fact here comes from
the files listed in section 9. Nothing is new, and nothing has been rounded. The full record
is `user_pilot/PILOT_FINDINGS.md` ("Final evaluation, 24 Sep 2026").

---

## 1. The study, in one paragraph

Five people (P1–P5), friends chosen by the author, filled in a remote screenshot form. It
had 18 screenshots of the finished system and 52 questions, and the answer key was fixed
before any response came in (`PROTOCOL.md`). Three of them (P1, P2, P4) had also taken the
August pilot, and P3 and P5 were new. Four used a laptop. P5 used a phone and reported low
vision, so some of P5's answers are about the study format and not the interface. The study
measured **reading and understanding, not use**: nobody clicked anything. A problem counts
only when **2 or more of the 5** raise it independently. P5 declined to be quoted, so P5's
written answers are counted by topic and never quoted.

## 2. What the numbers said

| Measure (n = 5) | Result |
|---|---|
| Comprehension, 17 keyed questions | median **16** (16, 17, 16, 16, 13) |
| Questions that fail the 2-of-5 rule | **R7** ("no clear difference") and **R14** (least reliable channel) |
| Trust in the result (R15, 1–5) | median **2** (2, 2, 1, 3, 3) |
| Would use it (O4, 1–5) | median **3** |
| Easy to understand (O3, 1–5) | median **3**. August: median 4, n = 3, on a different artefact, so this is not like for like |
| Themes grid readable (M8, 1–5) | median **2** |
| Scatter chart readable (M5, 1–5) | median **3** |
| Invalid question | **R9**: its answer key was a false sentence the system itself had written (section 3) |

**In one line:** people read the report correctly but trusted it little. The low trust is
arguably appropriate, because the system measures ρ = +0.0575 against human ratings. That
is an inference, not a measurement.

## 3. The main finding: the system was writing false sentences

**What was found.** P2 noticed that the card at 0:40 (Apple Duo) had a written note saying
the voice read positive, while the grid right above it said neutral. On checking, the fact
checker (`analyst_verify.py`) had never compared a moment note's claims with the actual
readings.

**What was done.** A new check, `moment_claim_problems`, compares every reading a note names
with the label that moment actually carries. It was run over **all 46 stored notes, and
34 (74%) were wrong**:

- 22 gave the face or the voice a reading at a moment where that channel was not read at all
- 11 gave a channel the wrong reading
- 1 did both

| Report | Wrong notes |
|---|---|
| Apple Duo | 2 of 3 |
| Nike | 0 of 3 |
| Huawei (members) | 7 of 14 |
| Samsung S27, six months | 14 of 15 |
| Samsung S27, last month | 11 of 11 |
| **Total** | **34 of 46** |

The old checker had kept all 46. Each of the 12 notes that survive was read by hand against
its labels, and all 12 are true. Where a note is dropped, the card now shows a sentence
**built by code from the readings**, marked "from the readings", so it cannot disagree with
the grid. The stored reports were re-checked **without running any model**
(`write_analysis.py --recheck --all`).

**Significance:**
- It is a real fault that **only user testing found**. The automated checks had passed it 46
  times.
- It had broken the written report's own design rule, "the model writes words, code owns
  facts", and the fix restores it.
- The likely cause is the note prompt's own example ("…while the face reads negative"),
  which the model seems to copy. This is an inference: the prompt has not been changed or
  re-run.

## 4. Every change, traced to what caused it

| # | Problem found | Raised by | What changed |
|---|---|---|---|
| 1 | The voice warning called the voice "the weakest of the four", while the facing page shows the face lower (34.2% against 48.9%) | P2; R14 failed | It now says "the second weakest of the four, after facial emotion". Old saved reports are shown the corrected text, and the files on disk are untouched. |
| 2 | No plain bottom line at the top | 4 of 5 | An **"In short"** note on each book's title page, written by code from facts only: how well covered the reading is, whether anything was flagged, whether a paid promotion was declared, and "It cannot say whether the reviewer is honest." |
| 3 | Sponsorship was buried (video 03's paid promotion appears only on page 28) | 3 of 5 | The combined book's "In short" names the videos that declared a paid promotion. |
| 4 | Jargon on the overview ("controller", "threshold 0.750") | 3 of 5 | Plain words: "none disagreed enough to be flagged (0.750 on a 0 to 1 scale)" and "the local model" instead of "the controller". |
| 5 | "did not pass the checks" read as a failure | 2 of 5 | "Written by code from the figures: the fact checks set the local model's own summary aside." |
| 6 | "The room" was unclear | 2 of 5 | Now "the audience" or "viewers" everywhere. |
| 7 | The first screen read as a lie detector, and its headline contradicted itself | 3 of 5; P3 | New headline: "Words are only one reading. / So this takes four, side by side." |
| 8 | The Analyse panel said "01 perspective" and "One subject" on the product tab | P3 | "04 channels · read locally" and "Every review." |
| 9 | "No clear difference" misread as "they agree" (R7 failed) | 3 of 5 | A bold first line under the topic chart: "No clear difference" does not mean the two sides agree. |
| 10 | Brand health about 16 on every Samsung video, while the book calls the audiences balanced | P4 | The table key explains why: a negative majority comment label, however narrow, leaves Brand health at 0.4 × Authenticity. All five videos checked. |
| 11 | Page 41 was cut off mid-sentence | P2 | Legend shortened, so the page now fits whole. |
| 12 | Stripes ran over the words on tile "05 leans negative" | P2, P3 | Softer stripes, and the words sit on a clear plate. |
| 13 | The scatter chart was squashed into the middle, and it was unclear which side meant what | P1, P2, P3 | A scale bug made every set draw at ±0.75 or wider; Samsung now draws at ±0.5. Each half is tinted and labelled ("Audience warmer" / "Reviewer warmer"). |
| 14 | The themes grid was hard to read | 4 of 5 rated it 2 or lower | The key moved beside the grid. "Neutral" has its own shape instead of a lighter shade. |
| 15 | Text too small or faint | 4 of 5 | Grey text on the dark pages is brighter (contrast 6.45 → 7.69:1 and 4.53 → 5.65:1). Score numbers on the shelf covers are bigger (0.094 → 0.118 of the cover width). |

## 5. What was deliberately not changed, and why

| Suggestion | Raised by | Why not |
|---|---|---|
| Rename "Authenticity" | 2 of 5 | The term is coupled to the scorer, stored reports and interface copy. It remained unchanged to avoid a late semantic migration without re-evaluation. |
| A yes/no or traffic-light verdict | P1, as part of the 4 of 5 bottom-line pattern | It would claim an honesty judgement the system cannot make (ρ = +0.0575). "In short" gives a bottom line without a verdict. |
| Change the Brand health formula | Follows from P4's finding | It would change every score ever reported, so the page explains the number instead. |
| Replace the book with a scrolling page | Split: 2 book, 2 scroll, 1 no preference | No pattern. |
| Drop the face channel | P3 only | One person. The channel stays, down-weighted and carrying its caveat. |
| Compare sponsored with unsponsored videos | 3 of 5 | Each set has only one sponsored video, which is too few to compare. |

## 6. How the changes were checked

- **Test suite: 1,988 pass, 12 fail.** It was 1,964 before, so 24 tests are new. The 12
  failures are old, already known, and unrelated; each message was read. With the fix
  removed, 7 of the moment-note tests and 2 of the caveat tests fail, so the tests really do
  guard the fix.
- **Test levels:**
  - *Unit:* the new check on its own (`tests/test_analyst_verify.py`, class `TestMomentClaims`).
  - *Integration:* the write path and the re-check (`tests/test_analyst_pipeline.py`).
  - *System:* the Flask routes, through the test client (`tests/test_current_caveats.py`).
- **Report claims checker** (kept with the written report, outside this repository): 254 claims, the same 6
  failures as before this work. None of them was caused by it.
- **Layout:** every page of three books was checked for cut-off text at four screen sizes,
  before and after. Page 41 is fixed, and at the study's screen size nothing new is cut off.
- **Looks:** screenshots of every spread in both themes, before and after. No console errors.
- **No model was run.** Stored text was re-checked by code only. The two Samsung combined
  reports were refreshed without a model, after proving the model's inputs were identical.

## 7. Limitations

- **Not re-tested with people.** These are changes made because of the findings, not
  improvements shown to work. R7 and R14 need showing to readers again.
- **Small sample** (n = 5), friends of the author, three of whom took the August pilot.
- **Reading only, not use.** It is not a usability test of the interaction. The live,
  keyboard session specified in `user_pilot/PILOT_QUESTIONS_V2.md` was not run.
- **One participant used a phone with low vision.** The screenshots were laptop captures, and
  the phone layout itself was not tested.
- **The multiple-choice distractors were weak**, so comprehension is probably flattered. This
  is an inference.
- **R9 is invalid** as registered. Its key was left unchanged, and it is reported both ways
  in `SCORES.md`.
- **Two August findings are still open:** telling Authenticity from Brand health (2 of 5 still
  could not, R5) and sponsorship context.
- **The note prompt still carries the example the model likely copies.** Changing it needs
  a model run to measure.
- **Small leftovers:**
  - Apple Duo pages 38 and 43 were already slightly cut off before this work.
  - The Huawei combined report stays out of date until it is re-run.

## 8. Evidence files

| What | File |
|---|---|
| Protocol and answer key, fixed before any response | `user_eval/PROTOCOL.md` |
| Individual responses | Held privately outside version control |
| Scores, generated | `user_eval/SCORES.md`, made by `user_eval/score.py` |
| Findings and patterns | `user_pilot/PILOT_FINDINGS.md`, "Final evaluation, 24 Sep 2026" |
| The new check | `pipeline/analyst_verify.py` (`moment_claim_problems`) |
| The corrected caveat | `pipeline/scorer.py` (`VOCAL_CAVEAT`) and `app.py` (`_current_caveats`) |
| New tests | `tests/test_analyst_verify.py`, `tests/test_analyst_pipeline.py`, `tests/test_current_caveats.py` |
