# The facial channel, cut by speaker

**12 Sep 2026.** Pre-registered in `PROTOCOL.md` before any number below was
computed; one amendment, A1, appended after the primary output and labelled
post-hoc everywhere it appears.

Every figure here is re-derived from disk by `verify_claims.py`.

---

## 1. Why this exists

This project attaches `BIAS_CAVEAT` to every report. It says facial emotion
recognition has documented accuracy disparities across skin tone and gender,
citing Buolamwini and Gebru (2018).

The citation is real. **The check on our own data had never been done.** This
bench does the half of it that can be done without human raters, and sets up the
half that cannot.

- **Q1 — does accuracy vary by speaker?** Answered below.
- **Q2 — does that variation track skin tone?** **Not run.** §6.

---

## 2. It reproduces the bench it re-cuts

Before any new claim, the method had to land on numbers already published.
Pooling this bench's per-speaker table back up:

| | This bench | `facial_bench/v2/` as published |
|---|---|---|
| Deployed `deepface_fer`, holdout | **34.2%** | 34.2% |
| Always-NEUTRAL constant, holdout | **67.5%** | 67.5% |
| Holdout frames | **114** | 114 |

Exact, to the decimal, on both models and the frame count. The ground-truth
mapping and the abstention rule are not re-implemented here — `per_speaker.py`
imports `facial_bench/v2/ground_truth_v2.py` and uses it directly, which is why
they agree.

320 frames carry a readable expression across 8 speakers.

---

## 3. Q1 — the primary result

### 3.1 The deployed model

| Speaker | Split | n | Accuracy | 95% CI | NEG on neutral |
|---|---|---|---|---|---|
| ShortCircuit | holdout | 29 | **27.6%** | [14.7, 45.7] | 13.6% |
| Jeremy Fragrance | holdout | 36 | 30.6% | [18.0, 46.9] | 50.0% |
| Dave2D | holdout | 27 | 37.0% | [21.5, 55.8] | 47.6% |
| Marques Brownlee | dev | 82 | 41.5% | [31.4, 52.3] | 26.8% |
| Seth Fowler | dev | 19 | 42.1% | [23.1, 63.7] | 18.2% |
| The Tech Chap | holdout | 22 | 45.5% | [26.9, 65.3] | 10.0% |
| Mrwhosetheboss | dev | 81 | 51.9% | [41.1, 62.4] | 31.2% |
| Jon Adams | dev | 24 | **58.3%** | [38.8, 75.5] | 30.0% |

Pooled **42.8%** — dev 47.6%, holdout 34.2%.

Best minus worst: **30.7 points**.

**This is not a finding, and `PROTOCOL.md` §5.3 said so in advance.** The Wilson
intervals of the best and worst speaker overlap heavily ([14.7, 45.7] against
[38.8, 75.5]). At roughly 40 frames per speaker, a 30.7-point spread is
consistent with noise.

A naive fairness pass would stop here, report "a 30.7-point disparity across
speakers", and imply the model produces it. That claim is exactly what the
pre-registered interval rule exists to refuse.

### 3.2 The constant, which is the reason it is not a finding

| Speaker | Neutral base rate = constant's accuracy |
|---|---|
| Mrwhosetheboss | 39.5% |
| The Tech Chap | 45.5% |
| Seth Fowler | 57.9% |
| Jeremy Fragrance | 66.7% |
| Marques Brownlee | 68.3% |
| ShortCircuit | 75.9% |
| Dave2D | 77.8% |
| Jon Adams | 83.3% |

Range **43.8 points**, and here the intervals **do not** overlap
([29.6, 50.4] against [64.1, 93.3]).

So the larger, statistically clearer per-speaker spread belongs to a model that
has no inputs at all. The always-NEUTRAL constant's accuracy for a speaker is
just the share of that speaker's frames a human called neutral — **a measure of
how still a presenter's face is**, and nothing whatever about a classifier.

Any per-speaker reading of §3.1 that ignores this is measuring presenters and
calling it bias.

---

## 4. A1, post-hoc — the quantity a fairness question actually wants

Declared in `PROTOCOL.md` amendment A1 after seeing §3 and before writing this:

    lift = accuracy(deployed) − accuracy(always-NEUTRAL constant)

Same speaker, same frames. It separates *this speaker is hard for everything*
from *this speaker is hard for this model*.

