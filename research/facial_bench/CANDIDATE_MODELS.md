# Facial Emotion Bench — Candidate Register and Pre-Registration

**Written 03 Sep 2026, before any candidate was scored against ground truth and
before the ground truth was joined to any prediction.** Sections 3, 5 and 9 are
fixed from this date and must not be revised after results are seen. Corrections
go in an Amendments section at the end, dated, never edited into the body.

Method: the eight-step bench method (README), already used in `comment_bench/`,
`transcript_bench/`, `whisper_bench/` and `vocal_bench/`.

Candidates were probed for loadability first (`probe_candidates.py`,
`probe_results.json`). That is feasibility, not result — the probe deliberately
computes no accuracy, and the ground truth had not been joined to anything when
this register was written.

---

## 1. Why this bench exists

`pipeline/visual_module.py` runs DeepFace with `detector_backend="opencv"` and
DeepFace's built-in FER-2013 emotion model. **This is the only channel of the five
never benched**, and it is the worst-evidenced one in the system by the project's
own measurements.

Two independent, author-verified failures are already on record.

| Source | Video | What was checked | Result |
|---|---|---|---|
| `PROTOTYPE_FINDINGS.md` §9 | `1VjPETN3m6U`, 77 segments | every segment's frames viewed against the stored label | **~79% error (61/77)**; 15 segments a confident emotion on frames with **no human being in them** |
| `PROTOTYPE_FINDINGS.md` §12D | `JpN1DQdV4G4`, all 827 frames | every frame viewed on 34 contact sheets | **34/375 detections (9.1%) on faceless content**; **127/341 (37.2%) "sad"** on a speaker the author verified as never sad |

### 1.1 These are two different failures and must be benched separately

The single most important design decision in this bench. §9 and §12D show the
channel failing in two ways that no single swap can fix:

- **Detection.** A Haar-cascade backend passes circular and textured product
  photography as face geometry. §9 attributes this to the triple camera-lens
  cluster having roughly the three-blob layout of two eyes and a mouth; §12D
  reproduces it on printed diagrams, boxed text and dotted shoe soles. Changing
  the emotion model cannot help: the emotion head is being handed a shoe.
- **Classification.** On genuine faces, the label skews to low-affect negatives.
  Changing the detector cannot help: the face was found correctly.

So there are two benches. **Bench A** scores detectors on face presence. **Bench B**
scores emotion models on *identical crops* cut by one fixed detector, so any
difference between two classifiers is a property of the classifier.

`pipeline/visual_module.py` couples them and cannot express the distinction. The coupling
is therefore an architectural finding as well as an evaluation constraint.

### 1.2 The label distribution flips with the speaker

The two videos disagree about which negative class the channel over-produces.

| | `1VjPETN3m6U` (Apple, 77 segments) | `JpN1DQdV4G4` (Nike, 341 real-face frames) |
|---|---|---|
| angry | **20 (26.0%)** | **1 (0.3%)** |
| sad | 25 (32.5%) | **127 (37.2%)** |
| happy | 1 (1.3%) | 57 (16.7%) |

Both figures are derived from files in this repository: the first from
`outputs/Apple (Iphone 17 Pro Max - 3).json`, re-derived by
`ground_truth.py:anchor_check()`; the second quoted from §12D.

This is the same shape of failure `vocal_bench/CANDIDATE_MODELS.md` §1 recorded
for the vocal channel — *a channel whose majority class is determined by which
speaker is talking is not measuring emotion*. It is what makes Q4 below the
central question rather than a footnote.

---

## 2. What is being tested

**Q1 — Can any available detector cut the hallucinated-face rate without losing
real faces?** The primary Bench A question. §9's 15 false-positive segments are
19.5% of the video. Any detector that removes them while keeping the 57 genuine
face segments is a strict improvement, and the channel currently has no evidence
that one exists.

**Q2 — Can any available emotion model beat the incumbent on genuine faces?** The
primary Bench B question. The incumbent's error rate has been *observed* twice and
never *measured* against a fixed ground truth with an interval on it.

**Q3 — Is the incumbent beaten by a degenerate baseline?** `transcript_bench` found
the deployed transcript model scored **worse than always guessing NEUTRAL**, and
`vocal_bench` found the same for the vocal model. §9's ground truth is 38 NEUTRAL
of 44, so always-NEUTRAL scores 86.4% before any model runs. This must be tested,
not assumed away, and it is the number every candidate has to beat.

**Q4 — Is a seven-way basic-emotion label the right output at all?** The design
question, and §5 argues it is not. A dimensional candidate is included specifically
to test whether the framing is the problem, exactly as `vocal_bench` tested a
dimensional model against categorical ones and adopted the dimensional reading.

**Q5 — Does the published accuracy on a model card predict anything here?** The
candidate set spans self-reported accuracies from 57.4% to 92.2%. §4.3 gives
concrete reasons to distrust the top of that range. If the ranking on this
project's data does not track the published ranking, that is direct evidence for
The project's evidence rule (README) — *a citation justifies interest in a model, never choosing or
rejecting it* — measured rather than asserted.

**Q6 — Where does anger actually go?** §5. Treated as a first-class question
because the project's own observation is that anger and frustration are rarely
detected strongly while disappointment-like readings dominate, and because the two
videos above disagree about it by a factor of eighty.

---

