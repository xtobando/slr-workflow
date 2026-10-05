"""Typed, extensible contracts for protocols, workflows and evidence-backed drafts."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EntityType = Literal["review", "record", "report", "study"]


class StrictModel(BaseModel):
    """Reject misspelled fields; use explicit extensions for user-defined metadata."""

    model_config = ConfigDict(extra="forbid")


class Question(StrictModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Criterion(StrictModel):
    id: str
    kind: Literal["inclusion", "exclusion"]
    description: str
    stages: list[str]


class Source(StrictModel):
    id: str
    name: str
    category: Literal["database", "register", "other"] = "database"
    planned_queries: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)


class Reviewers(StrictModel):
    identities: list[str] = Field(min_length=1)
    minimum_per_decision: int = Field(default=1, ge=1)
    independent: bool = False
    disagreement_procedure: str


class ExtractionField(StrictModel):
    id: str
    description: str
    type: Literal["text", "number", "integer", "boolean", "list"] = "text"
    required: bool = True
    choices: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)


class QualityItem(StrictModel):
    id: str
    question: str
    answers: list[str] = Field(min_length=1)


class Paths(StrictModel):
    database: str = "data/slr.sqlite"
    artifacts: str = "data/artifacts"
    exports: str = "data/exports"


class Protocol(StrictModel):
    schema_version: Literal[1] = 1
    review_id: str
    title: str
    rationale: str
    questions: list[Question] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    eligibility: list[Criterion]
    reviewers: Reviewers
    quality: list[QualityItem]
    extraction: list[ExtractionField]
    synthesis: dict[str, Any]
    search_start: date | None = None
    search_end: date | None = None
    paths: Paths = Field(default_factory=Paths)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identifiers(self) -> Protocol:
        for group in (
            self.questions,
            self.sources,
            self.eligibility,
            self.quality,
            self.extraction,
        ):
            ids = [item.id for item in group]
            if len(ids) != len(set(ids)):
                raise ValueError("Identifiers must be unique within each protocol section")
        identities = self.reviewers.identities
        if len(identities) != len(set(identities)):
            raise ValueError("Reviewer identities must be unique")
        if self.reviewers.minimum_per_decision > len(identities):
            raise ValueError("Minimum reviewer count exceeds configured identities")
        rq_ids = {q.id for q in self.questions}
        if any(set(f.research_questions) - rq_ids for f in self.extraction):
            raise ValueError("An extraction field references an unknown research question")
        if self.search_start and self.search_end and self.search_start > self.search_end:
            raise ValueError("Search start must not be later than search end")
        return self


class Stage(StrictModel):
    id: str
    name: str
    skill: str
    entity: EntityType
    enabled: bool = True
    choices: list[str] = Field(min_length=1)
    requires: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)


class Roles(StrictModel):
    record_screening: str
    report_screening: str
    quality: str
    extraction: str


class Workflow(StrictModel):
    schema_version: Literal[1] = 1
    stages: list[Stage]
    roles: Roles
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> Workflow:
        stages = {s.id: s for s in self.stages}
        if len(stages) != len(self.stages):
            raise ValueError("Workflow stage identifiers must be unique")
        for role in self.roles.model_dump().values():
            if role not in stages:
                raise ValueError(f"Unknown workflow role stage: {role}")
        expected = {self.roles.record_screening: "record", self.roles.report_screening: "report"}
        expected.update({self.roles.quality: "report", self.roles.extraction: "report"})
        for stage_id, entity in expected.items():
            if stages[stage_id].entity != entity:
                raise ValueError(f"Stage {stage_id} must operate on {entity} entities")
        for stage in self.stages:
            if len(stage.choices) != len(set(stage.choices)):
                raise ValueError(f"Duplicate choices for {stage.id}")
            if set(stage.requires) - stages.keys():
                raise ValueError(f"Unknown prerequisite for {stage.id}")

        def visit(node: str, trail: set[str]) -> None:
            if node in trail:
                raise ValueError("Workflow prerequisites contain a cycle")
            for dependency in stages[node].requires:
                visit(dependency, trail | {node})

        for node in stages:
            visit(node, set())
        for stage_id in (self.roles.record_screening, self.roles.report_screening):
            if not {"include", "exclude", "unclear"}.issubset(stages[stage_id].choices):
                raise ValueError("Screening roles must support include, exclude and unclear")
        return self


class RecordInput(StrictModel):
    source_record_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    abstract: str = ""
    doi: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(StrictModel):
    source: Literal["title", "abstract", "document"]
    quote: str = Field(min_length=1)
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    element_id: str | None = None


class ExtractedValue(StrictModel):
    status: Literal["observed", "not_reported", "not_applicable", "unclear"]
    value: Any = None
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_missingness(self) -> ExtractedValue:
        if self.status == "observed" and (self.value is None or not self.evidence):
            raise ValueError("Observed values require a value and supporting evidence")
        if self.status != "observed" and self.value is not None:
            raise ValueError("Missing or uncertain values must use null")
        return self


class Provenance(StrictModel):
    wrapper: str = "opencode"
    provider: str | None = None
    model: str | None = None
    session_id: str | None = None
    prompt_sha256: str | None = None
    notes: str = ""


class Draft(StrictModel):
    protocol_revision: str
    entity_type: EntityType
    entity_id: str
    stage: str
    suggestion: str
    rationale: str = Field(min_length=1)
    criteria: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    values: dict[str, ExtractedValue] = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
