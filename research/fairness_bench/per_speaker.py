"""
per_speaker.py — the facial channel's accuracy, cut by speaker.

PROTOCOL.md §3. Answers Q1 only: does accuracy vary between the eight speakers
in the v2 sample? It says nothing about why, because the skin-tone step (§4) has
not been run.

Adds no data. Re-cuts facial_bench/v2's existing result, and reuses that bench's
own ground-truth module rather than re-implementing the mapping or the
abstention rule — two files that claim to measure the same thing and each
implement it separately are two files that will quietly disagree.

    python research/fairness_bench/per_speaker.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V2 = ROOT / "research" / "facial_bench" / "v2"
OUT = HERE / "per_speaker.json"

sys.path.insert(0, str(V2))
import ground_truth_v2 as GT          # noqa: E402  (path set above)

DEPLOYED = "deepface_fer"
CONSTANT = "always-NEUTRAL constant"


def wilson(correct: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval, in percent. PROTOCOL.md §5.2."""
    if n == 0:
        return (0.0, 0.0)
    p = correct / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half) * 100, min(1.0, centre + half) * 100)


def spearman(xs: list[float], ys: list[float]) -> float:
    """Rank correlation, no SciPy. n is tiny here and is always stated with it."""
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            shared = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = shared
            i = j + 1
        return out
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def predictions(model: str) -> dict[str, str | None]:
    """uid -> three-way call, or None where the detector found no crop.

    None is an abstention and PROTOCOL.md §3 scores it wrong, because that is
    what the pipeline gets: no crop, no reading, no channel.
    """
    raw = json.loads((V2 / "predictions" / f"{model}.json").read_text())
    return {row["uid"]: (row["three"] if row["has_crop"] else None)
            for row in raw["rows"]}


def by_speaker(gold_rows: list[dict], calls: dict[str, str | None] | None) -> dict:
    """Group the scored result by speaker. `calls=None` means the constant."""
    out: dict[str, dict] = {}
    for row in gold_rows:
        s = out.setdefault(row["speaker"], {
            "split": row["split"], "n": 0, "correct": 0,
            "n_neutral": 0, "negative_on_neutral": 0, "abstained": 0,
        })
        call = "NEUTRAL" if calls is None else calls.get(row["uid"])
        s["n"] += 1
        if call is None:
            s["abstained"] += 1
        if call == row["three"]:
            s["correct"] += 1
        if row["three"] == "NEUTRAL":
            s["n_neutral"] += 1
            if call == "NEGATIVE":
                s["negative_on_neutral"] += 1
    for s in out.values():
        s["accuracy_pct"] = round(s["correct"] / s["n"] * 100, 1) if s["n"] else None
        lo, hi = wilson(s["correct"], s["n"])
        s["wilson_lo"], s["wilson_hi"] = round(lo, 1), round(hi, 1)
        s["negative_on_neutral_rate_pct"] = (
            round(s["negative_on_neutral"] / s["n_neutral"] * 100, 1)
            if s["n_neutral"] else None)
    return out


def spread(table: dict) -> dict:
    """Best and worst speaker, and whether their intervals stay apart."""
    ranked = sorted(table.items(), key=lambda kv: kv[1]["accuracy_pct"])
    worst_name, worst = ranked[0]
    best_name, best = ranked[-1]
    return {
        "worst": worst_name, "worst_pct": worst["accuracy_pct"],
        "worst_ci": [worst["wilson_lo"], worst["wilson_hi"]],
        "best": best_name, "best_pct": best["accuracy_pct"],
        "best_ci": [best["wilson_lo"], best["wilson_hi"]],
        "range_points": round(best["accuracy_pct"] - worst["accuracy_pct"], 1),
        # PROTOCOL.md §5.3: a spread is only a finding when the intervals part.
        "intervals_disjoint": worst["wilson_hi"] < best["wilson_lo"],
    }


