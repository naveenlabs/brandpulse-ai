# Facial bench v2 — pre-registration

**Written 03 Sep 2026, before any frame was sampled and before any label was
collected.** Nothing below was decided after seeing a result. Corrections, if any
are needed, are appended as dated amendments at the end and never edited into the
body — the same discipline `CANDIDATE_MODELS.md` used for v1, where six such
amendments were needed and all six are still visible.

---

## 1. Why v2 exists

v1 (`../FACIAL_MODEL_ANALYSIS.md`, 03 Sep 2026) scored six detectors and nine
emotion classifiers and reached a clear negative result: **no emotion model beat
an always-NEUTRAL constant**, and the best assemblable pipeline (46/77) was
statistically indistinguishable from the same detector with a fixed NEUTRAL label
(49/77, p=0.4531).

That result stands. v2 does not re-litigate it. v2 exists because v1's ground
truth had four defects that v1 itself documented and could not fix from the data
it had:

| # | v1 defect | Where v1 admits it | What v2 does |
|---|---|---|---|
| 1 | **One video, one face.** Every number came from `1VjPETN3m6U`. | §11 | 15 videos, 8 speakers |
| 2 | **Zero NEGATIVE labels.** The reviewer was never negative, so the anger question was *unanswerable*. | §2.1, §9.4 | corpus deliberately includes 5 critically-framed reviews |
| 3 | **Selection effect.** The 44 expression labels were 43 of §9's 46 mismatches + 1 of 11 matches — selected on the incumbent's errors. | §2.3 | uniform random sample, seeded, drawn before any model runs |
| 4 | **Labels derived from prose,** transcribed out of a review written for another purpose. | §2 | labels collected directly, one frame at a time |

v2 is therefore **a new ground truth for the same question**, not a new set of
candidate models. The candidate set is deliberately unchanged (§6) so that v1's
numbers and v2's numbers are directly comparable.

---

## 2. The question

> On real product-review footage, from speakers no model was tuned on, does any
> facial-emotion model beat a constant — and is genuine anger detected when it is
> actually present?

Three sub-questions, each with a stated success condition fixed here:

- **Q1 (replication).** Does v1's negative result hold on 8 speakers instead of 1?
  *Answered by:* Bench B accuracy vs the majority-class constant, on the dev set.
- **Q2 (anger).** When a human labels a frame angry or frustrated, does any model
  say so? *Answered by:* per-class recall on the NEGATIVE-anger label, reported
  with its sample size. **If the collected labels contain fewer than 20 anger
  frames, Q2 is reported as underpowered and no claim is made either way.**
- **Q3 (generalisation).** Does whatever wins on dev still win on speakers never
  looked at? *Answered by:* one scoring pass on the holdout, run once, at the end.

---

## 3. Corpus

All 15 videos in `corpus.py`, 184.8 minutes, 8 distinct on-screen reviewers.
Every field there was read from YouTube on 03 Sep 2026 and is quoted verbatim.

Twelve had been downloaded audio-only for `vocal_bench`; `acquire.py` fetched the
video track and extracted frames at 1 fps using the pipeline's **own**
`downloader.extract_frames`, not a reimplementation. v1 Amendment A3 is the
reason: benching a configuration the pipeline does not run invalidated a complete
sweep once already.

`tone_hint` in `corpus.py` records how each video's *title* frames the product.
It is a sampling aid and an argument that this corpus should contain criticism
where v1's did not. **It is never a label and never evidence.**

---

## 4. Sampling

Fixed here, before the sample was drawn.

- **40 frames per video, 15 videos, 600 frames.** Equal per video rather than
  proportional to duration, so no speaker dominates the pooled estimate.
- **Uniform random without replacement** within each video, over every extracted
  frame, seed **20260903**. No stratification by content, no exclusion of
  b-roll, no pre-filtering by any detector. A frame with no face in it is a
  legitimate draw and is exactly what Bench A needs.
- **Presentation order is shuffled across videos** with the same seed, so the
  rater never labels one video as a block. Judging a still without its
  neighbours is what the per-frame model does, so it is the honest comparison.
- **48 re-test frames (8%)** are drawn from the 600 and shown a second time, at
  a separated position in the order. The rater is not told which. See §5.3.

Total presentations: **648**.

