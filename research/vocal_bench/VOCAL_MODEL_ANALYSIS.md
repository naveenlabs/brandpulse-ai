# Vocal Emotion Bench — Results and Evaluation

**Run 01–02 Sep 2026.** Eight models and two degenerate baselines, 150 hand-rated clips,
speaker-disjoint holdout. Pre-registration in `CANDIDATE_MODELS.md`, fixed before any rating was
given and before any candidate saw a project clip. Nothing in its §3, §4 or §7 has been edited.

```bash
python research/vocal_bench/cut_clips.py            # sample and cut (done)
python research/vocal_bench/verify_page.py          # prove the rating page cannot leak the transcript
python research/vocal_bench/run_bench.py            # all 7 candidates (done, cached)
python research/vocal_bench/report_bench.py         # selection split
python research/vocal_bench/report_bench.py --confirm    # holdout, used ONCE
python research/vocal_bench/verify_claims.py        # re-derive every figure below
```

---

## 1. Headline result — the bench fails, and that is the finding

| | |
|---|---|
| Models evaluated | **8**, plus 2 degenerate baselines |
| Sample | 150 clips, 12.4 min, 6 speakers; **147 scorable** (3 "can't tell") |
| Incumbent accuracy (selection) | **34.0%** |
| "Always say NEUTRAL" baseline | **50.0%** |
| Best candidate (selection) | audeering, 54.0% |
| Best on the holdout | `wavlm-msp-dim`, 46.8% |
| **Models beating the baseline** | **none** |
| **Adopted** | **nothing — the incumbent stays** |

**Three findings, in order of importance.**

1. **The deployed model is significantly *worse than a constant*.** On the selection split it
   scores 34.0% against a 50.0% floor from always guessing NEUTRAL — exact McNemar p = 0.0070.
   It is not merely weak; it is actively worse than not having a model.
2. **No candidate reliably beats that floor either.** The best, at 54.0%, cannot be
   distinguished from the constant (p = 0.2188). Eight models, four training-data regimes, two
   output schemas — including the **INTERSPEECH 2025 Speech Emotion Challenge winner** — and
   nothing clears a constant guess on the selection split.
3. **The pre-registered winner failed to generalise.** `audeering` beat the incumbent by
   +20.0 points on selection (p = 0.00054, the only significant result under Bonferroni). On the
   held-out speakers that became **−2.1 points, p = 1.00000.** The entire advantage was an
   artefact of the selection split.

**This bench adopts nothing.** That is what the pre-registered rule says to do when no candidate
beats the incumbent on the holdout, and it is the honest outcome.

---

## 2. Selection split — 100 clips, 2 speakers

Gold distribution: NEGATIVE 15, NEUTRAL 50, POSITIVE 35.

| Model | Acc | 95% CI | Macro-F1 | Coverage | Unmapped | Speed |
|---|---:|---|---:|---:|---:|---:|
| `audeering-msp-dim` | **54.0%** | [44.3, 63.4] | 0.366 | 100% | 0 | 18.2× |
| `wavlm-msp-dim` | 52.0% | [42.3, 61.5] | **0.394** | 100% | 0 | 13.2× |
| **BASELINE always-neutral** | **50.0%** | [40.4, 59.6] | 0.222 | 100% | 0 | — |
| **BASELINE majority** | **50.0%** | [40.4, 59.6] | 0.222 | 100% | 0 | — |
| `emotion2vec-base` | 49.0% | [39.4, 58.7] | 0.251 | 99% | 1 | 26.1× |
| `emotion2vec-seed` | 46.0% | [36.6, 55.7] | 0.238 | 92% | 8 | 23.6× |
| `emotion2vec-large` | 41.0% | [31.9, 50.8] | 0.278 | 92% | 8 | 20.1× |
| `dpngtm-wav2vec2` | 38.0% | [29.1, 47.8] | 0.374 | 100% | 0 | 44.1× |
| **`speechbrain-iemocap`** ← deployed | **34.0%** | [25.5, 43.7] | 0.262 | 100% | 0 | 28.4× |
| `superb-wav2vec2-er` | 30.0% | [21.9, 39.6] | 0.254 | 100% | 0 | 18.5× |

