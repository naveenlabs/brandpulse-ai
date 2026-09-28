# baseline_bench — the human ground truth, and how far it can be trusted

**Analysis of the four collected rating sets. 08 Sep 2026.**

Pre-registered in `PROTOCOL.md` (06 Sep 2026, written before any segment was
sampled). Every number below is produced by `rater_analysis.py` and written to
`rater_analysis_results.json`; every statistic it uses is implemented in
`stats.py` and unit-tested in `tests/test_baseline_bench.py` (63 tests).

---

## 0. Headline

**The instrument works. The ground truth is usable. Two things about it will
constrain how P1–P4 can be read, and one of them is severe.**

| | measured | reading |
|---|---:|---|
| Krippendorff's α (ordinal, 4 raters, 119 segments) | **0.730** [0.645, 0.798] | above Krippendorff's 0.667 threshold for tentative conclusions, below 0.800 for firm ones |
| Human ceiling, P5 (mean leave-one-rater-out ρ) | **0.804** [0.734, 0.856] | no system should be expected to beat this |
| Human ceiling on **holdout** speakers | **0.761** | the number that actually governs P2 |
| ICC(2,k) — reliability of the 4-rater mean | **0.912** | the *mean* is a far better instrument than any one rater (ICC(2,1) = 0.723) |
| Segments surviving §5.4 | **119 / 120** (39 holdout) | power floor **met** (§8.3 required ≥ 90 and ≥ 30) |
| Ratings in the top half of the scale (3–5) | **95.1%** of 597 | severe compression — see §12 |
| Segments humans call *not genuine* (h < 3) | **5 / 119 (4.2%)** | 95% CI [1.8%, 9.5%] |

**Three findings outrank the rest.**

1. **The author is the weakest rater, not the most influential one.** `PROTOCOL.md`
   §9.4 pre-registered the opposite worry — that three recruited raters would drift
   toward the author. The data says the reverse: the author is the least
   self-consistent (63.3% exact re-test vs 83–90%), the least agreeing with
   everyone else, and **dropping them raises α from 0.730 to 0.786.** The ground
   truth itself barely moves (ρ = 0.978), so §8.4 passes — but the direction of
   the effect is the opposite of the one that was guarded against.

2. **The corpus is 95% "genuine".** Only 5 of 119 segments are judged
   not-genuine on balance. The bench is therefore not a balanced discrimination
   task; it is a rare-signal detection task, and P1 will be a correlation
   dominated by rank movement inside the 3-to-5 band.

3. **Human genuineness runs *toward* negative transcript sentiment, not away from
   it.** Segments the transcript channel labels NEGATIVE are rated the **most**
   genuine (h = 4.39), NEUTRAL the least (3.87); permutation p = 0.034. The naive
   "POSITIVE = sincere" mapping is not merely weak here, it has the **wrong
   sign**. This has a direct consequence for the `transcript_label` system, which
   `PROTOCOL.md` never fully specified — see §11.

A fourth finding is a defect rather than a result, and it is recorded at the top
because it qualifies everything below it: **`PROTOCOL.md` §5.1's claim that the
three non-author raters were naive to the system is false.** All three took part
in the August dashboard pilot, 37 days earlier, and already knew the system
judges sincerity by comparing words against face, voice and comments. The
instrument's blinding is intact and mechanically verified; the raters'
construct-naivety is not. See §2.1 for the direction of the possible bias and the
counter-evidence.

**Nothing here decides RQ1 or RQ2.** This document validates the measuring
device only. The systems were subsequently built and run —
`BASELINE_ANALYSIS.md` has the result, and it is that **no system tracks this
ground truth**: every 95% CI includes zero and the best reaches 7.2% of the
0.8038 ceiling measured below.

---

## 1. Scope, and why it is separated

`PROTOCOL.md` §6 defines six endpoints. P5 and P6 concern the raters; P1–P4
concern the five systems. This document reports **P5, P6, §5.4, §8.3, §8.4 and
§8.5 only.**

The separation is deliberate and is the right order of work. If the raters had
disagreed at chance, or if every clip had been rated identically, then P1–P4
could not have produced an interpretable number and running them would have
manufactured a result rather than measured one — `PROTOCOL.md` §9.5 anticipates
exactly that and requires it to be reported as the finding. The instrument is
validated first, on its own terms, and the gate is passed before anything is
judged against it.

Supplementary statistics not named in `PROTOCOL.md` §6 — ICC, response-style
profiling, order effects, the straight-lining test, and the channel diagnostics
of §13 — are **labelled as not pre-registered** wherever they appear, here and in
the results file.

---

## 2. Provenance: are these four files what they claim to be?

Checked before any statistic was computed, because a mislabelled export would
corrupt every number downstream and would not announce itself.

| check | result |
|---|---|
| Four files present, schema `{rater, n, answered, complete, answers[]}` | ✅ |
| `complete: true`, 150/150 answered, zero nulls | ✅ all four |
| Every rating in `{0,1,2,3,4,5}` | ✅ 600/600 |
| **File's `(pid, tok)` sequence identical to that rater's own page** | ✅ all four |
| All 120 tokens resolve via `_tokens.json` into `sample.json` | ✅ |
| Exactly 30 repeated tokens per rater, matching `sample.duplicate_uids` | ✅ all four |
| Each rater saw all 120 unique segments | ✅ |

The third check is the one that matters. Each page carries an independently
seeded running order (`PROTOCOL.md` §4.6), so the `(pid, tok)` sequence is a
fingerprint of *which page was rated*. All four files match their own page
exactly, which rules out two people rating the same page, a file being renamed,
or an export being hand-edited in any way that disturbs order. These assertions
live in `rater_analysis.load()` and are re-run by
`tests/test_baseline_bench.py::TestRealRatingFiles`, so they cannot be skipped.

