# The vocal down-weighting now fires. What that is worth, measured.

**Run 02 Sep 2026.** Harness `damping_ab.py`, results `damping_ab_results.json`, every
number below re-derived by `verify_damping_fix.py`. No controller calls: the rule is pure
post-processing, so re-coercing the A/B's cached raw responses reproduces exactly what a
fresh run would have produced. Seconds, not the eight hours the original A/B took.

**Headline.** The defect is fixed — the rule fires on **89 of 481** segments in the deployed
configuration where the old one fired on **0 of 479**. On the deployed arm that changes the
reported scores by **+0.00**, because llama3.2 returned a conflict score of exactly 0.0 for
473 of those 481 segments and damping multiplies. On the one cached arm where the controller
produces enough non-zero scores to act on, the rule damps **17 segments** and moves
Authenticity by **+0.52**.

**Honest summary in one line: a real defect was fixed, the fix demonstrably works, and on
this corpus it is worth almost nothing — because the limiting factor turned out to be the
controller, not the rule.**

---

## 1. What was broken

`CORPUS_AB_RESULT.md` §3.2 measured the original down-weighting firing on **0 of 479**
segments. It asked the controller which channels it thought were in conflict:

```python
vocal_only = _conflict_rests_only_on_vocal(data.get("channels_in_conflict"))
```

`llama3.2` answers that question — it populated the field in 481 of 481 responses, and named
at least one channel in 265 of them — but it decouples the answer from its own score. **257 of
those 265 attributions accompany a score of exactly 0.0**, and none named the vocal channel
alone. A rule keyed on the controller's self-report therefore had nothing to act on.

## 2. What replaced it

A rule computed from the channel labels the pipeline already holds, which depends on no
model's self-report. `orchestrator._vocal_is_sole_dissenter` is true when all four hold:

1. the vocal channel has a usable reading;
2. at least `MIN_CORROBORATING_CHANNELS` other channels do too;
3. those other channels all agree with one another;
4. the vocal reading differs from what they agree on.

Removing the vocal reading would then remove the disagreement entirely — which is exactly the
case where the conflict rests on a channel measured at 48.9% accuracy.

Three decisions inside it, each made in the conservative direction, meaning each makes the
rule fire **less** often:

- **`surprise` is not placed on the valence axis.** It accompanies delight and dismay equally.
  An unreadable channel is excluded from the agreement test rather than guessed at.
  (`static/index.html` colours surprise as positive. That is a cosmetic hint; a colour that is
  occasionally wrong costs nothing, a damping decision that is occasionally wrong changes the
  score. The divergence is deliberate.)
- **"Unknown" never becomes "neutral".** A channel that declined to answer stays distinct from
  one that answered neutral.
- **The others must agree with each other.** If they disagree among themselves, the conflict
  does not rest on the vocal channel and nothing is damped.

The old trigger is **kept, not deleted**, and ORed with the new one. It is inert on
`llama3.2` and costs nothing; a more compliant controller would make it work. Which trigger
fired is written into `conflict_reasons` as `[attributed]`, `[structural]` or
`[attributed+structural]`, so a run can be audited without re-deriving it.

## 3. Does it fire?

Coverage is a property of the channel labels alone, independent of what the controller scored,
so it is measured over every cached segment.

| Source arm | Segments | Fires | | Old rule |
|---|---:|---:|---:|---:|
| `after_nodamp` — the deployed configuration | 481 | **89** | 18.5% | 0 |
| `before` — the pre-swap configuration | 496 | **126** | 25.4% | 0 |

**The defect is fixed.** Both arms are real cached controller output; neither is simulated.

## 4. `MIN_CORROBORATING_CHANNELS` — chosen by reasoning, not measured

The constant is set to **2**: with a single comparator, "the others agree" is vacuously true
and a disagreement is a coin flip between two channels rather than one voice breaking a
consensus. The damping constant is the vocal channel's own accuracy, so it is only the right
correction when the vocal channel is the thing in doubt. Damping *raises* the Authenticity
Score, so the conservative error is to damp too rarely.

**Both settings were measured and came out identical**, on all 977 cached responses:

| Source arm | min = 1 | min = 2 | mean corroborating channels |
|---|---:|---:|---:|
| `after_nodamp` | 89 | 89 | 2.000 |
| `before` | 126 | 126 | 2.000 |

Every segment in this corpus has exactly two other readable channels, because no frames were
extracted (so there is no facial channel) and comment sentiment resolved for all 12 videos.
**The corpus cannot separate 1 from 2.** The value therefore rests on the argument above and
not on evidence, and the module comment says so. Recorded rather than presented as validated.

