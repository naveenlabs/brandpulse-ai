# Held-Out Generalisation Test — Result

**Date:** 30 August 2026
**Protocol:** `HOLDOUT_PROTOCOL.md`, written and dated **before** any label existed
**Test set:** 150 comments, 75 each from two videos neither model was trained on
**Analysis:** `analyse_holdout.py` → `analysis/holdout_analysis.json`

---

## 1. Verdict

**The improvement generalises. Adopt.**

The pre-registered decision rule required NEGATIVE recall to be higher on unseen videos
with a gain of similar size to the original (+0.179). Measured gain: **+0.263** — larger,
not merely retained. That is the "adopt" branch of the rule as written on 30 August before
the labels were entered.

---

## 2. Primary metric — NEGATIVE recall (pre-registered)

| | Base | Fine-tuned |
|---|---:|---:|
| Negatives correctly identified | 7 / 19 | **12 / 19** |
| Recall | 0.368 | **0.632** |
| Change | — | **+0.263** |

Exact McNemar: **base-only-correct 0, fine-tuned-only-correct 5, p = 0.0625.**

**The fine-tuned model fixed 5 negatives the base model missed and broke none.** A perfect
one-directional result.

### Why p = 0.0625 is not a failed test

With 5 discordant pairs, the smallest attainable two-sided exact p is
2 × (½)⁵ = **0.0625**. Even a flawless outcome — every discordant item favouring the
fine-tune, zero against — **cannot reach p < 0.05 at this sample size.** Six discordant
items would give p = 0.031.

The constraint is the **19 negatives** in the sample, not the size or direction of the
effect. The protocol anticipated this: *"n = 150 is small — it can detect a large effect,
not a subtle one. A null result here is inconclusive rather than disproof."*

Reporting this as "not significant" without the ceiling would be misleading. Reporting it
as "significant" would be false. The accurate statement is: **the effect is in the
predicted direction, perfectly one-sided, and the test lacked the power to certify it.**

For comparison, the original 350-comment set had 67 negatives and reached p = 0.0118 on a
*smaller* effect (+0.179).

---

## 3. Secondary metrics — and the unexpected result

| Held-out (n = 150) | Base | Fine-tuned | Change |
|---|---:|---:|---:|
| Accuracy | 69.33% (104/150) | **78.67%** (118/150) | **+9.33 pts** |
| 95% CI | 61.5 – 76.2 | 71.4 – 84.5 | |
| Macro-F1 | 0.602 | **0.718** | +0.116 |

Exact McNemar on accuracy: base-only 5, fine-tuned-only 19, **p = 0.0066 — significant.**

**The accuracy gain is larger on unseen videos than on the videos the model trained on,
and here it is statistically significant where there it was not:**

| | Original 350 (seen videos) | Held-out 150 (unseen videos) |
|---|---:|---:|
| Accuracy gain | +3.00 pts | **+9.33 pts** |
| p | 0.272 (not significant) | **0.0066 (significant)** |

This is the opposite of the memorisation failure the test was designed to catch. If the
fine-tune had merely learned the ten training videos, the advantage should have shrunk or
vanished on new ones. It grew.

**Every class improved:**

| Class | Base P | Base R | Base F1 | FT P | FT R | FT F1 | Support |
|---|---:|---:|---:|---:|---:|---:|---:|
| NEGATIVE | 0.583 | 0.368 | 0.452 | 0.632 | 0.632 | **0.632** | 19 |
| NEUTRAL | 0.444 | 0.727 | 0.552 | 0.585 | 0.727 | **0.649** | 33 |
| POSITIVE | 0.869 | 0.745 | 0.802 | 0.911 | 0.837 | **0.872** | 98 |

Notably, **NEUTRAL F1 improved here (+0.097)**, where on the original test set it fell
slightly (−0.003). The neutral-recall cost recorded in `FINETUNE_RESULT.md` §4 did not
reappear on unseen data.

Predicted distributions against a truth of NEG 19 / NEU 33 / POS 98:

| | NEGATIVE | NEUTRAL | POSITIVE |
|---|---:|---:|---:|
| base | 12 | 54 | 84 |
| **fine-tuned** | **19** | 41 | 90 |
| **truth** | **19** | **33** | **98** |

The fine-tuned model predicted exactly 19 negatives against a truth of 19. The base model
under-called them at 12.

**Cost:** false complaint alarms rose from 5 to 7. Small, and NEGATIVE precision improved
(0.583 → 0.632), so the extra negatives are better targeted, not indiscriminate.

---

## 4. Video-level — the Brand Health Score input

| Video | Human net | Base | Error | Fine-tuned | Error |
|---|---:|---:|---:|---:|---:|
| Xiaomi 17 Pro Max | +66.7 | +52.0 | −14.7 | +58.7 | **−8.0** |
| Samsung Z Flip 5 | +38.7 | +44.0 | +5.3 | +36.0 | **−2.7** |
| **MAE** | | | **10.0 pts** | | **5.3 pts** |

Video-level error roughly halves on unseen videos, consistent with the 13.0 → 7.3 measured
on the original set. Two videos only — indicative, not a robust estimate.

---

## 5. Limitations, stated plainly

1. **The primary test could not reach significance.** §2. The direction is unambiguous and
   perfectly one-sided, but 19 negatives is not enough to certify it.
2. **This set is much more positive than the original.** POSITIVE 65.3% here vs 41.4% in
   the 350; NEGATIVE 12.7% vs 22.9%. Part of the base model's weaker showing (69.33% vs
   71.33%) may come from the class balance rather than the videos being harder.
3. **Two videos, both phone reviews** — the same category as 8 of the 10 training videos.
   This is **near-domain** generalisation: unseen videos and creators, familiar category.
   Cross-category transfer remains untested and no claim about it is supported.
4. **n = 150, single rater, no second labeller** for this set, so no inter-rater figure.
5. **The +9.33-point accuracy result is a single measurement** on 150 items. The confidence
   intervals for base and fine-tuned overlap (61.5–76.2 vs 71.4–84.5); it is the *paired*
   test that carries the significance, which is the correct test but rests on 24 discordant
   items.

---

## 6. What this changes

The open question in `FINETUNE_RESULT.md` §6 was whether the fine-tune had memorised the
ten training videos. **It had not.** The advantage survived transfer to unseen videos and
unseen creators, and on the pre-registered primary metric it was larger there.

That removes the main objection to adoption. The recommendation in `FINETUNE_RESULT.md` §7
— adopt on negative-class evidence rather than headline accuracy — now has a second,
independent measurement behind it, and on this set the headline accuracy is significant too.

**Supported interpretation.** Fine-tuning on 1,000 in-domain comments improved
comment-sentiment accuracy from 69.3% to 78.7% on two held-out videos (p = 0.007) and
raised negative-class recall from 0.368 to 0.632. The negative-recall result was
one-directional, with five corrections and no regressions, but the sample contained only
19 negative items and the paired test did not reach conventional significance.

That claim is supported by measurement. "Fine-tuning improved the model by 9 points" is not
— it is one sample of 150 in one content category.