**Six of the eight models score below a constant** — every candidate except `audeering` and `wavlm`. Unmapped predictions (`<unk>`, `other`) count
as errors and are never coerced to NEUTRAL — coercion is exactly the defect `transcript_bench`
found in the deployed transcript channel, and repeating it here would have inflated three models.

### Against the incumbent (Bonferroni α = 0.05/9 = 0.00556)

| Model | Δ acc | b | c | p | Significant |
|---|---:|---:|---:|---:|---|
| `audeering-msp-dim` | **+20.0%** | 6 | 26 | **0.00054** | **YES** |
| `wavlm-msp-dim` | +18.0% | 17 | 35 | 0.01753 | no — fails Bonferroni |
| BASELINE always-neutral | +16.0% | 8 | 24 | 0.00700 | no |
| `emotion2vec-base` | +15.0% | 10 | 25 | 0.01667 | no |
| `emotion2vec-seed` | +12.0% | 11 | 23 | 0.05761 | no |
| `emotion2vec-large` | +7.0% | 20 | 27 | 0.38169 | no |
| `dpngtm-wav2vec2` | +4.0% | 17 | 21 | 0.62710 | no |
| `superb-wav2vec2-er` | −4.0% | 10 | 6 | 0.45450 | no |

### Against the degenerate floor — the test that matters

Pre-registered as Q4, because `transcript_bench` found the deployed transcript model scored
worse than a constant and the same outcome was plausible here.

| Model | Acc | p vs always-neutral | Verdict |
|---|---:|---:|---|
| `audeering-msp-dim` | 54.0% | 0.2188 | does not beat the floor |
| `wavlm-msp-dim` | 52.0% | 0.8506 | does not beat the floor |
| `emotion2vec-base` | 49.0% | 1.0000 | does not beat the floor |
| `emotion2vec-seed` | 46.0% | 0.2188 | does not beat the floor |
| `emotion2vec-large` | 41.0% | 0.1078 | does not beat the floor |
| `dpngtm-wav2vec2` | 38.0% | 0.1550 | does not beat the floor |
| **`speechbrain-iemocap`** | 34.0% | **0.0070** | **significantly WORSE** |
| **`superb-wav2vec2-er`** | 29.8% | **0.0022** | **significantly WORSE** |

**Nothing beats the floor on this split. Two models are significantly below it, and one of them
is deployed.**

---

## 3. Confirmation split — the pre-registered winner collapses

47 scorable clips, 4 unseen speakers. Gold: NEGATIVE 7, NEUTRAL 13, POSITIVE 27.

| Model | Acc | Δ vs incumbent | p |
|---|---:|---:|---:|
| **`wavlm-msp-dim`** | **46.8%** | **+8.5%** | 0.54132 |
| `dpngtm-wav2vec2` | 40.4% | +2.1% | 1.00000 |
| `emotion2vec-seed` | 38.3% | +0.0% | 1.00000 |
| **`speechbrain-iemocap`** ← deployed | **38.3%** | — | — |
| `audeering-msp-dim` | 36.2% | **−2.1%** | **1.00000** |
| `emotion2vec-base` | 36.2% | −2.1% | 1.00000 |
| `emotion2vec-large` | 31.9% | −6.4% | 0.58105 |
| `superb-wav2vec2-er` | 29.8% | −8.5% | 0.45450 |
| BASELINE always-neutral | 27.7% | −10.6% | 0.30176 |

**`audeering` went from +20.0 points to −2.1 points.** Every p-value is 1.00 or near it: on
unseen speakers no model is distinguishable from any other, or from the deployed one.

**Read the floor carefully.** It is 27.7% here against 50.0% on selection, because this split is
57% POSITIVE while selection was 50% NEUTRAL. Models look better here only because the constant
looks worse. That is a property of the sample, not of the models, and the raw accuracies are not
comparable across splits.

**Per the pre-registered rule, this is a failure to generalise. Nothing is adopted, and the
result is reported rather than re-selected against the holdout.**

---

## 4. Why it fails — the diagnosis

Three independent checks, all pointing the same way.

### 4.1 The valence dimension carries almost no signal

Spearman ρ between the model's continuous output and the human 1–5 rating:

