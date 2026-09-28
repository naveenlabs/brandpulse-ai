# Transcript Sentiment Channel — Candidate Model Register

**Written:** 30 Aug 2026, before any transcript was labelled and before any candidate was run.
**Status:** pre-registration. Section 3 (what "better" means) is fixed from this date and
must not be revised after results are seen.
**Method:** the eight-step bench method (README), already proven in `comment_bench/`.

---

## 1. Why this bench exists — the measured failure

The transcript channel currently runs `distilbert-base-uncased-finetuned-sst-2-english`
(`pipeline/audio_module.py:318`). SST-2 is a **two-class** model: it emits POSITIVE or
NEGATIVE and has no NEUTRAL class at all. The pipeline manufactures a third class with a
confidence rule (`NEUTRAL_CONFIDENCE_THRESHOLD = 0.70`, `audio_module.py:58`): if the winning
label scores below 0.70, the segment is relabelled NEUTRAL.

**Measured, 30 Aug 2026**, over all 585 segment records in `outputs/*.json` (8 saved runs,
3 distinct videos):

| Label | Count | Share |
|---|---:|---:|
| POSITIVE | 288 | 49.2% |
| NEGATIVE | 285 | 48.7% |
| **NEUTRAL** | **12** | **2.1%** |

The rule almost never fires. SST-2 is calibrated to be confident, so 97.9% of spoken
segments are forced into a binary that the underlying speech does not support. The channel
is effectively a coin flip between positive and negative.

A concrete instance, segment 0 of `outputs/Apple (Iphone 17 Pro Max).json`:

> *"Today we are talking about six months later with the 17 Pro Max. How has my experience
> been?"* → **NEGATIVE, confidence 0.9937**

This is a neutral framing sentence. The false NEGATIVE then propagates: the orchestrator
records `channels_in_conflict: transcript_sentiment` for that segment and flags it
(`conflict_score: 0.789`). Channel error becomes system error.

**Independent corroboration already in hand.** The comment bench tested
`siebert/sentiment-roberta-large-english`, a different two-class model, under this same 0.70
rule. It produced **1 NEUTRAL in 300 comments** (`comment_bench/v2/HUMAN_GROUND_TRUTH_EVALUATION.md`).
Two unrelated two-class models fail the same way under the same rule, which points at the
rule rather than at either model. That is the hypothesis this bench is built to test.

**Prior art in this project.** `PROTOTYPE_FINDINGS.md` records ~48% transcript-sentiment
error on the Apple video and ~38% on Nike. Those figures predate hand-labelled ground truth
and are superseded by whatever this bench measures.

---

## 2. What is being tested

Two questions, in this order:

**Q1 — Is the two-class-plus-threshold construction the fault, or is it SST-2 specifically?**
If any competent native three-class model beats SST-2 by a wide margin, the construction is
the fault and the fix is a swap.

**Q2 — Does spoken transcript text need a different model family from written text?**
Every candidate below was trained on *written* text: tweets, reviews, or NLI pairs. None was
trained on speech transcripts. Whisper output is unpunctuated-in-places, disfluent, and cut
mid-sentence. Whether written-text models transfer to it is unknown and is the second thing
this bench measures.

---

## 3. What "better" means — pre-registered, fixed 30 Aug 2026

**Primary metric: NEUTRAL recall.**
The measured failure is that neutral speech is misread as polarised. A model that raises
overall accuracy while still emitting ~2% NEUTRAL has not fixed the fault this bench exists
to fix.

**Secondary metrics, reported always:**
- Three-class accuracy with a Wilson 95% confidence interval and the sample size.
- Macro-F1 across the three classes (guards against a model that wins by predicting the
  majority class).
- Per-class precision/recall/F1 and the full confusion matrix.
- Exact McNemar test against the incumbent on discordant pairs.

**Decision rule.** A challenger is adopted only if **both** hold:
1. NEUTRAL recall is materially higher than the incumbent's, **and**
2. Three-class accuracy is not lower than the incumbent's by a statistically detectable margin.

**Declared in advance:** the McNemar power ceiling applies here as it did on the holdout set.
With *b*+*c* discordant pairs the smallest attainable two-sided exact p is 2×(½)^(b+c). If the
discordant count is small, a real improvement may be unable to reach p<0.05. This is a
property of the test, not a null result, and will be reported as such.

