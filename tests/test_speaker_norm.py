"""
Unit tests for the per-speaker normalisation experiment (vocal_bench/speaker_norm.py).

The experiment's conclusion is negative - nothing was adopted - so what these tests
protect is not a production code path but the *evidence*: the arithmetic that
produced SPEAKER_NORM_RESULT.md, and the guards that stop the harness reporting a
result it did not actually earn.

Three things are covered, in order of how much damage they would do if wrong:

  1. The arithmetic. percentile, fractional_rank, eta_squared, Spearman and the
     threshold fit are all hand-written here (so the bench runs without scipy) and
     are exercised against cases whose answers can be worked out by hand. None of
     it is mocked: mock I/O, never the arithmetic under test.

  2. The guards. The anchor that must reproduce the published bench, the
     monotonicity invariant, and the filesystem interlock that stops the
     confirmation split being scored before a winner has been declared. Each is
     tested by making it fail, not only by watching it pass.

  3. The degradation paths. A degenerate group (zero spread), a group too small to
     estimate from, an absent group, and a missing arousal reading must each
     downgrade the rule rather than raise - the same contract the pipeline follows.

`tests/test_vocal_channel.py` covers the deployed channel itself. This file covers
only the experiment that decided not to change it.
"""

import json
import statistics
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parent.parent / "research" / "vocal_bench"
sys.path.insert(0, str(BENCH))

import speaker_norm as SN  # noqa: E402


# ─────────────────────────────────────────────────────────────────── fixtures

def _row(uid, video, speaker, arousal, rating=3, label="NEUTRAL"):
    return {"uid": uid, "video_id": video, "speaker": speaker, "arousal": arousal,
            "rating": rating, "label": label, "channel": speaker}


@pytest.fixture(scope="module")
def results():
    """The recorded outcome, read once. Skips rather than fails if the experiment
    has not been run in this checkout - a missing artefact is not a regression."""
    path = BENCH / "speaker_norm_results.json"
    if not path.is_file():
        pytest.skip("speaker_norm_results.json not present - run speaker_norm.py")
    return json.loads(path.read_text())


@pytest.fixture
def tiny_corpus():
    """Two videos, one speaker each, deliberately offset from one another.

    Video A sits low (0.30-0.50), video B sits high (0.60-0.80). A global cut
    cannot separate them; a within-video rule can. Ten segments each, above
    MIN_GROUP_SEGMENTS, so no fallback fires.
    """
    a = [_row(f"A_{i}", "A", "spk_a", 0.30 + i * 0.02) for i in range(10)]
    b = [_row(f"B_{i}", "B", "spk_b", 0.60 + i * 0.02) for i in range(10)]
    return a + b


# ───────────────────────────────────────────────────────────────── percentile

class TestPercentile:
    def test_endpoints(self):
        assert SN.percentile([1.0, 2.0, 3.0], 0.0) == 1.0
        assert SN.percentile([1.0, 2.0, 3.0], 1.0) == 3.0

    def test_median_of_odd_and_even_samples(self):
        assert SN.percentile([1.0, 2.0, 3.0], 0.5) == 2.0
        assert SN.percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5

    def test_linear_interpolation(self):
        # p=0.25 over 5 points lands exactly on index 1
        assert SN.percentile([0.0, 1.0, 2.0, 3.0, 4.0], 0.25) == 1.0
        # p=0.30 over 5 points lands 20% of the way from index 1 to index 2
        assert SN.percentile([0.0, 1.0, 2.0, 3.0, 4.0], 0.30) == pytest.approx(1.2)

    def test_single_value_sample(self):
        assert SN.percentile([7.5], 0.0) == 7.5
        assert SN.percentile([7.5], 0.9) == 7.5

    def test_empty_sample_raises_rather_than_returning_a_number(self):
        with pytest.raises(ValueError):
            SN.percentile([], 0.5)


# ────────────────────────────────────────────────────────────── fractional rank

