"""
Tests for pipeline/analyst_verify.py — the gate between the model and the book.

Each check is tested in both directions: what it must let through (so real,
grounded prose survives) and what it must stop (so an invented figure, a
changed quote or a claim about payment or honesty never reaches a reader).
"""

from __future__ import annotations

import pytest

from pipeline import analyst_verify as V


# ── V1 quotes ────────────────────────────────────────────────────────────────

class TestQuotes:
    SOURCE = "I actually really like the way that it looks, and it's very comfortable underfoot."

    @pytest.mark.parametrize("quote", [
        "really like the way that it looks",
        "Really like the way that it looks.",
        "it’s very comfortable underfoot",
        "  it's   very comfortable  ",
    ])
    def test_case_punctuation_and_spacing_are_forgiven(self, quote):
        assert V.quote_in(quote, self.SOURCE)

    @pytest.mark.parametrize("quote", [
        "really love the way that it looks",        # a changed word
        "like the way it looks",                     # a missing word
        "very comfortable underfoot indeed",         # an added word
        "comfortable underfoot very",                # reordered
        "",
    ])
    def test_a_changed_word_is_not(self, quote):
        assert not V.quote_in(quote, self.SOURCE)

    def test_a_quote_longer_than_its_source_fails(self):
        assert not V.quote_in("a b c d", "a b c")


# ── V6 privacy ───────────────────────────────────────────────────────────────

class TestPrivacy:
    def test_handles_and_urls_are_masked(self):
        out = V.mask_comment("@john_doe agreed, see https://example.com/x?id=9 lol")
        assert "john_doe" not in out and "@…" in out
        assert "id=9" not in out and "example.com/…" in out

    def test_an_email_like_word_is_not_a_handle(self):
        assert V.mask_comment("mail me at a@b.com") == "mail me at a@b.com"


# ── V3 numbers ───────────────────────────────────────────────────────────────

class TestNumbers:
    def test_numbers_in_takes_numeric_leaves_only(self):
        out = V.numbers_in({"a": 70.37, "b": [1, True, None, "2:09"], "c": {"d": 3}})
        assert out == {70.37, 1.0, 3.0}

    @pytest.mark.parametrize("value,places,ok", [
        (70.37, 2, True), (70.4, 1, True), (70.0, 0, True), (71.0, 0, False),
        (70.3, 1, False), (1.0, 0, False),          # 0.789 must not license "1"
        (28.0, 0, True), (47.07, 2, True)])
    def test_a_figure_must_round_from_a_given_number(self, value, places, ok):
        allowed = {70.37, 0.789, 28.0, 47.07}
        assert V._supported(value, places, allowed) is ok

    def test_half_rounds_either_way(self):
        assert V._supported(13.0, 0, {12.5}) and V._supported(12.0, 0, {12.5})


# ── V1-V5 on prose ───────────────────────────────────────────────────────────

def ctx(**kw):
    base = dict(allowed_numbers={70.37, 47.07, 28.0, 39.0, 33.0, 100.0, 3.0, 29.0},
                allowed_times={"2:09", "0:00"},
                segment_text={13: "it promises to make you more focused and connected",
                              4: "the 45 watt charger is fast"},
                comment_text={0: "Personally I just like the look of them"},
                topic_names={0: "Comfort"},
                names="Apple iPhone 17 Pro Max")
    base.update(kw)
    return V.Context(**base)


