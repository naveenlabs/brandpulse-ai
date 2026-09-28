"""
test_facial_bench.py — unit tests for the facial-emotion bench.

Scope: the arithmetic and the label logic are tested for real;
model calls and image I/O are mocked. Nothing here loads a network or a checkpoint,
so the suite stays runnable offline.

What is deliberately covered:
  - the ground-truth transcription and its anchor against the saved run, including
    the partition arithmetic that lets §9's tally produce face-presence labels for
    segments it never tabulates individually;
  - the three-class mapping, both readings of the declared `surprise` judgement
    call, and the refusal to coerce an unmapped label;
  - both pooling functions, against the window rule `visual_module` actually uses;
  - abstention scoring, which must count as wrong rather than be dropped;
  - the failure paths: a candidate that raises, a segment with no frames, a
    degenerate group, an empty sample.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "research" / "facial_bench"

# Three bench directories ship modules with the same bare names — `candidates`,
# `ground_truth` and `report_bench` exist in facial_bench/, vocal_bench/ and
# transcript_bench/ alike. Each bench's own tests put its directory on sys.path
# and import the bare name, so whichever test file runs first wins `sys.modules`
# and every later bench silently gets the wrong module.
#
# This loader borrows those names only for the duration of the import and puts
# back whatever was there before, so importing the facial bench cannot change what
# `tests/test_vocal_bench.py` or `tests/test_transcript_metrics.py` see, in either
# collection order. The module objects captured below keep working afterwards —
# only the sys.modules entries are withdrawn, and the modules already hold direct
# references to each other.
#
# The underlying name collision is a pre-existing fragility across the benches. It
# is left alone rather than fixed by renaming four other test files, but it is
# recorded here so the next person meets it as a comment and not as 46 failures.
_SHARED_NAMES = ("candidates", "ground_truth", "report_bench", "run_detect", "run_classify")


def _load_facial_bench():
    saved = {n: sys.modules.pop(n, None) for n in _SHARED_NAMES}
    added_root = str(ROOT) not in sys.path
    sys.path.insert(0, str(BENCH))
    if added_root:
        sys.path.insert(0, str(ROOT))
    try:
        import candidates
        import ground_truth
        import report_bench
        import run_classify
        import run_detect
        return candidates, ground_truth, report_bench, run_classify, run_detect
    finally:
        for n in _SHARED_NAMES:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]
        sys.path.remove(str(BENCH))


C, GT, RB, RC, RD = _load_facial_bench()

# The v1 ground truth is anchored to one historical saved run, the one
# PROTOTYPE_FINDINGS.md §9 reviewed. That report is research data that is not
# part of this repository (it was removed from outputs/ on 24 Sep 2026), so the
# tests that read it skip, saying why, rather than fail. Everything else here
# (mapping, pooling, scoring, failure paths) runs on every checkout.
needs_anchor = unittest.skipUnless(
    GT.ANCHOR_REPORT.is_file(),
    f"facial_bench v1 research data absent: {GT.ANCHOR_REPORT.name} (the run "
    "PROTOTYPE_FINDINGS.md §9 reviewed) is not in this checkout; see "
    "facial_bench/FACIAL_MODEL_ANALYSIS.md")


# ── Ground truth ──────────────────────────────────────────────────────────────

class TestGroundTruthAnchor(unittest.TestCase):
    """The anchor is what licenses every number in the bench."""

    @needs_anchor
    def test_anchor_passes_against_the_saved_run(self):
        chk = GT.anchor_check()
        self.assertTrue(chk["ok"], f"anchor failed: {chk['problems']}")

    @needs_anchor
    def test_anchor_covers_every_segment_section_9_reviewed(self):
        chk = GT.anchor_check()
        self.assertEqual(chk["segments_in_run"], 77)
        self.assertEqual(chk["rows_total"], 77)

    @needs_anchor
    def test_faceless_count_matches_section_9_tally(self):
        # §9 reports 15 false positives and 5 correct-no-face. Both are frames
        # with no human being in them, so the faceless ground truth is 20.
        chk = GT.anchor_check()
        self.assertEqual(chk["faceless_segments"], 20)
        self.assertEqual(
            chk["faceless_segments"],
            GT.SECTION9_TALLY["false_positive"] + GT.SECTION9_TALLY["correct_no_face"])

    def test_section_9_categories_partition_the_video(self):
        t = GT.SECTION9_TALLY
        self.assertEqual(
            t["correct_no_face"] + t["false_positive"] + t["match"] + t["mismatch"],
            t["total"])

    def test_load_refuses_when_the_anchor_fails(self):
        real = GT.anchor_check
        GT.anchor_check = lambda: {"ok": False, "problems": ["injected"]}
        try:
            with self.assertRaises(ValueError):
                GT.load()
        finally:
            GT.anchor_check = real

    @needs_anchor
    def test_load_can_be_forced_past_a_failing_anchor(self):
        real = GT.anchor_check
        GT.anchor_check = lambda: {"ok": False, "problems": ["injected"]}
        try:
            self.assertEqual(len(GT.load(require_anchor=False)), 77)
        finally:
            GT.anchor_check = real

    def test_missing_anchor_report_raises_rather_than_guessing(self):
        real = GT.ANCHOR_REPORT
        GT.ANCHOR_REPORT = Path("/nonexistent/report.json")
        try:
            with self.assertRaises(FileNotFoundError):
                GT.load_anchor_segments()
        finally:
            GT.ANCHOR_REPORT = real


@needs_anchor
class TestGroundTruthContent(unittest.TestCase):

    def test_no_segment_is_labelled_twice(self):
        ids = [r["segment_id"] for r in GT.load()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_expression_set_excludes_face_only_segments(self):
        expr = {r["segment_id"] for r in GT.expression_set()}
        untab = set(GT.segments_without_expression())
        self.assertEqual(expr & untab, set())
        self.assertEqual(len(expr) + len(untab) + 20, 77)

    def test_expression_set_contains_no_negative_class(self):
        # Pre-registered limitation, CANDIDATE_MODELS.md §3.1. If this ever fails
        # the write-up's bound on §5 is wrong and must be revisited.
        classes = {r["expression"] for r in GT.expression_set()}
        self.assertNotIn("NEGATIVE", classes)
        self.assertEqual(classes, {"NEUTRAL", "POSITIVE"})

    def test_strict_tier_is_a_subset_of_the_full_set(self):
        strict = {r["segment_id"] for r in GT.expression_set(strict_only=True)}
        full = {r["segment_id"] for r in GT.expression_set()}
        self.assertTrue(strict.issubset(full))
        self.assertLess(len(strict), len(full))

    def test_every_row_carries_its_provenance(self):
        for r in GT.load():
            self.assertIn(r["tier"], {"explicit", "grouped", "inferred", "derived"})
            self.assertTrue(r["quote"], f"segment {r['segment_id']} has no source quote")

    def test_segment_39_is_in_the_angry_group_not_the_fear_group(self):
        # Amendment A1. §9's own stated ranges settle it: the angry row says
        # 0.46-0.95 and only segment 39 supplies the 0.46.
        row = next(r for r in GT.load() if r["segment_id"] == 39)
        self.assertEqual(row["claimed_label"], "angry")
        self.assertEqual(row["group"], "face_group_angry")

    def test_faceless_rows_carry_no_expression(self):
        for r in GT.load():
            if not r["face_present"]:
                self.assertIsNone(r["expression"])

    def test_summary_counts_agree_with_the_rows(self):
        s = GT.summary()
        self.assertEqual(s["face_presence_labels"], len(GT.load()))
        self.assertEqual(s["expression_labels"], len(GT.expression_set()))
        self.assertEqual(sum(s["by_tier"].values()), 77)


# ── Label mapping ─────────────────────────────────────────────────────────────

class TestThreeClassMapping(unittest.TestCase):

    def test_every_negative_label_maps_to_negative(self):
        for lab in ("angry", "anger", "sad", "sadness", "disgust",
                    "fear", "fearful", "contempt", "disgusted"):
            self.assertEqual(C.to_three(lab), C.NEGATIVE, lab)

    def test_neutral_maps_to_neutral(self):
        self.assertEqual(C.to_three("neutral"), C.NEUTRAL)

    def test_positive_labels_map_to_positive(self):
        for lab in ("happy", "happiness", "surprise", "surprised"):
            self.assertEqual(C.to_three(lab), C.POSITIVE, lab)

    def test_mapping_is_case_and_whitespace_insensitive(self):
        self.assertEqual(C.to_three("  Happy "), C.POSITIVE)
        self.assertEqual(C.to_three("ANGER"), C.NEGATIVE)

    def test_unknown_label_is_unmapped_not_coerced(self):
        for lab in ("ahegao", "confusion", "frustration", "disappointment", "LABEL_3"):
            self.assertIsNone(C.to_three(lab), lab)

    def test_empty_and_non_string_inputs_are_unmapped(self):
        for bad in (None, "", "   ", 3, [], {}):
            self.assertIsNone(C.to_three(bad))

    def test_surprise_sensitivity_mapping_differs_only_on_surprise(self):
        a, b = C.THREE_CLASS, C.THREE_CLASS_SURPRISE_NEUTRAL
        self.assertEqual(set(a), set(b))
        differing = {k for k in a if a[k] != b[k]}
        self.assertEqual(differing, {"surprise", "surprised"})
        self.assertEqual(b["surprise"], C.NEUTRAL)

    def test_no_candidate_emits_frustration_or_disappointment(self):
        # CANDIDATE_MODELS.md §5.1: a property of the whole model space, asserted
        # here so it cannot drift silently if a candidate is added.
        for lab in ("frustration", "frustrated", "disappointment", "disappointed"):
            self.assertNotIn(lab, C.THREE_CLASS)


class TestClassifierFailurePaths(unittest.TestCase):

    def _stub(self, fn):
        return C.Classifier(name="stub", source="", licence="", training_data="",
                            published="", n_classes=3, _loader=lambda: fn)

    def test_a_raising_model_returns_an_error_and_does_not_propagate(self):
        def boom(_):
            raise RuntimeError("checkpoint corrupt")
        res = self._stub(boom).predict(object())
        self.assertIsNone(res["top"])
        self.assertIsNone(res["three"])
        self.assertIn("checkpoint corrupt", res["error"])

    def test_an_empty_distribution_yields_no_prediction(self):
        res = self._stub(lambda _: ({}, {})).predict(object())
        self.assertIsNone(res["top"])
        self.assertIsNone(res["three"])
        self.assertNotIn("error", res)

    def test_argmax_and_mapping_on_a_normal_distribution(self):
        res = self._stub(lambda _: ({"sad": 0.6, "happy": 0.3, "neutral": 0.1}, {})).predict(object())
        self.assertEqual(res["top"], "sad")
        self.assertEqual(res["three"], C.NEGATIVE)

    def test_extras_are_passed_through_untouched(self):
        res = self._stub(lambda _: ({"neutral": 1.0}, {"valence": -0.4})).predict(object())
        self.assertEqual(res["extra"], {"valence": -0.4})

    def test_an_unmapped_top_label_is_reported_as_unmapped(self):
        res = self._stub(lambda _: ({"ahegao": 0.9, "neutral": 0.1}, {})).predict(object())
        self.assertEqual(res["top"], "ahegao")
        self.assertIsNone(res["three"])

    def test_the_loader_runs_only_once(self):
        calls = []

        def loader():
            calls.append(1)
            return lambda _: ({"neutral": 1.0}, {})
        cand = C.Classifier(name="s", source="", licence="", training_data="",
                            published="", n_classes=1, _loader=loader)
        cand.predict(object())
        cand.predict(object())
        self.assertEqual(len(calls), 1)


# ── Pooling ───────────────────────────────────────────────────────────────────

SEGMENTS = [
    {"segment_id": 0, "start_time": 0.0, "end_time": 5.0},
    {"segment_id": 1, "start_time": 5.0, "end_time": 10.0},
    {"segment_id": 2, "start_time": 10.0, "end_time": 12.0},
]


class TestDetectionPooling(unittest.TestCase):

    def _rows(self, spec):
        return [{"timestamp_s": float(t), "n_faces": n,
                 "confidences": [c] * n if n else []}
                for t, n, c in spec]

    def test_a_single_detection_makes_the_segment_face_present(self):
        rows = self._rows([(0, 0, 0), (1, 0, 0), (2, 1, 0.9), (3, 0, 0), (4, 0, 0)])
        pooled = RD.pool_to_segments(rows, SEGMENTS)
        self.assertTrue(pooled[0]["face_present"])
        self.assertEqual(pooled[0]["frames_with_face"], 1)

    def test_a_segment_with_no_frames_is_not_face_present(self):
        pooled = RD.pool_to_segments([], SEGMENTS)
        for sid in (0, 1, 2):
            self.assertFalse(pooled[sid]["face_present"])
            self.assertEqual(pooled[sid]["frames_in_window"], 0)

    def test_the_window_is_half_open_like_visual_module(self):
        # A frame exactly on a boundary belongs to the later segment.
        rows = self._rows([(5, 1, 0.9)])
        pooled = RD.pool_to_segments(rows, SEGMENTS)
        self.assertFalse(pooled[0]["face_present"])
        self.assertTrue(pooled[1]["face_present"])

    def test_max_confidence_is_the_highest_in_the_window(self):
        rows = [{"timestamp_s": 1.0, "n_faces": 1, "confidences": [0.6]},
                {"timestamp_s": 2.0, "n_faces": 2, "confidences": [0.4, 0.95]}]
        pooled = RD.pool_to_segments(rows, SEGMENTS)
        self.assertAlmostEqual(pooled[0]["max_confidence"], 0.95)

    def test_frames_outside_every_window_are_ignored(self):
        rows = self._rows([(99, 1, 0.9)])
        pooled = RD.pool_to_segments(rows, SEGMENTS)
        self.assertFalse(any(p["face_present"] for p in pooled.values()))


class TestClassificationPooling(unittest.TestCase):

    def _row(self, t, top, raw):
        return {"timestamp_s": float(t), "top": top, "raw": raw}

    def test_majority_vote_picks_the_most_common_label(self):
        rows = [self._row(0, "sad", {"sad": 0.9, "neutral": 0.1}),
                self._row(1, "sad", {"sad": 0.7, "neutral": 0.3}),
                self._row(2, "neutral", {"sad": 0.2, "neutral": 0.8})]
        pooled = RC.pool_to_segments(rows, SEGMENTS)
        self.assertEqual(pooled[0]["dominant"], "sad")
        self.assertEqual(pooled[0]["three"], C.NEGATIVE)
        self.assertEqual(pooled[0]["frame_count"], 3)

    def test_confidence_averages_only_the_agreeing_frames(self):
        rows = [self._row(0, "sad", {"sad": 0.9}), self._row(1, "sad", {"sad": 0.7}),
                self._row(2, "neutral", {"neutral": 0.99, "sad": 0.01})]
        pooled = RC.pool_to_segments(rows, SEGMENTS)
        self.assertAlmostEqual(pooled[0]["confidence"], 0.8, places=4)

    def test_mean_mass_is_averaged_over_every_frame_in_the_window(self):
        rows = [self._row(0, "sad", {"sad": 1.0, "angry": 0.0}),
                self._row(1, "sad", {"sad": 0.0, "angry": 1.0})]
        pooled = RC.pool_to_segments(rows, SEGMENTS)
        self.assertAlmostEqual(pooled[0]["mass"]["angry"], 0.5)
        self.assertAlmostEqual(pooled[0]["mass"]["sad"], 0.5)

    def test_a_segment_with_no_usable_frame_yields_none(self):
        pooled = RC.pool_to_segments([], SEGMENTS)
        self.assertIsNone(pooled[0]["dominant"])
        self.assertIsNone(pooled[0]["three"])
        self.assertEqual(pooled[0]["frame_count"], 0)

    def test_frames_the_model_failed_on_are_skipped_not_counted(self):
        rows = [{"timestamp_s": 0.0, "top": None, "raw": {}},
                self._row(1, "happy", {"happy": 0.9})]
        pooled = RC.pool_to_segments(rows, SEGMENTS)
        self.assertEqual(pooled[0]["dominant"], "happy")
        self.assertEqual(pooled[0]["frame_count"], 1)

    def test_the_alternative_surprise_mapping_is_honoured(self):
        rows = [self._row(0, "surprise", {"surprise": 0.9})]
        self.assertEqual(RC.pool_to_segments(rows, SEGMENTS)[0]["three"], C.POSITIVE)
        alt = RC.pool_to_segments(rows, SEGMENTS, C.THREE_CLASS_SURPRISE_NEUTRAL)
        self.assertEqual(alt[0]["three"], C.NEUTRAL)

    def test_an_unmapped_label_pools_to_a_dominant_with_no_three_class(self):
        rows = [self._row(0, "ahegao", {"ahegao": 0.9})]
        pooled = RC.pool_to_segments(rows, SEGMENTS)
        self.assertEqual(pooled[0]["dominant"], "ahegao")
        self.assertIsNone(pooled[0]["three"])


class TestSweepFailurePaths(unittest.TestCase):
    """One bad item degrades a sweep; it never aborts one."""

    def test_an_unreadable_crop_costs_one_row_not_the_sweep(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "crops" / "vid"
            d.mkdir(parents=True)
            (d / "frame_0000.jpg").write_bytes(b"not a jpeg")
            (d / "frame_0001.jpg").write_bytes(b"also not a jpeg")
            real_crops, real_preds = RC.CROPS, RC.PREDICTIONS
            RC.CROPS, RC.PREDICTIONS = Path(tmp) / "crops", Path(tmp) / "preds"
            C.CLASSIFIERS["__stub__"] = C.Classifier(
                name="__stub__", source="s", licence="l", training_data="t",
                published="p", n_classes=1, _loader=lambda: (lambda _: ({"neutral": 1.0}, {})))
            try:
                res = RC.run_one("vid", "__stub__")
                self.assertEqual(res["n_crops"], 2)
                self.assertEqual(res["failures"], 2)
                self.assertTrue(all(r["top"] is None for r in res["rows"]))
                self.assertTrue(all("crop unreadable" in r["error"] for r in res["rows"]))
            finally:
                RC.CROPS, RC.PREDICTIONS = real_crops, real_preds
                C.CLASSIFIERS.pop("__stub__", None)

    def test_a_missing_crop_directory_says_what_to_run(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            RC.run_one("no_such_video", C.INCUMBENT)
        self.assertIn("run_detect.py", str(ctx.exception))


class TestTimestampParsing(unittest.TestCase):

    def test_frame_number_is_seconds_at_one_fps(self):
        self.assertEqual(RD.timestamp_of(Path("frame_0042.jpg")), 42.0)
        self.assertEqual(RD.timestamp_of(Path("frame_0000.jpg")), 0.0)

    def test_an_unparseable_name_falls_back_to_zero(self):
        self.assertEqual(RD.timestamp_of(Path("thumbnail.jpg")), 0.0)

    def test_detect_and_classify_agree_on_the_rule(self):
        for name in ("frame_0000.jpg", "frame_0007.jpg", "frame_0571.jpg"):
            self.assertEqual(RD.timestamp_of(Path(name)), RC.timestamp_of(Path(name)))


# ── Scoring arithmetic ────────────────────────────────────────────────────────

class TestAbstainAwareScoring(unittest.TestCase):

    def test_a_perfect_prediction_scores_one(self):
        gold = ["NEUTRAL", "POSITIVE", "NEGATIVE"]
        self.assertEqual(RB.summarise_with_abstain(gold, list(gold))["accuracy"], 1.0)

    def test_an_abstention_counts_as_wrong(self):
        gold = ["NEUTRAL", "NEUTRAL"]
        res = RB.summarise_with_abstain(gold, ["NEUTRAL", RB.ABSTAIN])
        self.assertEqual(res["accuracy"], 0.5)
        self.assertEqual(res["abstentions"], 1)

    def test_abstaining_everywhere_cannot_beat_predicting(self):
        gold = ["NEUTRAL"] * 10
        allabs = RB.summarise_with_abstain(gold, [RB.ABSTAIN] * 10)
        allneu = RB.summarise_with_abstain(gold, ["NEUTRAL"] * 10)
        self.assertEqual(allabs["accuracy"], 0.0)
        self.assertEqual(allneu["accuracy"], 1.0)

    def test_abstention_is_a_prediction_column_never_a_gold_row(self):
        gold = ["NEUTRAL", "POSITIVE"]
        res = RB.summarise_with_abstain(gold, [RB.ABSTAIN, "POSITIVE"])
        # It is counted as a wrong prediction for the true class.
        self.assertEqual(res["confusion"]["NEUTRAL"][RB.ABSTAIN], 1)
        # And it is never itself a true class: the abstention row is all zeros
        # and its support is zero, so it cannot inflate any recall.
        self.assertEqual(sum(res["confusion"][RB.ABSTAIN].values()), 0)
        self.assertEqual(res["per_class"][RB.ABSTAIN]["support"], 0)

    def test_macro_f1_averages_the_three_real_classes_only(self):
        gold = ["NEUTRAL", "POSITIVE", "NEGATIVE"]
        res = RB.summarise_with_abstain(gold, list(gold))
        self.assertAlmostEqual(res["macro_f1"], 1.0)

    def test_wilson_interval_brackets_the_point_estimate(self):
        gold = ["NEUTRAL"] * 44
        pred = ["NEUTRAL"] * 38 + ["POSITIVE"] * 6
        res = RB.summarise_with_abstain(gold, pred)
        lo, hi = res["accuracy_ci95"]
        self.assertLessEqual(lo, res["accuracy"])
        self.assertGreaterEqual(hi, res["accuracy"])
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)

    def test_an_empty_sample_raises_rather_than_returning_zero(self):
        with self.assertRaises(ValueError):
            RB.summarise_with_abstain([], [])

    @needs_anchor
    def test_always_neutral_scores_the_floor_the_prereg_names(self):
        # CANDIDATE_MODELS.md §3.4 fixes this floor at 38/44 before any model ran.
        gold = [r["expression"] for r in GT.expression_set()]
        res = RB.summarise_with_abstain(gold, ["NEUTRAL"] * len(gold))
        self.assertEqual(res["n"], 44)
        self.assertAlmostEqual(res["accuracy"], 38 / 44, places=10)


@needs_anchor
class TestEndToEndComposite(unittest.TestCase):
    """
    The composite must reproduce §9's own metric, and must never turn an unknown
    segment into a right answer.
    """

    def test_the_deployed_arm_reproduces_section_9s_figure_inside_its_interval(self):
        res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        dep = res.get("deployed")
        if dep is None:
            self.skipTest("pipeline anchor has not been run")
        s9 = res["_section9"]["accuracy"]
        self.assertLessEqual(dep["accuracy_lower"], s9)
        self.assertGreaterEqual(dep["accuracy_upper"], s9)

    def test_every_segment_is_right_wrong_or_unknown_and_nothing_else(self):
        res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        for name, r in res.items():
            if name.startswith("_"):
                continue
            self.assertEqual(r["right"] + r["wrong"] + r["unknown"], 77, name)

    def test_the_unknowns_are_exactly_the_face_only_segments(self):
        res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        expected = len(GT.segments_without_expression())
        for name, r in res.items():
            if not name.startswith("_"):
                self.assertEqual(r["unknown"], expected, name)

    def test_the_lower_bound_never_exceeds_the_upper_bound(self):
        res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        for name, r in res.items():
            if not name.startswith("_"):
                self.assertLessEqual(r["accuracy_lower"], r["accuracy_upper"], name)

    def test_the_bounds_differ_by_exactly_the_unknown_share(self):
        res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        for name, r in res.items():
            if not name.startswith("_"):
                self.assertAlmostEqual(
                    r["accuracy_upper"] - r["accuracy_lower"], r["unknown"] / 77,
                    places=10, msg=name)

    def test_wrong_answers_are_attributed_to_one_of_three_causes(self):
        res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        for name, r in res.items():
            if not name.startswith("_"):
                self.assertEqual(
                    r["false_face"] + r["missed_face"] + r["wrong_label"],
                    r["wrong"], name)


@needs_anchor
class TestCompositeBaselines(unittest.TestCase):
    """The degenerate arms are scored as candidates, like every other model."""

    def setUp(self):
        self.res = RB.end_to_end(RD.GROUND_TRUTH_VIDEO)
        if "constant_neutral" not in self.res:
            self.skipTest("crop detector sweep has not been run")

    def test_all_three_constant_arms_are_present(self):
        for c in ("constant_neutral", "constant_positive", "constant_negative"):
            self.assertIn(c, self.res)
            self.assertTrue(self.res[c]["baseline"])

    def test_a_constant_arm_gets_every_faceless_segment_right_or_wrong_by_detection_alone(self):
        # A constant label cannot change which segments are called faceless, so
        # all three constants must share a false-face count.
        counts = {self.res[c]["false_face"]
                  for c in ("constant_neutral", "constant_positive", "constant_negative")}
        self.assertEqual(len(counts), 1)

    def test_always_negative_gets_every_expression_segment_wrong(self):
        # The ground truth has zero NEGATIVE expressions, so this is exact.
        self.assertEqual(self.res["constant_negative"]["wrong_label"], 44)

    def test_the_constant_arms_partition_the_expression_set(self):
        neu = self.res["constant_neutral"]["wrong_label"]
        pos = self.res["constant_positive"]["wrong_label"]
        self.assertEqual(neu, 44 - 38)
        self.assertEqual(pos, 44 - 6)

    def test_significance_is_reported_against_the_constant_floor(self):
        for name, r in self.res.items():
            if name.startswith("_") or name == "constant_neutral":
                continue
            self.assertIn("mcnemar_vs_constant", r, name)
            self.assertLessEqual(r["mcnemar_vs_constant"]["p_value"], 1.0)

    def test_the_significance_test_excludes_the_unknown_segments(self):
        n = len(self.res["constant_neutral"]["_outcomes"])
        self.assertEqual(n, 77 - len(GT.segments_without_expression()))
        self.assertEqual(n, 64)


class TestBenchConstants(unittest.TestCase):

    def test_the_crop_detector_is_a_real_candidate(self):
        self.assertIn(C.CROP_DETECTOR, C.DETECTORS)

    def test_exactly_one_detector_is_the_incumbent(self):
        inc = [k for k, v in C.DETECTORS.items() if v.get("incumbent")]
        self.assertEqual(inc, ["opencv"])

    def test_exactly_one_classifier_is_the_incumbent(self):
        inc = [k for k, v in C.CLASSIFIERS.items() if v.incumbent]
        self.assertEqual(inc, [C.INCUMBENT])

    def test_every_excluded_detector_has_a_stated_reason(self):
        for name, reason in C.EXCLUDED_DETECTORS.items():
            self.assertNotIn(name, C.DETECTORS)
            self.assertGreater(len(reason), 20, name)

    def test_every_classifier_declares_its_provenance(self):
        for name, cand in C.CLASSIFIERS.items():
            for field in ("source", "licence", "training_data", "published"):
                self.assertTrue(getattr(cand, field), f"{name}.{field} is empty")

    def test_the_sweep_aligns_because_the_pipeline_does(self):
        # Amendment A3. visual_module reaches the detector through
        # DeepFace.analyze, which aligns by default, and alignment feeds back
        # into detection. Running the bench unaligned benches a different model.
        self.assertTrue(RD.ALIGN)

    def test_the_ground_truth_video_is_in_the_bench_video_list(self):
        self.assertIn(RD.GROUND_TRUTH_VIDEO, RD.BENCH_VIDEOS)


class TestMidpointPooling(unittest.TestCase):
    """The midpoint mode exists to match the unit §9 actually observed."""

    def _rows(self, spec):
        return [{"timestamp_s": float(t), "n_faces": n,
                 "confidences": [0.9] * n if n else []} for t, n in spec]

    def test_only_the_midpoint_frame_is_consulted(self):
        # Segment 0 spans 0-5s, midpoint 2.5s -> frame 2 or 3. A face at 0s only
        # must not make the segment face-present under midpoint pooling.
        rows = self._rows([(0, 1), (1, 0), (2, 0), (3, 0), (4, 0)])
        self.assertTrue(RD.pool_to_segments(rows, SEGMENTS, "any")[0]["face_present"])
        self.assertFalse(RD.pool_to_segments(rows, SEGMENTS, "midpoint")[0]["face_present"])

    def test_the_nearest_frame_to_the_midpoint_is_chosen(self):
        rows = self._rows([(0, 0), (1, 0), (2, 1), (4, 0)])
        pooled = RD.pool_to_segments(rows, SEGMENTS, "midpoint")
        self.assertEqual(pooled[0]["frames_in_window"], 1)
        self.assertTrue(pooled[0]["face_present"])

    def test_midpoint_and_any_agree_when_the_window_has_one_frame(self):
        rows = self._rows([(10, 1), (11, 1)])
        a = RD.pool_to_segments(rows, SEGMENTS, "any")[2]
        m = RD.pool_to_segments(rows, SEGMENTS, "midpoint")[2]
        self.assertEqual(a["face_present"], m["face_present"])

    def test_an_empty_window_is_handled_in_both_modes(self):
        for mode in ("any", "midpoint"):
            pooled = RD.pool_to_segments([], SEGMENTS, mode)
            self.assertFalse(pooled[0]["face_present"])
            self.assertEqual(pooled[0]["frames_in_window"], 0)

    def test_an_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            RD.pool_to_segments([], SEGMENTS, "median")

    def test_midpoint_can_never_report_more_faces_than_any(self):
        rows = self._rows([(0, 1), (1, 0), (2, 0), (3, 1), (4, 0)])
        a = RD.pool_to_segments(rows, SEGMENTS, "any")
        m = RD.pool_to_segments(rows, SEGMENTS, "midpoint")
        for sid in a:
            self.assertLessEqual(m[sid]["frames_with_face"], a[sid]["frames_with_face"])


class TestAuc(unittest.TestCase):
    """Threshold-free separation, used for the dimensional arm."""

    def test_perfect_separation_scores_one(self):
        self.assertEqual(RB.auc([3.0, 4.0], [1.0, 2.0]), 1.0)

    def test_reversed_separation_scores_zero(self):
        self.assertEqual(RB.auc([1.0, 2.0], [3.0, 4.0]), 0.0)

    def test_identical_samples_score_one_half(self):
        self.assertEqual(RB.auc([1.0, 1.0], [1.0, 1.0]), 0.5)

    def test_ties_count_as_half(self):
        self.assertEqual(RB.auc([2.0], [1.0, 2.0, 3.0]), (1.0 + 0.5 + 0.0) / 3)

    def test_an_empty_side_returns_none_rather_than_a_number(self):
        self.assertIsNone(RB.auc([], [1.0]))
        self.assertIsNone(RB.auc([1.0], []))

    def test_auc_is_invariant_to_a_monotone_rescaling(self):
        pos, neg = [0.1, 0.4, 0.9], [0.0, 0.2, 0.3]
        import math
        rescaled_p = [math.log(x + 1) for x in pos]
        rescaled_n = [math.log(x + 1) for x in neg]
        self.assertEqual(RB.auc(pos, neg), RB.auc(rescaled_p, rescaled_n))


if __name__ == "__main__":
    unittest.main()