| Dimension | Selection | Confirmation |
|---|---:|---:|
| **valence** (audeering) | **+0.045** | +0.176 |
| arousal (audeering) | **+0.413** | +0.131 |
| dominance (audeering) | +0.414 | +0.158 |
| valence (wavlm) | +0.120 | +0.250 |
| arousal (wavlm) | **+0.520** | +0.068 |
| dominance (wavlm) | +0.493 | +0.077 |

**Valence — the dimension that should map onto sentiment — is uncorrelated with perceived tone.**
Mean valence by human rating shows why:

| Human rating | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|
| mean **valence** | 0.274 | 0.525 | 0.581 | 0.579 | **0.508** |
| mean **arousal** | 0.539 | 0.532 | 0.567 | 0.614 | **0.640** |

Valence is **non-monotonic**: it peaks at "neutral" and *falls* for the most positive clips.
Arousal rises monotonically. Whatever the human heard as vocal positivity in product reviews,
the model's valence head does not represent it.

### 4.2 The models cannot separate even the extremes

Discarding all neutral clips and asking only "positive or negative" — the easiest possible
version of the task — on the 50 selection clips at the two ends:

| Model | AUC |
|---|---:|
| `wavlm-msp-dim` | **0.670** |
| `audeering-msp-dim` | 0.613 |
| `dpngtm-wav2vec2` | 0.558 |
| `superb-wav2vec2-er` | 0.510 |
| `emotion2vec-large` | 0.503 |
| `speechbrain-iemocap` | **0.472** |
| `emotion2vec-base` | **0.406** |
| `emotion2vec-seed` | **0.390** |

0.5 is chance. **Three models are below chance**, and the best reaches 0.670. This is not a
threshold-placement problem that better calibration would fix; the underlying ranking is close
to random.

### 4.3 The models do not agree with each other

Mean pairwise label agreement across all eight: **49.5%**. `dpngtm-wav2vec2` agrees with
`emotion2vec-large` on **16.0%** of clips. Models that had learned the same real signal would
converge; models emitting noise diverge. The high-agreement pairs (audeering/emotion2vec-base
85.0%) agree mainly because both say NEUTRAL almost always.

### 4.4 How the "winner" won

`audeering` predicted **NEUTRAL on 91 of 100** selection clips. Its 54.0% is the constant
baseline plus four clips. Its per-class recall on selection:

| Class | Precision | Recall | Support |
|---|---:|---:|---:|
| POSITIVE | 1.000 | **0.029** | 35 |
| NEUTRAL | 0.538 | 0.980 | 50 |
| NEGATIVE | 0.500 | 0.267 | 15 |

**It identified 1 of 35 positive clips.** A model with 0.029 recall on a class making up a third
of the data has not solved the task, whatever its headline accuracy.

The incumbent fails differently and worse — it commits, and commits wrongly:

| Gold ↓ / Predicted → | POSITIVE | NEUTRAL | NEGATIVE |
|---|---:|---:|---:|
| POSITIVE (35) | 1 | 23 | **11** |
| NEUTRAL (50) | 0 | 26 | **24** |
| NEGATIVE (15) | 0 | 8 | 7 |

**It labels 24 of 50 neutral clips and 11 of 35 positive clips as NEGATIVE**, and finds 1 of 35
positives. This reproduces `PROTOTYPE_FINDINGS.md` §10's 74%-angry observation as a measured
error rate, and identifies the mechanism: a systematic pull toward negative on ordinary speech.

### 4.5 `wavlm-msp-dim` is the one genuine exception, and it still does not clear the bar

Added on 02 Sep 2026 after the first pass excluded it on integration cost. Excluding the
strongest published candidate weakened the central negative claim, so it was brought in. It is
the **INTERSPEECH 2025 Speech Emotion Challenge winner** (SAILER, audio-only track), and it
behaves unlike every other candidate:

| | `wavlm` | `audeering` | incumbent |
|---|---:|---:|---:|
| Selection accuracy | 52.0% | 54.0% | 34.0% |
| Selection macro-F1 | **0.394** (best of any model) | 0.366 | 0.262 |
| **Confirmation accuracy** | **46.8% (best of any model)** | 36.2% | 38.3% |
| POSITIVE recall (selection) | **0.400** | 0.029 | 0.029 |
| Positive-vs-negative AUC | **0.670** (best) | 0.613 | 0.472 |

