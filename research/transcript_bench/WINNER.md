# Transcript Bench — Winner, chosen on the selection set

**Written 31 Aug 2026, after scoring all sixteen registered candidates on the 400-row
selection set and before the sealed confirmation set was opened.**

The existence of this file is what unseals the confirmation set
(`run_bench.py` refuses `--split confirmation` until it exists). It is written first, and
deliberately, so that the choice cannot be revised after the holdout result is known.

---

## 1. The winner

**`cardiffnlp/twitter-xlm-roberta-base-sentiment`** (candidate 1.5), replacing
`distilbert-base-uncased-finetuned-sst-2-english` + the 0.70 confidence rule.

| Metric | Incumbent (0.1) | Winner (1.5) | Change |
|---|---:|---:|---|
| **NEUTRAL recall** (primary) | 0.045 | **0.795** | **×17.7** |
| Three-class accuracy | 0.463 | **0.647** | +0.184 |
| Accuracy 95% CI (Wilson) | [0.414, 0.511] | [0.599, 0.693] | intervals disjoint |
| Macro-F1 | 0.401 | **0.633** | +0.232 |
| NEUTRAL predicted (true = 156) | 13 | 216 | — |
| Exact McNemar vs incumbent | — | b=136, c=62, **p = 1.5×10⁻⁷** | significant under Bonferroni (α=0.0033) |
| Inference cost | 26.7 ms/segment | 25.0 ms/segment | no regression |

n = 400 segments, 8 videos, 2 speakers. Confidence intervals are computed over segments and
are therefore optimistic, because segments within a video share a speaker and script
(`HOLDOUT_PROTOCOL.md` §5).

## 2. How the decision was reached, including where the rule was under-specified

`CANDIDATE_MODELS.md` §3 fixed **NEUTRAL recall** as the primary metric and gave an adoption
rule: a challenger is adopted only if its NEUTRAL recall is materially higher than the
incumbent's *and* its accuracy is not detectably lower.

**That rule is a filter, not a ranking.** Thirteen of fifteen scored candidates pass it. The
pre-registration named a primary metric but did not fully specify how to order the survivors.
This is a real gap in the pre-registration and it is recorded here rather than papered over.

Ranking on the primary metric alone does not work, and this is demonstrable rather than
arguable. A degenerate predictor that answers NEUTRAL to every segment scores:

| Degenerate "always NEUTRAL" | Value |
|---|---:|
| NEUTRAL recall | **1.000** — higher than every real candidate |
| Accuracy | 0.390 |
| Macro-F1 | 0.187 |

So the primary metric is gameable by a model that has learned nothing. The pre-registration
anticipated exactly this: macro-F1 is listed in §3 as a secondary metric included to guard
"against a model that wins by predicting the majority class", and NEUTRAL is the majority
class in this corpus (39.0%). The guard was written before results were seen and it is what
resolves the ranking.

Applying it:

| Candidate | NEUT recall | NEUT predicted | Accuracy | Macro-F1 | Outcome |
|---|---:|---:|---:|---:|---|
| 1.3 j-hartmann-large | 0.897 | 289 (**1.85× true**) | 0.568 | 0.533 | **Rejected.** Highest NEUTRAL recall, but buys it by over-predicting NEUTRAL, and is significantly *less* accurate than 1.5 (McNemar b=31, c=63, p=0.0013 — significant under Bonferroni). |
| **1.5 cardiffnlp-xlm** | **0.795** | 216 (1.38×) | **0.647** | **0.633** | **Adopted.** |
| 6.1 our comment fine-tune | 0.558 | 125 (0.80×) | 0.657 | 0.650 | Best accuracy and macro-F1, but 0.237 lower NEUTRAL recall on the primary metric, and its accuracy edge over 1.5 is not detectable (p=0.779). |
| 1.1 cardiffnlp-latest | 0.769 | 222 (1.42×) | 0.623 | 0.600 | Loses to 1.5 on all three; difference vs 1.5 not significant (p=0.320). |

1.5 has the highest NEUTRAL recall of any candidate that is not significantly worse on
accuracy than the field's best. 6.1's higher accuracy is real but not statistically
detectable, and it costs 0.237 of the primary metric.

**Recorded as a methodological limitation:** the ordering step above was applied after
results were visible. It follows metrics fixed in advance and the guard's stated purpose, but
the *procedure* combining them was not written down in advance. A future bench in this
project should pre-register the full ranking procedure, not only the filter and the primary
metric. This is the single weakest point in the method and it is stated rather than hidden.

