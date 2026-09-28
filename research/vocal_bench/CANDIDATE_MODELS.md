# Vocal Emotion Bench — Candidate Register and Pre-Registration

**Written 01 Sep 2026, before any candidate was run on real clips and before any rating was
given.** Sections 3, 4 and 7 are fixed from this date and must not be revised after results are
seen. Method: the eight-step bench method (README), used in `comment_bench/`,
`transcript_bench/` and `whisper_bench/`.

Candidates were probed for loadability before this register was written. That is feasibility,
not result: no candidate has yet seen a single project clip, and no ground truth exists.

---

## 1. Why this bench exists

`pipeline/audio_module.py:64` runs `speechbrain/emotion-recognition-wav2vec2-IEMOCAP`, a 4-class
categorical model (angry / happy / sad / neutral). **This is the worst-evidenced channel in the
system and the only one with two independent, user-verified failures already on record.**

From `PROTOTYPE_FINDINGS.md` §10 and §12E:

| Video | Model's verdict | Author's verdict after listening |
|---|---|---|
| Apple (77 segments) | **74% "angry"** (57/77), 0% sad | "predominantly neutral… **never angry**" |
| Second video (29 segments) | **72.4% "happy"** (21/29) | "slightly positive but more neutral, never angry or sad" |

The label flips from mostly-angry to mostly-happy between two videos of similar content. **A
channel whose majority class is determined by which speaker is talking is not measuring emotion,
it is measuring voice timbre.**

§12E went further and cross-checked pitch on the four "angry" segments of the second video: three
sat inside the ordinary pitch range of the "happy" segments (151.9, 163.9, 168.4 Hz against a
happy range of 146.4–197.1 Hz). The anger calls are not explained by pitch either.

**Documented root cause:** IEMOCAP is acted, exaggerated emotional speech from scripted drama
performances. This corpus is calm, professional, conversational monologue. The model has
effectively never heard the kind of speech it is being asked to judge.

## 2. What is being tested

**Q1 — Can any available model beat the incumbent on natural conversational speech?**
The primary question. The incumbent's failure is documented but its error rate has never been
*measured* against ground truth, only observed. This bench measures it.

**Q2 — Does training data domain matter more than model size?**
The strongest hypothesis from §1. Models trained on MSP-Podcast (spontaneous podcast speech) and
on large heterogeneous corpora should beat models trained on acted drama, independent of
parameter count. If a small podcast-trained model beats a large acted-trained one, the finding is
about **data, not scale**.

**Q3 — Is categorical emotion the right output at all, or is dimensional valence better?**
This is the design question, not just a model question. The pipeline consumes this channel as a
signal that either agrees or disagrees with transcript sentiment. "Angry" has no clean mapping
to brand sentiment; **valence** (negative ↔ positive) maps directly, and would align this channel
with the three others, all of which are sentiment-shaped. A dimensional model is included
specifically to test whether the framing itself is the problem.

**Q4 — Is the incumbent beaten by a degenerate baseline?**
`transcript_bench` found the deployed transcript model scored *worse than always guessing
NEUTRAL*. Given §10's 74%-angry result, the same outcome is plausible here and must be tested,
not assumed away.

**Q5 — Does licensing block the best model?**
Verified 01 Sep 2026 by HuggingFace API: the strongest dimensional candidate is
**CC-BY-NC-SA-4.0, non-commercial**. BrandPulse is framed as a B2B product. If the measurement
winner cannot be deployed commercially, the evaluation must also identify the strongest
permissively licensed model as the deployable alternative.

## 3. Primary metric and decision rule — pre-registered, fixed 01 Sep 2026

**Ground truth** is a human rating of *vocal tone only* on a 5-point scale, collapsed to three
classes for scoring:

| Rating | Class |
|---|---|
| 1 clearly negative, 2 slightly negative | **NEGATIVE** |
| 3 neutral | **NEUTRAL** |
| 4 slightly positive, 5 clearly positive | **POSITIVE** |
| 0 can't tell | **excluded from scoring, count reported** |

