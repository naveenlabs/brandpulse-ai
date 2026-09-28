"""
verify_claims.py - re-derive every number quoted in WHISPER_MODEL_ANALYSIS.md.

Same discipline as transcript_bench/verify_claims.py. Each claim below is stated
as it appears in the write-up and is checked against a value recomputed from the
raw transcripts, the ground truth and the clip index. Nothing is read from the
cached analysis JSON, so a stale cache cannot make a wrong claim pass.

The project's evidence rule (README, "Engineering rules"): if a number is quoted anywhere, it must be traceable to a
file in this repo that produced it. This is that file.

    python verify_claims.py          # check all claims
    python verify_claims.py -v       # list every claim as it is checked
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from brand_terms import BRAND_TERMS, count_term  # noqa: E402
from report_whisper import (  # noqa: E402
    load_clip_index, load_ground_truth, load_transcripts,
    score_model, paired_bootstrap, per_speaker_wer, apply_decision_rule,
)
from wer import normalise  # noqa: E402

ANALYSIS = HERE / "WHISPER_MODEL_ANALYSIS.md"

failures: list[str] = []
checked = 0


def check(label: str, claimed, actual, tol=0.005, verbose=False):
    """Compare a claimed figure against a recomputed one."""
    global checked
    checked += 1
    if isinstance(claimed, (int, float)) and isinstance(actual, (int, float)):
        ok = abs(claimed - actual) <= tol
    else:
        ok = claimed == actual
    if not ok:
        failures.append(f"{label}: document says {claimed!r}, recomputed {actual!r}")
    elif verbose:
        print(f"  ok  {label}: {claimed}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    V = args.verbose

    clips = load_clip_index()
    ids = [c["video_id"] for c in clips]
    truth = load_ground_truth(ids)
    runs = load_transcripts()
    scores = {m: score_model(runs[m], truth, ids) for m in runs}

    print("Verifying WHISPER_MODEL_ANALYSIS.md against recomputed values\n")

    # ---------------------------------------------------------------- Section 1
    check("checkpoints evaluated", 12, len(runs), 0, V)
    check("clips", 12, len(ids), 0, V)
    check("duration minutes", 8.72, sum(c["duration_s"] for c in clips) / 60, 0.01, V)
    check("speakers", 6, len({c["channel"] for c in clips}), 0, V)
    check("raw typed words", 1780,
          sum(len(t.split()) for t in truth.values()), 0, V)
    check("normalised reference words", 1887, scores["base"]["ref_words"], 0, V)

    # ---------------------------------------------------------------- Section 2
    table = {
        "large-v3": (1541.6, 1.80, 15, 8, 11, 197, 1.3),
        "large-v3-turbo": (807.0, 1.91, 17, 6, 13, 181, 4.7),
        "medium": (762.3, 2.23, 21, 9, 12, 201, 2.3),
        "large-v2": (1541.4, 2.33, 17, 7, 20, 186, 1.2),
        "large-v1": (1541.4, 2.44, 22, 10, 14, 183, 1.3),
        "medium.en": (762.3, 2.54, 25, 11, 12, 199, 2.3),
        "small": (240.6, 2.60, 29, 7, 13, 183, 6.8),
        "small.en": (240.6, 2.65, 33, 7, 10, 180, 6.7),
        "base.en": (71.8, 3.07, 33, 12, 13, 197, 17.1),
        "base": (71.8, 3.13, 35, 10, 14, 186, 17.2),
        "tiny.en": (37.2, 4.40, 48, 15, 20, 170, 32.9),
        "tiny": (37.2, 4.82, 52, 18, 21, 182, 32.5),
    }
    for m, (params, w, sub, dele, ins, segs, rt) in table.items():
        s = scores[m]
        check(f"{m} params(M)", params, s["parameters_millions"], 0.05, V)
        check(f"{m} WER%", w, s["wer"] * 100, 0.005, V)
        check(f"{m} substitutions", sub, s["substitutions"], 0, V)
        check(f"{m} deletions", dele, s["deletions"], 0, V)
        check(f"{m} insertions", ins, s["insertions"], 0, V)
        check(f"{m} segments", segs, s["n_segments"], 0, V)
        check(f"{m} realtime", rt, s["realtime_factor"], 0.05, V)

    check("WER range low", 1.80, min(s["wer"] for s in scores.values()) * 100, 0.005, V)
    check("WER range high", 4.82, max(s["wer"] for s in scores.values()) * 100, 0.005, V)
    check("base word accuracy%", 96.87, scores["base"]["word_accuracy"] * 100, 0.005, V)
    check("param ratio tiny->large-v3", 41,
          round(scores["large-v3"]["parameters_millions"]
                / scores["tiny"]["parameters_millions"]), 0, V)

    # Pairwise comparisons quoted in Section 2
    pairs = {
        ("base.en", "base"): (-0.05, -1.03, 0.95, 0.9374, 4, 4, 4),
        ("small", "small.en"): (-0.05, -0.64, 0.57, 0.9212, 5, 3, 4),
        ("large-v3", "large-v2"): (-0.53, None, None, 0.2692, 4, 4, 4),
        ("large-v3-turbo", "large-v3"): (0.11, None, None, 0.6994, 3, 4, 5),
    }
    for (a, b), (diff, lo, hi, p, ca, cb, ct) in pairs.items():
        t = paired_bootstrap(scores[a], scores[b], ids)
        check(f"{a} vs {b} diff%", diff, t["observed_diff"] * 100, 0.005, V)
        check(f"{a} vs {b} p", p, t["p_value"], 0.0001, V)
        check(f"{a} vs {b} clips won", (ca, cb, ct),
              (t["clips_a_better"], t["clips_b_better"], t["clips_tied"]), 0, V)
        if lo is not None:
            check(f"{a} vs {b} CI low", lo, t["ci_low"] * 100, 0.005, V)
            check(f"{a} vs {b} CI high", hi, t["ci_high"] * 100, 0.005, V)

    check("large-v3-turbo speed multiple over large-v3", 3.6,
          scores["large-v3-turbo"]["realtime_factor"]
          / scores["large-v3"]["realtime_factor"], 0.05, V)
    check("large-v1 to large-v3 gap", 0.64,
          (scores["large-v1"]["wer"] - scores["large-v3"]["wer"]) * 100, 0.005, V)

    # ---------------------------------------------------------------- Section 3
    speaker_table = {
        "large-v3": {"Dave2D": 0.57, "Jeremy Fragrance": 3.48, "Marques Brownlee": 2.16,
                     "Mrwhosetheboss": 1.32, "ShortCircuit": 1.50, "The Tech Chap": 2.76},
        "large-v3-turbo": {"Dave2D": 0.00, "Jeremy Fragrance": 3.48, "Marques Brownlee": 1.83,
                           "Mrwhosetheboss": 1.62, "ShortCircuit": 2.26, "The Tech Chap": 3.87},
        "small": {"Dave2D": 0.57, "Jeremy Fragrance": 16.52, "Marques Brownlee": 1.99,
                  "Mrwhosetheboss": 1.76, "ShortCircuit": 0.75, "The Tech Chap": 2.21},
        "base": {"Dave2D": 0.57, "Jeremy Fragrance": 14.78, "Marques Brownlee": 2.99,
                 "Mrwhosetheboss": 1.32, "ShortCircuit": 3.76, "The Tech Chap": 4.97},
        "tiny": {"Dave2D": 3.98, "Jeremy Fragrance": 15.65, "Marques Brownlee": 3.65,
                 "Mrwhosetheboss": 2.21, "ShortCircuit": 9.77, "The Tech Chap": 8.84},
    }
    for m, row in speaker_table.items():
        got = per_speaker_wer(scores[m], clips)
        for ch, v in row.items():
            check(f"{m} / {ch} WER%", v, got[ch] * 100, 0.005, V)

    base_sp = per_speaker_wer(scores["base"], clips)
    others = [v for ch, v in base_sp.items() if ch != "Jeremy Fragrance"]
    check("base non-JF speaker range low", 0.57, min(others) * 100, 0.005, V)
    check("base non-JF speaker range high", 4.97, max(others) * 100, 0.005, V)
    check("JF base/large-v3 reduction factor", 4.2,
          base_sp["Jeremy Fragrance"]
          / per_speaker_wer(scores["large-v3"], clips)["Jeremy Fragrance"], 0.05, V)

    # ---------------------------------------------------------------- Section 4
    refw = {c: normalise(truth[c]) for c in ids}
    refc = {t: sum(count_term(w, t) for w in refw.values()) for t in BRAND_TERMS}
    total_terms = sum(refc.values())
    check("brand term occurrences", 30, total_terms, 0, V)
    check("JF share of brand terms", 14,
          sum(count_term(refw["haWvrSliMVY"], t) for t in BRAND_TERMS), 0, V)

    def brand_recall(model, exclude=()):
        keep = [c for c in ids if c not in exclude]
        tot = sum(sum(count_term(refw[c], t) for c in keep) for t in BRAND_TERMS)
        hyp = {c["video_id"]: normalise(c["text"]) for c in runs[model]["clips"]}
        got = sum(min(count_term(hyp[c], t), count_term(refw[c], t))
                  for t in BRAND_TERMS for c in keep)
        return got, tot

    for m, found in [("large-v2", 29), ("large-v3", 29), ("large-v3-turbo", 28),
                     ("large-v1", 27), ("medium", 23), ("medium.en", 22),
                     ("base", 21), ("small", 21), ("small.en", 21),
                     ("base.en", 20), ("tiny.en", 20), ("tiny", 17)]:
        g, t = brand_recall(m)
        check(f"{m} brand found", found, g, 0, V)
        check(f"{m} brand total", 30, t, 0, V)

    check("brand recall spread points", 26.7,
          (brand_recall("large-v3")[0] - brand_recall("base")[0]) / 30 * 100, 0.05, V)
    check("WER spread base->large-v3 points", 1.32,
          (scores["base"]["wer"] - scores["large-v3"]["wer"]) * 100, 0.005, V)

    for m, found in [("large-v3", 15), ("large-v3-turbo", 14), ("medium.en", 16),
                     ("base", 15), ("small", 15), ("tiny", 11)]:
        g, t = brand_recall(m, exclude={"haWvrSliMVY"})
        check(f"{m} brand found excl JF", found, g, 0, V)
        check(f"{m} brand total excl JF", 16, t, 0, V)

    # Sign test on discordant brand occurrences, base vs large-v3
    def discordant(m1, m2):
        b = c = 0
        for cid in ids:
            h1 = normalise(next(x["text"] for x in runs[m1]["clips"] if x["video_id"] == cid))
            h2 = normalise(next(x["text"] for x in runs[m2]["clips"] if x["video_id"] == cid))
            for t in BRAND_TERMS:
                r = count_term(refw[cid], t)
                if not r:
                    continue
                g1, g2 = min(count_term(h1, t), r), min(count_term(h2, t), r)
                if g1 > g2:
                    b += g1 - g2
                elif g2 > g1:
                    c += g2 - g1
        return b, c

    b, c = discordant("base", "large-v3")
    n = b + c
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)
    check("base vs large-v3 brand discordant", (0, 8), (b, c), 0, V)
    check("base vs large-v3 brand sign-test p", 0.0078, p, 0.0001, V)
    check("base vs small brand sign test", (0, 0), discordant("base", "small"), 0, V)

    # ---------------------------------------------------------------- Section 5
    def boundaries(m):
        return {c["video_id"]: [round(s["start"], 2) for s in c["segments"]]
                for c in runs[m]["clips"]}

    base_b = boundaries("base")
    agree_table = {"tiny.en": 79.4, "small.en": 78.3, "large-v1": 78.1, "base.en": 77.7,
                   "small": 76.5, "large-v3-turbo": 75.1, "large-v3": 72.6, "medium": 69.7}
    for m, pct in agree_table.items():
        bd = boundaries(m)
        tot = matched = 0
        for cid in ids:
            for s in bd[cid]:
                tot += 1
                if any(abs(s - t) <= 0.5 for t in base_b[cid]):
                    matched += 1
        check(f"{m} boundary agreement%", pct, matched / tot * 100, 0.05, V)

    check("segment count range low", 170, min(s["n_segments"] for s in scores.values()), 0, V)
    check("segment count range high", 201, max(s["n_segments"] for s in scores.values()), 0, V)
    check("base.en boundary disagreement%", 22.3, 100 - agree_table["base.en"], 0.05, V)
    check("small boundary disagreement%", 23.5, 100 - agree_table["small"], 0.05, V)

    label_sheet = HERE.parent / "transcript_bench" / "labels" / "transcript_label_sheet.csv"
    n_labels = sum(1 for _ in label_sheet.open()) - 1
    check("transcript labels", 599, n_labels, 0, V)

    # Adoption cost, measured after the swap (label_survival.py). Checked against
    # its own output so the document and the script cannot drift apart.
    surv = HERE.parent / "transcript_bench" / "label_survival.json"
    if surv.is_file():
        sv = json.loads(surv.read_text())
        check("survival old model", "base", sv["old_model"], 0, V)
        check("survival new model", "large-v3-turbo", sv["new_model"], 0, V)
        check("survival n labels", 599, sv["n_labels"], 0, V)
        check("Q1 identical", 127, sv["bands"]["identical"], 0, V)
        check("Q1 near", 77, sv["bands"]["near"], 0, V)
        check("Q1 aligned%", 34.1, sv["reusable"] / sv["n_labels"] * 100, 0.05, V)
        check("Q1 moved%", 65.9, sv["rework"] / sv["n_labels"] * 100, 0.05, V)
        check("Q2 intact", 483, sv["content_bands"]["intact"], 0, V)
        check("Q2 mostly", 105, sv["content_bands"]["mostly"], 0, V)
        check("Q2 changed", 11, sv["content_bands"]["changed"], 0, V)
        check("Q2 changed%", 1.8, sv["content_bands"]["changed"] / sv["n_labels"] * 100, 0.05, V)
        check("Q2 surviving%", 98.2,
              (sv["content_bands"]["intact"] + sv["content_bands"]["mostly"])
              / sv["n_labels"] * 100, 0.05, V)
        check("mean word coverage", 0.976, sv["mean_content_coverage"], 0.0005, V)
    else:
        print("  (label_survival.json absent - adoption-cost claims not checked)")

    # ---------------------------------------------------------------- Section 6
    decision = apply_decision_rule(list(scores.values()), ids)
    check("rule best model", "large-v3", decision["best_wer_model"], 0, V)
    check("rule adopts", "small", decision["adopt"], 0, V)
    check("rule qualifier count", 8, len(decision["qualifiers"]), 0, V)
    check("base is not a qualifier", False,
          "base" in [q["model"] for q in decision["qualifiers"]], 0, V)

    t = paired_bootstrap(scores["small"], scores["base"], ids)
    check("small vs base diff%", -0.53, t["observed_diff"] * 100, 0.005, V)
    check("small vs base p", 0.1936, t["p_value"], 0.0001, V)
    check("small vs base CI", (-1.34, 0.21), (round(t["ci_low"] * 100, 2),
                                              round(t["ci_high"] * 100, 2)), 0, V)
    check("small vs base not significant", False, t["significant"], 0, V)
    check("small vs base clips won", (5, 3, 4),
          (t["clips_a_better"], t["clips_b_better"], t["clips_tied"]), 0, V)
    check("small slower than base by", 2.5,
          scores["base"]["realtime_factor"] / scores["small"]["realtime_factor"], 0.05, V)

    better = {}
    for m, s in scores.items():
        if m == "base":
            continue
        tt = paired_bootstrap(s, scores["base"], ids)
        if tt["significant"] and tt["observed_diff"] < 0:
            better[m] = tt["p_value"]
    check("models detectably better than base", {"large-v3", "large-v3-turbo", "medium"},
          set(better), 0, V)
    check("large-v3 vs base p", 0.0244, better["large-v3"], 0.0001, V)
    check("large-v3-turbo vs base p", 0.0212, better["large-v3-turbo"], 0.0001, V)
    check("medium vs base p", 0.0344, better["medium"], 0.0001, V)
    check("fastest detectably-better model", "large-v3-turbo",
          max(better, key=lambda m: scores[m]["realtime_factor"]), 0, V)

    check("base->turbo WER gain points", 1.22,
          (scores["base"]["wer"] - scores["large-v3-turbo"]["wer"]) * 100, 0.005, V)

    # 15-minute video runtime, from measured realtime factors
    for m, mins in [("base", 0.9), ("large-v3-turbo", 3.2), ("large-v3", 11.5)]:
        check(f"{m} minutes for a 15-min video", mins,
              15 / scores[m]["realtime_factor"], 0.05, V)

    # ---------------------------------------------------------------- Section 9
    check("analysis file exists", True, ANALYSIS.exists(), 0, V)

    # ---------------------------------------------------------------- verdict
    print(f"{checked} numeric claims checked")
    if failures:
        print(f"\n{len(failures)} FAILED:\n")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all claims verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