---

## 5. What is collected

### 5.1 Two judgements per frame

**(a) Is a human face clearly visible?** — yes / no / unsure.
Any real human face counts, including a face on a screen within the shot, because
that is what a detector is being asked to find.

**(b) If yes, the expression of the largest face.** Only the largest, because
the pipeline keeps one label per frame. Options:

| Button | Maps to (primary) | Rationale |
|---|---|---|
| Happy / pleased | POSITIVE | |
| Neutral / just talking | NEUTRAL | the expected majority class in review footage |
| **Angry / frustrated** | NEGATIVE | **Q2 depends on this being separable from the next row** |
| Sad / disappointed | NEGATIVE | v1 §9.1 found this crowding out anger; they must be distinguishable |
| Surprised | *see §5.2* | |
| Unsure | abstain | |

Anger and sadness are separate buttons **because the project's standing
observation is precisely that these two get confused** (v1 §9.1: sadness beat
anger for six of nine models, and 2:1 for the incumbent). Collapsing them into
one NEGATIVE button would destroy the only evidence that could test it.

Disgust is deliberately **not** offered. It is rare in review footage and humans
rate it unreliably; a button nobody can use adds noise and slows every frame.
Models that emit `disgust` still map to NEGATIVE on the model side, as in v1.

### 5.2 The surprise mapping is decided after collection, and both are reported

v1 carried two mappings (`THREE_CLASS` and `THREE_CLASS_SURPRISE_NEUTRAL`)
because surprise is genuinely ambiguous in valence. Collecting `surprised` as its
own button means **both mappings can be scored on the same labels**. Both will be
reported. Neither is chosen to make a model look better: the primary mapping is
declared **now** to be `surprise → POSITIVE`, matching v1's `THREE_CLASS`, and the
alternative is reported as a sensitivity check.

### 5.3 Intra-rater reliability, and why it is the most important number here

The 48 re-test frames measure **how often the rater agrees with themselves** on an
identical image seen twice.

This sets a **ceiling**. If a human labelling the same still twice agrees only
*r* per cent of the time, no model can be expected to exceed *r*, and a model
scoring near *r* is at the practical limit of the task rather than merely
mediocre. v1 had no such ceiling and therefore could not distinguish "the models
are bad" from "the task is ill-posed on single frames". **Both readings are
consistent with v1's result, and this is the measurement that separates them.**

Reported as raw agreement and Cohen's κ, with n. It is reported **whatever it
says**, including if it is embarrassingly low, in which case it becomes the
headline finding and the model comparison becomes secondary.

### 5.4 Blinding

The labelling tool shows **no model output of any kind** — no prediction, no box,
no confidence, no v1 label. It shows a frame and buttons. The rater has not seen
per-frame predictions for 13 of the 15 videos, and the two they have seen
(`1VjPETN3m6U`, `JpN1DQdV4G4`) are forced into the dev set for that reason (§7).

---

## 6. Candidates

**Unchanged from v1, deliberately.** Six detectors and nine classifiers, the same
`candidates.py` interface, the same `retinaface` crop source, the same
three-class mapping. v2 changes the *ground truth*, so holding the candidate set
fixed is what makes v1 and v2 comparable. Adding models here would confound the
two changes.

Degenerate baselines are scored as candidates exactly as in v1: always-NEUTRAL,
always-POSITIVE, always-NEGATIVE, always-face, never-face.

---

## 7. The dev / holdout split

Drawn **by speaker, never by video.** Five videos are Marques Brownlee and four
are Mrwhosetheboss; a split drawn on videos would put the same face on both sides
and the holdout would measure nothing. `vocal_bench/SPEAKER_NORM_RESULT.md`
established held-out *speakers* as this project's standard and this follows it.

**Forced into dev, on contamination grounds, not preference:** `1VjPETN3m6U`
(Jon Adams) and `JpN1DQdV4G4` (Seth Fowler). Both were analysed in v1; per-frame
and per-segment results for them have already been read. A video whose results
have been seen cannot serve as a holdout.

**Rule for the rest,** applied by `sample.py` with seed 20260903: shuffle the six
remaining speakers; take them in order into the holdout until **at least three
distinct speakers** and **at least 25 per cent of labelled frames** are held out.
Three-speaker minimum is required so the holdout measures generalisation across
faces rather than luck on one.

