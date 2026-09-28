"""
test_baseline_systems.py — unit tests for the baseline bench's five-system
comparison: probe construction, payloads, coercion, the rule systems, and the
metric that decides RQ1.

Scope: no Ollama process, no network, no model. The LLM
boundary is `run_bench.call_ollama` and it is patched; everything on either side
of it is exercised for real.

The tests that matter most are the ones pinning **fairness properties**, because
those are the claims a marker or an examiner will attack:

  - `four_channel` uses the deployed prompt VERBATIM, and both text-only prompts
    carry the deployed JSON contract, so no system is scored on a different
    output schema (PROTOCOL.md §7);
  - `text_only_llm` cannot be damped by channels it never saw (Amendment A4) —
    the leak that would have made the single-channel control secretly
    multi-channel;
  - `three_channel` differs from `four_channel` in the facial field and nothing
    else (RQ2 is otherwise not an ablation of the facial channel);
  - `constant` scores exactly rho = 0.000, without which the metric is unsound
    (PROTOCOL.md §3.3);
  - the §8.1 verdict function returns "no detected difference" when the interval
    spans zero, rather than rounding toward the incumbent design.
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from unittest.mock import patch

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BB = ROOT / "research" / "baseline_bench"

_SHARED = ("stats", "rater_analysis", "systems", "run_bench", "report_bench",
           "sample", "build_pages", "verify_page", "candidates", "probes",
           "reference", "ground_truth", "corpus_ab")


def _load():
    saved = {n: sys.modules.pop(n, None) for n in _SHARED}
    sys.path.insert(0, str(BB))
    try:
        import report_bench
        import run_bench
        import stats
        import systems
        return systems, run_bench, report_bench, stats
    finally:
        for n in _SHARED:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]
        while str(BB) in sys.path:
            sys.path.remove(str(BB))


SY, RB, RPT, S = _load()

from pipeline import orchestrator as O  # noqa: E402


def _probe(transcript="NEUTRAL", vocal="NEUTRAL", facial=None,
           comment="POSITIVE", text="a segment", uid="v_1"):
    return {
        "uid": uid, "video_id": "v", "segment_id": 1, "split": "selection",
        "channel": "Speaker", "text": text,
        "segment": {
            "segment_id": 1, "start_time": 0.0, "end_time": 4.0, "text": text,
            "transcript_sentiment": {"label": transcript, "confidence": 0.9},
            "vocal_emotion": {"label": vocal, "arousal": 0.5, "reliability": 0.489},
            "facial_emotion": {"dominant": facial, "confidence": 0.8 if facial else 0.0},
        },
        "comment_sentiment": {"label": comment, "confidence": 0.98},
        "spec": {"transcript_sentiment": transcript, "vocal_emotion": vocal,
                 "facial_emotion": facial, "video_comment_sentiment": comment},
    }


class TestPrompts(unittest.TestCase):
    def test_four_and_three_channel_use_the_deployed_prompt_verbatim(self):
        for s in ("four_channel", "three_channel"):
            self.assertIs(SY.prompt_for(s), O._SYSTEM_PROMPT)

    def test_both_text_only_prompts_carry_the_deployed_json_contract(self):
        block = SY._json_schema_block(O._SYSTEM_PROMPT)
        self.assertTrue(SY.TEXT_ONLY_PROMPT.endswith(block))
        self.assertTrue(SY.TEXT_ONLY_ANCHORED_PROMPT.endswith(block))

    def test_the_two_text_only_prompts_actually_differ(self):
        # Amendment A5 is only meaningful if they are two prompts.
        self.assertNotEqual(SY.TEXT_ONLY_PROMPT, SY.TEXT_ONLY_ANCHORED_PROMPT)

    def test_missing_contract_marker_fails_loudly(self):
        # If the deployed prompt is edited so the marker moves, the bench must
        # stop rather than silently score systems on different contracts.
        with self.assertRaises(SystemExit):
            SY._json_schema_block("a prompt with no marker in it")

    def test_unknown_system_raises(self):
        with self.assertRaises(KeyError):
            SY.prompt_for("nope")


class TestPayloads(unittest.TestCase):
    def test_three_channel_differs_from_four_only_in_the_facial_field(self):
        p = _probe(facial="happy")
        a = SY.payload_for("four_channel", p)
        b = SY.payload_for("three_channel", p)
        self.assertNotEqual(a["facial_emotion"], b["facial_emotion"])
        self.assertEqual(b["facial_emotion"], "none detected")
        self.assertEqual({k: v for k, v in a.items() if k != "facial_emotion"},
                         {k: v for k, v in b.items() if k != "facial_emotion"})

    def test_ablation_is_a_no_op_when_no_face_was_detected(self):
        p = _probe(facial=None)
        self.assertEqual(SY.payload_for("four_channel", p),
                         SY.payload_for("three_channel", p))

    def test_text_only_payload_carries_the_transcript_and_nothing_else(self):
        p = _probe(facial="happy", text="hello there")
        pay = SY.payload_for("text_only_llm", p)
        self.assertEqual(set(pay), {"segment_id", "start_s", "end_s", "transcript"})
        self.assertEqual(pay["transcript"], "hello there")
        blob = json.dumps(pay)
        for leak in ("POSITIVE", "NEUTRAL", "happy", "arousal", "comment"):
            self.assertNotIn(leak, blob)

    def test_both_text_only_systems_get_the_same_payload(self):
        p = _probe()
        self.assertEqual(SY.payload_for("text_only_llm", p),
                         SY.payload_for("text_only_llm_anchored", p))

    def test_four_channel_payload_matches_production_builder(self):
        p = _probe(facial="sad")
        prod = O.build_segment_payload(p["segment"])
        got = SY.payload_for("four_channel", p)
        self.assertEqual({k: v for k, v in got.items()
                          if k != "video_comment_sentiment"}, prod)


class TestCoercionFairness(unittest.TestCase):
    """Amendment A4 — the leak that would have made the control multi-channel."""

    def _vocal_sole_dissenter_probe(self):
        # transcript, facial and comment all POSITIVE; vocal NEGATIVE.
        p = _probe(transcript="POSITIVE", vocal="NEGATIVE", facial="happy",
                   comment="POSITIVE")
        self.assertTrue(O._vocal_is_sole_dissenter(p["segment"],
                                                   p["comment_sentiment"]))
        return p

    def test_four_channel_damps_a_vocal_only_conflict(self):
        p = self._vocal_sole_dissenter_probe()
        r = SY.coerce_for("four_channel", {"conflict_score": 1.0}, p)
        self.assertAlmostEqual(r["conflict_score"], O.VOCAL_ONLY_CONFLICT_WEIGHT, places=4)
        self.assertTrue(any("vocal_channel_downweighted" in x
                            for x in r["conflict_reasons"]))

    def test_text_only_is_not_damped_by_channels_it_never_saw(self):
        p = self._vocal_sole_dissenter_probe()
        r = SY.coerce_for("text_only_llm", {"conflict_score": 1.0}, p)
        self.assertEqual(r["conflict_score"], 1.0)
        self.assertFalse(any("downweighted" in x for x in r["conflict_reasons"]))

    def test_text_only_stripped_segment_exposes_no_channel_valences(self):
        p = self._vocal_sole_dissenter_probe()
        seg = p["segment"]
        bare = {"segment_id": seg["segment_id"], "start_time": seg["start_time"],
                "end_time": seg["end_time"], "text": seg["text"]}
        self.assertEqual(O._channel_valences(bare, None), {})
        self.assertFalse(O._vocal_is_sole_dissenter(bare, None))
        self.assertFalse(O._facial_is_sole_dissenter(bare, None))

    def test_all_systems_share_the_clamping_and_flag_rule(self):
        p = _probe()
        for s in ("four_channel", "three_channel", "text_only_llm",
                  "text_only_llm_anchored"):
            self.assertEqual(SY.coerce_for(s, {"conflict_score": 5.0}, p)["conflict_score"], 1.0)
            self.assertEqual(SY.coerce_for(s, {"conflict_score": -3.0}, p)["conflict_score"], 0.0)
            self.assertEqual(SY.coerce_for(s, {}, p)["conflict_score"], 0.0)

    def test_malformed_response_degrades_identically_across_systems(self):
        p = _probe()
        got = {s: SY.coerce_for(s, {"conflict_score": "banana"}, p)["conflict_score"]
               for s in ("four_channel", "three_channel", "text_only_llm")}
        self.assertEqual(set(got.values()), {0.0})


class TestRuleSystems(unittest.TestCase):
    def test_constant_is_always_zero(self):
        for lab in ("POSITIVE", "NEUTRAL", "NEGATIVE", None):
            self.assertEqual(SY.rule_score("constant", _probe(transcript=lab)), 0.0)

    def test_the_two_transcript_mappings_are_exact_inverses(self):
        for lab in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
            p = _probe(transcript=lab)
            a = SY.rule_score("transcript_label_pos_genuine", p)
            b = SY.rule_score("transcript_label_neg_genuine", p)
            self.assertAlmostEqual(a + b, 1.0, places=9)

    def test_known_mapping_values(self):
        self.assertEqual(SY.rule_score("transcript_label_pos_genuine",
                                       _probe(transcript="POSITIVE")), 0.0)
        self.assertEqual(SY.rule_score("transcript_label_neg_genuine",
                                       _probe(transcript="POSITIVE")), 1.0)

    def test_unreadable_label_is_the_midpoint_not_zero(self):
        # 0.0 would be a claim of sincerity the channel never made.
        self.assertEqual(SY.rule_score("transcript_label_pos_genuine",
                                       _probe(transcript="GIBBERISH")), 0.5)

    def test_unknown_system_raises(self):
        with self.assertRaises(KeyError):
            SY.rule_score("mystery", _probe())


class TestMetric(unittest.TestCase):
    def test_sign_convention_a_good_system_scores_positive(self):
        # High conflict on the segments humans call least genuine.
        pairs = [(5.0, 0.0), (4.0, 0.25), (3.0, 0.5), (2.0, 0.75), (1.0, 1.0)]
        self.assertAlmostEqual(RPT.rho_for(pairs), 1.0, places=9)

    def test_an_inverted_system_scores_negative(self):
        pairs = [(5.0, 1.0), (4.0, 0.75), (3.0, 0.5), (2.0, 0.25), (1.0, 0.0)]
        self.assertAlmostEqual(RPT.rho_for(pairs), -1.0, places=9)

    def test_a_constant_system_scores_exactly_zero(self):
        # PROTOCOL.md §3.3. Without this the whole metric is unsound.
        pairs = [(h, 0.0) for h in (5.0, 4.0, 3.0, 2.0, 1.0)]
        self.assertEqual(RPT.rho_for(pairs), 0.0)

    def test_too_few_pairs_is_zero_not_an_exception(self):
        self.assertEqual(RPT.rho_for([(1.0, 0.5)]), 0.0)

    def test_evaluate_reports_granularity_and_flag_rate(self):
        h = {f"u{i}": float(i % 5 + 1) for i in range(20)}
        sc = {f"u{i}": (0.0 if i % 2 else 0.8) for i in range(20)}
        r = RPT.evaluate(sc, h, list(h))
        self.assertEqual(r["n"], 20)
        self.assertEqual(r["distinct_values"], 2)
        self.assertAlmostEqual(r["flag_rate"], 0.5, places=9)

    def test_paired_difference_of_a_system_with_itself_is_exactly_zero(self):
        h = {f"u{i}": float(i % 5 + 1) for i in range(20)}
        sc = {f"u{i}": i / 20 for i in range(20)}
        d = RPT.paired(sc, sc, h, list(h))
        self.assertEqual((d["point"], d["lo"], d["hi"]), (0.0, 0.0, 0.0))
        self.assertEqual(RPT.verdict(d), "no detected difference")


class TestVerdict(unittest.TestCase):
    def test_interval_spanning_zero_is_not_rounded_toward_the_incumbent(self):
        self.assertEqual(RPT.verdict({"point": 0.09, "lo": -0.2, "hi": 0.3,
                                      "excludes_zero": False}),
                         "no detected difference")

    def test_a_wins_and_b_wins(self):
        self.assertEqual(RPT.verdict({"point": 0.3, "lo": 0.1, "hi": 0.5,
                                      "excludes_zero": True}), "A wins")
        self.assertEqual(RPT.verdict({"point": -0.3, "lo": -0.5, "hi": -0.1,
                                      "excludes_zero": True}), "B wins")

    def test_no_data(self):
        self.assertEqual(RPT.verdict({"point": None}), "no data")


class TestRunnerFailurePaths(unittest.TestCase):
    """PROTOCOL.md graceful degradation: one bad call must not destroy a run."""

    def test_unreachable_ollama_yields_a_fallback_not_an_exception(self):
        p = _probe()
        with patch.object(RB, "call_ollama", side_effect=OSError("down")):
            rec = RB.run_one("four_channel", p)
        self.assertFalse(rec["ok"])
        self.assertIn("call_failed", rec["reason"])
        self.assertEqual(rec["result"]["conflict_score"], 0.0)

    def test_unparseable_json_yields_a_fallback(self):
        p = _probe()
        with patch.object(RB, "call_ollama", return_value=("not json{", 1.0)):
            rec = RB.run_one("four_channel", p)
        self.assertFalse(rec["ok"])
        self.assertIn("parse_failed", rec["reason"])
        self.assertEqual(rec["result"]["conflict_score"], 0.0)

    def test_non_object_json_yields_a_fallback(self):
        p = _probe()
        with patch.object(RB, "call_ollama", return_value=("[1,2,3]", 1.0)):
            rec = RB.run_one("four_channel", p)
        self.assertFalse(rec["ok"])

    def test_a_good_response_is_recorded_with_its_latency(self):
        p = _probe()
        body = json.dumps({"conflict_score": 0.4, "channels_in_conflict": [],
                           "flags": [], "narrative": "n"})
        with patch.object(RB, "call_ollama", return_value=(body, 2.5)):
            rec = RB.run_one("text_only_llm", p)
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["seconds"], 2.5)
        self.assertEqual(rec["result"]["conflict_score"], 0.4)

    def test_runner_options_match_production_exactly(self):
        captured = {}

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": "{}"}}

        def fake_post(url, json=None, timeout=None):
            captured.update(json)
            return FakeResp()

        with patch.object(RB.requests, "post", fake_post):
            RB.call_ollama("sys", "user")
        self.assertEqual(captured["model"], O.OLLAMA_MODEL)
        self.assertEqual(captured["options"]["temperature"], 0)
        self.assertEqual(captured["options"]["seed"], 42)
        self.assertEqual(captured["options"]["num_ctx"], O.OLLAMA_NUM_CTX)
        self.assertEqual(captured["format"], "json")
        self.assertFalse(captured["stream"])


class TestRealProbes(unittest.TestCase):
    def test_probes_rebuild_to_the_sample(self):
        probes = SY.build_probes()
        sample = json.loads((BB / "sample.json").read_text())
        self.assertEqual(len(probes), len(sample["items"]))
        self.assertEqual({p["uid"] for p in probes},
                         {it["uid"] for it in sample["items"]})

    def test_rebuilt_channel_labels_match_the_sample_exactly(self):
        # The sample was drawn from these caches months of edits ago. If a cache
        # has changed underneath, the ratings no longer describe these segments.
        probes = {p["uid"]: p for p in SY.build_probes()}
        for it in json.loads((BB / "sample.json").read_text())["items"]:
            spec = probes[it["uid"]]["spec"]
            self.assertEqual(spec["transcript_sentiment"], it["transcript_sentiment"])
            self.assertEqual(spec["vocal_emotion"], it["vocal_emotion"])
            self.assertEqual(spec["facial_emotion"], it["facial_emotion"])
            self.assertEqual(spec["video_comment_sentiment"],
                             it["video_comment_sentiment"])
            self.assertEqual(probes[it["uid"]]["text"], it["text"])

    def test_the_facial_ablation_is_real_on_most_segments(self):
        probes = SY.build_probes()
        differ = sum(1 for p in probes
                     if SY.payload_for("four_channel", p)
                     != SY.payload_for("three_channel", p))
        self.assertEqual(differ, 85)


if __name__ == "__main__":
    unittest.main()
