# baseline_bench — PROTOCOL

**Pre-registration. Written 06 Sep 2026, before any segment was sampled, any clip
was cut, any rating was collected and any baseline was run.**

Amendments are appended at the bottom with a date and a reason. Nothing in the
body above the amendment log is edited after the first rating is collected.

This is item **6** of the project's work plan — *"Text-only
baseline vs 4-channel"*, listed there as *"Answers RQ1 + RQ2, currently
unanswerable."*

---

## 1. The question, and why it is the last one worth asking

Six components of this system have now been benched: five channels plus the
controller. Every one of those benches asked the same shape of question —
*"which model is best for channel X?"*

Not one of them asked whether channel X should exist.

That is the gap. The entire premise of this project is the sentence:

> Comparing four independent channels reveals brand-authenticity signal that
> reading the transcript alone does not.

**That sentence has never been tested.** It is asserted in the Introduction, it
motivates the Design chapter, and it is the reason the system has four channels
instead of one. It is, at present, an assumption wearing the clothes of a finding.

It is also, on this project's own measurements, in real doubt:

| channel | measured accuracy | source |
|---|---:|---|
| comments | 78.7% | `comment_bench/v2/HUMAN_GROUND_TRUTH_EVALUATION.md` |
| transcript | 67.8% | `transcript_bench/` |
| vocal | 48.9% held-out | `vocal_bench/VOCAL_MODEL_ANALYSIS.md` |
| facial | 34.2%, **below an always-NEUTRAL constant (67.5%)** | `facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md` |

Two of the four channels are at or below chance for their task. A system that
averages a good signal with two bad ones can easily be worse than the good signal
alone. That is not a rhetorical worry; it is the default expectation from the
numbers above, and this bench exists to find out.

### 1.1 Both answers are publishable, and that is the point

This protocol is written so that the negative result is as reportable as the
positive one, and it is declared **now**, before the data exists, that:

- **If the 4-channel system wins**, the design premise is evidenced rather than
  argued, and §5.4 of the report stops resting on citations.
- **If the text-only baseline wins**, the finding is that *an LLM-orchestrated
  multi-channel architecture is capped by its weakest channel, and adding weak
  channels to a strong one destroys signal.* Framed generally that is a
  contribution about orchestration architectures, not a bug report about this
  prototype. The project's work plan already
  anticipates exactly this framing.

Neither outcome will be reported as a surprise, and neither will be reported as
a disappointment. The commitment made here is that the losing outcome is written
up with the same detail as the winning one.

---

## 2. Research questions

**RQ1 — Does the four-channel system track human authenticity judgement better
than a text-only baseline built on the same controller?**

**RQ2 — What does each additional channel contribute?** Specifically, is the
facial channel — measured below a constant in `facial_bench/v2/` — a net
positive, a net negative, or inert when embedded in the full system?

**RQ3 (secondary) — What is the human ceiling on this task?** Four raters make
this measurable for the first time in this project. `facial_bench/v2/` could
only estimate a *self*-consistency ceiling from hidden duplicates (87.5%,
κ=0.804, one rater). Here both are available: between-rater agreement and
within-rater consistency.

---

## 3. What is being compared

Five systems. All produce **one score per segment** on the same scale, so all
five go through an identical scoring path.

| id | what it is | channels | LLM? |
|---|---|---|---|
| `four_channel` | the deployed pipeline, facial populated | transcript, vocal, facial, comments | yes |
| `three_channel` | the pipeline **as it actually ran on this corpus** — facial `none detected` | transcript, vocal, comments | yes |
| `text_only_llm` | **the baseline that threatens the design** | transcript text only | yes |
| `transcript_label` | naive single-channel reference, no LLM | transcript sentiment label | no |
| `constant` | degenerate reference | none | no |

### 3.1 Why `text_only_llm` is built the way it is

The weak version of a text-only baseline is "transcript sentiment label", and it
is included as `transcript_label` — but it is a straw man, and a bench that beat
only the straw man would prove nothing.

The stronger comparison addresses the direct alternative to the multi-channel design:

