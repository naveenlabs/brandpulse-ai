# Whisper Transcription Bench — Results and Evaluation

**Run 31 Aug – 01 Sep 2026.** Twelve Whisper checkpoints, one 8.72-minute evaluation sample,
one hand-typed human reference. Method follows the eight-step bench method (README), the same procedure used
in `comment_bench/` and `transcript_bench/`.

Pre-registration is in `CANDIDATE_MODELS.md`, written and fixed **before any model was run and
before any ground truth was typed**. Nothing in §3 or §4 of that file has been edited since.

Every number below is reproducible:

```bash
python run_whisper_bench.py          # transcribe (already done, cached in transcripts/)
python report_whisper.py --json analysis_results.json
python brand_terms.py
python verify_claims.py              # re-derives every figure quoted here
```

---

## 1. Headline result

| | |
|---|---|
| Checkpoints evaluated | **12** |
| Evaluation sample | 12 clips, 8.72 min, 6 speakers |
| Reference words | 1,780 typed → **1,887 after normalisation** |
| Incumbent (`base`) WER | **3.13%** |
| Best WER (`large-v3`) | **1.80%** |
| Pre-registered rule selects | `small` |
| **Adopted 01 Sep 2026** | **`large-v3-turbo`** — a declared deviation, argued in §6 |

**The single most important finding is not which model won.** It is that the pre-registered
decision rule, applied mechanically, selects a model that is **not measurably better than the
one it would replace**, while costing 2.5× the runtime. That is a defect in the rule, it was
found by applying the rule honestly rather than by quietly ignoring it, and §6 deals with it in
the open.

---

## 2. Word Error Rate — all twelve checkpoints

WER = (S + D + I) / N, pooled across clips, normalised with OpenAI's own
`EnglishTextNormalizer` — the same normaliser used for the WER figures in the Whisper paper.

| Model | Params | WER | Sub | Del | Ins | Segments | Realtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `large-v3` | 1541.6M | **1.80%** | 15 | 8 | 11 | 197 | 1.3× |
| `large-v3-turbo` | 807.0M | 1.91% | 17 | 6 | 13 | 181 | 4.7× |
| `medium` | 762.3M | 2.23% | 21 | 9 | 12 | 201 | 2.3× |
| `large-v2` | 1541.4M | 2.33% | 17 | 7 | 20 | 186 | 1.2× |
| `large-v1` | 1541.4M | 2.44% | 22 | 10 | 14 | 183 | 1.3× |
| `medium.en` | 762.3M | 2.54% | 25 | 11 | 12 | 199 | 2.3× |
| `small` | 240.6M | 2.60% | 29 | 7 | 13 | 183 | 6.8× |
| `small.en` | 240.6M | 2.65% | 33 | 7 | 10 | 180 | 6.7× |
| `base.en` | 71.8M | 3.07% | 33 | 12 | 13 | 197 | 17.1× |
| **`base`** ← deployed | 71.8M | **3.13%** | 35 | 10 | 14 | 186 | 17.2× |
| `tiny.en` | 37.2M | 4.40% | 48 | 15 | 20 | 170 | 32.9× |
| `tiny` | 37.2M | 4.82% | 52 | 18 | 21 | 182 | 32.5× |

Parameter counts were **measured from the downloaded checkpoints**, not cited.

### The accuracy ladder is real but shallow

Every checkpoint from `tiny` to `large-v3` spans **1.80% to 4.82%** — a range of three
percentage points across a 41× difference in parameter count. On this material a 37M-parameter
model already transcribes more than 95% of words correctly.

This is the answer to **Q1** and it is an important one for the project's framing: the inherited
choice of `base` was **not** a serious error. It was untested, which was the real problem, but
it was not producing garbage. `base` gets 96.87% of words right.

### Q2 — the English-only variants do not win

This was the question with the most practical upside, because `base.en` is the same size and
speed as the deployed model. A win would have been free.

