"""Step-by-step argparse/Rich interface for humans and structured agent tool calls."""

from __future__ import annotations

import json
import sqlite3
import sys
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from ..config import load_configuration
from ..models import Draft
from ..reporting import export_snapshot, snapshot
from ..service import ReviewService
from .parser import build_parser

# Avoid Rich's legacy Win32/ctypes console detection while retaining its prompts.
console = Console(legacy_windows=False, color_system=None)


def execute(operation: Callable[[], Any]) -> None:
    """Keep machine-readable results separate from concise validation failures."""
    try:
        result = operation()
        if result is not None:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def require_terminal() -> None:
    """Reject piped approvals; this is a usability guard, not an identity security boundary."""
    if not sys.stdin.isatty():
        raise ValueError(
            "Human approval requires an interactive terminal. Open a separate VS Code terminal."
        )


def initialize(current: ReviewService) -> None:
    """Initialize SQLite and register the exact configuration revision."""
    execute(
        lambda: {
            "protocol_revision": current.initialize(),
            "database": current.config.database,
        }
    )


def approve_protocol(current: ReviewService, reviewer: str) -> None:
    """Review and sign the current protocol from a human-operated terminal."""

    def action() -> dict[str, Any]:
        require_terminal()
        console.print(Panel(Text(current.config.protocol_yaml), title="Protocol to approve"))
        console.print(Panel(Text(current.config.workflow_yaml), title="Workflow to approve"))
        reason = Prompt.ask("Approval reason or amendment justification", console=console)
        if not Confirm.ask("Approve this exact revision?", default=False, console=console):
            return {"approved": False}
        current.approve_protocol(reviewer, reason)
        return {"approved": True, "protocol_revision": current.config.revision}

    execute(action)


def import_records(
    current: ReviewService,
    path: Path,
    run_id: str,
    source: str,
    query: str,
    searched_at: str,
    truncated: bool = False,
) -> None:
    """Import a recorded search export in JSON or CSV format."""
    execute(lambda: current.import_records(path, run_id, source, query, searched_at, truncated))


def records(current: ReviewService) -> None:
    """List source records with stable record and publication identifiers."""
    execute(lambda: current.records())


def deduplicate(current: ReviewService) -> None:
    """Mark exact DOI-based duplicates while preserving every source record."""
    execute(lambda: current.deduplicate())


def workflow(current: ReviewService) -> None:
    """Expose the editable workflow to the current OpenCode model."""
    execute(
        lambda: {
            "revision": current.config.revision,
            "workflow": current.config.workflow.model_dump(),
        }
    )


def packet(current: ReviewService, stage: str, entity_id: str, output: Path | None = None) -> None:
    """Export an evidence packet and draft skeleton for one workflow stage."""

    def action() -> dict[str, Any]:
        result = current.packet(stage, entity_id)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"packet": str(output), "protocol_revision": result["protocol_revision"]}
        return result

    execute(action)


def submit(current: ReviewService, draft: Path) -> None:
    """Validate an agent draft and persist it as a proposal, without changing eligibility."""
    execute(lambda: {"proposal_id": current.submit(draft), "status": "awaiting_human_review"})


def proposal(current: ReviewService, proposal_id: str) -> None:
    """Read a stored proposal without granting approval."""
    execute(lambda: current.proposal(proposal_id).model_dump())


