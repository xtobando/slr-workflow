"""Version detection and project profile selection need no OpenCode login."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def selector() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "select_opencode_config", ROOT / "scripts/select_opencode_config.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("stdout", "stderr", "major"),
    [
        ("1.3.0\n", "", 1),
        ("v1.3.0\n", "", 1),
        ("opencode v2.0.23\n", "", 2),
        ("opencode 2.0.23\n", "", 2),
        ("OpenCode version v2.0.23\n", "", 2),
        ("opencode v2.0.23-beta.1+build.7\n", "", 2),
        ("\x1b[32mopencode v2.0.23\x1b[0m\n", "", 2),
        ("", "opencode v2.0.23\n", 2),
        ("Runtime 9.8.7 warning\nopencode v2.0.23\n", "", 2),
    ],
)
def test_detect_version_formats(
    selector: ModuleType, monkeypatch: pytest.MonkeyPatch, stdout: str, stderr: str, major: int
) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert command == ["synthetic-opencode", "--version"]
        assert kwargs["timeout"] == 15
        return subprocess.CompletedProcess(command, 0, stdout, stderr)

    monkeypatch.setattr(selector.subprocess, "run", run)
    assert selector.detect_major("synthetic-opencode") == major


@pytest.mark.parametrize("output", ["", "Runtime 1.2.3", "opencode v3.0.0", "1.2.3\n2.0.23"])
def test_unknown_versions_do_not_select_a_profile(
    selector: ModuleType, monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    monkeypatch.setattr(
        selector.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""),
    )
    with pytest.raises(ValueError, match="[Uu]nrecognized|Unsupported"):
        selector.detect_major("synthetic-opencode")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (subprocess.TimeoutExpired("opencode", 15), "timed out"),
        (subprocess.CalledProcessError(1, "opencode"), "exit 1"),
        (FileNotFoundError("synthetic missing executable"), "Could not run"),
    ],
)
def test_version_command_failures_are_actionable(
    selector: ModuleType, monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    def run(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(selector.subprocess, "run", run)
    with pytest.raises(ValueError, match=message):
        selector.detect_major("synthetic-opencode")


@pytest.mark.parametrize("major", [1, 2])
def test_profile_selection_preserves_custom_configuration(
    selector: ModuleType, tmp_path: Path, major: int
) -> None:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    original = '{"custom": "synthetic setting"}\n'
    (tmp_path / "opencode.json").write_text(original)
    selector.select_profile(tmp_path, major)
    assert (tmp_path / "opencode.previous.json").read_text() == original
    assert json.loads((tmp_path / "opencode.json").read_text()) == json.loads(
        (tmp_path / "config" / f"opencode.v{major}.json").read_text()
    )
    selector.select_profile(tmp_path, major)
    assert (tmp_path / "opencode.previous.json").read_text() == original
