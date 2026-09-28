"""
test_sweep.py — choosing five videos, and combining five reports into one.

Written 19 Sep 2026 with `sweep.py`.

Scope: the judgement in a sweep. Which videos are offered, which are refused and
for what stated reason, and what a combined score is allowed to claim.

The searching tests use a fake YouTube client built from the shapes the real API
actually returned on 19 Sep 2026 — including the awkward ones that decided the
design: a Hindi video with an English title, a video with comments disabled
(`statistics` carrying no `commentCount` at all rather than a zero), and a
competitor comparison whose title names both brands. Nothing here touches the
network.

The rule under test throughout is the one `sweep.py` is built on: a candidate is
never silently dropped. Every video that comes back from the API comes back from
`search_candidates` too, carrying the reason it was kept or refused.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pipeline import sweep


NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)


# ── A fake API, shaped like the real one ─────────────────────────────────────

def _video(video_id, title, *, channel="A Channel", language="en",
           comments=500, duration="PT12M30S", views=100_000,
           published="2026-09-15T10:00:00Z", comments_off=False):
    statistics = {"viewCount": str(views)}
    if not comments_off:
        statistics["commentCount"] = str(comments)
    return {
        "id": video_id,
        "snippet": {"title": title, "channelTitle": channel,
                    "publishedAt": published, "defaultAudioLanguage": language},
        "contentDetails": {"duration": duration},
        "statistics": statistics,
    }


class FakeYouTube:
    """Records the kwargs it was called with, so the query itself can be asserted."""

    def __init__(self, videos):
        self._videos = videos
        self.search_kwargs = None
        self.videos_kwargs = None

    def search(self):
        outer = self

        class _Search:
            def list(self, **kwargs):
                outer.search_kwargs = kwargs

                class _Req:
                    def execute(self):
                        return {"items": [{"id": {"videoId": v["id"]}}
                                          for v in outer._videos]}
                return _Req()
        return _Search()

    def videos(self):
        outer = self

        class _Videos:
            def list(self, **kwargs):
                outer.videos_kwargs = kwargs
                wanted = set(kwargs.get("id", "").split(","))

                class _Req:
                    def execute(self):
                        return {"items": [v for v in outer._videos if v["id"] in wanted]}
                return _Req()
        return _Videos()


@pytest.fixture
def corpus():
    """The mix the live API actually returns for a brand query."""
    return [
        _video("aaaaaaaaaaa", "Samsung Galaxy S26 FE Review: Don't Buy It... Yet!", comments=97),
        _video("bbbbbbbbbbb", "Samsung Galaxy S26 FE - What Really Changed?", comments=894),
        _video("ccccccccccc", "Samsung Galaxy S26 FE review: No longer the Fan Edition?",
               comments=172),
        _video("ddddddddddd", "Samsung Galaxy S26 Ultra long-term", comments=310),
        _video("eeeeeeeeeee", "Samsung Galaxy A27 Review: Budget Isn't Bad", comments=12),
        _video("fffffffffff", "Samsung Galaxy S26 FE Unboxing", language="hi", comments=2200),
        _video("ggggggggggg", "Galaxy Z Fold 8 After 30 days - I Was Wrong", comments=139),
        _video("hhhhhhhhhhh", "Samsung S26 first look", comments_off=True),
        _video("iiiiiiiiiii", "Samsung Galaxy S26 review in 60 seconds", duration="PT1M2S"),
        _video("jjjjjjjjjjj", "Samsung Galaxy S26 Ultra review", comments=640),
    ]


# ── Windows ──────────────────────────────────────────────────────────────────

class TestWindows:
    def test_the_four_offered_windows_are_the_four_defined(self):
        assert set(sweep.WINDOWS) == {"week", "month", "half", "year"}

    def test_a_window_runs_back_from_now_and_has_no_upper_bound(self):
        after, before = sweep.window_bounds("month", now=NOW)
        assert after == "2026-08-20T12:00:00Z"
        assert before is None

    def test_an_unknown_window_is_refused_rather_than_defaulted(self):
        with pytest.raises(ValueError, match="unknown window"):
            sweep.window_bounds("fortnight", now=NOW)

    def test_an_offset_window_keeps_the_same_width(self):
        """
        'Six months ago' has to be a slice as wide as 'the last 6 months', or
        the comparison view puts one width beside another and calls it a change.
        """
        after, before = sweep.offset_window_bounds("half", 182, now=NOW)
        span = (datetime.strptime(before, "%Y-%m-%dT%H:%M:%SZ")
                - datetime.strptime(after, "%Y-%m-%dT%H:%M:%SZ"))
        assert span == timedelta(days=sweep.WINDOWS["half"])
        assert before == "2026-03-21T12:00:00Z"


class TestHowFarBackAWindowMayEnd:
    """
    A window may end at most one window-length back (24 Sep 2026). "Last
    week, ending a year ago" was accepted before, and the author reported it as
    a pairing that does not mean anything.
    """

    @pytest.mark.parametrize("window", sorted(sweep.WINDOWS))
    def test_today_and_exactly_one_window_back_are_allowed(self, window):
        assert sweep.offset_problem(window, 0) is None
        assert sweep.offset_problem(window, sweep.WINDOWS[window]) is None

    @pytest.mark.parametrize("window", sorted(sweep.WINDOWS))
    def test_one_day_past_one_window_back_is_refused(self, window):
        problem = sweep.offset_problem(window, sweep.WINDOWS[window] + 1)
        assert problem and f"at most {sweep.WINDOWS[window]} days" in problem

    @pytest.mark.parametrize("window", sorted(sweep.WINDOWS))
    def test_an_ending_in_the_future_is_refused(self, window):
        assert sweep.offset_problem(window, -1)

    def test_the_reported_case_a_week_ending_a_year_ago_is_refused(self):
        assert sweep.offset_problem("week", 365)
        with pytest.raises(ValueError, match="at most 7 days"):
            sweep.offset_window_bounds("week", 365, now=NOW)

    def test_a_week_can_still_be_held_against_the_week_before(self):
        after, before = sweep.offset_window_bounds("week", 7, now=NOW)
        assert (after, before) == ("2026-09-05T12:00:00Z", "2026-09-12T12:00:00Z")
        # ...which ends exactly where "last week" begins: no day in common.
        assert before == sweep.window_bounds("week", now=NOW)[0]

    def test_an_unknown_window_is_a_problem_not_a_crash(self):
        assert "unknown window" in sweep.offset_problem("fortnight", 0)


class TestDurations:
    @pytest.mark.parametrize("iso,seconds", [
        ("PT13M34S", 814), ("PT1H2M3S", 3723), ("PT45S", 45),
        ("PT16M", 960), ("PT2H", 7200),
    ])
    def test_iso_durations_parse(self, iso, seconds):
        assert sweep.parse_duration(iso) == seconds

    @pytest.mark.parametrize("bad", ["", None, "13:34", "banana", "P3D"])
    def test_an_unparseable_duration_is_zero_not_an_exception(self, bad):
        """It should cost that video its place, not sink the whole search."""
        assert sweep.parse_duration(bad) == 0


# ── The query ────────────────────────────────────────────────────────────────

class TestTheQuery:
    def test_the_subject_is_augmented_because_a_bare_brand_returns_news(self):
        """Measured 19 Sep 2026: q='Apple' returned Fox and NDTV news clips."""
        assert sweep.build_query("Samsung") == "Samsung review"

    def test_a_subject_that_already_says_review_is_not_doubled(self):
        assert sweep.build_query("iPhone 18 review") == "iPhone 18 review"

    def test_whitespace_is_collapsed(self):
        assert sweep.build_query("  iPhone   18 Pro  ") == "iPhone 18 Pro review"

    def test_an_empty_subject_is_refused(self):
        with pytest.raises(ValueError):
            sweep.build_query("   ")


# ── Judging one video ────────────────────────────────────────────────────────

class TestVerdicts:
    def test_a_good_video_passes(self):
        assert sweep.verdict_for(
            {"language": "en", "comment_count": 500, "duration_s": 700,
             "title": "Samsung Galaxy S26 review"}, "Samsung") == "ok"

    @pytest.mark.parametrize("lang", ["hi", "ta", "ml", "fil"])
    def test_a_non_english_video_is_refused_and_names_the_language(self, lang):
        """
        The pipeline is Whisper plus English-tuned sentiment, and a non-English
        transcript is a listed failure path. relevanceLanguage does not filter.
        """
        verdict = sweep.verdict_for(
            {"language": lang, "comment_count": 500, "duration_s": 700,
             "title": "Samsung review"}, "Samsung")
        assert verdict == f"not English ({lang})"

    def test_en_gb_and_en_us_both_count_as_english(self):
        for lang in ("en", "en-GB", "en-US"):
            assert sweep.verdict_for(
                {"language": lang, "comment_count": 500, "duration_s": 700,
                 "title": "Samsung review"}, "Samsung") == "ok"

    def test_an_undeclared_language_is_refused_rather_than_assumed_english(self):
        assert sweep.verdict_for(
            {"language": "", "comment_count": 500, "duration_s": 700,
             "title": "Samsung review"}, "Samsung") == "language not declared"

    def test_comments_off_is_distinct_from_too_few_comments(self):
        """They are different failures and the reader is told which."""
        off = sweep.verdict_for(
            {"language": "en", "comment_count": 0, "duration_s": 700,
             "title": "Samsung review"}, "Samsung")
        few = sweep.verdict_for(
            {"language": "en", "comment_count": 12, "duration_s": 700,
             "title": "Samsung review"}, "Samsung")
        assert off == "comments are off"
        assert few == "only 12 comments"

    @pytest.mark.parametrize("seconds,fragment", [(62, "too short"), (4000, "too long")])
    def test_duration_is_bounded_at_both_ends(self, seconds, fragment):
        verdict = sweep.verdict_for(
            {"language": "en", "comment_count": 500, "duration_s": seconds,
             "title": "Samsung review"}, "Samsung")
        assert verdict.startswith(fragment)

    def test_a_title_that_does_not_name_the_subject_is_flagged_not_dropped(self):
        """
        Measured: 'Galaxy Z Fold 8 After 30 days' is a Samsung video that never
        says Samsung. The reader overrules this one, which is why it is a
        verdict rather than a filter.
        """
        assert sweep.verdict_for(
            {"language": "en", "comment_count": 139, "duration_s": 700,
             "title": "Galaxy Z Fold 8 After 30 days - I Was Wrong"},
            "Samsung") == "subject not named in the title"

    def test_short_subject_words_do_not_match_everything(self):
        """'Pro' in 'iPhone 18 Pro Max' would otherwise admit any title with Pro."""
        assert sweep.verdict_for(
            {"language": "en", "comment_count": 500, "duration_s": 700,
             "title": "The Pro camera bag I use"}, "iPhone 18 Pro Max") \
            == "subject not named in the title"

    def test_a_competitor_comparison_passes_because_it_names_the_subject(self):
        """
        'iPhone 18 Pro Max vs Samsung Galaxy S26 Ultra' is real, and whether it
        is Samsung signal is a judgement no rule here can make. It is offered,
        visibly, for a person to decide.
        """
        assert sweep.verdict_for(
            {"language": "en", "comment_count": 953, "duration_s": 900,
             "title": "iPhone 18 Pro Max vs Samsung Galaxy S26 Ultra Camera Test"},
            "Samsung") == "ok"


# ── Searching ────────────────────────────────────────────────────────────────

class TestSearching:
    def test_every_candidate_comes_back_judged_and_none_is_dropped(self, corpus):
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(corpus),
                                         now=NOW)
        assert len(result["candidates"]) == len(corpus)
        assert all(c["verdict"] for c in result["candidates"])

    def test_relevance_order_is_preserved(self, corpus):
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(corpus),
                                         now=NOW)
        assert [c["video_id"] for c in result["candidates"]] == [v["id"] for v in corpus]

    def test_five_eligible_videos_are_suggested(self, corpus):
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(corpus),
                                         now=NOW)
        assert len(result["suggested"]) == sweep.SWEEP_SIZE
        chosen = {c["video_id"] for c in result["candidates"] if c["suggested"]}
        assert chosen == set(result["suggested"])

    def test_nothing_refused_is_ever_suggested(self, corpus):
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(corpus),
                                         now=NOW)
        for candidate in result["candidates"]:
            if candidate["suggested"]:
                assert candidate["verdict"] == "ok"

    def test_the_query_actually_sent_is_reported(self, corpus):
        """The reader typed 'Samsung'; they are owed what was searched."""
        fake = FakeYouTube(corpus)
        result = sweep.search_candidates("Samsung", "month", client=fake, now=NOW)
        assert result["query_used"] == "Samsung review"
        assert fake.search_kwargs["q"] == "Samsung review"

    def test_the_search_is_ordered_by_relevance_not_views(self, corpus):
        """Views order returns old viral videos and defeats the time window."""
        fake = FakeYouTube(corpus)
        sweep.search_candidates("Samsung", "month", client=fake, now=NOW)
        assert fake.search_kwargs["order"] == "relevance"

    def test_the_window_is_passed_to_the_api(self, corpus):
        fake = FakeYouTube(corpus)
        sweep.search_candidates("Samsung", "week", client=fake, now=NOW)
        assert fake.search_kwargs["publishedAfter"] == "2026-09-12T12:00:00Z"
        assert "publishedBefore" not in fake.search_kwargs

    def test_an_offset_search_bounds_both_ends(self, corpus):
        fake = FakeYouTube(corpus)
        sweep.search_candidates("Samsung", "month", offset_days=30,
                                client=fake, now=NOW)
        assert fake.search_kwargs["publishedAfter"] == "2026-07-21T12:00:00Z"
        assert fake.search_kwargs["publishedBefore"] == "2026-08-20T12:00:00Z"

    def test_language_and_comment_count_are_requested(self, corpus):
        """
        Neither is available from search.list. Without the second call the
        language filter cannot run at all.
        """
        fake = FakeYouTube(corpus)
        sweep.search_candidates("Samsung", "month", client=fake, now=NOW)
        assert "snippet" in fake.videos_kwargs["part"]
        assert "statistics" in fake.videos_kwargs["part"]
        assert "contentDetails" in fake.videos_kwargs["part"]

    def test_comments_disabled_reads_as_off_not_as_zero_comments(self, corpus):
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(corpus),
                                         now=NOW)
        entry = next(c for c in result["candidates"] if c["video_id"] == "hhhhhhhhhhh")
        assert entry["verdict"] == "comments are off"

    def test_a_video_deleted_between_the_two_calls_is_skipped_not_fatal(self, corpus):
        class Vanishing(FakeYouTube):
            def videos(self):
                outer = self

                class _Videos:
                    def list(self, **kwargs):
                        outer.videos_kwargs = kwargs

                        class _Req:
                            def execute(self):
                                return {"items": outer._videos[1:]}   # first is gone
                        return _Req()
                return _Videos()

        result = sweep.search_candidates("Samsung", "month", client=Vanishing(corpus),
                                         now=NOW)
        assert len(result["candidates"]) == len(corpus) - 1

    def test_an_empty_result_does_not_call_videos_list_or_raise(self):
        fake = FakeYouTube([])
        result = sweep.search_candidates("Samsung", "month", client=fake, now=NOW)
        assert result["candidates"] == []
        assert result["suggested"] == []
        assert result["eligible"] == 0
        assert fake.videos_kwargs is None, "spent a quota unit on nothing"

    def test_fewer_than_five_eligible_suggests_what_there_is(self):
        thin = [_video("aaaaaaaaaaa", "Samsung review one", comments=400),
                _video("bbbbbbbbbbb", "Samsung review two", comments=400),
                _video("ccccccccccc", "Samsung unboxing", language="hi")]
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(thin),
                                         now=NOW)
        assert len(result["suggested"]) == 2
        assert result["eligible"] == 2


# ── Details by id, for a start that did not carry them ──────────────────────

class TestLookingUpDetailsById:
    def test_one_call_returns_what_the_search_would_have(self, corpus):
        fake = FakeYouTube(corpus)
        found = sweep.video_details(["aaaaaaaaaaa", "hhhhhhhhhhh"], client=fake)
        assert fake.search_kwargs is None, "a search is 100 quota units; this needs none"
        assert fake.videos_kwargs["id"] == "aaaaaaaaaaa,hhhhhhhhhhh"
        a = found["aaaaaaaaaaa"]
        assert a["title"] == "Samsung Galaxy S26 FE Review: Don't Buy It... Yet!"
        assert (a["channel"], a["duration_s"], a["comment_count"]) == ("A Channel", 750, 97)
        assert found["hhhhhhhhhhh"]["comment_count"] == 0, "comments off reads as none"

    def test_the_search_and_the_lookup_describe_a_video_identically(self, corpus):
        result = sweep.search_candidates("Samsung", "month", client=FakeYouTube(corpus), now=NOW)
        found = sweep.video_details([v["id"] for v in corpus], client=FakeYouTube(corpus))
        for candidate in result["candidates"]:
            mine = found[candidate["video_id"]]
            assert {k: candidate[k] for k in mine} == mine

    def test_a_removed_video_is_absent_rather_than_an_error(self, corpus):
        found = sweep.video_details(["aaaaaaaaaaa", "zzzzzzzzzzz"], client=FakeYouTube(corpus))
        assert set(found) == {"aaaaaaaaaaa"}

    def test_the_same_id_twice_is_asked_for_once(self, corpus):
        fake = FakeYouTube(corpus)
        sweep.video_details(["aaaaaaaaaaa", "aaaaaaaaaaa"], client=fake)
        assert fake.videos_kwargs["id"] == "aaaaaaaaaaa"

    def test_no_ids_make_no_call(self):
        class Refuses:
            def videos(self):
                raise AssertionError("called YouTube with nothing to ask")

        assert sweep.video_details([], client=Refuses()) == {}

    def test_without_a_key_it_raises_for_the_caller_to_degrade(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        with pytest.raises(EnvironmentError):
            sweep.video_details(["aaaaaaaaaaa"])


class TestFillingBlankDetails:
    def test_only_blanks_are_filled_and_a_recorded_title_wins(self):
        entries = [{"video_id": "a", "title": "", "channel": "", "duration_s": 0},
                   {"video_id": "b", "title": "As searched", "channel": ""}]
        found = {"a": {"title": "A", "channel": "Ca", "duration_s": 60},
                 "b": {"title": "Renamed since", "channel": "Cb"}}
        assert sweep.fill_blank_details(entries, found) == ["a", "b"]
        assert entries[0] == {"video_id": "a", "title": "A", "channel": "Ca", "duration_s": 60}
        assert entries[1] == {"video_id": "b", "title": "As searched", "channel": "Cb"}, \
            "what the person read before choosing is what the record keeps"

    def test_nothing_found_changes_nothing(self):
        entries = [{"video_id": "a", "title": ""}]
        assert sweep.fill_blank_details(entries, {}) == []
        assert sweep.fill_blank_details(entries, {"a": {"title": ""}}) == []
        assert entries == [{"video_id": "a", "title": ""}]

    def test_only_the_recorded_fields_are_copied(self):
        entries = [{"video_id": "a"}]
        sweep.fill_blank_details(entries, {"a": {"title": "A", "verdict": "ok", "view_count": 9,
                                                 "authenticity_score": 99.0}})
        assert entries == [{"video_id": "a", "title": "A"}]


# ── Combining ────────────────────────────────────────────────────────────────

def _report(auth, health, *, segments=10, flagged=2, comments=100, dist=None):
    return {
        "authenticity_score": auth,
        "brand_health_score": health,
        "all_segments": [{"segment_id": i} for i in range(segments)],
        "flagged_segments": [{"segment_id": i} for i in range(flagged)],
        "all_comments": [{"text": "x"} for _ in range(comments)],
        "comment_sentiment": {"distribution": dist or {"POSITIVE": 60, "NEUTRAL": 30,
                                                       "NEGATIVE": 10}},
    }


class TestCombining:
    def test_the_mean_and_the_range_are_both_reported(self):
        out = sweep.aggregate([_report(20, 50), _report(80, 50), _report(50, 50)])
        assert out["authenticity"]["mean"] == 50.0
        assert out["authenticity"]["min"] == 20.0
        assert out["authenticity"]["max"] == 80.0
        assert out["authenticity"]["spread"] == 60.0

    def test_the_same_mean_from_a_different_spread_reads_differently(self):
        """
        The reason the spread is reported at all: these two average identically
        and mean entirely different things.
        """
        tight = sweep.aggregate([_report(v, 50) for v in (48, 49, 50, 51, 52)])
        wide = sweep.aggregate([_report(v, 50) for v in (10, 30, 50, 70, 90)])
        assert tight["authenticity"]["mean"] == wide["authenticity"]["mean"]
        assert tight["spread_verdict"] != wide["spread_verdict"]

    def test_every_member_value_is_carried_so_the_reader_can_see_all_five(self):
        out = sweep.aggregate([_report(v, 50) for v in (10, 30, 50, 70, 90)])
        assert out["authenticity"]["values"] == [10.0, 30.0, 50.0, 70.0, 90.0]

    def test_the_combined_score_says_what_it_is_not(self):
        """
        baseline_bench measured no system on this corpus tracking human
        authenticity judgement. A combined number that travels without that
        caveat is the misreading this project spends a chapter warning about.
        """
        out = sweep.aggregate([_report(50, 50)])
        assert "not a measure of whether the brand is liked" in out["means_not"].lower()

    def test_the_sample_size_is_stated(self):
        out = sweep.aggregate([_report(50, 50), _report(60, 60)])
        assert "2 videos" in out["note"]

    def test_totals_are_summed_across_members(self):
        out = sweep.aggregate([_report(50, 50, segments=10, flagged=2, comments=100),
                               _report(60, 60, segments=30, flagged=4, comments=250)])
        assert out["segments_total"] == 40
        assert out["flagged_total"] == 6
        assert out["comments_total"] == 350
        assert out["flagged_share"] == pytest.approx(6 / 40)

    def test_comment_distributions_are_pooled(self):
        out = sweep.aggregate([
            _report(50, 50, dist={"POSITIVE": 10, "NEGATIVE": 5}),
            _report(60, 60, dist={"POSITIVE": 20, "NEUTRAL": 7}),
        ])
        assert out["comment_distribution"] == {"POSITIVE": 30, "NEGATIVE": 5, "NEUTRAL": 7}

    def test_a_member_missing_a_score_does_not_sink_the_aggregate(self):
        """One degraded member must not cost the other four their summary."""
        broken = _report(50, 50)
        del broken["authenticity_score"]
        out = sweep.aggregate([broken, _report(60, 60), _report(70, 70)])
        assert out["authenticity"]["values"] == [60.0, 70.0]
        assert out["brand_health"]["values"] == [50.0, 60.0, 70.0]

    def test_no_members_returns_nulls_rather_than_zero(self):
        """Zero is a measurement. Nothing measured is not."""
        out = sweep.aggregate([])
        assert out["video_count"] == 0
        assert out["authenticity"]["mean"] is None
        assert out["authenticity"]["values"] == []

    def test_one_member_has_no_spread_to_describe(self):
        out = sweep.aggregate([_report(50, 50)])
        assert out["authenticity"]["spread"] == 0
        assert "nothing to agree or disagree about" in out["spread_verdict"]


# ── The search route ─────────────────────────────────────────────────────────

class TestTheSearchRoute:
    """
    POST /sweep/search. Validation, and the shape of every failure.

    `sweep.search_candidates` is patched out throughout: what it does is tested
    above, and these are about what the route does with it. Nothing here reaches
    the network or spends quota.
    """

    @pytest.fixture
    def client(self):
        import app as app_module
        app_module.app.config.update(TESTING=True)
        return app_module.app.test_client()

    @pytest.fixture
    def stub(self, monkeypatch):
        """Records the arguments the route passed through."""
        import app as app_module
        calls = []

        def fake(subject, window, *, offset_days=0, **kwargs):
            calls.append({"subject": subject, "window": window,
                          "offset_days": offset_days})
            return {"subject": subject, "query_used": f"{subject} review",
                    "window": window, "offset_days": offset_days,
                    "published_after": "2026-08-20T12:00:00Z",
                    "published_before": None,
                    "candidates": [], "suggested": [], "eligible": 0}

        monkeypatch.setattr(app_module.sweep, "search_candidates", fake)
        return calls

    def test_a_search_returns_the_candidates_and_the_query_used(self, client, stub):
        response = client.post("/sweep/search",
                               json={"subject": "Samsung", "window": "month"})
        assert response.status_code == 200
        body = response.get_json()
        assert body["query_used"] == "Samsung review"
        assert "candidates" in body and "suggested" in body

    def test_the_window_defaults_to_month_rather_than_failing(self, client, stub):
        assert client.post("/sweep/search", json={"subject": "Samsung"}).status_code == 200
        assert stub[0]["window"] == "month"

    def test_a_missing_subject_is_refused(self, client, stub):
        response = client.post("/sweep/search", json={"window": "month"})
        assert response.status_code == 400
        assert "subject" in response.get_json()["error"]

    def test_a_blank_subject_is_refused(self, client, stub):
        assert client.post("/sweep/search", json={"subject": "   "}).status_code == 400

    def test_an_absurdly_long_subject_is_refused(self, client, stub):
        response = client.post("/sweep/search", json={"subject": "x" * 500})
        assert response.status_code == 400

    def test_an_unknown_window_is_refused_and_names_the_valid_ones(self, client, stub):
        response = client.post("/sweep/search",
                               json={"subject": "Samsung", "window": "fortnight"})
        assert response.status_code == 400
        error = response.get_json()["error"]
        for window in sweep.WINDOWS:
            assert window in error

    def test_the_offset_is_passed_through_for_the_comparison_view(self, client, stub):
        client.post("/sweep/search", json={"subject": "Samsung", "window": "half",
                                           "offset_days": 182})
        assert stub[0]["offset_days"] == 182

    @pytest.mark.parametrize("bad", ["soon", -5, 99999])
    def test_a_nonsense_offset_is_refused(self, client, stub, bad):
        response = client.post("/sweep/search",
                               json={"subject": "Samsung", "offset_days": bad})
        assert response.status_code == 400

    def test_an_ending_further_back_than_the_window_is_refused_before_any_search(
        self, client, stub
    ):
        """The reported case. Refused at the route, so no quota is spent on it."""
        response = client.post("/sweep/search", json={"subject": "Samsung", "window": "week",
                                                      "offset_days": 365})
        assert response.status_code == 400
        assert "at most 7 days" in response.get_json()["error"]
        assert stub == []

    def test_a_week_ending_a_week_ago_is_searched(self, client, stub):
        response = client.post("/sweep/search", json={"subject": "Samsung", "window": "week",
                                                      "offset_days": 7})
        assert response.status_code == 200
        assert stub[0]["offset_days"] == 7

    def test_a_missing_api_key_reads_as_unavailable_not_as_a_bad_request(
        self, client, monkeypatch
    ):
        """
        503, because the caller's request was fine and the machine is not
        configured. A 400 would send a reader looking for a typo.
        """
        import app as app_module

        def boom(*a, **k):
            raise EnvironmentError("YOUTUBE_API_KEY environment variable is not set.")

        monkeypatch.setattr(app_module.sweep, "search_candidates", boom)
        response = client.post("/sweep/search", json={"subject": "Samsung"})
        assert response.status_code == 503
        assert "YOUTUBE_API_KEY" in response.get_json()["error"]

    def test_a_quota_failure_reads_as_upstream_and_keeps_its_type(
        self, client, monkeypatch
    ):
        import app as app_module

        class QuotaExceeded(RuntimeError):
            pass

        def boom(*a, **k):
            raise QuotaExceeded("quota exceeded")

        monkeypatch.setattr(app_module.sweep, "search_candidates", boom)
        response = client.post("/sweep/search", json={"subject": "Samsung"})
        assert response.status_code == 502
        assert response.get_json()["detail"] == "QuotaExceeded"

    def test_searching_starts_nothing_and_writes_nothing(self, client, stub):
        """
        The whole point of the step: it costs one search and no pipeline. If it
        ever started a job, an hour of CPU would begin before anyone confirmed
        the videos were the right ones.
        """
        import app as app_module
        before = dict(app_module._jobs)
        client.post("/sweep/search", json={"subject": "Samsung"})
        assert dict(app_module._jobs) == before

    def test_another_site_is_not_granted_the_search(self, client):
        # Same-origin only (test_ui_routes.TestNoOtherSiteIsGrantedTheApi).
        response = client.options("/sweep/search", headers={
            "Origin": "https://example.org", "Access-Control-Request-Method": "POST"})
        assert "Access-Control-Allow-Origin" not in response.headers


# ── Storage and ids ──────────────────────────────────────────────────────────

class TestStorage:
    def test_a_sweep_id_is_stable_for_the_same_five_videos(self):
        """
        Stability is what makes a sweep resumable: the same five videos must
        resolve to the same directory, whatever order they were confirmed in.
        """
        a = sweep.sweep_id_for("Samsung", "month", 0, ["aaa", "bbb", "ccc"])
        b = sweep.sweep_id_for("Samsung", "month", 0, ["ccc", "aaa", "bbb"])
        assert a == b

    def test_different_videos_are_a_different_sweep(self):
        a = sweep.sweep_id_for("Samsung", "month", 0, ["aaa", "bbb"])
        b = sweep.sweep_id_for("Samsung", "month", 0, ["aaa", "zzz"])
        assert a != b

    def test_the_window_and_offset_are_part_of_the_identity(self):
        base = sweep.sweep_id_for("Samsung", "month", 0, ["aaa"])
        assert sweep.sweep_id_for("Samsung", "week", 0, ["aaa"]) != base
        assert sweep.sweep_id_for("Samsung", "month", 180, ["aaa"]) != base

    def test_the_id_is_readable_before_it_is_unique(self):
        assert sweep.sweep_id_for("iPhone 18 Pro Max", "month", 0, ["aaa"]) \
            .startswith("iphone-18-pro-max-month-")

    @pytest.mark.parametrize("nasty", ["../escape", "a/b", "", ".", "..", "a\\b"])
    def test_a_sweep_id_cannot_escape_the_sweeps_directory(self, nasty):
        with pytest.raises(ValueError):
            sweep.sweep_dir(nasty)

    @pytest.mark.parametrize("nasty", ["../../etc/passwd", "short", "waytoolongforanid"])
    def test_a_member_path_demands_a_real_video_id(self, nasty):
        with pytest.raises(ValueError):
            sweep.member_path("samsung-month-abcd1234", nasty)

    def test_a_write_leaves_no_temporary_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        sweep.write_json(sweep.sweep_path("samsung-month-abcd1234"), {"ok": True})
        assert not list(tmp_path.rglob("*.tmp"))

    def test_an_unreadable_sweep_does_not_empty_the_listing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        sweep.write_json(sweep.sweep_path("good-month-abcd1234"),
                         {"sweep_id": "good-month-abcd1234", "subject": "Good",
                          "finished_at": 2})
        broken = sweep.sweep_dir("bad-month-abcd1234")
        broken.mkdir(parents=True)
        (broken / "sweep.json").write_text("{not json", encoding="utf-8")
        rows = sweep.list_sweeps()
        assert [r["sweep_id"] for r in rows] == ["good-month-abcd1234"]


# ── Running a sweep ──────────────────────────────────────────────────────────

class TestRunningASweep:
    """
    `_run_sweep_job` end to end with the pipeline mocked at app.py's import
    boundary — the same seam `tests/test_app.py` uses. No Ollama, no network, no
    YouTube key, no model weights.
    """

    IDS = ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"]

    @pytest.fixture
    def rig(self, tmp_path, monkeypatch):
        import app as app_module

        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        monkeypatch.setattr(app_module.sweep, "SWEEPS", tmp_path / "sweeps")

        monkeypatch.setattr(app_module, "fetch_comments", lambda *a, **k: [])
        monkeypatch.setattr(app_module, "classify_comment_sentiment", lambda c: [])
        monkeypatch.setattr(app_module, "aggregate_video_sentiment",
                            lambda c: {"label": "POSITIVE", "confidence": 0.9,
                                       "comment_count": 0, "distribution": {}})
        monkeypatch.setattr(app_module, "_build_segments",
                            lambda url, vid: [{"segment_id": 0, "start_time": 0,
                                               "end_time": 5}])
        monkeypatch.setattr(app_module, "run_orchestration",
                            lambda *a, **k: [{"segment_id": 0, "conflict_score": 0.5}])
        monkeypatch.setattr(app_module, "_all_comments", lambda c: [])
        monkeypatch.setattr(app_module, "_enrich_all_segments", lambda s, c: [])
        monkeypatch.setattr(app_module.frame_cache, "warm", lambda r: 0)

        scores = iter([20.0, 50.0, 80.0] * 4)
        monkeypatch.setattr(app_module, "build_final_report",
                            lambda url, brand, seg, conf, cs: {
                                "video_url": url, "brand_name": brand,
                                "authenticity_score": next(scores),
                                "brand_health_score": 60.0,
                                "all_segments": [], "flagged_segments": [],
                                "comment_sentiment": {"distribution": {}},
                            })
        app_module._jobs.clear()
        yield app_module
        app_module._jobs.clear()

    def _selection(self, ids=None, titled=True):
        return [{"video_id": v, "title": f"Video {v[0]}" if titled else ""} for v in (ids or self.IDS)]

    def _start(self, app_module, ids=None, **kw):
        selection = self._selection(ids, titled=kw.get("titled", True))
        sweep_id = sweep.sweep_id_for("Samsung", "month", 0,
                                      [e["video_id"] for e in selection])
        job_id, blocker = app_module._claim_worker({
            "kind": "sweep", "status": "running", "subject": "Samsung",
            "sweep_id": sweep_id, "stage_index": -1, "stage_label": "Queued",
            "total_stages": 4, "video_index": 0, "video_total": len(selection),
            "video_title": "", "done": [], "failed": [],
            "cancel_requested": kw.get("cancel", False),
        })
        assert blocker is None
        app_module._run_sweep_job(job_id, sweep_id, "Samsung", "month", 0,
                                  selection, {"query_used": "Samsung review"}, 100)
        return job_id, sweep_id

    def test_a_clean_sweep_writes_every_member_and_the_combined_record(self, rig):
        job_id, sweep_id = self._start(rig)
        for video_id in self.IDS:
            assert sweep.member_path(sweep_id, video_id).is_file()
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["status"] == "done"
        assert record["summary"]["video_count"] == 3
        assert rig._jobs[job_id]["status"] == "done"

    def test_a_member_is_an_ordinary_report_the_existing_page_can_render(self, rig):
        _, sweep_id = self._start(rig)
        member = sweep.read_json(sweep.member_path(sweep_id, self.IDS[0]))
        for key in ("video_url", "authenticity_score", "brand_health_score",
                    "all_segments", "comment_sentiment"):
            assert key in member

    def test_the_combined_record_carries_the_mandatory_caveats(self, rig):
        """Any surface showing a facial-derived score must carry BIAS_CAVEAT."""
        _, sweep_id = self._start(rig)
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["bias_caveat"]
        assert "facial" in record["bias_caveat"].lower()
        assert record["vocal_caveat"]

    def test_the_controller_is_recorded_because_sweeps_are_not_comparable_without_it(self, rig):
        """
        controller_bench measured the controller swap at 49.08 points of
        Authenticity on byte-identical inputs. Two sweeps written by different
        controllers cannot be compared, and the comparison view needs this to
        know that.
        """
        _, sweep_id = self._start(rig)
        assert sweep.read_json(sweep.sweep_path(sweep_id))["controller"]

    def test_one_dead_video_does_not_lose_the_others(self, rig, monkeypatch):
        """
        The pipeline's graceful-degradation rule, one level up. Losing 50
        minutes of finished work because the third video was region-locked
        would be the worst possible reading of it.
        """
        real = rig._build_segments

        def sometimes(url, video_id):
            if video_id == "bbbbbbbbbbb":
                raise RuntimeError("Video unavailable in your region")
            return real(url, video_id)

        monkeypatch.setattr(rig, "_build_segments", sometimes)
        job_id, sweep_id = self._start(rig)

        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["status"] == "partial"
        assert record["summary"]["video_count"] == 2
        assert sweep.member_path(sweep_id, "aaaaaaaaaaa").is_file()
        assert sweep.member_path(sweep_id, "ccccccccccc").is_file()
        assert not sweep.member_path(sweep_id, "bbbbbbbbbbb").exists()

    def test_a_failure_is_recorded_with_a_reason_a_reader_can_act_on(self, rig, monkeypatch):
        def boom(url, video_id):
            raise RuntimeError("Video unavailable in your region")

        monkeypatch.setattr(rig, "_build_segments", boom)
        _, sweep_id = self._start(rig)
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["status"] == "error"          # nothing survived
        assert len(record["failed"]) == 3
        assert "region" in record["failed"][0]["reason"]
        assert record["failed"][0]["video_id"] in self.IDS

    def test_a_sweep_resumes_instead_of_repeating_an_hour_of_work(self, rig, monkeypatch):
        self._start(rig)                             # a complete first run
        rig._jobs.clear()

        analysed: list[str] = []
        real = rig._build_segments

        def counting(url, video_id):
            analysed.append(video_id)
            return real(url, video_id)

        monkeypatch.setattr(rig, "_build_segments", counting)
        sweep.member_path(sweep.sweep_id_for("Samsung", "month", 0, self.IDS),
                          "ccccccccccc").unlink()    # lose one member

        self._start(rig)
        assert analysed == ["ccccccccccc"], "re-analysed work already on disk"

    def test_cancelling_keeps_what_has_already_finished(self, rig):
        job_id, sweep_id = self._start(rig, cancel=True)
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["status"] == "cancelled"
        assert rig._jobs[job_id]["status"] == "cancelled"
        assert sweep.sweep_path(sweep_id).is_file(), "an hour of work thrown away"

    def test_the_provenance_of_the_selection_is_written_down(self, rig):
        _, sweep_id = self._start(rig)
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["selection"]["query_used"] == "Samsung review"
        assert [m["video_id"] for m in record["members"]] == self.IDS

    # A start that did not carry the search result. 24 Sep 2026: the Huawei
    # brand sweep was saved with all five titles blank, and every page of its
    # book named the videos by id.

    @staticmethod
    def _details(calls):
        def details(ids, client=None):
            calls.append(list(ids))
            return {v: {"video_id": v, "title": f"Real {v[0]}", "channel": "Chan",
                        "published_at": "2026-09-20T10:00:00Z", "duration_s": 600,
                        "comment_count": 120} for v in ids}
        return details

    def test_a_start_without_titles_looks_them_up_once_and_files_them(self, rig, monkeypatch):
        calls: list = []
        monkeypatch.setattr(sweep, "video_details", self._details(calls))
        _, sweep_id = self._start(rig, titled=False)
        assert calls == [self.IDS], "one lookup for all of them, 1 quota unit"
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert [m["title"] for m in record["members"]] == ["Real a", "Real b", "Real c"]
        first = record["members"][0]
        assert (first["channel"], first["duration_s"], first["comment_count"]) == ("Chan", 600, 120)
        member = sweep.read_json(sweep.member_path(sweep_id, self.IDS[0]))
        assert member["video_title"] == "Real a", "the member's own book is titled too"

    def test_a_start_with_titles_makes_no_lookup(self, rig, monkeypatch):
        calls: list = []
        monkeypatch.setattr(sweep, "video_details", self._details(calls))
        _, sweep_id = self._start(rig)
        assert calls == []
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert [m["title"] for m in record["members"]] == ["Video a", "Video b", "Video c"]

    def test_a_failed_lookup_costs_the_titles_never_the_sweep(self, rig, monkeypatch):
        def down(ids, client=None):
            raise OSError("network down")

        monkeypatch.setattr(sweep, "video_details", down)
        job_id, sweep_id = self._start(rig, titled=False)
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert record["status"] == "done" and rig._jobs[job_id]["status"] == "done"
        assert [m["title"] for m in record["members"]] == ["", "", ""]

    def test_what_youtube_told_the_written_reports_fills_what_the_lookup_could_not(
            self, rig, monkeypatch):
        """Each member's written report asks YouTube for its title anyway (S1, S3)."""
        from pipeline import analyst

        def down(ids, client=None):
            raise OSError("network down")

        monkeypatch.setattr(sweep, "video_details", down)
        monkeypatch.setattr(analyst, "fetch_video_meta", lambda vid: {
            "fetched": True, "at": "2026-09-24T06:00:00+00:00", "title": f"Meta {vid[0]}",
            "channel": "Meta chan", "published_at": "2026-09-21T00:00:00Z",
            "has_paid_product_placement": False, "description_hits": []})
        _, sweep_id = self._start(rig, titled=False)
        record = sweep.read_json(sweep.sweep_path(sweep_id))
        assert [m["title"] for m in record["members"]] == ["Meta a", "Meta b", "Meta c"]
        assert record["members"][0]["channel"] == "Meta chan"
        assert record["members"][0]["duration_s"] == 0, "not known from that source, so left blank"


