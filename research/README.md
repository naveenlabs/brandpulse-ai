# Research: how each model was chosen

Every model in the pipeline was measured against its alternatives on this project's own data, using
the bench method in the root README ("How the models were chosen"). Each folder holds one study: its
protocol and write-up as Markdown, the code that ran it, and the cached results the write-up is
checked against. None of it runs when the application runs.

| Folder | What it tested | Outcome in the pipeline | Main write-up |
|---|---|---|---|
| `comment_bench/` | Comment sentiment models against human labels, then a fine-tune (`v2/`) | fine-tuned `cardiffnlp/twitter-roberta-base-sentiment-latest` | `v2/HUMAN_GROUND_TRUTH_EVALUATION.md`, `v2/FINETUNE_RESULT.md`, `v2/holdout/HOLDOUT_RESULT.md` |
| `transcript_bench/` | Transcript sentiment models | `cardiffnlp/twitter-xlm-roberta-base-sentiment` | `TRANSCRIPT_MODEL_ANALYSIS.md`, `WINNER.md` |
| `whisper_bench/` | Whisper sizes against word error rate | Whisper `large-v3-turbo` | `WHISPER_MODEL_ANALYSIS.md` |
| `vocal_bench/` | Vocal emotion models, per-speaker normalisation, the down-weighting fix | audeering dimensional model, read on arousal, down-weighted | `VOCAL_MODEL_ANALYSIS.md`, `SPEAKER_NORM_RESULT.md`, `DAMPING_FIX_RESULT.md` |
| `facial_bench/` | Face detectors and emotion models against hand-labelled frames (`v2/`: held-out speakers) | YuNet detector; no emotion model adopted, channel down-weighted | `FACIAL_MODEL_ANALYSIS.md`, `v2/FACIAL_MODEL_ANALYSIS_V2.md` |
| `fairness_bench/` | The facial channel cut by speaker | a documented limitation | `FAIRNESS_ANALYSIS.md` |
| `controller_bench/` | Local language models as the controller, against rule and constant baselines | `llama3.1:8b` | `CONTROLLER_MODEL_ANALYSIS.md` |
| `baseline_bench/` | Whether comparing four channels beats reading the transcript, against human raters | a documented limitation | `BASELINE_ANALYSIS.md`, `BASELINE_RATER_ANALYSIS.md`, `AXIS_RESULT.md` |

## Checking the numbers

Every number in a write-up is re-derived from the cached results by that study's checker. Run them
from the repository root; none loads a model or uses the network:

```bash
python research/transcript_bench/verify_claims.py
python research/whisper_bench/verify_claims.py
python research/vocal_bench/verify_claims.py          # also verify_ab, verify_speaker_norm, verify_damping_fix
python research/facial_bench/v2/verify_claims.py
python research/fairness_bench/verify_claims.py
python research/controller_bench/verify_claims.py
python research/baseline_bench/verify_bench_claims.py # also verify_axis_claims, verify_claims, verify_page
```

Two checkers do not pass on the repository as it stands (27 Sep 2026):
- `facial_bench/verify_claims.py` needs a saved report that is no longer in `outputs/`, and says so.
- `baseline_bench/verify_claims.py` reports that one quoted sentence is no longer found in
  `evaluation/user_pilot/PILOT_FINDINGS.md`.

Re-running a study itself (not its checker) needs the downloaded media in `data/`, which is not in
the repository, and in most cases the models; each protocol says what it needs.
