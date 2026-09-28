# Controller bench — pre-registration

**Written 05 Sep 2026, before any candidate model was run and before any
candidate model was downloaded.** Nothing below was decided after seeing a
candidate's result. Corrections are appended as dated amendments at the end and
never edited into the body — the discipline `facial_bench/v2/PROTOCOL.md` and
`vocal_bench/SPEAKER_NORM_PREREG.md` established, where the amendments are still
visible.

---

## 1. Why this bench exists

Five channels have been benched (`comment_bench`, `transcript_bench`,
`whisper_bench`, `vocal_bench`, `facial_bench` ×2). **The controller has not.**
`llama3.2` was chosen once, never compared to anything, and never measured. It is
the last unmeasured model in the system, and it is the one the project's own
framing calls the centrepiece: this is an *orchestration* project, and the
orchestrator is the only component whose selection still rests on nothing.

The project's work plan scheduled this work and named
the research question:

> is the system's output a property of the *architecture*, or an artefact of one
> arbitrary model choice?

### The motivating measurement

This is prior knowledge, not a peek at a result. It concerns the **incumbent
only**, on **already-cached** responses, and part of it is already published in
`vocal_bench/CORPUS_AB_RESULT.md` §3.2.

Re-deriving the channel valences of the 481 cached `after_nodamp` segments from
the pipeline's own labels (`ab_cache/transcript`, `ab_cache/vocal_audeering`,
`ab_cache/comments`) gives:

| | segments | controller scored > 0 |
|---|---:|---:|
| all three readable channels agree | 43 | 0 |
| adjacent disagreement (NEUTRAL vs one pole) | 357 | 0 |
| **polar disagreement (POSITIVE *and* NEGATIVE both present)** | **81** | **8** |
| total | 481 | 8 |

So the incumbent returns `conflict_score` 0.0 on **473 of 481** segments, and on
**73 of the 81** segments where two channels sit at opposite poles of the valence
axis. Whether that is a defensible reading of the data or a failure of the model
is the question this bench exists to answer, and it cannot be answered by
inspecting the incumbent alone.

Three further properties of those cached responses are recorded here because they
shape the design below, not because they are results of this bench:

- **`flags` was emitted empty on all 481 responses.** `POTENTIAL_PAID_PROMOTION`
  and `SARCASM_DETECTED` — the outputs the product framing rests on — have never
  once fired.
- **The corpus contains only 8 distinct channel configurations,** and the
  comment channel is `POSITIVE` on all 12 videos. The natural corpus therefore
  cannot exercise most of the controller's input space. This is why §4.1 exists.
- **`facial_emotion` was named in `channels_in_conflict` on 264 responses** for a
  corpus with no facial channel at all (the payload reads `none detected`).

---

## 2. The question

> Does any locally-runnable LLM controller detect cross-channel disagreement
> better than `llama3.2` — and does any of them beat a deterministic rule that
> needs no LLM at all?

Four sub-questions, each with its success condition fixed here.

- **Q1 (is the incumbent the problem?).** On payloads whose correct answer is
  fixed by construction, does `llama3.2` under-detect conflict relative to other
  models of similar size? *Answered by:* P1 on the probe suite, §5.
- **Q2 (is it the model or the prompt?).** Does the incumbent's behaviour survive
  a prompt revision? A model that is fixed by editing its instructions was never
  the problem. *Answered by:* the prompt ablation, §7.
- **Q3 (does the LLM earn its place?).** Does any LLM beat the deterministic
  `rule_baseline` on the task the system prompt actually defines? *Answered by:*
  P1 and P2 with `rule_baseline` in the table.
- **Q4 (what can only an LLM do?).** On payloads where the four channel labels
  agree but the transcript text is sarcastic, hedged or incongruent, does any LLM
  raise a conflict where a label-only rule structurally cannot? *Answered by:* the
  incongruence suite, §4.3. **If fewer than 20 of the 24 incongruence probes are
  judged sound on post-hoc review, Q4 is reported as underpowered and no claim is
  made either way.**

Q3 and Q4 are deliberately opposed. Q3 can only embarrass the LLM; Q4 is the only
axis on which an LLM can beat a rule, and it is included so the bench is not rigged
toward the conclusion its design makes easy. A bench that can only produce one
answer is not a bench.