| Comparison | WER diff | 95% CI | p | Clips won | Detectable |
|---|---:|---|---:|---|---|
| `base.en` vs `base` | −0.05% | [−1.03, +0.95] | 0.9374 | 4–4–4t | no |
| `small` vs `small.en` | −0.05% | [−0.64, +0.57] | 0.9212 | 5–3–4t | no |

**There is no free win.** `base.en` and `base` are indistinguishable — they split the twelve
clips four apiece with four ties, and the interval is centred almost exactly on zero. The same
holds at `small`. At `medium` and `tiny` the multilingual variant was in fact *ahead*
(2.23% vs 2.54%; 4.82% vs 4.40% — the latter favouring `.en`), with no consistent direction.

The project is **not** paying a measurable multilingual tax. This is a genuine negative result
and it is reported as one.

### Q3 — large version matters, but not much

`large-v1` 2.44% → `large-v2` 2.33% → `large-v3` 1.80%. The v1→v3 gap is 0.64 points and
`large-v3` vs `large-v2` is not individually detectable (p = 0.2692, clips 4–4–4t).

### Q4 — `large-v3-turbo` is the standout

**1.91% WER at 4.7× realtime.** It is within 0.11 points of `large-v3` (p = 0.6994, clips
3–4–5t — indistinguishable) while running **3.6× faster** and at roughly half the parameter
count. On this evidence the distillation costs essentially nothing in accuracy.

---

## 3. Where the errors actually are

Pooled WER hides the thing that matters most. Per-speaker:

| Model | Dave2D | Jeremy Fragrance | MKBHD | Mrwhosetheboss | ShortCircuit | The Tech Chap |
|---|---:|---:|---:|---:|---:|---:|
| `large-v3` | 0.57% | **3.48%** | 2.16% | 1.32% | 1.50% | 2.76% |
| `large-v3-turbo` | 0.00% | **3.48%** | 1.83% | 1.62% | 2.26% | 3.87% |
| `small` | 0.57% | **16.52%** | 1.99% | 1.76% | 0.75% | 2.21% |
| `base` | 0.57% | **14.78%** | 2.99% | 1.32% | 3.76% | 4.97% |
| `tiny` | 3.98% | 15.65% | 3.65% | 2.21% | 9.77% | 8.84% |

**One speaker carries almost the entire model-size effect.** On the five native-English tech
reviewers, `base` ranges 0.57%–4.97% and the large models buy little. On Jeremy Fragrance — a
German-accented speaker discussing French product names — `base` scores **14.78%** and
`large-v3` scores **3.48%**, a 4.2× reduction.

This is the honest shape of the result: **model size does not buy general accuracy on clean
studio English. It buys robustness on the hard case.** A bench reporting only the pooled number
would have missed this entirely, which is why per-speaker breakdown was pre-registered in §3.

---

## 4. Brand-name recall — post-hoc, and weaker than it first looked

**This analysis was NOT pre-registered.** It was written after observing a specific failure, and
is reported as exploratory. It did not alter the pre-registered rule.

The observation that prompted it, from clip `haWvrSliMVY`:

| Source | Transcription |
|---|---|
| Human | "unlike its biggest competitor, **Dior Sauvage**" |
| `base` | "unlike its biggest competitor **Dior Savash**" ❌ |
| `small` | "unlike it's biggest competitor **Dior Savage**" ❌ |
| `large-v3` | "unlike its biggest competitor **Dior Sauvage**" ✅ |

For a brand-monitoring product this is not a generic word error. WER counts it as one
substitution among 1,887 words; the product consequence is that the segment becomes unusable for
its only purpose. WER weights every word equally, and for this application that assumption is
wrong.

Measured across 30 brand-term occurrences drawn from the human transcripts only
(`brand_terms.py`):

| Model | Brand recall | Missed |
|---|---:|---|
| `large-v2`, `large-v3` | **96.7%** (29/30) | qwen |
| `large-v3-turbo` | 93.3% (28/30) | qwen, draw things |
| `large-v1` | 90.0% (27/30) | eau de toilette, qwen |
| `medium` | 76.7% (23/30) | sauvage, qwen |
| `base`, `small`, `small.en` | **70.0%** (21/30) | sauvage, eau de toilette, qwen |
| `tiny` | 56.7% (17/30) | sauvage, eau de toilette, fold, macbook, qwen |

