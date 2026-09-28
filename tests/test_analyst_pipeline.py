"""
Tests for pipeline/analyst.py — the model layer of the written report.

The model is always faked: `analyse_report` takes the chat function as an
argument, so a test hands it a stand-in that answers each step. What is under
test is everything around the model: that its answers are verified, that bad
ones are dropped and logged, that required sentences fall back to code-built
ones, that an unreachable model degrades to facts rather than failing, and that
storage never lands where a report glob would find it.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline import analyst as A
from pipeline import analyst_verify as V

ROOT = Path(__file__).resolve().parent.parent


# ── fixtures ─────────────────────────────────────────────────────────────────

TEXTS = [
    "Nike made this shoe to control your mind. Well, not exactly. Let me explain.",
    "The foam that is used in the midst of the shoe is really comfortable underfoot.",
    "But honestly the price is way too high for what you actually get here.",
    "I did notice though that it felt good on feet and it got a lot of attention.",
]


def seg(sid, start, end, label, text, conflict=0.0, flagged=False, facial="happy"):
    return {"segment_id": sid, "start_s": start, "end_s": end, "text": text,
            "conflict_score": conflict, "flagged": flagged, "conflict_reasons": [],
            "model_outputs": {"transcript_sentiment": {"label": label, "confidence": 0.9},
                              "facial_emotion": {"dominant": facial, "confidence": 0.6},
                              "vocal_emotion": {"label": "neutral", "arousal": 0.4}}}


def make_report():
    segments = [seg(0, 0, 60, "NEUTRAL", TEXTS[0]),
                seg(1, 60, 150, "POSITIVE", TEXTS[1]),
                seg(2, 150, 200, "NEGATIVE", TEXTS[2], conflict=0.8, flagged=True, facial="sad"),
                seg(3, 200, 320, "POSITIVE", TEXTS[3], conflict=0.3)]
    comments = [{"text": "Love how comfy these are", "label": "POSITIVE", "confidence": 0.9, "like_count": 4},
                {"text": "way too expensive for foam @someone", "label": "NEGATIVE", "confidence": 0.8},
                {"text": "where can I buy them in size 12?", "label": "NEUTRAL", "confidence": 0.7},
                {"text": "lol", "label": "NEUTRAL", "confidence": 0.9}] * 10
    return {"video_url": "https://youtu.be/JpN1DQdV4G4", "brand_name": "Nike",
            "authenticity_score": 70.37, "brand_health_score": 47.07, "segment_count": 4,
            "all_segments": segments, "all_comments": comments,
            "comment_sentiment": {"label": "POSITIVE", "confidence": 0.63, "comment_count": 40,
                                  "distribution": {"POSITIVE": 10, "NEUTRAL": 20, "NEGATIVE": 10}}}


class Model:
    """A stand-in for Ollama. Each step's answer can be replaced per test."""

    def __init__(self, **answers):
        self.answers = answers
        self.seen = []

    def __call__(self, system, user, schema):
        step = {A.P1_SYSTEM: "claims", A.P2_SYSTEM: "topics",
                A.P3_SYSTEM: "comments", A.P4_SYSTEM: "prose"}[system]
        self.schemas = getattr(self, "schemas", {})
        self.schemas[step] = schema
        self.seen.append((step, json.loads(user)))
        answer = self.answers.get(step, self.default(step, json.loads(user)))
        if isinstance(answer, Exception):
            raise answer
        content = answer if isinstance(answer, str) else json.dumps(answer)
        return {"message": {"content": content}, "prompt_eval_count": 100, "eval_count": 50}

    @staticmethod
    def default(step, payload):
        if step == "claims":
            return {"claims": [
                {"seg": 1, "aspect": "Comfort", "stance": "praise",
                 "claim": "The reviewer finds the foam comfortable",
                 "quote": "the shoe is really comfortable underfoot"},
                {"seg": 2, "aspect": "price", "stance": "criticism",
                 "claim": "The reviewer thinks the price is too high",
                 "quote": "the price is way too high"}]}
        if step == "comments":
            out = []
            for c in payload["comments"]:
                t = c["text"].lower()
                out.append({"i": c["i"], "topics": (["Comfort"] if "comfy" in t else
                                                    ["Price"] if "expensive" in t else
                                                    ["Where to buy"] if "buy" in t else [])})
            return {"comments": out}
        if step == "topics":
            return {"topics": [{"name": "Comfort", "aspects": ["comfort"]},
                               {"name": "Price", "aspects": ["price"]},
                               {"name": "Where to buy", "aspects": []}]}
        return {"verdict": {"text": "The reviewer praises the comfort and criticises the price.",
                            "evidence": ["S1", "S2"]},
                "takeaways": [{"text": "Lead with comfort, which the reviewer praises.", "evidence": ["S1", "T0"]},
                              {"text": "Address the price the reviewer criticises.", "evidence": ["S2", "T1"]},
                              {"text": "Answer where to buy it.", "evidence": ["C2"]}],
                "brand_health_words": {"text": "Comments split 10 positive, 20 neutral and 10 negative.",
                                       "evidence": ["C0", "C1"]},
                "audience_words": {"text": "People talk about comfort and price.", "evidence": ["T0", "T1"]},
                "agreement_words": {"text": "The reviewer and the audience show no clear difference.",
                                    "evidence": ["S1", "C0"]},
                "moment_notes": [{"seg": 2, "text": "The words criticise the price while the face reads sad."}],
                "turn_labels": []}


