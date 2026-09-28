"""
stats.py — the statistics this bench reports, written out rather than imported.

PROTOCOL.md §6 requires it: *"All statistics are implemented by hand in
`stats.py` and unit-tested against values computed independently. No metric is
imported from a library whose behaviour on ties or on small samples has not been
checked here."*

The reason is not purity. It is that three decisions in here change the answer on
this data and must stay visible:

  1. **Tie handling in Spearman.** The human ratings take six values over 120
     segments, so the rank vectors are mostly ties. Average ranks are a choice.
  2. **The difference function in Krippendorff's alpha.** Ordinal, not nominal:
     a 4-vs-5 disagreement is not the same kind of error as a 1-vs-5, and a
     nominal alpha would score them identically and understate agreement.
  3. **The resampling unit in the bootstrap.** Segments, not ratings — the
     segment is the independent observation and the four ratings of one segment
     are not independent of each other.

`controller_bench/stats.py` is the precedent and several functions are restated
from it deliberately rather than imported. Bench directories in this project
share bare module names (`stats`, `report_bench`, `candidates`) and cross-importing
them is the collision that broke test collection in `facial_bench/v2`.

Every function here is pure, total, and covered by `tests/test_baseline_bench.py`,
which checks each one against scipy or scikit-learn where an equivalent exists and
against a hand-computed value where it does not.
"""

from __future__ import annotations

import math
import random
from collections import Counter

Z95 = 1.959963984540054  # two-sided normal quantile at 95%


# ---------------------------------------------------------------- ranks + rho

def ranks(xs: list[float]) -> list[float]:
    """Average ranks, 1-based. Ties share the mean of the ranks they span.

    Exposed rather than nested inside `spearman` because the tie structure of
    this data is itself a reported finding — see BASELINE_RATER_ANALYSIS.md on
    how few distinct values the ground truth actually takes.
    """
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


def pearson(a: list[float], b: list[float]) -> float:
    """Pearson r. Returns 0.0 when either vector is constant (r undefined)."""
    if len(a) != len(b):
        raise ValueError("vectors must be the same length")
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


def spearman(a: list[float], b: list[float]) -> float:
    """Spearman rho with average ranks for ties.

    Identical to `controller_bench/stats.spearman`. A constant vector gives 0.0,
    not an undefined value or a 1.0 — a predictor that says the same thing about
    every segment has demonstrated no correlation, and 0.0 is that statement.
    """
    if len(a) != len(b):
        raise ValueError("vectors must be the same length")
    if len(a) < 2:
        return 0.0
    return pearson(ranks(a), ranks(b))


# ------------------------------------------------------------------ bootstrap

def _percentile(sorted_xs: list[float], q: float) -> float:
    """Linear-interpolation percentile on an already-sorted list, q in [0, 1].

    Matches numpy's default ('linear') so the CI can be cross-checked.
    """
    if not sorted_xs:
        return float("nan")
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_xs[int(pos)]
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


def bootstrap_ci(values: list, statistic, n_boot: int = 10000, seed: int = 42,
                 alpha: float = 0.05) -> dict:
    """Percentile bootstrap over the elements of `values`.

    `values` is a list of *observations* — for this bench, one element per
    segment, each element carrying everything needed to score that segment. The
    segment is the resampling unit because it is the independent observation;
    resampling individual ratings would treat four ratings of one clip as four
    independent facts about the world, which they are not.

    `statistic` maps a resampled list to a float. Resamples on which the
    statistic is undefined (a constant resample, say) are counted and excluded
    rather than silently coerced, because a large `n_degenerate` is itself a
    warning about the sample.

    Percentile rather than BCa: BCa's acceleration term needs a jackknife over a
    statistic that is well behaved under deletion, and a rank correlation on 30
    holdout segments with heavy ties is not. The percentile interval is the more
    conservative and the more honest choice at this sample size, and it is what
    PROTOCOL.md §6 specifies.
    """
    n = len(values)
    point = statistic(values)
    if n < 2:
        return {"point": point, "lo": float("nan"), "hi": float("nan"),
                "n": n, "n_boot": 0, "n_degenerate": 0, "dist": []}
    rng = random.Random(seed)
    dist, degenerate = [], 0
    for _ in range(n_boot):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        s = statistic(resample)
        if s is None or (isinstance(s, float) and math.isnan(s)):
            degenerate += 1
            continue
        dist.append(s)
    dist.sort()
    return {
        "point": point,
        "lo": _percentile(dist, alpha / 2),
        "hi": _percentile(dist, 1 - alpha / 2),
        "n": n, "n_boot": len(dist), "n_degenerate": degenerate,
        "dist": dist,
    }