class TestProse:
    def check(self, text, evidence=("S13",), max_words=45, **kw):
        return V.check_prose(text, list(evidence), ctx(**kw), max_words=max_words)

    def test_grounded_prose_passes(self):
        ok, problems, ids = self.check(
            "The reviewer questions the claim that it will make you \"more focused and connected\" "
            "at 2:09, and the audience splits 28, 39 and 33.")
        assert ok, problems
        assert ids == ["S13"]

    def test_unknown_or_missing_evidence_fails(self):
        assert not self.check("The foam is comfortable.", evidence=("S99",))[0]
        assert not self.check("The foam is comfortable.", evidence=())[0]
        assert not self.check("The foam is comfortable.", evidence=("X1",))[0]

    def test_evidence_optional_when_the_field_allows_it(self):
        ok, _, _ = V.check_prose("A short label", [], ctx(), max_words=6, require_evidence=False)
        assert ok

    def test_too_long_fails(self):
        assert not self.check("word " * 50)[0]

    def test_a_quote_not_in_its_evidence_fails(self):
        ok, problems, _ = self.check('The reviewer says it "changed my life".')
        assert not ok and any("quote" in p for p in problems)

    @pytest.mark.parametrize("sentence", [
        "The reviewer was paid for this.",
        "This looks like a sponsored video.",
        "The reviewer sounds honest.",
        "The comments may be bots.",
        "The praise feels fake.",
        "The review is not authentic.",
        "The audience seems genuine.",
    ])
    def test_claims_only_the_signs_may_make_are_refused(self, sentence):
        ok, problems, _ = self.check(sentence)
        assert not ok and any("signs may make" in p for p in problems)

    def test_the_authenticity_score_may_be_named(self):
        assert self.check("The Authenticity Score is 70.37.")[0]

    @pytest.mark.parametrize("sentence", [
        "Most comments are neutral.",
        "The majority of viewers disagree.",
        "Half of the comments are negative.",
        "Nearly all viewers agree.",
        "Everyone likes the look.",
    ])
    def test_unverifiable_proportions_are_refused(self, sentence):
        ok, problems, _ = self.check(sentence)
        assert not ok and any("proportion" in p for p in problems)

    @pytest.mark.parametrize("sentence", [
        "The most contested moment is at 2:09.",
        "In the second half of the video the tone cools.",
        "The third moment is calmer.",
    ])
    def test_ordinary_words_that_look_like_proportions_pass(self, sentence):
        ok, problems, _ = self.check(sentence)
        assert ok, problems

    def test_an_invented_figure_fails(self):
        ok, problems, _ = self.check("The audience is 64% positive.")
        assert not ok and any("figure" in p for p in problems)

    def test_a_timecode_must_exist(self):
        assert not self.check("The turn comes at 4:44.")[0]

    def test_number_words_are_checked_but_one_is_left_alone(self):
        assert self.check("Three moments stand out.")[0]
        assert not self.check("Seven moments stand out.")[0]
        assert self.check("One of the moments stands out.")[0]

    def test_figures_in_the_products_name_or_cited_evidence_are_allowed(self):
        assert self.check("The iPhone 17 is discussed.")[0]
        assert self.check("The 45 watt charger is praised.", evidence=("S4",))[0]
        assert not self.check("The 45 watt charger is praised.", evidence=("S13",))[0]

    def test_malformed_input_never_raises(self):
        for bad in (None, 5, "", "   "):
            ok, problems, _ = V.check_prose(bad, None, ctx(), max_words=10)
            assert not ok and problems


class TestLog:
    def test_it_counts_and_records(self):
        log = V.Log()
        log.keep("verdict")
        log.drop("verdict", ["too long"], "x" * 500)
        log.keep("claim")
        out = log.as_dict()
        assert out["proposed"] == 3 and out["kept"] == 2
        assert out["by_field"] == {"verdict": {"kept": 1, "dropped": 1}, "claim": {"kept": 1, "dropped": 0}}
        assert out["dropped"][0]["field"] == "verdict" and len(out["dropped"][0]["text"]) == 300


class TestAgreementDirection:
    @pytest.mark.parametrize("text,call,ok", [
        ("The reviewer and the audience show no clear difference.", "no_clear_difference", True),
        ("The reviewer is warmer than the audience.", "no_clear_difference", False),
        ("The reviewer is warmer than the audience on comfort.", "reviewer_warmer", True),
        ("The reviewer and the audience agree.", "reviewer_warmer", False),
        ("The audience is more positive than the reviewer.", "reviewer_warmer", False),
        ("The comments are warmer than the reviewer's words.", "audience_warmer", True),
        ("The reviewer is more critical than the audience.", "audience_warmer", True),
        ("They agree on comfort.", "audience_warmer", False),
        ("The two disagree on price.", "audience_warmer", True),
        ("They agree.", "unknown", False),
        ("People talk about price.", "unknown", True),
    ])
    def test_direction_must_match_the_call(self, text, call, ok):
        assert (V.agreement_consistent(text, call) == []) is ok