A 26.7-point spread against a 1.32-point WER spread. **But this finding does not survive its own
robustness check intact.**

### The check that nearly killed it

47% of all brand-term occurrences (14 of 30) come from the single Jeremy Fragrance clip.
Excluding it:

| Model | All 12 clips | Excluding that one clip |
|---|---:|---:|
| `large-v3` | 96.7% | 93.8% (15/16) |
| `large-v3-turbo` | 93.3% | 87.5% (14/16) |
| `medium.en` | 73.3% | **100.0%** (16/16) |
| `base` | 70.0% | **93.8%** (15/16) |
| `small` | 70.0% | 93.8% (15/16) |
| `tiny` | 56.7% | 68.8% (11/16) |

**The spread collapses.** With that one clip removed, `base` ties `large-v3`, and `medium.en`
outscores both. A sign test on `base` vs `large-v3` gives 0–8 with exact p = 0.0078, but those
eight discordant occurrences are **repetitions of the same two words by the same speaker in the
same clip** — they are not eight independent observations, and the p-value should not be read as
though they were.

**Corrected claim.** Larger models are better at *hard* brand names — foreign-language product
names spoken with a non-native accent. There is no evidence here that they are better at brand
names in general. The original, stronger reading was wrong and is recorded as such rather than
quietly dropped.

This is a narrower finding than it first appeared, and it is still the most
application-relevant one in the bench.

---

## 5. The cost nobody can avoid: segmentation

Whisper defines the segment boundaries that **every other channel aligns to**. Changing the
model changes the spine of the system.

Boundary agreement against `base`, 0.5 s tolerance:

| Model | Segments | Agreement with `base` |
|---|---:|---:|
| `tiny.en` | 170 | 79.4% |
| `small.en` | 180 | 78.3% |
| `large-v1` | 183 | 78.1% |
| `base.en` | 197 | 77.7% |
| `small` | 183 | 76.5% |
| `large-v3-turbo` | 181 | 75.1% |
| `large-v3` | 197 | 72.6% |
| `medium` | 201 | 69.7% |

**Switching to any model moves roughly a quarter of segment boundaries.** There is no cheap
option — even `base.en`, same architecture and same size, disagrees on 22.3% of boundaries.

### What this does to the 599 transcript labels

`transcript_bench/labels/transcript_label_sheet.csv` holds 599 hand-labelled segments keyed
`video_id:segment_index`, with the segment **text** stored alongside. That text came from `base`.

Three consequences, separated by how certain they are:

1. **The transcript model choice is unaffected — verified fact.** All 16 candidates in that
   bench read *identical* text, so the comparison between them is invariant to which Whisper
   produced it. `cardiffnlp/twitter-xlm-roberta-base-sentiment` remains the winner.
2. **The absolute accuracy figure is conditioned on `base` — verified fact,** already declared
   as threat 3 in `transcript_bench/CANDIDATE_MODELS.md`. The 0.678 holdout accuracy is
   "accuracy given `base` transcripts", not "accuracy given perfect transcripts".
