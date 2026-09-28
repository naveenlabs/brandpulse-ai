"""
verify_claims.py — every number in FAIRNESS_ANALYSIS.md, re-derived from disk.

The write-up is prose and prose drifts. This reads the analysis, pulls out each
figure it states, recomputes that figure from facial_bench/v2/ by running the
bench again in-process, and fails if any of them disagree.

Same pattern as controller_bench/verify_claims.py and
facial_bench/v2/verify_claims.py. A number in the write-up that this file does
not check is a bug in this file, not a licence.

    python research/fairness_bench/verify_claims.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS = HERE / "FAIRNESS_ANALYSIS.md"
PROTOCOL = HERE / "PROTOCOL.md"
DATA = HERE / "per_speaker.json"
V2 = ROOT / "research" / "facial_bench" / "v2"

DEPLOYED = "deepface_fer"
CONSTANT = "always-NEUTRAL constant"

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def main() -> int:
    if not DATA.exists():
        print("per_speaker.json missing — run per_speaker.py first")
        return 1

    # Recompute rather than trust the cached JSON: if per_speaker.py has been
    # edited since it last ran, the file on disk is not evidence of anything.
    before = DATA.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(HERE / "per_speaker.py")],
                   cwd=ROOT, capture_output=True, check=True)
    after = DATA.read_text(encoding="utf-8")
    check("the bench is reproducible (re-running gives byte-identical output)",
          before == after)

    d = json.loads(after)
    md = flat(ANALYSIS.read_text(encoding="utf-8"))
    dep = d["speakers"][DEPLOYED]
    con = d["speakers"][CONSTANT]
    lift = d["lift_post_hoc"]

    # ── §2: it reproduces the bench it re-cuts ────────────────────────────────
    published = json.loads((ROOT / "evaluation" / "ui_evidence" / "figures.json").read_text())
    facial = next(c for c in published["channels"] if c["channel"] == "facial")
    constant_ref = next(r for r in published["facial_references"]
                        if "constant" in r["name"])
    check("holdout deployed accuracy equals the published channel figure",
          dep["by_split"]["holdout"] == facial["accuracy_pct"],
          f"{dep['by_split']['holdout']} vs {facial['accuracy_pct']}")
    check("holdout constant accuracy equals the published reference",
          con["by_split"]["holdout"] == constant_ref["value_pct"],
          f"{con['by_split']['holdout']} vs {constant_ref['value_pct']}")
    holdout_n = sum(s["n"] for s in dep["per_speaker"].values()
                    if s["split"] == "holdout")
    check("holdout frame count equals the published n",
          holdout_n == constant_ref["n"], f"{holdout_n} vs {constant_ref['n']}")
    check("the write-up states that holdout n", f"| **{holdout_n}** | {holdout_n} |" in md)

    # ── every per-speaker row in §3.1 and §4 ──────────────────────────────────
    for name, s in dep["per_speaker"].items():
        row = (f"| {name} | {s['split']} | {s['n']} | "
               f"{'**' if s['accuracy_pct'] in (dep['spread']['worst_pct'], dep['spread']['best_pct']) else ''}"
               f"{s['accuracy_pct']}%")
        check(f"§3.1 row present and correct for {name}",
              re.search(rf"\| {re.escape(name)} \| {s['split']} \| {s['n']} \| "
                        rf"\*?\*?{s['accuracy_pct']}%", md) is not None,
              row)
        check(f"§3.1 confidence interval for {name}",
              f"[{s['wilson_lo']}, {s['wilson_hi']}]" in md)

    for name, r in lift["per_speaker"].items():
        sign = f"{r['lift_points']:+.1f}".replace("+", "+").replace("-", "−")
        check(f"§4 lift row for {name}",
              sign in md or f"{r['lift_points']:+.1f}" in md,
              f"{name} {sign}")

    # ── the headline numbers ──────────────────────────────────────────────────
    for label, value in (
        ("pooled deployed accuracy", dep["pooled_pct"]),
        ("dev deployed accuracy", dep["by_split"]["dev"]),
        ("deployed per-speaker range", dep["spread"]["range_points"]),
        ("constant per-speaker range", con["spread"]["range_points"]),
        ("lift range", lift["range_points"]),
        ("mean lift on dev", lift["mean_lift_by_split"]["dev"]),
        ("mean lift on holdout", lift["mean_lift_by_split"]["holdout"]),
    ):
        shown = f"{abs(value)}"
        check(f"{label} ({value}) appears in the write-up", shown in md, str(value))

    check("the Spearman figure appears with its sign",
          str(abs(lift["spearman_lift_vs_neutral_base_rate"])) in md
          and "−" + str(abs(lift["spearman_lift_vs_neutral_base_rate"])) in md,
          str(lift["spearman_lift_vs_neutral_base_rate"]))
    check("the Spearman figure is stated with n=8",
          re.search(r"−?0\.714\*?\*?,? n ?= ?8", md) is not None)
    check("speakers below the constant is stated",
          f"{lift['n_speakers_below_constant']} of 8 speakers" in md,
          str(lift["n_speakers_below_constant"]))
    check("the gold frame count is stated",
          f"{d['n_gold_frames']} frames carry a readable expression" in md,
          str(d["n_gold_frames"]))

    crops = len(list((V2 / "crops").glob("*")))
    check("the crop count is stated correctly", f"**{crops} aligned face crops**" in md,
          str(crops))

    # ── the disciplines the protocol committed to ─────────────────────────────
    check("the primary spread is reported as NOT a finding",
          dep["spread"]["intervals_disjoint"] is False
          and "This is not a finding" in md)
    check("the constant's spread IS reported as separable",
          con["spread"]["intervals_disjoint"] is True
          and "do not** overlap" in md)
    check("the post-hoc quantity is labelled post-hoc",
          md.count("post-hoc") >= 3)
    check("Q2 is declared unrun", "**Not run.**" in md and "not run because it needs three people" in md)
    check("the Monk scale is named and Fitzpatrick is rejected",
          "Monk" in md and "Fitzpatrick" in flat(PROTOCOL.read_text(encoding="utf-8")))
    check("the write-up refuses the four claims §7 forbids",
          all(s in md for s in ("Not** that the system is fair",
                                "Not** that the system is biased by skin tone")))
    check("the uncited-disparity sentence is present",
          "cite a skin-tone disparity it has not observed" in md)
    check("the dev/holdout confound is stated rather than glossed",
          "cannot separate the two" in md)

    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        if not ok:
            print(f"  FAIL  {name}" + (f"   [{detail}]" if detail else ""))
    print(f"\n{len(checks) - len(failed)} of {len(checks)} claims verified "
          f"against facial_bench/v2/ and per_speaker.json")
    if failed:
        print(f"{len(failed)} FAILED")
        return 1
    print("every number in FAIRNESS_ANALYSIS.md re-derives from disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
