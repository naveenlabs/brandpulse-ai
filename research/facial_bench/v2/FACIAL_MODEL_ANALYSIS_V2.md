# Facial channel v2 — models measured against ground truth collected for the purpose

**Started 03 Sep 2026, labels collected 03 Sep 2026, written 04 Sep 2026.**
Pre-registration: [`PROTOCOL.md`](PROTOCOL.md), written before any frame was sampled
and before any label was collected. Every number below is re-derived from raw data
by [`verify_claims.py`](verify_claims.py).

Sections 1–5 describe the ground truth and are final: they were fixed before any
model was scored and no result can change them. Sections 6 onward are the model
results.

---

## 1. Why there is a v2

v1 (`../FACIAL_MODEL_ANALYSIS.md`, 03 Sep 2026) scored six detectors and nine
emotion models and adopted **no** emotion model, because none beat an
always-NEUTRAL constant. That finding is defensible, but the ground truth it rested
on had four defects that v1 documented against itself. v2 exists to remove them.

| # | v1 defect | v1 reference | What v2 does |
|---|---|---|---|
| 1 | **One video, one face.** All 77 segments came from a single presenter, so nothing separated "the model is bad" from "the model is bad *at this face*". | v1 §2.3 | 15 videos, **8 speakers**, held-out speakers |
| 2 | **Zero NEGATIVE labels.** The reviewer was never negative, so the anger question was literally unanswerable. | v1 §2.1, §9.4 | corpus deliberately includes 5 critically-framed reviews |
| 3 | **Selection effect.** The 44 expression labels were 43 of §9's 46 mismatches plus 1 of 11 matches — the labels were selected *on the incumbent's errors*. | v1 §2.3 | sample drawn by seed **before** any model ran |
| 4 | **Transcribed from prose** written for another purpose, at the segment, after pooling. | v1 §2.2 | labels collected at the **frame**, blind, in a purpose-built tool |

Two further changes follow from those:

- **The unit is the frame, not the segment.** v1 pooled frame predictions into
  Whisper segments and scored the pooled result, which confounded the model's error
  with the pooling rule's error. Here the label and the prediction are both at the
  frame, so a number in this file is a property of the model alone.
- **A reliability ceiling exists.** v1 had none, and therefore could not distinguish
  *the models are bad* from *the task is ill-posed on a single still*. Both readings
  were consistent with v1's result. §3 settles it.

The candidate set is deliberately **unchanged** from v1 (PROTOCOL.md §6). Changing
the ground truth *and* the candidates in the same step would confound the two, and
v1's numbers would stop being comparable.

---

## 2. What was collected

**Corpus.** 15 videos, 8 speakers, **11,087** frames extracted at 1 fps
(`corpus.py`, `acquire.py`). Every field in `corpus.py` was read from YouTube on
03 Sep 2026 with `yt-dlp --skip-download --print` and is quoted verbatim; frame
counts were verified against duration within ±1 frame at acquisition.

**Sample.** 600 frames, **40 per video**, drawn uniformly without replacement,
seed **20260903** (`sample.py`). No stratification by content, no exclusion of
frames that looked hard, and — critically — drawn before any detector or classifier
was run on this corpus.

**Presentations.** 648 = 600 first presentations + **48 hidden duplicates** (8%),
each re-shown at least 60 presentations after its original so the second rating
measures consistency rather than short-term recall.

**Collected.** **646 of 648** rated in `label_here.html`, exported
`facial_labels_v2.json` (2026-09-03T16:06:33Z). Two first presentations were left
unrated and are excluded rather than guessed:

- `i63u-iAnhuk:frame_0064` (Marques Brownlee, dev)
- `SSC0RkJuBVw:frame_0102` (Mrwhosetheboss, dev)

Both are dev, so the holdout is complete at 160/160. 2 of 600 is 0.33% of the draw
and cannot move any figure here materially, but it is stated rather than rounded
away.

**Blinding** (PROTOCOL.md §5.4). The tool showed no model prediction, no bounding
box, no confidence, no v1 label, no split label and no speaker name. Verified by
searching the generated 101 KB page for every model name, detector name, split name
and speaker name: **zero leaks**.

### 2.1 The labels, as clicked

598 first presentations were rated. They divide as:

