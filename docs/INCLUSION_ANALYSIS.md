# Inclusion analysis — BrandPulse AI

Written 12 Sep 2026, alongside the accessibility build (items B1–B9). **Updated 25 Sep 2026** after the inclusive-design pass
(`INCLUSIVE_DESIGN.md`), which re-measured everything below on the interface as it
now is — five redesigns later — and found several of the 12 Sep properties lost. This is the part of that work that is not code: who this system
acts upon, who was never asked, and where its inputs are unequal in ways that
have been measured here rather than assumed.

Every figure below is traceable to a file in this repository. Where something is
believed but not measured here, it says so in those words.

---

## 1. Basis of analysis

Section 4 uses measured inequalities from this project's own evaluation rather
than applying a generic bias taxonomy. Each quantitative claim is tied to a
repository artefact and a reproducible script. Conditions that were not measured
are identified explicitly.

---

## 2. Stakeholder map

### 2.1 Intended users

The project identifies the following primary and secondary users:

> "The primary users are brand managers and marketing analysts at consumer-facing
> companies… Secondary users are agencies and market-research firms providing
> brand-health audits."

Two groups. Both of them buy the tool.

### 2.2 Who is actually involved

| Stakeholder | Relationship to the system | Consulted? | Can they see the output? |
|---|---|---|---|
| Brand manager / analyst | Runs it, reads it, acts on it | Yes — 3 participants, Aug 2026 | Yes |
| Agency / market research | Secondary buyer | No | Yes |
| **The person in the video** | **Is scored by it. Face sampled at 1 fps, speech transcribed verbatim, a 0–100 number printed over their photograph** | **No** | **No** |
| **Comment authors** | **Their words are fetched, classified and aggregated into 60% of the Brand Health score** | **No** | **No** |
| Anyone who cannot use a mouse | Operates it | No — and see §3 | — |
| Anyone using a screen reader | Operates it | **No, and has not been approached** | — |

The two rows in bold are the ones with the most at stake and the least say. The
system was designed, built, evaluated and written up without either being asked
anything at all.

### 2.3 What was done about it in the build

- **The person in the video** has a statement on every report (lost when the
  report became a book on 20–23 Sep, restored 25 Sep as its own page, with a line
  beside the face on the title page pointing to it; INCLUSIVE_DESIGN.md A7): what the numbers are not, the measured unreliability of the channel
  reading their expression, and what a deployed version would owe them
  (build item B9). Nine of nine reports carry it. This is a statement *about*
  them written by the developer who built the thing scoring them. **It is not
  standing, and it is not consultation.** It is the most that can be done without
  them.
- **Comment authors** are protected but not represented: author identifiers are
  never stored, never written to `outputs/`, and a test asserts no comment author
  can reach the page. Their words still carry 60% of a score they will never see.

### 2.4 What is still missing

No creator has been shown a report about themselves. That is the single largest
gap in this analysis and nothing in the build closes it. It would
take one conversation with one person who has been reviewed on YouTube, and it
has not happened.

---

## 3. The spectrum, per interaction

Permanent, temporary and situational, applied to what this interface actually
asks a person to do. Where the build has addressed something, the entry names
the build item (B1–B9); where it has not, it says so.

