"""
test_axis_analysis.py — unit tests for `baseline_bench/axis_analysis.py`.

Scope: the arithmetic is exercised for real, never mocked. No
LLM is called, no rating file is written, no page is rebuilt.

Three things in that module are load-bearing for `AXIS_RESULT.md` and are tested
as properties rather than as remembered constants, because a constant frozen from
the same code it is testing proves nothing:

  1. `eta_upper_bound` is claimed to be a *proof*. So it is tested as one: on
     randomised data it must bound every ordering a rule could choose, including
     the exhaustive maximum. A single counterexample would invalidate §6.
  2. `_loo_predictions` is claimed to be rank-inverting, which is why §6.2 threw
     it away. That defect is asserted here so nobody "fixes" the analysis by
     reinstating it.
  3. `_repeated_split` is claimed to be unbiased where the other two estimators
     are not. All three are run against a null and their biases compared.

The provenance assertions in `build_rows` are exercised against the real files,
because their whole purpose is to fail on a mismatch that only real files can
have.
"""
from __future__ import annotations

import collections
import itertools
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BB = ROOT / "research" / "baseline_bench"

# Same save/pop/import/restore discipline as tests/test_baseline_bench.py: bare
# module names are shared across the bench directories, and an unrestored
# sys.modules entry makes a LATER bench's tests import this bench's module.
_SHARED = ("stats", "rater_analysis", "axis_analysis", "sample", "build_pages",
           "verify_page", "report_bench", "run_bench", "systems", "candidates")


def _load():
    saved = {n: sys.modules.pop(n, None) for n in _SHARED}
    sys.path.insert(0, str(BB))
    try:
        import axis_analysis
        import stats
        return stats, axis_analysis
    finally:
        for n in _SHARED:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]
        while str(BB) in sys.path:
            sys.path.remove(str(BB))


S, AX = _load()


def _rows(spec):
    """Minimal rows: (h, transcript, vocal, facial-or-None) tuples."""
    out = []
    for i, (h, t, v, f) in enumerate(spec):
        vt, vv = AX.VALENCE[t], AX.VALENCE[v]
        vf = AX.FACIAL_VALENCE[f] if f is not None else None
        out.append({"uid": f"u{i}", "split": "selection", "h": float(h),
                    "c": 0.5, "c_raw": 0.5, "t_label": t, "v_label": v,
                    "f_label": f, "vt": vt, "vv": vv, "vf": vf, "vc": 1,
                    "seen": [x for x in (vt, vv, vf, 1) if x is not None]})
    return out


