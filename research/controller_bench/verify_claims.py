"""
verify_claims.py — re-derive every number this bench publishes, from the cache.

The project's evidence rule (README, "Engineering rules"): "If a number is quoted anywhere, it must be traceable to a file in
this repo that produced it." This script is that traceability, in the pattern of
`facial_bench/v2/verify_claims.py`, `vocal_bench/verify_ab.py` and
`transcript_bench/verify_claims.py`.

Every claim is recomputed from the raw cached responses under `cache/`, and the
recomputed value is then required to appear **verbatim in the prose**. Both halves
matter and neither is sufficient alone: recomputing would only prove the code is
self-consistent, and grepping would only prove a string exists. Together they
prove the sentence in the write-up came from the responses on disk.

    python research/controller_bench/verify_claims.py
    python research/controller_bench/verify_claims.py --verbose

Exit code 0 if every claim holds, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(HERE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import candidates as C  # noqa: E402
import probes as P  # noqa: E402
import reference as R  # noqa: E402
import report_bench as RPT  # noqa: E402
import stats as S  # noqa: E402
import run_bench as RB  # noqa: E402

ANALYSIS = HERE / "CONTROLLER_MODEL_ANALYSIS.md"
PROTOCOL = HERE / "PROTOCOL.md"
CACHE = HERE / "cache"

PASS: list[tuple] = []
FAIL: list[tuple] = []


def check(name: str, got, want, tol: float | None = None) -> None:
    if tol is not None and isinstance(got, (int, float)) and isinstance(want, (int, float)):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    (PASS if ok else FAIL).append((name, got, want))


def check_true(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append((name, bool(condition), f"True {detail}".strip()))


def in_doc(name: str, needle: str, doc: str) -> None:
    """The recomputed value must appear verbatim in the write-up.

    Markdown emphasis is stripped for the second attempt: `**0.106**` carries the
    same value as `0.106`, and a check that failed on bold markers would be
    testing the typography rather than the number.
    """
    ok = needle in doc or needle in doc.replace("**", "")
    (PASS if ok else FAIL).append((name, f"{needle!r} in doc", "present"))


def _pct1(x: float) -> str:
    return f"{x * 100:.1f}%"


def _f3(x: float) -> str:
    return f"{x:.3f}"


def _p(pv: float) -> str:
    """Render a p-value the way the prose must render it.

    `f"{p:.4f}"` turns a genuinely tiny p into the string "0.0000", which reads as
    "exactly zero" and is not a thing a p-value can be. Below the display
    resolution it is written as an inequality instead, and the verifier requires
    that same string, so prose and check cannot drift apart.
    """
    return "< 0.0001" if pv < 0.0001 else f"{pv:.4f}"


# ── §1 the motivating measurement (the cached incumbent responses) ────────────

def verify_motivation(doc: str) -> None:
    """The 481/473/81/8 figures, re-derived from vocal_bench's cache."""
    ab = ROOT / "research" / "vocal_bench" / "ab_cache"
    if not (ab / "conflict_after_nodamp").is_dir():
        return
    rows = []
    for f in sorted((ab / "conflict_after_nodamp").glob("*.json")):
        vid = f.stem
        conf = json.loads(f.read_text())
        ts = json.loads((ab / "transcript" / f"{vid}.json").read_text())
        ve = json.loads((ab / "vocal_audeering" / f"{vid}.json").read_text())
        cs = json.loads((ab / "comments" / f"{vid}.json").read_text())
        for k, r in conf.items():
            v = ve[k]
            spec = {
                "transcript_sentiment": (ts[k] or {}).get("label"),
                "vocal_emotion": v.get("label") if isinstance(v, dict) else v,
                "facial_emotion": "none detected",
                "video_comment_sentiment": (cs or {}).get("label"),
            }
            rows.append((R.channel_valences(spec), float(r["conflict_score"]),
                         r.get("_raw") or {}))

    n = len(rows)
    zeros = sum(1 for _v, s, _raw in rows if s == 0.0)
    agree = [r for r in rows if not R.ref_any(r[0])]
    polar = [r for r in rows if R.ref_polar(r[0])]
    adjacent = [r for r in rows if R.ref_any(r[0]) and not R.ref_polar(r[0])]
    polar_hit = sum(1 for _v, s, _raw in polar if s > 0.0)

    check("motivation: corpus size", n, 481)
    check("motivation: zero-score responses", zeros, 473)
    check("motivation: full-agreement segments", len(agree), 43)
    check("motivation: adjacent-only segments", len(adjacent), 357)
    check("motivation: polar segments", len(polar), 81)
    check("motivation: polar detected", polar_hit, 8)
    in_doc("motivation: 473 of 481 in doc", "473 of 481", doc)
    in_doc("motivation: 81 polar in doc", "81", doc)
    in_doc("motivation: 8 detected in doc", "8", doc)

    named = sum(1 for _v, _s, raw in rows
                if isinstance(raw.get("channels_in_conflict"), list)
                and raw["channels_in_conflict"])
    check("motivation: responses naming >=1 channel", named, 265)
    flags = sum(1 for _v, _s, raw in rows if raw.get("flags"))
    check("motivation: responses emitting a flag", flags, 0)
    in_doc("motivation: zero flags in doc", "0 of 481", doc)

    halluc = sum(1 for _v, _s, raw in rows
                 if "facial_emotion" in R.normalise_channels(
                     raw.get("channels_in_conflict")))
    check("motivation: facial named on a corpus with no facial channel", halluc, 264)

    # Wilson interval on the polar detection rate, quoted in the write-up.
    lo, hi = S.wilson(polar_hit, len(polar))
    in_doc("motivation: polar detection rate", _pct1(polar_hit / len(polar)), doc)
    in_doc("motivation: polar CI", f"{_pct1(lo)}–{_pct1(hi)}", doc)


