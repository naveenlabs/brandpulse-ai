# Corpus A/B — what the vocal swap actually did to the scores

**Run 02 Sep 2026.** `VOCAL_MODEL_ANALYSIS.md` measured the vocal channel against human
ratings and recommended a change. It could not say whether making that change improves the
numbers the product reports. `CANDIDATE_MODELS.md` §9 recorded that gap *before any result was
seen*:

> "Whether a better vocal channel improves the final Authenticity/Brand Health scores is a
> separate question this bench cannot answer [...] Measuring that properly needs a corpus
> re-run after adoption, and is follow-up work."

This is that follow-up, and it is what closes Rule 7 for this channel.

```bash
python research/vocal_bench/corpus_ab.py --prepare   # channel inputs, no controller
python research/vocal_bench/corpus_ab.py             # the full three-arm experiment
python research/vocal_bench/verify_ab.py             # re-derive every figure below
```

---

## 1. Design

A **controlled A/B**, not a re-run. Every input except the vocal channel is computed once and
shared byte-for-byte across arms, so a difference in the final score cannot come from anywhere
else. Whisper is not re-run; transcript sentiment is not recomputed per arm; comment sentiment
is fetched once per video; the controller runs at `temperature: 0` with `seed: 42`, which was
verified to give identical output on repeated calls.

| Arm | vocal model | prompt | damping |
|---|---|---|---|
| `before` | speechbrain, categorical | pre-swap | none |
| `after` | audeering, arousal | post-swap | ×0.489 |
| `after_nodamp` | audeering, arousal | post-swap | none |

Three arms rather than two, because "before vs after" cannot attribute the change:

- `after − before` — the total effect
- `after_nodamp − before` — the model and dimension swap
- `after − after_nodamp` — the down-weighting

**`after` costs no controller calls.** It and `after_nodamp` send byte-identical payloads under
the same prompt, model, temperature and seed, so they receive byte-identical responses; they
differ only in a multiplication applied afterwards in `_coerce_result`. `after` is therefore
derived by re-coercing `after_nodamp`'s cached raw JSON — exact, not approximate, and it
demonstrates directly that the damping is pure post-processing.

### Sample

| | |
|---|---|
| Videos | 12 |
| Speakers | 6 |
| Segments | **1,863** |
| Audio | 152.3 min |
| Controller calls | 3,726 (2 arms × 1,863) |

The same 12 videos and 6 speakers the 150 rated clips were drawn from, verified mechanically:
every clip's `video_id` is in the corpus, and no corpus video is unrepresented.

### What this cannot see, stated up front

**The facial channel is absent.** The corpus videos were downloaded as audio only, so no frames
exist for them. It is absent *identically in all three arms*, so it cannot bias the comparison —
but these are three-channel numbers, not four-channel numbers, and the absolute Authenticity
Scores below are not directly comparable to a run on a video with frames.

**Comment sentiment is POSITIVE on all 12 videos** (confidence 0.95–0.99). It is identical
across arms, so it cannot bias the comparison either, but it means the Brand Health Score's 60%
comment term is effectively constant here: every Brand Health difference below is 0.4 × the
Authenticity difference, by construction, not by measurement.

---

## 2. The channel input changed on half the corpus

Measured before any controller call, so it is independent of anything the LLM does. The
pre-swap pipeline handed the controller a bare IEMOCAP word; this maps it to a valence direction
using the same mapping `report_bench.py` scored the incumbent under.

| Reading | `before` | `after` |
|---|---:|---:|
| NEGATIVE | **776 (41.7%)** | **14 (0.8%)** |
| NEUTRAL | 1,003 (53.9%) | 1,464 (78.7%) |
| POSITIVE | 81 (4.4%) | 382 (20.5%) |
| unknown | 3 | 3 |

**965 of 1,863 segments — 51.8% — changed reading.**

| Transition | n |
|---|---:|
| NEGATIVE → NEUTRAL | 565 |
| NEGATIVE → POSITIVE | 210 |
| NEUTRAL → POSITIVE | 135 |
| POSITIVE → NEUTRAL | 42 |
| NEUTRAL → NEGATIVE | 11 |
| POSITIVE → NEGATIVE | 2 |

