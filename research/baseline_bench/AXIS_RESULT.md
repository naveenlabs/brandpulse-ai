# baseline_bench — the system and the raters are measuring different things

**Post-hoc, exploratory, and declared as such.** `PROTOCOL.md` Amendment A6.
Specified after P1 was known, so it explains a result rather than testing a
prediction. Every pre-registered number in `BASELINE_ANALYSIS.md` is unchanged:
same 119 segments, same §5.4 ground truth, same cached LLM responses, nothing
re-run, no rating collected or revised after the result was seen.

Produced by `axis_analysis.py` (writes `axis_results.json`, 500 splits /
1,000 permutations / 10,000 bootstrap resamples, seed 42). Every statistic below
was independently re-derived against `scipy.stats` and matched to 0.00e+00 to
1.08e-19.

---

## 0. Headline

P1 measured that `four_channel` does not predict human judgement of genuineness
(ρ = +0.0575, CI spanning zero, against a human ceiling of 0.8038).
`BASELINE_ANALYSIS.md` §7 explained that as the design premise *operating in
reverse* — the system reading sincerity as conflict. **That explanation is too
generous to the design, and this analysis replaces it.**

Three measurements, in the order they build:

1. **The raters were not tracking sentiment direction.** Against human ratings,
   signed transcript valence gives ρ = **−0.0784** [−0.2587, +0.1066] — null.
   Its *magnitude*, "did the speaker take a position at all", gives ρ =
   **+0.1909** [+0.0162, +0.3635] — the interval excludes zero. Paired on the
   same resamples, magnitude beats sign by **+0.2694** [+0.0640, +0.4856], an
   interval that also excludes zero. Positive and negative segments are not
   distinguishable from each other (p = 0.113); committed and neutral segments
   are (p = 0.037).

2. **The system is faithful to its own design.** Its conflict score tracks
   cross-channel valence disagreement at ρ = **+0.4415** [+0.3025, +0.5620] —
   the strongest association this bench has measured for any controller output,
   and **7.67×** its association with human judgement. The same human judgement
   against that same disagreement quantity: ρ = **+0.0498** [−0.1327, +0.2287],
   null, and not even the sign the premise requires.

3. **No rule over these channels can close the gap.** For a predictor that is
   constant within a channel-label group, Spearman ρ is bounded above by the
   correlation ratio of the rank vector. That bound is **η = +0.4647** — a
   *proof*, covering every prompt, every LLM and every threshold that reads only
   these labels — and **57.8% of the human ceiling**. The best ordering actually
   achievable reaches **+0.4367**, and that only by overfitting 119 points into
   27 groups. Evaluated honestly on disjoint splits it falls to **+0.0551**
   [−0.1984, +0.2782] against a null of +0.0049.

**The conclusion is not that the fusion rule is inverted, or mistuned, or badly
prompted. It is that the four channels do not carry the construct.** Every
channel reports valence; the raters judged commitment. A better prompt, a better
threshold, or a better checkpoint moves a system along the first axis, and the
target is on the second.

---

## 1. The claim being tested

After P1, the author described how the four raters had actually answered §5.3's
question — *"Is this person being genuine here?"* — and subsequently confirmed
(Amendment A7) that this was the instruction given to the other three before they
rated, so it is the definition all four applied:

> sincere praise → 5. Sincere criticism → **also 5**. Insincere praise → 1.
> Whether the content was positive or negative never entered the rating.

If that is right, the ratings live on a **sincerity** axis: *does this person
mean it?* Every channel in the pipeline reports a **valence** axis:
*is this positive or negative?* Two axes, not one inverted axis.

The distinction matters because it changes what the null result implies. An
inverted premise is a bug with a fix — flip a sign, re-prompt the controller.
Two different axes is a statement about what the architecture can measure at all.

---

## 2. Method

The 119 segments are exactly P1's: at least `MIN_USABLE = 3` usable ratings
(`PROTOCOL.md` §5.4). `h` is the mean human rating; `c` is the deployed
`four_channel` score read from the same cached responses P1 used.

