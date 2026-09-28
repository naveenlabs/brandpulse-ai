"""
test_controller_bench.py — unit tests for the controller bench.

Scope: every piece of arithmetic and every normalisation or
coercion function is exercised for real. No model is loaded, no Ollama call is
made, no network is touched — `run_probe`'s LLM path is tested with the
production `_call_ollama` patched, which is the boundary the project's testing rule
names (mock I/O and model calls, never the arithmetic).

What is deliberately covered:
  - `stats`: every statistic against values derived independently by hand, plus
    the three degenerate cases that would otherwise be silently wrong — a
    constant predictor's MCC, a zero-discordant McNemar, and an n=0 Wilson;
  - the two-sided McNemar direction trap `facial_bench/v2` §6 documented: a model
    that is significantly WORSE must not be reported as better;
  - `reference`: the valence map, the pair-weighting arithmetic, the "no readable
    valence is never coerced to NEUTRAL" rule, and the alias normalisation that
    stops a model being penalised for saying `comment_sentiment`;
  - `probes`: the grid is complete, unique, and varies ONLY the four channel
    labels — the property the whole primary metric rests on;
  - `run_bench.revised_prompt`: it preserves the deployed prompt verbatim and
    fails loudly if its insertion marker ever moves;
  - `report_bench`: the metric arithmetic on hand-built runs, and the adoption
    rule evaluated condition by condition;
  - the failure paths that actually occur: an unreachable Ollama, unparseable
    JSON, a response missing every key, a cache file that does not exist.
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
CB = ROOT / "research" / "controller_bench"

# Bare module names are shared across the five bench directories in this repo
# (`candidates` and `report_bench` exist in four of them, `run_bench` in three).
# Same save/pop/import/restore discipline as tests/test_facial_bench_v2.py, and
# for the same reason: an unrestored sys.modules entry makes a LATER bench's test
# file import this bench's module under the shared name.
_SHARED_NAMES = ("candidates", "report_bench", "run_bench", "reference",
                 "probes", "stats", "ground_truth", "corpus_ab")


def _load():
    saved = {n: sys.modules.pop(n, None) for n in _SHARED_NAMES}
    sys.path.insert(0, str(CB))
    try:
        import candidates
        import probes
        import reference
        import report_bench
        import run_bench
        import stats
        return stats, reference, probes, candidates, run_bench, report_bench
    finally:
        for n in _SHARED_NAMES:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]
        while str(CB) in sys.path:
            sys.path.remove(str(CB))


S, R, P, C, RB, RPT = _load()

from pipeline import orchestrator as O  # noqa: E402


# ══════════════════════════════════════════════════════════ stats


class TestWilson(unittest.TestCase):
    def test_known_interval(self):
        # 8/81, the incumbent's corpus polar-detection rate. Hand-checked against
        # the closed form: centre (p + z^2/2n)/(1 + z^2/n).
        lo, hi = S.wilson(8, 81)
        self.assertAlmostEqual(lo, 0.05090011626879836, places=12)
        self.assertAlmostEqual(hi, 0.18296501401647305, places=12)

    def test_stays_inside_unit_interval_at_both_ends(self):
        for k, n in ((0, 20), (20, 20), (0, 1), (1, 1)):
            lo, hi = S.wilson(k, n)
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)
            self.assertLessEqual(lo, hi)

    def test_zero_n_is_no_information(self):
        self.assertEqual(S.wilson(0, 0), (0.0, 1.0))

    def test_interval_contains_the_point_estimate(self):
        for k, n in ((3, 10), (50, 108), (81, 108), (1, 481)):
            lo, hi = S.wilson(k, n)
            self.assertLessEqual(lo, k / n)
            self.assertGreaterEqual(hi, k / n)

    def test_narrows_as_n_grows(self):
        a = S.wilson(5, 10)
        b = S.wilson(500, 1000)
        self.assertLess(b[1] - b[0], a[1] - a[0])


class TestMcc(unittest.TestCase):
    def test_perfect_agreement(self):
        g = [True, True, False, False]
        self.assertAlmostEqual(S.mcc(g, list(g)), 1.0)

    def test_perfect_disagreement(self):
        g = [True, True, False, False]
        self.assertAlmostEqual(S.mcc(g, [not x for x in g]), -1.0)

    def test_constant_predictor_scores_exactly_zero(self):
        # The property MCC was chosen for (PROTOCOL.md §5.2). always_zero and
        # always_flag must both land on 0.0 whatever the class balance, or the
        # primary metric could be won by refusing to answer.
        gold = [True] * 102 + [False] * 6
        self.assertEqual(S.mcc(gold, [False] * 108), 0.0)
        self.assertEqual(S.mcc(gold, [True] * 108), 0.0)

    def test_hand_computed_value(self):
        # tp=3 tn=4 fp=1 fn=2  ->  (12-2)/sqrt(4*5*5*6) = 10/sqrt(600)
        gold = [True] * 5 + [False] * 5
        pred = [True, True, True, False, False, True, False, False, False, False]
        self.assertAlmostEqual(S.mcc(gold, pred), 10 / math.sqrt(600), places=12)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            S.mcc([True], [True, False])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            S.mcc([], [])

    def test_constant_gold_is_zero_not_one(self):
        # Undefined (zero denominator), reported as "no correlation demonstrated".
        self.assertEqual(S.mcc([True] * 5, [True] * 5), 0.0)


class TestConfusion(unittest.TestCase):
    def test_counts_and_rates(self):
        gold = [True, True, True, False, False]
        pred = [True, False, True, True, False]
        c = S.confusion(gold, pred)
        self.assertEqual((c["tp"], c["fn"], c["fp"], c["tn"]), (2, 1, 1, 1))
        self.assertAlmostEqual(c["sensitivity"], 2 / 3)
        self.assertAlmostEqual(c["specificity"], 1 / 2)

    def test_rates_are_none_when_undefined(self):
        c = S.confusion([True, True], [True, True])
        self.assertIsNone(c["specificity"])


class TestSpearman(unittest.TestCase):
    def test_monotone_is_one(self):
        self.assertAlmostEqual(S.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)

    def test_reversed_is_minus_one(self):
        self.assertAlmostEqual(S.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_constant_vector_is_zero(self):
        # A controller answering 0.0 on every probe is one giant tie.
        self.assertEqual(S.spearman([0.0] * 8, [0.1, 0.2, 0.3, 0.4] * 2), 0.0)

    def test_average_ranks_for_ties(self):
        # [1,1,2] ranks to [1.5,1.5,3]; against [5,5,9] the correlation is exact.
        self.assertAlmostEqual(S.spearman([1, 1, 2], [5, 5, 9]), 1.0)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            S.spearman([1, 2], [1])

    def test_single_observation_is_zero(self):
        self.assertEqual(S.spearman([1.0], [2.0]), 0.0)


class TestMcnemar(unittest.TestCase):
    def test_no_discordant_pairs_is_p_one(self):
        self.assertEqual(S.mcnemar_exact(0, 0), 1.0)

    def test_symmetric_in_its_arguments(self):
        self.assertEqual(S.mcnemar_exact(3, 11), S.mcnemar_exact(11, 3))

    def test_hand_computed_small_case(self):
        # 0 vs 6: two-sided exact = 2 * C(6,0) * 0.5^6 = 2/64 = 0.03125
        self.assertAlmostEqual(S.mcnemar_exact(0, 6), 0.03125, places=10)

    def test_clamped_at_one(self):
        self.assertLessEqual(S.mcnemar_exact(5, 5), 1.0)

    def test_verdict_requires_direction_as_well_as_significance(self):
        # The trap facial_bench/v2 §6 documents: a two-sided test also fires for a
        # model that is significantly WORSE.
        worse = S.mcnemar_verdict(0, 12)
        self.assertLess(worse["p"], 0.05)
        self.assertFalse(worse["better"])
        self.assertTrue(worse["worse"])

        better = S.mcnemar_verdict(12, 0)
        self.assertLess(better["p"], 0.05)
        self.assertTrue(better["better"])
        self.assertFalse(better["worse"])

    def test_verdict_not_significant_is_neither(self):
        v = S.mcnemar_verdict(4, 3)
        self.assertGreater(v["p"], 0.05)
        self.assertFalse(v["better"])
        self.assertFalse(v["worse"])
        self.assertEqual(v["n_discordant"], 7)


class TestMeanCi(unittest.TestCase):
    def test_mean_and_symmetric_interval(self):
        m, lo, hi = S.mean_ci([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(m, 2.5)
        self.assertAlmostEqual(m - lo, hi - m)

    def test_empty_and_singleton(self):
        self.assertEqual(S.mean_ci([]), (0.0, 0.0, 0.0))
        self.assertEqual(S.mean_ci([7.0]), (7.0, 7.0, 7.0))


# ══════════════════════════════════════════════════════════ reference


class TestValenceMapping(unittest.TestCase):
    def test_uses_the_production_vocabulary(self):
        self.assertEqual(R.to_valence("happy"), "POSITIVE")
        self.assertEqual(R.to_valence("SAD"), "NEGATIVE")
        self.assertEqual(R.to_valence("  neutral "), "NEUTRAL")

    def test_off_axis_labels_have_no_reading(self):
        # Never coerced to NEUTRAL — a channel that declined to answer must stay
        # distinguishable from one that answered "neutral".
        for x in ("surprise", "none detected", "unknown", "", None, 3, [], "  "):
            self.assertIsNone(R.to_valence(x), x)

    def test_matches_the_orchestrator_map_exactly(self):
        for word, expected in O._VALENCE_WORDS.items():
            self.assertEqual(R.to_valence(word), expected)


class TestChannelValences(unittest.TestCase):
    def test_omits_unreadable_channels(self):
        v = R.channel_valences({
            "transcript_sentiment": "POSITIVE", "vocal_emotion": "NEUTRAL",
            "facial_emotion": "none detected", "video_comment_sentiment": "POSITIVE"})
        self.assertEqual(set(v), {"transcript_sentiment", "vocal_emotion",
                                  "video_comment_sentiment"})

    def test_empty_spec_yields_nothing(self):
        self.assertEqual(R.channel_valences({}), {})


class TestReferenceQuantities(unittest.TestCase):
    def _v(self, t, vo, f, c):
        return R.channel_valences({
            "transcript_sentiment": t, "vocal_emotion": vo,
            "facial_emotion": f, "video_comment_sentiment": c})

    def test_full_agreement(self):
        v = self._v("POSITIVE", "POSITIVE", "happy", "POSITIVE")
        self.assertFalse(R.ref_any(v))
        self.assertFalse(R.ref_polar(v))
        self.assertEqual(R.ref_score(v), 0.0)
        self.assertEqual(R.ref_channels_in_conflict(v), set())

    def test_all_pairs_polar_is_exactly_one(self):
        v = {"a": "POSITIVE", "b": "NEGATIVE"}
        self.assertEqual(R.ref_score(v), 1.0)

    def test_adjacent_only_uses_the_half_weight(self):
        # 3 channels, 3 pairs: P/P agree (0), P/N adjacent (0.5), P/N adjacent
        # (0.5) -> 1.0/3
        v = {"a": "POSITIVE", "b": "POSITIVE", "c": "NEUTRAL"}
        self.assertAlmostEqual(R.ref_score(v), 1.0 / 3)
        self.assertTrue(R.ref_any(v))
        self.assertFalse(R.ref_polar(v))

    def test_polar_requires_both_poles(self):
        self.assertFalse(R.ref_polar({"a": "NEUTRAL", "b": "NEGATIVE"}))
        self.assertTrue(R.ref_polar({"a": "POSITIVE", "b": "NEGATIVE"}))

    def test_mixed_polar_and_adjacent(self):
        # P/N polar (1.0), P/NEU adjacent (0.5), N/NEU adjacent (0.5) -> 2.0/3
        v = {"a": "POSITIVE", "b": "NEGATIVE", "c": "NEUTRAL"}
        self.assertAlmostEqual(R.ref_score(v), 2.0 / 3)

    def test_fewer_than_two_channels_is_zero_not_undefined(self):
        self.assertEqual(R.ref_score({}), 0.0)
        self.assertEqual(R.ref_score({"a": "POSITIVE"}), 0.0)
        self.assertFalse(R.ref_any({"a": "POSITIVE"}))

    def test_score_is_bounded(self):
        import itertools
        for combo in itertools.product(("POSITIVE", "NEUTRAL", "NEGATIVE"), repeat=4):
            v = dict(zip("abcd", combo))
            self.assertGreaterEqual(R.ref_score(v), 0.0)
            self.assertLessEqual(R.ref_score(v), 1.0)

    def test_conflict_set_includes_both_sides_of_a_split(self):
        # The system prompt says "list every channel you consider to be in
        # conflict"; in a two-way split both sides qualify.
        v = {"a": "POSITIVE", "b": "POSITIVE", "c": "NEGATIVE"}
        self.assertEqual(R.ref_channels_in_conflict(v), {"a", "b", "c"})


class TestBaselines(unittest.TestCase):
    def test_rule_baseline_reproduces_the_reference(self):
        spec = {"transcript_sentiment": "POSITIVE", "vocal_emotion": "NEGATIVE",
                "facial_emotion": "neutral", "video_comment_sentiment": "POSITIVE"}
        out = R.rule_baseline(spec)
        self.assertAlmostEqual(out["conflict_score"],
                               R.ref_score(R.channel_valences(spec)))
        self.assertEqual(set(out["channels_in_conflict"]),
                         R.ref_channels_in_conflict(R.channel_valences(spec)))

    def test_rule_baseline_returns_the_model_response_shape(self):
        out = R.rule_baseline({"transcript_sentiment": "POSITIVE"})
        for key in ("conflict_score", "channels_in_conflict", "flags", "narrative"):
            self.assertIn(key, out)

    def test_rule_baseline_cannot_see_the_transcript(self):
        # Why it must score zero on the incongruence suite: it is never given the
        # text. This is the structural fact Q4 rests on.
        a = R.rule_baseline({"transcript_sentiment": "POSITIVE",
                             "vocal_emotion": "POSITIVE"})
        self.assertEqual(a["conflict_score"], 0.0)

    def test_constant_baselines_ignore_their_input(self):
        z, f = R.constant_baseline(0.0), R.constant_baseline(1.0)
        for spec in ({}, {"transcript_sentiment": "POSITIVE",
                          "vocal_emotion": "NEGATIVE"}):
            self.assertEqual(z(spec)["conflict_score"], 0.0)
            self.assertEqual(f(spec)["conflict_score"], 1.0)


class TestChannelNormalisation(unittest.TestCase):
    def test_maps_the_observed_alias_to_the_payload_key(self):
        # llama3.2 emitted `comment_sentiment` on 98 of 481 cached responses where
        # the payload key is `video_comment_sentiment`.
        self.assertEqual(R.normalise_channels(["comment_sentiment"]),
                         {"video_comment_sentiment"})

    def test_separator_and_case_insensitive(self):
        self.assertEqual(R.normalise_channels(["Vocal Emotion", "vocal_emotion",
                                               "vocalProsody"]),
                         {"vocal_emotion"})

    def test_unrecognised_names_are_dropped_not_kept(self):
        self.assertEqual(R.normalise_channels(["pitch_mean_hz", "banana"]), set())

    def test_non_list_input_is_empty(self):
        for x in (None, "vocal_emotion", 3, {}):
            self.assertEqual(R.normalise_channels(x), set())

    def test_every_payload_key_maps_to_itself(self):
        for key in R.CHANNELS:
            self.assertEqual(R.normalise_channels([key]), {key})


class TestJaccard(unittest.TestCase):
    def test_identical_sets(self):
        self.assertEqual(R.jaccard({"a", "b"}, {"a", "b"}), 1.0)

    def test_disjoint_sets(self):
        self.assertEqual(R.jaccard({"a"}, {"b"}), 0.0)

    def test_partial_overlap(self):
        self.assertAlmostEqual(R.jaccard({"a", "b"}, {"b", "c"}), 1 / 3)

    def test_both_empty_is_a_hit_not_undefined(self):
        self.assertEqual(R.jaccard(set(), set()), 1.0)

    def test_one_empty_is_zero(self):
        self.assertEqual(R.jaccard(set(), {"a"}), 0.0)


# ══════════════════════════════════════════════════════════ probes


class TestProbeGrid(unittest.TestCase):
    def setUp(self):
        self.grid = P.probe_suite()

    def test_size_is_the_full_product(self):
        self.assertEqual(len(self.grid), 3 * 3 * 4 * 3)
        self.assertEqual(len(self.grid), 108)

    def test_ids_are_unique(self):
        self.assertEqual(len({p["probe_id"] for p in self.grid}), 108)

    def test_every_configuration_appears_exactly_once(self):
        seen = [tuple(sorted(p["spec"].items())) for p in self.grid]
        self.assertEqual(len(set(seen)), 108)

    def test_only_the_channel_labels_vary(self):
        # The property the primary metric rests on: any variation in a model's
        # answer across probes must be attributable to the four labels.
        texts = {p["segment"]["text"] for p in self.grid}
        pitches = {p["segment"]["pitch_mean"] for p in self.grid}
        energies = {p["segment"]["energy_mean"] for p in self.grid}
        starts = {p["segment"]["start_time"] for p in self.grid}
        self.assertEqual(len(texts), 1)
        self.assertEqual(len(pitches), 1)
        self.assertEqual(len(energies), 1)
        self.assertEqual(len(starts), 1)

    def test_carrier_text_carries_no_evaluative_word(self):
        t = P.CARRIER_TEXT.lower()
        for word in ("great", "bad", "love", "hate", "amazing", "terrible",
                     "best", "worst", "good", "poor"):
            self.assertNotIn(word, t)

    def test_arousal_is_consistent_with_the_vocal_label(self):
        from pipeline.audio_module import classify_arousal
        for p in self.grid:
            ve = p["segment"]["vocal_emotion"]
            self.assertEqual(classify_arousal(ve["arousal"]), ve["label"],
                             f"{ve} is a payload the pipeline could not produce")

    def test_no_face_level_is_present_and_is_the_corpus_case(self):
        none_probes = [p for p in self.grid
                       if p["segment"]["facial_emotion"]["dominant"] is None]
        self.assertEqual(len(none_probes), 27)
        for p in none_probes:
            self.assertEqual(p["spec"]["facial_emotion"], "none detected")
            self.assertIsNone(R.to_valence(p["spec"]["facial_emotion"]))

    def test_reference_distribution_is_balanced_enough_for_mcc(self):
        vals = [R.channel_valences(p["spec"]) for p in self.grid]
        agree = sum(1 for v in vals if not R.ref_any(v))
        polar = sum(1 for v in vals if R.ref_polar(v))
        self.assertEqual(agree, 6)
        self.assertEqual(polar, 62)
        self.assertEqual(len(vals) - agree - polar, 40)

    def test_payload_builds_through_production_code(self):
        for p in self.grid[:12]:
            payload = O.build_segment_payload(p["segment"])
            self.assertIn("facial_emotion", payload)
            self.assertIn("transcript_sentiment", payload)
            self.assertIn("vocal_reliability", payload)

    def test_none_face_renders_as_none_detected_in_the_payload(self):
        p = next(x for x in self.grid
                 if x["segment"]["facial_emotion"]["dominant"] is None)
        self.assertEqual(O.build_segment_payload(p["segment"])["facial_emotion"],
                         "none detected")

    def test_is_deterministic_across_calls(self):
        self.assertEqual(json.dumps(P.probe_suite(), sort_keys=True),
                         json.dumps(P.probe_suite(), sort_keys=True))


class TestIncongruenceSuite(unittest.TestCase):
    def setUp(self):
        self.suite = P.incongruence_suite()

    def test_counts(self):
        self.assertEqual(len(self.suite), 36)
        self.assertEqual(sum(p["expected_conflict"] for p in self.suite), 24)
        self.assertEqual(sum(not p["expected_conflict"] for p in self.suite), 12)

    def test_ids_are_unique(self):
        self.assertEqual(len({p["probe_id"] for p in self.suite}), 36)

    def test_all_four_labels_agree_in_every_item(self):
        # The design guarantee: the rule baseline must be structurally unable to
        # score above zero here, or Q4 measures nothing.
        for p in self.suite:
            v = R.channel_valences(p["spec"])
            self.assertFalse(R.ref_any(v), p["probe_id"])
            self.assertEqual(R.ref_score(v), 0.0, p["probe_id"])

    def test_rule_baseline_scores_zero_on_every_item(self):
        for p in self.suite:
            self.assertEqual(R.rule_baseline(p["spec"])["conflict_score"], 0.0)

    def test_texts_are_distinct(self):
        self.assertEqual(len({p["segment"]["text"] for p in self.suite}), 36)

    def test_every_positive_item_has_a_published_rationale(self):
        rationales = P.incongruence_rationales()
        self.assertEqual(len(rationales), 24)
        for text, why in rationales:
            self.assertTrue(why.strip())
            self.assertTrue(text.strip())

    def test_controls_span_all_three_valences(self):
        vals = {p["spec"]["transcript_sentiment"]
                for p in self.suite if not p["expected_conflict"]}
        self.assertEqual(vals, {"POSITIVE", "NEUTRAL", "NEGATIVE"})

    def test_segment_ids_do_not_collide_with_the_grid(self):
        grid_ids = {p["segment"]["segment_id"] for p in P.probe_suite()}
        inc_ids = {p["segment"]["segment_id"] for p in self.suite}
        self.assertFalse(grid_ids & inc_ids)


# ══════════════════════════════════════════════════════════ candidates


class TestRegistry(unittest.TestCase):
    def test_the_incumbent_at_bench_time_is_registered_and_pinned(self):
        # `llama3.2` was the deployed controller when this bench ran and is the
        # baseline every comparison is against, so it stays registered under that
        # name after the adoption. Asserting it equals OLLAMA_MODEL would now be
        # asserting the bench never changed anything.
        self.assertIn("llama3.2", C.LLM_CANDIDATES)
        self.assertEqual(C.LLM_CANDIDATES["llama3.2"]["tag"], "llama3.2:latest")
        self.assertEqual(RPT.INCUMBENT, "llama3.2")

    def test_the_adopted_controller_is_a_benched_candidate(self):
        # Whatever the pipeline deploys must be something this bench measured.
        # Adopting a model that was never run would be exactly the unmeasured
        # choice the bench exists to end.
        tags = {s["tag"] for s in C.LLM_CANDIDATES.values()}
        self.assertIn(O.OLLAMA_MODEL, tags,
                      f"{O.OLLAMA_MODEL} is deployed but was never benched")

    def test_the_adopted_controller_runs_locally(self):
        self.assertNotIn("cloud", O.OLLAMA_MODEL)

    def test_every_tag_is_explicitly_pinned(self):
        for name, spec in C.LLM_CANDIDATES.items():
            self.assertIn(":", spec["tag"], f"{name} tag is not pinned")

    def test_references_are_not_llms(self):
        for n in C.REFERENCE_CANDIDATES:
            self.assertTrue(C.is_reference(n))
            self.assertNotIn(n, C.LLM_CANDIDATES)

    def test_cloud_models_are_excluded_on_the_constraint_not_on_quality(self):
        # The project rule: never call a cloud LLM API anywhere in the pipeline.
        for tag in ("gpt-oss:20b-cloud", "deepseek-v3.1:671b-cloud",
                    "qwen3-coder:480b-cloud"):
            self.assertIn(tag, C.EXCLUSIONS)
            self.assertEqual(C.EXCLUSIONS[tag][0], "constraint")
        for name, spec in C.LLM_CANDIDATES.items():
            self.assertNotIn("cloud", spec["tag"], f"{name} routes off-machine")


class TestDampingDisabled(unittest.TestCase):
    def test_neutralises_both_weights_and_restores_them(self):
        v, f = O.VOCAL_ONLY_CONFLICT_WEIGHT, O.FACIAL_ONLY_CONFLICT_WEIGHT
        with C.DampingDisabled():
            self.assertEqual(O.VOCAL_ONLY_CONFLICT_WEIGHT, 1.0)
            self.assertEqual(O.FACIAL_ONLY_CONFLICT_WEIGHT, 1.0)
        self.assertEqual(O.VOCAL_ONLY_CONFLICT_WEIGHT, v)
        self.assertEqual(O.FACIAL_ONLY_CONFLICT_WEIGHT, f)

    def test_restores_on_exception(self):
        v = O.VOCAL_ONLY_CONFLICT_WEIGHT
        with self.assertRaises(RuntimeError):
            with C.DampingDisabled():
                raise RuntimeError("boom")
        self.assertEqual(O.VOCAL_ONLY_CONFLICT_WEIGHT, v)

    def test_a_sole_dissenter_is_not_damped_inside_the_block(self):
        # The reason the bench disables damping: without this, a model would be
        # scored on a number the pipeline had already modified.
        seg = {"segment_id": 1, "start_time": 0.0, "end_time": 1.0,
               "transcript_sentiment": {"label": "POSITIVE"},
               "facial_emotion": {"dominant": "happy"},
               "vocal_emotion": {"label": "NEGATIVE"}}
        cs = {"label": "POSITIVE", "confidence": 0.9}
        data = {"conflict_score": 0.8}
        with C.DampingDisabled():
            self.assertEqual(O._coerce_result(data, seg, cs)["conflict_score"], 0.8)
        damped = O._coerce_result(data, seg, cs)["conflict_score"]
        self.assertLess(damped, 0.8)


class TestRunProbe(unittest.TestCase):
    def setUp(self):
        self.probe = P.probe_suite()[0]

    def test_reference_candidates_need_no_network(self):
        for name in C.REFERENCE_CANDIDATES:
            r = C.run_probe(name, self.probe)
            self.assertTrue(r["parsed"])
            self.assertIsNone(r["error"])

    def test_llm_path_parses_a_good_response(self):
        good = json.dumps({"segment_id": 0, "conflict_score": 0.6,
                           "channels_in_conflict": ["vocal_emotion"],
                           "flags": ["SARCASM_DETECTED"], "narrative": "n"})
        with patch.object(O, "_call_ollama", return_value=good):
            with C.DampingDisabled():
                r = C.run_probe("llama3.2", self.probe)
        self.assertTrue(r["parsed"])
        self.assertAlmostEqual(r["conflict_score"], 0.6)
        self.assertEqual(r["channels"], ["vocal_emotion"])
        self.assertEqual(r["flags"], ["SARCASM_DETECTED"])

    def test_unparseable_json_is_scored_as_production_scores_it(self):
        with patch.object(O, "_call_ollama", return_value="not json at all"):
            r = C.run_probe("llama3.2", self.probe)
        self.assertFalse(r["parsed"])
        self.assertEqual(r["conflict_score"], 0.0)
        self.assertIn("unparseable", r["error"])

    def test_non_object_json_is_rejected(self):
        with patch.object(O, "_call_ollama", return_value="[1, 2, 3]"):
            r = C.run_probe("llama3.2", self.probe)
        self.assertFalse(r["parsed"])

    def test_unreachable_ollama_never_raises(self):
        with patch.object(O, "_call_ollama", side_effect=OSError("connection refused")):
            r = C.run_probe("llama3.2", self.probe)
        self.assertFalse(r["parsed"])
        self.assertEqual(r["conflict_score"], 0.0)
        self.assertIn("OSError", r["error"])

    def test_response_missing_every_key_degrades_to_zero(self):
        with patch.object(O, "_call_ollama", return_value="{}"):
            r = C.run_probe("llama3.2", self.probe)
        self.assertTrue(r["parsed"])
        self.assertEqual(r["conflict_score"], 0.0)
        self.assertEqual(r["channels"], [])

    def test_model_global_is_restored_after_a_call(self):
        before = O.OLLAMA_MODEL
        with patch.object(O, "_call_ollama", return_value='{"conflict_score":0}'):
            C.run_probe("mistral_7b", self.probe)
        self.assertEqual(O.OLLAMA_MODEL, before)

    def test_model_global_is_restored_after_a_failure(self):
        before = O.OLLAMA_MODEL
        with patch.object(O, "_call_ollama", side_effect=OSError("x")):
            C.run_probe("mistral_7b", self.probe)
        self.assertEqual(O.OLLAMA_MODEL, before)

    def test_system_prompt_is_restored_after_an_override(self):
        before = O._SYSTEM_PROMPT
        with patch.object(O, "_call_ollama", return_value='{"conflict_score":0}'):
            C.run_probe("llama3.2", self.probe, system_prompt="OVERRIDE")
        self.assertEqual(O._SYSTEM_PROMPT, before)

    def test_the_payload_sent_carries_the_comment_channel(self):
        seen = {}

        def spy(content):
            seen.update(json.loads(content))
            return '{"conflict_score": 0.0}'

        with patch.object(O, "_call_ollama", side_effect=spy):
            C.run_probe("llama3.2", self.probe)
        self.assertIn("video_comment_sentiment", seen)
        self.assertIn("facial_emotion", seen)

    def test_out_of_range_score_is_clamped_by_production_coercion(self):
        with patch.object(O, "_call_ollama", return_value='{"conflict_score": 7.5}'):
            with C.DampingDisabled():
                r = C.run_probe("llama3.2", self.probe)
        self.assertEqual(r["conflict_score"], 1.0)

    def test_boolean_score_is_rejected_by_production_coercion(self):
        with patch.object(O, "_call_ollama", return_value='{"conflict_score": true}'):
            r = C.run_probe("llama3.2", self.probe)
        self.assertEqual(r["conflict_score"], 0.0)


# ══════════════════════════════════════════════════════════ run_bench


class TestRevisedPrompt(unittest.TestCase):
    def test_preserves_every_line_of_the_deployed_prompt(self):
        rev = RB.revised_prompt()
        for line in O._SYSTEM_PROMPT.splitlines():
            if line.strip():
                self.assertIn(line, rev, f"revision dropped: {line[:60]!r}")

    def test_keeps_the_channel_reliability_paragraph(self):
        # It is the hypothesis under test, so removing it would confound the
        # ablation with a second change.
        self.assertIn("CHANNEL RELIABILITY", RB.revised_prompt())

    def test_adds_the_scale_definition(self):
        rev = RB.revised_prompt()
        self.assertIn("HOW TO SET conflict_score", rev)
        self.assertGreater(len(rev), len(O._SYSTEM_PROMPT))

    def test_fails_loudly_if_the_marker_moves(self):
        with self.assertRaises(AssertionError):
            RB.revised_prompt("a prompt without the marker")

    def test_is_idempotent_in_the_sense_that_it_inserts_once(self):
        rev = RB.revised_prompt()
        self.assertEqual(rev.count("HOW TO SET conflict_score"), 1)


class TestSuiteSelection(unittest.TestCase):
    def test_grid_stages_share_one_suite(self):
        for stage in ("grid", "determinism", "ablation"):
            self.assertEqual(len(RB.suite_for(stage)), 108)

    def test_incongruence_stage(self):
        self.assertEqual(len(RB.suite_for("incongruence")), 36)

    def test_unknown_stage_raises(self):
        with self.assertRaises(KeyError):
            RB.suite_for("nonsense")


class TestCorpusProbes(unittest.TestCase):
    """Guards on the real-segment set. Skipped when the cache is not present."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.probes = RB.corpus_probes()
        except Exception as exc:  # pragma: no cover - cache-dependent
            raise unittest.SkipTest(f"ab_cache unavailable: {exc}")
        if not cls.probes:  # pragma: no cover
            raise unittest.SkipTest("ab_cache empty")

    def test_matches_the_cached_arm_size(self):
        self.assertEqual(len(self.probes), 481)

    def test_ids_are_unique(self):
        self.assertEqual(len({p["probe_id"] for p in self.probes}), len(self.probes))

    def test_facial_channel_is_absent_throughout(self):
        # These videos were downloaded audio-only. Stated in the spec rather than
        # silently missing, so the reference excludes it explicitly.
        for p in self.probes:
            self.assertEqual(p["spec"]["facial_emotion"], "none detected")

    def test_every_probe_builds_a_payload(self):
        for p in self.probes[:40]:
            self.assertIn("transcript", O.build_segment_payload(p["segment"]))


