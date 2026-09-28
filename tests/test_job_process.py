"""
The analysis child process (app._run_job_in_child) reports to the server.

/analyse/start runs the pipeline in a spawned process so that a cancel can kill
it outright. The child cannot write the server's `_jobs`, so it reports each
stage and then its verdict over a queue, which a watcher thread in the server
turns back into the record the page polls. These tests drive the child's entry
point in this process, with a plain queue and the pipeline mocked at the app
boundary (as in test_app.py); the scoring arithmetic runs for real.
"""

from __future__ import annotations

import queue
from pathlib import Path

import pytest

import app as A


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(A.os, "setsid", lambda: None)        # never detach the test runner
    monkeypatch.setattr(A, "fetch_comments", lambda *a, **k: [])
    monkeypatch.setattr(A, "classify_comment_sentiment", lambda c: [])
    monkeypatch.setattr(A, "aggregate_video_sentiment", lambda c: {
        "label": "NEUTRAL", "confidence": 0.0, "comment_count": 0, "distribution": {}})
    monkeypatch.setattr(A, "_build_segments", lambda url, vid: [
        {"segment_id": 0, "start_time": 0.0, "end_time": 5.0, "text": "fine"}])
    monkeypatch.setattr(A, "run_orchestration", lambda *a, **k: [
        {"segment_id": 0, "start_s": 0.0, "end_s": 5.0, "conflict_score": 0.1,
         "conflict_reasons": [], "flagged": False}])
    monkeypatch.setattr(A, "_save_report", lambda *a, **k: None)
    monkeypatch.setattr(A.frame_cache, "warm", lambda r: 0)
    monkeypatch.setattr(A, "write_report_analysis", lambda r, n: None)
    before = dict(A._jobs)
    yield monkeypatch
    A._jobs.clear()
    A._jobs.update(before)


def _run(messages: queue.Queue) -> list[tuple]:
    A._run_job_in_child(messages, "zz-child", "https://youtu.be/dQw4w9WgXcQ", "Brand", "Thing", 10)
    out = []
    while not messages.empty():
        out.append(messages.get_nowait())
    return out


def test_every_stage_is_relayed_in_order_then_the_report(pipeline):
    out = _run(queue.Queue())
    assert [m for m in out if m[0] == "stage"] == [("stage", i) for i in range(len(A._STAGES))]
    kind, report = out[-1]
    assert kind == "done"
    assert report["brand_name"] == "Brand" and report["bias_caveat"] == A.BIAS_CAVEAT


def test_a_failing_stage_is_relayed_as_an_error_with_its_reason(pipeline):
    def fails(url, vid):
        raise RuntimeError("Video unavailable")
    pipeline.setattr(A, "_build_segments", fails)
    out = _run(queue.Queue())
    assert [m for m in out if m[0] == "stage"] == [("stage", 0), ("stage", 1)]
    assert out[-1] == ("error", "Video unavailable")


def test_the_server_module_is_not_rewritten_by_the_child(pipeline):
    """The relay is passed in; the module's own `_set_stage` is left as it was."""
    original = A._set_stage
    _run(queue.Queue())
    assert A._set_stage is original


def test_a_sweep_cannot_be_marked_cancelled_through_the_analysis_route():
    """
    /analyse/cancel on a sweep would mark it cancelled while its thread kept
    running, freeing the one-job-at-a-time guard for a second run beside it.
    """
    A._jobs["zz-sweep-job"] = {"kind": "sweep", "status": "running", "cancel_requested": False}
    try:
        response = A.app.test_client().post("/analyse/cancel/zz-sweep-job")
        assert response.status_code == 400
        assert A._jobs["zz-sweep-job"]["status"] == "running"
        assert A._jobs["zz-sweep-job"]["cancel_requested"] is False
    finally:
        A._jobs.pop("zz-sweep-job", None)


def _sweep_and_single(text: str) -> tuple[str, str]:
    """The two branches of the one `isSweep ? "..." : "..."` choice in `text`."""
    ask = text.index('? "')
    other = text.index(': "', ask)
    return text[ask:other], text[other:]


def test_the_run_page_says_only_a_five_video_run_stops_at_its_next_checkpoint():
    """
    A single run is killed at once (app._stop_child); a sweep stops between
    stages. The page says so under the Stop button and again, to a screen
    reader, when Stop is pressed. Neither may tell a single run's reader to wait.
    """
    source = (Path(A.__file__).parent / "interface" / "ui" / "src" / "pages" / "run.js").read_text(encoding="utf-8")
    under_button = source[source.index("data-cancel>Stop this run"):]
    under_button = under_button[:under_button.index("</p>")]
    pressed = source[source.index("function wireRunning("):]
    pressed = pressed[:pressed.index("try {")]
    for text in (under_button, pressed):
        sweep_says, single_says = _sweep_and_single(text)
        assert "not instant" in sweep_says
        assert "not instant" not in single_says and "between stages" not in single_says
    assert "at once" in _sweep_and_single(under_button)[1]


class _NoChild:
    """A spawn context whose process never starts: /analyse/start's bookkeeping only."""

    def Queue(self):  # noqa: N802 - mirrors multiprocessing's name
        return queue.Queue()

    def Process(self, **kwargs):  # noqa: N802
        class Process:
            pid = None
            def start(self): pass
            def is_alive(self): return False
        return Process()