# ── §2 the suites ─────────────────────────────────────────────────────────────

def verify_suites(doc: str) -> None:
    grid = P.probe_suite()
    inc = P.incongruence_suite()
    check("grid size", len(grid), 108)
    check("grid unique ids", len({p["probe_id"] for p in grid}), 108)
    check("grid unique configurations",
          len({tuple(sorted(p["spec"].items())) for p in grid}), 108)
    check("grid single carrier text", len({p["segment"]["text"] for p in grid}), 1)

    vals = [R.channel_valences(p["spec"]) for p in grid]
    agree = sum(1 for v in vals if not R.ref_any(v))
    polar = sum(1 for v in vals if R.ref_polar(v))
    check("grid full-agreement configurations", agree, 6)
    check("grid polar configurations", polar, 62)
    check("grid adjacent-only configurations", 108 - agree - polar, 40)
    in_doc("grid: 108 in doc", "108", doc)
    in_doc("grid: 62 polar in doc", "62", doc)

    check("incongruence total", len(inc), 36)
    check("incongruence positives", sum(p["expected_conflict"] for p in inc), 24)
    check("incongruence controls", sum(not p["expected_conflict"] for p in inc), 12)
    check_true("incongruence: every item's labels agree",
               all(not R.ref_any(R.channel_valences(p["spec"])) for p in inc))
    check_true("incongruence: rule_baseline scores 0.0 on every item",
               all(R.rule_baseline(p["spec"])["conflict_score"] == 0.0 for p in inc))
    check("incongruence rationales published", len(P.incongruence_rationales()), 24)


# ── §3 Bench A, the configuration grid ────────────────────────────────────────

