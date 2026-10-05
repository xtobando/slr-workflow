"""Deterministic review operations. LLMs submit proposals; humans record decisions."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import Configuration
from .database import Database, canonical_json, stable_id, utc_now
from .models import Draft, Evidence, RecordInput


def normalized_text(value: str) -> str:
    """Normalize layout whitespace, without forgiving invented or changed words."""
    return " ".join(unicodedata.normalize("NFKC", value).split())


def normalize_doi(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    doi = re.sub(
        r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.IGNORECASE
    )
    if not re.match(r"^10\.\d{4,9}/\S+$", doi, re.IGNORECASE):
        raise ValueError(f"Invalid DOI: {value}")
    return doi.lower()


class ReviewService:
    def __init__(self, config: Configuration):
        self.config = config
        self.db = Database(config.database)

    def initialize(self) -> str:
        self.db.initialize(self.config)
        return self.config.revision

    def check_ready(self) -> None:
        self.db.require_initialized(self.config)

    def require_reviewer(self, identity: str) -> None:
        if identity not in self.config.protocol.reviewers.identities:
            raise ValueError("Reviewer is not listed in protocol.yaml")

    def protocol_approved(self, connection: sqlite3.Connection) -> bool:
        return bool(
            connection.execute(
                "SELECT 1 FROM events WHERE event_type='protocol_approved' AND protocol_revision=?",
                (self.config.revision,),
            ).fetchone()
        )

    def approve_protocol(self, reviewer: str, reason: str) -> None:
        """Called by the interactive human interface; identity is an audit label, not authentication."""
        self.check_ready()
        self.require_reviewer(reviewer)
        if not reason.strip():
            raise ValueError("Protocol approval requires a justification")
        with self.db.connect(write=True) as connection:
            Database.event(
                connection,
                self.config.revision,
                "protocol_approved",
                "review",
                self.config.protocol.review_id,
                {"reason": reason},
                "human",
                reviewer,
            )

    def import_records(
        self,
        path: Path,
        run_id: str,
        source_id: str,
        query: str,
        searched_at: str,
        truncated: bool = False,
    ) -> dict[str, Any]:
        """Import JSON or CSV; rerunning the same search-run identity is idempotent."""
        self.check_ready()
        sources = {s.id: s for s in self.config.protocol.sources}
        if source_id not in sources:
            raise ValueError("Source is not configured in protocol.yaml")
        from datetime import datetime

        when = datetime.fromisoformat(searched_at)
        if when.tzinfo is None:
            raise ValueError("Search date must include a timezone, for example +00:00")
        raw = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(raw.encode()).hexdigest()
        if path.suffix.lower() == ".csv":
            entries: list[dict[str, Any]] = list(csv.DictReader(io.StringIO(raw)))
            for entry in entries:
                if entry.get("year"):
                    entry["year"] = int(entry["year"])
                else:
                    entry["year"] = None
                for key, default in (("authors", []), ("metadata", {})):
                    entry[key] = json.loads(entry[key]) if entry.get(key) else default
        else:
            entries = json.loads(raw)
            if not isinstance(entries, list):
                raise ValueError("Import JSON must contain an array of records")
        records = [RecordInput.model_validate(entry) for entry in entries]
        if len({r.source_record_id for r in records}) != len(records):
            raise ValueError(
                "Duplicate source_record_id inside one import; resolve the export first"
            )
        with self.db.connect(write=True) as connection:
            if not self.protocol_approved(connection):
                raise ValueError("Approve the current protocol before importing search results")
            old = connection.execute("SELECT * FROM search_runs WHERE id=?", (run_id,)).fetchone()
            signature = (source_id, query, searched_at, digest, int(truncated))
            if old:
                original = tuple(
                    old[k]
                    for k in ("source_id", "query", "searched_at", "import_sha256", "truncated")
                )
                if original != signature:
                    raise ValueError(
                        "Search-run ID already exists with different content or metadata"
                    )
                return {"run_id": run_id, "imported": 0, "already_imported": True}
            connection.execute(
                "INSERT INTO search_runs VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    source_id,
                    sources[source_id].category,
                    query,
                    searched_at,
                    self.config.revision,
                    digest,
                    raw,
                    int(truncated),
                ),
            )
            for record in records:
                record_id = stable_id("rec", run_id + "\0" + record.source_record_id)
                doi = normalize_doi(record.doi)
                report_id = stable_id("rep", "doi:" + doi if doi else "record:" + record_id)
                connection.execute(
                    "INSERT OR IGNORE INTO reports VALUES (?,?,?,?)",
                    (report_id, doi, record.title, utc_now()),
                )
                connection.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        run_id,
                        record.source_record_id,
                        report_id,
                        record.title,
                        record.abstract,
                        record.year,
                        canonical_json(record.model_dump()),
                    ),
                )
            Database.event(
                connection,
                self.config.revision,
                "search_imported",
                "review",
                self.config.protocol.review_id,
                {"run_id": run_id, "records": len(records)},
            )
        return {"run_id": run_id, "imported": len(records), "already_imported": False}

    def records(self) -> list[dict[str, Any]]:
        self.check_ready()
        with self.db.connect() as connection:
            return [dict(r) for r in connection.execute("SELECT * FROM records ORDER BY rowid")]

    def events(
        self, connection: sqlite3.Connection, event_type: str, cutoff: int | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events WHERE event_type=?"
        params: list[Any] = [event_type]
        if cutoff is not None:
            sql += " AND sequence<=?"
            params.append(cutoff)
        return [dict(row) for row in connection.execute(sql + " ORDER BY sequence", params)]

    def duplicate_map(
        self, connection: sqlite3.Connection, cutoff: int | None = None
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for event in self.events(connection, "duplicate_marked", cutoff):
            result[event["entity_id"]] = json.loads(event["payload"])["canonical_record_id"]
        return result

    def deduplicate(self) -> dict[str, Any]:
        """Mark exact same-publication records; ambiguous no-DOI records remain for review."""
        self.check_ready()
        added: list[dict[str, str]] = []
        with self.db.connect(write=True) as connection:
            duplicates = self.duplicate_map(connection)
            canonical: dict[str, str] = {}
            for row in connection.execute("SELECT * FROM records ORDER BY rowid"):
                report_id, record_id = row["report_id"], row["id"]
                if report_id not in canonical:
                    canonical[report_id] = record_id
                elif record_id not in duplicates:
                    if connection.execute(
                        "SELECT 1 FROM decisions WHERE entity_type='record' AND entity_id=?",
                        (record_id,),
                    ).fetchone():
                        raise ValueError(
                            "Deduplicate before screening; this duplicate already has decisions needing explicit resolution"
                        )
                    pair = {"canonical_record_id": canonical[report_id], "rule": "normalized_doi"}
                    Database.event(
                        connection,
                        self.config.revision,
                        "duplicate_marked",
                        "record",
                        record_id,
                        pair,
                    )
                    added.append({"record_id": record_id, **pair})
        return {
            "duplicates_marked": len(added),
            "pairs": added,
            "note": "No DOI-free fuzzy merges are performed in this iteration",
        }

    def effective_decision(
        self,
        connection: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        stage: str,
        cutoff: int | None = None,
    ) -> dict[str, Any] | None:
        """Compute consensus from each reviewer's latest entry, without erasing revisions."""
        rows = connection.execute(
            "SELECT rowid AS insertion_order,* FROM decisions WHERE protocol_revision=? "
            "AND entity_type=? AND entity_id=? AND stage=? ORDER BY rowid",
            (self.config.revision, entity_type, entity_id, stage),
        ).fetchall()
        if cutoff is not None:
            allowed = {
                json.loads(e["payload"])["decision_id"]
                for e in self.events(connection, "decision_recorded", cutoff)
            }
            rows = [r for r in rows if r["id"] in allowed]
        if not rows:
            return None
        last = dict(rows[-1])
        if last["adjudication"]:
            return last
        reviewers: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not row["adjudication"]:
                reviewers[row["reviewer"]] = dict(row)
        if len(reviewers) < self.config.protocol.reviewers.minimum_per_decision:
            return None
        if len({r["choice"] for r in reviewers.values()}) != 1:
            return None
        if stage in (self.config.workflow.roles.quality, self.config.workflow.roles.extraction):
            signatures = {
                canonical_json(
                    {
                        key: {"status": value["status"], "value": value["value"]}
                        for key, value in json.loads(row["values_json"]).items()
                    }
                )
                for row in reviewers.values()
            }
            if len(signatures) != 1:
                return None
        return max(reviewers.values(), key=lambda r: r["insertion_order"])

    def entity_exists(
        self, connection: sqlite3.Connection, entity_type: str, entity_id: str
    ) -> bool:
        if entity_type == "review":
            return entity_id == self.config.protocol.review_id
        table = {"record": "records", "report": "reports", "study": "studies"}.get(entity_type)
        return bool(
            table
            and connection.execute(f"SELECT 1 FROM {table} WHERE id=?", (entity_id,)).fetchone()
        )

    def check_prerequisites(self, connection: sqlite3.Connection, draft: Draft) -> None:
        stage = self.config.stage(draft.stage)
        for dependency_id in stage.requires:
            dependency = self.config.stage(dependency_id)
            if dependency.entity == "review":
                if dependency.extensions.get(
                    "gate"
                ) == "protocol_approval" and self.protocol_approved(connection):
                    continue
                target_ids = [self.config.protocol.review_id]
            elif dependency.entity == draft.entity_type:
                target_ids = [draft.entity_id]
            elif dependency.entity == "record" and draft.entity_type == "report":
                duplicate_ids = self.duplicate_map(connection)
                target_ids = [
                    r[0]
                    for r in connection.execute(
                        "SELECT id FROM records WHERE report_id=?", (draft.entity_id,)
                    )
                    if r[0] not in duplicate_ids
                ]
            else:
                raise ValueError(
                    "Unsupported cross-entity prerequisite; add a resolver in service.py"
                )
            decisions = [
                self.effective_decision(connection, dependency.entity, target, dependency_id)
                for target in target_ids
            ]
            if not any(d and d["choice"] in ("include", "approved", "complete") for d in decisions):
                raise ValueError(f"Unfulfilled prerequisite: {dependency_id}")
        full_text_stages = (
            self.config.workflow.roles.report_screening,
            self.config.workflow.roles.quality,
            self.config.workflow.roles.extraction,
        )
        if (
            draft.stage in full_text_stages
            and not connection.execute(
                "SELECT 1 FROM documents WHERE report_id=?", (draft.entity_id,)
            ).fetchone()
        ):
            raise ValueError("Attach the full text before reviewing this stage")

    def report_is_included(self, connection: sqlite3.Connection, report_id: str) -> bool:
        """Require a valid current pathway, not only an old full-text approval."""
        decision = self.effective_decision(
            connection, "report", report_id, self.config.workflow.roles.report_screening
        )
        if not decision or decision["choice"] != "include":
            return False
        duplicates = self.duplicate_map(connection)
        for record in connection.execute("SELECT id FROM records WHERE report_id=?", (report_id,)):
            if record["id"] in duplicates:
                continue
            screening = self.effective_decision(
                connection, "record", record["id"], self.config.workflow.roles.record_screening
            )
            if screening and screening["choice"] == "include":
                return True
        return False

    def validate_evidence(
        self, connection: sqlite3.Connection, draft: Draft, evidence: Evidence
    ) -> None:
        if evidence.source in ("title", "abstract"):
            if evidence.document_id or evidence.page or evidence.element_id:
                raise ValueError("Bibliographic evidence must not invent document anchors")
            if draft.entity_type == "record":
                texts = connection.execute(
                    f"SELECT {evidence.source} FROM records WHERE id=?", (draft.entity_id,)
                ).fetchall()
            elif draft.entity_type == "report":
                texts = connection.execute(
                    f"SELECT {evidence.source} FROM records WHERE report_id=?", (draft.entity_id,)
                ).fetchall()
            else:
                raise ValueError("Bibliographic evidence requires a record or report target")
            candidates = [row[0] for row in texts]
        else:
            if not evidence.document_id:
                raise ValueError("Document evidence requires document_id")
            row = connection.execute(
                "SELECT * FROM documents WHERE id=?", (evidence.document_id,)
            ).fetchone()
            if not row or draft.entity_type != "report" or row["report_id"] != draft.entity_id:
                raise ValueError("Evidence document does not belong to the target publication")
            elements = json.loads(row["elements_json"])
            if evidence.page is not None or evidence.element_id is not None:
                candidates = [
                    e["text"]
                    for e in elements
                    if (evidence.page is None or e.get("page") == evidence.page)
                    and (evidence.element_id is None or e["id"] == evidence.element_id)
                ]
            else:
                candidates = [row["text_content"] or ""]
        quote = normalized_text(evidence.quote)
        if not any(quote in normalized_text(text) for text in candidates):
            raise ValueError("Evidence quote was not found at the claimed source/anchor")

    def validate_draft(self, draft: Draft, connection: sqlite3.Connection) -> None:
        if draft.protocol_revision != self.config.revision:
            raise ValueError("Draft belongs to an old or unknown protocol/workflow revision")
        if not self.protocol_approved(connection):
            raise ValueError("Approve the current protocol first")
        stage = self.config.stage(draft.stage)
        if stage.entity != draft.entity_type or draft.suggestion not in stage.choices:
            raise ValueError("Draft entity or suggestion does not match workflow.yaml")
        if not self.entity_exists(connection, draft.entity_type, draft.entity_id):
            raise ValueError("Draft references an unknown entity")
        if draft.entity_type == "record" and draft.entity_id in self.duplicate_map(connection):
            raise ValueError("Duplicate records must not be screened again")
        self.check_prerequisites(connection, draft)
        criteria = {c.id: c for c in self.config.protocol.eligibility}
        if any(c not in criteria or draft.stage not in criteria[c].stages for c in draft.criteria):
            raise ValueError("Criterion is unknown or not applicable to this stage")
        if draft.suggestion == "exclude" and not draft.criteria:
            raise ValueError(
                "An exclusion requires at least one criterion; the first is the primary reason"
            )
        all_evidence = draft.evidence + [
            e for value in draft.values.values() for e in value.evidence
        ]
        if draft.suggestion in ("include", "exclude") and not all_evidence:
            raise ValueError("An eligibility recommendation requires supporting evidence")
        full_text_stages = (
            self.config.workflow.roles.report_screening,
            self.config.workflow.roles.quality,
            self.config.workflow.roles.extraction,
        )
        if draft.stage in full_text_stages and any(e.source != "document" for e in all_evidence):
            raise ValueError("Full-text stages require document evidence")
        for evidence in all_evidence:
            self.validate_evidence(connection, draft, evidence)
        if draft.stage == self.config.workflow.roles.extraction:
            definitions = {f.id: f for f in self.config.protocol.extraction}
            if set(draft.values) - definitions.keys():
                raise ValueError(
                    "Unknown extraction variable; edit protocol.yaml and register a revision"
                )
            if {f.id for f in definitions.values() if f.required} - draft.values.keys():
                raise ValueError(
                    "Required variables need an observed or explicit missingness entry"
                )
            for key, extracted in draft.values.items():
                if extracted.status != "observed":
                    continue
                value, definition = extracted.value, definitions[key]
                types = {
                    "text": str,
                    "number": (int, float),
                    "integer": int,
                    "boolean": bool,
                    "list": list,
                }
                if not isinstance(value, types[definition.type]):
                    raise TypeError(f"Wrong value type for {key}")
                if definition.type in ("number", "integer") and isinstance(value, bool):
                    raise ValueError(f"Boolean is not a numerical result: {key}")
                if definition.choices and value not in definition.choices:
                    raise ValueError(f"Value is outside configured choices: {key}")
        elif draft.stage == self.config.workflow.roles.quality:
            definitions = {q.id: q for q in self.config.protocol.quality}
            if set(draft.values) != definitions.keys():
                raise ValueError("Quality draft must contain all configured checklist items")
            for key, answer in draft.values.items():
                if answer.status == "observed" and answer.value not in definitions[key].answers:
                    raise ValueError(f"Unknown quality answer for {key}")
        elif draft.values:
            raise ValueError(
                "Values are supported by quality/extraction roles; extend the validator for custom roles"
            )

    def submit(self, draft_path: Path) -> str:
        self.check_ready()
        draft = Draft.model_validate_json(draft_path.read_text(encoding="utf-8"))
        proposal_id = "proposal_" + uuid4().hex
        skill_path = (
            self.config.root
            / ".opencode"
            / "skills"
            / self.config.stage(draft.stage).skill
            / "SKILL.md"
        )
        skill_hash = (
            hashlib.sha256(skill_path.read_bytes()).hexdigest() if skill_path.exists() else None
        )
        with self.db.connect(write=True) as connection:
            self.validate_draft(draft, connection)
            connection.execute(
                "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?)",
                (
                    proposal_id,
                    self.config.revision,
                    draft.entity_type,
                    draft.entity_id,
                    draft.stage,
                    draft.model_dump_json(),
                    skill_hash,
                    utc_now(),
                ),
            )
            Database.event(
                connection,
                self.config.revision,
                "proposal_submitted",
                draft.entity_type,
                draft.entity_id,
                {"proposal_id": proposal_id, "stage": draft.stage},
                "agent",
                "opencode",
            )
        return proposal_id

    def proposal(self, proposal_id: str) -> Draft:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM proposals WHERE id=?", (proposal_id,)
            ).fetchone()
            if not row:
                raise ValueError("Unknown proposal ID")
            return Draft.model_validate_json(row[0])

    def decide(
        self,
        proposal_id: str,
        reviewer: str,
        revised: Draft | None = None,
        adjudication: bool = False,
    ) -> str:
        self.check_ready()
        self.require_reviewer(reviewer)
        original = self.proposal(proposal_id)
        draft = revised or original
        if any(
            getattr(draft, key) != getattr(original, key)
            for key in ("protocol_revision", "entity_type", "entity_id", "stage")
        ):
            raise ValueError("A revised decision must keep the same proposal target and revision")
        decision_id = "decision_" + uuid4().hex
        with self.db.connect(write=True) as connection:
            self.validate_draft(draft, connection)
            if adjudication:
                reviewers = connection.execute(
                    "SELECT DISTINCT reviewer FROM decisions WHERE protocol_revision=? AND entity_type=? "
                    "AND entity_id=? AND stage=?",
                    (self.config.revision, draft.entity_type, draft.entity_id, draft.stage),
                ).fetchall()
                if len(reviewers) < max(2, self.config.protocol.reviewers.minimum_per_decision):
                    raise ValueError(
                        "Adjudication requires existing judgments from the required reviewers"
                    )
            prior = connection.execute(
                "SELECT id FROM decisions WHERE protocol_revision=? AND entity_type=? AND entity_id=? "
                "AND stage=? AND reviewer=? ORDER BY rowid DESC LIMIT 1",
                (self.config.revision, draft.entity_type, draft.entity_id, draft.stage, reviewer),
            ).fetchone()
            connection.execute(
                "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    decision_id,
                    self.config.revision,
                    draft.entity_type,
                    draft.entity_id,
                    draft.stage,
                    reviewer,
                    draft.suggestion,
                    draft.rationale,
                    canonical_json(draft.criteria),
                    canonical_json([e.model_dump() for e in draft.evidence]),
                    canonical_json({k: v.model_dump() for k, v in draft.values.items()}),
                    proposal_id,
                    int(adjudication),
                    prior[0] if prior else None,
                    utc_now(),
                ),
            )
            Database.event(
                connection,
                self.config.revision,
                "decision_recorded",
                draft.entity_type,
                draft.entity_id,
                {
                    "decision_id": decision_id,
                    "stage": draft.stage,
                    "choice": draft.suggestion,
                    "adjudication": adjudication,
                },
                "human",
                reviewer,
            )
        return decision_id

    def attach(
        self,
        report_id: str,
        path: Path,
        kind: str = "markdown",
        elements: list[dict[str, Any]] | None = None,
    ) -> str:
        self.check_ready()
        if kind not in ("pdf", "markdown", "docling_json"):
            raise ValueError("Unknown document kind")
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        document_id = stable_id("doc", report_id + kind + sha)
        text: str | None = None
        if kind == "markdown":
            text = raw.decode("utf-8")
            # Explicit markers preserve physical PDF page numbers when available.
            sections = re.split(r"<!--\s*page:\s*(\d+)\s*-->", text)
            elements = [{"id": "element_0", "page": None, "text": sections[0]}]
            for index in range(1, len(sections), 2):
                elements.append(
                    {
                        "id": f"element_{index}",
                        "page": int(sections[index]),
                        "text": sections[index + 1],
                    }
                )
        elif kind == "docling_json" and elements:
            text = "\n\n".join(element["text"] for element in elements)
        artifact_dir = self.config.root / self.config.protocol.paths.artifacts / report_id
        suffix = {"pdf": ".pdf", "markdown": ".md", "docling_json": ".json"}[kind]
        destination = artifact_dir / (document_id + suffix)
        with self.db.connect(write=True) as connection:
            if not self.entity_exists(connection, "report", report_id):
                raise ValueError("Unknown publication ID")
            if connection.execute("SELECT 1 FROM documents WHERE id=?", (document_id,)).fetchone():
                return document_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            connection.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",
                (
                    document_id,
                    report_id,
                    kind,
                    sha,
                    str(destination.relative_to(self.config.root)),
                    text,
                    canonical_json(elements or []),
                    utc_now(),
                ),
            )
            Database.event(
                connection,
                self.config.revision,
                "document_attached",
                "report",
                report_id,
                {"document_id": document_id, "sha256": sha, "kind": kind},
            )
            Database.event(
                connection,
                self.config.revision,
                "retrieval_status",
                "report",
                report_id,
                {"status": "retrieved", "document_id": document_id},
            )
        return document_id

    def retrieval_status(self, report_id: str, status: str, reason: str, reviewer: str) -> None:
        self.check_ready()
        self.require_reviewer(reviewer)
        if status not in ("sought", "not_retrieved") or not reason.strip():
            raise ValueError("Use sought or not_retrieved and supply a reason")
        with self.db.connect(write=True) as connection:
            if not self.entity_exists(connection, "report", report_id):
                raise ValueError("Unknown publication ID")
            if (
                status == "not_retrieved"
                and connection.execute(
                    "SELECT 1 FROM documents WHERE report_id=?", (report_id,)
                ).fetchone()
            ):
                raise ValueError(
                    "A publication with attached full text cannot be marked not retrieved"
                )
            Database.event(
                connection,
                self.config.revision,
                "retrieval_status",
                "report",
                report_id,
                {"status": status, "reason": reason},
                "human",
                reviewer,
            )

    def link_study(self, report_id: str, study_id: str, label: str, reviewer: str) -> None:
        self.check_ready()
        self.require_reviewer(reviewer)
        if not study_id.strip() or not label.strip():
            raise ValueError("Study ID and label are required")
        with self.db.connect(write=True) as connection:
            if not self.entity_exists(connection, "report", report_id):
                raise ValueError("Unknown publication ID")
            connection.execute(
                "INSERT OR IGNORE INTO studies VALUES (?,?,?)", (study_id, label, utc_now())
            )
            Database.event(
                connection,
                self.config.revision,
                "study_linked",
                "report",
                report_id,
                {"study_id": study_id, "label": label},
                "human",
                reviewer,
            )

    def unlink_study(self, report_id: str, study_id: str, reason: str, reviewer: str) -> None:
        """Correct a study association by appending an event, preserving its history."""
        self.check_ready()
        self.require_reviewer(reviewer)
        if not reason.strip():
            raise ValueError("A study-link correction requires a reason")
        with self.db.connect(write=True) as connection:
            if not self.entity_exists(connection, "report", report_id) or not self.entity_exists(
                connection, "study", study_id
            ):
                raise ValueError("Unknown publication or study")
            Database.event(
                connection,
                self.config.revision,
                "study_unlinked",
                "report",
                report_id,
                {"study_id": study_id, "reason": reason},
                "human",
                reviewer,
            )

    def packet(self, stage_id: str, entity_id: str) -> dict[str, Any]:
        self.check_ready()
        stage = self.config.stage(stage_id)
        with self.db.connect() as connection:
            if not self.entity_exists(connection, stage.entity, entity_id):
                raise ValueError("Unknown target")
            table = {"record": "records", "report": "reports", "study": "studies"}.get(stage.entity)
            entity = (
                dict(
                    connection.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
                )
                if table
                else {"id": entity_id}
            )
            documents = (
                [
                    dict(r)
                    for r in connection.execute(
                        "SELECT * FROM documents WHERE report_id=?", (entity_id,)
                    )
                ]
                if stage.entity == "report"
                else []
            )
            if stage.entity == "report":
                entity["bibliographic_records"] = [
                    dict(r)
                    for r in connection.execute(
                        "SELECT * FROM records WHERE report_id=?", (entity_id,)
                    )
                ]
        return {
            "protocol_revision": self.config.revision,
            "stage": stage.model_dump(),
            "protocol": self.config.protocol.model_dump(mode="json"),
            "entity": entity,
            "documents": documents,
            "draft_template": {
                "protocol_revision": self.config.revision,
                "entity_type": stage.entity,
                "entity_id": entity_id,
                "stage": stage_id,
                "suggestion": "unclear" if "unclear" in stage.choices else stage.choices[0],
                "rationale": "REPLACE with a concise evidence-backed justification",
                "criteria": [],
                "evidence": [],
                "values": {},
                "provenance": {},
            },
        }

    def search_corpus(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve literal evidence locally; generation is handled by the OpenCode skill."""
        self.check_ready()
        if not query.strip() or limit < 1:
            raise ValueError("Nonempty query and positive limit required")
        hits: list[dict[str, Any]] = []
        with self.db.connect() as connection:
            for document in connection.execute(
                "SELECT * FROM documents WHERE text_content IS NOT NULL"
            ):
                if not self.report_is_included(connection, document["report_id"]):
                    continue
                for element in json.loads(document["elements_json"]):
                    if query.casefold() in element["text"].casefold():
                        hits.append(
                            {
                                "report_id": document["report_id"],
                                "document_id": document["id"],
                                "page": element.get("page"),
                                "element_id": element["id"],
                                "text": element["text"],
                                "retrieval": "literal",
                            }
                        )
                        if len(hits) == limit:
                            return hits
        return hits