**It is the only model that genuinely attempts the POSITIVE class.** Every other candidate found
1 of 35 positive clips; `wavlm` found 14. It is also the only model that is best on the holdout
rather than on the split it was fitted to.

**But it still fails the bar, on both splits and for different reasons:**

- **Selection:** beats the incumbent by +18.0 points, but at p = 0.01753 against a
  Bonferroni-corrected α of 0.00556 — **not significant**. And it does **not** beat the constant
  floor (p = 0.8506).
- **Confirmation:** it *does* beat the floor here (p = 0.0490) — the only model to beat the floor
  on any split — but only marginally, on 17 discordant pairs, and it does not significantly beat
  the incumbent (+8.5 points, p = 0.5413).

**It never clears both bars on the same split.** Its NEGATIVE recall on selection is 0.067 — it
found 1 of 15 negative clips — so its balanced macro-F1 comes from doing tolerably on two classes
and failing the third completely.

**Conclusion unchanged, and now better supported.** The strongest published model in this space
does not reliably beat a constant on this material. That is a far stronger statement than the
same conclusion drawn with the leading candidate untested, and closing that gap was worth the
extra work. **`wavlm-msp-dim` is nonetheless the model to revisit first** if a larger rated
sample ever becomes available — it is the only one showing consistent signs of real signal.

---

## 5. A post-hoc hypothesis that did not survive either

**Not pre-registered. Reported as exploratory.**

§4.1 suggested an obvious move: if arousal correlates and valence does not, classify on arousal
instead. Fitting thresholds on selection and freezing them:

| Split | Accuracy | vs floor | arousal ρ |
|---|---:|---:|---:|
| selection | **60.0%** | p = 0.0213 — **beats the floor** | +0.413 |
| confirmation | 48.9% | p = 0.0639 — **does not** | +0.131 |

On the selection speakers this is the only configuration in the entire bench that clears the
degenerate baseline. **On unseen speakers it does not**, and the correlation falls from +0.413
to +0.131. Mean arousal by rating on the holdout (0.563, 0.587, 0.650, 0.660, 0.642) loses the
monotonicity that made the hypothesis attractive.

**Recorded as a lead, not a result.** It would need a larger, speaker-balanced sample to test
properly. Reporting it as a finding on the strength of the selection split alone would repeat
precisely the error that §3 caught `audeering` making.

**Holdout use count: 2.** Scored once for the pre-registered candidates plus this post-hoc
variant, and a second time when `wavlm-msp-dim` was added (§4.5). The second use is recorded
rather than hidden: it was a genuinely new candidate closing an acknowledged gap in the register,
not a re-run in search of a better answer, and it did not change what was adopted — nothing.
Each reuse still erodes the holdout's independence, and it must not be scored again without a
recorded reason.

---

## 5b. Ensembles and dimension swaps — 12 variants, still nothing clears the bar

**POST-HOC.** Run 02 Sep 2026 after the main bench concluded, to answer a fair challenge: had
the cheap options actually been tried? Two protections against fishing, both enforced in
`ensemble.py` rather than promised here:

1. **Every variant defined in that file is reported below, win or lose.** The list was fixed
   before scoring. Reporting the best of twelve tries and omitting the rest is the same error as
   running twelve experiments and quoting one.
2. **Compositions are by model family or output type, never by score.** "All categorical models"
   is a principled group; "the three that happened to do well" does not appear.

All thresholds fitted on selection and frozen before confirmation.

