"""
test_baseline_bench.py — unit tests for the baseline bench's statistics and for
the ground-truth construction that PROTOCOL.md §5.4 specifies.

Scope: the arithmetic is exercised for real, never mocked. No
rating file is written, no page is rebuilt, no model is loaded.

Why the reference constants in here are trustworthy, since that is the whole
point of the file: every statistic in `baseline_bench/stats.py` was cross-checked
against an independent implementation before these values were frozen —

  spearman, pearson          -> scipy.stats (300 randomised heavy-tie cases)
  weighted_kappa lin + quad  -> sklearn.metrics.cohen_kappa_score (300 cases each)
  _percentile                -> numpy.percentile, 'linear' (300 cases)
  krippendorff_alpha         -> the `krippendorff` PyPI package, all three
                                metrics, 400 randomised cases WITH missing data,
                                zero mismatches, max |diff| 8.9e-16
  icc_2k                     -> pingouin ICC(A,1) / ICC(A,k) (120 cases)

`krippendorff` and `pingouin` are not project dependencies and are deliberately
not imported here — they were used once, in a throwaway environment, to certify
the constants below. scipy and scikit-learn ARE in the project venv, so the tests
that can re-derive their expected value live rather than quote it, do.

One caution this file exists to enforce: the canonical Krippendorff worked
example is often quoted with the wrong alpha values. The constants below are the
ones the reference implementation actually produces on that data, not the ones
recalled from a paper. If a future session "corrects" them upward, check against
the library before believing it.
"""
from __future__ import annotations

import json
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BB = ROOT / "research" / "baseline_bench"

# Bare module names are shared across the six bench directories in this repo.
# Same save/pop/import/restore discipline as tests/test_controller_bench.py, and
# for the same reason: an unrestored sys.modules entry makes a LATER bench's
# test file import this bench's module under the shared name.
_SHARED = ("stats", "rater_analysis", "sample", "build_pages", "verify_page",
           "report_bench", "run_bench", "candidates")


def _load():
    saved = {n: sys.modules.pop(n, None) for n in _SHARED}
    sys.path.insert(0, str(BB))
    try:
        import rater_analysis
        import stats
        return stats, rater_analysis
    finally:
        for n in _SHARED:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]
        while str(BB) in sys.path:
            sys.path.remove(str(BB))


S, RA = _load()

# Krippendorff's 3-observer / 12-unit worked example. '.' = not coded.
KRIPP_A = [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None]
KRIPP_B = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3]
KRIPP_C = [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None]
KRIPP_UNITS = [[v for v in t if v is not None]
               for t in zip(KRIPP_A, KRIPP_B, KRIPP_C)]

# Shrout & Fleiss's 6-target / 4-judge ICC dataset.
SF = [[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8],
      [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]]


class TestRanks(unittest.TestCase):
    def test_average_ranks_for_ties(self):
        self.assertEqual(S.ranks([1, 2, 2, 3]), [1.0, 2.5, 2.5, 4.0])

    def test_all_tied_gives_all_the_same_rank(self):
        self.assertEqual(S.ranks([7, 7, 7, 7]), [2.5] * 4)

    def test_ranks_are_a_permutation_of_1_to_n_in_sum(self):
        xs = [random.Random(1).randint(1, 5) for _ in range(50)]
        self.assertAlmostEqual(sum(S.ranks(xs)), 50 * 51 / 2, places=9)


class TestSpearman(unittest.TestCase):
    def test_matches_scipy_on_heavy_ties(self):
        from scipy import stats as sps
        rng = random.Random(11)
        for _ in range(60):
            n = rng.randint(6, 60)
            a = [rng.randint(1, 5) for _ in range(n)]
            b = [rng.randint(1, 5) for _ in range(n)]
            if len(set(a)) < 2 or len(set(b)) < 2:
                continue
            self.assertAlmostEqual(S.spearman(a, b),
                                   sps.spearmanr(a, b).statistic, places=12)

    def test_perfect_and_inverse(self):
        self.assertAlmostEqual(S.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0, places=12)
        self.assertAlmostEqual(S.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0, places=12)

    def test_constant_vector_is_zero_not_nan(self):
        # scipy returns nan here. 0.0 is the project convention and it is a
        # claim: a predictor saying the same thing about every segment has
        # demonstrated no correlation. `constant` in PROTOCOL.md §3.3 relies on
        # this returning exactly 0.0.
        self.assertEqual(S.spearman([1, 1, 1, 1], [1, 2, 3, 4]), 0.0)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            S.spearman([1, 2], [1, 2, 3])


