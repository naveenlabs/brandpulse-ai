# Transcript Sentiment Model Analysis — 16 candidates on 599 hand-labelled segments

**Run 31 Aug 2026.** Companion to `CANDIDATE_MODELS.md` (pre-registration),
`HOLDOUT_PROTOCOL.md` (split), `labels/GUIDELINES.md` (labelling rules) and `WINNER.md`
(the decision). Method is the eight-step bench method (README), proven in `comment_bench/`.

Every number here was produced on this project's own data by scripts in this directory and
can be re-derived with `python research/transcript_bench/report_bench.py`.

---

## 1. Methodology

| | |
|---|---|
| Corpus | 12 YouTube videos, 6 speakers, 151 minutes |
| Transcription | Whisper `base`, `language="en"`, 3,258 raw → 1,939 merged segments |
| Labelled | **599 segments** (400 selection / 199 confirmation), one human rater |
| Split | **By speaker, not by video** — 4 speakers held out entirely |
| Primary metric | **NEUTRAL recall**, fixed before labelling |
| Candidates | 16, in 7 groups, each testing a stated hypothesis |
| Blinding | One shuffled sheet; rater could not tell selection from confirmation rows |
| Ground truth | Hand-labelled against 12 written rules; never derived from any model |

Labelling integrity, verified programmatically before scoring: 599 of 599 rows labelled, 0
blank, 0 invalid values, 0 duplicate segment ids, 0 case or whitespace variants.

**Ground-truth class distribution:**

| Split | n | POSITIVE | NEUTRAL | NEGATIVE |
|---|---:|---:|---:|---:|
| Selection | 400 | 38.8% | **39.0%** | 22.2% |
| Confirmation | 199 | 32.2% | **48.2%** | 19.6% |

The two selection-set speakers agreed closely on NEUTRAL rate (40.5% and 37.5%), which is
weak evidence that the rater applied Rule 2 consistently across the sheet.

## 2. The failure this bench was built to measure — now quantified

The deployed channel used `distilbert-base-uncased-finetuned-sst-2-english`, a **two-class**
model, with a 0.70 confidence rule manufacturing a third class.

**Ground truth says 39.0% of spoken segments are NEUTRAL. The deployed model called 3.2%
of them NEUTRAL, and got 7 of 156 right.**

| | Incumbent, selection set |
|---|---:|
| NEUTRAL recall | **0.045** |
| Three-class accuracy | 0.463 |
| Macro-F1 | 0.401 |
| Majority-class baseline (always NEUTRAL) | 0.390 |

The channel was 7.3 percentage points better than a constant. On the confirmation set it was
**worse than a constant**: 0.382 accuracy against 0.482 for always-NEUTRAL.

This supersedes the ~48% / ~38% error figures in `PROTOTYPE_FINDINGS.md`, which predate
hand-labelled ground truth and were additionally measured on the pre-fix segmentation.

## 3. Headline results — selection set (n = 400)

Ranked by the pre-registered primary metric. `NEUT-R` = NEUTRAL recall, `NEUT-P` = NEUTRAL
precision, `p` = exact McNemar against the incumbent.

| # | Candidate | Grp | NEUT-R | NEUT-P | Accuracy | 95% CI | Macro-F1 | p | s/seg |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| 1.3 | j-hartmann-large | 1 | 0.897 | 0.484 | 0.568 | [0.519, 0.615] | 0.533 | 0.0083 | 0.039 |
| **1.5** | **cardiffnlp-xlm** | **1** | **0.795** | **0.574** | **0.647** | **[0.599, 0.693]** | **0.633** | **<10⁻⁵** | **0.025** |
| 1.4 | BERTweet | 1 | 0.776 | 0.528 | 0.615 | [0.566, 0.661] | 0.588 | <10⁻⁴ | 0.022 |
| 1.1 | cardiffnlp-latest | 1 | 0.769 | 0.541 | 0.623 | [0.574, 0.669] | 0.600 | <10⁻⁴ | 0.031 |
| 1.2 | cardiffnlp-original | 1 | 0.724 | 0.543 | 0.625 | [0.577, 0.671] | 0.597 | <10⁻⁵ | 0.021 |
| 4.1 | DeBERTa zero-shot | 4 | 0.712 | 0.526 | 0.598 | [0.549, 0.644] | 0.592 | 0.0002 | 0.130 |
| 6.1 | our comment fine-tune | 6 | 0.558 | 0.696 | 0.657 | [0.610, 0.702] | 0.650 | <10⁻⁵ | 0.017 |
| 0.3 | VADER | 0 | 0.468 | 0.514 | 0.507 | [0.459, 0.556] | 0.483 | 0.197 | 0.000 |
| 2.1 | nlptown 5-star | 2 | 0.436 | 0.453 | 0.492 | [0.444, 0.541] | 0.476 | 0.390 | 0.020 |
| 4.2 | BART-large-MNLI | 4 | 0.417 | 0.575 | 0.603 | [0.554, 0.649] | 0.581 | <10⁻⁴ | 0.171 |
| 5.2 | gemma3:4b | 5 | 0.372 | 0.598 | 0.608 | [0.559, 0.654] | 0.601 | <10⁻⁵ | 0.842 |
| 5.1 | llama3.2 | 5 | 0.276 | 0.512 | 0.557 | [0.509, 0.605] | 0.543 | 0.0008 | 0.636 |
| 1.6 | lxyuan-distil | 1 | 0.109 | 0.354 | 0.425 | [0.377, 0.474] | 0.384 | 0.188 | 0.019 |
| 0.1 | **SST-2 (incumbent)** | 0 | 0.045 | 0.538 | 0.463 | [0.414, 0.511] | 0.401 | — | 0.027 |
| 3.1 | siebert (control) | 3 | 0.000 | 0.000 | 0.512 | [0.464, 0.561] | 0.418 | 0.021 | 0.035 |

