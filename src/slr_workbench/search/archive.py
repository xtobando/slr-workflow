"""Atomic archive storage and verification shared by search and coverage reports."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from .catalog import PROVIDERS


def encoded(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def save(path: Path, value: Any, *, replace: bool = False) -> str:
    """Publish complete JSON atomically; evidence files use exclusive creation."""
    payload = encoded(value)
    temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            if path.is_symlink():
                raise ValueError("Refusing to replace a search archive symlink")
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        # Persist directory entries where supported (Windows lacks O_DIRECTORY).
        if hasattr(os, "O_DIRECTORY"):
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> Any:
    if path.is_symlink():
        raise ValueError("Search archives must not contain symlinks")
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def run_lock(directory: Path) -> Iterator[None]:
    """An OS lock is released after process death; no stale-lock deletion needed."""
    lock_path = directory / ".search.lock"
    if lock_path.is_symlink():
        raise ValueError("Search lock must not be a symlink")
    with lock_path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if lock_path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("This search run is already active in another process") from None
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError("This search run is already active in another process") from None
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def verify_bundle(manifest_path: Path) -> tuple[dict, Path]:
    """Verify a completed immutable v1/v2 bundle without opening the review DB."""
    manifest = read_json(manifest_path)
    version = manifest.get("schema_version")
    if version not in (1, 2) or manifest.get("status") != "completed":
        raise ValueError("Only completed version-1 or version-2 search bundles can be imported")
    provider = manifest["provider"]
    if provider not in PROVIDERS or manifest.get("endpoint") != PROVIDERS[provider].endpoint:
        raise ValueError("Unknown provider/interface in search manifest")
    if not isinstance(manifest.get("truncated"), bool):
        raise TypeError("Search manifest requires a Boolean truncated flag")
    directory = manifest_path.resolve().parent
    filename = manifest.get("records_file", "records.json") if version == 2 else "records.json"
    if filename != "records.json" and not re.fullmatch(r"records-[0-9]{6}\.json", filename):
        raise ValueError("Unsafe records filename in manifest")
    records_path = directory / filename
    checks = [(records_path, manifest["records_sha256"])]
    if version == 2:
        checks.append((directory / "run.json", manifest["run_sha256"]))
        run = read_json(directory / "run.json")
        for key in (
            "schema_version",
            "run_id",
            "provider",
            "query",
            "endpoint",
            "searched_at",
            "page_size",
        ):
            if manifest.get(key) != run.get(key):
                raise ValueError("Search manifest differs from its immutable run definition")
    for entry in manifest["pages"]:
        if not re.fullmatch(r"page-[0-9]{4}\.json", entry["file"]):
            raise ValueError("Unsafe response filename in manifest")
        checks.append((directory / entry["file"], entry["sha256"]))
    for path, expected in checks:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Search evidence checksum mismatch or symlink; nothing was imported")
    if version == 2:
        for filename, expected in manifest.get("request_receipt_hashes", {}).items():
            if not re.fullmatch(r"request-[0-9]{6}\.json", filename):
                raise ValueError("Unsafe request receipt filename")
            path = directory / filename
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Search request receipt checksum mismatch")
    records = read_json(records_path)
    if not isinstance(records, list) or len(records) != manifest["records_count"]:
        raise ValueError("Search record count mismatch")
    return manifest, records_path
