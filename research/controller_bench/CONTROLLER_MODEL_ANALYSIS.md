# Controller model bench — is `llama3.2` the problem, or is the data?

**05 Sep 2026.** Pre-registered in `PROTOCOL.md` before any candidate was
downloaded. Every number below is re-derived from the cached responses in
`cache/` by `verify_claims.py` and required to appear verbatim in this file.

---

## 0. The question, and the short answer

The deployed controller returns `conflict_score` **0.0 on 473 of 481** cached
corpus segments. Two readings were possible and the project had no way to choose
between them:

- **the data is quiet** — the channels really do agree almost everywhere, and a
  controller that says so is correct;
- **the controller is broken** — genuine cross-channel disagreements are being
  scored as agreement.

Re-deriving the channel valences of those 481 segments from the pipeline's own
labels puts numbers on it. **81** carry a *polar* disagreement — some channel
POSITIVE while another is NEGATIVE — and the incumbent scores above zero on **8**
of them: a detection rate of **9.9%** (95% Wilson **5.1%–18.3%**). Its `flags`
field came back empty on **0 of 481** — that is, it emitted a flag on none of
them. And it named `facial_emotion` among the channels in conflict on **264** of
481 responses, for a corpus that has no facial channel at all.

**The answer is the second reading, and §5 establishes it decisively.** Given
byte-identical payloads and the byte-identical deployed prompt, five other
locally-runnable models find every polar disagreement the incumbent misses.

Two further findings came out of the work that matter more than the model
ranking, and neither was planned: the flag threshold the whole product rests on
may be **mathematically unreachable** (§6), and the model that is best at
comparing labels is **blind** to the one thing only an LLM can do (§7).

---

## 1. Why the controller could be benched without collecting a single label

Five channels have been benched here, and every one of them needed hand-labelled
ground truth, because "what emotion is this face showing" has no closed form.

The controller is different in kind, and this is the design fact the whole bench
rests on:

> the controller is handed four discrete valence labels and asked whether they
> disagree. **Whether they disagree is a function of those labels.**

So the ground truth is *analytic*. It is computed from the controller's own
**inputs** — never from any model's output — which satisfies step 2 of the bench method (README) in
the strongest form available anywhere in this project: there is no rater to be
inconsistent with themselves, and therefore no reliability ceiling to estimate.
`facial_bench/v2` had to spend 48 duplicate frames measuring a human ceiling of
87.5%. Here the ceiling is 1.0 and it is provable.

**What that buys, and what it does not.** The reference measures whether a
controller performs the task the deployed system prompt specifies. It does **not**
measure whether that task detects real inauthenticity: the labels being compared
come from channels measured at 34.2%, 48.9%, 67.8% and 78.7%. A controller that
disagrees with them may well be right about the world. No claim of the second kind
is drawn from any number here.

### 1.1 The reference

Every channel label is mapped to the valence axis using the production
`orchestrator._VALENCE_WORDS`, imported rather than copied. A label off that axis
(`surprise`, `unknown`, `none detected`) yields **no reading**, and that channel is
excluded from the comparison rather than coerced to NEUTRAL — the rule the
pipeline already follows in `_channel_valences`.

For the readable valences `L`:

| quantity | definition |
|---|---|
| `ref_any` | `L` contains two different valences |
| `ref_polar` | `L` contains **both** POSITIVE and NEGATIVE |
| `ref_score` | mean over channel *pairs* of: **1.0** polar, **0.5** NEUTRAL-involving, **0.0** matching |

`ref_score` is 0.0 at full agreement and 1.0 when every pair is polar — exactly the
two endpoints the deployed prompt defines (*"0.0 (full agreement) to 1.0 (all
channels disagree)"*). The 0.5 is the bench's single free parameter; it was fixed
before any run, the primary metric does not use it, and §5.6 shows the ranking
does not move when it is changed.

---

## 2. What was tested against what

### 2.1 The candidates

Every candidate runs **locally under Ollama** on the deployment machine (Apple M1
Pro, 16 GB unified memory). That is a hard constraint of the project (README), not a
convenience: the entire B2B framing of this project is data sovereignty, and a
controller needing a cloud endpoint is not a candidate at any accuracy.

Parameter counts, quantisation and licences below are read from each model's own
manifest via `ollama show` (`cache/registry.json`), not recalled.

| id | Ollama tag | params | quant | licence |
|---|---|---|---|---|
| `llama3.2` | `llama3.2:latest` | 3.2 B | Q4_K_M | Llama 3.2 Community |
| `llama3.1_8b` | `llama3.1:8b` | 8.0 B | Q4_K_M | Llama 3.1 Community |
| `qwen2.5_7b` | `qwen2.5:7b-instruct` | 7.6 B | Q4_K_M | Apache 2.0 |
| `qwen3_8b` | `qwen3:8b` | 8.2 B | Q4_K_M | Apache 2.0 |
| `mistral_7b` | `mistral:7b` | 7.2 B | Q4_K_M | Apache 2.0 |
| `gemma3_4b` | `gemma3:4b` | 4.3 B | Q4_K_M | Gemma Terms of Use |
| `phi4_mini` | `phi4-mini:latest` | 3.8 B | Q4_K_M | MIT |
| `granite3.3_8b` | `granite3.3:8b` | 8.2 B | Q4_K_M | Apache 2.0 |

Four size peers of the incumbent (3–4 B) and four larger models (7–8 B), so
"bigger is better" is testable rather than assumed.

### 2.2 The three references, which are not competitors

| id | what it is |
|---|---|
| `rule_baseline` | the reference of §1.1, evaluated as a predictor — a complete controller in six lines, with no LLM |
| `always_zero` | constant 0.0. The strategy the incumbent currently approximates |
| `always_flag` | constant 1.0. The opposite degenerate |

`rule_baseline` scores **1.000 on P1 and P2 by construction**, because it *is* the
reference. That is stated in advance in `PROTOCOL.md` §3.2 and it is not reported
as a victory. It is a statement about the task: the label-comparison sub-task has a
closed form, and an LLM has to beat a six-line function before its language ability
is earning anything. Where `rule_baseline` can genuinely lose is the incongruence
suite (§7), where it is structurally incapable of scoring above zero.

`always_zero` and `always_flag` exist so that a metric either of them could win is
disqualified from being primary. **MCC is the metric with that property**: a
constant predictor scores exactly 0.0 on it whatever the class balance, and that is
why it is P1.

### 2.3 What was excluded, and on what grounds

| excluded | grounds |
|---|---|
| `gpt-oss:20b-cloud`, `deepseek-v3.1:671b-cloud`, `qwen3-coder:480b-cloud` | present in the local registry but **proxied to `ollama.com`**. The project's hard constraint forbids any pipeline call leaving the machine. Excluded on the **constraint**, not on quality. |
| `qwen3-coder:30b` | 18 GB of weights against 16 GB of unified memory (both measured on this machine), and code-tuned rather than instruction-tuned. |
| any OpenAI / Anthropic / Google API model | same hard constraint |

The first row is a real limitation and is not dressed up as a design choice: the
three strongest models in the local registry are untestable here, so **this bench
cannot say whether a frontier model would solve the problem** — only whether a
*deployable* one does. Stated again in §12.2.

