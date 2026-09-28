# fairness_bench — pre-registration

**Written 12 Sep 2026, before any number in this directory was computed.**

Follows the fixed bench method in the README, and the pre-registration
discipline of `facial_bench/v2/PROTOCOL.md` and
`vocal_bench/SPEAKER_NORM_PREREG.md`. Amendments are appended at the end with a
date and a reason; nothing above the amendment line is edited after the first
number is produced.

---

## 1. What is being tested, and why now

This project **states a bias disclaimer it has never tested**.

`BIAS_CAVEAT` is attached to every report and appears on every surface that
shows a facial-derived score. It says facial emotion recognition has documented
accuracy disparities across skin tone and gender, citing Buolamwini and Gebru
(2018). That citation is real and the caveat is correct to be there. But this
project has never checked whether **its own deployed model, on its own data**,
is worse for some speakers than others — and it has the materials to check.

So the question is in two parts, and they are deliberately separated because one
can be answered today and one cannot:

- **Q1 — does accuracy vary by speaker at all?** Answerable now, from data
  already on disk, with no new labels and no human judgement.
- **Q2 — does that variation track skin tone?** Not answerable without human
  raters attaching a skin-tone label to each speaker. §4 sets out how, and it
  is not run in this pass.

### 1.1 What "worse" means here

For Q1: the spread between the best-served and worst-served speaker, in
percentage points of three-way expression accuracy, on the same model.

A spread is not by itself unfairness — small samples produce spreads. §5.3
declares in advance what would and would not count as a finding.

---

## 2. Data — read-only, nothing new collected

Everything comes from `facial_bench/v2/`, which was itself pre-registered before
a frame was sampled. **This bench adds no frames, no labels and no models.** It
re-cuts an existing result by speaker.

| Artefact | What it is |
|---|---|
| `../facial_bench/v2/sample.json` | The frame sample, drawn by seed `20260903` before any model ran. Carries `speaker` and `split` per frame. |
| `../facial_bench/v2/facial_labels_v2.json` | The human expression labels, collected blind at the frame. |
| `../facial_bench/v2/predictions/*.json` | Every model's per-frame output, including the deployed `deepface_fer`. |
| `../facial_bench/v2/crops/` | The aligned face crops — the exact pixels the models scored. Used only in §4. |

Speakers, as fixed in `sample.json` and **not chosen by this bench**:

- dev: Jon Adams, Seth Fowler, Marques Brownlee, Mrwhosetheboss
- holdout: The Tech Chap, Dave2D, ShortCircuit, Jeremy Fragrance

---

## 3. Method for Q1 — declared before running

1. **Reuse `facial_bench/v2/ground_truth_v2.py` directly.** Do not re-implement
   the mapping or the scoring rule. Re-implementing is how two files that claim
   to measure the same thing quietly stop doing so.
2. Ground truth is `expression_set()` under the **primary** mapping
   (`happy`/`surprised` → POSITIVE, `neutral` → NEUTRAL, `angry`/`sad` →
   NEGATIVE). `expr_unsure` and `face_unsure` are excluded, as there.
3. **A model abstention is scored wrong**, exactly as in v2 §8: a frame the
   rater could read but the crop detector missed is no crop, no reading, no
   channel — which is what the pipeline actually experiences.
4. Group by `speaker`. Report, per speaker: n, correct, accuracy, and the count
   of verified-neutral frames called NEGATIVE.
5. Report the same for the **always-NEUTRAL constant**, because a per-speaker
   number for a model means nothing without the per-speaker number for the
   thing it failed to beat.
6. Report dev and holdout separately **and** pooled. The pooled figure is the
   headline; the split figures are there because the holdout was opened once,
   under seal, in v2, and pooling silently would undo that.

### 3.1 Corroborating strands, already measured elsewhere

Cited, not recomputed. Each is a per-speaker disparity this project has already
found in a different channel:

