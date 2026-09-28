# Per-speaker normalisation does not rescue the vocal channel

**Run 02 Sep 2026.** Pre-registered in `SPEAKER_NORM_PREREG.md` before any accuracy was
computed. Harness `speaker_norm.py`, results `speaker_norm_results.json`, every number below
re-derived by `verify_speaker_norm.py`.

**Decision: DO NOT ADOPT.** `pipeline/audio_module.py` is unchanged. This is the second
negative result on this channel, and the more informative of the two.

**Cost: no GPU time.** No model was re-run. All six rules read the same cached arousal values
from `ab_cache/vocal_audeering/` (1,863 segments, 1,860 with a usable reading). Only the rule
turning a continuous arousal value into POSITIVE / NEUTRAL / NEGATIVE changed.

---

## 1. What was asked

The deployed channel cuts every speaker at the same two arousal values, `0.40` and `0.65`,
fitted on two speakers and frozen. Speakers differ in baseline vocal energy — per-video mean
arousal spans 0.5182 to 0.6843, which is **2.85×** the median within-video sd of 0.0582.
Does re-expressing each segment relative to its own video's distribution beat a global cut on
held-out speakers?

Six decision rules, one shared model output:

| id | transform of arousal `a` in video `V` | deployable |
|---|---|---|
| `global` | `a` — the deployed rule | yes |
| `video_center` | `a − mean(V)` | yes |
| `video_z` | `(a − mean(V)) / sd(V)` | yes |
| `video_robust` | `(a − median(V)) / IQR(V)` | yes |
| `video_rank` | fractional rank of `a` within `V` | yes |
| `speaker_z` | `(a − mean(S)) / sd(S)` over all of speaker S's videos | **no — oracle** |

Every rule was fitted on a 19-point grid of its own transformed values' percentiles, so no
rule had more freedom to overfit than any other. Video statistics came from **all** of a
video's segments (n = 39 to 271) and used no labels, so the transform is available in
production without leakage. The fallback for a degenerate group (`MIN_GROUP_SEGMENTS = 8`)
**never fired** — 0 fallbacks across all six rules.

### Two checks that had to pass first

**Anchor.** Refitting `global` on the published grid returns `(0.40, 0.65)` and scores
**60/100** on selection and **23/47** on confirmation — reproducing
`VOCAL_MODEL_ANALYSIS.md` §5 exactly from the corpus cache. The harness aborts if it does not.

**Monotonicity invariant.** Every rule is monotone within a video, so within-video Spearman
rho against the raw 1–5 rating must be identical across rules. It is: **+0.211239** for all
six on selection. Asserted at runtime and in the test suite. It means any gain could only
have come from making thresholds comparable across videos — never from new information.

---

## 2. Selection split — 100 clips, 2 speakers, thresholds fitted here

| Rule | Thresholds | Accuracy | Wilson 95% | pooled rho | speaker range |
|---|---|---:|---|---:|---:|
| **`global`** | +0.4601 / +0.6183 | **60.0%** | [50.2, 69.1] | **+0.416** | 2.4 |
| `video_robust` | −1.3175 / +1.2098 | 56.0% | [46.2, 65.3] | +0.246 | 22.2 |
| `video_z` | −1.6683 / +1.5806 | 56.0% | [46.2, 65.3] | +0.241 | 26.3 |
| `video_center` | −0.1033 / +0.0489 | 55.0% | [45.2, 64.4] | +0.240 | 8.2 |
| `video_rank` | +0.0500 / +0.8500 | 55.0% | [45.2, 64.4] | +0.250 | 12.2 |
| `speaker_z` *(oracle)* | −1.6503 / +1.0131 | 55.0% | [45.2, 64.4] | +0.251 | 12.2 |

**The declared winner is `global` — the rule already deployed.** Written to
`speaker_norm_selection.json` before the holdout was touched; `--phase confirm` refuses to run
without that file and reads the winner from it rather than recomputing it.

