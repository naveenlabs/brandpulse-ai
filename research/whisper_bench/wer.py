"""
wer.py - word error rate arithmetic for the Whisper bench.

Pure functions, no I/O, no model calls, so the numbers the bench reports can be
unit-tested directly (mock I/O, never the arithmetic).

WER = (S + D + I) / N

    S  substitutions   a reference word replaced by a different word
    D  deletions       a reference word the model did not produce
    I  insertions      a word the model produced that is not in the reference
    N  reference words

Note WER can exceed 1.0: a model that hallucinates a long passage accrues more
insertions than there are reference words. That is a real outcome, not a bug, and
is left uncapped so it stays visible.

Text normalisation uses OpenAI's own EnglishTextNormalizer, shipped with the
whisper package and used for the WER figures in the Whisper paper. It lowercases,
strips punctuation, expands contractions and removes filler words. Using theirs
rather than a hand-rolled one means our numbers are computed the same way as the
published ones, and removes a degree of freedom we could otherwise have tuned.
"""

from __future__ import annotations

import math
from functools import lru_cache


@lru_cache(maxsize=1)
def _normalizer():
    from whisper.normalizers import EnglishTextNormalizer
    return EnglishTextNormalizer()


def normalise(text: str) -> list[str]:
    """Normalise with OpenAI's normalizer and split into words."""
    return _normalizer()(text).split()


def edit_counts(reference: list[str], hypothesis: list[str]) -> dict[str, int]:
    """Levenshtein alignment over words, returning S/D/I and the reference length.

    Standard dynamic programme with unit costs. Backtracking recovers the counts
    of each operation rather than only the total distance, because the three are
    reported separately: a model that deletes is failing differently from one
    that hallucinates.
    """
    n, m = len(reference), len(hypothesis)
    # d[i][j] = distance between reference[:i] and hypothesis[:j]
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if reference[i - 1] == hypothesis[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(
                    d[i - 1][j - 1],   # substitution
                    d[i - 1][j],       # deletion
                    d[i][j - 1],       # insertion
                )

    sub = dele = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and reference[i - 1] == hypothesis[j - 1] \
                and d[i][j] == d[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + 1:
            sub += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1

    return {"substitutions": sub, "deletions": dele, "insertions": ins,
            "ref_words": n, "hyp_words": m,
            "errors": sub + dele + ins}


def wer(reference: str, hypothesis: str) -> dict:
    """Word error rate between two raw strings, after normalisation."""
    ref, hyp = normalise(reference), normalise(hypothesis)
    counts = edit_counts(ref, hyp)
    counts["wer"] = counts["errors"] / counts["ref_words"] if counts["ref_words"] else 0.0
    return counts


def corpus_wer(pairs: list[tuple[str, str]]) -> dict:
    """Aggregate WER over many clips.

    Errors and reference words are pooled before dividing, rather than averaging
    the per-clip rates. Averaging rates would weight a 20-word clip the same as a
    200-word one; pooling weights each word equally, which is the standard
    definition and the one the published Whisper numbers use.
    """
    total = {"substitutions": 0, "deletions": 0, "insertions": 0,
             "ref_words": 0, "hyp_words": 0, "errors": 0}
    per_clip = []
    for ref, hyp in pairs:
        c = wer(ref, hyp)
        per_clip.append(c)
        for k in total:
            total[k] += c[k]
    total["wer"] = total["errors"] / total["ref_words"] if total["ref_words"] else 0.0
    total["per_clip"] = per_clip
    return total


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval, used here on word-level accuracy (1 - WER).

    Words within a clip are not independent, so this interval is optimistic. It is
    reported for scale, and that caveat is stated wherever it is quoted.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError(f"successes {successes} out of range for n {n}")
    phat = successes / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)