| Interaction | Permanent | Temporary | Situational | Status, re-measured 25 Sep 2026 |
|---|---|---|---|---|
| Start an analysis and wait 4–9 min | Blind, low vision | — | Away from the screen | **Built** — live regions announce every stage and ending; progress bar carries value text; tab title reports progress (B2; verify_ui check 10) |
| Get past the opening screens | Blind, motor | — | Keyboard only | **Built 25 Sep** — the boot screen has a real Continue control described by its log; modifier keys and screen-reader chords no longer dismiss it; a keyboard reader is not timed out (A6) |
| Read the two headline scores | Cognitive, dyslexia | — | Rushed, unfamiliar with the domain | **Built** — plain-sentence gloss on each score; "What these numbers cannot tell you" restored as a page 25 Sep (A7) |
| Read the landing's film | Blind | — | — | **Fixed 25 Sep** — three of its four parts, including the facial-accuracy disclosure and its only link, were hidden from screen readers (A5) |
| Read a report at 400% zoom | Low vision | — | Small laptop, split screen | **Built** — reflow measured at 13 window sizes, both motion states; Read as one page for a continuous document (R1, R2, I2) |
| Read with your own spacing | Dyslexia, low vision | — | — | **Built** — 1.4.12 override measured on every spread of every book (check 14; the 21 Sep version measured 0 elements) |
| Take a report off the shelf, or delete one | Motor, blind | Broken wrist | Trackpad on a train | **Fixed 25 Sep** — the keyboard could not reach the desk or Delete; Space was taken at the window (A2, A3) |
| Use the Library on a phone or a rotated tablet | — | — | Small window, split screen | **Fixed 25 Sep** — narrowing a loaded shelf left an empty page (R1) |
| Operate the trace | Motor, RSI | Broken wrist | Trackpad on a train | **Partly** — keyboard-operable (B4); **untested with a switch or a head pointer** |
| Say a command | Motor | Hands full | Voice control at a desk | **Built** — every overridden name leads with its visible words, measured in both themes (the 21 Sep run measured one theme twice) |
| Stop the movement | Vestibular | Migraine | Motion sickness, slow laptop, projector | **Built 25 Sep** — a Reduce motion switch on every page, asked for by 3 of 5 in the final evaluation (I1); the OS setting still honoured |
| Print a report | — | — | A meeting, a reader who wants paper | **Fixed 25 Sep** — only the spread on the desk printed, light ink on white paper (R5) |
| Windows High Contrast | Low vision | — | Glare | **Built 25 Sep** — marks that carry a reading survive forced colours; focus follows the system highlight (A11) |
| Any of it with JavaScript blocked | — | — | Locked-down corporate machine, text browser | **Built** — every page carries a readable core, caveat included (B1) |
| Understand the bias caveat | Cognitive | — | Reading fast | **Unknown** — present and undismissable, now on the Library too (A1); whether it is *understood* needs people |
| Read the four channel colours | Colour-vision deficiency | — | Bright sunlight, cheap projector | **Partly** — shape as well as colour; screenshots under six simulated conditions (check 18); **not validated with a CVD user** |
| Read it in your own language | — | — | Non-English speaker | **Not addressed** — and see §4.2 |
---

## 4. Where the inputs are unequal

Five, each measured here, each with a file that produced the number.

### 4.1 The facial channel is unreliable, and its unreliability is documented to vary by skin tone and gender

Measured here: on held-out speakers the deployed model scores **34.2%**, below an
always-NEUTRAL constant at **67.5%**, against a human ceiling of **87.5%**
(`facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md`). Its characteristic error is
manufacturing negativity — **33.8%** of verified-neutral held-out frames are
called NEGATIVE.

**Not measured here:** whether that error falls unevenly across skin tone or
gender. That is documented in the literature (Buolamwini and Gebru, 2018) and is
why `BIAS_CAVEAT` exists, but this project has never tested it on its own data.
The materials to do so are present — `facial_bench/v2/crops/` holds **362 aligned
face crops**, the exact pixels the models scored, across 8 speakers — and that is
what `fairness_bench/` is for. **Until it runs, this project cites a disparity it
has not observed.**

### 4.2 Speech recognition is unequal by accent, and the model choice already fixed it

`whisper_bench/WHISPER_MODEL_ANALYSIS.md` §: on a German-accented speaker
discussing French product names, `base` scores **14.78% WER** and `large-v3`
scores **3.48%** — a 4.2× reduction, and that single speaker produced nearly the
whole model-size effect in the bench.