class TestOneWorkerAtATime:
    @pytest.fixture
    def app_module(self):
        import app as app_module
        app_module._jobs.clear()
        yield app_module
        app_module._jobs.clear()

    def test_a_second_claim_is_refused_while_one_is_running(self, app_module):
        first, blocker = app_module._claim_worker({"kind": "analysis",
                                                   "status": "running"})
        assert first and blocker is None
        second, blocker = app_module._claim_worker({"kind": "sweep",
                                                    "status": "running"})
        assert second == ""
        assert blocker["job_id"] == first

    def test_the_blocker_says_what_is_running_so_the_page_can_say_so(self, app_module):
        app_module._claim_worker({"kind": "sweep", "status": "running",
                                  "subject": "Samsung", "stage_label": "Stage 2"})
        _, blocker = app_module._claim_worker({"kind": "analysis", "status": "running"})
        assert blocker["kind"] == "sweep"
        assert blocker["subject"] == "Samsung"

    def test_the_machine_frees_up_once_a_job_finishes(self, app_module):
        first, _ = app_module._claim_worker({"kind": "analysis", "status": "running"})
        app_module._jobs[first]["status"] = "done"
        second, blocker = app_module._claim_worker({"kind": "sweep", "status": "running"})
        assert second and blocker is None

    @pytest.mark.parametrize("finished", ["done", "partial", "cancelled", "error"])
    def test_no_terminal_state_holds_the_machine(self, app_module, finished):
        first, _ = app_module._claim_worker({"kind": "sweep", "status": "running"})
        app_module._jobs[first]["status"] = finished
        _, blocker = app_module._claim_worker({"kind": "analysis", "status": "running"})
        assert blocker is None

    def test_starting_an_analysis_while_a_sweep_runs_is_refused(self, app_module):
        """
        The hole this closes: /analyse/start never consulted _jobs, and run.js
        asks /analyse/active only at page load, so two tabs could start two
        pipelines. A sweep holds the machine for an hour.
        """
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        app_module._claim_worker({"kind": "sweep", "status": "running",
                                  "subject": "Samsung"})
        response = client.post("/analyse/start", json={
            "video_url": "https://youtu.be/aaaaaaaaaaa",
            "brand_name": "Nike", "product_name": "Test",
        })
        assert response.status_code == 409
        assert response.get_json()["active"]["kind"] == "sweep"


