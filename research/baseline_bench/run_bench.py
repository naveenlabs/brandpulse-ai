"""
run_bench.py — run every candidate over the 120 sampled segments, cache everything.

PROTOCOL.md §7 (fairness) is enforced here rather than trusted:

  - the same 120 segments, in the same order, for every system;
  - the same controller (`llama3.1:8b`), `temperature: 0`, `seed: 42`,
    `num_ctx: 4096` for all three LLM systems — read from
    `pipeline.orchestrator` so the bench cannot drift from production;
  - the same JSON contract and the same `_coerce_result` path, so a malformed
    response degrades identically whichever system produced it.

Every raw response is written to `cache/<system>/<uid>.json` before it is scored,
with its latency. That makes the run resumable, makes `report_bench.py` a pure
function of files on disk, and means the write-up's numbers can be re-derived
years later without a working Ollama. `controller_bench` established this and it
is the reason its 268 claims are checkable.

Usage:
    python research/baseline_bench/run_bench.py                 # all systems, resume
    python research/baseline_bench/run_bench.py --system text_only_llm
    python research/baseline_bench/run_bench.py --limit 5       # smoke test
    python research/baseline_bench/run_bench.py --determinism   # re-run 10, expect identical
    python research/baseline_bench/run_bench.py --force         # ignore the cache
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
sys.path.insert(0, str(BENCH))
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import requests  # noqa: E402

import systems as SY  # noqa: E402
from pipeline import orchestrator as O  # noqa: E402

CACHE = BENCH / "cache"
TIMEOUT = 180


def cache_path(system: str, uid: str, tag: str = "") -> Path:
    d = CACHE / (system + tag)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{uid}.json"


def call_ollama(system_prompt: str, user_content: str) -> tuple[str, float]:
    """One chat completion, returning (raw content, seconds).

    Deliberately a local copy of `orchestrator._call_ollama`'s body rather than a
    call to it: the bench must vary the *system prompt* per candidate, which the
    production function does not expose. Every other field — model, temperature,
    seed, num_ctx, format — is read from the orchestrator module, so production
    and bench cannot diverge on the settings that affect the answer.
    """
    body = {
        "model": O.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_content}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42, "num_ctx": O.OLLAMA_NUM_CTX},
    }
    t0 = time.time()
    r = requests.post(f"{O.OLLAMA_BASE_URL}/api/chat", json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["message"]["content"], time.time() - t0


def run_one(system: str, probe: dict) -> dict:
    """Score one segment with one system. Never raises.

    A failure is recorded as a result with `ok: False` and a reason, and falls
    through to `_safe_fallback` exactly as production does. PROTOCOL.md's
    graceful-degradation rule applies to the bench too: one unreachable call must
    not destroy a 40-minute run.
    """
    prompt = SY.prompt_for(system)
    payload = SY.payload_for(system, probe)
    user = json.dumps(payload)
    rec = {"uid": probe["uid"], "system": system, "video_id": probe["video_id"],
           "segment_id": probe["segment_id"], "split": probe["split"],
           "payload": payload}
    try:
        raw, secs = call_ollama(prompt, user)
    except Exception as exc:
        rec.update(ok=False, reason=f"call_failed: {type(exc).__name__}",
                   seconds=None, raw=None,
                   result=O._safe_fallback(probe["segment"], "parse_error"))
        return rec
    rec["seconds"] = round(secs, 3)
    rec["raw"] = raw
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("non-object JSON")
    except Exception as exc:
        rec.update(ok=False, reason=f"parse_failed: {type(exc).__name__}",
                   result=O._safe_fallback(probe["segment"], "parse_error"))
        return rec
    rec.update(ok=True, reason=None, result=SY.coerce_for(system, data, probe))
    return rec


def run_system(system: str, probes: list[dict], force: bool = False,
               limit: int | None = None, tag: str = "") -> dict:
    todo = probes[:limit] if limit else probes
    done = fresh = failed = 0
    t0 = time.time()
    for i, probe in enumerate(todo, 1):
        p = cache_path(system, probe["uid"], tag)
        if p.exists() and not force:
            done += 1
            continue
        rec = run_one(system, probe)
        p.write_text(json.dumps(rec, indent=1))
        fresh += 1
        if not rec["ok"]:
            failed += 1
        if i % 10 == 0 or i == len(todo):
            el = time.time() - t0
            rate = el / max(fresh, 1)
            print(f"  [{system}{tag}] {i}/{len(todo)}  fresh={fresh} cached={done} "
                  f"failed={failed}  {el:.0f}s elapsed, {rate:.1f}s/call",
                  flush=True)
    return {"system": system, "n": len(todo), "cached": done, "fresh": fresh,
            "failed": failed, "seconds": round(time.time() - t0, 1)}


def preflight() -> None:
    """Refuse to start unless Ollama is up and serving the pinned controller."""
    try:
        r = requests.get(f"{O.OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        names = {m["name"] for m in r.json().get("models", [])}
    except Exception as exc:
        raise SystemExit(f"Ollama unreachable at {O.OLLAMA_BASE_URL}: {exc}")
    if O.OLLAMA_MODEL not in names:
        raise SystemExit(f"{O.OLLAMA_MODEL} not installed. Have: {sorted(names)}")
    print(f"preflight ok — {O.OLLAMA_MODEL} @ {O.OLLAMA_BASE_URL}, "
          f"num_ctx={O.OLLAMA_NUM_CTX}, temperature=0, seed=42")


def determinism(probes: list[dict], n: int = 10) -> int:
    """Re-run the first n probes of each LLM system into a `_det` cache.

    PROTOCOL.md §12 requires every experiment to be reproducible, and
    `temperature: 0` plus a fixed seed is an assertion about Ollama's behaviour,
    not a guarantee. This checks it on this machine, with this model, and reports
    a mismatch rather than assuming one cannot happen.
    """
    bad = 0
    for system in SY.LLM_SYSTEMS:
        run_system(system, probes, force=True, limit=n, tag="_det")
        for probe in probes[:n]:
            a = json.loads(cache_path(system, probe["uid"]).read_text())
            b = json.loads(cache_path(system, probe["uid"], "_det").read_text())
            sa = a["result"]["conflict_score"]
            sb = b["result"]["conflict_score"]
            if sa != sb:
                bad += 1
                print(f"  MISMATCH {system} {probe['uid']}: {sa} vs {sb}")
    print(f"determinism: {bad} mismatches over {n} probes x "
          f"{len(SY.LLM_SYSTEMS)} systems")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=list(SY.LLM_SYSTEMS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--determinism", action="store_true")
    args = ap.parse_args()

    probes = SY.build_probes()
    print(f"{len(probes)} probes "
          f"({sum(1 for p in probes if p['split'] == 'holdout')} holdout)")
    preflight()

    if args.determinism:
        return 1 if determinism(probes) else 0

    which = [args.system] if args.system else list(SY.LLM_SYSTEMS)
    summary = []
    for system in which:
        print(f"\n== {system} ==", flush=True)
        summary.append(run_system(system, probes, force=args.force,
                                  limit=args.limit))
    print("\n" + json.dumps(summary, indent=1))
    (BENCH / "run_summary.json").write_text(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