## 5. What it changes in the reported scores

### 5.1 The deployed arm: nothing, and not because of the rule

| Variant | Authenticity | Brand Health | Flagged | Damped | Mean conflict |
|---|---:|---:|---:|---:|---:|
| `nodamp` (baseline) | 97.45 | 97.28 | 8 | 0 | 0.0131 |
| `attributed` (the old rule) | 97.45 | 97.28 | 8 | 0 | 0.0131 |
| `structural_min1` | 97.45 | 97.28 | 8 | 0 | 0.0131 |
| **`structural_min2`** (deployed) | **97.45** | **97.28** | **8** | **0** | **0.0131** |

**+0.00 on every measure.** The rule fires on 89 segments and **0 of them carry a non-zero
conflict score.** Damping multiplies, so it cannot move a score of 0.0.

The ceiling is not a property of the rule. It is a property of the controller: in this arm
`llama3.2` returned **0.0 for 473 of 481 segments**, and only **3 distinct scores** in total.

### 5.2 The `before` arm: a real, small effect

The pre-swap arm is not the deployed configuration, but it is the only cached arena where the
controller produced enough non-zero scores for a damping rule to have anything to act on —
235 of 496 segments, across 9 distinct values.

| Variant | Authenticity | Brand Health | Flagged | Damped | Mean conflict |
|---|---:|---:|---:|---:|---:|
| `nodamp` (baseline) | 70.68 | 86.57 | 70 | 0 | 0.2263 |
| `attributed` (the old rule) | 70.68 | 86.57 | 70 | **0** | 0.2263 |
| `structural_min1` | 71.20 | 86.78 | 70 | **17** | 0.2205 |
| **`structural_min2`** | **71.20** | **86.78** | **70** | **17** | **0.2205** |

**Authenticity +0.52, Brand Health +0.21, 17 segments damped, 7 of 12 videos changed**
(+0.31 to +1.57). The old rule still moves nothing, on either arm — which is the cleanest
possible confirmation that the replacement is what did the work.

**The flag count does not move: 70 → 70.** All 17 damped segments had a controller score of
exactly 0.3300, damped to 0.1614. That is already far below the 0.75 flag threshold, so the
damping changes the magnitude that feeds `compute_authenticity_score` and nothing else. **No
segment crossed the flag threshold in either direction.** The double-weighting of flagged
segments — the effect the down-weighting was written to protect against — was therefore never
exercised on this corpus, and remains untested against real data.

## 6. A controller finding, recorded for the controller bench

`llama3.2` at temperature 0 emits a very small set of canned conflict scores:

| Arm | Responses | Distinct scores | Most common |
|---|---:|---:|---|
| `before` | 496 | **9** | 0.0 (52.6%), 0.33 (32.9%), 0.75 (4.2%) |
| `after_nodamp` | 481 | **3** | 0.0 (98.3%), 0.80 (1.2%), 0.75 (0.4%) |

This is not a graded 0.0–1.0 judgement; it is a handful of quantised buckets. Combined with
§1's finding that the model decouples its score from its own attribution, it is a second
concrete reason the controller-LLM choice deserves its own bench. **Both findings are about
`llama3.2`, not about the pipeline.**

## 7. Status by claim type

**Verified fact** — the old rule fires on 0 of 481 and 0 of 496; the new rule fires on 89 and
126; the two `MIN_CORROBORATING_CHANNELS` settings are indistinguishable on this corpus; all
17 damped segments moved 0.3300 → 0.1614; the controller emits 3 and 9 distinct scores.

**Measured result** — every score, delta and count in §5, over 977 cached controller responses
and 12 videos.

**Reasonable inference** — that `MIN_CORROBORATING_CHANNELS = 2` is the safer choice. Argued,
not measured, and labelled as such in the code.

**Not claimed** — that the fix improves the accuracy of the reported scores. There is no
authenticity ground truth for this corpus; only the difference between variants is measured.
Nor that the protection has been exercised where it matters: **no segment crossed the flag
threshold**, so the double-weighting path the rule exists to guard is still untested against
real data. That needs a corpus where the controller returns high conflict scores on
vocal-only disagreements, which this one does not contain.

## 8. What is still open

- The protection is live but **unexercised at the flag threshold**. Until a segment crosses
  it, the rule's most important effect is verified by unit test only.
- The real bottleneck is now the controller, not the vocal channel: 98.3% of the deployed
  arm's segments score exactly 0.0. A controller-LLM bench (llama3.2 vs mistral vs qwen)
  would test whether that is a `llama3.2` artefact or the task's true answer.
- 481 of 1,863 segments are scored; the rest are cached and the run resumes.