class TestTheElapsedClock:
    """
    A reconnecting page knows when its own tab opened, not when the run began.

    Found while a real sweep was running: reopening /run after eight minutes
    read "Elapsed 0:03". The page was not lying about its own state — it was
    reporting the wrong thing — but "Elapsed" beside a number that is not the
    elapsed time is a figure a reader would act on.
    """

    @pytest.fixture
    def app_module(self):
        import app as app_module
        app_module._jobs.clear()
        yield app_module
        app_module._jobs.clear()

    def test_a_claimed_job_records_when_it_began(self, app_module):
        import time as _time
        before = _time.time()
        job_id, _ = app_module._claim_worker({
            "kind": "sweep", "status": "running", "started_at": _time.time(),
        })
        assert before <= app_module._jobs[job_id]["started_at"] <= _time.time()

    def test_the_sweep_status_reports_the_start(self, app_module):
        import time as _time
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        job_id, _ = app_module._claim_worker({
            "kind": "sweep", "status": "running", "started_at": _time.time(),
            "stage_index": 1, "stage_label": "x", "total_stages": 4,
            "video_index": 0, "video_total": 5, "video_title": "",
            "done": [], "failed": [], "cancel_requested": False,
        })
        body = client.get(f"/sweep/status/{job_id}").get_json()
        assert isinstance(body["started_at"], float)

    def test_the_active_route_reports_it_too(self, app_module):
        """The reconnect path reads /analyse/active before any status poll."""
        import time as _time
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        app_module._claim_worker({
            "kind": "sweep", "status": "running", "started_at": _time.time(),
            "stage_index": 0, "stage_label": "x", "subject": "Samsung",
        })
        body = client.get("/analyse/active").get_json()
        assert body["active"] is True
        assert isinstance(body["started_at"], float)

    def test_a_job_without_a_start_does_not_break_the_status(self, app_module):
        """
        A job created before this field existed — which is exactly the case
        while the change is deployed under a running sweep — reports null, and
        the page falls back to its own clock.
        """
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        job_id, _ = app_module._claim_worker({
            "kind": "sweep", "status": "running",
            "stage_index": 0, "stage_label": "x", "total_stages": 4,
            "video_index": 0, "video_total": 5, "video_title": "",
            "done": [], "failed": [], "cancel_requested": False,
        })
        body = client.get(f"/sweep/status/{job_id}").get_json()
        assert body["started_at"] is None


