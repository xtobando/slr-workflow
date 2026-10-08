"""Update candidates preserve the old project and fail closed when tests fail."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "workbench_update", Path(__file__).resolve().parents[1] / "scripts/update.py"
)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


def test_candidate_copies_customization_only_after_tests(review, tmp_path, monkeypatch) -> None:
    root = review.config.root
    candidate = root.parent / (root.name + "-updated")
    monkeypatch.setattr(updater, "ROOT", root)
    monkeypatch.setenv("SLR_BACKUP_DIR", str(root.parent / (root.name + "-backups")))

    def fake_git(*args, root=None):
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return "origin/main"
        if args == ("rev-parse", "HEAD"):
            return "old"
        if args == ("rev-parse", "FETCH_HEAD"):
            return "new"
        if args[:2] == ("remote", "get-url"):
            return "https://example.invalid/repo.git"
        if args[0] == "clone":
            candidate.mkdir()
        return ""

    monkeypatch.setattr(updater, "git", fake_git)
    commands = []

    def run(command, **options):
        commands.append(command)
        if "-q" in command:
            assert not (candidate / "protocol.yaml").exists()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(updater.subprocess, "run", run)
    before = review.db.verify_chain()
    result = updater.prepare_update(candidate)
    assert result["revision"] == "new"
    assert (candidate / "protocol.yaml").read_bytes() == (root / "protocol.yaml").read_bytes()
    assert (candidate / review.config.protocol.paths.database).exists()
    assert review.db.verify_chain() == before
    assert any("audit" in command for command in commands)


def test_failed_candidate_leaves_original_untouched(review, monkeypatch) -> None:
    root = review.config.root
    candidate = root.parent / (root.name + "-failed-update")
    monkeypatch.setattr(updater, "ROOT", root)
    monkeypatch.setenv("SLR_BACKUP_DIR", str(root.parent / (root.name + "-backups")))

    def fake_git(*args, root=None):
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return "origin/main"
        if args == ("rev-parse", "HEAD"):
            return "old"
        if args == ("rev-parse", "FETCH_HEAD"):
            return "new"
        if args[0] == "clone":
            candidate.mkdir()
        return ""

    monkeypatch.setattr(updater, "git", fake_git)

    def fail(command, **options):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(updater.subprocess, "run", fail)
    before = review.db.verify_chain()
    with pytest.raises(ValueError, match="Candidate failed validation"):
        updater.prepare_update(candidate)
    assert review.db.verify_chain() == before
    assert not (candidate / review.config.protocol.paths.database).exists()