**What provenance does *not* establish:** the exports carry no timestamps, so
there is no per-item response latency and no direct measure of attentiveness.
That is a design gap in `build_pages.py` and it is worth closing before the user
study (Item 7). Attentiveness is therefore inferred behaviourally in §5 rather
than measured. Identity of the raters cannot be verified from the data at all;
what §5–§7 can say is that the four response patterns differ from one another in
ways a single person filling in four files would be unlikely to produce.

### 2.1 A blinding assumption in the protocol that does not hold

`PROTOCOL.md` §5.1 states that *"the other three raters are not told what the
system does, which channels exist, or what the scores mean."*

**That statement is false, and the contradicting evidence is in this repository.**
`user_pilot/PILOT_FINDINGS.md` records that on **02 Aug 2026** — **37 days before
these ratings were collected** — the same three people reviewed seven screenshots
of the BrandPulse dashboard, and that write-up states:

> *"All 3 people correctly explained the tool's core purpose with zero coaching —
> reviewer sincerity/authenticity, comparing spoken words against face/voice,
> cross-checking against audience comments."*

So before rating a single clip, raters 2–4 already knew (a) that the construct
under study is reviewer sincerity, (b) that the system compares words against
face and voice, and (c) that it cross-checks against audience comments. They had
also seen the terms *Authenticity Score*, *Brand Health Score*, *cross-channel
conflict*, *Flagged* and *Below threshold*. This was not noticed when
`PROTOCOL.md` was written and is recorded as **Amendment A3**.

**What is *not* affected.** No rater saw any label, score, video id, transcript
text, speaker or brand for any of the 120 segments — that is enforced
mechanically by `verify_page.py` and re-verified at 778 checks. There is no
leakage of answers. The defect is in the raters' *construct-naivety*, not in the
blinding of the instrument.

**The direction of the possible bias, stated plainly.** A rater who knows the
system looks for word/voice/face mismatch may attend to exactly that mismatch.
That would bias the ground truth **toward** the multi-channel hypothesis — that
is, toward `four_channel` and against `text_only_llm`, which is the direction
that flatters the design. It is the opposite direction from `PROTOCOL.md` §9.6's
declared bias (rating audio means rating words, which favours `text_only_llm`).
Two identified biases now point opposite ways; neither is quantified.

**Two pieces of counter-evidence, which limit rather than dismiss the concern:**

1. **The three exposed raters did not converge on the author.** If prior exposure
   to the project's framing had shaped them, the natural expectation is that they
   would track the author, who briefed them. They do the opposite: the three
   lowest correlations in the whole matrix are the three involving the author
   (§7), and dropping the author *improves* agreement (§10).
2. **Their ratings show no alignment with the channels they were told about.**
   If they had been attending to face and voice as the framing suggests, some
   association with those channel labels would be expected. There is none —
   vocal p = 0.575, facial p = 0.853 (§14). The only channel showing any
   association is the transcript, and it does so with an inverted sign.

Neither observation rules the effect out. Both make a large effect less likely.
The honest position is that the ground truth was produced by raters with prior
exposure to the construct, the direction of any resulting bias is known, and the
size of it is not.

**Consequence for Item 7 (the user study).** Recruit raters with no prior
exposure to this project, and record prior exposure as a screening variable
rather than assuming it away.

### 2.2 A second departure, larger than the first *(added 08 Sep 2026)*

Stated by the author after the axis analysis was written, and recorded as
`PROTOCOL.md` **Amendment A7**: the other three raters were **told by the author,
before rating, how to apply the scale** — that a review counts as genuine when
the speaker means it, whether the content is praise or criticism, and that
direction is irrelevant.

§2.1 above describes incidental prior exposure. This is deliberate instruction,
from a person who is also one of the four raters, and it was not recorded
anywhere in the protocol.

**It strengthens the construct claim.** `AXIS_RESULT.md` rests on what the raters
were judging. That is now known for all four by direct instruction rather than
inferred for one by introspection, and applied uniformly.

**It weakens the independence of the agreement statistics, and only those.**
Briefing raters on a construct is ordinary practice — it is what rater training
is, and it raises reliability deliberately. What makes it a limitation here is
that the briefer also rated, and that it was not pre-registered. So §6's
α = 0.7296, §7.1's ICC(2,k) = 0.9124 and §8's ceiling ρ = 0.8038 measure
**agreement after shared instruction from a participant**, not independent
convergence. Raters given only the on-screen scale would likely agree less.

**What it does not touch.** No rater saw any label, score or system output;
`verify_page.py`'s 778 checks stand. There is no path from any system's answers
into the ratings. And the direction of the effect cannot rescue P1: a ceiling
that is too high cannot turn a null into a win — it only means every
"% of the human ceiling" figure is a **lower bound**.

**The counter-evidence in §2.1 applies here too, and is sharper.** The three
briefed raters agree with **each other** more than with the author who briefed
them: the three lowest correlations in the matrix are the three involving the
author (§7), and dropping the author *improves* agreement (§10). Being briefed on
a construct is evidently not the same as tracking the briefer's judgements.

**Consequence for Item 7.** The written scale must be the only instruction,
identical for every rater, delivered in writing rather than in conversation, and
the person who wrote it must not rate.

---

## 3. The raters

Pooled over all 600 presentations, 597 usable:

| rating | n | share |
|---|---:|---:|
| 5 — clearly genuine | 213 | 35.7% |
| 4 — probably genuine | 185 | 31.0% |
| 3 — can't say either way | 170 | 28.5% |
| 2 — probably not | 25 | 4.2% |
| 1 — clearly not genuine | 4 | 0.7% |
| 0 — unratable | 3 | (of 600) |

Per rater:

