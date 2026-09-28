# Comment Sentiment Labelling Guidelines

**Read this fully before labelling. Do not change these rules once labelling has started.**

Written 2026-08-27, before any label was entered. The rules are fixed in advance so that the
ground truth cannot be tuned after seeing how the models performed. Every example below is a
real comment from the corpus that is **not** in either labelling sheet.

---

## Your task

For each comment, choose exactly one label:

`POSITIVE`  `NEUTRAL`  `NEGATIVE`

Type it in the last column. Do not leave any row blank. Do not add your own labels.

---

## Rule 1 — What you are judging

Judge the commenter's **attitude toward the product or the video**.

You are *not* judging:
- whether the comment is polite or rude
- whether the comment is well written
- whether you agree with it
- the commenter's general mood

> "You should rub sand and dirt on the screen. Mostly trouser pockets have sand and dirt"

This sounds blunt but it is a **NEUTRAL** suggestion about testing method. No approval or
disapproval of the product is expressed.

---

## Rule 2 — Praise for the creator counts as POSITIVE

Many comments praise the reviewer rather than the product. That is still positive sentiment
attached to the video, and the pipeline treats it as audience approval.

> "Feels Illegal to be 19 seconds early 😂😭 Love your videos ❤️🔥"  → **POSITIVE**

> "Amazing video big quality"  → **POSITIVE**

---

## Rule 3 — Questions are NEUTRAL unless they carry a judgement

A plain request for information is NEUTRAL, even if it sounds keen.

> "Yes, but how does it compare to Lynx Africa though?"  → **NEUTRAL**

> "How's the latency? Very interested in proper LE support"  → **NEUTRAL**

But a question that clearly implies criticism is NEGATIVE:

> "That's 10 why you lying"  → **NEGATIVE**

---

## Rule 4 — Mixed comments go to the dominant side

If a comment contains both praise and criticism, pick whichever the commenter is actually
landing on. Only use NEUTRAL if the two sides are genuinely balanced.

> "i Wanna like this phone so much, but i was hoping they would give us a SD slot and
> better display"  → **NEGATIVE** (the disappointment is the point)

> "Coming from a Pixel 6, so a jump to a Pixel 10 Pro is really gonna make a difference"
> → **POSITIVE** (anticipating an improvement)

---

## Rule 5 — Sarcasm is labelled by intended meaning, not literal words

> "Tell me you're sponsored without telling me you're sponsored"  → **NEGATIVE**

The words are neutral. The meaning is an accusation of bias.

---

## Rule 6 — Complaints about YouTube itself are NEGATIVE

If someone complains about ads, the platform, or the upload, label it NEGATIVE. It is
genuine audience dissatisfaction expressed on this video.

> "Got 5 ad breaks in the first 6 minutes of this video, absolutely ridiculous."
> → **NEGATIVE**

---

## Rule 7 — Jokes and banter with no evaluation are NEUTRAL

> "Video title should be: Cooking Nothing and Carl Pei"  → **NEUTRAL**

> "Old ladies. My late grandma's bathroom soap."  → **NEUTRAL**

The second one is a description of a scent, not a verdict on it. If the commenter had said
"smells like old ladies, awful", that would be NEGATIVE.

---

## Rule 8 — Timestamps and quotes

Comments that just point at a moment in the video are NEUTRAL unless the surrounding words
carry sentiment.

> "4:29 hahahhaha...he is the BEST !!!"  → **POSITIVE**

> "3:40 this video is also training us to not focus on the looks, but on the content..."
> → **NEUTRAL**

---

## Rule 9 — Sentiment about a *different* product

If the commenter praises a competitor while criticising the reviewed product, label it by
their attitude to the **reviewed** product.

> "I tried the new Samsung fold and then compared to oppo find n. Somehow the oppo phone
> feels better"  → **NEGATIVE** (about the Samsung Fold, which is the product under review)

---

## Rule 10 — When you genuinely cannot decide

Choose NEUTRAL and move on. Do not agonise, and do not leave the row blank.

Genuine ambiguity exists in real data. It is expected, it will show up as disagreement
between the two raters, and reporting that honestly is part of the result.

---

## Practical notes

- Do not look up what any model predicted. The sheets deliberately do not show it.
- The two raters must **not** discuss individual comments while labelling. The whole point
  of the second rater is an independent judgement.
- Work in reasonable sittings. Fatigue lowers agreement.
- Emoji count as content. "🔥" alone is POSITIVE, "💀" alone is usually NEGATIVE.
- Non-English comments: label them if you can read them, otherwise NEUTRAL.