| Set | n | Composition |
|---|---:|---|
| Face-presence set | **595** | 344 with a face, 251 without |
| — excluded, `face_unsure` | 3 | rater could not tell whether a face was present |
| Expression set | **320** | of the 344 faces, those with a readable expression |
| — excluded, `expr_unsure` | 24 | a face, but the expression was unreadable |

| Fine label | n | Three-class | n |
|---|---:|---|---:|
| neutral | 196 | NEUTRAL | **196** |
| happy | 102 | POSITIVE | **114** |
| surprised | 12 | | |
| sad | 6 | NEGATIVE | **10** |
| angry | 4 | | |

Rater abstentions (`expr_unsure`, `face_unsure`) are excluded from the gold sets and
counted here, because they are a property of the frame, not of any model. **Model**
abstentions are the opposite case and are scored as wrong (PROTOCOL.md §8).

### 2.2 Per speaker

| Split | Speaker | n | face | no face | expr | neu | hap | ang | sad | sur |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | Marques Brownlee | 199 | 90 | 109 | 82 | 56 | 21 | 1 | 2 | 2 |
| dev | Mrwhosetheboss | 159 | 85 | 71 | 81 | 32 | 46 | 1 | 1 | 1 |
| dev | Jon Adams | 40 | 29 | 11 | 24 | 20 | 2 | 1 | 1 | 0 |
| dev | Seth Fowler | 40 | 21 | 19 | 19 | 11 | 7 | 0 | 0 | 1 |
| holdout | Jeremy Fragrance | 40 | 37 | 3 | 36 | 24 | 11 | 0 | 0 | 1 |
| holdout | ShortCircuit | 40 | 30 | 10 | 29 | 22 | 4 | 0 | 1 | 2 |
| holdout | Dave2D | 40 | 27 | 13 | 27 | 21 | 0 | 1 | 1 | 4 |
| holdout | The Tech Chap | 40 | 25 | 15 | 22 | 10 | 11 | 0 | 0 | 1 |

Two things are visible immediately and neither was designable in advance. Presenters
differ sharply in baseline expressiveness — **Mrwhosetheboss is happy on 46 of 81
readable frames, Dave2D on 0 of 27** — which is the single strongest argument for
having split by speaker rather than by video. And the b-roll rate differs just as
sharply: Marques Brownlee is faceless on 109 of 199 sampled frames, Jeremy Fragrance
on 3 of 40.

---

## 3. The reliability ceiling

The number v1 did not have. 48 frames were shown twice, unmarked, at least 60
presentations apart.

| | Agreement | Cohen's κ |
|---|---:|---:|
| Fine (the eight buttons as clicked) | **87.5%** (42/48) | **0.804** |
| Three-class (POSITIVE / NEUTRAL / NEGATIVE) | **87.5%** (42/48) | **0.804** |

The two rows being identical is not a coincidence and is not a rounding artefact:
**every one of the six disagreements crossed a three-class boundary.** None was a
within-class wobble.

| Frame | Speaker | First | Second |
|---|---|---|---|
| `Kk-RKpTAXmA:frame_0522` | ShortCircuit | neutral | happy |
| `Kk-RKpTAXmA:frame_0346` | ShortCircuit | neutral | happy |
| `5VMckmQneCk:frame_0383` | Mrwhosetheboss | happy | neutral |
| `Rlw_CI7pOKg:frame_0100` | The Tech Chap | happy | neutral |
| `Rlw_CI7pOKg:frame_0078` | The Tech Chap | neutral | expr_unsure |
| `1VjPETN3m6U:frame_0455` | Jon Adams | neutral | sad |

**Four of six are neutral ↔ happy** — the mild-smile boundary. That is where the
task is genuinely ambiguous on a single still, and it is a prediction this bench
makes about the models before scoring them: if the models fail anywhere, the
neutral/positive boundary is where a *human* already fails 4 times in 48.

κ = 0.804 is "substantial" on the conventional Landis–Koch bands, so the taxonomy is
usable. But 87.5% is a hard operational ceiling: **a model cannot be expected to
exceed the agreement the rater achieves with themselves**, because above that point
the disagreement is in the ground truth, not in the model. Any candidate scoring
near or above 87.5% would need explaining, not celebrating.

This matters for how v1 is read. v1 could not tell whether its models were bad or
its task was impossible. The ceiling now says the task is **not** impossible: there
is 29.7 points of genuine headroom between the dev majority-class constant (57.8%,
§4) and the human ceiling (87.5%). A model that fails to close any of it is failing
at something a human demonstrably can do.