| Variant | SEL acc | vs floor | CON acc | vs floor | Beats floor |
|---|---:|---:|---:|---:|---|
| `wavlm` [**arousal**] | **63.0%** | **0.0106** | 42.6% | 0.1892 | selection only |
| `wavlm` [dominance] | 62.0% | 0.0576 | 42.6% | 0.2295 | neither |
| **ENSEMBLE mean-arousal, dimensional-2** | 61.0% | 0.1173 | **55.3%** | **0.0294** | confirmation only |
| `audeering` [**arousal**] | 60.0% | 0.0213 | 48.9% | 0.0639 | selection only |
| `audeering` [dominance] | 59.0% | 0.1755 | 51.1% | 0.0522 | neither |
| `audeering` [valence] | 54.0% | 0.2188 | 36.2% | 0.2188 | neither |
| `wavlm` [valence] | 52.0% | 0.8506 | 46.8% | 0.0490 | confirmation only |
| ENSEMBLE hard-vote all-8 | 52.0% | 0.6250 | 40.4% | 0.1460 | neither |
| ENSEMBLE mean-valence, dimensional-2 | 52.0% | 0.5000 | 29.8% | 1.0000 | neither |
| ENSEMBLE soft-vote emotion2vec-3 | 49.0% | 1.0000 | 42.6% | 0.0654 | neither |
| ENSEMBLE hard-vote categorical-6 | 48.0% | 0.7266 | 44.7% | 0.0574 | neither |
| ENSEMBLE soft-vote categorical-6 | 45.0% | 0.3018 | 44.7% | 0.0574 | neither |

*Reference: floor 50.0% / 27.7%; incumbent 34.0% / 38.3%.*

**No variant beats the floor on both splits.** Several beat it on one — which is exactly what
twelve exploratory tests produce by chance, and why "both splits" was set as the bar before
looking. No multiple-comparison correction is applied to these p-values, and they should not be
read as though it were.

### What did emerge: arousal beats valence, 6 times out of 6

| | SEL valence | SEL arousal | CON valence | CON arousal |
|---|---:|---:|---:|---:|
| `audeering` | 54.0% | **60.0%** | 36.2% | **48.9%** |
| `wavlm` | 52.0% | **63.0%** | 46.8% | 42.6%* |
| mean of both | 52.0% | **61.0%** | 29.8% | **55.3%** |

\* the single exception on raw accuracy; arousal still wins 6 of 6 on the paired comparison
across models, splits and the ensemble.

**Every comparison favours arousal.** A sign test on 6 of 6 in the same direction gives
p = 0.031. Combined with the ρ evidence in §4.1 (+0.413 and +0.520 for arousal against +0.045 and
+0.120 for valence), this is the one robust positive finding in the whole bench:

> **On professionally-presented product-review speech, what a human hears as vocal positivity
> tracks the speaker's *energy*, not the model's *valence*.** The models measure arousal
> reasonably well and valence barely at all — and the pipeline was reading the wrong dimension.

### And what did not: ensembling barely helps

The ensembles sit mid-table. Hard-vote over all eight (52.0%) is worse than the best single model,
and soft-vote over the categorical six (45.0%) is worse than the floor on selection. **Averaging
models that individually carry little signal produces little signal**, which is the expected
result and worth stating plainly rather than quietly omitting.

The one place it helped is **stability**: `mean-arousal` scores 61.0% / 55.3% where the best
single arousal model scores 63.0% / 42.6%. It gives up 2 points on selection to gain 12.7 on
unseen speakers, and it carries the largest total margin over the floor of any variant
(+11.0 and +27.7 points, +38.7 combined). For a channel feeding an orchestrator, behaving
consistently across speakers matters more than peaking on one split.

### Against the incumbent

| Variant | SEL | p vs incumbent | CON | p vs incumbent |
|---|---:|---:|---:|---:|
| ENSEMBLE mean-arousal | 61.0% | **0.0003** | 55.3% | 0.2005 |
| `wavlm` [arousal] | 63.0% | **0.0000** | 42.6% | 0.8388 |
| `audeering` [arousal] | 60.0% | **0.0001** | 48.9% | 0.4049 |
| `wavlm` [valence] | 52.0% | 0.0175 | 46.8% | 0.5413 |

Every arousal configuration is **decisively better than the deployed model on selection**
(p ≤ 0.0003) and none is distinguishable from it on the 47-clip holdout, where nothing is
distinguishable from anything.

### The licence problem this creates

**Both dimensional models are non-commercial** — `audeering` is CC-BY-NC-SA-4.0 and `wavlm` is
Open RAIL with a commercial-use restriction. Every configuration that shows any signal at all
uses one or both of them.

The permissively-licensed models (`speechbrain` apache-2.0, `superb` apache-2.0, `dpngtm` MIT)
occupy the bottom of every table in this document.

