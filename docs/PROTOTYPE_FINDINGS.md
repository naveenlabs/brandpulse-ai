# BrandPulse AI — Prototype Findings & Limitations

> **Living document.** This file is updated as we discover, verify, and (where applicable) fix issues
> during prototype evaluation. Every claim below is backed by real data pulled from actual saved
> reports in `outputs/` — not speculation. Each finding includes: what we found, how we found it,
> concrete evidence, why it happens, and what we did/propose to do about it.

**Test videos:**
- iPhone 17 Pro Max review, `youtu.be/1VjPETN3m6U` / `youtu.be/q0aFOxT6TNw`
- Nike Mind 001 review, `youtu.be/JpN1DQdV4G4`

**Reports referenced:** `Apple (Iphone 17 Pro Max).json`, `Apple (Iphone 17 Pro Max - 1).json`,
`Apple (Iphone 17 Pro Max - 5).json` (canonical, all fixes applied), `Nike (Mind 001).json`

---

## 1. Transcript Sentiment Channel — DistilBERT SST-2 Miscalibration

### What we found
The transcript-sentiment model (`distilbert-base-uncased-finetuned-sst-2-english`) produces
confidently wrong labels on plain, neutral, factual sentences, and separately, suppresses correct
moderate-confidence judgments into a misleading NEUTRAL label.

### Root cause
SST-2 is a **binary classifier trained only on movie reviews** — it has no native concept of
"neutral." Our pipeline (`audio_module.py::add_transcript_sentiment`) bolts on a workaround: if the
model's top-label confidence is below `NEUTRAL_CONFIDENCE_THRESHOLD = 0.70`, the label is overridden
to NEUTRAL. This workaround only catches *honest* uncertainty — it does nothing when the model is
confidently wrong, and it actively destroys signal when the model is moderately-but-correctly leaning
toward a real sentiment.

### Evidence — Failure Mode A: Confidently wrong
| Segment | Text | Label | Confidence | Human judgment |
|---|---|---|---|---|
| 0 | "Today we are talking about six months later with the 17 Pro Max. How has my experience been?" | NEGATIVE | 99.37% | Neutral — no sentiment content at all |
| 6 | "This iPhone 16 Pro Max is titanium." | POSITIVE | 81.4% | Neutral — plain factual statement |
| 7 | "And the question was how are they going to hold up compared to each other? I'm answering that in another video." | NEGATIVE | 99.9% | Neutral — administrative statement |

### Evidence — Failure Mode B: Correct lean suppressed into NEUTRAL
| Segment | Text | Label | Confidence | What actually happened |
|---|---|---|---|---|
| 38 | "...you are looking at a real, real hefty bill, $1,200. That is so much money." | NEUTRAL | 44.46% | Model's real top guess was NEGATIVE at ~55.5% confidence — below the 70% cutoff, so the code overrode it to NEUTRAL, hiding a real (if moderate) negative sentiment |

### Why this matters
This channel feeds directly into the orchestrator's conflict scoring. A wrongly-labeled transcript
can trigger a **false conflict flag** — the system thinks "words say X, face/voice say Y" when the
words were actually neutral/correctly-negative all along. This is a direct contributor to the
inflated flag rate observed (41-52 of 77 segments flagged across test runs, ~55-67%).

### Proposed fix (future work, not implemented in prototype)
Replace SST-2 with a model trained with a **genuine 3-class system** (positive/neutral/negative) from
the start — e.g. a RoBERTa sentiment model trained on a 3-class corpus — rather than a 2-class model
with a post-hoc confidence-threshold workaround.

---

## 1B. Transcript Sentiment — Full Word-by-Word Review of All 77 Segments

### What we found
Following the same no-shortcuts methodology used for the comment channel (§2), every one of the 77
transcript segments from a real test run (`Apple (Iphone 17 Pro Max - 1).json`) was read individually
and judged by hand against its assigned POSITIVE/NEGATIVE label. No segment was skipped or treated as
"too ambiguous to call."

> **SUPERSEDED 31 Aug 2026 — retained as the historical record, not as a current figure.**
> This section's ~48% error rate was measured before hand-labelled ground truth existed, on a
> single video, against a two-class POSITIVE/NEGATIVE judgement, and on the **pre-fix**
> segmentation (`transcript_bench/MERGE_DEFECT.md`). All three make it non-comparable with
> anything measured since.
>
> The channel has since been benchmarked properly: 16 candidates on 599 hand-labelled segments
> from 12 videos and 6 speakers, with a speaker-disjoint holdout. The incumbent model scored
> **0.463 three-class accuracy** on the 400-segment selection set and **0.382** on the sealed
> 199-segment holdout — on the holdout, worse than always guessing NEUTRAL (0.482).
>
> The diagnosis in this section was nonetheless **correct**, and the bench confirmed its root
> cause by replication: the fault is the two-class-plus-confidence-threshold construction, not
> DistilBERT. `cardiffnlp/twitter-xlm-roberta-base-sentiment` was adopted on 31 Aug 2026,
> lifting holdout accuracy to 0.678 and NEUTRAL recall from 0.073 to 0.740.
>
> See `transcript_bench/TRANSCRIPT_MODEL_ANALYSIS.md` and `transcript_bench/WINNER.md`.

### Result: 37 mismatches out of 77 segments — a ~48% error rate
This is **worse than the comment channel's 28% error rate** (§2). The transcript channel is less
reliable than the comment channel, not more, despite both relying on conceptually similar sentiment
classifiers.

### Why transcripts fare worse than comments
Comments are short, self-contained, single-topic statements — close to the kind of text SST-2 was
trained on (short movie review snippets). This transcript is a **continuous, rambling spoken review**
full of setup sentences, rhetorical questions, qualifying statements, and mid-thought transitions —
structurally very different from anything in SST-2's training data.

### Evidence — Category 1: Clearly neutral/factual statements forced into POSITIVE or NEGATIVE (dominant pattern, ~24 of the 37 mismatches)
Setup sentences, transitions, and factual statements get assigned high-confidence sentiment labels
they don't deserve.

| Segment | Text | Labeled | Should be |
|---|---|---|---|
| 0 | "Today we are talking about six months later with the 17 Pro Max..." | NEGATIVE (0.99) | NEUTRAL |
| 2 | "but it might not be for everybody if you are somebody who you are looking for" | NEGATIVE (1.00) | NEUTRAL |
| 3 | "...you want to know are you going to use your hard earned money?... I want to help you make that decision today." | NEGATIVE (0.95) | NEUTRAL |
| 4 | "...how is the actual material, the aluminum going to hold up." | NEGATIVE (0.96) | NEUTRAL |
| 6 | "This iPhone 16 Pro Max is titanium." | POSITIVE (0.81) | NEUTRAL |
| 8 | "I want to talk about today this six months later, how this is held up." | POSITIVE (0.93) | NEUTRAL |
| 13 | "...they're going to keep their phone inside a case for the most part anyways." | NEGATIVE (0.99) | NEUTRAL |
| 15 | "The one thing I would look at is how much does the screen scratch up?" | NEGATIVE (1.00) | NEUTRAL |
| 18 | "I did have it in a screen protector for a little while." | NEGATIVE (0.99) | NEUTRAL |
| 30 | "However, the screen size on this is big." | POSITIVE (0.91) | NEUTRAL |
| 33 | "And when it's in your pocket compared to something like the 17 or the 16 E, that's one of" | NEGATIVE (0.99) | NEUTRAL |
| 48 | "I am so used to, I've been using iPhones for so long that I'm always 100% of the time." | POSITIVE (0.98) | NEUTRAL |
| 54 | "Now, I'm not on my phone 24, 7." | NEGATIVE (1.00) | NEUTRAL |
| 56 | "...the camera zoom length on this phone. On, on this iPhone, you get your three cameras." | NEGATIVE (0.96) | NEUTRAL |
| 57 | "You get your regular, your ultra wide, and then you've got your telephoto lens." | POSITIVE (0.82) | NEUTRAL |
| 59 | "My daughter was in gymnastics and I was really, really far away." | NEGATIVE (1.00) | NEUTRAL |
| 71 | "...is for the person that wants the absolute best that Apple has to offer? I don't think you always need that." | NEGATIVE (0.99) | NEUTRAL |