| rater | 0 | 1 | 2 | 3 | 4 | 5 | mean | sd | entropy | %extreme | %mid | %(1–2) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| rater1 *(author)* | 0 | 2 | 7 | 45 | 46 | 50 | 3.900 | 0.968 | 1.862 | 34.7% | 30.0% | 6.0% |
| rater2 | 1 | 0 | 4 | 42 | 48 | 55 | 4.034 | 0.873 | 1.712 | 36.9% | 28.2% | 2.7% |
| rater3 | 1 | 2 | 5 | 36 | 51 | 55 | 4.020 | 0.933 | 1.803 | 38.3% | 24.2% | 4.7% |
| rater4 | 1 | 0 | 9 | 47 | 40 | 53 | 3.919 | 0.955 | 1.809 | 35.6% | 31.5% | 6.0% |

**The response styles are unusually homogeneous.** Means span 3.900–4.034, SDs
0.873–0.968, extreme-response rates 34.7–38.3%, midpoint rates 24.2–31.5%. No
rater shows the classic pathologies — none is a straight-liner, none avoids the
endpoints, none parks on the midpoint. rater2 is the mildest at the bottom of the
scale (2.7% negative vs 6.0%), which is a leniency difference rather than a
different use of the instrument.

Homogeneity is good for the ground truth and is also a caution: four raters drawn
from a similar background, judging one genre, will agree partly because they
share priors. §14 treats this as the limitation it is.

### 3.1 Unratable was used, and used correctly

Three `0`s were recorded, and **all three fall on the same segment** — the only
segment in the study to lose ratings. See §9.

---

## 4. Within-rater consistency (P6, second half)

The 30 hidden duplicates, re-presented at a different position in the running
order. Raters were not told they existed.

| rater | pairs | exact | within ±1 | ρ | κ (linear) | κ (quadratic) | MAD | drift (2nd − 1st) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| rater1 *(author)* | 30 | **63.3%** | 93.3% | 0.756 | 0.604 | 0.719 | 0.433 | +0.033 |
| rater2 | 30 | **90.0%** | 100.0% | 0.939 | 0.901 | 0.943 | 0.100 | −0.033 |
| rater3 | 30 | **83.3%** | 96.7% | 0.833 | 0.816 | 0.875 | 0.200 | −0.067 |
| rater4 | 30 | **83.3%** | 96.7% | 0.885 | 0.830 | 0.884 | 0.200 | −0.067 |

**This is the single most informative table in the study**, and it is the number
`facial_bench/v2/` established the value of: it converts "the systems score X"
into "the systems score X against a ceiling of Y".

Readings:

- **Three of four raters re-test at 83–90% exact agreement with themselves.**
  On a 5-point ordinal scale that is high. Within ±1 point, rater2 is perfect
  (30/30), raters 3 and 4 are 29/30, and the author is 28/30.
- **rater1 is a clear outlier at 63.3%**, with more than four times rater2's mean
  absolute re-test difference (0.433 vs 0.100). §10 examines why.
- **There is no drift.** Signed differences are +0.033, −0.033, −0.067, −0.067 —
  all within a tenth of a scale point of zero. Raters did not become systematically
  harsher or softer on second sight, so the duplicates measure *noise*, not
  *fatigue*.

---

## 5. Attentiveness checks (not pre-registered)

Because no response latency was captured (§2), attentiveness is tested through
behaviour instead.

**Straight-lining.** Observed longest run of identical consecutive ratings,
against a null built by shuffling each rater's *own* answers 10,000 times — so
the null already contains their real marginal distribution:

| rater | longest run | null mean | P(run ≥ observed) |
|---|--:|--:|--:|
| rater1 | 5 | 4.84 | 0.568 |
| rater2 | 5 | 5.05 | 0.653 |
| rater3 | 4 | 5.08 | 0.972 |
| rater4 | 4 | 4.90 | 0.955 |

No rater is streakier than their own answers shuffled at random. Raters 3 and 4
are *less* streaky than chance. **No evidence of straight-lining in any file.**

**Order and fatigue.**

| rater | ρ(position, rating) | first 75 | second 75 |
|---|--:|--:|--:|
| rater1 | +0.048 | 3.800 | 4.000 |
| rater2 | +0.081 | 3.986 | 4.080 |
| rater3 | −0.055 | 4.054 | 3.987 |
| rater4 | **−0.139** | 4.095 | 3.747 |

Three raters show nothing. **rater4 drifts mildly downward** — 0.35 of a scale
point between halves. It is modest and the running orders are independently
seeded per rater (§4.6), so it cannot systematically bias any particular segment;
it adds noise, not bias. Flagged, not corrected.

**Independence.** Pairwise identical-answer rates run 58.0–73.9% (§7). Copying
would show near-100%. The spread of re-test consistency across raters
(63.3% to 90.0%) is a further behavioural signature that these are four
different people, though as noted in §2 the data cannot establish identity.

---

## 6. Between-rater agreement (P6, first half)

**Krippendorff's α**, ordinal metric, on every usable rating (a duplicated segment
contributes up to eight values, since a rater's second look is a genuine second
observation):

| subset | segments | pairable values | α ordinal | α interval | α nominal |
|---|--:|--:|--:|--:|--:|
| **all** | 119 | 596 | **0.7296** | 0.7178 | 0.5396 |
| selection | 80 | 380 | 0.7698 | 0.7613 | 0.5915 |
| **holdout** | 39 | 216 | **0.6377** | 0.6111 | 0.4336 |

Bootstrap 95% CI on the all-segments ordinal α, 10,000 resamples of segments,
seed 42: **[0.6447, 0.7978]**.

> **Read with §2.2.** All four raters were briefed on the construct by the author,
> who also rated. These figures measure agreement *after shared instruction from a
> participant*, not independent convergence, and are very likely higher than an
> unbriefed panel would produce.

Three things follow.

- **α = 0.730 clears the conventional bar for tentative conclusions (0.667) and
  does not clear the bar for firm ones (0.800).** That is the honest description
  and it should be stated that way in the report, not rounded up.
