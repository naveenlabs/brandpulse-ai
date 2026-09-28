# Held-Out Generalisation Test — Protocol

**Written 30 August 2026, BEFORE any label was entered.**

This document states the hypothesis, the decision rule and the failure conditions in
advance. It is dated and fixed so that the outcome cannot be reinterpreted after the fact.
Results go in a separate file.

---

## 1. The problem this test exists to solve

The fine-tuned model was trained on 1,000 comments drawn from the **ten videos in
`videos.txt`**. Every figure measured so far — +3.00 points accuracy, NEGATIVE recall
0.493 → 0.672 (p = 0.012), video-level MAE 13.0 → 7.3 — comes from held-out *comments*
within **those same ten videos**.

The training and test comments never overlap. But the model has seen the vocabulary, the
products, the creators and the commenter register of those videos. A model trained on 799
examples reached a training loss of 0.067, which means it memorised them. So the open
question is not whether it improved, but **whether the improvement is a property of the
model or of this corpus.**

## 2. What is being tested

**Hypothesis:** the fine-tuned model's advantage over the base model transfers to videos
neither model was trained on.

**Held-out set,** fetched 30 Aug 2026, frozen:

| Video | Title | Comments |
|---|---|---:|
| `0jHtyF_rCqU` | Xiaomi 17 Pro Max review - Apple are you seeing this!? | 500 |
| `32slGhAH3Xc` | Samsung Z Flip 5 - Biggest Upgrade Ever. | 500 |

**Verified before sampling:** 0 shared `comment_id` with the training corpus; comments
whose text appears verbatim in the training corpus were dropped (10 removed).

## 3. Scope — stated precisely, because it limits the claim

Both held-out videos are **phone reviews**, the same category as 8 of the 10 training
videos.

This test therefore measures **near-domain generalisation**: unseen videos, unseen
creators, familiar category. It does **not** measure cross-category transfer, and no claim
of the form "works on any content type" may be drawn from it.

That limitation is acceptable and arguably the more relevant question — the product is a
brand-monitoring tool, and brand/product review content is its actual domain. But the
report must describe the test as near-domain, not as general.

## 4. Method

- **150 comments** hand-labelled, 75 per video, random, seed 42.
- **Blind.** `holdout_label_sheet.csv` contains `row`, `comment_id`, `text` and an empty
  label column. Model predictions are in `_holdout_predictions.json`, which the rater does
  not open.
- **Rubric unchanged:** `labels/GUIDELINES.md`, the same 10 rules used for all 1,350
  existing labels. Not modified for this test.
- Both models were scored on all 1,000 held-out comments **before** labelling began, so
  predictions cannot be influenced by the labels.

## 5. Decision rule, fixed in advance

The primary metric is **NEGATIVE recall**, because that is the metric the fine-tune
significantly improved on the original test set, and §7 of
`HUMAN_GROUND_TRUTH_EVALUATION.md` identified it as the brand-monitoring critical metric
on 28 August, before any fine-tuning was attempted.

| Outcome | Interpretation | Action |
|---|---|---|
| NEGATIVE recall higher, gain of similar size (≈ +0.15) | Improvement generalises | Adopt |
| NEGATIVE recall higher but clearly smaller gain | Partial transfer | Adopt, report the attenuation |
| NEGATIVE recall equal or lower | Improvement was corpus-specific | **Do not adopt.** Report as memorisation |
| Overall accuracy materially worse than base | Fine-tune harmed the model | **Do not adopt** |

**Secondary metrics,** reported but not decisive: overall accuracy, macro-F1, per-class
precision/recall, video-level net sentiment error.

**Statistics:** exact McNemar on paired discordant classifications; Wilson intervals on
accuracy. n = 150 is small — it can detect a large effect, not a subtle one. A null result
here is therefore **inconclusive rather than disproof**, and must be written up that way.

## 6. Known limitations of this test, acknowledged in advance

1. **n = 150.** Detecting the +0.18 NEGATIVE-recall effect requires far fewer samples than
   detecting the +3-point accuracy effect, which is why recall is the primary metric. The
   accuracy comparison here is underpowered and is not expected to reach significance.
2. **Two videos.** Video-level results rest on 2 points and are indicative only.
3. **Same rater.** No second labeller for this set, so no inter-rater figure.
4. **Near-domain only.** See §3.

## 7. What is already known before labelling

Both models were run over all 1,000 held-out comments. Their predicted distributions:

| | NEGATIVE | NEUTRAL | POSITIVE |
|---|---:|---:|---:|
| base | 88 | 328 | 584 |
| fine-tuned | 126 | 256 | 618 |

They disagree on **162 of 1,000** comments.

The fine-tuned model predicts more NEGATIVE and fewer NEUTRAL on unseen videos — the same
behavioural shift measured on the original test set, where it was correct. **This shows the
behaviour transfers. It does not show the behaviour is right here.** Only the labels can
establish that, which is the entire purpose of this test.
