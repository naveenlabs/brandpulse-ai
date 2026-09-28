# Pre-registration — does per-speaker normalisation rescue the vocal channel?

**Written 02 Sep 2026, before any accuracy was computed.** Fixed in advance per steps 1 and 2
of the bench method (README). Nothing below was edited after the first result was seen; corrections, if
any were needed, are appended to `SPEAKER_NORM_RESULT.md` as amendments and dated there.

Holdout use count entering this experiment: **2** (`VOCAL_MODEL_ANALYSIS.md` §5). This
experiment makes it **3**.

---

## 1. The question

The deployed vocal channel applies one fixed pair of arousal thresholds to every speaker:

```python
AROUSAL_LOW  = 0.40   # < 0.40  -> NEGATIVE
AROUSAL_HIGH = 0.65   # < 0.65  -> NEUTRAL, else POSITIVE
```

Those two numbers were grid-fitted on the **selection** split — two speakers — and frozen.
Speakers differ in baseline vocal energy. **Does re-expressing each segment's arousal
relative to its own video's arousal distribution, rather than against a global cut, beat the
fixed thresholds on held-out speakers?**

## 2. Why this is worth a holdout use

Two independent motivations, both already on file before this experiment was designed.

**Ours.** `VOCAL_MODEL_ANALYSIS.md` §7 measured per-speaker accuracy for `audeering` across
all 147 scorable clips: 65.3% on Marques Brownlee down to 16.7% on ShortCircuit — a
**48.6-point** range. That section's conclusion was that a channel whose accuracy depends
this strongly on who is speaking cannot support per-segment claims. It did not test whether
the dependence is removable.

**The model authors'.** Wagner et al. (arXiv:2203.07378), the paper for the deployed
checkpoint, report the model is *"fair with respect to gender groups, but not towards
individual speakers."* The failure mode we measured is the one its own authors document.

## 3. The mechanism, stated before the result

Computed from the 1,863 cached corpus segments, using **no labels**, so this is a statement
about the inputs and is fixed before any scoring:

| Speaker | Split | n segments | mean arousal | sd |
|---|---|---:|---:|---:|
| The Tech Chap | confirmation | 130 | 0.6843 | 0.0569 |
| Jeremy Fragrance | confirmation | 39 | 0.6812 | 0.0593 |
| Mrwhosetheboss | **selection** | 712 | 0.6128 | 0.0611 |
| Dave2D | confirmation | 71 | 0.5982 | 0.0594 |
| ShortCircuit | confirmation | 164 | 0.5959 | 0.0970 |
| Marques Brownlee | **selection** | 744 | 0.5395 | 0.0605 |

Per-video mean arousal spans **0.5182 to 0.6843**, a spread of **0.1661**, which is
**2.85×** the median within-video standard deviation of 0.0582.

The specific prediction this licenses: the two speakers the thresholds were fitted on sit at
0.5395 and 0.6128. The two highest held-out speakers sit at 0.6843 and 0.6812 — roughly
**1.7 within-video sd above** the fitted speakers. A cut at 0.65 therefore sits near the
middle of the fitted speakers' range and near the *bottom* of those two held-out speakers'
range. If the model carries within-speaker signal but a between-speaker offset, removing the
offset should help, and should help **specifically on the held-out split**.

The null this competes against is equally clear: if the model carries no ordinal signal at
all, normalisation can do nothing, because a monotone per-video transform cannot create rank
information that was not already there.

## 4. Built-in correctness check

Every rule below is **monotone within a video**. Therefore *within-video* Spearman rho
against the raw 1-5 human rating must be **numerically identical** for the global rule and
for every normalised rule. If the harness reports a difference, the harness is wrong, not
the hypothesis. This is asserted in code and in the test suite, not merely hoped for.

It follows that any accuracy gain must come **entirely** from making thresholds comparable
across videos, and not from any new information. That is the honest ceiling on what this
experiment could ever deliver.

## 5. Candidates

Every rule reads the **same cached arousal values**. The model is not re-run and does not
change. Only the decision rule changes.

| id | transform of arousal `a` in video `V` | deployable? |
|---|---|---|
| `global` | `a` itself — **the deployed rule** | yes (deployed) |
| `video_center` | `a - mean(V)` | yes |
| `video_z` | `(a - mean(V)) / sd(V)` | yes |
| `video_robust` | `(a - median(V)) / IQR(V)` | yes |
| `video_rank` | fractional rank of `a` within `V`, in (0, 1) | yes |
| `speaker_z` | `(a - mean(S)) / sd(S)` pooled over **all** of speaker S's videos | **no — oracle** |

`speaker_z` is included as a ceiling, not a candidate for adoption. The pipeline analyses one
video and has no channel history, so it cannot compute speaker-level statistics. It is
reported to separate "normalisation does not work" from "normalisation works but one video is
too small a sample to estimate the offset".

Video-level statistics are computed from **all** of that video's pipeline segments
(n = 39 to 271), never from the labelled clips, and never using the human ratings. At
inference time the pipeline holds every segment of the video before scoring, so this is
available in production without leakage.

## 6. Equalised search freedom

A finer grid is more freedom to overfit the selection split. The published bench fitted
`global` on a 19-point grid (0.05 to 0.95, step 0.05), giving 171 ordered `(lo, hi)` pairs.

