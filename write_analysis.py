"""
write_analysis.py — write (or size) the written report for saved runs.

    python write_analysis.py --report "Nike (Mind 001).json"
    python write_analysis.py --sweep <sweep-id> --member <video-id>
    python write_analysis.py --sweep <sweep-id>                 # members, then the combined report
    python write_analysis.py --sweep <sweep-id> --combined-only
    python write_analysis.py --recheck --sweep <sweep-id>       # current checks on stored text, no model
    python write_analysis.py --dry-run --all          # sizes every prompt, calls nothing
    python write_analysis.py --all                    # every saved report and sweep (backfill)
    python write_analysis.py --fill-details --sweep <sweep-id>  # blank titles, from disk

The analysis is written beside the report (outputs/analysis/, or
outputs/sweeps/<id>/analysis/), never into it. A report whose analysis already
exists and whose file has not changed since is skipped unless --force. A
sweep's combined report (analysis/combined.json) is written after its members'
and is rewritten whenever the sweep or any member's written report changed.

--dry-run builds every prompt the model would receive, using a stand-in that
answers each step with the largest output the schema and the caps allow, and
prints the largest prompt per step. Nothing is sent to the model or written to
disk. It is how ANALYST_NUM_CTX was chosen.

The backfill (--all without --dry-run) is gated: it asks for confirmation,
because it runs the local model over every report and takes hours.

--fill-details repairs a sweep saved without its videos' titles, channels and
dates (started from a page that did not send the search result back, 24 Sep
2026). It copies them from what each member's written report was told by
YouTube, fills only blanks, and touches nothing but sweep.json: no model, no
network. The combined report then reads as out of date, correctly, until it is
rewritten with --combined-only. With --dry-run it prints and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pipeline import analyst, analyst_sweep  # noqa: E402  (after load_dotenv, as app.py does)
from pipeline import sweep  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
SWEEPS = OUTPUTS / "sweeps"

# Characters per token for sizing. Measured, not assumed: on the Gate A run,
# Ollama's own prompt_eval_count was compared with this.
CHARS_PER_TOKEN = 3.5


def report_targets(args) -> list[tuple[Path, Path, str | None]]:
    """(report path, analysis path, filename used for the subject) for each target."""
    out = []
    if args.report:
        path = OUTPUTS / Path(args.report).name
        out.append((path, analyst.storage_path_for_report(path.name), path.name))
    if args.sweep and not args.combined_only:
        members = SWEEPS / args.sweep / "members"
        ids = [args.member] if args.member else sorted(p.stem for p in members.glob("*.json"))
        for vid in ids:
            out.append((members / f"{vid}.json", analyst.storage_path_for_member(args.sweep, vid), None))
    if args.all:
        for path in sorted(OUTPUTS.glob("*.json")):
            out.append((path, analyst.storage_path_for_report(path.name), path.name))
        for members in sorted(SWEEPS.glob("*/members")):
            sid = members.parent.name
            for path in sorted(members.glob("*.json")):
                out.append((path, analyst.storage_path_for_member(sid, path.stem), None))
    return out


def sweep_targets(args) -> list[str]:
    """The sweeps whose combined report is written: never for a single --member."""
    if args.sweep and not args.member:
        return [args.sweep]
    if args.all:
        return sorted(p.parent.name for p in SWEEPS.glob("*/sweep.json"))
    return []


class Sizer:
    """A stand-in model that answers with the largest valid output, and records prompts."""

    def __init__(self) -> None:
        self.prompts: list[tuple[str, int]] = []

    def __call__(self, system: str, user: str, schema: dict) -> dict:
        step = {analyst.P1_SYSTEM: "claims", analyst.P2_SYSTEM: "topics",
                analyst.P3_SYSTEM: "comments", analyst.P4_SYSTEM: "prose",
                analyst_sweep.P5_SYSTEM: "themes", analyst_sweep.P5B_SYSTEM: "products",
                analyst_sweep.P6_SYSTEM: "set_prose"}[system]
        self.prompts.append((step, len(system) + len(user)))
        payload = json.loads(user)
        if step == "claims":
            claims = []
            for seg in payload["segments"]:
                words = seg["text"].split()
                if len(words) < 4:
                    continue
                claims.append({"seg": seg["seg"], "aspect": "battery life", "stance": "praise",
                               "claim": "The reviewer finds the battery life good enough for a full day",
                               "quote": " ".join(words[:25])})
            answer = {"claims": claims[:analyst.CLAIMS_PER_CHUNK]}
        elif step == "comments":
            answer = {"comments": [{"i": c["i"], "topics": payload["topics"][:2]}
                                   for c in payload["comments"]]}
        elif step == "topics":
            aspects = [x["aspect"] for x in payload["reviewer_aspects"]]
            answer = {"topics": [{"name": f"Topic number {k}", "aspects": aspects[k::8]}
                                 for k in range(8)]}
        elif step == "themes":
            refs = [t["ref"] for v in payload["videos"] for t in v["topics"]]
            answer = {"themes": [{"name": f"Theme number {k}", "topics": refs[k::8]} for k in range(8)]}
        elif step == "products":
            answer = {"products": [{"v": v["v"], "product": " ".join(v["title"].split()[:6])}
                                   for v in payload["videos"]]}
        else:
            answer = {}
        return {"message": {"content": json.dumps(answer)}, "prompt_eval_count": None, "eval_count": None}


def _record(sweep_id: str) -> tuple[Path, dict | None]:
    path = SWEEPS / sweep_id / "sweep.json"
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return path, None


def dry_run(targets, sweeps) -> int:
    worst: dict[str, tuple[int, str]] = {}
    sized: dict[str, dict] = {}          # member report path -> its in-memory analysis

    def note(sizer, name):
        for step, chars in sizer.prompts:
            if chars > worst.get(step, (0, ""))[0]:
                worst[step] = (chars, name)

    failures = 0
    for report_path, _, filename in targets:
        if not report_path.is_file():
            print(f"missing: {report_path}")
            failures += 1
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        sizer = Sizer()
        sized[str(report_path)] = analyst.analyse_report(report, filename=filename, fetch_meta=False,
                                                          chat=sizer)
        note(sizer, report_path.name)
        print(f"{report_path.name[:40]:40} calls {len(sizer.prompts):3}  "
              f"largest prompt {max((c for _, c in sizer.prompts), default=0):6} chars")
    for sid in sweeps:
        record_path, record = _record(sid)
        if record is None:
            print(f"missing: {record_path}")
            failures += 1
            continue
        bundles = analyst_sweep.load_bundles(sid, record, SWEEPS / sid / "members")
        for b in bundles:
            path = SWEEPS / sid / "members" / f"{b['entry'].get('video_id')}.json"
            if b.get("report") is not None and str(path) in sized:
                b["analysis"], b["stale"] = sized[str(path)], False
        sizer = Sizer()
        analyst_sweep.analyse_sweep(record, bundles, chat=sizer)
        note(sizer, f"{sid} (combined)")
        print(f"{sid[:40]:40} combined calls {len(sizer.prompts):3}  "
              f"largest prompt {max((c for _, c in sizer.prompts), default=0):6} chars")
    print("\nLargest prompt per step (system + user), estimated at "
          f"{CHARS_PER_TOKEN} characters per token:")
    for step, (chars, name) in sorted(worst.items()):
        print(f"  {step:9} {chars:6} chars  ~{chars / CHARS_PER_TOKEN:5.0f} tokens   ({name})")
    return 1 if failures else 0


def run(targets, force: bool) -> int:
    failures = 0
    for report_path, out_path, filename in targets:
        if not report_path.is_file():
            print(f"missing: {report_path}")
            failures += 1
            continue
        existing = analyst.load(out_path, report_path)
        if existing and not existing.get("stale") and not force:
            print(f"skip (up to date): {report_path.name}")
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        started = time.perf_counter()
        result = analyst.analyse_report(report, filename=filename)
        analyst.save(out_path, result, report_path)
        v = result["verifier"]
        print(f"{report_path.name}: {result['status']} in {time.perf_counter() - started:.0f}s, "
              f"{len(result['calls'])} calls, kept {v['kept']} of {v['proposed']} -> {out_path}")
    return 1 if failures else 0


def run_recheck(targets) -> int:
    """Apply the current checks to stored write-ups; rewrite only those that changed."""
    for report_path, out_path, filename in targets:
        existing = analyst.load(out_path, report_path) if report_path.is_file() else None
        if not existing or existing.get("stale") or not existing.get("written"):
            print(f"skip (nothing current to recheck): {report_path.name}")
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        existing.pop("stale", None)
        result = analyst.recheck(existing, report, filename)
        changed = result["rechecked"]["changed"]
        if changed:
            analyst.save(out_path, result, report_path)
        print(f"{report_path.name}: {changed} sentence{'s' if changed != 1 else ''} dropped on recheck")
    return 0


def run_combined(sweeps, force: bool) -> int:
    failures = 0
    for sid in sweeps:
        record_path, record = _record(sid)
        if record is None:
            print(f"missing: {record_path}")
            failures += 1
            continue
        bundles = analyst_sweep.load_bundles(sid, record, SWEEPS / sid / "members")
        ref = analyst_sweep.sweep_ref(sid, record_path, bundles)
        out_path = analyst_sweep.storage_path_for_sweep(sid)
        existing = analyst_sweep.load(out_path, ref)
        if existing and not existing.get("stale") and not force:
            print(f"skip (up to date): {sid} (combined)")
            continue
        started = time.perf_counter()
        result = analyst_sweep.analyse_sweep(record, bundles)
        analyst_sweep.save(out_path, result, ref)
        v = result["verifier"]
        print(f"{sid} (combined): {result['status']} in {time.perf_counter() - started:.0f}s, "
              f"{len(result['calls'])} calls, {len(result['reading']['themes'])} themes, "
              f"kept {v['kept']} of {v['proposed']} -> {out_path}")
    return 1 if failures else 0


def run_fill_details(sweeps, dry: bool) -> int:
    """Blank titles, channels and dates in sweep.json, from the members' written reports."""
    failures = 0
    for sid in sweeps:
        record_path, record = _record(sid)
        if record is None:
            print(f"missing: {record_path}")
            failures += 1
            continue
        entries = record.get("members") or []
        found = analyst_sweep.written_video_details(sid, [e.get("video_id") for e in entries])
        filled = sweep.fill_blank_details(entries, found)
        for entry in entries:
            if entry.get("video_id") in filled:
                print(f"  {entry['video_id']}: {entry.get('title')!r} ({entry.get('channel')})")
        untitled = sum(1 for e in entries if not e.get("title"))
        if filled and not dry:
            sweep.write_json(record_path, record)
        print(f"{sid}: {'would fill' if dry else 'filled'} {len(filled)} of {len(entries)} videos; "
              f"{untitled} still untitled")
    return 1 if failures else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--report", help="a report file name in outputs/")
    p.add_argument("--sweep", help="a sweep id in outputs/sweeps/")
    p.add_argument("--member", help="one video id within --sweep")
    p.add_argument("--combined-only", action="store_true",
                   help="with --sweep: rewrite only the combined report, from the members' existing ones")
    p.add_argument("--all", action="store_true", help="every saved report and sweep")
    p.add_argument("--dry-run", action="store_true", help="size the prompts; call nothing")
    p.add_argument("--recheck", action="store_true",
                   help="apply the current checks to stored write-ups (no model); then rewrite "
                        "the combined report with --combined-only --force")
    p.add_argument("--fill-details", action="store_true",
                   help="with --sweep or --all: fill blank video titles, channels and dates in "
                        "sweep.json from the members' written reports (no model, no network)")
    p.add_argument("--force", action="store_true", help="rewrite even if up to date")
    p.add_argument("--yes", action="store_true", help="skip the --all confirmation")
    args = p.parse_args(argv)
    if args.combined_only and (not args.sweep or args.member):
        p.error("--combined-only needs --sweep and no --member")
    targets = report_targets(args)
    sweeps = sweep_targets(args)
    if not targets and not sweeps:
        p.error("name --report, --sweep or --all")
    if args.fill_details:
        if not sweeps:
            p.error("--fill-details needs --sweep (without --member) or --all")
        return run_fill_details(sweeps, args.dry_run)
    if args.dry_run:
        return dry_run(targets, sweeps)
    if args.recheck:
        if not targets:
            p.error("--recheck applies to single and member reports; the combined report is "
                    "then rewritten with --combined-only --force")
        return run_recheck(targets)
    if args.all and not args.yes:
        answer = input(f"Run the local model over {len(targets)} reports and {len(sweeps)} sweeps? "
                       f"This takes hours. [y/N] ")
        if answer.strip().lower() != "y":
            print("Stopped.")
            return 1
    status = run(targets, args.force)
    return max(status, run_combined(sweeps, args.force))


if __name__ == "__main__":
    sys.exit(main())
