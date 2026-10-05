"""Generate auditable PRISMA count data and tables from a consistent database snapshot."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .database import canonical_json, utc_now
from .service import ReviewService


def snapshot(service: ReviewService, cutoff: int | None = None) -> dict[str, Any]:
    """Count records, reports and linked studies separately. Pending work remains explicit."""
    service.check_ready()
    with service.db.connect() as connection:
        connection.execute("BEGIN")
        head = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
        cutoff = head if cutoff is None else cutoff
        if cutoff < 0 or cutoff > head:
            raise ValueError("Snapshot sequence is outside the audit history")
        search_ids = {
            json.loads(e["payload"])["run_id"]
            for e in service.events(connection, "search_imported", cutoff)
        }
        records = [
            dict(r)
            for r in connection.execute("SELECT * FROM records ORDER BY rowid")
            if r["search_run_id"] in search_ids
        ]
        searches = {
            r["id"]: dict(r)
            for r in connection.execute("SELECT * FROM search_runs")
            if r["id"] in search_ids
        }
        duplicates = service.duplicate_map(connection, cutoff)
        retained = [r for r in records if r["id"] not in duplicates]
        by_source = Counter(searches[r["search_run_id"]]["source_id"] for r in records)
        by_category = Counter(searches[r["search_run_id"]]["category"] for r in records)
        counts: dict[str, int] = {
            "records_identified": len(records),
            "duplicate_records_removed": len(records) - len(retained),
            "records_marked_ineligible_by_automation": 0,
            "records_removed_for_other_reasons": 0,
            "records_available_for_screening": len(retained),
            "records_screened": 0,
            "records_excluded": 0,
            "records_pending": 0,
            "records_unclear": 0,
            "reports_sought_for_retrieval": 0,
            "reports_not_retrieved": 0,
            "reports_awaiting_retrieval": 0,
            "reports_retrieved": 0,
            "reports_assessed_for_eligibility": 0,
            "reports_excluded": 0,
            "reports_pending_full_text_screening": 0,
            "reports_unclear": 0,
            "reports_included": 0,
            "studies_included": 0,
        }
        candidates: set[str] = set()
        screening_rows: list[dict[str, Any]] = []
        for record in retained:
            decision = service.effective_decision(
                connection,
                "record",
                record["id"],
                service.config.workflow.roles.record_screening,
                cutoff,
            )
            choice = decision["choice"] if decision else "pending"
            counts["records_pending" if not decision else "records_screened"] += 1
            if choice == "exclude":
                counts["records_excluded"] += 1
            elif choice == "include":
                candidates.add(record["report_id"])
            elif choice not in ("include", "exclude", "pending"):
                counts["records_unclear"] += 1
            screening_rows.append(
                {
                    "record_id": record["id"],
                    "report_id": record["report_id"],
                    "title": record["title"],
                    "title_abstract_decision": choice,
                }
            )
        retrieval: dict[str, str] = {}
        for event in service.events(connection, "retrieval_status", cutoff):
            retrieval[event["entity_id"]] = json.loads(event["payload"])["status"]
        reasons: Counter[str] = Counter()
        included: set[str] = set()
        summary: list[dict[str, Any]] = []
        for report_id in sorted(candidates):
            status = retrieval.get(report_id, "pending")
            if status == "pending":
                counts["reports_awaiting_retrieval"] += 1
                continue
            counts["reports_sought_for_retrieval"] += 1
            if status == "not_retrieved":
                counts["reports_not_retrieved"] += 1
                continue
            if status == "sought":
                counts["reports_awaiting_retrieval"] += 1
                continue
            counts["reports_retrieved"] += 1
            decision = service.effective_decision(
                connection,
                "report",
                report_id,
                service.config.workflow.roles.report_screening,
                cutoff,
            )
            if not decision:
                counts["reports_pending_full_text_screening"] += 1
                continue
            counts["reports_assessed_for_eligibility"] += 1
            if decision["choice"] == "exclude":
                counts["reports_excluded"] += 1
                reasons[json.loads(decision["criteria_json"])[0]] += 1
            elif decision["choice"] != "include":
                counts["reports_unclear"] += 1
            elif decision["choice"] == "include":
                included.add(report_id)
                report = connection.execute(
                    "SELECT * FROM reports WHERE id=?", (report_id,)
                ).fetchone()
                extraction = service.effective_decision(
                    connection,
                    "report",
                    report_id,
                    service.config.workflow.roles.extraction,
                    cutoff,
                )
                # An extraction stops being effective when a required approval is withdrawn.
                if extraction:
                    for dependency_id in service.config.stage(
                        service.config.workflow.roles.extraction
                    ).requires:
                        dependency = service.config.stage(dependency_id)
                        if dependency.entity != "report":
                            continue
                        approval = service.effective_decision(
                            connection, "report", report_id, dependency_id, cutoff
                        )
                        if not approval or approval["choice"] not in (
                            "include",
                            "approved",
                            "complete",
                        ):
                            extraction = None
                            break
                entry = {
                    "report_id": report_id,
                    "title": report["title"],
                    "doi": report["doi"],
                    "extraction_decision_id": extraction["id"]
                    if extraction and extraction["choice"] == "approved"
                    else "",
                }
                values = (
                    json.loads(extraction["values_json"]) if entry["extraction_decision_id"] else {}
                )
                for field in service.config.protocol.extraction:
                    value = values.get(field.id)
                    entry[field.id] = (
                        (
                            canonical_json(value["value"])
                            if value["status"] == "observed"
                            else value["status"]
                        )
                        if value
                        else "pending"
                    )
                summary.append(entry)
        study_links: dict[tuple[str, str], bool] = {}
        link_events = service.events(connection, "study_linked", cutoff) + service.events(
            connection, "study_unlinked", cutoff
        )
        for event in sorted(link_events, key=lambda e: e["sequence"]):
            study_links[(event["entity_id"], json.loads(event["payload"])["study_id"])] = (
                event["event_type"] == "study_linked"
            )
        linked_reports = {
            report for (report, _), active in study_links.items() if active and report in included
        }
        included_studies = {
            study
            for (report, study), active in study_links.items()
            if active and report in included
        }
        counts["reports_included"] = len(included)
        counts["studies_included"] = len(included_studies)
        warnings: list[str] = []
        if included - linked_reports:
            warnings.append(
                "Included reports still need human-confirmed study links; study count is provisional"
            )
        if any(r["truncated"] for r in searches.values()):
            warnings.append(
                "One or more searches were truncated; search completeness must be addressed"
            )
        if (
            counts["records_pending"]
            or counts["records_unclear"]
            or counts["reports_awaiting_retrieval"]
            or counts["reports_pending_full_text_screening"]
            or counts["reports_unclear"]
        ):
            warnings.append(
                "Review is incomplete; unresolved entries are not counted as exclusions"
            )
        if any(not entry["extraction_decision_id"] for entry in summary):
            warnings.append("Some included reports still need approved extraction")
        if counts["records_identified"] != counts["duplicate_records_removed"] + len(retained):
            raise ValueError("Record accounting does not reconcile")
        if (
            counts["records_excluded"] > counts["records_screened"]
            or sum(reasons.values()) != counts["reports_excluded"]
        ):
            raise ValueError("Screening or exclusion accounting does not reconcile")
        approved = bool(
            connection.execute(
                "SELECT 1 FROM events WHERE event_type='protocol_approved' AND protocol_revision=? AND sequence<=?",
                (service.config.revision, cutoff),
            ).fetchone()
        )
        if not approved:
            warnings.append("Current protocol revision was not approved at this snapshot")
        head_row = connection.execute(
            "SELECT event_hash FROM events WHERE sequence<=? ORDER BY sequence DESC LIMIT 1",
            (cutoff,),
        ).fetchone()
    return {
        "schema_version": 1,
        "review_id": service.config.protocol.review_id,
        "protocol_revision": service.config.revision,
        "event_sequence": cutoff,
        "event_head_hash": head_row[0] if head_row else "0" * 64,
        "counts": counts,
        "identified_by_source": dict(by_source),
        "identified_by_category": dict(by_category),
        "full_text_exclusion_reasons": dict(reasons),
        "warnings": warnings,
        "screening": screening_rows,
        "summary": summary,
        "scope": "new-review count data; select the appropriate official PRISMA template",
    }


def latex_escape(value: Any) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in str(value))


def export_snapshot(service: ReviewService, cutoff: int | None = None) -> Path:
    result = snapshot(service, cutoff)
    directory = (
        service.config.root
        / service.config.protocol.paths.exports
        / (service.config.revision[:12] + "-" + str(result["event_sequence"]))
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "prisma_counts.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for filename, rows, headers in (
        (
            "screening.csv",
            result["screening"],
            ["record_id", "report_id", "title", "title_abstract_decision"],
        ),
        (
            "summary.csv",
            result["summary"],
            ["report_id", "title", "doi", "extraction_decision_id"]
            + [f.id for f in service.config.protocol.extraction],
        ),
    ):
        with (directory / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    lines = [r"\begin{tabular}{lll}", "Report & Title & DOI " + r"\\", r"\hline"]
    for row in result["summary"]:
        lines.append(
            " & ".join(latex_escape(row[key] or "") for key in ("report_id", "title", "doi"))
            + " "
            + r"\\"
        )
    lines.append(r"\end{tabular}")
    (directory / "summary.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {
        "created_at": utc_now(),
        "protocol_revision": service.config.revision,
        "event_sequence": result["event_sequence"],
        "files": {},
    }
    for path in sorted(directory.iterdir()):
        if path.name != "manifest.json":
            manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return directory
