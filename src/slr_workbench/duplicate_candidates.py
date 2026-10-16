"""Read-only bibliographic hints; candidate scores never resolve publication identity."""

from __future__ import annotations

import html
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .database import canonical_json
from .search.catalog import PROVIDERS
from .service import normalize_doi

if TYPE_CHECKING:
    from .service import ReviewService


def normalize_title(value: str) -> str:
    """Normalize typography, case and punctuation without discarding title words."""
    value = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _doi(value: Any) -> str | None:
    try:
        return normalize_doi(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _arxiv(value: Any) -> tuple[str, str | None] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"(?:https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/|arxiv:|10\.48550/arxiv\.)?"
        r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7})(v\d+)?(?:\.pdf)?",
        value.strip(),
        re.IGNORECASE,
    )
    return (match[1].casefold(), match[2].casefold() if match[2] else None) if match else None


IDENTITY_RELATIONS = {
    "is-preprint-of",
    "has-preprint",
    "is-version-of",
    "has-version",
    "is-identical-to",
    "is-manuscript-of",
    "has-manuscript",
    "is-original-form-of",
    "is-variant-form-of",
    "is-new-version-of",
    "is-previous-version-of",
}


def _relations(metadata: dict[str, Any]) -> list[dict[str, str]]:
    """Read explicitly labelled DOI relations, never infer a relation from any DOI mention."""
    result: list[dict[str, str]] = []
    relation = metadata.get("relation", {})
    if isinstance(relation, dict):
        for kind, targets in relation.items():
            if kind not in IDENTITY_RELATIONS or not isinstance(targets, list):
                continue
            for target in targets:
                if isinstance(target, dict) and target.get("id-type") == "doi":
                    doi = _doi(target.get("id"))
                    if doi:
                        result.append({"type": str(kind), "doi": doi})
    relations = metadata.get("relations", [])
    if isinstance(relations, list):
        for item in relations:
            if (
                isinstance(item, dict)
                and isinstance(item.get("relation_type"), str)
                and item["relation_type"] in IDENTITY_RELATIONS
            ):
                doi = _doi(item.get("doi"))
                if doi:
                    result.append({"type": item["relation_type"], "doi": doi})
    return sorted(result, key=lambda item: (item["type"], item["doi"]))


def _record(row: Any) -> dict[str, Any]:
    raw = json.loads(row["raw_metadata"])
    metadata = raw.get("metadata", {})
    authors = raw.get("authors", [])
    provider_value = metadata.get("provider")
    provider = (
        provider_value if isinstance(provider_value, str) and provider_value.strip() else None
    )
    if provider in {*PROVIDERS, "arxiv"}:
        namespace = ["provider", provider]
    elif provider is not None:
        namespace = ["source_and_unrecognized_provider", row["source_id"], provider]
    elif provider_value is None:
        namespace = ["source", row["source_id"]]
    else:
        # Malformed namespace metadata cannot establish cross-run identifier identity.
        namespace = ["invalid_provider_metadata", row["id"]]
    arxiv = []
    external = metadata.get("externalIds", {})
    for value in (
        metadata.get("arxiv_id"),
        external.get("ArXiv") if isinstance(external, dict) else None,
        raw.get("url"),
        _doi(raw.get("doi")),
    ):
        identity = _arxiv(value)
        if identity and identity not in arxiv:
            arxiv.append(identity)
    return {
        "record_id": row["id"],
        "report_id": row["report_id"],
        "run_id": row["search_run_id"],
        "source_id": row["source_id"],
        "source_record_id": row["source_record_id"],
        "provider": provider,
        "identifier_namespace": namespace,
        "title": row["title"],
        "normalized_title": normalize_title(row["title"]),
        "year": row["year"],
        "doi": _doi(raw.get("doi")),
        "authors": authors,
        "arxiv_identifiers": [{"id": identity, "version": version} for identity, version in arxiv],
        "doi_relations": _relations(metadata),
    }