Each channel label is mapped to valence — `POSITIVE +1, NEUTRAL 0, NEGATIVE −1`,
with the seven FER classes collapsed onto the same axis (`happy`/`surprise` +1,
`neutral` 0, `sad`/`fear`/`angry`/`disgust` −1). A missing face is **absent, not
zero**: "no evidence" and "neutral evidence" are different inputs, and merging
them would manufacture agreement that was never observed.

`build_rows` asserts that the labels the raters' clips were built from
(`sample.json`) are byte-identical to the labels the controller was shown
(`cache/four_channel/*.json`), for all four channels on all 119 segments. If a
page or a payload had been rebuilt from a different pipeline run, every number
here would be comparing two different worlds; the run aborts rather than produce
them.

**Disagreement** `D(s)` is the population standard deviation of the valences the
controller was actually shown — zero when every channel agrees, larger as they
spread. It involves no LLM, so correlating it against the LLM's output asks a
clean question: did the controller detect the thing it was asked to detect?

---

## 3. A1 — direction versus commitment

| channel | n | ρ(h, signed valence) | ρ(h, \|valence\|) | difference, paired |
|---|--:|--:|--:|--:|
| **transcript** | 119 | −0.0784 [−0.2587, +0.1066] | **+0.1909 [+0.0162, +0.3635]** | **+0.2694 [+0.0640, +0.4856]** |
| vocal | 119 | −0.0525 [−0.2192, +0.1179] | −0.0525 [−0.2192, +0.1179] | +0.0000 — *identity, see below* |
| facial | 85 | +0.0591 [−0.1470, +0.2586] | +0.0010 [−0.2123, +0.2158] | −0.0581 [−0.3386, +0.2280] |

**The transcript row is the finding.** Direction predicts nothing. Magnitude
predicts, weakly but with an interval clear of zero, and beats direction by an
amount whose interval is also clear of zero. That is the author's account,
measured: *taking a position* reads as genuine, and *which* position does not
matter.

**The vocal row is an identity, not a result.** The vocal channel emitted
`NEUTRAL` on 95 segments and `POSITIVE` on 24, and **`NEGATIVE` on none of the
119**. With no negative values, |v| = v identically, and the paired difference is
exactly 0.0000 by construction rather than by measurement. It is reported to make
that visible: a channel that never emits one of its three classes cannot express
direction at all, which is a further limitation of that channel on top of the
48.9% held-out accuracy in `vocal_bench`.

**The facial row is null in both forms**, consistent with `facial_bench/v2/`,
where every emotion model scored below an always-NEUTRAL constant on held-out
speakers.

---

## 4. A2 — testing direction directly

| transcript label | n | mean h |
|---|--:|--:|
| NEGATIVE | 15 | **4.392** |
| POSITIVE | 29 | 4.022 |
| NEUTRAL | 75 | 3.870 |
| *committed (POS ∪ NEG)* | 44 | *4.148* |

Rank-based permutation tests, 20,000 shuffles, seed 42, add-one smoothed
(cross-checked against Kruskal–Wallis: 0.1114 and 0.0381):

- **POSITIVE vs NEGATIVE: p = 0.1129.** Not distinguishable. Direction does not
  move the rating.
- **committed vs NEUTRAL: p = 0.0374.** Distinguishable. Commitment does.

The ordering is **non-monotonic in valence** — both extremes above the middle —
which is why a signed correlation finds nothing. A quantity that rises at both
ends of an axis is not a function of that axis.

`BASELINE_RATER_ANALYSIS.md` §14 reported the same three means and read them as
*"transcript sentiment carries real signal, with an inverted sign"*. On these
tests that reading is wrong: the NEGATIVE–POSITIVE gap that an inverted sign
requires is not distinguishable from zero, and the committed–neutral gap that it
does not predict is. **§14's conclusion 1 should be read as superseded by this
section.** Its conclusions 2 and 3 (vocal and facial carry nothing) stand.

---

## 5. A3 — the system does what it was built to do