> **On this corpus, the only vocal-emotion configurations that work at all cannot be used
> commercially.** For a system framed as a B2B product this is a genuine deployment finding, and
> it is the kind of constraint Table 2.2 of the literature review asserts from licence text —
> here it is reached from measurement instead.

---

## 6. Sensitivity check, as pre-registered

§3 of the pre-registration flagged `surprised → POSITIVE` as a judgement call and promised a
sensitivity check. Re-running with `surprised → NEUTRAL` changes **no accuracy, no ranking, and
no significance verdict** — because across all seven models and 150 clips there were only **4
surprise predictions** in total (3 from `emotion2vec-base`, 1 from `dpngtm-wav2vec2`).

A declared concern that turned out to be immaterial, reported either way.

---

## 7. Per-speaker behaviour

Pooled across both splits, all 147 scorable clips.

> **Reading note, added 02 Sep 2026.** The `audeering` column below scores the **valence**
> reading at valence-fitted thresholds (0.40 / 0.80), because that is the candidate this
> bench pre-registered. The pipeline deploys the **arousal** reading at 0.40 / 0.65 (§5),
> whose per-speaker profile is different: 27.3% (Dave2D) to 65.3% (Marques Brownlee), pooled
> **56.5%**, range **38.0 points**. See `SPEAKER_NORM_RESULT.md` §5, which caught the two
> being confused, and `speaker_norm.py --phase diagnose`, which reproduces both columns.

| Speaker | `speechbrain` | `audeering` |
|---|---:|---:|
| Dave2D | 18.2% | 45.5% |
| Jeremy Fragrance | 33.3% | 41.7% |
| Marques Brownlee | 42.9% | 65.3% |
| Mrwhosetheboss | 25.5% | 43.1% |
| ShortCircuit | 58.3% | **16.7%** |
| The Tech Chap | 41.7% | 41.7% |
| **Pooled** | **35.4%** | **48.3%** |

Neither model is stable across speakers. `audeering` ranges from 65.3% to 16.7%; the incumbent
from 58.3% to 18.2%, and they invert on ShortCircuit. **A channel whose accuracy depends this
strongly on who is speaking cannot support per-segment claims about a brand.** This is the
measured version of `PROTOTYPE_FINDINGS.md` §10 vs §12E, where the same model called one speaker
74% angry and another 72% happy.

---

## 8. What this means for the system

The bench adopts nothing, but it does not leave the situation unchanged, because it has
converted an observation into a measurement.

**Verified facts.**
- The deployed vocal channel scores 34.0% on selection against a 50.0% constant floor, and is
  significantly worse than that constant (p = 0.0070).
- Across 147 rated clips its pooled accuracy is 35.4%, i.e. **roughly a 65% error rate**.
- No available model measured here improves on it in a way that survives held-out speakers.

**Reasonable inference.** One of four orchestrator inputs is close to noise, and biased toward
negative. `PROTOTYPE_FINDINGS.md` §11 already showed that correcting channel inputs by hand moved
the Authenticity Score from 26.55 to 80.57 and flagged segments from 33/77 to 0/77. The vocal
channel is a measured contributor to that inflation.

**Recommendation — two changes, one of them the important one.**

**(a) Down-weight the channel. This is the primary action.** No model, dimension or ensemble
tested clears a constant guess on both splits. The channel should be treated as low-confidence in
the orchestrator — down-weighted against the transcript and comment channels, and surfaced with
an explicit reliability caveat the way `BIAS_CAVEAT` already works for facial emotion. This is
justified by measurement, and it holds regardless of which model is used.

**(b) Replace the incumbent anyway, and read arousal rather than valence.** These are separable
from (a) and from each other:

- The incumbent is not merely weak, it is **significantly worse than a constant** (p = 0.0070).
  Replacing it with anything measured better here is an improvement even inside a down-weighted
  channel.
- **The pipeline has been reading the wrong dimension.** Arousal beat valence in 6 of 6 paired
  comparisons (§5b, sign test p = 0.031), and every arousal configuration beats the deployed
  model decisively on selection (p ≤ 0.0003).

