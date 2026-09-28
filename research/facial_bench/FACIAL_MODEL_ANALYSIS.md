# Facial Emotion Channel — Model Evaluation and Findings

**Run 03 Sep 2026.** Protocol pre-registered in `CANDIDATE_MODELS.md`, written and
fixed before any candidate was scored. Every number below is measured on this
project's own frames and is re-derived by `verify_claims.py`.

The facial channel was the last unbenched channel in the system
(the bench method (README)). It is also the worst-evidenced: `PROTOTYPE_FINDINGS.md` §9
measured a ~79 per cent segment-level error rate on one video and §12D
reproduced the failure on a second, but neither compared the deployed model
against a single alternative.

---

## 1. What was actually done

Nine emotion models and six face detectors, on this project's own footage,
against the author's own frame-by-frame review as ground truth.

The bench is split in two, and that split is the main design decision. §9 and
§12D document two failures that no single swap can fix:

- **Detection.** Confident emotions returned on frames containing no human being.
- **Classification.** Low-affect negatives on faces that are not negative.

Changing the emotion model cannot fix the first — the emotion head is being handed
a photograph of a shoe. Changing the detector cannot fix the second — the face was
found correctly. So detectors are scored on face presence (**Bench A**), and every
emotion model is scored on **byte-identical crops** cut by one fixed detector
(**Bench B**), so a difference between two classifiers is a property of the
classifier and nothing else.

`pipeline/visual_module.py` couples the two and cannot express the distinction.
That coupling is itself a finding.

---

## 2. Ground truth

`ground_truth.py`, a machine-readable transcription of `PROTOTYPE_FINDINGS.md` §9
— the author's own visual review of all 77 segments of `1VjPETN3m6U`, made against
the frames and independently of every model here, the incumbent included.

| | n | Where it comes from |
|---|---|---|
| Face presence, every segment | **77** | §9's four categories, which partition all 77 |
| — no human face | 20 | 15 tabulated false positives + the 5 §9 counts as correct-no-face |
| — real face present | 57 | §9's "Match" and "Mismatch" both open "A real face is present" |
| Expression, three-class | **44** | the segments §9 describes in prose |
| — individually tabulated (`explicit`) | 7 | |
| Expression class balance | 38 NEUTRAL / 6 POSITIVE / **0 NEGATIVE** | |

Thirteen segments have a verified face but no verified expression: **ten of §9's
eleven "Match" segments** — a real face, with DeepFace's label judged reasonable —
and **three mismatches §9 counts but never tabulates individually**. They are
**excluded from the expression bench on purpose**. For the ten matches the only
expression evidence is that the incumbent was right, and scoring on them would
define the ground truth by the incumbent being right. They are not discarded: §8
counts them as *unknown* and reports an interval rather than guessing.

### 2.3 The expression sample is selected on the incumbent's errors

**The most serious methodological problem in this bench, and it was found before
the classification results were read.**

§9's Failure Mode B tables exist to document the incumbent's mistakes. So the 44
expression labels are **43 of §9's 46 mismatches plus exactly one of its 11
matches**. The sample is selected on the incumbent being wrong.

Scoring the incumbent on it is therefore close to guaranteed to return near zero,
and it does: **1 of 44, 2.27 per cent**, with **38 of 38** verified-neutral
segments called NEGATIVE. *That number is not the channel's accuracy and is never
quoted as one in this document.*

Three consequences, all applied:

1. The pre-registered Bench B rule — "detectably better than the incumbent" — is
   trivially satisfiable and was **withdrawn** (Amendment A5). The bar is the
   always-NEUTRAL floor instead.
2. The comparison **among the eight challengers is unbiased**: none of them
   influenced which segments §9 chose to write about. Only the incumbent's row is
   compromised.
3. The primary end-to-end number is §8's composite over **all 77** segments, which
   is not selected on anyone's errors and reproduces §9's own published figure.

### 2.1 The zero-NEGATIVE limitation, stated before the results

There are **no NEGATIVE segments in the expression ground truth**. §9 found this
reviewer never displayed a negative expression. So this bench can measure a model
*inventing* negativity that is not there, and **cannot** measure a model *missing*
negativity that is. Every claim in §7 is bounded by that, and no claim is made
about any model's ability to detect genuine anger.

### 2.2 The transcription is checked, not trusted

`anchor_check()` re-reads the saved run §9 analysed and refuses to release a single
label unless every transcribed label and confidence matches it, the segment count
is 77, §9's four category counts sum to 77, and the derived partition reproduces
them.

It caught an error on its first run. §9 lists **segment 39** in its `fear` row; the
saved run labels it `angry`, confidence 0.4646. §9's own stated ranges settle it:
the `angry` row says *0.46–0.95* and only segment 39 supplies the 0.46, while the
`fear` row's *0.40–0.70* is reproduced exactly once segment 39 is removed. Both
rows describe a neutral visible expression, so **no result changes** — only the
tier improves. Corrected in §9 with a dated note, and recorded as Amendment A1.

---

## 3. Two anchors had to pass before anything was scored

### 3.1 The pipeline reproduces itself exactly

`anchor_pipeline.py` runs `pipeline.visual_module` unmodified over the same 572
frames with the same segment boundaries and compares against the saved run from
June.

| | |
|---|---|
| Segment labels reproduced | **77 / 77 (100.0%)** |
| Confidences reproduced | **77 / 77 (100.0%)** |
| Frames with a detected face | 363 / 572 |
| Runtime | 397 s, 0.694 s/frame at 3840×2160 |

The channel is deterministic, and §9's ground truth still describes the code as it
stands three months later. This is a **system test** in the project's testing vocabulary:
real module, real frames, real windows, no mocks.

### 3.2 The bench reproduces §9's false positives segment for segment

The bench's own `opencv` sweep, pooled with the pipeline's rule, marks these
faceless segments as containing a face:

