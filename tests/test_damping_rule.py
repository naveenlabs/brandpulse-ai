"""
Unit tests for the deterministic vocal down-weighting rule (orchestrator.py).

Why this file exists. The original down-weighting asked the controller which
channels it thought were in conflict and damped when the answer was "the vocal one".
`vocal_bench/CORPUS_AB_RESULT.md` §3.2 measured that path firing on **0 of 479
segments**: llama3.2 populates `channels_in_conflict` but decouples it from its own
score. A protection that never fires is not a protection, so the trigger was
replaced by one computed from the channel labels the pipeline already holds.

What is tested here is that replacement, `_vocal_is_sole_dissenter`, and the two
functions it rests on. It is pure arithmetic over dicts - no Ollama, no network, no
model - so none of it is mocked. Every condition of the rule is tested in BOTH
directions: firing when it should, and staying silent when it should not. A
down-weighting that fires too eagerly raises the Authenticity Score, which is the
direction that flatters the system, so the negative cases matter more than the
positive ones.

`tests/test_vocal_channel.py::TestDamping` covers the arithmetic of the damping
itself and the older controller-attribution trigger; both still apply and are
unchanged.
"""

import pytest

from pipeline import orchestrator as O


def seg(transcript=None, vocal=None, facial=None, **extra):
    """A segment carrying only the channels a test cares about."""
    s = {"segment_id": 3, "start_time": 0.0, "end_time": 4.0}
    if transcript is not None:
        s["transcript_sentiment"] = {"label": transcript, "confidence": 0.9}
    if vocal is not None:
        s["vocal_emotion"] = {"label": vocal, "arousal": 0.5, "reliability": 0.489}
    if facial is not None:
        s["facial_emotion"] = {"dominant": facial, "confidence": 0.8}
    s.update(extra)
    return s


def comments(label):
    return {"label": label, "confidence": 0.8}


# ────────────────────────────────────────────────────────── valence normalisation

class TestValenceMapping:
    @pytest.mark.parametrize("word,expected", [
        ("POSITIVE", "POSITIVE"), ("positive", "POSITIVE"), ("  Positive ", "POSITIVE"),
        ("NEUTRAL", "NEUTRAL"), ("NEGATIVE", "NEGATIVE"),
    ])
    def test_the_three_class_labels_pass_through_case_insensitively(self, word, expected):
        assert O._to_valence(word) == expected

    @pytest.mark.parametrize("word,expected", [
        ("happy", "POSITIVE"), ("neutral", "NEUTRAL"), ("sad", "NEGATIVE"),
        ("angry", "NEGATIVE"), ("fear", "NEGATIVE"), ("disgust", "NEGATIVE"),
    ])
    def test_deepface_and_legacy_iemocap_words_map_onto_the_valence_axis(
            self, word, expected):
        assert O._to_valence(word) == expected

    def test_surprise_is_not_placed_on_the_valence_axis(self):
        """Ambiguous by construction: it accompanies delight and dismay equally.
        Excluding it makes the rule fire less often, never more."""
        assert O._to_valence("surprise") is None

    @pytest.mark.parametrize("bad", [None, "", "   ", "unknown", "UNKNOWN",
                                     "contempt", 3, 0.5, True, [], {}])
    def test_anything_unusable_returns_none_rather_than_neutral(self, bad):
        assert O._to_valence(bad) is None

    def test_declining_to_answer_stays_distinct_from_answering_neutral(self):
        assert O._to_valence("unknown") is None
        assert O._to_valence("neutral") == "NEUTRAL"


# ─────────────────────────────────────────────────────────── channel collection