# ══════════════════════════════════════════════════════════ report_bench


def _fake_grid_runs(score_fn) -> dict:
    """A complete cached grid run, built from a scoring function. No I/O."""
    out = {}
    for p in P.probe_suite():
        v = R.channel_valences(p["spec"])
        out[p["probe_id"]] = {
            "probe_id": p["probe_id"], "raw": {}, "parsed": True,
            "conflict_score": score_fn(v),
            "channels": sorted(R.ref_channels_in_conflict(v)),
            "flags": [], "narrative": "", "latency_s": 1.0, "error": None,
        }
    return out


class TestGridScoring(unittest.TestCase):
    def _score(self, runs, name="tmp"):
        with patch.object(RPT, "_load", return_value=runs):
            return RPT.score_grid(name)

    def test_a_perfect_predictor_scores_one_on_p1_and_p2(self):
        g = self._score(_fake_grid_runs(R.ref_score))
        self.assertAlmostEqual(g["P1_mcc"], 1.0)
        self.assertAlmostEqual(g["P2_spearman"], 1.0)
        self.assertAlmostEqual(g["P3_jaccard"], 1.0)
        self.assertEqual(g["P4_k"], g["P4_n"])

    def test_always_zero_scores_zero_on_p1(self):
        g = self._score(_fake_grid_runs(lambda v: 0.0))
        self.assertEqual(g["P1_mcc"], 0.0)
        self.assertEqual(g["zero_rate"], 1.0)
        self.assertEqual(g["P4_k"], 0)

    def test_always_flag_scores_zero_on_p1_too(self):
        g = self._score(_fake_grid_runs(lambda v: 1.0))
        self.assertEqual(g["P1_mcc"], 0.0)
        self.assertEqual(g["false_alarm_on_agreement"], g["n_agreement"])

    def test_polar_denominator_matches_the_suite(self):
        g = self._score(_fake_grid_runs(R.ref_score))
        self.assertEqual(g["P4_n"], 62)
        self.assertEqual(g["n_agreement"], 6)
        self.assertEqual(g["n"], 108)

    def test_missing_cache_returns_none(self):
        with patch.object(RPT, "_load", return_value=None):
            self.assertIsNone(RPT.score_grid("absent"))

    def test_empty_cache_returns_none(self):
        with patch.object(RPT, "_load", return_value={}):
            self.assertIsNone(RPT.score_grid("empty"))

    def test_unparseable_runs_lower_the_parse_rate(self):
        runs = _fake_grid_runs(R.ref_score)
        for k in list(runs)[:10]:
            runs[k].update(parsed=False, conflict_score=0.0, error="unparseable")
        g = self._score(runs)
        self.assertAlmostEqual(g["parse_rate"], 98 / 108)

    def test_hallucinated_channel_is_counted(self):
        runs = _fake_grid_runs(R.ref_score)
        # Name the facial channel on a probe where it reads "none detected".
        pid = next(p["probe_id"] for p in P.probe_suite()
                   if p["spec"]["facial_emotion"] == "none detected")
        runs[pid]["channels"] = list(runs[pid]["channels"]) + ["facial_emotion"]
        g = self._score(runs)
        self.assertGreaterEqual(g["hallucinated_channels"], 1)

    def test_latency_ignores_errored_calls(self):
        runs = _fake_grid_runs(R.ref_score)
        for k in list(runs)[:5]:
            runs[k].update(error="OSError", latency_s=999.0)
        g = self._score(runs)
        self.assertLess(g["median_latency_s"], 2.0)