- **The ordinal metric matters.** α is 0.730 ordinal against 0.540 nominal. The
  gap is the size of the near-miss effect: most disagreements are one point, and
  a nominal α — which scores a 4-vs-5 disagreement exactly like a 1-vs-5 —
  understates this instrument by 0.19. `PROTOCOL.md` §6 specified ordinal in
  advance, which was the right call.
- **The holdout split is materially harder.** α falls to 0.638 there. Since P2 —
  "the number that counts" — is computed on holdout, the primary comparison runs
  on the noisier half of the data. This is not a flaw in the split; it is a
  property of those four speakers, and it must be carried into P2's interpretation.

---

## 7. Pairwise structure

| pair | n | ρ | Pearson r | MAD | signed | identical |
|---|--:|--:|--:|--:|--:|--:|
| rater1 · rater2 | 119 | 0.733 | 0.718 | 0.378 | −0.126 | 63.9% |
| rater1 · rater3 | 119 | 0.654 | 0.634 | 0.450 | −0.122 | 58.0% |
| rater1 · rater4 | 119 | 0.647 | 0.622 | 0.424 | −0.029 | 63.0% |
| rater2 · rater3 | 119 | 0.772 | 0.789 | 0.315 | +0.004 | 67.2% |
| rater2 · rater4 | 119 | 0.747 | 0.751 | 0.340 | +0.097 | 66.4% |
| **rater3 · rater4** | 119 | **0.860** | 0.853 | **0.244** | +0.092 | **73.9%** |

**The three lowest correlations in the matrix are the three that involve rater1.**
The three blind raters agree with each other at ρ = 0.747–0.860; the author agrees
with them at ρ = 0.647–0.733. The pattern is consistent and it is not subtle.

### 7.1 Reliability of the mean — ICC *(not pre-registered)*

Pairwise agreement is the wrong quantity for the decision this bench makes,
because no system is scored against one rater; every system is scored against the
**mean of four**. ICC(2,k), two-way random effects, absolute agreement, on the 119
complete segments:

| quantity | value |
|---|--:|
| ICC(2,1) — reliability of one rater | 0.7226 |
| **ICC(2,k=4) — reliability of the panel mean** | **0.9124** |

Absolute agreement rather than consistency, deliberately: a rater who is
perfectly correlated with the others but two points more generous is *not*
interchangeable with them for a mean-based ground truth, and consistency-ICC
would forgive that.

Spearman–Brown, from the mean pairwise ρ of 0.7356, answers a live design
question for the user study that follows:

| panel size | projected reliability |
|---|--:|
| 1 | 0.736 |
| 2 | 0.848 |
| 3 | 0.893 |
| **4** | **0.918** |
| 5 | 0.933 |
| 8 | 0.957 |

**Four raters was a well-chosen number.** A fifth would add ~0.015; going from
one to four bought 0.18. The returns are flat past four, so recruiting more
raters is not the efficient way to improve this measurement — reducing
within-rater noise would be.

---

## 8. The human ceiling (P5)

Each rater's values against the mean of the other three, Spearman, then averaged
over the four:

| subset | rater1 | rater2 | rater3 | rater4 | **mean** |
|---|--:|--:|--:|--:|--:|
| all (119) | 0.731 | 0.825 | 0.836 | 0.823 | **0.8038** |
| selection (80) | 0.701 | 0.897 | 0.866 | 0.841 | 0.8261 |
| **holdout (39)** | 0.802 | 0.647 | 0.773 | 0.823 | **0.7613** |

Bootstrap 95% CI on the all-segments ceiling, 1,000 resamples, seed 42:
**[0.7343, 0.8559]**.

> **Read with §2.2.** The panel was briefed on the construct by one of its own
> members, so this ceiling describes how well *these four, after that briefing*
> predict each other. It is very likely an overestimate of what independent
> raters would reach, which makes every "% of the human ceiling" figure in
> `BASELINE_ANALYSIS.md` and `AXIS_RESULT.md` a **lower bound** on relative
> performance. It cannot rescue P1: a ceiling that is too high does not turn a
> confidence interval that includes zero into a win.

**ρ = 0.804 is the number every system in P1 should be compared against**, and it
is the right form of comparison: a system is scored against a mean of humans, so
the fair benchmark is what a human scores against a mean of the other humans.
Comparing a system's ρ to a *pairwise* human ρ instead would hold the system to a
stricter standard than any individual human meets.

On holdout the ceiling drops to **0.761**, and the per-rater figures scatter much
more widely there (0.647–0.823) on only 39 segments. rater2 is the strongest
rater on selection and the weakest on holdout, which at n=39 is most plausibly
sampling noise rather than a real speaker-specific effect; it is not
over-interpreted here.

---

## 9. Ground truth construction (§5.4) and the power floor (§8.3)

`h(s)` = the mean over raters of each rater's own mean usable rating, on 1–5.
Unratable answers are excluded, never scored as zero — treating a `0` as a rating
would drag a segment toward the bottom of the scale and make unjudgeable clips
look like the least genuine ones in the study. This is unit-tested
(`test_unratable_is_excluded_not_scored_as_zero`).

Each rater is averaged *first*, so a duplicated segment does not let one rater
count twice against a rater who marked one presentation unratable
(`test_each_rater_is_weighted_equally_despite_duplicates`).

**One segment was dropped**, having fewer than three usable ratings:

> **`Kk-RKpTAXmA_139`** — ShortCircuit, holdout, 3.98 s
> Transcript: *"Reese. Wah! Wah! Wah!"*
> rater1 → **3**, rater2 → **0**, rater3 → **0**, rater4 → **0**

This is the `0` option doing exactly the job `PROTOCOL.md` §5.3 designed it for.
The segment is non-propositional vocalisation; there is no claim in it to be
sincere or insincere about. **All three blind raters independently refused it.**
The author rated it 3.

