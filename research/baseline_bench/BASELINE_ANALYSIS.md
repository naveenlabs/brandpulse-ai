# baseline_bench — does comparing four channels beat reading the transcript?

**Results. 08 Sep 2026.** Pre-registered in `PROTOCOL.md` (06 Sep 2026) with five
dated amendments. Produced by `run_bench.py` (480 cached LLM calls, 0 failures)
and `report_bench.py`; every number recomputed by `verify_claims.py`.

The instrument these systems are judged against is validated separately in
`BASELINE_RATER_ANALYSIS.md` — four raters, α = 0.7296, human ceiling **0.8038**,
119 of 120 segments surviving.

---

## 0. Headline

**No system tracks human authenticity judgement on this corpus. Not the
four-channel design, not the text-only baseline, not either of them at any
sample split. Every 95% confidence interval includes zero.**

| system | channels | ρ (all, n=119) | 95% CI | ρ (holdout, n=39) | distinct values |
|---|---|---:|---|---:|---:|
| `four_channel` | T V F C | **+0.0575** | [−0.1282, +0.2364] | +0.0604 | 7 |
| `three_channel` | T V C | −0.0341 | [−0.2253, +0.1562] | −0.3033 | 6 |
| `text_only_llm` | transcript | −0.0676 | [−0.2373, +0.1085] | −0.0072 | 5 |
| `text_only_llm_anchored` | transcript | −0.1610 | [−0.3302, +0.0120] | +0.2664 | 4 |
| `transcript_label_neg_genuine` | T label, no LLM | +0.0784 | [−0.1089, +0.2595] | +0.2143 | 3 |
| `transcript_label_pos_genuine` | T label, no LLM | −0.0784 | [−0.2595, +0.1089] | −0.2143 | 3 |
| `constant` | none | **+0.0000** | [+0.0000, +0.0000] | +0.0000 | 1 |
| *human ceiling (P5)* | — | **+0.8038** | [+0.7343, +0.8559] | +0.7613 | — |

`constant` scores **exactly 0.000**, so the metric is sound and the comparison is
not being won by a degenerate predictor (`PROTOCOL.md` §3.3).

> **The human ceiling is very likely an overestimate.** Per `PROTOCOL.md`
> Amendment A7, all four raters were briefed on the construct by the author, who
> also rated, so 0.8038 measures agreement after shared instruction rather than
> independent convergence. Every "% of the human ceiling" figure below is a
> **lower bound** on relative performance. It changes no verdict: every system's
> interval includes zero, and a ceiling that is too high cannot turn a null into
> a win.

**The four pre-registered decisions:**

| | result |
|---|---|
| **RQ1 / P3 (primary, holdout)** | `four_channel` − `text_only_llm_anchored` = **−0.2060** [−0.6246, +0.2395] → **no detected difference** |
| **RQ2 / P4 (holdout)** | +0.3637 [+0.1082, +0.6425] → mechanically "four_channel wins", **but not credible — see §5** |
| **P5 human ceiling** | 0.8038 [0.7343, 0.8559] |
| **P6 agreement** | α = 0.7296 ordinal, ICC(2,k) = 0.9124 |

`PROTOCOL.md` §8.1 declared three possible outcomes in advance and named the
third — *"Neither, if the CI includes zero… the most likely one at n=120"* — as
the expected result. **That is what happened**, and per §8.1 it is reported as
such and **not rounded into a win for the incumbent design**.

**Four findings outrank the headline.**

1. **Coarseness is not the excuse.** Each system's own multiset of scores, if
   assigned to the right segments, would reach ρ = 0.797–0.928. They reach
   **7.2% of that at best** (§6). The scores are not too blunt to correlate;
   they are on the wrong segments.
2. **A three-line lookup table with no LLM matches the full pipeline.**
   `transcript_label_neg_genuine` scores +0.0784 against `four_channel`'s
   +0.0575 (both null). The entire LLM controller adds nothing measurable over
   `NEGATIVE → 0.0, NEUTRAL → 0.5, POSITIVE → 1.0`.
