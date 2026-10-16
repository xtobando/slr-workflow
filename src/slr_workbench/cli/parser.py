"""Argparse command contracts, separated from interactive presentation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Keep the existing CLI names, positional arguments, options and defaults."""
    from . import (
        approve_protocol,
        attach,
        audit,
        convert,
        deduplicate,
        duplicate_candidates,
        import_records,
        import_search_bundle,
        index_corpus,
        initialize,
        link_study,
        packet,
        pending_review,
        pilot_evaluation,
        proposal,
        records,
        report,
        retrieval,
        retrieve,
        review,
        review_sheet,
        schema,
        search_corpus,
        search_coverage,
        status,
        submit,
        unlink_study,
        workflow,
    )

    parser = argparse.ArgumentParser(
        prog="slr", description="Evidence-grounded SLR services for OpenCode.", allow_abbrev=False
    )
    parser.add_argument("--project", type=Path, default=Path("."), help="Project root")
    commands = parser.add_subparsers(dest="command")

    def command(name: str, handler: Callable[..., None]) -> argparse.ArgumentParser:
        sub = commands.add_parser(
            name, help=handler.__doc__, description=handler.__doc__, allow_abbrev=False
        )
        sub.set_defaults(handler=handler)
        return sub

    sub = commands.add_parser("backup", help="Create a verified recovery archive.")
    sub.add_argument("--destination", type=Path)
    sub.set_defaults(handler=None)
    sub = commands.add_parser("backup-verify", help="Verify a recovery archive.")
    sub.add_argument("archive", type=Path)
    sub.set_defaults(handler=None)
    sub = commands.add_parser(
        "restore", help="Restore into a new folder, never overwrite a review."
    )
    sub.add_argument("archive", type=Path)
    sub.add_argument("destination", type=Path)
    sub.set_defaults(handler=None)
    sub = commands.add_parser(
        "read-pdf", help="Read any PDF as Markdown without changing review state."
    )
    sub.add_argument("pdf", type=Path)
    sub.add_argument("--output-dir", type=Path)
    sub.set_defaults(handler=None)
    from ..search.catalog import PROVIDERS

    sub = commands.add_parser(
        "search-providers", help="List scientific databases and access options."
    )
    sub.set_defaults(handler=None)
    sub = commands.add_parser(
        "credentials", help="Manage external API credentials in a human terminal."
    )
    sub.add_argument("provider", choices=PROVIDERS)
    sub.add_argument("action", choices=("status", "set", "delete"))
    sub.add_argument("--field", default="api_key", choices=("api_key", "insttoken"))
    sub.set_defaults(handler=None)
    sub = commands.add_parser(
        "search-literature", help="Search a scientific API and archive results without importing."
    )
    sub.add_argument("provider", choices=PROVIDERS)
    sub.add_argument("--query", required=True)
    sub.add_argument("--max-results", type=int, default=100)
    sub.add_argument("--run-id")
    sub.add_argument(
        "--resume", action="store_true", help="Continue the same verified v2 search run."
    )
    sub.add_argument(
        "--dry-run", action="store_true", help="Plan requests without network access or artifacts."
    )
    sub.add_argument("--max-pages", type=int, default=100)
    sub.add_argument(
        "--max-requests",
        type=int,
        default=100,
        help="Cumulative run budget including retries; increase explicitly on resume.",
    )
    sub.add_argument(
        "--allow-credentials",
        action="store_true",
        help="Explicitly permit configured API credentials and their potential provider charges.",
    )
    sub.set_defaults(handler=None)
    sub = command("import-search", import_search_bundle)
    sub.add_argument("manifest_path", type=Path)
    sub.add_argument("--source", required=True)
    command("init", initialize)
    sub = command("approve-protocol", approve_protocol)
    sub.add_argument("--reviewer", required=True)
    sub = command("import-records", import_records)
    sub.add_argument("path", type=Path)
    for name in ("run-id", "source", "query", "searched-at"):
        sub.add_argument("--" + name, required=True)
    sub.add_argument("--truncated", action=argparse.BooleanOptionalAction, default=False)
    command("records", records)
    command("deduplicate", deduplicate)
    command("workflow", workflow)
    sub = command("packet", packet)
    sub.add_argument("stage")
    sub.add_argument("entity_id")
    sub.add_argument("--output", type=Path)
    sub = command("submit", submit)
    sub.add_argument("draft", type=Path)
    sub = command("proposal", proposal)
    sub.add_argument("proposal_id")
    sub = command("review", review)
    sub.add_argument("proposal_id")
    sub.add_argument("--reviewer", required=True)
    sub.add_argument("--decision-file", type=Path)
    sub.add_argument("--adjudicate", action=argparse.BooleanOptionalAction, default=False)
    sub = command("attach", attach)
    sub.add_argument("report_id")
    sub.add_argument("path", type=Path)
    sub.add_argument("--kind", default="markdown")
    sub = command("retrieval", retrieval)
    sub.add_argument("report_id")
    sub.add_argument("status")
    sub.add_argument("--reviewer", required=True)
    sub.add_argument("--reason", required=True)
    for name, handler, extra in (
        ("link-study", link_study, "label"),
        ("unlink-study", unlink_study, "reason"),
    ):
        sub = command(name, handler)
        sub.add_argument("report_id")
        sub.add_argument("study_id")
        sub.add_argument("--reviewer", required=True)
        sub.add_argument("--" + extra, required=True)
    for name, handler in (("status", status), ("report", report)):
        sub = command(name, handler)
        sub.add_argument("--at-sequence", type=int)
    command("audit", audit)
    sub = command("search-coverage", search_coverage)
    sub.add_argument("--seeds", type=Path)
    sub = command("duplicate-candidates", duplicate_candidates)
    sub.add_argument("--limit", type=int, default=100)
    sub.add_argument("--max-comparisons", type=int, default=50000)
    sub.add_argument("--title-threshold", type=float, default=0.9)
    sub.add_argument("--output", type=Path)
    for name, handler in (
        ("pending-review", pending_review),
        ("review-sheet", review_sheet),
        ("pilot-evaluation", pilot_evaluation),
    ):
        sub = command(name, handler)
        sub.add_argument("--reviewer", required=name == "review-sheet")
        sub.add_argument("--stage")
        sub.add_argument(
            "--batch",
            action="append",
            help="Search run or proposal IDs; repeat to select multiple.",
        )
        sub.add_argument("--evidence-stream")
        sub.add_argument("--uncertain-only", action="store_true")
        sub.add_argument("--include-history", action="store_true")
        sub.add_argument("--limit", type=int, default=None if name == "pilot-evaluation" else 25)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument(
            "--unblind",
            action="store_true",
            help="Human-operated interactive disclosure of recommendations.",
        )
        if name == "review-sheet":
            sub.add_argument("--package-id")
    sub = command("schema", schema)
    sub.add_argument("--output", type=Path, default=Path("schemas/draft.schema.json"))
    for name, handler, limit in (("search-corpus", search_corpus, 10), ("retrieve", retrieve, 5)):
        sub = command(name, handler)
        sub.add_argument("query")
        sub.add_argument("--limit", type=int, default=limit)
    sub = command("convert", convert)
    sub.add_argument("report_id")
    sub.add_argument("pdf", type=Path)
    command("index-corpus", index_corpus)
    return parser
