"""
The parsers that read the orchestrator's audit trail, run rather than inspected.

Everything else the interface is tested on is read off the source with a regex
or measured in a browser. This module is different: it does real arithmetic that
has to be right, and getting it wrong is silent. A parser that misreads the
orchestrator's audit line prints a number that was never measured.

So it is run. Node executes the actual shipped module -- not a Python
re-implementation of it, which would only prove that two copies of a mistake
agree -- against the real reports in outputs/. Skipped, not failed, when node is
absent: node is needed to build the interface, and a grader running the
committed build does not have to have it.

Trimmed 20 Sep 2026 with the fourth interface. The waffle chart's cell-allocation
arithmetic was tested here and that chart no longer exists, so its tests went
with it. Every test of `contract.js` is unchanged: `damping`, `channelFromReason`,
`conflictChannels` and `disagreementPairs` all still ship, and the last of them
now draws the combined report's pair grid.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIB = ROOT / "interface" / "ui" / "src" / "lib"
OUTPUTS = ROOT / "outputs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not on PATH")


def run_js(body: str) -> dict:
    """Execute `body` as a module beside ui/src/lib and return what it prints."""
    script = f"""
      const contract = await import({str(LIB / 'contract.js')!r});
      const fs = await import('node:fs');
      {body}
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"node failed:\n{result.stderr[-2000:]}")
    return json.loads(result.stdout)


def report_paths() -> list[pathlib.Path]:
    files = sorted(OUTPUTS.glob("*.json"))
    sweeps = OUTPUTS / "sweeps"
    if sweeps.is_dir():
        files += sorted(sweeps.glob("*/members/*.json"))
    return files


class TestTheAuditTrailIsReadNotReconstructed:
    """
    `_coerce_result` writes the undamped score, the damped score and the weight
    into `conflict_reasons`. Dividing the damped score back out would land on the
    same number and would be an inference printed as a measurement.
    """

    def test_every_damped_segment_in_the_corpus_parses(self):
        paths = [str(p) for p in report_paths()]
        out = run_js(f"""
          const paths = {json.dumps(paths)};
          let damped = 0, unparsed = 0, mismatched = 0;
          const channels = new Set(), triggers = new Set();
          for (const p of paths) {{
            const d = JSON.parse(fs.readFileSync(p, 'utf8'));
            for (const s of d.all_segments || []) {{
              const written = (s.conflict_reasons || [])
                .some((r) => typeof r === 'string' && r.includes('downweighted'));
              const read = contract.damping(s);
              if (written && !read) {{ unparsed += 1; continue; }}
              if (!read) continue;
              damped += 1;
              channels.add(read.channel);
              triggers.add(read.trigger);
              // The stored pair must be internally consistent.
              if (Math.abs(read.before * read.weight - read.after) > 0.0001) {{
                mismatched += 1;
              }}
              if (Math.abs(read.after - s.conflict_score) > 0.0001) mismatched += 1;
            }}
          }}
          console.log(JSON.stringify({{ damped, unparsed, mismatched,
            channels: [...channels].sort(), triggers: [...triggers].sort() }}));
        """)
        assert out["unparsed"] == 0, "a written down-weighting line was not read"
        assert out["mismatched"] == 0, "before x weight did not equal after"
        assert out["damped"] > 0, "the corpus carries no damped segments to check"
        assert set(out["channels"]) <= {"vocal", "facial"}
        # Recorded rather than asserted as a constant: the attributed trigger
        # firing on nothing is vocal_bench/DAMPING_FIX_RESULT.md's own finding,
        # and a future run that fires it must not fail this test.
        assert out["triggers"], "no trigger name was recorded"

    def test_an_absent_or_malformed_line_returns_nothing(self):
        out = run_js("""
          const cases = [
            {},
            { conflict_reasons: [] },
            { conflict_reasons: ['channels_in_conflict: facial_emotion'] },
            { conflict_reasons: ['vocal_channel_downweighted[structural]: oops'] },
            { conflict_reasons: [null, 42] },
          ];
          console.log(JSON.stringify(cases.map((c) => contract.damping(c))));
        """)
        assert out == [None, None, None, None, None]