> *"Why not just give the transcript to the LLM and ask it?"*

So `text_only_llm` is exactly that. **Same model** (`llama3.1:8b`), **same
`temperature: 0`, same `seed: 42`, same `num_ctx: 4096`**, same JSON output
contract, same parsing and coercion path. The *only* difference from
`four_channel` is that its payload carries the transcript text and nothing else.

If the multi-channel design has value, it must beat this. Anything less is not a
fair test.

### 3.2 Why `three_channel` is in the set

`facial_bench/v2/` established that no facial emotion model beats an
always-NEUTRAL constant, and that the deployed one *manufactures* negativity —
it calls 33.8% of verified-neutral held-out frames NEGATIVE. It is down-weighted
(`FACIAL_CHANNEL_RELIABILITY = 0.342`) but not removed.

`three_channel` is the same system with that channel absent. The difference
between it and `four_channel` is the facial channel's **net contribution in
situ**, which is RQ2 and which no previous bench has measured. `facial_bench`
measured the channel against frame labels; this measures whether it helps or
hurts the number a user reads.

### 3.3 Degenerate references, and what they are for

`constant` answers 0.0 for every segment. It **must** score ρ = 0.000 by
construction. It is present for the same reason `always_zero` and `always_flag`
were present in `controller_bench`: a metric that a constant can score well on
is the wrong metric, and the only way to prove the metric is sound is to publish
the constant's score next to everyone else's.

If `constant` scores anything other than ~0, this protocol is broken and the
result is void.

---

## 4. The test set

### 4.1 Source

The same 12-video corpus every other bench in this project uses
(`transcript_bench/corpus/`, re-transcribed with `large-v3-turbo` on 01 Sep
2026), restricted to the **481 segments** cached in
`vocal_bench/ab_cache/conflict_after_nodamp/`. Those are byte-for-byte the
inputs the deployed pipeline produced, and reusing them means this bench's
channel values are identical to `controller_bench`'s.

Nothing is re-transcribed. No sentiment is recomputed. No comment is re-fetched.

### 4.2 The facial channel is filled from an existing cache, not re-run

The 481 segments carry `facial_emotion: "none detected"` in `controller_bench`,
because no frames had been extracted for those videos **at the time that corpus
was built**. Frames exist now — 9,125 of them across the 12 videos — and
`facial_bench/v2/ab_cache_facial/` already holds the deployed pipeline's
per-segment facial output for all 12.

Measured coverage over the 481, recorded here before sampling:

| facial value | segments |
|---|---:|
| no face detected | 152 |
| neutral | 147 |
| happy | 84 |
| sad | 52 |
| angry | 21 |
| fear | 19 |
| surprise | 6 |

`four_channel` uses these. `three_channel` uses `"none detected"` throughout.
DeepFace is **not** re-run: doing so would introduce a second source of facial
values into a project that already has one, for no gain.

### 4.3 Speaker split

Unchanged from `transcript_bench` and `vocal_bench`, so holdout speakers stay
unseen across every bench in this project:

- **Selection (8 videos):** Marques Brownlee, Mrwhosetheboss
- **Holdout (4 videos):** The Tech Chap, ShortCircuit, Dave2D, Jeremy Fragrance

Headline results are reported on **both** splits, separately, and the holdout
number is the one that counts.

### 4.4 Sampling rule, fixed before any clip is cut

- **10 segments per video × 12 videos = 120 unique segments.** Balanced by video,
  which is a property of the data and not of any model's output.
- **Random within video, seeded 42.**
- **Deliberately NOT stratified on any channel label, any conflict score, or any
  model's prediction.** `vocal_bench/cut_clips.py` established this rule and the
  reason holds here: sampling on a model's output biases the test set toward or
  away from that model's failure modes. The natural class balance is whatever it
  is, and it is reported.
- **Duration window 1.5–15.0 s**, matching `vocal_bench`. Below 1.5 s there is
  too little to judge; above 15 s the rating task becomes a different task.
- **Near-silent segments rejected** (RMS < 0.005). A rater cannot judge a person
  from silence, and forcing a rating there manufactures noise and calls it data.