3. **Re-labelling cost — now MEASURED, and the estimate was wrong.**

   The line that stood here on 01 Sep said "roughly a quarter of the 599 labels would need
   review", flagged as an inference from boundary agreement on 12 clips. After adopting the
   model the corpus was re-transcribed and the cost was counted directly
   (`transcript_bench/label_survival.py`, results in `label_survival.json`).

   **The estimate conflated two different things.** Separated:

   | Question | Result |
   |---|---|
   | Q1 Do labels still align 1:1 with a single new segment? | **34.1%** do (127 identical, 77 near) |
   | Q2 Do the labelled words still appear in the transcript at all? | **98.2%** do (483 intact, 105 minor drift) |

   Mean word coverage is **0.976**. Only **11 of 599 labels (1.8%)** have genuinely different
   wording — and all eleven are labels applied to text `base` had garbled, which
   `large-v3-turbo` now transcribes correctly ("audit toilet" → "Eau de Toilette",
   "Dior Savash" → "Dior Sauvage"). Six of the eleven are from the fragrance video.

   **Re-labelling required: none.** `transcript_bench/ground_truth.py` loads its ground truth
   from `labels/transcript_label_sheet.csv` as (text, label) pairs and never reads `corpus/` —
   verified by running it after the overwrite, 400 selection + 199 confirmation rows load
   intact. The labels are a self-contained dataset, so a boundary moving does not invalidate
   them.

   What Q1's 34.1% does mean is real but narrower: the deployed segmentation has drifted from
   the segmentation the labelled sample was drawn from. The 599 labels remain a valid test set
   of genuine transcript segments; they are no longer a *perfectly matched* sample of what the
   deployed system now cuts. That is a sampling caveat to state, not a re-labelling bill.

---

## 6. The decision, and a defect in the pre-registered rule

### What the rule says

> *"Adopt the fastest model whose WER is not detectably worse than the best-scoring model."*
> — `CANDIDATE_MODELS.md` §3, fixed 31 Aug 2026

Applied mechanically by `report_whisper.py`:

- Best WER: `large-v3`, 1.80%
- Qualifiers (not detectably worse than `large-v3`): `large-v1`, `large-v2`, `large-v3`,
  `large-v3-turbo`, `medium`, `medium.en`, `small`, `small.en`
- Fastest qualifier: **`small`** at 6.8× realtime

`base` does **not** qualify — it is detectably worse than `large-v3` (p = 0.0244).

### Why following it mechanically would be wrong

| `small` vs `base` | Result |
|---|---|
| WER | 2.60% vs 3.13%, diff −0.53% |
| Bootstrap | p = 0.1936, CI [−1.34, +0.21] — **not detectable** |
| Clips won | 5–3, with 4 ties |
| Brand recall | 70.0% vs 70.0% — **identical**, sign test p = 1.0000 |
| Runtime | **2.5× slower** |
| Segmentation | 23.5% of boundaries move |

**The rule selects a model that cannot be shown to be better than the incumbent at anything, and
that costs runtime and a re-segmentation.** It would pay the full switching cost for no
demonstrated benefit.

### The defect, named precisely

The rule tests each challenger against **the best model** and never against **the incumbent**.
At n = 12 the "not detectably worse than best" criterion is weak, so it admits a wide band of
models — including ones that are also not detectably *better* than what is already deployed.
Significance is not transitive: `base` being distinguishable from `large-v3` while `small` is
not does **not** establish that `small` is distinguishable from `base`. Here it demonstrably is
not.

A correctly specified rule would have read: *adopt the fastest model that is detectably better
than the incumbent.* Under that rule the qualifiers are exactly:

| Model | WER | vs `base` | Realtime |
|---|---:|---:|---:|
| `large-v3` | 1.80% | p = 0.0244 | 1.3× |
| **`large-v3-turbo`** | **1.91%** | **p = 0.0212** | **4.7×** |
| `medium` | 2.23% | p = 0.0344 | 2.3× |

Fastest: **`large-v3-turbo`**.

### Declared deviation

**Recommendation: adopt `large-v3-turbo`, not `small`.**

This is a **deviation from pre-registration and is declared as one.** The pre-registered rule's
output is reported above in full and has not been hidden, edited, or retro-fitted. The reasons
for departing from it:

1. `small` cannot be shown to beat the incumbent on any measured axis.
2. `large-v3-turbo` **can** — detectably better WER (p = 0.0212), and 93.3% vs 70.0% brand
   recall on the post-hoc measure.
3. It is statistically indistinguishable from the outright best model (p = 0.6994) at 3.6× the
   speed.
4. At 4.7× realtime a 15-minute video takes roughly 3.2 minutes to transcribe against 0.9
   minutes for `base` — a real cost, but a tolerable one for a batch-oriented B2B tool, and far
   from `large-v3`'s 11.5 minutes.