**Primary metric: three-class accuracy** on the selection split. Chosen because the pipeline
consumes one label per segment, and because it is directly comparable to `transcript_bench`,
which used the same metric on the same corpus.

**Reported alongside, always:** macro-F1 (so a model cannot win by ignoring a class), per-class
precision/recall, the full confusion matrix, Wilson 95% intervals, and the count of excluded
"can't tell" clips.

**Mapping model outputs to three classes.** Fixed now, before any output is seen:

| Model output | Maps to |
|---|---|
| angry, sad, disgusted, fearful | NEGATIVE |
| neutral | NEUTRAL |
| happy, surprised | POSITIVE |
| other, unknown, `<unk>` | **recorded as unmapped, never silently coerced** |

`surprised` → POSITIVE is a judgement call and is flagged as one. Surprise is valence-ambiguous.
It is mapped this way because in product-review speech surprise is overwhelmingly delight rather
than alarm, and the alternative — dropping it — would discard real predictions. **The count of
surprise predictions is reported separately so the effect of this choice is visible**, and a
sensitivity check with surprise mapped to NEUTRAL will be reported if it changes any conclusion.

**Continuous outputs (the dimensional candidate) need thresholds, and thresholds are a free
parameter.** To stop that becoming a way to inflate its score: **thresholds are fitted on the
selection split only, by maximising three-class accuracy over a fixed grid, then frozen before
the confirmation split is touched.** Both the fitted thresholds and the grid are reported. Every
categorical candidate is threshold-free, so this advantage is given only to the model that
structurally requires it, and it is declared.

**Decision rule.**

> **Selection.** Adopt the candidate with the highest three-class accuracy on the selection
> split **that is also detectably better than the incumbent** (exact McNemar, p < 0.05). If two
> or more candidates are statistically indistinguishable from the best, prefer in this order:
> (a) higher macro-F1, (b) permissive licence, (c) faster inference.
>
> **Confirmation.** The chosen model is then scored **once** on the held-out speakers. If it
> fails to beat the incumbent there, that is reported as a failure to generalise — not quietly
> dropped, and not re-selected against the holdout.
>
> **If no candidate beats the incumbent, the incumbent stays** and the bench reports a negative
> result.

**Why the rule is worded this way.** `whisper_bench` pre-registered *"adopt the fastest model not
detectably worse than the best"* and that rule proved defective: it never compared challengers
against the **incumbent**, and at small n it admitted a model that could not be shown to beat the
deployed one on anything while costing real runtime. That failure is documented in
`whisper_bench/WHISPER_MODEL_ANALYSIS.md` §6. **This rule requires the challenger to beat the
incumbent, which is the comparison that actually decides whether a switch is worth making.**

**Significance testing.** Exact McNemar via the binomial, as in `transcript_bench` — no
statsmodels dependency, and exact rather than approximate at these counts. Bonferroni-corrected
for the number of candidate-vs-incumbent comparisons; the corrected α is reported explicitly.

## 4. Candidate register — 7 models and 2 degenerate baselines

All seven were **verified to load and produce output on this machine before this register was
fixed**. Licences read from the HuggingFace API on 01 Sep 2026, not from memory.

| # | Model | Output | Trained on | Licence | Probe |
|---|---|---|---|---|---|
| **0.1** | **`speechbrain/emotion-recognition-wav2vec2-IEMOCAP`** | 4-class | IEMOCAP (acted) | apache-2.0 | **incumbent** |
| 1.1 | `superb/wav2vec2-base-superb-er` | 4-class | IEMOCAP (acted) | apache-2.0 | ✅ hap/neu/ang/sad |
| 1.2 | `Dpngtm/wav2vec2-emotion-recognition` | 7-class | RAVDESS-family (acted) | mit | ✅ 7 labels |
| 2.1 | `emotion2vec/emotion2vec_plus_seed` | 9-class | EmoBox academic data | other* | ✅ 9 labels |
| 2.2 | `emotion2vec/emotion2vec_plus_base` | 9-class | ~42,500 h pseudo-labelled | other* | ✅ 9 labels |
| 2.3 | `emotion2vec/emotion2vec_plus_large` | 9-class | ~42,500 h pseudo-labelled | other* | ✅ 9 labels |
| **3.1** | **`audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim`** | **valence/arousal/dominance** | **MSP-Podcast (natural)** | **cc-by-nc-sa-4.0** | ✅ 3 floats |
| B1 | **always NEUTRAL** | degenerate | — | — | trivial |
| B2 | **majority class** (fitted on selection) | degenerate | — | — | trivial |