def paired_bootstrap_diff(values: list, stat_a, stat_b, n_boot: int = 10000,
                          seed: int = 42, alpha: float = 0.05) -> dict:
    """Bootstrap the difference `stat_a - stat_b` on the SAME resamples.

    PROTOCOL.md §6 P3/P4. Two correlations computed on the same segments against
    the same ground truth are dependent, so their individual CIs may overlap
    heavily while the difference is nonetheless consistent in sign. Resampling
    both statistics on one resample preserves that dependence; comparing two
    independently bootstrapped intervals does not, and would be the wrong test.

    `win_frac` is the fraction of resamples in which A strictly exceeds B. It is
    descriptive, not a p-value, and is reported as such.
    """
    n = len(values)
    point = stat_a(values) - stat_b(values)
    if n < 2:
        return {"point": point, "lo": float("nan"), "hi": float("nan"),
                "n": n, "n_boot": 0, "win_frac": float("nan")}
    rng = random.Random(seed)
    dist, wins = [], 0
    for _ in range(n_boot):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        da, db = stat_a(resample), stat_b(resample)
        dist.append(da - db)
        if da > db:
            wins += 1
    dist.sort()
    return {
        "point": point,
        "lo": _percentile(dist, alpha / 2),
        "hi": _percentile(dist, 1 - alpha / 2),
        "n": n, "n_boot": len(dist),
        "win_frac": wins / len(dist),
        "excludes_zero": bool(_percentile(dist, alpha / 2) > 0
                              or _percentile(dist, 1 - alpha / 2) < 0),
    }


# ------------------------------------------------------- agreement, two raters

def weighted_kappa(a: list[int], b: list[int], categories: list[int],
                   weights: str = "linear") -> float:
    """Cohen's weighted kappa for two raters on an ordered category set.

    `categories` is passed in rather than inferred from the data, for one
    reason that was checked rather than assumed: it makes an out-of-scale value
    raise `KeyError` instead of being silently absorbed. A stray 0 (this study's
    "unratable" code) reaching this function is a bug in the caller, and it must
    stop rather than quietly produce a number.

    It does NOT change the value. Adding unused categories to an evenly-spaced
    ordinal scale rescales every weight by the same constant, which cancels in
    the d_obs/d_exp ratio — verified against scikit-learn, which behaves the same
    way. An earlier version of this docstring claimed the opposite; the unit test
    `test_unused_categories_do_not_change_kappa` exists so the claim stays tied
    to the measurement.

    Returns 0.0 when expected disagreement is zero (both raters constant), for
    the same reason `mcc` does in controller_bench: no agreement beyond chance
    can be demonstrated, and 0.0 is that statement rather than a 1.0 awarded for
    two people both pressing the same key.
    """
    if len(a) != len(b):
        raise ValueError("vectors must be the same length")
    if not a:
        raise ValueError("no observations")
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    if weights == "linear":
        w = [[abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]
    elif weights == "quadratic":
        w = [[((i - j) / (k - 1)) ** 2 for j in range(k)] for i in range(k)]
    else:
        raise ValueError("weights must be 'linear' or 'quadratic'")

    n = len(a)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1.0 / n
    ma = [sum(obs[i]) for i in range(k)]
    mb = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    d_obs = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k))
    d_exp = sum(w[i][j] * ma[i] * mb[j] for i in range(k) for j in range(k))
    if d_exp == 0:
        return 0.0
    return 1.0 - d_obs / d_exp


# ------------------------------------------- agreement, any number of raters