**Multiple comparisons.** Sixteen candidates are scored on one selection set. The best of
sixteen is optimistically biased by selection alone. Two controls: Bonferroni correction on
the per-class tests, and confirmation of the single winner on a sealed set of videos that
played no part in selection (protocol in `HOLDOUT_PROTOCOL.md`, to be written before labelling).

---

## 4. Design — each candidate tests a stated hypothesis

The register is not a list of models that happen to be popular. Each group exists to
falsify one specific explanation of the failure in §1.

| Group | Hypothesis under test | Candidates |
|---|---|---:|
| 0 | Baselines and controls — what must be beaten | 3 |
| 1 | A native three-class head fixes it | 6 |
| 2 | Review-domain training fits product speech better | 1 |
| 3 | The fault is the two-class construction, not SST-2 | 1 |
| 4 | NEUTRAL must be *defined*, not inferred from low confidence | 2 |
| 5 | A generative model reasons better on ambiguous speech | 2 |
| 6 | Does our comment fine-tune transfer to speech? | 1 |
| | **Total** | **16** |

---

## 5. Candidate register

License and download figures were read from the Hugging Face API on **30 Aug 2026** and are
current as of that date. Parameter counts marked *(not published)* are absent from the API's
`safetensors` metadata; they are not estimated here.

### Group 0 — Baselines and controls

| # | Candidate | Role |
|---|---|---|
| 0.1 | `distilbert-base-uncased-finetuned-sst-2-english` + 0.70 rule | **Incumbent.** The thing to beat. apache-2.0, 67M params, 3,781,705 downloads. |
| 0.2 | Same model, **threshold swept** 0.50→0.99 | **Ablation.** Separates "the model is wrong" from "the threshold is wrong". If a tuned threshold recovers NEUTRAL, the fix is one constant, not a new model. Costs nothing — same predictions, re-thresholded. |
| 0.3 | **VADER** (`vaderSentiment`, already installed) | **Floor.** Rule-based, no neural model, designed for informal speech-like text, has a genuine neutral band. Any transformer that cannot beat VADER has not earned its place in the pipeline. |

0.2 is the single cheapest experiment in this register and the one most likely to be
skipped by a less careful bench. It is included precisely because its result changes what
the evidence-supported conclusion is.

### Group 1 — Native three-class models

| # | Model ID | License | Downloads | Notes |
|---|---|---|---:|---|
| 1.1 | `cardiffnlp/twitter-roberta-base-sentiment-latest` | cc-by-4.0 | 3,202,897 | Winner of the comment bench. ~124M tweets (2018–2021), TweetEval-tuned. Most-downloaded English sentiment model on the Hub. |
| 1.2 | `cardiffnlp/twitter-roberta-base-sentiment` | not stated | 414,063 | The older TweetEval release. Included to test whether the 2021 data refresh matters on speech. |
| 1.3 | `j-hartmann/sentiment-roberta-large-english-3-classes` | **not stated** | 99,917 | RoBERTa-large. Trained on 5,304 manually annotated social-media posts; 86.1% self-reported on its own held-out set. Largest English three-class candidate. |
| 1.4 | `finiteautomata/bertweet-base-sentiment-analysis` | not stated | 997,545 | BERTweet — different tokeniser, built for noisy informal text. |
| 1.5 | `cardiffnlp/twitter-xlm-roberta-base-sentiment` | not stated | 1,017,259 | Multilingual sibling. Tests whether multilingual capacity costs English accuracy. |
| 1.6 | `lxyuan/distilbert-base-multilingual-cased-sentiments-student` | apache-2.0 | 804,350 | Distilled, 135M. The speed candidate — matters because this runs per segment. |

### Group 2 — Review-domain

| # | Model ID | License | Downloads | Notes |
|---|---|---|---:|---|
| 2.1 | `nlptown/bert-base-multilingual-uncased-sentiment` | mit | 923,007 | 167M. Trained on **product reviews**, outputs 1–5 stars, collapsed to three classes. Closest training domain to a spoken product review, and the star scale gives a principled middle band (3★ → NEUTRAL) rather than a confidence hack. |

### Group 3 — Two-class control

| # | Model ID | License | Downloads | Notes |
|---|---|---|---:|---|
| 3.1 | `siebert/sentiment-roberta-large-english` | not stated | 57,876 | A *second* two-class model under the *same* 0.70 rule. Not expected to win. Its job is to confirm the failure is structural: it already produced 1 NEUTRAL in 300 comments. If it repeats that on speech, §1's hypothesis is confirmed by replication rather than by argument. |