@pytest.mark.parametrize("product, saved_as", [
    ("Galaxy S26 Ultra", "Samsung (Galaxy S26 Ultra).json"),
    ("S26/Ultra: 512GB?", "Samsung (S26Ultra 512GB).json"),
])
def test_a_finished_run_names_the_file_its_report_was_saved_under(monkeypatch, tmp_path, product, saved_as):
    """
    The finished page links to the report by this name. The report does not
    carry the product, and a page reloaded mid-run never saw the form, so the
    page cannot rebuild it; nor would it strip what the server strips.
    """
    monkeypatch.setattr(A, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(A.multiprocessing, "get_context", lambda method: _NoChild())
    monkeypatch.setattr(A.threading, "Thread", lambda **kw: type("T", (), {"start": lambda self: None})())
    before, procs = dict(A._jobs), dict(A._job_procs)
    try:
        client = A.app.test_client()
        started = client.post("/analyse/start", json={
            "video_url": "https://youtu.be/dQw4w9WgXcQ", "brand_name": "Samsung", "product_name": product})
        assert started.status_code == 202
        job_id = started.get_json()["job_id"]
        running = client.get(f"/analyse/status/{job_id}").get_json()
        assert "report_file" not in running
        A._jobs[job_id].update(status="done", result={"brand_name": "Samsung"})
        done = client.get(f"/analyse/status/{job_id}").get_json()
        assert done["report_file"] == saved_as == A._report_filename("Samsung", product)
    finally:
        A._jobs.clear()
        A._jobs.update(before)
        A._job_procs.clear()
        A._job_procs.update(procs)


def test_the_finished_page_links_to_the_name_the_server_returned():
    source = (Path(A.__file__).parent / "interface" / "ui" / "src" / "pages" / "run.js").read_text(encoding="utf-8")
    link = source[source.index("function reportLink("):]
    link = link[:link.index("\n}\n")]
    assert "report_file" in link
    assert "brand_name" not in link and "product_name" not in link


# ── Windows: no setsid, no process groups, no SIGKILL ───────────────────────
#
# os.setsid, os.getpgid, os.killpg and signal.SIGKILL do not exist on Windows.
# Until 28 Sep 2026 the child called os.setsid() inside `except OSError`, which
# the AttributeError Windows raises passes straight through, so every analysis
# started from the page died at once ("stopped unexpectedly (exit code 1)").
# These tests remove those names, as Windows has them, and drive the same code.

def test_the_child_detaches_where_the_platform_can(pipeline):
    calls = []
    pipeline.setattr(A.os, "setsid", lambda: calls.append("setsid"))
    assert _run(queue.Queue())[-1][0] == "done"
    assert calls == ["setsid"]


def test_the_child_runs_where_there_is_no_setsid(pipeline):
    pipeline.delattr(A.os, "setsid")
    out = _run(queue.Queue())
    assert [m for m in out if m[0] == "stage"] == [("stage", i) for i in range(len(A._STAGES))]
    assert out[-1][0] == "done"


class _Child:
    """A stand-in for the analysis process: alive until something ends it."""

    pid = 4321

    def __init__(self):
        self.alive, self.killed, self.terminated = True, False, False

    def is_alive(self):
        return self.alive

    def kill(self):
        self.killed, self.alive = True, False

    def terminate(self):
        self.terminated, self.alive = True, False

    def join(self, timeout=None):
        pass


@pytest.fixture
def child():
    process = _Child()
    A._job_procs["zz-stop"] = (process, None)
    yield process
    A._job_procs.pop("zz-stop", None)


@pytest.fixture
def windows(monkeypatch):
    for name in ("setsid", "getpgid", "killpg"):
        monkeypatch.delattr(A.os, name, raising=False)
    monkeypatch.delattr(A.signal, "SIGKILL", raising=False)
    return monkeypatch


def test_stop_ends_the_process_tree_by_id_on_windows(windows, child):
    ran = []

    def taskkill(cmd, **kwargs):
        ran.append(cmd)
        child.alive = False
        return None

    windows.setattr(A.subprocess, "run", taskkill)
    A._stop_child("zz-stop")
    assert ran == [["taskkill", "/PID", "4321", "/T", "/F"]]
    assert not child.killed


def test_stop_still_kills_the_process_when_taskkill_cannot_run(windows, child):
    def missing(cmd, **kwargs):
        raise FileNotFoundError("taskkill")

    windows.setattr(A.subprocess, "run", missing)
    A._stop_child("zz-stop")
    assert child.killed and not child.is_alive()


def test_stop_signals_the_group_where_there_is_one(monkeypatch, child):
    sent = []

    def killpg(group, sig):
        sent.append((group, sig))
        child.alive = False

    monkeypatch.setattr(A.os, "getpgid", lambda pid: 777, raising=False)
    monkeypatch.setattr(A.os, "killpg", killpg, raising=False)
    monkeypatch.setattr(A.subprocess, "run", lambda *a, **k: pytest.fail("taskkill on a POSIX system"))
    A._stop_child("zz-stop")
    assert sent == [(777, A.signal.SIGTERM)]
