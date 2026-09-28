"""
Unit tests for vocal_bench ground-truth loading, label mapping and scoring logic.

The arithmetic that produces the headline numbers lives in
transcript_bench/metrics.py and is covered by tests/test_transcript_metrics.py.
What is tested here is everything vocal_bench adds on top: the 5->3 collapse, the
refusal to coerce unmappable labels, threshold fitting and freezing, and the
Spearman implementation (which is hand-written and whose tie handling materially
changes the answer on this data).
"""

import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parent.parent / "research" / "vocal_bench"
sys.path.insert(0, str(BENCH))

import ground_truth as GT  # noqa: E402
import report_bench as RB  # noqa: E402


class TestRatingCollapse:
    def test_the_preregistered_mapping(self):
        assert GT.RATING_TO_CLASS == {
            1: "NEGATIVE", 2: "NEGATIVE", 3: "NEUTRAL", 4: "POSITIVE", 5: "POSITIVE"
        }

    def test_cant_tell_is_zero_and_has_no_class(self):
        assert GT.CANT_TELL == 0
        assert 0 not in GT.RATING_TO_CLASS


class TestGroundTruthValidation:
    def _setup(self, tmp_path, monkeypatch, ratings, clips):
        r = tmp_path / "r.json"
        r.write_text(json.dumps({"ratings": ratings}))
        i = tmp_path / "i.json"
        i.write_text(json.dumps({"clips": clips}))
        monkeypatch.setattr(GT, "RATINGS", r)
        monkeypatch.setattr(GT, "INDEX", i)

    def _clip(self, uid, split="selection"):
        return {"uid": uid, "video_id": "v", "channel": "C", "split": split,
                "duration": 4.0, "order": 0}

    def test_missing_file_points_at_the_rating_page(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GT, "RATINGS", tmp_path / "nope.json")
        with pytest.raises(GT.GroundTruthError, match="rate_here.html"):
            GT.load("selection")

    def test_rejects_an_incomplete_rating_set(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 3},
                    [self._clip("a"), self._clip("b")])
        with pytest.raises(GT.GroundTruthError, match="never rated"):
            GT.load("selection")

    def test_rejects_ratings_for_unknown_clips(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 3, "ghost": 4}, [self._clip("a")])
        with pytest.raises(GT.GroundTruthError, match="unknown clip"):
            GT.load("selection")

    def test_rejects_out_of_range_ratings(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 9}, [self._clip("a")])
        with pytest.raises(GT.GroundTruthError, match="outside 0-5"):
            GT.load("selection")

    def test_rejects_an_unknown_split_name(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 3}, [self._clip("a")])
        with pytest.raises(ValueError, match="split must be"):
            GT.load("test")

    def test_cant_tell_is_excluded_by_default_and_included_on_request(
            self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 3, "b": 0},
                    [self._clip("a"), self._clip("b")])
        assert len(GT.load("selection")) == 1
        both = GT.load("selection", include_cant_tell=True)
        assert len(both) == 2
        assert [r["label"] for r in both if r["rating"] == 0] == [None]

    def test_raw_rating_survives_the_collapse(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 5}, [self._clip("a")])
        row = GT.load("selection")[0]
        assert row["rating"] == 5 and row["label"] == "POSITIVE"

    def test_splits_do_not_leak_into_each_other(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, {"a": 3, "b": 4},
                    [self._clip("a", "selection"), self._clip("b", "confirmation")])
        assert [r["uid"] for r in GT.load("selection")] == ["a"]
        assert [r["uid"] for r in GT.load("confirmation")] == ["b"]