**The honest counter-argument, recorded rather than buried:** the WER gain from `base` to
`large-v3-turbo` is 1.22 points on 1,887 words from a 12-clip sample, and the brand-recall gain
is substantially carried by one speaker. A reviewer could reasonably argue that `base` should
stay, and that the switching cost is not justified by the size of the effect. That position is
defensible on this evidence. It is rejected here because the brand-name failure mode is
specifically the one this product cannot tolerate — but the argument is close, and pretending
otherwise would be dishonest.

**Adopted 01 Sep 2026.** `pipeline/audio_module.py:56` now runs `large-v3-turbo`, with the
measured justification written into the code beside it. The full 12-video corpus was
re-transcribed (32.4 min of compute; audio was already on disk). The re-labelling cost that
made adoption look expensive was then measured rather than assumed, and turned out to be
**zero** — see §5. Full suite re-run after the swap: **279 passing**.

The pre-registered rule's own output (`small`) is reported above unedited. It was not adopted,
and the reasons are argued rather than assumed.

---

## 7. Threats to validity — as declared, plus what actually bit

Pre-registered in `CANDIDATE_MODELS.md` §8. Assessed honestly after the fact:

| Threat | Declared? | What actually happened |
|---|---|---|
| 12 clips is few units | yes | **Bit hard.** Seven of eleven comparisons against `base` were non-significant. |
| 8.7 min is a small sample | yes | **Bit.** Differences under ~1 WER point were not resolvable. |
| Clean studio audio | yes | **Bit, and productively.** The one accented speaker produced nearly the whole size effect. |
| Proper nouns over-represented | yes | Became §4 — the most product-relevant finding. |
| Boundaries not evaluated | yes | Measured separately in §5. Confirms switching is not free. |
| Adoption cost not free | yes | §5. Measured after adoption: boundaries moved on 65.9% of labels, but content survived on 98.2% and **no re-labelling was needed**. The pre-adoption estimate was wrong. |
| — | **no** | **The decision rule itself was mis-specified.** Not anticipated. §6. |

The last row is the one that matters. Pre-registration is supposed to constrain the analyst, and
here it worked exactly as intended — it forced the flaw into the open instead of letting the
adopted model be chosen after the fact and justified backwards.

---

## 8. What this bench does not answer

- **Whether a WER win produces a downstream sentiment win.** Untested. It requires re-running
  the transcript channel on new transcripts and re-scoring against labels. Declared as an open
  question in §9 of the pre-registration and it remains open.
- **Whether `min_duration = 3.0 s` and `MAX_MERGE_GAP = 2.0 s` still hold** under different
  segmentation. Both were tuned on `base` output; §5 shows segment counts range 170–201.
- **`distil-whisper`** was excluded on scope, not merit. Still an open lead.
- **`faster-whisper`** (CTranslate2) would cut runtime on the *same* weights. If
  `large-v3-turbo` is adopted and 4.7× proves too slow, this is the first thing to try — it
  cannot change accuracy, only speed.
- **Generalisation beyond studio-recorded English tech reviews.** Nothing here supports it.

---

## 9. Bench integrity

- Ground truth typed by the project author from audio alone, before seeing any model output.
  Rules fixed in `TYPING_GUIDE.md` beforehand.
- `report_whisper.py` and its 25 unit tests were written **before `ground_truth.json` existed**,
  so the metric could not be tuned to a result. Verified: the script refuses to run without
  ground truth.
- Normalisation is OpenAI's own, not hand-rolled — removing a degree of freedom that could
  otherwise have been adjusted after seeing results.
- A property of the bootstrap found during testing and documented in code: against a *uniform*
  difference across all 12 clips it degenerates into a sign test and reports significance for
  very small effects. Per-clip win counts are printed alongside every comparison so this is
  visible rather than hidden.
- One analysis (§4) is post-hoc and labelled as such in the file that produces it, in this
  document, and in its own output header.
- Full suite: **279 passing** as of 01 Sep 2026.
