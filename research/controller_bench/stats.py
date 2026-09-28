"""
stats.py — the statistics this bench reports, written out rather than imported.

The project convention, set by `vocal_bench/report_bench.spearman`, is to write
these by hand: the bench keeps working without scipy, and — more importantly —
the parts that change the answer stay visible and unit-testable. Tie handling in
Spearman and the continuity choice in an exact McNemar are both decisions, not
library details, and this data has heavy ties.

Every function here is pure, total, and covered by `tests/test_controller_bench.py`
against values computed independently.
"""

from __future__ import annotations

import math

Z95 = 1.959963984540054  # two-sided normal quantile at 95%


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Wilson rather than the normal approximation because this bench reports
    proportions near 0 and near 1 — a detection rate of 8/81 and of 108/108 both
    occur — and the normal interval is nonsense at both ends, running below zero
    or above one. Wilson stays inside [0, 1] by construction and is the interval
    the other benches in this project report.

    n == 0 returns (0.0, 1.0): no information, stated as no information.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - half) / d), min(1.0, (centre + half) / d))


def mcc(gold: list[bool], pred: list[bool]) -> float:
    """Matthews correlation coefficient for two binary vectors.

    The primary metric of this bench (PROTOCOL.md §5.2), chosen for one property:
    **a constant predictor scores exactly 0.0, whatever the class balance.** The
    probe suite is unbalanced — 102 of 108 configurations disagree somewhere — so
    plain accuracy would hand `always_flag` a 94.4% and make the headline
    meaningless. MCC cannot be won that way.

    Returns 0.0 when either vector is constant, where the coefficient is
    undefined (a zero denominator): no correlation can be demonstrated, and 0.0
    is that statement. It is never returned as 1.0 for two matching constants.
    """
    if len(gold) != len(pred):
        raise ValueError("vectors must be the same length")
    if not gold:
        raise ValueError("no observations")
    tp = sum(1 for g, p in zip(gold, pred) if g and p)
    tn = sum(1 for g, p in zip(gold, pred) if not g and not p)
    fp = sum(1 for g, p in zip(gold, pred) if not g and p)
    fn = sum(1 for g, p in zip(gold, pred) if g and not p)
    den = math.sqrt(float(tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if den == 0.0:
        return 0.0
    return (tp * tn - fp * fn) / den


def confusion(gold: list[bool], pred: list[bool]) -> dict:
    """tp/tn/fp/fn plus the rates, so a table can quote them without recomputing."""
    tp = sum(1 for g, p in zip(gold, pred) if g and p)
    tn = sum(1 for g, p in zip(gold, pred) if not g and not p)
    fp = sum(1 for g, p in zip(gold, pred) if not g and p)
    fn = sum(1 for g, p in zip(gold, pred) if g and not p)
    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "sensitivity": tp / (tp + fn) if (tp + fn) else None,
        "specificity": tn / (tn + fp) if (tn + fp) else None,
    }


def spearman(a: list[float], b: list[float]) -> float:
    """Spearman rho with average ranks for ties.

    Tie handling matters here more than in most places: several candidates answer
    with a constant, and a controller that returns 0.0 on every probe is one giant
    tie. Average ranks make that a rho of 0.0 rather than an artefact.

    Same implementation as `vocal_bench/report_bench.spearman`, restated here so
    this bench does not import across bench directories — those share bare module
    names (`candidates`, `report_bench`) and cross-importing them is exactly the
    collision that broke test collection in `facial_bench/v2`.
    """
    if len(a) != len(b):
        raise ValueError("vectors must be the same length")
    n = len(a)
    if n < 2:
        return 0.0

    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


def _binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact McNemar p-value on the discordant pairs.

    `a_only` = pairs where model A is right and B is wrong; `b_only` = the
    reverse. Concordant pairs carry no information about a difference and are
    correctly ignored.

    Exact (binomial) rather than the chi-square approximation because the
    discordant counts here are often small — some comparisons have fewer than 10 —
    and chi-square is unreliable there.

    **Two-sided, and that matters.** A model that is significantly WORSE also
    returns p < 0.05. `facial_bench/v2` §6 records the consequence: six models
    there were "significantly different" from a constant by being far worse, and
    reading that as "significantly better" would have inverted the finding. Every
    caller must check the direction separately; `mcnemar_verdict` below does it so
    no caller has to remember.

    No discordant pairs at all returns 1.0: identical behaviour is not evidence
    of a difference.
    """
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(_binom_pmf(i, n) for i in range(k + 1))
    return min(1.0, 2.0 * tail)


def mcnemar_verdict(a_only: int, b_only: int, alpha: float = 0.05) -> dict:
    """The p-value AND the direction, so the two cannot be separated by accident.

    `better` is True only when A wins on more discordant pairs than B *and* the
    test clears alpha. That conjunction is the whole point of this wrapper.
    """
    p = mcnemar_exact(a_only, b_only)
    return {
        "a_only": a_only, "b_only": b_only, "n_discordant": a_only + b_only,
        "p": p,
        "better": bool(p < alpha and a_only > b_only),
        "worse": bool(p < alpha and b_only > a_only),
    }


def mean_ci(xs: list[float], z: float = Z95) -> tuple[float, float, float]:
    """(mean, lo, hi) using the normal interval on the standard error.

    Used only for bounded means over ~100 observations (P3's Jaccard, latency),
    where the normal interval is appropriate. Proportions use `wilson` instead —
    they are the ones that sit near the boundaries.
    """
    n = len(xs)
    if n == 0:
        return (0.0, 0.0, 0.0)
    m = sum(xs) / n
    if n < 2:
        return (m, m, m)
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return (m, m - z * se, m + z * se)
