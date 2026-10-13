"""The launcher forwards paths and arguments without shell interpolation or input capture."""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "workbench_launcher", Path(__file__).resolve().parents[1] / "scripts/workbench.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


@pytest.fixture(autouse=True)
def isolated_launcher_environment(monkeypatch):
    for name in ("SLR_ENVIRONMENT", "SLR_SETUP_ENVIRONMENT", "SLR_CONTAINER"):
        monkeypatch.delenv(name, raising=False)


def test_launcher_preserves_arguments_and_interactive_terminal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = tmp_path / ".venv" / suffix
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    calls = []

    def capture(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(launcher.subprocess, "run", capture)
    assert launcher.main(["read-pdf", "a path/paper.pdf"]) == 7
    args, options = calls[0]
    assert args == [str(interpreter), "-m", "slr_workbench", "read-pdf", "a path/paper.pdf"]
    assert options["cwd"] == tmp_path
    assert options["env"]["VIRTUAL_ENV"] == str(tmp_path / ".venv")
    assert not options.get("shell")
    assert "stdin" not in options and "capture_output" not in options


def test_launcher_missing_environment_is_actionable(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    assert launcher.main(["status"]) == 1
    assert "setup" in capsys.readouterr().err


def test_backup_failure_prevents_operation(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.delenv("SLR_AUTO_BACKUP", raising=False)
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = tmp_path / ".venv" / suffix
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    calls = []

    def fail_backup(command, **options):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(launcher.subprocess, "run", fail_backup)
    assert launcher.main(["submit", "draft.json"]) == 1
    assert len(calls) == 1 and calls[0][-1] == "backup"
    assert "not started" in capsys.readouterr().err


def test_container_environment_keeps_host_venv_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path / "review")
    environment = tmp_path / "image-environment"
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = environment / suffix
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    monkeypatch.setenv("SLR_ENVIRONMENT", str(environment))
    calls = []

    def capture(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(launcher.subprocess, "run", capture)
    assert launcher.main(["status"]) == 0
    command, options = calls[0]
    assert command[0] == str(interpreter)
    assert options["cwd"] == tmp_path / "review"
    assert options["env"]["VIRTUAL_ENV"] == str(environment)
    assert not (tmp_path / "review" / ".venv").exists()


def test_container_rejects_host_style_updates(monkeypatch, capsys):
    monkeypatch.setenv("SLR_CONTAINER", "1")
    assert launcher.main(["update", "--check"]) == 1
    assert "docker compose build" in capsys.readouterr().err
