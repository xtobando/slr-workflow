"""Synthetic bibliographic candidate tests never alter a real review."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from slr_workbench.duplicate_candidates import candidates, export_candidates
from slr_workbench.service import ReviewService


def add(
    review: ReviewService, tmp_path: Path, run: str, rows: list[dict], source: str = "demo-database"
) -> None:
    path = tmp_path / f"{run}.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    review.import_records(
        path, run, source, "Synthetic candidate fixture", "2026-10-05T00:00:00+00:00"
    )


def record(identity: str, title: str, **extra: object) -> dict:
    return {"source_record_id": identity, "title": title, **extra}


def test_title_candidates_are_read_only_deterministic_and_preserve_conflicts(review, tmp_path):
    add(
        review,
        tmp_path,
        "candidate-a",
        [
            record(
                "a",
                "Evaluation of a novel surface electrode array",
                year=2020,
                authors=["A. Author"],
                doi="10.1000/one",
            )
        ],
    )
    add(
        review,
        tmp_path,
        "candidate-b",
        [
            record(
                "b",
                "Evaluation of a novel surface-electrode array",
                year=2022,
                authors=["B. Author"],
                doi="10.1000/two",
            )
        ],
    )
    with review.db.connect() as connection:
        before = list(connection.iterdump())
    result = candidates(review)
    assert result == candidates(review)
    found = [
        pair
        for pair in result["candidates"]
        if "normalized_title_equal" in pair["evidence"][0]["reasons"]
    ]
    assert len(found) == 1
    evidence = found[0]["evidence"][0]
    assert evidence["year_difference"] == 2
    assert "different_dois_may_identify_distinct_reports" in evidence["differences"]
    assert "no_exact_normalized_author_name_overlap" in evidence["differences"]
    assert {r["doi"] for r in result["record_evidence"]} >= {"10.1000/one", "10.1000/two"}
    with review.db.connect() as connection:
        assert before == list(connection.iterdump())


def test_identifier_overlap_requires_observed_namespace(review, tmp_path):
    # Reused IDs from different sources or providers must never create a match.
    add(
        review,
        tmp_path,
        "id-a",
        [record("shared", "Entirely unrelated topic one", metadata={"provider": "crossref"})],
    )
    add(
        review,
        tmp_path,
        "id-b",
        [record("shared", "Completely separate area two", metadata={"provider": "openalex"})],
    )
    add(
        review,
        tmp_path,
        "id-c",
        [record("shared", "Unconnected work with unique title")],
        source="citation-search",
    )
    assert not candidates(review)["candidates"]
    add(
        review,
        tmp_path,
        "id-d",
        [record("shared", "A changed catalogue item name", metadata={"provider": "crossref"})],
    )
    found = candidates(review)["candidates"]
    assert len(found) == 1
    assert found[0]["evidence"][0]["reasons"] == ["same_source_identifier_across_runs"]


def test_doi_free_fuzzy_title_requires_support_and_rejects_generic_titles(review, tmp_path):
    base = "Evaluation of wearable surface electrode arrays for upper limb movement recognition"
    variant = "Evaluation of wearable surface electrode arrays for upper limb movements recognition"
    add(review, tmp_path, "fuzzy-a", [record("a", base, year=2020), record("intro-a", "Editorial")])
    add(
        review,
        tmp_path,
        "fuzzy-b",
        [record("b", variant, year=2021), record("intro-b", "Editorial")],
    )
    found = candidates(review)["candidates"]
    assert len(found) == 1
    assert "similar_title_with_bibliographic_support" in found[0]["evidence"][0]["reasons"]
    assert found[0]["evidence"][0]["title_similarity"] >= 0.9
    add(review, tmp_path, "fuzzy-c", [record("c", variant, year=1990)])
    drifted = candidates(review)
    run_by_record = {r["record_id"]: r["run_id"] for r in drifted["record_evidence"]}
    assert not any(
        {run_by_record[r] for r in evidence["record_ids"]} == {"fuzzy-a", "fuzzy-c"}
        for pair in drifted["candidates"]
        for evidence in pair["evidence"]
    )
    # Completely unrelated titles must not match on a common year alone.
    add(
        review,
        tmp_path,
        "fuzzy-d",
        [record("d", "An unrelated simulation of stellar collapse", year=2020)],
    )
    assert len(candidates(review)["candidates"]) == 2  # b/c have exactly equal observed titles.


def test_existing_shared_reports_remain_separate_from_unresolved_pairs(review, tmp_path):
    add(
        review,
        tmp_path,
        "doi-a",
        [
            record(
                "one", "Observed publication with shared digital identifier", doi="10.1000/shared"
            )
        ],
    )
    add(
        review,
        tmp_path,
        "doi-b",
        [
            record(
                "two",
                "Observed publication with shared digital identifier",
                doi="https://doi.org/10.1000/SHARED",
            )
        ],
    )
    review.deduplicate()
    result = candidates(review)
    assert not result["candidates"]
    provenance = [
        p
        for p in result["same_report_provenance"]
        if len(p["mechanically_marked_duplicate_record_ids"]) == 1
    ]
    assert len(provenance) >= 1
    assert not any("10.1000/shared" == record["doi"] for record in result["record_evidence"])


def test_observed_preprint_relationship_and_arxiv_versions_are_only_hints(review, tmp_path):
    add(
        review,
        tmp_path,
        "relation-a",
        [
            record(
                "preprint",
                "Earlier working paper title",
                doi="10.1000/pre",
                metadata={
                    "relation": {"is-preprint-of": [{"id-type": "doi", "id": "10.1000/final"}]}
                },
            )
        ],
    )
    add(
        review,
        tmp_path,
        "relation-b",
        [record("journal", "Different published article title", doi="10.1000/final")],
    )
    add(
        review,
        tmp_path,
        "version-a",
        [record("arxiv-a", "Initial technical report", url="https://arxiv.org/abs/2401.12345v1")],
    )
    add(
        review,
        tmp_path,
        "version-b",
        [record("arxiv-b", "Revised manuscript title", metadata={"arxiv_id": "2401.12345v2"})],
    )
    result = candidates(review)
    reasons = {
        reason for pair in result["candidates"] for e in pair["evidence"] for reason in e["reasons"]
    }
    assert reasons == {"observed_doi_relationship", "observed_arxiv_family"}
    assert all(pair["classification"].startswith("unresolved") for pair in result["candidates"])
    with review.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM studies").fetchone()[0] == 0


def test_bounded_work_and_candidate_limit_are_explicit(review, tmp_path):
    add(
        review,
        tmp_path,
        "cap-a",
        [record(str(i), "Shared title repeated for conservative inspection") for i in range(6)],
    )
    limited = candidates(review, max_comparisons=1)
    assert limited["coverage"]["record_pairs_examined"] == 1
    assert limited["coverage"]["truncated"]
    assert limited["coverage"]["stop_reason"] == "comparison_limit"
    limited = candidates(review, limit=1)
    assert len(limited["candidates"]) == 1
    assert limited["coverage"]["truncated"]
    assert limited["coverage"]["stop_reason"] == "candidate_limit"
    with pytest.raises(ValueError):
        candidates(review, limit=0)


def test_fresh_artifact_export_only_under_candidates_and_escaped_markdown(review, tmp_path):
    add(review, tmp_path, "export-a", [record("a", "Shared candidate title with <script> text")])
    add(review, tmp_path, "export-b", [record("b", "Shared candidate title with <script> text")])
    path = tmp_path / "data/candidates/inspection.md"
    exported = export_candidates(review, path)
    assert exported["candidate_pairs"] == 1
    assert "&lt;script&gt;" in path.read_text()
    assert "<script>" not in path.read_text()
    with pytest.raises(FileExistsError):
        export_candidates(review, path)
    with pytest.raises(ValueError):
        export_candidates(review, tmp_path / "outside.json")
    json_path = tmp_path / "data/candidates/inspection.json"
    export_candidates(review, json_path)
    assert json.loads(json_path.read_text())["mode"] == "read_only_candidates"


def test_unknown_or_malformed_provider_does_not_join_unrelated_namespaces(review, tmp_path):
    add(
        review,
        tmp_path,
        "unknown-a",
        [record("reuse", "First unique metadata entry", metadata={"provider": "unverified"})],
    )
    add(
        review,
        tmp_path,
        "unknown-b",
        [
            record(
                "reuse", "Second wholly separate publication", metadata={"provider": "unverified"}
            )
        ],
        source="citation-search",
    )
    add(
        review,
        tmp_path,
        "invalid-a",
        [record("bad", "Third isolated reference work", metadata={"provider": []})],
    )
    add(
        review,
        tmp_path,
        "invalid-b",
        [record("bad", "Fourth different manuscript item", metadata={"provider": []})],
    )
    assert not candidates(review)["candidates"]
    add(review, tmp_path, "missing-a", [record("manual", "Fifth bibliography source title")])
    add(review, tmp_path, "missing-b", [record("manual", "Sixth revised manual record")])
    assert len(candidates(review)["candidates"]) == 1


def test_citation_relation_and_malformed_relationship_are_not_identity_evidence(review, tmp_path):
    add(
        review,
        tmp_path,
        "citation-a",
        [
            record(
                "citing",
                "A distinct citing report",
                doi="10.1000/citing",
                metadata={
                    "relations": [
                        {"relation_type": "references", "doi": "10.1000/cited"},
                        {"relation_type": [], "doi": "10.1000/cited"},
                    ]
                },
            )
        ],
    )
    add(
        review,
        tmp_path,
        "citation-b",
        [record("cited", "An entirely different cited publication", doi="10.1000/cited")],
    )
    assert not candidates(review)["candidates"]


def test_candidate_omitted_on_last_comparison_is_still_truncated(review, tmp_path):
    import shutil

    from slr_workbench.config import load_configuration

    root = tmp_path / "minimal"
    root.mkdir()
    for name in ("protocol.yaml", "workflow.yaml"):
        shutil.copyfile(review.config.root / name, root / name)
    isolated = ReviewService(load_configuration(root))
    isolated.initialize()
    isolated.approve_protocol("thomas", "Approve isolated synthetic boundary test")
    add(
        isolated,
        root,
        "last-pair",
        [record(str(i), "Identical title for three synthetic reports") for i in range(3)],
    )
    result = candidates(isolated, limit=2)
    assert result["coverage"]["record_pairs_examined"] == 3
    assert result["coverage"]["possible_record_pairs"] == 3
    assert result["coverage"]["truncated"]
    assert result["coverage"]["stop_reason"] == "candidate_limit"
