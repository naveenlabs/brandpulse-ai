"""
test_facial_bench_v2.py — unit tests for the v2 facial ground-truth bench.

Scope: the sampling arithmetic, the split rule and the
blinding guarantee are tested for real. No checkpoint is loaded, no image is
read, no network is touched.

What is deliberately covered:
  - the corpus register: it is the only place video metadata is stated, so a
    typo here would silently corrupt the split;
  - the dev/holdout split rule from PROTOCOL.md §7, including the two floors,
    speaker disjointness, and the contamination constraint that forces the two
    v1 videos into dev;
  - determinism: the same seed must give the same split and the same draw, or
    the sample is not reproducible and §11 is a false claim;
  - the re-test construction from §4, which is what §5.3's reliability ceiling
    rests on;
  - blinding (§5.4): the generated tool must not contain a model name, a
    prediction, or a split label anywhere in its text;
  - the failure paths: frames missing, a manifest that would be overwritten,
    a video with fewer frames than the per-video draw.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "research" / "facial_bench"
V2 = V1 / "v2"

# Same collision hazard documented at the top of tests/test_facial_bench.py:
# bare module names are shared across benches. `corpus`, `sample`, `build_tool`
# and `run_v2` are added to the borrowed set here.
_SHARED_NAMES = ("candidates", "ground_truth", "report_bench", "run_detect",
                 "run_classify", "corpus", "sample", "build_tool", "run_v2",
                 "ground_truth_v2", "report_v2", "damping_ab", "corpus_ab")


def _load_v2():
    saved = {n: sys.modules.pop(n, None) for n in _SHARED_NAMES}
    sys.path.insert(0, str(V2))
    sys.path.insert(0, str(V1))
    try:
        import build_tool
        import corpus
        import ground_truth_v2
        import report_bench          # v1's, for the abstention-rule equivalence test
        import report_v2
        import run_v2
        import sample
        # LAST, deliberately. `damping_ab` reaches into `vocal_bench.corpus_ab`,
        # which puts *its* bench's `candidates` into sys.modules under the same
        # bare name facial_bench uses. Every module above has already bound the
        # facial one by reference, so importing this last means the swap cannot
        # reach them, and the finally block below unwinds it for everyone else.
        import damping_ab
        return (corpus, sample, build_tool, run_v2, ground_truth_v2,
                report_v2, report_bench, damping_ab)
    finally:
        for n in _SHARED_NAMES:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]
        # Every occurrence, not just the first: `report_v2` and v1's `report_bench`
        # both insert their own directory on import, so a single remove() would
        # leave a copy behind and let a later `import ground_truth` in another
        # bench's tests resolve to facial_bench's.
        for entry in (str(V1), str(V2)):
            while entry in sys.path:
                sys.path.remove(entry)


CORPUS, SAMPLE, BUILD, RUN, GT, RPT, RPT_V1, DAB = _load_v2()


# ── The corpus register ───────────────────────────────────────────────────────

class TestCorpus(unittest.TestCase):
    def test_fifteen_videos_eight_speakers(self):
        self.assertEqual(len(CORPUS.VIDEOS), 15)
        self.assertEqual(len(CORPUS.speakers()), 8)

    def test_video_ids_unique_and_well_formed(self):
        ids = [v.video_id for v in CORPUS.VIDEOS]
        self.assertEqual(len(ids), len(set(ids)))
        for vid in ids:
            self.assertEqual(len(vid), 11, vid)

    def test_by_id_matches_videos(self):
        self.assertEqual(len(CORPUS.BY_ID), len(CORPUS.VIDEOS))
        for v in CORPUS.VIDEOS:
            self.assertIs(CORPUS.BY_ID[v.video_id], v)

    def test_durations_and_heights_are_plausible(self):
        for v in CORPUS.VIDEOS:
            self.assertGreater(v.duration_s, 60, v.video_id)
            self.assertLess(v.duration_s, 3600, v.video_id)
            self.assertGreaterEqual(v.height, 1080, v.video_id)

    def test_url_is_a_youtube_watch_url(self):
        for v in CORPUS.VIDEOS:
            self.assertEqual(v.url, f"https://www.youtube.com/watch?v={v.video_id}")

    def test_exactly_two_videos_carry_the_v1_flag(self):
        """v1 analysed these two; PROTOCOL.md §7 forces their speakers into dev."""
        flagged = [v.video_id for v in CORPUS.VIDEOS if v.in_v1]
        self.assertEqual(sorted(flagged), ["1VjPETN3m6U", "JpN1DQdV4G4"])

    def test_forced_dev_matches_the_v1_flag(self):
        """The two lists must not be able to drift apart."""
        self.assertEqual(
            sorted(SAMPLE.FORCED_DEV),
            sorted(v.video_id for v in CORPUS.VIDEOS if v.in_v1),
        )

    def test_speakers_groups_every_video_once(self):
        grouped = CORPUS.speakers()
        total = sum(len(vs) for vs in grouped.values())
        self.assertEqual(total, len(CORPUS.VIDEOS))

    def test_repeat_speakers_are_present(self):
        """A split drawn on videos would be contaminated; this is why."""
        counts = {s: len(vs) for s, vs in CORPUS.speakers().items()}
        self.assertGreater(max(counts.values()), 1)

    def test_frame_count_is_zero_for_a_missing_directory(self):
        v = CORPUS.Video("aaaaaaaaaaa", "Nobody", "t", 100, 1080, "mixed", False)
        self.assertEqual(v.frame_count(), 0)

    def test_tone_hints_are_from_a_closed_set(self):
        allowed = {"positive", "mixed", "critical", "sceptical", "disappointed"}
        for v in CORPUS.VIDEOS:
            self.assertIn(v.tone_hint, allowed, v.video_id)

    def test_corpus_contains_critical_framing(self):
        """§2 defect 2: v1 had zero negative labels available. v2 must at least try."""
        critical = [v for v in CORPUS.VIDEOS
                    if v.tone_hint in {"critical", "disappointed", "sceptical"}]
        self.assertGreaterEqual(len(critical), 4)


# ── The dev / holdout split ───────────────────────────────────────────────────

class TestSplit(unittest.TestCase):
    def setUp(self):
        self.dev, self.holdout = SAMPLE.split_speakers()

    def test_speakers_are_disjoint(self):
        self.assertEqual(set(self.dev) & set(self.holdout), set())

    def test_every_speaker_is_placed(self):
        self.assertEqual(set(self.dev) | set(self.holdout),
                         set(CORPUS.speakers()))

    def test_contaminated_speakers_are_in_dev(self):
        for vid in SAMPLE.FORCED_DEV:
            self.assertIn(CORPUS.BY_ID[vid].speaker, self.dev)

    def test_holdout_meets_the_speaker_floor(self):
        self.assertGreaterEqual(len(self.holdout), SAMPLE.HOLDOUT_MIN_SPEAKERS)

    def test_holdout_meets_the_frame_floor(self):
        by = CORPUS.speakers()
        total = len(CORPUS.VIDEOS) * SAMPLE.PER_VIDEO
        held = sum(len(by[s]) for s in self.holdout) * SAMPLE.PER_VIDEO
        self.assertGreaterEqual(held / total, SAMPLE.HOLDOUT_MIN_FRACTION)

    def test_dev_keeps_the_majority(self):
        by = CORPUS.speakers()
        total = len(CORPUS.VIDEOS) * SAMPLE.PER_VIDEO
        held = sum(len(by[s]) for s in self.holdout) * SAMPLE.PER_VIDEO
        self.assertLess(held / total, 0.5)

    def test_split_is_deterministic(self):
        for _ in range(5):
            self.assertEqual(SAMPLE.split_speakers(), (self.dev, self.holdout))

    def test_split_does_not_depend_on_global_random_state(self):
        random.seed(1)
        a = SAMPLE.split_speakers()
        random.seed(999)
        b = SAMPLE.split_speakers()
        self.assertEqual(a, b)

    def test_no_video_appears_on_both_sides(self):
        dev_ids = {v.video_id for v in CORPUS.VIDEOS if v.speaker in self.dev}
        hold_ids = {v.video_id for v in CORPUS.VIDEOS if v.speaker in self.holdout}
        self.assertEqual(dev_ids & hold_ids, set())
        self.assertEqual(len(dev_ids) + len(hold_ids), len(CORPUS.VIDEOS))


# ── The draw ──────────────────────────────────────────────────────────────────

class _FakeFrames:
    """A corpus stand-in backed by a temporary directory of empty JPEGs."""

    def __init__(self, tmp: Path, per_video: int):
        self.tmp = tmp
        for v in CORPUS.VIDEOS:
            d = tmp / v.video_id / "frames"
            d.mkdir(parents=True)
            for i in range(per_video):
                (d / f"frame_{i:04d}.jpg").write_bytes(b"")


class TestDraw(unittest.TestCase):
    """`draw()` reads the disk, so these run against a synthetic frame tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        _FakeFrames(tmp, 120)
        self._orig = {}
        for v in CORPUS.VIDEOS:
            self._orig[v.video_id] = v.__class__
        self._patch(tmp)

    def _patch(self, tmp: Path):
        self._saved_data = CORPUS.DATA
        CORPUS.DATA = tmp

    def tearDown(self):
        CORPUS.DATA = self._saved_data
        self._tmp.cleanup()

    def test_draw_has_the_declared_size(self):
        m = SAMPLE.draw()
        self.assertEqual(m["n_frames"], 15 * SAMPLE.PER_VIDEO)
        self.assertEqual(m["seed"], SAMPLE.SEED)

    def test_every_video_contributes_equally(self):
        m = SAMPLE.draw()
        counts: dict[str, int] = {}
        for p in m["presentations"]:
            if not p["retest"]:
                counts[p["video_id"]] = counts.get(p["video_id"], 0) + 1
        self.assertEqual(set(counts.values()), {SAMPLE.PER_VIDEO})
        self.assertEqual(len(counts), 15)

    def test_draw_is_deterministic(self):
        a = [p["uid"] for p in SAMPLE.draw()["presentations"]]
        b = [p["uid"] for p in SAMPLE.draw()["presentations"]]
        self.assertEqual(a, b)

    def test_unique_frames_are_not_repeated_except_as_retests(self):
        m = SAMPLE.draw()
        firsts = [p["uid"] for p in m["presentations"] if not p["retest"]]
        self.assertEqual(len(firsts), len(set(firsts)))

    def test_retest_count_matches_the_declared_fraction(self):
        m = SAMPLE.draw()
        expected = round(m["n_frames"] * SAMPLE.RETEST_FRACTION)
        self.assertEqual(m["n_retest"], expected)
        actual = sum(1 for p in m["presentations"] if p["retest"])
        self.assertEqual(actual, expected)

    def test_retests_point_at_a_real_first_presentation(self):
        m = SAMPLE.draw()
        firsts = {p["uid"] for p in m["presentations"] if not p["retest"]}
        for p in m["presentations"]:
            if p["retest"]:
                self.assertIn(p["of"], firsts)
                self.assertEqual(p["uid"], p["of"] + "#r")

    def test_retests_come_after_their_original_with_a_gap(self):
        """§5.3 measures consistency, so the two showings must be separated."""
        m = SAMPLE.draw()
        pos = {p["uid"]: i for i, p in enumerate(m["presentations"])}
        for p in m["presentations"]:
            if p["retest"]:
                gap = pos[p["uid"]] - pos[p["of"]]
                self.assertGreaterEqual(gap, SAMPLE.RETEST_MIN_GAP)

    def test_presentation_uids_are_unique(self):
        m = SAMPLE.draw()
        uids = [p["uid"] for p in m["presentations"]]
        self.assertEqual(len(uids), len(set(uids)))

    def test_order_is_shuffled_across_videos(self):
        """A run of 40 consecutive frames from one video would defeat §4."""
        m = SAMPLE.draw()
        vids = [p["video_id"] for p in m["presentations"]]
        longest = best = 1
        for a, b in zip(vids, vids[1:]):
            longest = longest + 1 if a == b else 1
            best = max(best, longest)
        self.assertLess(best, 10)

    def test_split_labels_are_consistent_with_the_speaker_split(self):
        m = SAMPLE.draw()
        for p in m["presentations"]:
            speaker = CORPUS.BY_ID[p["video_id"]].speaker
            expected = "holdout" if speaker in m["holdout_speakers"] else "dev"
            self.assertEqual(p["split"], expected)

    def test_paths_are_relative_and_point_into_data(self):
        m = SAMPLE.draw()
        for p in m["presentations"]:
            self.assertTrue(p["path"].startswith("../../data/"), p["path"])
            self.assertTrue(p["path"].endswith(p["frame"]))

    def test_too_few_frames_is_a_hard_failure(self):
        """A short video must abort the draw, never silently under-sample."""
        tmp2 = tempfile.TemporaryDirectory()
        try:
            _FakeFrames(Path(tmp2.name), SAMPLE.PER_VIDEO - 1)
            saved = CORPUS.DATA
            CORPUS.DATA = Path(tmp2.name)
            try:
                with self.assertRaises(SystemExit):
                    SAMPLE.draw()
            finally:
                CORPUS.DATA = saved
        finally:
            tmp2.cleanup()

    def test_describe_reports_both_sides(self):
        text = SAMPLE.describe(SAMPLE.draw())
        self.assertIn("DEV", text)
        self.assertIn("HOLDOUT", text)