(plus 7 further cases of the same pattern: segments 5, 7, 11, 14, 17 [borderline], 44, 51)

### Evidence — Category 2: Explicit positive statements mislabeled NEGATIVE (~5 strong cases)
| Segment | Text | Labeled |
|---|---|---|
| 10 | "I don't know how well you can see it, but I don't really notice any scratches at all." | NEGATIVE (0.99) |
| 17 | "...I don't have any scratches on my phone. I don't have any cracks on the glass." | NEGATIVE (0.86) |
| 21 | "...So I'm **really happy** with the build quality of this phone." | NEGATIVE (0.98) |
| 68 | "**What's so great** about having this OLED screen is only the pixels that are white." | NEGATIVE (0.91) |

### Evidence — Category 3: Explicit negative/complaint statements mislabeled POSITIVE (~4 cases)
| Segment | Text | Labeled |
|---|---|---|
| 26 | "...First as far as **cons** go, the size and the weight of this thing. It is a chunky, chunky boy." | POSITIVE (0.88) |
| 31 | "**What I don't like** is when a phone, when I can't read stuff with my fingers because it's just that big." | POSITIVE (0.98) |
| 41 | "However, $1200 for a phone that doesn't do all that much more than all the other phones on Apple's lineup." | POSITIVE (1.00) |
| 72 | "Is it worth the upgrade for people who have 16 Pro Max? **Absolutely not.**" | POSITIVE (0.96) |

### Why this matters more than the comment channel's accuracy issue
The transcript channel is compared against face/voice/comments on **nearly every single segment** in
the orchestrator's conflict scoring — it is the most load-bearing of the four channels. A ~48% error
rate here means roughly half of the "words" input to the conflict-detection logic across the whole
video is unreliable, which is very likely the single largest contributor to the inflated flag rate
(41-52 of 77 segments flagged, ~55-67%) — larger than either the low-expressiveness face/voice issue
or the comment-channel inaccuracy on their own.

### Status
Documented. Same proposed fix as §1 (replace SST-2 with a genuine 3-class model) applies here, and
would likely have a bigger impact on overall system accuracy than fixing any other single channel,
given how load-bearing this channel is in the orchestrator's per-segment comparison.

---

## 2. Comment Sentiment Channel — tabularisai Accuracy (Manual Verification)

### What we found
A full manual review of all 100 classified comments (not a sample) against the actual comment text
found a **~28% error rate (28/100 mismatches)**, with a dominant, systematic pattern.

### Methodology
Every one of the 100 comments in the saved report (`all_comments` field) was read individually and
independently judged by hand against its assigned label (POSITIVE/NEUTRAL/NEGATIVE), with no
tolerance for skipped/ambiguous cases — each was given a definitive call.

### Evidence — dominant error pattern: contrast/comparison sentences
The model frequently mislabels comments that praise the **new** phone by contrasting it with an
**old** phone's problem. It picks up on the negative-sounding keyword ("hot," "scratched," "sucks")
without understanding the comparison structure.

| # | Comment (abbreviated) | Labeled | Should be |
|---|---|---|---|
| 3 | "...my 17 really doesn't get that hot... never overheated. Battery life is better too." | NEGATIVE (0.82) | POSITIVE |
| 14 | "17pm is so much better than 16pm imo with the heat being way more controlled" | NEGATIVE (0.85) | POSITIVE |
| 31 | "...not a big difference other than appearance and battery life **loving it tho**" | NEGATIVE (0.81) | POSITIVE |
| 74 | "...this phone lasts me 2 days consistently" (praising battery) | NEGATIVE (0.72) | POSITIVE |
| 70 | "Im upgrading from a 12promax. **Cant wait.**" | NEGATIVE (0.48) | POSITIVE |
| 66 | "...Lovin it" | NEGATIVE (0.70) | POSITIVE |
| 33 | "Just got mine (blue) ❤" | NEGATIVE (0.33) | POSITIVE |

(16 total cases of this exact pattern found — positive comments mislabeled NEGATIVE.)

### Evidence — secondary error pattern: neutral content forced into a sentiment class
Genuine questions or plain factual statements get force-fit into POSITIVE or NEGATIVE.

| # | Comment (abbreviated) | Labeled | Should be |
|---|---|---|---|
| 56 | "Titanium is more durable than aluminum... insulator, not good for heat" (factual/technical) | NEGATIVE (0.52) | NEUTRAL |
| 72 | "First! Hello from western coast of Alaska!" (irrelevant aside) | POSITIVE (0.40) | NEUTRAL |
| 53 | "In my opinion the 17 pro max feels small to me" (personal preference, not a complaint) | NEGATIVE (0.84) | NEUTRAL |
| 99 | "U guys think this is a good upgrade over my iPhone 7 Plus?" (question) | POSITIVE (0.58) | NEUTRAL |
| 100 | "...is it worth upgrading from 14 plus realistically speaking..." (question) | POSITIVE (0.52) | NEUTRAL |

(9 total cases of this pattern found.)

### Evidence — reverse errors: genuinely negative content labeled POSITIVE
| # | Comment | Labeled | Should be |
|---|---|---|---|
| 35 | "I have a 15 Pro Max and it runs really hot, and the battery life is crap." | POSITIVE (0.61) | NEGATIVE — clear complaint |
| 87 | "...a very tiny chip... it's really annoying me" | POSITIVE (0.39) | NEGATIVE — annoyance/complaint |

### Why this matters
This channel anchors **60% of the Brand Health Score formula**. A 28% error rate, systematically
biased toward over-counting NEGATIVE, means the aggregate 35/29/36 (POSITIVE/NEUTRAL/NEGATIVE) split
is not trustworthy as-is — the true distribution is likely meaningfully more positive than reported.

### Proposed fix (future work)
Either fine-tune/prompt-adapt the classifier specifically for comparison/contrast sentence structures,
or supplement with a rule-based pre-check for comparative language ("better than," "doesn't X
anymore," "used to be") before classification.

---

## 3. Video-Level Comment Aggregation — Misleading Label & Confidence Display

### What we found
The aggregate `comment_sentiment` object can display a NEUTRAL label even when NEUTRAL is the
**smallest** of the three groups, and its displayed "confidence" number is unrelated to how confident
the system actually is in that label.

### Evidence
From a real run: distribution was `POSITIVE: 36, NEUTRAL: 28, NEGATIVE: 36`. POSITIVE and NEGATIVE
are **tied** at 36 each — NEUTRAL is the smallest group at 28. Yet the displayed label was
**NEUTRAL**, because `aggregate_video_sentiment()` has a rule: *"if the top two categories are tied,
default to NEUTRAL."* The displayed confidence (65.07%) is the **mean confidence across all 100
comments combined**, regardless of label — not a measure of confidence in the NEUTRAL label
specifically.

### Why this matters
A reader sees "NEUTRAL (65%)" and reasonably assumes most comments were neutral with high confidence.
Neither is true: NEUTRAL won by tie-break default, not by count, and 65% describes unrelated average
certainty across all 100 individual classifications.

### Proposed fix (future work)
Report the tie explicitly (e.g. "POSITIVE/NEGATIVE tied at 36 each — defaulted to NEUTRAL") and
compute a label-specific confidence (e.g. mean confidence of only the comments belonging to that
winning label) rather than an all-comment average.

---

## 4. Orchestrator Conflict Scoring — Inconsistent Judgment on Similar Cases

### What we found
Two segments with structurally identical channel disagreement patterns received very different
conflict scores from the LLM orchestrator.

### Evidence
| Segment | Transcript | Face | Voice | Conflict Score | Flagged? |
|---|---|---|---|---|---|
| "Today we are talking about six months later..." | NEGATIVE | sad | angry | 0.789 | Yes |
| "This has been a really, really, really interesting phone..." | POSITIVE | sad | angry | 0.3 | No |

Both segments show the same structural pattern (words point one way, face/voice don't clearly
support it), yet scored 0.789 vs 0.3 — a large gap for cases a human would likely judge similarly.

### Why this matters
The conflict score is **not a deterministic formula** — it's generated by the LLM's own reasoning per
segment (see system prompt in `orchestrator.py`). This finding suggests the LLM's judgment is not
fully consistent across similarly-structured inputs, which limits the reproducibility/fairness of the
conflict-scoring mechanism.

### Status
Documented as a limitation. Not fixed — would require either a more constrained/rule-augmented
prompt, or a fundamentally different scoring approach (e.g. a fixed valence-comparison formula
instead of free LLM judgment).

---

## 5. Run-to-Run Reproducibility — Ollama Sampling Randomness (PARTIALLY FIXED — deeper cause isolated)

### What we found
Re-running the **exact same video** through the full pipeline multiple times, with no code changes,
produced significantly different final scores each time.

### Evidence (before fix)
| Run | Authenticity Score | Brand Health Score |
|---|---|---|
| Run 1 (14:50) | 18.92 | 7.57 |
| Run 2 (17:30) | 28.71 | 31.0 |

A swing of ~10 points on authenticity and ~23 points on brand health for the "same" video — far
exceeding this project's own stated reliability target of **±2 points** (set in the project's
evaluation strategy).