---

## 3. The three test sets

All three are built by calling the **production** `build_segment_payload` and
`_call_ollama`; nothing is reimplemented. `facial_bench` Amendment A3 is the
precedent — benching a payload shape the pipeline does not emit invalidated a
completed sweep once already.

### 3.1 Why the real corpus could not be the primary test set

The 481 cached corpus segments contain **8 distinct channel configurations**, and
the comment channel is POSITIVE on all 12 videos. A bench run only on that corpus
would be measuring eight points of a 108-point input space, in a region where the
right answer barely varies.

### 3.2 The configuration grid — 108 probes (primary)

3 transcript × 3 vocal × 4 facial × 3 comment = **108 configurations, each
presented once**. `none detected` is a facial level, not a gap: it is the *only*
facial value in the entire cached corpus, so omitting it would exercise a
configuration the deployed system has never produced.

Every probe carries the **same** carrier text, the same timings and the same
prosody numbers. Only the four labels vary. That is the design, and it is what
makes the primary metric interpretable: any variation in a model's answer across
probes is variation caused by something that is not the channel labels.

Reference distribution: **6** full-agreement, **40** adjacent-only, **62** polar.

### 3.3 The incongruence suite — 36 probes

24 items where all four labels **agree** but the transcript carries sarcasm, faint
praise, a disclosed sponsorship or an approving sentence about a defect, plus 12
congruent controls. `ref_score` is 0.0 for all 36, so `rule_baseline` answers 0.0
for all 36 and **only a model that reads the text can score**.

This suite exists so the bench is not rigged. §3.2 can only ever show an LLM
failing to match a function; this is the one axis where an LLM can beat one.

### 3.4 The real corpus — 481 segments

All 481 cached `after_nodamp` segments, on the real payloads. Reported for
**external validity only**: its labels come from models measured at 48.9–78.7%, so
a controller disagreeing with them may be right, and no adoption decision rests on
it.

---

## 4. Fairness, enforced structurally rather than promised

Identical for every candidate: the deployed `_SYSTEM_PROMPT` (imported, not
pasted), the deployed payload builder, `format: "json"`, `temperature: 0`,
`seed: 42`, `num_ctx: 4096`, the same endpoint and timeout, and the deployed
`_coerce_result`. **The only thing that varies between candidates is the string in
`orchestrator.OLLAMA_MODEL`.**

No model gets a prompt adjusted to suit it. Per-candidate prompt engineering would
measure the author's effort per model, not the models.

Damping is disabled for the whole bench (`VOCAL_ONLY_CONFLICT_WEIGHT` and
`FACIAL_ONLY_CONFLICT_WEIGHT` set to 1.0, the identity). Damping is a post-hoc
correction applied *after* the controller answers; leaving it on would score each
model on a number the pipeline had already modified.

### 4.1 A confound found mid-run, and fixed in production

`PROTOCOL.md` Amendment A1 records this in full. In short: the deployed
`_call_ollama` did not set `num_ctx`, so Ollama sized each model's KV cache from
its **advertised maximum context** — which differs by a factor of four across the
candidate set (32,768 to 131,072, read from `ollama show`). Measured consequence:
`llama3.1:8b` reserved **23.06 GB** for a prompt of at most ~700 tokens, on a 16 GB
machine. Swap hit 6.4 GB of 7 GB and throughput collapsed.

That is not "identical conditions" — it is each model being handed a different
memory budget by an allocator heuristic keyed to a number irrelevant to the task.
The largest payload this pipeline has **ever** built, over all 481 cached segments,
is **154 tokens**.

The fix went into production, not into the bench, because the defect is a
production defect: `orchestrator.OLLAMA_NUM_CTX = 4096`, a 5.8× margin over the
largest observed prompt, so no prompt is truncated and no result can change. The
confounded runs were **deleted and re-run**, not kept and footnoted.

Two side effects worth recording. The incumbent got **faster**: median latency fell
from 3.40 s to 2.13 s per probe, a 37% reduction, purely from not reserving a
context it never uses. And `llama3.1:8b`'s resident footprint fell from 23.06 GB to
**5.26 GB**.

---

*(Results sections follow.)*

## 5. Bench A — the configuration grid, 108 probes

P1 (Matthews correlation between `score > 0` and `ref_any`) is the primary metric.
It was chosen for one property, fixed in advance: **a constant predictor scores
exactly 0.000 on it whatever the class balance**, so the metric cannot be won by
refusing to answer or by flagging everything. Both degenerate references are in
the table and both score 0.000, as they must.

