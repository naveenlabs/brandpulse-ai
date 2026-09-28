"""
analyst/evaluate.py — how well the written report holds up, measured from its own files.

    python evaluation/analyst/evaluate.py                       # every stored analysis
    python evaluation/analyst/evaluate.py --same A.json B.json  # E2: two runs of one report

Writes analyst/ANALYST_EVALUATION.md and analyst/evaluation.json. Reads only
the stored analyses (outputs/analysis/, outputs/sweeps/*/analysis/) and the
reports they were written about; calls no model and changes nothing else.
Those two files are replaced from what is stored when it runs: the recorded
ones (24 Sep 2026, 11 analyses, some since deleted) are not reproducible.

  E1  grounding     Of everything the model proposed, how much passed the checks,
                    per field, and why the rest was dropped.
  E2  determinism   Two runs of the same report with the same prompts: are the
                    claims, topics and prose identical?
  E3  stance        The model's praise/criticism label on each claim against the
                    benched transcript classifier's reading of the same segment
                    (67.8% on held-out speakers), where both are polar. Agreement
                    with a Wilson 95% interval. Not an accuracy: neither side is
                    ground truth. A low figure says the two disagree, not which
                    is wrong.
  E4  cost          Seconds and tokens per call and per report.

The combined report (added 23 Sep 2026), from outputs/sweeps/*/analysis/combined.json:

  C1  grounding     The same as E1, per field of the combined prose and themes.
  C2  themes        How much of the members' topic weight (claims + comments)
                    the model placed in a shared theme, and how many themes
                    three or more videos discuss.
  C4  cost          Seconds and tokens per combined call.
  R1  read twice    Every video that appears in two sweeps on this machine, read
                    twice days apart: how far each lean and each score moved,
                    and whether the calls held. Facts only; no model involved.

What this does NOT measure, stated so it is not mistaken for it: whether the
prose is a fair summary of the video. That needs a person reading the video;
the spot-check sheet (E5, --sheet) is built for that and is not filled in here.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import analyst_facts as F  # noqa: E402
from pipeline import analyst_sweep as W  # noqa: E402
from pipeline import analyst_sweep_facts as SF  # noqa: E402

OUT_MD = Path(__file__).resolve().parent / "ANALYST_EVALUATION.md"
OUT_JSON = Path(__file__).resolve().parent / "evaluation.json"
SHEET = Path(__file__).resolve().parent / "spot_check_sheet.csv"


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def stored() -> list[tuple[Path, Path]]:
    """(analysis, report) pairs for every stored single-video analysis."""
    pairs = []
    for a in sorted((ROOT / "outputs" / "analysis").glob("*.json")):
        pairs.append((a, ROOT / "outputs" / a.name))
    for a in sorted((ROOT / "outputs" / "sweeps").glob("*/analysis/*.json")):
        if a.name == "combined.json":
            continue
        pairs.append((a, a.parent.parent / "members" / a.name))
    return [(a, r) for a, r in pairs if r.is_file()]


def evaluate(pairs) -> dict:
    fields = collections.defaultdict(lambda: {"kept": 0, "dropped": 0})
    reasons = collections.Counter()
    notes = 0
    stance_pairs = []
    calls = []
    reports = []
    for a_path, r_path in pairs:
        a = json.loads(a_path.read_text(encoding="utf-8"))
        r = json.loads(r_path.read_text(encoding="utf-8"))
        v = a.get("verifier") or {}
        for f, row in (v.get("by_field") or {}).items():
            fields[f]["kept"] += row.get("kept", 0)
            fields[f]["dropped"] += row.get("dropped", 0)
        for d in v.get("dropped") or []:
            for reason in d.get("reasons") or []:
                reasons[reason.split(":")[0]] += 1
        notes += len(v.get("notes") or [])
        by_id = {s.get("segment_id"): s for s in r.get("all_segments") or []}
        for c in ((a.get("reading") or {}).get("claims") or []):
            if c["stance"] not in ("praise", "criticism"):
                continue
            val = F.valences(by_id.get(c["seg"], {}), None).get("transcript")
            if val in ("POSITIVE", "NEGATIVE"):
                stance_pairs.append((c["stance"], val))
        for row in a.get("calls") or []:
            calls.append(row)
        reports.append({"file": a_path.name, "status": a.get("status"),
                        "runtime_s": a.get("runtime_s"), "calls": len(a.get("calls") or []),
                        "prompts": a.get("prompt_versions")})
    agree = sum(1 for s, v in stance_pairs
                if (s == "praise" and v == "POSITIVE") or (s == "criticism" and v == "NEGATIVE"))
    ok_calls = [c for c in calls if c.get("ok")]
    per_step = {}
    for step in ("claims", "topics", "comments", "prose"):
        rows = [c for c in ok_calls if c["step"] == step]
        if rows:
            per_step[step] = {
                "n": len(rows),
                "median_s": round(statistics.median(c["seconds"] for c in rows), 1),
                "max_prompt_tokens": max((c.get("prompt_tokens") or 0) for c in rows),
                "max_output_tokens": max((c.get("output_tokens") or 0) for c in rows),
            }
    return {
        "reports": reports,
        "E1": {"fields": dict(fields), "reasons": dict(reasons.most_common()), "corrections": notes},
        "E3": {"n": len(stance_pairs), "agree": agree,
               "rate": (agree / len(stance_pairs)) if stance_pairs else None,
               "ci": wilson(agree, len(stance_pairs))},
        "E4": {"calls": len(calls), "failed": len(calls) - len(ok_calls), "per_step": per_step,
               "runtime_s": [r["runtime_s"] for r in reports]},
    }


def combined_files() -> list[Path]:
    return sorted((ROOT / "outputs" / "sweeps").glob("*/analysis/combined.json"))


def evaluate_combined(paths) -> dict:
    """C1, C2 and C4 over every stored combined report."""
    fields = collections.defaultdict(lambda: {"kept": 0, "dropped": 0})
    reasons = collections.Counter()
    sources = collections.Counter()
    calls, sets = [], []
    for path in paths:
        a = json.loads(path.read_text(encoding="utf-8"))
        v = a.get("verifier") or {}
        for f, row in (v.get("by_field") or {}).items():
            fields[f]["kept"] += row.get("kept", 0)
            fields[f]["dropped"] += row.get("dropped", 0)
        for d in v.get("dropped") or []:
            for reason in d.get("reasons") or []:
                reasons[reason.split(":")[0]] += 1
        for f, item in ((a.get("written") or {}).items()):
            if isinstance(item, dict) and item.get("source"):
                sources[(f, item["source"])] += 1
        calls.extend(a.get("calls") or [])
        reading = a.get("reading") or {}
        weight = reading.get("topic_weight") or {}
        total = (weight.get("placed") or 0) + (weight.get("unplaced") or 0)
        themes = reading.get("themes") or []
        sets.append({"file": path.parent.parent.name, "status": a.get("status"),
                     "runtime_s": a.get("runtime_s"), "theme_source": reading.get("theme_source"),
                     "themes": len(themes),
                     "themes_in_3_or_more": sum(1 for t in themes if t["reviewer"]["talked"] >= 3),
                     "placed_share": (weight.get("placed", 0) / total) if total else None,
                     "unplaced_topics": len(reading.get("unplaced") or []),
                     "members_written": len(reading.get("members_written") or []),
                     "labels": dict(collections.Counter(t["reviewer"]["label"] for t in themes))})
    ok = [c for c in calls if c.get("ok")]
    per_step = {}
    for step in ("themes", "products", "set_prose"):
        rows = [c for c in ok if c["step"] == step]
        if rows:
            per_step[step] = {"n": len(rows), "median_s": round(statistics.median(c["seconds"] for c in rows), 1),
                              "max_prompt_tokens": max((c.get("prompt_tokens") or 0) for c in rows),
                              "max_output_tokens": max((c.get("output_tokens") or 0) for c in rows)}
    return {"sets": sets,
            "C1": {"fields": dict(fields), "reasons": dict(reasons.most_common()),
                   "sources": {f"{f}:{src}": n for (f, src), n in sorted(sources.items())}},
            "C4": {"calls": len(calls), "failed": len(calls) - len(ok), "per_step": per_step}}


def read_twice() -> dict:
    """R1: every video in two sweeps of one subject, read twice. Facts only."""
    sweeps_dir = ROOT / "outputs" / "sweeps"
    loaded = []
    for path in sorted(sweeps_dir.glob("*/sweep.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        sid = path.parent.name
        rows = [SF.video_row(b) for b in W.load_bundles(sid, record, path.parent / "members")]
        loaded.append((sid, " ".join(str(record.get("subject") or "").lower().split()),
                       {r["video_id"]: r for r in rows if r.get("analysed")}))
    out = []
    for i, (sa, subj_a, a) in enumerate(loaded):
        for sb, subj_b, b in loaded[i + 1:]:
            if subj_a != subj_b:
                continue
            for vid in sorted(set(a) & set(b)):
                ra, rb = a[vid], b[vid]
                out.append({
                    "video_id": vid, "sweeps": [sa, sb],
                    "reviewer": [ra["reviewer"]["lean"], rb["reviewer"]["lean"]],
                    "audience": [ra["audience"]["lean"], rb["audience"]["lean"]],
                    "authenticity": [ra["scores"]["authenticity"], rb["scores"]["authenticity"]],
                    "brand_health": [ra["scores"]["brand_health"], rb["scores"]["brand_health"]],
                    "label": [ra["comments"]["label"], rb["comments"]["label"]],
                    "near_tie": [bool((ra.get("near_tie") or {}).get("near_tie")),
                                 bool((rb.get("near_tie") or {}).get("near_tie"))],
                    "calls_same": (ra["reviewer"]["call"] == rb["reviewer"]["call"]
                                   and ra["audience"]["call"] == rb["audience"]["call"])})

    def most(key):
        ds = [abs(r[key][1] - r[key][0]) for r in out if r[key][0] is not None and r[key][1] is not None]
        return max(ds) if ds else None
    return {"n": len(out), "rows": out, "calls_same": sum(1 for r in out if r["calls_same"]),
            "label_changed": sum(1 for r in out if r["label"][0] != r["label"][1]),
            "max_delta": {k: most(k) for k in ("reviewer", "audience", "authenticity", "brand_health")}}


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def same(a_path: Path, b_path: Path) -> dict:
    """E2: are two runs of one report identical where it matters?"""
    a = json.loads(a_path.read_text(encoding="utf-8"))
    b = json.loads(b_path.read_text(encoding="utf-8"))
    out = {"prompts_equal": a.get("prompt_versions") == b.get("prompt_versions"),
           "files": [a_path.name if a_path.name != "combined.json" else f"{a_path.parent.parent.name}/combined.json",
                     b_path.name if b_path.name != "combined.json" else f"{b_path.parent.parent.name}/combined.json"]}
    for part in ("facts", "reading", "written"):
        out[part] = {"a": digest(a.get(part)), "b": digest(b.get(part)),
                     "identical": digest(a.get(part)) == digest(b.get(part))}
    return out


def sheet(pairs, n: int = 40, seed: int = 20260923) -> int:
    """E5: a blind spot-check sheet of n claims, drawn by seed, for a person to judge."""
    rows = []
    for a_path, r_path in pairs:
        a = json.loads(a_path.read_text(encoding="utf-8"))
        r = json.loads(r_path.read_text(encoding="utf-8"))
        by_id = {s.get("segment_id"): s for s in r.get("all_segments") or []}
        for c in ((a.get("reading") or {}).get("claims") or []):
            rows.append((a_path.name, c["time"], (by_id.get(c["seg"]) or {}).get("text", ""),
                         c["claim"], c["stance"]))
    random.Random(seed).shuffle(rows)
    import csv
    with SHEET.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["report", "time", "what was said (the whole segment)", "the model's claim",
                    "the model's stance", "supported? (yes / no / partly)", "stance right? (yes / no)"])
        for row in rows[:n]:
            w.writerow(list(row) + ["", ""])
    return min(n, len(rows))


def markdown(result: dict, e2: dict | None) -> str:
    e1, e3, e4 = result["E1"], result["E3"], result["E4"]
    lines = ["# The written report: evaluation", "",
             f"Generated by `analyst/evaluate.py` from {len(result['reports'])} stored "
             f"{'analysis' if len(result['reports']) == 1 else 'analyses'}. Nothing here is typed by hand.", "",
             "## E1 grounding: what survived the checks", "",
             "| field | kept | dropped | kept share |", "|---|---:|---:|---:|"]
    for f, row in sorted(e1["fields"].items()):
        tot = row["kept"] + row["dropped"]
        lines.append(f"| {f} | {row['kept']} | {row['dropped']} | "
                     f"{(row['kept'] / tot * 100):.1f}% (n={tot}) |" if tot else f"| {f} | 0 | 0 | - |")
    lines += ["", f"Claims kept after correcting the model's segment number to the segment the "
              f"verbatim quote is actually in: {e1['corrections']}.", "",
              "Why items were dropped:", ""]
    for reason, k in e1["reasons"].items():
        lines.append(f"- {reason}: {k}")
    lines += ["", "## E3 stance against the transcript classifier", ""]
    if e3["n"]:
        lo, hi = e3["ci"]
        lines.append(f"{e3['agree']} of {e3['n']} polar claims agree with the polar transcript reading "
                     f"of their segment: {e3['rate'] * 100:.1f}% (95% CI {lo * 100:.1f}% to {hi * 100:.1f}%).")
        lines.append("Neither side is ground truth; the transcript classifier itself is 67.8% on held-out speakers.")
    else:
        lines.append("No claim had a polar stance on a polar segment.")
    lines += ["", "## E4 cost", "", "| step | calls | median s | max prompt tokens | max output tokens |",
              "|---|---:|---:|---:|---:|"]
    for step, row in e4["per_step"].items():
        lines.append(f"| {step} | {row['n']} | {row['median_s']} | {row['max_prompt_tokens']} | "
                     f"{row['max_output_tokens']} |")
    lines.append("")
    lines.append(f"Runtime per report (s): {', '.join(str(x) for x in e4['runtime_s'])}. "
                 f"Failed calls: {e4['failed']} of {e4['calls']}.")
    if e2:
        what = (f"two runs of {e2['files'][0]}" if e2["files"][0] == e2["files"][1]
                else " and ".join(e2["files"]))
        lines += ["", "## E2 determinism", "", f"Compared: {what}, same inputs.", ""]
        for part in ("facts", "reading", "written"):
            lines.append(f"- {part}: {'identical' if e2[part]['identical'] else 'DIFFERENT'} "
                         f"({e2[part]['a']} / {e2[part]['b']})")
        lines.append(f"- same prompts: {e2['prompts_equal']}")
    comb = result.get("combined")
    if comb and comb["sets"]:
        lines += ["", "## The combined report", "",
                  f"From {len(comb['sets'])} stored combined "
                  f"{'report' if len(comb['sets']) == 1 else 'reports'}.", "",
                  "### C1 grounding", "", "| field | kept | dropped |", "|---|---:|---:|"]
        for f, row in sorted(comb["C1"]["fields"].items()):
            lines.append(f"| {f} | {row['kept']} | {row['dropped']} |")
        lines += ["", "Who wrote each printed sentence: `model`; `code`, by design (the summary: its facts are "
                  "counts); or `template`, code's sentence after the model's was dropped:", ""]
        for k, n in comb["C1"]["sources"].items():
            lines.append(f"- {k}: {n}")
        if comb["C1"]["reasons"]:
            lines += ["", "Why items were dropped:", ""]
            for reason, k in comb["C1"]["reasons"].items():
                lines.append(f"- {reason}: {k}")
        lines += ["", "### C2 themes", "",
                  "| sweep | status | members written | themes | in 3+ videos | topic weight placed | unplaced topics | source |",
                  "|---|---|---:|---:|---:|---:|---:|---|"]
        for st in comb["sets"]:
            share = "-" if st["placed_share"] is None else f"{st['placed_share'] * 100:.1f}%"
            lines.append(f"| {st['file']} | {st['status']} | {st['members_written']} | {st['themes']} | "
                         f"{st['themes_in_3_or_more']} | {share} | {st['unplaced_topics']} | {st['theme_source']} |")
        lines += ["", "### C4 cost", "", "| step | calls | median s | max prompt tokens | max output tokens |",
                  "|---|---:|---:|---:|---:|"]
        for step, row in comb["C4"]["per_step"].items():
            lines.append(f"| {step} | {row['n']} | {row['median_s']} | {row['max_prompt_tokens']} | "
                         f"{row['max_output_tokens']} |")
        lines.append(f"\nCombined runtime (s): {', '.join(str(st['runtime_s']) for st in comb['sets'])}. "
                     f"Failed calls: {comb['C4']['failed']} of {comb['C4']['calls']}.")
    rt = result.get("R1")
    if rt and rt["n"]:
        md = rt["max_delta"]
        lines += ["", "## R1 the same video, read twice", "",
                  f"{rt['n']} videos appear in two sweeps of the same subject on this machine, each analysed from "
                  f"the start days apart. Calls (reviewer and audience) unchanged in {rt['calls_same']} of "
                  f"{rt['n']}; comment label changed in {rt['label_changed']}. Largest change: reviewer lean "
                  f"{md['reviewer']:.3f}, audience lean {md['audience']:.3f}, Authenticity "
                  f"{md['authenticity']:.2f}, Brand health {md['brand_health']:.2f}.", "",
                  "| video | reviewer lean | audience lean | Authenticity | Brand health | comment label | near-tie |",
                  "|---|---|---|---|---|---|---|"]
        f3 = lambda p: " / ".join("-" if v is None else f"{v:+.3f}" for v in p)   # noqa: E731
        f2 = lambda p: " / ".join("-" if v is None else f"{v:.2f}" for v in p)    # noqa: E731
        for r in rt["rows"]:
            lines.append(f"| {r['video_id']} | {f3(r['reviewer'])} | {f3(r['audience'])} | {f2(r['authenticity'])} | "
                         f"{f2(r['brand_health'])} | {' / '.join(str(x) for x in r['label'])} | "
                         f"{' / '.join('yes' if x else 'no' for x in r['near_tie'])} |")
    lines += ["", "## What this does not measure", "",
              "Whether the prose is a fair summary of the video. That needs a person who has watched "
              "it; `--sheet` draws a blind sample of claims for exactly that (E5).", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--same", nargs=2, metavar=("A", "B"), help="E2: two analyses of one report")
    p.add_argument("--sheet", action="store_true", help="write the E5 spot-check sheet")
    args = p.parse_args(argv)
    pairs = stored()
    result = evaluate(pairs)
    result["combined"] = evaluate_combined(combined_files())
    result["R1"] = read_twice()
    e2 = same(Path(args.same[0]), Path(args.same[1])) if args.same else None
    if e2:
        result["E2"] = e2
    if args.sheet:
        result["E5_sheet_rows"] = sheet(pairs)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    OUT_MD.write_text(markdown(result, e2), encoding="utf-8")
    print(markdown(result, e2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
