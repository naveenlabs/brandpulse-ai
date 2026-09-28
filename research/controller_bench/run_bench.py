"""
run_bench.py — run every candidate over every suite, resuming from cache.

Usage
-----
    python research/controller_bench/run_bench.py --stage grid          # 108 probes/model
    python research/controller_bench/run_bench.py --stage incongruence  # 36 probes/model
    python research/controller_bench/run_bench.py --stage corpus        # 481 real segments/model
    python research/controller_bench/run_bench.py --stage determinism   # G2
    python research/controller_bench/run_bench.py --stage ablation      # revised prompt
    python research/controller_bench/run_bench.py --stage registry      # licences, sizes
    python research/controller_bench/run_bench.py --only llama3.2,mistral_7b

Every stage writes one JSON per (candidate, stage) under `cache/` and skips
probes already present, so a run that is interrupted — or a candidate added
later — costs only what it has not already done. That is the same discipline
`vocal_bench/corpus_ab.py` uses, and it is what makes a multi-hour sweep
survivable on a laptop.

Damping is disabled for the whole run (PROTOCOL.md §6, `DampingDisabled`).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
for p in (str(PROJECT), str(BENCH)):
    if p not in sys.path:
        sys.path.insert(0, p)

import candidates as C  # noqa: E402
import probes as P  # noqa: E402
from pipeline import orchestrator as O  # noqa: E402

CACHE = BENCH / "cache"
STAGES = ("grid", "incongruence", "corpus", "determinism", "ablation", "registry")

# How many probes G2 re-runs to test determinism. PROTOCOL.md §8 fixed 20.
DETERMINISM_N = 20

# ── The revised prompt for the Q2 ablation ────────────────────────────────────
#
# Written once, before the ablation ran, and fixed. It KEEPS every instruction of
# the deployed prompt — including the CHANNEL RELIABILITY paragraph, which is the
# hypothesis under test and so must not be removed — and ADDS an explicit
# statement of what the endpoints of the scale mean in terms of channel
# disagreement.
#
# The deployed prompt states the endpoints ("0.0 full agreement -> 1.0 all
# channels disagree") but never says what to do in between, and it spends a
# paragraph telling the controller when NOT to raise a score without ever telling
# it when to. The revision supplies the missing half. It is derived from the
# deployed prompt by insertion at a marker rather than pasted, so the two cannot
# silently drift apart — the same safeguard `corpus_ab._legacy_prompt` uses, and
# the assert is the safeguard.
_ABLATION_INSERT = """

HOW TO SET conflict_score. Compare the valence of every channel that reports one
(a facial channel reading "none detected" reports none, and is excluded).

- All reporting channels show the same valence  -> conflict_score 0.0
- Some channels differ only between NEUTRAL and one pole -> a LOW but NON-ZERO
  score, roughly 0.2-0.4
- At least one channel is POSITIVE while another is NEGATIVE -> a HIGH score,
  0.7 or above. Two channels at opposite poles of the valence axis is the
  strongest evidence of inauthenticity this system can observe, and it must not
  be scored 0.0.

