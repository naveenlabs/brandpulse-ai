# Transcript Fine-Tune — Null Result

**Run 31 Aug 2026.** Produced by `finetune_transcript.py`; per-run evidence in
`analysis/finetune_lr*.json`.

**Outcome: fine-tuning did not improve the transcript model. It was not adopted. The
off-the-shelf `cardiffnlp/twitter-xlm-roberta-base-sentiment` remains in the pipeline.**

---

## 1. The question

The same procedure on the comment channel worked well: 1,000 hand-labelled comments lifted
held-out accuracy from 69.3% to **78.7%** (p = 0.007). This asks whether 400 hand-labelled
*spoken transcript* segments do the same for the transcript channel, or whether 400 is simply
too few to move a 278M-parameter model.

Declared before running: a null result is written up as a null result.

## 2. Method

Copied from `comment_bench/v2/finetune_cardiffnlp.py` rather than reinvented.

| | |
|---|---|
| Base model | `cardiffnlp/twitter-xlm-roberta-base-sentiment` (the adopted one) |
| Train | 320 segments (from the 400-segment selection set, stratified, seed 42) |
| Validation | 80 segments (from the same 400) |
| Test | **199 segments, 4 speakers absent from training entirely** |
| max_len | 64 — token audit over all 599 labelled segments gives median 23, p95 34, max 57, so **nothing is truncated** |
| Device | CPU (MPS aborted with an out-of-memory fault, the same failure the comment script documents on this machine) |
| Determinism | seed 42; both reported configurations were re-run and reproduced identically |

Head order was asserted at load time (`negative, neutral, positive`) so the classifier head is
reused rather than reinitialised.

**Data discipline.** Validation came out of the 400, never the 199. Learning rates were
compared using a `--tune-only` mode that never loads or scores the test set, so the three
candidate learning rates cost zero uses of the holdout.

## 3. Learning-rate search — on validation only

| Learning rate | Best val macro-F1 | At epoch |
|---|---:|---:|
| untrained baseline | 0.5754 | — |
| 2e-5 | 0.6103 | 1 |
| 1e-5 | 0.6085 | 4 |
| **5e-6** | **0.6231** | **4** |

All three beat the untrained baseline *on validation*, which is what made the null result on
test worth reporting rather than assuming.

## 4. Test-set result — the two configurations that were scored

| Metric | Base (no fine-tune) | FT lr=2e-5 | FT lr=5e-6 (val-best) |
|---|---:|---:|---:|
| Accuracy | **0.6784** | 0.6784 | 0.6533 |
| NEUTRAL recall | **0.7396** | 0.7188 | 0.6562 |
| Macro-F1 | **0.6625** | 0.6586 | 0.6417 |
| POSITIVE F1 | 0.6726 | 0.6885 | — |
| NEGATIVE F1 | 0.5977 | 0.5647 | — |
| McNemar vs base | — | b=9, c=9, **p = 1.00** | b=6, c=11, p = 0.332 |

**The base model wins or ties on every metric.**

At lr=2e-5 the fine-tune changed 18 of 199 predictions and got exactly 9 better and 9 worse —
a perfectly symmetric result, which is what pure noise looks like. At the learning rate that
looked best on validation, test accuracy *fell* by 2.5 points.

## 5. Why it failed — overfitting, visible in the loss curve

| Epoch | Train loss | Val macro-F1 |
|---:|---:|---:|
| 0 | — | 0.5754 |
| 1 | 0.841 | **0.6103** |
| 2 | 0.542 | 0.5470 |
| 3 | 0.310 | 0.5863 |
| 4 | 0.135 | 0.5722 |
| 5 | 0.056 | 0.5662 |
| 6 | 0.041 | 0.5662 |

Training loss falls by 95% while validation macro-F1 peaks at epoch 1 and then declines. The
model is memorising 320 examples, not learning the task. Early stopping caught this — that is
why the adopted checkpoint was epoch 1 — but stopping early only limits the damage; it does
not manufacture a gain that the data cannot support.

## 6. Conclusion, and the contrast that makes it useful

**400 in-domain examples were not enough. 1,000 were.**

| Channel | Training rows | Held-out gain |
|---|---:|---|
| Comments | 1,000 | 69.3% → **78.7%** (p = 0.007) |
| Transcripts | 400 | 0.6784 → **0.6784** (p = 1.00) |

This is a more informative pair of results than either alone. The comment result shows the
fine-tuning procedure in this project works and is correctly implemented. The transcript
result shows it is *data-limited*, not method-limited — the same script, the same
hyperparameter discipline and the same base-model family produced a clear gain at 1,000 rows
and nothing at 400.

This is evidence about the cost of supervision rather than a failed experiment. It sets a
practical threshold for future channels: **budget closer to 1,000 labels than 400 before
expecting a fine-tune to pay.**

## 7. What was kept, and what was not

- **Not adopted.** `pipeline/audio_module.py` is unchanged and still loads the base model.
- **Weights deleted.** Three checkpoints at 1.1 GB each were produced and removed. They are
  reproducible from `finetune_transcript.py` at seed 42 — verified by re-running both reported
  configurations and obtaining identical numbers. The script and the labels are the artefact;
  the weights are not.
- **Evidence kept**: `analysis/finetune_lr2e-05_ep6.json` and
  `analysis/finetune_lr5e-06_ep6.json`, including every per-segment prediction for both the
  base and fine-tuned models.

## 8. Threats to this conclusion

- **The holdout has now been scored three times** — once to confirm the base model
  (`WINNER.md` §7) and twice here. None of the three was used to *select* anything, so it
  remains unbiased in the sense that matters, but repeated use erodes that guarantee and the
  count is recorded rather than forgotten. It should not be scored again without a reason.
- **One learning-rate family, one architecture, six epochs.** Layer freezing, class-weighted
  loss and longer schedules were not tried. The claim is "this did not work at 400 rows", not
  "no fine-tune can work at 400 rows".
- **The 80-segment validation set is small**, so validation macro-F1 is noisy — which is
  itself part of why the validation-best configuration lost on test.
- **Single rater**, so the ceiling on any supervised gain is set by one person's consistency.

## 9. If this is revisited

The cheapest route to a real answer is **more labels, not more hyperparameters**. 1,333
eligible segments in the corpus remain unlabelled (1,932 eligible, 599 labelled). Adding ~600 to reach the ~1,000 that worked
for comments is roughly 1.5–2 hours of labelling, and would test the data-limited hypothesis
directly.