```
bench:  [1, 4, 6, 9, 10, 11, 13, 17, 22, 24, 25, 30, 31, 41, 57]
§9:     [1, 4, 6, 9, 10, 11, 13, 17, 22, 24, 25, 30, 31, 41, 57]
```

Set-identical — not merely the same count — and it fires on **none** of §9's five
correct-no-face segments (16, 49, 64, 65, 68). That simultaneously validates the
harness and the one part of the ground truth that was *derived* rather than
transcribed.

### 3.3 The anchor caught the bench running the wrong configuration

Comparing the anchor frame by frame against the bench's first `opencv` sweep showed
them disagreeing on **28 of 572 frames**. The cause was the `align` flag:
`visual_module` reaches the detector through `DeepFace.analyze`, which aligns by
default, and the bench had called `extract_faces(align=False)`. Re-running the 28
differing frames with `align=True` matched the pipeline on **28 of 28**.

This is not a cosmetic flag. Reading deepface 0.0.100's source, `align=True` pads
the image with a black border of **half its height and width on every side** before
the detector runs — so a 3840×2160 frame is presented as 7680×4320 and the face
occupies **a quarter of the area** it otherwise would.

Two consequences:

1. Bench A would have measured an `opencv` the product does not run.
2. Bench B would have handicapped every classifier equally, since all nine are
   trained on aligned crops.

**The entire sweep was discarded and re-run with `align=True`.** No number measured
before that point appears anywhere in this document. Recorded as Amendment A3.

---

## 4. The incumbent's safety gate does nothing

`visual_module.FACE_CONFIDENCE_THRESHOLD = 0.50` exists to reject frames where
DeepFace is not confident a real face is present. Measured over the 415 detections
the aligned sweep produces on this video:

| | |
|---|---|
| Lowest face confidence returned | **0.88** |
| Highest | **1.01** |
| Detections the 0.50 gate rejects | **0 of 415** |

The gate has never rejected anything on this footage. It cannot: the distribution
starts far above it. The maximum exceeding 1.0 also shows this "confidence" is not
a probability — it is derived from the cascade's neighbour count.

§9's proposed fix 1 was to raise this threshold. Measured, on the pipeline's own
pooling rule:

| Gate | False positives (of 20) | Recall (of 57) | Accuracy |
|---|---|---|---|
| 0.50 (deployed) | 15 | 57 | 80.5% |
| 0.94 | 14 | 57 | 81.8% |
| 0.96 | 11 | **48** | 74.0% |
| 0.98 | 6 | **25** | 50.6% |

The threshold has almost no discriminative range. The best attainable point buys
**1.3 accuracy points**, and one step beyond it starts destroying real faces faster
than it removes false ones. **§9's first proposed fix does not work, and this is
the measurement that retires it.**

---

## 5. Frustration and disappointment are not in any model's vocabulary

This section answers the project's own standing observation — *anger and
frustration are rarely detected strongly, while disappointment-like readings
appear far more often* — and it starts with the part that needs no measurement at
all, because it is a property of the entire available model space.

### 5.1 Eight concepts, and none of them is the one you want

Every candidate's class list, taken from its own `config.json`, its source, or its
model card:

| Candidate | Classes |
|---|---|
| `deepface_fer` (incumbent) | angry, disgust, fear, happy, sad, surprise, neutral |
| `trpakov_vit` | angry, disgust, fear, happy, neutral, sad, surprise |
| `motheecreator_vit` | anger, disgust, fear, happy, neutral, sad, surprise |
| `dima806_vit` | sad, disgust, angry, neutral, fear, surprise, happy |
| `tanneru_beit_large` | anger, disgust, fear, happy, neutral, sad, surprise |
| `hardlyhumans_vit` | anger, **contempt**, disgust, fear, happy, neutral, sad, surprise |
| `dan_affectnet8` | neutral, happy, sad, surprise, fear, disgust, anger, **contempt** |
| `emotieffnet_b0_va` | anger, **contempt**, disgust, fear, happiness, neutral, sadness, surprise |
| `emotieffnet_b2` | anger, **contempt**, disgust, fear, happiness, neutral, sadness, surprise |

Across all nine, the union is **eleven distinct strings denoting exactly eight
concepts**: anger, contempt, disgust, fear, happiness, neutral, sadness, surprise.
`angry`/`anger`, `sad`/`sadness` and `happy`/`happiness` are the same class spelled
differently. Every one of the nine is Ekman's six plus neutral, optionally with
contempt.

**Not one of them can emit `frustration`, `disappointment`, `confusion` or
`boredom`.** Verified across every candidate by `verify_claims.py`.

This is not a gap in the candidate set — it is the shape of the whole
publicly-available FER model space. Frustration and disappointment are *appraisal*
states: they are about a mismatch between what someone expected and what they got.
They have no canonical facial prototype in this taxonomy, so a model can only
express them by borrowing one that does — frustration through anger or disgust,
disappointment through sadness.

**A reviewer who is disappointed by a product cannot be labelled disappointed by
any model available to this project.** That belongs in the report as a structural
finding about the channel, not as a failure of any particular model.

### 5.2 Why it lands on "sad" specifically

The affective-computing literature treats frustration as its own problem for
exactly this reason. Grafsgaard et al. (2013) related **AU4**, the brow lowerer, to
frustration in a learning context without reporting classification metrics for it.
AU4 is also a component of the canonical **anger** prototype *and* of the canonical
**sadness** prototype.

So a reviewer who is concentrating and mildly critical — brow slightly lowered,
otherwise still — is genuinely ambiguous between anger, sadness and neutral for any
classifier trained on this taxonomy. Which of the three it lands on is a fact about
the model's decision boundary and its training distribution, **not a fact about the
speaker**.

That is the mechanism behind the observation. It also predicts the failure should
be *unstable across speakers* rather than consistently biased in one direction —
which is exactly what §8 measures.

