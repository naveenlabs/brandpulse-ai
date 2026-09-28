"""
Unit tests for whisper_bench/report_whisper.py.

The decision rule in this module chooses which Whisper checkpoint the pipeline
ships. It is verified here against synthetic scores with known answers, BEFORE
any real ground truth exists, so the rule cannot be quietly bent once results
are visible.

Ground truth loading is tested for its failure paths specifically: a partial
transcript set scored silently would change the sample without changing the
reported n.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research" / "whisper_bench"))

import report_whisper as R  # noqa: E402


CLIP_IDS = [f"clip{i}" for i in range(12)]


def _score(model, wer_value, realtime, *, per_clip_errors=None, ref_per_clip=100):
    """Synthetic score dict with a chosen corpus WER, shaped like score_model()."""
    if per_clip_errors is None:
        per_clip_errors = [round(wer_value * ref_per_clip)] * len(CLIP_IDS)
    per_clip = {
        cid: {"errors": e, "ref_words": ref_per_clip}
        for cid, e in zip(CLIP_IDS, per_clip_errors)
    }
    total_err = sum(per_clip_errors)
    total_ref = ref_per_clip * len(CLIP_IDS)
    return {
        "model": model,
        "wer": total_err / total_ref,
        "realtime_factor": realtime,
        "per_clip": per_clip,
    }


class TestPairedBootstrap:
    def test_identical_models_show_no_difference(self):
        a = _score("a", 0.10, 10.0)
        b = _score("b", 0.10, 5.0)
        t = R.paired_bootstrap(a, b, CLIP_IDS)
        assert t["observed_diff"] == pytest.approx(0.0)
        assert not t["significant"]

    def test_large_consistent_gap_is_detected(self):
        # 30% WER against 5%, same direction on every clip.
        a = _score("bad", 0.30, 30.0)
        b = _score("good", 0.05, 1.0)
        t = R.paired_bootstrap(a, b, CLIP_IDS)
        assert t["observed_diff"] > 0
        assert t["significant"]
        assert t["ci_low"] > 0  # interval excludes zero on the positive side

    def test_tiny_gap_with_mixed_direction_is_not_detected_at_n_12(self):
        # a wins on 7 clips, b wins on 5, and the pooled gap is under a point.
        # This is what a genuine near-tie looks like on real data.
        a = _score("a", 0.0, 10.0, per_clip_errors=[8, 14, 9, 13, 8, 14, 9, 13, 10, 12, 11, 11])
        b = _score("b", 0.0, 5.0, per_clip_errors=[13, 9, 12, 8, 13, 9, 12, 8, 11, 11, 10, 12])
        t = R.paired_bootstrap(a, b, CLIP_IDS)
        assert abs(t["observed_diff"]) < 0.02
        assert not t["significant"]
        assert t["clips_a_better"] and t["clips_b_better"]  # genuinely mixed

    def test_a_uniform_small_gap_is_detected_because_it_is_uniform(self):
        # Pins the property found on 31 Aug 2026: when b is better on every
        # clip, no resample can favour a, so even a 1-word-per-clip gap reads as
        # detectable. The bootstrap has degenerated into a sign test at 12/12.
        # This is correct behaviour, not a bug, and the win counts expose it.
        a = _score("a", 0.0, 10.0, per_clip_errors=[10] * 12)
        b = _score("b", 0.0, 5.0, per_clip_errors=[9] * 12)
        t = R.paired_bootstrap(a, b, CLIP_IDS)
        assert t["significant"]
        assert (t["clips_a_better"], t["clips_b_better"]) == (0, 12)
        assert t["observed_diff"] == pytest.approx(0.01)

    def test_inconsistent_direction_is_not_detected(self):
        # Same corpus WER reached by opposite per-clip behaviour.
        a = _score("a", 0.0, 10.0, per_clip_errors=[30, 0] * 6)
        b = _score("b", 0.0, 5.0, per_clip_errors=[0, 30] * 6)
        t = R.paired_bootstrap(a, b, CLIP_IDS)
        assert not t["significant"]

    def test_is_deterministic_under_the_fixed_seed(self):
        a, b = _score("a", 0.20, 9.0), _score("b", 0.10, 3.0)
        first = R.paired_bootstrap(a, b, CLIP_IDS)
        second = R.paired_bootstrap(a, b, CLIP_IDS)
        assert first == second

    def test_reports_its_settings(self):
        t = R.paired_bootstrap(_score("a", 0.1, 1.0), _score("b", 0.1, 1.0), CLIP_IDS)
        assert t["resamples"] == 10_000
        assert t["seed"] == 42


class TestDecisionRule:
    def test_prefers_the_faster_model_when_the_gap_is_undetectable(self):
        # Marginally better pooled WER, but the two trade wins clip to clip.
        scores = [
            _score("slow_accurate", 0.0, 1.0,
                   per_clip_errors=[8, 14, 9, 13, 8, 14, 9, 13, 10, 12, 11, 11]),
            _score("fast_similar", 0.0, 30.0,
                   per_clip_errors=[14, 10, 13, 9, 14, 10, 13, 9, 12, 11, 10, 12]),
        ]
        # 132 errors against 137 out of 1200 words: slow_accurate is ahead on
        # pooled WER by 0.42 points, but each wins on 6 of the 12 clips.
        d = R.apply_decision_rule(scores, CLIP_IDS)
        assert d["best_wer_model"] == "slow_accurate"
        assert d["adopt"] == "fast_similar"
        assert d["adopt_is_best_wer"] is False

    def test_best_model_wins_outright_when_the_gap_is_real(self):
        scores = [
            _score("accurate", 0.05, 1.0),
            _score("fast_but_bad", 0.40, 30.0),
        ]
        d = R.apply_decision_rule(scores, CLIP_IDS)
        assert d["adopt"] == "accurate"
        assert d["adopt_is_best_wer"] is True

    def test_best_model_wins_when_it_is_also_the_fastest(self):
        scores = [
            _score("best_and_fastest", 0.05, 30.0),
            _score("other", 0.30, 1.0),
        ]
        d = R.apply_decision_rule(scores, CLIP_IDS)
        assert d["adopt"] == "best_and_fastest"
        assert d["adopt_is_best_wer"] is True

    def test_best_model_is_always_a_qualifier(self):
        scores = [_score("a", 0.05, 1.0), _score("b", 0.40, 30.0)]
        d = R.apply_decision_rule(scores, CLIP_IDS)
        assert "a" in [q["model"] for q in d["qualifiers"]]

    def test_picks_fastest_among_several_qualifiers(self):
        scores = [
            _score("best", 0.0, 2.0,
                   per_clip_errors=[8, 14, 9, 13, 8, 14, 9, 13, 10, 12, 11, 11]),
            _score("mid", 0.0, 8.0,
                   per_clip_errors=[13, 9, 12, 8, 13, 9, 12, 8, 11, 11, 10, 12]),
            _score("quickest", 0.0, 25.0,
                   per_clip_errors=[12, 10, 13, 9, 12, 10, 8, 14, 11, 11, 12, 10]),
        ]
        d = R.apply_decision_rule(scores, CLIP_IDS)
        assert d["adopt"] == "quickest"
        assert len(d["qualifiers"]) == 3

    def test_single_candidate_adopts_itself(self):
        d = R.apply_decision_rule([_score("only", 0.2, 5.0)], CLIP_IDS)
        assert d["adopt"] == "only"
        assert d["adopt_is_best_wer"] is True


class TestLoadGroundTruth:
    def _write(self, tmp_path, monkeypatch, payload):
        path = tmp_path / "ground_truth.json"
        path.write_text(json.dumps(payload))
        monkeypatch.setattr(R, "GROUND_TRUTH", path)
        return path

    def test_missing_file_names_the_typing_page(self, tmp_path, monkeypatch):
        monkeypatch.setattr(R, "GROUND_TRUTH", tmp_path / "nope.json")
        with pytest.raises(R.GroundTruthError, match="type_here.html"):
            R.load_ground_truth(["a"])

    def test_rejects_a_payload_with_no_transcripts_key(self, tmp_path, monkeypatch):
        self._write(tmp_path, monkeypatch, {"generated": "now"})
        with pytest.raises(R.GroundTruthError, match="transcripts"):
            R.load_ground_truth(["a"])

    def test_rejects_a_partially_typed_set(self, tmp_path, monkeypatch):
        self._write(tmp_path, monkeypatch,
                    {"transcripts": {"a": "hello there", "b": "", "c": "   "}})
        with pytest.raises(R.GroundTruthError, match="2 of 3 clips are empty"):
            R.load_ground_truth(["a", "b", "c"])

    def test_rejects_clip_ids_not_in_the_index(self, tmp_path, monkeypatch):
        self._write(tmp_path, monkeypatch,
                    {"transcripts": {"a": "hello", "stray": "text"}})
        with pytest.raises(R.GroundTruthError, match="unknown clip ids"):
            R.load_ground_truth(["a"])

    def test_accepts_a_complete_set_and_strips_whitespace(self, tmp_path, monkeypatch):
        self._write(tmp_path, monkeypatch,
                    {"transcripts": {"a": "  hello there  ", "b": "second clip"}})
        got = R.load_ground_truth(["a", "b"])
        assert got == {"a": "hello there", "b": "second clip"}


class TestScoreModel:
    def _run(self, model="m", texts=None):
        texts = texts or {"a": "the cat sat", "b": "on the mat"}
        return {
            "model": model,
            "parameters_millions": 71.8,
            "realtime_factor": 17.2,
            "total_wall_s": 30.4,
            "clips": [
                {"video_id": cid, "text": t, "n_segments": 3}
                for cid, t in texts.items()
            ],
        }

    def test_perfect_transcript_scores_zero_wer(self):
        truth = {"a": "the cat sat", "b": "on the mat"}
        s = R.score_model(self._run(), truth, ["a", "b"])
        assert s["wer"] == 0.0
        assert s["word_accuracy"] == 1.0

    def test_pools_errors_across_clips_rather_than_averaging_rates(self):
        # Clip a: 3 ref words, all wrong. Clip b: 3 ref words, all right.
        # Pooled = 3/6 = 0.5. Averaging the rates would also give 0.5 here, so
        # make the clips different lengths to tell them apart.
        run = self._run(texts={"a": "x", "b": "on the mat"})
        truth = {"a": "the cat sat", "b": "on the mat"}
        s = R.score_model(run, truth, ["a", "b"])
        # ref words = 3 + 3 = 6; clip a has 2 deletions + 1 substitution = 3 errors
        assert s["ref_words"] == 6
        assert s["errors"] == 3
        assert s["wer"] == pytest.approx(0.5)

    def test_raises_when_a_model_is_missing_a_clip(self):
        run = self._run(texts={"a": "the cat sat"})
        with pytest.raises(RuntimeError, match="no transcript for clip b"):
            R.score_model(run, {"a": "the cat sat", "b": "on the mat"}, ["a", "b"])

    def test_sums_segment_counts_for_the_boundary_check(self):
        s = R.score_model(self._run(), {"a": "the cat sat", "b": "on the mat"}, ["a", "b"])
        assert s["n_segments"] == 6

    def test_hallucination_can_push_wer_above_one(self):
        run = self._run(texts={"a": "the cat sat " + "extra " * 20, "b": "on the mat"})
        s = R.score_model(run, {"a": "the cat sat", "b": "on the mat"}, ["a", "b"])
        assert s["wer"] > 1.0

    def test_wilson_is_omitted_when_accuracy_is_not_a_proportion(self):
        run = self._run(texts={"a": "the cat sat " + "extra " * 20, "b": "on the mat"})
        s = R.score_model(run, {"a": "the cat sat", "b": "on the mat"}, ["a", "b"])
        lo, hi = s["word_accuracy_ci"]
        assert lo != lo and hi != hi  # NaN, deliberately not a fabricated 0.0


class TestPerSpeakerWer:
    def test_pools_within_speaker_not_across(self):
        scored = {"per_clip": {
            "a": {"errors": 10, "ref_words": 100},
            "b": {"errors": 30, "ref_words": 100},
            "c": {"errors": 0, "ref_words": 50},
        }}
        clips = [
            {"video_id": "a", "channel": "Alice"},
            {"video_id": "b", "channel": "Alice"},
            {"video_id": "c", "channel": "Bob"},
        ]
        got = R.per_speaker_wer(scored, clips)
        assert got["Alice"] == pytest.approx(0.20)  # 40 errors / 200 words
        assert got["Bob"] == pytest.approx(0.0)