def main() -> int:
    manifest = GT.load_manifest()
    raw = GT.load_raw()
    gold = GT.expression_set(raw=raw, manifest=manifest)   # primary mapping

    results = {
        "generated_by": "fairness_bench/per_speaker.py",
        "protocol": "fairness_bench/PROTOCOL.md",
        "source": "facial_bench/v2 — no new frames, labels or models",
        "seed": manifest["seed"],
        "mapping": "primary (happy/surprised POSITIVE, neutral NEUTRAL, angry/sad NEGATIVE)",
        "abstention": "scored wrong (PROTOCOL.md §3)",
        "n_gold_frames": len(gold),
        "speakers": {},
    }

    calls = predictions(DEPLOYED)
    for label, model_calls in ((DEPLOYED, calls), (CONSTANT, None)):
        table = by_speaker(gold, model_calls)
        pooled_n = sum(s["n"] for s in table.values())
        pooled_c = sum(s["correct"] for s in table.values())
        results["speakers"][label] = {
            "per_speaker": table,
            "pooled_pct": round(pooled_c / pooled_n * 100, 1),
            "pooled_n": pooled_n,
            "spread": spread(table),
            "by_split": {
                split: round(
                    sum(s["correct"] for s in table.values() if s["split"] == split)
                    / max(1, sum(s["n"] for s in table.values() if s["split"] == split))
                    * 100, 1)
                for split in ("dev", "holdout")
            },
        }

    # PROTOCOL.md amendment A1, post-hoc: per-speaker accuracy is dominated by
    # how much a presenter's face moves, which is exactly what the constant
    # measures. The lift separates "hard for everything" from "hard for this
    # model", and only the second is a fairness question.
    model = results["speakers"][DEPLOYED]["per_speaker"]
    const = results["speakers"][CONSTANT]["per_speaker"]
    lift = {
        name: {
            "split": model[name]["split"], "n": model[name]["n"],
            "deployed_pct": model[name]["accuracy_pct"],
            "constant_pct": const[name]["accuracy_pct"],
            "lift_points": round(model[name]["accuracy_pct"]
                                 - const[name]["accuracy_pct"], 1),
        }
        for name in model
    }
    ranked = sorted(lift.values(), key=lambda r: r["lift_points"])
    results["lift_post_hoc"] = {
        "note": "PROTOCOL.md amendment A1 — added after the primary output, "
                "descriptive, not a test",
        "per_speaker": lift,
        "worst_points": ranked[0]["lift_points"],
        "best_points": ranked[-1]["lift_points"],
        "range_points": round(ranked[-1]["lift_points"] - ranked[0]["lift_points"], 1),
        "n_speakers_below_constant": sum(1 for r in lift.values()
                                         if r["lift_points"] < 0),
    }

    # Still descriptive, still A1. The constant's accuracy for a speaker IS
    # that speaker's neutral base rate — how still their face is — so this asks
    # whether the model's disadvantage tracks stillness rather than identity.
    pairs = [(const[n]["accuracy_pct"], lift[n]["lift_points"]) for n in lift]
    results["lift_post_hoc"]["spearman_lift_vs_neutral_base_rate"] = round(
        spearman([a for a, _ in pairs], [b for _, b in pairs]), 3)
    results["lift_post_hoc"]["mean_lift_by_split"] = {
        split: round(sum(r["lift_points"] for r in lift.values()
                         if r["split"] == split)
                     / max(1, sum(1 for r in lift.values() if r["split"] == split)), 1)
        for split in ("dev", "holdout")
    }

    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    for label in (DEPLOYED, CONSTANT):
        block = results["speakers"][label]
        print(f"\n=== {label} — {block['pooled_n']} frames, "
              f"pooled {block['pooled_pct']}% "
              f"(dev {block['by_split']['dev']}%, holdout {block['by_split']['holdout']}%) ===")
        print(f"  {'speaker':<18} {'split':<8} {'n':>4} {'acc':>7}  {'95% CI':>14}  "
              f"{'NEG on neutral':>14}")
        for name, s in sorted(block["per_speaker"].items(),
                              key=lambda kv: kv[1]["accuracy_pct"]):
            ci = f"[{s['wilson_lo']:.1f}, {s['wilson_hi']:.1f}]"
            non = ("—" if s["negative_on_neutral_rate_pct"] is None
                   else f"{s['negative_on_neutral_rate_pct']:.1f}%")
            print(f"  {name:<18} {s['split']:<8} {s['n']:>4} {s['accuracy_pct']:>6.1f}% "
                  f"{ci:>16}  {non:>14}")
        sp = block["spread"]
        print(f"  range {sp['range_points']} points: {sp['worst']} {sp['worst_pct']}% "
              f"{sp['worst_ci']} .. {sp['best']} {sp['best_pct']}% {sp['best_ci']}")
        print(f"  intervals disjoint: {sp['intervals_disjoint']}")

    lp = results["lift_post_hoc"]
    print("\n=== lift: deployed minus always-NEUTRAL, same speaker, same frames ===")
    print("    (post-hoc, PROTOCOL.md amendment A1)")
    print(f"  {'speaker':<18} {'split':<8} {'n':>4} {'deployed':>9} {'constant':>9} "
          f"{'lift':>8}")
    for name, r in sorted(lp["per_speaker"].items(), key=lambda kv: kv[1]["lift_points"]):
        print(f"  {name:<18} {r['split']:<8} {r['n']:>4} {r['deployed_pct']:>8.1f}% "
              f"{r['constant_pct']:>8.1f}% {r['lift_points']:>+7.1f}")
    print(f"  {lp['n_speakers_below_constant']} of {len(lp['per_speaker'])} speakers "
          f"below the constant; lift range {lp['range_points']} points "
          f"({lp['worst_points']:+} to {lp['best_points']:+})")
    print(f"  mean lift by split: dev {lp['mean_lift_by_split']['dev']:+}, "
          f"holdout {lp['mean_lift_by_split']['holdout']:+}")
    print(f"  Spearman(lift, neutral base rate) = "
          f"{lp['spearman_lift_vs_neutral_base_rate']:+.3f}  (n=8, descriptive)")

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