### 5.3 The training corpora make it worse in a specific direction

FER-2013 contains 35,887 images with **547 disgust** against **8,989 happy** — the
smallest class is 1.5 per cent of the set. AffectNet is likewise skewed towards
happy and neutral. A model trained on either has weak, poorly-calibrated decision
boundaries precisely where low-intensity negative affect lives.

Six of the nine candidates are trained on FER-2013 or a mixture containing it;
three (`dan_affectnet8`, both `emotieffnet` models) are AffectNet-only. That split
is what makes the comparison in §8 informative rather than merely descriptive.

Py-Feat's own published AffectNet F1 scores for the ResMaskNet it bundles make the
same point from outside this project: **happy .77**, but **anger .53, sadness .54,
fear .48, neutral .49**, average **.55** (Cheong et al., 2023). The best
research-grade toolbox in this space reports its negative and neutral classes at
roughly half the quality of its happy class.

### 5.4 What this bench can and cannot say about it

**Can:** measure how often each model *invents* anger or sadness on faces the
author verified as neutral, measure whether anger is present in the probability
distribution and merely losing the argmax, and measure whether AffectNet-trained
candidates behave differently from FER-2013-trained ones.

**Cannot:** say anything about detecting *genuine* anger. §2.1 gives the reason —
the expression ground truth contains zero NEGATIVE segments, because this reviewer
never displayed one. Any claim that a model "misses real anger" would be
unsupported by this data, and none is made.

---

## 6. Bench A — which detector finds faces on this footage

Six detectors, every frame of the ground-truth video, at 3840×2160 with
`align=True` because that is what the pipeline does (§3.3). Scored against the
face-presence ground truth for all 77 segments.

**Both pooling modes are reported, because they answer different questions.**
`midpoint` scores the detector at the single frame §9 actually opened, so it is the
*valid* comparison. `any` is the pipeline's own rule — a segment has a face if any
frame in its window does — so it is the *deployment-relevant* one. Amendment A2
records that the midpoint mode was added post hoc, and why.

### 6.1 At the midpoint frame — the unit the ground truth was observed at

| Detector | False positives (of 20) | Recall (of 57) | Accuracy | 95% CI | s/frame | Minutes per video | vs incumbent |
|---|---|---|---|---|---|---|---|
| `mtcnn` † | **0** (0.0%) | 54 (94.7%) | **96.1%** | [0.892, 0.987] | 4.637 | **44.2** | **better, p=0.0078** |
| `yolov8n` | 1 (5.0%) | **55 (96.5%)** | **96.1%** | [0.892, 0.987] | 0.113 | 1.1 | **better, p=0.0215** |
| `retinaface` | 1 (5.0%) | 54 (94.7%) | 94.8% | [0.874, 0.980] | 1.137 | 10.8 | **better, p=0.0391** |
| `yunet` | **0** (0.0%) | 52 (91.2%) | 93.5% | [0.857, 0.972] | **0.062** | **0.6** | better, p=0.0703 |
| **`opencv`** (incumbent) | 1 (5.0%) | 47 (82.5%) | 85.7% | [0.762, 0.918] | 0.433 | 4.1 | — |
| `ssd` | **0** (0.0%) | **29 (50.9%)** | 63.6% | [0.525, 0.735] | 0.077 | 0.7 | **worse, p=0.0002** |
| *always-face* | 20 (100%) | 57 (100%) | 74.0% | — | — | — | worse |
| *never-face* | 0 (0%) | 0 (0%) | 26.0% | — | — | — | worse |

† `mtcnn` costs 4.6 s/frame at these settings, so it was run on the 77 midpoint
frames only. It has a complete midpoint score and **no pooled score at all**, by
design rather than by omission (Amendment A4).

**The four leading detectors are statistically indistinguishable from each other.**
Every pairwise exact McNemar among `mtcnn`, `yolov8n`, `retinaface` and `yunet`
returns p ≥ 0.5 on 1–4 discordant segments. They are one group, and every member of
it is clearly better than the incumbent. The choice among them is a cost and risk
decision, not an accuracy one — which is what makes the 75-fold spread in the
minutes-per-video column the operative number.

### 6.2 Under the pipeline's own pooling rule

| Detector | False positives (of 20) | Recall (of 57) | Accuracy | vs incumbent |
|---|---|---|---|---|
| `ssd` | **8** (40.0%) | 56 (98.2%) | 88.3% | better, p=0.0703 |
| `yolov8n` | 9 (45.0%) | **57 (100%)** | 88.3% | **better, p=0.0312** |
| `yunet` | 9 (45.0%) | 56 (98.2%) | 87.0% | better, p=0.1250 |
| `retinaface` | 9 (45.0%) | 56 (98.2%) | 87.0% | better, p=0.1250 |
| **`opencv`** (incumbent) | **15** (75.0%) | 57 (100%) | 80.5% | — |

**The incumbent is the worst detector under both modes.** It is the only one that
fires on 15 of the 20 verified-faceless segments, and those 15 are *exactly* §9's
own tabulated false positives (§3.2).

### 6.3 Applying the pre-registered rule, mechanically

§3.5: *adopt the lowest false-positive rate among detectors whose recall is not
detectably worse than the incumbent's; ties on accuracy, then speed.*

| Mode | Eligible | Rule selects |
|---|---|---|
| `midpoint` | `mtcnn`, `yunet`, `yolov8n`, `retinaface` (`ssd` excluded: recall worse, p=0.0000) | **`mtcnn`** |
| `any` | all four measured on the full sweep (no recall difference is detectable) | `ssd` |

**The two modes select different detectors, and that disagreement is itself the
finding**, exactly as Amendment A2 said it would be if it happened.