\* The HuggingFace card declares `other`; the project's GitHub repository displays an MIT badge.
**This discrepancy is unresolved and is recorded rather than assumed in either direction.** If
an emotion2vec model wins, the licence must be confirmed with the authors before deployment is
claimed.

**Candidate 3.1 is the one to watch.** It is the only dimensional model, the only one trained on
natural spontaneous speech, and the only one whose output maps directly onto what the pipeline
actually needs. It is also the only one that cannot be used commercially.

**Baselines B1 and B2 exist to make the metric unfalsifiable-proof.** If a candidate cannot beat
"always say neutral", it has learned nothing useful about this corpus, however good its published
benchmark numbers are.

## 5. Deliberately excluded, and why

| Excluded | Ground |
|---|---|
| `tiantiaf/wavlm-large-msp-podcast-emotion-dim` | The INTERSPEECH 2025 challenge winner, and a genuine loss. Its repository ships only `config.json` + `model.safetensors` and requires the `vox-profile-release` class to assemble (LoRA rank 16, custom conv-output pooling, 9+17 dual heads). Not on PyPI; needs a git clone and a conda environment. **Excluded on integration cost, not merit.** Hand-reconstructing the wrapper risks silently wrong numbers, which is worse than an honest omission. Recorded as the top open lead. |
| `autrainer/msp-podcast-emo-class-big4-w2v2-l-emo` | Requires the `autrainer` CLI and its config system as the only documented inference path. Same reasoning. Its published numbers (acc 0.617, UAR 0.650 on MSP-Podcast Test1) are noted as *published*, never as measured here. |
| `r-f/wav2vec-english-speech-emotion-recognition` | **Disqualified on a real defect, not on cost.** Under transformers 5.12.1 the checkpoint loads with `classifier.weight`, `classifier.bias`, `projector.weight` and `projector.bias` **missing and newly initialised at random**. It emits confident-looking labels from an untrained head. Benching it would produce numbers that mean nothing. |
| Fine-tuning any candidate | Ruled out on data, consistent with `transcript_bench/FINETUNE_RESULT.md`: 400 labels could not move a 278M-parameter classifier. This bench will have ~150 ratings. Fine-tuning is not on the table at this sample size and saying so now prevents it being reached for later. |
| Training a model from scratch | Out of scope for a pre-trained-model orchestration project. |

## 6. The evaluation sample

| | |
|---|---|
| Clips | **150** — 100 selection, 50 confirmation |
| Duration | 12.4 min total, 1.5–15.0 s each |
| Source | the 12-video corpus, re-transcribed with `large-v3-turbo` on 01 Sep 2026 |
| Selection speakers | Marques Brownlee, Mrwhosetheboss (8 videos) |
| Confirmation speakers | Dave2D, Jeremy Fragrance, ShortCircuit, The Tech Chap (4 videos) |
| Selection | seeded (42), random within video, round-robin across videos |
| Presentation | shuffled so speakers are interleaved, longest same-speaker run 5 |

**The speaker split is identical to `transcript_bench`.** Reusing it means the same four speakers
stay held out across every bench in this project, so nothing learned on one channel can leak into
another channel's holdout.

**Segments are the pipeline's own segments**, not independently cut windows, so the clips are
exactly what the deployed system feeds this model. The 1.5 s floor matches
`audio_module.MIN_SEGMENT_DURATION_S`; the 15 s ceiling is the documented input limit of the
excluded WavLM candidate and is kept anyway so the sample stays valid if that lead is picked up.