The deployed model is `large-v3-turbo` (`audio_module.py:78`), which also scores
**3.48%** on that speaker. So the accent disparity was found by measurement and
is mitigated by the model actually in use. **This is the one inequality in this
list that the project has already acted on**, and it is worth noting that it was
found by benchmarking for accuracy, not by looking for bias.

### 4.3 Vocal emotion accuracy varies enormously between speakers

`vocal_bench/SPEAKER_NORM_RESULT.md` §: per-speaker accuracy over all 147 clips
runs from **27.3%** (Dave2D) to **65.3%** (Marques Brownlee) — pooled 56.5%, a
**range of 38.0 points**. Per-speaker normalisation was pre-registered, tested,
and **rejected**: every variant was 12.7–21.2 points worse on held-out speakers,
because the between-video offset turned out to be real signal.

So the channel is known to work much better for some speakers than others, the
obvious correction makes it worse, and it ships down-weighted to 0.489 with a
caveat on every report that uses it.

### 4.4 The corpus is small, English, and professional

`ui_evidence/figures.json`: **9 reports over 6 distinct videos, 721 segments, 900
comments.** Every speaker is a professional presenter working in English in good
lighting with good audio. `facial_bench/v2/` pre-registered a floor of 20 anger
frames and the corpus produced **4** — the genre has almost no negative facial
affect in it at all.

Two consequences, and the second is the uncomfortable one: every accuracy figure
in this project is an accuracy *on studio-quality video of professional presenters*,
and the facial channel's premise — that faces contradict words — is being tested
on a genre where faces are performed for a camera.

### 4.5 The audience is whoever YouTube ranked, not whoever commented

`comment_module.py:161` fetches up to 100 comments with `order="relevance"` —
relevance-ranked by the Data API. That is not a sample of the audience; it is a sample of what one company's
ranking surfaced, and it carries 60% of the Brand Health score. Nothing in this
project has measured what that ranking selects for, and nothing on the page tells
a reader that the comments were ranked rather than drawn.

### 4.6 And one that is not about the data at all

The largest single influence on the output is which local model is installed:
the controller swap moved mean Authenticity across this corpus by **49.08 points
on byte-identical channel inputs** (`controller_bench/CONTROLLER_MODEL_ANALYSIS.md`).
This is now stated on every report (B7). It belongs in this document because it
is the clearest case of the system's answer depending on something the person
being scored has no visibility of and no say in.

---

## 5. What this analysis cannot conclude

- **That the interface is accessible.** It is measurably more accessible than it
  was, and the 25 Sep pass showed how that can quietly stop being true: five
  redesigns after 12 Sep had removed the Library's caveat, the statement to the
  person in the video and the keyboard route to Delete, while the harness meant
  to catch that could not run. None of the measurement is a disabled person
  completing a task.
- **That the caveats are understood.** They are present, undismissable, and on
  every surface that shows a facial-derived score. Whether anyone reads them or
  changes their mind because of them is unknown and is `PILOT_QUESTIONS_V2.md` B3.
- **That the facial channel is or is not biased by skin tone on this data.**
  Not measured. `fairness_bench/` is the next piece of work.
- **That the scored party is adequately protected.** One statement on a page,
  written by the developer, with no route to contest, in a prototype with no
  server. It is honest about being that, and that is all it is.

---

## 6. Referenced from

- `user_pilot/CONSENT.md` — consent process, and the August 2026 lapse
- `user_pilot/PILOT_QUESTIONS_V2.md` — the instrument that tests §3's unknowns
- `INCLUSIVE_DESIGN.md` — the 25 Sep pass: plan, defects, fixes, before and after
- `ui_evidence/SCREENREADER_SCRIPT.md` — the VoiceOver, keyboard and phone script, rewritten 25 Sep, unrun
- `ui_evidence/ui_measurements.json` — the real-browser checks (`.before.json` is the 25 Sep run before the fixes)
