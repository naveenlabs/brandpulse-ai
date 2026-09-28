"""
test_ui_documents.py — the built interface in static/.

Written 11 Sep 2026 with the third interface. `static/` is the committed output
of `npm run build` in `ui/`, and it is what a marker actually gets: `flask run`
serves this directory and nothing else is involved.

What this file guards is the difference between the source being right and the
SHIPPED ARTEFACT being right. In particular the one claim the build itself can
break: that a page describing data sovereignty makes no request off this
machine to render itself.

No browser, no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "interface" / "static"
DOCUMENTS = ["index.html", "run.html", "library.html", "report.html",
             "brand.html"]

# Two families, two speakers. Archivo is the instrument and Newsreader is the
# human; nothing else speaks, and there is deliberately no monospace family.
# See ui_build/fetch_fonts.py for why each one is here.
FONTS = [
    "archivo-var.woff2", "archivo-var-italic.woff2",
    "newsreader-var.woff2", "newsreader-var-italic.woff2",
]
LICENCES = [
    "OFL-Archivo.txt", "OFL-Newsreader.txt",
]

# Hosts a front end reaches for by habit. None may appear anywhere in the build.
FOREIGN_HOSTS = [
    "fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com", "unpkg.com", "esm.sh", "code.jquery.com",
    "googleapis.com", "gstatic.com", "googletagmanager.com",
    "google-analytics.com", "polyfill.io", "skypack.dev", "jsdelivr.net",
]


@pytest.fixture(scope="module")
def documents() -> dict[str, str]:
    return {name: (STATIC / name).read_text(encoding="utf-8") for name in DOCUMENTS}


@pytest.fixture(scope="module")
def built_text() -> dict[str, str]:
    """Every text file the build emits: documents, stylesheets and modules."""
    out = {}
    for path in sorted(STATIC.rglob("*")):
        if path.suffix.lower() in {".html", ".css", ".js", ".json", ".txt"} and path.is_file():
            out[str(path.relative_to(STATIC))] = path.read_text(encoding="utf-8", errors="replace")
    return out


class TestTheBuildExists:
    def test_all_four_documents_were_emitted(self):
        missing = [name for name in DOCUMENTS if not (STATIC / name).is_file()]
        assert not missing, f"missing documents: {missing} — run `npm run build` in ui/"

    def test_each_document_loads_a_module(self, documents):
        for name, html in documents.items():
            assert re.search(r'<script type="module"[^>]+src="/static/assets/[^"]+\.js"', html), \
                f"{name} loads no module"

    def test_each_document_loads_a_stylesheet(self, documents):
        for name, html in documents.items():
            assert re.search(r'<link rel="stylesheet"[^>]+href="/static/assets/[^"]+\.css"', html), \
                f"{name} loads no stylesheet"

    def test_every_referenced_asset_is_on_disk(self, documents):
        missing = []
        for name, html in documents.items():
            for href in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
                if not (STATIC / href[len("/static/"):]).is_file():
                    missing.append((name, href))
        assert not missing, f"referenced but absent: {missing}"


class TestNothingLeavesThisMachine:
    """
    The product's central claim is that no pipeline data leaves the machine.
    A page that fetched a typeface, a script or a beacon from elsewhere would
    contradict that claim on every load, in front of a marker, while
    describing data sovereignty.
    """

    @pytest.mark.parametrize("host", FOREIGN_HOSTS)
    def test_no_built_file_names_a_foreign_host(self, built_text, host):
        offenders = [name for name, text in built_text.items() if host in text]
        assert not offenders, f"{host} appears in {offenders}"

    # Every absolute URL allowed to exist as a STRING in the build, and why.
    # None of these is fetched; that is proven separately and in the only way
    # it can be proven, by watching the network in a real browser
    # (ui_evidence/verify_ui.py, "zero foreign requests"). A string scan cannot
    # tell an attribution notice from a request once the bundle is minified,
    # so this test polices the inventory and that one polices the behaviour.
    ALLOWED_URL_STRINGS = {
        "https://www.youtube.com/watch?v=":
            "an input's placeholder on /run. Shown to a reader so they know what "
            "shape of address to paste; the interface never requests it.",
        "https://gsap.com": "GSAP's own attribution. Its licence forbids "
                            "removing proprietary notices, so it must stay.",
        "https://gsap.com/standard-license": "same notice, the licence link.",
        "https://www.youtube.com/watch?v=...": "the URL field's placeholder — "
                                               "copy telling a user what to type.",
        "http://localhost:11434": "copy, naming where the local model runs.",
        "http://www.w3.org/2000/svg": "an XML namespace, never dereferenced.",
        "http://www.w3.org/1999/xhtml": "an XML namespace GSAP uses when it "
                                        "creates elements; never dereferenced.",
        "https://jcgt.org/published/0007/04/01/":
            "a citation (Heitz 2018, GGX visible-normal sampling) in a comment "
            "inside three.js's GLSL shader source; compiled on the GPU, never "
            "requested.",
    }

    def test_every_absolute_url_in_the_build_is_a_known_string(self, built_text):
        offenders = []
        for name, text in built_text.items():
            if name.startswith("fonts/OFL-"):
                continue          # the SIL licence text cites its own URLs
            for url in re.findall(r"https?://[^\s\"'`)>]+", text):
                if not any(url.startswith(allowed) for allowed in self.ALLOWED_URL_STRINGS):
                    offenders.append((name, url[:80]))
        assert not offenders, (
            f"unrecognised absolute URLs in the build: {offenders}. "
            "Add it to ALLOWED_URL_STRINGS with a reason, or remove it.")

    def test_the_allowlist_documents_a_reason_for_each_entry(self):
        for url, reason in self.ALLOWED_URL_STRINGS.items():
            assert len(reason) > 20, f"{url} has no stated reason"

    def test_the_favicon_is_inline_rather_than_a_request(self, documents):
        for name, html in documents.items():
            icon = re.search(r'<link rel="icon" href="([^"]+)"', html)
            assert icon, f"{name} has no icon"
            assert icon.group(1).startswith("data:"), f"{name} fetches its icon"

    def test_every_font_file_is_committed(self):
        missing = [f for f in FONTS if not (STATIC / "fonts" / f).is_file()]
        assert not missing, f"missing fonts: {missing}"

    def test_every_font_ships_with_its_licence(self):
        """Redistributing an OFL font without its licence text violates it."""
        for licence in LICENCES:
            path = STATIC / "fonts" / licence
            assert path.is_file(), f"missing {licence}"
            assert "SIL OPEN FONT LICENSE" in path.read_text(encoding="utf-8").upper()

    def test_the_grain_tile_is_a_committed_file_not_a_filter(self):
        assert (STATIC / "grain.png").is_file()

    def test_the_fonts_are_referenced_from_this_origin(self, built_text):
        css = "\n".join(t for n, t in built_text.items() if n.endswith(".css"))
        faces = re.findall(r"url\((/static/fonts/[^)]+)\)", css)
        assert len(faces) >= len(FONTS), "not every face is declared"


class TestTheDocumentsAreWellFormed:
    def test_each_declares_a_language(self, documents):
        for name, html in documents.items():
            assert '<html lang="en"' in html, f"{name} has no lang"

    def test_each_declares_a_viewport(self, documents):
        for name, html in documents.items():
            assert 'name="viewport"' in html and "width=device-width" in html

    def test_each_has_a_title_and_a_description(self, documents):
        for name, html in documents.items():
            assert re.search(r"<title>[^<]{6,}</title>", html), f"{name} has no title"
            assert re.search(r'<meta name="description" content="[^"]{20,}"', html), \
                f"{name} has no description"

    def test_each_offers_a_skip_link_as_the_first_focusable_thing(self, documents):
        """
        The FIRST focusable element must be the skip link itself. Checking that
        one merely appears near the start is not the same assertion, and does
        not fail when something else is put in front of it — which is how this
        test read until ui_evidence/verify_tests_bite.py showed it did not bite.
        """
        for name, html in documents.items():
            body = html[html.index("<body>"):]
            assert 'class="skip-link"' in body, f"{name} has no skip link"
            first = re.search(r"<(?:a|button|input|select|textarea)\b[^>]*>", body)
            assert first, f"{name} has no focusable element at all"
            assert "skip-link" in first.group(0), (
                f"{name}'s first focusable element is {first.group(0)[:60]!r}, "
                "not the skip link")

    def test_each_has_exactly_one_main_landmark(self, documents):
        for name, html in documents.items():
            assert html.count("<main") == 1, f"{name} has {html.count('<main')} mains"

    def test_the_theme_is_set_before_first_paint(self, documents):
        """
        An external script would be a second request, and the page would flash
        the wrong ground while it loaded.
        """
        for name, html in documents.items():
            head = html[:html.index("</head>")]
            assert "brandpulse-theme" in head
            assert head.index("<script>") < head.index("<link rel=\"stylesheet\"") \
                if "<link rel=\"stylesheet\"" in head else True

    def test_the_theme_script_falls_back_when_storage_throws(self, documents):
        """A private window can throw on localStorage; the page must still paint."""
        for name, html in documents.items():
            assert "catch (e) {}" in html
            assert "prefers-color-scheme" in html

    def test_each_document_starts_hidden_only_when_js_is_present(self, documents):
        for name, html in documents.items():
            assert 'classList.add("js")' in html


class TestTheDerivedImagery:
    @staticmethod
    @pytest.fixture(scope="class")
    def manifest() -> dict:
        path = STATIC / "frames" / "manifest.json"
        if not path.is_file():
            pytest.skip("no frames derived — run ui_build/build_frames.py")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_it_says_where_it_came_from(self, manifest):
        assert manifest["generated_by"] == "ui_build/build_frames.py"
        assert "nothing is fetched" in manifest["note"]

    def test_every_second_it_advertises_is_on_disk(self, manifest):
        missing = []
        for video_id, entry in manifest["videos"].items():
            for second in entry["seconds"][:12]:
                if not (STATIC / "frames" / video_id / "p" / f"{second}.jpg").is_file():
                    missing.append((video_id, second))
            for second in (entry.get("window_seconds") or [])[:12]:
                if not (STATIC / "frames" / video_id / "w" / f"{second}.jpg").is_file():
                    missing.append((video_id, second, "window"))
        assert not missing, f"manifest advertises absent frames: {missing}"

    def test_every_video_has_a_sprite(self, manifest):
        for video_id in manifest["videos"]:
            assert (STATIC / "frames" / video_id / "strip.jpg").is_file()

    def test_the_sprite_geometry_covers_every_tile(self, manifest):
        for video_id, entry in manifest["videos"].items():
            strip = entry["strip"]
            assert strip["cols"] * strip["rows"] >= len(entry["seconds"]), video_id

    def test_no_raw_frame_directory_was_copied_into_the_build(self):
        """data/ is 2 GB and gitignored; only derived sizes may ship."""
        for path in (STATIC / "frames").rglob("frame_*.jpg"):
            pytest.fail(f"a raw pipeline frame reached the build: {path}")


# ---------------------------------------------------------- the no-script core

class TestTheDocumentsReadWithoutScripting:
    """
    The interface is client-rendered, and until 12 Sep 2026 that meant it had no
    content at all without JavaScript.

    Measured that day with script execution disabled, before this existed:

        page        <h1>   chars in <main>   bias caveat
        overview     0            0              absent
        run          0            0              absent
        library      0           32              absent
        report       0           79              absent

    A locked-down machine, a text-only browser, or one parse error in the bundle
    produced a blank page — and the requirement that BIAS_CAVEAT appear
    wherever a facial-derived score is shown was met only while a script ran.

    Each document now carries a readable core inside its main element, which the
    page module replaces on render. These tests read the built files, so they
    guard the artefact a marker is actually served.
    """

    def test_each_carries_a_fallback_core(self, documents):
        for name, html in documents.items():
            assert "data-fallback" in html, f"{name} has no no-script core"

    def test_each_fallback_leads_with_a_heading(self, documents):
        """
        Without this the page has no <h1> at all when scripting is off, which
        is what was measured on all four documents.
        """
        for name, html in documents.items():
            start = html.index("data-fallback")
            assert "<h1>" in html[start:start + 2000], (
                f"{name}'s no-script core does not open with a heading")

    def test_each_fallback_says_something(self, documents):
        """
        A stub would satisfy the heading test and still leave a reader with
        nothing. 400 characters is well under the shortest core (run, ~780) and
        well over a placeholder.
        """
        for name, html in documents.items():
            start = html.index("data-fallback")
            body = re.sub(r"<[^>]+>", " ", html[start:html.index("</main>", start)])
            body = re.sub(r"\s+", " ", body).strip()
            assert len(body) > 400, f"{name}'s no-script core is {len(body)} chars"

    def test_each_fallback_offers_a_way_onward(self, documents):
        """A reader who cannot run the interface still needs to navigate."""
        for name, html in documents.items():
            core = html[html.index("data-fallback"):html.index("</main>", html.index("data-fallback"))]
            assert 'href="/' in core, f"{name}'s no-script core has no link out"

    def test_the_two_states_are_mutually_exclusive(self):
        """
        [data-boot] claims something is loading, which is only true while a
        script is running to do the loading. Showing it without scripting is a
        page that claims to be busy forever.
        """
        css = re.sub(r"\s+", "", _bundled_css())
        assert ".js[data-fallback]{display:none" in css, (
            "the no-script core is not hidden when scripting is live")
        assert "html:not(.js)[data-boot]{display:none" in css, (
            "the boot state is not hidden when scripting is off")

    def test_the_fallback_returns_if_the_bundle_never_runs(self, documents):
        """
        The `js` class is added by an inline script that runs even when the
        module bundle is blocked, 404s, or throws on parse — so the class alone
        would hide the core in exactly the case it is needed. A timer in each
        document un-marks the document, and lib/chrome.js cancels it, which is
        reached if and only if the bundle executed.
        """
        for name, html in documents.items():
            assert "__bpFallback" in html, f"{name} sets no fallback timer"
            assert "classList.remove(\"js\")" in html, (
                f"{name}'s timer does not restore the no-script core")

    def test_the_report_core_carries_a_substitution_point_for_the_caveats(self):
        """
        The caveats are not written into the document — Flask substitutes them
        from pipeline.scorer at serve time, so the text a reader sees without
        scripting cannot drift from the text attached to every report. The
        serving half is asserted in tests/test_ui_routes.py.
        """
        html = (STATIC / "report.html").read_text(encoding="utf-8")
        assert "<!--BP:CAVEATS-->" in html


def _bundled_css() -> str:
    """Every built stylesheet, concatenated. Vite hashes the filenames."""
    return "\n".join(
        p.read_text(encoding="utf-8") for p in (STATIC / "assets").glob("*.css")
    )