class TestPearson(unittest.TestCase):
    def test_matches_scipy(self):
        from scipy import stats as sps
        rng = random.Random(3)
        for _ in range(40):
            n = rng.randint(4, 40)
            a = [rng.gauss(0, 1) for _ in range(n)]
            b = [rng.gauss(0, 1) for _ in range(n)]
            self.assertAlmostEqual(S.pearson(a, b),
                                   sps.pearsonr(a, b).statistic, places=12)

    def test_constant_is_zero(self):
        self.assertEqual(S.pearson([2, 2, 2], [1, 2, 3]), 0.0)


class TestPercentile(unittest.TestCase):
    def test_matches_numpy_linear(self):
        import numpy as np
        rng = random.Random(5)
        for _ in range(40):
            xs = sorted(rng.gauss(0, 1) for _ in range(rng.randint(2, 120)))
            for q in (0.025, 0.25, 0.5, 0.75, 0.975):
                self.assertAlmostEqual(S._percentile(xs, q),
                                       float(np.percentile(xs, q * 100)), places=12)

    def test_single_element(self):
        self.assertEqual(S._percentile([4.0], 0.9), 4.0)


class TestWeightedKappa(unittest.TestCase):
    def test_matches_sklearn(self):
        from sklearn.metrics import cohen_kappa_score
        rng = random.Random(9)
        cats = [1, 2, 3, 4, 5]
        for w in ("linear", "quadratic"):
            for _ in range(40):
                n = rng.randint(15, 90)
                a = [rng.choice(cats) for _ in range(n)]
                b = [x if rng.random() < 0.5 else rng.choice(cats) for x in a]
                exp = cohen_kappa_score(a, b, labels=cats, weights=w)
                if math.isnan(exp):
                    continue
                self.assertAlmostEqual(S.weighted_kappa(a, b, cats, w), exp, places=12)

    def test_perfect_agreement_is_one(self):
        a = [1, 2, 3, 4, 5, 1, 2]
        self.assertAlmostEqual(S.weighted_kappa(a, a, [1, 2, 3, 4, 5]), 1.0, places=12)

    def test_both_constant_is_zero_not_one(self):
        # Two raters who both press 4 every time have shown nothing. Awarding
        # 1.0 there would make a lazy pair look like the best pair in the study.
        self.assertEqual(S.weighted_kappa([4] * 10, [4] * 10, [1, 2, 3, 4, 5]), 0.0)

    def test_unused_categories_do_not_change_kappa(self):
        # Checked, not assumed. Adding unused categories to an evenly-spaced
        # ordinal scale rescales every weight by one constant, which cancels in
        # the d_obs/d_exp ratio. scikit-learn agrees. An earlier docstring here
        # claimed unused categories INFLATE kappa; that was wrong, and this test
        # is what caught it.
        a, b = [1, 2, 3, 1, 2], [1, 2, 3, 2, 1]
        for w in ("linear", "quadratic"):
            self.assertAlmostEqual(S.weighted_kappa(a, b, [1, 2, 3, 4, 5], w),
                                   S.weighted_kappa(a, b, [1, 2, 3], w), places=12)

    def test_out_of_scale_value_raises_rather_than_being_absorbed(self):
        # This IS why `categories` is an argument. A stray 0 — this study's
        # "unratable" code — must stop the computation, not quietly join the
        # scale as a sixth category below 1.
        with self.assertRaises(KeyError):
            S.weighted_kappa([1, 0], [1, 2], [1, 2, 3, 4, 5])

    def test_bad_weight_name_raises(self):
        with self.assertRaises(ValueError):
            S.weighted_kappa([1, 2], [1, 2], [1, 2], weights="cubic")


