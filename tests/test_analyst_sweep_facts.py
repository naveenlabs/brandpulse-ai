"""
Tests for pipeline/analyst_sweep_facts.py — what several videos say together.

Every rule is tested at its boundaries, both ways: consensus, a video's stance
on a theme, a theme row's label, the odd one out, set coverage, near-ties, and
the two-period facts (overlapping windows, the same video read twice, the range
rule, matching themes). Nothing here is mocked: the arithmetic is the thing
under test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pipeline import analyst_facts as F
from pipeline import analyst_sweep_facts as S

ROOT = Path(__file__).resolve().parent.parent


# ── fixtures ─────────────────────────────────────────────────────────────────

def seg(sid, start, end, label, text="words that were said here", conflict=0.0, flagged=False):
    return {"segment_id": sid, "start_s": start, "end_s": end, "text": text,
            "conflict_score": conflict, "flagged": flagged, "conflict_reasons": [],
            "model_outputs": {"transcript_sentiment": {"label": label, "confidence": 0.9},
                              "facial_emotion": {"dominant": "neutral", "confidence": 0.6},
                              "vocal_emotion": {"label": "neutral", "arousal": 0.4}}}


def report(transcript=("POSITIVE",) * 6, comments=(("POSITIVE", 30), ("NEGATIVE", 10)),
           auth=60.0, health=55.0, label="POSITIVE"):
    segments = [seg(i, i * 20, i * 20 + 20, lab, conflict=0.5 if i == 1 else 0.0)
                for i, lab in enumerate(transcript)]
    all_comments = [{"text": f"comment number {k}", "label": lab, "confidence": 0.8}
                    for lab, count in comments for k in range(count)]
    dist = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    for lab, count in comments:
        dist[lab] += count
    return {"video_url": "https://youtu.be/AAAAAAAAAAA", "brand_name": "Acme",
            "authenticity_score": auth, "brand_health_score": health,
            "all_segments": segments, "all_comments": all_comments,
            "comment_sentiment": {"label": label, "confidence": 0.7, "distribution": dist}}


def bundle(n, rep, vid=None, analysis=None, stale=False):
    vid = vid or f"vid{n:08d}"[:11]
    return {"n": n, "entry": {"video_id": vid, "title": f"Video {n}", "channel": "C"},
            "report": rep, "analysis": analysis, "stale": stale}


RECORD = {"subject": "Acme One", "subject_kind": "product", "window": "month", "offset_days": 0,
          "summary": {"authenticity": {"mean": 60}, "brand_health": {"mean": 55}}}


# ── the near-tie twin ────────────────────────────────────────────────────────

class TestNearTie:
    def test_it_agrees_with_the_interface_constant(self):
        js = (ROOT / "interface" / "ui" / "src" / "lib" / "contract.js").read_text(encoding="utf-8")
        m = re.search(r"export const AGGREGATE_TIE_MARGIN = ([\d.]+);", js)
        assert m and float(m.group(1)) == S.AGGREGATE_TIE_MARGIN

    @pytest.mark.parametrize("dist,tie", [
        ({"POSITIVE": 38, "NEUTRAL": 28, "NEGATIVE": 34}, True),     # the S27 video, 4 in 100
        ({"POSITIVE": 37, "NEUTRAL": 26, "NEGATIVE": 37}, True),     # an exact tie
        ({"POSITIVE": 40, "NEUTRAL": 25, "NEGATIVE": 35}, True),     # exactly 5 in 100
        ({"POSITIVE": 41, "NEUTRAL": 25, "NEGATIVE": 34}, False),
    ])
    def test_the_margin_boundary(self, dist, tie):
        assert S.near_tie(dist)["near_tie"] is tie

    def test_nothing_to_rank_is_none(self):
        assert S.near_tie({}) is None and S.near_tie({"POSITIVE": 0, "NEGATIVE": 0}) is None

    def test_the_swing_is_the_scorers_own_arithmetic(self):
        """POSITIVE at confidence 0.8 scores 80 on comments, NEGATIVE 0; 60% of that is 48."""
        out = S.near_tie({"POSITIVE": 38, "NEUTRAL": 28, "NEGATIVE": 34}, 0.8, 50.0)
        assert out["swing"] == pytest.approx(48.0)


# ── consensus of calls ───────────────────────────────────────────────────────

class TestConsensus:
    @pytest.mark.parametrize("calls,label,call", [
        (["positive"] * 5, "all", "positive"),
        (["positive"] * 4 + ["balanced"], "all_but_one", "positive"),
        (["positive"] * 2 + ["balanced"], "all_but_one", "positive"),
        (["positive"] * 3 + ["balanced"] * 2, "split", "positive"),
        (["positive", "balanced", "positive", "balanced"], "split", None),
        (["positive", "positive"], "too_few", None),
        (["positive"] * 2 + ["unknown"] * 3, "too_few", None),
        (["balanced"] * 3, "all", "balanced"),
    ])
    def test_the_rule(self, calls, label, call):
        out = S.consensus(calls)
        assert (out["label"], out["call"]) == (label, call)

    def test_unknown_calls_are_not_counted_as_readable(self):
        out = S.consensus(["positive", "positive", "positive", "unknown"])
        assert out == {"label": "all", "call": "positive", "count": 3, "of": 3}


# ── one video's stance on a theme, and a row's label ─────────────────────────

class TestThemeRules:
    @pytest.mark.parametrize("stances,stance", [
        ({"praise": 2, "criticism": 1}, "praise"),
        ({"praise": 1, "criticism": 2}, "criticism"),
        ({"praise": 1, "criticism": 1}, "mixed"),
        ({"mixed": 1}, "mixed"),
        ({"neutral": 3}, "neutral"),
        ({}, "silent"),
    ])
    def test_cell_stance(self, stances, stance):
        assert S.cell_stance(stances) == stance

    @pytest.mark.parametrize("talked,a,b,label,side", [
        (4, 4, 0, "agreed", "first"),
        (2, 0, 2, "agreed", "second"),
        (4, 3, 1, "mostly", "first"),
        (4, 1, 3, "mostly", "second"),
        (3, 2, 1, "split", None),
        (2, 1, 1, "split", None),
        (5, 2, 2, "split", None),
        (3, 1, 0, "too_few", None),
        (1, 0, 0, "too_few", None),
        (3, 0, 0, "neutral", None),
    ])
    def test_row_label(self, talked, a, b, label, side):
        assert S.row_label(talked, a, b) == (label, side)


# ── the odd one out ──────────────────────────────────────────────────────────

def row(n, r_lean, a_lean, r_se=0.05, a_se=0.05):
    return {"n": n, "video_id": f"v{n}", "title": f"Video {n}", "analysed": True,
            "reviewer": {"lean": r_lean, "se": r_se, "call": "positive"},
            "audience": {"lean": a_lean, "se": a_se, "call": "balanced"}}


class TestOddOneOut:
    def test_a_video_far_from_the_rest_with_a_tight_interval_stands_apart(self):
        rows = [row(1, 0.2, 0.47), row(2, 0.2, -0.05), row(3, 0.3, -0.12), row(4, 0.25, 0.04)]
        out = S.odd_one_out(rows)
        assert out["n"] == 1 and out["dimension"] == "audience"
        assert out["others_median"] == pytest.approx(-0.05)
        assert out["distance"] == pytest.approx(0.52)

    def test_far_but_uncertain_is_not_enough(self):
        rows = [row(1, 0.2, 0.6, a_se=0.4), row(2, 0.2, 0.0), row(3, 0.2, 0.0)]
        assert S.odd_one_out(rows) is None

    def test_certain_but_near_is_not_enough(self):
        rows = [row(1, 0.2, 0.45, a_se=0.01), row(2, 0.2, 0.0), row(3, 0.2, 0.0)]
        assert S.odd_one_out(rows) is None

    def test_at_exactly_the_distance_it_qualifies(self):
        rows = [row(1, 0.2, 0.5, a_se=0.01), row(2, 0.2, 0.0), row(3, 0.2, 0.0)]
        assert S.odd_one_out(rows)["n"] == 1

    def test_a_video_under_its_coverage_floor_does_not_take_part(self):
        rows = [row(1, 0.2, 0.9, a_se=0.0), row(2, 0.2, 0.0), row(3, 0.2, 0.0)]
        rows[0]["coverage_failed_ids"] = ["comments"]
        assert S.odd_one_out(rows) is None
        rows[0]["coverage_failed_ids"] = ["transcript"]
        assert S.odd_one_out(rows)["n"] == 1

    def test_two_videos_are_never_enough(self):
        assert S.odd_one_out([row(1, 0.9, 0.9), row(2, -0.9, -0.9)]) is None

    def test_the_largest_distance_wins_across_both_leans(self):
        rows = [row(1, 0.9, 0.0), row(2, 0.1, 0.0), row(3, 0.1, 0.0), row(4, 0.1, 0.95)]
        out = S.odd_one_out(rows)
        assert (out["n"], out["dimension"]) == (4, "audience")

    def test_an_exact_tie_goes_to_the_reviewer_then_the_earlier_video(self):
        rows = [row(1, 0.9, 0.0), row(2, 0.1, 0.0), row(3, 0.1, 0.0), row(4, 0.1, 0.8)]
        out = S.odd_one_out(rows)
        assert (out["n"], out["dimension"]) == (1, "reviewer")


# ── the whole set, from reports ──────────────────────────────────────────────

class TestSetFacts:
    def bundles(self):
        return [bundle(1, report()),
                bundle(2, report(comments=(("POSITIVE", 20), ("NEGATIVE", 20)))),
                bundle(3, report(transcript=("NEGATIVE",) * 6, comments=(("NEGATIVE", 40),),
                                 label="NEGATIVE")),
                {"n": 4, "entry": {"video_id": "failedvideo", "title": "Gone"}, "report": None,
                 "analysis": None, "stale": False, "reason": "download failed"}]

    def test_rows_are_numbered_in_selection_order_and_failures_kept(self):
        out = S.compute_sweep_facts(RECORD, self.bundles())
        assert [r["n"] for r in out["videos"]] == [1, 2, 3, 4]
        assert out["videos"][3]["analysed"] is False and out["videos"][3]["reason"] == "download failed"
        assert out["set"]["analysed"] == 3 and out["set"]["failed"] == 1
        json.dumps(out)

    def test_calls_are_counted_from_the_single_video_facts(self):
        out = S.compute_sweep_facts(RECORD, self.bundles())
        for r, b in zip(out["videos"][:3], self.bundles()[:3]):
            f = F.compute_facts(b["report"])
            assert r["reviewer"]["lean"] == pytest.approx(f["reviewer"]["lean"])
            assert r["audience"]["call"] == f["audience"]["call"]
        assert out["set"]["reviewer_calls"]["positive"] == 2
        assert out["set"]["reviewer_calls"]["negative"] == 1
        assert out["audience"]["counts"] == {"POSITIVE": 50, "NEUTRAL": 0, "NEGATIVE": 70}

    def test_a_current_stored_analysis_supplies_its_facts_and_status(self):
        rep = report()
        stored = {"status": "complete", "facts": F.compute_facts(rep),
                  "written": {"verdict": {"text": "Liked it.", "source": "model"}, "moment_notes": []},
                  "reading": {"topics": [], "claims": [], "comment_tags": {}, "questions": []}}
        stored["facts"]["signs"]["present"] = 99          # proves the stored facts were the ones read
        r = S.video_row(bundle(1, rep, analysis=stored))
        assert r["written"] == "complete" and r["signs"]["present"] == 99
        assert r["verdict"] == {"text": "Liked it.", "source": "model"}

    def test_a_stale_analysis_is_not_trusted_for_facts_or_words(self):
        rep = report()
        stored = {"status": "complete", "facts": {"broken": True},
                  "written": {"verdict": {"text": "Old.", "source": "model"}}}
        r = S.video_row(bundle(1, rep, analysis=stored, stale=True))
        assert r["written"] == "stale" and r["verdict"] is None
        assert r["reviewer"]["lean"] == pytest.approx(F.compute_facts(rep)["reviewer"]["lean"])

    def test_the_tone_line_is_on_a_percent_axis(self):
        r = S.video_row(bundle(1, report()))
        ps = [p["p"] for p in r["tone"]["points"]]
        assert ps[0] > 0 and ps[-1] < 100 and ps == sorted(ps)

    def test_signs_are_counted_per_sign_over_the_videos(self):
        out = S.compute_sweep_facts(RECORD, self.bundles())
        s1 = next(s for s in out["signs"]["signs"] if s["id"] == "S1")
        assert s1["not_checked"] == 3 and s1["present"] == 0
        assert out["signs"]["disclaimer"] == F.PAID_DISCLAIMER


class TestSetCoverage:
    def rows(self, levels):
        return [{"n": i + 1, "analysed": True, "coverage": lv, "coverage_failed": []}
                for i, lv in enumerate(levels)]

    @pytest.mark.parametrize("levels,level", [
        (["well_covered"] * 3, "well_covered"),
        (["well_covered"] * 3 + ["thinly_covered"], "partly_covered"),
        (["well_covered"] * 2 + ["thinly_covered"] * 2, "thinly_covered"),
        (["well_covered"] * 2, "thinly_covered"),
        (["well_covered", "well_covered", "unknown"], "unknown"),
        (["partly_covered"] * 3, "well_covered"),
    ])
    def test_the_rule(self, levels, level):
        out = S.set_coverage(self.rows(levels))
        assert out["level"] == level
        assert out["ceiling"] is F.CEILING


# ── themes across the videos ─────────────────────────────────────────────────

def written_bundle(n, claims, topics, tags, comments_labels):
    rep = report(comments=())
    rep["all_comments"] = [{"text": f"c{i}", "label": lab, "confidence": 0.8}
                           for i, lab in enumerate(comments_labels)]
    analysis = {"status": "complete", "facts": F.compute_facts(rep),
                "written": {"verdict": {"text": "x", "source": "model"}},
                "reading": {"claims": claims, "topics": topics,
                            "comment_tags": {str(i): v for i, v in tags.items()}, "questions": []}}
    return bundle(n, rep, analysis=analysis)


def topic(tid, name, aspects, seconds=None, examples=()):
    return {"id": tid, "name": name, "aspects": aspects,
            "reviewer": {"seconds": seconds or {"POSITIVE": 10.0, "NEUTRAL": 0.0, "NEGATIVE": 0.0}},
            "audience": {"examples": list(examples)}}


def claim(seg_id, stance, tid, start=0.0):
    return {"seg": seg_id, "time": "0:00", "start": start, "aspect": "x", "stance": stance,
            "claim": f"A {stance} claim", "quote": f"quote for {stance}", "topic": tid}


class TestThemeMatrix:
    def test_two_topics_of_one_video_are_a_union_not_a_double_count(self):
        b = written_bundle(1,
                           claims=[claim(1, "praise", "T0"), claim(2, "praise", "T1")],
                           topics=[topic("T0", "Battery", ["battery"]), topic("T1", "Charging", ["charging"])],
                           tags={0: ["Battery", "Charging"], 1: ["Battery"], 2: []},
                           comments_labels=["POSITIVE", "NEGATIVE", "POSITIVE"])
        [row_] = S.theme_matrix([{"id": "H0", "name": "Battery", "refs": ["V1T0", "V1T1"]}], [b])
        cell = row_["cells"][0]
        assert cell["claims"]["praise"] == 2 and cell["stance"] == "praise"
        assert cell["audience"]["comments"] == 2          # comment 0 once, not twice
        assert cell["audience"]["counts"] == {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": 1}
        assert cell["seconds"]["POSITIVE"] == pytest.approx(20.0)
        assert row_["aspects"] == ["battery", "charging"]

    def test_row_counts_labels_and_the_dissenter(self):
        praising = [written_bundle(n, [claim(1, "praise", "T0")], [topic("T0", "Screen", ["screen"])],
                                   {0: ["Screen"]}, ["POSITIVE"]) for n in (1, 2, 3)]
        critic = written_bundle(4, [claim(1, "criticism", "T0")], [topic("T0", "Display", ["display"])],
                                {0: ["Display"]}, ["NEGATIVE"])
        refs = ["V1T0", "V2T0", "V3T0", "V4T0"]
        [r] = S.theme_matrix([{"id": "H0", "name": "Screen", "refs": refs}], praising + [critic])
        assert (r["reviewer"]["praise_in"], r["reviewer"]["criticism_in"]) == (3, 1)
        assert r["reviewer"]["label"] == "mostly" and r["reviewer"]["side"] == "praise"
        assert r["odd"] == {"n": 4, "stance": "criticism"}

    def test_pushback_is_a_reviewer_praising_what_the_comments_lean_against(self):
        b = written_bundle(1, [claim(1, "praise", "T0")], [topic("T0", "Price", ["price"])],
                           {i: ["Price"] for i in range(6)}, ["NEGATIVE"] * 6)
        [r] = S.theme_matrix([{"id": "H0", "name": "Price", "refs": ["V1T0"]}], [b])
        assert r["cells"][0]["audience"]["call"] == "negative" and r["pushback"] == [1]

    def test_a_video_without_a_written_report_is_not_silent_but_not_written(self):
        b1 = written_bundle(1, [claim(1, "praise", "T0")], [topic("T0", "Fit", ["fit"])], {}, [])
        b2 = bundle(2, report())
        [r] = S.theme_matrix([{"id": "H0", "name": "Fit", "refs": ["V1T0"]}], [b1, b2])
        assert r["cells"][1] == {"n": 2, "status": "not_written"}
        assert r["reviewer"]["talked"] == 1

    def test_a_quote_matching_the_cell_stance_is_chosen(self):
        b = written_bundle(1, [claim(1, "neutral", "T0", 1.0), claim(2, "criticism", "T0", 5.0),
                               claim(3, "criticism", "T0", 3.0)],
                           [topic("T0", "Fit", ["fit"])], {}, [])
        [r] = S.theme_matrix([{"id": "H0", "name": "Fit", "refs": ["V1T0"]}], [b])
        assert r["cells"][0]["quote"]["seg"] == 3

    def test_an_out_of_range_comment_index_is_ignored_not_raised(self):
        b = written_bundle(1, [], [topic("T0", "Fit", ["fit"])], {0: ["Fit"], 50: ["Fit"]}, ["POSITIVE"])
        [r] = S.theme_matrix([{"id": "H0", "name": "Fit", "refs": ["V1T0"]}], [b])
        assert r["cells"][0]["audience"]["comments"] == 1


# ── two periods ──────────────────────────────────────────────────────────────

def sweep_record(sid, after, before=None, finished=None, window="month"):
    return {"sweep_id": sid, "window": window, "offset_days": 0, "controller": "llama3.1:8b",
            "finished_at": finished, "selection": {"published_after": after, "published_before": before}}


def vrow(n, vid, r, a, auth, bh, label="POSITIVE", rc="positive", ac="balanced"):
    return {"n": n, "video_id": vid, "title": vid, "analysed": True,
            "reviewer": {"lean": r, "call": rc}, "audience": {"lean": a, "call": ac},
            "scores": {"authenticity": auth, "brand_health": bh},
            "comments": {"label": label, "distribution": {}, "read": 100}, "near_tie": {"near_tie": True}}


class TestPeriods:
    def test_a_month_inside_six_months_is_nested_and_overlapping(self):
        a = S.window_of(sweep_record("a", "2026-08-20T00:00:00Z", finished=1789820000.0))
        b = S.window_of(sweep_record("b", "2026-03-21T00:00:00Z", finished=1789830000.0))
        o = S.windows_overlap(a, b)
        assert o["nested"] is True and o["disjoint"] is False and o["overlap_days"] > 29
        assert a["end_is_run_time"] is True

    def test_an_earlier_period_is_disjoint(self):
        a = S.window_of(sweep_record("a", "2026-08-20T00:00:00Z", "2026-09-19T00:00:00Z"))
        b = S.window_of(sweep_record("b", "2026-02-20T00:00:00Z", "2026-03-22T00:00:00Z"))
        o = S.windows_overlap(a, b)
        assert o == {"known": True, "overlap_days": 0.0, "nested": False, "disjoint": True}
        assert a["end_is_run_time"] is False

    def test_unknown_dates_say_so(self):
        o = S.windows_overlap(S.window_of({}), S.window_of({}))
        assert o["known"] is False and o["nested"] is None

    def test_the_same_video_read_twice(self):
        a_rows = [vrow(1, "L8CswTQyuMw", 0.312, 0.04, 53.36, 79.29, "POSITIVE"),
                  vrow(2, "only_in_a__", 0.1, 0.0, 50.0, 50.0)]
        b_rows = [vrow(1, "L8CswTQyuMw", 0.312, -0.03, 39.89, 15.96, "NEGATIVE"),
                  vrow(2, "only_in_b__", 0.2, 0.1, 60.0, 60.0)]
        p = S.period_facts(sweep_record("a", None), a_rows, sweep_record("b", None), b_rows)
        sh = p["shared"]
        assert sh["n"] == 1 and sh["calls_unchanged"] == 1
        assert sh["max_delta"]["brand_health"] == pytest.approx(63.33)
        assert sh["max_delta"]["audience"] == pytest.approx(0.07)
        assert sh["videos"][0]["label_changed"] is True
        assert [x["title"] for x in p["only_a"]] == ["only_in_a__"]
        bh = next(m for m in p["measures"] if m["key"] == "brand_health")
        assert bh["read_twice"] == pytest.approx(63.33)

    @pytest.mark.parametrize("a_vals,b_vals,call", [
        ([0.1, 0.2], [0.3, 0.4], "moved"),
        ([0.1, 0.35], [0.3, 0.4], "within_spread"),
        ([0.1], [0.3, 0.4], "too_few"),
    ])
    def test_a_change_is_called_only_when_the_ranges_part(self, a_vals, b_vals, call):
        a_rows = [vrow(i + 1, f"a{i}", v, 0.0, 50, 50) for i, v in enumerate(a_vals)]
        b_rows = [vrow(i + 1, f"b{i}", v, 0.0, 50, 50) for i, v in enumerate(b_vals)]
        p = S.period_facts(sweep_record("a", None), a_rows, sweep_record("b", None), b_rows)
        rev = next(m for m in p["measures"] if m["key"] == "reviewer")
        assert rev["call"] == call

    def test_themes_match_by_name_then_by_aspects(self):
        a = [{"name": "The battery", "aspects": ["battery"]}, {"name": "Screen", "aspects": ["display", "screen"]},
             {"name": "Price", "aspects": ["price"]}]
        b = [{"name": "Display", "aspects": ["screen", "display", "brightness"]},
             {"name": "Battery", "aspects": ["charging"]}, {"name": "Camera", "aspects": ["camera"]}]
        assert S.align_themes(a, b) == [(0, 1), (1, 0)]

    def test_theme_changes_are_reported_when_both_are_written(self):
        t = lambda name, p: {"id": "H0", "name": name, "aspects": [name.lower()], "cells": [{}, {}],
                             "reviewer": {"talked": 2, "praise_in": p, "criticism_in": 2 - p, "label": "split"}}
        p = S.period_facts(sweep_record("a", None), [], sweep_record("b", None), [],
                           [t("Battery", 1), t("Price", 0)], [t("Battery", 2), t("Camera", 2)])
        th = p["themes"]
        assert [(m["a"]["praise_in"], m["b"]["praise_in"]) for m in th["matched"]] == [(1, 2)]
        assert [x["name"] for x in th["only_a"]] == ["Price"]
        assert [x["name"] for x in th["only_b"]] == ["Camera"]

    def test_without_both_written_reports_there_are_no_theme_changes(self):
        p = S.period_facts(sweep_record("a", None), [], sweep_record("b", None), [])
        assert p["themes"] is None
        json.dumps(p)