### Root cause
`orchestrator.py::_call_ollama()` was not setting a `temperature` or `seed` on the Ollama request.
LLMs sample from a probability distribution by default — the same prompt can produce a different
`conflict_score` each call. With 77+ segments per video, small per-segment variations compound into
large swings in the final aggregate scores.

### Fix applied
Added `"options": {"temperature": 0, "seed": 42}` to the Ollama request body in
`orchestrator.py::_call_ollama()`. This was judged a low-risk, one-line fix (not an architecture or
model change) and applied directly, unlike the other findings in this document which are documented
as future work only.

### Verification — rigorous, multi-step isolation (not assumed)

After applying the fix, two further full runs of the same video ("Pro Max 1" and "Pro Max 2," both
with the fix active) still showed a large difference: **53/77 segments flagged vs 19/77 flagged**,
and authenticity/brand-health scores that still differed substantially (24.14/9.66 vs 50.28/39.59).
At first glance this looked like the fix had failed. Rather than assume that, the actual cause was
isolated step by step:

**Step 1 — Is Ollama itself actually deterministic now?**
The exact same single segment payload was sent to Ollama directly (bypassing the full pipeline)
twice in a row, with `temperature: 0` and `seed: 42` set. **Result: byte-identical output both
times** (`conflict_score: 0.47`, identical narrative, identical everything). This confirms the fix
genuinely works at the model level — Ollama is not the source of the remaining variance.

**Step 2 — Is the input data feeding into Ollama actually identical between the two pipeline runs?**
Every one of the 77 segments' `text`, `transcript_sentiment`, `facial_emotion`, `vocal_emotion`,
`pitch_mean_hz`, and `energy_mean` were compared field-by-field between Pro Max 1 and Pro Max 2.
**Result: all 77 segments were perfectly identical on every field.** Nothing upstream (Whisper,
DeepFace, SpeechBrain, pyAudioAnalysis) introduced any variation between these two runs.

**Step 3 — So what actually differed?**
The **only** difference found anywhere in the two runs' inputs was the video-level
`video_comment_sentiment` field — present in *every one* of the 77 segments' prompts:
- Pro Max 1: `NEGATIVE (0.654)`
- Pro Max 2: `NEUTRAL (0.6492)`

This single field changed because of the comment-aggregation tie-break issue documented in §3 above:
the actual comment counts barely moved between runs (35/29/36 → 36/28/36, a 1-comment shift), but
because POSITIVE and NEGATIVE were nearly tied either way, that tiny shift was enough to flip the
*entire video-level label* from NEGATIVE to NEUTRAL.

### Conclusion
The temperature/seed fix **is working correctly** — Ollama reliably reproduces output for a truly
fixed prompt (proven directly, not assumed). The remaining run-to-run instability is **not** a
failure of that fix; it is a **downstream consequence of Finding §3** (the comment aggregation
tie-break rule) cascading into every single segment's LLM prompt via the shared
`video_comment_sentiment` field. Because the LLM weighs that field as one of 4 channels in its
judgment for *every* segment, a single flipped video-level label was enough to shift the LLM's
reasoning across roughly half the video — which is a large, but mechanistically well-explained,
effect.

### Why this is not being fixed in the prototype
Unlike the temperature/seed change (a one-line, unambiguous correctness fix), resolving this requires
a genuine **design decision**: how should near-tied comment distributions be aggregated (e.g.
weighted-confidence scoring instead of majority-vote-with-tie-break-to-neutral), and/or whether the
fetched comment set should be cached/frozen per video to eliminate live-fetch variability in the
first place. Both are legitimate future-work items, not bug fixes, so — consistent with how the other
model-accuracy findings in this document are handled — this is documented rather than patched.

### Proposed fix (future work)
1. Replace the majority-vote-with-neutral-tie-break rule in
   `comment_module.py::aggregate_video_sentiment()` with a method less sensitive to near-50/50 splits
   (e.g. a continuous weighted sentiment score rather than a discrete 3-way label).
2. Cache the fetched comment set per video (e.g. keyed by video_id) so re-analysing the same video
   does not re-fetch a slightly different live comment set each time.

---

## 6. Facial Emotion & Vocal Tone — Low-Expressiveness False Positives

### What we found
The system uses an **absolute** expressiveness standard for all reviewers — it flags conflict
whenever face/voice signals don't dramatically match the words, regardless of whether the speaker is
naturally calm/low-affect. This produces false positives on genuine but undemonstrative reviewers.

### Why this matters
This was the first limitation identified (prior to this evaluation pass) and remains the most
structurally significant one — it affects the majority of flagged segments across all test runs.

### Proposed fix (future work)
**Reviewer baseline calibration** — measure each speaker's natural expressiveness range first (e.g.
across the first N segments or a separate calibration pass), then score conflict *relative to that
speaker's own baseline* rather than an absolute standard. Not implemented in the prototype; proposed
as the principled fix.

---

## 7. Pitch / Energy — Undefined Contribution to Conflict Scoring

### What we found
`pitch_mean_hz` and `energy_mean` are sent to the LLM as part of the per-segment payload, but unlike
the three categorical channels (transcript/face/voice), there is **no explicit rule** for how these
numeric features should affect the conflict score. They are included as loosely-defined supporting
context, and whether/how the LLM actually uses them is unverified.

### Status
Documented as a limitation. Proposed future work: define explicit thresholds or rules for how
pitch/energy anomalies should factor into conflict scoring, to make their contribution auditable
rather than opaque.

---

## 8. YOLOv8 Logo Detection — Structural Placeholder

### What we found
`detect_logos()` in `visual_module.py` runs YOLOv8n, but the model's COCO-80 training classes
contain no brand-specific logos (Nike, Apple, etc.). It currently only works if a brand name happens
to match a generic COCO object class (e.g. "bottle").

### Status
Already documented in code as a known limitation. Real brand-logo detection requires a fine-tuned
model trained on brand-specific imagery — out of scope for the prototype, proposed as future work.

---

## 9. Facial Emotion Channel — Full Frame-by-Frame Visual Verification of All 77 Segments

### What we found
A full visual review of every one of the 77 segments' extracted video frames (`data/1VjPETN3m6U/frames/`)
against DeepFace's assigned `facial_emotion.dominant` label found a **~79% error rate (61/77 segments
wrong)** — only **16/77 (~21%) of segments had a facial emotion label that matched what is actually
visible in the frame.** This is the least reliable of the three channels manually verified so far,
well below the transcript channel (~48% error, §1B) and the comment channel (~28% error, §2).