# ── chunking ─────────────────────────────────────────────────────────────────

class TestChunks:
    def test_chunks_end_on_segment_boundaries(self):
        segs = [{"segment_id": i, "text": "word " * 300} for i in range(4)]
        chunks = A.chunk_segments(segs, max_words=650)
        assert [[s["segment_id"] for s in c] for c in chunks] == [[0, 1], [2, 3]]

    def test_an_oversized_segment_is_its_own_chunk_and_empty_ones_are_skipped(self):
        segs = [{"segment_id": 0, "text": "word " * 900}, {"segment_id": 1, "text": ""},
                {"segment_id": 2, "text": "short"}]
        chunks = A.chunk_segments(segs, max_words=650)
        assert [[s["segment_id"] for s in c] for c in chunks] == [[0], [2]]


# ── the whole step ───────────────────────────────────────────────────────────

class TestAnalyseReport:
    def test_a_good_run_is_complete_and_json_safe(self):
        out = A.analyse_report(make_report(), filename="Nike (Mind 001).json", fetch_meta=False,
                               chat=Model())
        json.dumps(out)
        assert out["status"] == "complete" and out["schema"] == A.SCHEMA
        assert out["subject"]["product"] == "Mind 001"
        assert [c["seg"] for c in out["reading"]["claims"]] == [1, 2]
        assert out["written"]["verdict"]["source"] == "model"
        assert len(out["written"]["takeaways"]) == 3
        assert out["verifier"]["dropped"] == []

    def test_the_model_being_down_degrades_to_facts(self):
        down = Model(claims=ConnectionError(), comments=ConnectionError(),
                     topics=ConnectionError(), prose=ConnectionError())
        out = A.analyse_report(make_report(), fetch_meta=False, chat=down)
        assert out["status"] == "partial"
        assert out["facts"]["reviewer"]["lean"] is not None
        assert out["written"]["verdict"]["source"] == "template"
        assert out["written"]["takeaways"] == []
        assert all(not row["ok"] for row in out["calls"])

    def test_malformed_json_is_a_failed_step_not_a_crash(self):
        out = A.analyse_report(make_report(), fetch_meta=False,
                               chat=Model(prose="not json {", claims="[1, 2]"))
        assert out["status"] == "partial"
        assert out["steps"]["prose"] is False and out["steps"]["claims"] is False
        assert out["written"]["verdict"]["source"] == "template"

    def test_a_changed_quote_is_dropped_and_logged(self):
        bad = {"claims": [{"seg": 1, "aspect": "comfort", "stance": "praise",
                           "claim": "The reviewer loves the foam",
                           "quote": "the shoe is incredibly comfortable underfoot"}]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(claims=bad))
        assert out["reading"]["claims"] == []
        assert any("quote" in r for d in out["verifier"]["dropped"] for r in d["reasons"])

    def test_an_unknown_number_with_a_quote_found_nowhere_or_a_bad_stance_is_dropped(self):
        bad = {"claims": [
            {"seg": 99, "aspect": "comfort", "stance": "praise", "claim": "Fine.",
             "quote": "words that appear in no segment at all"},
            {"seg": 1, "aspect": "comfort", "stance": "adoring", "claim": "Fine.",
             "quote": "really comfortable underfoot"}]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(claims=bad))
        assert out["reading"]["claims"] == []
        assert out["verifier"]["by_field"]["claim"]["dropped"] == 2

    def test_an_unknown_number_with_a_verbatim_quote_is_reattributed(self):
        claim = {"claims": [{"seg": 99, "aspect": "comfort", "stance": "praise",
                             "claim": "The foam is comfortable.", "quote": TEXTS[1]}]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(claims=claim))
        assert [c["seg"] for c in out["reading"]["claims"]] == [1]

    def test_a_forbidden_claim_in_a_paraphrase_is_dropped(self):
        bad = {"claims": [{"seg": 2, "aspect": "price", "stance": "criticism",
                           "claim": "The reviewer is honest about the price",
                           "quote": "the price is way too high"}]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(claims=bad))
        assert out["reading"]["claims"] == []

    def test_duplicate_claims_are_kept_once(self):
        c = {"seg": 1, "aspect": "comfort", "stance": "praise", "claim": "The foam is comfortable",
             "quote": "really comfortable underfoot"}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(claims={"claims": [c, dict(c)]}))
        assert len(out["reading"]["claims"]) == 1

    def test_an_invented_figure_in_the_verdict_falls_back_to_code(self):
        prose = Model.default("prose", {})
        prose["verdict"] = {"text": "The audience is 64% positive about comfort.", "evidence": ["T0"]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["verdict"]["source"] == "template"
        assert out["written"]["verdict"]["text"].endswith(".")
        assert any(d["field"] == "verdict" for d in out["verifier"]["dropped"])

    def test_takeaways_that_fail_are_dropped_not_padded(self):
        prose = Model.default("prose", {})
        prose["takeaways"][1] = {"text": "The creator was probably paid.", "evidence": ["S2"]}
        prose["takeaways"][2] = {"text": "Uncited advice.", "evidence": []}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert [t["text"] for t in out["written"]["takeaways"]] == [
            "Lead with comfort, which the reviewer praises."]

    def test_moment_notes_only_for_the_moments(self):
        prose = Model.default("prose", {})
        prose["moment_notes"] = [{"seg": 0, "text": "Not a moment."},
                                 {"seg": 2, "text": "The words criticise while the face reads sad."},
                                 {"seg": 2, "text": "A repeat."}]
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert [n["seg"] for n in out["written"]["moment_notes"]] == [2]

    def test_the_template_sentences_are_true_to_the_facts(self):
        out = A.analyse_report(make_report(), fetch_meta=False,
                               chat=Model(prose=ConnectionError()))
        health = out["written"]["brand_health_words"]["text"]
        assert health == "Of 40 comments, 10 read positive, 20 neutral and 10 negative."

    def test_it_is_deterministic(self):
        a = A.analyse_report(make_report(), fetch_meta=False, chat=Model())
        b = A.analyse_report(make_report(), fetch_meta=False, chat=Model())
        for key in ("facts", "reading", "written", "verifier"):
            assert a[key] == b[key]


# ── the pieces ───────────────────────────────────────────────────────────────

TOPICS = [{"name": "Price", "aspects": ["price"]}, {"name": "Design", "aspects": []},
          {"name": "Fit", "aspects": []}]


class TestComments:
    def test_only_named_topics_survive_capped_at_two(self):
        log, calls = V.Log(), A.Calls()
        model = Model(comments={"comments": [{"i": 0, "topics": ["Price", "Made up", "Design", "Fit"]},
                                             {"i": 77, "topics": ["Price"]}]})
        tags = A.tag_comments(model, calls, log, [{"text": "a"}, {"text": "b"}], TOPICS)
        assert tags == {0: ["Price", "Design"]}
        assert log.by_field["comment_tags"] == {"kept": 1, "dropped": 1}

    def test_the_topic_names_are_an_enum_in_the_schema(self):
        model = Model()
        A.tag_comments(model, A.Calls(), V.Log(), [{"text": "a"}], TOPICS)
        enum = model.schemas["comments"]["properties"]["comments"]["items"]["properties"]["topics"]["items"]["enum"]
        assert enum == ["Price", "Design", "Fit"]

    def test_no_topics_means_no_call(self):
        model = Model()
        assert A.tag_comments(model, A.Calls(), V.Log(), [{"text": "a"}], []) == {}
        assert model.seen == []

    def test_commenters_are_masked_before_the_model_sees_them(self):
        model = Model()
        A.tag_comments(model, A.Calls(), V.Log(), [{"text": "@john_doe is right https://x.com/a?b=1"}], TOPICS)
        sent = model.seen[0][1]["comments"][0]["text"]
        assert "john_doe" not in sent and "b=1" not in sent

    def test_questions_are_decided_by_code(self):
        assert A.is_question("where can I buy them?") and not A.is_question("buy them")


class TestTopics:
    counts = {"comfort": 2, "foam": 1, "price": 1, "shipping": 1}
    comments = [{"text": "where can I buy these in Canada"}, {"text": "too expensive"}]

    def test_aspects_left_out_go_to_other(self):
        model = Model(topics={"topics": [{"name": "comfort", "aspects": ["comfort", "foam"]},
                                         {"name": "Price", "aspects": ["price"]}]})
        topics, source = A.name_topics(model, A.Calls(), V.Log(), self.counts, self.comments, {})
        assert source == "model"
        assert [t["name"] for t in topics] == ["Comfort", "Price", "Other"]
        assert topics[-1]["aspects"] == ["shipping"]

    def test_an_audience_only_topic_is_kept_and_unknown_aspects_ignored(self):
        model = Model(topics={"topics": [{"name": "Comfort", "aspects": ["comfort", "foam", "nonsense"]},
                                         {"name": "comfort", "aspects": ["price"]},
                                         {"name": "Where to buy", "aspects": []}]})
        topics, _ = A.name_topics(model, A.Calls(), V.Log(), self.counts, self.comments, {})
        assert [t["name"] for t in topics] == ["Comfort", "Where to buy", "Other"]
        assert topics[0]["aspects"] == ["comfort", "foam"]
        assert topics[1]["aspects"] == []

    def test_the_model_sees_a_masked_sample_of_comments(self):
        model = Model()
        A.name_topics(model, A.Calls(), V.Log(), self.counts,
                      [{"text": "@someone where can I buy these"}] * 100, {})
        sample = model.seen[0][1]["comments"]
        assert len(sample) == A.TOPIC_COMMENTS and all("someone" not in c for c in sample)

    def test_a_failed_call_falls_back_to_the_aspects_themselves(self):
        topics, source = A.name_topics(Model(topics=ConnectionError()), A.Calls(), V.Log(),
                                       self.counts, self.comments, {})
        assert source == "fallback"
        assert topics[0]["aspects"] == ["comfort"]

    def test_at_the_cap_leftovers_replace_the_smallest_topic(self):
        counts = {f"a{i}": 10 - i for i in range(10)}
        model = Model(topics={"topics": [{"name": f"T{i}", "aspects": [f"a{i}"]} for i in range(10)]})
        topics, _ = A.name_topics(model, A.Calls(), V.Log(), counts, [], {})
        assert len(topics) == A.MAX_TOPICS and topics[-1]["name"] == "Other"
        assert sorted(topics[-1]["aspects"]) == ["a7", "a8", "a9"]


class TestAggregation:
    def test_reviewer_tone_comes_from_the_transcript_and_examples_are_masked(self):
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model())
        topics = {t["name"]: t for t in out["reading"]["topics"]}
        assert topics["Comfort"]["reviewer"]["seconds"]["POSITIVE"] == 90.0
        assert topics["Price"]["reviewer"]["seconds"]["NEGATIVE"] == 50.0
        assert topics["Price"]["audience"]["counts"]["NEGATIVE"] == 10
        quotes = [e["quote"] for e in topics["Price"]["audience"]["examples"]]
        assert quotes and all("@someone" not in q for q in quotes)

    def test_questions_are_listed(self):
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model())
        assert out["reading"]["questions"][0]["quote"].endswith("?")