## 3. Primary metric and decision rule — pre-registered, fixed 03 Sep 2026

### 3.1 Ground truth

`ground_truth.py`. It is a machine-readable transcription of the author's own
visual review in `PROTOTYPE_FINDINGS.md` §9 — a human judgement about what is
visible in the frames, made independently of every candidate in this bench,
including the incumbent.

| | n | Source |
|---|---|---|
| Face presence, all segments | **77** | §9's four categories, which partition all 77 |
| — no human face | 20 | 15 tabulated false positives + the 5 §9 counts as correct-no-face |
| — real face present | 57 | §9's "Match" and "Mismatch" both open "A real face is present" |
| Expression, three-class | **44** | the segments §9 describes in prose |
| — of which individually tabulated | 7 | tier `explicit` |
| Expression, class balance | 38 NEUTRAL / 6 POSITIVE / **0 NEGATIVE** | |

**Verification, not assertion.** `anchor_check()` re-reads the saved run §9
analysed and refuses to hand out any label unless every transcribed label and
confidence matches it, the segment count is 77, the four category counts sum to
77, and the derived partition reproduces them. A transcription error fails loudly
instead of silently producing a wrong ground truth. It has already caught one: see
Amendment A1.

**The class balance is a hard limitation and is stated here, before results.**
There are **no NEGATIVE segments in the expression ground truth**. §9 found the
reviewer never displayed a negative expression, so on this video negative recall
is not measurable at all. Bench B can therefore measure *false* negativity — a
model inventing anger or sadness that is not there — and cannot measure *missed*
negativity. Every conclusion in §5 is bounded by that, and no claim about a
model's ability to detect genuine anger will be made from this data.

### 3.2 Metrics

**Bench A, primary metric: false-positive rate on faceless segments**, that is
the share of the 20 verified-faceless segments where a detector reports a face.
Chosen because it is the failure §9 and §12D actually document and the one that
puts fabricated data into the orchestrator. Reported alongside, always: recall on
the 57 face segments (a detector that finds nothing has an FPR of zero and is
useless), precision, accuracy over all 77 with a Wilson 95% interval, and
seconds per frame at the 4K resolution the pipeline actually feeds it.

**Bench B, primary metric: three-class accuracy** on the 44 expression segments,
the same metric `transcript_bench` and `vocal_bench` used, so the facial channel's
number is directly comparable with theirs. Reported alongside, always: macro-F1,
per-class precision and recall, the full confusion matrix, Wilson 95% intervals,
exact McNemar against the incumbent **with `min_attainable_p`**, and the count of
unmapped predictions.

`min_attainable_p` is reported because n is 44 and the discordant count can be
small enough that no result could reach significance. When that happens the null
result is a property of the test, not of the models, and saying so is required.

### 3.3 Mapping model outputs to three classes — fixed before any output was seen

| Model output | Maps to |
|---|---|
| angry / anger, sad / sadness, disgust, fear, **contempt** | NEGATIVE |
| neutral | NEUTRAL |
| happy / happiness, **surprise** | POSITIVE |
| anything else | **recorded as unmapped, never silently coerced** |

Two declared judgement calls:

- **`surprise → POSITIVE`.** The same call `vocal_bench/CANDIDATE_MODELS.md` §3
  made, for the same reason: in product-review footage surprise is overwhelmingly
  delight rather than alarm. The count of surprise predictions is reported
  separately, and a sensitivity check with `surprise → NEUTRAL` is reported
  whenever it changes a conclusion. `candidates.THREE_CLASS_SURPRISE_NEUTRAL`
  exists for exactly that check.
- **`contempt → NEGATIVE`.** Only the three AffectNet-8 candidates emit it. It is
  the closest available class to the disdain a critical reviewer shows, so folding
  it into NEGATIVE is the reading that could *help* those models rather than the
  one that flatters the incumbent.

### 3.4 The floors every candidate must clear

Two degenerate baselines are scored as candidates, not mentioned as caveats:

- **always-NEUTRAL** — 38/44 = **86.36%** on the expression set.
- **always-face** and **never-face** on Bench A — 57/77 and 20/77.

`transcript_bench` and `vocal_bench` both found the deployed model losing to a
constant. Until a candidate beats the constant it has earned nothing.

### 3.5 Decision rule

> **Bench A.** Adopt the detector with the lowest false-positive rate on the 20
> faceless segments **among those whose recall on the 57 face segments is not
> detectably worse than the incumbent's** (exact McNemar, p < 0.05). Ties break on
> (a) accuracy over all 77, (b) seconds per frame, (c) no new dependency.
>
> **Bench B.** Adopt the classifier with the highest three-class accuracy **that
> is also detectably better than the incumbent** (exact McNemar, p < 0.05) **and
> not worse than always-NEUTRAL**. Ties break on (a) macro-F1, (b) permissive
> licence, (c) seconds per crop.
>
> ⚠️ **The incumbent clause of this rule was withdrawn on 03 Sep 2026 — see
> Amendment A5.** The 44-segment sample turned out to be selected on the
> incumbent's own errors, which makes "better than the incumbent" trivially true
> and therefore uninformative. The always-NEUTRAL clause stands and becomes the
> bar. The text above is left exactly as written so the change is visible; the
> amendment, not this paragraph, is what the bench follows.