| | ρ | 95% CI | excludes 0 |
|---|--:|---|:-:|
| conflict score vs valence disagreement | **+0.4415** | [+0.3025, +0.5620] | ✓ |
| raw controller output vs disagreement | +0.3839 | [+0.2358, +0.5107] | ✓ |
| conflict score vs count of distinct valences | +0.4877 | [+0.3694, +0.5889] | ✓ |
| **human rating vs valence disagreement** | **+0.0498** | [−0.1327, +0.2287] | ✗ |
| human rating vs count of distinct valences | +0.0849 | [−0.0894, +0.2552] | ✗ |

Replicated on the 39 held-out segments: conflict vs disagreement **+0.5451**
[+0.3194, +0.7206], human vs disagreement **−0.0983** [−0.4121, +0.2393].

This is the pivot of the whole argument. **The controller is not broken.** It
detects cross-channel valence disagreement, at 7.67× the strength of its
association with the thing it is supposed to predict. The failure is upstream of
the LLM, upstream of the prompt, and upstream of `CONFLICT_FLAG_THRESHOLD`: the
quantity the architecture converts into an authenticity score is a quantity
humans do not use.

Note the sign. The design premise says disagreement should mean *less* genuine,
so ρ(h, D) should be strongly **negative**. It is +0.0498 — null, and pointing
the wrong way for the premise even in its noise.

**One structural fact makes this worse.** Distribution of `D` across the 119:

| D | 0.000 | 0.433 | 0.471 | 0.500 | 0.707 | 0.816 | 0.829 | 0.943 | 1.000 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| segments | **3** | 30 | 27 | 24 | 16 | 2 | 13 | 3 | 1 |

**Only 3 of 119 segments (2.5%) had all channels agreeing.** The system's
"conflict detected" state is not an exception it flags; it is the state 97.5% of
ordinary, sincere product-review footage is already in. A signal that is on
almost always cannot discriminate, whatever it means.

---

## 6. A4 — the ceiling on any rule over these channels

How well could *any* rule over these channels do, if it were handed the answers?

Spearman is Pearson on ranks, so a predictor that is constant within a
label-group correlates with `h` exactly as far as the group structure allows.
Maximising a Pearson correlation against a group-constant vector is the
**correlation ratio**, η = √(between-group variance of ranks ⁄ total variance),
attained at the group mean rank. **η is therefore a proven upper bound** on every
rule that reads only these labels — every prompt, every LLM, every threshold,
every future checkpoint.

η is not always attainable, because what enters the correlation is the
predictor's own *mid-ranks*, which an ordering cannot always place
proportionally. So the largest value actually reachable is searched for
separately — exhaustively over all orderings at ≤ 8 groups, and by seeded
pairwise-swap local search with 60 restarts above that — and it brackets η from
below. The simple group-mean oracle is reported as a third column to show it
understates the ceiling slightly, which is why it is not used as the bound.

The out-of-sample column is the honest expectation for a real system.

| labels used | groups | sing. | **η — proven bound** | best achievable | group-mean | repeated split ×500 | null |
|---|--:|--:|--:|--:|--:|--:|--:|
| transcript | 3 | 0 | +0.2397 | +0.2177 *(exhaustive)* | +0.2177 | +0.1587 [−0.1665, +0.3932] | +0.0042 |
| transcript + vocal | 6 | 0 | +0.2866 | +0.2530 *(exhaustive)* | +0.2454 | +0.1310 [−0.1493, +0.3582] | −0.0015 |
| **all three channels** | 27 | 7 | **+0.4647** | **+0.4367** *(search)* | +0.4348 | **+0.0551 [−0.1984, +0.2782]** | +0.0049 |
| disagreement `D` alone | 9 | 1 | +0.3224 | +0.2902 *(search)* | +0.2883 | +0.1367 [−0.1323, +0.3670] | −0.0026 |

Comments are excluded: `POSITIVE` on 119 of 119, so the channel is a constant and
adds no groups.