| candidate | P1 (MCC) | P2 (ρ) | P3 (Jaccard) | polar detected | zero rate | false alarm on agreement | median latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rule_baseline` * | **1.000** | **1.000** | 1.000 | 62/62 | 5.6% | 0/6 | 0.0 s |
| `llama3.1_8b` | **0.561** | 0.630 | 0.556 | 62/62 | 15.7% | 0/6 | 4.8 s |
| `qwen2.5_7b` | 0.524 | 0.481 | 0.517 | 62/62 | 4.6% | 3/6 | 4.2 s |
| `mistral_7b` | 0.451 | 0.566 | 0.580 | 62/62 | 2.8% | 4/6 | 5.7 s |
| `granite3.3_8b` | 0.407 | 0.477 | 0.664 | 62/62 | 12.0% | 2/6 | 6.7 s |
| `qwen3_8b` | 0.366 | 0.300 | 0.484 | 46/62 | 30.6% | 0/6 | 45.5 s |
| `phi4_mini` | 0.336 | 0.724 | 0.490 | 59/62 | 34.3% | 0/6 | 2.3 s |
| **`llama3.2` (incumbent)** | **0.073** | 0.259 | 0.468 | **8/62** | **91.7%** | 0/6 | 2.1 s |
| `gemma3_4b` | 0.000 | 0.573 | 0.853 | 62/62 | 0.0% | 6/6 | 4.1 s |
| `always_zero` * | 0.000 | 0.000 | 0.000 | 0/62 | 100.0% | 0/6 | — |
| `always_flag` * | 0.000 | 0.000 | 0.000 | 62/62 | 0.0% | 6/6 | — |

\* reference, not a competitor. `rule_baseline`'s 1.000 is **by construction**
(§2.2) and is not a result.

Seven of the eight candidates parsed **100%** of their responses. `qwen3_8b`
parsed **75.9%** (26 unparseable of 108) — the only G1 failure, and it also fails
G4 at 45.5 s per successful call (59.7 s including the failures) against a 6.39 s
gate. Its row is reported because a candidate excluded *with* numbers is stronger
evidence than one excluded with an apology; it is absent from Bench C only
(Amendment A3).

### 5.1 The incumbent is the outlier, and it is not close

`llama3.2` detects **8 of 62** polar configurations (12.9%, 95% Wilson
**6.7%–23.4%**). Six of the seven other LLMs detect **62 of 62** (100%,
94.2%–100.0%); `phi4_mini` detects 59.

Exact McNemar against the incumbent over the 108 paired probes, two-sided, with
the direction checked separately:

| challenger | wins | losses | p | verdict |
|---|---:|---:|---|---|
| `llama3.1_8b` | 82 | 0 | < 0.0001 | significantly **better** |
| `qwen2.5_7b` | 91 | 3 | < 0.0001 | significantly **better** |
| `mistral_7b` | 92 | 4 | < 0.0001 | significantly **better** |
| `granite3.3_8b` | 84 | 2 | < 0.0001 | significantly **better** |
| `phi4_mini` | 62 | 0 | < 0.0001 | significantly **better** |
| `gemma3_4b` | 93 | 6 | < 0.0001 | *better on the test, MCC 0.000 — see §5.4* |

So the answer to the question this bench exists for is unambiguous.
**The 98.3% no-conflict rate is a property of `llama3.2`, not of the data.** Given
byte-identical payloads and the byte-identical deployed prompt, five other
locally-runnable models find every polar disagreement the incumbent misses.

### 5.2 What the incumbent is actually doing

Mean conflict score by the value of each channel. A controller performing the
specified task should be roughly **symmetric** — what matters is whether the
labels agree, not which channel happens to hold the odd one out. `rule_baseline`
is symmetric by construction (0.38–0.47 across all twelve cells).

| candidate | transcript P/N/Neg | vocal P/N/Neg | facial P/N/Neg | comment P/N/Neg |
|---|---|---|---|---|
| `rule_baseline` | 0.47 / 0.38 / 0.47 | 0.47 / 0.38 / 0.47 | 0.47 / 0.39 / 0.47 | 0.47 / 0.38 / 0.47 |
| `llama3.1_8b` | 0.49 / 0.49 / 0.49 | 0.47 / 0.45 / 0.53 | 0.49 / 0.40 / 0.60 | 0.47 / 0.46 / 0.54 |
| `mistral_7b` | 0.44 / 0.44 / 0.55 | 0.46 / 0.44 / 0.53 | 0.43 / 0.39 / 0.59 | 0.42 / 0.39 / 0.62 |
| **`llama3.2`** | 0.14 / 0.04 / 0.00 | 0.10 / 0.06 / 0.02 | 0.02 / 0.06 / 0.03 | **0.00 / 0.00 / 0.18** |

Every other model sits in a 0.35–0.75 band across all four channels. The incumbent
sits at 0.00–0.18, and **its only non-trivial cell is a NEGATIVE comment channel**.

Checked directly rather than inferred from the means: **all 9** of the incumbent's
non-zero answers on the grid have `video_comment_sentiment == NEGATIVE`. Zero of
its non-zero answers have a POSITIVE or NEUTRAL comment channel.

> `llama3.2` has collapsed a four-way comparison into reading one field. It is not
> under-detecting conflict; it is detecting **negative audience sentiment** and
> calling that the conflict score.

That also explains the corpus behaviour exactly. The comment channel is POSITIVE on
all 12 corpus videos, so on real data the mechanism the incumbent actually uses is
switched off almost everywhere — which is why 473 of 481 segments score 0.0.

### 5.3 The defence that the data is quiet does not survive

The strongest counter-argument is that the incumbent is right to discount those
disagreements, because the channels producing them are unreliable. It fails on
measurement. Decomposing all 81 polar corpus segments by which pair of channels
sits at opposite poles:

| polar pair | measured held-out accuracy of each side | segments |
|---|---|---:|
| transcript **vs** comment | 67.8% **vs** 78.7% | **78** |
| transcript **vs** vocal | 67.8% vs 48.9% | 21 |
| comment **vs** vocal | 78.7% vs 48.9% | 3 |

**78 of the 81** rest on the transcript-versus-comment pair — the system's two
*most* accurate channels, and the two the prompt does not down-weight. The weak
vocal channel is not what is generating these disagreements.

### 5.4 Two results that only the degenerate references make legible

**`gemma3_4b` never returns zero.** Zero rate 0.0%, false alarms 6/6 on
full-agreement probes: it answers "there is a conflict" to every one of the 108
probes. Its MCC is therefore exactly **0.000** — identical to `always_flag`, which
is what it is behaviourally. Without a constant baseline in the table it would have
appeared as a 62/62 polar detector and looked excellent.

**A trap in the significance test itself.** `always_flag` *passes* an exact McNemar
against the incumbent (93 wins, 6 losses, p < 0.0001) because it agrees with
`ref_any` on 102 of 108 probes purely by never abstaining — while scoring MCC
0.000. The adoption rule (§8) reads "beats the incumbent on **P1**, with an exact
McNemar ... in the challenger's favour", which is a conjunction; the
implementation checked only the second half until this table exposed it. Corrected,
and covered by two tests. Reported here rather than silently fixed, because a bench
whose own decision procedure had a hole is worth knowing about.

### 5.5 The quantisation question, answered

The project's work plan asked whether the conflict score's
coarseness is inherent to the design or an artefact of one model. Distinct values
emitted across 108 probes:

| model | distinct values |
|---|---|
| `llama3.2` | 4 — {0.0, 0.5, 0.75, 0.8} |
| `llama3.1_8b` | 5 — {0.0, 0.5, 0.6, 0.75, 0.8} |
| `qwen2.5_7b` | 4 — {0.0, 0.3333, 0.5, 0.6667} |

**Both.** Every controller quantises to a handful of values rather than reasoning
on a smooth scale — so the coarseness is inherent to asking an LLM for a float —
but *which* values differ by family: the Llama models land on quarters and fifths,
Qwen on thirds. The system's numeric output is therefore partly an artefact of the
model's preferred fractions, which is not a property a score used for ranking
should have.

### 5.6 Robustness — does the headline survive the reporting choices?

Three ways the ranking could be an artefact of how it is reported rather than a
property of the models. All three are recomputations over the same cached
responses; none required further inference.

| candidate | P2 at w=0.25 | **P2 at w=0.50** | P2 at w=0.75 | P1 at >0 | P1 at >0.25 | P1 at >0.5 | polar reaching the flag threshold |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rule_baseline` * | 0.945 | 1.000 | 0.896 | 1.000 | 0.480 | 0.193 | 0/62 |
| `llama3.1_8b` | 0.623 | 0.630 | 0.628 | **0.561** | **0.561** | 0.271 | 6/62 |
| `qwen2.5_7b` | 0.481 | 0.481 | 0.501 | 0.524 | 0.524 | 0.234 | 0/62 |
| `mistral_7b` | 0.568 | 0.566 | 0.503 | 0.451 | 0.354 | 0.149 | 4/62 |
| `granite3.3_8b` | 0.538 | 0.477 | 0.345 | 0.407 | 0.407 | 0.279 | 34/62 |
| `qwen3_8b` | 0.215 | 0.300 | 0.365 | 0.366 | 0.350 | 0.201 | 23/62 |
| `phi4_mini` | 0.671 | 0.724 | 0.722 | 0.336 | 0.336 | 0.271 | 54/62 |
| **`llama3.2`** | 0.267 | 0.259 | 0.172 | **0.073** | **0.073** | 0.069 | 7/62 |
| `gemma3_4b` | 0.564 | 0.573 | 0.528 | 0.000 | 0.218 | 0.123 | 0/62 |
| `always_zero` * | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0/62 |
| `always_flag` * | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 62/62 |