> ⚠️ **Bench A gained a second pooling mode on 03 Sep 2026 — see Amendment A2.**
> Both are reported for every detector and neither is suppressed.
>
> **If nothing clears the floor in Bench B, nothing is adopted for classification**
> and that is reported as the result, with the same weight as an adoption. The
> vocal channel's `SPEAKER_NORM_RESULT.md` is the worked example: a pre-registered
> rejection is evidence, the same rejection without a pre-registered rule is an
> anecdote.
>
> **The two benches are decided independently.** Adopting a detector does not
> require adopting a classifier, and vice versa. That is the point of separating
> them.

### 3.6 What is deliberately not being done

- **No fine-tuning.** `comment_bench` earned its fine-tune with 300 hand-labelled
  comments. There are 44 expression labels here. Fine-tuning on them would leave
  nothing to test on, and reporting an accuracy from it would be meaningless.
- **No threshold fitting on the scored set** for the dimensional candidate. If a
  valence threshold is fitted it is fitted on a split and frozen, following
  `vocal_bench`; if there is not enough data to split, the dimensional arm is
  reported descriptively and is **not eligible for adoption**.
- **No re-selection against a second video.** `JpN1DQdV4G4` and `SAb4zRyxrD4` have
  frames but no per-segment ground truth. They are used for distribution and
  agreement analysis only, and no adoption decision rests on them.

---

## 4. The candidate space

### 4.1 Face detectors — Bench A

Every backend DeepFace 0.0.100 exposes that loads in this project's venv.

| Candidate | Family | Weights | Why it is in |
|---|---|---|---|
| **`opencv`** | Haar cascade | ships with OpenCV | **the incumbent.** Chosen in the prototype for speed at 1 fps; §9 and §12D both trace the hallucinated faces to it |
| `ssd` | ResNet-10 SSD, 300×300 | OpenCV DNN | the cheapest CNN alternative; a like-for-like speed comparison with Haar |
| `mtcnn` | three-stage CNN cascade | bundled | the classic strong-precision baseline in the FER literature |
| `retinaface` | single-stage, landmark-supervised | 119 MB | the accuracy option; §9's proposed fix names it explicitly |
| `yunet` | OpenCV Zoo 2023-03 ONNX | 233 KB | designed for edge use; tests whether accuracy needs size |
| `yolov8n` | face-finetuned YOLOv8 nano | bundled | a modern one-stage detector on a family this project already ships |

**Excluded, with reasons** (recorded rather than quietly dropped):

| Excluded | Reason |
|---|---|
| `centerface` | deepface 0.0.100 raises `UnboundLocalError: cannot access local variable 'boxes_np'` on frames with no detection. An upstream defect, not a property of the detector. Measured 03 Sep 2026 |
| `mediapipe`, `dlib` | neither library installed; six backends already span Haar, SSD, cascade-CNN, single-stage and YOLO. Not worth a dependency |
| `fastmtcnn` | needs `facenet-pytorch`; plain `mtcnn` covers the same family |

**Frames are 3840×2160.** Every timing in this bench is at that resolution,
because that is what `downloader.extract_frames` produces and what the pipeline
actually feeds the detector. A Haar cascade sweeping a 4K frame full of textured
product photography has far more opportunities to match spurious face geometry
than the same cascade on a 640×480 webcam frame, which is the setting its default
parameters were tuned for. That is a hypothesis about *why* the incumbent fails,
and Bench A tests it.

### 4.2 Emotion classifiers — Bench B

All nine load and run in this venv on real project crops, verified 03 Sep 2026.

| Candidate | Architecture | Training data | Licence | Its own published number |
|---|---|---|---|---|
| **`deepface_fer`** | small CNN, 48×48 greyscale | FER-2013 | MIT (library) | **57.4%** — the library author's own figure for this 2018 model |
| `trpakov_vit` | ViT-B/16, 224px | FER-2013 | apache-2.0 | 71.16% test |
| `motheecreator_vit` | ViT-B/16 | FER-2013 + MMI + AffectNet | **not declared** | 84.34% eval |
| `dima806_vit` | ViT-B/16 | **not stated** | apache-2.0 | 90.92% |
| `hardlyhumans_vit` | ViT-B/16, 8-class | FER-2013 + AffectNet | **not declared** | 92.2% |
| `tanneru_beit_large` | BEiT-Large | FER-2013 + RAF-DB + AffectNet | apache-2.0 | 73.57%, macro-F1 0.6965 |
| `dan_affectnet8` | ResNet-18 + 4 cross-attention heads | AffectNet-8 | MIT | 62.09% AffectNet-8 |
| `emotieffnet_b0_va` | EfficientNet-B0, multi-task | VGGFace2 → AffectNet | apache-2.0 | 61.93% AffectNet-8; **also outputs valence and arousal** |
| `emotieffnet_b2` | EfficientNet-B2 | VGGFace2 → AffectNet | apache-2.0 | 63.03% AffectNet-8 |

Sources for every number above: the model's own card or repository README, read
03 Sep 2026. They are recorded to make Q5 answerable, **not** to rank candidates.

**Why these nine.** They span the three things that plausibly matter and let each
be isolated:

- **architecture** — 48×48 CNN, ViT-Base, BEiT-Large, ResNet+attention, EfficientNet;
- **training corpus** — FER-2013 only, AffectNet only, and mixtures. This is the
  variable `vocal_bench` found decisive (Q2 there: *does training-data domain
  matter more than model size*), and the direct test here is `trpakov_vit`
  (FER-2013, ViT-B) against `dan_affectnet8` (AffectNet, smaller ResNet-18);
