# Whisper Transcription Bench — Candidate Register and Pre-Registration

**Written 31 Aug 2026, before any candidate was run and before any ground truth was typed.**
Sections 3 and 4 are fixed from this date and must not be revised after results are seen.
Method: the eight-step bench method (README), used in `comment_bench/` and `transcript_bench/`.

---

## 1. Why this bench exists

`pipeline/audio_module.py:45` runs Whisper `base`. That choice has **never been measured on
this project's data**. It predates every other decision in the system and was inherited, not
selected.

This matters more than any other model choice in the project, for a structural reason:

> **Whisper is upstream of everything.** It produces the transcript that the sentiment channel
> classifies, and it defines the segment boundaries that the visual, vocal and prosodic
> channels all align to. A word Whisper mishears is a word every downstream channel reasons
> about incorrectly. A boundary it places badly is a boundary all four channels inherit.

`transcript_bench/CANDIDATE_MODELS.md` §7 already declared this as threat 3: *"Whisper
transcription error is confounded with sentiment error. Whisper WER on this corpus has never
been measured. Any transcript-channel accuracy is therefore an upper bound."* This bench
removes that open item.

**Documented evidence that base makes real errors.** From `haWvrSliMVY`, segment 0, produced by
the deployed model:

> *"Before you buy, **bloodshed nail audit toilet** in 2021."*

The speaker said *"Bleu de Chanel Eau de Toilette"*. That single phrase scores 0.75 WER. It is
one observation, not a rate, which is exactly why a measured rate is needed.

**The order was wrong and this is stated plainly.** Comment and transcript sentiment were
benched before this. Whisper should have been first, because it sits upstream of both. The
transcript bench remains valid — all 16 candidates read identical text, so the comparison
between them is unaffected — but its *absolute* accuracy figures are conditioned on `base`
output. That is a sequencing error in this project's plan, and it is recorded rather than
glossed.

## 2. What is being tested

**Q1 — Does model size reduce error on this material?**
Five sizes are available. Whether the accuracy ladder is steep or flat on clean studio audio
is unknown and is the primary question.

**Q2 — Do the English-only variants beat the multilingual ones at equal size?**
OpenAI ships `.en` checkpoints for tiny/base/small/medium, trained on English only. Every
video in this corpus is English. If the `.en` variants win, the project is currently paying a
multilingual tax for nothing.

**Q3 — Does the large version matter?** `large-v1`, `large-v2` and `large-v3` are separate
checkpoints, not aliases.

**Q4 — Is `large-v3-turbo` a viable accuracy/speed compromise?** It is a distilled `large-v3`
with a reduced decoder, at roughly half the file size.

## 3. Primary metric and decision rule — pre-registered, fixed 31 Aug 2026

**Primary metric: Word Error Rate (WER)** on the 12-clip, 8.7-minute evaluation sample,
computed against a human transcript typed from the audio.

WER = (substitutions + deletions + insertions) / reference words, pooled across clips rather
than averaged per clip, so every word carries equal weight.

**Normalisation is OpenAI's own `EnglishTextNormalizer`**, shipped with the whisper package and
used for the WER figures in the Whisper paper. Using theirs rather than a hand-rolled one keeps
our numbers computed the same way as the published ones and removes a degree of freedom that
could otherwise have been tuned after seeing results.

**Decision rule.** Adopt the **fastest** model whose WER is **not detectably worse than the
best-scoring model**.

This deliberately favours speed on ties. The pipeline transcribes on a live request, so
runtime is a user-facing cost, and buying an unmeasurable accuracy gain with an 8× slowdown
would be a bad trade for a prototype. If the largest model wins outright, it wins.

**Reported alongside, always:**
- WER with substitutions, deletions and insertions broken out separately — a model that
  deletes is failing differently from one that hallucinates.
- Realtime factor (audio seconds transcribed per wall-clock second) and absolute runtime.
- Per-clip and per-speaker WER, to show whether a win is uniform or carried by one video.
- Word-level accuracy with a Wilson 95% interval, flagged as optimistic.
- A paired bootstrap over clips (10,000 resamples, seed 42) for differences between models.

**Declared in advance:** the resampling unit is the **clip**, and there are only 12. Confidence
intervals from a 12-unit bootstrap are wide and coarse. A difference that fails to reach
significance here is not evidence of equivalence, and will not be reported as such.

## 4. Candidate register — 12 checkpoints

Sizes read from the official OpenAI CDN by HTTP HEAD request on 31 Aug 2026. Parameter counts
will be **measured directly from each downloaded checkpoint**, not cited, and recorded in the
results.