def _evidence(left: dict, right: dict, threshold: float) -> dict[str, Any] | None:
    reasons: list[str] = []
    observations: list[dict[str, Any]] = []
    same_namespace = left["identifier_namespace"] == right["identifier_namespace"]
    if (
        same_namespace
        and left["run_id"] != right["run_id"]
        and left["source_record_id"] == right["source_record_id"]
    ):
        reasons.append("same_source_identifier_across_runs")
        observations.append({"namespace": left["identifier_namespace"]})
    for origin, target in ((left, right), (right, left)):
        for relation in origin["doi_relations"]:
            if target["doi"] and relation["doi"] == target["doi"]:
                reasons.append("observed_doi_relationship")
                observations.append({"record_id": origin["record_id"], **relation})
    for first in left["arxiv_identifiers"]:
        for second in right["arxiv_identifiers"]:
            if first["id"] == second["id"]:
                reasons.append("observed_arxiv_family")
                observations.append(
                    {"arxiv_id": first["id"], "versions": [first["version"], second["version"]]}
                )
    first_title, second_title = left["normalized_title"], right["normalized_title"]
    first_tokens, second_tokens = set(first_title.split()), set(second_title.split())
    union = first_tokens | second_tokens
    overlap = len(first_tokens & second_tokens) / len(union) if union else 0.0
    authors_left = {normalize_title(author) for author in left["authors"]}
    authors_right = {normalize_title(author) for author in right["authors"]}
    author_overlap = sorted((authors_left & authors_right) - {""})
    year_difference = (
        abs(left["year"] - right["year"])
        if left["year"] is not None and right["year"] is not None
        else None
    )
    ratio = None
    # Avoid expensive character matching for unrelated or excessively long metadata.
    if (
        first_title
        and first_title == second_title
        and (len(first_tokens) >= 4 or (len(first_tokens) >= 2 and author_overlap))
    ):
        ratio = 1.0
        reasons.append("normalized_title_equal")
    elif (
        min(len(first_tokens), len(second_tokens)) >= 4
        and overlap >= 0.75
        and max(len(first_title), len(second_title)) <= 1000
    ):
        ratio = SequenceMatcher(None, first_title, second_title, autojunk=False).ratio()
        if ratio >= threshold and (author_overlap or year_difference in (0, 1)):
            reasons.append("similar_title_with_bibliographic_support")
    if not reasons:
        return None
    differences = []
    if left["doi"] and right["doi"] and left["doi"] != right["doi"]:
        differences.append("different_dois_may_identify_distinct_reports")
    if year_difference:
        differences.append("publication_years_differ")
    if authors_left and authors_right and not author_overlap:
        differences.append("no_exact_normalized_author_name_overlap")
    return {
        "record_ids": [left["record_id"], right["record_id"]],
        "reasons": sorted(set(reasons)),
        "title_similarity": round(ratio, 6) if ratio is not None else None,
        "title_token_jaccard": round(overlap, 6),
        "year_difference": year_difference,
        "exact_normalized_author_overlap": author_overlap,
        "differences": differences,
        "observed_relationships": observations,
    }