- **output shape** — seven basic classes, eight with contempt, and one continuous
  valence/arousal pair.

**`dan_affectnet8` is the one candidate with independent third-party evaluation on
naturalistic footage.** Salas-Cáceres et al. (2026) compared eleven FER systems —
four specialised networks, five vision-language models and one commercial product —
across four corpora, and found DAN trained on AffectNet the strongest traditional
model on both of their dynamic, lower-quality sets (60.5% on RAVDESS, 48.7% on
CREMA-D). That is a published result on *their* data. It justifies testing DAN
here, and nothing more. Its weights are on Google Drive with no package, so the
network definition and checkpoint are vendored under `vendor/dan/` with the MIT
licence, and the checkpoint's SHA-256 is recorded.

**`emotieffnet_b0_va` is the Q4 candidate.** It is the only one that emits a
continuous valence, which maps to the same negative-to-positive axis the other
three channels already produce. `vocal_bench` reached its only real improvement by
abandoning a categorical reading for a dimensional one; this tests whether the
same move helps here.

### 4.3 What the published numbers do not survive

Three cards claim accuracies at or above 84%. Published AffectNet-8 state of the
art is around 62–67%, and Salas-Cáceres et al. measured every system they tested
at 36–49% mean accuracy on their most naturalistic corpus. Two specific reasons
to distrust the top of the table, both visible in the cards themselves:

- **`dima806_vit`** reports per-class support of 3595–3596 for **every one of the
  seven classes**, including disgust. FER-2013 contains roughly 547 disgust images
  in total. A balanced evaluation set of that size can only have been produced by
  oversampling or augmentation, and the card reports **F1 0.9954 on disgust** —
  the class with the least real data scoring highest is the signature of augmented
  copies of the same images appearing in both splits. The card also does not state
  its training data at all.
- **`hardlyhumans_vit`** claims 92.2% on FER-2013 + AffectNet, above every
  published result on either. Its `preprocessor_config.json` additionally has
  `do_resize` set to the *string* `"google/vit-base-patch16-224"` instead of a
  boolean and omits `image_processor_type` entirely, so transformers 5.x cannot
  construct its processor. `motheecreator_vit` declares no licence.

None of this disqualifies them. **All three are benched anyway**, precisely
because Q5 asks whether published numbers predict anything here. Stating the
suspicion before the measurement is what makes the measurement worth having.

Where a broken published preprocessor blocked loading, the processor was
constructed explicitly with the settings the model's own config records (224px,
mean and std 0.5). That workaround is recorded because a broken published
preprocessor is itself evidence about provenance.

### 4.4 Approaches considered and rejected before benching

| Rejected | Why |
|---|---|
| **POSTER++ / POSTER V2** | Current state of the art on RAF-DB and AffectNet. The only accessible weights (`KaliberAI/posterv2_affectnet7`, `…8`) declare **no licence**, have zero downloads, and need the research repo to instantiate. An unlicensed checkpoint cannot be adopted into a B2B-framed product, so measuring it could not change the decision |
| **APViT** | Requires `mmcls`/`mmcv` pinned to a torch generation this venv does not have. Integration cost is days, and it would not be adoptable without pinning the whole project backwards |
| **DAN as a library** | Same model as `dan_affectnet8`; there is no package, which is why it is vendored rather than installed |
| **FaceReader 10** | Commercial and licensed. Salas-Cáceres et al. measured it at 96–98% on controlled corpora and **below a random classifier on CREMA-D**, their most naturalistic set — the exact overspecialisation this project's footage would expose |
| **Vision-language models** (`gemma3:4b` is present locally and does accept images) | Salas-Cáceres et al. found every VLM they tested "exhibited a pronounced bias toward the happy emotion", with fear and disgust "almost never correctly identified", and the best face-specialised VLM only "comparable to the weakest traditional model". At ~9 s per frame against 0.1–0.9 s for every specialised candidate, it is 10–90× the cost for a documented-worse expected result. **Recorded as a deliberate exclusion with a stated expected outcome, not an oversight** — it remains the obvious follow-up if the specialised models all fail |
| **Py-Feat** (Cheong et al., 2023) | The most attractive rejection. It bundles ResMaskNet and reports its own AffectNet F1 per class: happy .77 but **anger .53, sad .54, fear .48, neutral .49, average .55** — which is itself evidence for §5. Rejected for *this* bench because its value is Action Units, and AUs would require a new ground truth this project does not have. **Named as the specific future-work route in §5.4** |
| **Fine-tuned brand-logo detection** | `detect_logos` is a separate documented placeholder (`PROTOTYPE_FINDINGS.md` §8). Out of scope |
| **Any tightly-fused multimodal model** | Standing project constraint (README, "Engineering rules") |

---

## 5. Q6 — where anger actually goes

The project's own observation, and the reason this section is pre-registered
rather than written after the fact: **anger and frustration are rarely detected
strongly, while disappointment-like readings appear far more often.** Four
mechanisms could produce that, and they are separable by measurement.

### 5.1 The taxonomy cannot express it — verified, no measurement needed

