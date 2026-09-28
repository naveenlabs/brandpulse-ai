"""
Tests for pipeline/analyst_facts.py — the deterministic layer of the written report.

Every rule the book prints beside a verdict is exercised at its boundary here:
the leans and their intervals, the reviewer-against-audience call, each
coverage check, the tone line's turning points, the ordering of the moments,
and every commercial-interest sign in each of its three states. No model and no
network is involved anywhere in this module, so nothing is mocked; the
arithmetic is the thing under test.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import pytest

from pipeline import analyst_facts as F

ROOT = Path(__file__).resolve().parent.parent


# ── fixtures ─────────────────────────────────────────────────────────────────

def seg(sid, start, end, label="POSITIVE", conf=0.9, facial="happy", vocal=None,
        conflict=0.0, flagged=False, reasons=None, text="it is fine"):
    return {
        "segment_id": sid, "start_s": start, "end_s": end,
        "conflict_score": conflict, "flagged": flagged,
        "conflict_reasons": reasons or [], "text": text,
        "model_outputs": {
            "transcript_sentiment": None if label is None else {"label": label, "confidence": conf},
            "facial_emotion": {"dominant": facial, "confidence": 0.7, "frame_count": 3},
            "vocal_emotion": vocal if vocal is not None else {"label": "neutral", "arousal": 0.4,
                                                              "reliability": 0.489},
        },
    }


def comments(pos, neu, neg):
    return ([{"text": "good", "label": "POSITIVE", "confidence": 0.9}] * pos
            + [{"text": "ok", "label": "NEUTRAL", "confidence": 0.9}] * neu
            + [{"text": "bad", "label": "NEGATIVE", "confidence": 0.9}] * neg)


REFERENCE = {"accuracy": {"comment": 78.7, "transcript": 67.8, "vocal": 48.9, "facial": 34.2},
             "n": {}, "source": {}, "coverage_floor": 0.5}


# ── reading the report ───────────────────────────────────────────────────────

class TestReadingTheReport:
    def test_segment_view_lifts_model_outputs(self):
        v = F.segment_view(seg(3, 1.0, 4.0, label="NEGATIVE"))
        assert v["segment_id"] == 3 and v["start_time"] == 1.0 and v["end_time"] == 4.0
        assert v["transcript_sentiment"]["label"] == "NEGATIVE"

    def test_both_vocal_schemas_are_read(self):
        as_dict = seg(0, 0, 1, vocal={"label": "positive", "arousal": 0.8})
        as_word = seg(0, 0, 1, vocal="happy")
        assert F.valences(as_dict, None)["vocal"] == "POSITIVE"
        assert F.valences(as_word, None)["vocal"] == "POSITIVE"

    def test_valences_reuse_the_scorers_rule(self):
        s = seg(0, 0, 1, facial="sad")
        assert F.valences(s, None)["facial"] == "NEGATIVE"
        # surprise is off the valence axis in the orchestrator, so it is absent here too
        assert "facial" not in F.valences(seg(0, 0, 1, facial="surprise"), None)
        assert F.valences(s, {"label": "NEUTRAL"})["comment"] == "NEUTRAL"

    def test_a_malformed_segment_degrades(self):
        assert F.segment_view(None)["text"] == ""
        assert F.valences({"model_outputs": "garbage"}, None) == {}
        assert F.duration({"start_s": "x", "end_s": 3}) == 0.0
        assert F.duration({"start_s": 5, "end_s": 3}) == 0.0

    @pytest.mark.parametrize("seconds,expected", [
        (0, "0:00"), (129.68, "2:09"), (59.99, "0:59"), (3600, "60:00"), (None, "-"),
        (float("nan"), "-"), (-3, "0:00")])
    def test_mmss_matches_the_interface(self, seconds, expected):
        assert F.mmss(seconds) == expected

    def test_subject_is_read_back_from_the_filename(self):
        s = F.subject_of({"brand_name": "Nike"}, "Nike (Mind 001).json")
        assert s == {"brand": "Nike", "product": "Mind 001", "title": ""}
        member = F.subject_of({"brand_name": "Nike", "video_title": "Ja 4 review"})
        assert member["title"] == "Ja 4 review" and member["product"] == ""

    @pytest.mark.parametrize("url,vid", [
        ("https://youtu.be/JpN1DQdV4G4?si=abc", "JpN1DQdV4G4"),
        ("https://www.youtube.com/watch?v=B8-JHY94jvI&t=3", "B8-JHY94jvI"),
        ("https://example.com/video", None), (None, None)])
    def test_video_id(self, url, vid):
        assert F.video_id_of({"video_url": url}) == vid

    def test_min_comments_matches_the_sweep_floor(self):
        from pipeline import sweep
        assert F.MIN_COMMENTS == sweep.MIN_COMMENTS

    def test_the_reference_is_read_from_figures_json(self):
        ref = F.load_reference()
        assert ref["accuracy"]["comment"] == 78.7
        assert ref["accuracy"]["facial"] == 34.2
        assert ref["coverage_floor"] == 0.5

    def test_a_missing_reference_is_empty_not_invented(self, tmp_path):
        assert F.load_reference(tmp_path / "absent.json") == {}


# ── leans ────────────────────────────────────────────────────────────────────

class TestLeans:
    def test_equal_weights_reduce_to_the_textbook_standard_error(self):
        xs = [1, 1, 0, -1, 1, 0]
        out = F.lean_of(xs)
        assert out["lean"] == pytest.approx(statistics.mean(xs))
        assert out["se"] == pytest.approx(statistics.stdev(xs) / math.sqrt(len(xs)))
        assert out["n"] == 6

    def test_zero_weights_are_ignored_and_empty_is_none(self):
        assert F.lean_of([1, -1], [2.0, 0.0])["lean"] == 1.0
        assert F.lean_of([]) is None
        assert F.lean_of([1], [0.0]) is None
        assert F.lean_of([1])["se"] is None

    def test_calls_need_the_interval_to_exclude_zero(self):
        assert F.lean_call({"lean": 0.5, "se": 0.1}) == "positive"
        assert F.lean_call({"lean": -0.5, "se": 0.1}) == "negative"
        assert F.lean_call({"lean": 0.15, "se": 0.1}) == "balanced"     # 0.15 - 1.96*0.1 < 0
        assert F.lean_call({"lean": 0.5, "se": None}) == "unknown"
        assert F.lean_call(None) == "unknown"

    def test_the_reviewer_is_weighted_by_time_spoken(self):
        segs = [seg(0, 0, 100, "POSITIVE"), seg(1, 100, 110, "NEGATIVE"), seg(2, 110, 120, None)]
        out = F.reviewer_lean(segs)
        assert out["lean"] == pytest.approx((100 - 10) / 110)
        assert out["seconds"] == {"POSITIVE": 100.0, "NEUTRAL": 0.0, "NEGATIVE": 10.0}
        assert out["counts"]["NEGATIVE"] == 1 and out["unread"] == 1

    def test_the_audience_is_one_comment_one_vote(self):
        out = F.audience_lean(comments(6, 2, 2) + [{"text": "?", "label": None}])
        assert out["lean"] == pytest.approx(0.4)
        assert out["n"] == 10 and out["counts"] == {"POSITIVE": 6, "NEUTRAL": 2, "NEGATIVE": 2}

    def test_agreement_calls_only_a_distinguishable_gap(self):
        warm = {"lean": 0.8, "se": 0.05}
        cool = {"lean": -0.2, "se": 0.05}
        near = {"lean": 0.75, "se": 0.05}
        assert F.agreement(warm, cool)["call"] == "reviewer_warmer"
        assert F.agreement(cool, warm)["call"] == "audience_warmer"
        assert F.agreement(warm, near)["call"] == "no_clear_difference"
        assert F.agreement(warm, {"lean": None, "se": None})["call"] == "unknown"

    def test_the_gap_interval_uses_both_errors(self):
        out = F.compare({"lean": 0.5, "se": 0.3}, {"lean": 0.0, "se": 0.4})
        assert out["se"] == pytest.approx(0.5)
        assert out["low"] == pytest.approx(0.5 - F.Z95 * 0.5)


# ── coverage and reading confidence ──────────────────────────────────────────

def report(segs, n_pos=20, n_neu=10, n_neg=10, label="POSITIVE"):
    return {"all_segments": segs, "all_comments": comments(n_pos, n_neu, n_neg),
            "comment_sentiment": {"label": label, "distribution": {}},
            "authenticity_score": 80.0, "brand_health_score": 70.0}


class TestReadingConfidence:
    def test_weak_share_separates_strong_from_weak_driven_conflict(self):
        strong = seg(0, 0, 10, "NEGATIVE", conflict=0.6)      # words vs comments
        weak = seg(1, 10, 20, "POSITIVE", facial="sad", conflict=0.2)
        out = F.weak_conflict_share([strong, weak], {"label": "POSITIVE"})
        assert out["share"] == pytest.approx(0.2 / 0.8)
        assert F.weak_conflict_share([seg(0, 0, 1)], {"label": "POSITIVE"})["share"] is None

    def test_well_covered_when_every_check_passes(self):
        out = F.reading_confidence(report([seg(0, 0, 10), seg(1, 10, 20)]), REFERENCE)
        assert out["level"] == "well_covered"
        assert all(c["passed"] for c in out["checks"])
        assert out["checks"][2]["no_conflict"] is True

    def test_too_few_comments_is_thin(self):
        out = F.reading_confidence(report([seg(0, 0, 10)], n_pos=10, n_neu=5, n_neg=5), REFERENCE)
        assert out["level"] == "thinly_covered"
        assert out["checks"][0]["value"] == 20 and out["checks"][0]["passed"] is False

    def test_exactly_the_floor_passes(self):
        out = F.reading_confidence(report([seg(0, 0, 10)], n_pos=30, n_neu=0, n_neg=0), REFERENCE)
        assert out["checks"][0]["passed"] is True

    def test_unread_words_are_thin(self):
        segs = [seg(0, 0, 10, None), seg(1, 10, 20, None), seg(2, 20, 30)]
        out = F.reading_confidence(report(segs), REFERENCE)
        assert out["level"] == "thinly_covered"
        assert out["checks"][1]["value"] == pytest.approx(1 / 3, abs=1e-4)

    def test_conflict_resting_on_weak_channels_is_partial(self):
        segs = [seg(0, 0, 10, "POSITIVE", facial="sad", conflict=0.5), seg(1, 10, 20)]
        out = F.reading_confidence(report(segs), REFERENCE)
        assert out["level"] == "partly_covered"

    def test_no_floor_means_unknown_not_a_guess(self):
        out = F.reading_confidence(report([seg(0, 0, 10)]), {"accuracy": {}})
        assert out["level"] == "unknown"
        assert out["checks"][1]["passed"] is None

    def test_the_ceiling_always_travels_with_the_level(self):
        out = F.reading_confidence(report([seg(0, 0, 10)]), REFERENCE)
        assert out["ceiling"]["rho"] == 0.0575 and out["ceiling"]["human_rho"] == 0.8038
        assert "baseline_bench" in out["ceiling"]["source"]
        assert out["accuracy"]["facial"] == 34.2

    def test_the_ceiling_figures_are_the_benchs_own(self):
        text = (ROOT / "research" / "baseline_bench" / "BASELINE_ANALYSIS.md").read_text(encoding="utf-8")
        for figure in ("+0.0575", "−0.1282", "+0.2364", "+0.8038", "n=119"):
            assert figure in text, figure


# ── the tone line ────────────────────────────────────────────────────────────

class TestTone:
    def test_raw_is_valence_times_confidence_and_unread_is_none(self):
        out = F.tone_series([seg(0, 0, 10, "NEGATIVE", conf=0.5), seg(1, 10, 20, None)])
        assert out["points"][0]["raw"] == -0.5
        assert out["points"][1]["raw"] is None

    def test_smoothing_is_weighted_by_overlap(self):
        segs = [seg(0, 0, 10, "POSITIVE", conf=1.0), seg(1, 10, 40, "NEGATIVE", conf=1.0)]
        out = F.tone_series(segs, window_s=60)
        # the window around segment 0 (midpoint 5) covers [-25, 35]: 10 s positive, 25 s negative
        assert out["points"][0]["smooth"] == pytest.approx((10 - 25) / 35, abs=1e-4)

    def test_turning_points_are_prominent_interior_extrema(self):
        ys = [0.0, 0.1, 0.8, 0.1, 0.0, -0.1, -0.7, -0.1, 0.0]
        points = [{"seg": i, "t": i * 100.0, "smooth": y} for i, y in enumerate(ys)]
        turns = F.turning_points(points)
        assert [t["kind"] for t in turns] == ["peak", "dip"]
        assert [t["seg"] for t in turns] == [2, 6]

    def test_small_wiggles_and_endpoints_are_not_turns(self):
        flat = [{"seg": i, "t": i * 100.0, "smooth": y}
                for i, y in enumerate([0.9, 0.05, 0.0, 0.05, 0.0, -0.9])]
        assert F.turning_points(flat) == []

    def test_turns_closer_than_the_gap_keep_the_stronger(self):
        ys = [0.0, 0.9, 0.0, 0.5, 0.0]
        points = [{"seg": i, "t": i * 10.0, "smooth": y} for i, y in enumerate(ys)]
        turns = F.turning_points(points, min_gap_s=60)
        assert [t["seg"] for t in turns] == [1]


# ── moments ──────────────────────────────────────────────────────────────────

class TestMoments:
    def test_highest_conflict_first_earliest_on_a_tie(self):
        segs = [seg(0, 0, 5, conflict=0.5), seg(1, 5, 9, conflict=0.9),
                seg(2, 9, 12, conflict=0.5), seg(3, 12, 15, conflict=0.0)]
        out = F.top_moments(segs, {"label": "POSITIVE"})
        assert [m["seg"] for m in out] == [1, 0, 2]
        assert out[0]["time"] == "0:05"

    def test_no_conflict_is_never_a_moment(self):
        assert F.top_moments([seg(0, 0, 5)], None) == []

    def test_damping_is_carried(self):
        s = seg(0, 0, 5, conflict=0.3, reasons=["facial_channel_downweighted[structural]: ..."])
        assert F.top_moments([s], None)[0]["damped"] is True


# ── commercial-interest signs ────────────────────────────────────────────────

class TestSponsorWording:
    @pytest.mark.parametrize("text,category", [
        ("This video is sponsored by NordVPN", "sponsorship"),
        ("thanks to Dbrand for sponsoring today's video", "sponsorship"),
        ("Today's sponsor is Squarespace", "sponsorship"),
        ("use code MKBHD for ten percent off", "discount_code"),
        ("grab 20% off with my promo code", "discount_code"),
        ("links are affiliate links", "affiliate"),
        ("I may earn a small commission", "affiliate"),
        ("Samsung sent me this phone to test", "gifted"),
        ("this is a review unit", "gifted"),
    ])
    def test_it_finds_commercial_wording(self, text, category):
        hits = F.sponsor_wording([seg(0, 65, 70, text=text)])
        assert category in {h["category"] for h in hits}
        assert hits[0]["time"] == "1:05"

    @pytest.mark.parametrize("text", [
        "the sponsors of the event were there",
        "this code is well written",
        "the paid version of the app",
        "a gift for my brother",
        "they sent the update last week",
    ])
    def test_it_does_not_fire_on_ordinary_words(self, text):
        assert F.sponsor_wording([seg(0, 0, 5, text=text)]) == []

    def test_description_not_fetched_is_none_and_empty_is_empty(self):
        assert F.description_signs(None) is None
        assert F.description_signs("Just a review, no links.") == []

    def test_description_hits_keep_hosts_not_paths(self):
        hits = F.description_signs("Buy here: https://amzn.to/3xYzAbc?tag=secret #ad")
        cats = {h["category"] for h in hits}
        assert {"affiliate", "disclosure"} <= cats
        for h in hits:
            assert "3xYzAbc" not in h["context"] and "secret" not in h["context"]
            assert "amzn.to/" in h["context"] or h["category"] == "disclosure"

    def test_a_hashtag_inside_a_word_is_not_a_disclosure(self):
        assert F.description_signs("see #adobe tips and #advertising") == []


class TestPaidSigns:
    def base(self, **kw):
        return report([seg(0, 0, 10, **kw)])

    def test_unfetched_metadata_leaves_s1_and_s3_unchecked(self):
        out = F.paid_signs(self.base(), {"call": "no_clear_difference"}, None)
        states = {s["id"]: s["state"] for s in out["signs"]}
        assert states == {"S1": "not_checked", "S2": "absent", "S3": "not_checked",
                          "S4": "absent", "S5": "absent"}
        assert out["checked"] == 3 and out["present"] == 0

    def test_the_creators_label_is_a_disclosure_and_off_is_not_declared(self):
        on = F.paid_signs(self.base(), {"call": "unknown"},
                          {"fetched": True, "has_paid_product_placement": True, "description_hits": []})
        off = F.paid_signs(self.base(), {"call": "unknown"},
                           {"fetched": True, "has_paid_product_placement": False, "description_hits": []})
        assert on["signs"][0]["state"] == "present"
        assert off["signs"][0]["state"] == "absent"
        assert off["signs"][3]["state"] == "not_checked"          # S4 with an unknown call

    def test_description_commerce_is_s3(self):
        meta = {"fetched": True, "has_paid_product_placement": False,
                "description_hits": [{"category": "affiliate", "match": "amzn.to/"}]}
        out = F.paid_signs(self.base(), {"call": "no_clear_difference"}, meta)
        assert out["signs"][2]["state"] == "present" and out["signs"][0]["state"] == "absent"

    def test_speech_wording_is_s2(self):
        out = F.paid_signs(report([seg(0, 0, 10, text="sponsored by acme")]), {}, None)
        assert out["signs"][1]["state"] == "present"
        assert out["signs"][1]["evidence"]["speech"][0]["seg"] == 0

    def test_a_warmer_reviewer_is_s4(self):
        out = F.paid_signs(self.base(), {"call": "reviewer_warmer"}, None)
        assert out["signs"][3]["state"] == "present" and out["signs"][3]["kind"] == "inference"

    def test_positive_words_at_a_flagged_moment_are_s5(self):
        flagged = report([seg(0, 0, 10, "POSITIVE", conflict=0.8, flagged=True)])
        out = F.paid_signs(flagged, {}, None)
        assert out["signs"][4]["state"] == "present"
        assert out["signs"][4]["evidence"]["positive_flagged"] == [0]

    def test_the_controllers_own_flag_is_s5(self):
        r = report([seg(0, 0, 10, "NEGATIVE", conflict=0.3, reasons=["POTENTIAL_PAID_PROMOTION"])])
        assert F.paid_signs(r, {}, None)["signs"][4]["state"] == "present"

    def test_the_disclaimer_says_signs_not_proof(self):
        out = F.paid_signs(self.base(), {}, None)
        assert "not proof" in out["disclaimer"]


# ── the whole layer ──────────────────────────────────────────────────────────

class TestComputeFacts:
    def test_it_is_json_safe_and_complete(self):
        out = F.compute_facts(report([seg(0, 0, 10), seg(1, 10, 20, "NEGATIVE", conflict=0.5)]),
                              reference=REFERENCE)
        json.dumps(out)
        for key in ("scores", "reviewer", "audience", "agreement", "confidence",
                    "tone", "moments", "signs"):
            assert key in out

    def test_an_empty_report_degrades(self):
        out = F.compute_facts({}, reference=REFERENCE)
        json.dumps(out)
        assert out["reviewer"]["lean"] is None and out["moments"] == []

    def test_every_saved_report_computes(self):
        files = sorted((ROOT / "outputs").glob("*.json"))
        if not files:
            pytest.skip("no saved reports in this working copy")
        for path in files:
            r = json.loads(path.read_text(encoding="utf-8"))
            out = F.compute_facts(r, reference=REFERENCE)
            json.dumps(out)
            rv = out["reviewer"]
            assert rv["lean"] is None or -1.0 <= rv["lean"] <= 1.0
            assert sum(out["audience"]["counts"].values()) == out["audience"]["n"]
            assert len(out["tone"]["points"]) == len(r["all_segments"])