3. **The design's premise is not inverted — it is orthogonal.** The system reads
   cross-channel disagreement as inauthenticity; humans were not judging on that
   axis at all. §7 has two worked examples where the mismatch is exact and
   maximal, and **`AXIS_RESULT.md` measures it at corpus scale**: the conflict
   score tracks cross-channel valence disagreement at ρ = +0.4415, human ratings
   track it at +0.0498 (null), and no rule over these channel labels can exceed
   ρ = +0.4647 even when fitted directly on the answers — a proven bound, against
   a human ceiling of 0.8038.
4. **The controller emits one number.** 86 of 120 `four_channel` raw responses
   are `0.6` — 71.7% — across four distinct values total. It is not performing
   the four-way comparison its prompt specifies (§4.1).

---

## 1. What was run

| | |
|---|---|
| segments | 120 sampled, **119** scored (one dropped by §5.4 — see the rater analysis) |
| splits | 80 selection, 39 holdout — both above the §8.3 power floor |
| LLM systems | 4 × 120 = **480 calls, 0 failures** |
| controller | `llama3.1:8b`, `temperature: 0`, `seed: 42`, `num_ctx: 4096` — read from `pipeline/orchestrator.py`, not restated |
| total LLM time | **1,923.8 s (32.1 min)** — the sum of the 480 measured per-call latencies in the cache. `run_summary.json`'s per-system elapsed totals 1,891.8 s because two calls per system were already cached from a smoke test and cost that run no time. |
| median latency | 4.51 s (`four_channel`), 4.56 s (`three_channel`), 3.60 s / 3.38 s (text-only) |

**Determinism was checked, not assumed.** `temperature: 0` with a fixed seed is
an assertion about Ollama's behaviour, not a guarantee, and `PROTOCOL.md` §12
requires every experiment to be re-runnable. Re-running 10 probes per system
into a separate cache gave **0 mismatches over 40 re-runs**
(`run_bench.py --determinism`).

`four_channel` and `three_channel` call the production
`build_segment_payload` and `_coerce_result` with the deployed `_SYSTEM_PROMPT`
verbatim. Channel values are byte-identical to `controller_bench`'s: nothing was
re-transcribed, no sentiment recomputed, no comment re-fetched, DeepFace not
re-run (`PROTOCOL.md` §4.1–4.2).

---

## 2. P1 — every system against the human ground truth

Spearman ρ between `h(s)` and `−c(s)`, so a system that scores high conflict on
segments humans call less genuine gets a **positive** number. Bootstrap 95% CI
over segments, 10,000 resamples, seed 42.

| system | split | n | ρ | 95% CI | mean score | flag rate | distinct |
|---|---|--:|--:|---|--:|--:|--:|
| `four_channel` | all | 119 | +0.0575 | [−0.1282, +0.2364] | 0.527 | 6.7% | 7 |
| | selection | 80 | +0.0492 | [−0.1770, +0.2765] | 0.535 | 7.5% | 6 |
| | holdout | 39 | +0.0604 | [−0.2616, +0.3655] | 0.510 | 5.1% | 6 |
| `three_channel` | all | 119 | −0.0341 | [−0.2253, +0.1562] | 0.494 | 2.5% | 6 |
| | selection | 80 | +0.0689 | [−0.1663, +0.3063] | 0.500 | 2.5% | 6 |
| | holdout | 39 | −0.3033 | [−0.6039, +0.0257] | 0.483 | 2.6% | 5 |
| `text_only_llm` | all | 119 | −0.0676 | [−0.2373, +0.1085] | 0.751 | **67.2%** | 5 |
| | holdout | 39 | −0.0072 | [−0.3046, +0.2938] | 0.764 | 71.8% | 3 |
| `text_only_llm_anchored` | all | 119 | −0.1610 | [−0.3302, +0.0120] | 0.284 | 29.4% | 4 |
| | selection | 80 | **−0.3534** | [−0.5284, −0.1559] | 0.291 | 30.0% | 4 |
| | holdout | 39 | **+0.2664** | [−0.0635, +0.5588] | 0.269 | 28.2% | 3 |
| `transcript_label_neg_genuine` | all | 119 | +0.0784 | [−0.1089, +0.2595] | 0.559 | 24.4% | 3 |
| | holdout | 39 | +0.2143 | [−0.0935, +0.4908] | 0.526 | 23.1% | 3 |
| `constant` | all | 119 | +0.0000 | [+0.0000, +0.0000] | 0.000 | 0.0% | 1 |