**The holdout is scored exactly once, at the end, after every dev decision is
final and written down.** If a dev decision is revised afterwards, the holdout is
burned and the fact is reported.

---

## 8. Metrics

Imported from `transcript_bench/metrics.py`, not reimplemented:

- Accuracy with **Wilson 95% intervals**.
- **Exact McNemar** for paired comparisons, with `min_attainable_p` reported so a
  non-significant result on few discordant pairs is not read as equivalence.
- **Macro-F1**, because the label distribution is expected to be
  neutral-dominated and accuracy alone will hide per-class failure.
- **Per-class recall**, reported with n per class. Q2 lives here.

**Abstentions ("unsure") are scored as wrong for the model, never dropped.** A
model must not gain accuracy by declining to answer. Frames where the *rater*
answered "unsure" are excluded from the expression set and counted separately —
that is a property of the frame, not of any model.

---

## 9. Adoption rule, declared before results

**Detector.** No change is proposed. `yunet` was adopted in v1 on the strength of
a measurement and this bench does not re-open it. If v2's Bench A contradicts v1
on 8 speakers, that is reported as a finding and the adoption is revisited in a
separate, explicit decision.

**Emotion model.** A model is adopted only if **all four** hold:

1. It beats the majority-class constant on the **dev** set at p < 0.05 (exact
   McNemar), **and**
2. its macro-F1 exceeds the constant's, **and**
3. it does not invent NEGATIVE on more than 15 per cent of rater-verified
   neutral frames, **and**
4. it repeats (1) on the **holdout**.

Condition 3 exists because the deployed channel's worst measured behaviour was
calling **38 of 38** verified-neutral segments negative (v1 §9.3). A model that
beats a constant on average while inventing negativity is not fit for this
system's purpose, which is deciding whether a review is authentic.

**If no model satisfies all four, nothing is adopted and that is the result** —
as in v1, where nothing was adopted. A bench that adopts nothing, with the rule
written down first, is evidence. The same outcome without a rule is an anecdote.

**Separately, and regardless of the above:** if the channel is again shown to be
at or below a constant, the orchestrator down-weighting named in v1 §12.1 is
implemented, with its own before/after in the shape of
`vocal_bench/DAMPING_FIX_RESULT.md`. That work is *justified* by this bench but
is not conditional on which model wins.

---

## 10. Threats to validity, named in advance

1. **A single rater.** No inter-rater agreement is available, so §5.3's
   intra-rater figure is the only reliability estimate. It is a ceiling, not a
   substitute for a second rater, and the write-up must say so.
2. **The rater is the project author,** and has read v1. Mitigated by blinding
   (§5.4), by random presentation order, and by forcing the two seen videos into
   dev — not eliminated.
3. **Single stills lack context.** A human judging one frame has less information
   than a human watching the video. This *matches* what the per-frame model sees,
   so it is the right comparison for the model, but it means these labels are not
   a gold standard for "what the speaker actually felt".
4. **Anger may still be rare.** Critically-*titled* reviews need not contain
   visible anger; presenters stay affable while being negative in words. §2's Q2
   floor of 20 frames exists for exactly this, and the honest outcome may again
   be "not measurable here".
5. **Frames are 1 fps stills,** so peak expressions between samples are missed by
   both rater and model equally.
6. **Eight speakers is still small,** and all are professional presenters on
   camera. Nothing here generalises to consumer-recorded video.
7. **Class imbalance.** Neutral is expected to dominate. Macro-F1 and per-class
   recall are pre-committed (§8) so a high-accuracy, single-class model cannot
   look good.
8. **Re-test frames are shown in the same session,** so §5.3 measures
   within-session consistency, which is an *upper* bound on true reliability.

---

## 11. Reproducibility

- Seed **20260903** for sampling, ordering, re-test selection, and the split.
- The sample manifest is written to `sample.json` **before** labelling and is not
  regenerated afterwards.
- The candidate set, crop detector and mapping are v1's, unchanged.
- Every number in the write-up must be re-derivable by a `verify_claims.py` in
  this directory, as v1's 305 claims are.
- Commands are recorded in the write-up.

---

## Amendments

*(none yet — appended here, dated, if the protocol has to change)*