### 4.5 Hidden duplicates

**30 of the 120 unique segments are presented a second time**, at a different
position in the running order, giving **150 items per rater**.

Raters are not told this. The duplicates measure within-rater consistency, which
sets an upper bound on what any system can score. `facial_bench/v2/` used 48
hidden duplicates for exactly this and it was the single most useful number that
bench produced — it is what turned "the models are bad" into "the models are bad
*relative to a measured ceiling of 87.5%*".

### 4.6 Rating order

Independently shuffled **per rater**, from four different seeds (42, 43, 44, 45),
so that no ordering effect is shared across raters and a fatigue effect at
position 140 does not land on the same segment for everyone.

---

## 5. The human ground truth

### 5.1 The raters

**Four**, including the project author. This is the first bench in this project
with more than one rater.

The author's own ratings are collected **first and independently**, before any
other rater's file is opened, and the author's split is reported separately in a
sensitivity check (§8.4). The author is not blind to the project; the other three
raters are not told what the system does, which channels exist, or what the
scores mean.

### 5.2 What a rater sees

Per item, and nothing else:

- the **audio** of the segment (which carries the words, so the words are not
  withheld — a human judging genuineness naturally hears them)
- the **1-fps frames** spanning that segment, as a filmstrip

That is precisely the raw material the pipeline itself receives. The comparison
being made is *"can four automated channels approximate what a human gets from
the same audio and the same frames?"*, so giving the human more or less than the
pipeline would make the comparison meaningless in one direction or the other.

**Never shown:** any channel label, any conflict score, any system output, any
other rater's answer, the video title, the channel name, or the brand.

`verify_page.py` checks these absences mechanically rather than by review, in the
same way `vocal_bench/verify_page.py` does. A property asserted by reading the
code is not a property.

### 5.3 The question, and the scale

One question per item:

> **"Is this person being genuine here?"**

| key | label | hint |
|---|---|---|
| 1 | Clearly not genuine | forced, scripted, over-sold, doesn't mean it |
| 2 | Probably not genuine | something is off |
| 3 | Can't tell / neutral | plain delivery, nothing either way |
| 4 | Probably genuine | sounds like they mean it |
| 5 | Clearly genuine | unmistakably sincere |
| 0 | **Unratable** | can't hear it, can't judge it, no basis |

`0` is a first-class answer, not a cop-out. Forcing a rating on an unratable item
manufactures noise. Items rated `0` are excluded from scoring and their count is
reported per rater.

### 5.4 How ratings become ground truth

The ground-truth value for a segment is the **mean of the ratings from all raters
who did not mark it unratable**, on the 1–5 scale.

Not a majority vote: the scale is ordinal with a meaningful middle, so a
2/2/4/4 split should land at 3, not at an arbitrary one of the four.

Segments where **fewer than 3 raters** gave a usable rating are dropped from the
primary analysis, and the count dropped is reported.

### 5.5 Ground truth is never derived from any system's output

Stated explicitly because it is the rule most easily broken by accident, and
because step 2 of the bench method (README) requires it: no rater sees any channel label or any
score, the sample is not stratified on any prediction, and no system's output is
consulted at any point in producing the labels.

---

## 6. Metrics

Let `h(s)` be the mean human rating of segment `s` (1–5, higher = more genuine),
and `c(s)` a system's conflict score for that segment (0–1, higher = more
conflict, so lower should mean more genuine).

**P1 (primary) — Spearman ρ between `h(s)` and `−c(s)`.**

Rank correlation, not Pearson: the human scale is ordinal, the systems' scores
are known to be heavily quantised (`controller_bench` §5 measured the controller
emitting a handful of discrete values, mostly thirds and quarters), and a linear
correlation over a quantised predictor against an ordinal target would be
measuring the wrong thing. Ties get average ranks.

Reported with a **bootstrap 95% CI over segments** (10,000 resamples, seed 42).

**P2 — the same, restricted to the holdout speakers.** The number that counts.