def review(
    current: ReviewService,
    proposal_id: str,
    reviewer: str,
    decision_file: Path | None = None,
    adjudicate: bool = False,
) -> None:
    """Accept, modify or defer a proposal; persist a new human decision."""

    def action() -> dict[str, Any]:
        require_terminal()
        original = current.proposal(proposal_id)
        revised = (
            Draft.model_validate_json(decision_file.read_text(encoding="utf-8"))
            if decision_file
            else original
        )
        console.print(
            Panel(Text(revised.model_dump_json(indent=2)), title="Evidence and proposed decision")
        )
        console.print("Verify the quoted source and interpretation before approving.")
        choice = Prompt.ask(
            "Action", choices=["accept", "modify", "defer"], default="defer", console=console
        )
        if choice == "defer":
            return {"proposal_id": proposal_id, "status": "deferred"}
        if choice == "modify":
            stage = current.config.stage(original.stage)
            revised = revised.model_copy(
                update={
                    "suggestion": Prompt.ask("Decision", choices=stage.choices, console=console),
                    "rationale": Prompt.ask("Human justification", console=console),
                    "criteria": [
                        c.strip()
                        for c in Prompt.ask(
                            "Criterion IDs, comma separated", default="", console=console
                        ).split(",")
                        if c.strip()
                    ],
                }
            )
            console.print(
                "To change values or evidence, edit a JSON decision file and rerun with --decision-file."
            )
        if adjudicate and not Confirm.ask(
            "Record this as explicit disagreement adjudication?", default=False, console=console
        ):
            return {"status": "deferred"}
        if not Confirm.ask("Save this human decision?", default=False, console=console):
            return {"status": "deferred"}
        decision_id = current.decide(proposal_id, reviewer, revised, adjudicate)
        return {"decision_id": decision_id, "status": "human_decision_recorded"}

    execute(action)


def attach(current: ReviewService, report_id: str, path: Path, kind: str = "markdown") -> None:
    """Archive a PDF or manually converted Markdown with a content hash."""
    execute(lambda: {"document_id": current.attach(report_id, path, kind)})


def retrieval(
    current: ReviewService,
    report_id: str,
    status: str,
    reviewer: str,
    reason: str,
) -> None:
    """Record a human-confirmed retrieval attempt or non-retrieval outcome."""

    def action() -> dict[str, str]:
        require_terminal()
        if Confirm.ask(f"Record retrieval status {status}?", default=False, console=console):
            current.retrieval_status(report_id, status, reason, reviewer)
            return {"status": status}
        return {"status": "deferred"}

    execute(action)


def link_study(
    current: ReviewService,
    report_id: str,
    study_id: str,
    reviewer: str,
    label: str,
) -> None:
    """Associate a publication with an underlying investigation after human confirmation."""

    def action() -> dict[str, str]:
        require_terminal()
        if Confirm.ask(f"Link {report_id} to study {study_id}?", default=False, console=console):
            current.link_study(report_id, study_id, label, reviewer)
            return {"study_id": study_id}
        return {"status": "deferred"}

    execute(action)


def status(current: ReviewService, at_sequence: int | None = None) -> None:
    """Show counts and unresolved work without LLM-generated arithmetic."""
    execute(lambda: snapshot(current, at_sequence))


def unlink_study(
    current: ReviewService,
    report_id: str,
    study_id: str,
    reviewer: str,
    reason: str,
) -> None:
    """Correct an association without deleting its original audit event."""

    def action() -> dict[str, str]:
        require_terminal()
        if Confirm.ask(
            f"Unlink {report_id} from study {study_id}?", default=False, console=console
        ):
            current.unlink_study(report_id, study_id, reason, reviewer)
            return {"status": "study_unlinked"}
        return {"status": "deferred"}

    execute(action)


def report(current: ReviewService, at_sequence: int | None = None) -> None:
    """Export PRISMA count JSON, screening/summary CSV, LaTeX and a hash manifest."""
    execute(lambda: {"export_directory": export_snapshot(current, at_sequence)})


def audit(current: ReviewService) -> None:
    """Verify the event hash chain, SQLite integrity and archived document bytes."""

    from ..audit import audit_review

    execute(lambda: audit_review(current))


def schema(current: ReviewService, output: Path = Path("schemas/draft.schema.json")) -> None:
    """Export the dataclass JSON schema; protocol-specific rules are validated on submission."""

    def action() -> dict[str, str]:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(Draft.model_json_schema(), indent=2), encoding="utf-8")
        return {"schema": str(output)}

    execute(action)


def search_corpus(current: ReviewService, query: str, limit: int = 10) -> None:
    """Retrieve literal source fragments from human-included publications."""
    execute(lambda: current.search_corpus(query, limit))