class TestFractionalRank:
    def test_monotone_and_inside_the_unit_interval(self):
        vals = sorted([0.1, 0.2, 0.3, 0.4])
        ranks = [SN.fractional_rank(v, vals) for v in vals]
        assert ranks == sorted(ranks)
        assert all(0.0 < r < 1.0 for r in ranks)

    def test_ties_share_one_midpoint(self):
        vals = sorted([0.1, 0.5, 0.5, 0.5, 0.9])
        assert SN.fractional_rank(0.5, vals) == pytest.approx(0.5)

    def test_a_value_below_the_whole_group_ranks_at_zero(self):
        assert SN.fractional_rank(0.0, [0.1, 0.2, 0.3]) == 0.0

    def test_rank_is_order_preserving_so_it_cannot_invent_ordering(self):
        vals = sorted([0.05, 0.11, 0.12, 0.99])
        a, b = SN.fractional_rank(0.11, vals), SN.fractional_rank(0.12, vals)
        assert a < b


# ──────────────────────────────────────────────────────────────── group stats

class TestGroupStats:
    def test_known_sample(self):
        s = SN.group_stats([1.0, 2.0, 3.0, 4.0])
        assert s["n"] == 4
        assert s["mean"] == 2.5
        assert s["median"] == 2.5
        assert s["iqr"] == pytest.approx(1.5)   # q75 3.25 - q25 1.75
        assert s["sd"] == pytest.approx(statistics.pstdev([1.0, 2.0, 3.0, 4.0]))

    def test_constant_group_has_zero_spread(self):
        s = SN.group_stats([0.5] * 6)
        assert s["sd"] == 0.0
        assert s["iqr"] == 0.0

    def test_sorted_values_are_kept_for_ranking(self):
        assert SN.group_stats([3.0, 1.0, 2.0])["sorted"] == [1.0, 2.0, 3.0]


# ────────────────────────────────────────────────────────── transform contract

class TestTransformers:
    def test_global_rule_is_the_identity(self, tiny_corpus):
        t = SN.Transformer("global", tiny_corpus)
        for row in tiny_corpus:
            assert t(row) == row["arousal"]
        assert t.fallbacks == 0

    def test_centring_removes_the_video_offset(self, tiny_corpus):
        t = SN.Transformer("video_center", tiny_corpus)
        a = [t(r) for r in tiny_corpus if r["video_id"] == "A"]
        b = [t(r) for r in tiny_corpus if r["video_id"] == "B"]
        assert statistics.mean(a) == pytest.approx(0.0, abs=1e-12)
        assert statistics.mean(b) == pytest.approx(0.0, abs=1e-12)

    def test_zscore_gives_unit_spread_per_video(self, tiny_corpus):
        t = SN.Transformer("video_z", tiny_corpus)
        for vid in ("A", "B"):
            vals = [t(r) for r in tiny_corpus if r["video_id"] == vid]
            assert statistics.pstdev(vals) == pytest.approx(1.0)

    def test_every_rule_is_monotone_within_a_video(self, tiny_corpus):
        """The invariant the whole experiment rests on, checked rule by rule."""
        for rid in SN.RULES:
            t = SN.Transformer(rid, tiny_corpus)
            for vid in ("A", "B"):
                rows = [r for r in tiny_corpus if r["video_id"] == vid]
                rows.sort(key=lambda r: r["arousal"])
                vals = [t(r) for r in rows]
                assert vals == sorted(vals), f"{rid} is not monotone within {vid}"

    def test_speaker_rule_pools_a_speakers_videos(self):
        corpus = ([_row(f"A_{i}", "A", "same", 0.30 + i * 0.02) for i in range(10)]
                  + [_row(f"B_{i}", "B", "same", 0.60 + i * 0.02) for i in range(10)])
        by_video = SN.Transformer("video_z", corpus)
        by_speaker = SN.Transformer("speaker_z", corpus)
        row = corpus[0]
        # Same speaker across two offset videos, so the two groupings must differ.
        assert by_video(row) != pytest.approx(by_speaker(row))

    def test_grid_has_the_declared_number_of_points_for_every_rule(self, tiny_corpus):
        for rid in SN.RULES:
            grid = SN.Transformer(rid, tiny_corpus).grid(tiny_corpus)
            assert len(grid) == SN.GRID_POINTS
            assert grid == sorted(grid)