**The free parameter does not drive P2.** `reference.ADJACENT_WEIGHT` = 0.5 was
declared before any run but is still a choice. Varying it over 0.25 / 0.50 / 0.75
moves individual rows by at most a few hundredths and **does not reorder the top
of the table**: `llama3.1_8b` leads the LLMs at every setting on P1, and
`phi4_mini`'s high P2 (it orders well while detecting poorly) is stable too.

**The incumbent's result is not an artefact of the detection threshold.** P1
binarises at `score > 0`, which is generous — a model answering 0.05 to everything
would score well on it. Recomputing at 0.25 and 0.5 changes nothing that matters:
`llama3.2` stays at 0.073 / 0.073 / 0.069 and remains last among LLMs except
`gemma3_4b`. Two rows do move, and both move *down*: `mistral_7b` 0.451 → 0.354
and `rule_baseline` 1.000 → 0.480 → 0.193, the latter simply because the reference
rarely exceeds 0.5 at four channels — which is §6 seen from another angle.

**The operational column is the one that does not track P1, and it is the most
uncomfortable number in this bench.** At `CONFLICT_FLAG_THRESHOLD`, the thing the
pipeline actually acts on:

- `phi4_mini` flags **54/62** and `granite3.3_8b` **34/62** — both far below
  `llama3.1_8b` on P1, both far above it operationally;
- `llama3.1_8b` flags **6/62** and the incumbent **7/62** — *the adopted model
  flags fewer polar conflicts than the model it replaces*;
- `qwen2.5_7b` and `gemma3_4b` flag **0/62**, as does `rule_baseline`.

So a controller can be much better at *recognising* disagreement and no better at
*acting* on it, because the scale and the threshold are misaligned (§6). This is
recorded here rather than buried: it is the strongest evidence that the flag
threshold, not the model, is the binding constraint on this system, and it is why
§13 puts fixing the scale above the model choice.

---

## 6. The finding that reframes everything: the flag threshold may be unreachable

This was not a planned analysis. It fell out of the grid: **`rule_baseline` —
a perfect implementation of the task the system prompt specifies — flags 0 of 62
polar configurations** at `CONFLICT_FLAG_THRESHOLD = 0.75`.

The prompt fixes only the two endpoints (*"0.0 (full agreement) to 1.0 (all
channels disagree)"*) and says nothing about the middle, so a controller must pick
a reading. Maximum attainable score under four readings a competent reader might
pick, computed in closed form over all 3ⁿ valence assignments:

| reading of the scale | n=2 | n=3 | **n=4** |
|---|---|---|---|
| pairwise (this bench, pre-registered) | 1.000 | 0.667 ✗ | **0.667 ✗** |
| pairwise, unweighted | 1.000 | 1.000 | 0.833 ✓ |
| distinct valences, normalised | 1.000 | 1.000 | **0.667 ✗** |
| fraction dissenting from the mode | 0.500 ✗ | 0.667 ✗ | **0.500 ✗** |

✗ = the 0.75 threshold is **mathematically unattainable** at that channel count.

**Three of the four readings put the threshold out of reach for a four-channel
segment.** The finding is definition-dependent and is reported as such — one
reading does reach it.

One part is **not** definition-dependent. The prompt calls 1.0 "all channels
disagree". With four channels drawn from three valence levels, by pigeonhole at
least two must share a valence, so *no* formula can place a four-channel segment at
the top of the scale. The scale's stated maximum is unattainable by construction.

**What follows, if the pre-registered reading is right.** A controller that
correctly implements the specified task would flag **nothing**, on any segment,
ever. The flag drives the double-weighting in `compute_authenticity_score` and the
entire `POTENTIAL_PAID_PROMOTION` product story. So every flag this system has ever
raised came from a controller *not* following its own specification — the
incumbent's 0.75 and 0.8 answers do not follow from the pair arithmetic under any
of the four readings.

This is a **design defect in the specification, not in any model**, and no choice
of controller fixes it. Stated as a measured, definition-dependent result and left
for a decision rather than patched here: changing `CONFLICT_FLAG_THRESHOLD` alters
every score the system has ever reported, and that is not a bench's side effect to
take.

---

## 7. Bench B — the incongruence suite (Q4 underpowered; reported as a capability probe)

All four channel labels **agree** in every one of these 36 probes, so `ref_score`
is 0.0 throughout and `rule_baseline` answers 0.0 throughout. Only a model that
reads the transcript can score. P5 = incongruent hit rate **minus** control false
alarm rate.

**Q4 is declared underpowered and no claim is made either way.** PROTOCOL §2 fixed
a floor of 20 sound items before collection; measured against the pipeline's own
classifier, **19 of 24** hold up (Amendment A2). The floor binds by one item. What
follows is descriptive evidence, not an answer to Q4.

| candidate | hits (of 24) | false alarms (of 12) | **P5** | P5 on the 19 sound items |
|---|---:|---:|---:|---:|
| `mistral_7b` | **19** (79.2%) | 4 | **0.458** | 0.456 |
| `granite3.3_8b` | 1 | 0 | 0.042 | 0.000 |
| `qwen3_8b` | 0 | 0 | 0.000 | 0.000 |
| `llama3.2` | 0 | 0 | 0.000 | 0.000 |
| `llama3.1_8b` | **0** | 0 | 0.000 | 0.000 |
| `phi4_mini` | 0 | 0 | 0.000 | 0.000 |
| `gemma3_4b` | 24 (100%) | **12** | 0.000 | 0.000 |
| `qwen2.5_7b` | 3 | 3 | **-0.125** | -0.250 |
| `rule_baseline` * | 0 | 0 | 0.000 | 0.000 |

### 7.1 The two benches disagree about who wins, and that is the point

**The best label-comparer is the worst sarcasm-reader.** `llama3.1_8b` tops Bench A
at P1 0.561 and detects **0 of 24** incongruent transcripts. `mistral_7b` is third
on Bench A at 0.451 and detects **19 of 24**, including every disclosed-sponsorship
item.

A bench built only on the configuration grid would have named `llama3.1_8b` the
winner without noticing it is blind to the one capability a rule baseline
structurally cannot have. That is precisely why §3.3 exists, and it is the clearest
evidence that including it was not decoration.

### 7.2 The 12 controls earned their place

`gemma3_4b` scores **24 of 24** on the incongruent items — a perfect hit rate — and
**12 of 12** on the controls. P5 = 0.000. It is not reading sarcasm; it is
answering "conflict" to everything, exactly as Bench A showed. Reported without the
controls, it would have been the headline result of this section.

### 7.3 The flag vocabulary fires once, in the wrong field

> **Corrected 06 Sep 2026.** An earlier draft of this section, written before
> `qwen3_8b` finished, said no model emitted a flag on any of the 36 probes. That
> was true of the seven models then measured and is **false** of the eight. The
> corrected finding below is more interesting than the original claim, which is
> the usual reason to be glad a slow candidate was not dropped.

