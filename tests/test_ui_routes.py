"""
test_ui_routes.py — the server side of the interface.

Written 11 Sep 2026 with the third interface. It replaces the file of the same
name, which described the build retired that day.

Scope: what Flask serves. The four documents, the assets they load, the derived
frames, the evidence file, and the API contract — which is frozen and had to
come through this rebuild untouched.

Nothing here asserts anything about how the interface looks. Appearance is a
design decision and is allowed to change; these are contracts and are not.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

import pytest

import app as app_module

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "interface" / "static"
OUTPUTS = ROOT / "outputs"

DOCUMENTS = {
    "/": "index.html",
    "/run": "run.html",
    "/library": "library.html",
}

# The two documents served under a path segment rather than at a fixed address.
# Both read their own id back off the URL and fetch what they need, so the same
# bytes are served whatever the id is.
ADDRESSED = {
    "/library/Nike (Mind 001).json": "report.html",
    "/brand/preview-month-00000000": "brand.html",
    "/brand/preview-month-00000000/aaaaaaaaaaa": "report.html",
}


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def report_names() -> list[str]:
    names = sorted(p.name for p in OUTPUTS.glob("*.json"))
    if not names:
        pytest.skip("no reports in outputs/")
    return names


# ------------------------------------------------------------------ documents

class TestTheFourDocuments:
    # /library is served through the caveat substitution rather than straight
    # off disk: it surfaces a facial-derived score for every run on the machine,
    # so the bias-caveat rule applies to it exactly as it does to one report.
    SUBSTITUTED = {"/library"}

    @pytest.mark.parametrize("path,document", DOCUMENTS.items())
    def test_each_route_serves_its_document(self, client, path, document):
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        served = response.get_data(as_text=True)
        on_disk = (STATIC / document).read_text(encoding="utf-8")
        if path in self.SUBSTITUTED:
            assert "<!--BP:CAVEATS-->" not in served, "the marker was not substituted"
            assert served.replace("\n", "") != on_disk.replace("\n", "")
        else:
            assert served == on_disk

    def test_a_report_url_serves_the_report_document(self, client, report_names):
        """
        Served bytes are report.html with the caveats substituted in.

        This used to assert byte-equality with the file on disk. That stopped
        being the rule on 12 Sep 2026: the route now substitutes the two caveat
        constants into the document's no-script core, so the bytes differ from
        the file by exactly that substitution and byte-equality would be
        asserting the old mechanism rather than the contract. What matters is
        that the report URL serves the report document and nothing else, which
        is what is checked here.
        """
        path = "/library/" + urllib.parse.quote(report_names[0])
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == "text/html"

        served = response.get_data(as_text=True)
        on_disk = (STATIC / "report.html").read_text(encoding="utf-8")

        # It is the report document: same head, same mount point, same script.
        assert "<title>Report &mdash; BrandPulse</title>" in served or "Report" in served
        assert "data-report" in served
        assert served.count("<main") == on_disk.count("<main") == 1

        # It differs from the file only by the substitution having happened.
        assert "<!--BP:CAVEATS-->" in on_disk, (
            "the document no longer carries the substitution point; if that is "
            "deliberate, this test and _caveat_block() go together"
        )
        assert "<!--BP:CAVEATS-->" not in served, "the marker was served raw"

    def test_the_bias_caveat_reaches_the_page_without_javascript(self, client, report_names):
        """
        The project requires BIAS_CAVEAT on every surface presenting a
        facial-derived score. Before 12 Sep 2026 it reached the report only
        through JavaScript, so with scripting disabled the disclosure was not
        merely hidden — it was absent from the document. Measured that day: the
        report page delivered 79 characters inside its main element and no
        caveat at all.

        Asserted against the served bytes, because that is the only form the
        guarantee has when no script runs.
        """
        from html import escape

        from pipeline.scorer import BIAS_CAVEAT, VOCAL_CAVEAT

        path = "/library/" + urllib.parse.quote(report_names[0])
        served = client.get(path).get_data(as_text=True)

        # escape() because both caveats cite "Buolamwini & Gebru" and the
        # ampersand cannot travel into HTML raw. Comparing the escaped form is
        # comparing what a reader is actually served.
        assert escape(BIAS_CAVEAT) in served, "the bias caveat is not in the served bytes"
        assert escape(VOCAL_CAVEAT) in served, "the vocal caveat is not in the served bytes"

    def test_the_caveats_are_not_copied_into_the_document(self):
        """
        One source of truth. If the text were written into report.html as well,
        the copy in the HTML is the one nobody re-reads when scorer.py changes.
        """
        from pipeline.scorer import BIAS_CAVEAT

        on_disk = (STATIC / "report.html").read_text(encoding="utf-8")
        assert BIAS_CAVEAT not in on_disk, (
            "the caveat has been hard-coded into the document; it must come "
            "from pipeline.scorer at serve time"
        )

    def test_an_unreadable_report_name_still_serves_the_document(self, client):
        """
        This route does not read the file — the document fetches it from
        /reports/<filename>, which is where the traversal check lives. Serving
        the same static document for any path segment is therefore safe: an
        unreadable name produces the page's own "not found" state, not a file
        read.
        """
        response = client.get("/library/" + urllib.parse.quote("../../etc/passwd"))
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert "passwd" not in response.get_data(as_text=True)

    def test_the_retired_addresses_still_redirect(self, client):
        assert client.get("/landing").status_code == 308
        assert client.get("/landing").headers["Location"] == "/"
        assert client.get("/app").status_code == 308
        assert client.get("/app").headers["Location"] == "/run"


class TestTheAssetsTheDocumentsLoad:
    def test_every_module_and_stylesheet_is_served(self, client):
        for document in {**DOCUMENTS, **ADDRESSED}.values():
            html = (STATIC / document).read_text(encoding="utf-8")
            import re
            for href in re.findall(r'(?:src|href)="(/static/assets/[^"]+)"', html):
                response = client.get(href)
                assert response.status_code == 200, f"{href} is not served"

    @pytest.mark.parametrize("font", [
        "archivo-var.woff2", "archivo-var-italic.woff2",
        "newsreader-var.woff2", "newsreader-var-italic.woff2",
    ])
    def test_every_font_is_served_from_this_origin(self, client, font):
        response = client.get(f"/static/fonts/{font}")
        assert response.status_code == 200
        assert response.mimetype in ("font/woff2", "application/octet-stream")

    def test_the_grain_tile_is_served(self, client):
        assert client.get("/static/grain.png").status_code == 200

    def test_the_frames_manifest_is_served(self, client):
        """
        A manifest is served, and is shaped as the interface expects.

        This used to assert which tool produced it. Two now can: the manifest is
        computed at request time by `frame_cache.live_manifest()`, so a video
        analysed after the build is not drawn as an absence, and the file
        `ui_build/build_frames.py` writes stays a valid fallback for anyone
        serving static/ without Flask. Asserting the producer tested neither
        property. Asserting the shape tests both, and additionally bites on a
        manifest that is served but empty or malformed.
        """
        response = client.get("/static/frames/manifest.json")
        if response.status_code == 404:
            pytest.skip("no frames derived")
        manifest = response.get_json()
        assert manifest["generated_by"]
        assert isinstance(manifest["videos"], dict)
        for video_id, entry in manifest["videos"].items():
            assert re.fullmatch(r"[A-Za-z0-9_\-]{11}", video_id), video_id
            assert entry["seconds"], f"{video_id} listed with no plate seconds"
            assert all(isinstance(second, int) for second in entry["seconds"])

    def test_every_second_the_manifest_offers_actually_resolves(self, client):
        """
        The one rule `ui/src/lib/frames.js` states, enforced end to end.

        "Never return a URL for a frame that was not derived. A broken image
        would read as 'the system saw nothing', which is a claim about the data
        rather than about the build, and those must not be confused."

        Sampled rather than exhaustive — 501 plates at ~0.1 s each would make
        this the slowest test in the suite for no extra signal.
        """
        response = client.get("/static/frames/manifest.json")
        if response.status_code == 404:
            pytest.skip("no frames derived")
        for video_id, entry in response.get_json()["videos"].items():
            seconds = entry["seconds"]
            for second in {seconds[0], seconds[len(seconds) // 2], seconds[-1]}:
                got = client.get(f"/static/frames/{video_id}/p/{second}.jpg")
                assert got.status_code == 200, f"{video_id} offered second {second}"
                assert got.mimetype == "image/jpeg"

    def test_a_derived_plate_is_served(self, client):
        manifest = STATIC / "frames" / "manifest.json"
        if not manifest.is_file():
            pytest.skip("no frames derived")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        video_id, entry = next(iter(data["videos"].items()))
        response = client.get(f"/static/frames/{video_id}/p/{entry['seconds'][0]}.jpg")
        assert response.status_code == 200
        assert response.mimetype == "image/jpeg"

    @pytest.mark.parametrize("attempt", [
        "/static/../app.py",
        "/static/frames/../../app.py",
        "/static/%2e%2e/app.py",
    ])
    def test_the_static_mount_refuses_to_leave_itself(self, client, attempt):
        """
        Frames are served by Flask's own static handler, which already refuses
        traversal. No second, weaker implementation of that guard is added.
        """
        response = client.get(attempt)
        assert response.status_code in (301, 308, 400, 403, 404)
        if response.status_code == 200:
            pytest.fail("the static mount served a file outside static/")


# ------------------------------------------------------- the frozen API contract

class TestTheReportsApiIsUnchanged:
    def test_the_listing_shape(self, client, report_names):
        response = client.get("/reports")
        assert response.status_code == 200
        body = response.get_json()
        assert isinstance(body, list) and body
        for entry in body:
            assert "filename" in entry
        assert {e["filename"] for e in body} == set(report_names)

    def test_one_report_comes_back_whole(self, client, report_names):
        response = client.get("/reports/" + urllib.parse.quote(report_names[0]))
        assert response.status_code == 200
        body = response.get_json()
        for key in ("video_url", "brand_name", "authenticity_score", "brand_health_score",
                    "segment_count", "flagged_segments", "comment_sentiment",
                    "bias_caveat", "all_comments", "all_segments"):
            assert key in body, f"{key} missing from the report payload"

    def test_an_unknown_report_is_a_404(self, client):
        assert client.get("/reports/nope.json").status_code == 404

    @pytest.mark.parametrize("attempt", [
        "..%2F..%2Fapp.py", "....//app.py", "%2e%2e%2fapp.py",
    ])
    def test_the_report_route_refuses_to_leave_outputs(self, client, attempt):
        response = client.get(f"/reports/{attempt}")
        assert response.status_code in (400, 404)
        assert "def " not in response.get_data(as_text=True)

    def test_the_evidence_file_is_served(self, client):
        response = client.get("/evidence/figures.json")
        assert response.status_code == 200
        assert response.get_json()["generated_by"] == "ui_evidence/extract_figures.py"


class TestTheAnalyseApiIsUnchanged:
    def test_active_reports_no_job(self, client):
        response = client.get("/analyse/active")
        assert response.status_code == 200
        assert "active" in response.get_json()

    @pytest.mark.parametrize("missing", ["video_url", "brand_name", "product_name"])
    def test_start_requires_every_field(self, client, missing):
        body = {"video_url": "https://youtu.be/abcdefghijk",
                "brand_name": "B", "product_name": "P"}
        del body[missing]
        response = client.post("/analyse/start", json=body)
        assert response.status_code == 400
        assert missing in response.get_json()["error"]

    def test_start_rejects_a_url_with_no_video_id(self, client):
        response = client.post("/analyse/start", json={
            "video_url": "https://example.com/not-a-video",
            "brand_name": "B", "product_name": "P"})
        assert response.status_code == 400
        assert "invalid video_url" in response.get_json()["error"]

    def test_start_refuses_to_overwrite_an_existing_report(self, client, report_names):
        """The 409 the interface has a designed state for."""
        from app import _report_filename
        existing = report_names[0]
        # reconstruct the brand/product that produced this filename
        base = existing[:-len(".json")]
        brand, _, rest = base.partition(" (")
        product = rest.rstrip(")")
        if _report_filename(brand, product) != existing:
            pytest.skip(f"cannot reconstruct {existing}")
        response = client.post("/analyse/start", json={
            "video_url": "https://youtu.be/abcdefghijk",
            "brand_name": brand, "product_name": product})
        assert response.status_code == 409
        assert "already exists" in response.get_json()["error"]

    def test_status_of_an_unknown_job_is_a_404(self, client):
        response = client.get("/analyse/status/deadbeef")
        assert response.status_code == 404
        assert response.get_json()["error"] == "unknown job_id"

    def test_cancelling_an_unknown_job_is_a_404(self, client):
        response = client.post("/analyse/cancel/deadbeef")
        assert response.status_code == 404

    def test_the_stage_list_is_the_one_the_interface_draws(self):
        """
        The backend defines four stages and the interface draws four lanes
        against them by INDEX, so the count is the contract.

        The wording is deliberately not: app.py's labels are internal
        (`Downloading video & analysing transcript/facial/vocal channels`) and
        the interface rewrites them for a reader, adding a `spoken` form with no
        HTML entities in it for the live region. Asserting string equality would
        force a log line and a sentence read aloud to be the same string, which
        they should not be. What must not drift is how many there are and which
        of them reach a network.
        """
        # Five since 23 Sep 2026: the written report is the fifth stage.
        assert len(app_module._STAGES) == 5
        source = (ROOT / "interface" / "ui" / "src" / "pages" / "run.js").read_text(encoding="utf-8")
        stages = source[source.index("const STAGES = ["):source.index("function setTitle(")]
        assert len(re.findall(r"\n    label:", stages)) == len(app_module._STAGES)
        assert len(re.findall(r"\n    spoken:", stages)) == len(app_module._STAGES)
        assert len(re.findall(r"\n    reaches:", stages)) == len(app_module._STAGES)


# ------------------------------------------------------------------- sweeps

class TestTheCombinedReportDocument:
    """
    /brand/<sweep_id>. Served like the report page: one static document for any
    id, which reads its own id back off the URL and fetches the sweep itself.
    """

    PATH = "/brand/preview-month-00000000"

    def test_any_sweep_id_serves_the_brand_document(self, client):
        response = client.get(self.PATH)
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        served = response.get_data(as_text=True)
        assert "data-sweep" in served
        assert served.count("<main") == 1

    def test_the_bias_caveat_reaches_it_without_javascript(self, client):
        """
        A combined score is the mean of five facial-derived ones, so the bias-caveat
        rule applies to this surface exactly as it does to a single report: the
        caveat must be in the served bytes, not injected by a script.
        """
        from html import escape

        from pipeline.scorer import BIAS_CAVEAT, VOCAL_CAVEAT

        served = client.get(self.PATH).get_data(as_text=True)
        assert escape(BIAS_CAVEAT) in served
        assert escape(VOCAL_CAVEAT) in served

    def test_the_caveats_are_not_copied_into_the_document(self):
        from pipeline.scorer import BIAS_CAVEAT

        on_disk = (STATIC / "brand.html").read_text(encoding="utf-8")
        assert "<!--BP:CAVEATS-->" in on_disk
        assert BIAS_CAVEAT not in on_disk, (
            "the caveat has been hard-coded into the document; it must come "
            "from pipeline.scorer at serve time"
        )

    def test_the_no_script_core_says_what_a_combined_score_is_not(self, client):
        """
        With no script this page is the only thing a reader gets, and a mean of
        five numbers with no qualification is exactly the misreading the whole
        design is arranged against.
        """
        # Whitespace-collapsed and tag-stripped: the statement has to be there,
        # but where the source happens to wrap a line is not a contract.
        raw = client.get(self.PATH).get_data(as_text=True)
        prose = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).lower()
        assert "not a measurement of the subject" in prose
        assert "too few to generalise" in prose
        assert "one controller model on one day" in prose
        assert "range" in prose, "the spread is not mentioned without a script"

    def test_a_member_of_a_sweep_has_its_own_address(self, client):
        """
        The gap this closed: a sweep writes five complete reports and, until this
        route existed, nothing could open one. The combined page listed them as
        rows that went nowhere, and /library/<filename> only ever reads
        outputs/*.json.
        """
        response = client.get(self.PATH + "/aaaaaaaaaaa")
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        served = response.get_data(as_text=True)
        assert "data-report" in served, "a member is shown by the report document"
        assert served.count("<main") == 1

    def test_the_member_address_does_not_collide_with_the_combined_one(self, client):
        """
        /library/<path:filename> accepts slashes, so a two-segment member address
        under /library would have been swallowed by it. These two must stay
        distinct documents.
        """
        combined = client.get(self.PATH).get_data(as_text=True)
        member = client.get(self.PATH + "/aaaaaaaaaaa").get_data(as_text=True)
        assert "data-sweep" in combined and "data-report" not in combined
        assert "data-report" in member and "data-sweep" not in member

    def test_the_bias_caveat_reaches_a_member_without_javascript(self, client):
        from html import escape

        from pipeline.scorer import BIAS_CAVEAT

        served = client.get(self.PATH + "/aaaaaaaaaaa").get_data(as_text=True)
        assert escape(BIAS_CAVEAT) in served

    def test_a_member_address_reads_no_file(self, client):
        """
        Neither id reaches the filesystem here. Both are validated where they are
        used, behind GET /sweeps/<id>/members/<id>.
        """
        response = client.get(
            "/brand/" + urllib.parse.quote("../../etc") + "/passwd______")
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert "root:" not in response.get_data(as_text=True)

    def test_an_unreadable_sweep_id_still_serves_the_document(self, client):
        """
        Like the report route, this one reads no file — the document fetches the
        sweep from /sweeps/<id>, which is where the path check lives.
        """
        response = client.get("/brand/" + urllib.parse.quote("../../etc/passwd"))
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert "passwd" not in response.get_data(as_text=True)


class TestTheSweepApi:
    def test_the_list_is_an_array(self, client):
        response = client.get("/sweeps")
        assert response.status_code == 200
        assert isinstance(response.get_json(), list)

    def test_an_unknown_sweep_is_not_found(self, client):
        response = client.get("/sweeps/nothing-month-00000000")
        assert response.status_code == 404
        assert "error" in response.get_json()

    @pytest.mark.parametrize("nasty", ["..", "../secrets", "a/b"])
    def test_a_sweep_id_cannot_traverse(self, client, nasty):
        response = client.get("/sweeps/" + urllib.parse.quote(nasty, safe=""))
        assert response.status_code in (400, 404)

    def test_a_member_needs_a_real_video_id(self, client):
        response = client.get("/sweeps/x-month-00000000/members/notanid")
        assert response.status_code == 400

    def test_an_absent_member_is_not_found(self, client):
        response = client.get("/sweeps/x-month-00000000/members/aaaaaaaaaaa")
        assert response.status_code == 404


class TestNoOtherSiteIsGrantedTheApi:
    """
    The interface is served by this app, so it never needs CORS. Until 26 Sep
    2026 every response carried `Access-Control-Allow-Origin: *` and preflights
    allowed DELETE, so any page open in the same browser could list the saved
    reports and delete them while the server ran.
    """

    @pytest.mark.parametrize("path,method", [
        ("/reports", "GET"), ("/reports/x.json", "DELETE"), ("/sweeps/x-month-00000000", "DELETE"),
        ("/analyse/start", "POST"), ("/sweep/start", "POST"), ("/analyse/cancel/abc", "POST"),
    ])
    def test_a_cross_origin_preflight_is_not_granted(self, client, path, method):
        response = client.options(path, headers={
            "Origin": "https://example.org", "Access-Control-Request-Method": method})
        assert "Access-Control-Allow-Origin" not in response.headers
        assert "Access-Control-Allow-Methods" not in response.headers

    def test_a_cross_origin_read_carries_no_permission(self, client):
        response = client.get("/reports", headers={"Origin": "https://example.org"})
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_the_api_still_answers_the_interface_itself(self, client):
        assert client.get("/reports").status_code == 200
        assert client.get("/sweeps").status_code == 200


class TestTheAccessibilityStatementIsServed:
    """INCLUSIVE_DESIGN.md I4: the statement is a real document at its address."""

    def test_it_is_served_as_html(self, client):
        response = client.get("/accessibility")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "<h1" in body and "partially conforms" in body
