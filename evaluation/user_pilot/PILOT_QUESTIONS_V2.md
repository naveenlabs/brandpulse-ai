# BrandPulse AI — user evaluation, second instrument

**Status: written 12 Sep 2026. NOT YET RUN.** Nothing below has been performed and no
result from it may be cited until `RESPONSES_V2.md` exists with real answers in it.

This replaces `PILOT_QUESTIONS.md` as the current instrument. That file is kept as the
record of what the August participants were actually asked; it is not edited, because a
superseded instrument is evidence of what was done, not a draft.

---

## Rationale

The August pilot asked four open questions about **seven screenshots** of a dashboard
that has since been rebuilt twice and no longer exists. It was good at finding out
whether people understood the *scores*. It could not find out anything about whether
people could **operate** the thing, because a screenshot cannot be operated.

This instrument is run **live, on the machine, against the interface as built**, and adds
three things the first one structurally could not reach:

1. **Task completion by keyboard only** — can someone who does not use a mouse actually
   get to the answer?
2. **Caveat comprehension** — the bias caveat is on every report and cannot be dismissed.
   Does anyone know what it is telling them?
3. **Absence interpretation** — a channel that measured nothing is drawn as a hatched
   gap, never as a zero. Is that read as "no data" or as "bad score"?

Consent comes first: `CONSENT.md`, Part 1 given, Part 2 ticked, before anything is shown.

---

## Setup

```bash
cd brandpulse_ai
source .venv/bin/activate
python -m flask --app app run --port 5057
```

Open `/library` and leave it there. Do not pre-open a report; finding one is task 1.

Have ready: a report with a low Authenticity score, and
`Apple (Iphone 18 Pro Max).json`, where **71.3%** of segments have no facial reading —
that is the one that exercises the hatch.

**Say this before starting:** *"I'm testing the interface, not you. If something is
confusing that is the interface's fault and it is exactly what I need to find. Please
think out loud."*

---

## Part A — tasks (observed, not asked)

Record for each: **completed / completed with difficulty / not completed**, the time
taken, and what the participant said while doing it. Do not help until they ask, then
record that they asked.

| # | Task | What it tests |
|---|---|---|
| A1 | Open the report for Samsung Ultra 25. | Finding anything at all |
| A2 | Tell me how many segments disagreed. | Whether the headline figures are findable |
| A3 | Find the moment in the video where the face and the words disagreed most. | Whether the trace/ledger is usable for its purpose |
| A4 | Read me the full sentence that was spoken in segment 41. | Whether a truncated preview leads anywhere |
| A5 | **Keyboard only — hands off the mouse.** Get from the library to a report and find its bias caveat. | Operability without a pointer |
| A6 | **Keyboard only.** Step through three consecutive segments on the trace. | Whether the instrument is operable, not just readable |
| A7 | Open `Apple (Iphone 18 Pro Max)` and tell me what the hatched gaps mean. | Absence read as absence |

For A5 and A6, note whether they found the skip link, whether focus was ever somewhere
they could not see, and whether they tried the mouse by reflex.

---

## Part B — comprehension (asked, answers recorded verbatim)

**B1.** In your own words, what is the Authenticity score measuring?

**B2.** This report scores 38 out of 100. Does that tell you the reviewer was being
dishonest? *(Follow up, whatever they say: what on the page made you think that?)*

**B3.** There is a line on this page about bias. What is it warning you about?
*(Do not point at it. If they cannot find it, record that as the answer.)*

**B4.** Some rows have a dashed outline instead of a mark. What does that mean?

**B5.** One of the four channels is much less reliable than the others. Which one, and
how do you know?

**B6.** If this were your video being scored, what would you want to be able to do?

**B7.** What would you need to see before you would repeat one of these numbers to
someone else?

---

## Part C — the three questions the first pilot asked

Kept verbatim so the two rounds can be compared. `PILOT_FINDINGS.md` treats a thing as a
real pattern when two or more people raise it independently; that bar only works if the
wording does not drift.

**C1.** Without me explaining anything — what do you think this is telling you?

**C2.** What's confusing, unclear, or made you think "wait, what does that mean"?

**C3.** If you were deciding whether to trust a sponsored review based on this, what's
missing that you'd want to see?

---

## Data handling and analysis

If conducted, responses must be recorded verbatim under participant identifiers and stored
privately outside version control. Part A completion outcomes must be recorded alongside the
responses. Analysis uses the same pre-defined recurrence rule as the August pilot: a pattern
requires independent mention by at least two participants. Any resulting interface changes,
or a justified decision to make no change, must be documented with the findings.

---

## Scope limitations

Participants are friends and classmates. **Nobody in this study uses a screen reader,
switch access, voice control, or a braille display in daily life**, and nobody in it has
a colour-vision deficiency that has been established rather than assumed. Nobody in it is
a creator who has been scored by a system like this one.

That means Part A tests whether the interface is *operable by keyboard*, which is a real
and useful finding, and does **not** test whether it is usable by someone who depends on
assistive technology — which is a different question that this study cannot answer. The
write-up must say so in those terms rather than letting "keyboard-only task completion"
stand in for "accessible".
