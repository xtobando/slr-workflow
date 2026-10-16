"""Synthetic-only human review-package projections and independent-assessment guards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from test_review import draft_for, include_record, submit

from slr_workbench.config import load_configuration
from slr_workbench.review_support import evaluate_pilot, export_review_package, inspect_queue
from slr_workbench.service import ReviewService


def _proposal(review: ReviewService, suggestion: str = "unclear") -> str:
    record = review.records()[0]
    draft = draft_for(
        review,
        "record",
        record["id"],
        review.config.workflow.roles.record_screening,
        suggestion,
        "evaluates an LLM",
    )
    draft.rationale = "DISTINCTIVE PRIVATE RECOMMENDATION"
    return submit(review, draft)


def _amend(
    review: ReviewService, *, independent: bool = False, renamed: bool = False
) -> ReviewService:
    path = review.config.root / "protocol.yaml"
    protocol = yaml.safe_load(path.read_text())
    protocol["reviewers"]["identities"] = ["thomas", "second"]
    protocol["reviewers"]["minimum_per_decision"] = 2
    protocol["reviewers"]["independent"] = independent
    if renamed:
        for criterion in protocol["eligibility"]:
            criterion["stages"] = [
                "screen-records" if stage == "title_abstract" else stage
                for stage in criterion["stages"]
            ]
        workflow_path = review.config.root / "workflow.yaml"
        workflow = yaml.safe_load(workflow_path.read_text())
        workflow["roles"]["record_screening"] = "screen-records"
        for stage in workflow["stages"]:
            if stage["id"] == "title_abstract":
                stage["id"] = "screen-records"
            stage["requires"] = [
                "screen-records" if requirement == "title_abstract" else requirement
                for requirement in stage.get("requires", [])
            ]
        workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))
    path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    updated = ReviewService(load_configuration(review.config.root))
    updated.initialize()
    updated.approve_protocol("thomas", "Isolated synthetic two-reviewer fixture")
    return updated


def test_absent_database_is_reported_without_creating_it(review: ReviewService) -> None:
    database = review.config.database
    database.unlink()
    result = inspect_queue(review)
    assert not database.exists()
    assert not result["initialized"]
    assert result["current"] == []
    assert "absent" in result["blockers"][0]


def test_read_only_sheet_exposes_unclear_questions_and_hashes(review: ReviewService) -> None:
    proposal = _proposal(review)
    before = review.db.verify_chain()
    counts_before = evaluate_pilot(review)
    directory = export_review_package(review, reviewer="thomas", package_id="pilot-one")
    result = json.loads((directory / "review.json").read_text())
    row = result["current"][0]
    assert row["proposal_id"] == proposal
    assert row["status"] == "pending_reviewer"
    assert row["effective_human_decision"] is None
    assert row["uncertainty"][0]["evidence_needed"]
    assert "review" in row["human_review_command"]["windows_powershell"]
    assert "## 1." in (directory / "review.md").read_text()
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    assert review.db.verify_chain() == before
    assert evaluate_pilot(review) == counts_before
    with pytest.raises(FileExistsError):
        export_review_package(review, reviewer="thomas", package_id="pilot-one")
    with pytest.raises(ValueError, match="simple name"):
        export_review_package(review, reviewer="thomas", package_id="../escape")
    with pytest.raises(ValueError, match="not listed"):
        export_review_package(review, reviewer="automatic-approver")


def test_latest_proposals_do_not_overwrite_effective_human_decisions(review: ReviewService) -> None:
    first = _proposal(review, "include")
    decision = review.decide(first, "thomas")
    assert evaluate_pilot(review)["pilot_evaluation"]["matching_recommendations"] == 1
    second = _proposal(review, "unclear")
    result = evaluate_pilot(review, reviewer="thomas")
    row = result["current"][0]
    assert row["proposal_id"] == second
    assert row["older_proposal_ids"] == [first]
    assert row["effective_human_decision"]["id"] == decision
    assert row["status"] == "pending_reviewer"
    assert result["pilot_evaluation"]["same_proposal_compared"] == 0
    revised = review.proposal(second).model_copy(update={"suggestion": "include"})
    review.decide(second, "thomas", revised)
    result = evaluate_pilot(review)
    assert result["pilot_evaluation"]["changed_recommendations"] == 1
    assert result["current"][0]["latest_human_judgments"][0]["supersedes"] == decision


def test_two_reviewer_disagreement_is_pending_and_preserves_labels(review: ReviewService) -> None:
    service = _amend(review)
    proposal = _proposal(service, "include")
    service.decide(proposal, "thomas")
    result = evaluate_pilot(service)
    assert result["current"][0]["status"] == "pending_consensus"
    service.decide(
        proposal, "second", service.proposal(proposal).model_copy(update={"suggestion": "unclear"})
    )
    row = inspect_queue(service)["current"][0]
    assert row["disagreement"]
    assert {item["reviewer"] for item in row["latest_human_judgments"]} == {"thomas", "second"}
    assert row["effective_human_decision"] is None
    assert row["uncertainty"][-1]["question"].startswith("Which documented interpretation")


def test_blind_package_hides_recommendations_and_prior_judgments(review: ReviewService) -> None:
    service = _amend(review, independent=True)
    proposal = _proposal(service, "include")
    service.decide(proposal, "thomas")
    result = evaluate_pilot(service, reviewer="second")
    text = json.dumps(result)
    assert "DISTINCTIVE PRIVATE RECOMMENDATION" not in text
    row = result["current"][0]
    assert "recommendation" not in row
    assert "latest_human_judgments" not in row
    assert "--decision-file" in row["human_review_command"]["macos_linux"]
    assert result["pilot_evaluation"]["same_proposal_compared"] == 0
    directory = export_review_package(service, reviewer="second")
    assert "DISTINCTIVE PRIVATE RECOMMENDATION" not in (directory / "review.md").read_text()
    with pytest.raises(ValueError, match="reveals recommendations"):
        inspect_queue(service, uncertain_only=True)
    unblinded = inspect_queue(service, unblind=True)
    assert unblinded["current"][0]["recommendation"] == "include"


def test_stale_revision_segregation_and_dynamic_stage_names(review: ReviewService) -> None:
    old = _proposal(review)
    service = _amend(review, renamed=True)
    new = _proposal(service)
    result = inspect_queue(service, reviewer="second", include_history=True)
    assert result["roles"]["record_screening"] == "screen-records"
    assert result["current"][0]["proposal_id"] == new
    assert result["historical"][0]["proposal_id"] == old
    assert result["historical"][0]["human_review_command"] is None
    assert inspect_queue(service, stage="screen-records")["current"]
    assert inspect_queue(service, batch=["demo-run"])["current"]
    assert inspect_queue(service, batch=["missing-run"])["current"] == []
    assert inspect_queue(service, evidence_stream="invented-stream")["current"] == []


def test_withdrawn_prerequisite_prevents_review_handoff(review: ReviewService) -> None:
    record = include_record(review)
    document = review.attach(
        record["report_id"], Path(__file__).resolve().parents[1] / "examples/full-text.md"
    )
    full = draft_for(
        review,
        "report",
        record["report_id"],
        "full_text",
        "include",
        "We evaluate an LLM for software test generation",
        document,
    )
    proposal = submit(review, full)
    unclear = draft_for(
        review, "record", record["id"], "title_abstract", "unclear", "evaluates an LLM"
    )
    review.decide(submit(review, unclear), "thomas")
    result = inspect_queue(review, stage="full_text", reviewer="thomas")
    assert result["current"][0]["proposal_id"] == proposal
    assert "Unfulfilled prerequisite" in result["current"][0]["blockers"][0]
    assert result["current"][0]["human_review_command"] is None
    pathway = next(
        row for row in result["full_text_pathways"] if row["report_id"] == record["report_id"]
    )
    assert not pathway["record_screening_included"]


def test_shell_handoffs_quote_a_configured_identity(review: ReviewService) -> None:
    path = review.config.root / "protocol.yaml"
    protocol = yaml.safe_load(path.read_text())
    identity = "reviewer'$(touch NOPE)"
    protocol["reviewers"]["identities"] = [identity]
    path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    service = ReviewService(load_configuration(review.config.root))
    service.initialize()
    service.approve_protocol(identity, "Isolated shell quoting fixture")
    _proposal(service)
    row = inspect_queue(service, reviewer=identity)["current"][0]
    assert "'\"'\"'" in row["human_review_command"]["macos_linux"]
    assert "reviewer''$(touch NOPE)" in row["human_review_command"]["windows_powershell"]
    assert not (review.config.root / "NOPE").exists()


def test_pending_queue_pages_and_resumes_after_individual_decisions(review: ReviewService) -> None:
    first = _proposal(review)
    record = review.records()[2]
    second = submit(
        review,
        draft_for(review, "record", record["id"], "title_abstract", "unclear", "ocean currents"),
    )
    page = inspect_queue(review, reviewer="thomas", limit=1)
    assert page["total_pending"] == page["total_matching"] == 2
    assert page["remaining"] == 1
    assert page["current"][0]["proposal_id"] == first
    page_two = inspect_queue(review, reviewer="thomas", limit=1, offset=1)
    assert page_two["current"][0]["proposal_id"] == second
    review.decide(first, "thomas")
    resumed = inspect_queue(review, reviewer="thomas", limit=1)
    assert resumed["total_pending"] == 1
    assert resumed["current"][0]["proposal_id"] == second
    assert evaluate_pilot(review)["pilot_evaluation"]["same_proposal_compared"] == 1
    with pytest.raises(ValueError, match="nonnegative"):
        inspect_queue(review, offset=-1)


def test_stream_and_batch_filters_use_explicit_metadata_only(review: ReviewService) -> None:
    path = review.config.root / "additional.json"
    path.write_text(
        json.dumps(
            [
                {
                    "source_record_id": "synthetic-stream-case",
                    "title": "SYNTHETIC stream fixture",
                    "abstract": "Synthetic supporting evidence.",
                    "metadata": {"evidence_stream": "explicit-test-stream", "batch_id": "pilot-A"},
                }
            ]
        )
    )
    review.import_records(
        path, "stream-run", "demo-database", "synthetic query", "2026-10-05T00:00:00+00:00"
    )
    record = review.records()[-1]
    proposal = submit(
        review,
        draft_for(
            review,
            "record",
            record["id"],
            "title_abstract",
            "unclear",
            "Synthetic supporting evidence.",
        ),
    )
    result = inspect_queue(review, batch=["pilot-A"], evidence_stream="explicit-test-stream")
    assert result["current"][0]["proposal_id"] == proposal
    assert result["current"][0]["evidence_streams"] == ["explicit-test-stream"]
    assert inspect_queue(review, evidence_stream="prosthesis")["current"] == []