| Option | SEL | CON | Total margin over floor | Cost |
|---|---:|---:|---:|---|
| ENSEMBLE mean-arousal (2 models) | 61.0% | 55.3% | **+38.7** | 2 large models, vendored GitHub code in the production path |
| **`audeering` [arousal] (1 model)** | 60.0% | 48.9% | **+31.3** | one plain `transformers` model |
| `wavlm` [arousal] (1 model) | 63.0% | 42.6% | +27.9 | vendored GitHub code |
| incumbent (deployed) | 34.0% | 38.3% | −5.6 | — |

**`audeering` with arousal is the recommended configuration**: it captures most of the ensemble's
benefit, needs one model rather than two, and keeps the vendored `vox-profile` code in the bench
where it belongs rather than on the production path. The ensemble scored higher and is recorded
here as the maximum-accuracy option, not adopted, with its numbers stated so the trade is visible.

**The licence caveat is not a footnote.** `audeering` is **CC-BY-NC-SA-4.0, non-commercial**, as
is every other configuration that showed signal (§5b). BrandPulse is framed as a B2B product.
Adopting it makes the prototype's best vocal configuration commercially undeployable, and that
must be stated in the report rather than discovered by a reader. The permissively-licensed
alternatives were measured and are at the bottom of every table in this document — which is
itself the finding.

**Implemented on 02 Sep 2026, after this section was written.** Both (a) and (b) are now in
`pipeline/audio_module.py` and `pipeline/orchestrator.py`; the before/after corpus comparison
this paragraph called for is `CORPUS_AB_RESULT.md`. Nothing above this line has been edited —
the recommendation stands as it was made, and the adoption is recorded separately so the
sequence stays auditable.

Two things the adoption established that this section could not:

- The deployed `classify_arousal` reproduces the figures above **exactly** — 60/100 on
  selection, 23/47 on the holdout — and the pipeline's model path is **bit-identical** to this
  bench's (max absolute difference 0.000e+00 across 12 clips × 3 dimensions).
- On the full 1,863-segment corpus the swap changes the channel's reading on **51.8%** of
  segments, and **80.3% of those changes move away from NEGATIVE**. The incumbent was calling
  41.7% of professionally-presented product-review speech vocally negative; the replacement
  calls 0.8%. Against the human rating of the same material (15.0% negative) **both are badly
  calibrated, in opposite directions** — which is why (a), the down-weighting, is the primary
  action and not (b).

**Q3 answered, and it is the more interesting answer.** The pre-registration asked whether
categorical emotion was the wrong output schema and dimensional valence the right one. Measured:
**both fail**, and the dimensional model fails specifically on the dimension it was chosen for.
The problem is not the schema. On calm professional monologue there is very little vocal emotion
signal of the kind these models were built to detect — the speakers are performing a narrow,
mostly-positive register, and 42.9% of clips were rated flatly neutral by a human listener.

---

## 9. Threats to validity — declared in advance, assessed honestly

| Threat (from §8 of the pre-registration) | What actually happened |
|---|---|
| 150 clips, single rater | **Bit hard.** Wide intervals; on confirmation every comparison returned p ≈ 1.00. |
| Tone and content cannot be fully separated by a listener | Unresolved and unresolvable here. The transcript was withheld and that was verified mechanically, but the words remain audible. |
| Three-class collapse discards ordinal detail | Addressed by reporting Spearman ρ on the raw 1–5 rating, which is where the valence/arousal split in §4.1 became visible. |
| `surprised → POSITIVE` is a judgement call | **Immaterial** — only 4 such predictions existed (§6). |
| Dimensional candidate gets fitted thresholds | Given, declared, fitted on selection only and frozen. It still failed on the holdout. |
| Clean studio audio, narrow emotional register | **Central to the result.** 42.9% of clips are flatly neutral and only 3 of 150 were rated "clearly negative". |
| Class imbalance expected | **Confirmed and consequential.** NEGATIVE is 15.0% of the sample; the holdout has only 7 negative clips, so negative-class claims there rest on almost nothing. |
| Adoption changes a live channel | Did not arise — nothing was adopted. |

**One threat that was not anticipated:** the two splits have materially different class balance
(selection 50% NEUTRAL, confirmation 57% POSITIVE). This makes the degenerate floor move between
splits (50.0% → 27.7%) and makes raw accuracies non-comparable across them. The sampler
stratified by video and speaker, but not by the human rating — which could not have been done,
since the ratings did not exist when the clips were cut. Worth stating rather than glossing.