### Group 4 — Zero-shot NLI

| # | Model ID | License | Downloads | Notes |
|---|---|---|---:|---|
| 4.1 | `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` | mit | 73,682 | 184M, DeBERTa-v3-base, 512-token window. |
| 4.2 | `facebook/bart-large-mnli` | mit | 3,231,153 | 407M. The most-downloaded zero-shot model on the Hub. |

**Why this group matters.** Every model in Groups 1–3 inherited its notion of "neutral" from
whoever labelled its training set. Zero-shot lets us *write* the definition as a hypothesis
sentence — "this statement is factual and descriptive" — matched to how a reviewer actually
narrates. Since the measured fault is a missing neutral class, a method that defines neutral
explicitly is the most direct attack on it. The hypothesis wording will be fixed and recorded
before scoring, and will not be tuned after seeing results.

### Group 5 — Local generative models

| # | Model | Size | Notes |
|---|---|---|---|
| 5.1 | `llama3.2` (Ollama) | 2.02 GB | **The project's own controller LLM.** Already installed, already trusted to score cross-channel conflict. If it can classify segment sentiment directly, one channel's dedicated model becomes unnecessary — an architecturally interesting result either way. |
| 5.2 | `gemma3:4b` (Ollama) | 3.34 GB | Second local generative model, installed. Tests whether any 5.1 result is llama3.2-specific or general to small local LLMs. |

Both run at `temperature: 0` with a fixed seed and a fixed prompt, for reproducibility.

> **Hard constraint check.** `ollama list` on this machine also shows `qwen3-coder:480b-cloud`,
> `gpt-oss:20b-cloud` and `deepseek-v3.1:671b-cloud`. These are **cloud-executed** and are
> **excluded** — The project forbids any pipeline data leaving the machine. Only the two
> locally-resident models above are eligible. `qwen3-coder:30b` is local but is a
> code-specialised model and is not a credible sentiment candidate; it is excluded on that
> ground, not on licensing.

### Group 6 — Transfer test

| # | Model | Notes |
|---|---|---|
| 6.1 | `models/comment_sentiment_ft` (ours) | cardiffnlp fine-tuned on 1,000 hand-labelled **comments**. Comments and speech are both informal English but differ in register, length and who is speaking. If it transfers, that is a free gain and a genuinely interesting finding. If it does not, that is equally worth reporting: it would show the comment fine-tune learned commenter register rather than sentiment. |

---

## 6. Deliberately excluded, and why

Honest exclusions matter as much as inclusions. The project's evidence rule forbids rejecting a model on
citations alone where testing is feasible; each exclusion below is on grounds that testing
could not change.

| Excluded | Ground for exclusion |
|---|---|
| `tabularisai/multilingual-sentiment-analysis` | **cc-by-nc-4.0 — non-commercial.** Incompatible with the project's B2B framing. (It was the comment channel's original model; this licensing problem is a retrospective second justification for the swap already made.) Available to run as a reference point, not adoptable. |
| Non-English models (`pysentimiento/robertuito`, `blanchefort/rubert-*`, `CAMeL-Lab/*`, `savasy/*`, `oliverguhr/german-sentiment-bert`, and similar) | Wrong language. The corpus is English. Excluded on applicability, not on quality. |
| Financial-sentiment models (`ahmedrachid/FinancialBERT`, `mrm8488/distilroberta-finetuned-financial-news`, `StephanAkkerman/FinTwitBERT`, ModernFinBERT) | Trained to read *earnings sentiment*, where "revenue declined" is negative and "beat expectations" is positive. A different task wearing the same label. |
| `Xenova/twitter-roberta-base-sentiment-latest` | ONNX re-export of candidate 1.1. Same weights, not an independent candidate. |
| Hobby Amazon-review models (`sohan-ai/…`, `eakashyap/…`) | Low provenance, negligible download counts, and at least one is documented as trained on IMDB despite being named for product reviews. Including them would pad the count without informing the decision. |
| MELD-trained dialogue models | MELD (Friends TV dialogue) is the closest public *spoken* sentiment dataset, but no well-maintained off-the-shelf MELD sentiment classifier was found on the Hub on 30 Aug 2026 — only datasets. Recorded as an open lead, not a candidate. |
| Fusion models (MISA, MAG-BERT, Self-MM) | Excluded by project design decision (README, "Engineering rules"). |