---

## 3. Candidates

Declared here, before any of them was downloaded.

### 3.1 LLM controllers

Every candidate must run **locally under Ollama** on the deployment machine
(Apple M1 Pro, 16 GB unified memory). That is a hard constraint of the project (README),
not a convenience: the entire B2B framing of this project is data sovereignty, and
a controller that needs a cloud endpoint is not a candidate at any accuracy.

| id | Ollama tag | params | why it is in |
|---|---|---|---|
| `llama3.2` | `llama3.2:latest` | 3.2 B | the incumbent |
| `llama3.1_8b` | `llama3.1:8b` | 8 B | same family, 2.5× the parameters — isolates scale from family |
| `qwen2.5_7b` | `qwen2.5:7b-instruct` | 7 B | instruction-tuned, widely used for structured JSON output |
| `qwen3_8b` | `qwen3:8b` | 8 B | newer generation of the same family |
| `mistral_7b` | `mistral:7b` | 7 B | named explicitly in the work plan |
| `gemma3_4b` | `gemma3:4b` | 4 B | already present locally; nearest size peer to the incumbent |
| `phi4_mini` | `phi4-mini` | 3.8 B | reasoning-dense small model, direct size peer to the incumbent |
| `granite3.3_8b` | `granite3.3:8b` | 8 B | tuned for enterprise structured output and tool use |

Four size peers of the incumbent (3–4 B) and four larger models (7–8 B), so
"bigger is better" is testable rather than assumed.

### 3.2 Non-LLM references

These are not competitors. They are the yardsticks that make the LLM numbers
mean something, exactly as the always-NEUTRAL constant did in `facial_bench/v2`.

| id | what it is |
|---|---|
| `rule_baseline` | a deterministic function of the four channel valences — the reference of §5.1 used as a predictor |
| `always_zero` | constant `conflict_score` 0.0. The degenerate strategy the incumbent currently approximates on 98.3 % of segments |
| `always_flag` | constant `conflict_score` 1.0. The opposite degenerate, included so that a metric cannot be maximised by never abstaining |

`rule_baseline` scores perfectly on P1 and P2 **by construction**, because it *is*
the reference. That is not a victory and will not be reported as one. It is a
statement about the task: it fixes the ceiling of the label-comparison sub-task at
1.0 and shows what a controller has to beat before its language ability is
earning anything. Its P3 and its incongruence-suite score are *not* free, and
those are where it can lose.

### 3.3 Declared exclusions

| excluded | reason |
|---|---|
| `gpt-oss:20b-cloud`, `deepseek-v3.1:671b-cloud`, `qwen3-coder:480b-cloud` | present in the local Ollama registry but proxied to `ollama.com`. The project's hard constraint forbids any pipeline call leaving the machine. Excluded on the constraint, **not** on measured quality — see §9. |
| `qwen3-coder:30b` | 18.6 GB against 16 GB of unified memory, and code-tuned rather than instruction-tuned. Excluded **only if** measured throughput confirms it (§8 G4); asserted infeasibility is not evidence. |
| any OpenAI / Anthropic / Google API model | same hard constraint. |

---

## 4. Test sets

Three, fixed here. All three are built by calling the **production**
`orchestrator.build_segment_payload` and `orchestrator._call_ollama`, never a
reimplementation. `facial_bench` Amendment A3 is the precedent: benching a
configuration the pipeline does not actually run invalidated a completed sweep
once already.

### 4.1 Probe suite — full configuration coverage (primary)

The natural corpus exercises 8 of the controller's possible input configurations.
The probe suite exercises all of them.

Four channels, with the vocabularies the pipeline really emits:

- `transcript_sentiment` ∈ {POSITIVE, NEUTRAL, NEGATIVE}
- `vocal_emotion` ∈ {POSITIVE, NEUTRAL, NEGATIVE} (audeering arousal, thresholded)
- `facial_emotion` ∈ {happy, neutral, sad, **none detected**} (DeepFace vocabulary; `none detected` is the fourth level, and is the *only* value present in the entire cached corpus)
- `video_comment_sentiment` ∈ {POSITIVE, NEUTRAL, NEGATIVE}