**Read the columns together.** The proven bound, with all three channels and
119 points fitted into 27 groups, is 0.4647 — **57.8% of the 0.8038 human
ceiling**, and that is the number no rule over these labels can exceed *even
with the answer key*. The best actually reachable is 0.4367 (54.3% of the
ceiling). Evaluated on segments it has not seen, the same structure returns
+0.0551 against a null of +0.0049, i.e. nothing. The truth for a real system lies
between those, and both ends are far below what a human reaches from the clip
alone.

Every split estimate sits inside its own null band, so **no rule over these
labels is distinguishable from chance out-of-sample at n = 119.** That is a
statement about the channels, not about any model that reads them.

### 6.1 Scope of this bound, stated precisely

The oracle bounds **systems that reduce each channel to its categorical label and
combine them** — which is the architecture's stated premise, and which A3 shows
is empirically what the deployed conflict score tracks. It does **not** bound
everything the controller could in principle do, because the payload also carries
the raw transcript text, the confidence values, `pitch_mean_hz` and
`energy_mean`. A system that read the words themselves is not covered by this
ceiling — and `text_only_llm`, which does exactly that, was also null in P1
(ρ = −0.0676), for reasons of its own.

### 6.2 An estimator that had to be thrown away

Leave-one-out group means were the obvious out-of-sample estimator and are
**invalid here**. The LOO prediction for segment *i* is (S_g − h_i)/(n_g − 1), a
strictly *decreasing* function of h_i, so within every group the predictions are
perfectly rank-reversed against the truth.

Measured rather than argued: under a permutation null on this data — labels
held fixed, `h` permuted, so no information can survive — the LOO oracle on
transcript labels returns ρ = **−0.4697** [−0.8312, −0.2667]. **The observed
−0.2722 falls inside that band**, so it is entirely consistent with the labels
carrying nothing, and the large negative value is a property of the estimator
rather than of the data. Reported as a correlation it would have read as strong
evidence that transcript sentiment is *anti*-predictive of genuineness — a
confident, publishable, entirely artefactual finding, and one that happens to
point the same way as the "inverted sign" reading §4 supersedes.

10-fold cross-validation is better but still biased (null −0.1653), because a
fold's members are removed from each other's training group mean. Repeated
disjoint train/test splits are unbiased here — null +0.0049, +0.0042, −0.0015,
−0.0026 across the four granularities — and the conclusions rest on those.

---

## 7. A5 — sensitivity

`surprise` is the only unsigned FER class and the only arbitrary mapping
decision. Re-running with `surprise = 0` instead of +1:

| | primary | surprise = 0 |
|---|--:|--:|
| ρ(h, facial signed), n = 85 | +0.0591 | +0.0512 |
| ρ(h, facial \|valence\|), n = 85 | +0.0010 | −0.0135 |
| ρ(conflict, disagreement) | +0.4415 | +0.4355 |
| all-channel oracle, in-sample | +0.4348 | +0.4348 |

It occurs on 3 of 119 segments and moves nothing. The oracle is identical because
it groups on labels, not on the valence mapping.

---

## 8. What this changes

**`BASELINE_ANALYSIS.md` §7.2** framed the sincere-criticism segment as *"the
design premise operating in reverse"*. That is now measured to be wrong, and §7.2
has been corrected in place with a pointer here. The premise is not reversed —
it is orthogonal. A reversed premise would show up as a strong negative ρ(h, D);
what is there is +0.0498.

**§7.1 stands unchanged.** The sarcasm case — all four channels agreeing because
two of them share a failure mode — is a real and separate defect, and the
strongest single illustration this project has.

**`BASELINE_RATER_ANALYSIS.md` §14 conclusion 1** ("inverted sign") is superseded
by §4 above. Conclusions 2 and 3 stand.

**What does not change.** No model choice is re-opened, no channel is re-benched,
no pipeline code is touched, and the six adoption decisions in `comment_bench`,
`transcript_bench`, `whisper_bench`, `vocal_bench`, `facial_bench` and
`controller_bench` are all unaffected — every one of them measured whether a
model reads its own channel correctly, and that question is untouched by this
one. What is affected is the claim the *combination* was ever able to support.