class TestKrippendorff(unittest.TestCase):
    """Constants certified against the `krippendorff` PyPI reference — see the
    module docstring. They are NOT the values commonly recalled for this
    example."""

    def test_canonical_example_nominal(self):
        r = S.krippendorff_alpha(KRIPP_UNITS, "nominal")
        self.assertAlmostEqual(r["alpha"], 0.6752577319587629, places=13)

    def test_canonical_example_ordinal(self):
        r = S.krippendorff_alpha(KRIPP_UNITS, "ordinal")
        self.assertAlmostEqual(r["alpha"], 0.8048605240912934, places=13)

    def test_canonical_example_interval(self):
        r = S.krippendorff_alpha(KRIPP_UNITS, "interval")
        self.assertAlmostEqual(r["alpha"], 0.8621041879468846, places=13)

    def test_units_with_one_value_are_excluded(self):
        r = S.krippendorff_alpha(KRIPP_UNITS, "ordinal")
        self.assertEqual(r["n_units"], 10)     # 12 units, 2 singly-coded
        self.assertEqual(r["n_pairable"], 28)

    def test_frequency_form_equals_bruteforce_form(self):
        # The check that catches an algebra slip a function and its own unit
        # test could share: two different arrangements of the same definition.
        rng = random.Random(17)
        for _ in range(60):
            units = [[rng.randint(1, 5) for _ in range(rng.randint(0, 4))]
                     for _ in range(rng.randint(4, 20))]
            if sum(1 for u in units if len(u) >= 2) < 2:
                continue
            if len({v for u in units for v in u}) < 2:
                continue
            for m in ("nominal", "ordinal", "interval"):
                self.assertAlmostEqual(
                    S.krippendorff_alpha(units, m)["alpha"],
                    S.krippendorff_alpha_bruteforce(units, m), places=12)

    def test_perfect_agreement_is_one(self):
        units = [[1, 1], [2, 2], [3, 3], [5, 5]]
        self.assertAlmostEqual(S.krippendorff_alpha(units, "ordinal")["alpha"],
                               1.0, places=12)

    def test_no_usable_units_is_nan_not_zero(self):
        r = S.krippendorff_alpha([[1], [2], []], "ordinal")
        self.assertTrue(math.isnan(r["alpha"]))
        self.assertEqual(r["n_units"], 0)

    def test_ordinal_beats_nominal_when_errors_are_near_misses(self):
        # The reason PROTOCOL.md §6 specifies ordinal: raters who differ by one
        # point are not the same as raters who differ by four, and nominal alpha
        # cannot tell those apart.
        units = [[1, 2], [2, 3], [3, 4], [4, 5], [5, 4], [1, 2], [2, 1]]
        nom = S.krippendorff_alpha(units, "nominal")["alpha"]
        ordi = S.krippendorff_alpha(units, "ordinal")["alpha"]
        self.assertGreater(ordi, nom)

    def test_unused_categories_do_not_change_alpha(self):
        # A category nobody used has marginal zero and must contribute nothing.
        units = [[1, 1], [2, 2], [2, 1]]
        a = S.krippendorff_alpha(units, "ordinal")["alpha"]
        b = S.krippendorff_alpha(units, "ordinal", categories=[1, 2, 3, 4, 5])["alpha"]
        self.assertAlmostEqual(a, b, places=12)


class TestICC(unittest.TestCase):
    def test_shrout_fleiss_absolute_agreement(self):
        r = S.icc_2k(SF)
        self.assertAlmostEqual(r["icc_2_1"], 0.28976377952755916, places=13)
        self.assertAlmostEqual(r["icc_2_k"], 0.6200505475989893, places=13)

    def test_average_measure_exceeds_single_measure(self):
        r = S.icc_2k(SF)
        self.assertGreater(r["icc_2_k"], r["icc_2_1"])

    def test_perfect_agreement_is_one(self):
        M = [[1, 1, 1], [3, 3, 3], [5, 5, 5], [2, 2, 2]]
        self.assertAlmostEqual(S.icc_2k(M)["icc_2_k"], 1.0, places=9)

    def test_absolute_agreement_penalises_a_constant_offset(self):
        # A rater perfectly correlated but two points generous is NOT
        # interchangeable for a mean-based ground truth. Consistency-ICC would
        # forgive this; absolute-agreement must not.
        base = [[1, 1], [2, 2], [3, 3], [4, 4], [5, 5]]
        offset = [[a, b + 2] for a, b in base]
        self.assertLess(S.icc_2k(offset)["icc_2_k"], S.icc_2k(base)["icc_2_k"])

    def test_degenerate_shapes(self):
        self.assertTrue(math.isnan(S.icc_2k([[1, 2]])["icc_2_k"]))


