"""Scientific-state invariants: provenance, human gates, missingness and count units."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from slr_workbench.cli import app
from slr_workbench.config import load_configuration
from slr_workbench.models import Draft, Evidence, ExtractedValue
from slr_workbench.reporting import export_snapshot, snapshot
from slr_workbench.service import ReviewService

ROOT = Path(__file__).resolve().parents[1]


def draft_for(
    service: ReviewService,
    entity_type: str,
    entity_id: str,
    stage: str,
    suggestion: str,
    quote: str,
    document_id: str | None = None,
    criteria: list[str] | None = None,
    values: dict[str, ExtractedValue] | None = None,
) -> Draft:
    return Draft(
        protocol_revision=service.config.revision,
        entity_type=entity_type,
        entity_id=entity_id,
        stage=stage,
        suggestion=suggestion,
        rationale="Synthetic test judgment supported by the supplied fixture",
        criteria=criteria or [],
        values=values or {},
        evidence=[
            Evidence(
                source="document" if document_id else "abstract",
                document_id=document_id,
                quote=quote,
            )
        ],
    )


def submit(service: ReviewService, draft: Draft) -> str:
    path = service.config.root / "draft.json"
    path.write_text(draft.model_dump_json(), encoding="utf-8")
    return service.submit(path)


def include_record(service: ReviewService) -> dict:
    record = service.records()[0]
    draft = draft_for(
        service,
        "record",
        record["id"],
        "title_abstract",
        "include",
        "evaluates an LLM for software test generation",
        criteria=["IC1"],
    )
    service.decide(submit(service, draft), "thomas")
    return record


def include_report(service: ReviewService) -> tuple[dict, str]:
    record = include_record(service)
    document_id = service.attach(record["report_id"], ROOT / "examples/full-text.md")
    draft = draft_for(
        service,
        "report",
        record["report_id"],
        "full_text",
        "include",
        "We evaluate an LLM for software test generation",
        document_id,
        ["IC1", "IC2"],
    )
    service.decide(submit(service, draft), "thomas")
    return record, document_id


def quality_and_extraction(service: ReviewService, record: dict, document_id: str) -> None:
    methods = Evidence(
        source="document",
        document_id=document_id,
        page=1,
        quote="The experimental procedure compares generated tests with a fixed baseline.",
    )
    limitations = Evidence(
        source="document",
        document_id=document_id,
        page=2,
        quote="The evaluation uses one synthetic dataset and may not generalize to real projects.",
    )
    quality = draft_for(
        service,
        "report",
        record["report_id"],
        "quality",
        "approved",
        methods.quote,
        document_id,
        values={
            "Q1": ExtractedValue(status="observed", value="yes", evidence=[methods]),
            "Q2": ExtractedValue(status="observed", value="yes", evidence=[limitations]),
        },
    )
    service.decide(submit(service, quality), "thomas")
    extraction = draft_for(
        service,
        "report",
        record["report_id"],
        "extraction",
        "approved",
        methods.quote,
        document_id,
        values={
            "methodology": ExtractedValue(
                status="observed", value="Synthetic baseline comparison", evidence=[methods]
            ),
            "algorithms": ExtractedValue(status="not_reported"),
            "metrics": ExtractedValue(
                status="observed",
                value="Statement coverage; numerical estimate not supplied",
                evidence=[
                    Evidence(
                        source="document",
                        document_id=document_id,
                        page=2,
                        quote="The reported metric is statement coverage on the synthetic dataset.",
                    )
                ],
            ),
            "limitations": ExtractedValue(
                status="observed", value="One synthetic dataset", evidence=[limitations]
            ),
        },
    )
    service.decide(submit(service, extraction), "thomas")


def test_import_retry_is_idempotent_and_conflicting_metadata_is_rejected(
    review: ReviewService,
) -> None:
    receipt = review.import_records(
        ROOT / "examples/records.json",
        "demo-run",
        "demo-database",
        "synthetic fixture",
        "2026-10-05T00:00:00+00:00",
    )
    assert receipt["imported"] == 0
    assert len(review.records()) == 3
    with pytest.raises(ValueError, match="different content"):
        review.import_records(
            ROOT / "examples/records.json",
            "demo-run",
            "demo-database",
            "changed query",
            "2026-10-05T00:00:00+00:00",
        )


def test_doi_duplicates_preserve_raw_records_and_are_not_screened(review: ReviewService) -> None:
    assert review.deduplicate()["duplicates_marked"] == 0
    counts = snapshot(review)["counts"]
    assert (
        counts["records_identified"],
        counts["duplicate_records_removed"],
        counts["records_pending"],
    ) == (3, 1, 2)
    duplicate = review.records()[1]
    draft = draft_for(
        review, "record", duplicate["id"], "title_abstract", "include", "evaluates an LLM"
    )
    with pytest.raises(ValueError, match="Duplicate records"):
        submit(review, draft)


def test_agent_proposal_does_not_change_counts(review: ReviewService) -> None:
    record = review.records()[0]
    draft = draft_for(
        review, "record", record["id"], "title_abstract", "include", "evaluates an LLM"
    )
    submit(review, draft)
    counts = snapshot(review)["counts"]
    assert counts["records_screened"] == 0
    assert counts["records_marked_ineligible_by_automation"] == 0


def test_hallucinated_quote_and_wrong_page_are_rejected(review: ReviewService) -> None:
    record = include_record(review)
    bad = draft_for(
        review,
        "record",
        record["id"],
        "title_abstract",
        "include",
        "invented performance is 99 percent",
    )
    with pytest.raises(ValueError, match="quote was not found"):
        submit(review, bad)
    document_id = review.attach(record["report_id"], ROOT / "examples/full-text.md")
    full = draft_for(
        review,
        "report",
        record["report_id"],
        "full_text",
        "include",
        "We evaluate an LLM for software test generation",
        document_id,
    )
    full.evidence[0].page = 2
    with pytest.raises(ValueError, match="quote was not found"):
        submit(review, full)


def test_exclusion_criterion_must_exist_and_apply(review: ReviewService) -> None:
    record = review.records()[2]
    draft = draft_for(
        review,
        "record",
        record["id"],
        "title_abstract",
        "exclude",
        "contains no software testing evaluation",
        criteria=["EC2"],
    )
    with pytest.raises(ValueError, match="not applicable"):
        submit(review, draft)
    draft.criteria = ["EC1"]
    review.decide(submit(review, draft), "thomas")
    assert snapshot(review)["counts"]["records_excluded"] == 1


def test_decision_revision_is_append_only_and_uses_latest(review: ReviewService) -> None:
    record = include_record(review)
    unclear = draft_for(
        review, "record", record["id"], "title_abstract", "unclear", "evaluates an LLM"
    )
    review.decide(submit(review, unclear), "thomas")
    counts = snapshot(review)["counts"]
    assert counts["records_screened"] == 1
    assert counts["records_unclear"] == 1
    assert counts["reports_included"] == 0
    with review.db.connect() as connection:
        rows = connection.execute("SELECT * FROM decisions ORDER BY rowid").fetchall()
        assert rows[1]["supersedes"] == rows[0]["id"]
        with pytest.raises(sqlite3.IntegrityError, match="Append-only"):
            connection.execute("UPDATE decisions SET choice='exclude'")
        with pytest.raises(sqlite3.IntegrityError, match="Append-only"):
            connection.execute("DELETE FROM records")
    assert review.db.verify_chain()["events_checked"] > 0


def test_unretrieved_report_is_not_eligibility_exclusion(review: ReviewService) -> None:
    record = include_record(review)
    review.retrieval_status(
        record["report_id"], "not_retrieved", "Synthetic access failure", "thomas"
    )
    counts = snapshot(review)["counts"]
    assert counts["reports_sought_for_retrieval"] == 1
    assert counts["reports_not_retrieved"] == 1
    assert counts["reports_excluded"] == 0


def test_full_text_prerequisites_and_bibliographic_evidence_are_checked(
    review: ReviewService,
) -> None:
    record = review.records()[0]
    draft = draft_for(
        review, "report", record["report_id"], "full_text", "include", "evaluates an LLM"
    )
    with pytest.raises(ValueError, match="Unfulfilled prerequisite"):
        submit(review, draft)
    record = include_record(review)
    review.attach(record["report_id"], ROOT / "examples/full-text.md")
    with pytest.raises(ValueError, match="document evidence"):
        submit(review, draft)


def test_export_only_uses_approved_extraction_and_counts_linked_studies(
    review: ReviewService,
) -> None:
    record, document_id = include_report(review)
    quality_and_extraction(review, record, document_id)
    review.link_study(record["report_id"], "study-demo", "Synthetic study", "thomas")
    result = snapshot(review)
    assert result["counts"]["reports_included"] == 1
    assert result["counts"]["studies_included"] == 1
    assert result["summary"][0]["algorithms"] == "not_reported"
    directory = export_snapshot(review)
    assert {
        "summary.csv",
        "screening.csv",
        "prisma_counts.json",
        "summary.tex",
        "manifest.json",
    } <= {p.name for p in directory.iterdir()}
    assert review.search_corpus("synthetic dataset")[0]["document_id"] == document_id


def test_snapshot_cutoff_excludes_later_searches_and_decisions(review: ReviewService) -> None:
    assert snapshot(review, 1)["counts"]["records_identified"] == 0
    before = snapshot(review)["event_sequence"]
    include_record(review)
    assert snapshot(review, before)["counts"]["records_screened"] == 0
    assert snapshot(review)["counts"]["records_screened"] == 1


def test_protocol_change_rejects_stale_drafts_and_does_not_reuse_decisions(
    review: ReviewService,
) -> None:
    record = include_record(review)
    old = draft_for(review, "record", record["id"], "title_abstract", "include", "evaluates an LLM")
    path = review.config.root / "protocol.yaml"
    path.write_text(path.read_text() + "\n# Documented protocol amendment\n")
    changed = ReviewService(load_configuration(review.config.root))
    changed.initialize()
    changed.approve_protocol("thomas", "Re-evaluate decisions under the amended fixture")
    with pytest.raises(ValueError, match="old or unknown"):
        submit(changed, old)
    assert snapshot(changed)["counts"]["records_screened"] == 0


def test_two_reviewers_require_consensus_and_disagreements_remain_pending(
    review: ReviewService,
) -> None:
    path = review.config.root / "protocol.yaml"
    protocol = yaml.safe_load(path.read_text())
    protocol["reviewers"]["identities"] = ["thomas", "reviewer-two"]
    protocol["reviewers"]["minimum_per_decision"] = 2
    path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    updated = ReviewService(load_configuration(review.config.root))
    updated.initialize()
    updated.approve_protocol("thomas", "Two-reviewer synthetic fixture")
    record = updated.records()[0]
    included = draft_for(
        updated, "record", record["id"], "title_abstract", "include", "evaluates an LLM"
    )
    proposal = submit(updated, included)
    updated.decide(proposal, "thomas")
    assert snapshot(updated)["counts"]["records_screened"] == 0
    with pytest.raises(ValueError, match="existing judgments"):
        updated.decide(proposal, "thomas", adjudication=True)
    uncertain = included.model_copy(update={"suggestion": "unclear"})
    updated.decide(proposal, "reviewer-two", uncertain)
    assert snapshot(updated)["counts"]["records_screened"] == 0
    updated.decide(proposal, "thomas", included, adjudication=True)
    assert snapshot(updated)["counts"]["records_screened"] == 1


def test_human_cli_refuses_piped_approval(review: ReviewService) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--project", str(review.config.root), "approve-protocol", "--reviewer", "thomas"],
        input="yes\n",
    )
    assert result.exit_code == 1
    assert "interactive terminal" in result.output


def test_cli_submit_and_interactive_review_contract(
    review: ReviewService, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = review.records()[0]
    draft = draft_for(
        review, "record", record["id"], "title_abstract", "include", "evaluates an LLM"
    )
    path = review.config.root / "draft-cli.json"
    path.write_text(draft.model_dump_json())
    runner = CliRunner()
    prefix = ["--project", str(review.config.root)]
    result = runner.invoke(app, prefix + ["submit", str(path)])
    assert result.exit_code == 0, result.output
    proposal_id = json.loads(result.output)["proposal_id"]
    # Simulate an interactive human terminal only within this isolated test.
    monkeypatch.setattr("slr_workbench.cli.require_terminal", lambda: None)
    result = runner.invoke(
        app, prefix + ["review", proposal_id, "--reviewer", "thomas"], input="accept\ny\n"
    )
    assert result.exit_code == 0, str(result.exception) + result.output
    assert "human_decision_recorded" in result.output
    assert snapshot(review)["counts"]["records_screened"] == 1


def test_workflow_cycles_and_missing_reviewer_ids_fail_fast(review: ReviewService) -> None:
    path = review.config.root / "workflow.yaml"
    workflow = yaml.safe_load(path.read_text())
    workflow["stages"][0]["requires"] = ["title_abstract"]
    path.write_text(yaml.safe_dump(workflow, sort_keys=False))
    with pytest.raises(ValueError, match="cycle"):
        load_configuration(review.config.root)
    with pytest.raises(ValueError, match="not listed"):
        review.approve_protocol("imaginary-reviewer", "Not valid")