class TestTheStartRouteRefusesBadInput:
    """
    A bad request must read as a bad request. `max_comments: "banana"` used to
    raise out of the route as a 500 — a crash reported as a server fault when
    the caller had simply sent the wrong thing — and an unbounded value would
    have asked YouTube for a million comments on each of five videos.
    """

    @pytest.fixture
    def client(self, monkeypatch):
        import app as app_module
        app_module.app.config.update(TESTING=True)
        app_module._jobs.clear()
        yield app_module.app.test_client()
        app_module._jobs.clear()

    def _body(self, **over):
        body = {"subject": "Samsung", "window": "month",
                "video_ids": ["aaaaaaaaaaa"]}
        body.update(over)
        return body

    @pytest.mark.parametrize("value", ["banana", None, [], {}])
    def test_a_non_numeric_comment_count_is_a_bad_request_not_a_crash(
        self, client, value
    ):
        response = client.post("/sweep/start", json=self._body(max_comments=value))
        assert response.status_code == 400, f"{value!r} produced {response.status_code}"
        assert "max_comments" in response.get_json()["error"]

    @pytest.mark.parametrize("value", [0, -5, 100000])
    def test_an_out_of_range_comment_count_is_refused(self, client, value):
        response = client.post("/sweep/start", json=self._body(max_comments=value))
        assert response.status_code == 400

    def test_a_video_id_that_is_not_one_is_refused(self, client):
        response = client.post("/sweep/start", json=self._body(video_ids=["../../etc"]))
        assert response.status_code == 400

    def test_more_videos_than_a_sweep_takes_is_refused(self, client):
        ids = [f"aaaaaaaaaa{i}" for i in range(sweep.SWEEP_SIZE + 2)]
        response = client.post("/sweep/start", json=self._body(video_ids=ids))
        assert response.status_code == 400
        assert str(sweep.SWEEP_SIZE) in response.get_json()["error"]

    def test_no_videos_at_all_is_refused(self, client):
        response = client.post("/sweep/start", json=self._body(video_ids=[]))
        assert response.status_code == 400

    @pytest.mark.parametrize("window,offset", [("week", 365), ("month", 182), ("half", 365)])
    def test_an_ending_the_search_would_refuse_is_refused_here_too(self, client, window, offset):
        """A hand-made start must not file a sweep under an ending no search makes."""
        import app as app_module
        response = client.post("/sweep/start",
                               json=self._body(window=window, offset_days=offset))
        assert response.status_code == 400
        assert f"at most {sweep.WINDOWS[window]} days" in response.get_json()["error"]
        assert not app_module._jobs, "no job was started"

    @pytest.mark.parametrize("value", ["soon", -5])
    def test_a_nonsense_ending_is_refused_here_too(self, client, value):
        response = client.post("/sweep/start", json=self._body(offset_days=value))
        assert response.status_code == 400