Not one candidate has a class for frustration or for disappointment. Every one
emits Ekman's six plus neutral, or those eight with contempt. Verified from each
model's own `config.json` or source, 03 Sep 2026.

Frustration and disappointment are *appraisal* states, not basic emotions. They
have no canonical facial signature in this taxonomy, so a model can only express
them by borrowing: frustration through anger or disgust, disappointment through
sadness. **A reviewer who is disappointed by a product cannot be labelled
disappointed by any candidate here.** That is a property of the entire available
model space, not of any one model, and it belongs in the report as such.

The affective-computing literature treats frustration as its own problem for this
reason. Grafsgaard et al. (2013) related AU4, the brow lowerer, to frustration in
learning without reporting classification metrics for it. AU4 is *also* a
component of both the canonical anger and the canonical sadness prototypes. A
concentrating, mildly critical reviewer activating AU4 alone is therefore
genuinely ambiguous between anger, sadness and neutral for any basic-emotion
classifier — and which of the three it lands on is not a judgement about the
speaker's state.

### 5.2 The argmax may be discarding it — measurable here

"Rarely detected **strongly**" is a claim about the decision rule, not the model.
`pipeline/visual_module.py` keeps only `dominant_emotion` and throws the rest of
the distribution away. If anger consistently sits second at p ≈ 0.2, the model is
seeing it and the pipeline is discarding it.

Every candidate's **full probability distribution** is therefore recorded, not
just the argmax, and the bench reports mean probability mass per class alongside
argmax counts. This is the same distinction that mattered in `vocal_bench`, where
a continuous arousal value carried usable signal that the three-way threshold on
top of it destroyed.

### 5.3 The training corpora are imbalanced in a specific direction — documented

FER-2013's disgust class has roughly 547 examples against roughly 9,000 for happy.
AffectNet is skewed towards happy and neutral. A model trained on either will have
weak, poorly-calibrated boundaries exactly where low-intensity negative affect
lives. The bench cannot fix this; it can measure whether AffectNet-trained
candidates behave differently from FER-2013-trained ones, which is a direct
comparison the candidate set was chosen to support.

### 5.4 Speech confounds the mouth — hypothesis, tested only descriptively

Every frame in this corpus is a person talking. An open mouth mid-word resembles
the canonical surprise and fear prototypes, and the FER corpora are dominated by
closed-mouth posed stills. `PROTOTYPE_FINDINGS.md` §12D's finding that fear was
the dominant spurious label is consistent with this. The bench reports how often
each candidate predicts surprise and fear on genuine speaking faces. It cannot
prove the mechanism without Action Units, which is why Py-Feat is named in §4.4 as
the specific follow-up rather than dismissed.

### 5.5 What will be reported, and what will not

**Reported:** argmax distribution per candidate per video; mean probability mass
per class; how often anger is second when it is not first; the rate at which each
candidate invents NEGATIVE on the 38 segments the author verified as neutral; and
whether AffectNet-trained candidates differ from FER-2013-trained ones.

**Not reported, because the data cannot support it:** any claim that a model can
or cannot detect *genuine* anger. §3.1 states why — the expression ground truth
contains zero NEGATIVE segments. The observation that anger is under-produced on
one video and over-produced on another is about **false** negativity in both
directions, and will be worded that way.

---

## 6. What the corpus is

| Video | Frames | Ground truth | Role |
|---|---|---|---|
| `1VjPETN3m6U` | 572 | §9, all 77 segments | **the only scored video.** Both benches |
| `JpN1DQdV4G4` | 827 | §12D, aggregate counts only | distribution and agreement analysis; **no adoption decision rests on it** |
| `SAb4zRyxrD4` | 563 | none | distribution and agreement analysis only |

One scored video is a real limitation and is stated here rather than discovered
later. It bounds every Bench A and Bench B number to one speaker, one lighting
setup and one shooting style, and it is the reason §3.5 requires McNemar
significance rather than a raw accuracy gap.

---

## 7. Reproducibility

- Pinned: deepface 0.0.100, transformers 5.12.1, torch 2.12.0, tensorflow 2.21.0,
  emotiefflib 1.1.1 (ONNX engine), timm 1.0.29, opencv-python 4.13.0.92.
- `emotiefflib` and `timm` are **bench-only** additions. Neither is imported by
  anything under `pipeline/`, and nothing is adopted into the pipeline without a
  decision under §3.5.
- The DAN checkpoint's SHA-256 is recorded in `vendor/dan/README.md`.
- Every candidate is deterministic: no sampling, no temperature, `model.eval()`
  throughout. Re-running produces identical predictions.
- Crops are cut once and written to disk, so every classifier is scored on
  byte-identical pixels.
- Exact commands are recorded in `FACIAL_MODEL_ANALYSIS.md`.

---

## 8. Known threats to validity — written before results

1. **One scored video, one speaker.** §6. The largest threat. A detector or model
   that wins here may be winning on this speaker's lighting and framing.
2. **Zero NEGATIVE in the expression ground truth.** §3.1. Bounds §5 entirely.
3. **The ground truth is a transcription of prose.** 22 of 44 expression labels
   come from grouped rows describing several segments at once, and 20 of those
   describe the expression only by what it is *not*. Tiers are recorded and the
   strict subset is scored separately. Amendment A1 shows this risk is real.
4. **Author-verified is not independently verified.** §9 is one person's review.
   `comment_bench` used a second rater; that is not available retrospectively here.
   It is the honest ceiling on these numbers and is stated in the write-up.
