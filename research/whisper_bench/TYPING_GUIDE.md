# Whisper Ground Truth — Typing Guide

**Read this before you start. Do not change these rules once you have begun.**

Written 31 Aug 2026, before any transcript was typed and before any model result was seen.

---

## Your task

Listen to 12 short clips. Type exactly what the person says.

That's it. **No judgement calls this time.** Unlike the sentiment labelling, there is no
"hmm, is this positive or neutral?" — a word is either what was said or it isn't.

Open **`type_here.html`** in your browser (`python research/whisper_bench/build_typing_page.py` builds it).
Everything is in there: player, text box, autosave.

⏱️ About 45 minutes. 12 clips, roughly 40 seconds each.

---

## Rule 1 — Type what was said, not what was meant

If they stumble, type the stumble.

> They say: *"the the camera is really good"*
> You type: **"the the camera is really good"**

Do not tidy it up. Do not fix their grammar.

## Rule 2 — Don't worry about punctuation or capitals

The scoring strips all of it automatically. These all score identically:

- `The iPhone is good`
- `the iphone is good`
- `The iPhone, is good!`

So type however is fastest for you. Don't waste time on commas.

## Rule 3 — Spell names properly

**This is the one that matters most.** Product and brand names are exactly where these models
fail, and it's what we're testing.

If you're not sure how a product name is spelled, look it up. Get it right.

> **"Bleu de Chanel Eau de Toilette"** — not "blue de chanel"

That single phrase is where the deployed model produced *"bloodshed nail audit toilet"*, which
is the reason this bench exists.

## Rule 4 — Numbers: write them as digits

> **"6.9 inch screen"**, **"$1,200"**, **"120 hertz"**

The scorer normalises these forms, so no additional punctuation handling is required.

## Rule 5 — Skip the filler sounds

Don't type "uh", "um", "er". The scorer removes them anyway, so typing them just costs you
time.

But **do** type real words, even filler-ish ones: "like", "you know", "basically", "I mean".
Those are words and they count.

## Rule 6 — If you genuinely can't make it out

Type `[unclear]`.

Use it rarely. Replay the clip two or three times first. If it's still impossible, mark it and
move on — don't lose five minutes on one word.

> Clips with `[unclear]` are reported separately and excluded from the headline number, so
> being honest here costs nothing and guessing corrupts the result.

## Rule 7 — Don't look at any model's output

The whole point is that your transcript is independent.

Do not open the `transcripts/` folder. Do not check what Whisper produced. If you see its
guess first, you'll unconsciously agree with it, and the ground truth becomes worthless.

## Rule 8 — Work in one or two sittings

Fatigue makes typos, and a typo counts as a model error — it makes every model look worse than
it is. Take a break at clip 6.

---

## Practical

- **It autosaves** to your browser as you type. Closing the tab is safe.
- Use the **replay** button freely. Listening three times is normal.
- **Slow it down** with the speed control if someone talks fast — Mrwhosetheboss especially.
- When all 12 are done, click **Export** and the file saves to your Downloads.
- Return the exported file to the researcher for scoring with `wer.py`.

---

## Why this is worth 45 minutes

Whisper sits **upstream of everything**. Its output is what the sentiment model reads, and its
pauses define the segments that the face, voice and prosody channels all align to.

If it mishears a word, every channel below it reasons about the wrong word. Right now nobody
knows how often that happens — the number has never been measured on this project's data.

After this, it will be measured.