It is also, incidentally, a small illustration of the gap this whole bench
exists to probe: on a segment three humans said was unjudgeable, the pipeline's
channels returned `transcript_sentiment: POSITIVE` and `vocal_emotion: POSITIVE`
with no indication of difficulty. **Automated confidence does not degrade where
human confidence does.**

**Power floor — §8.3, checked rather than assumed:**

| | required | actual | met |
|---|--:|--:|:--:|
| surviving segments | ≥ 90 | **119** | ✅ |
| surviving holdout segments | ≥ 30 | **39** | ✅ |

**The bench is not underpowered by its own pre-registered definition.** The
holdout margin is 39 against a floor of 30, which is a pass and not a comfortable
one; §15 returns to what that means for P2.

---

## 10. Author-bias sensitivity (§8.4)

`PROTOCOL.md` §8.4 required P1 and P2 to be recomputed without the author, and
§9.4 named the risk: *"Three of the four raters are recruited by the author and
may be motivated to agree with each other or to be agreeable."*

**The data shows the opposite of the pre-registered worry.**

| quantity | with author (k=4) | without author (k=3) |
|---|--:|--:|
| α ordinal | 0.7296 | **0.7860** |
| ICC(2,k) | 0.9124 | **0.9213** |
| ceiling (mean LOO ρ) | 0.8038 | 0.8375 |
| mean h | 3.9727 | 3.9958 |

The ICC result is the striking one. ICC(2,k) normally *falls* when a rater is
removed, because k drops. Here it **rose** — the author was contributing more
noise than information to the panel mean.

Deviation from the mean of the other three:

| rater | mean signed | **mean absolute** | ≥1.5 below others | ≥1.5 above |
|---|--:|--:|--:|--:|
| **rater1** | −0.092 | **0.403** | **5** | 2 |
| rater2 | +0.076 | 0.300 | 0 | 2 |
| rater3 | +0.070 | 0.317 | 0 | 1 |
| rater4 | −0.053 | 0.325 | 1 | 1 |

rater1's mean absolute departure is 0.403 against 0.314 averaged over the other
three — **29% noisier** — and they account for **five of the six** severe
(≥1.5-point) *downward* departures in the study, and seven of the twelve severe
departures in either direction.

**Does the ground truth change?** Barely. ρ(h₄, h₃) = **0.9775**, Pearson 0.9783,
mean shift +0.023, worst single-segment shift 0.917. **§8.4 passes: no conclusion
that depends on h can flip on the author's inclusion**, so the primary analysis
retains all four raters as pre-registered.

### 10.1 Why is the author the outlier? A hypothesis, not a finding

The author's six largest downward departures are all of one kind — segments the
others heard as ordinary enthusiasm and the author marked as sales language:

| author | others | segment |
|--:|--:|---|
| 1.0 | 4.67 | *"And Corning's Ceramic Shield 2, in case you haven't already heard, is also clearly awesome"* |
| 2.5 | 4.50 | *"and one day be able to use all the apps that you've gotten used to, but in a whole new dim…"* |
| 3.0 | 4.67 | *"down it's gonna have to throttle more quickly versus a macbook pro…"* |
| 3.0 | 4.67 | *"Well, the main thing that you're going to be seeing is the screens. There's two of them."* |
| 2.0 | 3.67 | *"makes you yourself more confident. So if you care about that fact,"* |
| 3.0 | 4.33 | *"Xiaomi have actually gone as far as to create a completely bespoke case"* |

The first is the most contested segment in the entire study (across-rater SD =
1.89) and the pattern is legible: *"in case you haven't already heard, is also
clearly awesome"* reads as arch on the page. The author — the one rater who knows
the study is about authenticity and marketing language — marked it 1. The three
blind raters, hearing the delivery, marked it 4, 5, 5.

**This is a hypothesis consistent with the data, not a measured finding.** It was
not pre-registered and there is no independent measure of "reading for sarcasm"
to test it against. It is recorded because it is the most plausible mechanism for
the largest rater effect in the study, and because it has a concrete methodological
consequence: **an unblinded rater who knows the construct under test is a
liability, not an asset.** For the user study (Item 7), the author should not be
a rater.

---

## 11. Duplicate-handling sensitivity (§8.5)

`PROTOCOL.md` §5.4 says the ground truth is "the mean of the ratings from all
raters who did not mark it unratable". Read literally, that uses every usable
rating, so a rater's second sight of a duplicated segment counts. That reading is
the **primary** analysis here. §8.5 asks for the alternative:

| | averaged (primary) | first presentation only |
|---|--:|--:|
| mean h | 3.9727 | 3.9769 |
| ρ between the two | — | **0.9960** |
| segments whose h changes at all | — | 16 of 119 |
| largest change | — | 0.25 |

**The choice is immaterial.** ρ = 0.996 and the largest movement is a quarter of a
scale point on the 30 duplicated segments. No result in P1–P4 can turn on it.
Recorded so the decision is visible rather than silent.

---

## 12. What the ground truth actually looks like

| subset | n | mean | sd | min | Q1 | median | Q3 | max | distinct values |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| all | 119 | 3.973 | 0.803 | 1.625 | 3.25 | 4.00 | 4.75 | 5.000 | 18 |
| selection | 80 | 3.906 | 0.834 | 1.625 | 3.25 | 4.00 | 4.75 | 5.000 | 14 |
| holdout | 39 | 4.109 | 0.724 | 2.625 | 3.50 | 4.25 | 4.75 | 5.000 | 15 |

**`PROTOCOL.md` §9.5 predicted this and it happened.** The threat was written as:
*"Genuineness may be equally compressed. If the human ratings turn out to have
little variance, P1 is uninformative and that will be reported as the result."*

The outcome is between the two poles, and the distinction matters:

- **There IS usable variance.** sd = 0.803 on a 4-point-wide scale, IQR spans 1.5
  points, 18 distinct values, and the full range 1.625–5.000 is used. This is not
  a degenerate target and P1 is not vacuous.
