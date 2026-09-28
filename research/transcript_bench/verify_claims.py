"""
verify_claims.py - check every numeric claim in the bench write-ups against source data.

The project's evidence rule (README, "Engineering rules") requires that any number quoted anywhere is traceable to a file in
this repo that produced it. This script is that trace. It re-derives each figure printed
in TRANSCRIPT_MODEL_ANALYSIS.md and WINNER.md from predictions/ and the label sheet, and
fails loudly on any mismatch.

Run it after editing either document.

    python research/transcript_bench/verify_claims.py
"""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR))

import metrics                                   # noqa: E402
import report_bench as RB                        # noqa: E402
from ground_truth import load                    # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def chk(desc: str, got, want, tol: float = 0.0015) -> None:
    global CHECKS
    CHECKS += 1
    ok = abs(got - want) <= tol if isinstance(want, float) else got == want
    if not ok:
        FAILURES.append(f"{desc}: got {got!r}, document says {want!r}")


def preds(cid: str, split: str, rows: list[dict]) -> list[str]:
    record = json.loads((BENCH_DIR / "predictions" / f"{cid}__{split}.json").read_text())
    mapping = {p["segment_uid"]: p["label"] for p in record["predictions"]}
    return [mapping[r["segment_uid"]] for r in rows]


def main() -> int:
    sel, con = load("selection"), load("confirmation")
    gsel = [r["gold"] for r in sel]
    gcon = [r["gold"] for r in con]

    # --- sheet integrity ---
    sheet = list(csv.DictReader(
        (BENCH_DIR / "labels" / "transcript_label_sheet.csv").open(encoding="utf-8")))
    chk("sheet rows", len(sheet), 599)
    chk("blank labels", sum(
        1 for r in sheet if not r["label_POSITIVE_NEUTRAL_NEGATIVE"].strip()), 0)
    chk("unique uids", len(set(r["segment_uid"] for r in sheet)), 599)

    # --- class distributions ---
    cs, cc = collections.Counter(gsel), collections.Counter(gcon)
    chk("selection n", len(sel), 400)
    chk("confirmation n", len(con), 199)
    for lab, pct in [("POSITIVE", 38.8), ("NEUTRAL", 39.0), ("NEGATIVE", 22.2)]:
        chk(f"sel {lab}%", 100 * cs[lab] / 400, pct, 0.06)
    for lab, pct in [("POSITIVE", 32.2), ("NEUTRAL", 48.2), ("NEGATIVE", 19.6)]:
        chk(f"con {lab}%", 100 * cc[lab] / 199, pct, 0.06)
    chk("sel NEUTRAL count", cs["NEUTRAL"], 156)
    chk("con NEUTRAL count", cc["NEUTRAL"], 96)
    chk("majority baseline sel", cs["NEUTRAL"] / 400, 0.390)
    chk("majority baseline con", cc["NEUTRAL"] / 199, 0.482)

    bysp = collections.defaultdict(collections.Counter)
    for r in sel:
        bysp[r["channel"]][r["gold"]] += 1
    chk("MKBHD NEUTRAL%", 100 * bysp["Marques Brownlee"]["NEUTRAL"] / 200, 40.5, 0.06)
    chk("Mrwhosetheboss NEUTRAL%", 100 * bysp["Mrwhosetheboss"]["NEUTRAL"] / 200, 37.5, 0.06)

    # --- headline table: NEUT-R, NEUT-P, accuracy, macro-F1 for all 15 ---
    TABLE = {
        "1.3_jhartmann_large":     (0.897, 0.484, 0.568, 0.533),
        "1.5_cardiffnlp_xlm":      (0.795, 0.574, 0.647, 0.633),
        "1.4_bertweet":            (0.776, 0.528, 0.615, 0.588),
        "1.1_cardiffnlp_latest":   (0.769, 0.541, 0.623, 0.600),
        "1.2_cardiffnlp_original": (0.724, 0.543, 0.625, 0.597),
        "4.1_deberta_zeroshot":    (0.712, 0.526, 0.598, 0.592),
        "6.1_comment_ft":          (0.558, 0.696, 0.657, 0.650),
        "0.3_vader":               (0.468, 0.514, 0.507, 0.483),
        "2.1_nlptown_stars":       (0.436, 0.453, 0.492, 0.476),
        "4.2_bart_mnli":           (0.417, 0.575, 0.603, 0.581),
        "5.2_gemma3_4b":           (0.372, 0.598, 0.608, 0.601),
        "5.1_llama32":             (0.276, 0.512, 0.557, 0.543),
        "1.6_lxyuan_distil":       (0.109, 0.354, 0.425, 0.384),
        "0.1_sst2_incumbent":      (0.045, 0.538, 0.463, 0.401),
        "3.1_siebert_control":     (0.000, 0.000, 0.512, 0.418),
    }
    for cid, (nr, npr, acc, mf1) in TABLE.items():
        s = metrics.summarise(gsel, preds(cid, "selection", sel))
        chk(f"{cid} NEUT-R", s["neutral_recall"], nr)
        chk(f"{cid} NEUT-P", s["per_class"]["NEUTRAL"]["precision"], npr)
        chk(f"{cid} accuracy", s["accuracy"], acc)
        chk(f"{cid} macro-F1", s["macro_f1"], mf1)

    # --- p-values quoted in the table ---
    results = {r["id"]: r for r in
               json.loads((BENCH_DIR / "results_selection.json").read_text())["results"]}
    PVALS = {
        "1.3_jhartmann_large": 0.0083, "1.5_cardiffnlp_xlm": 1e-5,
        "1.4_bertweet": 1e-4, "1.1_cardiffnlp_latest": 1e-4,
        "1.2_cardiffnlp_original": 1e-5, "4.1_deberta_zeroshot": 0.0002,
        "6.1_comment_ft": 1e-5, "0.3_vader": 0.197, "2.1_nlptown_stars": 0.390,
        "4.2_bart_mnli": 1e-4, "5.2_gemma3_4b": 1e-5, "5.1_llama32": 0.0008,
        "1.6_lxyuan_distil": 0.188, "3.1_siebert_control": 0.021,
    }
    for cid, claimed in PVALS.items():
        actual = results[cid]["mcnemar_vs_incumbent"]["p_value"]
        global CHECKS
        CHECKS += 1
        ok = actual < claimed if claimed in (1e-5, 1e-4) else abs(actual - claimed) <= 0.0006
        if not ok:
            FAILURES.append(f"{cid} p-value: got {actual:.6g}, document says {claimed}")

    alpha = 0.05 / 15
    n_sig = sum(1 for c, r in results.items()
                if c != "0.1_sst2_incumbent"
                and r["mcnemar_vs_incumbent"]["p_value"] < alpha)
    chk("Bonferroni alpha", round(alpha, 4), 0.0033)
    chk("challengers significant at Bonferroni", n_sig, 9)

    # --- winner detail, selection ---
    w = preds("1.5_cardiffnlp_xlm", "selection", sel)
    sw = metrics.summarise(gsel, w)
    chk("win CI lo", sw["accuracy_ci95"][0], 0.599)
    chk("win CI hi", sw["accuracy_ci95"][1], 0.693)
    chk("win NEUTRAL predicted", sw["neutral_predicted"], 216)
    chk("win over-prediction 1.38x", round(216 / 156, 2), 1.38)
    chk("win NEGATIVE recall", sw["per_class"]["NEGATIVE"]["recall"], 0.494)
    chk("win POSITIVE recall", sw["per_class"]["POSITIVE"]["recall"], 0.587)
    cm = metrics.confusion_matrix(gsel, w)
    for true_lab, pred_lab, v in [
        ("POSITIVE", "POSITIVE", 91), ("POSITIVE", "NEUTRAL", 54), ("POSITIVE", "NEGATIVE", 10),
        ("NEUTRAL", "POSITIVE", 17), ("NEUTRAL", "NEUTRAL", 124), ("NEUTRAL", "NEGATIVE", 15),
        ("NEGATIVE", "POSITIVE", 7), ("NEGATIVE", "NEUTRAL", 38), ("NEGATIVE", "NEGATIVE", 44),
    ]:
        chk(f"sel confusion[{true_lab}][{pred_lab}]", cm[true_lab][pred_lab], v)

    i = preds("0.1_sst2_incumbent", "selection", sel)
    si = metrics.summarise(gsel, i)
    chk("inc CI lo", si["accuracy_ci95"][0], 0.414)
    chk("inc CI hi", si["accuracy_ci95"][1], 0.511)
    chk("inc NEUTRAL predicted", si["neutral_predicted"], 13)
    chk("inc NEUTRAL correct", metrics.confusion_matrix(gsel, i)["NEUTRAL"]["NEUTRAL"], 7)
    chk("inc NEUTRAL share 3.2%", round(100 * 13 / 400, 1), 3.2)
    chk("NEUTRAL recall ratio 17.7x", round(0.795 / 0.045, 1), 17.7)

    mcw = metrics.mcnemar_exact(gsel, w, i)
    chk("sel McNemar b", mcw["b"], 136)
    chk("sel McNemar c", mcw["c"], 62)

    # --- over-prediction ratios ---
    for cid, n in [("1.3_jhartmann_large", 289), ("6.1_comment_ft", 125),
                   ("1.1_cardiffnlp_latest", 222)]:
        chk(f"{cid} NEUTRAL predicted",
            collections.Counter(preds(cid, "selection", sel))["NEUTRAL"], n)
    chk("j-hartmann 1.85x", round(289 / 156, 2), 1.85)

    # --- degenerate baseline ---
    deg = metrics.summarise(gsel, ["NEUTRAL"] * 400)
    chk("degenerate NEUT-R", deg["neutral_recall"], 1.0)
    chk("degenerate accuracy", deg["accuracy"], 0.390)
    chk("degenerate macro-F1", deg["macro_f1"], 0.187)

    # --- head-to-head ---
    chk("j-hartmann vs xlm p",
        metrics.mcnemar_exact(gsel, preds("1.3_jhartmann_large", "selection", sel), w)["p_value"],
        0.0013, 0.0002)
    chk("xlm vs comment-ft p",
        metrics.mcnemar_exact(gsel, w, preds("6.1_comment_ft", "selection", sel))["p_value"],
        0.7789, 0.001)
    chk("xlm vs cardiff-latest p",
        metrics.mcnemar_exact(gsel, w, preds("1.1_cardiffnlp_latest", "selection", sel))["p_value"],
        0.3203, 0.001)

    # --- siebert control ---
    sb = preds("3.1_siebert_control", "selection", sel)
    chk("siebert NEUTRAL predicted", collections.Counter(sb)["NEUTRAL"], 3)
    chk("siebert NEUTRAL correct", metrics.confusion_matrix(gsel, sb)["NEUTRAL"]["NEUTRAL"], 0)
    sbr = json.loads(
        (BENCH_DIR / "predictions" / "3.1_siebert_control__selection.json").read_text())
    chk("siebert min winning confidence",
        min(max(p["scores"].values()) for p in sbr["predictions"]), 0.5154, 0.0002)

    # --- confirmation set ---
    wc = preds("1.5_cardiffnlp_xlm", "confirmation", con)
    ic = preds("0.1_sst2_incumbent", "confirmation", con)
    swc, sic = metrics.summarise(gcon, wc), metrics.summarise(gcon, ic)
    chk("con win NEUT-R", swc["neutral_recall"], 0.740)
    chk("con inc NEUT-R", sic["neutral_recall"], 0.073)
    chk("con win accuracy", swc["accuracy"], 0.678)
    chk("con inc accuracy", sic["accuracy"], 0.382)
    chk("con win macro-F1", swc["macro_f1"], 0.662)
    chk("con inc macro-F1", sic["macro_f1"], 0.360)
    chk("con win CI lo", swc["accuracy_ci95"][0], 0.611)
    chk("con win CI hi", swc["accuracy_ci95"][1], 0.739)
    chk("con inc CI lo", sic["accuracy_ci95"][0], 0.317)
    chk("con inc CI hi", sic["accuracy_ci95"][1], 0.451)
    chk("con win NEGATIVE recall", swc["per_class"]["NEGATIVE"]["recall"], 0.667)
    chk("con win POSITIVE recall", swc["per_class"]["POSITIVE"]["recall"], 0.594)
    mcc = metrics.mcnemar_exact(gcon, wc, ic)
    chk("con McNemar b", mcc["b"], 76)
    chk("con McNemar c", mcc["c"], 17)
    chk("con McNemar discordant", mcc["n_discordant"], 93)
    chk("con NEUT-R ratio 10.1x", round(0.740 / 0.073, 1), 10.1)

    byspc = collections.defaultdict(list)
    for idx, r in enumerate(con):
        byspc[r["channel"]].append(idx)
    for ch, (ia, wa, inr, wnr) in {
        "Dave2D": (0.500, 0.760, 0.000, 0.647),
        "Jeremy Fragrance": (0.388, 0.735, 0.097, 0.742),
        "ShortCircuit": (0.340, 0.560, 0.150, 0.750),
        "The Tech Chap": (0.300, 0.660, 0.036, 0.786),
    }.items():
        ix = byspc[ch]
        g = [gcon[k] for k in ix]
        chk(f"{ch} inc accuracy", metrics.accuracy(g, [ic[k] for k in ix]), ia)
        chk(f"{ch} win accuracy", metrics.accuracy(g, [wc[k] for k in ix]), wa)
        chk(f"{ch} inc NEUT-R",
            metrics.per_class_prf(g, [ic[k] for k in ix])["NEUTRAL"]["recall"], inr)
        chk(f"{ch} win NEUT-R",
            metrics.per_class_prf(g, [wc[k] for k in ix])["NEUTRAL"]["recall"], wnr)

    # --- cost and parse integrity ---
    for cid, secs in [("5.1_llama32", 0.636), ("5.2_gemma3_4b", 0.842)]:
        rec = json.loads((BENCH_DIR / "predictions" / f"{cid}__selection.json").read_text())
        chk(f"{cid} parse failures", sum(p["parse_failed"] for p in rec["predictions"]), 0)
        chk(f"{cid} distinct replies", len(set(p["raw_reply"] for p in rec["predictions"])), 3)
        chk(f"{cid} s/segment", rec["seconds_per_row"], secs, 0.0006)
    for cid, secs in [("1.5_cardiffnlp_xlm", 0.025), ("0.1_sst2_incumbent", 0.027),
                      ("4.1_deberta_zeroshot", 0.130), ("4.2_bart_mnli", 0.171),
                      ("6.1_comment_ft", 0.017), ("1.3_jhartmann_large", 0.039),
                      ("1.4_bertweet", 0.022), ("1.1_cardiffnlp_latest", 0.031),
                      ("1.2_cardiffnlp_original", 0.021), ("2.1_nlptown_stars", 0.020),
                      ("3.1_siebert_control", 0.035), ("1.6_lxyuan_distil", 0.019)]:
        rec = json.loads((BENCH_DIR / "predictions" / f"{cid}__selection.json").read_text())
        chk(f"{cid} s/segment", rec["seconds_per_row"], secs, 0.0006)

    # --- threshold sweep ---
    inc_rec = json.loads(
        (BENCH_DIR / "predictions" / "0.1_sst2_incumbent__selection.json").read_text())
    sweep = {r["threshold"]: r for r in RB.threshold_sweep(inc_rec)}
    for th, (npd, nr, npr, acc, mf1) in {
        0.50: (0, 0.000, 0.000, 0.450, 0.369), 0.65: (7, 0.013, 0.286, 0.450, 0.378),
        0.70: (13, 0.045, 0.538, 0.463, 0.401), 0.80: (25, 0.058, 0.360, 0.453, 0.400),
        0.90: (44, 0.115, 0.409, 0.460, 0.426), 0.95: (65, 0.167, 0.400, 0.460, 0.439),
        0.99: (155, 0.500, 0.503, 0.535, 0.535),
    }.items():
        chk(f"sweep {th} NEUTRAL predicted", sweep[th]["neutral_predicted"], npd)
        chk(f"sweep {th} NEUT-R", sweep[th]["neutral_recall"], nr)
        chk(f"sweep {th} NEUT-P", sweep[th]["neutral_precision"], npr)
        chk(f"sweep {th} accuracy", sweep[th]["accuracy"], acc)
        chk(f"sweep {th} macro-F1", sweep[th]["macro_f1"], mf1)

    print(f"checked {CHECKS} numeric claims against source data")
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all verified - 0 failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
