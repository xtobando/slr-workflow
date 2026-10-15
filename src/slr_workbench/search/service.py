"""Archive real searches separately from gated, idempotent review imports."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from ..service import ReviewService

from .adapters import normalize, page, request
from .catalog import PROVIDERS
from .credentials import load_credentials
from .http import APIError, get_json, redact


def save(path: Path, value: Any) -> str:
    payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    # Exclusive creation preserves search evidence and prevents accidental overwrites.
    with path.open("xb") as stream:
        stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


def search(
    project: Path,
    provider: str,
    query: str,
    max_results: int = 100,
    run_id: str | None = None,
    fetch: Callable[[str, dict, dict], dict] | None = None,
) -> dict:
    if provider not in PROVIDERS:
        raise ValueError("Unknown API provider; use search-providers")
    if not query.strip() or len(query) > 10000:
        raise ValueError("Query must contain 1–10000 characters")
    if not 1 <= max_results <= 10000:
        raise ValueError("max-results must be between 1 and 10000")
    run_id = run_id or f"{provider}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", run_id):
        raise ValueError("run-id must be a safe filename of at most 120 characters")
    keys = load_credentials(provider, project)
    spec = PROVIDERS[provider]
    if any(not keys.get(field) for field in spec.required):
        raise ValueError(
            "This provider requires an API key; use credentials or its documented environment variable"
        )
    secrets = tuple(keys.values())
    if redact(query, secrets) != query or redact(run_id, secrets) != run_id:
        raise ValueError("The query contains a configured credential; remove it before searching")
    directory = project.resolve() / "data" / "searches" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "provider": provider,
        "query": query,
        "searched_at": datetime.now(UTC).isoformat(),
        "endpoint": spec.endpoint,
        "max_results": max_results,
        "pages": [],
        "status": "failed",
        "truncated": True,
        "records_count": 0,
        "note": "API totals and exhaustion describe this query/interface, not exhaustive review coverage.",
    }
    records, seen = [], set()
    cursor = None
    size = min(spec.page_size, max_results)
    failure = None
    try:
        for number in range(1, 101):
            params, headers = request(provider, query, cursor, size, keys)
            response = redact((fetch or get_json)(spec.endpoint, params, headers), secrets)
            filename = f"page-{number:04d}.json"
            digest = save(directory / filename, response)
            manifest["pages"].append(
                {"file": filename, "sha256": digest, "parameters": redact(params, secrets)}
            )
            rows, total, following = page(provider, response, cursor, size)
            manifest["provider_total"] = total
            remaining = max_results - len(records)
            for row in rows[:remaining]:
                record = normalize(provider, row)
                if record["source_record_id"] in seen:
                    raise ValueError(
                        "Repeated provider record across pages; repeat the search with a narrower query"
                    )
                seen.add(record["source_record_id"])
                record["metadata"].update({"search_run_id": run_id, "response_file": filename})
                records.append(record)
            if len(rows) > remaining:
                manifest["stop_reason"] = "max_results"
                break
            if len(records) >= total and provider != "semantic-scholar":
                manifest.update(truncated=False, stop_reason="provider_total_reached")
                break
            if not rows or (following is None and not (provider == "openalex" and not keys)):
                # A short or missing page before a stated total is not proof of completeness.
                complete = provider == "semantic-scholar" and not following or len(records) >= total
                manifest.update(truncated=not complete, stop_reason="provider_paging_ended")
                break
            if len(records) >= max_results:
                manifest["stop_reason"] = "max_results"
                break
            if provider == "openalex" and not keys:
                manifest["stop_reason"] = "api_key_required_for_paging"
                break
            cursor = following
        else:
            manifest["stop_reason"] = "page_limit"
        manifest["status"] = "completed"
    except (ValueError, TypeError, KeyError, OSError, AttributeError, IndexError) as error:
        # Do not serialize arbitrary provider errors, rows, URLs or transport credentials.
        failure = error
        manifest["stop_reason"] = "request_or_metadata_failure"
        manifest["error"] = (
            str(error)
            if isinstance(error, APIError)
            else "Invalid provider metadata or local archive failure"
        )
    except (KeyboardInterrupt, EOFError) as error:
        failure = error
        manifest["stop_reason"] = "interrupted"
    finally:
        manifest["records_count"] = len(records)
        manifest["records_sha256"] = save(directory / "records.json", records)
        save(directory / "manifest.json", manifest)
    if failure is not None:
        raise ValueError(
            f"Search failed; partial evidence preserved in {directory}. Nothing was imported. {manifest.get('error', 'Search interrupted')}. Retry with a new run ID."
        ) from None
    return {"manifest": str(directory / "manifest.json"), **manifest}


def import_search(current: ReviewService, manifest_path: Path, source: str) -> dict:
    """Verify archived evidence, then use the existing approved import transaction."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "completed":
        raise ValueError("Only completed version-1 search bundles can be imported")
    provider = manifest["provider"]
    if provider not in PROVIDERS or manifest.get("endpoint") != PROVIDERS[provider].endpoint:
        raise ValueError("Unknown provider/interface in search manifest")
    configured = next((s for s in current.config.protocol.sources if s.id == source), None)
    if configured is None or configured.limits.get("api_provider", configured.id) != provider:
        raise ValueError(
            "Configure this source with its provider ID or limits.api_provider in protocol.yaml, initialize and have a human approve the revision"
        )
    if not isinstance(manifest.get("truncated"), bool):
        raise TypeError("Search manifest requires a Boolean truncated flag")
    directory = manifest_path.resolve().parent
    records_path = directory / "records.json"
    checks = [(records_path, manifest["records_sha256"])]
    for entry in manifest["pages"]:
        if not re.fullmatch(r"page-[0-9]{4}\.json", entry["file"]):
            raise ValueError("Unsafe response filename in manifest")
        checks.append((directory / entry["file"], entry["sha256"]))
    for path, digest in checks:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Search evidence checksum mismatch or symlink; nothing was imported")
    if len(json.loads(records_path.read_text(encoding="utf-8"))) != manifest["records_count"]:
        raise ValueError("Search record count mismatch")
    return current.import_records(
        records_path,
        manifest["run_id"],
        source,
        manifest["query"],
        manifest["searched_at"],
        manifest["truncated"],
    )
