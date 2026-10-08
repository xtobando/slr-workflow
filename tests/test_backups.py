"""Recovery archives must restore committed WAL data and reject unsafe/corrupt inputs."""

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from slr_workbench.backups import create_backup, restore_backup, verify_backup
from slr_workbench.service import ReviewService


def test_restore_preserves_committed_review_and_customization(
    review: ReviewService, tmp_path: Path
) -> None:
    root = review.config.root
    (root / "notes.md").write_text("Work already done")
    (root / ".env").write_text("PRIVATE=value")
    with sqlite3.connect(review.config.database) as open_connection:
        open_connection.execute("PRAGMA journal_mode=WAL")
        open_connection.execute("CREATE TABLE recovery_probe (note TEXT)")
        open_connection.execute("INSERT INTO recovery_probe VALUES ('committed WAL data')")
        open_connection.commit()
        assert Path(str(review.config.database) + "-wal").exists()
        # Keep a connection open, so recovery cannot rely on SQLite closing/checkpointing.
        result = create_backup(root, tmp_path.parent / (tmp_path.name + "-backups"))
    archive = Path(result["backup"])
    assert verify_backup(archive)["verified"]
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert (restored / "notes.md").read_text() == "Work already done"
    assert not (restored / ".env").exists()
    with sqlite3.connect(restored / review.config.protocol.paths.database) as connection:
        assert connection.execute("SELECT count(*) FROM events").fetchone()[0] > 0
        assert (
            connection.execute("SELECT note FROM recovery_probe").fetchone()[0]
            == "committed WAL data"
        )
    with pytest.raises(ValueError, match="must not exist"):
        restore_backup(archive, restored)
    assert (root / "notes.md").read_text() == "Work already done"


def test_corrupt_archive_never_publishes_restore(review: ReviewService, tmp_path: Path) -> None:
    result = create_backup(review.config.root, tmp_path.parent / (tmp_path.name + "-backups"))
    changed = tmp_path / "changed.zip"
    with zipfile.ZipFile(result["backup"]) as source, zipfile.ZipFile(changed, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            target.writestr(name, data + b"changed" if name == "protocol.yaml" else data)
    with pytest.raises(ValueError, match="checksum"):
        restore_backup(changed, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_traversal_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape", "bad")
        output.writestr("backup-manifest.json", json.dumps({"format": 1, "files": {}}))
    with pytest.raises(ValueError, match="Unsafe"):
        verify_backup(archive)
    assert not (tmp_path / "escape").exists()


def test_backup_inside_project_is_rejected(review: ReviewService) -> None:
    with pytest.raises(ValueError, match="outside"):
        create_backup(review.config.root, review.config.root / "backups")


def test_interrupted_backup_keeps_previous_archive(review, tmp_path, monkeypatch) -> None:
    folder = tmp_path.parent / (tmp_path.name + "-backups")
    prior = create_backup(review.config.root, folder)

    def fail(*args, **kwargs):
        raise OSError("Simulated disk full")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    with pytest.raises(OSError, match="disk full"):
        create_backup(review.config.root, folder)
    assert list(folder.glob("*.zip")) == [Path(prior["backup"])]
    assert verify_backup(Path(prior["backup"]))["verified"]