## 3. What the controls established

The two control candidates did their job, and both results are findings in their own right.

**Candidate 3.1 (siebert, second two-class model, same 0.70 rule) — the fault is structural.**
It emitted 3 NEUTRAL predictions in 400 segments and got all 3 wrong: NEUTRAL recall and
precision both **0.000**. Only 3 of 400 segments fell below the 0.70 cut-off at all. This
replicates the comment bench's finding of 1 NEUTRAL in 300 comments on the same model. Two
unrelated two-class models fail identically under the same rule, which locates the fault in
the *construction* rather than in DistilBERT. §1 of `CANDIDATE_MODELS.md` proposed this as a
hypothesis; it is now measured.

**Candidate 0.2 (threshold sweep) — the constant is also badly chosen, but retuning it is
not a fix.** Re-thresholding the incumbent's own cached scores:

| Threshold | NEUTRAL predicted | NEUTRAL recall | Accuracy | Macro-F1 |
|---:|---:|---:|---:|---:|
| 0.50 | 0 | 0.000 | 0.450 | 0.369 |
| **0.70 (production)** | **13** | **0.045** | **0.463** | **0.401** |
| 0.85 | 35 | 0.103 | 0.465 | 0.425 |
| 0.95 | 65 | 0.167 | 0.460 | 0.439 |
| 0.99 | 155 | 0.500 | 0.535 | 0.535 |

This is the cheapest experiment in the register and it changes the supported conclusion.
Production's 0.70 is not merely arbitrary, it is *poorly* chosen: pushing the cut-off to 0.99
raises accuracy to 0.535 and NEUTRAL recall to 0.500 at no compute cost. But even that
extreme setting — where the rule fires on 39% of segments — remains well below the adopted
model on every metric (0.535 vs 0.647 accuracy; 0.500 vs 0.795 NEUTRAL recall). So both
things are true, and the report must say both: the constant was wrong, *and* fixing the
constant would not have been enough.

## 4. Other findings worth reporting

- **Multilingual capacity did not cost English accuracy — it helped.** §5 of the register
  included 1.5 to test whether the multilingual sibling would underperform the English-only
  cardiffnlp models. It beat both (0.647 vs 0.623 for 1.1 and 0.625 for 1.2), though the
  margins are not statistically detectable. The prior behind the question was wrong.
- **The comment fine-tune transfers (candidate 6.1).** Fine-tuned on 1,000 hand-labelled
  *comments*, it scores the highest accuracy (0.657) and macro-F1 (0.650) of any candidate on
  *speech* it has never seen. It was not adopted only because it under-predicts NEUTRAL
  relative to the primary metric. This answers the register's open question: the comment
  fine-tune learned sentiment, not commenter register.
- **The local LLMs lost, with a handicap in their favour.** llama3.2 (0.276 NEUTRAL recall,
  0.557 accuracy) and gemma3:4b (0.372, 0.608) both underperformed the encoder models
  *despite* being the only candidates given the surrounding context, and at 25–34× the
  inference cost per segment (0.64 s and 0.84 s vs 0.025 s). The declared context asymmetry
  therefore did not decide anything, and the context-free ablation §8 required before
  adopting a Group 5 model is not needed. Both parsed cleanly: 0 parse failures in 400,
  exactly three distinct replies each, so the result is about classification, not formatting.
- **Zero-shot underperformed a fine-tuned head.** Defining NEUTRAL explicitly in the
  hypothesis (0.712 recall for 4.1) beat every two-class construction but not the native
  three-class models, at 5× the cost. bart-large-mnli (4.2) was worse still (0.417).
- **VADER, the rule-based floor, was not beaten by everything.** VADER (0.468 NEUTRAL recall,
  0.507 accuracy) outscored the incumbent, nlptown (2.1), and lxyuan (1.6). Three of the
  fifteen candidates fail to beat a model with no neural network in it, and the incumbent is
  one of them.

## 5. The winner's own weaknesses

Stated here because §4 of the marking criteria asks for evaluation, not advocacy.

Confusion matrix, selection set (rows = true, columns = predicted):

| | POS | NEU | NEG |
|---|---:|---:|---:|
| **POSITIVE** (155) | 91 | 54 | 10 |
| **NEUTRAL** (156) | 17 | 124 | 15 |
| **NEGATIVE** (89) | 7 | 38 | 44 |