# ── The labelling tool ────────────────────────────────────────────────────────

class TestTool(unittest.TestCase):
    def test_choice_values_are_unique(self):
        vals = [v for v, _, _, _ in BUILD.CHOICES]
        self.assertEqual(len(vals), len(set(vals)))

    def test_choice_keys_are_unique_single_characters(self):
        keys = [k for _, k, _, _ in BUILD.CHOICES]
        self.assertEqual(len(keys), len(set(keys)))
        for k in keys:
            self.assertEqual(len(k), 1)

    def test_anger_and_sadness_are_separate_buttons(self):
        """PROTOCOL.md §5.1: collapsing them would destroy the Q2 evidence."""
        vals = {v for v, _, _, _ in BUILD.CHOICES}
        self.assertIn("angry", vals)
        self.assertIn("sad", vals)

    def test_both_abstentions_exist_and_are_distinct(self):
        vals = {v for v, _, _, _ in BUILD.CHOICES}
        self.assertIn("expr_unsure", vals)     # face present, expression unclear
        self.assertIn("face_unsure", vals)     # cannot tell whether a face is there
        self.assertIn("no_face", vals)

    def test_every_three_class_target_is_reachable(self):
        vals = {v for v, _, _, _ in BUILD.CHOICES}
        for needed in ("happy", "neutral", "angry", "sad", "surprised"):
            self.assertIn(needed, vals)


