# Transcript Sentiment Labelling Guidelines

**Read this fully before labelling. Do not change these rules once labelling has started.**

Written 31 Aug 2026, before any label was entered and before any candidate model was run.
The rules are fixed in advance so the ground truth cannot be tuned after seeing how the
models performed.

Every example below is a real segment from the corpus that is **not** in the labelling
sheet. Nothing here is invented.

---

## Your task

Each row has three text columns. **Rate only the middle one.**

| Column | What to do |
|---|---|
| `context_before_DO_NOT_RATE` | Read it. It is there so a fragment makes sense. |
| **`TEXT_TO_RATE`** | **This is the one you label.** |
| `context_after_DO_NOT_RATE` | Read it. Same purpose. |

Put exactly one of `POSITIVE` `NEUTRAL` `NEGATIVE` in the last column.
Do not leave any row blank. Do not add your own labels.

---

## Rule 1 — Judge the reviewer's attitude to the product

This is speech from the person reviewing the product. You are judging **what they think of
the thing they are reviewing**.

You are *not* judging:
- whether the sentence sounds enthusiastic or flat
- whether you agree with them
- whether the product sounds good to you
- how well they speak

---

## Rule 2 — Description is NEUTRAL. This is the most important rule.

Most of a review is **narration**: stating specs, explaining how something works, walking
through a feature. That carries **no verdict** and is **NEUTRAL**.

> "The Pixel 10 is powered by a tensor G5 chip." → **NEUTRAL**

> "So you can quickly switch between your Mac, your iPhone" → **NEUTRAL**

> "So let's just skip all that and focus on the product." → **NEUTRAL**

A statement is only POSITIVE or NEGATIVE when the speaker is **evaluating**, not describing.

> "I'm loving this solid, punchy bass." → **POSITIVE** (evaluating)

> "This thing has a camera feature" → **NEUTRAL** (describing)

Expect a lot of NEUTRAL. That is correct and it is exactly what this bench exists to
measure. Do not force a row to POSITIVE or NEGATIVE because it feels like it should have
an opinion in it.

---

## Rule 3 — Fragments: rate what is actually in the middle column

Whisper cuts on pauses, so segments often start or end mid-sentence. Use the context
columns to understand it, then rate **only the middle text**.

> `TEXT_TO_RATE`: "I have this at what would basically be like kind of..." → **NEUTRAL**

Incomplete and carries no verdict. NEUTRAL, not a guess at where the sentence was going.

If the middle text carries a clear verdict, label it even when it is a fragment:

> "then the M5 is significantly faster than even last year." → **POSITIVE**

---

## Rule 4 — Praise and criticism

> "So it's pretty clear, the phone's fundamentals are crazy good." → **POSITIVE**

> "for they turn on and they just work when you want them to" → **POSITIVE**

> "and that it requires you to put them in this stupid case" → **NEGATIVE**

> "You can't turn the colorful sound off. And it just doesn't have the production stuff
> built in." → **NEGATIVE**

---

## Rule 5 — A missing or unimproved feature is NEGATIVE

Reviewers often criticise by pointing out what did *not* change.

> "What hasn't been upgraded, again, is the screen. Still, 60Hz IPS LCD, 500 Nits of
> brightness." → **NEGATIVE**

The word "again" and the flat spec recital are a complaint.

> "although the price has also gone up too, so that's not really a perk." → **NEGATIVE**

---

## Rule 6 — A feature the reviewer does not use is NEGATIVE

> "though it doesn't sync with anything externally. So I don't use it." → **NEGATIVE**

---

## Rule 7 — Questions and transitions are NEUTRAL

Reviewers constantly set up the next section. That is structure, not sentiment.

> "that we've not had any change this year. So how much faster is this new M5?"
> → **NEUTRAL**

The first half hints at criticism but the segment lands on a setup question. If you think
the criticism dominates, NEGATIVE is defensible — genuine borderline cases exist and Rule 10
covers them.

---

## Rule 8 — Comparisons: judge the attitude to the **reviewed** product

> "This is a much older device. This is the op-o find end two, I believe." → **NEUTRAL**

Describing a comparison device, no verdict on the product under review.

If a competitor is praised in order to criticise the reviewed product, that is **NEGATIVE**.

---

## Rule 9 — Mistranscriptions: rate what was clearly meant

Whisper makes errors. "the op-o find end two" is the Oppo Find N2. "bloodshed nail audit
toilet" is Bleu de Chanel Eau de Toilette.

If the intended meaning is clear despite the error, rate the meaning. If the text is so
garbled that you genuinely cannot tell what was said, use NEUTRAL and move on.

Do not try to correct the text. Do not skip the row.

---

## Rule 10 — Mixed segments go to the dominant side

If a segment contains both praise and criticism, pick the side the speaker lands on. Use
NEUTRAL only when the two are genuinely balanced.

> "Both of these are sub-$500 phones. I also think they were very clever pairing it up with
> 12 gigs" → **POSITIVE** ("very clever" is the verdict)

---

## Rule 11 — Jokes, asides and off-topic remarks are NEUTRAL

> "I'm compensating for something. Made in Vietnam. Hey, that's convenient in the current
> climate." → **NEUTRAL**

> "marketing push, a Jimmy Fallon presentation, a Jonas Brothers music video."
> → **NEUTRAL**

Neither is a verdict on the product.

Sarcasm is different: label it by **intended meaning**, not literal words. A remark that
sounds neutral but is clearly mocking the product is NEGATIVE.

---

## Rule 12 — When you genuinely cannot decide

Choose NEUTRAL and move on. Do not agonise, and do not leave the row blank.

Genuine ambiguity exists in real speech. It is expected, and reporting it honestly is part
of the result.

---

## Practical notes

- **Do not look up what any model predicted.** The sheet deliberately does not show it, and
  `_sheet_manifest.json` must not be opened while labelling.
- The sheet is **shuffled**. Rows from different videos are interleaved on purpose, so you
  cannot tell which video or which half of the experiment a row belongs to. Do not try to
  work it out — knowing would change how you rate.
- Work in sittings of about 150 rows. Fatigue lowers consistency, and consistency is the
  whole value of this exercise.
- If a second rater labels a subset, the two of you must **not** discuss individual rows
  while labelling. Independence is the entire point of a second rater.
- 599 rows. Budget roughly 1.5 to 2 hours in total.