class TestDegradationPaths:
    """A statistic that cannot be estimated downgrades the rule; it never raises."""

    def test_missing_arousal_returns_none_not_a_guessed_value(self, tiny_corpus):
        t = SN.Transformer("video_z", tiny_corpus)
        assert t(_row("A_x", "A", "spk_a", None)) is None

    def test_constant_video_falls_back_to_the_raw_value(self):
        corpus = [_row(f"C_{i}", "C", "spk", 0.5) for i in range(10)]
        t = SN.Transformer("video_z", corpus)
        assert t(corpus[0]) == 0.5
        assert t.fallbacks == 1

    def test_zero_iqr_falls_back_to_the_raw_value(self):
        corpus = [_row(f"C_{i}", "C", "spk", 0.5) for i in range(10)]
        t = SN.Transformer("video_robust", corpus)
        assert t(corpus[0]) == 0.5
        assert t.fallbacks == 1

    def test_group_below_the_minimum_falls_back(self):
        corpus = [_row(f"D_{i}", "D", "spk", 0.3 + i * 0.05)
                  for i in range(SN.MIN_GROUP_SEGMENTS - 1)]
        t = SN.Transformer("video_z", corpus)
        assert t(corpus[0]) == corpus[0]["arousal"]
        assert t.fallbacks == 1

    def test_unseen_group_falls_back_rather_than_raising(self, tiny_corpus):
        t = SN.Transformer("video_z", tiny_corpus)
        assert t(_row("Z_0", "Z", "spk_z", 0.42)) == 0.42
        assert t.fallbacks == 1

    def test_segments_with_no_reading_are_excluded_from_group_statistics(self):
        corpus = ([_row(f"E_{i}", "E", "spk", 0.5) for i in range(9)]
                  + [_row("E_none", "E", "spk", None)])
        assert SN.build_stats(corpus, "video_id")["E"]["n"] == 9


# ───────────────────────────────────────────────────────────────── thresholds

class TestThresholds:
    def test_the_three_way_cut(self):
        assert SN.apply_thresholds(0.1, 0.4, 0.65) == "NEGATIVE"
        assert SN.apply_thresholds(0.5, 0.4, 0.65) == "NEUTRAL"
        assert SN.apply_thresholds(0.9, 0.4, 0.65) == "POSITIVE"

    def test_boundaries_are_closed_below(self):
        assert SN.apply_thresholds(0.4, 0.4, 0.65) == "NEUTRAL"
        assert SN.apply_thresholds(0.65, 0.4, 0.65) == "POSITIVE"

    def test_no_reading_yields_no_label_rather_than_neutral(self):
        assert SN.apply_thresholds(None, 0.4, 0.65) is None

    def test_fit_recovers_a_separable_boundary(self):
        rows = ([_row(f"n{i}", "V", "s", 0.1, 1, "NEGATIVE") for i in range(5)]
                + [_row(f"u{i}", "V", "s", 0.5, 3, "NEUTRAL") for i in range(5)]
                + [_row(f"p{i}", "V", "s", 0.9, 5, "POSITIVE") for i in range(5)])
        lo, hi, acc = SN.fit(rows, SN.Transformer("global", rows),
                             [round(x / 10, 2) for x in range(1, 10)])
        assert acc == 1.0
        assert lo <= 0.5 < hi

    def test_ties_break_toward_the_widest_neutral_band(self):
        """Matches report_bench.fit_thresholds: without this the winner would
        depend on iteration order, which is not a decision anyone made."""
        rows = [_row(f"u{i}", "V", "s", 0.5, 3, "NEUTRAL") for i in range(5)]
        grid = [0.1, 0.2, 0.8, 0.9]
        lo, hi, acc = SN.fit(rows, SN.Transformer("global", rows), grid)
        assert acc == 1.0
        assert (lo, hi) == (0.1, 0.9)

    def test_fit_raises_when_the_grid_admits_no_pair(self):
        rows = [_row("a", "V", "s", 0.5)]
        with pytest.raises(RuntimeError):
            SN.fit(rows, SN.Transformer("global", rows), [0.5])


# ──────────────────────────────────────────────────────────────── correlation

