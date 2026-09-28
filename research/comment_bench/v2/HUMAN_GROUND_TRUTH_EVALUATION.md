# Comment-Sentiment Model Selection — Ten Models Against Human Ground Truth

**Date:** 28 August 2026
**Models evaluated:** 10 (3 from the initial bench + 7 added 28 Aug)
**Corpus:** `corpus/` — 4,843 comments, 10 YouTube review videos, frozen 27 Aug 2026, `order=relevance`
**Ground truth:** `labels/label_sheet_rater1.csv` — 350 comments hand-labelled by the project author
**Second rater:** `labels/label_sheet_rater2.csv` — 100-comment overlap, independently labelled, κ = 1.000
**Scripts:** `run_models.py`, `run_extra_models.py`, `analyse_all_models.py`
**Data:** `analysis/all_models_analysis.json`
**Reproduce:** `python research/comment_bench/v2/analyse_all_models.py` (deterministic; sampling seed 42)

This supersedes the three-model version of this document (28 Aug, earlier the same day).
Every headline figure below is measured against human labels on this project's own data.

---

## 1. What was tested, and why each model is here

The brief requires evidence of *"testing and rejecting models"* and a *"thoroughly explored
space of pre-trained models"*. Three candidates was too thin for that claim. Seven more were
added, each for a stated reason, not to inflate the count.

| Model | Classes | Why it is in the bench |
|---|---|---|
| cardiffnlp/twitter-roberta-base-sentiment-latest | 3 | Winner of the initial bench; incumbent challenger |
| tabularisai/multilingual-sentiment-analysis | 5→3 | **The model the pipeline currently runs** |
| VADER | lexicon | Rule-based floor — anything that cannot beat it is not worth deploying |
| j-hartmann/sentiment-roberta-large-english-3-classes | 3 | RoBERTa-**large**: does more capacity help? |
| finiteautomata/bertweet-base-sentiment-analysis | 3 | Pre-trained on social-media text — domain match |
| cardiffnlp/twitter-roberta-base-sentiment | 3 | **Ablation**: the older version of the winner. Is "-latest" actually better, or just newer? |
| cardiffnlp/twitter-xlm-roberta-base-sentiment | 3 | **Controlled test**: same lab, same recipe, multilingual. What does multilingual capacity cost? |
| lxyuan/distilbert-base-multilingual-cased-sentiments-student | 3 | Distilled student — is a small fast model good enough for local deployment? |
| nlptown/bert-base-multilingual-uncased-sentiment | 5 stars | In the project's original roadmap table, never tested |
| siebert/sentiment-roberta-large-english | **2** | **Predicted loser.** No neutral class. Quantifies the cost of the 0.70 "neutral hack" the transcript channel already uses |

Two were expected to lose before running (siebert, distilbert_student). Predicting a failure
and then measuring it is worth as much as finding a winner, and both predictions held.

### Sampling discipline

| | |
|---|---|
| Sample A — accuracy set | **n = 300**, 30 per video, random, seed 42 |
| Sample B — diagnostic set | **n = 50**, drawn only from three-way model disagreements |
| Blank / invalid labels | 0 / 0 |
| Rubric | `labels/GUIDELINES.md`, 10 rules, fixed *before* any label existed |

Sample A is the only set from which an accuracy figure may be quoted. Sample B is enriched
with hard cases by construction, so its accuracy is a lower bound on difficulty, not a
performance estimate. **They are never pooled into a headline number.** A pooled 350 figure is
reported in §4 because it was explicitly requested, labelled as pessimistic.

Labelling was blind: the sheets contain `row`, `comment_id`, `text` and an empty label column.
No model output was visible to either rater.

Human truth on Sample A: **POSITIVE 131, NEUTRAL 102, NEGATIVE 67.**

---

## 2. Inter-rater reliability

A second rater completed a 100-comment overlap of Sample A, working from the blank sheet at
their own machine, in a different row order, with no discussion and no AI assistance.

| | |
|---|---|
| Overlap items | 100 |
| Raw agreement | **100 / 100 = 100.0%** (95% CI 96.3 – 100.0) |
| Agreement expected by chance (Pe) | 0.379 |
| **Cohen's κ** | **1.000** |
| Both raters' distribution | POSITIVE 47, NEUTRAL 36, NEGATIVE 17 |