class TestLabelMapping:
    @pytest.mark.parametrize("raw,expected", [
        ("angry", "NEGATIVE"), ("sad", "NEGATIVE"), ("disgusted", "NEGATIVE"),
        ("fearful", "NEGATIVE"), ("neutral", "NEUTRAL"), ("calm", "NEUTRAL"),
        ("happy", "POSITIVE"), ("surprised", "POSITIVE"),
    ])
    def test_maps_the_preregistered_labels(self, raw, expected):
        assert RB.map_label(raw) == expected

    def test_is_case_and_whitespace_insensitive(self):
        assert RB.map_label("  Angry  ") == "NEGATIVE"

    @pytest.mark.parametrize("raw", ["other", "unknown", "<unk>", None])
    def test_refuses_to_coerce_unmappable_labels(self, raw):
        # The whole point: these must NOT become NEUTRAL. That silent coercion is
        # the defect transcript_bench found in the deployed transcript channel.
        assert RB.map_label(raw) is None

    def test_an_unrecognised_label_is_unmapped_not_guessed(self):
        assert RB.map_label("ecstatic") is None

    def test_surprise_sensitivity_switch(self):
        assert RB.map_label("surprised") == "POSITIVE"
        assert RB.map_label("surprised", surprise_neutral=True) == "NEUTRAL"
        # the switch must not disturb anything else
        assert RB.map_label("angry", surprise_neutral=True) == "NEGATIVE"


class TestThresholds:
    def test_bands_are_half_open_and_ordered(self):
        assert RB.apply_thresholds(0.1, 0.3, 0.7) == "NEGATIVE"
        assert RB.apply_thresholds(0.3, 0.3, 0.7) == "NEUTRAL"   # lower edge inclusive
        assert RB.apply_thresholds(0.5, 0.3, 0.7) == "NEUTRAL"
        assert RB.apply_thresholds(0.7, 0.3, 0.7) == "POSITIVE"  # upper edge inclusive
        assert RB.apply_thresholds(0.9, 0.3, 0.7) == "POSITIVE"

    def test_missing_valence_is_unmapped_not_neutral(self):
        assert RB.apply_thresholds(None, 0.3, 0.7) is None

    def test_fit_recovers_thresholds_that_perfectly_separate(self):
        rows = [{"uid": "a", "label": "NEGATIVE"}, {"uid": "b", "label": "NEUTRAL"},
                {"uid": "c", "label": "POSITIVE"}]
        preds = {"a": {"valence": 0.1}, "b": {"valence": 0.5}, "c": {"valence": 0.9}}
        lo, hi, acc = RB.fit_thresholds(rows, preds)
        assert acc == 1.0
        assert lo <= 0.5 < hi

    def test_ties_break_toward_the_widest_neutral_band(self):
        # Every clip is neutral, so any band containing 0.5 scores 1.0. The
        # tie-break must make this deterministic rather than dict-order dependent.
        rows = [{"uid": str(i), "label": "NEUTRAL"} for i in range(5)]
        preds = {str(i): {"valence": 0.5} for i in range(5)}
        lo, hi, acc = RB.fit_thresholds(rows, preds)
        assert acc == 1.0
        assert (lo, hi) == (RB.GRID[0], RB.GRID[-1])

    def test_grid_is_the_declared_one(self):
        assert RB.GRID[0] == 0.05 and RB.GRID[-1] == 0.95
        assert all(round(b - a, 2) == 0.05 for a, b in zip(RB.GRID, RB.GRID[1:]))


class TestSpearman:
    def test_perfect_agreement(self):
        assert RB.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)

    def test_perfect_inversion(self):
        assert RB.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)

    def test_is_monotonic_not_linear(self):
        # Spearman must see a monotone but very non-linear relation as perfect.
        assert RB.spearman([1, 2, 3, 4], [1, 10, 1000, 100000]) == pytest.approx(1.0)

    def test_all_ties_on_one_side_gives_zero_not_a_crash(self):
        assert RB.spearman([1, 1, 1, 1], [1, 2, 3, 4]) == 0.0

    def test_average_ranks_are_used_for_ties(self):
        # b has a tied pair; with average ranks rho is high but not 1.0. Naive
        # ordinal ranking would wrongly return exactly 1.0 here.
        rho = RB.spearman([1, 2, 3, 4], [1, 2, 2, 4])
        assert 0.9 < rho < 1.0


class TestBaselines:
    def test_always_neutral_predicts_only_neutral(self):
        rows = [{"label": "POSITIVE"}] * 4
        assert RB.baseline_predictions(rows, "always-neutral") == ["NEUTRAL"] * 4

    def test_majority_uses_the_fitted_class(self):
        rows = [{"label": "POSITIVE"}] * 3
        assert RB.baseline_predictions(rows, "majority", "NEGATIVE") == ["NEGATIVE"] * 3

    def test_unknown_baseline_is_rejected(self):
        with pytest.raises(ValueError):
            RB.baseline_predictions([], "wishful-thinking")