---

## 9. Limitations

1. **Post-hoc.** The hypothesis was formed after seeing the null. It is a
   well-measured explanation, not a confirmed prediction, and a confirmatory test
   would need a fresh corpus and a pre-registered statement of the construct.
2. **Range restriction.** Human ratings run **1.625–5.000**, with only 3 of 119
   segments below 2.5 and a mean of 3.973. The corpus is overwhelmingly sincere,
   so the low-sincerity end of the axis is barely sampled and every correlation
   here is attenuated. This is the single biggest threat to §10's conclusions:
   the channels are being asked to rank sincere clips against each other, not to
   separate sincere from insincere.
3. **n = 119, and 15 NEGATIVE segments.** The direction test rests on 29 vs 15.
   Its non-significance is weak evidence of absence, and is reported as such —
   the load-bearing claim is the *paired* comparison in §3, where the interval
   excludes zero.
4. **The valence collapse is a modelling choice.** Seven FER classes onto one
   axis discards intensity, and a different collapse could give different facial
   numbers. The facial channel is null under both mappings tried.
5. **`D` is one summary of disagreement.** Standard deviation weights a
   POSITIVE/NEGATIVE clash the same as two NEUTRAL/POSITIVE ones. The distinct-
   value count is reported alongside it and gives the same answer.
6. **The oracle bounds label-based fusion only** (§6.1), not a system that reads
   the raw text.
7. **The construct was taught, not independently arrived at** (Amendment A7,
   added after this analysis was written). The author briefed the other three on
   how to apply the scale — genuine means the speaker means it, direction
   irrelevant — before they rated. This *strengthens* §1: the construct is known
   for all four by instruction rather than inferred for one by introspection.
   It *weakens* the human ceiling used for comparison throughout, because α,
   ICC and ρ = 0.8038 now measure agreement after shared instruction from a
   participant. Every "% of the human ceiling" figure here is therefore a
   **lower bound** on relative performance. It does not affect §5 or §6, which
   compare the system against the ratings rather than against the ceiling, and
   it cannot turn P1's null into a win.

---

## 10. Conclusions

1. **The raters judged commitment, not valence.** Magnitude of transcript
   sentiment predicts their ratings; direction does not; magnitude beats
   direction by +0.2694 [+0.0640, +0.4856].
2. **The controller correctly detects the thing it was designed to detect**
   (ρ = +0.4415 with cross-channel valence disagreement, +0.5451 on the
   holdout), and that thing does not predict human judgement (+0.0498, null,
   wrong sign for the premise).
3. **The channels almost never agree** — 3 of 119 segments — so "conflict" is
   the default state of ordinary sincere footage rather than a detectable event.
4. **No rule over these channel labels reaches human performance**, even fitted
   directly on the answers. The bound is a proof, not a search result:
   η = 0.4647 against a 0.8038 human ceiling, best achievable 0.4367, and
   +0.0551 out-of-sample against a null of +0.0049.
5. Therefore the null result in P1 is **not a tuning failure and not a prompt
   failure**. The system measures valence agreement; the raters measured
   sincerity; the two are close to unrelated on this corpus.

The honest one-line statement of what this project measured: *a multimodal
consensus architecture, each of whose six components was independently benched
and adopted on its own measured accuracy, produced a combined signal that does
not predict the construct it was built to estimate — because the construct is not
on the axis the channels report.* That is a negative result with a mechanism, an
upper bound, and a stated scope, and it generalises past this prototype to any
consensus-based design whose channels all report sentiment.

---

## 11. Reproduction

```bash
cd brandpulse_ai/baseline_bench
source .venv/bin/activate
python axis_analysis.py          # ~70 s, writes axis_results.json
python verify_axis_claims.py     # re-derives every number in this file
```

No Ollama call is made: the analysis reads the cached responses P1 used. The run
is deterministic — seed 42 throughout — and `axis_results.json` regenerates
byte-identically.
