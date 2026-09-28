"""
Tests for pipeline/analyst_sweep.py — the model layer of the combined written report.

The model is always a stand-in: `analyse_sweep` takes the chat function as an
argument. What is under test is everything around it: that the themes it names
can only hold topics that exist, that a product name must come from the title,
that every sentence is verified against the matrix and the evidence, that
required sentences fall back to code's, that an unreachable model degrades
rather than failing, and that storage stays out of every report glob.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import analyst as A
from pipeline import analyst_facts as F
from pipeline import analyst_sweep as W
from pipeline import analyst_sweep_facts as S
from pipeline import analyst_verify as V


# ── fixtures ─────────────────────────────────────────────────────────────────

TEXTS = {
    1: ["The battery easily lasts a full day of heavy use for me", "and the screen is bright and sharp outdoors",
        "but the price is really hard to justify"],
    2: ["Battery life is excellent on this phone honestly", "the display looks fantastic in sunlight",
        "at this price I expected a better camera"],
    3: ["The battery drains far too quickly when gaming", "I do love the screen though it is gorgeous",
        "the price is fair for what you get"],
}


def seg(sid, label, text):
    return {"segment_id": sid, "start_s": sid * 30.0, "end_s": sid * 30.0 + 30.0, "text": text,
            "conflict_score": 0.0, "flagged": False, "conflict_reasons": [],
            "model_outputs": {"transcript_sentiment": {"label": label, "confidence": 0.9}}}


def member(n, stances, comment_labels, topic_names=("Battery", "Screen", "Price")):
    texts = TEXTS[n]
    rep = {"video_url": f"https://youtu.be/{'V' * 10}{n}", "brand_name": "Acme",
           "authenticity_score": 50.0 + n, "brand_health_score": 40.0 + n,
           "all_segments": [seg(i, "POSITIVE", t) for i, t in enumerate(texts)],
           "all_comments": [{"text": f"comment {i} about the battery", "label": lab, "confidence": 0.8}
                            for i, lab in enumerate(comment_labels)],
           "comment_sentiment": {"label": "POSITIVE", "confidence": 0.7,
                                 "distribution": {k: comment_labels.count(k) for k in F.VALENCES}}}
    topics = [{"id": f"T{k}", "name": name, "aspects": [name.lower()],
               "reviewer": {"claims": 1, "seconds": {"POSITIVE": 30.0, "NEUTRAL": 0.0, "NEGATIVE": 0.0}},
               "audience": {"comments": 2 if k == 0 else 0,
                            "examples": ([{"i": 0, "quote": "comment 0 about the battery", "label": "POSITIVE",
                                           "likes": 3}] if k == 0 else [])}}
              for k, name in enumerate(topic_names)]
    claims = [{"seg": k, "time": F.mmss(k * 30.0), "start": k * 30.0, "aspect": topic_names[k].lower(),
               "stance": stances[k], "claim": f"A claim about {topic_names[k].lower()}",
               "quote": " ".join(texts[k].split()[:5]), "topic": f"T{k}"} for k in range(3)]
    analysis = {"status": "complete", "facts": F.compute_facts(rep),
                "written": {"verdict": {"text": f"Video {n} verdict.", "source": "model"}, "moment_notes": []},
                "reading": {"claims": claims, "topics": topics,
                            "comment_tags": {"0": [topic_names[0]], "1": [topic_names[0]]}, "questions": []}}
    vid = f"{'V' * 10}{n}"
    return {"n": n, "entry": {"video_id": vid, "title": f"Acme Phone {n} review", "channel": "C"},
            "report": rep, "analysis": analysis, "stale": False}


def bundles():
    return [member(1, ["praise", "praise", "criticism"], ["POSITIVE", "POSITIVE"]),
            member(2, ["praise", "praise", "criticism"], ["POSITIVE", "NEGATIVE"], ("Battery life", "Display", "Price")),
            member(3, ["criticism", "praise", "praise"], ["NEGATIVE", "NEGATIVE"])]


RECORD = {"sweep_id": "acme-phone-month-00000000", "subject": "Acme Phone", "subject_kind": "product",
          "window": "month", "offset_days": 0, "members": [], "summary": {}}

THEMES = {"themes": [{"name": "Battery", "topics": ["V1T0", "V2T0", "V3T0"]},
                     {"name": "Screen", "topics": ["V1T1", "V2T1", "V3T1"]},
                     {"name": "Price", "topics": ["V1T2", "V2T2", "V3T2"]}]}


class Model:
    """A stand-in for Ollama that answers the combined steps."""

    def __init__(self, **answers):
        self.answers = answers
        self.seen = []
        self.schemas = {}

    def __call__(self, system, user, schema):
        step = {W.P5_SYSTEM: "themes", W.P5B_SYSTEM: "products", W.P6_SYSTEM: "set_prose"}[system]
        payload = json.loads(user)
        self.seen.append((step, payload))
        self.schemas[step] = schema
        answer = self.answers.get(step, self.default(step, payload))
        if isinstance(answer, Exception):
            raise answer
        return {"message": {"content": answer if isinstance(answer, str) else json.dumps(answer)},
                "prompt_eval_count": 100, "eval_count": 50}

    @staticmethod
    def default(step, payload):
        if step == "themes":
            return THEMES
        if step == "products":
            return {"products": [{"v": v["v"], "product": f"Phone {v['v']}"} for v in payload["videos"]]}
        ids = {t["name"]: t["id"] for t in payload["sheet"]["themes"]}
        return prose(ids)


def theme_id(out, name):
    return next(t["id"] for t in out["reading"]["themes"] if t["name"] == name)


# The ids the matrix gives these themes: rows are ordered by how many videos
# talk about a theme, then by weight, so Battery (with comments) comes first.
IDS = {"Battery": "H0", "Price": "H1", "Screen": "H2"}


def prose(ids=None, **over):
    ids = ids or IDS
    base = {"takeaways": [{"text": "Show the screen outdoors, which reviewers praise.", "evidence": [ids["Screen"]]}],
            "odd_words": {"text": "", "evidence": []},
            "lineup_words": {"text": "", "evidence": []}}
    base.update(over)
    return base


def take(text, evidence=None):
    """One takeaway, the field the model still writes."""
    return prose(takeaways=[{"text": text, "evidence": evidence if evidence is not None else ["V1"]}])


def kept(out):
    return [t["text"] for t in out["written"]["takeaways"]]


def run(model=None, bs=None, record=RECORD):
    return W.analyse_sweep(record, bs or bundles(), chat=model or Model())


# ── P5 themes ────────────────────────────────────────────────────────────────

class TestThemes:
    def test_a_good_grouping_builds_the_matrix(self):
        out = run()
        names = [t["name"] for t in out["reading"]["themes"]]
        assert set(names) == {"Battery", "Screen", "Price"}
        screen = next(t for t in out["reading"]["themes"] if t["name"] == "Screen")
        assert screen["reviewer"]["label"] == "agreed" and screen["reviewer"]["side"] == "praise"
        assert out["reading"]["theme_source"] == "model"
        assert [t["id"] for t in out["reading"]["themes"]] == ["H0", "H1", "H2"]

    def test_the_refs_are_an_enum_of_exactly_the_topics(self):
        model = Model()
        run(model)
        enum = model.schemas["themes"]["properties"]["themes"]["items"]["properties"]["topics"]["items"]["enum"]
        assert sorted(enum) == sorted(f"V{n}T{k}" for n in (1, 2, 3) for k in range(3))

    def test_a_topic_about_the_reviewer_never_reaches_the_model(self):
        bs = bundles()
        bs[0]["analysis"]["reading"]["topics"][2]["name"] = "The reviewer"
        model = Model()
        out = run(model, bs)
        sent = [t["ref"] for v in model.seen[0][1]["videos"] for t in v["topics"]]
        assert "V1T2" not in sent and out["reading"]["meta_refs"] == ["V1T2"]

    def test_unknown_and_repeated_refs_are_dropped_and_logged(self):
        themes = {"themes": [{"name": "Battery", "topics": ["V1T0", "V9T9"]},
                             {"name": "Power", "topics": ["V1T0"]},
                             {"name": "The reviewer", "topics": ["V2T0"]}]}
        out = run(Model(themes=themes))
        assert [t["name"] for t in out["reading"]["themes"]] == ["Battery"]
        fields = {d["field"] for d in out["verifier"]["dropped"]}
        assert {"theme_ref", "theme"} <= fields

    def test_a_topic_left_out_joins_the_theme_with_its_own_name(self):
        themes = {"themes": [{"name": "Battery", "topics": ["V2T0"]}, {"name": "Price", "topics": ["V1T2"]}]}
        out = run(Model(themes=themes))
        battery = next(t for t in out["reading"]["themes"] if t["name"] == "Battery")
        assert "V1T0" in battery["refs"] and "V3T0" in battery["refs"]
        assert "V2T1" in out["reading"]["unplaced"]

    def test_a_failed_call_falls_back_to_grouping_by_name_and_aspects(self):
        out = run(Model(themes=RuntimeError("down")))
        assert out["reading"]["theme_source"] == "fallback"
        names = {t["name"] for t in out["reading"]["themes"]}
        assert "Battery" in names or "Battery life" in names
        battery = next(t for t in out["reading"]["themes"] if t["name"] in ("Battery", "Battery life"))
        assert {"V1T0", "V3T0"} <= set(battery["refs"])

    def test_the_fallback_merges_by_aspect_overlap(self):
        refs = [{"ref": "V1T0", "n": 1, "name": "Screen", "aspects": ["display", "screen"], "claims": 2, "comments": 0},
                {"ref": "V2T0", "n": 2, "name": "Display", "aspects": ["display", "screen"], "claims": 1, "comments": 0},
                {"ref": "V3T0", "n": 3, "name": "Camera", "aspects": ["camera"], "claims": 5, "comments": 0}]
        out = W.fallback_themes(refs)
        assert out[0]["refs"] == ["V1T0", "V2T0"] and out[0]["name"] == "Screen"
        assert out[1]["refs"] == ["V3T0"]

    def test_no_written_members_means_no_themes_and_no_prose(self):
        bs = [dict(b, analysis=None) for b in bundles()]
        model = Model()
        out = run(model, bs)
        assert out["reading"]["themes"] == [] and out["written"] is None
        assert out["status"] == "partial" and model.seen == []


# ── P5b products ─────────────────────────────────────────────────────────────

class TestProducts:
    BRAND = dict(RECORD, subject="Acme", subject_kind="brand")

    def test_only_a_brand_asks(self):
        model = Model()
        run(model)
        assert "products" not in [s for s, _ in model.seen]

    def test_names_are_copied_from_the_title_and_grouped(self):
        bs = bundles()
        bs[0]["entry"]["title"] = "Acme Glide 4 first look"
        bs[1]["entry"]["title"] = "Is the Glide 4 worth it? | Acme review"
        bs[2]["entry"]["title"] = "Acme Slide review"
        products = {"products": [{"v": 1, "product": "Acme Glide 4"}, {"v": 2, "product": "Glide 4"},
                                 {"v": 3, "product": "Slide"}]}
        out = run(Model(products=products), bs, self.BRAND)
        groups = out["reading"]["product_groups"]
        assert [(g["product"], g["videos"]) for g in groups] == [("Acme Glide 4", [1, 2]), ("Slide", [3])]

    @pytest.mark.parametrize("name,why", [
        ("Acme Phone 9", "not copied from the title"),
        ("Acme", "only the brand's name"),
        ("Acme Phone 1 review extra long words here", "too long"),
    ])
    def test_a_name_not_in_the_title_or_only_the_brand_is_refused(self, name, why):
        products = {"products": [{"v": 1, "product": name}]}
        out = run(Model(products=products), bundles(), self.BRAND)
        assert out["reading"]["products"] == []
        assert any(why in r for d in out["verifier"]["dropped"] if d["field"] == "product" for r in d["reasons"])

    def test_a_failed_call_means_no_products_not_a_crash(self):
        out = run(Model(products=RuntimeError("down")), bundles(), self.BRAND)
        assert out["reading"]["products"] is None and out["status"] == "partial"


# ── P6 prose ─────────────────────────────────────────────────────────────────

class TestProse:
    def test_the_summary_is_code_and_the_advice_is_the_model_s(self):
        out = run()
        w = out["written"]
        assert all(w[f]["source"] == "code" for f in W.CODE_FIELDS)
        assert kept(out) == ["Show the screen outdoors, which reviewers praise."]
        assert w["takeaways"][0]["evidence"] == [IDS["Screen"]]
        assert out["status"] == "complete"

    def test_the_code_verdict_says_the_calls_and_the_themes(self):
        w = run()["written"]
        assert w["verdict"]["text"].startswith("Across 3 videos, the reviewers' words lean positive in 3")
        assert "By theme, they agree on screen (praised); they split on battery and price." in w["verdict"]["text"]
        assert set(w["verdict"]["evidence"]) == set(IDS.values())       # the themes it names link to the matrix
        assert w["agreement_words"]["text"].startswith("Of 3 videos, ")
        assert w["consensus_words"]["text"].startswith("Reviewers agree on Screen (praised in 3 of 3)")
        assert "Price (praised in 1, criticised in 2)" in w["split_words"]["text"]

    def test_an_invented_figure_is_dropped(self):
        assert kept(run(Model(set_prose=take("Seven videos praise the screen; show it.", [IDS["Screen"]])))) == []

    def test_praise_the_matrix_does_not_show_is_refused(self):
        assert kept(run(Model(set_prose=take("Reviewers criticise the screen; fix it.", [IDS["Screen"]])))) == []

    def test_a_named_video_is_held_to_its_own_cell(self):
        themes = run()["reading"]["themes"]
        assert any("video 3" in p for p in V.set_stance_problems("Video 3 praises the battery.", themes, 3))

    def test_every_needs_a_row_every_video_agreed_on(self):
        assert kept(run(Model(set_prose=take("Every reviewer praises the screen; lead with it.")))) != []
        assert kept(run(Model(set_prose=take("Every reviewer praises the battery; lead with it.")))) == []

    @pytest.mark.parametrize("text,ok", [
        ("Lead with the screen, which reviewers agree on.", True),
        ("Watch the price, which reviewers are split on.", True),
        ("Lead with the price, which reviewers agree on.", False),
        ("Watch the screen, a point of contention.", False),
    ])
    def test_calling_a_theme_agreed_or_split_must_match_its_label(self, text, ok):
        assert bool(kept(run(Model(set_prose=take(text))))) is ok

    @pytest.mark.parametrize("text,wrong", [
        ("Video 3 is the only one to praise the price.", False),       # price: praised in 1
        ("Video 1 is the only one to criticise the price.", True),     # criticised in 2
    ])
    def test_the_only_one_must_be_the_only_one(self, text, wrong):
        assert bool(V.only_problems(text, run()["reading"]["themes"])) is wrong

    @pytest.mark.parametrize("text", [
        "Revise the camera bump, criticized in two videos.",
        "Lead with the screen, as videos 3 and 4 praise it.",
        "Keep the screen, which 3 reviewers praise.",
    ])
    def test_a_takeaway_does_not_argue_from_counts_or_name_videos(self, text):
        assert V.advice_problems(text)

    def test_a_quote_must_be_verbatim_and_may_run_into_the_next_segment(self):
        across = take('Quote the reviewer on the screen: "a full day of heavy use for me and the screen is bright".',
                      ["V1:S0"])
        assert kept(run(Model(set_prose=across)))
        changed = take('Quote the reviewer on the screen: "a full week of heavy use".', ["V1:S0"])
        assert not kept(run(Model(set_prose=changed)))

    @pytest.mark.parametrize("evidence", [["V9"], ["V1:S99"], ["V1:C99"], ["H9"], ["agreement"]])
    def test_evidence_that_does_not_exist_is_refused(self, evidence):
        assert not kept(run(Model(set_prose=take("Lead with the screen.", evidence + ["V1"]))))

    def test_claims_only_the_signs_may_make_are_refused(self):
        assert not kept(run(Model(set_prose=take("The screen praise seems sponsored by Acme."))))

    def test_a_takeaway_without_a_theme_is_dropped_not_padded(self):
        p = prose(takeaways=[{"text": "Keep going.", "evidence": ["V1"]},
                             {"text": "Show the screen outdoors.", "evidence": [IDS["Screen"]]}])
        assert kept(run(Model(set_prose=p))) == ["Show the screen outdoors."]

    @pytest.mark.parametrize("text,ok", [
        ("Show the screen outdoors, where it is bright and sharp.", True),     # the screen's own quotes
        ("Consider revising the screen bezel to make it more appealing.", False),   # no bezel anywhere
        ("Improve the message about the screen.", True),                        # general words only
        ("Improve the pricing message for the screen.", False),                 # pricing is the price theme's
        ("Improve the screen to meet user expectations.", True),                # everyday words, on their stem
        ("Expand the screen, as requested by reviewers.", False),               # a claim someone asked
    ])
    def test_a_takeaway_s_specifics_come_from_its_theme(self, text, ok):
        """The S27 run advised revising 'the camera bump' under a theme that never mentioned one."""
        out = run(Model(set_prose=take(text, [IDS["Screen"]])))
        assert bool(kept(out)) is ok, out["verifier"]["dropped"]

    def test_one_takeaway_to_a_theme(self):
        p = prose(takeaways=[{"text": "Show the screen outdoors.", "evidence": [IDS["Screen"]]},
                             {"text": "Put the screen in every campaign frame.", "evidence": [IDS["Screen"]]},
                             {"text": "Answer the price criticism.", "evidence": [IDS["Price"]]}])
        assert kept(run(Model(set_prose=p))) == ["Show the screen outdoors.", "Answer the price criticism."]

    def test_a_theme_named_in_words_is_its_evidence(self):
        out = run(Model(set_prose=take("Show the screen outdoors.", ["V1"])))
        assert IDS["Screen"] in out["written"]["takeaways"][0]["evidence"]

    def test_a_whole_audience_direction_the_set_does_not_show_is_dropped(self):  # noqa: E301
        out = run(Model(set_prose=take("Lead with the screen. The audience is generally positive.")))
        assert not kept(out)
        assert any("computed call is split" in r for d in out["verifier"]["dropped"] for r in d["reasons"])

    def test_a_video_s_number_is_not_an_invented_figure(self):
        p = prose(odd_words={"text": "Video 3 stands apart: its audience is far cooler.", "evidence": ["V3"]})
        ctx_numbers = W.set_context(W.set_sheet(run()["facts"], run()["reading"]["themes"], None, bundles()),
                                    bundles(), run()["reading"]["themes"], W._subject(RECORD)).allowed_numbers
        assert 3.0 in ctx_numbers and p

    @pytest.mark.parametrize("text,refused", [
        ("Reviewers praise the screen (H2).", True),
        ("Reviewers praise the screen (V1, V2).", True),
        ("Video 1 says it at V1:S0.", True),
        ("Reviewers praise the H2 chip and the Galaxy S27 screen.", False),
    ])
    def test_ids_belong_in_the_evidence_not_the_sentence(self, text, refused):
        assert bool(V.ids_in_text(text)) is refused

    @pytest.mark.parametrize("text,wrong", [
        ("Three videos praise the screen.", False),
        ("Two videos praise the screen.", True),
        ("The screen is praised in 3 of 3 videos.", False),
        ("The screen is praised in 3 of 5 videos.", True),
        ("2 out of 3 videos criticise the price.", False),
        ("One video criticises the price.", True),
    ])
    def test_a_count_for_a_theme_is_held_to_its_row(self, text, wrong):
        assert bool(V.theme_count_problems(text, run()["reading"]["themes"])) is wrong

    def test_a_video_said_to_be_silent_on_a_theme_must_be(self):
        themes = run()["reading"]["themes"]
        assert V.silence_problems("Video 2 does not mention the screen.", themes)
        screen = next(t for t in themes if t["name"] == "Screen")
        screen["cells"][1] = {**screen["cells"][1], "stance": "silent"}
        assert not V.silence_problems("Video 2 does not mention the screen.", themes)

    def test_a_count_of_comments_is_the_real_count(self):
        out = run()
        themes = out["reading"]["themes"]
        neg = next(t for t in themes if t["name"] == "Battery")["audience"]["counts"]["NEGATIVE"]
        assert not V.comment_count_problems(f"The battery drew {neg} negative comments.", themes, {})
        assert V.comment_count_problems(f"The battery drew {neg + 1} negative comments.", themes, {})
        overall = out["facts"]["audience"]["counts"]
        assert not V.comment_count_problems(f"There are {overall['POSITIVE']} positive comments.", themes, overall)
        assert V.comment_count_problems("There are 999 positive comments.", themes, overall)

    def test_an_audience_is_held_to_the_side_its_counts_favour(self):
        themes = run()["reading"]["themes"]
        battery = next(t for t in themes if t["name"] == "Battery")
        battery["audience"]["counts"] = {"POSITIVE": 5, "NEUTRAL": 1, "NEGATIVE": 2}
        assert not V.set_stance_problems("Audiences are positive about the battery.", themes, 3)
        assert V.set_stance_problems("Audiences are negative about the battery.", themes, 3)
        battery["audience"]["counts"] = {"POSITIVE": 3, "NEUTRAL": 0, "NEGATIVE": 3}      # a tie favours no side
        assert V.set_stance_problems("Audiences are positive about the battery.", themes, 3)
        assert V.set_stance_problems("Audiences are negative about the battery.", themes, 3)

    def test_with_no_odd_one_out_there_is_no_sentence_for_it(self):
        out = run()
        assert out["facts"]["odd_one_out"] is None and out["written"]["odd_words"] is None

    def test_the_odd_one_out_sentence_needs_the_video_and_its_dimension(self, monkeypatch):
        odd = {"n": 3, "dimension": "audience", "lean": -0.9, "others_median": 0.4, "video_id": "x",
               "title": "t", "se": 0.05, "low": -1.0, "high": -0.8, "others": [0.4, 0.4], "distance": 1.3}
        monkeypatch.setattr(S, "odd_one_out", lambda rows: dict(odd))
        p = prose(odd_words={"text": "Video 3 stands apart: its audience is far cooler.", "evidence": ["V3"]})
        assert run(Model(set_prose=p))["written"]["odd_words"]["source"] == "model"
        p = prose(odd_words={"text": "Video 3 stands apart from the others.", "evidence": ["V3"]})
        w = run(Model(set_prose=p))["written"]
        assert w["odd_words"]["source"] == "template"
        assert w["odd_words"]["text"] == "Video 3 stands apart: its audience leans −0.90, where the others' median is +0.40."

    def test_the_sheet_carries_words_not_leans_and_no_video_s_own_verdict(self):
        model = Model()
        run(model)
        sheet = [p for s, p in model.seen if s == "set_prose"][0]["sheet"]
        assert {v["reviewer"] for v in sheet["videos"]} <= {"leaning positive", "balanced", "leaning negative",
                                                          "not readable"}
        assert all(isinstance(v, int) for v in sheet["set"].values())
        assert all("verdict" not in v for v in sheet["videos"])
        assert {"audience_negative_comments", "audiences_leaning_negative"} <= set(sheet["themes"][0])

    def test_evidence_ids_are_an_enum_of_exactly_the_sheet_s_ids(self):
        model = Model()
        run(model)
        sheet = [p for s, p in model.seen if s == "set_prose"][0]["sheet"]
        items = model.schemas["set_prose"]["properties"]["takeaways"]["items"]
        assert set(items["properties"]["evidence"]["items"]["enum"]) == set(W.sheet_ids(sheet))

    def test_every_array_in_the_combined_schemas_is_bounded(self):
        """An unbounded enum array let the model repeat 'H0' until its output ran out."""
        def arrays(node, path=""):
            if isinstance(node, dict):
                if node.get("type") == "array":
                    yield path, node
                for k, v in node.items():
                    yield from arrays(v, f"{path}/{k}")
        for schema in (W.p5_schema(["V1T0", "V2T0"]), W.p5b_schema([1, 2]), W.p6_schema(["V1", "H0"])):
            found = list(arrays(schema))
            assert found and all("maxItems" in node for _, node in found), [p for p, n in found if "maxItems" not in n]

    def test_every_call_has_an_output_cap(self):
        assert A.ANALYST_MAX_OUTPUT >= 822      # the largest answer measured, combined prose, S27

    def test_an_oversized_sheet_loses_quotes_before_anything_else(self):
        out = run()
        sheet = W.set_sheet(out["facts"], out["reading"]["themes"], None, bundles())
        small = W.fit_set_sheet(sheet, 10)
        assert all(len(t["quotes"]) <= 1 and t["comments"] == [] for t in small["themes"])
        assert [t["praised_in"] for t in small["themes"]] == [t["praised_in"] for t in sheet["themes"]]


class TestTheStep:
    def test_the_model_being_down_degrades_to_code(self):
        out = run(Model(themes=RuntimeError("x"), set_prose=RuntimeError("x")))
        assert out["status"] == "partial"
        assert all(out["written"][f]["source"] == "code" for f in W.CODE_FIELDS)
        assert out["written"]["takeaways"] == []
        json.dumps(out)

    def test_malformed_json_is_a_failed_step_not_a_crash(self):
        out = run(Model(set_prose="{not json"))
        assert out["steps"]["set_prose"] is False and out["written"]["takeaways"] == []

    def test_the_test_guard_covers_this_step(self):
        """No chat given: the default is analyst.ollama_chat, which the guard makes refuse."""
        out = W.analyse_sweep(RECORD, bundles())
        assert out["status"] == "partial"
        assert all(not c["ok"] and c["error"] == "RuntimeError" for c in out["calls"])

    def test_it_is_deterministic(self):
        a, b = run(), run()
        for part in ("facts", "reading", "written"):
            assert json.dumps(a[part], sort_keys=True) == json.dumps(b[part], sort_keys=True)


# ── storage ──────────────────────────────────────────────────────────────────

class TestStorage:
    def test_the_path_is_beside_the_members_never_among_them(self):
        path = W.storage_path_for_sweep("acme-phone-month-00000000")
        assert path.parts[-3:] == ("acme-phone-month-00000000", "analysis", "combined.json")
        assert "members" not in path.parts

    @pytest.mark.parametrize("bad", ["../x", "a/b", ".hidden", "", "a\\b"])
    def test_unsafe_ids_are_refused(self, bad):
        with pytest.raises(ValueError):
            W.storage_path_for_sweep(bad)

    def test_load_bundles_reads_members_and_their_reports(self, tmp_path):
        sid = "acme-phone-month-00000000"
        members = tmp_path / "members"
        members.mkdir()
        b = bundles()[0]
        (members / f"{b['entry']['video_id']}.json").write_text(json.dumps(b["report"]), encoding="utf-8")
        A.save(A.storage_path_for_member(sid, b["entry"]["video_id"]), b["analysis"],
               members / f"{b['entry']['video_id']}.json")
        record = {"members": [b["entry"], {"video_id": "gonegonegon", "title": "Gone"}],
                  "failed": [{"video_id": "gonegonegon", "reason": "download failed"}]}
        out = W.load_bundles(sid, record, members)
        assert out[0]["report"] and out[0]["analysis"]["status"] == "complete" and out[0]["stale"] is False
        assert out[1]["report"] is None and out[1]["reason"] == "download failed"

    def test_save_load_and_staleness(self, tmp_path):
        sid = "acme-phone-month-00000000"
        record_path = tmp_path / "sweep.json"
        record_path.write_text("{}", encoding="utf-8")
        bs = bundles()
        path = W.storage_path_for_sweep(sid)
        ref = W.sweep_ref(sid, record_path, bs)
        W.save(path, {"schema": W.SCHEMA, "status": "complete"}, ref)
        assert W.load(path, W.sweep_ref(sid, record_path, bs))["stale"] is False
        # a member's written report appearing later makes the combined one stale
        A.save(A.storage_path_for_member(sid, bs[0]["entry"]["video_id"]), {"x": 1})
        loaded = W.load(path, W.sweep_ref(sid, record_path, bs))
        assert loaded["stale"] is True and loaded["stale_members"] == [bs[0]["entry"]["video_id"]]
        record_path.write_text('{"changed": true}', encoding="utf-8")
        assert W.load(path, W.sweep_ref(sid, record_path, bs))["stale"] is True

    def test_a_missing_or_corrupt_file_loads_as_none(self, tmp_path):
        bad = tmp_path / "combined.json"
        assert W.load(bad) is None
        bad.write_text("{nope", encoding="utf-8")
        assert W.load(bad) is None

    def test_facts_only_needs_no_model(self):
        out = W.facts_only(RECORD, bundles())
        assert out["status"] == "facts-only" and out["written"] is None
        assert out["facts"]["set"]["analysed"] == 3

    def test_what_youtube_told_each_member_is_read_back_from_disk(self):
        sid = "acme-phone-month-00000000"
        meta = {"fetched": True, "at": "2026-09-24T06:00:00+00:00", "title": "Acme Phone 1 review",
                "channel": "Chan", "published_at": "2026-09-20T10:00:00Z",
                "has_paid_product_placement": False, "description_hits": []}
        A.save(A.storage_path_for_member(sid, "VVVVVVVVVV1"), {"video_meta": meta})
        A.save(A.storage_path_for_member(sid, "VVVVVVVVVV2"),
               {"video_meta": {"fetched": False, "error": "no API key"}})
        out = W.written_video_details(sid, ["VVVVVVVVVV1", "VVVVVVVVVV2", "VVVVVVVVVV3", "../../x"])
        assert out == {"VVVVVVVVVV1": {"title": "Acme Phone 1 review", "channel": "Chan",
                                       "published_at": "2026-09-20T10:00:00Z"}}

    def test_an_unusable_sweep_id_reads_as_nothing_rather_than_raising(self):
        """It runs before a finished sweep's record is written; raising would lose the record."""
        assert W.written_video_details("../x", ["VVVVVVVVVV1"]) == {}