Normalisation lost on the split it was allowed to fit on. The pooled rank correlation nearly
halves, from +0.416 to about +0.25, under every normalisation. That is the first sign that the
between-video offset is not nuisance.

---

## 3. Confirmation split — 47 clips, 4 unseen speakers, scored once

| Rule | | Accuracy | Wilson 95% | vs floor *p* | vs deployed *p* | speaker range |
|---|---|---:|---|---:|---:|---:|
| deployed `0.40 / 0.65` | | 48.9% (23/47) | — | 0.0639 | — | 38.0† |
| **`global`** | ← declared | **53.2%** (25/47) | [39.2, 66.7] | **0.0357** | 0.6250 | 39.4 |
| `video_robust` | | 36.2% (17/47) | [24.0, 50.5] | 0.2188 | 0.3075 | 37.8 |
| `video_z` | | 34.0% (16/47) | [22.2, 48.3] | 0.4531 | 0.2295 | 37.8 |
| `video_rank` | | 34.0% (16/47) | [22.2, 48.3] | 0.5078 | 0.1892 | 20.5 |
| `speaker_z` | *(oracle)* | 31.9% (15/47) | [20.4, 46.2] | 0.7539 | 0.1338 | 28.8 |
| `video_center` | | 27.7% (13/47) | [16.9, 41.8] | 1.0000 | **0.0309** | 37.2 |

† pooled over both splits; the confirmation-only figure is in §5.

**Every normalisation rule is worse on held-out speakers than the rule it was meant to
replace**, by 12.7 to 21.2 points. `video_center` is worse *significantly* (exact McNemar
p = 0.0309). The oracle `speaker_z`, which is allowed to pool all of a speaker's videos and is
not deployable, scores 31.9% — no rescue there either.

`global` refit on the percentile grid reaches 53.2% against the deployed rule's 48.9%. **This
is not an improvement worth having:** it is a 2-clip difference on 47 clips, McNemar
p = 0.6250 over 4 discordant pairs, and the smallest two-sided p that discordant count could
ever produce is 0.1250. The pre-registered adoption rule requires p < 0.05, so it does not
adopt. That rule earned its place here.

Both reference baselines, for calibration: always-NEUTRAL scores 13/47 = 27.7%, and the
confirmation majority class — always-POSITIVE — scores **27/47 = 57.4%**. The majority class
is an oracle, chosen with knowledge of the held-out split's own distribution, and **no rule
tested beats it.**

---

## 4. Why it failed — post-hoc, exploratory, not pre-registered

The pre-registration predicted that if the model carried within-speaker signal plus a
between-speaker offset, removing the offset would help. It did the opposite, on both splits.
That leaves one obvious alternative, and it is testable from data already on disk.

### 4.1 Most of the channel's signal is *between* videos, not within

| | clips | videos | pooled rho | mean within-video rho | within-video range | video-level rho |
|---|---:|---:|---:|---:|---|---:|
| selection | 100 | 8 | +0.415 | +0.211 | [−0.149, +0.608] | +0.762 |
| confirmation | 47 | 4 | +0.131 | **+0.056** | [−0.337, +0.471] | +0.400 |
| pooled | 147 | 12 | +0.386 | **+0.159** | [−0.337, +0.608] | **+0.790** |

Pooled across 147 clips the channel's rank correlation with the human rating is +0.386. Inside
a single video it is **+0.159** — well under half. On held-out speakers it is **+0.056**,
which is nothing.

Meanwhile a video's *mean* arousal tracks its *mean* human rating at **rho = +0.790** across
the 12 videos. **The between-video offset is real signal, not nuisance.** Normalising it away
removes the larger part of what the channel knows, which is exactly what the accuracy tables
show.

### 4.2 Arousal is roughly twice as video-determined as the thing it predicts

Share of total variance lying between groups:

