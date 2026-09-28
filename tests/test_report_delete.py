"""
Deleting a volume from the library — 23 Sep 2026.

These two endpoints are the only code in this project that removes a user's
data, and the sweep one removes a directory tree. So the failure paths matter
more than the happy path and are tested first: a filename that tries to climb
out of outputs/, a sweep id that tries to climb out of outputs/sweeps/, a
report route asked to reach a sweep, and a sweep deleted out from under a job
still writing into it.

Every test runs against a temporary outputs/ (with sweeps/ inside it), so
nothing here reads, writes or could delete a real report. The traversal cases
aim at sentinel files beside and above that folder and assert they survive.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

import app as A
from pipeline import sweep as S


# Replaced for every test by the `library` fixture below.
OUTPUTS: Path
SWEEPS: Path


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    """A temporary <repo>/outputs/sweeps tree, used by the app and by this module."""
    outputs = tmp_path / "repo" / "outputs"
    (outputs / "sweeps").mkdir(parents=True)
    monkeypatch.setattr(A, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(S, "SWEEPS", outputs / "sweeps")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "OUTPUTS", outputs, raising=False)
    monkeypatch.setattr(module, "SWEEPS", outputs / "sweeps", raising=False)
    return outputs


@pytest.fixture
def client():
    return A.app.test_client()


@pytest.fixture
def a_report():
    """One disposable report, removed again if a test leaves it behind."""
    path = OUTPUTS / "zz-pytest-brand (zz-pytest-product).json"
    path.write_text(json.dumps({"authenticity_score": 50.0}), encoding="utf-8")
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def a_sweep():
    """One disposable sweep: sweep.json plus three members."""
    sweep_id = "zz-pytest-sweep-0001"
    directory = SWEEPS / sweep_id
    (directory / "members").mkdir(parents=True, exist_ok=True)
    (directory / "sweep.json").write_text(
        json.dumps({"sweep_id": sweep_id, "subject": "zz-pytest"}), encoding="utf-8")
    for video_id in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"):
        (directory / "members" / f"{video_id}.json").write_text("{}", encoding="utf-8")
    yield sweep_id, directory
    shutil.rmtree(directory, ignore_errors=True)


# ── the refusals ──────────────────────────────────────────────────────────────

class TestDeleteReportRefuses:
    def test_a_name_that_climbs_out_of_outputs_cannot_delete_a_file_beside_it(self, client):
        target = OUTPUTS.parent / "beside.json"
        target.write_text("{}", encoding="utf-8")
        response = client.delete("/reports/..%2Fbeside.json")
        assert response.status_code != 200
        assert target.exists(), "traversal deleted a file outside outputs/"

    def test_a_name_that_climbs_two_levels_cannot_reach_above_the_repository(self, client):
        target = OUTPUTS.parent.parent / "above.json"
        target.write_text("{}", encoding="utf-8")
        response = client.delete("/reports/..%2F..%2Fabove.json")
        assert response.status_code != 200
        assert target.exists(), "traversal deleted a file above the repository"

    def test_the_report_route_cannot_reach_a_sweep(self, client, a_sweep):
        sweep_id, directory = a_sweep
        response = client.delete(f"/reports/sweeps%2F{sweep_id}%2Fsweep.json")
        assert response.status_code != 200
        assert (directory / "sweep.json").exists(), "a sweep was deleted by the report route"

    def test_a_name_that_is_not_json_is_rejected(self, client):
        response = client.delete("/reports/notes.txt")
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid filename"

    def test_a_report_that_is_not_there_is_a_404(self, client):
        response = client.delete("/reports/zz-pytest-absent (nothing).json")
        assert response.status_code == 404


class TestDeleteSweepRefuses:
    def test_an_id_that_climbs_out_of_sweeps_is_refused(self, client):
        response = client.delete("/sweeps/..%2F..%2Foutputs")
        assert response.status_code != 200
        assert OUTPUTS.is_dir(), "traversal removed the outputs directory"

    def test_a_hidden_id_is_refused(self, client):
        response = client.delete("/sweeps/.hidden")
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid sweep id"

    def test_a_sweep_that_is_not_there_is_a_404(self, client):
        response = client.delete("/sweeps/zz-pytest-absent-9999")
        assert response.status_code == 404

    def test_a_running_sweep_is_refused_and_survives(self, client, a_sweep):
        sweep_id, directory = a_sweep
        with A._jobs_lock:
            A._jobs["zz-pytest-job"] = {
                "status": "running", "kind": "sweep", "sweep_id": sweep_id,
                "stage_index": 0, "stage_label": "", "subject": "zz-pytest",
            }
        try:
            response = client.delete(f"/sweeps/{sweep_id}")
            assert response.status_code == 409
            assert "still running" in response.get_json()["error"]
            assert directory.is_dir(), "a running sweep was deleted from under its job"
        finally:
            with A._jobs_lock:
                A._jobs.pop("zz-pytest-job", None)

    def test_a_finished_job_does_not_block_the_delete(self, client, a_sweep):
        sweep_id, directory = a_sweep
        with A._jobs_lock:
            A._jobs["zz-pytest-done"] = {
                "status": "done", "kind": "sweep", "sweep_id": sweep_id,
                "stage_index": 0, "stage_label": "", "subject": "zz-pytest",
            }
        try:
            assert client.delete(f"/sweeps/{sweep_id}").status_code == 200
            assert not directory.exists()
        finally:
            with A._jobs_lock:
                A._jobs.pop("zz-pytest-done", None)


# ── the deletions ─────────────────────────────────────────────────────────────

class TestDeleteReport:
    def test_it_deletes_the_file_and_says_so(self, client, a_report):
        response = client.delete(f"/reports/{a_report.name}")
        assert response.status_code == 200
        body = response.get_json()
        assert body["deleted"] == a_report.name
        assert body["kind"] == "report"
        assert not a_report.exists()

    def test_deleting_twice_is_a_404_not_an_error(self, client, a_report):
        assert client.delete(f"/reports/{a_report.name}").status_code == 200
        assert client.delete(f"/reports/{a_report.name}").status_code == 404

    def test_it_leaves_every_sweep_alone(self, client, a_report, a_sweep):
        _, directory = a_sweep
        before = sorted(p.name for p in (directory / "members").glob("*.json"))
        assert client.delete(f"/reports/{a_report.name}").status_code == 200
        assert sorted(p.name for p in (directory / "members").glob("*.json")) == before


class TestDeleteSweep:
    def test_it_takes_the_members_with_it(self, client, a_sweep):
        sweep_id, directory = a_sweep
        response = client.delete(f"/sweeps/{sweep_id}")
        assert response.status_code == 200
        body = response.get_json()
        assert body["deleted"] == sweep_id
        assert body["kind"] == "sweep"
        assert body["members_deleted"] == 3, "the members count must name what actually went"
        assert not directory.exists(), "the sweep directory survived its own delete"

    def test_it_leaves_the_sweeps_folder_itself_standing(self, client, a_sweep):
        sweep_id, _ = a_sweep
        assert client.delete(f"/sweeps/{sweep_id}").status_code == 200
        assert SWEEPS.is_dir()

    def test_it_leaves_standalone_reports_alone(self, client, a_report, a_sweep):
        sweep_id, _ = a_sweep
        assert client.delete(f"/sweeps/{sweep_id}").status_code == 200
        assert a_report.exists(), "deleting a sweep deleted a report in outputs/"

    def test_a_sweep_with_no_members_folder_still_deletes(self, client):
        sweep_id = "zz-pytest-sweep-empty"
        directory = SWEEPS / sweep_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "sweep.json").write_text("{}", encoding="utf-8")
        try:
            response = client.delete(f"/sweeps/{sweep_id}")
            assert response.status_code == 200
            assert response.get_json()["members_deleted"] == 0
            assert not directory.exists()
        finally:
            shutil.rmtree(directory, ignore_errors=True)


def test_the_path_guard_is_the_one_sweep_py_already_had():
    """The route must not carry its own copy of the check."""
    with pytest.raises(ValueError):
        S.sweep_dir("../escape")
    with pytest.raises(ValueError):
        S.sweep_dir(".hidden")