- **NEGATIVE recall is 0.494** — it misses half of all criticism, and 38 of those 45 misses
  go to NEUTRAL. For a brand-sentiment product this is the costliest error direction there
  is: the system will under-report negative sentiment about a client's product.
- **NEUTRAL precision is 0.574** — it still over-predicts NEUTRAL by 1.38×, having swung from
  the incumbent's opposite failure.
- **POSITIVE recall is 0.587**, with 54 positives read as neutral. The model is systematically
  biased toward the middle class.
- Accuracy is **0.647**, so roughly one segment in three is still wrong. This is an
  improvement, not a solution, and the orchestrator downstream should continue to be treated
  as consuming a noisy channel.

Improvement is uniform across the selection set rather than carried by one video: accuracy
rises on 8 of 8 videos (from +0.000 to +0.440) and NEUTRAL recall rises on 8 of 8.

## 6. What happens next, in this order

1. Adopt 1.5 into `pipeline/audio_module.py` (step 6 of the bench method — a bench that is not
   adopted is a benchmarking exercise, not a decision).
2. Re-run the full test suite and record the pass count.
3. **Only then** score the sealed confirmation set — 199 segments, 4 unseen speakers.
4. Report the confirmation result whatever it is. Per `HOLDOUT_PROTOCOL.md` §5 it cannot
   change the winner; if 1.5 underperforms there, that is the finding.

---

## 7. Confirmation result — appended 31 Aug 2026, after the holdout was scored

Sections 1–6 above were written and saved **before** this section existed and before the
sealed set was opened. Nothing above has been edited since. Only the incumbent and the single
adopted winner were scored here; the other thirteen candidates were deliberately not run on
the holdout, so that there is no table to be tempted by (`HOLDOUT_PROTOCOL.md` §5).

**199 segments, 4 speakers that played no part in selection.**

| Metric | Incumbent | Winner 1.5 | Change |
|---|---:|---:|---|
| **NEUTRAL recall** | 0.073 | **0.740** | ×10.1 |
| Three-class accuracy | 0.382 | **0.678** | +0.296 |
| Accuracy 95% CI | [0.317, 0.451] | [0.611, 0.739] | disjoint |
| Macro-F1 | 0.360 | **0.662** | +0.302 |
| Exact McNemar | — | b=76, c=17, **p = 4.4×10⁻¹⁰** | — |

The power ceiling declared in advance did not bind: with 93 discordant pairs the smallest
attainable p was 2×10⁻²⁸, so the test had room to detect the effect and did.

**Per speaker — the improvement holds on all four, on both metrics:**

| Speaker | n | Accuracy (inc → win) | NEUTRAL recall (inc → win) |
|---|---:|---|---|
| Dave2D | 50 | 0.500 → 0.760 | 0.000 → 0.647 |
| Jeremy Fragrance | 49 | 0.388 → 0.735 | 0.097 → 0.742 |
| ShortCircuit | 50 | 0.340 → 0.560 | 0.150 → 0.750 |
| The Tech Chap | 50 | 0.300 → 0.660 | 0.036 → 0.786 |

**Three things worth stating plainly.**

1. **The result is stronger on the holdout than on the selection set** (accuracy 0.678 vs
   0.647; NEGATIVE recall 0.667 vs 0.494). A selection-set winner usually regresses on a
   holdout, because part of its selection-set margin was selection noise. This one did not.
   The most likely explanation is that the confirmation set is 48.2% NEUTRAL against the
   selection set's 39.0%, and the adopted model is strongest on NEUTRAL — so this is partly a
   property of the split, not purely of the model, and it should not be over-claimed.
2. **Cross-category transfer held.** `haWvrSliMVY` is a fragrance review, the one non-tech
   video in the corpus, and it improved from 0.388 to 0.735 accuracy. On 49 segments this is
   too small to carry a claim on its own, exactly as `HOLDOUT_PROTOCOL.md` §5 declared in
   advance, but it is evidence against the failure being tech-vocabulary-specific.
3. **The incumbent is worse than chance-level guessing on this set.** Always predicting
   NEUTRAL would score 0.482 on the confirmation set; the deployed model scored **0.382**.
   The channel was actively worse than a constant.

**The decision recorded in §1 stands unchanged.** The holdout confirmed it rather than
altering it, which is the only outcome that leaves both the selection and the confirmation
estimates interpretable.
