"""Resumable search evidence, separate from gated and idempotent review imports."""

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
from .archive import digest, read_json, run_lock, save, verify_bundle
from .catalog import PROVIDERS
from .credentials import load_credentials
from .http import APIError, get_json, redact

NOTE = "API totals and exhaustion describe this query/interface, not exhaustive review coverage."


class PaginationError(ValueError):
    """A local, safe diagnostic with an explicit stop code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def search(
    project: Path,
    provider: str,
    query: str,
    max_results: int = 100,
    run_id: str | None = None,
    fetch: Callable[[str, dict, dict], dict] | None = None,
    *,
    resume: bool = False,
    dry_run: bool = False,
    max_pages: int = 100,
    max_requests: int = 100,
    allow_credentials: bool = False,
) -> dict:
    """Plan, start or resume a fixed native query without changing review state.

    Caps bound the cumulative run, including previous sessions. Increasing a cap
    on resume does not change the query. Credentials are never read without the
    explicit opt-in; dry runs never read credentials or contact a provider.
    """
    if provider not in PROVIDERS:
        raise ValueError("Unknown API provider; use search-providers")
    if not query.strip() or len(query) > 10000:
        raise ValueError("Query must contain 1–10000 characters")
    if (
        not 1 <= max_results <= 100000
        or not 1 <= max_pages <= 9999
        or not 1 <= max_requests <= 30000
    ):
        raise ValueError("Caps: max-results 1–100000, max-pages 1–9999, max-requests 1–30000")
    if resume and not run_id:
        raise ValueError("Resume requires the original run-id and unchanged provider/query")
    run_id = run_id or f"{provider}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", run_id):
        raise ValueError("run-id must be a safe filename of at most 120 characters")
    directory = project.resolve() / "data" / "searches" / run_id
    spec = PROVIDERS[provider]
    size = min(spec.page_size, max_results)
    run = None
    if resume:
        if not (directory / "run.json").is_file():
            raise ValueError(
                "Only version-2 runs can be resumed; preserve legacy pilots and start a new run"
            )
        run = read_json(directory / "run.json")
        if run.get("schema_version") != 2 or (
            run.get("provider"),
            run.get("query"),
            run.get("run_id"),
            run.get("endpoint"),
        ) != (provider, query, run_id, spec.endpoint):
            raise ValueError("Provider/query/interface changes require a new stable run-id")
        size = run["page_size"]
        if (directory / "checkpoint.json").is_file():
            previous = read_json(directory / "checkpoint.json")
            if max_results < previous["max_results"]:
                raise ValueError(
                    "A resumed run cannot lower max-results; use the previous or a larger cap"
                )
    elif directory.exists():
        raise FileExistsError(f"Search run already exists: {directory}; use resume or a new run-id")
    if dry_run:
        params, _ = request(provider, query, None, size, {})
        return {
            "status": "planned",
            "run_id": run_id,
            "provider": provider,
            "query": query,
            "endpoint": spec.endpoint,
            "first_page_parameters": redact(params, ()),
            "max_results": max_results,
            "max_pages": max_pages,
            "max_requests": max_requests,
            "resume": resume,
            "credential_use_requested": allow_credentials,
            "credentials_required": list(spec.required),
            "minimum_request_interval_seconds": spec.minimum_interval,
            "note": "No requests, credentials, archives, imports or review decisions were made. Key use may consume paid quota; inspect the provider plan first.",
        }
    keys = load_credentials(provider, project) if allow_credentials else {}
    if any(not keys.get(field) for field in spec.required):
        raise ValueError(
            "This provider requires an API key; configure it yourself and explicitly allow credentials after checking API costs"
        )
    secrets = tuple(keys.values())
    if redact(query, secrets) != query or redact(run_id, secrets) != run_id:
        raise ValueError(
            "The query or run-id contains a configured credential; remove it before searching"
        )
    if not resume:
        directory.mkdir(parents=True, exist_ok=False)
        run = {
            "schema_version": 2,
            "run_id": run_id,
            "provider": provider,
            "query": query,
            "searched_at": datetime.now(UTC).isoformat(),
            "endpoint": spec.endpoint,
            "page_size": size,
            "note": NOTE,
        }
        save(directory / "run.json", run)
    with run_lock(directory):
        return _continue(directory, run, keys, secrets, max_results, max_pages, max_requests, fetch)


def _continue(
    directory: Path,
    run: dict,
    keys: dict,
    secrets: tuple[str, ...],
    max_results: int,
    max_pages: int,
    max_requests: int,
    fetch: Callable | None,
) -> dict:
    provider, query, size = run["provider"], run["query"], run["page_size"]
    manifest = {
        **run,
        "run_sha256": digest(run),
        "max_results": max_results,
        "max_pages": max_pages,
        "max_requests": max_requests,
        "pages": [],
        "status": "running",
        "truncated": True,
        "records_count": 0,
        "fetched_count": 0,
        "stop_reason": "running",
    }
    records: list[dict] = []
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()
    seen_pages: set[str] = set()
    cursor: Any = "*" if provider in {"crossref", "openalex"} else None
    failure = None
    prior = (
        read_json(directory / "checkpoint.json") if (directory / "checkpoint.json").exists() else {}
    )
    if (
        prior
        and prior.get("run_sha256")
        != hashlib.sha256((directory / "run.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Search run definition checksum mismatch; do not resume")
    expected_hashes = prior.get(
        "archived_page_hashes", {entry["file"]: entry["sha256"] for entry in prior.get("pages", [])}
    )
    for filename, expected in expected_hashes.items():
        if not re.fullmatch(r"page-[0-9]{4}\.json", filename):
            raise ValueError("Unsafe archived page filename")
        path = directory / filename
        if (
            path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Archived page checksum mismatch; do not resume")
    manifest["archived_page_hashes"] = dict(expected_hashes)
    attempts = sorted(directory.glob("request-[0-9][0-9][0-9][0-9][0-9][0-9].json"))
    if [p.name for p in attempts] != [
        f"request-{i:06d}.json" for i in range(1, len(attempts) + 1)
    ] or any(p.is_symlink() for p in attempts):
        raise ValueError("Missing or unsafe archived request receipts")
    if len(attempts) < prior.get("request_count", 0):
        raise ValueError("Archived request receipts are missing; do not reset the request budget")
    request_hashes = prior.get("request_receipt_hashes", {})
    for filename, expected in request_hashes.items():
        if not re.fullmatch(r"request-[0-9]{6}\.json", filename):
            raise ValueError("Unsafe request receipt filename")
        path = directory / filename
        if (
            path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Archived request receipt checksum mismatch")
    manifest["request_receipt_hashes"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in attempts
    }
    manifest["request_count"] = len(attempts)

    def checkpoint() -> None:
        manifest["records_count"] = len(records)
        manifest["next_cursor"] = cursor
        manifest["updated_at"] = datetime.now(UTC).isoformat()
        save(directory / "checkpoint.json", manifest, replace=True)

    def accept(path: Path, envelope: dict) -> bool:
        """Replay one successful response; return True at provider exhaustion."""
        nonlocal cursor
        envelope_hash = digest(envelope)
        if envelope.get("access_mode") not in {"anonymous", "configured_credentials"}:
            raise ValueError("Invalid archived access mode")
        archived_keys = (
            {"api_key": "ARCHIVED-KEY"}
            if envelope["access_mode"] == "configured_credentials"
            else {}
        )
        expected_params, _ = request(provider, query, cursor, size, archived_keys)
        if envelope.get("parameters") != redact(expected_params, ("ARCHIVED-KEY",)):
            raise ValueError("Archived request differs from the immutable query/paging definition")
        receipts = envelope.get("request_receipts")
        if not isinstance(receipts, list) or not receipts:
            raise ValueError("Archived response lacks its physical request receipt")
        for receipt_name in receipts:
            if receipt_name not in manifest["request_receipt_hashes"]:
                raise ValueError("Archived response refers to a missing request receipt")
            receipt = read_json(directory / receipt_name)
            if (
                any(
                    receipt.get(field) != envelope.get(field)
                    for field in ("parameters", "requested_cursor", "access_mode")
                )
                or receipt.get("endpoint") != run["endpoint"]
            ):
                raise ValueError("Archived request receipt does not match its response")
        if path.name in expected_hashes and expected_hashes[path.name] != envelope_hash:
            raise ValueError("Archived page checksum mismatch")
        if envelope.get("requested_cursor") != cursor or envelope.get("response_sha256") != digest(
            envelope["response"]
        ):
            raise ValueError("Archived page cursor or response checksum mismatch")
        cursor_key = json.dumps(cursor, sort_keys=True)
        if cursor_key in seen_cursors and provider == "crossref":
            manifest.setdefault("warnings", []).append(
                {
                    "code": "repeated_crossref_cursor",
                    "page": path.name,
                    "note": "Crossref historically used stateful repeated cursors; page hashes and source IDs must still advance. Current API documentation recommends updating cursors every page.",
                }
            )
        elif cursor_key in seen_cursors:
            raise PaginationError(
                "repeated_cursor", "Repeated provider cursor; investigate before starting a new run"
            )
        seen_cursors.add(cursor_key)
        manifest["archived_page_hashes"][path.name] = envelope_hash
        response_hash = envelope["response_sha256"]
        if response_hash in seen_pages:
            raise PaginationError(
                "repeated_page",
                "Repeated provider response page; investigate before starting a new run",
            )
        seen_pages.add(response_hash)
        rows, total, following = page(provider, envelope["response"], cursor, size)
        normalized = []
        for row in rows:
            record = normalize(provider, row)
            if record["source_record_id"] in seen_ids:
                raise PaginationError(
                    "duplicate_source_id",
                    "Repeated source record ID; overlap requires investigation",
                )
            seen_ids.add(record["source_record_id"])
            record["metadata"].update({"search_run_id": run["run_id"], "response_file": path.name})
            normalized.append(record)
        remaining = max(0, max_results - len(records))
        records.extend(normalized[:remaining])
        manifest["fetched_count"] += len(rows)
        manifest["provider_total"] = total
        manifest["pages"].append(
            {
                "file": path.name,
                "sha256": envelope_hash,
                "parameters": envelope["parameters"],
                "requested_at": envelope["requested_at"],
                "received_at": envelope["received_at"],
                "requested_cursor": cursor,
                "next_cursor": following,
                "rows_count": len(rows),
                "response_sha256": response_hash,
                "access_mode": envelope["access_mode"],
            }
        )
        cursor = following
        # Semantic Scholar totals are estimates: token exhaustion governs it.
        exhausted = (
            not following if provider == "semantic-scholar" else manifest["fetched_count"] >= total
        )
        if exhausted and len(records) == manifest["fetched_count"]:
            manifest.update(
                truncated=False,
                stop_reason="provider_total_reached"
                if provider != "semantic-scholar"
                else "provider_paging_ended",
            )
            return True
        if len(normalized) > remaining:
            manifest["stop_reason"] = "max_results"
            return True
        if not rows or following is None:
            manifest["stop_reason"] = "provider_paging_ended"
            return True
        return False

    try:
        archived = sorted(directory.glob("page-[0-9][0-9][0-9][0-9].json"))
        expected_names = [f"page-{i:04d}.json" for i in range(1, len(archived) + 1)]
        if [p.name for p in archived] != expected_names or set(expected_hashes) - set(
            expected_names
        ):
            raise ValueError("Missing or non-contiguous archived search pages")
        exhausted = False
        for archived_page in archived:
            exhausted = accept(archived_page, read_json(archived_page))
            if exhausted and archived_page != archived[-1]:
                raise ValueError("Archived pages continue beyond provider exhaustion")
        # A fully exhausted run is an offline, idempotent resume.
        if exhausted:
            manifest["status"] = "completed"
        else:
            while True:
                if len(records) >= max_results:
                    manifest["stop_reason"] = "max_results"
                    break
                if len(manifest["pages"]) >= max_pages:
                    manifest["stop_reason"] = "page_limit"
                    break
                if manifest["request_count"] >= max_requests:
                    manifest["stop_reason"] = "request_limit"
                    break
                if provider == "arxiv" and (cursor or 0) >= 30000:
                    manifest["stop_reason"] = "provider_offset_limit"
                    break
                if provider == "openalex" and manifest["pages"] and not keys:
                    manifest["stop_reason"] = "api_key_required_for_paging"
                    break
                if provider != "crossref" and json.dumps(cursor, sort_keys=True) in seen_cursors:
                    raise PaginationError(
                        "repeated_cursor", "Repeated provider cursor; refusing another request"
                    )
                params, headers = request(provider, query, cursor, size, keys)
                requested_at = datetime.now(UTC).isoformat()
                attempt_start = manifest["request_count"]

                def before_attempt(params: dict = params, requested_cursor: Any = cursor) -> None:
                    if manifest["request_count"] >= max_requests:
                        raise APIError(
                            "Physical request budget reached; resume with a larger explicit cap"
                        )
                    manifest["request_count"] += 1
                    receipt_name = f"request-{manifest['request_count']:06d}.json"
                    manifest["request_receipt_hashes"][receipt_name] = save(
                        directory / receipt_name,
                        {
                            "requested_at": datetime.now(UTC).isoformat(),
                            "requested_cursor": requested_cursor,
                            "endpoint": run["endpoint"],
                            "parameters": redact(params, secrets),
                            "access_mode": "configured_credentials" if keys else "anonymous",
                        },
                    )
                    checkpoint()

                if fetch is None:
                    response = get_json(
                        run["endpoint"], params, headers, before_attempt=before_attempt
                    )
                else:
                    before_attempt()
                    response = fetch(run["endpoint"], params, headers)
                response = redact(response, secrets)
                envelope = {
                    "parameters": redact(params, secrets),
                    "requested_cursor": cursor,
                    "request_receipts": [
                        f"request-{i:06d}.json"
                        for i in range(attempt_start + 1, manifest["request_count"] + 1)
                    ],
                    "requested_at": requested_at,
                    "received_at": datetime.now(UTC).isoformat(),
                    "access_mode": "configured_credentials" if keys else "anonymous",
                    "response": response,
                    "response_sha256": digest(response),
                }
                filename = directory / f"page-{len(manifest['pages']) + 1:04d}.json"
                manifest["archived_page_hashes"][filename.name] = save(filename, envelope)
                checkpoint()
                exhausted = accept(filename, envelope)
                checkpoint()
                if exhausted:
                    break
            manifest["status"] = "completed"
    except (ValueError, TypeError, KeyError, OSError, AttributeError, IndexError) as error:
        failure = error
        manifest["status"] = "failed"
        manifest["stop_reason"] = (
            "request_limit"
            if isinstance(error, APIError) and "request budget" in str(error).lower()
            else "request_or_metadata_failure"
        )
        if isinstance(error, PaginationError):
            manifest["stop_reason"] = error.code
        manifest["error"] = (
            redact(str(error), secrets)
            if isinstance(error, (APIError, PaginationError))
            else "Invalid provider metadata, repeated pagination/IDs or local archive failure"
        )
    except (KeyboardInterrupt, EOFError) as error:
        failure = error
        manifest.update(status="failed", stop_reason="interrupted")
    finally:
        # Until all latest pointers exist, a crash must leave an in-progress
        # checkpoint rather than falsely presenting an older snapshot as current.
        final_status = manifest["status"]
        manifest["status"] = "running"
        checkpoint()
        manifest["status"] = final_status
        snapshots = list(directory.glob("manifest-[0-9][0-9][0-9][0-9][0-9][0-9].json"))
        revision = max((int(p.stem.split("-")[-1]) for p in snapshots), default=0) + 1
        # Interrupted earlier finalization may have left an orphan records snapshot.
        while (directory / f"records-{revision:06d}.json").exists():
            revision += 1
        manifest["records_file"] = f"records-{revision:06d}.json"
        manifest["records_sha256"] = save(directory / manifest["records_file"], records)
        snapshot = directory / f"manifest-{revision:06d}.json"
        save(snapshot, manifest)
        save(directory / "records.json", records, replace=True)
        save(directory / "manifest.json", manifest, replace=True)
        save(directory / "checkpoint.json", manifest, replace=True)
    if failure is not None:
        raise ValueError(
            f"Search failed; partial evidence preserved in {directory}. Nothing was imported. {manifest.get('error', 'Search interrupted')}. Resume the unchanged run after resolving the problem; query changes need a new run ID."
        ) from None
    return {
        "manifest": str(snapshot),
        "latest_manifest": str(directory / "manifest.json"),
        **manifest,
    }


def import_search(current: ReviewService, manifest_path: Path, source: str) -> dict:
    """Verify archived evidence, then use the existing approved import transaction."""
    manifest, records_path = verify_bundle(manifest_path)
    provider = manifest["provider"]
    configured = next((s for s in current.config.protocol.sources if s.id == source), None)
    if configured is None or configured.limits.get("api_provider", configured.id) != provider:
        raise ValueError(
            "Configure this source with its provider ID or limits.api_provider in protocol.yaml, initialize and have a human approve the revision"
        )
    return current.import_records(
        records_path,
        manifest["run_id"],
        source,
        manifest["query"],
        manifest["searched_at"],
        manifest["truncated"],
    )