**P3 — paired comparison of `four_channel` against `text_only_llm`.** Two
correlations on the *same* segments against the *same* ground truth are dependent
samples, so the comparison uses **a paired bootstrap on the difference
`ρ_four − ρ_text`** (10,000 resamples, seed 42), reporting the CI of the
difference and the fraction of resamples in which `four_channel` wins.

A difference whose 95% CI includes zero is reported as **no detected
difference**, never as a win for either side.

**P4 — the facial channel's net contribution:** `ρ_four − ρ_three`, same paired
bootstrap. This is RQ2.

**P5 (human ceiling) — leave-one-rater-out.** For each rater, Spearman ρ between
that rater's ratings and the mean of the other three, averaged over the four.
This is the ceiling: it is how well a human predicts other humans on this task,
and no system should be expected to beat it.

**P6 (rater agreement) — Krippendorff's α** on the ordinal scale across all four
raters, plus **within-rater ρ on the 30 hidden duplicates** for each rater
individually.

All statistics are implemented by hand in `stats.py` and unit-tested against
values computed independently, following the precedent set by
`controller_bench/stats.py` and `vocal_bench/report_bench.py`. No metric is
imported from a library whose behaviour on ties or on small samples has not been
checked here.

---

## 7. Fairness

Identical for every candidate, no per-system tuning:

- Same 120 segments, same channel values, same order of evaluation.
- Same controller (`llama3.1:8b`), same `temperature: 0`, `seed: 42`,
  `num_ctx: 4096` for all three LLM systems.
- Same JSON contract and the same `_coerce_result` path, so a malformed response
  degrades identically whichever system produced it.
- Same ground truth, produced once, before any system was run.

`controller_bench` Amendment A1 is the cautionary precedent: a difference in
`num_ctx` that nobody had thought of made an entire sweep unfair and it had to be
thrown away and re-run. `num_ctx` is therefore pinned explicitly here rather than
left to the allocator.

### 7.1 Down-weighting is left ON

`VOCAL_ONLY_CONFLICT_WEIGHT = 0.489` and `FACIAL_ONLY_CONFLICT_WEIGHT = 0.342`
stay active for `four_channel` and `three_channel`. They are part of the deployed
system, and the question is whether *the deployed system* beats a text-only
baseline, not whether some hypothetical un-damped variant does.

A sensitivity run with damping disabled is reported in §8.5 as a secondary
result, not as the headline.

---

## 8. Decision rules, fixed in advance

### 8.1 The primary decision

On **P2 (holdout)**, using **P3 (paired bootstrap)**:

- **`four_channel` wins** if its ρ exceeds `text_only_llm`'s and the 95% CI of
  the difference excludes zero. → *The multi-channel design is supported by
  evidence on this project's own data.*
- **`text_only_llm` wins** under the mirror condition. → *The design is not
  supported; the finding is the weakest-channel result of §1.1, reported as a
  contribution.*
- **Neither**, if the CI includes zero. → *No detected difference on this sample.*
  Reported as such, with the sample size and the width of the interval, and
  **not** rounded into a win for the incumbent design.

The third outcome is the most likely one at n=120 and it is written down here so
that it cannot later be presented as a disappointment or quietly upgraded.

### 8.2 What is NOT a decision rule

No channel is removed from the pipeline on the strength of this bench alone, and
no threshold is retuned because of it. This bench measures; it does not
refactor. Any change to the pipeline arising from it is a separate, separately
documented decision with its own before/after numbers (step 7 of the bench method, README).

### 8.3 Power floor

If **fewer than 90** of the 120 segments survive §5.4 (three usable ratings), or
if **fewer than 30** holdout segments survive, the holdout result is reported as
**underpowered** and the primary decision is deferred to the full-sample result
with that limitation stated in the headline, not in a footnote.

`controller_bench` §7's Q4 floor is the precedent: it was declared at 20 of 24,
the data came in at 19, and Q4 was reported as underpowered at its own cost. The
same applies here.

### 8.4 Author-bias sensitivity check

