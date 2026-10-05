"""Step-by-step Typer/Rich interface for humans and structured agent tool calls."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from .config import load_configuration
from .models import Draft
from .reporting import export_snapshot, snapshot
from .service import ReviewService

app = typer.Typer(no_args_is_help=True, help="Evidence-grounded SLR services for OpenCode.")
console = Console()


def execute(operation: Callable[[], Any]) -> None:
    """Keep machine-readable results separate from concise validation failures."""
    try:
        result = operation()
        if result is not None:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except (ValueError, TypeError, OSError, sqlite3.Error) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error


@app.callback()
def main(
    ctx: typer.Context, project: Annotated[Path, typer.Option("--project")] = Path(".")
) -> None:
    """Resolve project files independently of the shell's current working directory."""
    try:
        ctx.obj = ReviewService(load_configuration(project))
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from error


def service(ctx: typer.Context) -> ReviewService:
    return ctx.obj


def require_terminal() -> None:
    """Reject piped approvals; this is a usability guard, not an identity security boundary."""
    if not sys.stdin.isatty():
        raise ValueError(
            "Human approval requires an interactive terminal. Open a separate VS Code terminal."
        )


@app.command("init")
def initialize(ctx: typer.Context) -> None:
    """Initialize SQLite and register the exact configuration revision."""
    execute(
        lambda: {
            "protocol_revision": service(ctx).initialize(),
            "database": service(ctx).config.database,
        }
    )


@app.command("approve-protocol")
def approve_protocol(ctx: typer.Context, reviewer: str = typer.Option(...)) -> None:
    """Review and sign the current protocol from a human-operated terminal."""

    def action() -> dict[str, Any]:
        require_terminal()
        current = service(ctx)
        console.print(Panel(Text(current.config.protocol_yaml), title="Protocol to approve"))
        console.print(Panel(Text(current.config.workflow_yaml), title="Workflow to approve"))
        reason = Prompt.ask("Approval reason or amendment justification")
        if not Confirm.ask("Approve this exact revision?", default=False):
            return {"approved": False}
        current.approve_protocol(reviewer, reason)
        return {"approved": True, "protocol_revision": current.config.revision}

    execute(action)


@app.command("import-records")
def import_records(
    ctx: typer.Context,
    path: Path,
    run_id: str = typer.Option(...),
    source: str = typer.Option(...),
    query: str = typer.Option(...),
    searched_at: str = typer.Option(...),
    truncated: bool = False,
) -> None:
    """Import a recorded search export in JSON or CSV format."""
    execute(
        lambda: service(ctx).import_records(path, run_id, source, query, searched_at, truncated)
    )


@app.command("records")
def records(ctx: typer.Context) -> None:
    """List source records with stable record and publication identifiers."""
    execute(lambda: service(ctx).records())


@app.command("deduplicate")
def deduplicate(ctx: typer.Context) -> None:
    """Mark exact DOI-based duplicates while preserving every source record."""
    execute(lambda: service(ctx).deduplicate())


@app.command("workflow")
def workflow(ctx: typer.Context) -> None:
    """Expose the editable workflow to the current OpenCode model."""
    execute(
        lambda: {
            "revision": service(ctx).config.revision,
            "workflow": service(ctx).config.workflow.model_dump(),
        }
    )


@app.command("packet")
def packet(ctx: typer.Context, stage: str, entity_id: str, output: Path | None = None) -> None:
    """Export an evidence packet and draft skeleton for one workflow stage."""

    def action() -> dict[str, Any]:
        result = service(ctx).packet(stage, entity_id)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"packet": str(output), "protocol_revision": result["protocol_revision"]}
        return result

    execute(action)


@app.command("submit")
def submit(ctx: typer.Context, draft: Path) -> None:
    """Validate an agent draft and persist it as a proposal, without changing eligibility."""
    execute(lambda: {"proposal_id": service(ctx).submit(draft), "status": "awaiting_human_review"})


@app.command("proposal")
def proposal(ctx: typer.Context, proposal_id: str) -> None:
    """Read a stored proposal without granting approval."""
    execute(lambda: service(ctx).proposal(proposal_id).model_dump())


@app.command("review")
def review(
    ctx: typer.Context,
    proposal_id: str,
    reviewer: str = typer.Option(...),
    decision_file: Path | None = None,
    adjudicate: bool = False,
) -> None:
    """Accept, modify or defer a proposal; persist a new human decision."""

    def action() -> dict[str, Any]:
        require_terminal()
        current = service(ctx)
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
        choice = Prompt.ask("Action", choices=["accept", "modify", "defer"], default="defer")
        if choice == "defer":
            return {"proposal_id": proposal_id, "status": "deferred"}
        if choice == "modify":
            stage = current.config.stage(original.stage)
            revised = revised.model_copy(
                update={
                    "suggestion": Prompt.ask("Decision", choices=stage.choices),
                    "rationale": Prompt.ask("Human justification"),
                    "criteria": [
                        c.strip()
                        for c in Prompt.ask("Criterion IDs, comma separated", default="").split(",")
                        if c.strip()
                    ],
                }
            )
            console.print(
                "To change values or evidence, edit a JSON decision file and rerun with --decision-file."
            )
        if adjudicate and not Confirm.ask(
            "Record this as explicit disagreement adjudication?", default=False
        ):
            return {"status": "deferred"}
        if not Confirm.ask("Save this human decision?", default=False):
            return {"status": "deferred"}
        decision_id = current.decide(proposal_id, reviewer, revised, adjudicate)
        return {"decision_id": decision_id, "status": "human_decision_recorded"}

    execute(action)