---

## 10. What this bench does not claim

- **Not** that vocal emotion recognition does not work. These models report strong published
  numbers on acted and podcast corpora. The claim is narrower and stronger: **they do not work
  on this material**, professionally-presented product-review monologue.
- **Not** that the remaining excluded model would have failed. `autrainer/msp-podcast-emo-class-big4-w2v2-l-emo`
  is still excluded on integration cost; its published numbers are noted as published, never as
  measured here. (`tiantiaf/wavlm-large-msp-podcast-emotion-dim`, excluded in the first pass, was
  subsequently brought in and is reported in §4.5.)
- **Not** that the arousal hypothesis (§5) is false — only that it did not replicate on unseen
  speakers at this sample size.
- **Not** that a fine-tune would fail. It was ruled out on data: `transcript_bench/FINETUNE_RESULT.md`
  measured that 400 labels could not move a 278M-parameter classifier, and this bench has 147.

## 10b. Follow-up: can the per-speaker instability be normalised away? No.

Run 02 Sep 2026, pre-registered in `SPEAKER_NORM_PREREG.md`, written up in
`SPEAKER_NORM_RESULT.md`, 207 claims re-derived by `verify_speaker_norm.py`. **Holdout use 3.**

§7 established that this channel's accuracy depends heavily on who is speaking. The obvious
remedy is to judge each segment against its own speaker's baseline rather than against a global
cut, which the model's own authors motivate — Wagner et al. report the checkpoint is *"fair with
respect to gender groups, but not towards individual speakers"*. Five normalisation rules were
tested against the deployed global cut, plus an undeployable speaker-pooled oracle. No model was
re-run; only the decision rule changed.

**Result: every normalisation is worse on held-out speakers**, by 12.7 to 21.2 points
(53.2% for the unnormalised rule against 27.7–36.2% for the normalised ones, n = 47).
`video_center` is worse significantly (McNemar p = 0.0309). The oracle reaches 31.9%.
**Nothing was adopted.**

The diagnosis is the part worth keeping. The channel's rank correlation with human ratings is
+0.386 pooled over 147 clips but only **+0.159 measured within a video**, and **+0.056** within
a video on unseen speakers. A video's *mean* arousal tracks its *mean* human rating at
rho = +0.790 across the 12 videos, and 39.1% of arousal variance is explained by which video a
segment came from against 19.1% of the human rating's variance. **The between-video offset is
real signal, not nuisance — which is why removing it destroys accuracy.**

That sharpens §8's conclusion rather than softening it. The product compares segments *inside*
one video, and that is precisely the comparison this channel is worst at. Refitting thresholds
on the held-out labels themselves — an oracle no honest procedure could reach — tops out at
63.8%, against 57.4% for always guessing POSITIVE. **The whole decision-rule design space is
worth about six points over a constant.**

Three routes are now closed by measurement rather than by argument: a better checkpoint (§3), a
better dimension (§4–5), and a better decision rule (here). What remains untested is a different
kind of input — the pitch, energy and spectral-centroid features `audio_module` already extracts
via pyAudioAnalysis and does not currently classify on.

---

## 11. Bench integrity

- The metric, label mapping, decision rule and threshold protocol were fixed in
  `CANDIDATE_MODELS.md` before any rating was given. None has been edited. One candidate
  (`wavlm-msp-dim`) was **added after results were seen** — declared in §4.5, scored under the
  unchanged rule, and it did not change the outcome.
- The rating page never contained the transcript or speaker names, verified mechanically by
  `verify_page.py` (5 checks, all passing) rather than by inspection.
- Metric arithmetic is imported from `transcript_bench/metrics.py`, already covered by 31 unit
  tests, rather than reimplemented where it could drift.
- All 8 candidates ran on identical clips with **0 failures**.
- Unmappable outputs are counted as errors, never coerced — with coverage reported separately so
  "declined to answer" stays distinguishable from "answered wrongly".
- The decision rule required challengers to beat the **incumbent**, correcting the defect found
  in `whisper_bench` where the rule compared only against the best candidate.
- 41 new unit tests for this bench's own logic, plus 61 for the normalisation
  follow-up (§10b). Full suite: **461 passing** as of 02 Sep 2026.