class TestSpearman:
    def test_perfect_agreement(self):
        assert SN.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)

    def test_perfect_inversion(self):
        assert SN.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)

    def test_monotone_transform_leaves_rho_unchanged(self):
        """The property the experiment's invariant depends on."""
        x = [0.30, 0.34, 0.41, 0.55, 0.62]
        y = [1, 2, 3, 4, 5]
        shifted = [(v - 0.4) / 0.07 for v in x]
        assert SN.spearman(x, y) == pytest.approx(SN.spearman(shifted, y))

    def test_a_constant_input_has_no_correlation_rather_than_a_zero_division(self):
        assert SN.spearman([1, 1, 1], [1, 2, 3]) == 0.0

    def test_ties_take_the_average_rank(self):
        # [1,1,2] -> ranks [1.5, 1.5, 3]; correlating with itself is still 1.0
        assert SN.spearman([1, 1, 2], [1, 1, 2]) == pytest.approx(1.0)


class TestWithinVideoRho:
    def test_identical_across_every_rule(self, tiny_corpus):
        rows = []
        for i, r in enumerate(tiny_corpus):
            rows.append({**r, "rating": (i % 5) + 1})
        values = {rid: SN.within_video_rho(rows, SN.Transformer(rid, tiny_corpus))
                  for rid in SN.RULES}
        per_video = [v["per_video"] for v in values.values()]
        assert all(p == per_video[0] for p in per_video)

    def test_a_video_with_too_few_clips_is_skipped_not_scored(self, tiny_corpus):
        rows = [{**tiny_corpus[0], "rating": 3}, {**tiny_corpus[1], "rating": 4}]
        assert SN.within_video_rho(rows, SN.Transformer("global", tiny_corpus)) == {
            "per_video": {}, "mean": None}


# ───────────────────────────────────────────────────── variance decomposition

class TestEtaSquared:
    def test_all_variance_between_groups(self):
        assert SN.eta_squared([1.0, 1.0, 5.0, 5.0], ["a", "a", "b", "b"]) == 1.0

    def test_no_variance_between_groups(self):
        assert SN.eta_squared([1.0, 5.0, 1.0, 5.0], ["a", "a", "b", "b"]) == 0.0

    def test_a_known_intermediate_case(self):
        # groups [0,2] and [4,6]: means 1 and 5, grand mean 3.
        # SS_between = 2*(1-3)^2 + 2*(5-3)^2 = 16; SS_total = 9+1+1+9 = 20.
        assert SN.eta_squared([0.0, 2.0, 4.0, 6.0],
                              ["a", "a", "b", "b"]) == pytest.approx(0.8)

    def test_a_constant_variable_has_no_variance_to_apportion(self):
        assert SN.eta_squared([3.0, 3.0, 3.0], ["a", "b", "c"]) == 0.0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            SN.eta_squared([1.0, 2.0], ["a"])

    def test_a_single_observation_raises_rather_than_returning_zero(self):
        with pytest.raises(ValueError):
            SN.eta_squared([1.0], ["a"])


# ───────────────────────────────────────────────────────────────────── guards

