"""SQLite transactions, migrations and a hash-chained append-only event history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import Configuration

IMMUTABLE_TABLES = (
    "protocol_versions",
    "search_runs",
    "reports",
    "records",
    "studies",
    "documents",
    "proposals",
    "decisions",
    "events",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, value: str) -> str:
    return prefix + "_" + hashlib.sha256(value.encode()).hexdigest()[:20]


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        """Enable foreign keys on every connection and close all connections reliably."""
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, config: Configuration) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f"Unsupported database schema version: {version}")
            migration = files("slr_workbench").joinpath("migrations/001_initial.sql")
            connection.executescript(migration.read_text(encoding="utf-8"))
            for table in IMMUTABLE_TABLES:
                for operation in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()} "
                        f"BEFORE {operation} ON {table} BEGIN "
                        "SELECT RAISE(ABORT, 'Append-only table: add a new version instead'); END"
                    )
            connection.commit()
        with self.connect(write=True) as connection:
            existing = connection.execute(
                "SELECT DISTINCT review_id FROM protocol_versions"
            ).fetchall()
            if existing and {r[0] for r in existing} != {config.protocol.review_id}:
                raise ValueError("This database belongs to a different review_id")
            connection.execute(
                "INSERT OR IGNORE INTO protocol_versions VALUES (?,?,?,?,?)",
                (
                    config.revision,
                    config.protocol.review_id,
                    config.protocol_yaml,
                    config.workflow_yaml,
                    utc_now(),
                ),
            )

    def require_initialized(self, config: Configuration) -> None:
        if not self.path.exists():
            raise ValueError("Run slr init first")
        with self.connect() as connection:
            if not connection.execute(
                "SELECT 1 FROM protocol_versions WHERE revision=?", (config.revision,)
            ).fetchone():
                raise ValueError("Configuration changed: run slr init and approve the new revision")

    @staticmethod
    def event(
        connection: sqlite3.Connection,
        revision: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        actor_type: str = "mechanical",
        actor_id: str = "slr-core",
    ) -> int:
        previous = connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous[0] if previous else "0" * 64
        body = {
            "event_id": str(uuid4()),
            "protocol_revision": revision,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "payload": canonical_json(payload),
            "created_at": utc_now(),
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(canonical_json(body).encode()).hexdigest()
        cursor = connection.execute(
            "INSERT INTO events(event_id,protocol_revision,event_type,entity_type,entity_id,"
            "actor_type,actor_id,payload,created_at,previous_hash,event_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (*body.values(), event_hash),
        )
        return int(cursor.lastrowid or 0)

    def verify_chain(self) -> dict[str, Any]:
        previous = "0" * 64
        checked = 0
        with self.connect() as connection:
            for row in connection.execute("SELECT * FROM events ORDER BY sequence"):
                body = {
                    key: row[key]
                    for key in (
                        "event_id",
                        "protocol_revision",
                        "event_type",
                        "entity_type",
                        "entity_id",
                        "actor_type",
                        "actor_id",
                        "payload",
                        "created_at",
                        "previous_hash",
                    )
                }
                if body["previous_hash"] != previous:
                    raise ValueError(f"Broken event chain at sequence {row['sequence']}")
                calculated = hashlib.sha256(canonical_json(body).encode()).hexdigest()
                if calculated != row["event_hash"]:
                    raise ValueError(f"Altered event at sequence {row['sequence']}")
                previous = calculated
                checked += 1
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise ValueError("SQLite integrity or foreign-key check failed")
        return {"events_checked": checked, "head_hash": previous, "sqlite_integrity": integrity}