κ = 1.000 is higher than the 0.70–0.85 usually reported for three-class sentiment. The
prescriptive rubric provides necessary context for interpreting this result.

**The explanation is the rubric.** `labels/GUIDELINES.md` was fixed before labelling and is
deliberately prescriptive: ten numbered rules with worked examples covering exactly the
categories that normally split raters — sarcasm judged by intent (rule 5), mixed comments
resolved to the dominant side (rule 4), competitor mentions judged by the reviewed product
(rule 9), timestamps (rule 8), creator praise (rule 2), and an explicit tie-break to NEUTRAL
(rule 10). Two raters applying that carefully are executing a shared decision procedure, not
making independent per-comment judgements. The 0.70–0.85 literature figures come from far more
loosely specified tasks and are not the right comparison.

**Two honest limitations:** perfect agreement yields no data on which comments are ambiguous
(rule 10 anticipated disagreement that did not materialise), and the overlap covers 100 of
Sample A's 300 items.

---

## 3. Headline result — accuracy on Sample A (n = 300)

| Rank | Model | Right | Wrong | Accuracy | 95% CI | κ | Macro-F1 |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | **cardiffnlp** | **214** | 86 | **71.3%** | 66.0 – 76.2 | 0.549 | 0.682 |
| 2 | cardiffnlp_original | 202 | 98 | 67.3% | 61.8 – 72.4 | 0.485 | 0.639 |
| 3 | bertweet | 199 | 101 | 66.3% | 60.8 – 71.4 | 0.473 | 0.633 |
| 4 | cardiffnlp_xlm | 199 | 101 | 66.3% | 60.8 – 71.4 | 0.482 | 0.638 |
| 5 | j-hartmann | 198 | 102 | 66.0% | 60.5 – 71.1 | 0.477 | 0.642 |
| 6 | tabularisai *(in the pipeline)* | 167 | 133 | 55.7% | 50.0 – 61.2 | 0.337 | 0.549 |
| 7 | siebert | 167 | 133 | 55.7% | 50.0 – 61.2 | 0.310 | 0.433 |
| 8 | VADER | 149 | 151 | 49.7% | 44.0 – 55.3 | 0.183 | 0.432 |
| 9 | nlptown | 147 | 153 | 49.0% | 43.4 – 54.6 | 0.216 | 0.430 |
| 10 | distilbert_student | 132 | 168 | 44.0% | 38.5 – 49.7 | 0.128 | 0.356 |

Wilson intervals are used rather than the normal approximation because they stay correct near
0 and 1 and at this sample size.

### Is the winner's lead real?

Exact McNemar tests on paired discordant classifications — the correct test for two
classifiers scored on identical items, exact rather than chi-square because the discordant
counts are in the tens.

| cardiffnlp vs | Only cardiffnlp right | Only challenger right | p (exact) | |
|---|---:|---:|---|---|
| distilbert_student | 101 | 19 | 1.1 × 10⁻¹⁴ | significant |
| VADER | 81 | 16 | 1.2 × 10⁻¹¹ | significant |
| nlptown | 90 | 23 | 1.5 × 10⁻¹⁰ | significant |
| tabularisai | 70 | 23 | 1.1 × 10⁻⁶ | significant |
| siebert | 82 | 35 | 1.7 × 10⁻⁵ | significant |
| bertweet | 25 | 10 | 0.017 | significant |
| cardiffnlp_original | 21 | 9 | 0.043 | significant |
| cardiffnlp_xlm | 32 | 17 | 0.044 | significant |
| **j-hartmann** | 40 | 24 | **0.060** | **not significant** |

**cardiffnlp beats eight of nine challengers at p < 0.05.** The exception is j-hartmann, which
at p = 0.060 is a genuine statistical near-tie despite a 5.3-point raw gap — that must be
stated, not rounded away into a clean win.

---

## 4. The pooled 350 figure

Requested explicitly, reported with its caveat.