5. **Segment pooling is held fixed.** Both benches pool with the pipeline's own
   rule so they measure models rather than pooling policy. §9's root-cause analysis
   argues the pooling is *also* wrong (unweighted majority vote, no minimum frame
   count). That is a real confound: a better model could be masked by bad pooling.
   It is deliberately out of scope here and named as separate future work.
6. **The crop detector is a fixed choice.** Bench B's crops come from one
   detector, `retinaface`. If it systematically mis-crops, every classifier
   inherits it. It was chosen **a priori, before Bench A ran** — §9's own proposed
   fix names it, and it is the strongest-precision option in the literature —
   specifically so the choice could not be made by looking at which detector won.
   Whether it was the right choice is checked against Bench A afterwards and
   reported either way.
7. **Small n.** 44 expression labels, 20 faceless segments. Wilson intervals will
   be wide and `min_attainable_p` may exceed 0.05. Both are reported.

---

## 9. Adoption commitments — fixed 03 Sep 2026

1. Whatever wins under §3.5 is **implemented in `pipeline/visual_module.py`**, not
   left in the bench. A bench that is not adopted earns nothing (step 6 of the bench method, README).
2. If nothing clears the floor, **nothing is adopted**, and the negative result is
   written up in full with the same weight as an adoption.
3. Either way the corpus is re-run and before/after numbers are reported
   (step 7 of the bench method, README).
4. `BIAS_CAVEAT` stays on every report regardless of which model wins. No accuracy
   result retires it.
5. Losers are written up with **this project's own measured numbers**, not with
   citations (step 8 of the bench method, README).

---

## Amendments

### A1 — 03 Sep 2026, before any scoring: a transcription error in §9, caught by the anchor check

`PROTOTYPE_FINDINGS.md` §9 lists **segment 39** in its `fear (0.40–0.70)` row. The
saved run it analysed labels segment 39 **`angry`, confidence 0.4646**.
`ground_truth.py:anchor_check()` refused to release any label until this was
resolved.

Two facts in §9 itself settle it:

- §9's angry row states the range **0.46–0.95**. The angry group as listed spans
  0.5277–0.9523. Only adding segment 39 at 0.4646 produces the stated 0.46.
- §9's fear row states **0.40–0.70**. Removing segment 39 leaves exactly
  0.3999–0.7023.

Segment 39 belongs to the angry group; it was typed into the wrong row. The
ground-truth **class is unchanged** — both rows describe a neutral visible
expression — so no number in this bench moves. Only the tier improves, from
`inferred` to `grouped`. Recorded here rather than edited
silently into §9.

This is the anchor check doing the job it was written for, on the first run.

### A2 — 03 Sep 2026, after Bench A ran: a second pooling mode, added post hoc

**This is a metric decision made after seeing data, and it is recorded as one.**

§3.2 fixed the primary Bench A metric as "the share of the 20 verified-faceless
segments where a detector reports a face". It did **not** fix how frame detections
are pooled into a segment, and the bench originally used only the pipeline's rule:
a segment has a face if *any* frame in its window does.

Under that rule every detector fired inside 15–18 per cent of the frames in
author-verified faceless windows — opencv 17.6 per cent, mtcnn 16.8, ssd 15.1. If
the incumbent's Haar cascade were the cause, the stronger detectors should have
fired far less. That near-equality was the signal that something other than
detector quality was being measured.

**What it was.** §9's Methodology states the ground truth was observed at the
segment's **midpoint frame**, with one or two neighbours opened only where the
midpoint was ambiguous. A segment that is b-roll at its midpoint can still cut
back to the talking head before it ends. `disagreement_analysis()` splits the
detections in those windows by how many detectors agree, and four frames were
opened and looked at to test the split:

| Frame | Agreement | §9's description of the segment | What is actually in the frame |
|---|---|---|---|
| `frame_0291` | all three | "Empty desk top-down shot" | a large, clear, front-facing human face |
| `frame_0176` | all three | "Phone in hand, b-roll" | a large, clear human face holding a phone |
| `frame_0059` | opencv only | "Phone in hand, b-roll" | a phone over a desk, no face; camera-lens cluster visible |
| `frame_0108` | opencv only | "Phone lock screen close-up" | a phone lock screen over a desk, no face |

Four of four behaved as the split predicts. **Unanimous detections in faceless
windows are real faces §9 never inspected; incumbent-only detections are genuine
hallucinations**, and the mechanism §9 hypothesised — the triple camera-lens
cluster presenting three-blob face geometry — is visible in `frame_0059`.

Those four frames are recorded in `report_bench.INSPECTED_FRAMES` with what was
seen. None of them is used as a label: §9 remains the only human ground truth in this bench, and this is
a check on a hypothesis about the *metric*, not new data.

**What changes.** A second pooling mode, `midpoint`, is added and scored alongside
the pipeline's `any`. Midpoint compares a detector against exactly the frame the
human looked at, so it is the valid measurement; `any` is what production does, so
it remains the deployment-relevant one. **Both are reported for every detector,
always, and neither is suppressed.**

**What this does not license.** The two modes do not agree on significance, so the
post-hoc choice is load-bearing and is treated as such. The write-up states the
result under both, states which detector wins under each, and does not present the
more favourable one alone. The §3.5 decision rule is applied to both, and if they
select different detectors that disagreement is the finding.

