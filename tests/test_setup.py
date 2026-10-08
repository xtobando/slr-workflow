"""Setup preserves environments and stops before announcing a failed installation."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "workbench_setup", Path(__file__).resolve().parents[1] / "scripts/setup.py"
)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def test_incomplete_environment_is_preserved(tmp_path: Path) -> None:
    environment = tmp_path / ".venv"
    environment.mkdir()
    marker = environment / "keep.txt"
    marker.write_text("existing")
    with pytest.raises(ValueError, match="incomplete"):
        setup.prepare(environment)
    assert marker.read_text() == "existing"


def test_different_python_is_not_replaced(tmp_path: Path, monkeypatch) -> None:
    environment = tmp_path / ".venv"
    interpreter = setup.python_in(environment)
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("existing interpreter")
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout='[[3, 12], "/different/python"]'),
    )
    with pytest.raises(ValueError, match="another Python"):
        setup.prepare(environment)
    assert interpreter.read_text() == "existing interpreter"


def test_setup_sync_preserves_extras_and_avoids_decisions(monkeypatch, capsys) -> None:
    monkeypatch.setattr(setup.sys, "version_info", (3, 12))
    monkeypatch.setattr(setup, "prepare", lambda directory: setup.python_in(directory))
    calls = []
    monkeypatch.setattr(setup, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    assert setup.main() == 0
    sync, options = next((args, kw) for args, kw in calls if "sync" in args)
    assert "--locked" in sync and "--inexact" in sync
    assert options["env"]["UV_PYTHON_DOWNLOADS"] == "never"
    assert not any("approve-protocol" in args or "init" in args for args, _ in calls)
    assert "Core setup complete" in capsys.readouterr().out


def test_failed_install_does_not_report_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(setup.sys, "version_info", (3, 12))
    monkeypatch.setattr(setup, "prepare", lambda directory: Path(sys.executable))

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "installation")

    monkeypatch.setattr(setup, "run", fail)
    assert setup.main() == 1
    output = capsys.readouterr()
    assert "Core setup complete" not in output.out
    assert "Setup stopped" in output.err


def test_bash_setup_accepts_python3_without_versioned_executable(tmp_path: Path) -> None:
    import os

    if os.name == "nt":
        pytest.skip("Bash discovery test; PowerShell is exercised in CI")
    executable = tmp_path / "python3"
    executable.write_text(
        '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\necho selected-python3\nexit 9\n'
    )
    executable.chmod(0o755)
    env = dict(os.environ, PATH=str(tmp_path) + ":/usr/bin:/bin")
    env.pop("SLR_PYTHON", None)
    result = subprocess.run(
        ["/bin/bash", str(setup.ROOT / "scripts/setup.sh")],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 9
    assert "selected-python3" in result.stdout
