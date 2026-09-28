"""
Unit tests for whisper_bench/wer.py.

The bench's headline numbers come out of these functions, so the counts are
checked against hand-worked alignments rather than against the implementation's
own output.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research" / "whisper_bench"))

import wer as W  # noqa: E402


class TestEditCounts:
    def test_identical_sequences_have_no_errors(self):
        c = W.edit_counts(["the", "cat", "sat"], ["the", "cat", "sat"])
        assert c["errors"] == 0
        assert (c["substitutions"], c["deletions"], c["insertions"]) == (0, 0, 0)

    def test_single_substitution(self):
        c = W.edit_counts(["the", "cat", "sat"], ["the", "dog", "sat"])
        assert c["substitutions"] == 1
        assert c["deletions"] == 0 and c["insertions"] == 0

    def test_single_deletion(self):
        c = W.edit_counts(["the", "cat", "sat"], ["the", "sat"])
        assert c["deletions"] == 1
        assert c["substitutions"] == 0 and c["insertions"] == 0

    def test_single_insertion(self):
        c = W.edit_counts(["the", "cat"], ["the", "big", "cat"])
        assert c["insertions"] == 1
        assert c["substitutions"] == 0 and c["deletions"] == 0

    def test_empty_hypothesis_is_all_deletions(self):
        c = W.edit_counts(["a", "b", "c"], [])
        assert c["deletions"] == 3
        assert c["errors"] == 3

    def test_empty_reference_is_all_insertions(self):
        c = W.edit_counts([], ["a", "b"])
        assert c["insertions"] == 2
        assert c["errors"] == 2

    def test_both_empty(self):
        c = W.edit_counts([], [])
        assert c["errors"] == 0

    def test_counts_sum_to_edit_distance(self):
        ref = "one two three four five".split()
        hyp = "one three four six seven".split()
        c = W.edit_counts(ref, hyp)
        assert c["errors"] == c["substitutions"] + c["deletions"] + c["insertions"]

    def test_ref_and_hyp_lengths_recorded(self):
        c = W.edit_counts(["a", "b", "c"], ["a", "b"])
        assert c["ref_words"] == 3 and c["hyp_words"] == 2

    def test_completely_different_is_all_substitutions(self):
        c = W.edit_counts(["a", "b"], ["x", "y"])
        assert c["substitutions"] == 2
        assert c["errors"] == 2


class TestWer:
    def test_perfect_transcription_is_zero(self):
        assert W.wer("the cat sat", "the cat sat")["wer"] == 0.0

    def test_one_of_three_wrong(self):
        assert W.wer("the cat sat", "the dog sat")["wer"] == pytest.approx(1 / 3)

    def test_wer_can_exceed_one_on_hallucination(self):
        # Deliberately uncapped: a model inventing text must not look like it
        # merely got everything wrong.
        r = W.wer("hello", "hello and then a lot more words appear here now")
        assert r["wer"] > 1.0

    def test_normalisation_ignores_case_and_punctuation(self):
        assert W.wer("The Cat, sat!", "the cat sat")["wer"] == 0.0

    def test_normalisation_ignores_filler_words(self):
        # OpenAI's normalizer strips fillers; a model should not be penalised
        # for omitting "uh".
        assert W.wer("uh the cat sat", "the cat sat")["wer"] == 0.0

    def test_real_mistranscription_from_the_corpus(self):
        # Whisper base produced "bloodshed nail audit toilet" for
        # "Bleu de Chanel Eau de Toilette" in haWvrSliMVY.
        r = W.wer("Bleu de Chanel Eau de Toilette in 2021",
                  "bloodshed nail audit toilet in 2021")
        assert r["errors"] == 6
        assert r["ref_words"] == 8
        assert r["wer"] == pytest.approx(0.75)

    def test_empty_reference_does_not_divide_by_zero(self):
        assert W.wer("", "")["wer"] == 0.0


class TestCorpusWer:
    def test_pools_errors_rather_than_averaging_rates(self):
        # Clip A: 1 error in 1 word (rate 1.0). Clip B: 0 errors in 9 words.
        # Averaging rates would give 0.5; pooling gives 1/10 = 0.1.
        pairs = [("cat", "dog"), ("a b c d e f g h i", "a b c d e f g h i")]
        r = W.corpus_wer(pairs)
        assert r["ref_words"] == 10
        assert r["errors"] == 1
        assert r["wer"] == pytest.approx(0.1)

    def test_per_clip_results_retained(self):
        r = W.corpus_wer([("the cat", "the cat"), ("a b", "a c")])
        assert len(r["per_clip"]) == 2
        assert r["per_clip"][0]["wer"] == 0.0
        assert r["per_clip"][1]["wer"] == pytest.approx(0.5)

    def test_totals_are_sums_of_parts(self):
        pairs = [("one two three", "one two"), ("four five", "four five six")]
        r = W.corpus_wer(pairs)
        assert r["deletions"] == sum(c["deletions"] for c in r["per_clip"])
        assert r["insertions"] == sum(c["insertions"] for c in r["per_clip"])
        assert r["ref_words"] == sum(c["ref_words"] for c in r["per_clip"])

    def test_empty_corpus(self):
        assert W.corpus_wer([])["wer"] == 0.0


class TestWilsonInterval:
    def test_known_value(self):
        lo, hi = W.wilson_interval(50, 100)
        assert lo == pytest.approx(0.3983, abs=0.01)
        assert hi == pytest.approx(0.6017, abs=0.01)

    def test_stays_within_bounds_at_extremes(self):
        assert W.wilson_interval(0, 100)[0] == 0.0
        assert W.wilson_interval(100, 100)[1] == pytest.approx(1.0)

    def test_narrows_as_n_grows(self):
        s_lo, s_hi = W.wilson_interval(5, 10)
        l_lo, l_hi = W.wilson_interval(500, 1000)
        assert (l_hi - l_lo) < (s_hi - s_lo)

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError):
            W.wilson_interval(0, 0)
        with pytest.raises(ValueError):
            W.wilson_interval(11, 10)
