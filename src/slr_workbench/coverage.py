"""Inspect search completeness and declared seed sensitivity without running searches."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .search.service import verify_bundle
from .service import ReviewService, normalize_doi


def read_json(path: Path) -> Any:
    if path.is_symlink():
        raise ValueError("Search inventory refuses symlink artifacts")
    return json.loads(path.read_text(encoding="utf-8"))


def read_seeds(path: Path) -> list[dict[str, Any]]:
    """A seed's scientific relevance is user-verified, never inferred from a match."""
    seeds = read_json(path)
    if not isinstance(seeds, list):
        raise TypeError("Seed file must contain a JSON array")
    seen = set()
    for seed in seeds:
        if not isinstance(seed, dict) or not isinstance(seed.get("id"), str) or not seed["id"]:
            raise ValueError("Each seed requires a nonempty id")
        if seed["id"] in seen:
            raise ValueError("Seed ids must be unique")
        seen.add(seed["id"])
        if (
            seed.get("verified") is not True
            or not isinstance(seed.get("verification_note"), str)
            or not seed["verification_note"].strip()
        ):
            raise ValueError("Each seed requires verified=true and a human verification_note")
        seed["doi"] = normalize_doi(seed.get("doi"))
        identities = seed.get("source_ids", {})
        if not isinstance(identities, dict) or any(
            not isinstance(namespace, str)
            or not isinstance(ids, list)
            or not ids
            or any(not isinstance(value, str) or not value for value in ids)
            for namespace, ids in identities.items()
        ):
            raise ValueError(
                "Seed source_ids must map provider/source names to nonempty identifier lists"
            )
        if not seed["doi"] and not identities:
            raise ValueError("Each seed needs a DOI or namespaced source_ids")
    return seeds


def _identities(record: dict, namespace: str) -> tuple[str | None, str, str]:
    metadata = record.get("metadata") or {}
    provider = metadata.get("provider")
    provider = provider if isinstance(provider, str) and provider else namespace
    return normalize_doi(record.get("doi")), provider, record["source_record_id"]