class TestStanceAgainstTheRun:
    TOPICS = [
        {"name": "Comfort", "aspects": ["comfort", "foam"],
         "reviewer": {"stances": {"praise": 2, "criticism": 0, "mixed": 0, "neutral": 1}},
         "audience": {"counts": {"POSITIVE": 3, "NEUTRAL": 1, "NEGATIVE": 0}}},
        {"name": "Price", "aspects": ["price"],
         "reviewer": {"stances": {"praise": 0, "criticism": 1, "mixed": 0, "neutral": 0}},
         "audience": {"counts": {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 4}}},
        {"name": "Other", "aspects": ["box"],
         "reviewer": {"stances": {}}, "audience": {"counts": {}}},
    ]

    @pytest.mark.parametrize("text", [
        "The reviewer praises the comfort but criticises the price.",
        "Viewers complain about the price.",
        "The comments like the comfort.",
        "The reviewer does not dislike the foam.",
        "The reviewer talks about the price and the comfort.",     # no stance: left alone
        "Other products come up.",                                  # 'Other' is never matched
    ])
    def test_sentences_the_run_supports_pass(self, text):
        assert V.stance_problems(text, self.TOPICS) == []

    @pytest.mark.parametrize("text,fragment", [
        ("The reviewer criticises its design and comfort.", "negative about Comfort"),
        ("The reviewer praises the price.", "positive about Price"),
        ("Viewers complain about the comfort.", "negative about Comfort"),
        ("The comments love the price.", "positive about Price"),
        ("The reviewer does not like the foam.", "negative about Comfort"),
    ])
    def test_the_wrong_direction_is_caught(self, text, fragment):
        problems = V.stance_problems(text, self.TOPICS)
        assert problems and any(fragment in p for p in problems)


class TestShortFields:
    @pytest.mark.parametrize("text,n", [
        ("The words read positive while the face reads negative.", 2),
        ("The reviewer praises the foam.", 0),
        ("What was said is upbeat but the voice sounds flat and the comments disagree.", 3),
    ])
    def test_channels_named(self, text, n):
        assert V.channels_named(text) == n

    @pytest.mark.parametrize("label,generic", [
        ("The tone peaks", True), ("The coolest stretch", True), ("Trying them on", False),
        ("The price", False)])
    def test_generic_turn_labels(self, label, generic):
        assert V.is_generic_turn(label) is generic

    def test_not_worth_is_negative_and_lackluster_counts(self):
        topics = [{"name": "Price", "aspects": ["price"],
                   "reviewer": {"stances": {"praise": 0, "criticism": 0, "mixed": 0}},
                   "audience": {"counts": {}}}]
        assert V.stance_problems("The reviewer says it is not worth the price.", topics)
        assert V.stance_problems("A lacklustre price.", topics)


# ── where a quote is, when Whisper cut the sentence (23 Sep 2026) ────────────

class TestQuoteHome:
    ORDERED = [(44, "example, and I love that Apple did not neglect the half-folded use case."),
               (45, "and the controls drop to the bottom half while the video stays up top. iOS actually adapts to how the"),
               (46, "device is angled or propped, and it slides content away from the crease,"),
               (47, "register. Apple even tunes the audio for changing distance")]

    def test_a_quote_inside_one_segment_is_at_that_segment(self):
        assert V.quote_home("the controls drop to the bottom half", self.ORDERED) == (45, 45)

    def test_a_quote_across_one_cut_is_found_across_that_pair(self):
        """The Apple (Duo) claim that was dropped: its words run over 45 into 46."""
        assert V.quote_home("iOS actually adapts to how the device is angled or propped,",
                            self.ORDERED) == (45, 46)

    def test_a_changed_word_across_the_cut_is_still_refused(self):
        assert V.quote_home("iOS really adapts to how the device is angled", self.ORDERED) is None

    def test_a_quote_over_three_segments_is_refused(self):
        quote = "adapts to how the device is angled or propped, and it slides content away from the crease, register"
        assert V.quote_home(quote, self.ORDERED) is None

    def test_a_quote_in_two_places_is_refused_rather_than_guessed(self):
        ordered = [(1, "it is really good"), (2, "honestly it is really good")]
        assert V.quote_home("it is really good", ordered) is None

    def test_segments_that_are_not_neighbours_are_never_joined(self):
        ordered = [(1, "the battery is"), (2, "unrelated words here"), (3, "great all day")]
        assert V.quote_home("the battery is great all day", ordered) is None