- **Vocal**: 27.3% (Dave2D) to 65.3% (Marques Brownlee) over 147 clips, pooled
  56.5%, range **38.0 points** — `vocal_bench/SPEAKER_NORM_RESULT.md`.
- **Speech recognition**: `base` 14.78% WER vs `large-v3` 3.48% on the one
  German-accented speaker, a 4.2× difference which produced nearly the whole
  model-size effect — `whisper_bench/WHISPER_MODEL_ANALYSIS.md`. The deployed
  `large-v3-turbo` also scores 3.48%, so this one is already mitigated.

---

## 4. Method for Q2 — declared, and NOT run in this pass

### 4.1 Scale: Monk, not Fitzpatrick

The **Monk Skin Tone Scale** (10 points), because it was built for evaluating
machine-learning systems on people. The Fitzpatrick scale is widely used in this
literature and is the wrong instrument: it classifies **how skin responds to
ultraviolet light**, was developed to dose phototherapy, and compresses darker
tones into fewer categories than lighter ones — which is precisely the region
where a fairness result would live.

Using Fitzpatrick here would import a known measurement bias into a measurement
of bias.

### 4.2 Unit of rating

**The speaker, not the frame.** Eight judgements, not 362. Skin tone is a
property of the person; lighting, white balance and compression vary frame to
frame and would add noise without adding information. Raters see a contact sheet
of that speaker's crops and give one value.

### 4.3 Raters

**Three**, rating independently, with no access to any model output, any
accuracy figure, or each other's ratings. Inter-rater agreement is recorded as
Krippendorff's alpha for ordinal data, and **reported whatever it is** —
including if it is poor, which would itself be the finding.

Disagreements are **not** resolved by discussion. The median is used and the
spread is reported.

### 4.4 Declared before collection

- If alpha is below 0.6, the skin-tone analysis is reported as **inconclusive**
  and no correlation is quoted. Raters who cannot agree on the independent
  variable cannot support a claim about it.
- The correlation reported is Spearman's rho between median Monk value and
  per-speaker accuracy, with n=8 stated beside it every time it appears.
- **A null result is written up in full.** `vocal_bench/SPEAKER_NORM_RESULT.md`
  is the worked example in this project of a rejected hypothesis reported with
  its pre-registered adoption rule intact.

### 4.4a The instrument does not reproduce the scale, on purpose

`monk_rating.html` shows the crops and takes a number from 1 to 10. **It does
not display the ten Monk swatches.** Raters open the official published scale
alongside it and compare against that.

This is deliberate. The swatch values could be transcribed into the tool, but
not verified offline against the official source — and a colour scale
reproduced approximately, inside the instrument that measures colour, would
introduce exactly the error this bench exists to look for. A rating taken
against a near-miss of the scale is worse than no rating, because it looks
like a measurement.

### 4.5 Why it is not run in this pass

The raters available are friends and classmates: non-expert, and not diverse in
the way that matters for this particular judgement. That is a real limitation,
and §6 records it rather than hiding it — but it is not a reason to skip the
step, and the instrument is built and ready in this directory.

---

## 5. Analysis plan, declared before seeing any result

### 5.1 Primary output

A table: speaker × (n, accuracy, NEGATIVE-on-neutral rate) for the deployed
`deepface_fer` and for the always-NEUTRAL constant.

### 5.2 Confidence

Wilson 95% intervals on every per-speaker accuracy. At n≈40 per speaker these
will be wide, and the write-up must show them rather than quoting point
estimates that look more precise than they are.

### 5.3 What counts as a finding

- **A spread worth reporting**: the best and worst speaker's Wilson intervals do
  not overlap. Anything less is reported as "consistent with noise at this
  sample size", in those words.
- **What is not claimed either way**: that any spread found is caused by skin
  tone. That is Q2 and Q2 is not run.
- **What is reported regardless**: the full per-speaker table, including
  speakers that make the deployed model look good.

