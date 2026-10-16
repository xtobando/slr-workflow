"""Characterize integrity, snapshot preservation and read-only operational tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_runner import CliRunner

from slr_workbench.audit import audit_review
from slr_workbench.cli import app, build_parser
from slr_workbench.coverage import search_coverage
from slr_workbench.reporting import export_snapshot, snapshot
from slr_workbench.search.service import search


def test_exports_never_overwrite_an_earlier_snapshot(review):
    first = export_snapshot(review)
    original = {path.name: path.read_bytes() for path in first.iterdir()}
    second = export_snapshot(review)
    assert first != second
    assert {path.name: path.read_bytes() for path in first.iterdir()} == original
    assert json.loads((first / "prisma_counts.json").read_text()) == json.loads(
        (second / "prisma_counts.json").read_text()
    )


def test_audit_checks_import_bytes_as_well_as_chain(review):
    assert audit_review(review)["search_imports_checked"] == 1
    # Simulate file-owner tampering solely in a disposable synthetic fixture.
    with review.db.connect() as connection:
        connection.execute("DROP TRIGGER immutable_search_runs_update")
        connection.execute("UPDATE search_runs SET raw_import='[]' WHERE id='demo-run'")
        connection.commit()
    assert review.db.verify_chain()["sqlite_integrity"] == "ok"
    with pytest.raises(ValueError, match="Archived search import changed"):
        audit_review(review)


def test_manual_search_inventory_does_not_sum_overlapping_totals(review):
    before = review.db.verify_chain()
    result = search_coverage(review)
    assert len(result["runs"]) == 1
    assert result["runs"][0]["imported_records"] == 3
    assert result["runs"][0]["provider_total_or_estimate"] is None
    assert result["coverage_complete"] is None
    assert result["runs"][0]["request_state"] == "reported_complete"
    assert review.db.verify_chain() == before


def test_archive_caps_and_seed_matching_use_checked_evidence(review, tmp_path):
    result = search(
        review.config.root,
        "crossref",
        "synthetic fixture",
        1,
        "pilot-fixture",
        fetch=lambda *a: {
            "message": {
                "items": [{"DOI": "10.99999/slr-demo-001", "title": ["Synthetic fixture"]}],
                "total-results": 1000,
                "next-cursor": "fixture-next",
            }
        },
    )
    seed_path = tmp_path / "seeds.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-seed",
                    "doi": "10.99999/slr-demo-001",
                    "verified": True,
                    "verification_note": "Synthetic fixture only, never cite as a publication",
                }
            ]
        )
    )
    coverage = search_coverage(review, seed_path)
    row = next(run for run in coverage["runs"] if run["run_id"] == "pilot-fixture")
    assert row["request_state"] == "truncated" and row["provider_total_or_estimate"] == 1000
    assert row["archive_integrity"] == "verified_completed_bundle"
    assert coverage["seed_sensitivity"]["fraction_found"] == 1
    records_path = Path(result["manifest"]).parent / result.get("records_file", "records.json")
    records_path.write_text("[]")
    corrupted = search_coverage(review)
    assert corrupted["archive_issues"][0]["run_id"] == "pilot-fixture"
    assert not any(run["run_id"] == "pilot-fixture" for run in corrupted["runs"])


def test_seed_sensitivity_requires_declared_verification(review, tmp_path):
    seeds = tmp_path / "seeds.json"
    seeds.write_text(json.dumps([{"id": "unverified", "doi": "10.99999/slr-demo-001"}]))
    with pytest.raises(ValueError, match="verified"):
        search_coverage(review, seeds)


def test_new_read_only_cli_tools_leave_events_and_counts_unchanged(review):
    before = review.db.verify_chain(), snapshot(review)["counts"]
    for command in (
        "search-coverage",
        "pending-review",
        "pilot-evaluation",
        "duplicate-candidates",
        "audit",
    ):
        result = CliRunner().invoke(app, ["--project", str(review.config.root), command])
        assert result.exit_code == 0, result.output
    assert (review.db.verify_chain(), snapshot(review)["counts"]) == before


def test_unblind_requires_human_terminal(review):
    result = CliRunner().invoke(
        app, ["--project", str(review.config.root), "pending-review", "--unblind"], input="yes\n"
    )
    assert result.exit_code == 1 and "interactive terminal" in result.output


def test_search_plan_cli_has_no_network_or_artifacts(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--project",
            str(tmp_path),
            "search-literature",
            "arxiv",
            "--query",
            "all:testing",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "data").exists()
    parser = build_parser()
    assert parser.parse_args(["pending-review"]).limit == 25
    assert parser.parse_args(["pilot-evaluation"]).limit is None
