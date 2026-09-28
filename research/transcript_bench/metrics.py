"""
metrics.py - scoring arithmetic for the transcript bench.

Pure functions, no I/O, no model calls. Everything the bench reports as a number
is computed here so that it can be unit-tested directly:
I/O and model calls are mocked in tests, the arithmetic never is.

Definitions follow CANDIDATE_MODELS.md Section 3:
  - primary metric        NEUTRAL recall
  - reported alongside    three-class accuracy + Wilson 95% interval, macro-F1,
                          per-class precision/recall/F1, confusion matrix,
                          exact McNemar against the incumbent
"""

from __future__ import annotations

import math
from collections import Counter

LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")


def accuracy(gold: list[str], pred: list[str]) -> float:
    if len(gold) != len(pred):
        raise ValueError(f"length mismatch: {len(gold)} gold vs {len(pred)} pred")
    if not gold:
        raise ValueError("cannot compute accuracy on an empty sample")
    return sum(g == p for g, p in zip(gold, pred)) / len(gold)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation because it stays inside [0, 1] and
    behaves at extreme proportions - this bench has classes where a model scores
    near 0 (the incumbent's NEUTRAL recall), where the normal approximation
    produces negative lower bounds.
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


def confusion_matrix(
    gold: list[str], pred: list[str], labels: tuple[str, ...] = LABELS
) -> dict[str, dict[str, int]]:
    """matrix[true_label][predicted_label] = count."""
    if len(gold) != len(pred):
        raise ValueError(f"length mismatch: {len(gold)} gold vs {len(pred)} pred")
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for g, p in zip(gold, pred):
        if g not in matrix:
            raise ValueError(f"unknown gold label {g!r}")
        if p not in matrix[g]:
            raise ValueError(f"unknown predicted label {p!r}")
        matrix[g][p] += 1
    return matrix


def per_class_prf(
    gold: list[str], pred: list[str], labels: tuple[str, ...] = LABELS
) -> dict[str, dict[str, float]]:
    """Precision, recall, F1 and support for each class.

    A class with no predictions gets precision 0.0 rather than an error: a model
    that never predicts NEUTRAL is a real and expected outcome on this bench, and
    it must score, not crash.
    """
    gold_counts = Counter(gold)
    pred_counts = Counter(pred)
    hits = Counter(g for g, p in zip(gold, pred) if g == p)

    out: dict[str, dict[str, float]] = {}
    for lab in labels:
        tp = hits[lab]
        precision = tp / pred_counts[lab] if pred_counts[lab] else 0.0
        recall = tp / gold_counts[lab] if gold_counts[lab] else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        out[lab] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": gold_counts[lab],
            "predicted": pred_counts[lab],
        }
    return out


def macro_f1(
    gold: list[str], pred: list[str], labels: tuple[str, ...] = LABELS
) -> float:
    prf = per_class_prf(gold, pred, labels)
    return sum(prf[lab]["f1"] for lab in labels) / len(labels)


def mcnemar_exact(
    gold: list[str], pred_a: list[str], pred_b: list[str]
) -> dict[str, float | int]:
    """Two-sided exact McNemar test comparing two classifiers on the same items.

    b = items A got right and B got wrong; c = the reverse. Concordant pairs carry
    no information and are excluded by construction. The exact test is the two-sided
    binomial test on b successes in b+c trials at p=0.5, which is why scipy is not
    needed here and statsmodels is not added as a dependency.

    Also returns `min_attainable_p` = 2*(1/2)^(b+c), the smallest two-sided p this
    discordant count could ever produce. CANDIDATE_MODELS.md Section 3 requires it
    to be reported: when it exceeds 0.05, a genuine improvement cannot reach
    significance and the null result is a property of the test, not of the models.
    """
    if not (len(gold) == len(pred_a) == len(pred_b)):
        raise ValueError("gold, pred_a and pred_b must be the same length")

    b = sum(a == g and bb != g for g, a, bb in zip(gold, pred_a, pred_b))
    c = sum(a != g and bb == g for g, a, bb in zip(gold, pred_a, pred_b))
    n = b + c

    if n == 0:
        return {
            "b": 0, "c": 0, "n_discordant": 0,
            "p_value": 1.0, "min_attainable_p": 1.0,
        }

    # Two-sided exact binomial: sum of probabilities of outcomes no more likely
    # than the observed one. For p=0.5 the distribution is symmetric, so this is
    # the doubled smaller tail, capped at 1.
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    p_value = min(1.0, 2 * tail)

    return {
        "b": b,
        "c": c,
        "n_discordant": n,
        "p_value": p_value,
        "min_attainable_p": min(1.0, 2 * (0.5 ** n)),
    }


def summarise(gold: list[str], pred: list[str]) -> dict:
    """The full metric block reported for every candidate."""
    n = len(gold)
    correct = sum(g == p for g, p in zip(gold, pred))
    lo, hi = wilson_interval(correct, n)
    prf = per_class_prf(gold, pred)
    return {
        "n": n,
        "accuracy": correct / n,
        "accuracy_ci95": [lo, hi],
        "macro_f1": macro_f1(gold, pred),
        "neutral_recall": prf["NEUTRAL"]["recall"],
        "neutral_predicted": prf["NEUTRAL"]["predicted"],
        "per_class": prf,
        "confusion": confusion_matrix(gold, pred),
    }