class TestMetaTopics:
    @pytest.mark.parametrize("name,meta", [
        ("The Reviewer", True), ("The reviewer", True), ("About the creator", True),
        ("The channel", True), ("Reviewers", True), ("Video", True),
        ("Video quality", False), ("Price", False), ("Comfort", False), ("Reviewer bias", False)])
    def test_topics_about_the_person_or_the_video(self, name, meta):
        assert V.is_meta_topic(name) is meta

    def test_the_reviewer_as_subject_is_not_read_as_a_topic(self):
        """The Apple (Duo) verdict: correct, and dropped because of a topic named 'The Reviewer'."""
        topics = [{"name": "The Reviewer", "aspects": [],
                   "reviewer": {"stances": {"praise": 0, "criticism": 0, "mixed": 0}},
                   "audience": {"counts": {"POSITIVE": 0, "NEGATIVE": 3}}},
                  {"name": "Design", "aspects": ["design"],
                   "reviewer": {"stances": {"praise": 5, "criticism": 0, "mixed": 0}},
                   "audience": {"counts": {"POSITIVE": 22, "NEGATIVE": 5}}}]
        text = ("The reviewer concludes that the Apple Duo is a premium product with good design "
                "and performance, but criticizes the price.")
        assert not [p for p in V.stance_problems(text, topics) if "Reviewer" in p]

    def test_a_real_topic_is_still_held_to_the_run(self):
        topics = [{"name": "Design", "aspects": ["design"],
                   "reviewer": {"stances": {"praise": 0, "criticism": 2, "mixed": 0}},
                   "audience": {"counts": {}}}]
        assert V.stance_problems("The reviewer praises the design.", topics)


# ── a percentage is held to percentages (24 Sep 2026) ────────────────────────

class TestPercentages:
    SHEET = {"audience": {"comments": 359, "positive": 135, "positive_pct": 38, "negative_pct": 39},
             "themes": [{"audiences_positive_in": 1}]}

    def ctx(self):
        return V.Context(allowed_numbers=V.numbers_in(self.SHEET), allowed_pct=V.percentages_in(self.SHEET),
                         segment_text={1: "the modem is up to 50% faster than before"})

    def test_only_keys_naming_a_percentage_give_percentages(self):
        assert V.percentages_in(self.SHEET) == {38.0, 39.0}

    @pytest.mark.parametrize("text,ok", [
        ("38% of comments are positive.", True),
        ("1% of comments are positive.", False),            # a count of 1, not a percentage
        ("135 comments are positive.", True),
        ("The modem is 50% faster.", False),                 # not in the facts or the evidence cited
    ])
    def test_the_rule(self, text, ok):
        good, problems, _ = V.check_prose(text, ["C0"] if False else [], self.ctx(), max_words=30,
                                          require_evidence=False)
        assert good is ok, problems

    def test_a_percentage_in_the_cited_evidence_is_allowed(self):
        good, problems, _ = V.check_prose('The reviewer says it is "up to 50% faster".', ["S1"], self.ctx(),
                                          max_words=30)
        assert good, problems

    def test_without_a_percentage_set_the_old_rule_holds(self):
        ctx = V.Context(allowed_numbers={1.0})
        assert V.check_prose("1% of them.", [], ctx, max_words=10, require_evidence=False)[0]


class TestBareVideoIds:
    @pytest.mark.parametrize("text,names,refused", [
        ("Videos V1, V3 and V4 praise it.", "", True),
        ("The Pegasus V2 is praised.", "Nike Pegasus V2 review", False),
        ("Video 3 praises it.", "", False),
    ])
    def test_the_rule(self, text, names, refused):
        assert bool(V.ids_in_text(text, names)) is refused


class TestCriticalIsNegative:
    def test_a_clause_with_both_sides_is_left_alone(self):
        """'the reviewer praising it and the audience being critical' was read as praise (24 Sep 2026)."""
        topics = [{"name": "Design", "aspects": ["design"],
                   "reviewer": {"stances": {"praise": 2, "criticism": 0, "mixed": 0}},
                   "audience": {"counts": {"POSITIVE": 8, "NEGATIVE": 16}}}]
        text = "The reviewer and audience disagree on the new design, with the reviewer praising it and the audience being critical."
        assert V.stance_problems(text, topics) == []
        assert V.stance_problems("The comments are critical of the design.", topics) == []
        assert V.stance_problems("The comments love the design.", topics)


class TestCountsAreNotStances:
    def test_a_listed_count_does_not_hide_the_direction_beside_it(self):
        """'mostly negative ... with 139 negative comments, 135 positive' over a balanced audience."""
        text = ("The audiences are negative about the product, with 139 negative comments, "
                "135 positive comments, and 85 neutral comments.")
        assert V.audience_direction_problems(text, "balanced")

    def test_a_bare_count_says_nothing_about_direction(self):
        assert V.audience_direction_problems("There are 139 negative comments and 135 positive.", "balanced") == []

    def test_mostly_is_a_proportion_the_verifier_cannot_check(self):
        ok, problems, _ = V.check_prose("The audience is mostly negative.", [], V.Context(), max_words=20,
                                        require_evidence=False)
        assert not ok and any("proportion" in p for p in problems)


