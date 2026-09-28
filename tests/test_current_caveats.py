"""
A saved report is served with its caveats as they stand now (app._current_caveats).

Added 24 Sep 2026. VOCAL_CAVEAT called the voice "the weakest of the four" after
facial_bench/v2 had measured the face below it, and every saved report carried
that sentence in its own copy. The fix changes the constant and serves the
current one; these tests hold both halves, and the half that must not happen:
a caveat being added to a report that was saved without one.
"""

from __future__ import annotations

import json

import pytest

import app as app_module
from pipeline import sweep
from pipeline.scorer import BIAS_CAVEAT, VOCAL_CAVEAT

OLD_VOCAL = "IMPORTANT: The vocal emotion channel is the weakest of the four and is explicitly down-weighted."
REPORT = {"video_url": "https://youtu.be/JpN1DQdV4G4", "brand_name": "Zzpytest",
          "authenticity_score": 60.0, "brand_health_score": 55.0, "segment_count": 0,
          "all_segments": [], "all_comments": []}


@pytest.fixture
def client():
    return app_module.app.test_client()


class TestTheConstant:
    def test_the_vocal_caveat_no_longer_calls_the_voice_the_weakest(self):
        assert "the weakest of the four" not in VOCAL_CAVEAT
        assert "second weakest of the four, after facial emotion" in VOCAL_CAVEAT

    def test_its_measured_figures_are_unchanged(self):
        for figure in ("48.9%", "34.0%", "p = 0.0070", "+0.159", "+0.056", "147 clips"):
            assert figure in VOCAL_CAVEAT


class TestCurrentCaveats:
    def test_an_old_copy_is_replaced_by_the_current_text(self):
        out = app_module._current_caveats({**REPORT, "vocal_caveat": OLD_VOCAL, "bias_caveat": "old"})
        assert out["vocal_caveat"] == VOCAL_CAVEAT and out["bias_caveat"] == BIAS_CAVEAT

    def test_a_report_saved_without_a_caveat_is_left_without_one(self):
        out = app_module._current_caveats(dict(REPORT))
        assert "vocal_caveat" not in out and "bias_caveat" not in out
        assert app_module._current_caveats({**REPORT, "vocal_caveat": ""})["vocal_caveat"] == ""

    def test_nothing_else_in_the_report_changes(self):
        before = {**REPORT, "vocal_caveat": OLD_VOCAL}
        out = app_module._current_caveats(dict(before))
        assert {k: v for k, v in out.items() if k != "vocal_caveat"} == \
               {k: v for k, v in before.items() if k != "vocal_caveat"}


class TestTheRoutes:
    def test_a_saved_report_is_served_with_the_current_vocal_caveat(self, client, tmp_path, monkeypatch):
        """In a temporary library: until 26 Sep 2026 this wrote into the real outputs/."""
        monkeypatch.setattr(app_module, "OUTPUTS_DIR", tmp_path)
        name = "zz-pytest-brand (zz-pytest-caveat).json"
        path = tmp_path / name
        path.write_text(json.dumps({**REPORT, "vocal_caveat": OLD_VOCAL, "bias_caveat": BIAS_CAVEAT}),
                        encoding="utf-8")
        body = client.get(f"/reports/{name}").get_json()
        assert body["vocal_caveat"] == VOCAL_CAVEAT
        assert json.loads(path.read_text(encoding="utf-8"))["vocal_caveat"] == OLD_VOCAL  # file untouched

    def test_a_sweep_and_its_members_are_served_with_the_current_caveats(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(sweep, "SWEEPS", tmp_path / "sweeps")
        sid = "zz-pytest-sweep-0003"
        member = sweep.member_path(sid, "AAAAAAAAAAA")
        member.parent.mkdir(parents=True)
        member.write_text(json.dumps({**REPORT, "vocal_caveat": OLD_VOCAL}), encoding="utf-8")
        sweep.sweep_path(sid).write_text(json.dumps({"sweep_id": sid, "vocal_caveat": OLD_VOCAL,
                                                     "bias_caveat": BIAS_CAVEAT}), encoding="utf-8")
        assert client.get(f"/sweeps/{sid}/members/AAAAAAAAAAA").get_json()["vocal_caveat"] == VOCAL_CAVEAT
        assert client.get(f"/sweeps/{sid}").get_json()["vocal_caveat"] == VOCAL_CAVEAT
