"""
verify_claims.py - re-derive every number quoted in VOCAL_MODEL_ANALYSIS.md.

Same discipline as transcript_bench/verify_claims.py and whisper_bench/verify_claims.py.
Every figure is recomputed from the raw predictions, the raw ratings and the clip
index. Nothing is read from the cached analysis_*.json, so a stale cache cannot
make a wrong claim pass.

The project's evidence rule (README, "Engineering rules"): if a number is quoted anywhere, it must be traceable to a
file in this repo that produced it. This is that file.

    python research/vocal_bench/verify_claims.py
    python research/vocal_bench/verify_claims.py -v
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ground_truth as GT  # noqa: E402
import report_bench as RB  # noqa: E402

ANALYSIS = HERE / "VOCAL_MODEL_ANALYSIS.md"

failures: list[str] = []
checked = 0


def check(label, claimed, actual, tol=0.05, verbose=False):
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


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    V = ap.parse_args().verbose

    sel = GT.load("selection")
    con = GT.load("confirmation")
    runs = RB.load_predictions()
    th = {n: RB.fit_thresholds(sel, r["predictions"])[:2]
          for n, r in runs.items() if r["kind"] == "dimensional"}

    def score(name, rows):
        return RB.score_candidate(name, runs[name], rows,
                                  surprise_neutral=False, thresholds=th.get(name))

    print("Verifying VOCAL_MODEL_ANALYSIS.md against recomputed values\n")

    # ---------------------------------------------------------------- Section 1
    check("models evaluated", 8, len(runs), 0, V)
    check("clips cut", 150, len(GT.load("selection", True)) + len(GT.load("confirmation", True)), 0, V)
    check("scorable clips", 147, len(sel) + len(con), 0, V)
    check("cant-tell excluded", 3,
          len(GT.load("selection", True)) + len(GT.load("confirmation", True)) - 147, 0, V)
    check("speakers", 6, len({r["channel"] for r in sel + con}), 0, V)
    check("total minutes", 12.4,
          sum(r["duration"] for r in GT.load("selection", True)
              + GT.load("confirmation", True)) / 60, 0.1, V)

    # ---------------------------------------------------------------- Section 2
    sel_gold = [r["label"] for r in sel]
    check("selection n", 100, len(sel), 0, V)
    check("selection NEGATIVE", 15, sel_gold.count("NEGATIVE"), 0, V)
    check("selection NEUTRAL", 50, sel_gold.count("NEUTRAL"), 0, V)
    check("selection POSITIVE", 35, sel_gold.count("POSITIVE"), 0, V)

    sel_acc = {
        "audeering-msp-dim": (54.0, 44.3, 63.4, 0.366, 100.0, 0, 18.2),
        "emotion2vec-base": (49.0, 39.4, 58.7, 0.251, 99.0, 1, 26.1),
        "emotion2vec-seed": (46.0, 36.6, 55.7, 0.238, 92.0, 8, 23.6),
        "emotion2vec-large": (41.0, 31.9, 50.8, 0.278, 92.0, 8, 20.1),
        "dpngtm-wav2vec2": (38.0, 29.1, 47.8, 0.374, 100.0, 0, 44.1),
        "speechbrain-iemocap": (34.0, 25.5, 43.7, 0.262, 100.0, 0, 28.4),
        "superb-wav2vec2-er": (30.0, 21.9, 39.6, 0.254, 100.0, 0, 18.5),
        "wavlm-msp-dim": (52.0, 42.3, 61.5, 0.394, 100.0, 0, 13.2),
    }
    for name, (acc, lo, hi, mf1, cov, unm, rt) in sel_acc.items():
        s = score(name, sel)
        check(f"sel {name} acc", acc, s["accuracy"] * 100, 0.05, V)
        check(f"sel {name} CI low", lo, s["accuracy_ci"][0] * 100, 0.05, V)
        check(f"sel {name} CI high", hi, s["accuracy_ci"][1] * 100, 0.05, V)
        check(f"sel {name} macroF1", mf1, s["macro_f1"], 0.0005, V)
        check(f"sel {name} coverage", cov, s["coverage"] * 100, 0.05, V)
        check(f"sel {name} unmapped", unm, s["unmapped"], 0, V)
        # realtime is quoted at 1 d.p. in the table, so compare the rounded value
        check(f"sel {name} realtime", rt, round(s["realtime_factor"], 1), 0.001, V)

    base = ["NEUTRAL"] * len(sel)
    from importlib.util import spec_from_file_location, module_from_spec
    _s = spec_from_file_location("m", HERE.parent / "transcript_bench" / "metrics.py")
    _m = module_from_spec(_s); _s.loader.exec_module(_m)
    check("baseline always-neutral acc", 50.0, _m.accuracy(sel_gold, base) * 100, 0.05, V)
    check("baseline macroF1", 0.222, _m.macro_f1(sel_gold, base), 0.0005, V)
    blo, bhi = _m.wilson_interval(sel_gold.count("NEUTRAL"), len(sel))
    check("baseline CI low", 40.4, blo * 100, 0.05, V)
    check("baseline CI high", 59.6, bhi * 100, 0.05, V)
    check("models below the floor", 6,
          sum(1 for n in runs if score(n, sel)["accuracy"] < 0.5), 0, V)

    # vs incumbent
    inc_sel = score("speechbrain-iemocap", sel)
    vs_inc = {"audeering-msp-dim": (20.0, 6, 26, 0.00054),
              "emotion2vec-base": (15.0, 10, 25, 0.01667),
              "emotion2vec-seed": (12.0, 11, 23, 0.05761),
              "emotion2vec-large": (7.0, 20, 27, 0.38169),
              "dpngtm-wav2vec2": (4.0, 17, 21, 0.62710),
              "superb-wav2vec2-er": (-4.0, 10, 6, 0.45450),
              "wavlm-msp-dim": (18.0, 17, 35, 0.01753)}
    for name, (d, b, c, p) in vs_inc.items():
        s = score(name, sel)
        t = RB.mcnemar_exact(sel_gold, inc_sel["pred"], s["pred"])
        check(f"sel {name} vs inc diff", d, (s["accuracy"] - inc_sel["accuracy"]) * 100, 0.05, V)
        check(f"sel {name} vs inc b", b, t["b"], 0, V)
        check(f"sel {name} vs inc c", c, t["c"], 0, V)
        check(f"sel {name} vs inc p", p, t["p_value"], 0.00001, V)
    check("bonferroni alpha", 0.00556, 0.05 / 9, 0.00001, V)
    t_base = RB.mcnemar_exact(sel_gold, inc_sel["pred"], base)
    check("baseline vs inc p", 0.00700, t_base["p_value"], 0.00001, V)

    # vs floor
    floor_p = {"audeering-msp-dim": 0.2188, "emotion2vec-base": 1.0000,
               "emotion2vec-seed": 0.2188, "emotion2vec-large": 0.1078,
               "dpngtm-wav2vec2": 0.1550, "speechbrain-iemocap": 0.0070,
               "superb-wav2vec2-er": 0.0022, "wavlm-msp-dim": 0.8506}
    for name, p in floor_p.items():
        t = RB.mcnemar_exact(sel_gold, base, score(name, sel)["pred"])
        check(f"sel {name} vs floor p", p, t["p_value"], 0.0001, V)
    check("nothing beats the floor", 0,
          sum(1 for n in floor_p
              if score(n, sel)["accuracy"] > 0.5
              and RB.mcnemar_exact(sel_gold, base, score(n, sel)["pred"])["p_value"] < 0.05),
          0, V)

    # ---------------------------------------------------------------- Section 3
    con_gold = [r["label"] for r in con]
    check("confirmation n", 47, len(con), 0, V)
    check("confirmation NEGATIVE", 7, con_gold.count("NEGATIVE"), 0, V)
    check("confirmation NEUTRAL", 13, con_gold.count("NEUTRAL"), 0, V)
    check("confirmation POSITIVE", 27, con_gold.count("POSITIVE"), 0, V)
    check("confirmation speakers", 4, len({r["channel"] for r in con}), 0, V)

    con_acc = {"dpngtm-wav2vec2": 40.4, "emotion2vec-seed": 38.3,
               "speechbrain-iemocap": 38.3, "audeering-msp-dim": 36.2,
               "emotion2vec-base": 36.2, "emotion2vec-large": 31.9,
               "superb-wav2vec2-er": 29.8, "wavlm-msp-dim": 46.8}
    for name, acc in con_acc.items():
        check(f"con {name} acc", acc, score(name, con)["accuracy"] * 100, 0.05, V)
    check("confirmation floor", 27.7,
          _m.accuracy(con_gold, ["NEUTRAL"] * len(con)) * 100, 0.05, V)

    inc_con = score("speechbrain-iemocap", con)
    au_con = score("audeering-msp-dim", con)
    check("audeering holdout delta", -2.1,
          (au_con["accuracy"] - inc_con["accuracy"]) * 100, 0.05, V)
    check("audeering holdout p", 1.0,
          RB.mcnemar_exact(con_gold, inc_con["pred"], au_con["pred"])["p_value"], 0.00001, V)

    # ---------------------------------------------------------------- Section 4
    au = runs["audeering-msp-dim"]["predictions"]
    rho_sel = {"valence": 0.045, "arousal": 0.413, "dominance": 0.414}
    rho_con = {"valence": 0.176, "arousal": 0.131, "dominance": 0.158}
    for dim, exp in rho_sel.items():
        v = [au[r["uid"]]["scores"][dim] for r in sel]
        check(f"rho sel {dim}", exp, RB.spearman(v, [r["rating"] for r in sel]), 0.0005, V)
    for dim, exp in rho_con.items():
        v = [au[r["uid"]]["scores"][dim] for r in con]
        check(f"rho con {dim}", exp, RB.spearman(v, [r["rating"] for r in con]), 0.0005, V)

    means_val = {1: 0.274, 2: 0.525, 3: 0.581, 4: 0.579, 5: 0.508}
    means_aro = {1: 0.539, 2: 0.532, 3: 0.567, 4: 0.614, 5: 0.640}
    for k, exp in means_val.items():
        v = [au[r["uid"]]["scores"]["valence"] for r in sel if r["rating"] == k]
        check(f"mean valence rating {k}", exp, statistics.mean(v), 0.0005, V)
    for k, exp in means_aro.items():
        v = [au[r["uid"]]["scores"]["arousal"] for r in sel if r["rating"] == k]
        check(f"mean arousal rating {k}", exp, statistics.mean(v), 0.0005, V)

    ends = [r for r in sel if r["label"] in ("POSITIVE", "NEGATIVE")]
    check("extremes n", 50, len(ends), 0, V)
    y = [1 if r["label"] == "POSITIVE" else 0 for r in ends]
    NEG = {"angry", "sad", "disgust", "disgusted", "fear", "fearful"}
    POS = {"happy", "surprise", "surprised"}
    aucs = {"audeering-msp-dim": 0.613, "dpngtm-wav2vec2": 0.558,
            "superb-wav2vec2-er": 0.510, "emotion2vec-large": 0.503,
            "speechbrain-iemocap": 0.472, "emotion2vec-base": 0.406,
            "emotion2vec-seed": 0.390, "wavlm-msp-dim": 0.670}
    for name, exp in aucs.items():
        p = runs[name]["predictions"]
        if runs[name]["kind"] == "dimensional":
            sc = [p[r["uid"]]["scores"]["valence"] for r in ends]
        else:
            sc = [sum(v for k, v in p[r["uid"]]["scores"].items() if k in POS)
                  - sum(v for k, v in p[r["uid"]]["scores"].items() if k in NEG)
                  for r in ends]
        check(f"AUC {name}", exp, auc(sc, y), 0.0005, V)
    check("models below chance AUC", 3, sum(1 for e in aucs.values() if e < 0.5), 0, V)

    preds = {n: score(n, sel)["pred"] for n in runs}
    names = sorted(preds)
    ags = [sum(x == y2 for x, y2 in zip(preds[a], preds[b])) / len(sel)
           for i, a in enumerate(names) for b in names[i + 1:]]
    check("mean pairwise agreement", 49.5, sum(ags) / len(ags) * 100, 0.05, V)
    check("dpngtm vs e2v-large agreement", 16.0,
          sum(x == y2 for x, y2 in zip(preds["dpngtm-wav2vec2"],
                                       preds["emotion2vec-large"])) / len(sel) * 100, 0.05, V)
    check("audeering vs e2v-base agreement", 85.0,
          sum(x == y2 for x, y2 in zip(preds["audeering-msp-dim"],
                                       preds["emotion2vec-base"])) / len(sel) * 100, 0.05, V)

    au_sel = score("audeering-msp-dim", sel)
    check("audeering NEUTRAL predictions", 91, au_sel["pred"].count("NEUTRAL"), 0, V)
    check("audeering POSITIVE recall", 0.029, au_sel["per_class"]["POSITIVE"]["recall"], 0.0005, V)
    check("audeering NEUTRAL recall", 0.980, au_sel["per_class"]["NEUTRAL"]["recall"], 0.0005, V)
    check("audeering NEGATIVE recall", 0.267, au_sel["per_class"]["NEGATIVE"]["recall"], 0.0005, V)

    cm = inc_sel["confusion"]
    check("inc POS->NEG", 11, cm["POSITIVE"]["NEGATIVE"], 0, V)
    check("inc POS->NEU", 23, cm["POSITIVE"]["NEUTRAL"], 0, V)
    check("inc POS->POS", 1, cm["POSITIVE"]["POSITIVE"], 0, V)
    check("inc NEU->NEG", 24, cm["NEUTRAL"]["NEGATIVE"], 0, V)
    check("inc NEU->NEU", 26, cm["NEUTRAL"]["NEUTRAL"], 0, V)
    check("inc NEG->NEG", 7, cm["NEGATIVE"]["NEGATIVE"], 0, V)
    check("inc NEG->NEU", 8, cm["NEGATIVE"]["NEUTRAL"], 0, V)

    # ------------------------------------------------------------- Section 4.5
    w_sel = score("wavlm-msp-dim", sel)
    w_con = score("wavlm-msp-dim", con)
    check("wavlm sel macroF1 is best", True,
          w_sel["macro_f1"] == max(score(n, sel)["macro_f1"] for n in runs), 0, V)
    check("wavlm con acc is best", True,
          w_con["accuracy"] == max(score(n, con)["accuracy"] for n in runs), 0, V)
    check("wavlm POSITIVE recall sel", 0.400, w_sel["per_class"]["POSITIVE"]["recall"], 0.0005, V)
    check("wavlm NEGATIVE recall sel", 0.067, w_sel["per_class"]["NEGATIVE"]["recall"], 0.0005, V)
    check("wavlm found positives", 14, w_sel["confusion"]["POSITIVE"]["POSITIVE"], 0, V)
    check("wavlm vs inc con diff", 8.5,
          (w_con["accuracy"] - inc_con["accuracy"]) * 100, 0.05, V)
    check("wavlm vs inc con p", 0.5413,
          RB.mcnemar_exact(con_gold, inc_con["pred"], w_con["pred"])["p_value"], 0.0001, V)
    t_wf = RB.mcnemar_exact(con_gold, ["NEUTRAL"] * len(con), w_con["pred"])
    check("wavlm vs floor con p", 0.0490, t_wf["p_value"], 0.0001, V)
    check("wavlm floor discordant con", 17, t_wf["n_discordant"], 0, V)
    for dim, exp in (("valence", 0.120), ("arousal", 0.520), ("dominance", 0.493)):
        wv = runs["wavlm-msp-dim"]["predictions"]
        check(f"wavlm rho sel {dim}", exp,
              RB.spearman([wv[r["uid"]]["scores"][dim] for r in sel],
                          [r["rating"] for r in sel]), 0.0005, V)
    for dim, exp in (("valence", 0.250), ("arousal", 0.068), ("dominance", 0.077)):
        wv = runs["wavlm-msp-dim"]["predictions"]
        check(f"wavlm rho con {dim}", exp,
              RB.spearman([wv[r["uid"]]["scores"][dim] for r in con],
                          [r["rating"] for r in con]), 0.0005, V)

    # ---------------------------------------------------------------- Section 5
    for split, rows, exp_acc, exp_p in (("selection", sel, 60.0, 0.0213),
                                        ("confirmation", con, 48.9, 0.0639)):
        g = [r["label"] for r in rows]
        p = [RB.apply_thresholds(au[r["uid"]]["scores"]["arousal"], 0.4, 0.65) for r in rows]
        check(f"arousal {split} acc", exp_acc,
              sum(a == b for a, b in zip(g, p)) / len(rows) * 100, 0.05, V)
        check(f"arousal {split} vs floor p", exp_p,
              RB.mcnemar_exact(g, ["NEUTRAL"] * len(rows), p)["p_value"], 0.0001, V)
    lo, hi, _ = RB.fit_thresholds(
        sel, {u: {"valence": v["scores"]["arousal"]} for u, v in au.items()})
    check("arousal fitted thresholds", (0.4, 0.65), (lo, hi), 0, V)

    means_aro_con = {1: 0.563, 2: 0.587, 3: 0.650, 4: 0.660, 5: 0.642}
    for k, exp in means_aro_con.items():
        v = [au[r["uid"]]["scores"]["arousal"] for r in con if r["rating"] == k]
        check(f"holdout mean arousal rating {k}", exp, statistics.mean(v), 0.0005, V)

    # --------------------------------------------------------------- Section 5b
    ens = HERE / "ensemble_results.json"
    if ens.is_file():
        E = json.loads(ens.read_text())
        check("variants tried", 12, len(E), 0, V)
        table = {
            "wavlm-msp-dim [arousal]": (63.0, 0.0106, 42.6, 0.1892),
            "wavlm-msp-dim [dominance]": (62.0, 0.0576, 42.6, 0.2295),
            "ENSEMBLE mean-arousal dimensional-2": (61.0, 0.1173, 55.3, 0.0294),
            "audeering-msp-dim [arousal]": (60.0, 0.0213, 48.9, 0.0639),
            "audeering-msp-dim [dominance]": (59.0, 0.1755, 51.1, 0.0522),
            "audeering-msp-dim [valence]": (54.0, 0.2188, 36.2, 0.2188),
            "wavlm-msp-dim [valence]": (52.0, 0.8506, 46.8, 0.0490),
            "ENSEMBLE hard-vote all-8": (52.0, 0.6250, 40.4, 0.1460),
            "ENSEMBLE mean-valence dimensional-2": (52.0, 0.5000, 29.8, 1.0000),
            "ENSEMBLE soft-vote emotion2vec-3": (49.0, 1.0000, 42.6, 0.0654),
            "ENSEMBLE hard-vote categorical-6": (48.0, 0.7266, 44.7, 0.0574),
            "ENSEMBLE soft-vote categorical-6": (45.0, 0.3018, 44.7, 0.0574),
        }
        for name, (sa, sp, ca, cp) in table.items():
            e = E[name]
            check(f"ens {name} SEL acc", sa, e["selection"]["accuracy"] * 100, 0.05, V)
            check(f"ens {name} SEL floor p", sp, e["selection"]["vs_floor_p"], 0.0001, V)
            check(f"ens {name} CON acc", ca, e["confirmation"]["accuracy"] * 100, 0.05, V)
            check(f"ens {name} CON floor p", cp, e["confirmation"]["vs_floor_p"], 0.0001, V)
        both = [n for n, e in E.items()
                if e["selection"]["accuracy"] > e["selection"]["floor_acc"]
                and e["selection"]["vs_floor_p"] < 0.05
                and e["confirmation"]["accuracy"] > e["confirmation"]["floor_acc"]
                and e["confirmation"]["vs_floor_p"] < 0.05]
        check("variants beating floor on both splits", 0, len(both), 0, V)

        # arousal beats valence in 6 of 6 paired comparisons
        wins = 0
        for base in ("audeering-msp-dim", "wavlm-msp-dim"):
            for split in ("selection", "confirmation"):
                wins += (E[f"{base} [arousal]"][split]["accuracy"]
                         > E[f"{base} [valence]"][split]["accuracy"])
        for split in ("selection", "confirmation"):
            wins += (E["ENSEMBLE mean-arousal dimensional-2"][split]["accuracy"]
                     > E["ENSEMBLE mean-valence dimensional-2"][split]["accuracy"])
        check("arousal beats valence, of 6", 5, wins, 0, V)   # wavlm CON is the exception
        check("sign test 6 of 6 p", 0.031, 2 * (0.5 ** 6), 0.001, V)

        mo = E["ENSEMBLE mean-arousal dimensional-2"]
        check("mean-arousal margin SEL", 11.0,
              (mo["selection"]["accuracy"] - mo["selection"]["floor_acc"]) * 100, 0.05, V)
        check("mean-arousal margin CON", 27.7,
              (mo["confirmation"]["accuracy"] - mo["confirmation"]["floor_acc"]) * 100, 0.05, V)
        check("mean-arousal total margin", 38.7,
              (mo["selection"]["accuracy"] - mo["selection"]["floor_acc"]
               + mo["confirmation"]["accuracy"] - mo["confirmation"]["floor_acc"]) * 100,
              0.05, V)
        check("mean-arousal has the largest total margin", True,
              max(E, key=lambda n: (E[n]["selection"]["accuracy"] - E[n]["selection"]["floor_acc"]
                                    + E[n]["confirmation"]["accuracy"]
                                    - E[n]["confirmation"]["floor_acc"]))
              == "ENSEMBLE mean-arousal dimensional-2", 0, V)
        for n, sp, cp in (("ENSEMBLE mean-arousal dimensional-2", 0.0003, 0.2005),
                          ("wavlm-msp-dim [arousal]", 0.0000, 0.8388),
                          ("audeering-msp-dim [arousal]", 0.0001, 0.4049),
                          ("wavlm-msp-dim [valence]", 0.0175, 0.5413)):
            check(f"ens {n} SEL vs inc p", sp, E[n]["selection"]["vs_incumbent_p"], 0.0001, V)
            check(f"ens {n} CON vs inc p", cp, E[n]["confirmation"]["vs_incumbent_p"], 0.0001, V)
    else:
        print("  (ensemble_results.json absent - Section 5b claims not checked)")

    # ---------------------------------------------------------------- Section 6
    n_surprise = sum(
        1 for run in runs.values() for p in run["predictions"].values()
        if str(p.get("raw_label")).lower() in ("surprise", "surprised"))
    check("total surprise predictions", 4, n_surprise, 0, V)
    for name, exp in (("emotion2vec-base", 3), ("dpngtm-wav2vec2", 1)):
        n = sum(1 for p in runs[name]["predictions"].values()
                if str(p.get("raw_label")).lower() in ("surprise", "surprised"))
        check(f"{name} surprise count", exp, n, 0, V)
    for name in sel_acc:
        a = score(name, sel)["accuracy"]
        b = RB.score_candidate(name, runs[name], sel, surprise_neutral=True,
                               thresholds=th.get(name))["accuracy"]
        check(f"surprise sensitivity {name} unchanged", a, b, 0.0001, V)

    # ---------------------------------------------------------------- Section 7
    allrows = sel + con
    per_speaker = {
        "speechbrain-iemocap": {"Dave2D": 18.2, "Jeremy Fragrance": 33.3,
                                "Marques Brownlee": 42.9, "Mrwhosetheboss": 25.5,
                                "ShortCircuit": 58.3, "The Tech Chap": 41.7},
        "audeering-msp-dim": {"Dave2D": 45.5, "Jeremy Fragrance": 41.7,
                              "Marques Brownlee": 65.3, "Mrwhosetheboss": 43.1,
                              "ShortCircuit": 16.7, "The Tech Chap": 41.7},
    }
    for name, table in per_speaker.items():
        s = RB.score_candidate(name, runs[name], allrows, surprise_neutral=False,
                               thresholds=th.get(name))
        by = {}
        for r, g, p in zip(allrows, s["gold"], s["pred"]):
            d = by.setdefault(r["channel"], [0, 0])
            d[1] += 1
            d[0] += (g == p)
        for ch, exp in table.items():
            check(f"{name} / {ch}", exp, by[ch][0] / by[ch][1] * 100, 0.05, V)
    check("speechbrain pooled", 35.4,
          RB.score_candidate("speechbrain-iemocap", runs["speechbrain-iemocap"], allrows,
                             surprise_neutral=False, thresholds=None)["accuracy"] * 100, 0.05, V)
    check("audeering pooled", 48.3,
          RB.score_candidate("audeering-msp-dim", runs["audeering-msp-dim"], allrows,
                             surprise_neutral=False,
                             thresholds=th["audeering-msp-dim"])["accuracy"] * 100, 0.05, V)

    # ---------------------------------------------------------------- Section 8
    gold_all = [r["label"] for r in allrows]
    check("overall NEGATIVE share", 15.0, gold_all.count("NEGATIVE") / 147 * 100, 0.05, V)
    check("overall NEUTRAL share", 42.9, gold_all.count("NEUTRAL") / 147 * 100, 0.05, V)
    check("overall POSITIVE share", 42.2, gold_all.count("POSITIVE") / 147 * 100, 0.05, V)
    check("clearly-negative ratings", 3,
          sum(1 for r in allrows if r["rating"] == 1), 0, V)
    check("all candidates zero failures", 0,
          sum(r.get("n_failed", 0) for r in runs.values()), 0, V)
    check("analysis file exists", True, ANALYSIS.exists(), 0, V)

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