| Speaker | Split | n | Deployed | Constant | Lift |
|---|---|---|---|---|---|
| ShortCircuit | holdout | 29 | 27.6% | 75.9% | **−48.3** |
| Dave2D | holdout | 27 | 37.0% | 77.8% | −40.8 |
| Jeremy Fragrance | holdout | 36 | 30.6% | 66.7% | −36.1 |
| Marques Brownlee | dev | 82 | 41.5% | 68.3% | −26.8 |
| Jon Adams | dev | 24 | 58.3% | 83.3% | −25.0 |
| Seth Fowler | dev | 19 | 42.1% | 57.9% | −15.8 |
| The Tech Chap | holdout | 22 | 45.5% | 45.5% | +0.0 |
| Mrwhosetheboss | dev | 81 | 51.9% | 39.5% | **+12.4** |

**6 of 8 speakers are worse off with the model than with the constant**, and the
lift ranges over **60.7 points**.

### 4.1 And it tracks stillness, not identity

Spearman's rho between a speaker's neutral base rate and their lift:
**−0.714**, n = 8 — post-hoc and descriptive, not a test.

The stiller a presenter's face, the more the model loses to doing nothing. That
is the direct consequence of the failure mode `facial_bench/v2/` already named:
this model manufactures negativity, and a still face is precisely what the
constant gets right and a negativity-manufacturing model gets wrong.

### 4.2 Confounded with the split, and not disentangled

Mean lift: **dev −13.8, holdout −31.3**.

Three of the four worst-served speakers are holdout and three of the four
best-served are dev. `facial_bench/v2/` already established that this model
collapses on unseen speakers, so per-speaker differences here are confounded
with a dev/holdout effect that has nothing to do with who the speaker is.

**With four speakers per split, this bench cannot separate the two**, and does
not try. Stated rather than glossed.

---

## 5. What Q1 answers

- **Does per-speaker accuracy vary?** Yes — 27.6% to 58.3%. **But not
  distinguishably from noise** at this sample size, by the rule set in advance.
- **Is the model evenly bad?** No. It is worse than doing nothing for 6 of 8
  speakers, over a 60.7-point range.
- **Why?** Most of it is explained by how expressive each presenter is
  (rho −0.714, n=8, post-hoc), plus a dev/holdout effect this sample cannot
  separate.
- **Is that unfairness?** **Unknown, and not claimed.** Nothing here connects
  any of it to any protected characteristic. That is Q2.

---

## 6. Q2 — not run, and what it needs

The materials are on disk: `facial_bench/v2/crops/` holds **362 aligned face
crops**, the exact pixels every model scored, across the same 8 speakers.
`PROTOCOL.md` §4 sets out the method — **Monk** scale rather than Fitzpatrick,
rated per speaker rather than per frame, three independent raters, Krippendorff's
alpha reported whatever it is, and the analysis declared inconclusive if alpha
falls below 0.6.

The instrument is built and ready: `monk_rating.html`, opened in a browser,
showing one speaker's crops at a time.

It is not run because it needs three people, and the three available are
non-expert and not diverse in the way this particular judgement requires. That
is a limitation of the study, pre-registered in §6 of the protocol — not a
reason to leave the instrument unwritten.

**Until it runs, this project continues to cite a skin-tone disparity it has not
observed on its own data.** That sentence belongs in the report.

---

## 7. What this bench does not show

- **Not** that the system is fair. It cannot.
- **Not** that the system is biased by skin tone. Q2 is unrun.
- **Not** that eight professional presenters represent anyone. n=8, all filming
  themselves in good light with good audio, in English.
- **Not** a per-speaker disparity that survives its own confidence intervals.

## 8. What it does show

That the deployed facial model is **worse than doing nothing for three quarters
of the speakers in this corpus**, that its disadvantage is concentrated on the
speakers who move their faces least, and that the obvious per-speaker fairness
number — a 30.7-point spread — dissolves once the base rate is accounted for.

The channel's problem in this corpus is not that it treats speakers differently.
It is that it is worse than a constant for most of them, and the one measurement
that looked like a disparity was mostly measuring how still people sit.

---

## 9. Reproducing this

```bash
cd brandpulse_ai
source .venv/bin/activate
python research/fairness_bench/per_speaker.py     # writes per_speaker.json
python research/fairness_bench/verify_claims.py   # re-derives every number above
```

No network, no models, no Ollama. It reads `facial_bench/v2/` and nothing else.
