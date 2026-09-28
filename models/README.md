# Local model weights

## `comment_sentiment_ft/`

Fine-tuned `cardiffnlp/twitter-roberta-base-sentiment-latest`, adopted 30 Aug 2026 as the
comment-sentiment model in `pipeline/comment_module.py`.

**Provenance.** Trained on 1,000 comments hand-labelled by the project author
(`comment_bench/v2/train/train_sheet.csv`), 799 train / 201 validation, epoch 4 selected on
validation macro-F1. Produced by `comment_bench/v2/finetune_cardiffnlp.py`, seed 42; two runs
in the environment it was trained in gave identical results, but a retrain with newer package
versions does not reproduce it (measured below).

**Evidence.**

| | Base | Fine-tuned |
|---|---:|---:|
| Original test set (350 human labels, seen videos) | 71.3% | 74.3% (p = 0.272) |
| NEGATIVE recall, same set | 0.493 | 0.672 (p = 0.012) |
| Held-out videos (150 human labels, unseen) | 69.3% | **78.7% (p = 0.007)** |
| NEGATIVE recall, held-out | 0.368 | 0.632 (5 fixed, 0 broken) |

Full write-ups: `comment_bench/v2/FINETUNE_RESULT.md`,
`comment_bench/v2/holdout/HOLDOUT_RESULT.md`.

**Not committed to git.** The folder is 502 MB, of which `model.safetensors` is 498,615,900
bytes, and GitHub refuses files over 100 MB. `comment_sentiment_ft.sha256` beside this file
records the SHA-256 of each of the four files. Install the model one of two ways.

*Exact adopted weights* (the model every recorded result used). The archive is published as
a release asset; `install_comment_model.py` downloads it, checks all four hashes and
installs nothing unless every one matches:

    python models/install_comment_model.py --url <archive URL>
    python models/install_comment_model.py --from-dir <folder holding the four files>
    python models/install_comment_model.py --check        # prints whether it is the adopted model

The author builds that archive from a verified install with
`python models/install_comment_model.py --pack comment_sentiment_ft.zip`.

*Retrained from this repository's own labels* (no archive needed; the base checkpoint is
downloaded from the Hugging Face hub):

    python research/comment_bench/v2/finetune_cardiffnlp.py --install

This re-runs the bench: it rewrites `comment_bench/v2/analysis/finetune_result.json` and
`comment_bench/v2/finetuned/` before installing. Hashes are not checked on this route, because
a retrain is not guaranteed to be byte-identical (MPS kernels are not bit-reproducible, as the
script's header notes), so `--check` does not report a retrained model as the adopted one.

Measured on 26 Sep 2026, in a fresh environment built from `requirements-dev.txt` (torch 2.14,
transformers 5.17, Apple M1 Pro, MPS): the retrain took 5 min 3 s, selected epoch 2 where the
adopted run selected epoch 4, and scored 113 of 150 (75.3%) on the held-out videos, against the
adopted model's 118 of 150 (78.7%). The adopted weights installed by the first route give the
adopted model's labels on all 150 held-out comments, in that same fresh environment.

**Fallback.** If this directory is absent, `pipeline/comment_module.py` falls back to the
base model from the Hugging Face hub and logs a warning that names this file. The pipeline
never fails because the weights are missing, but comment sentiment is measurably weaker, and
a saved report does not record which of the two models produced it.