class TestChannelNamesCollapseToFour:
    """
    The prompt names four channels, the payload names one of them differently,
    and a local LLM echoes whichever it prefers. Six distinct spellings appear
    across the corpus and all six have to land on the four the interface draws.
    """

    def test_no_name_in_the_corpus_goes_unrecognised(self):
        paths = [str(p) for p in report_paths()]
        out = run_js(f"""
          const paths = {json.dumps(paths)};
          const seen = new Set(), unknown = new Set();
          for (const p of paths) {{
            const d = JSON.parse(fs.readFileSync(p, 'utf8'));
            for (const s of d.all_segments || []) {{
              for (const r of s.conflict_reasons || []) {{
                if (typeof r !== 'string') continue;
                if (!r.startsWith('channels_in_conflict: ')) continue;
                const raw = r.slice('channels_in_conflict: '.length);
                seen.add(raw);
                if (!contract.channelFromReason(raw)) unknown.add(raw);
              }}
            }}
          }}
          console.log(JSON.stringify({{ seen: [...seen].sort(), unknown: [...unknown] }}));
        """)
        assert out["unknown"] == [], f"unmapped channel names: {out['unknown']}"
        assert len(out["seen"]) >= 4, "expected several spellings in the corpus"

    def test_the_two_vocal_spellings_are_one_channel(self):
        out = run_js("""
          const s = { conflict_reasons: [
            'channels_in_conflict: vocal_prosody',
            'channels_in_conflict: vocal_emotion',
          ] };
          const read = contract.conflictChannels(s);
          console.log(JSON.stringify({ channels: [...read.channels], unknown: read.unknown }));
        """)
        assert out["channels"] == ["vocal"], "the two spellings counted twice"
        assert out["unknown"] == []

    def test_a_name_it_does_not_know_is_reported_not_swallowed(self):
        out = run_js("""
          const read = contract.conflictChannels({
            conflict_reasons: ['channels_in_conflict: astrology'] });
          console.log(JSON.stringify({
            channels: [...read.channels], unknown: read.unknown }));
        """)
        assert out["channels"] == []
        assert out["unknown"] == ["astrology"], "an unknown channel was dropped silently"


class TestTheDisagreementGridCounts:
    """
    The pairwise grid is the project's own claim counted on its own data, so the
    counts have to be the counts.
    """

    def test_pairs_are_unordered_and_complete(self):
        out = run_js("""
          const r = contract.disagreementPairs([]);
          console.log(JSON.stringify({
            pairs: r.pairs.map((p) => p.a + '|' + p.b),
            singles: r.singles.map((s) => s.channel), total: r.total }));
        """)
        # Four channels make six unordered pairs, and all six are present even
        # with nothing to count -- a pair at zero is a result, not an absence.
        assert len(out["pairs"]) == 6
        assert len(set(out["pairs"])) == 6
        assert out["singles"] == ["transcript", "facial", "vocal", "audience"]
        assert out["total"] == 0

    def test_a_pair_is_counted_once_per_segment(self):
        out = run_js("""
          const seg = { conflict_reasons: [
            'channels_in_conflict: transcript_sentiment',
            'channels_in_conflict: facial_emotion',
          ] };
          const r = contract.disagreementPairs([seg, seg, seg]);
          const tf = r.pairs.find((p) => p.a === 'transcript' && p.b === 'facial');
          const va = r.pairs.find((p) => p.a === 'vocal' && p.b === 'audience');
          console.log(JSON.stringify({
            tf: tf.count, tfShare: tf.share, va: va.count,
            attributed: r.attributed, total: r.total }));
        """)
        assert out["tf"] == 3
        assert out["tfShare"] == 1.0
        assert out["va"] == 0, "a pair that never disagreed must stay at zero"
        assert out["attributed"] == 3
        assert out["total"] == 3

    def test_a_lone_channel_makes_no_pair(self):
        out = run_js("""
          const r = contract.disagreementPairs([
            { conflict_reasons: ['channels_in_conflict: facial_emotion'] }]);
          console.log(JSON.stringify({
            pairs: r.pairs.reduce((n, p) => n + p.count, 0),
            facial: r.singles.find((s) => s.channel === 'facial').count }));
        """)
        assert out["pairs"] == 0, "one channel cannot disagree with itself"
        assert out["facial"] == 1

    def test_the_grid_matches_a_hand_count_on_a_real_report(self):
        """
        One report counted independently in Python, against the module's answer.

        The report is one the repository ships, so its absence is a failure. (It
        named "Apple (18 Pro Max).json" until that run was re-saved under a new
        name, after which this test skipped silently.)
        """
        path = OUTPUTS / "Apple (iPhone 18 Pro Max).json"
        assert path.is_file(), f"{path.name} is committed with the repository"
        payload = json.loads(path.read_text(encoding="utf-8"))

        def channel_of(raw: str) -> str | None:
            key = raw.strip().lower()
            for needle, name in (("transcript", "transcript"), ("facial", "facial"),
                                 ("vocal", "vocal"), ("comment", "audience")):
                if needle in key:
                    return name
            return None

        order = ["transcript", "facial", "vocal", "audience"]
        expected: dict[str, int] = {}
        for segment in payload["all_segments"]:
            named = sorted(
                {channel_of(r.split(": ", 1)[1])
                 for r in (segment.get("conflict_reasons") or [])
                 if isinstance(r, str) and r.startswith("channels_in_conflict: ")}
                - {None},
                key=order.index)
            for i, a in enumerate(named):
                for b in named[i + 1:]:
                    expected[f"{a}|{b}"] = expected.get(f"{a}|{b}", 0) + 1

        out = run_js(f"""
          const d = JSON.parse(fs.readFileSync({str(path)!r}, 'utf8'));
          const r = contract.disagreementPairs(d.all_segments);
          const out = {{}};
          for (const p of r.pairs) out[p.a + '|' + p.b] = p.count;
          console.log(JSON.stringify(out));
        """)
        assert expected, "the report has no attributed disagreement to count"
        for key, n in expected.items():
            assert out[key] == n, f"{key}: module said {out[key]}, hand count {n}"