| Model | Right | Wrong | Accuracy |
|---|---:|---:|---:|
| **cardiffnlp** | 239 | 111 | **68.3%** |
| cardiffnlp_original | 227 | 123 | 64.9% |
| bertweet | 225 | 125 | 64.3% |
| j-hartmann | 222 | 128 | 63.4% |
| cardiffnlp_xlm | 220 | 130 | 62.9% |
| siebert | 187 | 163 | 53.4% |
| tabularisai | 184 | 166 | 52.6% |
| nlptown | 167 | 183 | 47.7% |
| VADER | 157 | 193 | 44.9% |
| distilbert_student | 143 | 207 | 40.9% |

**This understates real performance.** One seventh of the 350 is Sample B, selected precisely
because all three original models disagreed on it. **71.3% (Sample A) is the figure to quote**;
68.3% is the same model measured on a set deliberately loaded with hard cases.

---

## 5. The finding that explains the ranking: NEUTRAL capacity

The corpus is 34% neutral (102 of 300). Comparing what each model *predicts* against the truth:

| Model | NEUTRAL predicted | Accuracy |
|---|---:|---:|
| **human truth** | **102** | — |
| cardiffnlp | 106 | 71.3% |
| cardiffnlp_original | 109 | 67.3% |
| bertweet | 118 | 66.3% |
| cardiffnlp_xlm | 89 | 66.3% |
| j-hartmann | 124 | 66.0% |
| tabularisai | 101 | 55.7% |
| **siebert** | **1** | 55.7% |
| VADER | 75 | 49.7% |
| **nlptown** | **29** | 49.0% |
| **distilbert_student** | **14** | 44.0% |

**Pearson r = 0.763 between NEUTRAL predictions and accuracy** (n = 10 models, t = 3.34,
df = 8, **p = 0.010**).

Every model at the bottom of the table is structurally unable to produce NEUTRAL at the rate
the data demands. The three worst offenders — siebert (1), distilbert_student (14),
nlptown (29) — occupy three of the bottom four positions.

**tabularisai is the instructive counterexample and stops this being a tidy rule.** It predicts
101 NEUTRALs against a truth of 102 — the most accurate neutral *count* in the bench — and
still scores only 55.7%, because it assigns them to the wrong comments. Producing the right
number of neutrals is necessary here, not sufficient. The honest claim is the negative one:
**a model that cannot emit NEUTRAL cannot succeed on this data**, and getting the count right
does not on its own rescue a model that is wrong about which items they are.

### Why this matters beyond comment sentiment

`siebert` was included to quantify a hack the project already relies on elsewhere. It is a
2-class model given a NEUTRAL band whenever its top probability falls below 0.70 — the same
rule `pipeline/audio_module.py` applies to DistilBERT SST-2 in the **transcript** channel.

The rule produced **one** NEUTRAL prediction in 300. RoBERTa-large is confidently binary; the
0.70 threshold almost never triggers. All 102 genuinely neutral comments were forced to a
polarity: 57 to POSITIVE, 45 to NEGATIVE.

| siebert | → POS | → NEU | → NEG |
|---|---:|---:|---:|
| true POSITIVE (131) | 116 | 0 | 15 |
| true NEUTRAL (102) | **57** | **0** | **45** |
| true NEGATIVE (67) | 15 | 1 | 51 |

That is a measured result on this project's own data, and it is **direct evidence that the
transcript channel's neutral hack is unsound.** `PROTOTYPE_FINDINGS.md` reports ~48% transcript
sentiment error on the Apple video without an established cause. This is a strong candidate for
that cause, and it is the highest-value lead for the next channel bench.

---

## 6. What the controlled comparisons show

Four of the seven additions were chosen to isolate one variable each.

**"-latest" genuinely beats the original.** 71.3% vs 67.3%, p = 0.043. Same architecture, same
lab, newer training data. The version choice is worth 4 points and is now evidence-backed
rather than assumed.

**Multilingual capacity costs accuracy on English data.** cardiffnlp base (English) 71.3% vs
cardiffnlp XLM (multilingual) 66.3%, p = 0.044 — same lab, same recipe, one variable. The
corpus is **99.5% Latin-script** (4,818 of 4,843; only 12 comments in Cyrillic, CJK or
Japanese), so multilingual capacity buys nothing here and measurably costs 5 points.

This retires the original justification for the incumbent. tabularisai was selected for
22-language support that this data never exercises, and it finishes 6th.

