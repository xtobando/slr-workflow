"""Verified recovery archives; SQLite snapshots include committed WAL transactions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import ExitStack, closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .config import load_configuration
from .database import Database

MANIFEST = "backup-manifest.json"
EXCLUDED = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    "dist",
    "build",
    "htmlcov",
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Backup requires project-local paths: {path}")
    return resolved.relative_to(root)


def validate_snapshot(root: Path, database: str | None) -> None:
    if database is None:
        return
    db = root / database
    Database(db).verify_chain()
    with closing(sqlite3.connect(db)) as connection:
        for name, expected in connection.execute("SELECT local_path, sha256 FROM documents"):
            path = root / inside(root, root / name)
            if not path.is_file() or digest(path) != expected:
                raise ValueError(f"Missing or changed archived evidence: {name}")


def create_backup(root: Path, destination: Path | None = None) -> dict:
    root = root.resolve()
    destination = (
        destination
        or Path(os.environ.get("SLR_BACKUP_DIR", str(root.parent / (root.name + "-backups"))))
    ).resolve()
    if destination.is_relative_to(root):
        raise ValueError("Choose a backup folder outside the project to avoid recursive backups.")
    config = load_configuration(root)
    db_relative = inside(root, config.database)
    for value in (config.protocol.paths.artifacts, config.protocol.paths.exports):
        inside(root, root / value)
    destination.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix=".pending-", dir=destination) as temporary,
        ExitStack() as stack,
    ):
        staging = Path(temporary) / "project"
        staging.mkdir()
        database = None
        if config.database.exists():
            # Block app writers while copying the DB and its referenced immutable artifacts.
            guard = stack.enter_context(closing(sqlite3.connect(config.database, timeout=10)))
            guard.execute("BEGIN IMMEDIATE")
            source = stack.enter_context(
                closing(sqlite3.connect(config.database.as_uri() + "?mode=ro", uri=True))
            )
            target = staging / db_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(target)) as output:
                source.backup(output)
            database = db_relative.as_posix()
        copied = {}
        for parent, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in EXCLUDED and not d.startswith(".venv-") and not d.endswith(".egg-info")
            ]
            for entry in dirs:
                if (Path(parent) / entry).is_symlink():
                    raise ValueError(
                        f"Move symlinked project content inside the project before backup: {entry}"
                    )
            for name in files:
                source_file = Path(parent) / name
                relative = source_file.relative_to(root)
                if (
                    name == ".env"
                    or name.startswith(".env.")
                    or name in {".DS_Store", ".coverage"}
                    or name.endswith(".pyc")
                    or relative.as_posix()
                    in {db_relative.as_posix() + suffix for suffix in ("-wal", "-shm", "-journal")}
                ):
                    continue
                if relative == db_relative:
                    continue
                if relative.as_posix() == MANIFEST or source_file.is_symlink():
                    raise ValueError(f"Unsupported backup entry: {relative}")
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                before = digest(source_file)
                shutil.copy2(source_file, target)
                if digest(target) != before or digest(source_file) != before:
                    raise ValueError(
                        f"File changed during backup; close editors and retry: {relative}"
                    )
                copied[relative.as_posix()] = before
        for name, expected in copied.items():
            if digest(root / name) != expected:
                raise ValueError(f"File changed during backup; retry: {name}")
        if (staging / "protocol.yaml").read_text(encoding="utf-8") != config.protocol_yaml or (
            staging / "workflow.yaml"
        ).read_text(encoding="utf-8") != config.workflow_yaml:
            raise ValueError("Configuration changed during backup; retry.")
        validate_snapshot(staging, database)
        hashes = {
            p.relative_to(staging).as_posix(): digest(p)
            for p in staging.rglob("*")
            if p.is_file() and not p.name.endswith(("-wal", "-shm"))
        }
        manifest = {
            "format": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "database": database,
            "files": hashes,
            "excluded": ["environments", "caches", ".git", ".env files", "build outputs"],
        }
        archive = Path(temporary) / "archive.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name in hashes:
                output.write(staging / name, name)
            output.writestr(MANIFEST, json.dumps(manifest, indent=2))
        verify_backup(archive)
        final = destination / f"backup-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.zip"
        with archive.open("rb+") as stream:
            os.fsync(stream.fileno())
        archive.replace(final)
    return {"backup": str(final), "files": len(hashes), "verified": True}


def unpack_verified(archive: Path, target: Path) -> dict:
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        names = [item.filename for item in entries]
        if len(names) != len({name.casefold() for name in names}):
            raise ValueError("Duplicate archive entries")
        for item in entries:
            name = item.filename
            path = PurePosixPath(name)
            if (
                path.as_posix() != name
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or ":" in name
                or item.is_dir()
                or ((item.external_attr >> 16) & 0o170000) == 0o120000
            ):
                raise ValueError(f"Unsafe archive path: {name}")
        manifest = json.loads(source.read(MANIFEST))
        if manifest.get("format") != 1 or set(names) != set(manifest["files"]) | {MANIFEST}:
            raise ValueError("Backup manifest does not match archive contents")
        for name, expected in manifest["files"].items():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(name) as input_file, destination.open("wb") as output:
                shutil.copyfileobj(input_file, output)
            if digest(destination) != expected:
                raise ValueError(f"Backup checksum mismatch: {name}")
    database = manifest["database"]
    if database is not None and database not in manifest["files"]:
        raise ValueError("Database missing from backup manifest")
    validate_snapshot(target, database)
    return manifest


def verify_backup(archive: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="slr-verify-") as temporary:
        manifest = unpack_verified(archive, Path(temporary).resolve())
    return {"verified": True, "files": len(manifest["files"]), "created_at": manifest["created_at"]}


def restore_backup(archive: Path, destination: Path) -> dict:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(
            "Restore destination must not exist; the active project is never overwritten."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "project"
        staging.mkdir()
        unpack_verified(archive, staging.resolve())
        if destination.exists():
            raise ValueError("Restore destination now exists; refusing to overwrite it.")
        staging.rename(destination)
    return {
        "restored": str(destination),
        "next": "Run guided setup in the restored folder, then audit/status. Do not reapprove existing decisions.",
    }