To keep the comparison fair, **every** rule is fitted on a 19-point grid: the 5th, 10th, ...,
95th percentiles of that rule's own transformed values across all 1,863 corpus segments.
Identical number of candidate pairs for every rule, computed without labels.

As a separate anchor, `global` is also fitted on the original fixed 0.05-step grid, and the
harness asserts that this reproduces the published `(0.40, 0.65)` and **60/100** selection /
**23/47** confirmation. If that anchor fails, the run aborts.

## 7. Protocol

1. Thresholds for every rule are grid-searched on the **selection** split only (2 speakers,
   100 scorable clips) and frozen. Ties break toward the widest neutral band, as in
   `report_bench.fit_thresholds`.
2. The winner is **declared on selection** and written to disk *before* the confirmation
   split is scored.
3. The **confirmation** split (4 unseen speakers, 47 scorable clips) is scored once, for all
   rules. Only the pre-declared winner is the confirmatory result. The others are reported so
   the reader sees the whole surface, and are explicitly marked as not confirmatory.

## 8. What "better" means

In priority order, fixed now:

1. Held-out confirmation accuracy above the deployed rule's **48.9% (23/47)**.
2. Beating the degenerate floor: exact McNemar against always-NEUTRAL at alpha = 0.05, the
   same floor and the same test used throughout `VOCAL_MODEL_ANALYSIS.md`. The deployed rule
   scores p = 0.0639 there and does not clear it. Reported alongside: the confirmation
   majority class (always-POSITIVE, 27/47 = 57.4%), labelled as the oracle baseline it is.
3. Secondary, reported whatever happens: the per-speaker accuracy range, currently 48.6
   points. Shrinking it is a fairness result even if pooled accuracy does not move.
4. Threshold-free view: pooled and within-video Spearman rho against the raw 1-5 rating.

## 9. Adoption rule, fixed now

Adopt into `pipeline/audio_module.py` **only if** the pre-declared winner beats the deployed
rule on the confirmation split **and** exact McNemar against the deployed rule gives
p < 0.05.

Otherwise: change nothing in the pipeline, and record a second negative result for this
channel. A rule that wins on selection alone is **not** adopted — that is precisely the error
§3 of `VOCAL_MODEL_ANALYSIS.md` caught `audeering` making, and repeating it here would be
worse than not running the experiment.

`min_attainable_p` is reported with every McNemar. With 47 clips the discordant count may be
too small for any true improvement to reach significance; if so, that is a property of the
sample, it will be said plainly, and it still does not license adoption.

## 10. Threats already known

- **n = 47 held out, 12-13 clips per speaker.** Under-powered. Stated up front, not
  discovered afterwards.
- **Six speakers, all English-language technology and lifestyle YouTubers.** Narrow.
- **Video statistics from one video per speaker on the confirmation split**, so `video_z` and
  `speaker_z` coincide there by construction for three of four speakers. The oracle is a
  weaker ceiling than it would be with more videos per speaker; the harness reports where the
  two rules are identical rather than presenting them as independent evidence.
- **Grid-fitting two thresholds on 100 clips overfits**, which is the whole reason the
  confirmation split exists and is scored once.

---

## Amendments

The body above is not edited after the fact. Corrections are recorded here instead, so the
record shows what was actually pre-registered and what was wrong with it.

### A1 — 02 Sep 2026. Section 2 quoted the wrong reading's per-speaker figures.

**What it said.** "`audeering` per-speaker accuracy 65.3% on Marques Brownlee down to 16.7%
on ShortCircuit — a 48.6-point range", cited to `VOCAL_MODEL_ANALYSIS.md` §7.

**What is wrong.** Those figures are correct as printed in §7, but §7's `audeering` column
scores the **valence** reading with valence-fitted thresholds (0.40 / 0.80). The pipeline
deploys the **arousal** reading at 0.40 / 0.65. Verified by recomputing §7 from
`predictions/audeering-msp-dim.json`: the valence path reproduces 45.5 / 41.7 / 65.3 / 43.1 /
16.7 / 41.7 and pooled 48.3% exactly.

**The correct figures for the deployed channel**, arousal at 0.40 / 0.65, all 147 scorable
clips, reproduced by `speaker_norm.py --phase diagnose`:

| Speaker | Deployed (arousal) | §7 as printed (valence) |
|---|---:|---:|
| Dave2D | 27.3% (3/11) | 45.5% |
| Jeremy Fragrance | 58.3% (7/12) | 41.7% |
| Marques Brownlee | 65.3% (32/49) | 65.3% |
| Mrwhosetheboss | 54.9% (28/51) | 43.1% |
| ShortCircuit | 50.0% (6/12) | 16.7% |
| The Tech Chap | 58.3% (7/12) | 41.7% |
| **Pooled** | **56.5%** | **48.3%** |

**Range: 38.0 points, not 48.6.**

**Does the motivation survive?** Yes. A 38.0-point spread across six speakers on the reading
the pipeline actually deploys is severe instability and is ample motivation for the
experiment. The hypothesis, the candidates, the grids, the protocol and the adoption rule are
all unaffected — none of them was derived from the size of that range.

**Why this is recorded rather than silently fixed.** The pre-registration is only worth
something if it cannot be quietly rewritten once results are in. An amendment that makes the
motivating number *smaller* is exactly the kind that would be tempting to hide.