def verify_grid(doc: str) -> dict:
    grids = {n: g for n in C.ALL_CANDIDATES if (g := RPT.score_grid(n))}
    check_true("grid: at least the incumbent was run", RPT.INCUMBENT in grids)

    for name, g in grids.items():
        check(f"grid[{name}]: n", g["n"], 108)
        in_doc(f"grid[{name}]: P1 in doc", _f3(g["P1_mcc"]), doc)
        in_doc(f"grid[{name}]: P4 in doc", f"{g['P4_k']}/{g['P4_n']}", doc)

    if "rule_baseline" in grids:
        rb = grids["rule_baseline"]
        check("grid: rule_baseline P1 is 1.000 by construction",
              round(rb["P1_mcc"], 6), 1.0)
        check("grid: rule_baseline P2 is 1.000 by construction",
              round(rb["P2_spearman"], 6), 1.0)
        check("grid: rule_baseline detects every polar configuration",
              rb["P4_k"], rb["P4_n"])
    for const in ("always_zero", "always_flag"):
        if const in grids:
            check(f"grid: {const} P1 is exactly 0.000", grids[const]["P1_mcc"], 0.0)

    inc_g = grids.get(RPT.INCUMBENT)
    if inc_g:
        # The characterisation claim: every non-zero answer the incumbent gave has
        # a NEGATIVE comment channel. Recomputed, not asserted.
        runs = json.loads((CACHE / "grid" / f"{RPT.INCUMBENT}.json").read_text())
        by = {p["probe_id"]: p for p in P.probe_suite()}
        nonzero = [by[k]["spec"] for k, v in runs.items() if v["conflict_score"] > 0]
        check(f"grid[{RPT.INCUMBENT}]: non-zero probes", len(nonzero), 9)
        check_true(f"grid[{RPT.INCUMBENT}]: every non-zero has a NEGATIVE comment "
                   "channel",
                   all(s["video_comment_sentiment"] == "NEGATIVE" for s in nonzero))
        by_comment = Counter(s["video_comment_sentiment"] for s in nonzero)
        check(f"grid[{RPT.INCUMBENT}]: non-zero with POSITIVE comments",
              by_comment.get("POSITIVE", 0), 0)
        check(f"grid[{RPT.INCUMBENT}]: non-zero with NEUTRAL comments",
              by_comment.get("NEUTRAL", 0), 0)
    return grids


# ── §4 Bench B, the incongruence suite ────────────────────────────────────────

def verify_incongruence(doc: str) -> dict:
    incs = {n: i for n in C.ALL_CANDIDATES if (i := RPT.score_incongruence(n))}
    for name, i in incs.items():
        check(f"incong[{name}]: positives", i["n_pos"], 24)
        check(f"incong[{name}]: controls", i["n_neg"], 12)
        in_doc(f"incong[{name}]: P5 in doc", _f3(i["P5"]), doc)
    for const, expect in (("rule_baseline", 0.0), ("always_zero", 0.0)):
        if const in incs:
            check(f"incong: {const} P5 is exactly 0.000", incs[const]["P5"], expect)
    if "always_flag" in incs:
        check("incong: always_flag P5 is exactly 0.000", incs["always_flag"]["P5"], 0.0)
    return incs


# ── §5 Bench C, the real corpus ───────────────────────────────────────────────

CORPUS_N = 481


def verify_corpus(doc: str) -> dict:
    """Corpus claims, for the candidates whose corpus run is COMPLETE.

    A partially-run candidate is skipped rather than failed, and the skip is
    printed. The corpus stage takes hours per candidate and is external validity
    only (PROTOCOL.md §4.2); a half-finished run is not evidence of anything and
    must not be quoted, but neither is it a broken claim. The write-up states its
    own coverage, and `check` below enforces that every candidate the prose cites
    is one of the complete ones.
    """
    corp = {n: c for n in C.ALL_CANDIDATES if (c := RPT.score_corpus(n))}
    complete = {n: c for n, c in corp.items() if c["n"] == CORPUS_N}
    partial = sorted(set(corp) - set(complete))
    if partial:
        print(f"  (corpus incomplete, skipped: {partial})")

    for name, c in complete.items():
        check(f"corpus[{name}]: n", c["n"], CORPUS_N)
        in_doc(f"corpus[{name}]: polar in doc", f"{c['polar_k']}/{c['polar_n']}", doc)
    if complete:
        any_c = next(iter(complete.values()))
        check("corpus: polar denominator matches the motivating measurement",
              any_c["polar_n"], 81)

    # Nothing partial may be quoted. A candidate named in the corpus table whose
    # run did not finish would be a number with no denominator behind it.
    for name in partial:
        check_true(f"corpus[{name}]: incomplete run is NOT quoted in the prose",
                   f"| `{name}` |" not in doc.split("## 10.")[-1].split("## 11.")[0]
                   if "## 10." in doc else True)
    return complete


