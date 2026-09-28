"""
Root pytest configuration.

`_retired_ui/` holds the front end retired on 10 Sep 2026 and the 191 tests that
described it (test_dashboard.py, test_landing.py, test_design_system.py). The
directory is kept rather than deleted because this working copy is the only copy
of some of those files, but its contents are not part of the product and must not
be collected: those tests assert an interface that no longer exists, and a green
run of them would mean the old design had been rebuilt.
"""

import pytest

collect_ignore_glob = ["_retired_ui/*"]


@pytest.fixture(autouse=True)
def _the_written_report_never_leaves_the_test(tmp_path, monkeypatch):
    """
    No test reaches the local model, the YouTube API or the real outputs folder
    through the written-report step.

    Added 23 Sep 2026 after the first run with that step wired into the app: the
    existing job tests drive `_run_job` and `_run_sweep_job` with their pipeline
    mocked at the app boundary, which did not yet include the new step, so it
    ran for real. It made three real YouTube lookups for the fixture ids, three
    real local-model calls, and wrote three files into a new folder under
    outputs/sweeps/. Nothing it touched existed before, and it was removed.

    Here, for every test, the model call refuses, the YouTube client is absent,
    and the analysis is stored under a temporary folder. A test that exercises
    one of these on purpose patches it back explicitly, which is the point: it
    has to say so.

    `sweep.build` joined on 24 Sep 2026, when a sweep job that was started
    without its videos' titles began looking them up itself: the same job tests
    would otherwise have made that lookup for real. `comment_module.build`
    joined on 26 Sep 2026: every job test mocks the comment fetch at the app
    boundary, so none reached it, but nothing stopped one that did not.
    """
    from pipeline import analyst, comment_module, sweep

    def no_model(*_args, **_kwargs):
        raise RuntimeError("the local model is not called from tests")

    monkeypatch.setattr(analyst, "ollama_chat", no_model)
    monkeypatch.setattr(analyst, "build", None)
    monkeypatch.setattr(sweep, "build", None)
    monkeypatch.setattr(comment_module, "build", None)
    monkeypatch.setattr(analyst, "OUTPUTS", tmp_path / "outputs")
    yield