P1 and P2 are recomputed with the author's ratings excluded entirely. If the
direction of the primary decision changes when the author is dropped, the result
is reported as **author-dependent** and that becomes the headline finding rather
than a caveat.

### 8.5 Secondary sensitivity runs

Reported in full, none of them able to change the primary decision:

- damping disabled (§7.1)
- `constant` and `transcript_label` scored on the same path (§3.3)
- P1 recomputed with the 30 duplicate presentations averaged vs. first-presentation-only
- per-video ρ, to check the result is not carried by one video

---

## 9. Known threats to validity, stated before the result

1. **The comment channel is a constant on this corpus.** All 12 videos are
   `POSITIVE`. The comment channel therefore contributes no *between-segment*
   variance — though it still creates conflicts, since a POSITIVE crowd against a
   NEGATIVE transcript is a disagreement. This means the bench cannot measure the
   comment channel's discriminative contribution at all, and **any conclusion
   about "four channels" is really a conclusion about three varying channels plus
   a constant.** This is a limitation of the corpus, it is not fixable within the
   time available, and it will appear in the write-up's headline limitations
   rather than at the end.

2. **n = 120 is small.** Detecting a small true difference in correlation at this
   sample size is not realistic. §8.1's third outcome exists because of this.

3. **"Genuine" is a subjective construct.** Four raters is better than one but is
   not a validated instrument. P5 and P6 exist to quantify how subjective it
   turned out to be, rather than to argue that it isn't.

4. **Three of the four raters are recruited by the author** and may be motivated
   to agree with each other or to be agreeable. Blinding (§5.2) is the mitigation;
   it is partial.

5. **The corpus is one genre** — English-language consumer-tech reviews by
   professional presenters, plus one fragrance channel. `facial_bench/v2/` already
   found this genre has almost no negative facial affect (4 anger frames against
   a pre-registered floor of 20). Genuineness may be equally compressed. If the
   human ratings turn out to have little variance, P1 is uninformative and that
   will be reported as the result.

6. **Rating the audio means rating the words.** A rater who hears sincerity in
   the words is partly doing what `text_only_llm` does, which could bias the
   ground truth *toward* the text-only baseline. The alternative — withholding
   the audio — would bias it the other way and would not match what the pipeline
   sees. There is no neutral choice here; the choice made is stated so the
   direction of the bias is known.

---

## 10. Out of scope