class TestIncongruenceScoring(unittest.TestCase):
    def _runs(self, pos_score, neg_score):
        out = {}
        for p in P.incongruence_suite():
            out[p["probe_id"]] = {
                "probe_id": p["probe_id"], "parsed": True, "error": None,
                "conflict_score": pos_score if p["expected_conflict"] else neg_score,
                "channels": [], "flags": [], "narrative": "", "latency_s": 1.0,
            }
        return out

    def test_perfect_discrimination(self):
        with patch.object(RPT, "_load", return_value=self._runs(0.8, 0.0)):
            i = RPT.score_incongruence("x")
        self.assertEqual(i["hits"], 24)
        self.assertEqual(i["false_alarms"], 0)
        self.assertAlmostEqual(i["P5"], 1.0)
        self.assertAlmostEqual(i["mcc"], 1.0)

    def test_flagging_everything_scores_zero(self):
        # The reason the 12 controls exist.
        with patch.object(RPT, "_load", return_value=self._runs(0.9, 0.9)):
            i = RPT.score_incongruence("x")
        self.assertAlmostEqual(i["P5"], 0.0)
        self.assertEqual(i["mcc"], 0.0)

    def test_flagging_nothing_scores_zero(self):
        with patch.object(RPT, "_load", return_value=self._runs(0.0, 0.0)):
            i = RPT.score_incongruence("x")
        self.assertAlmostEqual(i["P5"], 0.0)

    def test_denominators(self):
        with patch.object(RPT, "_load", return_value=self._runs(0.5, 0.0)):
            i = RPT.score_incongruence("x")
        self.assertEqual((i["n_pos"], i["n_neg"]), (24, 12))

    def test_missing_cache_returns_none(self):
        with patch.object(RPT, "_load", return_value=None):
            self.assertIsNone(RPT.score_incongruence("absent"))


