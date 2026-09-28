"""
Unit tests for transcript_bench/metrics.py.

The bench's headline numbers come out of these functions, so they are verified
against values computed independently rather than against the implementation's
own output (never mock the arithmetic being verified).
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research" / "transcript_bench"))

import metrics  # noqa: E402


class TestAccuracy:
    def test_all_correct(self):
        assert metrics.accuracy(["POSITIVE"] * 3, ["POSITIVE"] * 3) == 1.0

    def test_none_correct(self):
        assert metrics.accuracy(["POSITIVE"] * 3, ["NEGATIVE"] * 3) == 0.0

    def test_half_correct(self):
        assert metrics.accuracy(
            ["POSITIVE", "NEGATIVE"], ["POSITIVE", "POSITIVE"]
        ) == 0.5

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            metrics.accuracy(["POSITIVE"], ["POSITIVE", "NEGATIVE"])

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            metrics.accuracy([], [])


class TestWilsonInterval:
    def test_known_value_half_of_hundred(self):
        # Independently known Wilson 95% interval for 50/100.
        lo, hi = metrics.wilson_interval(50, 100)
        assert lo == pytest.approx(0.3983, abs=0.01)
        assert hi == pytest.approx(0.6017, abs=0.01)

    def test_symmetric_about_half(self):
        lo, hi = metrics.wilson_interval(50, 100)
        assert (lo + hi) / 2 == pytest.approx(0.5, abs=1e-9)

    def test_zero_successes_stays_in_bounds(self):
        # The normal approximation goes negative here; Wilson must not.
        lo, hi = metrics.wilson_interval(0, 100)
        assert lo == 0.0
        assert 0.0 < hi < 0.05

    def test_all_successes_stays_in_bounds(self):
        # The exact upper bound here is 1.0; in floating point it lands one ulp
        # below, so this asserts the bound is not exceeded rather than exact
        # equality.
        lo, hi = metrics.wilson_interval(100, 100)
        assert hi == pytest.approx(1.0)
        assert hi <= 1.0
        assert 0.95 < lo < 1.0

    def test_narrows_as_n_grows(self):
        lo_s, hi_s = metrics.wilson_interval(5, 10)
        lo_l, hi_l = metrics.wilson_interval(500, 1000)
        assert (hi_l - lo_l) < (hi_s - lo_s)

    def test_invalid_n_raises(self):
        with pytest.raises(ValueError):
            metrics.wilson_interval(0, 0)

    def test_successes_out_of_range_raises(self):
        with pytest.raises(ValueError):
            metrics.wilson_interval(11, 10)


class TestConfusionMatrix:
    def test_counts_land_in_right_cells(self):
        gold = ["POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE"]
        pred = ["POSITIVE", "NEUTRAL", "NEUTRAL", "POSITIVE"]
        m = metrics.confusion_matrix(gold, pred)
        assert m["POSITIVE"]["POSITIVE"] == 1
        assert m["POSITIVE"]["NEUTRAL"] == 1
        assert m["NEUTRAL"]["NEUTRAL"] == 1
        assert m["NEGATIVE"]["POSITIVE"] == 1
        assert m["NEGATIVE"]["NEGATIVE"] == 0

    def test_total_equals_sample_size(self):
        gold = ["POSITIVE", "NEUTRAL", "NEGATIVE"] * 7
        pred = ["NEUTRAL", "NEUTRAL", "POSITIVE"] * 7
        m = metrics.confusion_matrix(gold, pred)
        assert sum(sum(r.values()) for r in m.values()) == 21

    def test_unknown_label_raises(self):
        with pytest.raises(ValueError, match="unknown"):
            metrics.confusion_matrix(["MYSTERY"], ["POSITIVE"])


class TestPerClassPRF:
    def test_precision_recall_hand_computed(self):
        # NEUTRAL: gold 3, predicted 2, correct 1 -> P=1/2, R=1/3, F1=0.4
        gold = ["NEUTRAL", "NEUTRAL", "NEUTRAL", "POSITIVE"]
        pred = ["NEUTRAL", "POSITIVE", "POSITIVE", "NEUTRAL"]
        prf = metrics.per_class_prf(gold, pred)["NEUTRAL"]
        assert prf["precision"] == pytest.approx(0.5)
        assert prf["recall"] == pytest.approx(1 / 3)
        assert prf["f1"] == pytest.approx(0.4)
        assert prf["support"] == 3
        assert prf["predicted"] == 2

    def test_class_never_predicted_scores_zero_not_error(self):
        # This is the incumbent's expected behaviour on NEUTRAL - it must score.
        gold = ["NEUTRAL", "POSITIVE", "NEGATIVE"]
        pred = ["POSITIVE", "POSITIVE", "NEGATIVE"]
        prf = metrics.per_class_prf(gold, pred)["NEUTRAL"]
        assert prf["precision"] == 0.0
        assert prf["recall"] == 0.0
        assert prf["f1"] == 0.0
        assert prf["support"] == 1
        assert prf["predicted"] == 0

    def test_perfect_prediction_all_ones(self):
        gold = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        prf = metrics.per_class_prf(gold, list(gold))
        for lab in metrics.LABELS:
            assert prf[lab]["f1"] == pytest.approx(1.0)


class TestMacroF1:
    def test_perfect_is_one(self):
        gold = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        assert metrics.macro_f1(gold, list(gold)) == pytest.approx(1.0)

    def test_majority_class_predictor_is_penalised(self):
        # 6 POSITIVE, 2 NEUTRAL, 2 NEGATIVE; always guess POSITIVE.
        gold = ["POSITIVE"] * 6 + ["NEUTRAL"] * 2 + ["NEGATIVE"] * 2
        pred = ["POSITIVE"] * 10
        assert metrics.accuracy(gold, pred) == pytest.approx(0.6)
        # Only POSITIVE has non-zero F1 (2*0.6*1/1.6 = 0.75), so macro is 0.25.
        assert metrics.macro_f1(gold, pred) == pytest.approx(0.75 / 3)


class TestMcnemarExact:
    def test_no_discordant_pairs_is_p_one(self):
        gold = ["POSITIVE", "NEUTRAL"]
        r = metrics.mcnemar_exact(gold, list(gold), list(gold))
        assert r["n_discordant"] == 0
        assert r["p_value"] == 1.0

    def test_b_and_c_counted_correctly(self):
        gold = ["POSITIVE", "POSITIVE", "POSITIVE"]
        pred_a = ["POSITIVE", "NEGATIVE", "POSITIVE"]   # right, wrong, right
        pred_b = ["NEGATIVE", "POSITIVE", "POSITIVE"]   # wrong, right, right
        r = metrics.mcnemar_exact(gold, pred_a, pred_b)
        assert r["b"] == 1   # A right, B wrong
        assert r["c"] == 1   # A wrong, B right
        assert r["n_discordant"] == 2

    def test_ten_nil_split_matches_hand_computation(self):
        # b=10, c=0 -> two-sided exact p = 2 * (1/2)^10
        gold = ["POSITIVE"] * 10
        pred_a = ["POSITIVE"] * 10
        pred_b = ["NEGATIVE"] * 10
        r = metrics.mcnemar_exact(gold, pred_a, pred_b)
        assert r["b"] == 10 and r["c"] == 0
        assert r["p_value"] == pytest.approx(2 * (0.5 ** 10))

    def test_five_one_split_matches_hand_computation(self):
        # b=5, c=1, n=6: 2 * (C(6,0)+C(6,1)) / 2^6 = 2 * 7/64 = 0.21875
        gold = ["POSITIVE"] * 6
        pred_a = ["POSITIVE"] * 5 + ["NEGATIVE"]
        pred_b = ["NEGATIVE"] * 5 + ["POSITIVE"]
        r = metrics.mcnemar_exact(gold, pred_a, pred_b)
        assert r["b"] == 5 and r["c"] == 1
        assert r["p_value"] == pytest.approx(0.21875)

    def test_symmetric_in_its_arguments(self):
        gold = ["POSITIVE"] * 8
        a = ["POSITIVE"] * 6 + ["NEGATIVE"] * 2
        b = ["POSITIVE"] * 3 + ["NEGATIVE"] * 5
        assert metrics.mcnemar_exact(gold, a, b)["p_value"] == pytest.approx(
            metrics.mcnemar_exact(gold, b, a)["p_value"]
        )

    def test_min_attainable_p_reported(self):
        # With 4 discordant pairs the best possible two-sided p is 0.125,
        # so significance at 0.05 is unreachable however lopsided the split.
        gold = ["POSITIVE"] * 4
        r = metrics.mcnemar_exact(gold, ["POSITIVE"] * 4, ["NEGATIVE"] * 4)
        assert r["min_attainable_p"] == pytest.approx(0.125)
        assert r["p_value"] >= 0.05

    def test_p_value_never_exceeds_one(self):
        gold = ["POSITIVE"] * 4
        a = ["POSITIVE", "NEGATIVE", "POSITIVE", "NEGATIVE"]
        b = ["NEGATIVE", "POSITIVE", "NEGATIVE", "POSITIVE"]
        assert metrics.mcnemar_exact(gold, a, b)["p_value"] == 1.0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            metrics.mcnemar_exact(["POSITIVE"], ["POSITIVE"], ["POSITIVE", "NEUTRAL"])


class TestSummarise:
    def test_block_has_every_reported_field(self):
        gold = ["POSITIVE", "NEUTRAL", "NEGATIVE", "NEUTRAL"]
        pred = ["POSITIVE", "NEUTRAL", "NEGATIVE", "POSITIVE"]
        s = metrics.summarise(gold, pred)
        for key in (
            "n", "accuracy", "accuracy_ci95", "macro_f1",
            "neutral_recall", "neutral_predicted", "per_class", "confusion",
        ):
            assert key in s, f"missing {key}"

    def test_neutral_recall_matches_per_class(self):
        gold = ["NEUTRAL"] * 4 + ["POSITIVE"]
        pred = ["NEUTRAL", "NEUTRAL", "POSITIVE", "POSITIVE", "POSITIVE"]
        s = metrics.summarise(gold, pred)
        assert s["neutral_recall"] == pytest.approx(0.5)
        assert s["neutral_recall"] == s["per_class"]["NEUTRAL"]["recall"]

    def test_accuracy_inside_its_own_interval(self):
        gold = ["POSITIVE", "NEUTRAL", "NEGATIVE"] * 10
        pred = ["POSITIVE", "NEUTRAL", "POSITIVE"] * 10
        s = metrics.summarise(gold, pred)
        lo, hi = s["accuracy_ci95"]
        assert lo <= s["accuracy"] <= hi
