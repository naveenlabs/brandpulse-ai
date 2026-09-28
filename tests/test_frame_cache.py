"""
test_frame_cache.py — deriving the report page's imagery at run time.

Written 19 Sep 2026, with `frame_cache.py`.

Scope: the module that closes the gap between what `ui_build/build_frames.py`
derived before the build and what a report saved after it needs. The defect it
fixes was visible rather than subtle — a video analysed after the interface
shipped rendered with the absence hatch in every frame slot, which the page
draws to mean "the facial channel had no reading here". That is a claim about
the data. It was in fact a claim about the build.

Two properties matter more than the rest and are tested first:

  - An image derived here is byte-identical to one derived by build_frames.py.
    If the two drift, a report changes appearance depending on which path
    produced its frames, and the pre-built imagery stops being a valid cache.
  - A second is offered in the manifest only when it will actually resolve.
    This is the rule ui/src/lib/frames.js states in its header, and it is the
    reason the absence hatch can be trusted.

Filesystem-touching tests build their own tree under tmp_path and point the
module at it. Nothing here writes into the real data/, outputs/ or static/.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from pipeline import frame_cache

ROOT = Path(__file__).resolve().parent.parent


def _load_build_frames():
    """
    Import ui_build/build_frames.py by path.

    It is a build-time script rather than a package module, so it cannot be
    imported normally. Loading it here is what lets the two derivations be
    compared rather than assumed equal.
    """
    path = ROOT / "interface" / "ui_build" / "build_frames.py"
    if not path.is_file():
        pytest.skip("ui_build/build_frames.py not present")
    spec = importlib.util.spec_from_file_location("_build_frames", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_frames():
    return _load_build_frames()


def _jpeg(path: Path, size: tuple[int, int] = (1920, 1080)) -> None:
    """
    A real JPEG with structure in it.

    Deliberately not a flat colour: a uniform image survives two different
    resize paths identically, so it would pass the byte-equality test even if
    the two derivations had genuinely drifted.
    """
    Image = pytest.importorskip("PIL").Image
    image = Image.new("RGB", size)
    pixels = image.load()
    for x in range(0, size[0], 7):
        for y in range(0, size[1], 5):
            pixels[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y) * 2) % 256)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


# ── The two derivations must not drift ───────────────────────────────────────

class TestTheParametersMatchTheBuilder:
    """
    frame_cache must not import from the build-time ui_build/ folder (a Flask
    process cannot depend on it), so since 26 Sep 2026 build_frames imports
    frame_cache's values instead of keeping copies. These stay, so that a copy
    reintroduced on either side is caught.
    """

    def test_plate_width_and_quality_match(self, build_frames):
        assert frame_cache.PLATE_WIDTH == build_frames.PLATE_WIDTH
        assert frame_cache.PLATE_QUALITY == build_frames.PLATE_QUALITY

    def test_window_width_and_quality_match(self, build_frames):
        assert frame_cache.WINDOW_WIDTH == build_frames.WINDOW_WIDTH
        assert frame_cache.WINDOW_QUALITY == build_frames.WINDOW_QUALITY

    def test_the_source_frame_naming_matches(self, build_frames, tmp_path, monkeypatch):
        """Both must look for frame_0000.jpg upward, the number being the second."""
        monkeypatch.setattr(frame_cache, "DATA", tmp_path)
        monkeypatch.setattr(build_frames, "DATA", tmp_path)
        _jpeg(tmp_path / "vid00000001" / "frames" / "frame_0007.jpg")
        assert frame_cache.source_frame("vid00000001", 7) is not None
        assert build_frames.source_frame("vid00000001", 7) is not None
        assert frame_cache.source_frame("vid00000001", 8) is None


class TestADerivedImageIsIdenticalToAPreBuiltOne:
    def test_a_plate_derived_here_matches_the_builders_bytes(
        self, build_frames, tmp_path, monkeypatch
    ):
        Image = pytest.importorskip("PIL").Image
        source = tmp_path / "src.jpg"
        _jpeg(source)

        # frame_cache's derivation, via the real code path
        monkeypatch.setattr(frame_cache, "DATA", tmp_path / "data")
        monkeypatch.setattr(frame_cache, "SERVED", tmp_path / "served")
        frames_dir = tmp_path / "data" / "vid00000001" / "frames"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0003.jpg").write_bytes(source.read_bytes())
        mine = frame_cache.derive("vid00000001", "p", 3)
        assert mine is not None

        # the builder's derivation, inlined exactly as build_video performs it
        theirs = tmp_path / "theirs.jpg"
        with Image.open(source) as image:
            image = image.convert("RGB")
            ratio = image.height / image.width
            image.resize(
                (build_frames.PLATE_WIDTH,
                 max(1, round(build_frames.PLATE_WIDTH * ratio))),
                Image.LANCZOS,
            ).save(theirs, "JPEG", quality=build_frames.PLATE_QUALITY,
                   optimize=True, progressive=True)

        assert mine.read_bytes() == theirs.read_bytes()


# ── Reading a report ─────────────────────────────────────────────────────────

class TestReadingAReport:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=PjAyUhf52D0", "PjAyUhf52D0"),
        ("https://youtu.be/PjAyUhf52D0?si=gXb22wRXAcbAqz-X", "PjAyUhf52D0"),
        ("https://www.youtube.com/shorts/PjAyUhf52D0", "PjAyUhf52D0"),
        ("https://example.com/not-a-video", None),
        ("", None),
    ])
    def test_the_video_id_is_read_from_the_url(self, url, expected):
        assert frame_cache.video_id_of({"video_url": url}) == expected

    def test_midpoints_match_the_builder(self, build_frames):
        report = {"all_segments": [
            {"start_s": 0, "end_s": 10},
            {"start_s": 10.4, "end_s": 21.6},
            {"start_s": 30, "end_s": 30},
        ]}
        assert frame_cache.midpoint_seconds(report) == \
               build_frames.midpoint_seconds(report)

    def test_window_seconds_match_the_builder(self, build_frames):
        report = {"all_segments": [
            {"start_s": 0, "end_s": 3, "flagged": True},
            {"start_s": 10, "end_s": 12, "flagged": False},
        ]}
        assert frame_cache.window_seconds(report) == \
               build_frames.window_seconds(report)

    def test_a_segment_with_no_timing_is_skipped_not_guessed(self):
        report = {"all_segments": [{"start_s": None, "end_s": 4},
                                   {"start_s": 6, "end_s": 8}]}
        assert frame_cache.midpoint_seconds(report) == [7]


# ── Deriving ─────────────────────────────────────────────────────────────────

class TestDeriving:
    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frame_cache, "DATA", tmp_path / "data")
        monkeypatch.setattr(frame_cache, "SERVED", tmp_path / "served")
        monkeypatch.setattr(frame_cache, "OUTPUTS", tmp_path / "outputs")
        frames = tmp_path / "data" / "vid00000001" / "frames"
        for second in (0, 1, 2, 5):
            _jpeg(frames / f"frame_{second:04d}.jpg")
        return tmp_path

    def test_a_missing_source_returns_none_rather_than_a_placeholder(self, tree):
        assert frame_cache.derive("vid00000001", "p", 99) is None

    def test_an_unknown_size_is_refused(self, tree):
        assert frame_cache.derive("vid00000001", "x", 0) is None

    def test_deriving_twice_reuses_the_first_file(self, tree):
        first = frame_cache.derive("vid00000001", "p", 1)
        stamp = first.stat().st_mtime_ns
        second = frame_cache.derive("vid00000001", "p", 1)
        assert second == first
        assert second.stat().st_mtime_ns == stamp, "re-derived instead of reusing"

    def test_no_temporary_file_is_left_behind(self, tree):
        frame_cache.derive("vid00000001", "p", 1)
        assert not list((tree / "served").rglob("*.tmp"))

    def test_the_two_sizes_differ_as_configured(self, tree):
        Image = pytest.importorskip("PIL").Image
        with Image.open(frame_cache.derive("vid00000001", "p", 0)) as plate:
            assert plate.width == frame_cache.PLATE_WIDTH
        with Image.open(frame_cache.derive("vid00000001", "w", 0)) as window:
            assert window.width == frame_cache.WINDOW_WIDTH


class TestWarming:
    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frame_cache, "DATA", tmp_path / "data")
        monkeypatch.setattr(frame_cache, "SERVED", tmp_path / "served")
        frames = tmp_path / "data" / "vid00000001" / "frames"
        for second in range(0, 12):
            _jpeg(frames / f"frame_{second:04d}.jpg")
        return tmp_path

    REPORT = {
        "video_url": "https://youtu.be/vid00000001",
        "all_segments": [
            {"start_s": 0, "end_s": 4, "flagged": True},
            {"start_s": 4, "end_s": 10, "flagged": False},
        ],
    }

    def test_warming_derives_plates_and_window_frames(self, tree):
        made = frame_cache.warm(self.REPORT)
        assert made > 0
        assert (tree / "served" / "vid00000001" / "p").is_dir()
        assert (tree / "served" / "vid00000001" / "w").is_dir()

    def test_a_midpoint_is_never_also_stored_as_a_window_frame(self, tree):
        frame_cache.warm(self.REPORT)
        plates = {p.stem for p in (tree / "served" / "vid00000001" / "p").glob("*.jpg")}
        windows = {p.stem for p in (tree / "served" / "vid00000001" / "w").glob("*.jpg")}
        assert not (plates & windows), "the same second stored at two sizes"

    def test_warming_a_report_with_no_video_id_is_a_no_op(self, tree):
        assert frame_cache.warm({"video_url": "nonsense", "all_segments": []}) == 0

    def test_warming_never_raises_on_a_malformed_report(self, tree):
        """Imagery is not worth failing a finished analysis over."""
        assert frame_cache.warm({}) == 0
        assert frame_cache.warm({"video_url": "https://youtu.be/vid00000001",
                                 "all_segments": [{"start_s": "x", "end_s": None}]}) == 0


# ── The manifest ─────────────────────────────────────────────────────────────

class TestTheManifest:
    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frame_cache, "DATA", tmp_path / "data")
        monkeypatch.setattr(frame_cache, "SERVED", tmp_path / "served")
        monkeypatch.setattr(frame_cache, "OUTPUTS", tmp_path / "outputs")
        (tmp_path / "outputs").mkdir()
        frames = tmp_path / "data" / "vid00000001" / "frames"
        for second in range(0, 20):
            _jpeg(frames / f"frame_{second:04d}.jpg")
        return tmp_path

    def _write(self, tree, name, segments):
        (tree / "outputs" / name).write_text(json.dumps({
            "video_url": "https://youtu.be/vid00000001",
            "all_segments": segments,
        }), encoding="utf-8")

    def test_a_video_appears_from_its_source_frames_alone(self, tree):
        """No derivation has happened yet; the manifest must still offer it."""
        self._write(tree, "a.json", [{"start_s": 0, "end_s": 4}])
        videos = frame_cache.live_manifest()["videos"]
        assert "vid00000001" in videos
        assert videos["vid00000001"]["seconds"] == [2]

    def test_seconds_with_no_source_frame_are_not_offered(self, tree):
        """
        The rule frames.js states: never offer a URL for a frame that does not
        exist. Second 500 has no frame on disk, so it must be absent from the
        manifest — which is what makes the page draw the hatch instead.
        """
        self._write(tree, "a.json", [{"start_s": 0, "end_s": 4},
                                     {"start_s": 999, "end_s": 1001}])
        entry = frame_cache.live_manifest()["videos"]["vid00000001"]
        assert 2 in entry["seconds"]
        assert 1000 not in entry["seconds"]

    def test_reports_sharing_a_video_are_unioned_not_overwritten(self, tree):
        """
        Six of the nine shipped reports are runs of one video and they do not
        flag the same segments. Taking the first report's view would hide window
        frames that exist, and the page would draw absence over a real frame.
        """
        self._write(tree, "a.json", [{"start_s": 0, "end_s": 4, "flagged": True}])
        self._write(tree, "b.json", [{"start_s": 10, "end_s": 14, "flagged": True}])
        entry = frame_cache.live_manifest()["videos"]["vid00000001"]
        assert 2 in entry["seconds"] and 12 in entry["seconds"]
        assert {0, 1, 3, 4} <= set(entry["window_seconds"])
        assert {10, 11, 13, 14} <= set(entry["window_seconds"])

    def test_a_video_with_no_frames_at_all_is_omitted(self, tree):
        (tree / "outputs" / "c.json").write_text(json.dumps({
            "video_url": "https://youtu.be/vid00000002",
            "all_segments": [{"start_s": 0, "end_s": 4}],
        }), encoding="utf-8")
        assert "vid00000002" not in frame_cache.live_manifest()["videos"]

    def test_an_unreadable_report_does_not_sink_the_manifest(self, tree):
        self._write(tree, "a.json", [{"start_s": 0, "end_s": 4}])
        (tree / "outputs" / "broken.json").write_text("{not json", encoding="utf-8")
        assert "vid00000001" in frame_cache.live_manifest()["videos"]

    def test_the_window_never_repeats_a_plate_second(self, tree):
        self._write(tree, "a.json", [{"start_s": 0, "end_s": 4, "flagged": True}])
        entry = frame_cache.live_manifest()["videos"]["vid00000001"]
        assert not (set(entry["seconds"]) & set(entry["window_seconds"]))


# ── The sprite sheet ─────────────────────────────────────────────────────────

class TestTheSprite:
    """
    A video warmed at run time must end up as complete as one the builder
    produced. This was found by `test_ui_documents.py::test_every_video_has_a_
    sprite` failing after a real analysis: warming derived every plate and every
    window frame and no sprite, so the manifest declared a video whose strip.jpg
    did not exist.
    """

    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frame_cache, "DATA", tmp_path / "data")
        monkeypatch.setattr(frame_cache, "SERVED", tmp_path / "served")
        monkeypatch.setattr(frame_cache, "OUTPUTS", tmp_path / "outputs")
        frames = tmp_path / "data" / "vid00000001" / "frames"
        for second in range(0, 26):
            _jpeg(frames / f"frame_{second:04d}.jpg")
        return tmp_path

    REPORT = {
        "video_url": "https://youtu.be/vid00000001",
        "all_segments": [{"start_s": i * 2, "end_s": i * 2 + 2} for i in range(10)],
    }

    def test_constants_match_the_builder(self, build_frames):
        assert frame_cache.TILE_W == build_frames.TILE_W
        assert frame_cache.STRIP_COLS == build_frames.STRIP_COLS
        assert frame_cache.STRIP_QUALITY == build_frames.STRIP_QUALITY

    def test_warming_leaves_a_sprite_behind(self, tree):
        frame_cache.warm(self.REPORT)
        assert frame_cache.strip_path("vid00000001").is_file()

    def test_the_geometry_covers_every_tile(self, tree):
        """The contract `test_ui_documents.py` checks: cols * rows >= seconds."""
        geometry = frame_cache.build_strip("vid00000001", list(range(10)))
        assert geometry["cols"] * geometry["rows"] >= 10

    def test_the_sheet_is_as_wide_as_a_full_row_and_as_tall_as_its_rows(self, tree):
        geometry = frame_cache.build_strip("vid00000001", list(range(10)))
        assert geometry["w"] == frame_cache.TILE_W * frame_cache.STRIP_COLS
        assert geometry["h"] == geometry["tile"]["h"] * geometry["rows"]

    def test_a_second_call_reuses_the_sheet_rather_than_redrawing_it(self, tree):
        first = frame_cache.build_strip("vid00000001", list(range(10)))
        stamp = frame_cache.strip_path("vid00000001").stat().st_mtime_ns
        again = frame_cache.build_strip("vid00000001", list(range(10)))
        assert again["rows"] == first["rows"]
        assert frame_cache.strip_path("vid00000001").stat().st_mtime_ns == stamp

    def test_no_source_frames_means_no_sprite_rather_than_a_blank_one(self, tree):
        assert frame_cache.build_strip("vid00000002", [0, 1, 2]) is None
        assert not frame_cache.strip_path("vid00000002").exists()

    def test_no_temporary_file_survives(self, tree):
        frame_cache.build_strip("vid00000001", list(range(10)))
        assert not list((tree / "served").rglob("*.tmp"))

    def test_the_manifest_declares_the_sprite_only_once_it_exists(self, tree):
        (tree / "outputs").mkdir(exist_ok=True)
        (tree / "outputs" / "a.json").write_text(json.dumps(self.REPORT), encoding="utf-8")

        before = frame_cache.live_manifest()["videos"]["vid00000001"]
        assert "strip" not in before, "advertised a sprite that is not on disk"

        frame_cache.warm(self.REPORT)
        after = frame_cache.live_manifest()["videos"]["vid00000001"]
        assert after["strip"]["cols"] == frame_cache.STRIP_COLS
        assert after["tile"]["w"] == frame_cache.TILE_W


class TestSweepMembersAreSeenToo:
    """
    A sweep's member reports live under `outputs/sweeps/<id>/members/`, which
    `outputs/*.json` does not reach — that is the whole point of putting them
    there, since `extract_figures.py` globs the same pattern and the corpus
    figures feed 254 verified claims in the final report.

    The manifest is the one place that has to see both. `warm()` derives a
    member's frames like any other report's, and a manifest that did not list
    them would have the combined page draw the absence hatch over frames that
    are sitting on disk — the exact defect this module exists to remove, one
    directory further down. Found by checking a real sweep's videos against the
    manifest while that sweep was still running: three of its five had no entry.
    """

    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frame_cache, "DATA", tmp_path / "data")
        monkeypatch.setattr(frame_cache, "SERVED", tmp_path / "served")
        monkeypatch.setattr(frame_cache, "OUTPUTS", tmp_path / "outputs")
        for video in ("vid00000001", "vid00000002"):
            frames = tmp_path / "data" / video / "frames"
            for second in range(0, 12):
                _jpeg(frames / f"frame_{second:04d}.jpg")
        (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def _report(self, tree, path, video):
        payload = {"video_url": f"https://youtu.be/{video}",
                   "all_segments": [{"start_s": 0, "end_s": 4},
                                    {"start_s": 4, "end_s": 8}]}
        target = tree / "outputs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")

    def test_a_sweep_member_gets_a_manifest_entry(self, tree):
        self._report(tree, "sweeps/x-month-abcd1234/members/vid00000002.json",
                     "vid00000002")
        videos = frame_cache.live_manifest()["videos"]
        assert "vid00000002" in videos, "a sweep member's frames are unreachable"

    def test_single_runs_and_sweep_members_appear_together(self, tree):
        self._report(tree, "single.json", "vid00000001")
        self._report(tree, "sweeps/x-month-abcd1234/members/vid00000002.json",
                     "vid00000002")
        videos = frame_cache.live_manifest()["videos"]
        assert set(videos) == {"vid00000001", "vid00000002"}

    def test_a_sweep_directory_with_no_members_is_harmless(self, tree):
        (tree / "outputs" / "sweeps" / "empty-month-abcd1234").mkdir(parents=True)
        self._report(tree, "single.json", "vid00000001")
        assert set(frame_cache.live_manifest()["videos"]) == {"vid00000001"}

    def test_the_sweep_record_itself_is_not_read_as_a_report(self, tree):
        """
        `sweep.json` sits beside `members/` and has no `video_url`. It must be
        skipped rather than parsed as a report whose video cannot be identified.
        """
        self._report(tree, "single.json", "vid00000001")
        (tree / "outputs" / "sweeps" / "x-month-abcd1234").mkdir(parents=True)
        (tree / "outputs" / "sweeps" / "x-month-abcd1234" / "sweep.json").write_text(
            json.dumps({"sweep_id": "x-month-abcd1234", "subject": "Samsung"}),
            encoding="utf-8")
        assert set(frame_cache.live_manifest()["videos"]) == {"vid00000001"}