Seven of the eight models emitted **no flag on any of the 36 probes** — not even
on the item that opens *"Full disclosure, the brand paid for this trip and sent me
the unit for free. Anyway, it's incredible."*

`qwen3_8b` is the exception, and it is instructive. It emitted flags on **9 of the
36** probes, using the system prompt's own vocabulary correctly:
**`SARCASM_DETECTED` ×6** and **`POTENTIAL_PAID_PROMOTION` ×3**, 8 of them on
incongruent items and 1 on a control.

**And on all 9 it scored `conflict_score` 0.0.**

So the one model that recognised the sarcasm reported it in a field the pipeline
does not act on, while telling the scorer there was no conflict. That is exactly
the score/attribution decoupling `vocal_bench/CORPUS_AB_RESULT.md` §3.2 measured in
`llama3.2` — which named channels in conflict on 265 of 481 responses and scored
257 of those at 0.0 — appearing again in a different model and a different field.

The operational conclusion is unchanged and is arguably worse than "the vocabulary
is dead": across 481 real segments and 36 constructed probes,
`POTENTIAL_PAID_PROMOTION` and `SARCASM_DETECTED` have driven **zero** downstream
behaviour, because nothing in `_coerce_result` or `scorer` reads `flags` — it
reads `conflict_score`. The capability exists in at least one deployable model and
the pipeline throws it away.


---

## 8. Q2 — is it the model, or is it the prompt?

A model that is fixed by editing its instructions was never the problem. The
deployed prompt has one property that made this a live hypothesis: its
`CHANNEL RELIABILITY` paragraph spends its length telling the controller when
*not* to raise a score and never once says what a high score is *for*.

So a revised prompt was written **before the ablation ran** and fixed. It keeps
every line of the deployed prompt — including the `CHANNEL RELIABILITY` paragraph,
which is the hypothesis under test and so must not be removed — and adds the
missing half: an explicit statement that a POSITIVE channel against a NEGATIVE one
is the strongest evidence the system can observe and must score 0.7 or above. It
is derived from the deployed prompt by insertion at a fixed marker, so the two
cannot silently drift, and the insertion asserts.

Run over the full 108-probe grid for the incumbent and the two best challengers
(chosen by measured P1 from the finished grid, not named in advance):

| model | prompt | P1 | P2 | polar detected | false alarm | zero rate | **polar reaching the flag threshold** |
|---|---|---:|---:|---:|---:|---:|---:|
| `llama3.2` | deployed | 0.073 | 0.259 | 8/62 | 0/6 | 91.7% | 7/62 |
| `llama3.2` | **revised** | **0.009** | 0.147 | **26/62** | 2/6 | 64.8% | **18/62** |
| `llama3.1_8b` | deployed | **0.561** | 0.630 | 62/62 | 0/6 | 15.7% | 6/62 |
| `llama3.1_8b` | **revised** | 0.400 | 0.644 | 61/62 | 0/6 | 26.9% | **61/62** |
| `qwen2.5_7b` | deployed | 0.524 | 0.481 | 62/62 | 3/6 | 4.6% | 0/62 |
| `qwen2.5_7b` | **revised** | 0.512 | 0.613 | 62/62 | 2/6 | 8.3% | 0/62 |

### 8.1 The answer is "both, and the model is the larger factor"

**The prompt is implicated.** On the revised prompt the incumbent's polar detection
rises from **8/62 to 26/62** and its zero rate falls from 91.7% to 64.8%. Some of
its silence was the instructions.

**But the revision does not rescue it, and P1 says the revision is worse.** Every
one of the three models loses P1 on the revised prompt. The incumbent on its best
prompt (0.073) is still an order of magnitude below `llama3.1_8b` on the deployed
one (0.561). **No prompt tested closes that gap**, so the model choice is the
larger factor, and the pre-registered primary metric does not support adopting the
revision.

### 8.2 The revision's real effect is operational, and it ties back to §6

P1 is not the whole story here and saying so is not special pleading — the
operational column is the one the product acts on, and it moves in the opposite
direction. `llama3.1_8b` goes from flagging **6 of 62** polar conflicts to
flagging **61 of 62**.

The mechanism is exactly the §6 defect. The revision instructs the model to score
a polar disagreement "0.7 or above" — a number that, under the pre-registered
reading of the prompt's own scale, **a correct implementation cannot produce** (the
maximum at four channels is 0.667). So the revision makes flagging work by telling
the controller to *abandon the scale definition*.

That is worth stating plainly, because it is the single most useful thing this
ablation found:

> The system's flag mechanism only functions when the controller ignores the
> specification. Fixing that is a threshold-and-scale decision, not a model choice
> and not a prompt tweak.

### 8.3 Why P1 fell for `llama3.1_8b` when its polar detection did not

Its polar detection is unchanged (62 → 61) and its false alarms stay at 0/6. What
moved is the **40 adjacent-only** configurations: the zero rate rose 15.7% → 26.9%,
so roughly a dozen NEUTRAL-versus-one-pole disagreements it previously scored above
zero it now scores at zero. The revision told it to reserve high scores for polar
cases and it also became stricter about mild ones. P2 actually *improved*
(0.630 → 0.644), which is consistent: its ordering got better while its binary
sensitivity to weak disagreements got worse.

---

## 9. Gates

| gate | requirement | outcome |
|---|---|---|
| **G1** parse rate | ≥ 95% valid JSON | **7 of 8 pass at 100%. `qwen3_8b` fails at 75.9%** — 26 of 108 responses unparseable *despite* `format: "json"` being enforced. |
| **G2** determinism | 20 probes reproduce exactly | **passed by all 7 measured: 20/20 score-identical AND 20/20 byte-identical.** Not run for `qwen3_8b`, already excluded on G1 and G4. |
| **G3** footprint | fits in 16 GB | passed by all after the `num_ctx` fix (§4.1); before it, `llama3.1:8b` did not. |
| **G4** latency | ≤ 3× the incumbent's 2.13 s, i.e. ≤ 6.39 s | **`granite3.3_8b` fails at 6.7 s. `qwen3_8b` fails at 45.5 s — 7.1× the gate, 21× the incumbent.** All others pass. |

`qwen3_8b` is the only candidate to fail two gates, and the parse failure is the
more interesting of the two. Ollama's `format: "json"` constrains generation, so a
75.9% parse rate is not a model that writes prose — it is a hybrid reasoning model
whose thinking output collides with the constraint often enough that a quarter of
its answers never reach the scorer. In production every one of those becomes
`_safe_fallback`: `conflict_score` 0.0, not flagged. A controller that silently
returns "no conflict" on a quarter of segments is worse than a slow one.

G2 deserves emphasis. `PROTOTYPE_FINDINGS.md` §5 records this project losing
10–20 points of Authenticity Score to controller non-determinism, and the fix
(`temperature: 0`, `seed: 42`) had never been verified across models. It now is,
on seven of them, at byte level.


---

## 10. Bench C — 481 real segments, and what each controller does to the reported score

The probe suite is synthetic. This is the external-validity check: the same
reference applied to the 481 cached corpus segments, on real Whisper text, real
prosody numbers and the pipeline's own channel labels.