### 5.4 Adoption rule

This bench **adopts nothing**. There is no model to swap: `facial_bench/v2/`
already established that no emotion model on offer beats an always-NEUTRAL
constant on held-out speakers, and none was adopted. The output of this bench
supports `INCLUSION_ANALYSIS.md` §4.1 and, if Q1 shows a real spread, supports
expanding the caveat to name measured per-speaker variation alongside the cited
literature.

Stating that in advance matters because a bench with no adoption decision is the
easiest kind to quietly bend toward an interesting result.

---

## 6. Limits, pre-registered

Written now so they cannot be softened later.

- **n = 8 speakers.** This is an observation, not a population estimate, and
  will be called an observation everywhere it appears.
- **All eight are professional presenters** filming themselves in good light
  with good audio, in English. A disparity found here is a disparity in the
  easiest conditions this system will ever see.
- **The sample was not designed for this question.** `facial_bench/v2/` drew
  frames to measure expression accuracy, and the speaker mix is whatever the
  corpus happened to contain. Nobody balanced it for skin tone, gender, or
  anything else.
- **Roughly 40 usable frames per speaker**, so every per-speaker interval is
  wide.
- **The raters for §4 are non-expert and not diverse.**
- **Gender is not analysed.** The caveat names skin tone *and* gender; this
  bench addresses neither directly and the second not at all. Recorded as an
  omission, not an oversight.

---

## 7. What this bench will not be allowed to say

- That the system is fair. It cannot show that.
- That the system is biased by skin tone. Without §4 it cannot show that either.
- That eight professional presenters represent anyone.
- Any figure that `verify_claims.py` cannot re-derive from disk.

---

## 8. Verification

`verify_claims.py` re-derives **every** number that appears in
`FAIRNESS_ANALYSIS.md` from the files in `facial_bench/v2/`, and fails if any
claim in the prose has drifted from the data. Same pattern as
`controller_bench/verify_claims.py` (268 claims) and
`facial_bench/v2/verify_claims.py` (463 claims).

A number in the write-up that the verifier does not check is a bug in the
verifier.

---

# Amendments

Appended after the date given. Nothing above this line is edited.

## A1 — 12 Sep 2026, after the primary output of §5.1 and before any write-up

**What happened.** The primary table came back with a 30.7-point spread across
speakers for the deployed model, whose Wilson intervals **overlap** — so by §5.3
that is "consistent with noise at this sample size" and not a finding.

But the same table for the always-NEUTRAL constant came back with a **larger**
spread, 43.8 points, whose intervals **do not** overlap.

That is informative and was not anticipated. The constant's per-speaker accuracy
is nothing but the share of that speaker's frames the rater called neutral — it
is a measure of **how much a given presenter's face moves**, not of any model.
So a large part of any per-speaker difference in the model's accuracy is
inherited from the base rate, not produced by the model treating faces
differently.

A naive fairness reading of the primary table alone would report "30.7-point
spread across speakers" and imply the model is the cause. That would be wrong,
and this bench would have produced exactly the kind of unsupported disparity
claim §7 forbids.

**What is added.** One derived quantity, per speaker:

    lift = accuracy(deployed) − accuracy(always-NEUTRAL constant)

on the same frames for the same speaker. This separates "this speaker is hard
for everything" from "this speaker is hard for *this model*", and it is the
latter that a fairness question is actually about.

**Declared before computing it:** the lift is expected to be negative for most
speakers, because v2 already established the model loses to the constant
overall. What is not known, and is what this adds, is whether the loss is
**evenly spread** or concentrated on particular speakers. A spread in lift is
reported as a finding only under the same §5.3 rule — intervals must part — and
with n=8 stated beside it.

**This is post-hoc and is labelled post-hoc everywhere it appears.** It was
added after seeing the primary result, which is why it is here rather than in
§5, and why it is a description of the data rather than a test of a hypothesis.
