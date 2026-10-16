"""Mechanical integrity checks shared by the CLI and operational reports."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import ReviewService


def audit_review(current: ReviewService) -> dict[str, Any]:
    """Check history and immutable source bytes without repairing scientific state."""
    current.check_ready()
    result = current.db.verify_chain()
    with current.db.connect() as connection:
        documents = connection.execute("SELECT * FROM documents ORDER BY id").fetchall()
        searches = connection.execute("SELECT * FROM search_runs ORDER BY id").fetchall()
    for document in documents:
        path = current.config.root / document["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != document["sha256"]:
            raise ValueError(f"Archived document changed: {document['id']}")
    for run in searches:
        if hashlib.sha256(run["raw_import"].encode()).hexdigest() != run["import_sha256"]:
            raise ValueError(f"Archived search import changed: {run['id']}")
    result.update(documents_checked=len(documents), search_imports_checked=len(searches))
    return result