class TestChannelValences:
    def test_collects_every_readable_channel(self):
        got = O._channel_valences(
            seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy"),
            comments("POSITIVE"))
        assert got == {"transcript": "POSITIVE", "vocal": "NEGATIVE",
                       "facial": "POSITIVE", "comment": "POSITIVE"}

    def test_unreadable_channels_are_omitted_not_defaulted(self):
        got = O._channel_valences(
            seg(transcript="POSITIVE", vocal="unknown", facial="surprise"), None)
        assert got == {"transcript": "POSITIVE"}

    def test_a_segment_with_no_channels_yields_nothing(self):
        assert O._channel_valences({"segment_id": 1}, None) == {}

    def test_a_pre_02_sep_segment_storing_a_bare_string_still_reads(self):
        """Backwards compatibility: the vocal channel used to be an IEMOCAP word."""
        got = O._channel_valences({"vocal_emotion": "angry"}, None)
        assert got == {"vocal": "NEGATIVE"}

    @pytest.mark.parametrize("junk", [
        {"transcript_sentiment": "not a dict"},
        {"facial_emotion": []},
        {"vocal_emotion": 42},
        {"transcript_sentiment": {"label": None}},
        {"facial_emotion": {"dominant": None}},
    ])
    def test_malformed_channels_are_skipped_rather_than_raising(self, junk):
        assert O._channel_valences(junk, None) == {}

    def test_a_malformed_comment_channel_is_skipped(self):
        assert "comment" not in O._channel_valences(seg(transcript="POSITIVE"), "nope")

    def test_no_face_detected_is_not_a_neutral_face(self):
        got = O._channel_valences(
            seg(transcript="POSITIVE", facial=None,
                facial_emotion={"dominant": None, "confidence": 0.0}), None)
        assert "facial" not in got


# ─────────────────────────────────────────────────────────── the rule itself

class TestSoleDissenter:
    def test_fires_when_vocal_alone_breaks_a_consensus(self):
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy"), None) is True

    def test_fires_using_the_video_level_comment_channel_as_a_corroborator(self):
        """The corpus has no extracted frames, so transcript + comments is the
        realistic two-channel consensus this rule has to work with."""
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="NEGATIVE"), comments("POSITIVE")) is True

    def test_silent_when_the_other_channels_disagree_among_themselves(self):
        """Then the conflict does not rest on the vocal channel at all."""
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="NEGATIVE", facial="sad"), None) is False

    def test_silent_when_the_vocal_channel_agrees_with_the_consensus(self):
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="POSITIVE", facial="happy"), None) is False

    def test_silent_when_the_vocal_channel_has_no_reading(self):
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="unknown", facial="happy"), None) is False

    def test_silent_with_only_one_corroborating_channel(self):
        """With a single comparator, 'the others agree' is vacuous and the
        disagreement is a coin flip between two channels, not a lone dissent."""
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="NEGATIVE"), None) is False

    def test_silent_when_no_channel_at_all_is_readable(self):
        assert O._vocal_is_sole_dissenter({"segment_id": 1}, None) is False

    def test_neutral_counts_as_a_position_not_as_an_absence(self):
        assert O._vocal_is_sole_dissenter(
            seg(transcript="NEUTRAL", vocal="POSITIVE", facial="neutral"), None) is True

    def test_an_ambiguous_face_does_not_count_toward_the_consensus(self):
        """surprise is unreadable, so only transcript remains and the minimum of
        two corroborating channels is not met."""
        assert O._vocal_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="NEGATIVE", facial="surprise"), None) is False

    def test_three_corroborators_all_agreeing_still_fires(self):
        assert O._vocal_is_sole_dissenter(
            seg(transcript="NEGATIVE", vocal="POSITIVE", facial="sad"),
            comments("NEGATIVE")) is True

    def test_the_threshold_is_a_named_constant_not_a_literal(self):
        assert O.MIN_CORROBORATING_CHANNELS == 2

    def test_the_rule_never_raises_on_arbitrary_junk(self):
        for junk in ({}, {"vocal_emotion": None}, {"vocal_emotion": {"label": []}},
                     {"transcript_sentiment": 1, "vocal_emotion": "sad"}):
            assert O._vocal_is_sole_dissenter(junk, None) is False


# ─────────────────────────────────────────── the rule wired into the coercion