**Not one interval on the full sample excludes zero.** The single interval
anywhere in the table that does is `text_only_llm_anchored` on *selection*, at
**−0.354** — significantly **anti**-correlated — and the same system is **+0.266**
on holdout. A predictor that flips sign by 0.62 between two halves of one corpus
is describing noise, not a property of the world.

Expressed against the measured human ceiling of 0.8038, the best system reaches
**7.2%** of it.

---

## 3. P3 — the primary decision (RQ1)

Paired bootstrap of `ρ_four − ρ_text` on the same resamples (dependent samples;
comparing two independent intervals would be the wrong test), 10,000 resamples,
seed 42. Amendment A5 gives the baseline its **best of two pre-declared prompts**,
which is `text_only_llm_anchored` on holdout (+0.2664 against −0.0072).

| split | n | ρ_four − ρ_text | 95% CI | four wins in | verdict |
|---|--:|--:|---|--:|---|
| **holdout — the number that counts** | 39 | **−0.2060** | [−0.6246, +0.2395] | 17.6% | **no detected difference** |
| all | 119 | +0.2185 | [−0.0573, +0.4881] | 94.2% | no detected difference |
| selection | 80 | +0.4026 | [+0.0659, +0.7294] | 99.0% | *four_channel wins* |
| holdout vs the *original* text-only prompt | 39 | +0.0676 | [−0.3445, +0.4615] | 61.9% | no detected difference |

**Verdict: no detected difference on the pre-registered primary endpoint.**

The selection split does show `four_channel` ahead with an interval excluding
zero. It is not the primary endpoint (§4.3, §8.1 both name holdout), and it
should not be promoted into one, for a reason visible in the table: the holdout
point estimate has the **opposite sign**. A design whose advantage is +0.40 on
the speakers it was developed against and −0.21 on unseen speakers has not
demonstrated an advantage; it has demonstrated why the split exists.

Reported per §8.1 with the sample size and interval width: at n = 39 the holdout
interval spans **0.864** of correlation. This experiment could not have detected
anything short of a very large effect, and that is a property of the sample, not
a defence of the result.

---

## 4. Why the systems produce what they produce

### 4.1 The controller emits essentially one number

Raw `conflict_score` before any coercion, over all 120 segments:

| system | distinct raw values | distribution | modal share | raw mean (n=120) |
|---|--:|---|--:|--:|
| `four_channel` | 4 | 0.0×10, 0.5×16, **0.6×86**, 0.8×8 | **71.7%** | 0.550 |
| `three_channel` | 4 | 0.0×9, 0.5×32, **0.6×76**, 0.8×3 | 63.3% | 0.533 |
| `text_only_llm` | 5 | 0.0×1, 0.6×13, 0.7×25, **0.8×80**, 0.9×1 | 66.7% | 0.752 |
| `text_only_llm_anchored` | 4 | **0.0×56**, 0.25×28, 0.75×33, 1.0×3 | 46.7% | 0.290 |

(These are the **raw** means over all 120 responses. §2's `mean score` column is
the *coerced* mean over the 119 scored segments and is a different quantity —
0.284 for the anchored prompt against 0.290 here.)

`controller_bench` §5 measured the controller emitting "a handful of discrete
values, mostly thirds and quarters" and that reproduces here exactly.