3 × 3 × 4 × 3 = **108 configurations**, each presented once = **108 probes**.

Every probe carries the **same** transcript text, the same segment id, the same
timings and the same prosody numbers. Only the four channel labels vary. This is
the whole point: any variation in a model's output across probes that share a
configuration is variation caused by something that is not the channel labels,
and the design makes that measurable rather than arguable.

The carrier text is one factually neutral sentence about a product, chosen so
that a model reading it instead of the labels has nothing to read. It is fixed in
`probes.py` before any run and is identical for all 108.

### 4.2 Corpus set — real segments (external validity)

The probe suite is synthetic. It cannot show that a model behaves the same way on
real transcripts, real prosody numbers and real Whisper segment text.

**All 481 segments** of the cached `after_nodamp` arm, on the real payloads, for
every candidate. Not a subsample: 481 × 11 candidates is within the runtime
budget and a subsample would only add a sampling defence to argue about.

This set is *not* used for the adoption decision. Its channel labels come from
models measured at 67.8 % (transcript), 48.9 % (vocal) and 78.7 % (comment), so a
controller that disagrees with them may be right. It answers a different and
narrower question — *does the probe-suite behaviour reproduce in the wild* — and
it is reported as such.

### 4.3 Incongruence suite — the LLM's home ground (Q4)

**24 hand-written probes** in which all four channel labels **agree** but the
transcript text carries something a label-only rule cannot see: sarcasm, faint
praise, a disclosed sponsorship, an approving sentence about a defect, hedging
that undercuts the claim.

Ground truth is **by construction**: the probe is written to contain the
incongruence, so "a conflict is present" is a property of how the item was built,
in the same way a unit test's expected value is. Twelve matched controls are
written alongside — same construction, genuinely congruent text — so that a model
which simply raises every score cannot score well. **36 items, 24 positive, 12
control.**

Every item is listed verbatim in the write-up. This suite is author-written and
synthetic; it can show that a capability exists or is absent, and it cannot show
how often the capability matters on real footage. That limit is stated here, in
advance, and will be restated in the results.

---

## 5. The reference

### 5.1 What counts as a disagreement

Every channel label is mapped onto the valence axis with the pipeline's **own**
map, `orchestrator._VALENCE_WORDS`, imported rather than copied. A label not on
that map (`surprise`, `unknown`, `none detected`) yields **no reading** and the
channel is excluded from the comparison — never coerced to NEUTRAL. That is
already the rule `_channel_valences` follows in production.

For a segment with readable valences `L`:

- `ref_any` — True iff `L` contains two different valences.
- `ref_polar` — True iff `L` contains both POSITIVE and NEGATIVE.
- `ref_score` ∈ [0, 1] — the mean over all channel *pairs* of a per-pair weight:
  **1.0** for a POSITIVE/NEGATIVE pair, **0.5** for a pair where one side is
  NEUTRAL, **0.0** for a matching pair.

`ref_score` is 0.0 for full agreement and 1.0 when every pair is polar, which are
exactly the two endpoints the deployed system prompt defines
(*"0.0 (full agreement) to 1.0 (all channels disagree)"*). The half-weight for a
NEUTRAL-involving pair is the one free parameter, it is declared here before any
run, and P1 — the primary metric — does not depend on it.

**This reference is analytic, not learned.** It is computed from the *inputs* the
controller is given, so it cannot be derived from the outputs of any model under
test. Step 2 of the bench method (README) is satisfied in the strongest available form.

**What it is not.** It measures whether a controller does the job the system
prompt specifies. It does **not** measure whether that job detects real
inauthenticity — the channel labels it reads are themselves 34–79 % accurate. No
claim of the second kind will be made from it.

### 5.2 Metrics

| id | metric | on |
|---|---|---|
| **P1** | Matthews correlation coefficient between `score > 0` and `ref_any` | probe suite |
| **P2** | Spearman ρ between `conflict_score` and `ref_score` | probe suite |
| **P3** | mean Jaccard between the normalised `channels_in_conflict` set and the reference disagreeing-channel set, over probes where `ref_any` is true | probe suite |
| **P4** | detection rate on `ref_polar` probes: fraction with `score > 0` | probe suite |
| **P5** | incongruence detection rate minus control false-alarm rate | incongruence suite |