def _delta2(metric: str, c, k, cats: list, marg: dict) -> float:
    """Squared difference between two categories under a Krippendorff metric."""
    if c == k:
        return 0.0
    if metric == "nominal":
        return 1.0
    if metric == "interval":
        return float(c - k) ** 2
    if metric == "ordinal":
        lo, hi = (c, k) if c <= k else (k, c)
        span = [g for g in cats if lo <= g <= hi]
        s = sum(marg[g] for g in span) - (marg[lo] + marg[hi]) / 2.0
        return float(s) ** 2
    raise ValueError(f"unknown metric {metric!r}")


def krippendorff_alpha(units: list[list], metric: str = "ordinal",
                       categories: list | None = None) -> dict:
    """Krippendorff's alpha for any number of raters, with missing data allowed.

    `units` is one list per unit (segment) holding the values actually given to
    it; a rater who skipped a unit, or marked it unratable, simply contributes
    nothing to that list. Units with fewer than two values carry no information
    about agreement and are excluded — that is the definition, not a convenience.

    Alpha rather than Fleiss' kappa because Fleiss requires every unit to have
    the same number of raters and cannot express ordinal distance, and both of
    those bite here: unratable answers make the rater count vary per segment,
    and the scale is ordinal.

    The ordinal metric's difference function depends on the **global marginal
    frequencies**, so alpha is not decomposable per unit and cannot be averaged
    over subsets. Reporting a per-split alpha therefore means recomputing it on
    that split, which this function makes the caller do explicitly.

    Returns a dict rather than a float so the observed and expected disagreement
    are inspectable — a high alpha built on a tiny D_e is a different fact from
    a high alpha built on a large one, and only the components show which.
    """
    usable = [u for u in units if len(u) >= 2]
    if not usable:
        return {"alpha": float("nan"), "n_units": 0, "n_pairable": 0,
                "d_obs": float("nan"), "d_exp": float("nan"), "metric": metric}

    values = [v for u in usable for v in u]
    marg = Counter(values)
    cats = sorted(categories) if categories is not None else sorted(marg)
    for c in cats:
        marg.setdefault(c, 0)
    n_pairable = len(values)

    # Observed disagreement.
    d_obs = 0.0
    for u in usable:
        m = len(u)
        cnt = Counter(u)
        acc = 0.0
        for c in cnt:
            for k in cnt:
                acc += cnt[c] * cnt[k] * _delta2(metric, c, k, cats, marg)
        d_obs += acc / (m - 1)
    d_obs /= n_pairable

    # Expected disagreement, from the marginals over all pairable values.
    d_exp = 0.0
    for c in cats:
        for k in cats:
            if marg[c] and marg[k]:
                d_exp += marg[c] * marg[k] * _delta2(metric, c, k, cats, marg)
    d_exp /= n_pairable * (n_pairable - 1)

    alpha = float("nan") if d_exp == 0 else 1.0 - d_obs / d_exp
    return {"alpha": alpha, "n_units": len(usable), "n_pairable": n_pairable,
            "d_obs": d_obs, "d_exp": d_exp, "metric": metric}


def krippendorff_alpha_bruteforce(units: list[list], metric: str = "ordinal",
                                  categories: list | None = None) -> float:
    """Second, independent implementation of alpha, by explicit pair enumeration.

    Not used in the write-up. It exists so the frequency-based implementation
    above can be checked against a different arrangement of the same definition
    rather than against itself — the one form of verification that catches an
    algebra slip shared by a function and its own unit test.

    D_o here is the mean delta^2 over every ordered within-unit pair, weighted so
    each unit contributes in proportion to its number of values, exactly as the
    (m_u - 1) denominator does above. D_e is the mean delta^2 over every ordered
    pair of values drawn from different positions in the whole pooled set.
    """
    usable = [u for u in units if len(u) >= 2]
    if not usable:
        return float("nan")
    values = [v for u in usable for v in u]
    marg = Counter(values)
    cats = sorted(categories) if categories is not None else sorted(marg)
    for c in cats:
        marg.setdefault(c, 0)
    n = len(values)

    num = 0.0
    for u in usable:
        m = len(u)
        pair_sum = sum(_delta2(metric, u[i], u[j], cats, marg)
                       for i in range(m) for j in range(m) if i != j)
        num += pair_sum / (m - 1)
    d_obs = num / n

    d_exp = sum(_delta2(metric, values[i], values[j], cats, marg)
                for i in range(n) for j in range(n) if i != j) / (n * (n - 1))
    return float("nan") if d_exp == 0 else 1.0 - d_obs / d_exp


