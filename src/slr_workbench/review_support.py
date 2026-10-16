"""Read-only pilot inspection and individual human-review handoffs.

These projections are not another decision service: only the existing interactive
review command may record a scientific judgment. Reviewer labels are audit labels,
not authentication or proof of independent assessment.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import canonical_json, utc_now
from .models import Draft
from .service import ReviewService


def _command(*arguments: str) -> dict[str, str]:
    """Always quote arguments for each shell; never interpolate research text."""
    if any(any(ord(char) < 32 or ord(char) == 127 for char in part) for part in arguments):
        raise ValueError("Command arguments must not contain control characters")
    quoted_posix = ["'" + part.replace("'", "'\"'\"'") + "'" for part in arguments]
    quoted_windows = ["'" + part.replace("'", "''") + "'" for part in arguments]
    return {
        "macos_linux": "python -m slr_workbench " + " ".join(quoted_posix),
        "windows_powershell": "python -m slr_workbench " + " ".join(quoted_windows),
    }


def _metadata(records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    streams: set[str] = set()
    batches: set[str] = set()
    for record in records:
        metadata = json.loads(record["raw_metadata"]).get("metadata", {})
        for key in ("evidence_stream", "evidence_streams"):
            value = metadata.get(key)
            values = value if isinstance(value, list) else [value]
            streams.update(item for item in values if isinstance(item, str) and item)
        for key in ("batch", "batch_id", "round_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                batches.add(value)
    return sorted(streams), sorted(batches)


def _decision(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "reviewer": row["reviewer"],
        "choice": row["choice"],
        "proposal_id": row["proposal_id"],
        "adjudication": bool(row["adjudication"]),
        "supersedes": row["supersedes"],
        "rationale": row["rationale"],
        "criteria": json.loads(row["criteria_json"]),
        "values": json.loads(row["values_json"]),
    }


def _signature(choice: str, values: dict[str, Any], with_values: bool) -> str:
    signature: dict[str, Any] = {"choice": choice}
    if with_values:
        signature["values"] = {
            key: {"status": item["status"], "value": item["value"]} for key, item in values.items()
        }
    return canonical_json(signature)


def _uncertainty(draft: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, str]]:
    questions = []
    if draft["suggestion"] == "unclear":
        questions.append(
            {
                "question": "What source evidence resolves the draft uncertainty: "
                + draft["rationale"]
                + "?",
                "evidence_needed": "Check the cited source against the exact protocol criterion.",
                "next_permitted_action": "Inspect the source and revise the draft or keep unclear.",
            }
        )
    if records and all(not record["abstract"].strip() for record in records):
        questions.append(
            {
                "question": "Can relevance be established without an available abstract?",
                "evidence_needed": "Verified bibliographic source text or a lawfully available abstract.",
                "next_permitted_action": "Inspect available metadata; missing abstract is not exclusion.",
            }
        )
    for key, value in draft["values"].items():
        if value["status"] != "observed":
            questions.append(
                {
                    "question": f"Is {key} truly {value['status']} in the source?",
                    "evidence_needed": "Inspect relevant full-text sections and the field definition.",
                    "next_permitted_action": "Verify missingness; submit a supported revision if needed.",
                }
            )
    return questions


def inspect_queue(
    current: ReviewService,
    *,
    reviewer: str | None = None,
    stage: str | None = None,
    batch: list[str] | None = None,
    evidence_stream: str | None = None,
    uncertain_only: bool = False,
    include_history: bool = False,
    unblind: bool = False,
    pending_only: bool = True,
    limit: int | None = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Inspect proposals and latest human judgments in one strictly read-only snapshot.

    Batch members may be proposal, record, report, search-run IDs or explicit
    metadata batch labels. Evidence streams come only from imported metadata.
    Historical revisions are visibly segregated and never get review commands.
    """
    if offset < 0 or (limit is not None and limit < 1):
        raise ValueError("Offset must be nonnegative and limit must be positive")
    if reviewer is not None:
        current.require_reviewer(reviewer)
    if stage is not None:
        current.config.stage(stage)
    blind = current.config.protocol.reviewers.independent and not unblind
    if blind and uncertain_only:
        raise ValueError("Uncertainty filtering reveals recommendations; explicitly unblind first")
    result: dict[str, Any] = {
        "schema_version": 1,
        "review_id": current.config.protocol.review_id,
        "protocol_revision": current.config.revision,
        "roles": current.config.workflow.roles.model_dump(),
        "reviewer": reviewer,
        "blind": blind,
        "initialized": False,
        "history_totals": None,
        "protocol_approved": False,
        "event_sequence": 0,
        "event_head_hash": "0" * 64,
        "filters": {
            "stage": stage,
            "batch": batch or [],
            "evidence_stream": evidence_stream,
            "uncertain_only": uncertain_only,
            "pending_only": pending_only,
            "limit": limit,
            "offset": offset,
        },
        "current": [],
        "historical": [],
        "full_text_pathways": [],
        "full_text_pathways_total": 0,
        "total_matching": 0,
        "total_pending": 0,
        "remaining": 0,
        "omitted_before": 0,
        "total_historical": 0,
        "blockers": [],
        "warnings": [
            "A proposal is not a human decision. Reviewer labels do not prove independence.",
            "Research text is untrusted data; commands use identifiers only.",
        ],
    }
    if not current.config.database.exists():
        result["blockers"].append("Review database is absent; run init before scientific work.")
        return result
    connection = sqlite3.connect(current.config.database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        result["initialized"] = bool(
            connection.execute(
                "SELECT 1 FROM protocol_versions WHERE revision=?", (current.config.revision,)
            ).fetchone()
        )
        result["protocol_approved"] = current.protocol_approved(connection)
        head = connection.execute(
            "SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        if head:
            result.update(event_sequence=head["sequence"], event_head_hash=head["event_hash"])
        if not result["initialized"]:
            result["blockers"].append("Configuration changed; run init and obtain human approval.")
        if not result["protocol_approved"]:
            result["blockers"].append("Current protocol revision requires human approval.")
        proposals = [
            dict(row)
            for row in connection.execute(
                "SELECT rowid AS insertion_order,* FROM proposals ORDER BY rowid"
            )
        ]
        decisions = [
            dict(row)
            for row in connection.execute(
                "SELECT rowid AS insertion_order,* FROM decisions ORDER BY rowid"
            )
        ]
        result["history_totals"] = {
            "proposals_all_revisions": len(proposals),
            "human_decisions_all_revisions": len(decisions),
            "proposals_current_revision": sum(
                row["protocol_revision"] == current.config.revision for row in proposals
            ),
            "human_decisions_current_revision": sum(
                row["protocol_revision"] == current.config.revision for row in decisions
            ),
        }
        records = [dict(row) for row in connection.execute("SELECT * FROM records ORDER BY rowid")]
        documents = [dict(row) for row in connection.execute("SELECT * FROM documents")]
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for proposal in proposals:
            key = tuple(
                proposal[field]
                for field in ("protocol_revision", "entity_type", "entity_id", "stage")
            )
            groups.setdefault(key, []).append(proposal)
        duplicates = current.duplicate_map(connection)
        for key, group in groups.items():
            revision, entity_type, entity_id, stage_id = key
            historical = revision != current.config.revision
            if historical and not include_history:
                continue
            if stage is not None and stage_id != stage:
                continue
            proposal = group[-1]
            draft = json.loads(proposal["payload"])
            entity_records = [
                row
                for row in records
                if (
                    row["id"] == entity_id
                    if entity_type == "record"
                    else row["report_id"] == entity_id
                    if entity_type == "report"
                    else False
                )
            ]
            streams, metadata_batches = _metadata(entity_records)
            identifiers = {proposal["id"], entity_id, *metadata_batches}
            for record in entity_records:
                identifiers.update((record["id"], record["report_id"], record["search_run_id"]))
            if batch and not identifiers.intersection(batch):
                continue
            if evidence_stream and evidence_stream not in streams:
                continue
            scoped = [
                row
                for row in decisions
                if (row["protocol_revision"], row["entity_type"], row["entity_id"], row["stage"])
                == key
            ]
            latest: dict[str, dict[str, Any]] = {}
            for decision in scoped:
                latest[decision["reviewer"]] = decision
            effective = (
                None
                if historical
                else current.effective_decision(connection, entity_type, entity_id, stage_id)
            )
            blockers = []
            if historical:
                blockers.append("Historical revision: prepare a new current-revision proposal.")
            else:
                try:
                    current.validate_draft(Draft.model_validate(draft), connection)
                except (ValueError, TypeError, KeyError) as error:
                    blockers.append(str(error))
            if entity_type == "record" and entity_id in duplicates:
                blockers.append("Record is a bibliographic duplicate; do not screen it again.")
            own = latest.get(reviewer) if reviewer else None
            completed = bool(
                effective
                and not blockers
                and (
                    own and own["proposal_id"] == proposal["id"]
                    if reviewer
                    else effective["proposal_id"] == proposal["id"]
                )
            )
            if pending_only and completed and not historical:
                continue
            questions = _uncertainty(draft, entity_records)
            disagreement = (
                len(
                    {
                        _signature(
                            row["choice"],
                            json.loads(row["values_json"]),
                            stage_id
                            in (
                                current.config.workflow.roles.quality,
                                current.config.workflow.roles.extraction,
                            ),
                        )
                        for row in latest.values()
                    }
                )
                > 1
            )
            if uncertain_only and not (questions or disagreement):
                continue
            if not historical and not completed:
                result["total_pending"] += 1
            row = {
                "proposal_id": proposal["id"],
                "proposal_ids": [entry["id"] for entry in group],
                "older_proposal_ids": [entry["id"] for entry in group[:-1]],
                "protocol_revision": revision,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "stage": stage_id,
                "title": entity_records[0]["title"] if entity_records else entity_id,
                "abstract": entity_records[0]["abstract"]
                if entity_type == "record" and entity_records
                else None,
                "search_run_ids": sorted({entry["search_run_id"] for entry in entity_records}),
                "evidence_streams": streams,
                "metadata_batches": metadata_batches,
                "documents": [
                    {field: doc[field] for field in ("id", "kind", "sha256", "local_path")}
                    for doc in documents
                    if entity_type == "report" and doc["report_id"] == entity_id
                ],
                "blockers": blockers,
                "packet_command": None if historical else _command("packet", stage_id, entity_id),
                "human_review_command": None,
            }
            if not historical and reviewer and not blockers:
                command = ["review", proposal["id"], "--reviewer", reviewer]
                if blind:
                    command.extend(("--decision-file", f"data/drafts/human-{proposal['id']}.json"))
                row["human_review_command"] = _command(*command)
            if blind:
                row["status"] = (
                    "independent_assessment_required" if not historical else "historical"
                )
                row["next_permitted_action"] = (
                    "Read the packet and source; create your own complete decision JSON before "
                    "running review --decision-file in a separate human-operated terminal."
                )
            else:
                own = latest.get(reviewer) if reviewer else None
                pending_for_reviewer = own is None or own["proposal_id"] != proposal["id"]
                row.update(
                    recommendation=draft["suggestion"],
                    rationale=draft["rationale"],
                    criteria=draft["criteria"],
                    evidence=draft["evidence"],
                    values=draft["values"],
                    latest_human_judgments=[_decision(value) for value in latest.values()],
                    effective_human_decision=_decision(effective) if effective else None,
                    disagreement=disagreement,
                    uncertainty=questions,
                    status="historical"
                    if historical
                    else "blocked"
                    if blockers
                    else "disagreement"
                    if disagreement and not effective
                    else "pending_reviewer"
                    if reviewer and pending_for_reviewer
                    else "pending_consensus"
                    if not effective
                    else "effective_human_decision",
                    pending_for_reviewer=pending_for_reviewer,
                    next_permitted_action="Resolve blockers before review."
                    if blockers
                    else "Inspect evidence and run the individual interactive review command.",
                )
                if disagreement:
                    row["uncertainty"].append(
                        {
                            "question": "Which documented interpretation resolves reviewer disagreement?",
                            "evidence_needed": "Compare independent judgments with criteria and source anchors.",
                            "next_permitted_action": "Follow the configured disagreement procedure; "
                            "use existing interactive adjudication only when its prerequisites hold.",
                        }
                    )
            result["historical" if historical else "current"].append(row)
        if not blind:
            result["full_text_pathways"] = _full_text_pathways(current, connection)
    finally:
        connection.close()
    result["full_text_pathways_total"] = len(result["full_text_pathways"])
    result["full_text_pathways"] = result["full_text_pathways"][
        offset : None if limit is None else offset + limit
    ]
    result["total_matching"] = len(result["current"])
    result["total_historical"] = len(result["historical"])
    end = None if limit is None else offset + limit
    result["current"] = result["current"][offset:end]
    result["historical"] = result["historical"][:limit]
    result["omitted_before"] = min(offset, result["total_matching"])
    result["remaining"] = max(0, result["total_matching"] - offset - len(result["current"]))
    result["summary"] = dict(Counter(row["status"] for row in result["current"]))
    if not result["current"]:
        result["warnings"].append(
            "No current proposals match; no pilot has been completed by this view."
        )
    if blind:
        result["warnings"].append(
            "Blind view hides recommendations, rationale, citations, values and other human judgments. "
            "Explicit human unblinding is needed for recommendation comparisons."
        )
    return result


def evaluate_pilot(current: ReviewService, **filters: Any) -> dict[str, Any]:
    """Compare drafts to effective human judgments, never to agent self-agreement."""
    filters.setdefault("pending_only", False)
    filters.setdefault("limit", None)
    queue = inspect_queue(current, **filters)
    comparisons = []
    for row in queue["current"]:
        if queue["blind"]:
            continue
        effective = row["effective_human_decision"]
        if not effective:
            continue
        with_values = row["stage"] in (queue["roles"]["quality"], queue["roles"]["extraction"])
        comparisons.append(
            {
                "proposal_id": row["proposal_id"],
                "entity_id": row["entity_id"],
                "stage": row["stage"],
                "decision_id": effective["id"],
                "decision_proposal_id": effective["proposal_id"],
                "same_proposal": effective["proposal_id"] == row["proposal_id"],
                "current_prerequisites_satisfied": not row["blockers"],
                "recommendation": row["recommendation"],
                "human_choice": effective["choice"],
                "matches": _signature(row["recommendation"], row["values"], with_values)
                == _signature(effective["choice"], effective["values"], with_values),
                "missing_values": {
                    key: value["status"]
                    for key, value in row["values"].items()
                    if value["status"] != "observed"
                },
            }
        )
    comparable = [
        row
        for row in comparisons
        if row["same_proposal"] and row["current_prerequisites_satisfied"]
    ]
    return {
        **queue,
        "pilot_evaluation": {
            "effective_comparisons": comparisons,
            "same_proposal_compared": len(comparable),
            "matching_recommendations": sum(row["matches"] for row in comparable),
            "changed_recommendations": sum(not row["matches"] for row in comparable),
            "unresolved_targets": None
            if queue["blind"]
            else sum(row["effective_human_decision"] is None for row in queue["current"]),
            "interpretation": "Descriptive within-pilot comparison, not accuracy or independent validation. "
            "Historical human decisions and decisions on older proposals are not current-proposal agreement.",
        },
    }


def _full_text_pathways(
    current: ReviewService, connection: sqlite3.Connection
) -> list[dict[str, Any]]:
    """List real prerequisite gaps without inventing full-text pilot candidates."""
    output = []
    duplicates = current.duplicate_map(connection)
    roles = current.config.workflow.roles
    retrieval = {}
    for event in current.events(connection, "retrieval_status"):
        retrieval[event["entity_id"]] = json.loads(event["payload"])["status"]
    for report in connection.execute("SELECT * FROM reports ORDER BY rowid"):
        records = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM records WHERE report_id=? ORDER BY rowid", (report["id"],)
            )
            if row["id"] not in duplicates
        ]
        if not records:
            continue
        screening = [
            current.effective_decision(connection, "record", record["id"], roles.record_screening)
            for record in records
        ]
        eligible = any(row and row["choice"] == "include" for row in screening)
        documents = [
            dict(row)
            for row in connection.execute(
                "SELECT id,kind,text_content FROM documents WHERE report_id=?", (report["id"],)
            )
        ]
        approvals = {}
        for stage_id in (roles.report_screening, roles.quality, roles.extraction):
            decision = current.effective_decision(connection, "report", report["id"], stage_id)
            approvals[stage_id] = decision["choice"] if decision else "pending"
        missing = []
        if not eligible:
            missing.append(f"Human include at {roles.record_screening} is required first.")
        if not documents:
            missing.append("No attached full text; discovery/reading is not eligibility exclusion.")
        elif not any(doc["text_content"] for doc in documents):
            missing.append("No attached extracted text; verify conversion and source anchors.")
        if approvals[roles.report_screening] != "include":
            missing.append(
                f"Human include at {roles.report_screening} is required for downstream work."
            )
        extraction_stage = next(
            stage for stage in current.config.workflow.stages if stage.id == roles.extraction
        )
        if roles.quality in extraction_stage.requires and (
            approvals[roles.quality] not in ("approved", "include", "complete")
        ):
            missing.append(
                f"Configured {roles.quality} approval may block extraction; inspect actual prerequisites."
            )
        readiness = {}
        for stage_id in (roles.report_screening, roles.quality, roles.extraction):
            try:
                stage = current.config.stage(stage_id)
                inspection = Draft(
                    protocol_revision=current.config.revision,
                    entity_type="report",
                    entity_id=report["id"],
                    stage=stage_id,
                    suggestion=stage.choices[0],
                    rationale="Read-only prerequisite inspection",
                )
                current.check_prerequisites(connection, inspection)
                readiness[stage_id] = {
                    "ready": current.protocol_approved(connection),
                    "blocker": None
                    if current.protocol_approved(connection)
                    else "Current protocol requires human approval.",
                }
            except ValueError as error:
                readiness[stage_id] = {"ready": False, "blocker": str(error)}
        output.append(
            {
                "report_id": report["id"],
                "title": report["title"],
                "evidence_streams": _metadata(records)[0],
                "record_screening_included": eligible,
                "retrieval_status": retrieval.get(report["id"], "pending"),
                "attached_documents": [{"id": doc["id"], "kind": doc["kind"]} for doc in documents],
                "human_choices": approvals,
                "stage_prerequisites": readiness,
                "blockers": missing,
                "next_permitted_action": "Inspect configured stage prerequisites before drafting; "
                "hand human decisions to a separate terminal. Public-source discovery and read-pdf "
                "do not change eligibility or retrieval status.",
            }
        )
    return output