def candidates(
    current: ReviewService,
    limit: int = 100,
    max_comparisons: int = 50000,
    title_threshold: float = 0.9,
) -> dict[str, Any]:
    """Inspect imported records without merging, linking, decisions, events or counts."""
    if not 1 <= limit <= 10000 or not 1 <= max_comparisons <= 1000000:
        raise ValueError("Candidate limit must be 1..10000 and comparisons 1..1000000")
    if not 0.8 <= title_threshold <= 1:
        raise ValueError("Title threshold must be between 0.8 and 1")
    current.check_ready()
    with current.db.connect() as connection:
        connection.execute("BEGIN")  # One snapshot for records and duplicate provenance.
        records = [
            _record(row)
            for row in connection.execute(
                "SELECT r.*,s.source_id FROM records r JOIN search_runs s "
                "ON s.id=r.search_run_id ORDER BY r.id"
            )
        ]
        marked = current.duplicate_map(connection)
    by_report: dict[str, list[dict]] = {}
    for record in records:
        by_report.setdefault(record["report_id"], []).append(record)
    provenance = [
        {
            "report_id": identity,
            "record_ids": [record["record_id"] for record in group],
            "sources": [
                {
                    key: record[key]
                    for key in (
                        "record_id",
                        "run_id",
                        "source_id",
                        "provider",
                        "source_record_id",
                        "doi",
                    )
                }
                for record in group
            ],
            "mechanically_marked_duplicate_record_ids": [
                record["record_id"] for record in group if record["record_id"] in marked
            ],
            "note": "Existing shared report identity; not an unresolved report pair",
        }
        for identity, group in sorted(by_report.items())
        if len(group) > 1
    ]
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    comparisons = 0
    scanned = 0
    possible = len(records) * (len(records) - 1) // 2
    stopped = None
    for index, left in enumerate(records):
        if stopped:
            break
        for following in range(index + 1, len(records)):
            right = records[following]
            if comparisons >= max_comparisons:
                stopped = "comparison_limit"
                break
            comparisons += 1
            scanned += 1
            if left["report_id"] == right["report_id"]:
                continue
            evidence = _evidence(left, right, title_threshold)
            if not evidence:
                continue
            key = tuple(sorted((left["report_id"], right["report_id"])))
            if key not in pairs and len(pairs) >= limit:
                stopped = "candidate_limit"
                break
            if key not in pairs:
                pairs[key] = {
                    "report_ids": list(key),
                    "classification": "unresolved_publication_or_report_family_candidate",
                    "candidate_kinds": [],
                    "evidence": [],
                    "evidence_pairs_omitted": 0,
                    "action": "Human inspection required; no merge or study link has been made",
                }
            kinds = set(pairs[key]["candidate_kinds"])
            if (
                "observed_doi_relationship" in evidence["reasons"]
                or "observed_arxiv_family" in evidence["reasons"]
                or "different_dois_may_identify_distinct_reports" in evidence["differences"]
            ):
                kinds.add("report_family_for_inspection")
            else:
                kinds.add("bibliographic_identity_for_inspection")
            pairs[key]["candidate_kinds"] = sorted(kinds)
            if len(pairs[key]["evidence"]) < 10:
                pairs[key]["evidence"].append(evidence)
            else:
                pairs[key]["evidence_pairs_omitted"] += 1
    involved = {
        record_id
        for candidate in pairs.values()
        for evidence in candidate["evidence"]
        for record_id in evidence["record_ids"]
    }
    return {
        "schema_version": 1,
        "protocol_revision": current.config.revision,
        "mode": "read_only_candidates",
        "entity_meaning": "Records are source hits; reports are publications; studies require human-confirmed links",
        "parameters": {
            "limit": limit,
            "max_comparisons": max_comparisons,
            "title_threshold": title_threshold,
        },
        "coverage": {
            "records_loaded": len(records),
            "existing_reports": len(by_report),
            "possible_record_pairs": possible,
            "record_pairs_examined": scanned,
            "truncated": stopped is not None or scanned < possible,
            "stop_reason": stopped or "all_imported_record_pairs_examined",
            "scope": "Imported metadata only; not a completeness claim about literature or study families",
        },
        "candidates": [pairs[key] for key in sorted(pairs)],
        "same_report_provenance": provenance,
        "record_evidence": [record for record in records if record["record_id"] in involved],
        "limitations": [
            "Similarity is a bibliographic hint, not a probability or a scientific decision",
            "Different DOIs, publication years and authors remain visible and may indicate distinct reports",
            "Missing metadata can hide matches; fuzzy title matching requires token overlap and author or year support",
            "Fuzzy character matching skips titles longer than 1000 normalized characters",
            "No duplicates are marked, records merged, studies linked, decisions recorded or review counts changed",
        ],
    }


def export_candidates(current: ReviewService, path: Path, **options: Any) -> dict[str, Any]:
    """Write a fresh JSON or Markdown candidate artifact inside data/candidates."""
    path = path.expanduser().resolve()
    folder = (current.config.root / "data/candidates").resolve()
    if not path.is_relative_to(folder) or path.suffix.lower() not in {".json", ".md"}:
        raise ValueError("Use a fresh .json or .md path inside data/candidates")
    result = candidates(current, **options)
    content = canonical_json(result) + "\n"
    if path.suffix.lower() == ".md":
        # Escaping the full structured evidence keeps imported text from becoming Markdown instructions.
        escaped = html.escape(json.dumps(result, ensure_ascii=False, indent=2))
        content = (
            "# Unresolved duplicate and report-family candidates\n\nRead-only metadata hints. Human inspection required.\n\n<pre>"
            + escaped
            + "</pre>\n"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)
    return {
        "path": str(path),
        "candidate_pairs": len(result["candidates"]),
        "coverage": result["coverage"],
    }