**775 of the 965 changes (80.3%) move away from NEGATIVE.** The deployed channel was calling
41.7% of a corpus of professional product reviews vocally negative. That is the corpus-scale
version of a specific observation made while rating the clips by ear — that almost nothing in
this material sounds genuinely angry, and the worst case is an occasional disappointed tone.

This also matters methodologically: with the controller's input changed on half the segments, a
null result downstream would be a fact about the controller, not an artefact of the two models
agreeing.

### But the new distribution is wrong too, in the opposite direction

This is the part that must not be glossed. Against the 147 hand-rated clips — drawn from the
same 12 videos, so a like-for-like comparison:

| Class | human (n=147) | `before` (n=1,860) | `after` (n=1,860) |
|---|---:|---:|---:|
| NEGATIVE | **15.0%** | 41.7% | 0.8% |
| NEUTRAL | 42.9% | 53.9% | 78.7% |
| POSITIVE | 42.2% | 4.4% | 20.5% |

| | total variation distance from human |
|---|---:|
| `before` | 0.3782 |
| `after` | **0.3585** |
| change | **−0.0197** |

**The swap improved the distribution match by 2 points on a 38-point error.** The old model
over-called NEGATIVE by 2.8×; the new one under-calls it by 20×. Neither is close.

Distribution match and per-segment accuracy are different things, and only the second was ever
claimed: the new configuration is right on 48.9% of held-out clips against the old model's
34.0%, and the old model was *significantly worse than a constant* (p = 0.0070). A model can be
more accurate per item while remaining badly calibrated in aggregate, and that is exactly what
happened here.

> **Honest summary of the swap: one badly-calibrated channel was replaced with a differently,
> and slightly less, badly-calibrated channel that is meaningfully more accurate per segment.**
> The down-weighting is not a belt-and-braces addition to that. It is the main protection, and
> this table is why.

---

## 3. Effect on the reported scores

**479 segments across all 12 videos** — 40 per video, sampled evenly across each video's timeline
rather than truncated, because a video's opening is its intro and hook and would bias exactly the
quantity under test. 958 controller calls; the third arm derived without any.

| Arm | Authenticity | Brand Health | flagged | mean conflict | non-zero conflicts | damped |
|---|---:|---:|---:|---:|---:|---:|
| `before` | **70.76** | 86.60 | **69 / 479** | 0.2309 | 232 | 0 |
| `after` | **97.45** | 97.28 | **8 / 479** | 0.0131 | 8 | **0** |
| `after_nodamp` | 97.45 | 97.28 | 8 / 479 | 0.0131 | 8 | 0 |

### Decomposition

| Component | Δ Authenticity |
|---|---:|
| **total** (`after − before`) | **+26.69** |
| model + dimension (`after_nodamp − before`) | **+26.69** |
| down-weighting (`after − after_nodamp`) | **+0.00** |

**Every point of the change comes from the model and dimension swap. The down-weighting
contributed exactly nothing.** That is dealt with honestly in §3.2 rather than left as a footnote.

### 3.1 The effect is consistent, not carried by one video

| | |
|---|---|
| Videos where Authenticity rose | **12 / 12** |
| Sign test | **p = 0.000488** |
| Mean change | +26.69 |
| Smallest / largest change | +4.15 / +47.62 |

Per-video Authenticity, `before` → `after`:

| Video | before | after | Δ | flagged before → after |
|---|---:|---:|---:|---|
| 0jHtyF_rCqU | 95.85 | 100.00 | +4.15 | 0 → 0 |
| 32slGhAH3Xc | 79.10 | 100.00 | +20.90 | 2 → 0 |
| 4KbrxIpQgkM | 72.53 | 96.10 | +23.57 | 3 → 1 |
| 5VMckmQneCk | 55.04 | 96.10 | +41.06 | 14 → 1 |
| Gvvo6vUpJRc | 57.37 | 96.10 | +38.73 | 11 → 1 |
| Kk-RKpTAXmA | 57.28 | 96.10 | +38.82 | 10 → 1 |
| Rlw_CI7pOKg | 75.74 | 100.00 | +24.26 | 3 → 0 |
| SSC0RkJuBVw | 82.25 | 92.62 | +10.37 | 4 → 2 |
| haWvrSliMVY | 64.16 | 96.25 | +32.09 | 6 → 1 |
| i63u-iAnhuk | 73.49 | 96.10 | +22.61 | 3 → 1 |
| q0aFOxT6TNw | 83.88 | 100.00 | +16.12 | 1 → 0 |
| vOhuf18b-g8 | 52.38 | 100.00 | +47.62 | 12 → 0 |