def search_coverage(current: ReviewService, seeds: Path | None = None) -> dict[str, Any]:
    """Separate saved requests, imported runs, overlapping totals and literature coverage."""
    current.check_ready()
    with current.db.connect() as connection:
        connection.execute("BEGIN")
        imports = {
            row["id"]: dict(row)
            for row in connection.execute("SELECT * FROM search_runs ORDER BY id")
        }
        counts = {
            row["search_run_id"]: row["n"]
            for row in connection.execute(
                "SELECT search_run_id, COUNT(*) AS n FROM records GROUP BY search_run_id"
            )
        }
    archive_root = current.config.root / "data" / "searches"
    archived = {}
    errors = []
    for directory in sorted(archive_root.iterdir()) if archive_root.exists() else []:
        if not directory.is_dir() or directory.is_symlink():
            continue
        manifest_path, checkpoint_path = directory / "manifest.json", directory / "checkpoint.json"
        try:
            manifest = read_json(manifest_path) if manifest_path.exists() else {}
            checkpoint = read_json(checkpoint_path) if checkpoint_path.exists() else {}
            if not isinstance(manifest, dict) or not isinstance(checkpoint, dict):
                raise TypeError("Invalid search archive metadata")
            if not manifest and not checkpoint:
                errors.append(
                    {
                        "run_id": directory.name,
                        "issue": "No manifest or checkpoint; unfinished archive",
                    }
                )
                continue
            if manifest and manifest.get("run_id") != directory.name:
                raise ValueError("Search run id does not match its archive directory")
            integrity = "not_verified_failed_or_in_progress"
            records = []
            if manifest.get("status") == "completed" and checkpoint.get("status") != "running":
                _, records_path = verify_bundle(manifest_path)
                records = read_json(records_path)
                integrity = "verified_completed_bundle"
            archived[directory.name] = {
                "manifest": manifest,
                "checkpoint": checkpoint,
                "records": records,
                "integrity": integrity,
            }
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append(
                {
                    "run_id": directory.name,
                    "issue": "Unreadable, malformed or symlink search metadata; inspect preserved files",
                }
            )
    rows = []
    record_sets = {}
    for run_id in sorted(imports.keys() | archived.keys()):
        imported = imports.get(run_id)
        archive = archived.get(run_id, {})
        manifest, checkpoint = archive.get("manifest", {}), archive.get("checkpoint", {})
        truncated = bool(imported["truncated"]) if imported else manifest.get("truncated")
        status = checkpoint.get("status", manifest.get("status", "manual_import"))
        if status not in {"completed", "manual_import"}:
            request_state = "unfinished_or_failed"
        elif truncated is True:
            request_state = "truncated"
        elif truncated is False:
            request_state = "reported_complete"
        else:
            request_state = "unknown"
        rows.append(
            {
                "run_id": run_id,
                "provider": manifest.get("provider"),
                "source": imported["source_id"] if imported else None,
                "query": imported["query"] if imported else manifest.get("query"),
                "searched_at": imported["searched_at"] if imported else manifest.get("searched_at"),
                "imported": imported is not None,
                "imported_records": counts.get(run_id, 0),
                "archived_records": len(archive.get("records", [])),
                "provider_total_or_estimate": manifest.get("provider_total"),
                "truncated": truncated,
                "request_state": request_state,
                "archive_status": status,
                "archive_integrity": archive.get("integrity", "not_present"),
                "stop_reason": manifest.get("stop_reason"),
                "current_revision_import": bool(
                    imported and imported["protocol_revision"] == current.config.revision
                ),
                "completion_strategy": (
                    "Resume a verified v2 checkpoint with the original query and a reviewed request budget, or execute a new round. A methodological refinement needs approval and a new run ID."
                    if request_state in {"truncated", "unfinished_or_failed", "unknown"}
                    else "Evaluate seed sensitivity, source coverage and false positives before claiming literature coverage."
                ),
            }
        )
        if imported:
            raw = imported["raw_import"]
            if hashlib.sha256(raw.encode()).hexdigest() != imported["import_sha256"]:
                raise ValueError(f"Archived search import changed: {run_id}")
            # JSON imports and manual CSV use the existing RecordInput schema.
            try:
                parsed = json.loads(raw)
                record_sets[run_id] = (
                    parsed if isinstance(parsed, list) else [],
                    imported["source_id"],
                )
            except ValueError:
                import csv
                import io

                values = list(csv.DictReader(io.StringIO(raw)))
                for value in values:
                    value["metadata"] = json.loads(value.get("metadata") or "{}")
                record_sets[run_id] = (values, imported["source_id"])
        else:
            record_sets[run_id] = (archive.get("records", []), manifest.get("provider", "unknown"))
    sensitivity = None
    if seeds is not None:
        declared = read_seeds(seeds)
        matched = []
        for seed in declared:
            found = []
            for run_id, (records, namespace) in record_sets.items():
                for record in records:
                    doi, provider, identity = _identities(record, namespace)
                    if (seed["doi"] and doi == seed["doi"]) or identity in seed.get(
                        "source_ids", {}
                    ).get(provider, []):
                        found.append(run_id)
                        break
            matched.append(
                {
                    "seed_id": seed["id"],
                    "evidence_stream": seed.get("evidence_stream"),
                    "matched_runs": found,
                    "found": bool(found),
                }
            )
        sensitivity = {
            "declared_verified_seeds": len(declared),
            "found": sum(item["found"] for item in matched),
            "fraction_found": sum(item["found"] for item in matched) / len(declared)
            if declared
            else None,
            "seeds": matched,
            "interpretation": "Identifier recall against the declared, user-verified seed set only. Matches do not independently verify relevance or full search sensitivity.",
        }
    return {
        "schema_version": 1,
        "protocol_revision": current.config.revision,
        "runs": rows,
        "archive_issues": errors,
        "seed_sensitivity": sensitivity,
        "coverage_complete": None,
        "warnings": [
            "Provider totals overlap across queries and sources; never sum them as unique papers.",
            "A relevance-ranked capped page is not a representative sample.",
            "Request completeness is distinct from literature coverage; no scientific coverage approval is inferred.",
        ],
    }
