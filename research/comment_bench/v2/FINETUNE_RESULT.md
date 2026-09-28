# Fine-Tuning the Comment-Sentiment Model — Result

**Date:** 30 August 2026
**Base model:** `cardiffnlp/twitter-roberta-base-sentiment-latest` (adopted 28 Aug after a ten-model bench)
**Training data:** `train/train_sheet.csv` — 1,000 comments hand-labelled by the project author
**Test data:** `labels/label_sheet_rater1.csv` — the same 350 human labels used throughout, never seen in training
**Script:** `finetune_cardiffnlp.py` → `analysis/finetune_result.json`
**Reproduce:** `python research/comment_bench/v2/finetune_cardiffnlp.py` (seed 42; reproduced identically on two runs)

---

## 1. The question

The ten-model bench established that 71.3% is the best any off-the-shelf model achieves on
this data. cardiffnlp is already fine-tuned on ~124M tweets. **Does 1,000 in-domain YouTube
comments improve it, or is the off-the-shelf model already at this data's ceiling?**

A null result was an expected and acceptable outcome, and was declared as such before running.

## 2. Method

| | |
|---|---|
| Training set | 799 comments (80% of the 1,000, stratified by label) |
| Validation set | 201 comments (20%) — used for epoch selection |
| Test set | 350 human labels; **Sample A (n=300) is the headline** |
| Contamination check | **0 overlap** between the 1,000 and the 350, asserted in code |
| Hyperparameters | 5 epochs, lr 2e-5, batch 8, max_len 128, AdamW, OneCycleLR, weight decay 0.01 |
| Epoch selection | Best **validation** macro-F1 (epoch 4). The test set was never used to choose anything |
| Seed | 42 |

**Validation was carved out of the 1,000, not the 350.** Using the test set for early stopping
would leak it and make the final number meaningless.

Token-length audit over all 1,350 labelled comments: median 23, p90 73, p95 102, max 464.
`max_len=128` covers 96.5% of comments in full; the baseline is recomputed at the same length
so the comparison is like-for-like. The base model scored 68.29% on the 350 here, matching the
independently measured 68.3% from the ten-model bench exactly.

Validation curve (test set untouched throughout):

| Epoch | Train loss | Val macro-F1 | |
|---:|---:|---:|---|
| 0 | — | 0.6246 | untrained baseline |
| 1 | 0.7360 | 0.6495 | |
| 2 | 0.4739 | 0.6899 | |
| 3 | 0.2665 | 0.6886 | |
| **4** | 0.1424 | **0.7085** | **selected** |
| 5 | 0.0675 | 0.6963 | overfitting begins |

Training loss falls to 0.067 by epoch 5 while validation macro-F1 turns down — the model is
memorising 799 examples. Epoch 4 is the pre-registered stopping point.

## 3. Headline result

| Sample A (n = 300) | Base | Fine-tuned | Change |
|---|---:|---:|---:|
| Accuracy | 71.33% (214/300) | **74.33%** (223/300) | **+3.00 pts** |
| Macro-F1 | 0.682 | **0.723** | +0.041 |

**Exact McNemar: base-only-correct 22, fine-tuned-only-correct 31, p = 0.272.**

**The overall accuracy gain is NOT statistically significant.** With n = 300 and 53 discordant
items, a 3-point difference is inside the noise. The pre-declared adoption rule — significance
on Sample A accuracy — is **not met**, and this must be stated plainly rather than softened.

The pooled 350 shows the same picture: 68.29% → 70.86%, +2.57 pts, p = 0.349.

## 4. Where the model actually changed

| Class | Base P | Base R | Base F1 | FT P | FT R | FT F1 | ΔF1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| POSITIVE | 0.771 | 0.824 | 0.797 | 0.776 | 0.870 | 0.820 | +0.023 |
| NEUTRAL | 0.682 | 0.716 | 0.699 | 0.780 | 0.627 | 0.696 | −0.003 |
| **NEGATIVE** | 0.623 | 0.493 | 0.550 | 0.634 | **0.672** | **0.652** | **+0.102** |

Per-class McNemar on recall, Sample A:

| Class | Recall | base-only | ft-only | p (exact) | |
|---|---|---:|---:|---|---|
| **NEGATIVE** | 0.493 → **0.672** | 4 | 16 | **0.0118** | **significant** |
| NEUTRAL | 0.716 → 0.627 | 15 | 6 | 0.0784 | not significant |
| POSITIVE | 0.824 → 0.870 | 3 | 9 | 0.1460 | not significant |