---

## 4. The split, as the seed drew it

By **speaker**, never by video (PROTOCOL.md §7): 5 of the 15 videos are Marques
Brownlee and 4 are Mrwhosetheboss, so a video-level split would have put the same
face on both sides and the holdout would have measured nothing.

`1VjPETN3m6U` (Jon Adams) and `JpN1DQdV4G4` (Seth Fowler) were **forced into dev on
contamination grounds, not preference** — both were analysed in v1 and their results
have already been read. A video whose results have been seen cannot serve as a
holdout.

| | Speakers | Face frames | with face | faceless | Expression frames | POS | NEU | NEG | Majority constant |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **dev** | Jon Adams, Seth Fowler, Marques Brownlee, Mrwhosetheboss | 435 | 225 | 210 | **206** | 80 | 119 | 7 | **57.8%** |
| **holdout** | The Tech Chap, Dave2D, ShortCircuit, Jeremy Fragrance | 160 | 119 | 41 | **114** | 34 | 77 | 3 | **67.5%** |

The four holdout faces appear nowhere in dev. Holdout is 26.7% of the sampled frames
and covers 4 speakers, clearing both pre-registered floors (≥25%, ≥3 speakers).

**A difference worth stating before it is used:** dev is 48.3% faceless (210/435),
holdout only 25.6% (41/160). Face detection is therefore an *easier* problem on the
holdout than on dev, and the two splits' Bench A numbers are not directly
comparable to each other. They are each compared against their own baselines, which
is what the adoption rule requires anyway.

---

## 5. Q2 (anger) is underpowered — the pre-registration binds

PROTOCOL.md §2 fixed this before collection:

> **If the collected labels contain fewer than 20 anger frames, Q2 is reported as
> underpowered and no claim is made either way.**

**The labels contain 4.**

| | |
|---|---:|
| Frames labelled `angry` | **4** (3 dev, 1 holdout) |
| Frames labelled `sad` | 6 |
| All NEGATIVE frames | **10** of 320 (3.1%) |
| Pre-registered floor | 20 |

The four anger frames are `0jHtyF_rCqU:frame_0509` (Mrwhosetheboss, dev),
`4KbrxIpQgkM:frame_0094` (Marques Brownlee, dev), `1VjPETN3m6U:frame_0137`
(Jon Adams, dev) and `vOhuf18b-g8:frame_0156` (Dave2D, holdout).

**Therefore no claim is made about Q2 in either direction.** Per-class NEGATIVE
recall is still reported in §7 with its sample size attached, because suppressing a
measured number would be worse than reporting an underpowered one — but it is not
evidence and is not used in the adoption decision.

This is the pre-registration doing the work it was written to do. Without it, an
n=4 recall figure could have been reported as either a success or a failure
depending on which was convenient, and neither reading would have been honest.

### 5.1 The underpowering is itself the finding

v1's defect #2 was that its single reviewer was never negative. v2 answered that by
building a corpus around it. By the `tone_hint` recorded in `corpus.py` — read from
each video's own title, never from a label — **6 of the 15 videos are framed
critically, sceptically or with disappointment** (4 `critical`, 1 `sceptical`,
1 `disappointed`), and a further 5 are `mixed`. Only 4 are straightforwardly
`positive`:

| Video | Speaker | Framing | Title |
|---|---|---|---|
| `4KbrxIpQgkM` | Marques Brownlee | critical | Nothing Phone 3 Review: They Lied! |
| `5VMckmQneCk` | Mrwhosetheboss | critical | Samsung S25 Ultra Review - Things just got Messy. |
| `SAb4zRyxrD4` | Marques Brownlee | critical | Samsung Galaxy S25/Ultra Impressions: What Happened? |
| `Kk-RKpTAXmA` | ShortCircuit | critical | Can they LEGALLY say this?? - Sony WH-1000XM6 |
| `SSC0RkJuBVw` | Mrwhosetheboss | sceptical | Apple Vision Pro - Is it worth $3500? |
| `vOhuf18b-g8` | Dave2D | disappointed | Samsung Fold 7 - Why Don't I Love This More?? |

The corpus was chosen to produce anger. It produced **4 anger frames in 320 readable
ones** — and the framing did not predict where they landed:

- Only **2 of those 6 negatively-framed videos** produced any anger frame at all
  (`4KbrxIpQgkM`, `vOhuf18b-g8`). Four produced none.