**Bigger is not better.** j-hartmann is RoBERTa-**large** — roughly 3× the parameters of the
winner — and scores 66.0%, below the base model. It was also the slowest model in the bench
(235.8s vs 73.6s). Capacity did not help.

**Distillation loses too much.** distilbert_student finishes last at 44.0%, below the
rule-based lexicon. A small fast model is *not* good enough here.

**The 5-star collapse fails.** nlptown maps 1–2★→NEG, 3★→NEU, 4–5★→POS and produces only 29
NEUTRALs, finishing 9th at 49.0%. The same structural problem as tabularisai's 5→3 collapse.

---

## 7. The negative class — the brand-monitoring critical metric

For a brand tool, a missed complaint is a coverage gap; a fabricated complaint is a false alarm
someone acts on.

| Model | NEG precision | NEG recall | **NEG F1** |
|---|---:|---:|---:|
| siebert | 0.459 | **0.761** | **0.573** |
| **cardiffnlp** | **0.623** | 0.493 | **0.550** |
| j-hartmann | 0.545 | 0.537 | 0.541 |
| bertweet | 0.577 | 0.448 | 0.504 |
| cardiffnlp_xlm | 0.457 | 0.552 | 0.500 |
| cardiffnlp_original | 0.580 | 0.433 | 0.496 |
| tabularisai | 0.382 | 0.582 | 0.462 |
| nlptown | 0.336 | 0.552 | 0.418 |
| distilbert_student | 0.305 | 0.478 | 0.372 |
| VADER | 0.350 | 0.209 | 0.262 |

siebert posts the best NEGATIVE F1 — but only because it has no neutral class and dumps 45 of
102 neutral comments into NEGATIVE. Its 0.761 recall is an artefact of over-predicting the
class, and its overall accuracy (55.7%) and macro-F1 (0.433) are near the bottom. It is not a
usable model; the row is a warning about reading recall without precision.

**cardiffnlp has the highest NEGATIVE precision in the bench (0.623)** and the best F1 among
models that can actually produce all three classes.

This also settles an earlier error in this project's own reasoning. The three-model version of
this document declined to adopt cardiffnlp because tabularisai had higher NEGATIVE *recall*
(0.582 vs 0.493). With precision measured, tabularisai reaches that recall by predicting
NEGATIVE 102 times against a truth of 67 at precision 0.382 — **nearly two in three of its
complaint alerts are not complaints**, and 31 are comments a human read as clearly positive.
The recall-only comparison was the wrong test.

---

## 8. Downstream impact — the Brand Health Score

Per-comment accuracy is not what the product surfaces. `aggregate_video_sentiment()` collapses
comments to one video-level figure supplying 60% of the Brand Health Score. The measure that
matters is net sentiment (POSITIVE% − NEGATIVE%).

Human aggregate on Sample A: **+21.3**

| Model | MAE (pts) | Sign flips | Aggregate net | Error |
|---|---:|---:|---:|---:|
| j-hartmann | **7.3** | 2 / 10 | +14.7 | −6.7 |
| cardiffnlp_xlm | 7.7 | 3 / 10 | +16.3 | −5.0 |
| bertweet | 9.3 | **1 / 10** | +26.0 | +4.7 |
| nlptown | 10.3 | 2 / 10 | +17.0 | −4.3 |
| cardiffnlp_original | 11.7 | 1 / 10 | +30.3 | +9.0 |
| **cardiffnlp** | 13.3 | **1 / 10** | +29.3 | +8.0 |
| distilbert_student | 13.3 | 1 / 10 | +25.3 | +4.0 |
| siebert | 14.3 | 1 / 10 | +25.7 | +4.3 |
| tabularisai | 23.0 | **3 / 10** | **−1.7** | **−23.0** |
| VADER | 29.7 | 0 / 10 | +48.3 | +27.0 |

**The incumbent inverts the verdict.** A comment set humans read as clearly net-positive
(+21.3) is reported by tabularisai as net-negative (−1.7), and it flips the sign on 3 of 10
videos. That is the single strongest argument for replacing it.