def convert(current: ReviewService, report_id: str, pdf: Path) -> None:
    """Convert a PDF through the optional Docling adapter, preserving source anchors."""
    from ..integrations import convert_document

    execute(lambda: convert_document(current, report_id, pdf))


def index_corpus(current: ReviewService) -> None:
    """Build the optional local Chroma index from included publications."""
    from ..integrations import index_corpus as build_index

    execute(lambda: build_index(current))


def retrieve(current: ReviewService, query: str, limit: int = 5) -> None:
    """Retrieve semantic evidence using the optional Chroma adapter."""
    from ..integrations import retrieve as semantic_retrieve

    execute(lambda: semantic_retrieve(current, query, limit))


def import_search_bundle(current: ReviewService, manifest_path: Path, source: str) -> None:
    """Import a verified scientific search bundle through the existing protocol gates."""
    from ..search.service import import_search

    execute(lambda: import_search(current, manifest_path, source))


def search_coverage(current: ReviewService, seeds: Path | None = None) -> None:
    """Inspect per-run completeness and optional user-verified seed sensitivity."""
    from ..coverage import search_coverage as coverage

    execute(lambda: coverage(current, seeds))


def pending_review(current: ReviewService, **filters: Any) -> None:
    """List pending recommendations and human-review blockers without recording decisions."""
    from ..review_support import inspect_queue

    if filters.get("unblind"):
        execute(require_terminal)
    execute(lambda: inspect_queue(current, **filters))


def review_sheet(current: ReviewService, **filters: Any) -> None:
    """Generate a numbered review package with individual human command handoffs."""
    from ..review_support import export_review_package

    if filters.get("unblind"):
        execute(require_terminal)
    execute(lambda: {"package_directory": export_review_package(current, **filters)})


def pilot_evaluation(current: ReviewService, **filters: Any) -> None:
    """Compare recorded human judgments with proposals while retaining uncertainty."""
    from ..review_support import evaluate_pilot

    if filters.get("unblind"):
        execute(require_terminal)
    execute(lambda: evaluate_pilot(current, **filters))


def duplicate_candidates(
    current: ReviewService,
    limit: int = 100,
    max_comparisons: int = 50000,
    title_threshold: float = 0.9,
    output: Path | None = None,
) -> None:
    """Present uncertain bibliographic identities; never merge records or link studies."""
    from ..duplicate_candidates import candidates, export_candidates

    options = {
        "limit": limit,
        "max_comparisons": max_comparisons,
        "title_threshold": title_threshold,
    }
    if output:
        execute(lambda: export_candidates(current, current.config.root / output, **options))
    else:
        execute(lambda: candidates(current, **options))


def app(argv: Sequence[str] | None = None) -> None:
    """Shared entry point for the optional slr launcher and python -m slr_workbench."""
    parser = build_parser()
    args = vars(parser.parse_args(argv))
    selected = args.pop("command")
    if selected is None:
        parser.print_help()
        raise SystemExit(2)
    handler = args.pop("handler")
    project = args.pop("project")
    if selected in {"backup", "backup-verify", "restore"}:
        from ..backups import create_backup, restore_backup, verify_backup

        if selected == "backup":
            execute(lambda: create_backup(project, args["destination"]))
        elif selected == "backup-verify":
            execute(lambda: verify_backup(args["archive"]))
        else:
            execute(lambda: restore_backup(args["archive"], args["destination"]))
        return
    if selected in {"search-providers", "credentials", "search-literature"}:
        from ..search.catalog import catalog
        from ..search.credentials import configure_credentials
        from ..search.service import search

        if selected == "search-providers":
            execute(catalog)
        elif selected == "credentials":
            execute(lambda: configure_credentials(project, **args))
        else:
            execute(lambda: search(project, **args))
        return
    if selected == "read-pdf":
        from ..pdf_reader import read_pdf

        execute(lambda: read_pdf(args["pdf"], args["output_dir"] or project / "data" / "reading"))
        return
    try:
        current = ReviewService(load_configuration(project))
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    try:
        handler(current, **args)
    except (EOFError, KeyboardInterrupt):
        print("Aborted; no confirmation recorded.", file=sys.stderr)
        raise SystemExit(1) from None