Bonferroni-corrected threshold for 15 candidates is α = 0.0033. **Nine of the fourteen
challengers beat the incumbent significantly** at that level. The five that do not are VADER,
nlptown, lxyuan, siebert and — notably — j-hartmann, whose p = 0.0083 clears an uncorrected
0.05 but not the corrected threshold.

Confidence intervals are computed over segments. Segments within a video share a speaker and
script, so the intervals are optimistic and the effective sample size tracks the 6 speakers
more closely than the 599 segments.

## 4. The two controls, which are the most informative rows in the table

**Candidate 3.1 — the fault is the construction, not DistilBERT.**
`siebert/sentiment-roberta-large-english` is a different two-class model by different authors
on a different architecture. Under the same 0.70 rule it produced 3 NEUTRAL predictions in
400 segments and got all 3 wrong (recall and precision both 0.000). Only 3 of 400 segments
fell below the cut-off at all: its *minimum* winning confidence across the whole set was
0.5154, and it is confident nearly everywhere. This replicates the comment bench's 1-in-300
result on the same model. Two unrelated two-class models fail identically under the same
rule, which is replication rather than argument.

**Candidate 0.2 — the constant was also wrong, but retuning it was never the fix.**
Re-thresholding the incumbent's own cached scores costs no additional compute:

| Threshold | NEUTRAL predicted | NEUT-R | NEUT-P | Accuracy | Macro-F1 |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 0 | 0.000 | 0.000 | 0.450 | 0.369 |
| 0.65 | 7 | 0.013 | 0.286 | 0.450 | 0.378 |
| **0.70 (production)** | **13** | **0.045** | **0.538** | **0.463** | **0.401** |
| 0.80 | 25 | 0.058 | 0.360 | 0.453 | 0.400 |
| 0.90 | 44 | 0.115 | 0.409 | 0.460 | 0.426 |
| 0.95 | 65 | 0.167 | 0.400 | 0.460 | 0.439 |
| 0.99 | 155 | 0.500 | 0.503 | 0.535 | 0.535 |

Both conclusions are true and the report must carry both. The production constant was
*poorly* chosen — pushing it to 0.99 would have lifted accuracy to 0.535 and NEUTRAL recall
to 0.500 for free. And even that extreme setting stays well below the adopted three-class
model (0.647 accuracy, 0.795 NEUTRAL recall), so tuning the constant would have been an
improvement and still the wrong fix.

This is the cheapest experiment in the register and the one most likely to be skipped. It is
the row that makes the conclusion honest.

## 5. What each group's hypothesis returned

| Group | Hypothesis | Verdict |
|---|---|---|
| 1 — native 3-class head | A real NEUTRAL class fixes it | **Supported.** 5 of 6 beat the incumbent; the best lifts NEUTRAL recall 17.7×. |
| 2 — review domain | Review training fits product speech | **Not supported.** nlptown scored 0.492, below VADER, and its p vs incumbent is 0.390. Closest training domain lost. |
| 3 — 2-class control | The construction is the fault | **Supported by replication.** 0.000 NEUTRAL recall. |
| 4 — zero-shot NLI | NEUTRAL must be defined, not inferred | **Partly.** Defining it explicitly (0.712) beat every two-class construction but lost to fine-tuned 3-class heads at 5× the cost. |
| 5 — local LLM | Generative reasoning beats a classifier | **Not supported.** Both lost, at 25–34× the cost, *with* a context advantage. |
| 6 — transfer | Does our comment fine-tune transfer to speech? | **Yes.** Highest accuracy (0.657) and macro-F1 (0.650) of any candidate. |

**Findings worth reporting beyond the winner:**

- **Multilingual capacity did not cost English accuracy.** 1.5 was included to test whether
  the multilingual sibling would underperform the English-only cardiffnlp models. It beat
  both (0.647 vs 0.623 and 0.625), though not detectably. The prior was wrong.