### Methodology
The video was re-run after switching `app.py::_build_segments()` to a persistent
`data/<video_id>/frames/` directory (previously a temp folder auto-deleted after each run, which is
why this check wasn't possible until now). For every one of the 77 segments, the frame at the
temporal midpoint of the segment's `[start_s, end_s]` window was opened and visually inspected;
wherever the midpoint frame was ambiguous or the segment's `frame_count` suggested faces were detected
elsewhere in the window, 1-2 additional neighbouring frames were also opened and checked. Each
segment's visible expression (or absence of any face) was independently judged against the
`facial_emotion.dominant` label actually stored in the saved report
(`Apple (Iphone 17 Pro Max - 3).json`), with no segment skipped.

### Result breakdown — four categories

| Category | Count | % of 77 | Meaning |
|---|---|---|---|
| **Correct "no face"** | 5 | 6.5% | DeepFace correctly reported no face (`dominant: None`) and the frame genuinely has no human face |
| **False positive** | 15 | 19.5% | DeepFace reported a confident emotion, but the frame has **no human face at all** — only product b-roll (camera lenses, Apple logo, phone screen, hands) |
| **Match** | 11 | 14.3% | A real face is present and the assigned label is a reasonable description of the visible expression |
| **Mismatch** | 46 | 59.7% | A real face is present, but the assigned emotion is **not** what's visible (e.g. "sad"/"angry"/"fear" assigned to a neutral talking-head or even a visibly smiling/thumbs-up frame) |

**Overall accuracy = (Match + Correct-no-face) / 77 = 16/77 = ~20.8%. Error rate = ~79.2%.**
Of the 72 segments where DeepFace claimed to detect *any* face (False positive + Match + Mismatch),
only 11 (15.3%) were actually correct.

### Evidence — Failure Mode A: False face detection on pure product b-roll (15 segments)
DeepFace (`detector_backend="opencv"`, `FACE_CONFIDENCE_THRESHOLD = 0.50` in `visual_module.py`)
detects a "face" and assigns it a confident emotion in frames that contain **zero humans** — only a
phone's camera-lens cluster, the Apple logo, a lock-screen, or hands on a desk. These are b-roll
cutaways the reviewer uses while narrating off-camera.

| Segment | Timestamp | Claimed label (confidence) | What's actually in frame |
|---|---|---|---|
| 1 | 0:05–0:12 | sad (0.84) | Phone held face-down over desk, no person visible |
| 4 | 0:27–0:33 | surprise (0.91) | Two phones lying on desk, hand only |
| 6 | 0:44–0:48 | neutral (0.94) | Two phones held side-by-side, no face |
| 9 | 0:57–1:03 | fear (0.52) | Phone in hand, b-roll |
| 10 | 1:03–1:08 | fear (0.84) | Phone camera bump close-up |
| 11 | 1:08–1:15 | neutral (0.74) | Phone in hand, top-down desk shot |
| 13 | 1:24–1:29 | angry (0.54) | Phone in hand, b-roll |
| 17 | 1:43–1:48 | fear (0.51) | Phone lock screen close-up |
| 22 | 2:35–2:43 | sad (0.36) | Phone in hand, b-roll |
| 24 | 2:49–2:55 | neutral (0.82) | Phone in hand, sliver of out-of-focus hair top-right, no real face |
| 25 | 2:55–3:03 | neutral (0.49) | Phone in hand, b-roll |
| 30 | 3:34–3:38 | surprise (0.53) | Phone with blank screen on desk |
| 31 | 3:38–3:44 | fear (0.58) | Phone lock screen on desk |
| 41 | 4:42–4:53 | fear (0.64) | Empty desk top-down shot |
| 57 | 6:57–7:00 | fear (0.75) | Side profile turned away, mostly out of frame |

This means DeepFace's "face confidence" gate is matching on circular/symmetric patterns — most likely
the triple camera-lens cluster, which has the same rough 3-blob geometric layout as two eyes + a
mouth/nose that a basic Haar/OpenCV-style detector keys on.

### Evidence — Failure Mode B: Real face present, wrong/negatively-biased emotion (46 segments)
Even when a real face is correctly detected, DeepFace overwhelmingly defaults to sad/angry/fear
labels on ordinary neutral talking-head footage, and in the most extreme cases **mislabels visibly
positive expressions as negative ones**.

| Segment | Timestamp | Claimed label (confidence) | What's actually visible |
|---|---|---|---|
| 76 | 9:25–9:31 | **angry (0.97)** | Thumbs up, **smiling** — the single most contradictory case in the dataset |
| 32 | 3:44–3:51 | sad (0.72) | Smiling/smirking, content expression |
| 53 | 6:27–6:32 | (correctly "happy" 0.82) | *(included for contrast — proves DeepFace **can** detect happy correctly when it's unambiguous)* |
| 61 | 7:18–7:31 | sad (0.99) | Looking at phone, content/slightly smiling |
| 71 | 8:41–8:47 | sad (0.95) | Content, slight smile |
| 0 | 0:00–0:05 | sad (0.93) | Neutral/mildly skeptical look, not sad |
| 3, 26, 34, 35, 36, 39, 42, 43, 44, 51, 55, 56, 59, 63, 66, 72, 73 | various | angry (0.46–0.95) | Normal mid-sentence talking, neutral expression, hand gestures — no anger visible |
| 14, 15, 19, 20, 27, 29, 38, 47, 50, 52, 54, 58, 69, 74, 75 | various | sad (0.51–0.99) | Normal talking, often animated/enthusiastic gesturing — not sad |
| 33, 37, 40, 46, 62 | various | fear (0.40–0.70) | Normal talking, holding phone near face — no fear visible |

> **Correction, 03 Sep 2026.** Segment 39 was originally listed in the `fear` row
> above. It is in the `angry` row and has been moved there. The saved run labels
> segment 39 **`angry`, confidence 0.4646**, and this section's own stated ranges
> confirm it: the `angry` row says *0.46–0.95*, and the angry group produces 0.46
> only with segment 39 included, while the `fear` row's stated *0.40–0.70* is
> reproduced exactly once segment 39 is removed. Found by
> `facial_bench/ground_truth.py:anchor_check()`, which refuses to release any
> ground-truth label unless every claimed label and confidence in this section
> matches the saved run. **No conclusion in §9 changes** — both rows describe a
> neutral visible expression, so the error rate, the category counts and the
> corrected-input rerun in §11 are all unaffected. Logged in
> `facial_bench/CANDIDATE_MODELS.md` Amendment A1.
| 21 | 2:24–2:35 | neutral (0.89) | Mouth open wide, eyebrows raised — looks surprised/excited, opposite of "neutral" |

(Full per-segment list with exact timestamps for every one of the 46 mismatches was provided
separately in conversation and can be re-derived from `Apple (Iphone 17 Pro Max - 3).json`'s
`all_segments[*].model_outputs.facial_emotion` field cross-referenced with `start_s`/`end_s`.)

### Root cause analysis
Two independent, compounding problems:

1. **Face-detection false positives.** `FACE_CONFIDENCE_THRESHOLD = 0.50` (`visual_module.py`) is too
   permissive for the lightweight `opencv` detector backend used (`detector_backend="opencv"` —
   chosen for speed at 1 fps, per the module docstring). It passes geometric patterns on product
   close-ups as faces roughly 1 in 5 times a face is "detected" in this video.
2. **Emotion-classification negative bias on real faces.** DeepFace's underlying FER (facial emotion
   recognition) model appears biased toward sad/angry/fear on a bearded, deep-set-eyed, naturally
   low-affect speaker — consistent with the **documented accuracy disparities across face shape,
   skin tone, and expressiveness** already called out in `BIAS_CAVEAT` and the module docstring
   (Buolamwini & Gebru, 2018; Fan et al., 2023). This is the same root cause as Finding §6
   (low-expressiveness false positives), but this visual check proves it's worse than "doesn't
   register positive emotion strongly enough" — it actively **mislabels visibly positive expressions
   as negative** in multiple cases (segments 32, 61, 71, and especially 76).
3. **Mean/majority-pooling amplifies both problems.** `pool_emotions_per_segment()` mean-pools
   frame-level emotions into each Whisper segment window (see §-prior clarification on variable
   segment length). A 17-second segment (e.g. seg 52, 6:08–6:27) may pool over a dozen frames into one
   "dominant" label by majority vote — a single misdetected b-roll frame or one bad FER call can swing
   the whole segment's label, and there is no confidence-weighting or outlier rejection in the pooling
   logic.

### Why this matters
The facial emotion channel is one of 4 inputs to the orchestrator's per-segment conflict scoring
(`orchestrator.py::build_segment_payload`) and is **structurally load-bearing**: with a ~79% error
rate, the orchestrator is comparing largely-fabricated facial-emotion data against transcript/voice/
comment data on nearly 4 out of every 5 segments. Combined with the ~48% transcript error rate (§1B)
and the ~28% comment error rate (§2), this means **all three of the non-deterministic channels feeding
the orchestrator are independently unreliable**, and the facial channel is the worst of the three.
This is very likely a larger contributor to the inflated flag rate (often 50%+ of segments flagged
across test runs) than the LLM orchestration logic itself — the orchestrator is reasoning correctly
over largely incorrect inputs.

### Fix-now vs. future-work decision
**Not fixed in the prototype — documented as future work**, for the same reason as the transcript
(§1) and comment (§2) accuracy findings: there is no low-risk, single-line correction available here.
Genuine fixes require either a different pretrained model, a fine-tuning pass, or a redesign of the
pooling logic — all real engineering/research decisions, not bug fixes. (Contrast with the Ollama
`temperature`/`seed` fix in §5, which was a one-line correctness fix with no design tradeoff and was
applied immediately.)

### Proposed fixes (future work)
1. **Raise `FACE_CONFIDENCE_THRESHOLD`** (currently 0.50) and/or switch `detector_backend` from
   `"opencv"` to a more accurate backend (e.g. `"retinaface"` or `"mtcnn"`) to reduce false-positive
   face detection on product b-roll — at the cost of slower per-frame inference, which matters less
   here since frames are only sampled at 1 fps.
2. **Add a face-detection confidence floor before emotion classification** — i.e. don't run/trust the
   emotion head at all below a stricter face-confidence cutoff, rather than only gating on the current
   single 0.50 threshold.
3. **Replace or supplement DeepFace's FER model** with one independently validated for lower
   demographic/expressiveness bias, or recalibrate per-speaker (ties into the baseline-calibration fix
   already proposed in §6).
4. **Confidence-weighted pooling instead of simple majority vote** in `pool_emotions_per_segment()` —
   weight each frame's contribution by its own `face_confidence`/emotion-confidence so a handful of
   low-confidence misdetections in a long segment can't dominate the "dominant" label.
5. **Outlier rejection in pooling** — e.g. require a minimum number of corroborating frames before
   trusting a "dominant" emotion in segments with very low `frame_count` (several of the false
   positives above have `frame_count` of just 1).

### Status
Documented. This is the **third and most severe** of the three model-accuracy deep-dives in this
document (after §1B transcript and §2 comments), and reframes the relative reliability ranking of the
three non-deterministic channels: facial emotion (≈79% error) is markedly less trustworthy than
transcript sentiment (≈48% error), which is itself less trustworthy than comment sentiment (≈28%
error).

---

## 10. Vocal Tone Channel — SpeechBrain IEMOCAP Negative Bias (User-Verified)

### What we found
Across all 77 segments of the same test video, SpeechBrain's IEMOCAP emotion model
(`speechbrain/emotion-recognition-wav2vec2-IEMOCAP`, 4-class: angry/happy/sad/neutral) labeled
**57/77 (74%) of segments "angry"**, 17/77 (22%) "happy", 3/77 (4%) "neutral", and **0/77 "sad."**

### Verification method
Unlike the transcript (§1B), comment (§2), and facial (§9) reviews — each checked item-by-item against
saved text/frames — this channel cannot be visually or textually inspected the same way. It was
verified by **the project author listening to the actual video directly.** Ground-truth judgment: the
speaker's tone is predominantly **neutral** throughout, with only occasional mild happy/surprised/
disappointed moments, and **never angry**. This directly contradicts the model's 74%-angry majority
and its complete absence of any neutral-dominant read.

### Root cause
The same class of failure as the facial-emotion finding (§9). IEMOCAP is trained on **acted,
exaggerated emotional speech** from scripted drama performances, not natural conversational tone. A
calm, low-affect speaking voice — exactly the profile of this reviewer — gets systematically pulled
toward "angry," mirroring how DeepFace pulled the same speaker's neutral face toward "sad." This is
consistent with the documented demographic/expressiveness accuracy disparities already cited via
`BIAS_CAVEAT` (Buolamwini & Gebru, 2018; Fan et al., 2023) — the same underlying issue, here showing up
in the audio modality rather than the visual one.

### Why this matters
This is now the **third of four** orchestrator input channels shown to carry severe systematic bias
(transcript ~48% error, §1B; facial ~79% error, §9; vocal heavily skewed here). It reinforces the
document's central conclusion: the inflated conflict-flag rate observed across test runs is driven
mainly by unreliable channel inputs feeding the orchestrator, not by faulty LLM reasoning over correct
inputs.

### Status
Documented as future work. **Not fixed** — same reasoning as §1/§2/§9: there is no low-risk,
single-line correction available for a model-accuracy/bias limitation. Genuine fixes (model swap,
fine-tuning, or per-speaker baseline calibration — see §6) are research/design decisions, not bugs.

### Note — a separate implementation bug was found and fixed during this same investigation
While checking why `pitch_mean_hz` looked suspiciously low/zero on many segments (a question raised
alongside this vocal-tone review), a genuine **coding bug** was found in `audio_module.py::
extract_prosody()`: pitch was estimated once over each entire multi-second segment instead of
frame-by-frame like energy already was, causing 47/77 segments (61%) to incorrectly return 0.0 Hz.
This was fixed immediately (added `_estimate_pitch_hz_framewise()`, verified against the real audio
file: 47/77 → 0/77 zero-pitch segments, all recovered into a sane 128–224 Hz range) and is not listed
as a numbered finding here — it was an implementation defect we caught and corrected ourselves, not a
limitation of the modeling approach.

---

## 11. System-Level Compounding Effect — Recomputing Final Scores with Corrected Channel Inputs

> **Important framing note, read before the numbers below:** This section is a **sensitivity /
> diagnostic exercise**, not a prediction of what a fixed system would score. The "corrected" values
> used here come from the specific manual corrections documented in §1B, §2, §9, and §10 of this
> document — a different fix (different replacement model, different calibration method) would
> produce different numbers. **Nothing in this section should be read as a forecast or commitment for
> the final system's accuracy.** Its purpose is narrower and more defensible: to show whether the
> channel errors already documented are large enough to *materially change the system's overall
> verdict*, or whether they are minor noise that washes out. The answer turns out to be the former.

### What we did
Every other finding in this document evaluates one channel at a time. This section asks the natural
follow-up question: when all four documented error patterns are combined, what happens to the two
numbers a user actually sees — **Authenticity Score** and **Brand Health Score**?

Using a real saved report (`Apple (Iphone 17 Pro Max - 5).json`, 77 segments, 100 comments), each
channel's output was replaced with the corresponding verified correction already documented elsewhere
in this file:

| Channel | Correction applied | Source | Coverage |
|---|---|---|---|
| Transcript sentiment | 31 of the ~37 known mismatches relabeled (the ones with concrete textual evidence already tabulated in §1B); remaining ~6 left as-is | §1B | Partial, conservative |
| Facial emotion | 15 false-positive "face" detections on pure b-roll set to "no face"; 46 mismatches relabeled to the visually-observed expression (mostly "neutral", 4 to "happy") | §9 | Full (all 61 corrected segments) |
| Vocal tone | Every "angry" label changed to "neutral" (the verified aggregate bias direction); "happy"/"neutral" labels left untouched | §10 | Aggregate-pattern-based, not segment-by-segment re-listen |
| Comment sentiment | All 100 comments re-read and relabeled by hand (36/100 mismatches found in this fresh batch — consistent with §2's ~28% on the original batch) | This session | Full |

The corrected per-segment values were fed through the **real, unmodified orchestrator code**
(`orchestrator.run_orchestration()`), making genuine calls to the local Ollama LLM for all 77
segments — not a simulated or invented formula. The resulting `conflict_score`s were then passed
through the real, unmodified `scorer.compute_authenticity_score()` and `compute_brand_health_score()`.

### Result

| | Original (as reported) | Corrected inputs | Change |
|---|---|---|---|
| Segments flagged | 33 / 77 (43%) | **0 / 77 (0%)** | −33 |
| Authenticity Score | 26.55 | **80.57** | +54.0 |
| Brand Health Score | 10.62 | **51.91** | +41.3 |
| Comment sentiment label | NEGATIVE (41/100) | NEUTRAL (50/100) | winner flips |

Sanity checks performed before trusting this result: confirmed zero silent Ollama failures across all
77 corrected calls (no `parse_error`/`orchestration_error` fallbacks), confirmed real variance in the
output (not a degenerate all-zero result — e.g. segment 1 still scored 0.67 for a sensible reason: a
strongly positive transcript line with no corroborating face/voice signal), and manually inspected
that reasoning against the corrected payload.

### Why this matters
With the current, unfixed channels, this video — a calm, fairly ordinary 9-minute phone review —
is scored as showing **severe cross-channel deception** (Authenticity 26.55, deep into the "low
authenticity" range) and **poor brand health** (10.62). Under the corrected inputs, the same video
scores as **showing no real conflict** (0 flagged segments) with a **moderate, unremarkable brand
health reading** (51.91). The direction of the system's verdict — not just its precision — inverts.
This is the single strongest piece of evidence in this document that the four per-channel error
findings (§1B, §2, §9, §10) are not independent minor inaccuracies: when combined through the real
scoring pipeline, they are large enough to **flip the system's conclusion about the same video**.

### What this section does NOT claim
- It does **not** claim a future, fixed BrandPulse AI will score this video at 80.57/51.91 — those
  exact numbers depend entirely on which specific replacement models or calibration methods are
  eventually chosen for each channel, none of which are implemented in the prototype.
- It does **not** claim the corrected channel values used here are themselves perfectly accurate —
  the transcript correction is partial (31/37), and the vocal correction is an aggregate-pattern
  approximation rather than a full segment-by-segment re-verification.
- It **does** claim, with the above caveats, that the magnitude of the channel errors already found is
  large enough to flip — not just shift — the system's overall verdict on a real test video.

### Status
Documented. This section sits on top of, and depends on, Findings §1B, §2, §9, and §10 — it is not a
new error discovery but a demonstration of their combined downstream effect on the two scores that
matter most to an end user.

---

## 12. Second Test Video — Nike Mind 001 Review (`Nike (Mind 001).json`)

Everything below this point was found by repeating the same rigorous, line-by-line/frame-by-frame
verification methodology used in §1B, §2, §9, and §10 on a **second, independent video** — a ~13.8
minute Nike Mind 001 slide/mule review (29 Whisper segments, 100 comments, 827 extracted frames at
1 fps). The purpose was to check whether the biases already documented above are properties of this
specific pipeline/these specific models (and therefore should recur on any video), or whether they
were specific to the one Apple video tested so far. **They recur — in some cases more severely, and
with at least one new failure mode not previously documented.**

---

## 12A. Segment Boundary Granularity — Long Monologue Sections Produce Oversized Segments

### What we found
Segment durations in this video range from 3.4 seconds (segment 0) to **211.5 seconds** (segment 23) —
a 62× spread. Three segments in particular are extreme outliers: segment 22 (90.5s), segment 23
(211.5s), and segment 26 (91.2s). Each of these single segments gets exactly **one** transcript-
sentiment label, **one** pooled facial-emotion label, and **one** vocal-emotion label, despite spanning
over a minute and a half of continuous, topically-varied speech.

### Root cause
Whisper segments speech by detected pauses/silence breaks, not by fixed time windows. From
roughly the 4:45 mark onward, the reviewer shifts into one long, largely unbroken descriptive
monologue about the shoe's construction — there are no pauses long enough for Whisper's internal
voice-activity detection to register a break, so it keeps extending the same segment. Segments 0–21,
by contrast, are short because that part of the video has frequent cuts (talking head ↔ b-roll,
trying the shoes on, pausing to react), which create natural pause points Whisper splits on.

This is **not a bug** — Whisper is segmenting correctly according to its own pause-detection logic.
It is a structural consequence of using Whisper segment boundaries as the cross-channel alignment
spine (`audio_module.py` docstring: "segment boundaries... are the temporal anchors for DeepFace
pooling, SpeechBrain slicing, and pyAudioAnalysis extraction"): the spine's granularity is entirely
dependent on how often the speaker pauses, which varies enormously by content style (interview-style
cutting vs. continuous narration).

### Evidence
Segment 23 (375.2s–586.8s, 211.5 seconds long) contains, among other things: a complaint about a toe
clicking uncomfortably, praise for the logo placement ("really, really like"), a statement of having
"no issues with these whatsoever," a caution against wearing them on concrete, and a tangent about
shoe-sizing policy — genuinely mixed sentiment collapsed into one DistilBERT call that returned
NEGATIVE (0.9853) for the entire block.

### Why this matters
The longer a segment is, the more independent sub-topics and emotional shifts get flattened into a
single label per channel, which directly degrades the resolution of the orchestrator's per-segment
conflict scoring — a 211-second segment is treated by the rest of the pipeline exactly the same as a
3-second one, despite carrying ~60x more content and proportionally more chances for internal
sentiment to vary.

### Status
Documented as a structural/architectural observation, not an error. No fix proposed in the prototype —
a true fix would require re-segmenting independently of Whisper boundaries (e.g. a fixed-window or
sentence-level re-split above some duration threshold), which is a design change to the alignment
strategy, not a bug fix.

---

## 12B. Transcript Sentiment — Second Video Corroboration (29/29 segments reviewed)

### What we found
All 29 Whisper segments' text were read against the `transcript_sentiment.label` DistilBERT SST-2
assigned. Result: **~11/29 (38%) clear mislabels**, a further **~11/29 (38%) borderline/diluted by
segment size** (see §12A — several of these are the oversized monologue segments where one label
can't fairly represent the whole block), and **~7/29 (24%) correct.** This is the same systematic
failure mode as §1B (no true neutral class in SST-2, so purely factual/descriptive text gets forced
into NEGATIVE with high confidence) recurring on an independent video.

### Evidence — representative clear mislabels

| Segment | Text (truncated) | Label (confidence) | Why it's wrong |
|---|---|---|---|
| 0 | "Nike made this shoe to control your mind. Well, not exactly. Let me explain." | NEGATIVE (0.996) | Playful clickbait hook, not negative |
| 4 | "I don't know if they're gonna be like game-changing or if they're gonna be mind-controlling. I have no idea." | NEGATIVE (0.998) | Plain statement of uncertainty |
| 6 | "...They're not bad... They're definitely comfortable... It's not as aggressive as I was expecting." | NEGATIVE (0.994) | Net mildly positive/neutral, not negative |
| 12 | "And the fact that it moves and flexes, depending on how you're walking," | POSITIVE (0.999) | Incomplete, purely descriptive clause |
| 14 | "...was finally announced as January 8th for a retail price of $95," | NEGATIVE (0.959) | Pure factual price statement |
| 17 | "...this $95 pair of mules does not come in the standard Nike Orange box. Instead, it comes in a white box..." | NEGATIVE (0.995) | Neutral unboxing description |
| 24 | "...this is one of the most unique clicking pieces of footwear that I've ever seen..." | NEGATIVE (0.880) | "Most unique" is a positive framing |

### Why this matters
Confirms §1B's root cause is a property of the SST-2 model itself, not specific to one video's
phrasing style — it recurs at a similar rate (38% clear-mislabel here vs. ~48% on the Apple video,
the difference plausibly explained by this video having more long monologue segments where the
"correct" label is itself ambiguous, see §12A).

### Status
Documented — corroborates §1B. No new fix proposed; same future-work status as §1.

---

## 12C. Comment Sentiment — Second Video Corroboration (100/100 comments reviewed)

### What we found
All 100 comments' text were read against the tabularisai model's assigned label. **~13/100 confident,
clear mislabels** plus **~12/100 near-coin-flip calls (confidence 0.3–0.5) that landed on the wrong
side** — roughly a quarter of all comments directionally questionable, consistent with §2's ~28% error
rate on the Apple video's comment set.

### Evidence — representative mislabels

| Comment (truncated) | Label (confidence) | Why it's wrong |
|---|---|---|
| "The review I been waiting for" | NEGATIVE (0.623) | Anticipation/excitement, not negative |
| "Was waiting for this video from you" | NEGATIVE (0.629) | Same — anticipatory enthusiasm |
| "I've never wanted a new pair of Nikes so much since huarache back in the early 90's." | NEGATIVE (0.651) | Strong positive desire statement |
| "...so excited can't wait to get it" | NEGATIVE (0.294) | Contains the explicit word "excited" |
| "THE GOAT SETH" | NEUTRAL (0.389) | Strong compliment ("GOAT" = greatest of all time) |
| "I'm rocking them daily... dope shoe 🔥🔥🔥💪" | NEGATIVE (0.490) | Explicit slang praise + fire emojis |
| "would love more slides... those are my favorite... would definitely buy" | NEGATIVE (0.898) | Three separate positive-preference phrases |
| "I'm sceptical!" | POSITIVE (0.759) | The word itself states the sentiment — clearest single error in the set |
| "Low key excited to wear mine when they come in the mail" | NEUTRAL (0.466) | Contains the explicit word "excited" |

### Why this matters
Confirms the comment-sentiment error pattern from §2 is not specific to the Apple video's comment
section — the same struggle with slang ("dope," "GOAT"), anticipation phrasing, and explicit
self-reported sentiment words recurs here at a similar error rate.

### Status
Documented — corroborates §2. No new fix proposed; same future-work status as §2.

---

## 12D. Facial Emotion Channel — False-Positive Face Detection on Non-Face Content (NEW failure mode, quantified across all 827 frames)

### What we found
Every one of the 827 extracted frames (1 fps) was re-run through `analyse_facial_emotion()` to get
per-frame (not segment-pooled) output, then visually inspected via 34 generated contact sheets
(25 labeled frames each). Result:

- **452/827 (54.7%)** correctly returned no face (product b-roll, feet shots, shoe close-ups).
- Of the **375/827 frames where a face was "detected"**, **34 (9.1% of detected, 4.1% of all frames)
  are confirmed false positives** — DeepFace reported a confident emotion on frames containing **zero
  humans**: a printed foot-hotspot diagram, a "NIKE MIND" text box, tissue paper, dotted shoe-sole
  textures, plain product shots on a coloured background, and feet/floor b-roll.
- **Fear is the dominant spurious label** on these false positives — 16 of the 34 (47%), often at
  0.90–1.00 confidence on a completely faceless frame.
- **Zero false negatives** were found — no case where a clearly visible, prominent face was wrongly
  reported as no-face. The detector only errs in the hallucinating direction here.

### Methodology
`pipeline.visual_module.analyse_facial_emotion()` was re-run directly against
`data/JpN1DQdV4G4/frames/` (827 frames) to obtain raw per-frame `dominant_emotion`/`confidence`
output — this is not persisted in the saved report (only the segment-pooled result is), so it had to
be regenerated. The 827 results were rendered into 34 contact-sheet images (5×5 grid, each thumbnail
labeled with timestamp + model output) and every single sheet was visually reviewed frame-by-frame
against the model's claim, with no frame skipped.

### Evidence — representative false positives

| Timestamp | Claimed label (confidence) | What's actually in frame |
|---|---|---|
| 5s | fear (1.00) | Printed foot-hotspot diagram held up to camera, no person |
| 79s, 122s | fear (0.99 / 0.91) | Close-up shoe/feet b-roll, no face |
| 197–201s | happy → neutral → neutral → fear → fear (5 consecutive frames) | Same static multi-colourway product shot, no person, yet 5 different random emotion labels across 5 frames of the *same image* |
| 214s | fear (0.90) | Same foot-hotspot diagram as 5s, again |
| 223s, 224s | fear (1.00 / 1.00) | Plain "NIKE MIND" branding text on a box, no face |
| 233–237s | neutral/neutral/sad/neutral/neutral | Box-opening shot, tissue paper texture, no person |
| 511s, 513s, 516s | fear / happy / happy | Feet-walking b-roll, no face visible |

### Root cause analysis
`detector_backend="opencv"` in `analyse_facial_emotion()` (chosen for speed at 1 fps, per the module
docstring) uses a lightweight Haar-cascade-style detector that is known to be the least accurate of
DeepFace's available backends. `enforce_detection=False` means it never raises on a non-face frame —
it just returns whatever its weakest guess was, gated only by `FACE_CONFIDENCE_THRESHOLD = 0.50`. On
textured, dotted, or high-contrast product photography (this video's product shots are full of
circular dot patterns on the shoe sole, plus printed diagrams and boxed text), that threshold is
evidently still permissive enough to pass spurious "face" geometry roughly 1 in 11 times a face is
"detected." Once a false detection passes the gate, the downstream FER (emotion) head still runs and
returns a confident-sounding label on pure noise — and disproportionately returns "fear," which is
consistent with §9's facial-bias finding on the Apple video, just manifesting here as a detection-stage
problem rather than a classification-stage one.

### Evidence — corroborating the existing "sad" bias on real faces (§9)
Excluding the 34 false positives, 341 frames have a genuine face. Distribution: **neutral 130
(38.1%), sad 127 (37.2%)**, happy 57 (16.7%), fear 17 (5.0%), surprise 9 (2.6%), angry 1 (0.3%). "Sad"
is essentially tied with "neutral" as the most common real-face label, despite the reviewer's
expression being — per direct visual review and independently confirmed by the project author
watching the actual video — "neutral and very expressive, maybe slightly positive... never sad or
angry." This is the same DeepFace negative/low-affect bias documented in §9 on the Apple video,
now independently reproduced and precisely quantified (37.2% sad on real faces) on a second video.

### Why this matters
This is a **new, distinct failure mode** from §9's false-positive finding (which was about specific
product close-ups resembling face geometry on *one* video). Here the false positives are more varied
(diagrams, text, dotted textures, b-roll) and occur at a similar rate (9.1% of detections) on an
entirely different video — suggesting the `opencv` backend's false-positive rate on this kind of
review-style product content (lots of close-up textured product shots) is a general property of the
detector choice, not a one-off artifact of either specific video. Combined with the corroborated
37.2% "sad" rate on real faces, a meaningful fraction of every facial-emotion-derived signal this
pipeline produces is either fabricated from non-face content or systematically skewed negative on
genuinely neutral faces.

### Status
Documented as a refinement/extension of §9 — same root cause category (face-detection threshold +
backend choice), now quantified at the frame level on a second video, with the previously-unremarked
"fear is the dominant spurious label" pattern newly identified. No fix implemented in the prototype;
same proposed fixes as §9 apply (raise `FACE_CONFIDENCE_THRESHOLD`, switch `detector_backend` away
from `"opencv"`, confidence-weighted pooling).

---

## 12E. Vocal Tone Channel — Second Video Corroboration, with Pitch Cross-Check (User-Verified)

### What we found
Across the 29 segments, SpeechBrain's IEMOCAP model labeled **21/29 (72.4%) "happy," 4/29 (13.8%)
"angry," 3/29 (10.3%) "neutral," and 1/29 (3.4%) "sad."** The project author listened to the actual
video directly and reports: the speaker is an outspoken, confident extrovert throughout, tone is
"slightly positive but more neutral," and **never angry or sad** at any point. The 72.4% "happy"
majority roughly tracks the verified positive-but-mild lean; the 4 "angry" calls do not match anything
heard in the audio.

### Verification method — pitch cross-check on the 4 "angry" segments
To test the specific hypothesis raised during verification — "is the angry label just a side-effect of
his voice/pitch being high?" — the `pitch_mean_hz` value behind each of the 4 angry-labeled segments
was compared against the pitch range of the 21 segments labeled "happy" (146.4–197.1 Hz, mean 169.1 Hz):

| Segment | Vocal label | Pitch (Hz) | Inside "happy" pitch range? |
|---|---|---|---|
| 0 | angry | **252.7** | No — highest pitch in the entire video, a clear outlier |
| 2 | angry | 168.4 | Yes — unremarkable, sits inside the happy range |
| 11 | angry | 151.9 | Yes — unremarkable |
| 17 | angry | 163.9 | Yes — unremarkable |

### Root cause
Pitch height does **not** generally explain the "angry" mislabels — 3 of the 4 angry segments have
pitch values indistinguishable from segments the same model called "happy" on the same speaker, in
the same video. Only segment 0 (252.7 Hz, the energetic cold-open line "Nike made this shoe to
control your mind!") has a plausible pitch-based explanation — it's genuinely the most vocally
emphatic moment in the video, well above every other segment. The other 3 angry calls are simply
IEMOCAP's general bias toward over-predicting negative/high-arousal emotion on natural conversational
speech — the same root cause already documented in §10 (IEMOCAP is trained on scripted, exaggerated
acted emotion, not calm narration) — now confirmed independent of pitch on a second video.

### Why this matters
Rules out a simpler, more fixable hypothesis (a pitch-threshold miscalibration that could be tuned
away) in favour of the harder, already-documented explanation (§10): this is a genuine model-bias
limitation of IEMOCAP itself, not a parameter that can be cheaply corrected. Reinforces that the
vocal-tone channel's bias is a property of the pretrained model's training distribution, recurring
consistently across two independently reviewed videos.

### Status
Documented — corroborates §10, with a new, concrete pitch-based root-cause test added (previously
only the bias direction was confirmed; this video additionally tests and rules out the pitch-driven
explanation for 3 of 4 mislabels). No new fix proposed; same future-work status as §10.

---

## 13. Facial Emotion — Closed by Measurement (`facial_bench/v2/`, 04 Sep 2026)

This section closes §9 and §12D. Both were logged as "future work"; the work has
now been done, and the conclusion is stronger than either of them could support.

### What was done

§9's review was a single reviewer reading a single video's segments, and §12D
extended it to a second video. Neither had a control, a held-out speaker, or a
measure of how consistent the reviewer was with themselves. `facial_bench/v2/`
replaced that with a pre-registered protocol (`facial_bench/v2/PROTOCOL.md`,
written before any frame was sampled): 15 videos, 8 speakers, 600 frames sampled
by seed **before any model ran**, labelled blind in a purpose-built tool, split by
speaker, holdout opened exactly once.

### What was found

- **The reliability ceiling is 87.5%** (κ = 0.804, 48 hidden duplicate frames).
  This is the number §9 and §12D lacked. It means the task is *not* ill-posed —
  a human labelling the same still twice agrees 87.5% of the time — so a model's
  failure is the model's.
- **Nine emotion models, nothing adopted.** On held-out speakers **every** model
  scored below an always-NEUTRAL constant (67.5%), the best by 30.7 points. The
  deployed `deepface_fer` scored 34.2%.
- **§9's headline error rate is corroborated in direction but was measured on a
  confounded sample.** v1's 44 expression labels were 43 of §9's own 46 mismatches
  plus 1 of its 11 matches — selected on the incumbent's errors. v2's sample was
  drawn before any model ran and reaches the same conclusion without that defect.
- **§12D's false-positive finding does not survive at the frame level for the
  deployed detector.** §12D measured 9.1% spurious face detection using DeepFace's
  `opencv` default. With `yunet` (adopted 03 Sep 2026) the per-frame
  false-positive rate is **0 of 251** rater-verified faceless frames across both
  splits; `opencv` on the same frames produces 65. The detector swap fixed the
  failure §12D described.
- **The characteristic error is manufactured negativity.** Eight of nine models
  call verified-neutral frames NEGATIVE at 21.0%–87.4% (dev) and 33.8%–90.9%
  (holdout). This is the mechanism behind §11: manufactured negativity becomes
  cross-channel disagreement, then a conflict flag, then a depressed Authenticity
  Score for a video that did nothing wrong.
- **There is very little negative facial affect in this genre to detect.** A
  corpus deliberately containing 6 negatively-framed reviews yielded **4 anger
  frames in 320 readable ones**. The pre-registered floor for answering the anger
  question was 20, so no claim is made about it — but the shortfall is itself the
  finding.

### What changed in the code

The facial channel is now **down-weighted in the orchestrator** by its measured
held-out accuracy, `FACIAL_ONLY_CONFLICT_WEIGHT = 0.342`, exactly as the vocal
channel is at 0.489. `BIAS_CAVEAT` stays on every report regardless.

Full write-up and all 463 verified claims:
`facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md`.

---

## Summary Table

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Transcript sentiment miscalibration (SST-2) | High | Documented — future work |
| 1B | Transcript sentiment — full 77-segment review: **~48% error rate** | **Critical** (most load-bearing channel) | Documented — future work |
| 2 | Comment sentiment ~28% error rate, systematic bias | High | Documented — future work |
| 3 | Comment aggregate label/confidence misleading | Medium | Documented — future work |
| 4 | Orchestrator scoring inconsistency on similar cases | Medium | Documented — future work |
| 5 | Run-to-run reproducibility — Ollama-level fix confirmed working via isolated test; remaining variance traced to §3's comment tie-break cascading into every segment's prompt | High | Ollama fix **confirmed** — root cause of remaining variance is §3, documented as future work |
| 6 | Low-expressiveness false positives | High | Documented — future work (baseline calibration proposed) |
| 7 | Pitch/energy undefined contribution | Low | Documented — future work |
| 8 | YOLOv8 logo detection placeholder | Low (pre-existing, known) | Documented in code already |
| 9 | Facial emotion — full 77-segment visual review: **~79% error rate** (worst of the three channels checked) | **Critical** | **Closed by §13** — benched 04 Sep 2026, nothing adopted, channel down-weighted |
| 10 | Vocal tone — SpeechBrain IEMOCAP 74% "angry" vs. user-verified mostly-neutral speech | High | Documented — future work |
| 11 | Combined effect of §1B+§2+§9+§10 recomputed through real orchestrator: Authenticity 26.55→80.57, Brand Health 10.62→51.91, flagged 33→0 (illustrative, not a forecast) | **Critical** | Documented — diagnostic only |
| 12A | Whisper segment granularity — long monologue sections produce oversized segments (up to 211.5s, one label each) | Medium (structural) | Documented — not a bug, no fix proposed |
| 12B | Transcript sentiment — 2nd video corroboration: **38% error rate** (29 segments) | High | Documented — corroborates §1B |
| 12C | Comment sentiment — 2nd video corroboration: **~25% error rate** (100 comments) | High | Documented — corroborates §2 |
| 12D | Facial emotion — 2nd video, all 827 frames: **9.1% false-positive face detection** on non-face content (new failure mode, "fear" dominant spurious label) + **37.2% "sad" on real faces** (corroborates §9) | **Critical** | **Superseded by §13** — the 9.1% false-positive rate was `opencv`; the deployed `yunet` measures 0 of 251 |
| 12E | Vocal tone — 2nd video corroboration + pitch cross-check: 3 of 4 "angry" mislabels have unremarkable pitch (rules out pitch as the cause); only 1 plausibly pitch-related | High | Documented — corroborates §10 |

---

| 13 | Facial emotion — pre-registered bench on 8 speakers: human ceiling **87.5%**, nine models all below an always-NEUTRAL constant on held-out speakers (best −30.7 pts), nothing adopted, channel down-weighted to **0.342** | **Critical** | **Closed** — `facial_bench/v2/`, 463 claims verified |

---

*Last updated: this file will be appended to as further verification (face/voice vs real video,
non-flagged segment spot-checks, post-fix reproducibility comparison) is completed.*
