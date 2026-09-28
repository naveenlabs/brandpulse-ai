"""
The written report, wired into app.py: the fifth job stage, the routes the
book reads it from, and deleting it with its report.

The pipeline is mocked at app.py's import boundary, as in test_app.py and
test_sweep.py. The root conftest stops the model, the YouTube client and the
real outputs folder from being reached, so the stage here runs with the model
refusing — which is also the degraded path it must survive.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as app_module
from pipeline import sweep
from pipeline import analyst

ROOT = Path(app_module.__file__).parent
OUTPUTS = ROOT / "outputs"

REPORT = {
    "video_url": "https://youtu.be/JpN1DQdV4G4", "brand_name": "Zzpytest",
    "authenticity_score": 60.0, "brand_health_score": 55.0, "segment_count": 1,
    "flagged_segments": [], "comment_sentiment": {"label": "POSITIVE", "distribution": {}},
}


@pytest.fixture
def client():
    return app_module.app.test_client()


@pytest.fixture
def mocked(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_comments", lambda *a, **k: [])
    monkeypatch.setattr(app_module, "classify_comment_sentiment", lambda c: [
        {"text": "love it", "sentiment_label": "POSITIVE", "sentiment_confidence": 0.9,
         "like_count": 3}])
    monkeypatch.setattr(app_module, "aggregate_video_sentiment",
                        lambda c: {"label": "POSITIVE", "confidence": 0.9,
                                   "comment_count": 1, "distribution": {"POSITIVE": 1}})
    monkeypatch.setattr(app_module, "_build_segments", lambda url, vid: [
        {"segment_id": 0, "start_time": 0.0, "end_time": 8.0, "text": "it is great",
         "transcript_sentiment": {"label": "POSITIVE", "confidence": 0.9}}])
    monkeypatch.setattr(app_module, "run_orchestration",
                        lambda *a, **k: [{"segment_id": 0, "start_s": 0.0, "end_s": 8.0,
                                          "conflict_score": 0.2, "conflict_reasons": [],
                                          "flagged": False}])
    monkeypatch.setattr(app_module, "build_final_report", lambda *a: dict(REPORT))
    monkeypatch.setattr(app_module, "_save_report", lambda *a, **k: None)
    monkeypatch.setattr(app_module.frame_cache, "warm", lambda r: 0)
    app_module._jobs.clear()
    yield app_module
    app_module._jobs.clear()


def _job(module):
    job_id = "zz-job"
    module._jobs[job_id] = {"status": "running", "stage_index": -1, "stage_label": "Queued",
                            "total_stages": len(module._STAGES)}
    return job_id


class TestTheJobWritesTheReport:
    def test_the_fifth_stage_writes_the_analysis_beside_the_report(self, mocked):
        job_id = _job(mocked)
        mocked._run_job(job_id, "https://youtu.be/JpN1DQdV4G4", "Zzpytest", "Thing", 100)
        assert mocked._jobs[job_id]["status"] == "done"
        assert mocked._jobs[job_id]["stage_index"] == 4
        path = analyst.storage_path_for_report("Zzpytest (Thing).json")
        written = json.loads(path.read_text(encoding="utf-8"))
        # the model refuses in tests, so this is the degraded path: facts, templates
        assert written["status"] == "partial"
        assert written["facts"]["audience"]["n"] == 1
        assert written["written"]["verdict"]["source"] == "template"
        assert not (OUTPUTS / "analysis" / "Zzpytest (Thing).json").exists()

    def test_a_failing_analysis_never_fails_the_run(self, mocked, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("anything at all")
        monkeypatch.setattr(analyst, "analyse_report", boom)
        job_id = _job(mocked)
        mocked._run_job(job_id, "https://youtu.be/JpN1DQdV4G4", "Zzpytest", "Thing", 100)
        assert mocked._jobs[job_id]["status"] == "done"
        assert not analyst.storage_path_for_report("Zzpytest (Thing).json").exists()

    def test_like_counts_are_kept_and_nothing_identifying_is(self):
        out = app_module._all_comments([{"text": "x", "sentiment_label": "NEGATIVE",
                                         "sentiment_confidence": 0.5, "like_count": 7,
                                         "author": "someone", "comment_id": "abc"}])
        assert out == [{"text": "x", "label": "NEGATIVE", "confidence": 0.5, "like_count": 7}]


class TestASweepMemberGetsItsReport:
    def test_each_member_is_analysed(self, mocked, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        monkeypatch.setattr(app_module.sweep, "SWEEPS", tmp_path / "sweeps")
        ids = ["aaaaaaaaaaa", "bbbbbbbbbbb"]
        sweep_id = sweep.sweep_id_for("Zzpytest", "month", 0, ids)
        job_id, blocker = app_module._claim_worker({
            "kind": "sweep", "status": "running", "subject": "Zzpytest", "sweep_id": sweep_id,
            "stage_index": -1, "stage_label": "Queued", "total_stages": 5, "video_index": 0,
            "video_total": 2, "video_title": "", "done": [], "failed": [],
            "cancel_requested": False})
        assert blocker is None
        app_module._run_sweep_job(job_id, sweep_id, "Zzpytest", "month", 0,
                                  [{"video_id": v, "title": v} for v in ids], {}, 100)
        for v in ids:
            assert analyst.storage_path_for_member(sweep_id, v).is_file()
            assert "members" not in analyst.storage_path_for_member(sweep_id, v).parts


@pytest.fixture
def library(tmp_path, monkeypatch):
    """
    A temporary outputs/ holding one small report, so the routes are tested on a
    fixed fixture rather than on whichever reports the working copy has.
    tmp_path is the same folder the root conftest points analyst.OUTPUTS at.
    """
    outputs = tmp_path / "outputs"
    outputs.mkdir(exist_ok=True)
    monkeypatch.setattr(app_module, "OUTPUTS_DIR", outputs)
    segments = [
        {"segment_id": i, "start_s": 8.0 * i, "end_s": 8.0 * (i + 1), "text": f"part {i}",
         "flagged": i == 1, "conflict_score": 0.8 if i == 1 else 0.1,
         "model_outputs": {"transcript_sentiment": {"label": "POSITIVE", "confidence": 0.9}}}
        for i in range(3)]
    report = {**REPORT, "segment_count": 3, "all_segments": segments,
              "all_comments": [{"text": "love it", "label": "POSITIVE", "confidence": 0.9}]}
    (outputs / TestTheRoutes.NAME).write_text(json.dumps(report), encoding="utf-8")
    return outputs


class TestTheRoutes:
    NAME = "Zzpytest (Fixture).json"

    def test_without_a_written_report_the_facts_are_computed_live(self, client, library):
        r = client.get(f"/reports/{self.NAME}/analysis")
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "facts-only" and body["written"] is None
        assert body["facts"]["segments"] == 3 and body["facts"]["flagged"] == 1
        assert not analyst.storage_path_for_report(self.NAME).exists()   # nothing written

    def test_a_written_report_is_served_and_checked_for_staleness(self, client, library):
        analyst.save(analyst.storage_path_for_report(self.NAME), {"schema": analyst.SCHEMA,
                     "status": "complete"}, library / self.NAME)
        body = client.get(f"/reports/{self.NAME}/analysis").get_json()
        assert body["status"] == "complete" and body["stale"] is False

    @pytest.mark.parametrize("name", ["..%2F..%2Fapp.py", "..%2Fsweeps%2Fx.json", "notjson.txt"])
    def test_traversal_is_refused(self, client, name):
        assert client.get(f"/reports/{name}/analysis").status_code in (400, 404)

    def test_a_missing_report_is_404(self, client):
        assert client.get("/reports/zz-absent (none).json/analysis").status_code == 404

    def test_a_member_route_computes_facts_and_refuses_bad_ids(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        sid = "zz-pytest-sweep-0002"
        member = sweep.member_path(sid, "AAAAAAAAAAA")
        member.parent.mkdir(parents=True)
        member.write_text(json.dumps({**REPORT, "all_segments": [], "all_comments": []}),
                          encoding="utf-8")
        ok = client.get(f"/sweeps/{sid}/members/AAAAAAAAAAA/analysis")
        assert ok.status_code == 200 and ok.get_json()["status"] == "facts-only"
        assert client.get(f"/sweeps/{sid}/members/BBBBBBBBBBB/analysis").status_code == 404
        assert client.get(f"/sweeps/{sid}/members/bad/analysis").status_code == 400


class TestDeletingTakesTheWrittenReportWithIt:
    def test_the_sidecar_goes_with_the_report(self, client, library):
        report = library / TestTheRoutes.NAME
        sidecar = analyst.storage_path_for_report(report.name)
        analyst.save(sidecar, {"schema": analyst.SCHEMA}, report)
        r = client.delete(f"/reports/{report.name}")
        assert r.status_code == 200
        assert not report.exists() and not sidecar.exists()


# ── the combined written report (23 Sep 2026) ───────────────────────────────

from pipeline import analyst_sweep  # noqa: E402


def _sweep_job(module, sweep_id, n=2):
    job_id, blocker = module._claim_worker({
        "kind": "sweep", "status": "running", "subject": "Zzpytest", "sweep_id": sweep_id,
        "stage_index": -1, "stage_label": "Queued", "total_stages": 5, "video_index": 0,
        "video_total": n, "video_title": "", "done": [], "failed": [], "cancel_requested": False})
    assert blocker is None
    return job_id


class TestTheSweepWritesTheCombinedReport:
    IDS = ["aaaaaaaaaaa", "bbbbbbbbbbb"]

    @pytest.fixture
    def sweeps(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        return tmp_path / "sweeps"

    def run(self, module, sweep_id):
        job_id = _sweep_job(module, sweep_id)
        module._run_sweep_job(job_id, sweep_id, "Zzpytest", "month", 0,
                              [{"video_id": v, "title": v} for v in self.IDS], {}, 100)
        return job_id

    def test_a_finished_sweep_gets_its_combined_report(self, mocked, sweeps):
        sweep_id = sweep.sweep_id_for("Zzpytest", "month", 0, self.IDS)
        job_id = self.run(mocked, sweep_id)
        assert mocked._jobs[job_id]["status"] == "done"
        assert mocked._jobs[job_id]["phase"] == "combined"
        path = analyst_sweep.storage_path_for_sweep(sweep_id)
        combined = json.loads(path.read_text(encoding="utf-8"))
        # the model refuses in tests: the degraded path; the summary is code's by design
        assert combined["schema"] == analyst_sweep.SCHEMA and combined["status"] == "partial"
        assert combined["facts"]["set"]["analysed"] == 2
        assert combined["written"]["verdict"]["source"] == "code"
        assert combined["written"]["takeaways"] == []
        assert "members" not in path.parts

    def test_a_cancelled_sweep_skips_it(self, mocked, sweeps, monkeypatch):
        monkeypatch.setattr(mocked, "_is_cancelled", lambda job_id: True)
        sweep_id = sweep.sweep_id_for("Zzpytest", "month", 0, self.IDS)
        job_id = self.run(mocked, sweep_id)
        assert mocked._jobs[job_id]["status"] == "cancelled"
        assert not analyst_sweep.storage_path_for_sweep(sweep_id).exists()

    def test_a_failing_combined_report_never_fails_the_sweep(self, mocked, sweeps, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("anything at all")
        monkeypatch.setattr(analyst_sweep, "analyse_sweep", boom)
        sweep_id = sweep.sweep_id_for("Zzpytest", "month", 0, self.IDS)
        job_id = self.run(mocked, sweep_id)
        assert mocked._jobs[job_id]["status"] == "done"
        assert not analyst_sweep.storage_path_for_sweep(sweep_id).exists()
        assert sweep.read_json(sweep.sweep_path(sweep_id))["status"] == "done"

    def test_a_resumed_member_without_its_report_gets_one(self, mocked, sweeps):
        sweep_id = sweep.sweep_id_for("Zzpytest", "month", 0, self.IDS)
        on_disk = {**REPORT, "all_segments": [], "all_comments": []}
        sweep.write_json(sweep.member_path(sweep_id, self.IDS[0]), on_disk)
        assert mocked._member_analysis_missing(sweep_id, self.IDS[0])
        self.run(mocked, sweep_id)
        assert analyst.storage_path_for_member(sweep_id, self.IDS[0]).is_file()
        assert not mocked._member_analysis_missing(sweep_id, self.IDS[0])


class TestTheCombinedRoutes:
    @pytest.fixture
    def two(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        made = []
        for sid, subject, window in (("zz-pytest-month-00000001", "Zzpytest", "month"),
                                     ("zz-pytest-half-00000002", "zzpytest ", "half"),
                                     ("zz-other-month-00000003", "Something else", "month")):
            vid = "AAAAAAAAAAA"
            member = {**REPORT, "all_segments": [], "all_comments": [], "video_title": "A"}
            sweep.write_json(sweep.member_path(sid, vid), member)
            sweep.write_json(sweep.sweep_path(sid), {
                "sweep_id": sid, "subject": subject, "subject_kind": "product", "window": window,
                "offset_days": 0, "status": "done", "controller": "llama3.1:8b", "finished_at": 1789820000.0,
                "summary": {}, "members": [{"video_id": vid, "title": "A", "analysed": True}], "failed": [],
                "selection": {"published_after": "2026-08-20T00:00:00Z", "published_before": None}})
            made.append(sid)
        return made

    def test_without_a_combined_report_the_facts_are_computed_live(self, client, two):
        r = client.get(f"/sweeps/{two[0]}/analysis")
        body = r.get_json()
        assert r.status_code == 200 and body["status"] == "facts-only" and body["written"] is None
        assert body["facts"]["set"]["analysed"] == 1
        assert not analyst_sweep.storage_path_for_sweep(two[0]).exists()     # nothing written

    def test_a_stored_report_is_served_and_goes_stale_when_a_member_changes(self, client, two):
        sid = two[0]
        bundles = analyst_sweep.load_bundles(sid, sweep.read_json(sweep.sweep_path(sid)),
                                             sweep.sweep_dir(sid) / "members")
        analyst_sweep.save(analyst_sweep.storage_path_for_sweep(sid), {"schema": analyst_sweep.SCHEMA,
                           "status": "complete"}, analyst_sweep.sweep_ref(sid, sweep.sweep_path(sid), bundles))
        body = client.get(f"/sweeps/{sid}/analysis").get_json()
        assert body["status"] == "complete" and body["stale"] is False
        analyst.save(analyst.storage_path_for_member(sid, "AAAAAAAAAAA"), {"x": 1})
        body = client.get(f"/sweeps/{sid}/analysis").get_json()
        assert body["stale"] is True and body["status"] == "complete"
        # the figures are recomputed from the files as they are now
        assert body["facts"]["set"]["analysed"] == 1

    def test_two_periods_of_one_subject_are_compared(self, client, two):
        body = client.get(f"/sweeps/{two[0]}/compare/{two[1]}").get_json()
        assert body["comparable"] is True
        assert body["shared"]["n"] == 1 and body["shared"]["calls_unchanged"] == 1
        assert body["themes"] is None

    def test_different_subjects_and_the_same_sweep_are_refused(self, client, two):
        assert client.get(f"/sweeps/{two[0]}/compare/{two[2]}").get_json()["comparable"] is False
        assert client.get(f"/sweeps/{two[0]}/compare/{two[0]}").status_code == 400

    @pytest.mark.parametrize("path", ["/sweeps/zz-absent-00000000/analysis",
                                      "/sweeps/zz-absent-00000000/compare/zz-absent-00000001"])
    def test_missing_is_404(self, client, two, path):
        assert client.get(path).status_code == 404

    def test_unsafe_ids_are_refused(self, client, two):
        assert client.get("/sweeps/.hidden/analysis").status_code == 400
        assert client.get(f"/sweeps/{two[0]}/compare/.hidden").status_code == 400