class TestHeadToHeadAndAdoption(unittest.TestCase):
    def _grid(self, name, score_fn):
        with patch.object(RPT, "_load", return_value=_fake_grid_runs(score_fn)):
            return RPT.score_grid(name)

    def test_identical_models_have_no_discordant_pairs(self):
        a = self._grid("a", R.ref_score)
        b = self._grid("b", R.ref_score)
        h = RPT.head_to_head(a, b)
        self.assertEqual(h["n_discordant"], 0)
        self.assertEqual(h["p"], 1.0)
        self.assertFalse(h["better"])

    def test_a_better_model_wins_with_direction(self):
        good = self._grid("good", R.ref_score)
        bad = self._grid("bad", lambda v: 0.0)
        h = RPT.head_to_head(good, bad)
        self.assertGreater(h["a_only"], h["b_only"])
        self.assertLess(h["p"], 0.05)
        self.assertTrue(h["better"])

    def test_the_reverse_comparison_is_not_reported_as_better(self):
        good = self._grid("good", R.ref_score)
        bad = self._grid("bad", lambda v: 0.0)
        h = RPT.head_to_head(bad, good)
        self.assertLess(h["p"], 0.05)
        self.assertFalse(h["better"])
        self.assertTrue(h["worse"])

    def _adoption(self, incumbent_fn, challenger_fn, inc_p5=0.0, chal_p5=0.0,
                  chal_parse=1.0, chal_latency=1.0):
        grids = {RPT.INCUMBENT: self._grid(RPT.INCUMBENT, incumbent_fn),
                 "chal": self._grid("chal", challenger_fn)}
        grids["chal"]["parse_rate"] = chal_parse
        grids["chal"]["median_latency_s"] = chal_latency
        incs = {RPT.INCUMBENT: {"P5": inc_p5}, "chal": {"P5": chal_p5}}
        return RPT.evaluate_adoption(grids, incs, latency_ref=1.0)

    def test_a_clearly_better_challenger_qualifies(self):
        ad = self._adoption(lambda v: 0.0, R.ref_score)
        self.assertEqual(ad["winner"], "chal")

    def test_a_worse_challenger_does_not_qualify(self):
        ad = self._adoption(R.ref_score, lambda v: 0.0)
        self.assertIsNone(ad["winner"])

    def test_a_low_parse_rate_disqualifies_regardless_of_p1(self):
        ad = self._adoption(lambda v: 0.0, R.ref_score, chal_parse=0.80)
        self.assertIsNone(ad["winner"])
        self.assertFalse(ad["rows"][0]["conditions"]["G1_parse"])

    def test_excessive_latency_disqualifies_regardless_of_p1(self):
        ad = self._adoption(lambda v: 0.0, R.ref_score, chal_latency=10.0)
        self.assertIsNone(ad["winner"])
        self.assertFalse(ad["rows"][0]["conditions"]["G4_latency"])

    def test_a_p5_regression_disqualifies(self):
        ad = self._adoption(lambda v: 0.0, R.ref_score, inc_p5=0.5, chal_p5=0.1)
        self.assertIsNone(ad["winner"])
        self.assertFalse(ad["rows"][0]["conditions"]["C4_no_P5_regression"])

    def test_the_incumbent_is_never_its_own_challenger(self):
        ad = self._adoption(R.ref_score, R.ref_score)
        self.assertNotIn(RPT.INCUMBENT, [r["candidate"] for r in ad["rows"]])

    def test_reference_rows_are_excluded_from_adoption(self):
        grids = {RPT.INCUMBENT: self._grid(RPT.INCUMBENT, lambda v: 0.0),
                 "rule_baseline": self._grid("rule_baseline", R.ref_score)}
        ad = RPT.evaluate_adoption(grids, {}, latency_ref=1.0)
        self.assertEqual(ad["rows"], [])
        self.assertIsNone(ad["winner"])