class TestTriggerIntegration:
    RAW = {"conflict_score": 0.90, "channels_in_conflict": []}

    def test_the_structural_trigger_damps_where_attribution_would_not(self):
        """The whole point of the fix: an empty channels_in_conflict - what
        llama3.2 supplies 216 times out of 481 - used to mean no damping."""
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        out = O._coerce_result(dict(self.RAW), s)
        assert out["conflict_score"] == pytest.approx(
            round(0.90 * O.VOCAL_ONLY_CONFLICT_WEIGHT, 4))
        assert out["flagged"] is False

    def test_the_reason_names_which_trigger_fired(self):
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        note = [r for r in O._coerce_result(dict(self.RAW), s)["conflict_reasons"]
                if "vocal_channel_downweighted" in r]
        assert len(note) == 1 and "[structural]" in note[0]

    def test_both_triggers_firing_is_recorded_as_both(self):
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        raw = {"conflict_score": 0.90, "channels_in_conflict": ["vocal_emotion"]}
        note = [r for r in O._coerce_result(raw, s)["conflict_reasons"]
                if "vocal_channel_downweighted" in r]
        assert "[attributed+structural]" in note[0]

    def test_the_attribution_trigger_still_works_on_its_own(self):
        """Preserved behaviour: it is inert on llama3.2, not removed."""
        raw = {"conflict_score": 0.90, "channels_in_conflict": ["vocal_emotion"]}
        note = [r for r in O._coerce_result(raw, {"segment_id": 1})["conflict_reasons"]
                if "vocal_channel_downweighted" in r]
        assert "[attributed]" in note[0]

    def test_a_genuine_multi_channel_conflict_is_left_at_full_strength(self):
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="sad")
        out = O._coerce_result(dict(self.RAW), s)
        assert out["conflict_score"] == pytest.approx(0.90)
        assert out["flagged"] is True

    def test_a_stale_flagged_boolean_is_overridden_by_the_structural_trigger(self):
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        raw = {"conflict_score": 0.90, "flagged": True, "channels_in_conflict": []}
        assert O._coerce_result(raw, s)["flagged"] is False

    def test_a_zero_score_is_never_damped_by_either_trigger(self):
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        out = O._coerce_result({"conflict_score": 0.0}, s)
        assert out["conflict_score"] == 0.0
        assert not any("downweighted" in r for r in out["conflict_reasons"])

    def test_comment_sentiment_reaches_the_rule_through_analyse_segment(self,
                                                                       monkeypatch):
        """The comment channel is passed separately from the segment, so this is
        the wire that would silently break without a test."""
        seen = {}

        def fake(data, segment, comment_sentiment=None):
            seen["cs"] = comment_sentiment
            return {"segment_id": 1, "start_s": 0.0, "end_s": 1.0,
                    "conflict_score": 0.0, "conflict_reasons": [], "flagged": False}

        monkeypatch.setattr(O, "_call_ollama", lambda _: '{"conflict_score": 0.5}')
        monkeypatch.setattr(O, "_coerce_result", fake)
        O.analyse_segment(seg(transcript="POSITIVE", vocal="NEGATIVE"),
                          comments("POSITIVE"))
        assert seen["cs"] == comments("POSITIVE")

    def test_coerce_result_still_accepts_two_arguments(self):
        """Callers written before the comment channel was threaded through must
        keep working - vocal_bench/corpus_ab.py is one of them."""
        out = O._coerce_result({"conflict_score": 0.4}, {"segment_id": 9})
        assert out["conflict_score"] == pytest.approx(0.4)


# ──────────────────────────────────────────────── the measurement harness itself