**The NEGATIVE-class improvement is significant, and survives correction for testing three
classes** (Bonferroni: 0.0118 × 3 = 0.035 < 0.05).

This is not post-hoc fishing. §7 of `HUMAN_GROUND_TRUTH_EVALUATION.md`, written on 28 August
*before* this experiment, names the negative class "the brand-monitoring critical metric" and
identifies cardiffnlp's 0.493 NEGATIVE recall as its clearest weakness. The fine-tune was
aimed at exactly that weakness and moved exactly that number.

In product terms, on the 67 genuinely negative comments in Sample A:

| | Base | Fine-tuned |
|---|---:|---:|
| Complaints **caught** | 33 / 67 | **45 / 67** |
| Complaints **missed** | 34 | **22** |
| False complaint alarms | 20 | 26 |

**Twelve more real complaints caught, at a cost of six more false alarms.** Precision held
(0.623 → 0.634), so the extra negatives are not indiscriminate.

The cost is NEUTRAL recall, down 0.716 → 0.627 (p = 0.078 — not significant, but the direction
is real and NEUTRAL precision rose 0.682 → 0.780 in exchange). The model became more decisive:
NEUTRAL predictions fell from 107 to 82 against a truth of 102.

## 5. Downstream — the Brand Health Score

Video-level net sentiment (POSITIVE% − NEGATIVE%) on Sample A, 10 videos:

| | Human | Base | Fine-tuned |
|---|---:|---:|---:|
| Aggregate net | **+21.3** | +29.0 | **+25.3** |
| Mean absolute error | — | 13.0 pts | **7.3 pts** |
| Sign flips | — | 1 / 10 | 1 / 10 |

**Video-level error nearly halves, 13.0 → 7.3 points.** This is the number that feeds 60% of
the Brand Health Score, and it improves because catching more genuine complaints corrects the
base model's known positive bias on mixed material.

For scale, 7.3 pts matches the best video-level MAE in the entire ten-model bench (j-hartmann,
7.3) while keeping cardiffnlp's higher per-comment accuracy.

## 6. Honest assessment

**What is proven:** NEGATIVE recall improves significantly (p = 0.012, surviving Bonferroni),
catching 12 more of 67 real complaints without losing precision.

**What is not proven:** the +3.00-point overall accuracy gain (p = 0.272). It may be real — the
direction is consistent across Sample A, the pooled 350, macro-F1 and the validation set — but
n = 300 cannot demonstrate it.

**What it cost:** NEUTRAL recall fell 0.089 (p = 0.078). Not significant, but not nothing.

**Risks worth stating:**

1. **The test set has now been examined several ways** — overall accuracy, three per-class
   tests, video-level error. Each look erodes its independence a little. Any further tuning
   decided against these 350 would be overfitting to them.
2. **799 training examples is very small.** Training loss reached 0.067, so the model is
   memorising. The gain may not transfer to videos outside this corpus.
3. **Single split.** No cross-validation on the training set, and no repeated seeds, so the
   +3.00 figure carries run-to-run variance that has not been quantified.

## 7. Recommendation

**Adopt the fine-tuned model — but on the negative-class evidence, not on the headline
accuracy.**

The case for:
- The pre-identified critical metric improved significantly and survives multiple-testing correction
- 12 more real complaints caught out of 67, precision maintained
- Video-level error nearly halved (13.0 → 7.3 pts), directly improving the Brand Health Score
- No metric got significantly worse

The case against:
- The headline accuracy gain is unproven (p = 0.272), and the pre-declared adoption rule was not met
- NEUTRAL recall declined
- 799 training examples is thin, and generalisation beyond this corpus is untested

**Interpretation.** The evidence does not support the claim that fine-tuning improved the
model by three percentage points. It supports the narrower conclusion that
"fine-tuning on 1,000 in-domain examples significantly improved detection of the class the
system exists to detect, at a measured cost to neutral recall."

**Not adopted at the time of writing.** `pipeline/comment_module.py` still loads the base
model. Candidate weights are saved at `comment_bench/v2/finetuned/` — saving is not adoption.

## 8. What would settle it

- **Label ~2,000 more comments.** The single biggest lever. 799 examples is well below what a
  RoBERTa fine-tune normally needs, and the validation curve suggests capacity is not the limit.
- **A larger test set.** Detecting a true 3-point difference at 80% power needs roughly n ≈ 1,700,
  not 300.
- **Repeated seeds.** Five runs would quantify the run-to-run variance that a single split hides.

Ranked against the project's remaining time, none of these beats benching the transcript
channel, which currently has ~48% error and an identified probable cause.