**Coverage claim.** The Hugging Face API listing of `text-classification` models matching
"sentiment", sorted by downloads (retrieved 30 Aug 2026), was reviewed to the top 40. Every
English general-purpose sentiment model in that listing is either included above or excluded
with a reason recorded here. This is stated as a bounded search of one ranked listing on one
date, not as a claim to have surveyed the Hub exhaustively.

---

## 7. Threats to validity, declared in advance

1. **Segment boundaries are not sentence boundaries.** Whisper splits on pauses. A segment
   can start mid-clause, so a human rater and a model may both be reading a fragment. The
   label sheet will show the preceding and following segment as greyed context, with only the
   middle segment rated. This is a mitigation, not a cure.
2. **Segments are clustered within videos.** Segments from one video share a speaker, script
   and topic and are not independent observations. Effective sample size tracks the number of
   *videos* more closely than the number of segments. Confidence intervals computed over
   segments will therefore be optimistic, and this will be stated wherever they are quoted.
3. **Whisper transcription error is confounded with sentiment error.** A misheard word can
   flip a prediction. Whisper WER on this corpus has never been measured (open item in the
   roadmap). Any transcript-channel accuracy is therefore an upper bound on what is
   attributable to the sentiment model alone.

   > **Resolved 01 Sep 2026 - measured, not removed.** `whisper_bench/` benched 12 checkpoints
   > on hand-typed ground truth: `base`, which produced every segment in this bench, scores
   > **3.13% WER** (96.87% of words correct). The best available model reaches 1.80%. The
   > confound is therefore real but small, worth roughly 1.3 WER points. The 16-candidate
   > comparison in this bench is **unaffected** - all candidates read identical text - but its
   > absolute accuracy figures are correctly read as *"accuracy given `base` transcripts"*.
   > See `whisper_bench/WHISPER_MODEL_ANALYSIS.md` sections 2 and 5.
4. **Segment yield varies by an order of magnitude.** Measured on the three downloaded
   videos: Samsung 10.1 segments/min, Apple 8.1, Nike 2.1. Nike's longest single segment is
   211 s, which no single sentiment label can honestly describe. Video selection must favour
   continuous-speech content, and any segment over a length cap will be recorded as
   unratable rather than silently labelled.
5. **Corpus is narrow.** All twelve candidate videos are technology reviews. Findings
   generalise to that genre and the report must say so.

---

## 8. Open questions

**Resolved 31 Aug 2026** (see `HOLDOUT_PROTOCOL.md`):

- *Video set and split.* All 12 comment-bench videos retained. The split is **by speaker, not
  by video** — the 12 videos come from only 6 speakers, so a video-level split would have put
  the same voice on both sides. Selection: Marques Brownlee ×4 + Mrwhosetheboss ×4 = 8 videos,
  400 rows. Confirmation: 4 single-video channels, 199 rows, 4 unseen speakers.
- *Segment yield.* 3,258 raw Whisper segments → 1,939 merged. 599 labelled.
- *Unratable criteria.* Under 4 words, or over 20 s. 7 of 1,939 excluded (0.4%).
  `no_speech_prob` was trialled and rejected — it is a 30-second decoding-window statistic.
- *Threat 4 has been superseded.* The order-of-magnitude spread in segment yield was not a
  property of the videos. It was a defect in `_merge_short_segments`, since fixed
  (`MERGE_DEFECT.md`). Post-fix spread is 1.4×, not 4.7×. **All figures in §1 of this document
  were measured on the pre-fix segmentation and are retained as the historical record of the
  fault; the bench itself runs on the rebuilt corpus.**

**Resolved 31 Aug 2026 — recorded before any candidate was scored.**

Ground truth arrived on 31 Aug 2026: 599 rows, all labelled, no blanks, no invalid values.
The two wordings below were fixed and written here *before* the first scoring run, as §3
requires. Neither may be tuned after seeing results; if either is ever changed, the change
and its reason must be recorded here and the affected candidate re-run from scratch.

**Group 4 — zero-shot hypothesis wording (fixed).**