- **2 of the 4 anger frames came from videos that are not negatively framed** —
  `0jHtyF_rCqU` is `positive` ("Apple are you seeing this!?") and `1VjPETN3m6U`
  is `mixed`.

Widening to all NEGATIVE frames (angry + sad, n=10) does not rescue it either: 4 of
the 6 negatively-framed videos contributed one, and `SAb4zRyxrD4` ("What Happened?")
and `SSC0RkJuBVw` ("Is it worth $3500?") contributed none.

PROTOCOL.md §10 named this in advance as threat 5: *"Reviewers can be negative in
words while staying affable on camera."* The measurement now supports that as a
property of the domain rather than as an excuse. Tech reviewers criticising a product
do not, as a rule, look angry while doing it — they stay pleasant on camera and put
the criticism in the words. Whatever the emotion models can or cannot do, **the
facial channel has very little negative affect available to detect in this genre**,
and a system that infers brand sentiment from a presenter's face is reading a signal
that is largely absent at exactly the moments it would matter most.

That is a limitation of the channel's premise, not of any checkpoint, and no better
model fixes it. It is the strongest argument in this bench for down-weighting the
facial channel in the orchestrator (v1 §12.1) rather than for replacing the model
inside it.

---

## 6. Bench A — face presence

Six detectors, one label per frame (largest region), `align=True`, against the
595-frame face-presence set. Scored on both splits; the holdout was opened once,
after §10's dev decision was written to `DEV_DECISION.json`.

**Dev — 435 frames, 225 with a face, 210 without**

| Detector | Accuracy | 95% CI | Recall | False positives | FP rate | s/frame | vs `yunet` |
|---|---:|---|---:|---:|---:|---:|---|
| retinaface | 97.2% (423/435) | 95.2–98.4 | 99.6% | 11/210 | 5.2% | 1.151 | p=0.3449 |
| yolov8n | 97.2% (423/435) | 95.2–98.4 | 100.0% | 12/210 | 5.7% | 0.106 | p=0.3616 |
| **yunet** *(deployed)* | **95.9%** (417/435) | 93.6–97.4 | 92.0% | **0/210** | **0.0%** | **0.056** | — |
| mtcnn | 93.8% (408/435) | 91.1–95.7 | 99.1% | 25/210 | 11.9% | 3.911 | p=0.2110 |
| opencv *(DeepFace default)* | 79.8% (347/435) | 75.7–83.3 | 83.1% | 50/210 | 23.8% | 0.384 | **p<0.0001** |
| ssd | 73.8% (321/435) | 69.5–77.7 | 49.3% | 0/210 | 0.0% | 0.072 | **p<0.0001** |
| *always_face* | 51.7% (225/435) | 47.0–56.4 | 100.0% | 210/210 | 100.0% | — | p<0.0001 |
| *never_face* | 48.3% (210/435) | 43.6–53.0 | 0.0% | 0/210 | 0.0% | — | p<0.0001 |

**Holdout — 160 frames, 119 with a face, 41 without**

| Detector | Accuracy | 95% CI | Recall | False positives | FP rate | vs `yunet` |
|---|---:|---|---:|---:|---:|---|
| retinaface | 98.1% (157/160) | 94.6–99.4 | 100.0% | 3/41 | 7.3% | p=1.0000 |
| yolov8n | 98.1% (157/160) | 94.6–99.4 | 100.0% | 3/41 | 7.3% | p=1.0000 |
| **yunet** *(deployed)* | **98.1%** (157/160) | 94.6–99.4 | 97.5% | **0/41** | **0.0%** | — |
| mtcnn | 95.0% (152/160) | 90.4–97.4 | 100.0% | 8/41 | 19.5% | p=0.2266 |
| opencv | 87.5% (140/160) | 81.5–91.8 | 95.8% | 15/41 | 36.6% | **p=0.0002** |
| ssd | 81.2% (130/160) | 74.5–86.5 | 74.8% | 0/41 | 0.0% | **p<0.0001** |
| *always_face* | 74.4% (119/160) | 67.1–80.5 | 100.0% | 41/41 | 100.0% | p<0.0001 |
| *never_face* | 25.6% (41/160) | 19.5–32.9 | 0.0% | 0/41 | 0.0% | p<0.0001 |

### 6.1 v1's `yunet` adoption replicates, on faces v1 never saw