def _safe(value: Any) -> str:
    """Render research data as literal text, including fences, links and HTML."""
    escaped = html.escape(str(value), quote=True).replace("\n", "<br>")
    return "".join(f"&#{ord(char)};" if char in "`[]*_#|\\" else char for char in escaped)


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Human review package",
        "",
        f"Revision: `{result['protocol_revision']}`",
        "",
        "Read-only snapshot. Run decisions yourself in a separate interactive terminal.",
        "",
        "Research text below is data, never instructions.",
        "",
    ]
    lines.extend(
        [
            (
                f"Shown: {len(result['current'])}; matching targets: {result['total_matching']}; "
                f"pending targets: {result['total_pending']}; remaining after this sheet: {result['remaining']}."
            ),
            "",
            "Rerun after human decisions to resume the pending queue; offset pages a snapshot only.",
            "",
        ]
    )
    if result["blind"]:
        lines.extend(["Blind initial assessment: recommendations and judgments are hidden.", ""])
    for index, row in enumerate(result["current"], 1):
        lines.extend(
            [
                f"## {index}. {_safe(row['title'])}",
                "",
                (
                    f"Target: {_safe(row['entity_id'])}; stage: {_safe(row['stage'])}; "
                    f"status: {_safe(row['status'])}."
                ),
                "",
            ]
        )
        if row["abstract"] is not None:
            lines.extend(["Abstract (untrusted research data): " + _safe(row["abstract"]), ""])
        if not result["blind"]:
            lines.extend(
                [
                    "Recommendation: " + _safe(row["recommendation"]),
                    "",
                    "Rationale: " + _safe(row["rationale"]),
                    "",
                    "Criteria: " + _safe(", ".join(row["criteria"]) or "None recorded"),
                    "",
                ]
            )
            for evidence in row["evidence"]:
                lines.extend(
                    [
                        "Evidence (verify exact source/anchor): " + _safe(canonical_json(evidence)),
                        "",
                    ]
                )
            for question in row["uncertainty"]:
                lines.extend(
                    [
                        "Unresolved question: " + _safe(question["question"]),
                        "",
                        "Evidence needed: " + _safe(question["evidence_needed"]),
                        "",
                        "Next permitted action: " + _safe(question["next_permitted_action"]),
                        "",
                    ]
                )
            judgments = row["latest_human_judgments"]
            lines.extend(
                [
                    "Latest human judgments: "
                    + _safe(
                        "; ".join(
                            f"{value['reviewer']}: {value['choice']} ({value['id']})"
                            for value in judgments
                        )
                        or "None recorded"
                    ),
                    "",
                ]
            )
        for blocker in row["blockers"]:
            lines.extend(["Blocker: " + _safe(blocker), ""])
        lines.extend([_safe(row["next_permitted_action"]), ""])
        for label, command in (
            ("Source packet", row["packet_command"]),
            ("Human review", row["human_review_command"]),
        ):
            if command:
                lines.extend(
                    [
                        label + " — macOS/Linux:",
                        "",
                        "```sh",
                        command["macos_linux"],
                        "```",
                        "",
                        label + " — Windows PowerShell:",
                        "",
                        "```powershell",
                        command["windows_powershell"],
                        "```",
                        "",
                    ]
                )
    lines.extend(
        [
            "## Historical revisions",
            "",
            f"{len(result['historical'])} historical targets; no commands reuse their decisions.",
            "",
        ]
    )
    for row in result["historical"]:
        lines.extend(
            [
                (
                    f"- {_safe(row['entity_id'])}, {_safe(row['stage'])}, "
                    f"revision `{row['protocol_revision']}`."
                ),
                "",
            ]
        )
    lines.extend(["## Warnings and blockers", ""])
    for warning in result["blockers"] + result["warnings"]:
        lines.append("- " + _safe(warning))
    return "\n".join(lines) + "\n"


def export_review_package(
    current: ReviewService, *, reviewer: str, package_id: str | None = None, **filters: Any
) -> Path:
    """Write an immutable fresh derived package; never overwrite historical exports."""
    filters.setdefault("pending_only", True)
    filters.setdefault("limit", 25)
    result = evaluate_pilot(current, reviewer=reviewer, **filters)
    identifier = package_id or "pilot-" + uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", identifier):
        raise ValueError("Package ID must be a simple name, not a path")
    base = current.config.root / "data" / "review-packages"
    if not base.resolve().is_relative_to(current.config.root.resolve()):
        raise ValueError("Review package directory must remain inside the project")
    base.mkdir(parents=True, exist_ok=True)
    directory = base / identifier
    directory.mkdir(exist_ok=False)
    (directory / "review.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (directory / "review.md").write_text(_markdown(result), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "protocol_revision": result["protocol_revision"],
        "event_sequence": result["event_sequence"],
        "event_head_hash": result["event_head_hash"],
        "files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.iterdir())
        },
        "purpose": "Read-only human review handoff; no decision or approval was recorded.",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return directory
