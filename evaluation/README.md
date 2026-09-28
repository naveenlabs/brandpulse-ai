# Evaluation: people, the written report, and the interface

How the finished system was evaluated: two rounds of user testing, the quality of the written
report, and checks of the running interface. Commands run from the repository root.

| Folder | What it holds |
|---|---|
| `user_pilot/` | The pilot study (3 participants, named Participant A to C): questions, findings, consent note, and screenshots of the interface before and after the changes it led to |
| `user_eval/` | The final evaluation (5 participants, P1 to P5): the protocol and answer key, the scores, the changes made afterwards, and the form participants used (`form/`) |
| `analyst/` | How well the written report holds up: `ANALYST_EVALUATION.md`, produced by `evaluate.py` from the stored analyses |
| `ui_evidence/` | Checks of the running interface: the browser harness (`verify_ui.py`), the mutation check that tests notice breakage (`verify_tests_bite.py`), hostile saved files (`verify_hostile_files.py`), contrast over the animated grounds (`measure_grounds.py`), the screen-reader script, and colour-vision screenshots |

**One file here is read by the running site.** `ui_evidence/figures.json` supplies the figures on
the opening page (served at `/evidence/figures.json`) and the channel accuracies the written report
quotes. `python evaluation/ui_evidence/extract_figures.py` rebuilds it from `outputs/` and checks
every quoted accuracy against its source in `research/`; re-run it after adding or deleting a report.

**What is not here.** Individual participants' responses, and the real names behind the pilot's
pseudonyms, stay on the author's machine and are ignored by git. `user_eval/SCORES.md` is produced
by `python evaluation/user_eval/score.py` from those responses, so it cannot be regenerated from the
repository alone; it says so when they are missing.

```bash
python evaluation/analyst/evaluate.py             # rewrites analyst/ANALYST_EVALUATION.md and evaluation.json
python evaluation/ui_evidence/verify_ui.py        # needs the server on port 5057; see the root README, "Tests"
python evaluation/user_eval/build_single.py       # the evaluation form as one self-contained page (not committed)
```