# ── YouTube metadata ─────────────────────────────────────────────────────────

class TestVideoMeta:
    def test_no_key_is_not_fetched(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        out = A.fetch_video_meta("JpN1DQdV4G4")
        assert out["fetched"] is False and out["error"] == "no API key"

    def test_the_label_and_description_hits_are_read(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "secret-key-value")
        client = MagicMock()
        client.videos.return_value.list.return_value.execute.return_value = {"items": [{
            "snippet": {"title": "t", "channelTitle": "c", "publishedAt": "2026-09-01",
                        "description": "Use code SAVE10. Links are affiliate links: https://amzn.to/x"},
            "paidProductPlacementDetails": {"hasPaidProductPlacement": True}}]}
        with patch.object(A, "build", return_value=client) as built:
            out = A.fetch_video_meta("JpN1DQdV4G4")
        assert out["fetched"] and out["has_paid_product_placement"] is True
        assert {h["category"] for h in out["description_hits"]} >= {"affiliate", "discount_code"}
        parts = client.videos.return_value.list.call_args.kwargs["part"]
        assert "paidProductPlacementDetails" in parts
        assert "secret-key-value" not in json.dumps(out)
        assert built.called

    def test_an_api_error_degrades_without_the_key(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "secret-key-value")
        with patch.object(A, "build", side_effect=RuntimeError("quota secret-key-value")):
            out = A.fetch_video_meta("JpN1DQdV4G4")
        assert out == {"fetched": False, "error": "RuntimeError", "at": out["at"]}


# ── storage ──────────────────────────────────────────────────────────────────

class TestStorage:
    def test_paths_stay_out_of_every_report_glob(self):
        single = A.storage_path_for_report("Nike (Mind 001).json")
        member = A.storage_path_for_member("nike-week-19a4d6f6", "B8-JHY94jvI")
        assert single.parent.name == "analysis" and single.parent.parent == A.OUTPUTS
        assert member.parent.name == "analysis" and member.parent.parent.parent.name == "sweeps"
        assert "members" not in member.parts
        assert A.storage_path_for_report("../../etc/x.json").parent == A.OUTPUTS / "analysis"

    def test_save_load_and_staleness(self, tmp_path):
        report = tmp_path / "r.json"
        report.write_text("{}", encoding="utf-8")
        out = tmp_path / "analysis" / "r.json"
        A.save(out, {"schema": A.SCHEMA}, report)
        loaded = A.load(out, report)
        assert loaded["stale"] is False and loaded["report_ref"]["file"] == "r.json"
        report.write_text('{"changed": 1}', encoding="utf-8")
        assert A.load(out, report)["stale"] is True
        assert not list(out.parent.glob("*.tmp"))

    def test_a_missing_or_corrupt_analysis_loads_as_none(self, tmp_path):
        assert A.load(tmp_path / "absent.json") is None
        bad = tmp_path / "bad.json"
        bad.write_text("{", encoding="utf-8")
        assert A.load(bad) is None

    def test_facts_only_needs_no_model(self):
        out = A.facts_only(make_report(), "Nike (Mind 001).json")
        json.dumps(out)
        assert out["status"] == "facts-only" and out["written"] is None
        assert out["facts"]["signs"]["signs"][0]["state"] == "not_checked"


class TestAgreementSentence:
    def test_a_sentence_against_the_call_falls_back_to_code(self):
        prose = Model.default("prose", {})
        report = make_report()
        # make the reviewer clearly warmer: every comment negative
        for c in report["all_comments"]:
            c["label"] = "NEGATIVE"
        prose["agreement_words"] = {"text": "The reviewer and the audience agree.", "evidence": ["S1", "C0"]}
        out = A.analyse_report(report, fetch_meta=False, chat=Model(prose=prose))
        assert out["facts"]["agreement"]["call"] == "reviewer_warmer"
        assert out["written"]["agreement_words"]["source"] == "template"
        assert out["written"]["agreement_words"]["text"].startswith("The reviewer is measurably warmer")


class TestCorrections:
    def test_a_verbatim_quote_under_the_wrong_number_is_reattributed(self):
        claims = {"claims": [{"seg": 0, "aspect": "comfort", "stance": "praise",
                              "claim": "The reviewer finds the foam comfortable",
                              "quote": "really comfortable underfoot"}]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(claims=claims))
        assert [c["seg"] for c in out["reading"]["claims"]] == [1]
        assert out["verifier"]["notes"][0]["to"] == 1

    def test_the_sheet_carries_the_closing_words(self):
        model = Model()
        A.analyse_report(make_report(), fetch_meta=False, chat=model)
        sheet = [p for step, p in model.seen if step == "prose"][0]["sheet"]
        assert sheet["closing_words"]["said"].endswith("a lot of attention.")
        assert sheet["closing_words"]["id"].startswith("S")

    def test_a_moment_note_must_name_two_readings(self):
        prose = Model.default("prose", {})
        prose["moment_notes"] = [{"seg": 2, "text": "The reviewer is unhappy here."}]
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["moment_notes"] == []

    def test_a_moment_note_that_misreads_a_channel_is_dropped(self):
        """At seg 2 the voice read NEUTRAL and the comments POSITIVE (24 Sep 2026)."""
        prose = Model.default("prose", {})
        prose["moment_notes"] = [{"seg": 2, "text": "The words read negative, but the voice and comments read positive."}]
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["moment_notes"] == []
        reasons = [r for d in out["verifier"]["dropped"] if d["field"] == "moment_note" for r in d["reasons"]]
        assert "says the voice read positive; it read neutral" in reasons

    def test_a_moment_note_true_to_every_reading_it_names_is_kept(self):
        prose = Model.default("prose", {})
        text = "The words and face read negative, while the comments read positive."
        prose["moment_notes"] = [{"seg": 2, "text": text}]
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["moment_notes"] == [{"seg": 2, "text": text}]

    def test_a_generic_turn_label_is_dropped(self):
        prose = Model.default("prose", {})
        report = make_report()
        out = A.analyse_report(report, fetch_meta=False, chat=Model(prose=prose))
        turns = [t["seg"] for t in out["facts"]["tone"]["turns"]]
        if not turns:
            pytest.skip("this fixture has no turns")
        prose["turn_labels"] = [{"seg": turns[0], "label": "The tone peaks"}]
        out = A.analyse_report(report, fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["turn_labels"] == []


class TestTheWindow:
    def test_the_window_holds_the_largest_measured_call_with_room(self):
        # 3,197 prompt + 585 output tokens: the prose call on Nike Mind 001
        assert A.ANALYST_NUM_CTX >= 1.5 * (3197 + 585)

    def test_an_oversized_sheet_is_cut_from_the_end_of_its_lists(self):
        sheet = {"claims": [{"id": f"S{i}", "claim": "x " * 60} for i in range(12)],
                 "audience_examples": [{"id": f"C{i}", "said": "y " * 60} for i in range(8)],
                 "closing_words": {"id": "S1", "said": "z " * 70}, "scores": {"authenticity": 70.37}}
        # a budget the fully cut sheet can meet: the instructions alone plus 400
        budget = A.estimated_tokens(A.P4_SYSTEM, {"sheet": {}}) + 400
        assert A.estimated_tokens(A.P4_SYSTEM, {"sheet": sheet}) > budget
        small = A.fit_sheet(sheet, budget)
        assert A.estimated_tokens(A.P4_SYSTEM, {"sheet": small}) <= budget
        assert small["claims"] == sheet["claims"][:len(small["claims"])]
        assert small["scores"] == sheet["scores"]

    def test_a_sheet_that_fits_is_untouched(self):
        sheet = {"claims": [{"id": "S1"}], "audience_examples": [], "closing_words": {"said": "a b"}}
        assert A.fit_sheet(sheet, 5000) == sheet


# ── what the live Apple (Duo) run showed (23 Sep 2026) ───────────────────────

class TestLiveRunFixes:
    def cut_report(self):
        report = make_report()
        report["all_segments"][1]["text"] = "The foam that is used in the midst of the shoe is really"
        report["all_segments"][2]["text"] = "comfortable underfoot. But the price is way too high here."
        return report

    def test_a_quote_across_a_whisper_cut_is_kept_with_both_ends(self):
        claims = {"claims": [{"seg": 1, "aspect": "comfort", "stance": "praise",
                              "claim": "The reviewer finds the foam comfortable",
                              "quote": "the shoe is really comfortable underfoot"}]}
        out = A.analyse_report(self.cut_report(), fetch_meta=False, chat=Model(claims=claims))
        [claim] = out["reading"]["claims"]
        assert (claim["seg"], claim["seg_end"]) == (1, 2)
        assert any(n["what"] == "quote runs across two segments" for n in out["verifier"]["notes"])
        comfort = next(t for t in out["reading"]["topics"] if t["name"] == "Comfort")
        assert comfort["reviewer"]["segments"] == [1, 2]

    def test_a_claim_in_one_segment_has_no_end(self):
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model())
        assert all("seg_end" not in c for c in out["reading"]["claims"])

    def test_a_changed_quote_across_the_cut_is_still_dropped(self):
        claims = {"claims": [{"seg": 1, "aspect": "comfort", "stance": "praise",
                              "claim": "The reviewer finds the foam comfortable",
                              "quote": "the shoe is truly comfortable underfoot"}]}
        out = A.analyse_report(self.cut_report(), fetch_meta=False, chat=Model(claims=claims))
        assert out["reading"]["claims"] == []

    def test_an_agreement_sentence_may_cite_nothing_but_must_match_the_call(self):
        prose = Model.default("prose", {})
        prose["agreement_words"] = {"text": "There is no clear difference between the reviewer and the audience.",
                                    "evidence": []}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["facts"]["agreement"]["call"] == "no_clear_difference"
        assert out["written"]["agreement_words"]["source"] == "model"

        report = make_report()
        for c in report["all_comments"]:
            c["label"] = "NEGATIVE"
        prose["agreement_words"] = {"text": "The reviewer and the audience agree.", "evidence": []}
        out = A.analyse_report(report, fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["agreement_words"]["source"] == "template"

    def test_an_unknown_id_in_the_agreement_sentence_is_still_refused(self):
        prose = Model.default("prose", {})
        prose["agreement_words"] = {"text": "There is no clear difference between them.",
                                    "evidence": ["agreement"]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["written"]["agreement_words"]["source"] == "template"

    def test_a_topic_about_the_reviewer_does_not_sink_the_verdict(self):
        topics = {"topics": [{"name": "Comfort", "aspects": ["comfort"]},
                             {"name": "Price", "aspects": ["price"]},
                             {"name": "The Reviewer", "aspects": []}]}
        prose = Model.default("prose", {})
        prose["verdict"] = {"text": "The reviewer concludes the foam is good but criticises the price.",
                            "evidence": ["S1", "S2"]}
        out = A.analyse_report(make_report(), fetch_meta=False, chat=Model(topics=topics, prose=prose))
        assert out["written"]["verdict"]["source"] == "model"


# ── the audience as a whole, and rechecking stored text (23 Sep 2026) ────────

class TestTheAudienceAsAWhole:
    def balanced_report(self):
        report = make_report()
        labels = ["POSITIVE", "NEGATIVE"] * 20          # 20 against 20: a balanced call
        for c, lab in zip(report["all_comments"], labels):
            c["label"] = lab
        return report

    def test_a_direction_the_call_does_not_show_is_dropped(self):
        """The first S27 run: 'generally positive' over 35 positive and 38 negative."""
        prose = Model.default("prose", {})
        prose["verdict"] = {"text": "The reviewer praises the foam, and the audience is generally positive.",
                            "evidence": ["S1", "C0"]}
        out = A.analyse_report(self.balanced_report(), fetch_meta=False, chat=Model(prose=prose))
        assert out["facts"]["audience"]["call"] == "balanced"
        assert out["written"]["verdict"]["source"] == "template"
        assert any("computed call is balanced" in r for d in out["verifier"]["dropped"] for r in d["reasons"])

    def test_a_topic_clause_is_left_to_the_topic_check(self):
        problems = V.audience_direction_problems("The comments love the comfort.", "balanced",
                                                 [{"name": "Comfort", "aspects": ["comfort"]}])
        assert problems == []

    @pytest.mark.parametrize("text,call,ok", [
        ("The audience is positive.", "positive", True),
        ("The audience is positive.", "negative", False),
        ("Viewers are not happy with it.", "negative", True),
        ("The comments are split.", "balanced", True),
    ])
    def test_the_rule(self, text, call, ok):
        assert (V.audience_direction_problems(text, call) == []) is ok


class TestRecheck:
    def stored(self, verdict):
        prose = Model.default("prose", {})
        prose["verdict"] = verdict
        report = TestTheAudienceAsAWhole().balanced_report()
        # written before the new check existed: simulate by accepting everything
        original = V.audience_direction_problems
        try:
            V.audience_direction_problems = lambda *a, **k: []
            out = A.analyse_report(report, fetch_meta=False, chat=Model(prose=prose))
        finally:
            V.audience_direction_problems = original
        return out, report

    def test_a_sentence_that_now_fails_is_replaced_and_logged(self):
        out, report = self.stored({"text": "The reviewer praises the foam, and the audience is generally positive.",
                                   "evidence": ["S1", "C0"]})
        assert out["written"]["verdict"]["source"] == "model"
        again = A.recheck(out, report)
        assert again["written"]["verdict"]["source"] == "template"
        assert again["rechecked"]["changed"] == 1
        assert any(r.startswith("recheck: ") for d in again["verifier"]["dropped"] for r in d["reasons"])
        assert out["written"]["verdict"]["source"] == "model"            # the input is not mutated

    def test_sentences_that_still_pass_are_untouched_and_it_is_idempotent(self):
        out, report = self.stored({"text": "The reviewer praises the foam and criticises the price.",
                                   "evidence": ["S1", "S2"]})
        again = A.recheck(out, report)
        assert again["rechecked"]["changed"] == 0
        assert again["written"] == out["written"]
        assert A.recheck(again, report)["written"] == again["written"]

    def test_a_stored_moment_note_that_misreads_a_channel_is_dropped_on_recheck(self):
        prose = Model.default("prose", {})
        bad = "The words read negative, but the voice and comments read positive."
        good = "The words and face read positive, but the voice reads neutral."
        prose["moment_notes"] = [{"seg": 2, "text": bad}, {"seg": 3, "text": good}]
        report = make_report()
        original = V.moment_claim_problems
        try:                                  # written before the check existed
            V.moment_claim_problems = lambda *a, **k: []
            out = A.analyse_report(report, fetch_meta=False, chat=Model(prose=prose))
        finally:
            V.moment_claim_problems = original
        assert [n["seg"] for n in out["written"]["moment_notes"]] == [2, 3]
        again = A.recheck(out, report)
        assert again["written"]["moment_notes"] == [{"seg": 3, "text": good}]
        assert again["rechecked"]["changed"] == 1
        row = [d for d in again["verifier"]["dropped"] if d["field"] == "moment_note" and d["text"] == bad]
        assert row and row[0]["reasons"] == ["recheck: says the voice read positive; it read neutral"]
        assert again["verifier"]["by_field"]["moment_note"]["dropped"] >= 1
        assert [n["seg"] for n in out["written"]["moment_notes"]] == [2, 3]   # the input is not mutated
        assert A.recheck(again, report)["rechecked"]["changed"] == 0          # idempotent

    def test_a_facts_only_analysis_has_nothing_to_recheck(self):
        report = make_report()
        f = A.facts_only(report)
        assert A.recheck(f, report) == f