class TestDampingHarness:
    """`vocal_bench/damping_ab.py` mutates orchestrator module globals to switch
    variants. A leaked mutation would silently corrupt every later test and every
    later pipeline call in the same process, so the restoration is tested - and
    tested on the failure path, which is the one that leaks."""

    @staticmethod
    def _harness():
        import sys
        from pathlib import Path
        bench = Path(__file__).resolve().parent.parent / "research" / "vocal_bench"
        sys.path.insert(0, str(bench))
        import damping_ab
        return damping_ab

    def test_the_variant_table_covers_the_baseline_and_the_proposal(self):
        D = self._harness()
        assert D.BASELINE in D.VARIANTS and D.PROPOSED in D.VARIANTS
        assert D.VARIANTS[D.BASELINE] == (1.0, None)      # 1.0 is the identity
        assert D.VARIANTS[D.PROPOSED] == (O.VOCAL_ONLY_CONFLICT_WEIGHT,
                                          O.MIN_CORROBORATING_CHANNELS)

    def test_the_off_switch_makes_the_structural_trigger_unsatisfiable(self):
        """Disabling by raising the threshold, rather than by patching the
        function out, keeps the real code path under test."""
        D = self._harness()
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        assert O._vocal_is_sole_dissenter(s, comments("POSITIVE")) is True
        old = O.MIN_CORROBORATING_CHANNELS
        O.MIN_CORROBORATING_CHANNELS = D._STRUCTURAL_OFF
        try:
            assert O._vocal_is_sole_dissenter(s, comments("POSITIVE")) is False
        finally:
            O.MIN_CORROBORATING_CHANNELS = old

    @staticmethod
    def _a_cached_video(D):
        vids = D.videos("after_nodamp") if (D.CACHE / "conflict_after_nodamp").is_dir() else []
        if not vids:
            pytest.skip("A/B caches not present in this checkout")
        return vids[0]

    def test_recoerce_restores_the_globals_when_coercion_raises(self, monkeypatch):
        """The real leak risk is a failure INSIDE the try block - a read failure
        before it never touches the globals at all."""
        D = self._harness()
        video = self._a_cached_video(D)
        before = (O.VOCAL_ONLY_CONFLICT_WEIGHT, O.MIN_CORROBORATING_CHANNELS)

        def boom(*_a, **_k):
            raise RuntimeError("coercion failed mid-loop")

        monkeypatch.setattr(O, "_coerce_result", boom)
        with pytest.raises(RuntimeError):
            D.recoerce(video, "structural_min1", "after_nodamp")
        assert (O.VOCAL_ONLY_CONFLICT_WEIGHT, O.MIN_CORROBORATING_CHANNELS) == before

    def test_coverage_restores_the_global_when_the_rule_raises(self, monkeypatch):
        D = self._harness()
        video = self._a_cached_video(D)
        before = O.MIN_CORROBORATING_CHANNELS

        def boom(*_a, **_k):
            raise RuntimeError("rule failed mid-loop")

        monkeypatch.setattr(O, "_vocal_is_sole_dissenter", boom)
        with pytest.raises(RuntimeError):
            D.coverage(video, 1, "after_nodamp")
        assert O.MIN_CORROBORATING_CHANNELS == before

    def test_recoerce_leaves_the_globals_at_their_deployed_values_on_success(self):
        D = self._harness()
        video = self._a_cached_video(D)
        D.recoerce(video, "nodamp", "after_nodamp")
        assert O.VOCAL_ONLY_CONFLICT_WEIGHT == 0.489
        assert O.MIN_CORROBORATING_CHANNELS == 2

    def test_the_deployed_constants_are_what_the_document_reports(self):
        """DAMPING_FIX_RESULT.md §5.2 quotes 0.3300 -> 0.1614 for all 17 damped
        segments. That is exactly the deployed weight, so it is asserted here as
        well as in the verifier."""
        assert round(0.33 * O.VOCAL_ONLY_CONFLICT_WEIGHT, 4) == 0.1614


# ══════════════════════════════════════════════════════════════════════════════
# The same rule for the facial channel, added 04 Sep 2026.
#
# `facial_bench/v2/` scored nine emotion models against 320 purpose-collected
# frame labels split by speaker. Nothing was adopted: on the holdout every model
# scored below an always-NEUTRAL constant, the deployed one by 33.3 points, and it
# calls 33.8% of verified-neutral frames NEGATIVE. That last number is why this
# damping matters — the channel's characteristic error is *manufacturing*
# negativity, which is precisely what becomes a cross-channel conflict and then a
# flag. PROTOCOL.md §9 pre-committed to this change before the results were read.
#
# Same structure as the vocal tests above, and for the same reason: a
# down-weighting that fires too eagerly raises the Authenticity Score, which is
# the direction that flatters the system, so the negative cases matter most.
# ══════════════════════════════════════════════════════════════════════════════