Direction and magnitude are consistent with `PROTOTYPE_FINDINGS.md` §11, where correcting the
channel inputs by hand moved the Authenticity Score from 26.55 to 80.57 and flagged segments from
33/77 to 0/77. That was one video, corrected manually; this is 12 videos, corrected by a model
adoption, with the confound controlled.

### 3.2 The down-weighting never fired, and the reason is a defect

> **Superseded 02 Sep 2026, later the same day.** This section describes the rule as it stood
> when this A/B ran, and it is left unedited because it is the measurement that motivated the
> replacement. The trigger has since been rewritten to read the pipeline's own channel labels
> instead of the controller's self-report, and now fires on **89 of 481** segments in this same
> arm. See `DAMPING_FIX_RESULT.md`. Consequence for reproduction: re-deriving the `after` arm
> with today's code will **not** reproduce the numbers in §3 — the cached arms in `ab_cache/`
> are the pre-fix ones, and `verify_ab.py` checks those.

**Measured: the damping applied to 0 of 479 segments.** It is implemented, unit-tested, and inert.
Reporting it as a delivered protection would be false confidence.

The rule fires when the controller assigns a non-zero conflict score **and** attributes that
conflict solely to the vocal channel. Both halves were checked against the raw controller output:

| | `before` (legacy prompt) | `after` (new prompt) |
|---|---:|---:|
| Responses carrying `channels_in_conflict` | **0 / 496** | **481 / 481** |
| …with at least one channel named | 0 | 265 |
| …of those, with a conflict score > 0 | 0 | **8** |
| …of those, naming the vocal channel alone | 0 | **0** |

Two separate things are visible here.

**The prompt change worked.** Adding an explicit instruction to populate `channels_in_conflict`
took the field from absent in every response to present in every response. That is a real, measured
effect of a prompt edit.

**The controller is internally inconsistent, and that is what disables the rule.** `llama3.2` names
channels as being in conflict while simultaneously scoring the conflict at 0.0 — 257 of its 265
attributions accompany a zero score. When it does assign a non-zero score, it almost never says
which channels are responsible. Score and attribution are effectively decoupled, so a rule keyed on
attribution has nothing to act on.

A counterfactual was run to check whether the rule would at least have rescued the *old* channel:
applying the damping to the `before` arm's raw responses would have altered **0 segments and
unflagged 0**, because that arm's responses carry no attribution at all.

**Consequence.** The damping is not proven useless — it is **unexercised**. On this corpus it had
nothing to act on, partly because the model swap removed nearly all conflict (232 non-zero scores
down to 8). But a protection that cannot fire against the deployed controller is not yet a
protection, and the honest status is *implemented, untested in effect*.

**The fix — proposed here, implemented and measured the same day:** key the rule on the channel
readings the pipeline already holds rather than on the controller's self-report. The vocal channel
is the only dissenter whenever its label differs from the transcript and comment labels and those
two agree — computable deterministically from the segment dict, needing no LLM compliance, firing
regardless of what the controller chooses to say.

`orchestrator._vocal_is_sole_dissenter` now does this. It fires on **89 of 481** segments in this
arm and **126 of 496** in the `before` arm, against 0 for the rule it replaced. Its effect on the
reported scores is **+0.00 here** — none of the 89 lands on a non-zero conflict score — and
**+0.52 Authenticity on the `before` arm**, the only cached arena where the controller produced
enough non-zero scores to act on. Full write-up and 113 re-derived claims in
`DAMPING_FIX_RESULT.md`.

### 3.3 What this does NOT show

The Authenticity Score went **up** by 26.69 points and flagging fell from 14.4% of segments to
1.7%. Nothing here establishes that the new numbers are *more correct*.

- There is **no ground truth for authenticity** on this corpus. Both scores are unvalidated; only
  the difference between them is measured.