def icc_2k(matrix: list[list[float]]) -> dict:
    """ICC(2,1) and ICC(2,k), two-way random effects, absolute agreement.

    `matrix` is units x raters, complete (no missing cells).

    Reported because the quantity the bench actually depends on is not how well
    one rater agrees with another — it is how reliable **the mean of four** is,
    since that mean is the ground truth. ICC(2,k) estimates exactly that, and it
    is systematically higher than any pairwise agreement figure for the same
    data. Quoting only a pairwise number would understate the instrument;
    quoting only ICC(2,k) would overstate what one person can do. Both appear.

    Absolute agreement rather than consistency: a rater who is perfectly
    correlated with the others but two points more generous is NOT interchangeable
    with them for a mean-based ground truth, and consistency-ICC would forgive
    that.

    This is a supplementary statistic. It is not named in PROTOCOL.md §6 and is
    labelled as not pre-registered wherever it is quoted.
    """
    n = len(matrix)
    k = len(matrix[0])
    if n < 2 or k < 2:
        return {"icc_2_1": float("nan"), "icc_2_k": float("nan"), "n": n, "k": k}
    grand = sum(sum(r) for r in matrix) / (n * k)
    row_means = [sum(r) / k for r in matrix]
    col_means = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]

    ss_rows = k * sum((rm - grand) ** 2 for rm in row_means)
    ss_cols = n * sum((cm - grand) ** 2 for cm in col_means)
    ss_tot = sum((matrix[i][j] - grand) ** 2 for i in range(n) for j in range(k))
    ss_err = ss_tot - ss_rows - ss_cols

    ms_r = ss_rows / (n - 1)
    ms_c = ss_cols / (k - 1)
    ms_e = ss_err / ((n - 1) * (k - 1))

    den1 = ms_r + (k - 1) * ms_e + k * (ms_c - ms_e) / n
    denk = ms_r + (ms_c - ms_e) / n
    return {
        "icc_2_1": (ms_r - ms_e) / den1 if den1 else float("nan"),
        "icc_2_k": (ms_r - ms_e) / denk if denk else float("nan"),
        "ms_rows": ms_r, "ms_cols": ms_c, "ms_err": ms_e, "n": n, "k": k,
    }


def spearman_brown(rho: float, k: float) -> float:
    """Reliability of a k-times-longer instrument, from the single-unit value.

    Used one way only here: given the measured agreement of one rater with
    others, what would a panel of k such raters achieve? It answers "is four
    raters enough, and how much would a fifth buy?" — which is a real design
    question for the user study that follows this bench, and is cheap to answer
    from data already collected.
    """
    if rho <= -1 or rho >= 1:
        return rho
    den = 1 + (k - 1) * rho
    return k * rho / den if den else float("nan")


def mean_ci(xs: list[float], z: float = Z95) -> tuple[float, float, float]:
    """(mean, lo, hi) using the normal interval on the standard error."""
    n = len(xs)
    if n == 0:
        return (0.0, 0.0, 0.0)
    m = sum(xs) / n
    if n < 2:
        return (m, m, m)
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return (m, m - z * se, m + z * se)


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Restated from
    controller_bench/stats.py — see the note at the top on why this bench does
    not import across bench directories."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - half) / d), min(1.0, (centre + half) / d))


def describe(xs: list[float]) -> dict:
    """mean / sd / median / quartiles / range, for one vector."""
    n = len(xs)
    if n == 0:
        return {"n": 0}
    s = sorted(xs)
    m = sum(s) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in s) / (n - 1)) if n > 1 else 0.0
    return {"n": n, "mean": m, "sd": sd,
            "min": s[0], "q1": _percentile(s, 0.25), "median": _percentile(s, 0.5),
            "q3": _percentile(s, 0.75), "max": s[-1]}