class TestFacialSoleDissenter:
    def test_fires_when_facial_alone_breaks_a_consensus(self):
        assert O._facial_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="POSITIVE", facial="sad"),
            comments("POSITIVE")) is True

    def test_silent_when_the_other_channels_disagree_among_themselves(self):
        assert O._facial_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="NEGATIVE", facial="sad"),
            comments("POSITIVE")) is False

    def test_silent_when_the_facial_channel_agrees_with_the_consensus(self):
        assert O._facial_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="POSITIVE", facial="happy"),
            comments("POSITIVE")) is False

    def test_silent_when_no_face_was_detected(self):
        """`dominant: None` means the channel declined, not that it said neutral."""
        s = seg(transcript="POSITIVE", vocal="POSITIVE")
        s["facial_emotion"] = {"dominant": None, "confidence": 0.0, "frame_count": 0}
        assert O._facial_is_sole_dissenter(s, comments("POSITIVE")) is False

    def test_silent_with_only_one_corroborating_channel(self):
        assert O._facial_is_sole_dissenter(
            seg(transcript="POSITIVE", facial="sad"), None) is False

    def test_an_ambiguous_face_is_not_a_dissent(self):
        """`surprise` is off the valence axis, so the channel has no reading."""
        assert O._facial_is_sole_dissenter(
            seg(transcript="POSITIVE", vocal="POSITIVE", facial="surprise"),
            comments("POSITIVE")) is False

    def test_the_rule_never_raises_on_arbitrary_junk(self):
        for junk in ({}, {"facial_emotion": None}, {"facial_emotion": {"dominant": []}},
                     {"transcript_sentiment": 1, "facial_emotion": "happy"}):
            assert O._facial_is_sole_dissenter(junk, None) is False

    @pytest.mark.parametrize("transcript,vocal,facial,comment", [
        ("POSITIVE", "NEGATIVE", "happy", "POSITIVE"),
        ("POSITIVE", "POSITIVE", "sad", "POSITIVE"),
        ("NEGATIVE", "POSITIVE", "sad", "NEGATIVE"),
        ("NEUTRAL", "NEUTRAL", "happy", "NEUTRAL"),
        ("POSITIVE", "NEGATIVE", "sad", "POSITIVE"),
        ("NEUTRAL", "POSITIVE", "happy", "NEGATIVE"),
    ])
    def test_the_two_channels_can_never_both_be_the_sole_dissenter(
            self, transcript, vocal, facial, comment):
        """
        A property, not a coincidence: if the vocal channel is the lone dissenter
        then every *other* channel agrees, and the facial channel is one of those
        others. `_coerce_result` relies on this — it is why the two weights are
        never multiplied together in the ordinary case.
        """
        s = seg(transcript=transcript, vocal=vocal, facial=facial)
        c = comments(comment)
        assert not (O._vocal_is_sole_dissenter(s, c)
                    and O._facial_is_sole_dissenter(s, c))


class TestFacialAttribution:
    @pytest.mark.parametrize("name", [
        "facial_emotion", "facial emotion", "facialEmotion", "face",
        "FACIAL", "visual", "deepface", "facial-expression",
    ])
    def test_recognised_names_for_the_facial_channel(self, name):
        assert O._conflict_rests_only_on_facial([name])

    @pytest.mark.parametrize("channels", [
        ["vocal_emotion"], ["transcript_sentiment"], ["comment_sentiment"],
        ["facial_emotion", "transcript_sentiment"],
    ])
    def test_not_fired_when_another_channel_is_named(self, channels):
        assert not O._conflict_rests_only_on_facial(channels)

    def test_an_empty_attribution_is_not_an_attribution(self):
        assert not O._conflict_rests_only_on_facial([])

    @pytest.mark.parametrize("value", [None, "facial", 42, {"a": 1}])
    def test_a_malformed_attribution_never_raises(self, value):
        assert O._conflict_rests_only_on_facial(value) is False

    def test_the_two_alias_sets_are_disjoint(self):
        """A name that matched both would damp by whichever weight sorted first."""
        assert O._VOCAL_CHANNEL_ALIASES & O._FACIAL_CHANNEL_ALIASES == frozenset()