The disagreement resolves cleanly, and not by preference. Under `any` pooling a
segment counts as having a face if *one* frame in it does, so every detector scores
56–57 of 57 and **the eligibility gate can never fire**. The rule then degenerates
to "lowest false-positive rate", which rewards the detector that detects least —
and `ssd` is exactly that: the midpoint mode shows it missing **half the real
faces** (29 of 57). The `any` mode does not disagree with the midpoint mode about
`ssd`; it is blind to the failure that disqualifies it.

So the midpoint result is decisive, on an argument from the structure of the two
metrics rather than from which answer is more attractive.

### 6.4 The rule selects `mtcnn`. `yunet` was adopted. That is a deviation, and it is declared.

At the midpoint, `mtcnn` and `yunet` tie on the primary metric at 0 of 20 false
positives, so the rule falls to tie-break (a), accuracy over all 77, which picks
`mtcnn` at 96.1 per cent over `yunet` at 93.5.

**That tie-break fires on two segments, and p = 0.5000.** It runs *before*
tie-break (b), speed, ever gets a chance — which is a defect in the rule, visible
only now the numbers exist. The rule is not rewritten to hide it.

`yunet` was adopted instead, on two grounds both fixed **before** `mtcnn`'s accuracy
was known (Amendment A4):

1. **Cost.** 0.6 minutes per video against 44.2. A detector costing five times the
   video's own duration is not an option for a product that analyses videos on
   demand.
2. **Coverage.** `mtcnn` has no pooled score at all. Adopting a candidate measured
   on 77 frames over one measured on 572 would be adopting the less-evidenced
   option.

`yunet` also carries the lowest behavioural risk of the four. Its confidences span
0.90–0.94, so like `opencv` it leaves `FACE_CONFIDENCE_THRESHOLD` inert and the swap
changes exactly one thing. `yolov8n`'s run down to 0.27, which would start that gate
rejecting frames and change two things at once.

Full reasoning in Amendment A6. Every member of the leading group is a strict
improvement on the incumbent, so the documented failure is repaired by any of them.

### 6.5 The false positives are amplified by pooling, not caused by it

The frame-level picture explains the gap between the two tables. Inside the 119
frames that fall in author-verified faceless windows:

| | |
|---|---|
| No detector fires | 90 |
| All fire (unanimous) | 11 |
| **Only the incumbent fires** | **8** |
| Split decision | 10 |