if __name__ == "__main__":
    unittest.main()


class TestThresholdReachability(unittest.TestCase):
    """The flag threshold against the prompt's own scale.

    Added after the grid showed `rule_baseline` — a perfect implementation of the
    specified task — flagging 0 of 62 polar configurations. Pure arithmetic, so it
    is tested rather than trusted.
    """

    def test_pigeonhole_bound_is_definition_independent(self):
        # The prompt calls 1.0 "all channels disagree". With four channels drawn
        # from three valence levels, two must share a valence, so no reading of
        # the scale can put a four-channel segment at the top of it.
        import itertools
        for combo in itertools.product(("POSITIVE", "NEUTRAL", "NEGATIVE"), repeat=4):
            self.assertLess(len(set(combo)), 4)

    def test_pre_registered_reading_cannot_reach_the_threshold_above_two_channels(self):
        from pipeline.orchestrator import CONFLICT_FLAG_THRESHOLD
        tr = RPT.threshold_reachability()
        row = tr["readings"]["pairwise (this bench, pre-registered)"]
        self.assertTrue(row[2]["reaches"])
        self.assertFalse(row[3]["reaches"])
        self.assertFalse(row[4]["reaches"])
        self.assertAlmostEqual(row[4]["max"], 2 / 3, places=6)
        self.assertEqual(tr["threshold"], CONFLICT_FLAG_THRESHOLD)

    def test_the_finding_is_reported_as_definition_dependent(self):
        # Two of the four readings reach the threshold. Reporting only the two
        # that do not would be selecting the definition to fit the conclusion.
        tr = RPT.threshold_reachability()
        reaches = [r[4]["reaches"] for r in tr["readings"].values()]
        self.assertIn(True, reaches)
        self.assertIn(False, reaches)

    def test_no_grid_configuration_reaches_the_threshold_under_the_reference(self):
        from pipeline.orchestrator import CONFLICT_FLAG_THRESHOLD
        worst = max(R.ref_score(R.channel_valences(p["spec"]))
                    for p in P.probe_suite())
        self.assertLess(worst, CONFLICT_FLAG_THRESHOLD)

    def test_every_reading_agrees_on_full_agreement(self):
        for f in RPT._spec_readings().values():
            self.assertEqual(f(("POSITIVE",) * 4), 0.0)