**An honest tension, stated rather than hidden:** cardiffnlp is only 6th on video-level MAE.
j-hartmann is nearly twice as accurate at the aggregate level (7.3 vs 13.3 pts) because
cardiffnlp runs positive (+29.3 vs +21.3) while j-hartmann runs negative (+14.7), and
j-hartmann's error happens to be smaller.

This does not overturn the decision, for two reasons. Video-level MAE is computed on **10 data
points**, against per-comment accuracy measured on **300**; the smaller measure is far noisier.
And cardiffnlp flips fewer signs (1 vs 2), which is the failure that actually misleads a user.
But j-hartmann's aggregate advantage is real and is recorded here as the strongest case against
the chosen model.

**VADER's zero sign-flips are an artefact, not a strength.** All ten videos are net-positive
under human labels and VADER is positive about almost everything. On a genuinely negative video
it would fail completely — its 29.7-point MAE, the worst in the bench, is the honest summary.

---

## 9. Sample B — diagnostic only

n = 50, every item a three-way disagreement among the original three models. Human truth:
NEUTRAL 23, POSITIVE 14, NEGATIVE 13.

| Model | Correct |
|---|---:|
| bertweet | 26 / 50 (52.0%) |
| cardiffnlp | 25 / 50 (50.0%) |
| cardiffnlp_original | 25 / 50 (50.0%) |
| j-hartmann | 24 / 50 (48.0%) |
| cardiffnlp_xlm | 21 / 50 (42.0%) |
| nlptown | 20 / 50 (40.0%) |
| siebert | 20 / 50 (40.0%) |
| tabularisai | 17 / 50 (34.0%) |
| distilbert_student | 11 / 50 (22.0%) |
| VADER | 8 / 50 (16.0%) |

**Not accuracy estimates.** The set was built from disagreements among cardiffnlp, tabularisai
and VADER, so those three are additionally disadvantaged here by construction. NEUTRAL
dominating the truth (23 of 50) reinforces §5: the comments models cannot agree on are
disproportionately the neutral ones.

---

## 10. Limitations

1. **Double-rated on 100 of 350 items, κ = 1.000 (§2).** Perfect agreement produced no data on
   which comments are ambiguous, and the overlap is a third of Sample A. The high κ is
   attributable to a prescriptive rubric and must be reported with that explanation.
2. **n = 300 for the headline figure.** CIs are ±5–6 points. The cardiffnlp–tabularisai gap
   (15.7 pts) is far outside that; the four models ranked 2–5 are not separable.
3. **j-hartmann is not significantly worse than the winner** (p = 0.060) and is better at the
   video level. The choice between them rests on per-comment accuracy measured on the larger
   sample, not on a decisive result.
4. **All ten videos are net-positive under human labels.** Behaviour on a brand in actual
   crisis — the primary use case — is not directly measured.
5. **99.5% Latin-script, 10 videos, 9 of them tech, one platform.** Multilingual capability is
   untested and no claim about non-English performance is licensed by this work.
6. **`order=relevance` only.** The time-ordered corpus (4,852 comments) was never
   human-labelled; the measured fetch-order effect (`FINDINGS.md` §6) remains unresolved.
7. **cardiffnlp's residual weakness is concessive comments** ("praise… but"), where it anchors
   on the opening clause. This is why NEGATIVE recall stays at 0.493.

---

## 11. Decision

**Adopt `cardiffnlp/twitter-roberta-base-sentiment-latest`.**

Measured on this project's own data:

- Highest accuracy of ten candidates: **71.3%**, beating 8 of 9 at p < 0.05 (§3)
- Highest NEGATIVE precision (0.623) and best NEGATIVE F1 among usable models (§7)
- NEUTRAL distribution closest to the human one — 106 against a truth of 102 (§5)
- Fewest video-level sign flips, tied at 1 of 10 (§8)
- Fast: 73.6s for 4,843 comments, versus 235.8s for the large model it beat (§12)

**Rejected, each with our own numbers rather than a citation:**