# ── the verifier's combined checks ───────────────────────────────────────────

class TestSetChecks:
    def test_video_numbers_named_in_a_clause(self):
        assert V._videos_named("videos 1, 3 and 4 praise it") == [1, 3, 4]
        assert V._videos_named("the second video") == []

    @pytest.mark.parametrize("text,dim,ok", [
        ("Its audience is far cooler.", "audience", True),
        ("Its comments lean negative.", "audience", True),
        ("The reviewer's words are warmer.", "reviewer", True),
        ("It stands apart.", "audience", False),
    ])
    def test_names_dimension(self, text, dim, ok):
        assert V.names_dimension(text, dim) is ok


# ── the command line (write_analysis.py) ─────────────────────────────────────

class TestTheCommandLine:
    SID = "acme-phone-month-00000000"

    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        import write_analysis as WA
        sweeps = tmp_path / "sweeps"
        members = sweeps / self.SID / "members"
        members.mkdir(parents=True)
        entries = []
        for b in bundles():
            (members / f"{b['entry']['video_id']}.json").write_text(json.dumps(b["report"]), encoding="utf-8")
            entries.append({**b["entry"], "analysed": True})
        (sweeps / self.SID / "sweep.json").write_text(json.dumps({**RECORD, "members": entries}), encoding="utf-8")
        monkeypatch.setattr(WA, "SWEEPS", sweeps)
        return WA

    def test_combined_only_needs_a_sweep(self, tree):
        with pytest.raises(SystemExit):
            tree.main(["--combined-only"])
        with pytest.raises(SystemExit):
            tree.main(["--sweep", self.SID, "--member", "VVVVVVVVVV1", "--combined-only"])

    def test_recheck_with_only_the_combined_report_is_refused_not_a_silent_no_op(self, tree):
        with pytest.raises(SystemExit):
            tree.main(["--recheck", "--sweep", self.SID, "--combined-only"])

    def test_the_dry_run_names_a_missing_report_and_fails_instead_of_raising(
            self, tree, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(tree, "OUTPUTS", tmp_path)
        assert tree.main(["--dry-run", "--report", "no such report.json"]) == 1
        assert "missing:" in capsys.readouterr().out
        assert tree.main(["--dry-run", "--sweep", "no-such-sweep-00000000"]) == 1

    def test_the_dry_run_sizes_the_combined_prompts_and_writes_nothing(self, tree, capsys):
        assert tree.main(["--dry-run", "--sweep", self.SID]) == 0
        out = capsys.readouterr().out
        assert "(combined)" in out and "themes" in out and "set_prose" in out
        assert not W.storage_path_for_sweep(self.SID).exists()

    def test_combined_only_writes_it_once_and_then_skips(self, tree, capsys):
        assert tree.main(["--sweep", self.SID, "--combined-only"]) == 0
        path = W.storage_path_for_sweep(self.SID)
        stored = json.loads(path.read_text(encoding="utf-8"))
        # no member has a written report, and the model refuses in tests
        assert stored["schema"] == W.SCHEMA and stored["written"] is None
        assert stored["facts"]["set"]["analysed"] == 3
        tree.main(["--sweep", self.SID, "--combined-only"])
        assert "skip (up to date)" in capsys.readouterr().out

    def test_fill_details_needs_a_sweep(self, tree):
        with pytest.raises(SystemExit):
            tree.main(["--fill-details", "--report", "x.json"])
        with pytest.raises(SystemExit):
            tree.main(["--fill-details", "--sweep", self.SID, "--member", "VVVVVVVVVV1"])

    def test_fill_details_fills_blanks_from_the_written_reports_and_touches_nothing_else(
            self, tree, capsys):
        sweep_dir = tree.SWEEPS / self.SID
        path = sweep_dir / "sweep.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        for entry in record["members"]:
            entry["title"] = entry["channel"] = ""
        record["members"][2]["title"] = "Kept as searched"
        path.write_text(json.dumps(record), encoding="utf-8")
        for entry in record["members"]:
            A.save(A.storage_path_for_member(self.SID, entry["video_id"]), {"video_meta": {
                "fetched": True, "title": f"On YouTube {entry['video_id'][-1]}", "channel": "Chan",
                "published_at": "2026-09-20T10:00:00Z"}})
        members_before = {p.name: p.read_bytes() for p in (sweep_dir / "members").iterdir()}
        before = path.read_bytes()

        assert tree.main(["--fill-details", "--dry-run", "--sweep", self.SID]) == 0
        assert "would fill 3 of 3" in capsys.readouterr().out
        assert path.read_bytes() == before, "a dry run wrote"

        assert tree.main(["--fill-details", "--sweep", self.SID]) == 0
        after = json.loads(path.read_text(encoding="utf-8"))
        assert [m["title"] for m in after["members"]] == ["On YouTube 1", "On YouTube 2", "Kept as searched"]
        assert {m["channel"] for m in after["members"]} == {"Chan"}
        assert {k: v for k, v in after.items() if k != "members"} == \
               {k: v for k, v in record.items() if k != "members"}
        assert {p.name: p.read_bytes() for p in (sweep_dir / "members").iterdir()} == members_before, \
            "a member report changed, which would mark its written report out of date"
        capsys.readouterr()
        tree.main(["--fill-details", "--sweep", self.SID])
        assert "filled 0 of 3" in capsys.readouterr().out