**P1 is the primary metric.** MCC rather than accuracy because the probe suite is
unbalanced (most configurations disagree somewhere), and MCC is the coefficient
that a constant predictor cannot win: `always_zero` and `always_flag` both score
exactly 0.0 on it by definition. That property is why it was chosen.

P4 is reported because it is the quantity the motivating measurement is about, and
it is deliberately **not** primary: it is maximised by `always_flag`.

Every proportion is reported with its denominator and a **Wilson 95 % interval**.
Paired model-vs-model comparisons use an **exact McNemar test** on the 108 paired
probes, two-sided, with the direction stated separately — `facial_bench/v2` §6
records why: a two-sided test also returns p < 0.05 for a model that is
significantly *worse*, and reading that as "significantly different" would be
wrong.

---

## 6. Prompt, decoding and fairness

Identical for every candidate, no per-model tuning:

- the **deployed** `orchestrator._SYSTEM_PROMPT`, imported, not pasted;
- the payload produced by the **deployed** `build_segment_payload`;
- `format: "json"`, `temperature: 0`, `seed: 42`, `num_predict` unset;
- the same `/api/chat` endpoint and the same 120 s timeout;
- responses parsed and normalised by the **deployed** `_coerce_result`, so a model
  is credited or penalised for exactly what the production pipeline would make of
  its answer.

No model gets a prompt adjusted to suit it. Prompt engineering per candidate would
measure the author's effort per model, not the models.

**Damping is disabled for the bench** (`VOCAL_ONLY_CONFLICT_WEIGHT` and
`FACIAL_ONLY_CONFLICT_WEIGHT` set to 1.0). Damping is a deliberate post-hoc
correction applied to the score; leaving it on would mean scoring each model on a
number the pipeline has already modified, and would advantage models that happen
to trip it. Its effect is measured separately in Rule 7 re-run.

---

## 7. Prompt ablation (Q2)

If the incumbent under-detects, the cause could be the model or the instructions.
The current prompt has one property that makes this a live possibility: its
`CHANNEL RELIABILITY` paragraph tells the controller in bold terms *not* to raise
a high score on weak evidence, and it never tells it to raise one on strong
evidence.

So a **revised prompt** is written — once, before the ablation runs, and fixed —
which keeps every instruction of the deployed prompt and adds an explicit
statement of what the endpoints of the scale mean in terms of channel
disagreement. It is written to be a fair test of the hypothesis, not to be a
better prompt for one model.

Both prompts are run over the full probe suite for **the incumbent and the two
best-performing challengers**. Reported as a 3 × 2 table. The comparison of
interest is the within-model prompt delta, not the between-model difference.

---

## 8. Gates and the adoption rule

Fixed here, before any result.

**Gates.** A candidate that fails any of these is not adoptable whatever its P1.

- **G1 — parse rate.** `_coerce_result` must receive valid JSON on ≥ 95 % of
  probe-suite calls.
- **G2 — determinism.** Re-running 20 probes must reproduce byte-identical
  `conflict_score` values. `PROTOTYPE_FINDINGS.md` §5 is why this is a gate: the
  project has already lost 10–20 points of Authenticity Score to controller
  non-determinism once.
- **G3 — footprint.** Resident size must fit in 16 GB alongside the pipeline's own
  models.
- **G4 — throughput.** Median wall-clock latency per segment must be ≤ 3× the
  incumbent's. At 1,863 segments a 3× slower controller adds hours per corpus run,
  and the interface has a user waiting on it.

**Adoption rule.** `llama3.2` is replaced if and only if a candidate:

1. passes G1–G4;
2. beats the incumbent on **P1**, with an exact McNemar test over the 108 paired
   probes giving **p < 0.05 in the challenger's favour**;