class TestAdoptionRequiresBothHalvesOfConditionTwo(unittest.TestCase):
    """C2 is a conjunction: a higher P1 AND a McNemar win.

    Added after the full grid showed `always_flag` passing the McNemar test — it
    agrees with `ref_any` on 102 of 108 probes purely by never abstaining — while
    scoring MCC exactly 0.000. A rule keyed on the significance test alone would
    adopt a model that is significantly better at a binary decision and no better
    on the metric the rule names.
    """

    def _grid(self, name, score_fn):
        with patch.object(RPT, "_load", return_value=_fake_grid_runs(score_fn)):
            return RPT.score_grid(name)

    def test_a_constant_flagger_does_not_qualify_despite_winning_mcnemar(self):
        grids = {RPT.INCUMBENT: self._grid(RPT.INCUMBENT, lambda v: 0.0),
                 "flagger": self._grid("flagger", lambda v: 1.0)}
        incs = {RPT.INCUMBENT: {"P5": 0.0}, "flagger": {"P5": 0.0}}
        ad = RPT.evaluate_adoption(grids, incs, latency_ref=1.0)
        row = next(r for r in ad["rows"] if r["candidate"] == "flagger")
        self.assertTrue(row["mcnemar"]["better"], "McNemar should favour it")
        self.assertEqual(row["P1"], 0.0, "but its MCC is zero")
        self.assertFalse(row["conditions"]["C2_beats_P1"])
        self.assertIsNone(ad["winner"])

    def test_a_genuinely_better_model_still_qualifies(self):
        grids = {RPT.INCUMBENT: self._grid(RPT.INCUMBENT, lambda v: 0.0),
                 "good": self._grid("good", R.ref_score)}
        incs = {RPT.INCUMBENT: {"P5": 0.0}, "good": {"P5": 0.0}}
        ad = RPT.evaluate_adoption(grids, incs, latency_ref=1.0)
        self.assertEqual(ad["winner"], "good")
