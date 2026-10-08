"""Automatic activation must never switch to a stale or altered review snapshot."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "auto_updates", Path(__file__).resolve().parents[1] / "scripts/auto_update.py"
)
auto = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auto)


def pending(tmp_path):
    return {
        "active": str(tmp_path / "old"),
        "enabled": True,
        "pending": {
            "path": str(tmp_path / "new"),
            "source_files": {"data": "saved"},
            "candidate_files": {"data": "saved", "code": "new"},
        },
    }


def test_activation_switches_only_verified_snapshots(tmp_path, monkeypatch):
    state = pending(tmp_path)
    monkeypatch.setattr(
        auto,
        "snapshot",
        lambda root: {"data": "saved"} if root.name == "old" else {"data": "saved", "code": "new"},
    )
    path = tmp_path / "state.json"
    auto.activate(state, path)
    assert state["active"] == str(tmp_path / "new")
    assert state["previous"]["path"] == str(tmp_path / "old")
    assert json.loads(path.read_text())["pending"] is None


@pytest.mark.parametrize("changed", ["old", "new"])
def test_changed_review_or_candidate_never_activates(tmp_path, monkeypatch, changed):
    state = pending(tmp_path)
    monkeypatch.setattr(
        auto,
        "snapshot",
        lambda root: {"changed": True} if root.name == changed else {"data": "saved"},
    )
    auto.activate(state, tmp_path / "state.json")
    assert state["active"] == str(tmp_path / "old")
    assert state["pending"] is None


def test_failed_pointer_write_does_not_switch_in_memory(tmp_path, monkeypatch):
    state = pending(tmp_path)
    monkeypatch.setattr(
        auto,
        "snapshot",
        lambda root: {"data": "saved"} if root.name == "old" else {"data": "saved", "code": "new"},
    )

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(auto, "save", fail)
    with pytest.raises(OSError):
        auto.activate(state, tmp_path / "state.json")
    assert state["active"] == str(tmp_path / "old")


def test_concurrent_launcher_is_rejected(tmp_path):
    with (
        auto.exclusive(tmp_path),
        pytest.raises(ValueError, match="Another launcher"),
        auto.exclusive(tmp_path),
    ):
        pass
    assert not (tmp_path / "running.lock").exists()


def test_rollback_refuses_new_work(tmp_path, monkeypatch):
    monkeypatch.setattr(auto, "ROOT", tmp_path)
    folder = tmp_path / ".workbench-state"
    folder.mkdir()
    state = {
        "active": str(tmp_path / "new"),
        "active_files": {"data": "old"},
        "previous": {"path": str(tmp_path / "old"), "files": {"data": "old"}},
        "enabled": True,
    }
    auto.save(folder / "state.json", state)
    monkeypatch.setattr(auto, "snapshot", lambda root: {"data": "new work"})
    assert auto.dispatch(["auto-update", "rollback"]) == 1
    assert json.loads((folder / "state.json").read_text())["active"] == str(tmp_path / "new")


def test_all_commands_route_to_active_environment(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setattr(auto, "ROOT", tmp_path)
    folder = tmp_path / ".workbench-state"
    folder.mkdir()
    active = tmp_path / "selected"
    auto.save(folder / "state.json", {"active": str(active), "enabled": True, "pending": None})
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 9)

    monkeypatch.setattr(auto.subprocess, "run", run)
    assert auto.dispatch(["status"]) == 9
    command, options = calls[0]
    assert command[0] == str(auto.interpreter(active))
    assert command[-1] == "status"
    assert options["cwd"] == active
    assert options["env"]["SLR_ROUTED_LAUNCH"] == "1"