class TestBootstrap(unittest.TestCase):
    def test_is_deterministic_for_a_fixed_seed(self):
        vals = [(i, i * 2) for i in range(40)]
        f = lambda vs: S.spearman([a for a, _ in vs], [b for _, b in vs])
        a = S.bootstrap_ci(vals, f, n_boot=200, seed=42)
        b = S.bootstrap_ci(vals, f, n_boot=200, seed=42)
        self.assertEqual(a["lo"], b["lo"])
        self.assertEqual(a["hi"], b["hi"])

    def test_different_seeds_differ(self):
        vals = [(i, (i * 7) % 40) for i in range(40)]
        f = lambda vs: S.spearman([a for a, _ in vs], [b for _, b in vs])
        self.assertNotEqual(S.bootstrap_ci(vals, f, n_boot=200, seed=1)["lo"],
                            S.bootstrap_ci(vals, f, n_boot=200, seed=2)["lo"])

    def test_interval_brackets_the_point_estimate(self):
        vals = [(i, i + random.Random(i).gauss(0, 3)) for i in range(60)]
        f = lambda vs: S.spearman([a for a, _ in vs], [b for _, b in vs])
        r = S.bootstrap_ci(vals, f, n_boot=500, seed=42)
        self.assertLessEqual(r["lo"], r["point"])
        self.assertLessEqual(r["point"], r["hi"])

    def test_paired_diff_of_a_system_with_itself_is_exactly_zero(self):
        # The strongest available check that the pairing is real: the same
        # statistic on both sides must give a difference of 0 on EVERY resample,
        # so the whole interval collapses. If the two sides were resampled
        # independently this test fails.
        vals = [(i, i * 2) for i in range(30)]
        f = lambda vs: S.spearman([a for a, _ in vs], [b for _, b in vs])
        r = S.paired_bootstrap_diff(vals, f, f, n_boot=300, seed=42)
        self.assertEqual(r["point"], 0.0)
        self.assertEqual(r["lo"], 0.0)
        self.assertEqual(r["hi"], 0.0)
        self.assertEqual(r["win_frac"], 0.0)

    def test_paired_diff_detects_a_real_difference(self):
        vals = [(i, i, 30 - i) for i in range(30)]
        good = lambda vs: S.spearman([a for a, _, _ in vs], [b for _, b, _ in vs])
        bad = lambda vs: S.spearman([a for a, _, _ in vs], [c for _, _, c in vs])
        r = S.paired_bootstrap_diff(vals, good, bad, n_boot=400, seed=42)
        self.assertGreater(r["point"], 0)
        self.assertTrue(r["excludes_zero"])
        self.assertEqual(r["win_frac"], 1.0)


class TestSpearmanBrown(unittest.TestCase):
    def test_known_value(self):
        self.assertAlmostEqual(S.spearman_brown(0.5, 4), 0.8, places=12)

    def test_k_of_one_is_identity(self):
        self.assertAlmostEqual(S.spearman_brown(0.61, 1), 0.61, places=12)

    def test_monotone_in_k(self):
        vals = [S.spearman_brown(0.4, k) for k in (1, 2, 4, 8)]
        self.assertEqual(vals, sorted(vals))