| # | Model | File | Size | Role |
|---|---|---|---:|---|
| 0.1 | **`base`** | base.pt | 145 MB | **Incumbent.** The thing to beat. |
| 1.1 | `tiny` | tiny.pt | 76 MB | Floor. Is base already buying anything? |
| 1.2 | `small` | small.pt | 484 MB | One step up. |
| 1.3 | `medium` | medium.pt | 1528 MB | Two steps up. |
| 1.4 | `large-v3` | large-v3.pt | 3087 MB | Current flagship. |
| 2.1 | `tiny.en` | tiny.en.pt | 76 MB | English-only pair for 1.1. |
| 2.2 | `base.en` | base.en.pt | 145 MB | **English-only pair for the incumbent.** Same size, same speed — a free win if it is better. |
| 2.3 | `small.en` | small.en.pt | 484 MB | English-only pair for 1.2. |
| 2.4 | `medium.en` | medium.en.pt | 1528 MB | English-only pair for 1.3. |
| 3.1 | `large-v1` | large-v1.pt | 3087 MB | Does the large version matter? |
| 3.2 | `large-v2` | large-v2.pt | 3087 MB | Same question. |
| 4.1 | `large-v3-turbo` | large-v3-turbo.pt | 1618 MB | Distilled large-v3; the speed/accuracy compromise. |

Candidate **2.2 (`base.en`) is the one to watch**: identical size and speed to what is deployed,
so if it is more accurate it is a strictly free improvement with no runtime cost at all.

**Disk discipline.** 15.34 GB of checkpoints against 21 GB free. Each model is downloaded,
run on the 8.7-minute sample, and its weights deleted before the next is fetched, so peak usage
stays near 3 GB. Transcripts are kept; weights are re-downloadable.

## 5. Deliberately excluded, and why

| Excluded | Ground |
|---|---|
| `large` and `turbo` aliases | `large` resolves to `large-v3.pt` and `turbo` to `large-v3-turbo.pt` — verified identical filenames in `whisper._MODELS`. Same weights, not independent candidates. Counting them would pad the register. |
| `faster-whisper` (CTranslate2) | A re-implementation of the **same weights** for speed. It is a runtime optimisation, not an accuracy candidate, so it cannot change which checkpoint is most accurate. Worth a note as future work for latency; it is not a new model. |
| `distil-whisper` | Genuinely different weights and a fair candidate. Excluded on scope: it needs a separate `transformers` code path rather than the `whisper` package the pipeline already uses, and 12 checkpoints already answer Q1–Q4. Recorded as an open lead, not silently dropped. |
| Non-English models / `--language` sweeps | The corpus is English and the pipeline pins `language="en"`. |
| Fine-tuning Whisper | Ruled out on data, not on principle. `transcript_bench/FINETUNE_RESULT.md` measured that 400 labels could not move a 278M-parameter classifier; Whisper is larger and needs thousands of audio/transcript pairs. Weeks of labelling for this project's remaining time. |

## 6. The evaluation sample

| | |
|---|---|
| Clips | 12, one per corpus video |
| Duration | 8.7 minutes total (40–45 s each) |
| Speakers | all 6 |
| Selection | seeded (42), contiguous, aligned to existing segment boundaries |
| Intro skip | first 30 s of each video excluded (music beds and channel idents) |
| Format | 16 kHz mono PCM WAV — identical to what the pipeline feeds Whisper |

Clips are aligned to segment boundaries so none starts or ends mid-word; otherwise every model
would differ at the edges for reasons unrelated to accuracy. Cut by `cut_clips.py`, indexed in
`_clip_index.json`.

## 7. Ground truth

Typed by hand from the audio by the project author, **without seeing any model's output**.
This is the one channel where ground truth requires no judgement: a word is either what was
said or it is not. There is no analogue of the transcript bench's "is this neutral or positive"
ambiguity, so single-rater subjectivity is a far smaller threat here than it was there.

Rules given to the typist are in `TYPING_GUIDE.md`, fixed before typing began.

## 8. Threats to validity, declared in advance

1. **12 clips is a small number of independent units.** Words within a clip share a speaker,
   topic and recording chain. Word-level intervals are optimistic; the bootstrap over clips is
   the honest one and it is coarse at n=12.
2. **8.7 minutes is a small sample** — roughly 1,300 words. It can separate large WER
   differences and cannot resolve small ones. Stated wherever a near-tie is reported.
3. **Clean studio audio.** All twelve videos are professionally recorded tech and product
   reviews. WER here will be lower than on noisy or accented speech, and the finding
   generalises to this genre only.
4. **Proper nouns are over-represented.** Product names, brand names and spec figures are
   exactly where ASR fails, and this corpus is dense with them. This makes the sample harder
   than generic English and arguably *more* relevant to a brand-monitoring product, but it is
   not a neutral sample of English.
5. **Segment boundaries are not evaluated, only words.** A model could produce identical words
   with worse boundaries and score the same WER, while degrading every downstream channel. The
   boundary effect is recorded separately as segment counts, not folded into WER.
6. **Adoption cost is not free.** Switching model changes segmentation, which means the 599
   existing transcript labels may not map cleanly. That cost is weighed in the write-up, not
   assumed away.

## 9. Open questions to record before results are seen

- Whether a WER win translates into a **downstream sentiment win** is a separate empirical
  question this bench does not answer. It can only be answered by re-running the transcript
  channel on new transcripts, and is listed as follow-up work rather than claimed.
- Whether `min_duration = 3.0 s` and `MAX_MERGE_GAP = 2.0 s` remain right under a different
  model's segmentation. They were tuned on `base` output.