@app.command("attach")
def attach(ctx: typer.Context, report_id: str, path: Path, kind: str = "markdown") -> None:
    """Archive a PDF or manually converted Markdown with a content hash."""
    execute(lambda: {"document_id": service(ctx).attach(report_id, path, kind)})


@app.command("retrieval")
def retrieval(
    ctx: typer.Context,
    report_id: str,
    status: str,
    reviewer: str = typer.Option(...),
    reason: str = typer.Option(...),
) -> None:
    """Record a human-confirmed retrieval attempt or non-retrieval outcome."""

    def action() -> dict[str, str]:
        require_terminal()
        if Confirm.ask(f"Record retrieval status {status}?", default=False):
            service(ctx).retrieval_status(report_id, status, reason, reviewer)
            return {"status": status}
        return {"status": "deferred"}

    execute(action)


@app.command("link-study")
def link_study(
    ctx: typer.Context,
    report_id: str,
    study_id: str,
    reviewer: str = typer.Option(...),
    label: str = typer.Option(...),
) -> None:
    """Associate a publication with an underlying investigation after human confirmation."""

    def action() -> dict[str, str]:
        require_terminal()
        if Confirm.ask(f"Link {report_id} to study {study_id}?", default=False):
            service(ctx).link_study(report_id, study_id, label, reviewer)
            return {"study_id": study_id}
        return {"status": "deferred"}

    execute(action)


@app.command("status")
def status(ctx: typer.Context, at_sequence: int | None = None) -> None:
    """Show counts and unresolved work without LLM-generated arithmetic."""
    execute(lambda: snapshot(service(ctx), at_sequence))


@app.command("unlink-study")
def unlink_study(
    ctx: typer.Context,
    report_id: str,
    study_id: str,
    reviewer: str = typer.Option(...),
    reason: str = typer.Option(...),
) -> None:
    """Correct an association without deleting its original audit event."""

    def action() -> dict[str, str]:
        require_terminal()
        if Confirm.ask(f"Unlink {report_id} from study {study_id}?", default=False):
            service(ctx).unlink_study(report_id, study_id, reason, reviewer)
            return {"status": "study_unlinked"}
        return {"status": "deferred"}

    execute(action)


@app.command("report")
def report(ctx: typer.Context, at_sequence: int | None = None) -> None:
    """Export PRISMA count JSON, screening/summary CSV, LaTeX and a hash manifest."""
    execute(lambda: {"export_directory": export_snapshot(service(ctx), at_sequence)})


@app.command("audit")
def audit(ctx: typer.Context) -> None:
    """Verify the event hash chain, SQLite integrity and archived document bytes."""

    def action() -> dict[str, Any]:
        import hashlib

        current = service(ctx)
        current.check_ready()
        result = current.db.verify_chain()
        with current.db.connect() as connection:
            documents = connection.execute("SELECT * FROM documents").fetchall()
        for document in documents:
            path = current.config.root / document["local_path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != document["sha256"]:
                raise ValueError(f"Archived document changed: {document['id']}")
        result["documents_checked"] = len(documents)
        return result

    execute(action)


@app.command("schema")
def schema(ctx: typer.Context, output: Path = Path("schemas/draft.schema.json")) -> None:
    """Export the Pydantic JSON schema; protocol-specific rules are validated on submission."""

    def action() -> dict[str, str]:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(Draft.model_json_schema(), indent=2), encoding="utf-8")
        return {"schema": str(output)}

    execute(action)


@app.command("search-corpus")
def search_corpus(ctx: typer.Context, query: str, limit: int = 10) -> None:
    """Retrieve literal source fragments from human-included publications."""
    execute(lambda: service(ctx).search_corpus(query, limit))


@app.command("convert")
def convert(ctx: typer.Context, report_id: str, pdf: Path) -> None:
    """Convert a PDF through the optional Docling adapter, preserving source anchors."""
    from .integrations import convert_document

    execute(lambda: convert_document(service(ctx), report_id, pdf))


@app.command("index-corpus")
def index_corpus(ctx: typer.Context) -> None:
    """Build the optional local Chroma index from included publications."""
    from .integrations import index_corpus as build_index

    execute(lambda: build_index(service(ctx)))


@app.command("retrieve")
def retrieve(ctx: typer.Context, query: str, limit: int = 5) -> None:
    """Retrieve semantic evidence using the optional Chroma adapter."""
    from .integrations import retrieve as semantic_retrieve

    execute(lambda: semantic_retrieve(service(ctx), query, limit))