- **But the variance is nearly all in the top half.** 95.1% of ratings are 3–5.
  Only **5 of 119 segments (4.2%, 95% CI [1.8%, 9.5%])** have h < 3. Segments the
  panel judges outright not-genuine are *rare events* in this corpus.

The practical consequence for P1: a system's ρ will be determined almost entirely
by how it ranks segments *within* the 3-to-5 band — that is, by ordering degrees
of ordinary sincerity — and almost not at all by whether it can find the five
genuinely inauthentic moments. **This is a different task from the one the system
was designed for**, and it is a limitation of the corpus rather than of the
method. It belongs in the write-up's headline limitations alongside §9.1's
comment-channel constant.

### 12.1 Ceilings on ρ that have nothing to do with model quality

Worth establishing before P1, so a mediocre ρ is not misread as a mediocre system:

| bound | value | what it means |
|---|--:|---|
| ρ of a perfectly-ordering **untied** predictor vs h | 0.993 | h's 18-value tie structure costs almost nothing |
| max correlation of an **errorless** predictor, √ICC(2,k) | 0.955 | measurement error in h itself |
| **measured human ceiling (P5)** | **0.804** | what a person achieves |
| human ceiling on holdout | 0.761 | what governs P2 |

And on the system side, since `controller_bench` §5 measured the controller
emitting only a handful of discrete values, a perfectly-ordered but coarsely
quantised score is capped by its own granularity:

| distinct values a system emits | max achievable ρ |
|---|--:|
| 2 | 0.781 |
| 3 | 0.879 |
| 4 | 0.950 |
| 5 | 0.957 |
| 8 | 0.987 |

**A system that emits only two or three distinct conflict scores cannot exceed
ρ ≈ 0.78–0.88 no matter how correct it is.** When P1 is reported, the number of
distinct values each system actually emitted must be reported beside its ρ, or
the comparison will silently confuse discrimination with granularity.

---

## 13. Disagreement structure

Across-rater SD per segment: mean 0.327, max 1.893. **52 of 119 segments (43.7%)
are unanimous** (SD = 0); only **5 (4.2%)** have SD ≥ 1.0.

### 13.1 The five most contested segments

| SD | h | ratings | transcript | vocal | facial | text |
|--:|--:|---|---|---|---|---|
| 1.89 | 3.75 | 1 / 4 / 5 / 5 | POSITIVE | NEUTRAL | — | *"And Corning's Ceramic Shield 2, in case you haven't already heard, is also clearly awesome"* |
| 1.31 | 3.88 | 4.5 / 5 / 4 / 2 | NEUTRAL | POSITIVE | neutral | *"should know, placebo effect works. I myself know how the stupid game works. I wear a suit."* |
| 1.08 | 4.00 | 2.5 / 4 / 4.5 / 5 | POSITIVE | NEUTRAL | happy | *"and one day be able to use all the apps that you've gotten used to…"* |
| 1.00 | 3.50 | 5 / 3 / 3 / 3 | NEGATIVE | NEUTRAL | happy | *"and gathered around it will start to fade. And that brings me onto the why."* |
| 1.00 | 3.50 | 3 / 5 / 3 / 3 | POSITIVE | NEUTRAL | neutral | *"Shout out Sony's other division. Now, in my tiny hands, they look like quarter-inch jacks."* |

The contested cases are **rhetorically marked** — arch praise, meta-commentary
about persuasion ("placebo effect works… I wear a suit"), aspirational framing.
Humans genuinely differ on whether knowingness signals honesty or performance.
That is a real property of the construct, not rater carelessness, and it puts a
principled cap on any α this task can reach.

### 13.2 The segments humans agree are *not* genuine

These five are the entire positive class for the construct the system is meant to
detect, so they deserve individual attention:

| h | SD | transcript | vocal | facial | text |
|--:|--:|---|---|---|---|
| 1.62 | 0.48 | NEUTRAL | NEUTRAL | — | *"to how to display notifications, to the exact shade of color that you want,"* |
| 2.00 | **0.00** | NEGATIVE | NEUTRAL | neutral | *"Harsh. They're brutal. They squeeze your head like a lot."* |
| 2.00 | **0.00** | **POSITIVE** | **POSITIVE** | — | *"oh yeah, thank gosh I have eight lenses now in my smartphone."* |
| 2.62 | 0.48 | NEUTRAL | NEUTRAL | — | *"Sony Sound Connect. We're going to need an app because everything does."* |
| 2.88 | 0.85 | NEUTRAL | NEUTRAL | — | *"We'll see. There's a couple other things like the Journal app and Notebook LM,"* |

**The third row is the clearest single example in this dataset of the problem the
project exists to solve.** *"oh yeah, thank gosh I have eight lenses now in my
smartphone"* is sarcasm. All four humans marked it 2, unanimously. The transcript
channel labelled it **POSITIVE** and the vocal channel labelled it **POSITIVE** —
both maximally wrong, and in agreement with each other, so a cross-channel
conflict score would see **no conflict at all**.

That is worth stating plainly because it cuts against the project's own premise:
**channel agreement is not evidence of authenticity when the channels share a
failure mode.** Two channels can be confidently and identically wrong. This result
therefore remains relevant independently of P1's outcome.

---

## 14. Do the pipeline's channels see what humans see? *(not pre-registered)*

Raters never saw any channel label (`verify_page.py`, 778 mechanical checks).
Comparing h against each channel's label is therefore a clean diagnostic. The
test is a rank-based permutation test (20,000 shuffles, seed 42, add-one
smoothed) that asks only whether the label carries **any** information about
human judgement — **the direction is not assumed**, for the reason in §15 below.