| | arousal \| video | arousal \| speaker | rating \| video | rating \| speaker |
|---|---:|---:|---:|---:|
| selection, 100 clips | 0.3741 | 0.2664 | 0.2105 | 0.1757 |
| confirmation, 47 clips | 0.1446 | 0.1446 | 0.1020 | 0.1020 |
| pooled, 147 rated clips | **0.3907** | 0.3283 | **0.1911** | 0.1702 |
| all 1,860 cached segments (no ratings used) | **0.3905** | 0.3266 | — | — |

39.1% of arousal variance is explained by which video a segment came from; only 19.1% of the
human rating's variance is — a ratio of **2.04**. The model is measuring the speaker's habitual energy about twice
as strongly as it measures the thing being rated.

### 4.3 The failure is the method, not the threshold transfer

An obvious objection: perhaps normalisation is fine and only the selection-fitted thresholds
transferred badly. Refitting each rule **on the confirmation split's own labels** gives the
best score it could ever have reached there — an oracle no honest procedure can achieve:

| Rule | Oracle upper bound on confirmation |
|---|---:|
| `video_robust` | 63.8% |
| `video_rank` | 63.8% |
| `global` | 61.7% |
| `video_z` | 61.7% |
| `speaker_z` *(oracle rule, oracle thresholds)* | 61.7% |
| `video_center` | 57.4% |

Normalisation's ceiling is 2.1 points above `global`'s, on 47 clips — noise. Its *achievable*
score is 17 to 25 points below. So the method does not have a threshold problem that better
tuning would fix; it has nothing to offer in the first place.

The harsher reading: **the entire decision-rule design space, oracle-fitted on the answers,
is worth at most 6.4 points over always guessing POSITIVE** (63.8% vs 57.4%). No arrangement
of thresholds on this model's arousal output makes this channel trustworthy.

### 4.4 What the rules actually did

On confirmation, `global` predicts POSITIVE for 31 of 47 clips and **NEGATIVE for none** —
the same under-calling of NEGATIVE that `CORPUS_AB_RESULT.md` §2 measured at 20× on the full
corpus. `video_z` collapses the other way: with ±1.6 sd thresholds frozen from selection it
predicts NEUTRAL for **39 of 47** clips, degenerating into a near-constant predictor.

Per-speaker, the swap is not uniform — it is a trade, not a loss everywhere:

| Speaker | mean arousal | `global` | `video_z` |
|---|---:|---:|---:|
| Dave2D | 0.5982 | 27.3% (3/11) | **54.5%** (6/11) |
| Jeremy Fragrance | 0.6812 | 58.3% (7/12) | 41.7% (5/12) |
| ShortCircuit | 0.5959 | **66.7%** (8/12) | 25.0% (3/12) |
| The Tech Chap | 0.6843 | 58.3% (7/12) | 16.7% (2/12) |

Normalisation helps the one speaker whose baseline sits closest to the fitted speakers, and
destroys the two highest-energy ones. Those two are *genuinely* the most positively rated
speakers in the set; the global rule calls them POSITIVE because they are loud, and happens to
be right. Recentring each speaker on their own mean throws that away. This is §4.1 again, seen
one speaker at a time.

**Fairness did not improve either.** The per-speaker accuracy range on confirmation is 39.4
points for `global` and 37.2 to 37.8 for three of the four normalisations. Only `video_rank`
narrows it, to 20.5 points, and it pays 19.2 accuracy points for that. Levelling by making
every speaker equally badly predicted is not a fairness gain.

---

## 5. Corrections made to my own work

**The pre-registration's motivating figures were for the wrong reading.** §2 cited
`VOCAL_MODEL_ANALYSIS.md` §7's "65.3% down to 16.7%, a 48.6-point range". Verified by
recomputation: §7's `audeering` column scores **valence** at valence-fitted thresholds
(0.40 / 0.80), not the **arousal** reading the pipeline deploys. The deployed channel's real
per-speaker profile over all 147 clips is 27.3% (Dave2D) to 65.3% (Marques Brownlee),
**pooled 56.5%, range 38.0 points.** Recorded as amendment A1 in `SPEAKER_NORM_PREREG.md`
rather than edited into the body. The motivation survives — 38 points is still severe — and
nothing in the design depended on the size of that range.