### A3 — 03 Sep 2026: the bench was running the detector in a configuration the pipeline does not use

Caught by the pipeline-fidelity anchor (`anchor_pipeline.py`), not by inspection.

The anchor reproduced the saved run **exactly** — 77 of 77 segment labels and 77
of 77 confidences, running `pipeline.visual_module` unmodified over the same 572
frames. That established the pipeline is deterministic and that §9's ground truth
still describes the code as it stands.

Comparing that run frame by frame against the bench's own `opencv` sweep then
showed the two disagreeing on **28 of 572 frames** (95.10 per cent agreement). The
cause was `align`: `run_detect.py` called `extract_faces(align=False)` while
`visual_module` reaches the detector through `DeepFace.analyze`, which aligns by
default. Alignment in deepface is not a crop transform applied after the fact — it
rotates on the eye landmarks and re-detects, so it changes **whether a face is
found**. Re-running the 28 differing frames with `align=True` matched the pipeline
on **28 of 28**.

Two consequences, and the second is the more important:

1. **Bench A would have benched a configuration the product does not run.** The
   incumbent row in particular would have been a different `opencv` from the
   deployed one.
2. **Bench B would have handicapped every classifier.** All nine FER candidates
   are trained on aligned face crops. Feeding them unaligned ones would have
   depressed every score for a reason that has nothing to do with the models.

`run_detect.ALIGN` is therefore `True`, the flag is recorded in every detection
file, and **the entire sweep was discarded and re-run**. No number measured before
this point is reported anywhere. The frame counts quoted in the write-up are from
the aligned sweep.

The general lesson is the one the anchor was written for: a bench that does not
reproduce production is measuring something else, and the only way to know is to
run production and diff it.

### A4 — 03 Sep 2026: `mtcnn`'s cost forced a change to the run order

A seven-frame timing probe, run to plan the remaining sweep, put `mtcnn` at
roughly **5.5 seconds per frame** at 3840×2160 with `align=True` — about **52
minutes for this one 9.5-minute video**, against 0.06–1.3 s/frame for every other
candidate. The alignment padding of A3 is why: the detector is handed an image four
times the area, and a three-stage cascade pays for that at every scale.

That probe ran alongside another sweep and its numbers are **planning estimates,
not results**. The per-detector timings published in `FACIAL_MODEL_ANALYSIS.md`
are the `seconds_per_frame` each full 572-frame sweep records for itself, and only
those are quoted as measurements.

**What changed.** `mtcnn` was moved to run **last**, after the crops and the
classification bench, because those are on the critical path and it is not. If its
sweep does not complete, `mtcnn` is reported as **accuracy not measured** — never
estimated, and never carried over from the discarded unaligned run.

A detector costing five times the video's own duration is close to disqualifying
for this pipeline whatever its accuracy, but that is stated as a cost fact and is
not used to avoid measuring it.

### A5 — 03 Sep 2026: the expression ground truth is selected on the incumbent's errors

**The most serious methodological problem in this bench, found before the
classification results were read, and it invalidates one of the pre-registered
comparisons.**

§3.1 recorded that the 44 expression labels come from "the segments §9 describes
in prose". What that sentence did not draw out is *why* §9 described them. §9's
Failure Mode B tables exist to document the incumbent's mistakes, so the 44 break
down as **43 of §9's 46 mismatches plus exactly one of its 11 matches**.

The sample is therefore selected on the incumbent being wrong. Scoring the
incumbent on it is close to guaranteed to return near zero, and it does:
**1 of 44, 2.27 per cent**, with 38 of 38 verified-neutral segments called
NEGATIVE. That number is not the channel's accuracy and must never be quoted as
one.

**What this invalidates.** §3.5's Bench B rule — "detectably better than the
incumbent (exact McNemar, p < 0.05)" — is now trivially satisfiable and therefore
meaningless. It is **withdrawn** for Bench B and replaced, before the results were
read, by the two comparisons the sampling does not corrupt:

1. **Against the always-NEUTRAL floor.** §3.4 already fixed this at 38/44 = 86.36
   per cent, and it remains the bar a candidate has to clear.
2. **Against each other.** No challenger influenced which segments §9 chose to
   write about, so the comparison *among the eight challengers* is unbiased. Only
   the incumbent's position in the table is compromised.

**What replaces it as the primary end-to-end number.** §9 partitions all 77
segments and states its own overall figure — **16 of 77, 20.8 per cent** — for the
deployed channel. The same composite is computed for every candidate pipeline:
for each of the 77 segments, does the channel return the right thing, where "right"
is no-face on the 20 verified-faceless segments and the correct three-class label
on the 44 with a verified expression. The 13 segments with a verified face but no
verified expression are **unknown**, so the result is reported as an interval —
all 13 wrong to all 13 right — rather than as a point estimate.

That composite is unbiased with respect to every candidate, is directly comparable
to §9's own published 20.8 per cent, and is what the write-up leads with. The
44-segment table is retained and reported as what it actually is: a **conditional
repair test** — given a segment the incumbent got wrong, does another model get it
right?

Recording this before reading the challenger results is the point. Discovering the
selection effect afterwards, in a table where challengers happened to beat the
incumbent by eighty points, would have been worthless.