More telling than the count: **the same channel configuration does not produce
the same score.** The configuration `transcript POSITIVE / vocal NEUTRAL / face
present` occurs 15 times in the sample and returned **0.0 five times, 0.5 six
times and 0.6 four times**. With `temperature: 0` and a fixed seed the
model is deterministic per input, so the variation comes from the *transcript
text*, which the payload also carries. The controller is not performing the
four-way valence comparison its prompt specifies; it is reading the words and
producing a number that mostly does not move.

### 4.2 `text_only_llm` flags two-thirds of everything

Mean score 0.751, **flag rate 67.2%** at the deployed threshold of 0.75, against
a human ground truth in which **4.2%** of segments are judged not-genuine. This
is exactly the degeneracy Amendment A5 was written to guard against, and it is
why the amendment exists — declared after two probes, before any distribution
was seen.

---

## 5. P4 — the facial channel (RQ2), and why its "win" is not credible

| split | n | ρ_four − ρ_three | 95% CI | verdict |
|---|--:|--:|---|---|
| holdout | 39 | **+0.3637** | [+0.1082, +0.6425] | *four_channel wins* |
| segments where facial is present | 85 | +0.1721 | [+0.0055, +0.3392] | *four_channel wins* |
| all | 119 | +0.0917 | [−0.0180, +0.2067] | no detected difference |
| selection | 80 | −0.0197 | [−0.1349, +0.0779] | no detected difference |

Applied mechanically, two of four slices say the facial channel helps. **That
conclusion should not be drawn, for four reasons, and this section exists so the
number is not quoted without them.**

1. **Both components are null.** The "win" is the gap between ρ = −0.3033
   (`three_channel`, holdout) and ρ = +0.0604 (`four_channel`, holdout). Neither
   is distinguishable from zero. A difference between two null results is not a
   demonstration that one of them works.
2. **The mechanism is noise cancellation, not signal.** `three_channel` on
   holdout is *anti*-correlated. Adding an uninformative channel to an
   anti-correlated predictor pushes it toward zero, which the metric scores as an
   improvement. `facial_bench/v2/` measured this channel below an always-NEUTRAL
   constant on these same held-out speakers, so "it adds noise" is the
   better-evidenced explanation and it predicts exactly this pattern.
3. **The splits disagree.** Selection says −0.0197. If the facial channel carried
   signal, it would not be absent on 80 segments and decisive on 39.
4. **It rests on 19 segments.** Although the payloads differ on 34 of 39 holdout
   segments, the two systems returned **identical scores on 86 of 119** overall
   and differ on only **19 of the 39** holdout segments. The interval excluding
   zero is computed over 39 points of which 20 are tied by construction.

`PROTOCOL.md` §8.2 applies: *"No channel is removed from the pipeline on the
strength of this bench alone."* Nothing is changed. **RQ2's honest answer is that
the facial channel's contribution is not measurable at this sample size**, which
is consistent with, and no better than, what `facial_bench/v2/` already
established by a more direct route.

---

## 6. Coarseness is not the explanation

The obvious objection to §2 is that these systems emit 4–7 distinct values and
cannot correlate with an 18-value target. **That objection is measurably wrong.**

Take each system's *exact multiset of scores* and re-assign it optimally — lowest
conflict to the most genuine segment, and so on. That is the best ρ its own
granularity permits:

| system | actual ρ (all) | best its own values permit | achieved |
|---|--:|--:|--:|
| `four_channel` | +0.0575 | **+0.7974** | **7.2%** |
| `three_channel` | −0.0341 | +0.8601 | −4.0% |
| `text_only_llm` | −0.0676 | +0.8269 | −8.2% |
| `text_only_llm_anchored` | −0.1610 | +0.9279 | −17.4% |

Every system had the resolution to score ρ ≈ 0.80–0.93. They are not too blunt.
**The right scores are being assigned to the wrong segments.**