class TestValenceMaps(unittest.TestCase):
    def test_sentiment_map_is_the_three_way_axis(self):
        self.assertEqual(AX.VALENCE,
                         {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": -1})

    def test_every_deepface_class_is_mapped(self):
        # DeepFace's FER head emits exactly these seven. An unmapped class would
        # raise KeyError mid-run rather than silently scoring as neutral.
        for cls in ("angry", "disgust", "fear", "happy", "sad", "surprise",
                    "neutral"):
            self.assertIn(cls, AX.FACIAL_VALENCE)

    def test_facial_map_is_signed_consistently(self):
        for cls in ("sad", "fear", "angry", "disgust"):
            self.assertEqual(AX.FACIAL_VALENCE[cls], -1)
        self.assertEqual(AX.FACIAL_VALENCE["happy"], 1)
        self.assertEqual(AX.FACIAL_VALENCE["neutral"], 0)

    def test_alt_map_differs_only_on_surprise(self):
        diff = {k for k in AX.FACIAL_VALENCE
                if AX.FACIAL_VALENCE[k] != AX.FACIAL_VALENCE_ALT[k]}
        self.assertEqual(diff, {"surprise"})
        self.assertEqual(AX.FACIAL_VALENCE_ALT["surprise"], 0)


class TestDisagreement(unittest.TestCase):
    def test_all_agreeing_is_zero(self):
        r = _rows([(4, "POSITIVE", "POSITIVE", "happy")])[0]
        self.assertEqual(r["seen"], [1, 1, 1, 1])
        self.assertAlmostEqual(AX.disagreement(r), 0.0)
        self.assertEqual(AX.n_distinct(r), 1)

    def test_population_sd_not_sample_sd(self):
        # seen = [-1, 1]; population SD 1.0, sample SD would be sqrt(2).
        r = {"seen": [-1, 1]}
        self.assertAlmostEqual(AX.disagreement(r), 1.0)

    def test_maximum_spread_is_one(self):
        r = {"seen": [-1, -1, 1, 1]}
        self.assertAlmostEqual(AX.disagreement(r), 1.0)

    def test_missing_face_is_absent_not_zero(self):
        # A missing face must shrink the channel count, not add a neutral vote:
        # "no evidence" and "neutral evidence" are different inputs.
        with_face = _rows([(4, "POSITIVE", "POSITIVE", "neutral")])[0]
        without = _rows([(4, "POSITIVE", "POSITIVE", None)])[0]
        self.assertEqual(len(with_face["seen"]), 4)
        self.assertEqual(len(without["seen"]), 3)
        self.assertGreater(AX.disagreement(with_face), AX.disagreement(without))
        self.assertAlmostEqual(AX.disagreement(without), 0.0)

    def test_n_distinct_counts_values_not_channels(self):
        self.assertEqual(AX.n_distinct({"seen": [1, 1, 0, -1]}), 3)
        self.assertEqual(AX.n_distinct({"seen": [0, 0, 0]}), 1)


class TestEtaIsAProof(unittest.TestCase):
    """§6's bound is a mathematical claim, so it is tested as one."""

    def _eta_and_exhaustive_max(self, rows, key):
        eta = AX.eta_upper_bound(rows, key)
        h = [r["h"] for r in rows]
        groups = collections.defaultdict(list)
        for i, r in enumerate(rows):
            groups[key(r)].append(i)
        ks = list(groups)
        best = -2.0
        for order in itertools.permutations(ks):
            pred = [0.0] * len(rows)
            for pos, k in enumerate(order):
                for i in groups[k]:
                    pred[i] = float(pos)
            v = S.spearman(h, pred)
            if v is not None and v > best:
                best = v
        return eta, best

    def test_eta_bounds_the_exhaustive_maximum_on_random_data(self):
        rng = random.Random(20260908)
        labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        faces = [None, "happy", "neutral", "sad"]
        for _ in range(120):
            spec = [(rng.choice([1, 2, 3, 4, 5]), rng.choice(labels),
                     rng.choice(labels), rng.choice(faces))
                    for _ in range(rng.randint(6, 14))]
            rows = _rows(spec)
            key = (lambda r: (r["t_label"], r["v_label"]))
            groups = {key(r) for r in rows}
            if not 2 <= len(groups) <= 6:
                continue
            eta, best = self._eta_and_exhaustive_max(rows, key)
            if math.isnan(eta):
                continue
            self.assertLessEqual(best, eta + 1e-9,
                                 f"eta {eta} failed to bound {best}")

    def test_eta_bounds_arbitrary_group_constant_predictors(self):
        rng = random.Random(7)
        labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        for _ in range(200):
            rows = _rows([(rng.choice([1, 2, 3, 4, 5]), rng.choice(labels),
                           rng.choice(labels), None) for _ in range(20)])
            key = (lambda r: (r["t_label"],))
            eta = AX.eta_upper_bound(rows, key)
            if math.isnan(eta):
                continue
            vals = {k: rng.uniform(-5, 5) for k in {key(r) for r in rows}}
            got = S.spearman([r["h"] for r in rows], [vals[key(r)] for r in rows])
            if got is not None:
                self.assertLessEqual(abs(got), eta + 1e-9)

    def test_eta_is_one_when_groups_perfectly_separate(self):
        rows = _rows([(1, "NEGATIVE", "NEUTRAL", None),
                      (1, "NEGATIVE", "NEUTRAL", None),
                      (5, "POSITIVE", "NEUTRAL", None),
                      (5, "POSITIVE", "NEUTRAL", None)])
        self.assertAlmostEqual(AX.eta_upper_bound(rows, lambda r: (r["t_label"],)),
                               1.0, places=12)

    def test_eta_is_zero_when_the_grouping_is_uninformative(self):
        rows = _rows([(1, "POSITIVE", "NEUTRAL", None),
                      (5, "POSITIVE", "NEUTRAL", None),
                      (1, "NEGATIVE", "NEUTRAL", None),
                      (5, "NEGATIVE", "NEUTRAL", None)])
        self.assertAlmostEqual(AX.eta_upper_bound(rows, lambda r: (r["t_label"],)),
                               0.0, places=12)

    def test_best_ordering_never_exceeds_eta(self):
        rng = random.Random(99)
        labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        seen_methods = set()
        for _ in range(25):
            rows = _rows([(rng.choice([1, 2, 3, 4, 5]), rng.choice(labels),
                           rng.choice(labels), None) for _ in range(24)])
            key = (lambda r: (r["t_label"], r["v_label"]))
            eta = AX.eta_upper_bound(rows, key)
            best = AX.best_ordering(rows, key, restarts=4)
            n_groups = len({key(r) for r in rows})
            seen_methods.add(best["method"])
            self.assertEqual(best["method"] == "exhaustive",
                             n_groups <= AX.EXHAUSTIVE_MAX)
            if math.isnan(eta):
                continue
            self.assertLessEqual(best["rho"], eta + 1e-9)
        self.assertTrue(seen_methods)

    def test_best_ordering_is_at_least_the_group_mean_oracle(self):
        rng = random.Random(11)
        labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        for _ in range(25):
            rows = _rows([(rng.choice([1, 2, 3, 4, 5]), rng.choice(labels),
                           rng.choice(labels), None) for _ in range(24)])
            key = (lambda r: (r["t_label"], r["v_label"]))
            means, _ = AX._group_means(rows, key)
            gm = S.spearman([r["h"] for r in rows], [means[key(r)] for r in rows])
            best = AX.best_ordering(rows, key, restarts=4)["rho"]
            if gm is not None:
                self.assertGreaterEqual(best, gm - 1e-12)


class TestEstimatorBias(unittest.TestCase):
    """§6.2: LOO is rank-inverting, K-fold is mildly biased, splits are not."""

    def _null_rows(self, n, seed):
        rng = random.Random(seed)
        labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        return _rows([(rng.choice([1, 2, 3, 4, 5]), rng.choice(labels),
                       "NEUTRAL", None) for _ in range(n)])

    def test_loo_predictions_are_rank_reversed_within_every_group(self):
        # The defect, stated exactly. It is cross-sectional, not a response to
        # perturbation: within a group the prediction for member i is
        # (S_g - h_i)/(n_g - 1), which for fixed S_g strictly DECREASES in h_i.
        # So ordering a group's members by h orders their predictions backwards.
        rows = self._null_rows(60, 1)
        key = (lambda r: (r["t_label"],))
        pred = AX._loo_predictions(rows, key)
        groups = collections.defaultdict(list)
        for r in rows:
            groups[key(r)].append(r)
        checked = 0
        for members in groups.values():
            if len(members) < 3:
                continue
            checked += 1
            by_h = sorted(members, key=lambda r: r["h"])
            preds = [pred[r["uid"]] for r in by_h]
            for a, b in zip(preds, preds[1:]):
                self.assertGreaterEqual(a, b)      # non-increasing: reversed
            self.assertGreater(preds[0], preds[-1])
        self.assertGreater(checked, 0)

    def test_loo_is_negatively_biased_under_the_null(self):
        key = (lambda r: (r["t_label"],))
        vals = []
        for seed in range(40):
            rows = self._null_rows(60, seed)
            pred = AX._loo_predictions(rows, key)
            v = S.spearman([r["h"] for r in rows],
                           [pred[r["uid"]] for r in rows])
            if v is not None:
                vals.append(v)
        self.assertLess(sum(vals) / len(vals), -0.05)

    def test_repeated_split_is_unbiased_under_the_null(self):
        key = (lambda r: (r["t_label"],))
        rows = self._null_rows(90, 5)
        d = AX._repeated_split(rows, key, n_train=60, n_splits=300, seed=3,
                               shuffle_h=True)
        self.assertLess(abs(d["mean"]), 0.05)
        self.assertLess(d["lo"], 0.0)
        self.assertGreater(d["hi"], 0.0)

    def test_repeated_split_is_less_biased_than_loo(self):
        key = (lambda r: (r["t_label"],))
        rows = self._null_rows(90, 8)
        split = AX._repeated_split(rows, key, n_train=60, n_splits=300, seed=3,
                                   shuffle_h=True)["mean"]
        loo = []
        for seed in range(30):
            rr = self._null_rows(90, 100 + seed)
            pred = AX._loo_predictions(rr, key)
            v = S.spearman([r["h"] for r in rr], [pred[r["uid"]] for r in rr])
            if v is not None:
                loo.append(v)
        self.assertLess(abs(split), abs(sum(loo) / len(loo)))

    def test_cv_never_uses_a_segment_to_predict_itself(self):
        # Changing one segment's h must not change any OTHER fold's prediction
        # for it beyond what removing it from training does -- concretely, a
        # singleton-group segment gets the training mean, never its own value.
        rows = _rows([(1, "NEGATIVE", "NEUTRAL", None)]
                     + [(5, "POSITIVE", "NEUTRAL", None) for _ in range(19)])
        key = (lambda r: (r["t_label"],))
        pred = AX._cv_predictions(rows, key, n_folds=10, seed=1)
        self.assertNotAlmostEqual(pred[rows[0]["uid"]], 1.0)
        self.assertAlmostEqual(pred[rows[0]["uid"]], 5.0)

    def test_split_sizes_are_respected(self):
        rows = self._null_rows(50, 2)
        d = AX._repeated_split(rows, (lambda r: (r["t_label"],)),
                               n_train=30, n_splits=10, seed=1)
        self.assertEqual(d["n_train"], 30)
        self.assertEqual(d["n_test"], 20)
        self.assertEqual(d["n_splits"], 10)


class TestGroupMeans(unittest.TestCase):
    def test_group_means_and_grand_mean(self):
        rows = _rows([(1, "POSITIVE", "NEUTRAL", None),
                      (3, "POSITIVE", "NEUTRAL", None),
                      (5, "NEGATIVE", "NEUTRAL", None)])
        means, grand = AX._group_means(rows, lambda r: (r["t_label"],))
        self.assertAlmostEqual(means[("POSITIVE",)], 2.0)
        self.assertAlmostEqual(means[("NEGATIVE",)], 5.0)
        self.assertAlmostEqual(grand, 3.0)


class TestRealFiles(unittest.TestCase):
    """Integration: the provenance assertions only mean something on real files."""

    @classmethod
    def setUpClass(cls):
        if not (BB / "sample.json").exists():
            raise unittest.SkipTest("baseline_bench sample not present")
        saved = {n: sys.modules.pop(n, None) for n in _SHARED}
        sys.path.insert(0, str(BB))
        try:
            import rater_analysis as RA
            cls.RA = RA
            cls.sample, cls.items, cls.dups, cls.pr = RA.load()
        finally:
            for n in _SHARED:
                sys.modules.pop(n, None)
                if saved[n] is not None:
                    sys.modules[n] = saved[n]
            while str(BB) in sys.path:
                sys.path.remove(str(BB))

    def test_rows_are_exactly_P1s_segments(self):
        rows = AX.build_rows(self.items, self.pr)
        keep = {u for u in self.items
                if self.RA.usable_count(self.pr, u) >= self.RA.MIN_USABLE}
        self.assertEqual({r["uid"] for r in rows}, keep)

    def test_h_matches_the_protocol_ground_truth(self):
        rows = AX.build_rows(self.items, self.pr)
        for r in rows[:25]:
            self.assertAlmostEqual(r["h"],
                                   self.RA.ground_truth(self.pr, r["uid"]))

    def test_payload_labels_match_the_rated_clips(self):
        # build_rows asserts this internally; if it ever stops asserting, this
        # test still fails rather than passing vacuously.
        rows = AX.build_rows(self.items, self.pr)
        for r in rows:
            it = self.items[r["uid"]]
            self.assertEqual(r["t_label"], it["transcript_sentiment"])
            self.assertEqual(r["v_label"], it["vocal_emotion"])
            self.assertEqual(r["f_label"], it["facial_emotion"])

    def test_provenance_assertion_fires_on_a_tampered_label(self):
        tampered = {u: dict(it) for u, it in self.items.items()}
        first = sorted(tampered)[0]
        flip = {"POSITIVE": "NEGATIVE", "NEGATIVE": "POSITIVE",
                "NEUTRAL": "POSITIVE"}
        tampered[first]["transcript_sentiment"] = \
            flip[tampered[first]["transcript_sentiment"]]
        with self.assertRaises(AssertionError):
            AX.build_rows(tampered, self.pr)

    def test_comment_channel_is_constant(self):
        # §6 excludes comments from the oracle on this ground.
        rows = AX.build_rows(self.items, self.pr)
        self.assertEqual({r["vc"] for r in rows}, {1})

    def test_vocal_never_emits_negative(self):
        # §3's |v| == v identity depends on this and would silently become a
        # measured result rather than an identity if it stopped holding.
        rows = AX.build_rows(self.items, self.pr)
        self.assertNotIn(-1, {r["vv"] for r in rows})
        self.assertTrue(all(abs(r["vv"]) == r["vv"] for r in rows))

    def test_eta_bounds_every_measured_value_on_the_real_data(self):
        rows = AX.build_rows(self.items, self.pr)
        key = (lambda r: (r["t_label"], r["v_label"], r["f_label"]))
        eta = AX.eta_upper_bound(rows, key)
        means, _ = AX._group_means(rows, key)
        gm = S.spearman([r["h"] for r in rows], [means[key(r)] for r in rows])
        self.assertLessEqual(gm, eta + 1e-12)
        self.assertLess(eta, 0.8037884759743298)   # the P5 human ceiling


if __name__ == "__main__":
    unittest.main()