### A6 — 03 Sep 2026: the Bench A rule selects `mtcnn`; `yunet` was adopted instead. A declared deviation.

**Stated as a deviation rather than presented as compliance.**

`mtcnn` was run on the 77 midpoint frames only (A4). It scored **0 of 20 false
positives, 54 of 57 recall, 96.1 per cent**, significantly better than the
incumbent (p = 0.0078).

Applying §3.5 mechanically: lowest false-positive rate → `mtcnn` and `yunet` tie at
0 of 20 (`ssd` is excluded, its recall is detectably worse). The tie breaks on
(a) accuracy over all 77 → **`mtcnn` (96.1%) over `yunet` (93.5%)**. So the rule as
written selects `mtcnn`.

**Why that tie-break should not be trusted here.** The four leading detectors are
statistically indistinguishable from one another:

| Comparison | Right of 77 | Exact McNemar |
|---|---|---|
| `mtcnn` vs `yunet` | 74 vs 72 | p = 0.5000, n = 2 |
| `mtcnn` vs `yolov8n` | 74 vs 74 | p = 1.0000, n = 2 |
| `yolov8n` vs `yunet` | 74 vs 72 | p = 0.6250, n = 4 |
| `yolov8n` vs `retinaface` | 74 vs 73 | p = 1.0000, n = 1 |
| `retinaface` vs `yunet` | 73 vs 72 | p = 1.0000, n = 3 |

Tie-break (a) fires on a **two-segment difference the data cannot resolve**, and it
fires before tie-break (b), speed, ever gets to run. That ordering is a defect in
the rule, visible only now that the numbers exist. The rule is not rewritten to
hide it.

**What was adopted, and on what ground.** `yunet`, on tie-break (b), for two
reasons both fixed before `mtcnn`'s accuracy was known:

1. **Cost.** 0.062 s/frame against 4.637 — **0.6 minutes per video against 44.2**.
   A4 recorded, before measuring, that a detector costing five times the video's own
   duration is close to disqualifying for a product that analyses videos on demand.
2. **Coverage.** `mtcnn` has **no pooled score at all** — it was never run on the
   full 572 frames, so it cannot be compared on the deployment-relevant metric.
   Adopting a candidate measured on 77 frames over one measured on 572 would be
   adopting the less-evidenced option.

`yunet` also carries the lowest behavioural risk of the four: its confidences span
0.90–0.94, so like `opencv` it leaves `FACE_CONFIDENCE_THRESHOLD` inert and the
swap changes exactly one thing. `yolov8n`'s run down to 0.27, which would start the
gate rejecting frames and change two things at once.

**What a reader should take from this.** On this evidence `yunet`, `yolov8n`,
`retinaface` and `mtcnn` are one group, all clearly better than the incumbent, and
the choice among them is a cost and risk decision rather than an accuracy one. The
rule's letter says `mtcnn`; the rule's purpose is served by `yunet`; and the gap
between those two sentences is recorded here rather than smoothed over.

---

## References

Verified 03 Sep 2026 from primary sources. None of these justifies a model choice;
they justify which models are worth measuring.

- Salas-Cáceres, J., Lorenzo-Navarro, J., Castrillón-Santana, M., Picazo-Peral, P.,
  & Moreno-Gil, S. (2026). Evaluating the robustness of specialized and
  general-purpose facial expression recognition systems across varied scenarios.
  *Frontiers in Artificial Intelligence*, 9. doi:10.3389/frai.2026.1800342
- Wen, Z., Lin, W., Wang, T., & Xu, G. (2021). Distract Your Attention: Multi-head
  Cross Attention Network for Facial Expression Recognition. arXiv:2109.07270.
  Code and AffectNet-8 checkpoint: github.com/yaoing/DAN (MIT)
- Savchenko, A. V. (2022). HSEmotion: High-speed emotion recognition library.
  *Software Impacts*, 14, 100433. doi:10.1016/j.simpa.2022.100433. Library, ONNX
  weights and per-model AffectNet accuracies: github.com/sb-ai-lab/EmotiEffLib
- Goodfellow, I. J., et al. (2013). Challenges in Representation Learning: A report
  on three machine learning contests. arXiv:1307.0311 — the FER-2013 dataset. Class
  counts used in §5.3 (disgust 547, happy 8,989 of 35,887) verified 03 Sep 2026
- Ryumina, E., Dresvyanskiy, D., & Karpov, A. (2022). In Search of a Robust Facial
  Expressions Recognition Model: A Large-Scale Visual Cross-Corpus Study.
  *Neurocomputing*. doi:10.1016/j.neucom.2022.10.013
- Cheong, J. H., Jolly, E., Xie, T., Byrne, S., Kenney, M., & Chang, L. J. (2023).
  Py-Feat: Python Facial Expression Analysis Toolbox. *Affective Science*, 4(4),
  781–796. doi:10.1007/s42761-023-00191-4
- Grafsgaard, J. F., Wiggins, J. B., Boyer, K. E., Wiebe, E. N., & Lester, J. C.
  (2013). Automatically Recognizing Facial Expression: Predicting Engagement and
  Frustration. *Proceedings of the 6th International Conference on Educational
  Data Mining*
- Buolamwini, J., & Gebru, T. (2018). Gender Shades. *PMLR* 81. Already in
  the project's verified citation list
- Fan, Xiao & Washington (2023). arXiv:2308.04674. Already in that list