**No adoption decision rests on this section** (PROTOCOL §4.2). Its labels come
from models measured at 48.9–78.7%, so a controller that disagrees with them may
be right about the world.

| candidate | P1 (MCC) | P2 (ρ) | polar detected | zero rate | flag rate |
|---|---:|---:|---:|---:|---:|
| `rule_baseline` * | 1.000 | 1.000 | 81/81 | 8.9% | 0.0% |
| **`llama3.1_8b`** | **0.882** | 0.582 | **81/81** | 10.2% | 2.3% |
| `phi4_mini` | 0.226 | 0.655 | 81/81 | 65.7% | 21.8% |
| `granite3.3_8b` | 0.146 | 0.691 | 81/81 | 0.2% | 25.2% |
| **`llama3.2`** | 0.048 | 0.288 | **11/81** | **97.7%** | 1.9% |
| `qwen2.5_7b` | 0.000 | 0.773 | 81/81 | 0.0% | 0.6% |
| `mistral_7b` | 0.000 | 0.607 | 81/81 | 0.0% | 0.6% |
| `gemma3_4b` | 0.000 | 0.735 | 81/81 | 0.0% | 0.0% |
| `always_zero` * | 0.000 | 0.000 | 0/81 | 100.0% | 0.0% |
| `always_flag` * | 0.000 | 0.000 | 81/81 | 0.0% | 100.0% |

(`qwen3_8b` is absent: excluded from this stage on its measured gate failures,
Amendment A3.)

**The grid result reproduces on real data.** `llama3.1_8b` finds **81 of 81**
polar disagreements; the incumbent finds **11 of 81** and answers 0.0 on 97.7% of
segments. The incumbent's figure here (11/81) is close to the 8/81 from the
pre-existing `vocal_bench` cache quoted in §0 — the two runs differ only in the
`num_ctx` fix, and the agreement is a useful consistency check on both.

**Three models collapse to MCC 0.000 on real data**, and all three for the same
reason: a 0.0% zero rate. `qwen2.5_7b`, `mistral_7b` and `gemma3_4b` each answer
"there is a conflict" on every one of the 481 real segments, which makes them
constant predictors however well they scored on the synthetic grid. This is the
single most valuable thing Bench C contributed: **the grid could not distinguish a
model that discriminates from a model that never abstains**, because the grid's own
class balance (102 of 108 configurations disagree somewhere) rewards both. Real
segments are 91.1% disagreeing and expose it.

Only `llama3.1_8b` retains a high MCC on real data (0.882), and it does so by
keeping a 10.2% zero rate that closely tracks `rule_baseline`'s 8.9%.

### 10.1 Rule 7 — the controller choice dominates the reported score

`scorer.build_final_report` run over each controller's answers, per video, mean
across the 12 corpus videos. Every input except the controller is byte-identical.

| controller | Authenticity | Brand Health | segments flagged |
|---|---:|---:|---:|
| `always_zero` * | 100.00 | 98.30 | 0/481 |
| **`llama3.2` (before)** | **96.87** | **97.05** | 9/481 |
| `phi4_mini` | 68.49 | 85.69 | 105/481 |
| `rule_baseline` * | 64.05 | 83.92 | 0/481 |
| `gemma3_4b` | 62.45 | 83.28 | 0/481 |
| `mistral_7b` | 55.96 | 80.69 | 3/481 |
| **`llama3.1_8b` (after)** | **47.79** | **77.42** | 11/481 |
| `qwen2.5_7b` | 47.37 | 77.25 | 3/481 |
| `granite3.3_8b` | 34.62 | 72.15 | 121/481 |
| `always_flag` * | 0.00 | 58.30 | 481/481 |

**Swapping the controller — and nothing else — moves the mean Authenticity Score
by 49.08 points and Brand Health by 19.63.** The channel inputs are identical
across every row.

Across the seven *real, deployable* controllers the spread is wider still:
**34.62 to 96.87 on Authenticity, a range of 62.25 points**, and 72.15 to 97.05 on
Brand Health. The same twelve videos, the same four channels, the same prompt —
and a verdict that moves from "almost entirely authentic" to "barely a third
authentic" depending on which local LLM happens to be installed.

The project's work plan asked:

> is the system's output a property of the *architecture*, or an artefact of one
> arbitrary model choice?

**Measured answer: overwhelmingly an artefact of the model choice.** The headline
number this system reports is more sensitive to which local LLM happens to be
installed than to anything the four analysis channels observed. That is the most
important single result in this bench, and it generalises beyond this project: an
LLM-orchestration architecture inherits the arbitrariness of its orchestrator, and
a system that never benched its controller cannot know how much of its output is
that arbitrariness.

Note also where `always_zero` sits. The incumbent's 96.87 is **3.13 points** from
the score produced by a controller that does nothing at all. Whatever the true
authenticity of these 12 videos, a system that reports near-identical numbers to a
constant is not measuring it.

### 10.2 The controllers are reading the transcript, not only the labels

The corpus has only 8 distinct channel configurations across 481 segments, so most
recur many times with *different* transcript text. At `temperature: 0` with a
fixed seed, a controller comparing four labels should answer identically within a
configuration.

| candidate | configurations split | segments on a minority answer |
|---|---:|---:|
| `rule_baseline` * | 0 of 8 | 0/481 (0.0%) |
| `llama3.2` | 2 of 8 | 11/481 (2.3%) |
| `llama3.1_8b` | 6 of 8 | 56/481 (11.6%) |
| `qwen2.5_7b` | 5 of 8 | 81/481 (16.8%) |

(Other candidates omitted; the four shown span the range.)

This is a diagnostic, not a fault. Reading the transcript may be exactly the right
thing to do — §7 is about a capability that requires it. What it establishes is
that the conflict score is **not a function of the four channel labels**, which is
what the system prompt describes it as. A user told "these four channels disagree"
is being given a number that also depends on wording the four channels never saw.

---

## 11. The decision

The rule was fixed in `PROTOCOL.md` §8 before any candidate ran: replace the
incumbent only if a candidate passes every gate, beats it on **P1** with an exact
McNemar test in its favour, does not regress P2 by more than 0.05, and does not
regress P5.

| candidate | G1 parse | G4 latency | C2 beats P1 | C3 no P2 loss | C4 no P5 loss | McNemar p | verdict |
|---|:-:|:-:|:-:|:-:|:-:|---|---|
| **`llama3.1_8b`** | ok | ok | ok | ok | ok | < 0.0001 | **QUALIFIES** |
| `mistral_7b` | ok | ok | ok | ok | ok | < 0.0001 | QUALIFIES |
| `phi4_mini` | ok | ok | ok | ok | ok | < 0.0001 | QUALIFIES |
| `qwen2.5_7b` | ok | ok | ok | ok | **no** | < 0.0001 | — (P5 −0.125) |
| `granite3.3_8b` | ok | **no** | ok | ok | ok | < 0.0001 | — (6.7 s > 6.39 s gate) |
| `qwen3_8b` | **no** | **no** | ok | ok | ok | < 0.0001 | — (75.9% parse, 45.5 s) |
| `gemma3_4b` | ok | ok | **no** | ok | ok | < 0.0001 | — (MCC 0.000) |