```
hypothesis_template = "In this sentence, the reviewer is {}."

candidate_labels = {
    "POSITIVE": "praising or recommending the product",
    "NEUTRAL":  "describing the product without giving a verdict",
    "NEGATIVE": "criticising or complaining about the product",
}
```

The label phrasings are lifted from `labels/GUIDELINES.md` Rules 1, 2 and 4 — the same
operative definition the human rater was given ("judge the reviewer's attitude to the
product"; "description is NEUTRAL"; a statement is polarised only when the speaker is
*evaluating*, not describing). This is the point of the group: the NEUTRAL class is
*defined* rather than inferred from low confidence, and it is defined identically for the
model and for the human. Scoring uses `multi_label=False` (a softmax over the three
hypotheses), so the three scores are comparable and the argmax is the prediction.

**Group 5 — LLM prompt and decoding parameters (fixed).**

```
system: You are a sentiment annotator for spoken product-review transcripts.
        Reply with one word only.

user:   Decide the reviewer's attitude to the product in the SENTENCE below.

        POSITIVE - the reviewer praises or recommends the product.
        NEGATIVE - the reviewer criticises or complains about the product.
        NEUTRAL  - the reviewer describes, explains, asks a question, or makes an
                   aside, without giving a verdict. Most narration is NEUTRAL.

        Judge only the SENTENCE. The CONTEXT is there to make a fragment readable and
        must not be rated.

        CONTEXT BEFORE: {context_before}
        SENTENCE: {text}
        CONTEXT AFTER: {context_after}

        Answer with exactly one word: POSITIVE, NEGATIVE, or NEUTRAL.
```

Decoding, for reproducibility: `temperature: 0`, `seed: 42`, `num_predict: 8`,
`top_p: 1.0`, via `POST http://localhost:11434/api/chat` — local only. The reply is
uppercased and matched against the three labels; anything unmatched is recorded as a
parse failure and counted, never silently coerced to NEUTRAL, because coercing to the
majority class would flatter the model on this bench's primary metric.

**Context is supplied to Group 5 only.** Groups 0–4 are scored on the segment text alone.

- *Groups 0–3 and 6* are scored on the segment alone because that is exactly how
  `audio_module.add_transcript_sentiment()` calls them in production. Giving them context
  would measure a system the pipeline does not run.
- *Group 4* is also scored on the segment alone. **This corrects the first draft of this
  section, written earlier the same day, which had grouped 4 with 5.** In zero-shot NLI the
  sequence *is* the premise: appending the neighbouring segments would ask the model whether
  the hypothesis is entailed by all three segments together, which is a different task from
  the one the human performed and from the one the pipeline needs. The variable this group
  isolates is the *hypothesis wording*, not the input window, and it is held to the same
  input as every other classifier. Recorded here rather than silently amended, per the
  paragraph above; no candidate had been scored when this was changed.
- *Group 5* receives context, with an explicit instruction to rate only the middle sentence.
  A prompt can carry that distinction and a fixed classification head cannot. This mirrors
  what the human rater saw.

The remaining asymmetry favours Group 5 and must be stated wherever its results are quoted.
If a Group 5 model wins, a context-free ablation of it is required before adoption, so that
the gain is attributed to the model rather than to the extra input.

**Still open:**

- Whether `min_duration = 3.0 s` is itself the right floor. It predates this work and has
  never been chosen by measurement. Out of scope for this bench, but it is not validated.

---

## 9. Provenance

| Fact | Source | Date |
|---|---|---|
| Label distribution 288/285/12 over 585 segments | `outputs/*.json`, counted directly | 30 Aug 2026 |
| Segments-per-minute, segment length extremes | `outputs/*.json`, computed directly | 30 Aug 2026 |
| Licenses, download counts, parameter counts | Hugging Face API (`/api/models/{id}`) | 30 Aug 2026 |
| Zero-shot model card facts (MIT, 0.2B, 512 tokens) | model card, `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` | 30 Aug 2026 |
| j-hartmann training data (5,304 posts, 86.1%) | model card | 30 Aug 2026 |
| cardiffnlp-latest training data (~124M tweets, 2018–2021) | model card / TweetEval | 30 Aug 2026 |
| Locally installed Ollama models and sizes | `curl http://localhost:11434/api/tags` | 30 Aug 2026 |
| siebert 1 NEUTRAL / 300 comments | `comment_bench/v2/HUMAN_GROUND_TRUTH_EVALUATION.md` | 27–30 Aug 2026 |