# ── a moment note against the readings it describes (24 Sep 2026) ───────────

class TestMomentClaims:
    """
    The final user evaluation found a moment card whose note said the voice read
    positive beside a grid that said neutral; the same check over every stored
    note then dropped 34 of 46. Each case below is a real stored note, with the
    labels its moment actually carried.
    """
    DUO_0_05 = {"transcript": "NEUTRAL", "vocal": "NEUTRAL", "comment": "POSITIVE"}
    DUO_0_40 = {"transcript": "NEGATIVE", "vocal": "NEUTRAL", "comment": "POSITIVE"}

    def test_the_0_05_note_misreads_the_face_and_the_voice(self):
        text = "The words read neutral, but the face and voice read positive, while the comments read positive."
        assert V.moment_claim_problems(text, self.DUO_0_05) == [
            "says the face read positive; the face was not read at this moment",
            "says the voice read positive; it read neutral"]

    def test_the_0_40_note_misreads_the_voice(self):
        text = "The words read negative, but the voice and comments read positive."
        assert V.moment_claim_problems(text, self.DUO_0_40) == ["says the voice read positive; it read neutral"]

    def test_a_face_given_a_reading_where_none_was_read(self):
        text = "The words read positive as the reviewer praises the design, while the face reads negative."
        valences = {"transcript": "POSITIVE", "vocal": "POSITIVE", "comment": "NEGATIVE"}
        assert V.moment_claim_problems(text, valences) == [
            "says the face read negative; the face was not read at this moment"]

    def test_a_list_of_readings_keeps_its_valence_across_the_commas(self):
        text = "The words, face, voice, and comments all read positive. The reviewer is introducing the phone."
        valences = {"transcript": "NEUTRAL", "facial": "NEUTRAL", "vocal": "NEUTRAL", "comment": "POSITIVE"}
        assert V.moment_claim_problems(text, valences) == [
            "says the face read positive; it read neutral",
            "says the voice read positive; it read neutral",
            "says the words read positive; it read neutral"]

    @pytest.mark.parametrize("text, valences", [
        ("The words and face read neutral, but the voice and comments read positive.",
         {"transcript": "NEUTRAL", "facial": "NEUTRAL", "vocal": "POSITIVE", "comment": "POSITIVE"}),
        ("The words read positive as the reviewer praises the watch's health tracking features, "
         "while the face reads negative and the voice is neutral.",
         {"transcript": "POSITIVE", "facial": "NEGATIVE", "vocal": "NEUTRAL", "comment": "POSITIVE"}),
        ("The words read neutral, but the voice and comments are negative, discussing the new design.",
         {"transcript": "NEUTRAL", "vocal": "NEGATIVE", "comment": "NEGATIVE"}),
        ("The words read positive as the reviewer talks about the shoe's idea, while the face is neutral "
         "and the comments are neutral.",
         {"transcript": "POSITIVE", "facial": "NEUTRAL", "vocal": "NEGATIVE", "comment": "NEUTRAL"}),
    ])
    def test_true_notes_pass(self, text, valences):
        assert V.moment_claim_problems(text, valences) == []

    @pytest.mark.parametrize("text", [
        "The words criticise the price while the face reads sad.",       # no valence word: not judged
        "The reviewer sounds positive although he said the price is too high.",  # no channel named
        "",
        None,
    ])
    def test_what_it_cannot_read_it_leaves_alone(self, text):
        assert V.moment_claim_problems(text, {"transcript": "NEGATIVE"}) == []

    def test_a_clause_still_ambiguous_after_splitting_on_and_is_not_judged(self):
        text = "The words and face are positive or negative depending on the moment."
        assert V.moment_claim_problems(text, {"transcript": "NEUTRAL", "facial": "NEUTRAL"}) == []

    def test_labels_are_compared_without_regard_to_case_and_missing_labels_mean_unread(self):
        assert V.moment_claim_problems("The voice reads neutral.", {"vocal": "neutral"}) == []
        assert V.moment_claim_problems("The voice reads neutral.", {"vocal": None}) == [
            "says the voice read neutral; the voice was not read at this moment"]
        assert V.moment_claim_problems("The voice reads neutral.", None) == [
            "says the voice read neutral; the voice was not read at this moment"]