- The old channel was manufacturing false conflict — that much is established independently in §2,
  where it labelled 41.7% of the corpus vocally negative against a human rate of 15.0%. Removing a
  known source of false positives is a defensible improvement.
- But **over-flagging may simply have become under-flagging.** 8 flags in 479 segments is a system
  that flags almost nothing, and its ability to detect genuine inauthenticity remains untested in
  both arms. Establishing that needs videos with known paid promotion, which this corpus does not
  contain and which `PROTOTYPE_FINDINGS.md` already lists as an open evaluation gap.

The defensible claim is narrow: **the swap removed a large, measured source of spurious conflict,
consistently across 12 videos.** It is not that the system is now accurate at detecting
inauthenticity.

---

## 4. Threats to validity

| Threat | Assessment |
|---|---|
| Facial channel absent | Absent identically in all arms, so unbiased, but these are three-channel numbers. |
| Comment sentiment constant (POSITIVE on 12/12) | Brand Health deltas are 0.4 × Authenticity deltas by construction. Reported, not interpreted. |
| One controller (`llama3.2`) | The whole experiment is conditional on it. A different controller could respond differently to the same input change; that is the next bench, not this one. |
| `before` arm is a reconstruction | It uses the bench's verbatim historical copy of the pre-swap code, and the same segment windows. It is not a recording of a real historical run. |
| Single corpus, 6 speakers, one genre | Same limitation as every bench in this project. |
| No held-out split | This is a measurement of an effect on a fixed corpus, not a model-selection decision, so a holdout is not the right instrument. Nothing is being chosen on these numbers. |
| 40 of ~155 segments per video | Sampled evenly across each video's timeline, not truncated, so the opening is not over-represented. 479 of 1,863 segments; the remainder are cached and the run is resumable if a fuller pass is wanted. |
| Ceiling effects | Five videos reach exactly 100.00 and four reach 96.10 in the `after` arm. With conflict this rare the score saturates, so the +26.69 is a lower bound on the input change's effect, not a linear reading of it. |

---

## 5. What is verified, and what is not

**Verified facts** (re-derivable by `verify_ab.py`):
- The pipeline's audeering path is **bit-identical** to the bench's: max absolute difference
  0.000e+00 across 12 clips × 3 dimensions, 12/12 label agreement.
- The deployed `classify_arousal` reproduces the bench figures exactly: **60/100** on selection,
  **23/47** on the held-out speakers.
- 965 of 1,863 segments (51.8%) changed vocal reading; 775 of those move away from NEGATIVE.
- 99.7% of pipeline segments fall inside the bench clips' duration range.
- Authenticity rose **70.76 → 97.45** (+26.69) across 479 segments, on **12 of 12 videos**
  (sign test p = 0.000488); flagged segments fell 69 → 8.
- **The entire change is attributable to the model and dimension swap.** The down-weighting
  contributed +0.00 and fired on 0 of 479 segments.
- Full suite: **400 passing**. `verify_ab.py` re-derives **94 claims** from the raw data.

**Reasonable inference, labelled as such:**
- That `VOCAL_ONLY_CONFLICT_WEIGHT = 0.489` is the right damping factor. Three-class accuracy is
  a proxy for "this specific conflict is real"; the two are related but not identical.

**Measured defect in this work, not hidden:**
- The vocal down-weighting was **implemented and inert** when this A/B ran. `llama3.2` decouples
  its conflict score from its channel attribution — 257 of 265 attributions accompany a score of
  0.0 — so a rule keyed on attribution had nothing to act on. **Fixed the same day**
  (`DAMPING_FIX_RESULT.md`): the deterministic replacement fires on 89 of these 481 segments.
  Its status is now *fires, but unexercised at the flag threshold* — no segment in either arm
  crossed 0.75 in either direction, so the double-weighting path it guards is still covered by
  unit test only.

**Not claimed:**
- That the vocal channel now works. It does not. It is right on fewer than half of held-out
  clips and no model tested beat a constant.
- That a higher Authenticity Score is a more *correct* one. This experiment measures that the
  score moved and attributes the movement; whether the new value is closer to ground truth needs
  human-rated authenticity labels, which do not exist for this corpus.