class TestWilsonAndDescribe(unittest.TestCase):
    def test_wilson_stays_in_unit_interval(self):
        for k, n in ((0, 20), (20, 20), (0, 1), (1, 1), (3, 119)):
            lo, hi = S.wilson(k, n)
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)
            self.assertLessEqual(lo, hi)

    def test_wilson_with_no_observations_is_no_information(self):
        self.assertEqual(S.wilson(0, 0), (0.0, 1.0))

    def test_describe_matches_numpy(self):
        import numpy as np
        xs = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        d = S.describe(xs)
        self.assertAlmostEqual(d["median"], float(np.median(xs)), places=12)
        self.assertAlmostEqual(d["q1"], float(np.percentile(xs, 25)), places=12)
        self.assertAlmostEqual(d["sd"], float(np.std(xs, ddof=1)), places=12)

    def test_describe_empty(self):
        self.assertEqual(S.describe([]), {"n": 0})


class TestGroundTruthConstruction(unittest.TestCase):
    """PROTOCOL.md §5.4, on synthetic ratings — the arithmetic that turns four
    people's keypresses into the number five systems get judged against."""

    def _pr(self, spec):
        return {rn: {u: [(i, r) for i, r in enumerate(v)] for u, v in d.items()}
                for rn, d in spec.items()}

    def test_unratable_is_excluded_not_scored_as_zero(self):
        # The failure this guards is severe and silent: treating a 0 as a rating
        # drags a segment's mean toward the bottom of the scale and would make
        # unratable clips look like the least genuine ones in the study.
        pr = self._pr({"rater1": {"u": [0, 4]}})
        self.assertEqual(RA.rater_value(pr, "rater1", "u"), 4.0)

    def test_a_rater_with_only_unratable_answers_contributes_nothing(self):
        pr = self._pr({"rater1": {"u": [0]}})
        self.assertIsNone(RA.rater_value(pr, "rater1", "u"))

    def test_duplicates_are_averaged_within_a_rater_first(self):
        pr = self._pr({"rater1": {"u": [2, 5]}})
        self.assertEqual(RA.rater_value(pr, "rater1", "u"), 3.5)

    def test_each_rater_is_weighted_equally_despite_duplicates(self):
        # r1 saw the segment twice, r2 once. h must be the mean of 3.0 and 5.0,
        # not the mean of the four raw values 2, 4, 5, 5 (= 4.0).
        pr = self._pr({"rater1": {"u": [2, 4]}, "rater2": {"u": [5]}})
        self.assertEqual(RA.ground_truth(pr, "u", ["rater1", "rater2"]), 4.0)
        pr2 = self._pr({"rater1": {"u": [1, 1]}, "rater2": {"u": [5]}})
        self.assertEqual(RA.ground_truth(pr2, "u", ["rater1", "rater2"]), 3.0)

    def test_ordinal_mean_not_majority_vote(self):
        # PROTOCOL.md §5.4 is explicit: a 2/2/4/4 split lands at 3.
        pr = self._pr({"rater1": {"u": [2]}, "rater2": {"u": [2]},
                       "rater3": {"u": [4]}, "rater4": {"u": [4]}})
        self.assertEqual(RA.ground_truth(pr, "u"), 3.0)

    def test_usable_count_counts_raters_not_ratings(self):
        pr = self._pr({"rater1": {"u": [4, 5]}, "rater2": {"u": [0]},
                       "rater3": {"u": [3]}, "rater4": {"u": [0]}})
        self.assertEqual(RA.usable_count(pr, "u"), 2)

    def test_first_presentation_only_ignores_the_second_sight(self):
        pr = self._pr({"rater1": {"u": [2, 5]}})
        self.assertEqual(RA.ground_truth_first_only(pr, "u", ["rater1"]), 2.0)

    def test_first_presentation_only_skips_an_unratable_first_sight(self):
        pr = self._pr({"rater1": {"u": [0, 5]}, "rater2": {"u": [4]}})
        self.assertEqual(RA.ground_truth_first_only(pr, "u", ["rater1", "rater2"]), 4.0)