### 6.1 Finding the segments that matter

The five segments the panel judged not-genuine (h < 3) are the entire positive
class for the construct this system exists to detect. Ranked by each system's
conflict score, out of 119:

| system | ranks of the 5 target segments | in its top 5 |
|---|---|--:|
| `four_channel` | 3, 22, 49, 75, **118** | 1 |
| `three_channel` | 2, 17, 42, 62, **118** | 1 |
| `text_only_llm` | 11, 34, 36, 70, 98 | 0 |
| `text_only_llm_anchored` | 17, 58, 71, 84, 108 | 0 |
| *random* | — | 0.21 expected |

The ranks are spread across the full range. One target sits at **118 of 119** for
both channel-based systems — the deployed pipeline considers it the second *most*
authentic segment in the corpus. §7 is that segment.

---

## 7. The mechanism, in two segments

These two cases are the clearest evidence this bench produced, and they are
worth more to the report than any correlation in it.

### 7.1 Unanimous sarcasm, scored 0.0 — the minimum possible

> *"oh yeah, thank gosh I have eight lenses now in my smartphone."*
> — Marques Brownlee. **All four raters: 2. h = 2.00, across-rater SD = 0.00.**

| channel | label |
|---|---|
| transcript | **POSITIVE** |
| vocal | **POSITIVE** |
| facial | no face detected |
| comments | POSITIVE |

`four_channel` scored **0.0000** — its lowest possible output — and explained:

> *"The creator's sentiment is consistent across all channels, with a strong
> positive tone in the transcript, vocal emotion, and video comments."*

The system is maximally confident this segment is authentic **because all
channels agree**. They agree because both content channels made the *same*
mistake: sarcasm reads as positive to a sentiment classifier, and raised pitch
reads as positive arousal.

**Channel agreement is only evidence of authenticity if the channels fail
independently. Here they share a failure mode, so agreement is evidence of
nothing.** This is a structural criticism of the architecture, not of a
checkpoint, and it generalises to any consensus-based multi-channel design.

Both text-only systems scored this above zero (0.8 and 0.25), i.e. reading the
words alone did better than four channels here.

### 7.2 Sincere criticism, scored 0.8 — near the maximum

> *"I hate that it looks like a mini purse and I hate that I know Apple
> thoroughly considered…"*
> — **h = 5.00. The most genuine score the scale allows.**

Transcript NEGATIVE, vocal POSITIVE. The controller saw a cross-channel
disagreement and returned **0.800**, its second-highest score in the corpus.

Humans hear a person who is genuinely annoyed and amused at once, and read that
complexity as *sincerity*. The system reads exactly the same complexity as
*conflict*, and conflict is what it converts into an inauthenticity score.

**Corrected 08 Sep 2026.** This paragraph originally continued *"this is the
design premise operating in reverse"*, and cited §14 of the rater analysis —
transcript-NEGATIVE segments rated the **most** genuine (h = 4.392 against 3.870
for NEUTRAL, p = 0.034) — as the corpus-scale version of it. **That reading is
now measured and it is wrong**, and it was too generous to the design: a reversed
premise is a fixable sign error.

`AXIS_RESULT.md` (`PROTOCOL.md` Amendment A6, post-hoc) tests it directly.
Reversal requires human ratings to fall as cross-channel disagreement rises; the
measured association is **+0.0498** [−0.1327, +0.2287] — null, and not even the
sign a reversed premise needs. Nor is the NEGATIVE-vs-POSITIVE gap that "inverted
sign" rests on distinguishable (p = 0.113), while the committed-vs-NEUTRAL gap it
does not predict is (p = 0.037).

**The premise is orthogonal, not reversed.** The raters judged whether the
speaker meant it; every channel reports whether the content was positive or
negative. This segment is not a sign error caught in the act — it is a system
answering a different question and being scored on this one.

---

## 8. Where `four_channel`'s score comes from *(not pre-registered)*