- **The comment fine-tune transfers to speech.** Trained on 1,000 hand-labelled *comments*,
  it leads on accuracy and macro-F1 on *spoken* segments it has never seen. It answers the
  register's open question: that fine-tune learned sentiment, not commenter register. It was
  not adopted only because it under-predicts NEUTRAL (0.558 recall) against the primary
  metric, and its accuracy edge over 1.5 is not detectable (p = 0.779).
- **Both local LLMs lost despite a handicap in their favour.** They were the only candidates
  given surrounding context, and still scored 0.276 and 0.372 NEUTRAL recall at 0.64 s and
  0.84 s per segment against 0.025 s. The context asymmetry declared in advance therefore
  decided nothing, and no context-free ablation is required. Both parsed cleanly — 0 failures
  in 400, exactly three distinct replies each — so this is a classification result, not a
  formatting artefact. For an orchestration project this is worth stating directly: the
  controller LLM is good at scoring cross-channel conflict and measurably bad at replacing a
  channel.
- **Three candidates failed to beat a rule-based floor.** VADER (0.507) outscored nlptown,
  lxyuan, and the deployed incumbent. A model with no neural network in it beat the model
  that was in production.

## 6. The adopted model, and where it is weak

`cardiffnlp/twitter-xlm-roberta-base-sentiment`, adopted into
`pipeline/audio_module.py:51` on 31 Aug 2026. The 0.70 threshold was **removed, not retuned**.

**Confirmation set — 199 segments, 4 speakers never seen during selection:**

| Metric | Incumbent | Adopted | Change |
|---|---:|---:|---|
| NEUTRAL recall | 0.073 | **0.740** | ×10.1 |
| Accuracy | 0.382 | **0.678** | +0.296 |
| Macro-F1 | 0.360 | **0.662** | +0.302 |
| Exact McNemar | — | b=76, c=17 | **p = 4.4×10⁻¹⁰** |

Improvement holds on all 4 unseen speakers on both metrics, and on the one non-technology
video in the corpus (fragrance, 0.388 → 0.735).

**Weaknesses, stated because evaluation is not advocacy:**

- **NEGATIVE recall is 0.494 on the selection set** (0.667 on confirmation). It misses roughly
  half of all criticism, and most misses go to NEUTRAL. For a brand-monitoring product this is
  the costliest error direction available: the system under-reports negative sentiment about a
  client's product. This is the most important open weakness in the channel.
- **It over-predicts NEUTRAL by 1.38×** — the opposite failure to the incumbent's, smaller but
  real. NEUTRAL precision is 0.574.
- **Roughly one segment in three is still wrong** (0.647 / 0.678 accuracy). The orchestrator
  downstream must continue to be treated as consuming a noisy channel, not a solved one.
- **Whisper WER is unmeasured**, so a misheard word can flip a prediction. Every accuracy
  figure here is an upper bound on what is attributable to the sentiment model alone.
- **One rater.** No second annotator, so no inter-annotator agreement statistic exists and
  rater bias cannot be separated from model error. This is the single biggest threat to the
  ground truth and it is not mitigated, only declared.
- **Genre.** 11 of 12 videos are technology reviews. Findings generalise to that genre.

## 7. Method limitations found while running this bench

- **The pre-registered decision rule was a filter, not a ranking.** Thirteen candidates passed
  it. Ordering them required the pre-registered secondary metric (macro-F1, included
  explicitly to guard against majority-class gaming) and that combination step was not written
  down in advance. Recorded in `WINNER.md` §2. A future bench should pre-register the full
  ranking procedure.
- **The primary metric is gameable and this was demonstrated, not assumed.** A degenerate
  "always NEUTRAL" predictor scores NEUTRAL recall 1.000 — better than all 16 real candidates
  — with accuracy 0.390 and macro-F1 0.187. Any bench that ranks on a single class-level
  recall needs this reductio run against it.
- **The aggregate class distribution over all 599 rows was computed during label validation,
  before the winner was fixed**, which technically reveals the sealed set's distribution by
  subtraction. The leak is weak and could not steer the outcome, because the adoption rule was
  mechanical and fixed in advance, but it is recorded rather than ignored. A cleaner
  implementation would validate each split's labels separately.

## 8. Reproducing this

```bash
cd brandpulse_ai
source .venv/bin/activate

python research/transcript_bench/run_bench.py                        # 15 runs, selection set
python research/transcript_bench/report_bench.py --json-out results_selection.json
python research/transcript_bench/run_bench.py --split confirmation --only 0.1 1.5
python -m pytest                                            # 229 passed
```

Predictions are cached in `transcript_bench/predictions/`, so the analysis re-derives without
re-running a model. `run_bench.py` refuses `--split confirmation` unless `WINNER.md` exists.