Cut by `cut_clips.py`, indexed in `_clip_index.json`. Near-silent clips (RMS < 0.005) are
rejected before rating because tone cannot be judged from silence; 0 were rejected.

## 7. Ground truth protocol — fixed before rating

Rated by the project author from **audio alone**.

**The transcript is never shown.** This is the single most important property of this bench. If
the rater can read the words, they will rate the words, and this channel exists precisely to
measure whether the voice *disagrees* with the words. `build_rating_page.py` never writes segment
text into the page, and `verify_page.py` proves it mechanically — checking every clip's
significant word-trigrams against the full page source, along with speaker names, audio-file
integrity and speaker interleaving. **All five checks passed before rating began.**

Speaker names are withheld for the same reason: knowing whose voice it is invites rating by
reputation rather than by clip.

Ratings are 1–5 with an explicit **"can't tell"** escape. Forcing a rating on an unratable clip
manufactures noise and calls it data. Excluded clips are counted and reported.

**The honest limitation, stated now rather than discovered later.** A listener who understands
English cannot fully separate *how it sounds* from *what it says*. Withholding the transcript
removes the strongest cue but not the words themselves. This is the same constraint under which
MSP-Podcast and IEMOCAP were themselves annotated, so the ground truth is no weaker than the
data the candidates were trained on — but it is not a clean separation and must not be described
as one. A low-pass-filtered re-rating of a subset would test this directly and is recorded as an
available robustness check, not claimed as done.

**Single rater.** No inter-rater agreement can be computed, so no κ will be reported. This is a
real weakness, identical to `transcript_bench`, and is stated wherever the numbers are quoted.

## 8. Threats to validity, declared in advance

1. **150 clips, single rater, one hour of judgement.** Confidence intervals will be wide.
   Differences under roughly 10 accuracy points will likely not be resolvable.
2. **Tone and content cannot be fully separated by a human listener** (§7). The ground truth is
   "perceived vocal tone by someone who also understands the words", not "acoustic prosody in
   isolation".
3. **The three-class collapse discards information.** A 5-point rating carries ordinal detail
   that three classes throw away. Spearman correlation against the raw 1–5 rating will be
   reported as a secondary measure for the continuous-output candidate, which can use it.
4. **`surprised` → POSITIVE is a judgement call** (§3), declared with a sensitivity check.
5. **The dimensional candidate gets fitted thresholds; categorical candidates do not.** Declared
   in §3, fitted on selection only, frozen before confirmation.
6. **Professional presenters, clean studio audio, one genre.** The finding generalises to
   product-review monologue and nothing further. Notably these speakers are *performing* — a
   trained presenter's warmth is a professional skill, which may be exactly what an
   authenticity-detection system should be suspicious of, but it means the emotional range is
   narrow and probably skewed positive.
7. **Class imbalance is expected and unknown in advance.** If the corpus is overwhelmingly
   neutral, accuracy becomes a weak metric and macro-F1 carries the argument. Both are
   pre-registered for exactly this reason, and baselines B1/B2 quantify the floor.
8. **Adoption changes a live channel.** Unlike the Whisper swap, this one alters what the
   orchestrator sees per segment, which changes conflict scores and therefore every downstream
   score. Any adoption must be followed by a corpus re-run and a before/after comparison.

## 9. Open questions to record before results are seen

- **Whether a better vocal channel improves the final Authenticity/Brand Health scores** is a
  separate question this bench cannot answer. `PROTOTYPE_FINDINGS.md` §11 already showed that
  correcting channel inputs by hand moved the Authenticity Score from 26.55 to 80.57. Measuring
  that properly needs a corpus re-run after adoption, and is follow-up work.
- **Whether the 4-class categorical framing should survive at all** (Q3). If the dimensional
  model wins clearly, the supported conclusion may be that the *output schema* was the defect, not
  merely the model — which would be a design finding, not a model-selection one.
- **Whether `speechbrain_emotion` should keep its field name** in the segment schema if a
  non-SpeechBrain model is adopted. The field is referenced in `orchestrator.py` and the report;
  renaming is a breaking change and is deliberately not decided here.