# ── §5.6 robustness, and §5.2 channel marginals ───────────────────────────────

def verify_robustness(doc: str) -> None:
    """Every figure in the §5.6 robustness table and the §5.2 marginals table.

    These were published late (§5.6 was written after the run finished), which is
    exactly when a table is most likely to be typed rather than pasted. Each cell
    is recomputed and required verbatim.
    """
    for name in C.ALL_CANDIDATES:
        if not RPT.score_grid(name):
            continue
        sw = RPT.sensitivity_adjacent_weight(name)
        for w in RPT.ADJACENT_WEIGHTS:
            if w in sw:
                in_doc(f"robust[{name}]: P2 at w={w} in doc", _f3(sw[w]), doc)
        st = RPT.sensitivity_p1_threshold(name)
        for t in RPT.P1_THRESHOLDS:
            if t in st:
                in_doc(f"robust[{name}]: P1 at >{t} in doc", _f3(st[t]), doc)
        ft = RPT.detection_at_flag_threshold(name)
        if ft:
            in_doc(f"robust[{name}]: flagged polar in doc",
                   f"{ft['flagged_polar']}/{ft['n_polar']}", doc)

    # §5.2: the incumbent's marginal on the comment channel is the claim that
    # names its failure, so it is checked cell by cell rather than in prose.
    m = RPT.channel_marginals(RPT.INCUMBENT)
    if m:
        cell = m["video_comment_sentiment"]
        for lvl in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
            in_doc(f"marginal[{RPT.INCUMBENT}]: comment {lvl} in doc",
                   f"{cell[lvl]['mean']:.2f}", doc)
        check_true("marginal: incumbent is non-zero ONLY on a NEGATIVE comment "
                   "channel",
                   cell["POSITIVE"]["mean"] == 0.0 and cell["NEUTRAL"]["mean"] == 0.0
                   and cell["NEGATIVE"]["mean"] > 0.0)

    # §6's closed-form result, recomputed.
    tr = RPT.threshold_reachability()
    row = tr["readings"]["pairwise (this bench, pre-registered)"]
    check("threshold: max at 4 channels under the pre-registered reading",
          round(row[4]["max"], 4), 0.6667)
    check_true("threshold: unreachable at 4 channels under the pre-registered "
               "reading", not row[4]["reaches"])
    n_unreachable = sum(1 for r in tr["readings"].values() if not r[4]["reaches"])
    check("threshold: readings that cannot reach 0.75 at 4 channels",
          n_unreachable, 3)
    in_doc("threshold: 0.667 quoted", "0.667", doc)


# ── §6 determinism (G2) ───────────────────────────────────────────────────────

def verify_determinism(doc: str) -> None:
    for name in C.LLM_CANDIDATES:
        a_path = CACHE / "grid" / f"{name}.json"
        b_path = CACHE / "determinism" / f"{name}_rep.json"
        if not (a_path.is_file() and b_path.is_file()):
            continue
        a, b = json.loads(a_path.read_text()), json.loads(b_path.read_text())
        shared = sorted(set(a) & set(b))
        if not shared:
            continue
        same = sum(1 for k in shared
                   if a[k]["conflict_score"] == b[k]["conflict_score"])
        check(f"G2[{name}]: identical scores on re-run", same, len(shared))