| channel | label | n | mean h | permutation p |
|---|---|--:|--:|--:|
| **transcript** | NEGATIVE | 15 | **4.392** | **p = 0.034** |
| | POSITIVE | 29 | 4.022 | |
| | NEUTRAL | 75 | 3.870 | |
| **vocal** | NEUTRAL | 95 | 3.997 | p = 0.575 |
| | POSITIVE | 24 | 3.875 | |
| **facial** | fear | 5 | 4.250 | p = 0.853 |
| | surprise | 3 | 4.167 | |
| | happy | 19 | 4.105 | |
| | neutral | 40 | 4.022 | |
| | sad | 15 | 3.950 | |
| | angry | 3 | 3.792 | |
| | *(no face)* | 34 | 3.809 | |
| **comments** | POSITIVE | 119 | 3.973 | — (constant) |

Three results, and they line up exactly with what the earlier benches measured
independently:

1. **Transcript sentiment carries real signal, with an inverted sign.** NEGATIVE
   segments are judged *most* genuine and NEUTRAL *least*. The effect is modest
   (0.52 of a scale point between extremes, p = 0.034 at n = 119) but it is the
   only channel showing any association at all. The mechanism is intuitive:
   criticism in a product review reads as honest; praise reads as marketing; flat
   descriptive narration reads as scripted.

   > **Superseded 08 Sep 2026 — see `AXIS_RESULT.md` §4.** The "inverted sign"
   > reading does not survive being tested. The NEGATIVE-vs-POSITIVE gap an
   > inverted sign requires is **not** distinguishable (p = 0.113); the
   > committed-vs-NEUTRAL gap it does not predict **is** (p = 0.037); and the
   > three means are non-monotonic in valence (NEUTRAL 3.870 < POSITIVE 4.022 <
   > NEGATIVE 4.392), which is why signed valence correlates at −0.0784 (null)
   > while its magnitude correlates at +0.1909 (interval excludes zero). The
   > channel carries information about **whether the speaker took a position**,
   > not about which position. The p = 0.034 three-group test above is correct
   > and unchanged; only the direction read into it was wrong. Conclusions 2 and
   > 3 below are unaffected.

2. **Vocal emotion carries nothing measurable** (p = 0.575). Consistent with
   `vocal_bench`'s 48.9% on held-out speakers, and with the +0.159 within-video
   rank correlation in `SPEAKER_NORM_RESULT.md`.

3. **Facial emotion carries nothing measurable** (p = 0.853), and the label
   ordering is close to arbitrary — `fear` ranks most genuine, `angry` least,
   on 5 and 3 segments respectively. Consistent with `facial_bench/v2/`, where
   every model scored below an always-NEUTRAL constant on held-out speakers.

**This is the first evidence in the project that connects the channels to human
judgement of the actual construct**, rather than to frame labels or clip labels.
It does not pre-empt P1 — a *conflict* between channels is a different quantity
from any single channel's label, and the LLM controller could in principle extract
signal that no single channel shows. But it does set a sober prior.

### 14.1 Confounds the raters could have used

| against h | ρ |
|---|--:|
| clip duration | +0.175 |
| transcript length | +0.173 |
| facial frame count | +0.150 |
| audio RMS | −0.026 |

**Longer clips are rated slightly more genuine.** The effect is small but real and
it has an obvious mechanism: more material gives a rater more to be persuaded by,
and a 2-second fragment offers little to trust. Duration, transcript length and
frame count are ~the same variable measured three ways, which is why they move
together. Loudness is unrelated.

The sample was drawn without stratifying on any model output (`PROTOCOL.md` §4.4)
but it was **not** balanced on duration, so this is a genuine uncontrolled
covariate. It is small enough not to threaten P1 and it should be reported, and
in any future round the duration window should be narrowed or the sample balanced
on it.

---

## 15. A gap found in the protocol — must be closed before P1

`PROTOCOL.md` §3 lists `transcript_label` as a system: *"naive single-channel
reference, no LLM"*, producing "one score per segment on the same scale". **It
never defines the mapping** from `{POSITIVE, NEUTRAL, NEGATIVE}` to a conflict
score in [0, 1]. That is an under-specification, and it is a live one: §14 has now
established that the intuitive mapping (POSITIVE → genuine) would have the
**wrong sign** on this data.

This must be handled carefully, because the diagnostic in §14 was computed
*before* the gap was noticed. Choosing the mapping now, with that table in view,
would be fitting a system to the test set and would invalidate `transcript_label`
as a reference.

**Therefore the mapping is not chosen here.** `PROTOCOL.md` Amendment A1
(08 Sep 2026) records the gap, records that the diagnostic had already been seen,
and commits to running **both** directions as two separately named references
(`transcript_label_pos_genuine` and `transcript_label_neg_genuine`), reporting
both, and treating neither as "the" transcript baseline. Two degenerate references
cost nothing and remove the degree of freedom entirely.

This does not affect `text_only_llm`, which is the baseline that actually threatens
the design (`PROTOCOL.md` §3.1) and which is fully specified — same model, same
temperature, same seed, same `num_ctx`, same JSON contract.

---

## 16. Limitations

Stated in full.

1. **The corpus is 95% "genuine" (§12).** Only 5 of 119 segments are judged
   not-genuine. P1 measures ranking within a narrow band of ordinary sincerity,
   not detection of inauthenticity. This is the most important limitation here.
2. **The comment channel is a constant** — POSITIVE on all 12 videos. Pre-registered
   as `PROTOCOL.md` §9.1. Any "four-channel" conclusion is really about three
   varying channels plus a constant.
3. **No rater was construct-naive (§2.1).** All three non-author raters had seen
   the dashboard and its framing 37 days earlier, contradicting `PROTOCOL.md`
   §5.1. Possible bias runs toward the multi-channel design; size unquantified.
4. **No response latency was captured.** Attentiveness is inferred behaviourally
   (§5), not measured. `build_pages.py` should record per-item timing before the
   user study.
5. **Rater identity cannot be verified from the data.** The response patterns
   differ in ways consistent with four people; that is evidence, not proof.