v1 adopted `yunet` on one speaker. On 8 speakers, 4 of them held out:

- **No detector significantly beats it** on either split (best p = 0.2110 on dev,
  0.2266 on holdout). `retinaface` and `yolov8n` edge it on raw accuracy by 1.3
  points on dev and tie it on holdout, and neither difference survives the test.
- **`opencv`, DeepFace's default and v1's incumbent, is significantly worse on
  both splits** (p < 0.0001, p = 0.0002) with 4.6× and 5.0× its own accuracy gap
  in false positives. Swapping it out was the right call and this is an
  independent confirmation of it, not a re-reading of the same data.
- `yunet` is **70× faster than `mtcnn`** and **21× faster than `retinaface`** on
  this hardware (0.056 vs 3.911 vs 1.151 s/frame).

### 6.2 The number that matters for this system: 0 of 251

Pooled across both splits, **`yunet` produced zero false positives on all 251
rater-verified faceless frames.** `opencv` produced 65.

That asymmetry is the whole argument for `yunet` here, and it is not the same as
the accuracy argument. `retinaface` and `yolov8n` have higher recall (100% vs
92.0% on dev) but pay for it with 11–12 false faces. In *this* pipeline a false
face is strictly worse than a missed face: a missed face degrades the segment to
"no facial reading", which the orchestrator already handles, whereas a false face
on product b-roll injects a confident emotion label derived from a wall or a
handbag, and that label then argues with the other three channels. A
precision-first detector is the correct choice for a conflict-detection system,
and this is now measured rather than asserted.

### 6.3 What this does *not* say about v1

v1 reported `yunet` firing in 9 of 20 verified-faceless **segments** (`opencv`
15 of 20). This bench reports 0 of 251 verified-faceless **frames**. These are not
the same measurement and the second does not overturn the first. They differ in
unit (a pooled segment fires if *any* frame in it fires), in corpus (one speaker
vs eight), and in how the ground truth was built (transcribed from a prose review
vs collected against the frame). Any of the three could contribute. What v2
establishes is the cleaner quantity — the per-frame false-positive rate on
purpose-collected labels — and on that quantity the deployed detector is exact.

### 6.4 The confidence gate is still inert where it matters

At `visual_module.FACE_CONFIDENCE_THRESHOLD` = 0.50, **the deployed detector loses
no detections at all**; across the whole candidate set only `yolov8n` drops any,
and only 2. v1 measured this gate as inert on one speaker (0 of 415 detections
below it); it is inert on eight. The gate is not what controls the
false-positive rate — the detector is.

---

## 7. Bench B — emotion models

Nine models on the crops `retinaface` produced, three-class, against the
320-frame expression set. A frame the rater could read but the crop detector
missed is an abstention and is scored **wrong** (PROTOCOL.md §8); in the event no
model abstained on any scored frame, so this rule did not affect any number below.

**Dev — 206 frames: POSITIVE 80, NEUTRAL 119, NEGATIVE 7. Constant = 57.8%**

| Model | Accuracy | 95% CI | Macro-F1 | NEG on neutral | vs constant |
|---|---:|---|---:|---:|---|
| trpakov_vit | **59.7%** (123/206) | 52.9–66.2 | 0.437 | 9/119 (7.6%) | +1.9 pts, **p=0.7343** |
| *always_NEUTRAL* | 57.8% (119/206) | 50.9–64.3 | 0.244 | 0/119 | — |
| **deepface_fer** *(deployed)* | 47.6% (98/206) | 40.9–54.4 | 0.381 | 33/119 (27.7%) | −10.2 pts, p=0.1079 |
| dima806_vit | 46.6% (96/206) | 39.9–53.4 | 0.341 | 25/119 (21.0%) | −11.2 pts, p=0.0542 |
| *always_POSITIVE* | 38.8% (80/206) | 32.4–45.6 | 0.186 | 0/119 | −18.9 pts, p=0.0069 |
| emotieffnet_b0_va | 38.3% (79/206) | 32.0–45.1 | 0.298 | 28/119 (23.5%) | −19.4 pts, p=0.0028 |
| motheecreator_vit | 37.9% (78/206) | 31.5–44.7 | 0.331 | 35/119 (29.4%) | −19.9 pts, p=0.0005 |
| emotieffnet_b2 | 30.6% (63/206) | 24.7–37.2 | 0.262 | 54/119 (45.4%) | −27.2 pts, p<0.0001 |
| dan_affectnet8 | 29.6% (61/206) | 23.8–36.2 | 0.274 | 57/119 (47.9%) | −28.2 pts, p<0.0001 |
| tanneru_beit_large | 22.3% (46/206) | 17.2–28.5 | 0.169 | 38/119 (31.9%) | −35.4 pts, p<0.0001 |
| hardlyhumans_vit | 5.8% (12/206) | 3.4–9.9 | 0.058 | 104/119 (87.4%) | −51.9 pts, p<0.0001 |
| *always_NEGATIVE* | 3.4% (7/206) | 1.7–6.8 | 0.022 | 119/119 (100.0%) | −54.4 pts, p<0.0001 |