The deployed score is the controller's answer with `_coerce_result`'s
down-weighting applied. Both halves, scored separately:

| | ρ all | ρ holdout |
|---|--:|--:|
| deployed `four_channel` | +0.0575 | +0.0604 |
| raw controller output, damping disabled | +0.0413 | +0.0826 |
| the damping indicator alone (a binary flag) | −0.0442 | +0.0603 |

Damping changed **11 of 119** scores for `four_channel` and 20 of 119 for
`three_channel`, moving the mean from 0.527 to 0.555 and 0.494 to 0.538
respectively. All three rows are null. **Neither half of the system carries
signal, so the damping rule is not rescuing an LLM that works, nor is it
destroying one.** The `vocal_bench`/`facial_bench` down-weighting remains
justified on its own measured grounds; it simply does not move this metric.

---

## 9. Sensitivity runs (§8.4, §8.5)

None of the pre-registered sensitivity analyses changes any conclusion.

| run | `four_channel` ρ all | holdout | P3 holdout verdict |
|---|--:|--:|---|
| primary | +0.0575 | +0.0604 | no detected difference |
| **author's ratings dropped** (§8.4) | +0.0636 | +0.1161 | no detected difference (−0.1179) |
| **duplicates: first presentation only** (§8.5) | +0.0488 | +0.0629 | — |
| **damping disabled** (§8.5) | +0.0413 | +0.0826 | — |

**§8.4 passes.** The primary decision does not depend on the author's ratings, so
it is not reported as author-dependent. Every other system moves by less than
0.04 under each sensitivity run.

---

## 10. What Amendment A5 bought

A5 fixed two text-only prompts in advance and gave the baseline its better
result. The two differ far more in *calibration* than in *correlation*:

| | mean score | flag rate | vs human reality | ρ (all) |
|---|--:|--:|---|--:|
| `text_only_llm` | 0.751 | 67.2% | badly miscalibrated | −0.0676 |
| `text_only_llm_anchored` | 0.284 | 29.4% | far closer | −0.1610 |
| *human ground truth* | — | **4.2%** judged not-genuine | — | — |

The anchored prompt is a much better-behaved instrument — it puts 56 of 120
segments at 0.0, which is the right *shape* for a corpus that is 95% sincere —
and it is **no better correlated**. On the full sample it is slightly worse.

**Calibration and discrimination are separate properties, and fixing the first
did not touch the second.** That is worth stating because a reader looking at the
first prompt's 67% flag rate would reasonably assume better prompting was the
fix. It was measured, and it was not.

---

## 11. What this means for the project

Stated plainly, because §1.1 of the protocol committed in advance to reporting
the losing outcome with the same detail as the winning one.

1. **The design premise is not evidenced.** *"Comparing four independent channels
   reveals brand-authenticity signal that reading the transcript alone does not"*
   remains unsupported on this project's own data. It is also not refuted in the
   direction that would favour the baseline: the text-only systems are equally
   null. **The finding is not "text-only wins", it is "none of them works".**
2. **The finding generalises, and that is the contribution.** §7.1 is a
   mechanism, not a bug: a consensus-based multi-channel architecture converts
   *correlated* channel errors into false confidence. Two channels that fail the
   same way agree, and agreement is what the design treats as evidence. Framed
   that way this is a result about orchestration architectures, which is exactly
   the framing the project's work plan anticipated.
3. **A three-line lookup table is the honest benchmark.**
   `transcript_label_neg_genuine` — no LLM, no channels, no orchestration —
   scores +0.0784 against the deployed pipeline's +0.0575. Both null; the point
   is that ~2,000 seconds of local LLM inference bought nothing over it.
4. **Nothing is changed in the pipeline** (§8.2). This bench measures.

### 11.1 What would have to be true for this to be a fixable result

Recorded so the write-up does not read as a dead end:

- The corpus is 95% sincere (rater analysis §12). A corpus with a real positive
  class — disclosed sponsorships, scripted reads, known ad segments — would test
  detection rather than ranking, and this bench cannot say the design fails there.