Four of those frames were opened and looked at (a spot check, recorded in
`report_bench.INSPECTED_FRAMES`, **not** part of the author's ground truth):

| Frame | Agreement | §9's description of the segment | What is in the frame |
|---|---|---|---|
| `frame_0291` | unanimous | "Empty desk top-down shot" | a large, clear, front-facing human face |
| `frame_0176` | unanimous | "Phone in hand, b-roll" | a large, clear human face holding a phone |
| `frame_0059` | opencv only | "Phone in hand, b-roll" | a phone over a desk, no face; the camera-lens cluster is visible |
| `frame_0108` | opencv only | "Phone lock screen close-up" | a phone lock screen over a desk, no face |

Four of four behave as predicted. **Unanimous detections in a "faceless" window are
real faces §9 never inspected** — the segment cuts back to the talking head before
it ends. **Incumbent-only detections are genuine hallucinations**, and §9's
hypothesised mechanism — the triple camera-lens cluster presenting the three-blob
geometry of two eyes and a mouth — is visible in `frame_0059`.

The pipeline's `any` rule then turns a single-frame error into a whole-segment one.
Requiring corroborating frames before trusting a detection is §9's proposed fix 5,
and it is a **pooling** change rather than a model change, so it is out of scope for
this bench and named in §12 as separate work.

---

## 7. Bench B — nine emotion models on identical crops

Every candidate on the same 414 crop files, cut once by `retinaface`, scored on the
44 segments with a verified expression. Because those 44 are selected on the
incumbent's errors (§2.3), **the bar is the always-NEUTRAL floor, not the
incumbent**.

| Model | Accuracy | 95% CI | macro-F1 | NEG invented (of 38) | s/crop | vs floor |
|---|---|---|---|---|---|---|
| *always-NEUTRAL* | **86.4%** | [0.733, 0.936] | 0.3089 | 0 | — | — the floor — |
| `trpakov_vit` | **79.5%** | [0.655, 0.888] | **0.4306** | 3 | 0.079 | worse, p=0.4531 |
| **`deepface_fer`** (incumbent) | 56.8% | [0.422, 0.703] | 0.3377 | 14 | 0.014 | worse, p=0.0010 |
| `emotieffnet_b0_va` | 18.2% | [0.095, 0.320] | 0.1333 | 8 | 0.013 | worse, p<0.0001 |
| `motheecreator_vit` | 18.2% | [0.095, 0.320] | 0.1281 | 5 | 0.072 | worse, p<0.0001 |
| `dan_affectnet8` | 13.6% | [0.064, 0.267] | 0.1000 | 8 | 0.026 | worse, p<0.0001 |
| `emotieffnet_b2` | 13.6% | [0.064, 0.267] | 0.1053 | 12 | 0.023 | worse, p<0.0001 |
| `tanneru_beit_large` | 13.6% | [0.064, 0.267] | 0.0816 | 1 | 0.222 | worse, p<0.0001 |
| `dima806_vit` | 9.1% | [0.036, 0.212] | 0.0650 | 7 | 0.070 | worse, p<0.0001 |
| `hardlyhumans_vit` | 4.5% | [0.013, 0.151] | 0.0556 | 22 | 0.068 | worse, p<0.0001 |

**No model beats the constant.** `trpakov_vit` is the only one not *detectably*
worse than it (p=0.4531, 7 discordant pairs), and it is 6.9 points behind.

This is the third channel in this project to produce that result.
`transcript_bench` and `vocal_bench` both found their deployed model losing to a
constant; the facial channel now joins them, and it loses by the widest margin.

### 7.1 The published accuracies are worse than useless

The single most useful thing this bench measured.

| Model | Its own published figure | Measured here |
|---|---|---|
| `hardlyhumans_vit` | 92.2% | **4.5%** |
| `dima806_vit` | 90.9% | **9.1%** |
| `motheecreator_vit` | 84.3% | 18.2% |
| `tanneru_beit_large` | 73.6% | 13.6% |
| `trpakov_vit` | 71.2% | **79.5%** |
| `emotieffnet_b2` | 63.0% | 13.6% |
| `dan_affectnet8` | 62.1% | 13.6% |
| `emotieffnet_b0_va` | 61.9% | 18.2% |
| `deepface_fer` | 57.4% | 56.8% |

**Spearman rank correlation between published and measured accuracy: −0.6214**
(n = 9). Not zero — *negative*. On this project's data the published ranking is
close to inverted, and a reader choosing by model card would have picked the two
worst candidates in the set.

The two models whose cards are most modest — `trpakov_vit` at a credible 71.16 per
cent on FER-2013, and the incumbent at its author's own 57.4 per cent — are the two
that transfer. The three claiming 84–92 per cent, all above published state of the
art on the corpora they name, are three of the four worst.

§4.3 of the register predicted this **before** the measurement, from evidence
visible in the cards themselves: `dima806_vit` reports per-class support of
3595–3596 for every class including disgust, of which FER-2013 contains 547 in
total, and reports F1 0.9954 on it — the signature of augmented copies of the same
images landing in both splits. This is that prediction coming true, measured.

The project's evidence rule says a citation justifies interest in a model and never justifies
choosing one. **This is the number that supports that rule**, and it is
this project's own.

### 7.2 `tanneru_beit_large` is degenerate here, and its label order is not the reason

This candidate publishes `LABEL_0 … LABEL_6` in `config.json` and names the class
order only in its README, so the order had to be verified rather than trusted
(§4.2 of the register).

It predicts `surprise` on **350 of 414 crops (84.5%)** regardless of content. That
could be a degenerate model *or* a wrong label order, and the two were separated by
searching all **5,040** permutations of the seven classes against the consensus of
the other eight candidates:

| | Agreement with consensus |
|---|---|
| The card's stated order | 98 / 176 (55.7%) |
| Best of all 5,040 orders | 99 / 176 (56.2%) |

The best possible permutation beats the card's by **one crop**, and differs from it
only by swapping `neutral` and `sadness`. **No relabelling rescues this model.** The
card's order is correct to within the resolution of the test, and the model is
simply degenerate on this footage.

### 7.3 The dimensional arm does not work here

`emotieffnet_b0_va` also regresses a continuous valence, which is the move that
turned the vocal channel around (`vocal_bench` adopted a dimensional arousal
reading over categorical labels). §3.6 forbids fitting a threshold on this sample,
so it is scored threshold-free: the probability that a randomly chosen POSITIVE
segment carries a higher valence than a randomly chosen NEUTRAL one.

| | |
|---|---|
| Mean valence, POSITIVE segments | −0.0247 |
| Mean valence, NEUTRAL segments | −0.0759 |
| **AUC** | **0.5439** |
| Coverage | 65 of 77 segments |

**0.54 against a chance value of 0.50.** The valence carries essentially no usable
ordering between the two classes present. The design move that rescued the vocal
channel does not transfer, and this is the measurement that says so rather than an
assumption that it would.

---

## 8. The whole channel, end to end

The composite §9 itself reports: for each of the 77 segments, does the channel
return the right thing — no label where there is no face, the right label where
there is one? The 13 segments with a verified face but no verified expression are
counted as unknown, so each arm is an interval.

| Arm | Right | Accuracy range | False faces (of 20) | Wrong labels (of 44) | vs constant |
|---|---|---|---|---|---|
| *`retinaface` + always-NEUTRAL* | **49/77** | **63.6–80.5%** | 9 | 6 | — the floor — |
| `retinaface` + `trpakov_vit` | 46/77 | 59.7–76.6% | 9 | 9 | worse, p=0.4531 |
| `retinaface` + `deepface_fer` | 36/77 | 46.8–63.6% | 9 | 19 | worse, p=0.0010 |
| `retinaface` + `emotieffnet_b0_va` | 19/77 | 24.7–41.6% | 9 | 36 | worse, p<0.0001 |
| `retinaface` + `motheecreator_vit` | 19/77 | 24.7–41.6% | 9 | 36 | worse, p<0.0001 |
| `retinaface` + `dan_affectnet8` | 17/77 | 22.1–39.0% | 9 | 38 | worse, p<0.0001 |
| `retinaface` + `emotieffnet_b2` | 17/77 | 22.1–39.0% | 9 | 38 | worse, p<0.0001 |
| `retinaface` + `tanneru_beit_large` | 17/77 | 22.1–39.0% | 9 | 38 | worse, p<0.0001 |
| `retinaface` + `dima806_vit` | 15/77 | 19.5–36.4% | 9 | 40 | worse, p<0.0001 |
| `retinaface` + `hardlyhumans_vit` | 13/77 | 16.9–33.8% | 9 | 42 | worse, p<0.0001 |
| **`opencv` + `deepface_fer`** (deployed) | **6/77** | **7.8–24.7%** | **15** | 43 | worse, p<0.0001 |
| *`retinaface` + always-POSITIVE* | 17/77 | 22.1–39.0% | 9 | 38 | worse, p<0.0001 |
| *`retinaface` + always-NEGATIVE* | 11/77 | 14.3–31.2% | 9 | 44 | worse, p<0.0001 |

§9's own published figure for the deployed channel — **16 of 77, 20.8 per cent** —
falls inside the deployed arm's interval, at exactly the point where 10 of the 13
unknowns are right. That is the arithmetic identity §3.2 predicted, and it is what
makes every other row on this table comparable to a number already in the project.

**Two things this table settles.**

**The detector is the bigger lever.** Holding the emotion model fixed and changing
only the detector takes the channel from **6/77 to 36/77** — a sixfold improvement
from a component that has nothing to do with emotion. Holding the detector fixed
and changing the emotion model, the best available gain is 36/77 → 46/77.

**Nothing reaches the constant.** The best full pipeline available from nine
models and six detectors is 46/77, and pairing the same detector with a fixed
NEUTRAL label scores 49/77. The gap is not significant (p=0.4531), which is the
honest way to put it: **the best facial-emotion pipeline this project can assemble
is indistinguishable from not running an emotion model at all.**

---

## 9. Where anger actually goes

The project's standing observation — *anger and frustration are rarely detected
strongly, while disappointment-like readings appear more often* — measured rather
than assumed. §5 gives the structural half. This is the empirical half.

All nine candidates on **the same 414 crops of the same face**, so every difference
below is a property of the model and nothing else. No ground truth is used.

| Model | top-1 anger | top-1 sad | top-1 happy | mean anger mass | anger ranked 2nd |
|---|---|---|---|---|---|
| `dima806_vit` | **22.5%** | 13.8% | **57.2%** | 0.1838 | 34.3% |
| `trpakov_vit` | 14.3% | 17.1% | 16.4% | 0.1654 | 33.8% |
| **`deepface_fer`** | 12.6% | 25.4% | 10.9% | 0.1250 | **94.5%** |
| `hardlyhumans_vit` | 11.8% | **46.6%** | **0.0%** | 0.1520 | 24.1% |
| `emotieffnet_b0_va` | 10.4% | 12.8% | 10.9% | 0.1170 | 14.3% |
| `dan_affectnet8` | 10.1% | 19.3% | 1.4% | 0.1072 | 11.8% |
| `tanneru_beit_large` | 6.0% | 5.8% | 0.7% | 0.0985 | 38.6% |
| `emotieffnet_b2` | 3.1% | 15.0% | 5.6% | 0.0798 | 5.7% |
| `motheecreator_vit` | **2.4%** | 18.4% | 13.5% | 0.0481 | 4.2% |

### 9.1 The observation is confirmed, and its cause is not the face

**Sadness beats anger for six of the nine models**, and for the incumbent by two to
one (25.4% against 12.6%). The observed pattern — disappointment-shaped readings
crowding out anger — is real and reproduces across most of the model space.

But look at the spread on identical pixels. Top-1 anger ranges from **2.4% to
22.5%**, a factor of nine. Top-1 sadness ranges from **5.8% to 46.6%**, a factor of
eight. Top-1 happiness ranges from **0.0% to 57.2%**.

One face, one video, one set of crops, and the answer to "how angry is this person"
depends almost entirely on which model is asked. **The label is a property of the
model, not of the speaker.**

That is the same finding `vocal_bench/CANDIDATE_MODELS.md` §1 recorded for the
vocal channel — *a channel whose majority class is determined by which model or
which speaker is talking is not measuring emotion* — now reproduced on the visual
channel with nine models instead of two speakers.

The cross-speaker half is already on record for the incumbent and points the same
way: **26.0 per cent** of segments labelled angry on `1VjPETN3m6U` (20 of 77, from
the saved run), against **0.3 per cent** of real-face frames on `JpN1DQdV4G4`
(1 of 341, `PROTOTYPE_FINDINGS.md` §12D). Same model, same kind of content, a
factor of eighty.

### 9.2 "Rarely detected **strongly**" is exactly right, and it is a decision-rule problem

The most precise result in this section. For the incumbent, **anger is ranked
second on 94.5 per cent of the crops where it is not ranked first**, carrying a mean
probability mass of 0.125.

Anger is not absent from the incumbent's judgement. It is present on almost every
frame and almost always losing. `pipeline/visual_module.py` keeps only
`dominant_emotion` and discards the rest of the distribution, so a signal that is
permanently in second place is thrown away at every frame.

This is the same shape of problem `vocal_bench` found and fixed: a continuous
reading carried usable signal that the three-way threshold on top of it destroyed.
Here it is worth noting and **not** worth acting on, for a reason §8 already
settles — the argmax the pipeline keeps is already indistinguishable from a
constant, so the rest of the distribution has no established value to recover.
Recovering it would need ground truth this bench does not have.

### 9.3 Inventing negativity that is not there

The 38 segments the author verified as neutral, and how often each model calls them
NEGATIVE:

| Model | Invents NEGATIVE (of 38) |
|---|---|
| `hardlyhumans_vit` | **22 (57.9%)** |
| **`deepface_fer` (incumbent), as deployed with `opencv` crops** | **38 (100%)** |
| `deepface_fer` on `retinaface` crops | 14 (36.8%) |
| `emotieffnet_b2` | 12 (31.6%) |
| `emotieffnet_b0_va`, `dan_affectnet8` | 8 (21.1%) |
| `dima806_vit` | 7 (18.4%) |
| `motheecreator_vit` | 5 (13.2%) |
| `trpakov_vit` | **3 (7.9%)** |
| `tanneru_beit_large` | 1 (2.6%) — but it calls 84.5% of everything `surprise` |

**As deployed, the channel calls every single verified-neutral segment negative.**
Giving the same emotion model better crops cuts that from 38 of 38 to 14 of 38
without touching the model — more evidence for §8's conclusion that the detector is
the bigger lever.

`trpakov_vit` invents negativity on 3 of 38. That is the best result in the table
and it is the reason it leads Bench B.

### 9.4 What this does **not** show

No model here was tested on genuine anger, because this reviewer never displayed
any (§2.1). Everything above is about **false** negativity. A claim that these
models miss real anger would need a video containing some, and would need it
labelled.

---

## 10. The decision, and what was changed

### 10.1 Bench A — adopted

**`yunet` replaces `opencv` as the face detector in `pipeline/visual_module.py`.**
`FACE_DETECTOR_BACKEND` is now a named constant carrying the measurement that
chose it. §6.4 and Amendment A6 record that this is a declared deviation from the
letter of the pre-registered rule, which selects `mtcnn` on a two-segment tie-break
at p = 0.5000 and 44 minutes per video.

**The before/after, on the real pipeline, over the same 572 frames**
(`adopt_rerun.py`, `adopt_rerun.json`):

| | before (`opencv`) | after (`yunet`) |
|---|---|---|
| Segments right (of 77) | 6 | **11** |
| **False faces (of 20)** | **15** | **9** |
| Missed faces (of 57) | 0 | 0 |
| Wrong labels (of 44) | 43 | 44 |
| Frames with a detected face | 363 | 386 |
| **Seconds per frame** | 0.694 | **0.099** |
| Composite accuracy | 7.8–24.7% | **14.3–31.2%** |

24 segments changed label. Exact McNemar on the change: **p = 0.1250** (b = 1,
c = 6, smallest attainable 0.0156).

Read honestly: the hallucinated-face count falls by **40 per cent**, the channel is
**seven times faster**, and the composite roughly doubles — but on 7 discordant
segments the improvement is **not statistically significant**. The direction is
consistent with everything in §6 and the false-positive reduction is the effect the
change was made for; the significance is what this sample size can support, and
that is stated rather than rounded up.

The row that does not improve is the honest one: wrong labels go 43 → 44. **The
detector swap does not fix the emotion model, and was never going to.**

### 10.2 Bench B — nothing adopted

**No emotion model is adopted, and that is the result.**

Under the rule as amended (A5), a candidate must beat the always-NEUTRAL floor.
None does. The best, `trpakov_vit`, is 6.9 points *below* it and not detectably
different from it (p = 0.4531). Every other candidate is significantly worse.

`vocal_bench/SPEAKER_NORM_RESULT.md` is the precedent: a pre-registered rejection
is evidence; the same rejection without a rule fixed in advance is an anecdote. The
rule was fixed on 03 Sep 2026 before any candidate was scored, it was amended once
for a sampling defect found before the results were read, and it selects nothing.

### 10.3 What the channel now is, stated plainly

The facial emotion channel is, on this project's own data:

- **worse than a constant.** The deployed channel scores 46.8–63.6 per cent on the
  composite against 63.6–80.5 per cent for the same detector paired with a fixed
  NEUTRAL label. The best pipeline assemblable from nine models and six detectors,
  46 of 77, is indistinguishable from that constant.
- **the third channel in this system to show that pattern**, after transcript
  sentiment and vocal emotion — and it shows it by the widest margin.
- **improved but not repaired** by the detector swap. The false-positive half of
  the failure is materially better. The classification half is unchanged, and no
  available model fixes it.

The module docstring now says this, so anything consuming `facial_emotion` meets
the measurement rather than having to find it.

The natural consequence is the one the vocal channel already implements: a channel
measured at this level should be **down-weighted in the orchestrator**, exactly as
`VOCAL_ONLY_CONFLICT_WEIGHT` and `_vocal_is_sole_dissenter` down-weight the vocal
channel. That is a change to `orchestrator.py` with its own before/after
measurement to earn, and it is **not** made here — §12 names it as the next piece
of work rather than bundling it into this one.

---

## 11. Limitations

### 11.1 One scored video, one speaker

Every accuracy figure here comes from `1VjPETN3m6U` — one reviewer, one lighting
setup, one shooting style. A detector or model that wins here may be winning on
this speaker's face and framing. This is the largest single threat and it is why
the decision rule requires McNemar significance rather than a raw accuracy gap.

`JpN1DQdV4G4` (827 frames) and `SAb4zRyxrD4` (563 frames) are on disk and have no
per-segment ground truth, so they cannot extend the scored comparison without new
human labelling.

### 11.2 No NEGATIVE expressions exist in the ground truth

§2.1. This reviewer never displayed one, so **negative recall is not measurable at
all**. Everything §5 and §8 say concerns models *inventing* negativity, never
models *missing* it. No claim about detecting genuine anger is made anywhere.

### 11.3 The expression sample is selected on the incumbent's errors

§2.3 and Amendment A5. Handled by withdrawing the incumbent comparison, using the
always-NEUTRAL floor as the bar, and leading with the whole-video composite. The
challenger-versus-challenger comparison is unaffected.

### 11.4 The ground truth is a transcription of prose, by one person

Of the 44 expression labels, 7 come from rows §9 tabulates individually, 17 from a
group whose expression §9 states positively ("neutral expression"), and 20 from
groups that describe the expression only by what it is **not** ("not sad", "no fear
visible"). Tiers are recorded per row and the strict subset is scored separately.

Amendment A1 shows the transcription risk is real: the anchor check found segment
39 in the wrong row on its first run. And §9 is **one person's review**.
`comment_bench` used a second, independent rater; that is not available
retrospectively here, and it is the honest ceiling on every number in this
document.

### 11.5 Segment pooling is held fixed, and it is itself a suspect

Both benches pool with `visual_module`'s own rule so they measure models rather
than pooling policy. But §9's root-cause analysis argues the pooling is *also*
wrong — unweighted majority vote, no minimum frame count, no confidence weighting —
and §6.5 measures how much that rule amplifies a frame-level error into a
segment-level one. A better model could be partly masked by it. Deliberately out of
scope, and named as separate future work rather than quietly bundled in.

### 11.6 Bench B holds the detector fixed, so it is not the deployed configuration

Every classifier is scored on `retinaface` crops, including the incumbent emotion
model. That isolates the classifier, which is the point, but it means Bench B's
incumbent row is *the deployed emotion model on better crops than it normally
gets*, not the deployed channel. The deployed channel's own number comes from the
pipeline anchor and appears in §8 and §10.1.

### 11.7 Small samples, wide intervals

44 expression labels; 20 faceless segments; 57 face segments. Wilson intervals are
wide and `min_attainable_p` is reported everywhere so a null result can be read as
"the test could not have detected this" where that is the truth.

### 11.8 Timings are single-machine and single-run

Every `seconds_per_frame` is one pass on one laptop at 3840×2160. No two sweeps
were run concurrently — an early attempt to overlap two was abandoned precisely
because it distorted both — but light analysis commands were running alongside some
of them, so the figures are indicative rather than benchmark-grade. They are good
enough for the only distinction the decision rule draws from them: 0.06 s/frame
against 4.64 is a 75-fold gap that no amount of measurement noise explains.

---

## 12. What to do next, in priority order

### 12.1 Down-weight the facial channel in the orchestrator

**The highest-value follow-up, and the one this result most obviously implies.**

The channel is measured as indistinguishable from a constant (§8). The orchestrator
currently treats its label as a peer of the transcript and comment channels. The
vocal channel already has the machinery for exactly this situation —
`VOCAL_ONLY_CONFLICT_WEIGHT = 0.489` and `_vocal_is_sole_dissenter()` — and the
same pattern applies here with a weight this bench has now measured.

It is a change to `orchestrator.py` and it owes its own before/after on the corpus,
in the shape of `vocal_bench/DAMPING_FIX_RESULT.md`. Not bundled into this bench.

### 12.2 Fix the pooling, which is a separate defect from the model

§6.5 shows the `any`-frame rule turning single-frame detection errors into
whole-segment ones, and §9's proposed fixes 4 and 5 — confidence-weighted pooling
and a minimum corroborating-frame count — are pooling changes, not model changes.
A diagnostic sweep run during this bench suggests requiring two corroborating
frames cuts the incumbent's segment-level false positives roughly in half. That
number is **diagnostic only**: it was measured while the pooling was being held
fixed on purpose, and it needs its own pre-registered test before anything is
claimed for it.

### 12.3 Get a second video labelled

Every accuracy figure here is one speaker (§11.1). `JpN1DQdV4G4` has 827 frames on
disk and §12D's aggregate review already exists for it; what is missing is
per-segment labels. That is the single cheapest way to find out whether `yunet` and
`trpakov_vit` win on this footage or on this face.

It would also let §9.1's most striking claim be tested properly. Right now the
cross-speaker instability — 26.0 per cent angry against 0.3 per cent — is
established for the **incumbent only**, from two existing measurements. Whether the
challengers are equally unstable is unknown, and it decides whether the problem is
DeepFace or the whole model class.

### 12.4 Action Units, if the taxonomy question is worth pursuing

§5 argues the basic-emotion taxonomy cannot express what a product reviewer
actually shows. Py-Feat (Cheong et al., 2023) outputs Action Units directly, and
AU4 + AU23 is the closest thing the literature offers to a frustration signature.

Rejected for *this* bench in §4.4 because AUs need a ground truth this project does
not have, and that has not changed — it would need AU-level labelling, which is
specialist work. Named here because it is the only route that addresses the
structural finding rather than working around it, not because it is affordable.

### 12.5 What is deliberately **not** worth doing

- **Fine-tuning a facial model on this data.** 44 expression labels, 38 of one
  class. `comment_bench` earned its fine-tune with 300 hand-labelled examples;
  there is nothing here to fine-tune on and nothing left to test on.
- **Raising `FACE_CONFIDENCE_THRESHOLD`.** Measured, §4. It does not work.
- **Per-speaker calibration of the facial channel.** §9's proposed fix 3 and §6 of
  `PROTOTYPE_FINDINGS.md`. `vocal_bench/SPEAKER_NORM_RESULT.md` pre-registered,
  tested and **rejected** exactly this idea for the vocal channel, where every
  variant was 12.7–21.2 points worse on held-out speakers. It should not be
  re-proposed here without reading that file first.
- **Trying more HuggingFace FER checkpoints.** §7.1 is the argument: the published
  ranking correlates **−0.62** with what happens on this footage. Another model card
  claiming 90 per cent is not evidence, and nine candidates spanning five
  architectures and three training corpora already agree on the shape of the answer.

---

## 13. Artefacts

| File | What it is |
|---|---|
| `CANDIDATE_MODELS.md` | the register and pre-registration, with six dated amendments |
| `ground_truth.py` | §9's review, machine-readable, with the anchor check that guards it |
| `candidates.py` | all nine classifiers and six detectors behind one interface |
| `run_detect.py` / `run_classify.py` | the two sweeps |
| `anchor_pipeline.py` | the system test that reproduces the saved run, 77/77 |
| `adopt_rerun.py` | the before/after the adoption owes |
| `report_bench.py` | all scoring; imports `transcript_bench/metrics.py` rather than copying it |
| `verify_claims.py` | every number above, re-derived from source |
| `tests/test_facial_bench.py` | the unit tests for the bench's own arithmetic |
| `vendor/dan/` | DAN, vendored under MIT with its checkpoint hash |

**Commands.** Run from `brandpulse_ai/` with the project venv active:

```bash
python research/facial_bench/probe_candidates.py                        # feasibility only
python research/facial_bench/anchor_pipeline.py                         # the fidelity anchor
python research/facial_bench/run_detect.py --video 1VjPETN3m6U --crops  # Bench A + crops
python research/facial_bench/run_detect.py --video 1VjPETN3m6U --detector mtcnn --midpoints-only
python research/facial_bench/run_classify.py --video 1VjPETN3m6U        # Bench B
python research/facial_bench/report_bench.py                            # every table above
python research/facial_bench/adopt_rerun.py                             # the adoption before/after
python research/facial_bench/verify_claims.py                           # re-derive every number
```