**Holdout — 114 frames: POSITIVE 34, NEUTRAL 77, NEGATIVE 3. Constant = 67.5%**

| Model | Accuracy | 95% CI | Macro-F1 | NEG on neutral | vs constant |
|---|---:|---|---:|---:|---|
| *always_NEUTRAL* | **67.5%** (77/114) | 58.5–75.4 | 0.269 | 0/77 | — |
| trpakov_vit | 36.8% (42/114) | 28.6–46.0 | 0.311 | 38/77 (49.4%) | −30.7 pts, p<0.0001 |
| **deepface_fer** *(deployed)* | 34.2% (39/114) | 26.1–43.3 | 0.277 | 26/77 (33.8%) | −33.3 pts, p<0.0001 |
| *always_POSITIVE* | 29.8% (34/114) | 22.2–38.8 | 0.153 | 0/77 | −37.7 pts, p=0.0001 |
| motheecreator_vit | 20.2% (23/114) | 13.8–28.5 | 0.220 | 57/77 (74.0%) | −47.4 pts, p<0.0001 |
| emotieffnet_b0_va | 19.3% (22/114) | 13.1–27.5 | 0.198 | 49/77 (63.6%) | −48.2 pts, p<0.0001 |
| dima806_vit | 17.5% (20/114) | 11.7–25.6 | 0.201 | 61/77 (79.2%) | −50.0 pts, p<0.0001 |
| tanneru_beit_large | 15.8% (18/114) | 10.2–23.6 | 0.167 | 52/77 (67.5%) | −51.8 pts, p<0.0001 |
| emotieffnet_b2 | 12.3% (14/114) | 7.5–19.6 | 0.147 | 63/77 (81.8%) | −55.3 pts, p<0.0001 |
| dan_affectnet8 | 11.4% (13/114) | 6.8–18.5 | 0.141 | 65/77 (84.4%) | −56.1 pts, p<0.0001 |
| hardlyhumans_vit | 4.4% (5/114) | 1.9–9.9 | 0.057 | 70/77 (90.9%) | −63.2 pts, p<0.0001 |
| *always_NEGATIVE* | 2.6% (3/114) | 0.9–7.5 | 0.017 | 77/77 (100.0%) | −64.9 pts, p<0.0001 |

**On the holdout, every one of the nine models is below a constant, and every one
significantly so.** The best is 30.7 points below it.

---

## 8. Where they fail: neutral

Per-class recall makes the failure mode unambiguous. This is the deployed model
and the dev leader, on both splits:

| | POSITIVE recall | NEUTRAL recall | NEGATIVE recall |
|---|---:|---:|---:|
| deepface_fer, dev | 80.0% | **26.1%** | 42.9% (n=7) |
| deepface_fer, holdout | 58.8% | **24.7%** | 0.0% (n=3) |
| trpakov_vit, dev | 50.0% | **68.9%** | 14.3% (n=7) |
| trpakov_vit, holdout | 23.5% | **41.6%** | 66.7% (n=3) |

The models can see a smile. `deepface_fer` recovers 80% of POSITIVE frames on dev.
What they cannot do is see *nothing*: they recover a quarter of neutral frames and
convert most of the rest into an emotion that is not there. Since neutral is 61%
of the dev expression set and 68% of the holdout, that single failure is enough to
put every model below a constant.