6. **α = 0.730 supports tentative, not firm, conclusions**, and on the holdout
   split — the one that governs P2 — it is 0.638.
7. **Holdout is n = 39**, against a pre-registered floor of 30. The floor is met,
   but P2's bootstrap intervals will be wide and a null result there will not
   distinguish "no effect" from "not enough data".
8. **Four raters, one genre, similar backgrounds.** Their homogeneity (§3) is
   partly shared priors. Agreement among four similar people is a weaker warrant
   than agreement among four dissimilar ones.
9. **rater4 drifts mildly downward** over the running order (ρ = −0.139). Noise,
   not bias, because orders are independently seeded — but recorded.
10. **Duration is an uncontrolled covariate** (ρ = +0.175 with h), §14.1.
11. **§10.1's account of the author's deviation is a hypothesis**, not a
    measured finding. There is no independent measure of "reading for sarcasm".

---

## 17. Conclusions

1. **The ground truth is fit for purpose, with stated caveats.** α = 0.730
   [0.645, 0.798] ordinal, ICC(2,k) = 0.912, human ceiling 0.804 [0.734, 0.856],
   119 of 120 segments surviving, power floor met on both criteria. **P1–P4 may
   proceed.**
2. **Report every system's ρ against 0.804, and against 0.761 on holdout.** A
   system at ρ = 0.5 is not "poor" in the abstract; it is at 62% of the human
   ceiling, and that is the defensible way to state it.
3. **Report the number of distinct values each system emits beside its ρ** (§12.1),
   or granularity will be mistaken for discrimination.
4. **Future recruitment must avoid evaluator overlap (Item 7).** The researcher should not
rate because they were the least consistent rater here (63.3% re-test vs 83–90%), the
least agreeing, and removing them *improved* every agreement statistic. Nor
should returning participants from the August pilot be used, for the reason in §2.1.
   Prior exposure to the construct should be screened and recorded, not assumed
   absent.
5. **Four raters is the right panel size** (§7.1). A fifth buys ~0.015. Effort is
   better spent on within-rater consistency — clearer instructions, a practice
   block, per-item timing — than on recruitment.
6. **Close the `transcript_label` gap by running both directions** (§15, Amendment A1).
7. **Two findings remain valid regardless of P1's result:** the sarcastic segment on which
   transcript and vocal channels
   were confidently and *identically* wrong (§13.2), and the inverted association
   between transcript sentiment and human authenticity judgement (§14).

---

## 18. What happens next

| step | file | status |
|---|---|---|
| pre-registration | `PROTOCOL.md` | done, + Amendment A1 |
| sampling, clip cutting | `sample.py` | done — 120 segments, 480 frames |
| blind rating pages | `build_pages.py` | done — 4 pages |
| blinding verification | `verify_page.py` | done — 778 checks pass |
| statistics | `stats.py` | **done — 63 unit tests** |
| **rater analysis (P5, P6, §5.4, §8.3–8.5)** | **`rater_analysis.py`** | **done — this document** |
| claim verification (this document) | `verify_claims.py` | done — 304 claims |
| the systems | `systems.py` | done — 7 candidates |
| running them over the 120 | `run_bench.py` | done — 480 calls, 0 failures |
| P1–P4 | `report_bench.py` | done |
| **results** | **`BASELINE_ANALYSIS.md`** | **done — 213 claims verified** |

---

## 19. Reproduction

```bash
cd brandpulse_ai
source .venv/bin/activate

python research/baseline_bench/rater_analysis.py     # ~9 s -> rater_analysis_results.json
python -m pytest tests/test_baseline_bench.py -q    # 63 passed
python -m pytest -q                                 # 994 passed
```

Fixed seed 42 throughout; 10,000 bootstrap resamples for α, 1,000 for the ceiling
(each draw there costs four Spearman correlations), 20,000 permutations for the
channel diagnostics. All inputs are on disk: `ratings_rater{1..4}.json`,
`sample.json`, `_tokens.json`, `pages/rate_rater{1..4}.html`.

**Verification of the statistics themselves.** `stats.py` is hand-written per
`PROTOCOL.md` §6, and every function was cross-checked against an independent
implementation in a throwaway environment before its expected values were frozen
into the test suite:

| function | checked against | result |
|---|---|---|
| `spearman` | `scipy.stats.spearmanr`, 300 heavy-tie cases | max diff 3.3e-16 |
| `pearson` | `scipy.stats.pearsonr` | 3.3e-16 |
| `weighted_kappa` (linear, quadratic) | `sklearn.metrics.cohen_kappa_score`, 300 cases each | 5.6e-16 |
| `_percentile` | `numpy.percentile`, `linear` | 4.4e-16 |
| `krippendorff_alpha` (3 metrics) | `krippendorff` PyPI, 400 randomised cases **with missing data** | 0 mismatches, max 8.9e-16 |
| `icc_2k` | `pingouin` ICC(A,1) / ICC(A,k), 120 cases | 6.1e-16 |
| `krippendorff_alpha` freq. form | its own brute-force pair-enumeration form, 200 cases | exact, 0.0 |

Two corrections made during that process, recorded because they are the reason
the check was worth running:

- The Krippendorff and ICC constants first written into the test file were
  **recalled from memory and wrong in their trailing digits.** The reference
  implementations supplied the true values; `stats.py` had been correct all along
  and now matches to 13 decimal places.
- `weighted_kappa`'s docstring claimed that inferring the category list from the
  data "inflates kappa". **That claim was false** — unused categories at the end
  of an evenly-spaced ordinal scale rescale all weights by one constant, which
  cancels. The docstring is corrected and
  `test_unused_categories_do_not_change_kappa` now pins the true behaviour, with
  `test_out_of_scale_value_raises_rather_than_being_absorbed` recording the real
  reason the argument exists.

`krippendorff` and `pingouin` are **not** project dependencies and are not
imported by anything in this repo. They were used once, in a scratch virtualenv,
to certify constants.