`VOCAL_MODEL_ANALYSIS.md` §7 itself is **correct as printed** and is not changed; it reports
the pre-registered valence candidate, which is what that section is about. A pointer to the
arousal equivalent has been added there so the two are not confused again.

---

## 6. What this changes

**In the pipeline: nothing.** The adoption rule was fixed in advance and is not met.

**In what the system claims.** The number that matters for this product is not the 48.9%
headline. BrandPulse compares segments *within one video*; the channel's within-video rank
correlation with human judgement is **+0.159 pooled and +0.056 on unseen speakers**. The
`VOCAL_CAVEAT` carried on every report has been extended to say so, because a caveat that
quotes only the flattering aggregate is not a caveat.

**In what is worth trying next.** Three things are now ruled out for this channel by
measurement rather than by argument: a better checkpoint (`VOCAL_MODEL_ANALYSIS.md` §3 — six
candidates, none beat a constant on held-out speakers), a better dimension (§4–5 — arousal
beats valence but still fails), and now a better decision rule, including the oracle version
of one. What remains untested is a different *kind* of input: prosodic features computed
directly (pitch range, energy contour, speaking rate), which the pipeline already extracts via
pyAudioAnalysis and currently does not use for classification. That is a genuinely different
hypothesis, not another arrangement of the same output.

---

## 7. Threats and limits

- **n = 47 held out; 11–12 clips per speaker.** Under-powered, stated in the pre-registration
  before the run rather than after. Several McNemar tests here have `min_attainable_p` above
  0.05, meaning no true difference could have reached significance; those are reported with
  the p-value in `speaker_norm_results.json` and never read as null results.
- **Six speakers, all English-language technology and lifestyle YouTubers.** The between-video
  offset carrying real signal may be a property of this genre, where a video's overall energy
  genuinely tracks its overall sentiment. It need not hold for, say, a complaint call.
- **`speaker_z` is a weak oracle on confirmation.** Each held-out speaker contributes exactly
  one video, so its transform coincides with `video_z` there and only its frozen thresholds
  differ. It is a real ceiling only on the selection split, where each speaker has four videos.
- **Grid-fitting two thresholds on 100 clips overfits**, which is why the confirmation split
  exists and was scored once.
- **Post-hoc analysis is post-hoc.** §4 was written after the result and is labelled
  exploratory throughout. It explains a finding; it does not establish one. The
  variance decomposition on all 1,860 cached segments uses no ratings and is the most robust
  part of it.
- **Holdout use count: 3.** Recorded, not hidden. Uses 1 and 2 are logged in
  `VOCAL_MODEL_ANALYSIS.md` §5.

---

## 8. Status by claim type

**Verified fact** — the harness reproduces the published anchor (0.40 / 0.65; 60/100; 23/47);
the monotonicity invariant holds at +0.211239 across all six rules; 0 fallbacks; §7 of
`VOCAL_MODEL_ANALYSIS.md` is the valence reading.

**Measured result** — every accuracy, interval, McNemar p, correlation and variance share in
§§2–4, on 100 selection and 47 confirmation clips and 1,860 cached segments.

**Reasonable inference** — that the between-video offset carries genuine signal in this genre,
and that this is why normalisation hurts. Supported by three independent measurements
(video-level rho +0.790, the eta-squared gap 0.3907 vs 0.1911, and the per-speaker trade in §4.4) but
inferred from 12 videos.

**Not claimed** — that per-speaker normalisation cannot help vocal emotion recognition in
general; that a larger held-out sample would not change the ordering of rules within the
27.7–36.2% band; that prosodic features will succeed where this failed.
