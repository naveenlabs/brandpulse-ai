"""
What a new installation is told must match what the code does.

  - `.env.example` is copied to `.env` by every new user. Until 26 Sep 2026 it
    set OLLAMA_MODEL=llama3.2, so following the setup instructions silently
    replaced the adopted controller (llama3.1:8b, controller_bench/) with the
    one the bench rejected. Every optional variable it shows must carry the
    code's own default, and none may be switched on.
  - `python app.py` must start the same server as `flask --app app run --port
    5001`: not on 5000 (held by macOS's AirPlay Receiver) and without the
    Werkzeug debugger, which executes code sent to it.
  - The README tells a new user to replace the key placeholder in `.env`; it
    must name the placeholder `.env.example` actually contains (until 28 Sep
    2026 it showed a different one).
  - A clone must check files out byte for byte. Git for Windows converts text
    files to CRLF by default, and each stored written report records the
    SHA-256 of the report it was written from, so a converted clone showed the
    committed combined report as out of date (measured 28 Sep 2026: 0 of 9
    single and 0 of 4 member hashes matched). `.gitattributes` turns the
    conversion off.
"""

from __future__ import annotations

import ast
import re
import runpy
from pathlib import Path
from unittest.mock import patch

import flask

from pipeline import analyst, analyst_sweep

ROOT = Path(__file__).resolve().parent.parent


def _code_defaults() -> dict[str, str]:
    """{VARIABLE: default} for every os.getenv / os.environ.get with a default under pipeline/."""
    found: dict[str, str] = {}
    for path in sorted((ROOT / "pipeline").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            reader = node.func
            is_getenv = reader.attr == "getenv" and isinstance(reader.value, ast.Name) \
                and reader.value.id == "os"
            is_environ_get = reader.attr == "get" and isinstance(reader.value, ast.Attribute) \
                and reader.value.attr == "environ"
            if not (is_getenv or is_environ_get) or len(node.args) != 2:
                continue
            name, default = node.args
            if isinstance(name, ast.Constant) and isinstance(default, ast.Constant) \
                    and isinstance(name.value, str) and name.value.isupper():
                found[name.value] = str(default.value)
    return found


def _example() -> tuple[dict[str, str], dict[str, str]]:
    """(active assignments, commented-out assignments) in .env.example."""
    active, commented = {}, {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(#\s*)?([A-Z][A-Z0-9_]*)=(.*)$", line.strip())
        if m:
            (commented if m.group(1) else active)[m.group(2)] = m.group(3).strip()
    return active, commented


def test_the_example_shows_every_optional_variable_with_the_code_default():
    defaults = _code_defaults()
    assert "OLLAMA_MODEL" in defaults and "WHISPER_MODEL_SIZE" in defaults
    _, commented = _example()
    for name, default in defaults.items():
        assert commented.get(name) == default, f"{name}: example says {commented.get(name)!r}, code {default!r}"


def test_the_example_switches_nothing_on_but_the_api_key():
    active, _ = _example()
    assert set(active) == {"YOUTUBE_API_KEY"}


def test_the_controller_the_example_documents_is_the_adopted_one():
    _, commented = _example()
    assert commented["OLLAMA_MODEL"] == "llama3.1:8b"
    assert _code_defaults()["OLLAMA_MODEL"] == "llama3.1:8b"


def test_python_app_py_serves_on_5001_without_the_debugger():
    with patch.object(flask.Flask, "run") as run:
        runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
    run.assert_called_once()
    assert run.call_args.kwargs.get("port") == 5001
    assert not run.call_args.kwargs.get("debug")


def test_the_readme_names_the_placeholder_the_example_contains():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    shown = re.findall(r"^YOUTUBE_API_KEY=(\S+)$", readme, re.M)
    active, _ = _example()
    assert shown and set(shown) == {active["YOUTUBE_API_KEY"]}


def test_every_file_is_checked_out_without_line_ending_conversion():
    rules = [line.split() for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    assert ["*", "-text"] in rules


def test_every_stored_written_report_matches_the_report_it_was_written_from():
    """What a converted checkout breaks: each hash must match the file as checked out."""
    outputs = ROOT / "outputs"
    singles = sorted((outputs / "analysis").glob("*.json"))
    for path in singles:
        report = outputs / analyst.load(path)["report_ref"]["file"]
        assert analyst.load(path, report)["stale"] is False, path.name
    combined = sorted((outputs / "sweeps").glob("*/analysis/combined.json"))
    for path in combined:
        stored = analyst_sweep.load(path)["sweep_ref"]
        current = {"record": analyst.file_sha256(path.parent.parent / "sweep.json"),
                   "members": {vid: analyst.file_sha256(path.parent / f"{vid}.json")
                               for vid in stored["members"]}}
        assert analyst_sweep.load(path, current)["stale"] is False, path.parent.parent.name
    assert singles and combined