3. does not regress **P2** by more than 0.05 Spearman ρ;
4. does not regress **P5** (does not lose the LLM's one genuine advantage).

If more than one candidate qualifies, the winner is the highest P1; ties broken by
P5, then by latency.

**If no candidate qualifies, nothing is adopted and that is the result** — the
same discipline as `facial_bench/v2` and `vocal_bench/SPEAKER_NORM_RESULT.md`,
both of which adopted nothing.

**Rule 7 obligation.** If a model is adopted, the 481-segment corpus is re-run
with it and the before/after Authenticity and Brand Health scores are reported.
If nothing is adopted, the equivalent obligation is discharged by the prompt
ablation: whatever change *is* adopted gets the same corpus re-run.

---

## 9. Threats to validity, stated in advance

1. **The reference is a specification, not truth.** §5.1 covers this. P1–P4 measure
   spec compliance. They do not measure whether the spec is the right spec.
2. **The frontier is untestable here.** The three strongest models in the local
   registry route to `ollama.com` and are excluded by a hard project constraint.
   This bench therefore cannot say whether a frontier model would solve the
   problem — only whether a *deployable* one does. Stated as a limitation, not
   worked around.
3. **The probe suite is synthetic.** Its uniform coverage is bought at the cost of
   realism, which is why §4.2 exists as the external-validity check.
4. **The incongruence suite is author-written.** Its ground truth is by
   construction, and construction can be unrepresentative. Every item is published
   verbatim so a reader can disagree with any of them.
5. **The corpus set's labels are themselves wrong 21–66 % of the time.** No claim
   about real-world conflict detection is drawn from it.
6. **One rater, one machine, one Ollama build** (0.33.2). Quantisation is Q4_K_M
   for most candidates and differs across families; a model is being judged as it
   would actually be deployed, not at full precision.
7. **The comment channel is POSITIVE on all 12 corpus videos,** so the corpus set
   cannot exercise a negative audience at all. The probe suite can, and does.

---

## 10. Out of scope, declared now

- Fine-tuning a controller. No time, and it would break the "off-the-shelf
  orchestration" premise the report describes.
- Replacing the LLM controller with the rule baseline in production. The bench may
  well show the rule matches it; *acting* on that is a design change with
  consequences for the narrative output and the flag vocabulary, and it needs its
  own decision, not a bench's side effect.
- Multi-call or chain-of-thought controller architectures. One call per segment is
  the deployed architecture and the one under test.
- Anything about the narrative field's *quality*. Only its consistency with the
  model's own score is measured (P3 is the attribution analogue); rating prose
  needs raters this bench does not have.

---

## Amendments

*(Appended in date order as they are needed. Nothing above this line is edited.)*

### Amendment A1 — 05 Sep 2026, before any candidate's grid run was scored

**A confound was found in §6 and removed. One candidate's partial run was
discarded and every candidate re-run from scratch under the corrected condition.**

§6 says "identical for every candidate … no per-model tuning". While running the
first two candidates it became clear that this was not in fact true, for a reason
nothing in §6 anticipated.

The deployed `_call_ollama` does not set `num_ctx`, so Ollama sizes the KV cache
from each **model's own advertised maximum context**. Those maxima differ by a
factor of four across the candidate set (32,768 for the Qwen and Mistral models,
131,072 for the Llama, Gemma and Phi ones — read from `ollama show`, recorded in
`cache/registry.json`). Measured consequence on this machine: `llama3.1:8b`
requested **23.06 GB** for a prompt of at most **~700 tokens**, against 16 GB of
unified memory. Swap went to 6.4 GB of 7 GB and throughput collapsed. The 3.2 B
incumbent never showed it, because its KV cache fits regardless — which is
precisely why a single-model pipeline never surfaced the problem.

That is not "identical conditions". It is each model being handed a different
memory budget by an allocator heuristic keyed to a number that has nothing to do
with the task: the largest payload this pipeline has **ever** built, over all 481
cached corpus segments, is **154 tokens**.

**Fix, applied to production rather than to the bench.**
`orchestrator.OLLAMA_NUM_CTX = 4096`, passed as `num_ctx` in the request options.
A 5.8× margin over the largest prompt observed, so no prompt is truncated and no
result can change; only the reservation changes. It is a production fix because
the defect is a production defect — the deployed pipeline was reserving memory it
could not use, on the machine it is meant to run on.

**Consequence for this bench, accepted rather than worked around.** The
`llama3.2` grid run and the partial `llama3.1_8b` grid run were made under the
old condition. Both were **deleted**, not kept and footnoted: comparing a model
run at 131 k context against one run at 4 k would be the exact confound this
amendment exists to remove. Every number in the write-up comes from a run made
after this change.

**What this costs the bench, stated plainly.** G3 (footprint) can no longer
discriminate between candidates, because the fix makes their footprints
near-identical by design. That is the right trade: G3 was a deployment gate, and
a gate that fires because of an allocator default rather than a model property
was never measuring what it claimed to. The *finding* — that an unbounded context
window makes a larger controller unusable on this hardware — is reported in the
write-up as a result, which is what it is.

### Amendment A2 — 05 Sep 2026, after the grid runs began and **before any incongruence probe was run**

**§2 Q4's "judged sound on post-hoc review" is given a concrete, objective
criterion here, and the criterion is fixed before any model's P5 exists.**
`cache/incongruence/` did not exist when this was written; the sweep was still in
the grid stage.

§4.3 asserts that in every incongruence item "all four channel labels agree", and
assigns those labels by hand as the ones "the pipeline's own models would
plausibly assign to that surface text". *Plausibly* is an assumption, and this
project's own rule is that an assumption that is cheap to test gets tested.

**The test.** All 36 texts were passed through the deployed transcript classifier
(`audio_module.add_transcript_sentiment`, fine-tuned cardiffnlp). An item is
**sound** if the pipeline's own label matches the label the item was built with —
because only then would the item actually reach the controller with its four
channel labels in agreement, which is the entire premise of the suite.

**Measured: 31 of 36 match.** Controls **12/12**. Incongruent items **19/24**.
Raw per-item output in `cache/incongruence_label_check.json`.

The five that do not match are all cases where the transcript classifier
*already* detects the negativity the item was written to hide:

| item | assigned | pipeline's own label | text |
|---|---|---|---|
| `incong_01` | POSITIVE | NEUTRAL (0.53) | "It only overheats when you actually use it…" |
| `incong_11` | POSITIVE | NEGATIVE (0.55) | "Everyone in the comments said it was terrible…" |
| `incong_14` | POSITIVE | NEGATIVE (0.47) | "Nothing wrong with it at all, and I've only mentioned three things wrong with it." |
| `incong_16` | POSITIVE | NEGATIVE (0.88) | "Ten out of ten. Would not buy again." |
| `incong_18` | POSITIVE | NEGATIVE (0.40) | "So the good news is it's waterproof. The bad news is I found that out the hard way." |

**Consequence, and the pre-registered floor binds.** §2 Q4 fixed, in advance:
*"If fewer than 20 of the 24 incongruence probes are judged sound on post-hoc
review, Q4 is reported as underpowered and no claim is made either way."*
Under this criterion **19 of 24 are sound. 19 < 20. Q4 is therefore reported as
underpowered, and no claim is made either way** — by one item.

That is uncomfortable and it is honoured anyway. `facial_bench/v2` pre-registered
a floor of 20 anger frames, collected 4, and declared Q2 underpowered rather than
reporting the number it had; the same discipline applies here or neither is worth
anything. A floor that is only honoured when it is convenient is not a floor.

**What is still reported, and how it is labelled.** The suite is run in full and
its numbers are published as a **capability probe** — descriptive evidence about
what each controller does with a sarcastic transcript — explicitly not as an
answer to Q4. P5 is reported twice: over all 24 incongruent items, and over the
19-item sound subset. Neither is presented as settling Q4.

**A finding in its own right.** Five of 24 hand-written sarcasm cases are caught
by the *transcript* channel before the controller ever sees them. Sarcasm
detection in this pipeline is not solely the controller's job, and a controller
bench that assumed it was would have mislocated the capability.

### Amendment A3 — 05 Sep 2026, during the grid stage, before any `qwen3_8b` result was scored

**`qwen3_8b` is measured to fail gate G4, is moved to the end of the run order, and
is dropped from the corpus stage. Its accuracy rows are still collected in full.**

§8 G4 fixed, in advance: *"Median wall-clock latency per segment must be ≤ 3× the
incumbent's."* The incumbent's measured median on the grid is **2.13 s**, so the
gate is **6.39 s**.

**Measured.** `qwen3_8b` ran for over **16 minutes without completing 20 probes**,
against the incumbent's 108 probes in under 4 minutes and `llama3.1_8b`'s 108 in
under 9. That is a floor of **>48 s per probe**, roughly **8× the gate** and **23×
the incumbent**. It is a floor, not a point estimate, and it is reported as one —
the exact median is recorded in `cache/grid/qwen3_8b.json` once the stage
completes, and the write-up quotes that figure rather than this bound.

**Cause, stated as an inference rather than a measurement.** `qwen3` is a hybrid
reasoning model whose thinking mode is on by default, and Ollama exposes
`"think": false` to disable it. The deployed `_call_ollama` does not set that
field, so thinking-on is the condition this pipeline would actually run it under,
and that is the condition benched. **No per-model flag was added to rescue it**,
because §6 forbids per-candidate tuning: adding `think: false` for one candidate
is exactly the prompt-engineering-per-model that §6 exists to prevent.

This is deliberately *not* treated the way Amendment A1 treated `num_ctx`. That
was a defect affecting **every** candidate and its fix changed no output. This is a
capability of **one** model, and disabling it would change that model's output.
Measuring qwen3 with thinking enabled, then reporting that a follow-up could
measure it disabled, is the honest order.

**Two consequences, both bounded.**

1. **Run order.** Left first in the registry order, `qwen3_8b` would hold four
   remaining models and every later stage behind it for more than two hours. It is
   moved to the end of `finish_run.sh`. Nothing about its treatment changes; only
   what waits on it.
2. **Corpus stage.** `qwen3_8b` is **excluded from the 481-segment corpus run**,
   which at its measured floor would take over four hours of the deployment
   machine. §8 states that a candidate failing a gate "is not adoptable whatever
   its P1", so those four hours could not change a decision. Its grid and
   incongruence rows — the ones where accuracy is what is being compared — are
   collected in full, so it is absent from exactly one table and present in the
   rest, marked.

**What this costs, stated plainly.** `qwen3_8b` has no external-validity check.
If its grid accuracy turns out to be high, this bench cannot say whether that
reproduces on real segments. That is a real gap and it is the price of not
spending four hours on a candidate the gate has already excluded.

### Amendment A4 — 06 Sep 2026, on completion of the run

**A3's `>48 s` figure is replaced by the measured one, and `qwen3_8b` turns out to
fail a second gate that A3 did not anticipate.**

A3 excluded `qwen3_8b` from the corpus stage on a *lower bound* — it had produced
no cached batch in 16 minutes — and promised the write-up would quote the exact
median once the stage completed. It has.

| measured over the full 108-probe grid | value |
|---|---|
| median latency, successful calls | **45.5 s** (7.1× the 6.39 s G4 gate, 21× the incumbent) |
| median latency, all calls | 59.7 s |
| **parse rate** | **75.9%** — 26 of 108 responses unparseable |

**The parse failure was not anticipated and is the more serious of the two.**
Ollama's `format: "json"` constrains generation, so 75.9% is not a model writing
prose; it is a hybrid reasoning model whose thinking output collides with the
constraint often enough that a quarter of its answers never reach the scorer. In
production each one becomes `_safe_fallback` — `conflict_score` 0.0, not flagged.
A controller that silently reports "no conflict" on a quarter of segments is a
worse failure than a slow one, and it would have been invisible in any evaluation
that did not count parse failures as errors. This bench counts them, because §6
scores every candidate through the deployed `_coerce_result`.

`qwen3_8b` therefore fails **G1 and G4**, the only candidate to fail two gates.
A3's decision stands and its reasoning is unchanged; only the evidence is now a
measurement rather than a bound.

**One claim in the write-up was falsified by this candidate and has been
corrected in place, with the correction visible.** §7.3 previously read "no model
emitted a single flag on any of the 36 probes", which was true of the seven models
then measured. `qwen3_8b` emitted **9** — `SARCASM_DETECTED` ×6 and
`POTENTIAL_PAID_PROMOTION` ×3 — while scoring `conflict_score` 0.0 on all nine.
The corrected finding is stronger than the original: the flag vocabulary is not
dead, it is *decoupled from the score and unread by the pipeline*.

**This is the case for having run it.** A3 could have dropped `qwen3_8b` entirely
and saved two hours. Doing so would have left a candidate excluded on speed alone,
missed a second and more serious gate failure, and left a false sentence standing
in §7.3.
