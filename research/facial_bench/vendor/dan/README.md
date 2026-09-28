# Vendored third-party code — facial bench

## `dan/` — DAN (Distract your Attention Network)

`dan.py` and `LICENSE` are copied verbatim from <https://github.com/yaoing/DAN>
(MIT, Copyright (c) 2021 Zhengyao Wen), retrieved 03 Sep 2026. Nothing in them is
modified; the bench imports the `DAN` class and supplies its own preprocessing.

`affectnet8_epoch5_acc0.6209.pth` is the repository's released AffectNet-8
checkpoint, downloaded from the Google Drive link its README gives. The repository
reports 62.09 per cent on AffectNet-8 for this checkpoint.

**Why it is vendored rather than pip-installed.** DAN publishes no package and
hosts its weights on Google Drive, so there is no pinned, programmatic install
path. Vendoring the two files makes the bench re-runnable without a manual
download step and records exactly which revision was measured.

**Why DAN is in the bench at all.** It is the only candidate with independent
third-party evaluation on *naturalistic* footage: Fernandes et al. (2026,
Frontiers in Artificial Intelligence, 10.3389/frai.2026.1800342) compared eleven
FER systems and found DAN trained on AffectNet the strongest traditional model on
their two dynamic, lower-quality corpora. That is a published result on their
data external to this project. It justifies including DAN as a candidate but does
not establish its performance on this project's data.

**One modification to how it is used.** `DAN.__init__(pretrained=True)` reads a
local `./models/resnet18_msceleb.pth` that the repository does not ship. The bench
constructs it with `pretrained=False` and then loads the released checkpoint,
which contains all the weights. `candidates.py` asserts the state dict loads with
no missing or unexpected keys, so a silent partial load fails instead of scoring.
