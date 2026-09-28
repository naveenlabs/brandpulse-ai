"""
Tests for pipeline/scorer.py

Pass criteria (per project spec):
  - compute_authenticity_score: weighted mean formula, flagged double-weight,
    clamp to [0,100], round to 2dp, empty → 100.0
  - compute_brand_health_score: label-to-score mapping, blend formula,
    empty → 50.0 neutral baseline, clamp, round to 2dp
  - build_final_report: required keys, flagged filtering, text enrichment,
    segment_count, bias_caveat, comment_sentiment pass-through

All tests are pure Python — no model downloads, no Ollama, no network.
"""

from __future__ import annotations

import pytest

from pipeline.scorer import (
    BIAS_CAVEAT,
    build_final_report,
    compute_authenticity_score,
    compute_brand_health_score,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _result(
    sid: int = 0,
    score: float = 0.0,
    flagged: bool = False,
    reasons: list[str] | None = None,
) -> dict:
    return {
        "segment_id":       sid,
        "start_s":          0.0,
        "end_s":            10.0,
        "conflict_score":   score,
        "conflict_reasons": reasons or [],
        "flagged":          flagged,
    }


def _segment(sid: int = 0, text: str = "test text") -> dict:
    return {
        "segment_id": sid,
        "start_time": 0.0,
        "end_time":   10.0,
        "text":       text,
    }


def _comment_sentiment(
    label: str = "POSITIVE",
    conf: float = 0.9,
    count: int = 10,
) -> dict:
    dist = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    dist[label] = count
    return {
        "label":         label,
        "confidence":    conf,
        "comment_count": count,
        "distribution":  dist,
    }


# ── compute_authenticity_score ─────────────────────────────────────────────────

class TestComputeAuthenticityScore:
    def test_empty_returns_100(self):
        assert compute_authenticity_score([]) == 100.0

    def test_all_zero_scores_returns_100(self):
        results = [_result(score=0.0), _result(score=0.0)]
        assert compute_authenticity_score(results) == 100.0

    def test_all_ones_returns_0(self):
        results = [_result(score=1.0), _result(score=1.0)]
        assert compute_authenticity_score(results) == 0.0

    def test_single_not_flagged(self):
        # score=0.5, weight=1 → mean=0.5 → 100−50=50
        assert compute_authenticity_score([_result(score=0.5, flagged=False)]) == 50.0

    def test_single_flagged_same_result(self):
        # flagged doubles weight, but with one segment mean is unchanged
        assert compute_authenticity_score([_result(score=0.5, flagged=True)]) == 50.0

    def test_weighted_mean_two_segments(self):
        # seg0: score=0.0 weight=1; seg1: score=1.0 flagged weight=2
        # weighted_mean = (0×1 + 1×2)/(1+2) = 2/3 ≈ 0.6667
        # auth = 100 − 66.67 = 33.33
        results = [
            _result(sid=0, score=0.0, flagged=False),
            _result(sid=1, score=1.0, flagged=True),
        ]
        score = compute_authenticity_score(results)
        assert abs(score - 33.33) < 0.01

    def test_all_flagged_same_as_unweighted(self):
        # When all segments have the same weight multiplier, mean is unchanged
        results = [
            _result(sid=0, score=0.2, flagged=True),
            _result(sid=1, score=0.8, flagged=True),
        ]
        expected = 100.0 - ((0.2 + 0.8) / 2 * 100.0)  # = 50.0
        assert abs(compute_authenticity_score(results) - expected) < 0.01

    def test_result_rounded_to_2dp(self):
        # score=1/3 → weighted_mean=1/3 → auth=100-33.333...=66.666... → 66.67
        results = [_result(score=1 / 3)]
        score = compute_authenticity_score(results)
        assert score == round(score, 2)
        assert isinstance(score, float)

    def test_clamp_above_100(self):
        # Inject a negative conflict_score (shouldn't happen, but must be safe)
        results = [_result(score=-1.0)]
        assert compute_authenticity_score(results) == 100.0

    def test_clamp_below_zero(self):
        # inject score > 1.0 — not normally possible but clamp must protect
        results = [_result(score=2.0)]
        assert compute_authenticity_score(results) == 0.0

    def test_mixed_flagged_and_unflagged(self):
        # Verify weighting is applied correctly with mixed flags
        results = [
            _result(sid=0, score=0.4, flagged=False),   # weight=1
            _result(sid=1, score=0.4, flagged=True),    # weight=2
            _result(sid=2, score=0.4, flagged=False),   # weight=1
        ]
        # weighted_mean = (0.4×1 + 0.4×2 + 0.4×1) / (1+2+1) = 1.6/4 = 0.4
        # auth = 100 − 40 = 60.0
        assert compute_authenticity_score(results) == 60.0


# ── compute_brand_health_score ─────────────────────────────────────────────────

class TestComputeBrandHealthScore:
    def test_positive_full_confidence_full_auth(self):
        # comment_score=100, auth=100 → (100×0.6)+(100×0.4)=100
        cs = _comment_sentiment("POSITIVE", conf=1.0)
        assert compute_brand_health_score(cs, 100.0) == 100.0

    def test_negative_full_confidence_full_auth(self):
        # comment_score=0, auth=100 → (0×0.6)+(100×0.4)=40
        cs = _comment_sentiment("NEGATIVE", conf=0.9)
        assert compute_brand_health_score(cs, 100.0) == 40.0

    def test_neutral_sentiment(self):
        # comment_score = 0.8×50 = 40; auth=80 → (40×0.6)+(80×0.4)=24+32=56
        cs = _comment_sentiment("NEUTRAL", conf=0.8)
        assert compute_brand_health_score(cs, 80.0) == 56.0

    def test_empty_comment_sentiment_neutral_baseline(self):
        # comment_score=50 (neutral baseline); auth=100 → (50×0.6)+(100×0.4)=30+40=70
        assert compute_brand_health_score({}, 100.0) == 70.0

    def test_unknown_label_defaults_50(self):
        # comment_score=50 (unknown label); auth=0 → (50×0.6)+(0×0.4)=30
        cs = {"label": "UNKNOWN", "confidence": 0.9, "comment_count": 5}
        assert compute_brand_health_score(cs, 0.0) == 30.0

    def test_result_rounded_to_2dp(self):
        cs = _comment_sentiment("NEUTRAL", conf=1 / 3)
        score = compute_brand_health_score(cs, 50.0)
        assert score == round(score, 2)

    def test_clamp_above_100(self):
        # Artificially high auth score should clamp
        cs = _comment_sentiment("POSITIVE", conf=1.0)
        assert compute_brand_health_score(cs, 200.0) == 100.0

    def test_clamp_below_zero(self):
        # Artificially negative auth score
        cs = _comment_sentiment("NEGATIVE", conf=1.0)
        assert compute_brand_health_score(cs, -100.0) == 0.0

    def test_returns_float(self):
        cs = _comment_sentiment("POSITIVE", conf=0.9)
        result = compute_brand_health_score(cs, 75.0)
        assert isinstance(result, float)


# ── build_final_report ─────────────────────────────────────────────────────────

class TestBuildFinalReport:
    def _run(
        self,
        video_url: str = "https://youtu.be/test",
        brand_name: str = "TestBrand",
        segments: list[dict] | None = None,
        conflict_results: list[dict] | None = None,
        comment_sentiment: dict | None = None,
    ) -> dict:
        return build_final_report(
            video_url=video_url,
            brand_name=brand_name,
            segments=segments or [],
            conflict_results=conflict_results or [],
            comment_sentiment=comment_sentiment or _comment_sentiment(),
        )

    def test_required_keys_present(self):
        report = self._run()
        expected = {
            "video_url", "brand_name", "authenticity_score", "brand_health_score",
            "segment_count", "flagged_segments", "comment_sentiment", "bias_caveat",
            # Added 02 Sep 2026 with the vocal-channel swap. BIAS_CAVEAT names a
            # limitation from the literature; these two name one measured here,
            # plus the commercial-use restriction on the adopted checkpoint.
            "vocal_caveat", "vocal_licence_note",
        }
        assert set(report.keys()) == expected

    def test_video_url_and_brand_name_passthrough(self):
        report = self._run(video_url="https://example.com/v", brand_name="Acme")
        assert report["video_url"] == "https://example.com/v"
        assert report["brand_name"] == "Acme"

    def test_segment_count_equals_input_length(self):
        segs = [_segment(i) for i in range(5)]
        report = self._run(segments=segs)
        assert report["segment_count"] == 5

    def test_flagged_segments_only_flagged(self):
        results = [
            _result(sid=0, score=0.2, flagged=False),
            _result(sid=1, score=0.8, flagged=True),
            _result(sid=2, score=0.9, flagged=True),
        ]
        report = self._run(conflict_results=results)
        assert len(report["flagged_segments"]) == 2
        for fs in report["flagged_segments"]:
            assert fs["flagged"] is True

    def test_unflagged_segments_excluded(self):
        results = [_result(sid=0, score=0.1, flagged=False)]
        report = self._run(conflict_results=results)
        assert report["flagged_segments"] == []

    def test_flagged_segments_enriched_with_text(self):
        segs = [_segment(0, "hello world"), _segment(1, "brand mention")]
        results = [
            _result(sid=0, score=0.7, flagged=True),
            _result(sid=1, score=0.8, flagged=True),
        ]
        report = self._run(segments=segs, conflict_results=results)
        texts = {fs["segment_id"]: fs["text"] for fs in report["flagged_segments"]}
        assert texts[0] == "hello world"
        assert texts[1] == "brand mention"

    def test_flagged_segment_missing_match_defaults_empty_text(self):
        # Result refers to a segment_id not present in segments
        results = [_result(sid=99, score=0.9, flagged=True)]
        report = self._run(segments=[], conflict_results=results)
        assert report["flagged_segments"][0]["text"] == ""

    def test_bias_caveat_is_bias_caveat_constant(self):
        report = self._run()
        assert report["bias_caveat"] == BIAS_CAVEAT
        assert len(report["bias_caveat"]) > 0

    def test_comment_sentiment_passthrough(self):
        cs = _comment_sentiment("NEGATIVE", conf=0.75, count=20)
        report = self._run(comment_sentiment=cs)
        assert report["comment_sentiment"] is cs

    def test_authenticity_score_in_range(self):
        results = [_result(score=0.5, flagged=False)]
        report = self._run(conflict_results=results)
        assert 0.0 <= report["authenticity_score"] <= 100.0

    def test_brand_health_score_in_range(self):
        report = self._run()
        assert 0.0 <= report["brand_health_score"] <= 100.0

    def test_scores_computed_consistently(self):
        # Verify build_final_report produces the same scores as calling functions directly
        segs = [_segment(0)]
        results = [_result(sid=0, score=0.4, flagged=False)]
        cs = _comment_sentiment("POSITIVE", conf=0.8)

        report = build_final_report("url", "Brand", segs, results, cs)

        expected_auth = compute_authenticity_score(results)
        expected_health = compute_brand_health_score(cs, expected_auth)
        assert report["authenticity_score"] == expected_auth
        assert report["brand_health_score"] == expected_health

    def test_empty_everything_does_not_raise(self):
        report = build_final_report("url", "Brand", [], [], {})
        assert report["authenticity_score"] == 100.0
        assert report["flagged_segments"] == []
        assert report["segment_count"] == 0