Three of the eight qualify. The tie-break is highest P1.

> ### Winner: `llama3.1:8b`, and it is adopted.
> `orchestrator.OLLAMA_MODEL` now defaults to `llama3.1:8b`, overridable by
> environment variable so reverting is a config change rather than an edit.

### 11.1 Where the winner loses, stated because it does

- **It is blind to sarcasm.** 0 of 24 incongruent transcripts (§7). It satisfies
  C4 only because the incumbent also scores 0.000 — this is a non-regression, not
  a strength. `mistral_7b` catches 19 of 24 and is the better model on that axis
  by a wide margin.
- **It is 2.3× slower.** 4.8 s against 2.1 s per segment. A 1,863-segment corpus
  run goes from roughly 1 hour to roughly 2.5.
- **It hallucinates channels.** 16 named-channel errors on the grid, the highest of
  any candidate; `mistral_7b` and `granite3.3_8b` each had 0.
- **It is still far below a six-line function.** P1 0.561 against `rule_baseline`'s
  1.000 on the specified task.

### 11.2 The case that was rejected — and why the real corpus settled it

> **Revised 06 Sep 2026, when the corpus stage finished.** An earlier draft of
> this section argued that `mistral_7b` had the stronger claim on the merits and
> lost only on a pre-registered technicality. **Bench C shows that argument was
> wrong**, and the revision is recorded rather than the original quietly replaced.

On the two synthetic benches `mistral_7b` looked like the moral winner. It is the
only model that reads sarcasm — P5 **0.458** against the adopted model's 0.000,
catching 19 of 24 sarcastic transcripts including every disclosed-sponsorship
item — and it was only 0.110 behind on P1. The argument was that this capability
matters more to the product than the primary metric does, and that the rule was
being followed against the evidence.

**On real segments that argument collapses.** `mistral_7b` scores MCC **0.000** on
the 481 corpus segments, with a **0.0% zero rate**: it answers "there is a
conflict" on every single real segment it sees. So does `qwen2.5_7b`, and so does
`gemma3_4b`. Their sarcasm detection is not discrimination — it is a model that
says yes to everything, and the incongruence suite's 12 controls caught that for
`gemma3_4b` but not for `mistral_7b`, whose 4/12 false-alarm rate looked survivable
on 12 items and does not survive 481.

So the pre-registered rule and the evidence agree after all, and it took the stage
that *no decision depended on* to show it. Two lessons worth carrying:

- **The synthetic grid could not distinguish "discriminates" from "never
  abstains."** Its class balance (102 of 108 configurations disagree somewhere)
  rewards both, and only real data with a different balance separates them.
- **A 12-item control set is too small a specificity check.** It caught the model
  that flagged 12 of 12 and missed the one that flagged 4 of 12. If this suite is
  reused, the controls need to outnumber the positives, not the reverse.

`mistral_7b` remains the only candidate with a demonstrated sarcasm capability and
that is still worth something — but as a *second-pass* component on segments
already selected by a discriminating controller, not as the controller.


## 12. Stepping back: what this bench could still be wrong about

Written as a deliberate attempt to break the result rather than to defend it.
Where a threat could be closed cheaply it was closed and the closure is measured;
where it could not, it is left open and named.

### 12.1 Threats that were closed, and how

| threat | how it was closed |
|---|---|
| **The reference could be circular** — ground truth derived from a model under test | It is derived from the controller's *inputs*, which no controller influences. `rule_baseline`'s perfect P1/P2 is declared in advance as an artefact, not reported as a win. |
| **The corpus could be unrepresentative** — 8 of 108 configurations | The primary test set is the full 108-configuration grid; the corpus is demoted to an external-validity check (§3.1, §7). |
| **The suite could be rigged against the LLM** — a label-only reference can only ever favour a label-only rule | The incongruence suite (§5) is the opposite: `rule_baseline` is structurally incapable of scoring above 0.0 on it. |
| **The incongruence labels could be unrealistic** | Measured against the pipeline's own classifier, not assumed. 31/36 match; the 5 that do not are excluded from the restricted reading and the pre-registered floor is honoured (Amendment A2). |
| **The failure could be the prompt, not the model** | Directly tested by the prompt ablation (§6). |
| **Candidates could have been given unequal compute** | Found true, mid-run, and fixed in production; confounded runs deleted and re-run (Amendment A1). |
| **The free parameter in `ref_score` could be driving P2** | Varied over 0.25 / 0.50 / 0.75 (§8.1). |
| **"Any non-zero score" could be too generous a detection rule** | P1 recomputed at three thresholds, and detection reported at the operational flag threshold too (§8.2). |
| **A model could win by flagging everything** | `always_flag` is in the table and MCC scores it exactly 0.0. |
| **A single lucky run** | Determinism gate G2: every candidate re-run on 20 probes and compared call for call. |
| **Licence and size claims from memory** | Read from each model's own manifest via `ollama show` (`cache/registry.json`). |

### 12.2 Threats that remain open, and are not dressed up

1. **The frontier is untestable here.** The three strongest models in the local
   registry (`gpt-oss:20b`, `deepseek-v3.1:671b`, `qwen3-coder:480b`) proxy to
   `ollama.com` and are excluded by a hard project constraint. This bench cannot
   say whether a frontier model would solve the problem — only whether a
   **deployable** one does. That is the right question for this product, and it is
   still a narrower question than "which controller is best".

2. **The reference is a specification, not truth.** P1–P4 measure whether a
   controller does the job the system prompt defines. Whether that job detects
   real inauthenticity is a different question, and answering it needs
   hand-labelled *segments* — a human deciding, for a given segment, whether the
   creator was being straight. That is the natural successor to this bench and it
   is not attempted here.

3. **The incongruence suite is author-written and synthetic.** Ground truth is by
   construction. All 24 items are published verbatim in §5.3 so any of them can be
   disputed individually, and Q4 is declared underpowered under its own
   pre-registered floor. It shows a capability exists or does not; it cannot show
   how often the capability matters on real footage.

4. **One machine, one Ollama build (0.33.2), one quantisation family.** Every
   candidate is Q4_K_M, which is how they would actually be deployed here, but a
   model that quantises badly is being judged partly on its quantisation. No
   full-precision comparison was run.

5. **The corpus comment channel is POSITIVE on all 12 videos.** The real-segment
   check therefore cannot exercise a negative audience at all. The grid can, and
   does — which is exactly how the incumbent's single-channel dependence became
   visible.

6. **Narrative quality is not assessed.** Only the *consistency* between a model's
   narrative-level attribution and its own score. Rating prose needs raters this
   bench does not have, and §10 of the protocol declared it out of scope in
   advance.

7. **One prompt revision, not a prompt search.** The ablation tests one
   hypothesis — that the deployed prompt never says what a high score is *for* —
   with one revision written before it ran. A different revision might do better
   or worse. This is a controlled test of a hypothesis, not an optimisation.

8. **Coverage of the corpus stage is partial and is stated rather than implied.**
   `qwen3_8b` is excluded from it entirely on a measured gate failure (Amendment
   A3), and the four breadth candidates were still running when this was written.
   Only candidates whose 481-segment run **completed** are quoted in §10;
   `verify_claims.py` enforces that, skipping incomplete runs and failing if one
   is cited. No conclusion in §11 depends on the corpus stage.