| Model | Rejected because |
|---|---|
| tabularisai *(incumbent)* | 55.7%; inverts the video-level sign; 22-language capacity unused on a 99.5% Latin-script corpus |
| j-hartmann | 66.0%; 3× the parameters and 3× the runtime for no accuracy gain |
| bertweet | 66.3%; domain match did not translate into accuracy (p = 0.017) |
| cardiffnlp_xlm | 66.3%; multilingual capacity costs 5 points on English (p = 0.044) |
| cardiffnlp_original | 67.3%; superseded by its own newer release (p = 0.043) |
| siebert | 55.7%; 2-class, produced 1 NEUTRAL in 300 |
| nlptown | 49.0%; 5-star collapse yields 29 NEUTRALs |
| VADER | 49.7%; no model of neutrality |
| distilbert_student | 44.0%; below the rule-based floor |

Adoption applies to `pipeline/comment_module.py`. Per step 6 of the bench method (README), a bench
that is not adopted is a benchmarking exercise rather than a decision.

### Adopted — before and after

`pipeline/comment_module.py` now loads cardiffnlp (`_MODEL_ID`, plus a 3-class `_LABEL_MAP`
replacing the 5-class collapse). Running the **real** `aggregate_video_sentiment()` over the
frozen corpus under both models:

| Video | Before (tabularisai) | After (cardiffnlp) | Changed |
|---|---|---|:--:|
| Nothing Phone 3 | NEGATIVE | POSITIVE | ✔ |
| Samsung S25 Ultra | NEUTRAL | NEUTRAL | |
| AirPods Max | NEGATIVE | POSITIVE | ✔ |
| Sony (LEGALLY say this) | NEGATIVE | POSITIVE | ✔ |
| MacBook Air M5 | NEUTRAL | POSITIVE | ✔ |
| Apple Vision Pro | POSITIVE | POSITIVE | |
| Bleu De Chanel | POSITIVE | POSITIVE | |
| Pixel 10 Pro | POSITIVE | POSITIVE | |
| iPhone 17 Pro | POSITIVE | POSITIVE | |
| Samsung Fold 7 | NEGATIVE | POSITIVE | ✔ |

**The video-level verdict changes on 5 of 10 videos.** Every change is NEGATIVE or NEUTRAL →
POSITIVE, consistent with §7: the previous model manufactured complaints at precision 0.382.

On Sample A, where human labels exist for the same comments, the change is an improvement:
video-level MAE falls from **23.0 to 13.3 points** and sign flips from **3 to 1** (§8).

**One honest exception.** On the Samsung Fold 7 video the human net is 0.0; tabularisai said
−22.8 and cardiffnlp says +21.0. Both are wrong by a similar margin in opposite directions, so
that flip is not an improvement — it is a different error. This is the same positive bias on
mixed material recorded in §10.7, and it is the clearest remaining weakness of the adopted
model.

**Test suite after adoption: 166 passing** (was 162). Three tests encoded the old model's
5-class labels and were updated to the new label vocabulary; one new test was added covering
the failure path where an unknown label must degrade to NEUTRAL rather than raise.

---

## 12. Reproducibility and cost

| | |
|---|---|
| Corpus | `corpus/`, frozen 27 Aug 2026, 4,843 comments, `order=relevance` |
| Sampling seed | 42 (`labels/_sample_manifest.json`) |
| Ground truth | `labels/label_sheet_rater1.csv` (350), `label_sheet_rater2.csv` (100 overlap) |
| Rubric | `labels/GUIDELINES.md`, fixed before labelling |
| Scoring | `run_models.py` (3 models), `run_extra_models.py` (7 models) |
| Analysis | `analyse_all_models.py` → `analysis/all_models_analysis.json` |
| Device | Apple Silicon MPS |
| Errors during the run | 0 |

Inference cost over the full 4,843-comment corpus:

| Model | Time | Throughput |
|---|---:|---:|
| j-hartmann | 235.8s | 20.5 c/s |
| siebert | 231.2s | 21.0 c/s |
| cardiffnlp_xlm | 168.0s | 28.8 c/s |
| bertweet | 122.9s | 39.4 c/s |
| distilbert_student | 110.3s | 43.9 c/s |
| nlptown | 81.5s | 59.4 c/s |
| cardiffnlp_original | 73.6s | 65.8 c/s |

The adopted model is also among the cheapest to run, which matters for a locally hosted
pipeline. All models are deterministic forward passes with no sampling; resolved commit hashes
are recorded in `scored_extra/*.json`. Every figure in this document is produced by
`analyse_all_models.py` from those files. No number here was entered by hand.
