"""Regression checks for evidence, retrieval transitions and configured list choices."""

from __future__ import annotations

import pytest
import yaml
from test_review import (
    ROOT,
    draft_for,
    include_record,
    include_report,
    quality_and_extraction,
    submit,
)

from slr_workbench.config import load_configuration
from slr_workbench.models import Evidence, ExtractedValue
from slr_workbench.reporting import snapshot
from slr_workbench.service import ReviewService


@pytest.mark.parametrize("quote", [" ", "\n\t", "\u00a0\u2003"])
@pytest.mark.parametrize("source", ["abstract", "markdown", "pdf"])
def test_whitespace_evidence_is_rejected(
    review: ReviewService, quote: str, source: str
) -> None:
    record = include_record(review)
    document_id = None
    entity_type, entity_id, stage = "record", record["id"], "title_abstract"
    if source != "abstract":
        path = ROOT / "examples/full-text.md"
        if source == "pdf":
            path = review.config.root / "synthetic.pdf"
            path.write_bytes(b"%PDF-1.4\n% Synthetic test placeholder, no extracted text\n")
        document_id = review.attach(record["report_id"], path, source)
        entity_type, entity_id, stage = "report", record["report_id"], "full_text"
    draft = draft_for(review, entity_type, entity_id, stage, "include", quote, document_id)
    with pytest.raises(ValueError, match="non-whitespace"):
        submit(review, draft)


@pytest.mark.parametrize("status", ["sought", "not_retrieved"])
def test_unattached_report_can_record_retrieval_attempt(
    review: ReviewService, status: str
) -> None:
    record = include_record(review)
    review.retrieval_status(record["report_id"], status, "Synthetic retrieval attempt", "thomas")
    counts = snapshot(review)["counts"]
    assert counts["reports_sought_for_retrieval"] == 1
    key = "reports_awaiting_retrieval" if status == "sought" else "reports_not_retrieved"
    assert counts[key] == 1
    review.attach(record["report_id"], ROOT / "examples/full-text.md")
    counts = snapshot(review)["counts"]
    assert counts["reports_retrieved"] == 1
    assert counts["reports_not_retrieved"] == 0
    assert counts["reports_awaiting_retrieval"] == 0


@pytest.mark.parametrize("status", ["sought", "not_retrieved"])
def test_attached_report_cannot_regress_to_unretrieved(
    review: ReviewService, status: str
) -> None:
    record, document_id = include_report(review)
    before = snapshot(review)
    with pytest.raises(ValueError, match="attached full text"):
        review.retrieval_status(record["report_id"], status, "Synthetic repeat attempt", "thomas")
    # A rejected transition must leave both counts and the event history unchanged.
    assert snapshot(review) == before
    assert review.attach(record["report_id"], ROOT / "examples/full-text.md") == document_id
    assert review.search_corpus("synthetic dataset")
    assert snapshot(review)["counts"]["reports_included"] == 1


@pytest.mark.parametrize(
    ("value", "valid"),
    [(["A"], True), (["A", "B"], True), (["A", "unknown"], False), ([1], False)],
)
def test_list_extraction_validates_each_allowed_choice(
    review: ReviewService, value: list, valid: bool
) -> None:
    # Register a changed protocol only inside pytest's isolated synthetic project.
    path = review.config.root / "protocol.yaml"
    protocol = yaml.safe_load(path.read_text())
    for field in protocol["extraction"]:
        if field["id"] == "algorithms":
            field["choices"] = ["A", "B"]
    path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    updated = ReviewService(load_configuration(review.config.root))
    updated.initialize()
    updated.approve_protocol("thomas", "Synthetic list-choice regression fixture")
    record, document_id = include_report(updated)
    quality_and_extraction(updated, record, document_id)
    with updated.db.connect() as connection:
        proposal_id = connection.execute(
            "SELECT id FROM proposals WHERE stage='extraction'"
        ).fetchone()[0]
    draft = updated.proposal(proposal_id)
    draft.values["algorithms"] = ExtractedValue(
        status="observed",
        value=value,
        evidence=[Evidence(source="document", document_id=document_id, quote="LLM")],
    )
    if valid:
        assert submit(updated, draft).startswith("proposal_")
    else:
        with pytest.raises(ValueError, match="outside configured choices"):
            submit(updated, draft)