The systematic direction of the error is the part that matters for this project.
**Eight of the nine models call verified-neutral frames NEGATIVE at rates from
21.0% to 87.4% on dev, and 33.8% to 90.9% on holdout.** `hardlyhumans_vit` at
90.9% is functionally an always-NEGATIVE detector wearing a classifier's API. A
system whose purpose is to decide whether a review is authentic cannot take a
channel that manufactures negativity on a presenter who is simply talking: the
manufactured negativity becomes cross-channel disagreement, the disagreement
becomes a conflict flag, and the flag lowers the Authenticity Score of a video
that did nothing wrong. This is the failure mode `PROTOTYPE_FINDINGS.md` §11
measured from the other direction, and condition 3 of the adoption rule was
written for it before any of these numbers existed.

### 8.1 Against the ceiling

| | Constant | Best model | Human ceiling | Headroom | Captured |
|---|---:|---:|---:|---:|---:|
| dev | 57.8% | 59.7% | 87.5% | 29.7 pts | **6.5%**, p=0.7343 |
| holdout | 67.5% | 36.8% | 87.5% | 20.0 pts | **negative** |

**No model came within 27.8 points of the ceiling on either split.** This is the
comparison v1 could not make, and it converts a soft conclusion into a hard one:
the task is demonstrably doable to 87.5% by a human on the same single stills, so
the failure is in the models, not in the question.

---

## 9. What the holdout was for

`trpakov_vit` led the dev set at 59.7%, was the only model to beat the constant at
all, and was the **only** model to satisfy condition 3 on dev — 9 of 119 neutral
frames called NEGATIVE, 7.6%, comfortably inside the 15% limit. On dev it looked
like the one candidate worth taking seriously.

On four unseen faces it scored **36.8%**, 30.7 points *below* the constant, and
its negative-on-neutral rate went from **7.6% to 49.4%** — from the best in the
field to a failure 3.3 times the limit it had just passed.

Nothing about the dev result was wrong; it simply did not describe the model. Had
this bench stopped at dev, or drawn its split by video instead of by speaker, or
scored the holdout more than once, `trpakov_vit` is the model that would have been
proposed for adoption. It is the clearest justification in this project for the
speaker-level holdout and for sealing it in code (`DEV_DECISION.json`,
fingerprint `72eed1436294…`, `dev_unchanged_since_freeze: true`).

---

## 10. The adoption decision

The rule was fixed in PROTOCOL.md §9 before any result existed. All four
conditions must hold.

| Model | C1 sig. beats constant (dev) | C2 macro-F1 > constant | C3 ≤15% NEG on neutral | C4 repeats on holdout |
|---|---|---|---|---|
| trpakov_vit | no (p=0.7343) | yes | **yes** (7.6%) | no |
| deepface_fer *(deployed)* | no | yes | no (27.7%) | no |
| dima806_vit | no | yes | no (21.0%) | no |
| motheecreator_vit | no | yes | no (29.4%) | no |
| emotieffnet_b0_va | no | yes | no (23.5%) | no |
| emotieffnet_b2 | no | yes | no (45.4%) | no |
| dan_affectnet8 | no | yes | no (47.9%) | no |
| tanneru_beit_large | no | no | no (31.9%) | no |
| hardlyhumans_vit | no | no | no (87.4%) | no |

### **Decision: nothing is adopted.**

`DEV_DECISION.json` recorded **zero candidates still eligible** before the holdout
was opened, so the holdout could not have rescued anything; it was scored anyway,
once, because it answers Q3 (generalisation) independently of the adoption
question.

Note that condition 1 is read as *significantly better*, not *significantly
different*. Exact McNemar is two-sided, so a model losing badly to the constant
also produces p < 0.05 — six of them do. Without the direction check, 6 failures
would have registered as passes. That reading is enforced in
`report_v2.py` and unit-tested.

**Detector:** no change proposed, and none is warranted. §6.1 confirms `yunet`
against five alternatives on 8 speakers; PROTOCOL.md §9 pre-committed to leaving
that adoption alone unless v2 contradicted it, and it did not.

---

## 11. Sensitivity and robustness

**The surprise mapping.** `surprised → POSITIVE` was the primary mapping and
`surprised → NEUTRAL` the pre-declared sensitivity check (PROTOCOL.md §5.2). Under
the alternative, dev accuracies rise for both the leader and the constant —
`trpakov_vit` 59.7% → 61.7%, constant 57.8% → 59.7% — leaving the gap at 1.9
points and the ranking unchanged. **The conclusion does not depend on how the 12
surprised frames were mapped.**