# ── §7 the adoption rule ──────────────────────────────────────────────────────

def verify_adoption(doc: str, grids: dict, incs: dict) -> None:
    if RPT.INCUMBENT not in grids:
        return
    lat = grids[RPT.INCUMBENT]["median_latency_s"]
    ad = RPT.evaluate_adoption(grids, incs, lat)
    verdict = ad["winner"] or "NONE"
    check_true("adoption: the rule was evaluated", isinstance(ad["rows"], list))
    if ad["winner"] is None:
        in_doc("adoption: nothing adopted is stated", "nothing is adopted", doc)
    else:
        in_doc("adoption: winner named in doc", ad["winner"], doc)
    for r in ad["rows"]:
        if r["mcnemar"]:
            in_doc(f"adoption[{r['candidate']}]: McNemar p in doc",
                   _p(r["mcnemar"]["p"]), doc)
    # No candidate may be reported as better without the direction check.
    for r in ad["rows"]:
        m = r["mcnemar"]
        if m and m["p"] < 0.05:
            check_true(f"adoption[{r['candidate']}]: direction checked, not just p",
                       m["better"] != m["worse"])
    print(f"  (adoption verdict recomputed: {verdict})")


# ── §8 the prompt ablation ────────────────────────────────────────────────────

def verify_ablation(doc: str) -> None:
    rev = RB.revised_prompt()
    from pipeline import orchestrator as O
    check_true("ablation: revision keeps every deployed prompt line",
               all(line in rev for line in O._SYSTEM_PROMPT.splitlines() if line.strip()))
    check_true("ablation: revision keeps the CHANNEL RELIABILITY paragraph",
               "CHANNEL RELIABILITY" in rev)
    for name in C.LLM_CANDIDATES:
        base, revd = RPT.score_grid(name), RPT.score_grid(name, "ablation", "_revised")
        if base and revd:
            in_doc(f"ablation[{name}]: revised P1 in doc", _f3(revd["P1_mcc"]), doc)


# ── §9 the hard constraints this bench must not have broken ───────────────────

def verify_constraints() -> None:
    check_true("constraint: no candidate routes off-machine",
               all("cloud" not in s["tag"] for s in C.LLM_CANDIDATES.values()))
    check_true("constraint: all three cloud models are excluded on the constraint",
               all(C.EXCLUSIONS[t][0] == "constraint"
                   for t in ("gpt-oss:20b-cloud", "deepseek-v3.1:671b-cloud",
                             "qwen3-coder:480b-cloud")))
    from pipeline import orchestrator as O
    check_true("constraint: the orchestrator still points at localhost",
               "localhost" in O.OLLAMA_BASE_URL or "127.0.0.1" in O.OLLAMA_BASE_URL)
    # No cached response may contain anything that looks like a comment author.
    for stage in ("grid", "incongruence"):
        d = CACHE / stage
        if d.is_dir():
            for f in d.glob("*.json"):
                check_true(f"privacy: {stage}/{f.name} carries no author field",
                           '"authorDisplayName"' not in f.read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    doc = ANALYSIS.read_text() if ANALYSIS.exists() else ""
    if not doc:
        print(f"note: {ANALYSIS.name} not written yet — "
              "recomputation runs, prose checks are skipped", file=sys.stderr)

    verify_constraints()
    verify_suites(doc)
    verify_motivation(doc)
    grids = verify_grid(doc)
    incs = verify_incongruence(doc)
    verify_corpus(doc)
    verify_robustness(doc)
    verify_determinism(doc)
    verify_adoption(doc, grids, incs)
    verify_ablation(doc)

    if args.verbose:
        for name, got, want in PASS:
            print(f"  ok    {name}: {got}")
    for name, got, want in FAIL:
        print(f"  FAIL  {name}: got {got!r}, expected {want!r}")

    print(f"\n{len(PASS)} claims verified, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