class TestScoringTreatsUnmappedAsError:
    def _run(self, labels):
        return {
            "kind": "categorical", "licence": "x", "incumbent": False,
            "realtime_factor": 1.0, "n_failed": 0,
            "predictions": {f"c{i}": {"raw_label": l} for i, l in enumerate(labels)},
        }

    def _rows(self, golds):
        return [{"uid": f"c{i}", "label": g, "rating": 3, "channel": "C"}
                for i, g in enumerate(golds)]

    def test_unmapped_lowers_accuracy_rather_than_being_skipped(self):
        run = self._run(["happy", "<unk>", "<unk>"])
        s = RB.score_candidate("m", run, self._rows(["POSITIVE"] * 3),
                               surprise_neutral=False, thresholds=None)
        assert s["unmapped"] == 2
        assert s["accuracy"] == pytest.approx(1 / 3)   # not 1.0 over 1 usable clip
        assert s["n"] == 3

    def test_coverage_accuracy_separates_declining_from_being_wrong(self):
        run = self._run(["happy", "<unk>", "<unk>"])
        s = RB.score_candidate("m", run, self._rows(["POSITIVE"] * 3),
                               surprise_neutral=False, thresholds=None)
        assert s["coverage"] == pytest.approx(1 / 3)
        assert s["coverage_accuracy"] == 1.0   # right on everything it answered

    def test_unmapped_never_counts_as_a_neutral_hit(self):
        run = self._run(["<unk>"])
        s = RB.score_candidate("m", run, self._rows(["NEUTRAL"]),
                               surprise_neutral=False, thresholds=None)
        assert s["accuracy"] == 0.0


class TestSystematicSample:
    """corpus_ab.systematic_sample - how the A/B picks segments when it caps them.

    Truncating to the first n would bias the experiment: a video's opening
    segments are its intro and hook, systematically shorter and more energetic
    than its body, and arousal is exactly the quantity under test.
    """

    @staticmethod
    def _fn():
        import corpus_ab
        return corpus_ab.systematic_sample

    @staticmethod
    def _rows(n):
        return [{"segment_id": i} for i in range(n)]

    def test_no_cap_returns_everything_unchanged(self):
        rows = self._rows(50)
        assert self._fn()(rows, None) is rows

    def test_a_cap_larger_than_the_input_returns_everything(self):
        rows = self._rows(10)
        assert self._fn()(rows, 40) is rows

    def test_it_returns_exactly_the_requested_count(self):
        assert len(self._fn()(self._rows(164), 40)) == 40

    def test_it_spans_the_whole_video_not_just_the_opening(self):
        # The defect this function exists to avoid: rows[:40] would stop at 39.
        picked = [r["segment_id"] for r in self._fn()(self._rows(164), 40)]
        assert picked[0] == 0
        assert picked[-1] > 150

    def test_it_never_repeats_a_segment(self):
        picked = [r["segment_id"] for r in self._fn()(self._rows(164), 40)]
        assert len(set(picked)) == len(picked)

    def test_it_preserves_order(self):
        picked = [r["segment_id"] for r in self._fn()(self._rows(271), 40)]
        assert picked == sorted(picked)

    def test_it_is_deterministic_across_calls(self):
        a = self._fn()(self._rows(190), 40)
        b = self._fn()(self._rows(190), 40)
        assert [r["segment_id"] for r in a] == [r["segment_id"] for r in b]

    def test_the_gap_between_picks_stays_even(self):
        picked = [r["segment_id"] for r in self._fn()(self._rows(200), 40)]
        gaps = {b - a for a, b in zip(picked, picked[1:])}
        # Integer flooring allows adjacent step sizes, never a large jump.
        assert max(gaps) - min(gaps) <= 1

    def test_a_short_video_is_not_over_sampled(self):
        # haWvrSliMVY has 39 segments, fewer than the 40 cap.
        rows = self._rows(39)
        assert len(self._fn()(rows, 40)) == 39
