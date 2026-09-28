"""
Tests for models/install_comment_model.py — installing the fine-tuned comment model.

The real weights are 499 MB and are not in the repository, so these tests build
a four-file stand-in and its manifest in a temporary folder. What is under test
is the installer's contract, which is what decides whether the pipeline runs the
adopted model or silently falls back to a weaker one:

  - the exact route installs nothing unless every file matches the manifest;
  - an incomplete or tampered copy is refused and leaves the target untouched;
  - an existing folder is never deleted (kept aside with --force);
  - an archive can write only the expected files, and only inside the target;
  - a packed archive round-trips through the download route byte for byte.
"""

from __future__ import annotations

import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "install_comment_model", ROOT / "models" / "install_comment_model.py")
inst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inst)

NAMES = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")


@pytest.fixture
def model(tmp_path):
    """A four-file stand-in for the model, its manifest, and an empty models/ folder."""
    src = tmp_path / "source"
    src.mkdir()
    lines = []
    for i, name in enumerate(NAMES):
        data = f"{name} {i}".encode() * 50
        (src / name).write_bytes(data)
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    manifest = tmp_path / "comment_sentiment_ft.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    return {"src": src, "manifest": manifest, "target": models / "comment_sentiment_ft"}


def _install(m, folder, **kw):
    return inst.install_from(folder, target=m["target"], manifest=m["manifest"], **kw)


def test_the_real_manifest_names_the_four_files_the_pipeline_loads():
    want = inst.expected()
    assert set(want) == set(NAMES)
    assert all(len(d) == 64 for d in want.values())


def test_exact_install_copies_every_file_and_verifies(model):
    _install(model, model["src"])
    assert inst.problems(model["target"], inst.expected(model["manifest"])) == []


def test_a_tampered_file_is_refused_and_nothing_is_installed(model):
    (model["src"] / "model.safetensors").write_bytes(b"not the adopted weights")
    with pytest.raises(inst.InstallError, match="model.safetensors differs"):
        _install(model, model["src"])
    assert not model["target"].exists()


def test_a_missing_file_is_refused_on_both_routes(model):
    (model["src"] / "tokenizer.json").unlink()
    with pytest.raises(inst.InstallError, match="missing tokenizer.json"):
        _install(model, model["src"])
    with pytest.raises(inst.InstallError, match="incomplete"):
        _install(model, model["src"], exact=False)
    assert not model["target"].exists()


def test_the_retrained_route_skips_the_hash_check_but_not_completeness(model):
    (model["src"] / "model.safetensors").write_bytes(b"retrained weights")
    _install(model, model["src"], exact=False)
    assert (model["target"] / "model.safetensors").read_bytes() == b"retrained weights"


def test_an_existing_different_folder_is_never_deleted(model):
    model["target"].mkdir()
    (model["target"] / "config.json").write_text("{}")
    with pytest.raises(inst.InstallError, match="already exists"):
        _install(model, model["src"])
    assert (model["target"] / "config.json").read_text() == "{}"

    _install(model, model["src"], force=True)
    kept = list(model["target"].parent.glob("comment_sentiment_ft.previous-*"))
    assert len(kept) == 1 and (kept[0] / "config.json").read_text() == "{}"
    assert inst.problems(model["target"], inst.expected(model["manifest"])) == []


def test_installing_the_same_model_twice_changes_nothing(model):
    _install(model, model["src"])
    _install(model, model["src"])
    assert not list(model["target"].parent.glob("comment_sentiment_ft.previous-*"))


def test_an_archive_writes_only_the_expected_names_inside_the_target(model, tmp_path):
    archive = tmp_path / "hostile.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name in NAMES:
            z.write(model["src"] / name, f"nested/{name}")
        z.writestr("../../escaped.txt", "outside")
        z.writestr("extra.bin", "unexpected")
    into = tmp_path / "unpacked"
    into.mkdir()
    inst.unpack(archive, into, set(NAMES))
    assert sorted(p.name for p in into.iterdir()) == sorted(NAMES)
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_an_archive_missing_a_file_is_refused(model, tmp_path):
    archive = tmp_path / "short.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(model["src"] / "config.json", "config.json")
    with pytest.raises(inst.InstallError, match="missing"):
        inst.unpack(archive, tmp_path, set(NAMES))


def test_pack_then_download_round_trips_exactly(model, tmp_path):
    _install(model, model["src"])
    archive = tmp_path / "release.zip"
    digest = inst.pack(archive, source=model["target"], manifest=model["manifest"])
    assert digest == inst.sha256(archive)

    fresh = tmp_path / "fresh" / "comment_sentiment_ft"
    fresh.parent.mkdir()
    inst.install_from_url(archive.as_uri(), target=fresh, manifest=model["manifest"])
    for name in NAMES:
        assert (fresh / name).read_bytes() == (model["src"] / name).read_bytes()


def test_pack_refuses_a_folder_that_is_not_the_adopted_model(model, tmp_path):
    _install(model, model["src"], exact=False)
    (model["target"] / "config.json").write_text("changed")
    with pytest.raises(inst.InstallError):
        inst.pack(tmp_path / "x.zip", source=model["target"], manifest=model["manifest"])
