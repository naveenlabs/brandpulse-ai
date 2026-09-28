# Defect: unbounded segment merging in `_merge_short_segments`

**Found:** 31 Aug 2026, while building the transcript-sentiment bench corpus.
**Fixed:** 31 Aug 2026, `pipeline/audio_module.py`.
**Severity:** affects all four channels, because every channel attaches to these segments.

---

## 1. What was wrong

`_merge_short_segments` merges segments shorter than `min_duration` (3.0 s) into the previous
segment, to stop very short Whisper outputs becoming noise. The test was applied to the
**arriving** segment only:

```python
duration = seg["end_time"] - seg["start_time"]
if duration < min_duration:
    merged[-1]["end_time"] = seg["end_time"]
    merged[-1]["text"] = (merged[-1]["text"] + " " + seg["text"]).strip()
```

The accumulator is never re-tested. An unbroken run of sub-threshold segments therefore
appends to the same segment without limit. There is no cap, and none was intended — the
docstring's promise ("merge segments shorter than min_duration") implies the result should
*reach* min_duration, not grow past it indefinitely.

A second, independent problem: neither version checked the **gap** between segments, so
merging could bridge a long silence and join material either side of an edit.

## 2. Evidence

Measured on the transcript-bench corpus: 12 videos, 151 minutes, 3,258 raw Whisper segments.

| | Before | After |
|---|---:|---:|
| Merged segments | 1,128 | 1,939 |
| Median duration | 5.6 s | 4.4 s |
| p99 duration | 39.9 s | 8.8 s |
| **Longest segment** | **121.2 s** | **22.1 s** |
| Segments over 20 s | 55 (4.9%) | 2 (0.1%) |
| Words inside those | 7,038 of 30,631 (**23.0%**) | 9 (0.0%) |
| Segments over 45 s | 11 | 0 |
| Segments/min, range across videos | 2.7 – 12.8 (4.7× spread) | 10.2 – 14.3 (1.4× spread) |

**The worst case.** In `0jHtyF_rCqU`, 65 consecutive raw Whisper segments — 64 of them under
3 s — collapsed into a single 121.2-second, 435-word block. It spans several unrelated
topics. No single sentiment, emotion or conflict label can describe it honestly.

**The silence case.** In `q0aFOxT6TNw` a 21-second speechless intro gap sat between two
segments. Merging bridged it, producing a segment whose wall-clock span was 38.4 s but which
contained 17.4 s of speech.

Worst affected videos, by raw-to-merged compression:

| Video | Raw | Merged (before) | Ratio | Longest |
|---|---:|---:|---:|---:|
| `32slGhAH3Xc` | 287 | 28 | 10.2× | 91.2 s |
| `0jHtyF_rCqU` | 346 | 56 | 6.2× | 121.2 s |
| `Rlw_CI7pOKg` | 333 | 60 | 5.5× | 63.6 s |

## 3. Why it matters beyond this bench

Segments are the spine of the system. Every channel attaches to the same segment dicts, so a
segmentation defect corrupts all of them simultaneously:

- **Transcript sentiment** is asked for one label over 435 words spanning several topics.
- **Facial emotion** pools frames across a 121-second window, flattening any real variation.
- **Vocal emotion** classifies a two-minute span as one emotion.
- **The orchestrator** then scores cross-channel "disagreement" between four labels that are
  each summarising too much material to be meaningful, and `CONFLICT_FLAG_THRESHOLD` fires on
  the result.

The distortion was concentrated rather than diffuse: **4.9% of segments carried 23% of all
words**. Those few segments dominated the content while being the least labelable.

This also supplies the mechanism behind an existing recorded observation. `PROTOTYPE_FINDINGS.md`
notes the Nike video producing 29 segments with one spanning 211 seconds, and attributed it to
the video being advertising with sparse speech. Sparse speech was the trigger, but the 211-second
block was produced by this defect, not by the content.

## 4. The fix

Two conditions now gate a merge:

```python
accumulated = merged[-1]["end_time"] - merged[-1]["start_time"]
gap = seg["start_time"] - merged[-1]["end_time"]
if accumulated < min_duration and gap <= max_gap:
```

- **Test the accumulator, not the arrival.** Merging stops as soon as the segment being built
  reaches `min_duration`. Worst case becomes `min_duration` plus one raw segment, which is
  bounded because Whisper caps its own segments around 30 s.
- **Never merge across a long silence.** `MAX_MERGE_GAP = 2.0 s`, set to the 95th percentile
  of the 203 inter-segment gaps measured in this corpus (median 0.48 s, max 21.0 s). Not a
  guessed constant.
- A trailing short segment is folded back into its predecessor, unless a large gap separates
  them — in which case it stays short, honestly, rather than being glued across a scene break.

After the fix, 4 segments of 1,939 (0.2%) remain under 3.0 s. All sit at silence boundaries,
which is the intended behaviour.

## 5. Testing

`_merge_short_segments` previously had **no unit tests at all**, despite being a pure function
with branching logic — the category the project's testing rule requires tests for. Twelve were added in
`tests/test_audio.py::TestMergeShortSegments`, covering the merge invariants, both silence
boundary cases, id renumbering, input immutability, and the empty and single-segment paths.

Three were checked against the old implementation to confirm they discriminate:

| Test | Old implementation |
|---|---|
| run of 20 × 1 s segments must not collapse | **fails** — produced 1 segment of 20 s |
| must not merge across a 21 s silence | **fails** — produced 1 segment |
| all but last reach min_duration | passes vacuously — old produced a single segment, so the slice is empty |

The third is an invariant guard, not a regression test. The first two do the discriminating
work.

**Suite: 170 → 182 passing.** No existing test changed behaviour.

## 6. Consequences and what is still open

- The bench corpus was rebuilt post-fix. Raw Whisper output is cached separately in `raw/`, so
  the rebuild re-merged without re-transcribing — no transcription drift, and the before/after
  comparison is on identical raw input.
- **All eight files in `outputs/` predate this fix** and carry the old segmentation. Their
  segment counts, conflict scores and Authenticity/Brand Health numbers are not comparable to
  anything produced after it. They should be regenerated before any of those figures is quoted
  in the report.
- The `~48%` transcript-sentiment and `~79%` facial-emotion error figures in
  `PROTOTYPE_FINDINGS.md` were measured on the old segmentation. How much of that error was
  segmentation rather than the models is **not yet known** and is exactly what the bench will
  now measure.
- `min_duration = 3.0 s` itself remains unjustified by measurement. It predates this work and
  was not chosen empirically. Whether 3.0 s is the right floor is a separate open question,
  not addressed here.
