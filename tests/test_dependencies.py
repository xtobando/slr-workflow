"""Dependency changes must not leave stale scientific results in exports or retrieval."""

from __future__ import annotations

import json

import pytest
import yaml
from test_review import ROOT, draft_for, include_report, quality_and_extraction, submit
from typer.testing import CliRunner

from slr_workbench.cli import app
from slr_workbench.config import load_configuration
from slr_workbench.integrations import included_documents, rag_configuration
from slr_workbench.reporting import snapshot
from slr_workbench.service import ReviewService


def test_upstream_withdrawal_removes_report_from_retrieval_and_counts(
    review: ReviewService,
) -> None:
    record, _ = include_report(review)
    assert review.search_corpus("synthetic dataset")
    changed = draft_for(
        review, "record", record["id"], "title_abstract", "unclear", "evaluates an LLM"
    )
    review.decide(submit(review, changed), "thomas")
    assert snapshot(review)["counts"]["reports_included"] == 0
    assert review.search_corpus("synthetic dataset") == []
    assert included_documents(review) == []


def test_withdrawn_quality_approval_removes_extraction_from_summary(review: ReviewService) -> None:
    record, document_id = include_report(review)
    quality_and_extraction(review, record, document_id)
    with review.db.connect() as connection:
        proposal_id = connection.execute(
            "SELECT id FROM proposals WHERE stage='quality'"
        ).fetchone()[0]
    original = review.proposal(proposal_id)
    review.decide(proposal_id, "thomas", original.model_copy(update={"suggestion": "revise"}))
    result = snapshot(review)
    assert result["counts"]["reports_included"] == 1
    assert result["summary"][0]["extraction_decision_id"] == ""
    assert result["summary"][0]["methodology"] == "pending"


def test_two_publications_can_count_as_one_study_and_links_are_reversible(
    review: ReviewService,
) -> None:
    first, _ = include_report(review)
    extra = json.loads((ROOT / "examples/records.json").read_text())[0]
    extra["doi"] = "10.99999/slr-demo-extension"
    extra["source_record_id"] = "synthetic-study-extension"
    extra["title"] += " — synthetic extended report"
    path = review.config.root / "additional-search.json"
    path.write_text(json.dumps([extra]))
    review.import_records(
        path, "additional-run", "demo-database", "synthetic update", "2026-10-05T01:00:00+00:00"
    )
    second = review.records()[-1]
    screening = draft_for(
        review, "record", second["id"], "title_abstract", "include", "evaluates an LLM"
    )
    review.decide(submit(review, screening), "thomas")
    document_id = review.attach(second["report_id"], ROOT / "examples/full-text.md")
    full_text = draft_for(
        review,
        "report",
        second["report_id"],
        "full_text",
        "include",
        "We evaluate an LLM for software test generation",
        document_id,
    )
    review.decide(submit(review, full_text), "thomas")
    for record in (first, second):
        review.link_study(
            record["report_id"], "shared-investigation", "Synthetic shared study", "thomas"
        )
    counts = snapshot(review)["counts"]
    assert counts["reports_included"] == 2
    assert counts["studies_included"] == 1
    for record in (first, second):
        review.unlink_study(
            record["report_id"], "shared-investigation", "Correct synthetic association", "thomas"
        )
    assert snapshot(review)["counts"]["studies_included"] == 0
    with review.db.connect() as connection:
        assert len(review.events(connection, "study_linked")) == 2
        assert len(review.events(connection, "study_unlinked")) == 2


def test_stage_ids_and_role_links_are_editable(review: ReviewService) -> None:
    root = review.config.root
    workflow = yaml.safe_load((root / "workflow.yaml").read_text())
    workflow["roles"]["record_screening"] = "initial_screen"
    for stage in workflow["stages"]:
        if stage["id"] == "title_abstract":
            stage["id"] = "initial_screen"
        stage["requires"] = [
            "initial_screen" if item == "title_abstract" else item
            for item in stage.get("requires", [])
        ]
    protocol = yaml.safe_load((root / "protocol.yaml").read_text())
    for criterion in protocol["eligibility"]:
        criterion["stages"] = [
            "initial_screen" if item == "title_abstract" else item for item in criterion["stages"]
        ]
    (root / "workflow.yaml").write_text(yaml.safe_dump(workflow, sort_keys=False))
    (root / "protocol.yaml").write_text(yaml.safe_dump(protocol, sort_keys=False))
    changed = ReviewService(load_configuration(root))
    changed.initialize()
    changed.approve_protocol("thomas", "Rename stage in isolated customization fixture")
    record = changed.records()[0]
    draft = draft_for(
        changed,
        "record",
        record["id"],
        "initial_screen",
        "include",
        "evaluates an LLM",
        criteria=["IC1"],
    )
    changed.decide(submit(changed, draft), "thomas")
    assert snapshot(changed)["counts"]["records_screened"] == 1


def test_rag_chunk_configuration_rejects_invalid_overlap(review: ReviewService) -> None:
    path = review.config.root / "rag.yaml"
    config = yaml.safe_load(path.read_text())
    config["overlap_characters"] = config["chunk_characters"]
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="overlap_characters"):
        rag_configuration(review)


def test_audit_detects_changed_archived_document(review: ReviewService) -> None:
    record, _ = include_report(review)
    with review.db.connect() as connection:
        document = connection.execute(
            "SELECT local_path FROM documents WHERE report_id=?", (record["report_id"],)
        ).fetchone()
    (review.config.root / document[0]).write_text("Changed original fixture")
    result = CliRunner().invoke(app, ["--project", str(review.config.root), "audit"])
    assert result.exit_code == 1
    assert "Archived document changed" in result.output