class TestFacialDampingIntegration:
    RAW = {"conflict_score": 0.90, "channels_in_conflict": []}

    def _sole_facial(self):
        return seg(transcript="POSITIVE", vocal="POSITIVE", facial="sad")

    def test_the_weight_is_the_channels_measured_reliability(self):
        from pipeline.visual_module import FACIAL_CHANNEL_RELIABILITY
        assert O.FACIAL_ONLY_CONFLICT_WEIGHT == FACIAL_CHANNEL_RELIABILITY
        assert O.FACIAL_ONLY_CONFLICT_WEIGHT == 0.342

    def test_the_facial_channel_is_damped_harder_than_the_vocal_one(self):
        """It measures worse, so it must weigh less. 0.342 < 0.489."""
        assert O.FACIAL_ONLY_CONFLICT_WEIGHT < O.VOCAL_ONLY_CONFLICT_WEIGHT

    def test_a_conflict_resting_on_the_face_alone_is_damped(self):
        out = O._coerce_result(dict(self.RAW), self._sole_facial(),
                               comments("POSITIVE"))
        assert out["conflict_score"] == pytest.approx(
            round(0.90 * O.FACIAL_ONLY_CONFLICT_WEIGHT, 4))

    def test_the_reason_names_the_channel_and_the_trigger(self):
        out = O._coerce_result(dict(self.RAW), self._sole_facial(),
                               comments("POSITIVE"))
        note = [r for r in out["conflict_reasons"]
                if "facial_channel_downweighted" in r]
        assert len(note) == 1
        assert "[structural]" in note[0]
        assert "0.9000 -> 0.3078" in note[0]

    def test_the_flag_is_recomputed_against_the_damped_score(self):
        """A stale `flagged: true` formed against 0.90 must not survive."""
        raw = {"conflict_score": 0.90, "flagged": True, "channels_in_conflict": []}
        out = O._coerce_result(raw, self._sole_facial(), comments("POSITIVE"))
        assert out["conflict_score"] < O.CONFLICT_FLAG_THRESHOLD
        assert out["flagged"] is False

    def test_a_genuine_multi_channel_conflict_is_left_alone(self):
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="sad")
        out = O._coerce_result(dict(self.RAW), s, comments("POSITIVE"))
        assert out["conflict_score"] == pytest.approx(0.90)
        assert not any("downweighted" in r for r in out["conflict_reasons"])

    def test_a_zero_score_is_not_damped(self):
        raw = {"conflict_score": 0.0, "channels_in_conflict": []}
        out = O._coerce_result(raw, self._sole_facial(), comments("POSITIVE"))
        assert out["conflict_score"] == 0.0
        assert not any("downweighted" in r for r in out["conflict_reasons"])

    def test_contradictory_triggers_apply_one_weight_not_their_product(self):
        """
        The controller blames the vocal channel; the pipeline's own labels say the
        facial channel is the lone dissenter. Only one of them can be right, so
        multiplying 0.489 x 0.342 = 0.167 would treat a contradiction as two
        independent pieces of evidence. The smaller weight is applied once.
        """
        raw = {"conflict_score": 0.90, "channels_in_conflict": ["vocal_emotion"]}
        out = O._coerce_result(raw, self._sole_facial(), comments("POSITIVE"))
        notes = [r for r in out["conflict_reasons"] if "downweighted" in r]
        assert len(notes) == 1
        assert "facial_channel_downweighted" in notes[0]
        assert out["conflict_score"] == pytest.approx(
            round(0.90 * O.FACIAL_ONLY_CONFLICT_WEIGHT, 4))
        assert out["conflict_score"] != pytest.approx(
            round(0.90 * O.VOCAL_ONLY_CONFLICT_WEIGHT
                  * O.FACIAL_ONLY_CONFLICT_WEIGHT, 4))

    def test_the_vocal_rule_is_unchanged_by_all_this(self):
        """Regression guard: the 02 Sep behaviour must survive the generalisation."""
        s = seg(transcript="POSITIVE", vocal="NEGATIVE", facial="happy")
        out = O._coerce_result(dict(self.RAW), s)
        assert out["conflict_score"] == pytest.approx(
            round(0.90 * O.VOCAL_ONLY_CONFLICT_WEIGHT, 4))
        assert any("vocal_channel_downweighted[structural]" in r
                   for r in out["conflict_reasons"])