- Two of four channels are at or below chance for their own task, and the comment
  channel is a constant on all 12 videos (§9.1). The architecture has never been
  tested with four channels that work.
- n = 39 holdout gives an interval 0.864 wide. Only a very large effect was
  detectable.

None of these rescues the result. All three are reasons the result is *narrow*,
and they belong beside it.

---

## 12. Limitations

1. **n = 119 (39 holdout).** Meets the pre-registered floor; still small. The
   holdout interval spans 0.864 of correlation.
2. **The corpus is 95% "genuine"** — 5 of 119 segments below the midpoint. This
   is a ranking task, not a detection task.
3. **The comment channel is a constant** on all 12 videos (§9.1). "Four channels"
   is really three varying channels plus a constant.
4. **No rater was construct-naive** (rater analysis §2.1, Amendment A3).
5. **P4's two "wins" are reported and disbelieved** (§5). A reader who quotes the
   +0.3637 without §5 will draw a conclusion this bench does not support.
6. **Four slices were tested per endpoint with no multiplicity correction**,
   which was not pre-registered. At α = 0.05 and 4 slices, one interval excluding
   zero by chance is unsurprising. This is a reason to disbelieve P4's holdout
   result, and it applies equally to P3's selection result — which points the
   *other* way and is disbelieved on the same grounds.
7. **One controller, one prompt family.** A different local model might behave
   differently; `controller_bench` measured 49.08 points of Authenticity
   difference between controllers on byte-identical inputs, so this is not a
   small caveat.
8. **`pitch_mean` and `energy_mean` are 0.0** in every payload, as they were in
   `controller_bench` — absent from the cached corpus. Identical across all three
   LLM systems, so it cannot favour any of them, but the deployed pipeline sends
   real values.

---

## 13. Conclusions

1. **RQ1: no detected difference.** `four_channel` does not beat a text-only
   baseline built on the same controller, on held-out speakers, at this sample
   size. `PROTOCOL.md` §8.1's third outcome, declared in advance.
2. **RQ2: not measurable.** The facial channel's contribution is indistinguishable
   from noise; the two slices that say otherwise are explained in §5 and should
   not be quoted alone.
3. **RQ3: the human ceiling is 0.8038.** The best system reaches 7.2% of it.
4. **Every system is statistically indistinguishable from a constant**, and
   `constant` scores exactly 0.000 by construction, so the metric is sound.
5. **The failure has a mechanism and it is reportable** (§7): consensus across
   channels that share a failure mode produces confident wrong answers, and
   emotional complexity — which humans read as sincerity — is read by the design
   as conflict. `AXIS_RESULT.md` measures the second half of that and sharpens
   it: the mismatch is not an inverted premise but an orthogonal one, the
   controller faithfully detects the valence disagreement it was built to detect
   (ρ = +0.4415), and that quantity does not predict human judgement (+0.0498).
6. **Nothing in `pipeline/` is changed** (§8.2).

---

## 14. Reproduction

```bash
cd brandpulse_ai
source .venv/bin/activate
ollama serve                                     # llama3.1:8b must be pulled

python research/baseline_bench/run_bench.py               # 480 calls, ~32 min, resumable
python research/baseline_bench/run_bench.py --determinism # re-runs 10 probes per system
python research/baseline_bench/report_bench.py            # -> bench_results.json
python research/baseline_bench/verify_claims.py           # every number in both write-ups
python -m pytest tests/test_baseline_systems.py tests/test_baseline_bench.py -q
```

Every raw response is cached in `cache/<system>/<uid>.json` with its latency, so
`report_bench.py` is a pure function of files on disk and every number here can
be re-derived without a working Ollama.

Fixed throughout: seed 42, `temperature: 0`, `num_ctx: 4096`, 10,000 bootstrap
resamples, the same 120 segments in the same order for every system.