**Abstention.** No model abstained on any scored frame: `retinaface` produced a
crop for every frame in the expression set, so the PROTOCOL.md §8 rule that scores
abstention as wrong never bound. It is reported because it was pre-registered, not
because it changed anything.

**The two unrated frames.** Both are dev, both are first presentations, 0.33% of
the draw. The holdout is complete at 160/160.

**The splits are not comparable to each other.** Holdout is 25.6% faceless against
dev's 48.3%, and its expression set is more neutral-heavy (67.5% vs 57.8%). Both
Bench A and Bench B numbers are therefore higher on the holdout for reasons that
have nothing to do with the models. Every comparison in this file is against a
baseline computed on the *same* split, which is what makes the comparison valid.

**What was not tested.** Action Units, temporal smoothing across adjacent frames,
and any model outside v1's candidate set. Holding the candidate set fixed was
deliberate (PROTOCOL.md §6) so that v1's and v2's numbers stay comparable; the
cost is that v2 cannot say whether a tenth model would have done better.

---

## 12. What follows

**The facial channel is measurably worse than a constant on unseen speakers, and
v1's conclusion is confirmed on ground truth that has none of v1's four defects.**
The deployed model, `deepface_fer`, is 33.3 points below an always-NEUTRAL
constant on the holdout and calls 33.8% of verified-neutral frames NEGATIVE.

Three things follow, in order of value:

1. **Down-weight the facial channel in the orchestrator**, as the vocal channel
   already is. PROTOCOL.md §9 pre-committed to this "regardless of which model
   wins", and §7's holdout supplies the weight: the deployed model's measured
   held-out accuracy, 39/114 = **0.342**. This mirrors
   `VOCAL_ONLY_CONFLICT_WEIGHT = 0.489` exactly, including its honest label as a
   *reasonable inference* rather than a verified fact.
2. **Keep `yunet`, and keep `BIAS_CAVEAT`.** The detector half of this channel is
   excellent — 98.1% on unseen faces with zero false positives on 251 faceless
   frames. The channel's problem is entirely downstream of detection.
3. **Do not chase another checkpoint.** Nine models spanning FER-2013, AffectNet
   and MMI training data, four architectures, and published accuracies from 57.4%
   to 84.34% produce a spread of 4.4% to 36.8% on held-out speakers here, and the
   ranking does not follow the published figures. v1 measured that correlation at
   **−0.62**; v2 does not contradict it. A tenth checkpoint is the least
   promising remaining move.

The deeper finding is §5's, and it is not about checkpoints at all: in this genre
there is very little negative facial affect to detect. A corpus built to contain
criticism yielded 4 anger frames in 320. Even a perfect classifier would have
almost nothing to report at exactly the moments a brand-authenticity system cares
about most. That is a limitation of the channel's premise — worth stating plainly,
and worth designing around rather than modelling harder.

---

## 13. Item 1 is done: the channel is down-weighted

Implemented the same day, before this file was finished, because PROTOCOL.md §9
pre-committed to it. Full before/after in
[`DAMPING_FIX_RESULT.md`](DAMPING_FIX_RESULT.md); the headline:

- `FACIAL_ONLY_CONFLICT_WEIGHT = 0.342` in the orchestrator,
  `FACIAL_CHANNEL_RELIABILITY = 0.342` in `visual_module`, mirroring the vocal
  channel's 0.489.
- The facial channel was computed for the 12-video corpus (**9,125 frames**, 50.9%
  with a detected face) so that the rule could be measured on real four-channel
  segments rather than argued for.
- **Coverage:** the rule fires on 18 of 481 controller-scored segments (3.7%).
- **Effect on this corpus: zero**, for two reasons that are both worth stating.
  `llama3.2` returned a conflict score of 0.0 on 473 of 481 segments and damping
  multiplies; and all 8 non-zero segments are genuine multi-channel disagreements
  where no channel is the lone dissenter, so the rule correctly declined to touch
  any of them. The second is a result about specificity, not an absence of one.
- **An unanticipated finding:** adding the facial channel cuts the *vocal* rule's
  coverage from 89 of 481 to 49. A fourth channel makes "every other channel
  agrees" harder to satisfy, so `vocal_bench`'s published 89-of-481 figure is
  specific to a corpus that had no facial channel. That is a correction to how an
  existing number should be read, and it was invisible until this run.

The harness reproduces `vocal_bench`'s 89 of 481 exactly when the facial channel is
stripped back out, which is what licenses the rest of those numbers.
