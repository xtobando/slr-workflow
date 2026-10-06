"""The argparse interface preserves command contracts and human-only transitions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cli_runner import CliRunner

from slr_workbench.cli import app, build_parser
from slr_workbench.service import ReviewService


@pytest.mark.parametrize(
    "args",
    [
        ["approve-protocol", "--reviewer", "thomas"],
        ["review", "synthetic-proposal", "--reviewer", "thomas"],
        ["retrieval", "synthetic-report", "sought", "--reviewer", "thomas", "--reason", "fixture"],
        ["link-study", "synthetic-report", "study", "--reviewer", "thomas", "--label", "fixture"],
        [
            "unlink-study",
            "synthetic-report",
            "study",
            "--reviewer",
            "thomas",
            "--reason",
            "fixture",
        ],
    ],
)
def test_all_human_commands_reject_piped_confirmation(
    review: ReviewService, args: list[str]
) -> None:
    before = review.db.verify_chain()
    result = CliRunner().invoke(app, ["--project", str(review.config.root), *args], input="yes\n")
    assert result.exit_code == 1
    assert "interactive terminal" in result.output
    assert review.db.verify_chain() == before


def test_argparse_preserves_options_defaults_and_errors() -> None:
    parser = build_parser()
    assert parser.parse_args(["attach", "report", "file.md"]).kind == "markdown"
    assert parser.parse_args(["search-corpus", "phrase"]).limit == 10
    assert parser.parse_args(["retrieve", "phrase"]).limit == 5
    assert parser.parse_args(["review", "proposal", "--reviewer", "id"]).adjudicate is False
    args = [
        "import-records",
        "file.json",
        "--run-id",
        "run",
        "--source",
        "source",
        "--query",
        "query",
        "--searched-at",
        "2026-10-05T00:00:00+00:00",
    ]
    assert parser.parse_args([*args, "--truncated"]).truncated is True
    assert parser.parse_args([*args, "--no-truncated"]).truncated is False
    result = CliRunner().invoke(app, ["review", "proposal"])
    assert result.exit_code == 2
    assert "--reviewer" in result.output
    result = CliRunner().invoke(app, ["status", "--at-sequence", "invalid"])
    assert result.exit_code == 2


def test_module_entry_point_reads_existing_database(review: ReviewService, tmp_path: Path) -> None:
    command = [sys.executable, "-m", "slr_workbench", "--project", str(review.config.root)]
    result = subprocess.run([*command, "records"], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == review.records()
    schema = tmp_path / "schema.json"
    subprocess.run([*command, "schema", "--output", str(schema)], check=True, capture_output=True)
    assert json.loads(schema.read_text())["title"] == "Draft"


def test_core_runs_without_removed_or_ctypes_imports(review: ReviewService) -> None:
    script = """
import importlib.abc
import json
import sys
class BlockRemoved(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pydantic', 'pydantic_core', 'typer', 'click', 'ctypes'}:
            raise AssertionError('Forbidden core import: ' + fullname)
sys.meta_path.insert(0, BlockRemoved())
import rich.console
# Exercise console construction and rendering without native Windows probes.
rich.console.WINDOWS = True
from slr_workbench.cli import app, console
console.print('Rendering check')
app(['--project', sys.argv[1], 'status'])
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(review.config.root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "records_identified" in result.stdout
