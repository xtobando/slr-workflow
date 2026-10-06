"""Preserve nested validation and serialization without the compiled model runtime."""

from __future__ import annotations

import json
from dataclasses import is_dataclass
from datetime import date
from pathlib import Path

import pytest
import yaml

from slr_workbench.models import (
    Draft,
    Evidence,
    ExtractedValue,
    Protocol,
    Provenance,
    RecordInput,
    Reviewers,
    Workflow,
)

ROOT = Path(__file__).resolve().parents[1]


def payload() -> dict:
    return {
        "protocol_revision": "synthetic-revision",
        "entity_type": "report",
        "entity_id": "synthetic-report",
        "stage": "extraction",
        "suggestion": "approved",
        "rationale": "Synthetic serialization fixture; not a scientific decision",
        "values": {
            "methodology": {
                "status": "observed",
                "value": ["synthetic", 2, False],
                "evidence": [{"source": "document", "quote": "synthetic", "page": 2}],
            }
        },
    }


def test_legacy_json_round_trip_and_nested_types() -> None:
    draft = Draft.model_validate_json(json.dumps(payload()))
    assert is_dataclass(draft)
    assert isinstance(draft.provenance, Provenance)
    assert isinstance(draft.values["methodology"], ExtractedValue)
    assert isinstance(draft.values["methodology"].evidence[0], Evidence)
    assert draft.values["methodology"].value == ["synthetic", 2, False]
    assert Draft.model_validate_json(draft.model_dump_json()).model_dump() == draft.model_dump()
    assert json.loads(draft.model_dump_json(indent=2)) == draft.model_dump(mode="json")
    assert draft.provenance.provider is None


def test_schema_matches_pre_migration_contract() -> None:
    # This checked-in schema predates the dataclass migration and must not drift.
    expected = json.loads((ROOT / "schemas/draft.schema.json").read_text())
    assert Draft.model_json_schema() == expected


@pytest.mark.parametrize("level", ["draft", "provenance", "value", "evidence"])
def test_unknown_fields_rejected_at_every_nested_level(level: str) -> None:
    value = payload()
    targets = {
        "draft": value,
        "provenance": value.setdefault("provenance", {}),
        "value": value["values"]["methodology"],
        "evidence": value["values"]["methodology"]["evidence"][0],
    }
    targets[level]["misspelled_field"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        Draft.model_validate(value)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("entity_type", "paper"),
        ("stage", 10),
        ("rationale", ""),
        ("rationale", None),
        ("criteria", "IC1"),
        ("criteria", [1]),
        ("evidence", {}),
        ("values", []),
        ("provenance", None),
    ],
)
def test_invalid_draft_shapes(field: str, bad: object) -> None:
    value = payload()
    value[field] = bad
    with pytest.raises(ValueError):
        Draft.model_validate_json(json.dumps(value))


@pytest.mark.parametrize(
    "field", ["protocol_revision", "entity_type", "entity_id", "stage", "suggestion", "rationale"]
)
def test_missing_required_fields(field: str) -> None:
    value = payload()
    del value[field]
    with pytest.raises(ValueError, match="missing required"):
        Draft.model_validate(value)


@pytest.mark.parametrize("page", [0, -1, 1.5, "bad", "2.", "٢", "2e3", "2__0"])
def test_invalid_page_numbers(page: object) -> None:
    with pytest.raises(ValueError):
        Evidence(source="document", quote="synthetic", page=page)


def test_scalar_conversions_and_python_yaml_loader() -> None:
    assert Evidence(source="document", quote="synthetic", page="2").page == 2
    assert RecordInput(source_record_id="test", title="Synthetic", year="2020").year == 2020
    reviewers = Reviewers(
        identities=["reviewer"], independent="yes", disagreement_procedure="Discuss"
    )
    assert reviewers.independent is True
    assert yaml.SafeLoader.__module__ == "yaml.loader"
    protocol = Protocol.model_validate(yaml.safe_load((ROOT / "protocol.yaml").read_text()))
    assert isinstance(protocol.search_start, date)
    assert isinstance(protocol.model_dump()["search_start"], date)
    assert isinstance(protocol.model_dump(mode="json")["search_start"], str)
    assert Protocol.model_validate_json(protocol.model_dump_json()) == protocol
    workflow = Workflow.model_validate(yaml.safe_load((ROOT / "workflow.yaml").read_text()))
    assert Workflow.model_validate_json(workflow.model_dump_json()) == workflow


@pytest.mark.parametrize(
    "value",
    [
        {"status": "observed", "value": 1, "evidence": []},
        {"status": "observed", "value": None, "evidence": [{"source": "title", "quote": "x"}]},
        {"status": "not_reported", "value": 1},
        {"status": "invented"},
    ],
)
def test_missingness_rules(value: dict) -> None:
    with pytest.raises(ValueError):
        ExtractedValue.model_validate(value)


def test_defaults_and_deep_copy_do_not_share_mutable_values() -> None:
    first = Draft.model_validate(payload())
    second = Draft.model_validate(payload())
    first.criteria.append("synthetic-criterion")
    assert second.criteria == []
    clone = first.model_copy(deep=True, update={"suggestion": "unclear"})
    clone.values["methodology"].evidence[0].quote = "changed"
    assert first.values["methodology"].evidence[0].quote == "synthetic"
    assert first.suggestion == "approved"
