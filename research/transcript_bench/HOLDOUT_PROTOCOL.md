# Transcript Bench — Split and Confirmation Protocol

**Written 31 Aug 2026, before any label was entered and before any candidate model was run.**
Fixed from this date. Sections 2–5 must not be revised after results are seen.

Companion to `CANDIDATE_MODELS.md` (candidates and primary metric) and
`labels/GUIDELINES.md` (labelling rules).

---

## 1. Why the split is by speaker, not by video

The corpus is twelve videos but only **six speakers**:

| Speaker | Videos | Segments |
|---|---:|---:|
| Marques Brownlee | 4 | 757 |
| Mrwhosetheboss | 4 | 718 |
| The Tech Chap | 1 | 167 |
| ShortCircuit | 1 | 168 |
| Dave2D | 1 | 80 |
| Jeremy Fragrance | 1 | 49 |

Eight of the twelve videos come from two people. A split that only kept *videos* apart would
put the same voice, vocabulary, delivery and editing style on both sides. A "held-out" video
from a speaker already seen is not held out in the way that matters: the thing a sentiment
model could overfit to here is a person's manner of speaking, not a particular product.

This is the transcript-channel analogue of the duplicate-text contamination check applied in
the comment bench, and it is a stronger constraint than the video-level split originally
proposed.

## 2. The split — fixed

**Selection set — 8 videos, 2 speakers, 400 labelled segments**
Marques Brownlee (`q0aFOxT6TNw`, `Gvvo6vUpJRc`, `4KbrxIpQgkM`, `i63u-iAnhuk`)
Mrwhosetheboss (`5VMckmQneCk`, `SSC0RkJuBVw`, `0jHtyF_rCqU`, `32slGhAH3Xc`)

All sixteen candidates are scored here. The winner is chosen here. This set may be inspected
freely.

**Confirmation set — 4 videos, 4 speakers, 199 labelled segments**
The Tech Chap (`Rlw_CI7pOKg`), ShortCircuit (`Kk-RKpTAXmA`), Dave2D (`vOhuf18b-g8`),
Jeremy Fragrance (`haWvrSliMVY`)

**Sealed.** Not examined, not scored, and not used to compare candidates until a single
winner has been chosen on the selection set and that choice has been written down.

Four unseen speakers is a materially stronger generalisation test than four unseen videos
from seen speakers would have been.

`build_label_sheet.py` asserts both video-level and speaker-level disjointness and fails
loudly rather than producing a leaky sheet.

## 3. Labelling procedure — fixed

- Both sets are interleaved and shuffled into **one** sheet, `labels/transcript_label_sheet.csv`.
  The rater cannot tell which rows are the sealed set, so effort cannot differ between them.
- Sampling is 50 segments per video, seeded (`seed=42`), from eligible segments only.
  `haWvrSliMVY` contributes 49 because that is its entire eligible corpus.
- Unratable criteria, applied before sampling: fewer than 4 words, or duration over 20 s.
  7 segments of 1,939 (0.4%) were excluded.
- `no_speech_prob` was **trialled and rejected** as a criterion. It is a per-30-second
  decoding-window statistic — a mean of 9.8 consecutive segments share each value — so it
  excludes speech in blocks. It removed 21 of 49 segments from `haWvrSliMVY`, including
  clean sentences. It is recorded per segment for sensitivity analysis but never used to
  exclude.
- The rater does not open `_sheet_manifest.json` and is not shown any model's prediction.

## 4. Primary metric and decision rule — fixed

Restated from `CANDIDATE_MODELS.md` §3 and binding here.

**Primary: NEUTRAL recall**, measured on the selection set.

A challenger is adopted only if **both** hold:
1. NEUTRAL recall is materially higher than the incumbent's, **and**
2. three-class accuracy is not lower than the incumbent's by a statistically detectable margin.

Reported alongside, always: three-class accuracy with a Wilson 95% interval and n, macro-F1,
per-class precision/recall/F1, the confusion matrix, and an exact McNemar test against the
incumbent.

## 5. What the confirmation set can and cannot do

**It can** show whether the selection-set winner holds up on four speakers it has never
seen.

**It cannot** be used to pick a different winner. If the winner underperforms on the
confirmation set, that is the reported result. Re-selecting on the sealed set would destroy
the only unbiased estimate in the experiment, and the failure would be reported rather than
engineered away.

**Declared in advance:**
- With *b*+*c* discordant pairs the smallest attainable two-sided exact McNemar p is
  2×(½)^(b+c). A genuine improvement may be unable to reach p<0.05 on 199 segments. That is a
  property of the test, not a null result, and will be reported as such.
- Segments within a video are not independent — same speaker, script and topic. Confidence
  intervals computed over segments are therefore optimistic, and this will be stated wherever
  they are quoted. The effective sample size tracks the six speakers more closely than the
  599 segments.
- Eleven of twelve videos are technology reviews. Findings generalise to that genre. The one
  exception (`haWvrSliMVY`, fragrance) is deliberately in the confirmation set, where it
  tests cross-category transfer on 49 segments — too few to carry a claim alone, and it will
  not be reported as one.

## 6. Corpus provenance

| Property | Value |
|---|---|
| Videos | 12 |
| Audio | mono 16 kHz PCM WAV, 292 MB, `data/<video_id>/audio.wav` |
| Total audio | 151 minutes |
| Transcriber | Whisper `base`, `language="en"`, `fp16=False` |
| Transcription cost | 613 s wall for 151 min audio (14.8× realtime) |
| Raw Whisper segments | 3,258 |
| Merged segments | 1,939 (`min_duration=3.0 s`, `max_gap=2.0 s`) |
| Words | 30,631 |
| Labelled | 599 (400 selection, 199 confirmation) |
| Sampling seed | 42 |
| yt-dlp | 2026.08.19 |

> **Note on the merge parameters.** This corpus was rebuilt on 31 Aug 2026 after a defect was
> found and fixed in `pipeline/audio_module._merge_short_segments`. Under the previous
> implementation the same audio yielded 1,128 segments with a maximum of 121.2 s; 55 segments
> exceeded 20 s and held 23% of all words. See `MERGE_DEFECT.md`. All figures
> in this protocol are post-fix.