- Changing any pipeline code. This bench is read-only with respect to `pipeline/`.
- Re-running DeepFace, Whisper, or any sentiment model.
- Fetching new videos or new comments.
- Any cloud LLM (the project's hard constraint).
- Re-opening the controller choice (`controller_bench`, closed 05 Sep 2026) or
  the facial model choice (`facial_bench/v2/`, closed 04 Sep 2026).

---

## 11. Deliverables

| file | what |
|---|---|
| `PROTOCOL.md` | this file |
| `sample.py` | seeded sampling, clip cutting, filmstrip extraction |
| `build_pages.py` | the four blind rating pages |
| `verify_page.py` | mechanical check that no system output leaks into a page |
| `systems.py` | the five candidates |
| `run_bench.py` | runs all five over the sample, caches every response |
| `stats.py` | Spearman, bootstrap, Krippendorff's α, all hand-written |
| `report_bench.py` | P1–P6 |
| `verify_claims.py` | every number in the write-up recomputed and required verbatim |
| `BASELINE_ANALYSIS.md` | the write-up |

---

## Amendment log

### A1 — 08 Sep 2026 — `transcript_label` was never fully specified

**What the gap is.** §3 lists `transcript_label` as a system and §6 requires every
system to produce "one score per segment on the same scale" (0–1, higher = more
conflict). It never states how `{POSITIVE, NEUTRAL, NEGATIVE}` becomes that
number. The direction is a free parameter, and the protocol left it open.

**Why this is being written now, and the honest ordering of events.** The gap was
noticed while writing `BASELINE_RATER_ANALYSIS.md` §14, and it was noticed
*because* of a diagnostic that had already been computed: across the 119 surviving
segments, transcript-NEGATIVE segments are rated the **most** genuine by the human
panel (h = 4.392, n = 15) and NEUTRAL the least (h = 3.870, n = 75), permutation
p = 0.034. The intuitive mapping — POSITIVE means sincere — has the **wrong sign**
on this data.

That ordering matters and is stated rather than concealed: **the association was
seen before the mapping was fixed.** Choosing a direction now would be selecting a
system's behaviour with knowledge of the answer, which is fitting on the test set,
and it would make `transcript_label`'s score uninterpretable as a reference.

**The amendment.** No direction is chosen. `transcript_label` is replaced by two
separately named degenerate references, both run and both reported:

- `transcript_label_pos_genuine` — POSITIVE → 0.0, NEUTRAL → 0.5, NEGATIVE → 1.0
- `transcript_label_neg_genuine` — the exact inverse

Neither is "the" transcript baseline; they bracket the free parameter and remove
it. They are references in the sense of §3.3, alongside `constant` — present so
the metric's behaviour on a trivial predictor is visible, not as candidates.

**What is unaffected.** `text_only_llm` — the baseline that actually threatens the
design (§3.1) — is fully specified and untouched: same `llama3.1:8b`, same
`temperature: 0`, `seed: 42`, `num_ctx: 4096`, same JSON contract, same coercion
path. The §8.1 primary decision is `four_channel` vs `text_only_llm` and does not
involve `transcript_label` in either form. `four_channel`, `three_channel` and
`constant` are unchanged.

**Precedent.** `controller_bench` Amendment A1 (an unnoticed `num_ctx` difference
that made a sweep unfair) is the reason this project appends amendments instead of
editing protocol bodies. The failure mode there was the same shape: a parameter
nobody had thought to pin.

---

### A2 — 08 Sep 2026 — supplementary statistics added to the rater analysis

§6 names P1–P6. `rater_analysis.py` additionally reports ICC(2,1)/ICC(2,k),
per-rater response-style profiles, order/fatigue correlations, a straight-lining
test against a per-rater shuffle null, and the channel-label diagnostics of
§14 of the write-up.

None of these can change a pre-registered decision, and none is used to select or
tune any system. They are **labelled "not pre-registered" wherever they are
quoted**, in `BASELINE_RATER_ANALYSIS.md` and in `rater_analysis_results.json`.

ICC(2,k) earns its place: the ground truth is a *mean of four raters*, and ICC(2,k)
is the reliability of exactly that quantity, whereas α and pairwise ρ describe
agreement between individuals. Reporting only the latter would understate the
instrument the bench actually uses.

---

### A3 — 08 Sep 2026 — §5.1's rater-naivety claim is false, and was false when written

**What §5.1 says.** *"The other three raters are not told what the system does,
which channels exist, or what the scores mean."*

**What is actually the case.** All three are returning participants from the
mini user-pilot of **02 Aug 2026**, 37 days before these ratings were collected.
`user_pilot/PILOT_FINDINGS.md` records that they reviewed seven dashboard
screenshots and states: *"All 3 people correctly explained the tool's core
purpose with zero coaching — reviewer sincerity/authenticity, comparing spoken
words against face/voice, cross-checking against audience comments."* They had
also seen the terms *Authenticity Score*, *Brand Health Score*, *cross-channel
conflict*, *Flagged* and *Below threshold*.

§5.1 was therefore wrong at the moment it was written. The error was not caught
during pre-registration because the pilot and this bench were treated as separate
pieces of work, and the overlap in participants was never checked.

**Scope of the defect.** It is a failure of *construct-naivety*, not of blinding.
No rater saw any channel label, conflict score, video id, transcript text,
speaker name or brand for any of the 120 segments; `verify_page.py` enforces that
against the built HTML and passes at 778 checks. No answer leaked.

**Direction of the possible bias.** Toward the multi-channel design: a rater
primed to notice word/voice/face mismatch may weight exactly the signal
`four_channel` is built on, inflating `four_channel` relative to `text_only_llm`.
This is the opposite direction from §9.6's declared bias. Both are now on record;
neither is quantified.

**No data is discarded and no analysis is changed.** Discarding it would leave the
bench with one rater. The defect is reported in `BASELINE_RATER_ANALYSIS.md` §2.1
and §16.3, with the two pieces of counter-evidence available (the exposed raters
did not converge on the author, and their ratings show no association with the
vocal or facial channels they were told about).

**Binding change for Item 7.** The user study must screen for and record prior
exposure to this project. Returning pilot participants may not be counted as
naive raters.

---

### A4 — 08 Sep 2026 — `text_only_llm` is coerced on a stripped segment

§3.1 requires `text_only_llm` to use the "same parsing and coercion path" as
`four_channel`. Implementing that literally would be unfair in the baseline's
disfavour, and the reason was not noticed when §3.1 was written.

`orchestrator._coerce_result` down-weights a conflict resting on one weak channel
alone, and it decides that from **the segment's own channel labels** —
`_vocal_is_sole_dissenter` and `_facial_is_sole_dissenter` read the vocal and
facial readings directly, not the LLM's output. Passing the full segment would
therefore adjust the text-only system's score using vocal and facial information
it never saw: multi-channel data leaking into the single-channel control.

**Resolution.** `text_only_llm` runs the *same function* on *its own* inputs — a
segment carrying only `segment_id`, `start_time`, `end_time` and `text`, and no
comment channel. `_channel_valences` then returns `{}` and neither damping
trigger can fire. The coercion path, the clamping, the flag rule and the JSON
contract are all unchanged and shared. Asserted in
`tests/test_baseline_systems.py`, not assumed.

---

### A5 — 08 Sep 2026 — the text-only baseline gets two pre-declared prompts, and its best result counts

**Why.** §3.1 is explicit that `text_only_llm` must be the *strong* version of a
text-only baseline — *"If the multi-channel design has value, it must beat this.
Anything less is not a fair test."* A two-probe smoke test returned
`conflict_score` 0.8 on *"The USB-C cable. And a little insert, which has the
case."* — a plain descriptive sentence — despite the prompt instructing that such
a statement should score near 0.0.

If the baseline calls everything promotional it has no variance, scores rho near
zero for a trivial reason, and `four_channel` beats a straw man. That is a threat
to the primary comparison's validity, not a convenient result.

**What would be cheating.** Re-wording the prompt until the baseline behaves,
then reporting the version that happened to run. §7 forbids per-system tuning.

**What is done instead.** Two prompts are fixed **now, in advance**, both run over
all 120 segments, and **the baseline's better result is the one `four_channel`
must beat** in the §8.1 primary decision:

- `text_only_llm` — the original, as written before any probe was run.
- `text_only_llm_anchored` — identical task and identical JSON contract, with
  explicit calibration anchors at 0.0 / 0.25 / 0.5 / 0.75 / 1.0, a stated base
  rate ("most segments of an ordinary product review are sincere"), and two
  clarifications that follow from the task rather than from any observed score:
  describing features is what a review is, and criticism is evidence of sincerity.

**Timing, stated so it can be judged.** This is declared after seeing two probes
and before seeing any score distribution. It can only help the baseline — the
side that threatens this project's design — so it cannot be a thumb on the scale
for the incumbent. Both results are reported in full whichever wins, and if the
two prompts disagree materially that disagreement is itself reported as a finding
about how much a text-only baseline depends on its wording.

**Unchanged:** `four_channel`, `three_channel`, `constant`, both
`transcript_label` references, the sample, the ground truth, and every metric in
§6.

### A6 — 08 Sep 2026 — the construct the raters used, measured post-hoc

**Why this amendment exists.** §5.3 asked one question — *"Is this person being
genuine here?"* — and §6 correlated the answers against a conflict score. Neither
section states what dimension the raters would actually use to answer it, and the
protocol quietly assumed it was close to the one the pipeline measures. After P1
returned null on every system, the author stated in plain terms how the four of
them had in fact rated: **whether the speaker means what they are saying, with the
positive or negative direction of the content explicitly irrelevant** — sincere
praise and sincere criticism both rated 5, insincere praise rated 1.

That is a claim about the construct, and an unmeasured claim about a construct is
an anecdote. `axis_analysis.py` measures it.

**Status.** Everything in `axis_analysis.py` and `AXIS_RESULT.md` is **post-hoc
and exploratory**. It is not a pre-registered hypothesis, it was specified after
the primary result was known, and it must be read as generating an explanation
rather than confirming one. It is reported separately from `BASELINE_ANALYSIS.md`
for exactly that reason.

**What it must not do, and does not do.** It changes no pre-registered quantity.
P1–P6 stand exactly as reported: the same 119 segments under the same §5.4 rule,
the same ground truth, the same cached LLM responses, nothing re-run and nothing
re-scored. No rating was collected, revised, or re-elicited after the result was
seen — the ratings are frozen as exported, and re-rating on a different question
after seeing a null result would have destroyed the experiment rather than
rescued it.

**The one arbitrary decision, declared.** Collapsing seven FER classes onto a
valence axis requires a call on `surprise`, which is high-arousal and unsigned.
It is mapped +1 in the primary run and 0 in a sensitivity run, both reported. It
occurs on 3 of 119 segments and moves nothing.

**Estimator bias, checked rather than assumed.** §A4 bounds what any rule over
the channel labels could achieve. The obvious estimator — leave-one-out group
means — is **rank-inverting by construction** and produces ρ = −0.4697 on this
data under a permutation null. It is reported only beside that null, and the
conclusions rest on repeated disjoint train/test splits, whose null is centred on
zero (+0.0049). A null band is measured for all three estimators.

### A7 — 08 Sep 2026 — the author briefed the other three raters on the construct

**The fact.** Stated by the author after Amendment A6 was written: the other
three raters were told **by the author, before rating, how to apply the scale** —
specifically that a review counts as genuine when the speaker means it, whether
the content is praise or criticism, and that direction is irrelevant. All four
therefore rated on one explicitly shared definition.

This was not recorded in §5.1, §5.3 or Amendment A3, and it should have been. A3
established that raters 2–4 were not construct-naive because of the 02 Aug 2026
pilot. **A7 is a second and larger departure**: not incidental prior exposure, but
deliberate instruction from a person who is also one of the four raters.

**What it strengthens.** `AXIS_RESULT.md` §1 rests on the author's account of what
the raters were judging. That account now covers all four raters by direct
instruction, not one rater by introspection. The construct is well defined and
was applied uniformly, and the axis finding rests on firmer ground than it did.

**What it weakens, precisely.** Briefing raters on a construct is ordinary and
usually good practice — it is what rater training *is*, and it raises reliability
on purpose. Two things make it a limitation here rather than a method:

1. **The briefer is also a rater.** So §6's Krippendorff α = 0.7296, §7.1's
   ICC(2,k) = 0.9124 and §8's ceiling ρ = 0.8038 measure *agreement after shared
   instruction from a participant*, not independent convergence on a construct.
   Independent raters given only the on-screen scale would likely agree less.
2. **It was not pre-registered**, so it cannot be presented as a designed
   training step. It is reported as what it is: an undocumented procedure
   discovered after the analysis.

**What it does not change.** No rater saw any channel label, score, or system
output — `verify_page.py`'s 778 checks are unaffected, and there is no path from
any system's answers into the ratings. P1's conclusion is unaffected in
direction: every system's CI includes zero, and a ceiling that is too high cannot
turn a null into a win. Every "% of the human ceiling" figure in
`BASELINE_ANALYSIS.md` and `AXIS_RESULT.md` should be read as a **lower bound on
relative performance** — if the true independent-rater ceiling is lower, those
percentages rise.

**Counter-evidence that limits the concern.** §2.1 records that the three briefed
raters agree with **each other** more than with the author: the three lowest
correlations in the matrix are the three involving the author, and dropping the
author *improves* agreement (§10). Being briefed on a construct is evidently not
the same as tracking the briefer's judgements.

**Consequence for Item 7.** The written scale must be the only instruction, it
must be identical for every rater, it must be delivered in writing rather than in
conversation, and the person who wrote it must not rate.