class TestGuards:
    """Each guard is tested by making it fail, not only by watching it pass."""

    def test_anchor_aborts_when_the_cache_no_longer_reproduces_the_bench(
            self, tiny_corpus):
        rows = [_row(f"A_{i}", "A", "spk_a", 0.30 + i * 0.02, 3, "NEUTRAL")
                for i in range(10)]
        with pytest.raises(RuntimeError, match="anchor failed"):
            SN.anchor_check(tiny_corpus, rows, rows)

    def test_anchor_message_names_both_numbers(self, tiny_corpus):
        rows = [_row(f"A_{i}", "A", "spk_a", 0.30 + i * 0.02, 3, "NEUTRAL")
                for i in range(10)]
        with pytest.raises(RuntimeError) as e:
            SN.anchor_check(tiny_corpus, rows, rows)
        assert "published" in str(e.value) and "vs" in str(e.value)

    def test_the_published_constants_are_the_ones_the_pipeline_deploys(self):
        from pipeline import audio_module
        assert SN.PUBLISHED_THRESHOLDS == (audio_module.AROUSAL_LOW,
                                           audio_module.AROUSAL_HIGH)

    def test_confirm_phase_refuses_to_run_without_a_declared_winner(
            self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(SN, "SELECTION_OUT", tmp_path / "absent.json")
        monkeypatch.setattr(sys, "argv", ["speaker_norm.py", "--phase", "confirm"])
        assert SN.main() == 2
        assert "refusing to score the holdout" in capsys.readouterr().err

    def test_only_deployable_rules_can_be_declared_the_winner(self):
        assert SN.RULES["speaker_z"][2] is False
        assert all(SN.RULES[r][2] for r in
                   ("global", "video_center", "video_z", "video_robust", "video_rank"))

    def test_the_deployed_rule_is_named_and_is_a_real_rule(self):
        assert SN.DEPLOYED_RULE in SN.RULES


# ──────────────────────────────────────────────────────── the recorded result

class TestRecordedResult:
    """The findings the write-up rests on, read back from the results file.

    These are frozen deliberately. If a later change to the harness silently moves
    them, the suite says so rather than the document quietly becoming false.
    """

    def test_nothing_was_adopted(self, results):
        assert results["adopt"]["decision"] == "DO NOT ADOPT"
        assert results["adopt"]["significant_at_0.05"] is False

    def test_the_declared_winner_was_the_incumbent_rule(self, results):
        assert results["declared"]["declared_winner"] == "global"

    def test_the_winner_was_declared_before_the_holdout_was_scored(self, results):
        """The selection file carries no per-rule holdout score, so the winner it
        names cannot have been chosen with knowledge of the holdout.

        One confirmation figure IS present, in `anchor`: the 23/47 the published
        bench already reported for the deployed thresholds. That is a previously
        spent holdout use being reproduced as a consistency check, not new
        information, and it is the same for every rule - so it cannot separate
        them. Asserted explicitly rather than glossed.
        """
        assert (BENCH / "speaker_norm_selection.json").is_file()
        declared = json.loads((BENCH / "speaker_norm_selection.json").read_text())
        assert declared["declared_winner"] == results["declared"]["declared_winner"]
        assert set(declared) & {"confirmation", "vs_deployed_mcnemar", "adopt"} == set()
        assert set(declared["selection"]) == set(SN.RULES)
        assert declared["anchor"]["confirmation"] == "23/47"

    def test_the_declared_winner_is_a_function_of_the_selection_scores_alone(
            self, results):
        declared = results["declared"]
        deployable = {r: declared["selection"][r]["accuracy"]
                      for r in SN.RULES if SN.RULES[r][2]}
        assert declared["declared_winner"] == max(deployable, key=deployable.get)

    def test_the_anchor_reproduced_the_published_bench(self, results):
        a = results["declared"]["anchor"]
        assert a["passed"] is True
        assert a["selection"] == "60/100"
        assert a["confirmation"] == "23/47"

    def test_the_monotonicity_invariant_held(self, results):
        assert results["monotonicity_invariant"] == "held"

    def test_every_normalisation_lost_on_the_held_out_split(self, results):
        deployed = results["deployed_baseline"]["accuracy"]
        for rid, res in results["confirmation"].items():
            if rid == "global":
                continue
            assert res["accuracy"] < deployed, rid

    def test_no_rule_beat_the_majority_class(self, results):
        oracle = results["oracle_majority_baseline"]["accuracy"]
        assert all(r["accuracy"] < oracle for r in results["confirmation"].values())

    def test_the_signal_is_mostly_between_videos_not_within(self, results):
        d = results["diagnostics"]["pooled"]
        assert d["within_video_rho_mean"] < d["pooled_rho"] / 2
        assert d["video_level_rho_arousal_vs_rating"] > 0.75

    def test_arousal_is_more_video_determined_than_the_human_rating(self, results):
        d = results["diagnostics"]["pooled"]
        assert d["eta2_arousal_by_video"] > 2 * d["eta2_rating_by_video"]

    def test_the_fallback_path_never_fired_on_this_corpus(self, results):
        assert sum(results["declared"]["fallbacks"].values()) == 0

    def test_the_report_caveat_quotes_this_experiments_measured_figures(self, results):
        """Every number in a user-facing caveat must be traceable to a file that
        produced it. These two come from here, so they are checked from here."""
        from pipeline import scorer

        pooled = results["diagnostics"]["pooled"]["within_video_rho_mean"]
        holdout = results["diagnostics"]["confirmation"]["within_video_rho_mean"]
        assert f"+{pooled:.3f}" in scorer.VOCAL_CAVEAT
        assert f"+{holdout:.3f}" in scorer.VOCAL_CAVEAT
        assert "SPEAKER_NORM_RESULT.md" in scorer.VOCAL_CAVEAT