class TestAnalysisHelpers(unittest.TestCase):
    def test_longest_run(self):
        self.assertEqual(RA.longest_run([1, 1, 2, 2, 2, 3]), 3)
        self.assertEqual(RA.longest_run([1, 2, 3]), 1)
        self.assertEqual(RA.longest_run([4] * 7), 7)

    def test_permutation_p_never_returns_zero(self):
        # add-one smoothing. A p of exactly 0 is not a thing 20,000 shuffles can
        # establish, and reporting one would be a stronger claim than the data.
        p = RA.permutation_p([[1.0] * 20, [9.0] * 20], n_perm=200)
        self.assertGreater(p, 0.0)

    def test_permutation_p_is_large_when_groups_are_exchangeable(self):
        rng = random.Random(4)
        g1 = [rng.gauss(0, 1) for _ in range(40)]
        g2 = [rng.gauss(0, 1) for _ in range(40)]
        self.assertGreater(RA.permutation_p([g1, g2], n_perm=2000), 0.05)

    def test_permutation_p_is_small_for_separated_groups(self):
        g1 = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        g2 = [9.0, 9.1, 9.2, 9.3, 9.4, 9.5]
        self.assertLess(RA.permutation_p([g1, g2], n_perm=2000), 0.01)

    def test_loo_ceiling_of_identical_raters_is_one(self):
        pr = {rn: {f"u{i}": [(0, (i % 5) + 1)] for i in range(20)}
              for rn in ("rater1", "rater2", "rater3", "rater4")}
        out = RA.loo_ceiling(pr, [f"u{i}" for i in range(20)])
        self.assertAlmostEqual(out["mean_rho"], 1.0, places=9)


class TestRealRatingFiles(unittest.TestCase):
    """Integrity of the four collected files. These are the assertions that stop
    a mislabelled or hand-edited export becoming a published number."""

    @classmethod
    def setUpClass(cls):
        cls.sample, cls.items, cls.dups, cls.pr = RA.load()

    def test_load_enforces_page_provenance(self):
        # RA.load() asserts each file's (pid, tok) sequence equals its own page's
        # payload. Reaching here means all four passed.
        self.assertEqual(len(self.pr), 4)

    def test_every_segment_seen_by_every_rater(self):
        for rn in RA.RATERS:
            self.assertEqual(len(self.pr[rn]), 120)

    def test_thirty_hidden_duplicates_per_rater(self):
        for rn in RA.RATERS:
            self.assertEqual(sum(1 for v in self.pr[rn].values() if len(v) == 2), 30)

    def test_ratings_are_on_the_declared_scale(self):
        for rn in RA.RATERS:
            for pres in self.pr[rn].values():
                for _, r in pres:
                    self.assertIn(r, RA.SCALE + [RA.UNRATABLE])

    def test_exactly_one_segment_falls_below_the_usable_floor(self):
        dropped = [u for u in self.items if RA.usable_count(self.pr, u) < RA.MIN_USABLE]
        self.assertEqual(dropped, ["Kk-RKpTAXmA_139"])

    def test_power_floor_is_met(self):
        keep = [u for u in self.items if RA.usable_count(self.pr, u) >= RA.MIN_USABLE]
        hol = [u for u in keep if self.items[u]["split"] == "holdout"]
        self.assertGreaterEqual(len(keep), RA.FLOOR_TOTAL)
        self.assertGreaterEqual(len(hol), RA.FLOOR_HOLDOUT)


class TestResultsFileMatchesRecomputation(unittest.TestCase):
    """The write-up quotes rater_analysis_results.json. This re-derives the
    headline entries from the raw files so a stale results file cannot silently
    keep publishing yesterday's numbers."""

    def test_headline_numbers_recompute(self):
        path = BB / "rater_analysis_results.json"
        if not path.exists():
            self.skipTest("run rater_analysis.py first")
        R = json.loads(path.read_text())
        sample, items, dups, pr = RA.load()
        keep = [u for u in sorted(items) if RA.usable_count(pr, u) >= RA.MIN_USABLE]
        self.assertEqual(R["ground_truth"]["n_kept"], len(keep))
        self.assertAlmostEqual(R["alpha"]["all"]["ordinal"]["alpha"],
                               RA.alpha_of(pr, keep, "ordinal")["alpha"], places=12)
        self.assertAlmostEqual(R["ceiling"]["all"]["mean_rho"],
                               RA.loo_ceiling(pr, keep)["mean_rho"], places=12)


if __name__ == "__main__":
    unittest.main()
