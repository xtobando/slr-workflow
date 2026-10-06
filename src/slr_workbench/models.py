"""Typed, extensible contracts for protocols, workflows and evidence-backed drafts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from .validation import StrictModel

EntityType = Literal["review", "record", "report", "study"]


@dataclass(kw_only=True)
class Question(StrictModel):
    id: str = field(metadata={"min_length": 1})
    text: str = field(metadata={"min_length": 1})


@dataclass(kw_only=True)
class Criterion(StrictModel):
    id: str
    kind: Literal["inclusion", "exclusion"]
    description: str
    stages: list[str]


@dataclass(kw_only=True)
class Source(StrictModel):
    id: str
    name: str
    category: Literal["database", "register", "other"] = "database"
    planned_queries: list[str] = field(default_factory=list)
    limits: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Reviewers(StrictModel):
    identities: list[str] = field(metadata={"min_length": 1})
    minimum_per_decision: int = field(default=1, metadata={"ge": 1})
    independent: bool = False
    disagreement_procedure: str


@dataclass(kw_only=True)
class ExtractionField(StrictModel):
    id: str
    description: str
    type: Literal["text", "number", "integer", "boolean", "list"] = "text"
    required: bool = True
    choices: list[str] = field(default_factory=list)
    research_questions: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class QualityItem(StrictModel):
    id: str
    question: str
    answers: list[str] = field(metadata={"min_length": 1})


@dataclass(kw_only=True)
class Paths(StrictModel):
    database: str = "data/slr.sqlite"
    artifacts: str = "data/artifacts"
    exports: str = "data/exports"


@dataclass(kw_only=True)
class Protocol(StrictModel):
    schema_version: Literal[1] = 1
    review_id: str
    title: str
    rationale: str
    questions: list[Question] = field(metadata={"min_length": 1})
    sources: list[Source] = field(metadata={"min_length": 1})
    eligibility: list[Criterion]
    reviewers: Reviewers
    quality: list[QualityItem]
    extraction: list[ExtractionField]
    synthesis: dict[str, Any]
    search_start: date | None = None
    search_end: date | None = None
    paths: Paths = field(default_factory=Paths)
    extensions: dict[str, Any] = field(default_factory=dict)

    def validate_model(self) -> Protocol:
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


@dataclass(kw_only=True)
class Stage(StrictModel):
    id: str
    name: str
    skill: str
    entity: EntityType
    enabled: bool = True
    choices: list[str] = field(metadata={"min_length": 1})
    requires: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Roles(StrictModel):
    record_screening: str
    report_screening: str
    quality: str
    extraction: str


@dataclass(kw_only=True)
class Workflow(StrictModel):
    schema_version: Literal[1] = 1
    stages: list[Stage]
    roles: Roles
    extensions: dict[str, Any] = field(default_factory=dict)

    def validate_model(self) -> Workflow:
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


@dataclass(kw_only=True)
class RecordInput(StrictModel):
    source_record_id: str = field(metadata={"min_length": 1})
    title: str = field(metadata={"min_length": 1})
    abstract: str = ""
    doi: str | None = None
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Evidence(StrictModel):
    source: Literal["title", "abstract", "document"]
    quote: str = field(metadata={"min_length": 1})
    document_id: str | None = None
    page: int | None = field(default=None, metadata={"ge": 1})
    element_id: str | None = None


@dataclass(kw_only=True)
class ExtractedValue(StrictModel):
    status: Literal["observed", "not_reported", "not_applicable", "unclear"]
    value: Any = None
    evidence: list[Evidence] = field(default_factory=list)

    def validate_model(self) -> ExtractedValue:
        if self.status == "observed" and (self.value is None or not self.evidence):
            raise ValueError("Observed values require a value and supporting evidence")
        if self.status != "observed" and self.value is not None:
            raise ValueError("Missing or uncertain values must use null")
        return self


@dataclass(kw_only=True)
class Provenance(StrictModel):
    wrapper: str = "opencode"
    provider: str | None = None
    model: str | None = None
    session_id: str | None = None
    prompt_sha256: str | None = None
    notes: str = ""


@dataclass(kw_only=True)
class Draft(StrictModel):
    protocol_revision: str
    entity_type: EntityType
    entity_id: str
    stage: str
    suggestion: str
    rationale: str = field(metadata={"min_length": 1})
    criteria: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    values: dict[str, ExtractedValue] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=Provenance)