---

## 13. Recommendation

**Adopt `llama3.1:8b` as the controller.** Done — `orchestrator.OLLAMA_MODEL`.
It is the pre-registered winner: it passes every gate, it beats the incumbent on
the primary metric with p < 0.0001 in its favour, and the margin is not marginal —
62/62 against 8/62 on the grid, 81/81 against 11/81 on real segments.

**Three things matter more than that recommendation, and all three are open.**

1. **Fix the scale, then the threshold.** §6: under three of four valid readings
   of the prompt's own scale, `CONFLICT_FLAG_THRESHOLD = 0.75` is unattainable at
   four channels, and the prompt's stated maximum ("all channels disagree") is
   unattainable by pigeonhole under *any* reading. The flag drives the
   double-weighting in the Authenticity Score and the entire paid-promotion story.
   No choice of controller fixes this. It needs a decision about what the scale
   means and where the threshold sits — and that decision changes every number the
   system has ever reported, which is why this bench measured it and stopped.

2. **The controller choice dominates the output.** §10.1: 49.08 points of
   Authenticity Score, on byte-identical channel inputs. Any claim this system
   makes about a video is, to a first approximation, a claim about which local LLM
   was installed. That is the finding to write up, and it generalises past this
   project.

3. **Sarcasm detection exists, in the wrong model and the wrong field.**
   `mistral_7b` catches 19 of 24 constructed sarcasm cases and the adopted
   controller catches 0 — but `mistral_7b` cannot be the controller, because it
   flags every one of the 481 real segments (§11.2). `qwen3_8b` emitted
   `SARCASM_DETECTED` ×6 and `POTENTIAL_PAID_PROMOTION` ×3 on the incongruence
   suite, correctly, **while scoring `conflict_score` 0.0 on all nine** — and
   nothing in `_coerce_result` or `scorer` reads `flags`. Separately the
   *transcript* channel already catches 5 of the 24 before the controller sees
   them (Amendment A2). So the capability is present in at least two models and in
   one existing channel, and the pipeline acts on none of it. That is a plumbing
   problem, not a model-selection problem, and it is cheap to fix.

**What would settle what this bench cannot.** The reference here is a
specification, not truth (§12.2). The natural successor is a set of hand-labelled
*segments* — a human deciding, for each, whether the creator was being straight —
scored the way `facial_bench/v2` scored frames. That would convert every P1 in
this document from "does the controller follow its instructions" into "does the
controller detect inauthenticity", which is the question the project actually
asks. It is a day of labelling and it is the highest-value follow-up here.

---

## Appendix A — the incongruence suite, published in full

Ground truth here is **by construction**: an item is positive because it was
written to contain an incongruence, the way a unit test's expected value is what
the author wrote. Every item is printed so any of them can be disputed
individually. The last two columns are the measurement from Amendment A2 — the
label the pipeline's **own** transcript classifier assigns, and whether that
matches the label the item was built with. 19 of 24 match, one short of the
pre-registered floor of 20, which is why Q4 is reported as underpowered.

| # | text | why it is incongruent | pipeline's own transcript label | sound |
|---:|---|---|---|:-:|
| 1 | "Oh, fantastic, they removed the charger from the box. Really generous of them." | sarcasm: praise for a removal the speaker resents | POSITIVE (0.80) | yes |
| 2 | "It only overheats when you actually use it, so that's basically never a problem." | approving sentence describing a defect | NEUTRAL (0.53) | **no** |
| 3 | "Full disclosure, the brand paid for this trip and sent me the unit for free. Anyway, it's incredible." | disclosed sponsorship immediately followed by unqualified praise | POSITIVE (0.86) | yes |
| 4 | "I mean, it's fine. It's fine. Everything about it is fine, I guess." | faint praise by repetition; enthusiasm absent | POSITIVE (0.72) | yes |
| 5 | "Battery life is amazing, if you don't mind charging it twice a day." | superlative undercut by the conditional that follows | POSITIVE (0.78) | yes |
| 6 | "This is easily the best phone I have ever had to send back twice." | superlative whose object is a repeated failure | POSITIVE (0.87) | yes |
| 7 | "They finally fixed the thing they broke last year, so well done to them." | praise for the repair of a self-inflicted problem | POSITIVE (0.75) | yes |
| 8 | "Love the new design. Love that it costs four hundred more. Love everything about it." | sarcasm by anaphora on a price increase | POSITIVE (0.91) | yes |
| 9 | "Look, I'm contractually obliged to say I enjoyed it, and I did enjoy it." | praise explicitly framed as compelled | POSITIVE (0.87) | yes |
| 10 | "The camera is great. Not as great as the one it replaced, but great." | praise retracted mid-sentence and then restated | POSITIVE (0.90) | yes |
| 11 | "Honestly it's a great little device for the money, assuming you already own the ecosystem, a case, the adapter, and a lot of patience." | praise conditioned into meaninglessness | POSITIVE (0.82) | yes |
| 12 | "Everyone in the comments said it was terrible, and they're right, but I still love it." | endorsement of a criticism the speaker then ignores | NEGATIVE (0.55) | **no** |
| 13 | "I'm being told through my earpiece that I love this product." | explicit attribution of the opinion to someone else | POSITIVE (0.87) | yes |
| 14 | "What a beautifully engineered way to lose all your data." | aesthetic praise attached to a catastrophic outcome | POSITIVE (0.49) | yes |
| 15 | "Nothing wrong with it at all, and I've only mentioned three things wrong with it." | self-contradiction within one sentence | NEGATIVE (0.47) | **no** |
| 16 | "It's genuinely impressive how confidently they shipped this unfinished." | admiration directed at the shipping of a defect | POSITIVE (0.84) | yes |
| 17 | "Ten out of ten. Would not buy again." | maximum score paired with a refusal to repurchase | NEGATIVE (0.88) | **no** |
| 18 | "Great value, provided your definition of value has recently changed." | praise whose premise is withdrawn by the qualifier | POSITIVE (0.67) | yes |
| 19 | "So the good news is it's waterproof. The bad news is I found that out the hard way." | positive framing of an accident | NEGATIVE (0.40) | **no** |
| 20 | "A masterclass in removing features people liked." | praise vocabulary applied to a loss | POSITIVE (0.82) | yes |
| 21 | "Perfect. Absolutely perfect. Now let me show you the crack." | superlative immediately falsified by the next clause | POSITIVE (0.82) | yes |
| 22 | "Best in class, if the class is phones that do this one thing badly." | superlative whose scope is redefined into an insult | POSITIVE (0.43) | yes |
| 23 | "It's amazing, and I want to be clear that I'm not being paid to say that. Anymore." | disclaimer that reverses itself on the final word | POSITIVE (0.81) | yes |
| 24 | "I have never been happier to stop using a phone." | happiness attached to abandoning the product | POSITIVE (0.77) | yes |
The 12 congruent controls are in `probes.py` (`_CONGRUENT`); all 12 match the
pipeline's own label.