Do not return 0.0 unless the reporting channels genuinely agree."""


def revised_prompt(current: str | None = None) -> str:
    """The deployed prompt plus the scale definition, inserted at a fixed marker."""
    cur = current if current is not None else O._SYSTEM_PROMPT
    marker = "\n\nIMPORTANT: You must ALWAYS return valid JSON"
    assert marker in cur, "prompt marker missing — revised_prompt needs updating"
    head, tail = cur.split(marker, 1)
    return head + _ABLATION_INSERT + marker + tail


# ── Suites ────────────────────────────────────────────────────────────────────

def corpus_probes() -> list[dict]:
    """The 481 cached `after_nodamp` segments, rebuilt as probes.

    Channels come from `vocal_bench/ab_cache/`, byte-for-byte the same inputs the
    incumbent saw when it produced the responses in PROTOCOL.md §1. Whisper is not
    re-run, no sentiment is recomputed, no comment is re-fetched.
    """
    ab = PROJECT / "research" / "vocal_bench" / "ab_cache"
    corpus = PROJECT / "research" / "transcript_bench" / "corpus"
    out = []
    for conflict_file in sorted((ab / "conflict_after_nodamp").glob("*.json")):
        vid = conflict_file.stem
        wanted = set(json.loads(conflict_file.read_text()))
        ts = json.loads((ab / "transcript" / f"{vid}.json").read_text())
        ve = json.loads((ab / "vocal_audeering" / f"{vid}.json").read_text())
        cs = json.loads((ab / "comments" / f"{vid}.json").read_text())
        doc = json.loads((corpus / f"{vid}.json").read_text())
        for s in doc["segments"]:
            key = str(s["segment_id"])
            if key not in wanted:
                continue
            seg = {
                "segment_id": s["segment_id"],
                "start_time": s["start_time"], "end_time": s["end_time"],
                "text": s["text"],
                "transcript_sentiment": ts[key],
                "vocal_emotion": ve[key],
            }
            v = ve[key]
            out.append({
                "probe_id": f"{vid}#{key}",
                "suite": "corpus",
                "video_id": vid,
                "segment": seg,
                "comment_sentiment": cs,
                "spec": {
                    "transcript_sentiment": (ts[key] or {}).get("label"),
                    "vocal_emotion": v.get("label") if isinstance(v, dict) else v,
                    # No frames were extracted for these videos, so the payload
                    # shows "none detected" and the channel has no valence. Stated
                    # rather than silently absent.
                    "facial_emotion": "none detected",
                    "video_comment_sentiment": (cs or {}).get("label"),
                },
            })
    return out


def suite_for(stage: str) -> list[dict]:
    if stage in ("grid", "determinism", "ablation"):
        return P.probe_suite()
    if stage == "incongruence":
        return P.incongruence_suite()
    if stage == "corpus":
        return corpus_probes()
    raise KeyError(stage)


# ── Running ───────────────────────────────────────────────────────────────────

def _cache_path(stage: str, name: str, tag: str = "") -> Path:
    return CACHE / stage / f"{name}{tag}.json"


def run_stage(stage: str, names: list[str], limit: int | None = None,
              prompt: str | None = None, tag: str = "") -> None:
    suite = suite_for(stage)
    if limit:
        suite = suite[:limit]
    for name in names:
        path = _cache_path(stage, name, tag)
        path.parent.mkdir(parents=True, exist_ok=True)
        done = json.loads(path.read_text()) if path.is_file() else {}
        todo = [p for p in suite if p["probe_id"] not in done]
        if not todo:
            print(f"  {name:<14} {stage:<13} cached ({len(done)})")
            continue
        print(f"  {name:<14} {stage:<13} {len(todo)} to run "
              f"({len(done)} cached) …", flush=True)
        t0 = time.time()
        with C.DampingDisabled():
            for i, probe in enumerate(todo, 1):
                done[probe["probe_id"]] = C.run_probe(name, probe, system_prompt=prompt)
                if i % 20 == 0 or i == len(todo):
                    path.write_text(json.dumps(done, indent=1))
                    rate = (time.time() - t0) / i
                    print(f"      {i}/{len(todo)}  {rate:.2f}s/probe  "
                          f"eta {(len(todo) - i) * rate / 60:.1f}min", flush=True)
        path.write_text(json.dumps(done, indent=1))
        lat = [r["latency_s"] for r in done.values() if r.get("error") is None]
        errs = sum(1 for r in done.values() if r.get("error"))
        print(f"      done: median {statistics.median(lat):.2f}s, "
              f"{errs} errors", flush=True)


def run_determinism(names: list[str]) -> None:
    """G2: re-run the first DETERMINISM_N grid probes and compare, call for call.

    A second cache file rather than a second key, so the first run is untouched
    and the comparison is between two independent passes.
    """
    run_stage("determinism", names, limit=DETERMINISM_N, tag="_rep")
    for name in names:
        a = json.loads(_cache_path("grid", name).read_text())
        b = json.loads(_cache_path("determinism", name, "_rep").read_text())
        shared = sorted(set(a) & set(b))
        same = sum(1 for k in shared if a[k]["conflict_score"] == b[k]["conflict_score"])
        ident = sum(1 for k in shared
                    if json.dumps(a[k]["raw"], sort_keys=True)
                    == json.dumps(b[k]["raw"], sort_keys=True))
        print(f"  {name:<14} score-identical {same}/{len(shared)}   "
              f"byte-identical {ident}/{len(shared)}")


def run_registry() -> None:
    """Record each model's own metadata from `ollama show`. Rule 4: verify.

    Licence and parameter count are read from the model's own manifest rather
    than typed from memory, so the write-up's licensing column is a primary
    source and not a recollection.
    """
    import requests
    out = {}
    for name, spec in C.LLM_CANDIDATES.items():
        try:
            r = requests.post(f"{O.OLLAMA_BASE_URL}/api/show",
                              json={"model": spec["tag"]}, timeout=30)
            r.raise_for_status()
            d = r.json()
            det = d.get("details", {})
            lic = (d.get("license") or "").strip()
            info = d.get("model_info", {})
            out[name] = {
                "tag": spec["tag"],
                "note": spec["note"],
                "family": det.get("family"),
                "parameter_size": det.get("parameter_size"),
                "quantization": det.get("quantization_level"),
                "context_length": next((v for k, v in info.items()
                                        if k.endswith("context_length")), None),
                "licence_first_line": lic.splitlines()[0][:160] if lic else None,
                "licence_chars": len(lic),
            }
        except Exception as exc:
            out[name] = {"tag": spec["tag"], "error": f"{type(exc).__name__}: {exc}"[:200]}
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "registry.json").write_text(json.dumps(out, indent=1))
    for name, d in out.items():
        print(f"  {name:<14} {d.get('parameter_size', '?'):>8} "
              f"{str(d.get('quantization')):<8} ctx={d.get('context_length')} "
              f"{str(d.get('licence_first_line'))[:60]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=STAGES + ("all",))
    ap.add_argument("--only", help="comma-separated candidate names")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    names = ([n.strip() for n in args.only.split(",")] if args.only
             else list(C.ALL_CANDIDATES))
    unknown = [n for n in names if n not in C.ALL_CANDIDATES]
    if unknown:
        sys.exit(f"unknown candidate(s): {unknown}")

    if args.stage == "registry":
        run_registry()
        return
    if args.stage == "determinism":
        run_determinism([n for n in names if not C.is_reference(n)])
        return
    if args.stage == "ablation":
        run_stage("ablation", [n for n in names if not C.is_reference(n)],
                  limit=args.limit, prompt=revised_prompt(), tag="_revised")
        return

    missing = C.missing_candidates()
    if missing:
        print(f"note: not pulled, will be skipped: {missing}")
        names = [n for n in names if n not in missing]

    stages = ("grid", "incongruence", "corpus") if args.stage == "all" else (args.stage,)
    for st in stages:
        print(f"\n=== {st} ===")
        run_stage(st, names, limit=args.limit)


if __name__ == "__main__":
    main()