class TestToolBlinding(unittest.TestCase):
    """PROTOCOL.md §5.4 — the page must leak nothing about any model."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls._tmp = tmp
        path = Path(tmp.name)
        manifest = {
            "seed": 1, "per_video": 2, "n_frames": 2, "n_presentations": 2,
            "n_retest": 0, "dev_speakers": ["A"], "holdout_speakers": ["B"],
            "presentations": [
                {"uid": "v1:frame_0000", "video_id": "v1", "frame": "frame_0000.jpg",
                 "path": "../../data/v1/frames/frame_0000.jpg", "speaker": "A",
                 "split": "dev", "retest": False},
                {"uid": "v2:frame_0001", "video_id": "v2", "frame": "frame_0001.jpg",
                 "path": "../../data/v2/frames/frame_0001.jpg", "speaker": "B",
                 "split": "holdout", "retest": False},
            ],
        }
        saved_manifest, saved_out = BUILD.MANIFEST, BUILD.OUT
        BUILD.MANIFEST = path / "sample.json"
        BUILD.OUT = path / "label_here.html"
        BUILD.MANIFEST.write_text(json.dumps(manifest))
        try:
            cls.html = BUILD.build().read_text()
        finally:
            BUILD.MANIFEST, BUILD.OUT = saved_manifest, saved_out

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_no_model_name_appears(self):
        for name in ("deepface", "trpakov", "retinaface", "yunet", "mtcnn",
                     "dima806", "emotieff", "opencv", "yolo"):
            self.assertNotIn(name, self.html.lower(), name)

    def test_no_split_label_reaches_the_page(self):
        """Knowing which side a frame is on could bias the rater."""
        self.assertNotIn("holdout", self.html.lower())

    def test_no_speaker_name_reaches_the_page(self):
        self.assertNotIn('"speaker"', self.html)

    def test_images_are_referenced_not_embedded(self):
        self.assertIn("../../data/v1/frames/frame_0000.jpg", self.html)
        self.assertNotIn("data:image", self.html)

    def test_every_choice_is_rendered(self):
        for v, _, label, _ in BUILD.CHOICES:
            self.assertIn(f'data-v="{v}"', self.html)
            self.assertIn(label, self.html)

    def test_manifest_is_required(self):
        saved = BUILD.MANIFEST
        BUILD.MANIFEST = Path(self._tmp.name) / "nope.json"
        try:
            with self.assertRaises(SystemExit):
                BUILD.build()
        finally:
            BUILD.MANIFEST = saved


# ── The sweep runner ──────────────────────────────────────────────────────────

class TestRunner(unittest.TestCase):
    def test_align_matches_the_deployed_pipeline(self):
        """v1 Amendment A3: a bench that runs align=False measures nothing."""
        self.assertTrue(RUN.ALIGN)

    def test_crop_detector_is_v1s(self):
        self.assertEqual(RUN.C.CROP_DETECTOR, "retinaface")

    def test_candidate_set_is_unchanged_from_v1(self):
        """PROTOCOL.md §6 — changing ground truth and candidates at once confounds."""
        self.assertEqual(len(RUN.C.CLASSIFIERS), 9)
        self.assertEqual(len(RUN.C.DETECTORS), 6)

    def test_load_sample_drops_retests(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            path = Path(tmp.name) / "sample.json"
            path.write_text(json.dumps({"presentations": [
                {"uid": "a", "video_id": "v", "frame": "frame_0000.jpg",
                 "path": "p", "retest": False},
                {"uid": "a#r", "video_id": "v", "frame": "frame_0000.jpg",
                 "path": "p", "retest": True, "of": "a"},
                {"uid": "b", "video_id": "v", "frame": "frame_0001.jpg",
                 "path": "p", "retest": False},
            ]}))
            saved = RUN.MANIFEST
            RUN.MANIFEST = path
            try:
                got = RUN.load_sample()
            finally:
                RUN.MANIFEST = saved
            self.assertEqual([g["uid"] for g in got], ["a", "b"])
        finally:
            tmp.cleanup()

    def test_missing_manifest_is_a_hard_failure(self):
        saved = RUN.MANIFEST
        RUN.MANIFEST = Path("/nonexistent/sample.json")
        try:
            with self.assertRaises(SystemExit):
                RUN.load_sample()
        finally:
            RUN.MANIFEST = saved

    def test_crop_path_is_unique_per_video_and_frame(self):
        a = RUN.crop_path({"video_id": "vidA", "frame": "frame_0007.jpg"})
        b = RUN.crop_path({"video_id": "vidB", "frame": "frame_0007.jpg"})
        c = RUN.crop_path({"video_id": "vidA", "frame": "frame_0008.jpg"})
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.name.startswith("vidA_frame_0007"))

    def test_frame_path_points_into_the_data_tree(self):
        p = RUN.frame_path({"video_id": "vidA", "frame": "frame_0003.jpg"})
        self.assertEqual(p.parent.name, "frames")
        self.assertEqual(p.parent.parent.name, "vidA")


# ── Ground truth: loading, validation, reliability ────────────────────────────

def _manifest(pres):
    return {"seed": 1, "per_video": 1, "n_frames": len(pres),
            "n_presentations": len(pres), "n_retest": 0,
            "dev_speakers": ["A"], "holdout_speakers": ["B"],
            "presentations": pres}


def _p(uid, choice_video="v1", speaker="A", split="dev", retest=False, of=None):
    row = {"uid": uid, "video_id": choice_video, "frame": "frame_0000.jpg",
           "path": "p", "speaker": speaker, "split": split, "retest": retest}
    if of:
        row["of"] = of
    return row


class TestGroundTruthMapping(unittest.TestCase):
    def test_every_button_is_classified_exactly_once(self):
        groups = [GT.FACE_PRESENT, GT.FACE_ABSENT, GT.FACE_UNKNOWN]
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                self.assertEqual(groups[a] & groups[b], set())
        self.assertEqual(GT.ALL_CHOICES, set().union(*groups))

    def test_tool_buttons_and_loader_agree(self):
        """A button the loader cannot interpret would silently drop labels."""
        self.assertEqual({v for v, _, _, _ in BUILD.CHOICES}, GT.ALL_CHOICES)

    def test_expression_mapping_covers_every_readable_button(self):
        readable = GT.FACE_PRESENT - {"expr_unsure"}
        self.assertEqual(set(GT.EXPRESSION_THREE), readable)

    def test_anger_and_sadness_both_map_to_negative(self):
        self.assertEqual(GT.EXPRESSION_THREE["angry"], GT.NEGATIVE)
        self.assertEqual(GT.EXPRESSION_THREE["sad"], GT.NEGATIVE)

    def test_the_two_surprise_mappings_differ_only_in_surprise(self):
        a, b = GT.EXPRESSION_THREE, GT.EXPRESSION_THREE_SURPRISE_NEUTRAL
        self.assertEqual(a["surprised"], GT.POSITIVE)
        self.assertEqual(b["surprised"], GT.NEUTRAL)
        self.assertEqual({k: v for k, v in a.items() if k != "surprised"},
                         {k: v for k, v in b.items() if k != "surprised"})


class TestGroundTruthValidation(unittest.TestCase):
    def test_unknown_uid_is_rejected(self):
        m = _manifest([_p("a")])
        with self.assertRaises(GT.GroundTruthError):
            GT.validate({"a": "neutral", "ghost": "happy"}, m)

    def test_unknown_value_is_rejected(self):
        m = _manifest([_p("a")])
        with self.assertRaises(GT.GroundTruthError):
            GT.validate({"a": "ecstatic"}, m)

    def test_partial_labelling_is_reported_not_rejected(self):
        m = _manifest([_p("a"), _p("b")])
        rep = GT.validate({"a": "neutral"}, m)
        self.assertFalse(rep["complete"])
        self.assertEqual(rep["n_missing"], 1)
        self.assertEqual(rep["missing"], ["b"])

    def test_complete_labelling_is_flagged_complete(self):
        m = _manifest([_p("a")])
        self.assertTrue(GT.validate({"a": "no_face"}, m)["complete"])

    def test_missing_labels_file_is_a_clear_error(self):
        with self.assertRaises(GT.GroundTruthError):
            GT.load_raw(Path("/nonexistent/facial_labels_v2.json"))


class TestGroundTruthSets(unittest.TestCase):
    def setUp(self):
        self.m = _manifest([
            _p("a"), _p("b"), _p("c"), _p("d"), _p("e"),
            _p("f", speaker="B", split="holdout"),
        ])
        self.raw = {"a": "neutral", "b": "no_face", "c": "face_unsure",
                    "d": "expr_unsure", "e": "angry", "f": "happy"}

    def test_face_set_excludes_only_face_unsure(self):
        rows = GT.face_set(self.raw, self.m)
        self.assertEqual({r["uid"] for r in rows}, {"a", "b", "d", "e", "f"})

    def test_face_set_marks_presence_correctly(self):
        rows = {r["uid"]: r["has_face"] for r in GT.face_set(self.raw, self.m)}
        self.assertTrue(rows["a"])
        self.assertTrue(rows["d"])      # face there, expression unreadable
        self.assertFalse(rows["b"])

    def test_expression_set_excludes_unreadable_and_faceless(self):
        rows = GT.expression_set(self.raw, self.m)
        self.assertEqual({r["uid"] for r in rows}, {"a", "e", "f"})

    def test_expression_set_maps_to_three_classes(self):
        rows = {r["uid"]: r["three"] for r in GT.expression_set(self.raw, self.m)}
        self.assertEqual(rows["a"], GT.NEUTRAL)
        self.assertEqual(rows["e"], GT.NEGATIVE)
        self.assertEqual(rows["f"], GT.POSITIVE)

    def test_split_filter_selects_only_that_side(self):
        dev = GT.expression_set(self.raw, self.m, split="dev")
        hold = GT.expression_set(self.raw, self.m, split="holdout")
        self.assertEqual({r["uid"] for r in dev}, {"a", "e"})
        self.assertEqual({r["uid"] for r in hold}, {"f"})

    def test_alternative_surprise_mapping_changes_only_surprise(self):
        m = _manifest([_p("s")])
        raw = {"s": "surprised"}
        a = GT.expression_set(raw, m)[0]["three"]
        b = GT.expression_set(raw, m, mapping=GT.EXPRESSION_THREE_SURPRISE_NEUTRAL)[0]["three"]
        self.assertEqual(a, GT.POSITIVE)
        self.assertEqual(b, GT.NEUTRAL)

    def test_retest_presentations_never_enter_the_sets(self):
        m = _manifest([_p("a"), _p("a#r", retest=True, of="a")])
        rows = GT.expression_set({"a": "happy", "a#r": "sad"}, m)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["three"], GT.POSITIVE)

    def test_unlabelled_frames_are_simply_absent(self):
        rows = GT.face_set({"a": "neutral"}, self.m)
        self.assertEqual(len(rows), 1)


class TestCohensKappa(unittest.TestCase):
    """Real arithmetic, never mocked."""

    def test_perfect_agreement_across_two_classes_is_one(self):
        a = ["x", "y", "x", "y"]
        self.assertAlmostEqual(GT.cohens_kappa(a, list(a)), 1.0)

    def test_single_category_agreement_returns_zero_not_one(self):
        """pe == 1 makes kappa undefined; claiming 1.0 would overstate reliability."""
        a = ["x"] * 5
        self.assertEqual(GT.cohens_kappa(a, list(a)), 0.0)

    def test_known_value(self):
        # 2x2: both raters 'x' on 8, both 'y' on 8, disagree on 4.
        a = ["x"] * 10 + ["y"] * 10
        b = ["x"] * 8 + ["y"] * 2 + ["x"] * 2 + ["y"] * 8
        # po = 16/20 = 0.8 ; marginals are 10/10 both ways so pe = 0.5
        self.assertAlmostEqual(GT.cohens_kappa(a, b), 0.6)

    def test_chance_level_agreement_is_about_zero(self):
        a = ["x", "y"] * 10
        b = ["x", "x", "y", "y"] * 5
        self.assertAlmostEqual(GT.cohens_kappa(a, b), 0.0, places=6)

    def test_worse_than_chance_is_negative(self):
        a = ["x", "y"] * 6
        b = ["y", "x"] * 6
        self.assertLess(GT.cohens_kappa(a, b), 0.0)

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            GT.cohens_kappa(["x"], ["x", "y"])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            GT.cohens_kappa([], [])


class TestReliability(unittest.TestCase):
    def setUp(self):
        self.m = _manifest([
            _p("a"), _p("b"), _p("c"),
            _p("a#r", retest=True, of="a"),
            _p("b#r", retest=True, of="b"),
            _p("c#r", retest=True, of="c"),
        ])

    def test_pairs_require_both_showings(self):
        pairs = GT.retest_pairs({"a": "happy", "a#r": "happy", "b": "sad"}, self.m)
        self.assertEqual([p["uid"] for p in pairs], ["a"])

    def test_agreement_and_disagreement_are_counted(self):
        raw = {"a": "happy", "a#r": "happy",
               "b": "sad", "b#r": "angry",
               "c": "neutral", "c#r": "neutral"}
        rel = GT.reliability(raw, self.m)
        self.assertEqual(rel["n_pairs"], 3)
        self.assertAlmostEqual(rel["fine_agreement"], 2 / 3)

    def test_three_class_agreement_can_exceed_fine_agreement(self):
        """sad vs angry is a fine-grained miss but the same three-class label."""
        raw = {"a": "sad", "a#r": "angry",
               "b": "neutral", "b#r": "neutral",
               "c": "happy", "c#r": "happy"}
        rel = GT.reliability(raw, self.m)
        self.assertAlmostEqual(rel["fine_agreement"], 2 / 3)
        self.assertAlmostEqual(rel["three_agreement"], 1.0)

    def test_no_pairs_is_reported_not_raised(self):
        rel = GT.reliability({"a": "happy"}, self.m)
        self.assertEqual(rel["n_pairs"], 0)
        self.assertIn("note", rel)

    def test_disagreements_are_listed_for_inspection(self):
        raw = {"a": "happy", "a#r": "sad", "b": "neutral", "b#r": "neutral"}
        rel = GT.reliability(raw, self.m)
        self.assertEqual([d["uid"] for d in rel["disagreements"]], ["a"])

    def test_face_and_expression_choices_are_both_representable(self):
        """A no_face/expr_unsure pair must not crash the coarse mapping."""
        raw = {"a": "no_face", "a#r": "face_unsure",
               "b": "expr_unsure", "b#r": "neutral"}
        rel = GT.reliability(raw, self.m)
        self.assertEqual(rel["n_pairs"], 2)
        self.assertAlmostEqual(rel["three_agreement"], 0.0)


if __name__ == "__main__":
    unittest.main()


# ── The scorer (report_v2.py) ─────────────────────────────────────────────────
#
# The arithmetic itself lives in transcript_bench/metrics.py and is tested there.
# What is tested here is everything report_v2 adds on top of it: the abstention
# rule, the pre-registered adoption conditions, the Q2 power floor, and the
# holdout seal. Those are the parts that decide what the bench is allowed to
# claim, so a bug in them is a bug in the finding, not just in a number.

import ast                                                       # noqa: E402


def _pipeline_constant(name: str):
    """
    Read a constant out of pipeline/visual_module.py without importing it.

    Importing would pull DeepFace and TensorFlow into every test run for the sake
    of two literals. Parsing is exact — no regex — and fails loudly if the
    constant is renamed, which is the case this test exists to catch.
    """
    tree = ast.parse((ROOT / "pipeline" / "visual_module.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in pipeline/visual_module.py")


class TestScorerMirrorsThePipeline(unittest.TestCase):
    """report_v2 declares the deployed configuration locally; it must not drift."""

    def test_deployed_detector_matches_visual_module(self):
        self.assertEqual(RPT.DEPLOYED_DETECTOR,
                         _pipeline_constant("FACE_DETECTOR_BACKEND"))

    def test_pipeline_gate_matches_visual_module(self):
        self.assertEqual(RPT.PIPELINE_GATE,
                         _pipeline_constant("FACE_CONFIDENCE_THRESHOLD"))

    def test_deployed_classifier_is_a_real_candidate(self):
        # Nothing was adopted in v1, so DeepFace's FER head is still what runs.
        self.assertIn(RPT.DEPLOYED_CLASSIFIER, RPT.C.CLASSIFIERS)
        self.assertTrue(RPT.C.CLASSIFIERS[RPT.DEPLOYED_CLASSIFIER].incumbent)


class TestAbstentionRule(unittest.TestCase):
    """PROTOCOL.md §8: a model may not gain accuracy by declining to answer."""

    GOLD = ["POSITIVE", "NEUTRAL", "NEGATIVE", "NEUTRAL", "NEUTRAL"]
    PRED = ["POSITIVE", "NO_PREDICTION", "NEUTRAL", "NEUTRAL", "NO_PREDICTION"]

    def test_matches_v1_implementation_exactly(self):
        # v1 and v2 must score abstention the same way or their headline numbers
        # are not comparable, which is the whole point of holding the candidate
        # set fixed (PROTOCOL.md §6).
        a = RPT.summarise_with_abstain(self.GOLD, self.PRED)
        b = RPT_V1.summarise_with_abstain(self.GOLD, self.PRED)
        self.assertEqual(a, b)

    def test_abstention_is_wrong_not_dropped(self):
        res = RPT.summarise_with_abstain(self.GOLD, self.PRED)
        self.assertEqual(res["n"], 5)              # nothing dropped
        self.assertEqual(res["abstentions"], 2)
        self.assertAlmostEqual(res["accuracy"], 2 / 5)

    def test_total_abstention_scores_zero(self):
        res = RPT.summarise_with_abstain(self.GOLD, ["NO_PREDICTION"] * 5)
        self.assertEqual(res["accuracy"], 0.0)
        self.assertEqual(res["macro_f1"], 0.0)

    def test_macro_f1_averages_over_the_three_real_classes_only(self):
        # NO_PREDICTION appears in the confusion matrix but must never be
        # averaged into macro-F1, or abstaining consistently would look like a
        # fourth class the model is good at.
        res = RPT.summarise_with_abstain(self.GOLD, self.PRED)
        self.assertIn("NO_PREDICTION", res["per_class"])
        by_hand = sum(res["per_class"][c]["f1"] for c in ("POSITIVE", "NEUTRAL",
                                                          "NEGATIVE")) / 3
        self.assertAlmostEqual(res["macro_f1"], by_hand)

    def test_empty_sample_raises(self):
        with self.assertRaises(ValueError):
            RPT.summarise_with_abstain([], [])


class TestDeclaredMappings(unittest.TestCase):
    """PROTOCOL.md §5.2: the sensitivity check must move both sides together."""

    def test_only_the_two_declared_mappings_exist(self):
        self.assertEqual(set(RPT.MAPPINGS), {"primary", "surprise_neutral"})

    def test_primary_sends_surprise_positive_on_both_sides(self):
        gold_map, model_map = RPT.MAPPINGS["primary"]
        self.assertEqual(gold_map["surprised"], "POSITIVE")
        self.assertEqual(model_map["surprise"], "POSITIVE")

    def test_sensitivity_sends_surprise_neutral_on_both_sides(self):
        gold_map, model_map = RPT.MAPPINGS["surprise_neutral"]
        self.assertEqual(gold_map["surprised"], "NEUTRAL")
        self.assertEqual(model_map["surprise"], "NEUTRAL")
        self.assertEqual(model_map["surprised"], "NEUTRAL")

    def test_the_two_mappings_differ_only_in_surprise(self):
        a, _ = RPT.MAPPINGS["primary"]
        b, _ = RPT.MAPPINGS["surprise_neutral"]
        self.assertEqual({k: v for k, v in a.items() if k != "surprised"},
                         {k: v for k, v in b.items() if k != "surprised"})

    def test_unknown_mapping_is_refused(self):
        with self.assertRaises(RPT.ProtocolError):
            RPT.score_classifiers(mapping="whatever_gives_the_best_number")


class TestQ2PowerFloor(unittest.TestCase):
    """
    PROTOCOL.md §2 fixed the floor before collection so the call could not be
    made after seeing which answer it would give.
    """

    def test_floor_is_the_pre_registered_twenty(self):
        self.assertEqual(RPT.Q2_ANGER_FLOOR, 20)

    def test_below_the_floor_is_underpowered(self):
        s = RPT.q2_status(4)
        self.assertTrue(s["underpowered"])
        self.assertIn("UNDERPOWERED", s["verdict"])

    def test_at_the_floor_is_answerable(self):
        self.assertFalse(RPT.q2_status(20)["underpowered"])

    def test_one_below_the_floor_is_not(self):
        self.assertTrue(RPT.q2_status(19)["underpowered"])

    def test_floor_applies_to_the_collection_not_one_split(self):
        # A split holds part of the collection. Applying the floor per split would
        # make Q2 look differently powered depending on which half is scored,
        # which is not what PROTOCOL.md §2 pre-registered.
        s = RPT.q2_status(24, n_anger_split=3, split="dev")
        self.assertFalse(s["underpowered"])
        self.assertEqual(s["n_anger_in_split"], 3)
        self.assertEqual(s["split"], "dev")


def _model(accuracy, macro_f1, neg_rate, p, beats, baseline=False):
    return {"accuracy": accuracy, "macro_f1": macro_f1,
            "negative_on_neutral_rate": neg_rate, "beats_constant": beats,
            "mcnemar_vs_constant": {"p_value": p, "min_attainable_p": 0.002},
            **({"baseline": True} if baseline else {})}


def _bench(models, constant="always_NEUTRAL"):
    return {"constant_name": constant, "models": models, "n_anger": 4}


class TestAdoptionRule(unittest.TestCase):
    """PROTOCOL.md §9: all four conditions, or nothing is adopted."""

    def _dev(self, **over):
        base = dict(accuracy=0.80, macro_f1=0.55, neg_rate=0.05, p=0.001, beats=True)
        base.update(over)
        return _bench({
            "always_NEUTRAL": _model(0.60, 0.25, 0.0, 1.0, False, baseline=True),
            "cand": _model(**base),
        })

    def _hold(self, p=0.01, beats=True):
        return _bench({
            "always_NEUTRAL": _model(0.60, 0.25, 0.0, 1.0, False, baseline=True),
            "cand": _model(0.78, 0.54, 0.05, p, beats),
        })

    def test_all_four_conditions_adopts(self):
        ad = RPT.evaluate_adoption(self._dev(), self._hold())
        self.assertTrue(ad["verdicts"]["cand"]["adopt"])
        self.assertEqual(ad["adopted"], ["cand"])
        self.assertEqual(ad["decision"], "cand")

    def test_significantly_worse_is_not_adopted(self):
        # McNemar is two-sided: a model that loses to the constant at p<0.05
        # satisfies the test and fails the intent. The direction check is the
        # difference between "significantly different" and "better".
        ad = RPT.evaluate_adoption(self._dev(accuracy=0.40, beats=False), self._hold())
        self.assertFalse(ad["verdicts"]["cand"]["c1_beats_constant_dev"])
        self.assertFalse(ad["verdicts"]["cand"]["adopt"])

    def test_better_but_not_significant_is_not_adopted(self):
        ad = RPT.evaluate_adoption(self._dev(p=0.32), self._hold())
        self.assertFalse(ad["verdicts"]["cand"]["adopt"])

    def test_macro_f1_below_the_constant_is_not_adopted(self):
        ad = RPT.evaluate_adoption(self._dev(macro_f1=0.10), self._hold())
        self.assertFalse(ad["verdicts"]["cand"]["c2_macro_f1"])
        self.assertFalse(ad["verdicts"]["cand"]["adopt"])

    def test_inventing_negativity_is_not_adopted(self):
        # v1 §9.3: the deployed channel called 38 of 38 verified-neutral segments
        # negative. Condition 3 exists for exactly that failure.
        ad = RPT.evaluate_adoption(self._dev(neg_rate=0.16), self._hold())
        self.assertFalse(ad["verdicts"]["cand"]["c3_negative_on_neutral"])
        self.assertFalse(ad["verdicts"]["cand"]["adopt"])

    def test_condition_three_boundary_is_inclusive(self):
        ad = RPT.evaluate_adoption(self._dev(neg_rate=0.15), self._hold())
        self.assertTrue(ad["verdicts"]["cand"]["c3_negative_on_neutral"])

    def test_failing_on_holdout_is_not_adopted(self):
        ad = RPT.evaluate_adoption(self._dev(), self._hold(p=0.9))
        self.assertFalse(ad["verdicts"]["cand"]["c4_repeats_on_holdout"])
        self.assertFalse(ad["verdicts"]["cand"]["adopt"])

    def test_unscored_holdout_cannot_adopt(self):
        ad = RPT.evaluate_adoption(self._dev(), None)
        self.assertIsNone(ad["verdicts"]["cand"]["c4_repeats_on_holdout"])
        self.assertFalse(ad["verdicts"]["cand"]["adopt"])
        self.assertFalse(ad["holdout_scored"])
        self.assertEqual(ad["decision"], "NOTHING ADOPTED")

    def test_baselines_are_not_candidates_for_adoption(self):
        ad = RPT.evaluate_adoption(self._dev(), self._hold())
        self.assertNotIn("always_NEUTRAL", ad["verdicts"])

    def test_nothing_adopted_is_a_valid_outcome(self):
        ad = RPT.evaluate_adoption(self._dev(p=0.9), self._hold(p=0.9))
        self.assertEqual(ad["adopted"], [])
        self.assertEqual(ad["decision"], "NOTHING ADOPTED")


class TestHoldoutSeal(unittest.TestCase):
    """PROTOCOL.md §7, enforced in code rather than asserted in prose."""

    def setUp(self):
        self._orig = RPT.DEV_DECISION
        self._tmp = tempfile.TemporaryDirectory()
        RPT.DEV_DECISION = Path(self._tmp.name) / "DEV_DECISION.json"

    def tearDown(self):
        RPT.DEV_DECISION = self._orig
        self._tmp.cleanup()

    def test_holdout_is_sealed_until_the_dev_decision_is_written(self):
        with self.assertRaises(RPT.ProtocolError) as ctx:
            RPT.require_frozen_dev()
        self.assertIn("sealed", str(ctx.exception))

    def test_freeze_then_open(self):
        dev_a = {"detectors": {"yunet": {"accuracy": 0.9}}}
        dev_b = _bench({"always_NEUTRAL": _model(0.6, 0.25, 0.0, 1.0, False, baseline=True),
                        "cand": _model(0.8, 0.55, 0.05, 0.001, True)})
        ad = RPT.evaluate_adoption(dev_b, None)
        frozen = RPT.freeze_dev(dev_a, dev_b, ad)
        self.assertEqual(RPT.require_frozen_dev()["fingerprint"], frozen["fingerprint"])
        self.assertEqual(frozen["candidates_still_eligible"], ["cand"])

    def test_fingerprint_changes_if_a_dev_number_changes(self):
        dev_a = {"detectors": {"yunet": {"accuracy": 0.9}}}
        dev_b = _bench({"always_NEUTRAL": _model(0.6, 0.25, 0.0, 1.0, False, baseline=True),
                        "cand": _model(0.8, 0.55, 0.05, 0.001, True)})
        ad = RPT.evaluate_adoption(dev_b, None)
        first = RPT._dev_fingerprint(dev_a, dev_b, ad)

        dev_b["models"]["cand"]["accuracy"] = 0.81
        ad2 = RPT.evaluate_adoption(dev_b, None)
        self.assertNotEqual(first, RPT._dev_fingerprint(dev_a, dev_b, ad2))

    def test_fingerprint_is_stable_for_identical_input(self):
        dev_a = {"detectors": {"yunet": {"accuracy": 0.9}}}
        dev_b = _bench({"always_NEUTRAL": _model(0.6, 0.25, 0.0, 1.0, False, baseline=True)})
        ad = RPT.evaluate_adoption(dev_b, None)
        self.assertEqual(RPT._dev_fingerprint(dev_a, dev_b, ad),
                         RPT._dev_fingerprint(dev_a, dev_b, ad))


class TestPersistence(unittest.TestCase):
    def test_strip_drops_the_per_frame_vectors(self):
        res = {"models": {"m": {"accuracy": 0.5, "_pred": ["NEUTRAL"] * 3}}}
        out = RPT._strip(res)
        self.assertNotIn("_pred", out["models"]["m"])
        self.assertEqual(out["models"]["m"]["accuracy"], 0.5)
        self.assertIn("_pred", res["models"]["m"])       # original untouched

    def test_strip_handles_the_detector_shape_too(self):
        res = {"detectors": {"yunet": {"accuracy": 0.9, "_pred": ["FACE"]}}}
        self.assertNotIn("_pred", RPT._strip(res)["detectors"]["yunet"])


# ── Integration: the scorer against the real artefacts ────────────────────────
#
# These skip until the bench has actually been run, so the suite stays green on a
# clean checkout. Once detections and predictions exist they are the check that
# the scorer joins gold to predictions correctly — the one bug class the synthetic
# tests above cannot reach, because it lives in the join and not in the
# arithmetic.

_HAS_DETECTIONS = (V2 / "detections").is_dir() and any((V2 / "detections").glob("*.json"))
_HAS_PREDICTIONS = (V2 / "predictions").is_dir() and any((V2 / "predictions").glob("*.json"))
_HAS_LABELS = (V2 / "facial_labels_v2.json").exists()


@unittest.skipUnless(_HAS_LABELS and _HAS_DETECTIONS, "bench not run yet")
class TestBenchAOnRealData(unittest.TestCase):
    def setUp(self):
        self.dev = RPT.score_detectors(split="dev")
        self.hold = RPT.score_detectors(split="holdout")

    def test_gold_matches_the_ground_truth_module(self):
        gold = GT.face_set(split="dev")
        self.assertEqual(self.dev["n_frames"], len(gold))
        self.assertEqual(self.dev["n_faced"], sum(g["has_face"] for g in gold))

    def test_splits_partition_the_face_set(self):
        self.assertEqual(self.dev["n_frames"] + self.hold["n_frames"],
                         len(GT.face_set()))
        self.assertEqual(set(self.dev["order"]) & set(self.hold["order"]), set())

    def test_every_detector_scored_every_frame(self):
        for name, rec in self.dev["detectors"].items():
            with self.subTest(detector=name):
                self.assertFalse(rec.get("incomplete"), f"{name} did not cover the sample")
                self.assertEqual(rec["n_frames"], self.dev["n_frames"])

    def test_confusion_matrix_totals_equal_the_sample(self):
        for name, rec in self.dev["detectors"].items():
            with self.subTest(detector=name):
                total = sum(sum(row.values()) for row in rec["confusion"].values())
                self.assertEqual(total, self.dev["n_frames"])

    def test_baselines_are_exactly_what_they_claim(self):
        never = self.dev["detectors"]["never_face"]
        self.assertEqual(never["false_positives"], 0)
        self.assertEqual(never["recall"], 0.0)
        always = self.dev["detectors"]["always_face"]
        self.assertEqual(always["recall"], 1.0)
        self.assertEqual(always["false_positives"], self.dev["n_faceless"])

    def test_accuracy_is_inside_its_own_interval(self):
        for name, rec in self.dev["detectors"].items():
            lo, hi = rec["accuracy_ci95"]
            with self.subTest(detector=name):
                self.assertLessEqual(lo, rec["accuracy"])
                self.assertLessEqual(rec["accuracy"], hi)


@unittest.skipUnless(_HAS_LABELS and _HAS_PREDICTIONS, "classifiers not run yet")
class TestBenchBOnRealData(unittest.TestCase):
    def setUp(self):
        self.dev = RPT.score_classifiers(split="dev")
        self.alt = RPT.score_classifiers(split="dev", mapping="surprise_neutral")

    def test_gold_matches_the_ground_truth_module(self):
        self.assertEqual(self.dev["n_frames"], len(GT.expression_set(split="dev")))

    def test_class_counts_sum_to_the_sample(self):
        self.assertEqual(sum(self.dev["class_counts"].values()), self.dev["n_frames"])

    def test_every_model_predicted_every_frame(self):
        for name, rec in self.dev["models"].items():
            with self.subTest(model=name):
                self.assertEqual(rec["n"], self.dev["n_frames"])

    def test_abstentions_are_counted_not_dropped(self):
        for name, rec in self.dev["models"].items():
            if rec.get("baseline"):
                continue
            with self.subTest(model=name):
                scored = sum(sum(r.values()) for r in rec["confusion"].values())
                self.assertEqual(scored, self.dev["n_frames"])

    def test_sensitivity_mapping_moves_only_surprise(self):
        # Same frames, same order; only frames the rater called `surprised` may
        # change class between the two declared mappings.
        rows = {r["uid"]: r for r in GT.expression_set(split="dev")}
        alt_rows = {r["uid"]: r for r in
                    GT.expression_set(split="dev",
                                      mapping=GT.EXPRESSION_THREE_SURPRISE_NEUTRAL)}
        self.assertEqual(set(rows), set(alt_rows))
        for uid, r in rows.items():
            if r["fine"] != "surprised":
                self.assertEqual(r["three"], alt_rows[uid]["three"])
            else:
                self.assertEqual(r["three"], "POSITIVE")
                self.assertEqual(alt_rows[uid]["three"], "NEUTRAL")

    def test_constant_is_the_majority_class(self):
        counts = self.dev["class_counts"]
        self.assertEqual(self.dev["majority_class"], max(counts, key=counts.get))
        const = self.dev["models"][self.dev["constant_name"]]
        self.assertAlmostEqual(const["accuracy"],
                               max(counts.values()) / self.dev["n_frames"])

    def test_no_model_is_compared_against_itself(self):
        self.assertNotIn("mcnemar_vs_constant",
                         self.dev["models"][self.dev["constant_name"]])

    def test_collected_anger_count_covers_both_splits(self):
        total = RPT.n_anger_collected()
        hold = RPT.score_classifiers(split="holdout")["n_anger"]
        self.assertEqual(total, self.dev["n_anger"] + hold)
        q2 = RPT.q2_status(total, self.dev["n_anger"], "dev")
        self.assertEqual(q2["n_anger_frames"], total)
        self.assertEqual(q2["floor"], RPT.Q2_ANGER_FLOOR)


# ── The down-weighting A/B harness ────────────────────────────────────────────
#
# `damping_ab.py` is a bench script, but two of its behaviours decide whether the
# before/after it reports is honest, so they are tested rather than trusted: that
# a segment the controller never scored is copied through instead of being
# re-scored, and that the module-level weight it monkeypatches is always put back.

class TestDampingABHarness(unittest.TestCase):
    ROWS = {"0": {"segment_id": 0, "start_time": 0.0, "end_time": 2.0,
                  "transcript_sentiment": {"label": "POSITIVE"},
                  "vocal_emotion": {"label": "POSITIVE"},
                  "facial_emotion": {"dominant": "sad"}}}
    COMMENTS = {"label": "POSITIVE", "confidence": 0.8}

    def test_a_fallback_entry_without_raw_is_copied_through(self):
        # No `_raw` means the controller failed and `_safe_fallback` ran. A live
        # run would produce the same thing, so re-scoring it would invent a
        # difference between the arms that the pipeline would never show.
        source = {"0": {"segment_id": 0, "conflict_score": 0.5, "flagged": False}}
        out = DAB._coerce_all(self.ROWS, source, self.COMMENTS, 0.342)
        self.assertEqual(out, [source["0"]])
        self.assertIsNot(out[0], source["0"])          # copied, not aliased

    def test_a_segment_missing_from_rows_is_copied_through(self):
        source = {"9": {"segment_id": 9, "conflict_score": 0.5,
                        "_raw": {"conflict_score": 0.5}}}
        out = DAB._coerce_all(self.ROWS, source, self.COMMENTS, 0.342)
        self.assertEqual(out[0]["conflict_score"], 0.5)

    def test_the_weight_is_applied_then_restored(self):
        import importlib
        O = importlib.import_module("pipeline.orchestrator")
        before = O.FACIAL_ONLY_CONFLICT_WEIGHT
        source = {"0": {"segment_id": 0, "_raw": {"conflict_score": 0.9,
                                                  "channels_in_conflict": []}}}
        out = DAB._coerce_all(self.ROWS, source, self.COMMENTS, 0.5)
        self.assertAlmostEqual(out[0]["conflict_score"], 0.45)
        self.assertEqual(O.FACIAL_ONLY_CONFLICT_WEIGHT, before)

    def test_the_weight_is_restored_even_when_coercion_raises(self):
        import importlib
        O = importlib.import_module("pipeline.orchestrator")
        before = O.FACIAL_ONLY_CONFLICT_WEIGHT
        with self.assertRaises(ValueError):
            DAB._coerce_all(self.ROWS, {"not-an-int": {}}, self.COMMENTS, 0.5)
        self.assertEqual(O.FACIAL_ONLY_CONFLICT_WEIGHT, before)

    def test_weight_of_one_is_the_identity(self):
        source = {"0": {"segment_id": 0, "_raw": {"conflict_score": 0.9,
                                                  "channels_in_conflict": []}}}
        out = DAB._coerce_all(self.ROWS, source, self.COMMENTS, 1.0)
        self.assertAlmostEqual(out[0]["conflict_score"], 0.9)
