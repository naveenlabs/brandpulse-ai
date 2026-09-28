# Facial down-weighting: does it fire, and what does it change?

**04 Sep 2026.** Harness `damping_ab.py`, results `damping_ab_results.json`.
The facial analogue of `vocal_bench/DAMPING_FIX_RESULT.md`, and it reaches a
partly different answer, reported in full.

## 1. What was changed

`facial_bench/v2/` measured the facial emotion channel at **34.2%** on held-out
speakers, below an always-NEUTRAL constant's 67.5%, and found it calls **33.8%**
of verified-neutral held-out frames NEGATIVE
(`FACIAL_MODEL_ANALYSIS_V2.md` §7–§8). `PROTOCOL.md` §9 pre-committed to
down-weighting the channel on that basis "regardless of which model wins", so this
change was decided before the numbers were seen.

- `visual_module.FACIAL_CHANNEL_RELIABILITY = 0.342` (39 of 114 held-out frames)
- `orchestrator.FACIAL_ONLY_CONFLICT_WEIGHT = 0.342`, applied when
  `_facial_is_sole_dissenter()` or `_conflict_rests_only_on_facial()` fires

## 2. The corpus, and one thing it did not have

The 12-video corpus in `vocal_bench/ab_cache/` is reused, because everything
except the facial channel is already cached there: Whisper segments, transcript
sentiment, vocal readings, comments, and the controller's raw responses.

**It had no facial channel.** No frames had been extracted when it was built. So
the channel was computed here, with the deployed configuration, and cached to
`ab_cache_facial/`:

| | |
|---|---:|
| Videos | 12 |
| Frames processed | **9,125** |
| Frames with a detected face | **4,645** (50.9%) |
| Wall clock | 12.6 min (0.0826 s/frame) |
| Segments (all) | 1,863 |
| Segments the controller actually scored | **481** |

## 3. Harness validation

Before reporting anything new, the harness reproduces the published figure. With
the facial channel stripped back out, the vocal rule fires on:

**89 of 481 segments (18.5%)** — exactly the figure in
`vocal_bench/DAMPING_FIX_RESULT.md`.

If that had not reproduced, nothing else in this file would be trustworthy.

## 4. Coverage

| Rule | Controller-scored (481) | All segments (1,863) |
|---|---:|---:|
| **facial is sole dissenter** | **18 (3.7%)** | **53 (2.8%)** |
| vocal is sole dissenter, facial channel present | 49 (10.2%) | 211 (11.3%) |
| vocal is sole dissenter, facial channel stripped | 89 (18.5%) | 396 (21.3%) |
| both rules on the same segment | **0** | **0** |
| segments where the facial channel has a readable valence | 323 (67.2%) | 1,172 (62.9%) |

Two things follow, and the second was not anticipated.

**The facial rule fires, but rarely** — 18 of 481. It requires the facial channel
to carry a readable valence *and* the other three channels to agree with each
other *and* the face to disagree with them. On this corpus that combination is
uncommon.

**Adding the facial channel nearly halves the vocal rule's coverage: 89 → 49.**
This is not a bug and it is not a regression. A fourth channel makes "every other
channel agrees" strictly harder to satisfy, so segments that looked like a lone
vocal dissent in a three-channel world are revealed as genuine multi-channel
disagreements once the face is present. **The published 89-of-481 figure is
therefore specific to a corpus with no facial channel, and the deployed
four-channel pipeline damps the vocal channel on roughly half as many segments as
that number implies.** That is a correction to how an existing measurement should
be read, not to the measurement itself, and it was invisible before this run.

**The two rules never fire together** — 0 of 1,863. That confirms empirically what
`_facial_is_sole_dissenter`'s docstring argues structurally and what the
parametrised test in `tests/test_damping_rule.py` asserts: only one channel can be
the lone dissenter. The "never multiply the two weights" branch in
`_coerce_result` is therefore unreachable on this corpus, and is kept for the
contradictory-attribution case the controller could still produce.

## 5. Effect: zero, and precisely why

| | segments | non-zero score | flagged | mean score |
|---|---:|---:|---:|---:|
| before (weight 1.0) | 481 | 8 | 8 | 0.0131 |
| after (weight 0.342) | 481 | 8 | 8 | 0.0131 |

**Nothing changed. 0 segments, 0 flags.** There are two independent reasons, and
both need stating:

1. **The controller returned `conflict_score` 0.0 on 473 of 481 segments.**
   Damping multiplies, and 0 × 0.342 = 0. This ceiling is not a property of the
   rule; `vocal_bench/damping_ab.py` documented the same one.
2. **All 8 non-zero segments are genuine multi-channel disagreements.** In every
   one, transcript is NEGATIVE while comments are POSITIVE, and no single channel
   is the lone dissenter. The facial rule fires on **0 of 8**, and so does the
   vocal rule.

Reason 2 is the more interesting half, and it is a *positive* result about
specificity rather than an absence of one: on the only 8 segments this corpus
gives that carry a real conflict, the rule correctly declined to touch any of
them. A down-weighting that fired on those would have raised the Authenticity
Score of segments that deserved their flags, which is the failure direction that
flatters the system.

## 6. What this does not establish

**The cached controller responses were produced from prompts with no facial
channel.** Re-coercing them with the facial channel attached is valid for
coverage — coverage depends only on the channel labels — but the *scores* it
multiplies are scores the facial channel never influenced. A live four-channel
controller run would show the controller different prompts and could produce a
different score distribution.

So §5's "effect: zero" is honest for this corpus and is **not** a claim that the
change can never move a score. `damping_ab.py --controller live` is the
outstanding work; it is deliberately not implemented rather than approximated,
because an approximation here would be indistinguishable from a measurement in the
write-up.

What would make the effect visible is a controller that produces non-zero conflict
scores more than 1.7% of the time. That is a property of `llama3.2`, not of this
rule, and it is the strongest argument in this repo for the controller-model bench
that is still open.

## 7. Status against Rule 7

Adopted, deployed, corpus re-run, before and after reported — including the two
results that do not flatter it: the effect on this corpus is zero, and the change
reduces the vocal rule's coverage from a previously published figure.
