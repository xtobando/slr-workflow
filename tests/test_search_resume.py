"""Resumable searches use synthetic data and never read account credentials."""

import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from slr_workbench.search import http
from slr_workbench.search import service as searches
from slr_workbench.search.adapters import normalize, page, request
from slr_workbench.search.catalog import PROVIDERS
from slr_workbench.search.service import digest, save, search, verify_bundle


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Tests must not read user credentials")

    monkeypatch.setattr(searches, "load_credentials", forbidden)


def oa_page(ids, total=3, following="next"):
    return {
        "results": [{"id": f"https://openalex.org/W{i}", "title": f"Fixture {i}"} for i in ids],
        "meta": {"count": total, "next_cursor": following},
    }


def synthetic_keys(monkeypatch):
    monkeypatch.setattr(
        searches, "load_credentials", lambda *a: {"api_key": "synthetic-test-key-not-real"}
    )


def test_plan_no_requests_credentials_or_files(tmp_path):
    result = search(
        tmp_path,
        "openalex",
        "software",
        dry_run=True,
        allow_credentials=True,
        fetch=lambda *a: pytest.fail("No network in plan"),
    )
    assert result["status"] == "planned"
    assert result["max_requests"] == 100
    assert not (tmp_path / "data").exists()


def test_public_search_ignores_keys_without_explicit_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("SLR_OPENALEX_API_KEY", "must-not-use-this-key")

    def fetch(endpoint, params, headers):
        assert not headers and params["cursor"] == "*"
        return oa_page([1], 3)

    result = search(tmp_path, "openalex", "software", 200, fetch=fetch)
    assert result["stop_reason"] == "api_key_required_for_paging"
    assert result["request_count"] == 1


def test_openalex_resume_uses_saved_cursor_and_preserves_original_snapshot(tmp_path, monkeypatch):
    first = search(tmp_path, "openalex", "software", 200, "pilot", fetch=lambda *a: oa_page([1], 3))
    directory = Path(first["manifest"]).parent
    before = {p.name: p.read_bytes() for p in directory.glob("page-*.json")}
    old_manifest = Path(first["manifest"]).read_bytes()
    synthetic_keys(monkeypatch)
    calls = []

    def fetch(endpoint, params, headers):
        calls.append(params["cursor"])
        assert headers["Authorization"] == "Bearer synthetic-test-key-not-real"
        return oa_page([2, 3], 3, None)

    final = search(
        tmp_path, "openalex", "software", 200, "pilot", fetch, resume=True, allow_credentials=True
    )
    assert calls == ["next"]
    assert final["records_count"] == 3 and not final["truncated"]
    assert final["request_count"] == 2
    assert Path(first["manifest"]).read_bytes() == old_manifest
    for name, payload in before.items():
        assert (directory / name).read_bytes() == payload
    manifest, records_file = verify_bundle(Path(final["manifest"]))
    assert manifest["schema_version"] == 2
    assert records_file.name.startswith("records-")
    # The original pilot snapshot is still independently importable.
    pilot, pilot_records = verify_bundle(Path(first["manifest"]))
    assert pilot["truncated"] and len(json.loads(pilot_records.read_text())) == 1


def test_failed_request_resume_does_not_refetch_successful_page(tmp_path, monkeypatch):
    synthetic_keys(monkeypatch)
    calls = []

    def fetch(endpoint, params, headers):
        calls.append(params["cursor"])
        if params["cursor"] == "next":
            raise http.APIError("Bibliographic API could not be reached")
        return oa_page([1], 2)

    with pytest.raises(ValueError, match="Nothing was imported"):
        search(tmp_path, "openalex", "software", 200, "run", fetch, allow_credentials=True)
    before = (tmp_path / "data/searches/run/page-0001.json").read_bytes()
    resumed_calls = []

    def resumed(endpoint, params, headers):
        resumed_calls.append(params["cursor"])
        return oa_page([2], 2, None)

    final = search(
        tmp_path, "openalex", "software", 200, "run", resumed, resume=True, allow_credentials=True
    )
    assert calls == ["*", "next"] and resumed_calls == ["next"]
    assert final["request_count"] == 3
    assert (tmp_path / "data/searches/run/page-0001.json").read_bytes() == before
    assert final["status"] == "completed" and not final["truncated"]


def test_resume_cap_extension_consumes_already_archived_overflow_offline(tmp_path):
    def fetch(*args):
        return {
            "data": [{"paperId": str(i), "title": f"Fixture {i}"} for i in range(3)],
            "total": 3,
        }

    pilot = search(tmp_path, "semantic-scholar", "software", 1, "run", fetch)
    assert pilot["fetched_count"] == 3 and pilot["records_count"] == 1
    final = search(
        tmp_path,
        "semantic-scholar",
        "software",
        3,
        "run",
        lambda *a: pytest.fail("Archived overflow must not be refetched"),
        resume=True,
    )
    assert final["records_count"] == 3 and not final["truncated"]
    assert len(final["pages"]) == 1 and final["request_count"] == 1


@pytest.mark.parametrize("change", ["provider", "query", "lower_cap"])
def test_resume_cannot_change_query_provider_or_reduce_cap(tmp_path, change):
    search(tmp_path, "openalex", "software", 200, "run", lambda *a: oa_page([1], 2))
    with pytest.raises(ValueError, match="new stable run-id|cannot lower"):
        search(
            tmp_path,
            "crossref" if change == "provider" else "openalex",
            "changed" if change == "query" else "software",
            100 if change == "lower_cap" else 200,
            "run",
            resume=True,
        )


def test_legacy_bundle_import_integrity_still_supported_and_never_resumed(tmp_path):
    directory = tmp_path / "data/searches/legacy"
    directory.mkdir(parents=True)
    records_hash = save(directory / "records.json", [])
    response_hash = save(directory / "page-0001.json", {"result": {"hits": {"@total": "0"}}})
    save(
        directory / "manifest.json",
        {
            "schema_version": 1,
            "status": "completed",
            "provider": "dblp",
            "endpoint": PROVIDERS["dblp"].endpoint,
            "records_sha256": records_hash,
            "records_count": 0,
            "truncated": False,
            "pages": [{"file": "page-0001.json", "sha256": response_hash}],
        },
    )
    assert verify_bundle(directory / "manifest.json")[0]["schema_version"] == 1
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(ValueError, match="legacy pilots"):
        search(tmp_path, "dblp", "software", run_id="legacy", resume=True)
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_resumed_search_rejects_tampered_archive_without_rewriting_checkpoint(tmp_path):
    result = search(tmp_path, "openalex", "software", 200, "run", lambda *a: oa_page([1], 2))
    directory = Path(result["manifest"]).parent
    checkpoint = (directory / "checkpoint.json").read_bytes()
    (directory / "page-0001.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        search(tmp_path, "openalex", "software", 200, "run", resume=True)
    assert (directory / "checkpoint.json").read_bytes() == checkpoint


def test_orphan_successful_page_is_replayed_after_checkpoint_crash(tmp_path, monkeypatch):
    synthetic_keys(monkeypatch)
    first = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        lambda *a: oa_page([1], 2),
        max_pages=1,
        allow_credentials=True,
    )
    directory = Path(first["manifest"]).parent
    # Simulate a fully persisted response with no following checkpoint write.
    response = oa_page([2], 2, None)
    save(
        directory / "request-000002.json",
        {
            "parameters": {"search": "software", "per_page": 100, "cursor": "next"},
            "requested_cursor": "next",
            "endpoint": PROVIDERS["openalex"].endpoint,
            "requested_at": "2026-01-01T00:00:00+00:00",
            "access_mode": "configured_credentials",
        },
    )
    save(
        directory / "page-0002.json",
        {
            "request_receipts": ["request-000002.json"],
            "parameters": {"search": "software", "per_page": 100, "cursor": "next"},
            "requested_cursor": "next",
            "requested_at": "2026-01-01T00:00:00+00:00",
            "received_at": "2026-01-01T00:00:01+00:00",
            "response": response,
            "response_sha256": digest(response),
            "access_mode": "configured_credentials",
        },
    )
    result = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        lambda *a: pytest.fail("Do not refetch saved success"),
        resume=True,
        allow_credentials=True,
    )
    assert result["records_count"] == 2 and not result["truncated"]


@pytest.mark.parametrize("failure", ["cursor", "page", "ids"])
def test_duplicate_cursor_page_or_source_id_is_explicit_failure(tmp_path, monkeypatch, failure):
    synthetic_keys(monkeypatch)
    calls = []

    def fetch(endpoint, params, headers):
        calls.append(1)
        if failure == "cursor":
            return oa_page([len(calls)], 10, "*")
        if failure == "page" or len(calls) == 1:
            return oa_page([1], 10, "next")
        return oa_page([1], 10, "another")

    with pytest.raises(ValueError, match="Nothing was imported"):
        search(tmp_path, "openalex", "software", 200, "run", fetch, allow_credentials=True)
    manifest = json.loads((tmp_path / "data/searches/run/manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert (
        manifest["stop_reason"]
        == {"cursor": "repeated_cursor", "page": "repeated_page", "ids": "duplicate_source_id"}[
            failure
        ]
    )
    assert len(calls) == (1 if failure == "cursor" else 2)
    with pytest.raises(ValueError, match="Only completed"):
        verify_bundle(tmp_path / "data/searches/run/manifest.json")


def test_request_and_page_caps_are_explicit_and_resumable(tmp_path, monkeypatch):
    synthetic_keys(monkeypatch)
    first = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        lambda *a: oa_page([1], 3),
        max_pages=1,
        allow_credentials=True,
    )
    assert first["stop_reason"] == "page_limit"
    second = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        resume=True,
        max_requests=1,
        allow_credentials=True,
        fetch=lambda *a: pytest.fail("Request budget already consumed"),
    )
    assert second["stop_reason"] == "request_limit" and second["request_count"] == 1
    final = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        lambda *a: oa_page([2, 3], 3, None),
        resume=True,
        max_requests=2,
        allow_credentials=True,
    )
    assert not final["truncated"] and final["request_count"] == 2


def test_physical_retry_attempts_obey_request_budget(tmp_path, monkeypatch):
    calls = []

    class Opener:
        def open(self, *args, **kwargs):
            calls.append(1)
            raise HTTPError("https://example.invalid/", 429, "", {"Retry-After": "0"}, None)

    monkeypatch.setattr(http, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(http.time, "sleep", lambda *a: None)
    with pytest.raises(ValueError, match="request budget"):
        search(tmp_path, "crossref", "software", run_id="budget", max_requests=2)
    directory = tmp_path / "data/searches/budget"
    assert len(calls) == 2
    assert len(list(directory.glob("request-*.json"))) == 2
    assert json.loads((directory / "manifest.json").read_text())["stop_reason"] == "request_limit"


def atom(ids=("2401.00001v1",), total=1, start=0):
    entries = "".join(
        f"""<entry><id>http://arxiv.org/abs/{identity}</id>
      <title>Synthetic\n paper</title><summary>Synthetic abstract</summary>
      <published>2024-01-01T00:00:00Z</published><updated>2024-01-02T00:00:00Z</updated>
      <author><name>Test Author</name></author><category term="cs.SE"/>
      <arxiv:doi>10.0000/synthetic</arxiv:doi></entry>"""
        for identity in ids
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:arxiv="http://arxiv.org/schemas/atom">
    <opensearch:totalResults>{total}</opensearch:totalResults><opensearch:startIndex>{start}</opensearch:startIndex>{entries}</feed>""".encode()


def test_arxiv_atom_normalization_and_native_parameters():
    parsed = http.parse_atom(atom())
    assert parsed["atom_xml"].startswith("<?xml")
    rows, total, cursor = page("arxiv", parsed, None, 100)
    assert total == cursor == 1
    record = normalize("arxiv", rows[0])
    assert record["title"] == "Synthetic paper"
    assert record["abstract"] == "Synthetic abstract" and record["year"] == 2024
    assert record["metadata"]["arxiv_base_id"] == "2401.00001"
    params, headers = request("arxiv", "all:software AND cat:cs.SE", 100, 100, {})
    assert params["start"] == 100 and params["sortBy"] == "submittedDate" and not headers


def test_arxiv_offset_paging_and_resume(tmp_path):
    calls = []

    def fetch(endpoint, params, headers):
        start = params["start"]
        calls.append(start)
        return http.parse_atom(atom((f"2401.0000{start + 1}v1",), 2, start))

    first = search(tmp_path, "arxiv", "cat:cs.SE", 10, "arxiv-run", fetch, max_pages=1)
    assert first["stop_reason"] == "page_limit"
    final = search(tmp_path, "arxiv", "cat:cs.SE", 10, "arxiv-run", fetch, resume=True)
    assert calls == [0, 1] and final["records_count"] == 2 and not final["truncated"]


def test_arxiv_rejects_wrong_start_offset(tmp_path):
    with pytest.raises(ValueError, match="Nothing was imported"):
        search(tmp_path, "arxiv", "cat:cs.SE", fetch=lambda *a: http.parse_atom(atom(start=10)))


@pytest.mark.parametrize(
    "payload",
    [
        b"<html>blocked</html>",
        b'<!DOCTYPE feed [<!ENTITY x "boom">]><feed/>',
        b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors</id></entry></feed>',
    ],
)
def test_arxiv_rejects_xml_entities_html_and_error_feed(payload):
    with pytest.raises(http.APIError):
        http.parse_atom(payload)


def test_arxiv_transport_paces_physical_requests_and_parses_atom(monkeypatch):
    clock = [0.0]
    starts = []
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    class Response:
        status = 200

        def __init__(self):
            self.headers = {"Content-Type": "application/atom+xml"}

        def __enter__(self):
            starts.append(clock[0])
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return atom()

    class Opener:
        def open(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(http, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(http.time, "sleep", sleep)
    monkeypatch.setattr(http.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http, "_LAST_REQUEST", {})
    for _ in range(2):
        result = http.get_json(PROVIDERS["arxiv"].endpoint, {}, {})
        assert result["entries"]
    assert starts == [0, 3] and sleeps == [3]


def test_bundle_rejects_mutated_run_definition(tmp_path):
    result = search(tmp_path, "openalex", "software", 200, "run", lambda *a: oa_page([1], 1))
    directory = Path(result["manifest"]).parent
    original = (directory / "run.json").read_bytes()
    (directory / "run.json").write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(Path(result["manifest"]))
    assert hashlib.sha256(original).hexdigest() == result["run_sha256"]


def test_crossref_legacy_constant_cursor_is_allowed_only_with_page_progress(tmp_path):
    calls = []

    def fetch(endpoint, params, headers):
        calls.append(params["cursor"])
        number = len(calls)
        return {
            "message": {
                "items": [{"DOI": f"10.0000/fixture{number}", "title": [f"Fixture {number}"]}],
                "total-results": 3,
                "next-cursor": "legacy-stateful",
            }
        }

    result = search(tmp_path, "crossref", "software", 10, fetch=fetch)
    assert calls == ["*", "legacy-stateful", "legacy-stateful"]
    assert result["records_count"] == 3 and not result["truncated"]
    assert result["warnings"][0]["code"] == "repeated_crossref_cursor"


def test_request_receipt_deletion_cannot_reset_resume_budget(tmp_path):
    result = search(tmp_path, "openalex", "software", 200, "run", lambda *a: oa_page([1], 2))
    directory = Path(result["manifest"]).parent
    (directory / "request-000001.json").unlink()
    with pytest.raises(ValueError, match="receipts are missing"):
        search(tmp_path, "openalex", "software", 200, "run", resume=True)


def test_request_receipt_tampering_rejected_for_import_and_resume(tmp_path):
    result = search(tmp_path, "openalex", "software", 200, "run", lambda *a: oa_page([1], 2))
    directory = Path(result["manifest"]).parent
    (directory / "request-000001.json").write_text("{}")
    with pytest.raises(ValueError, match="receipt checksum"):
        search(tmp_path, "openalex", "software", 200, "run", resume=True)
    with pytest.raises(ValueError, match="receipt checksum"):
        verify_bundle(Path(result["manifest"]))


def test_snapshot_publication_crash_leaves_running_checkpoint_and_recovers_offline(
    tmp_path, monkeypatch
):
    synthetic_keys(monkeypatch)
    first = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        lambda *a: oa_page([1], 2),
        max_pages=1,
        allow_credentials=True,
    )
    directory = Path(first["manifest"]).parent
    original_save = searches.save

    def fail_latest_pointer(path, value, **kwargs):
        if path.name == "manifest.json":
            raise OSError("Synthetic interrupted publication")
        return original_save(path, value, **kwargs)

    monkeypatch.setattr(searches, "save", fail_latest_pointer)
    with pytest.raises(OSError, match="interrupted publication"):
        search(
            tmp_path,
            "openalex",
            "software",
            200,
            "run",
            lambda *a: oa_page([2], 2, None),
            resume=True,
            allow_credentials=True,
        )
    assert json.loads((directory / "checkpoint.json").read_text())["status"] == "running"
    assert json.loads((directory / "manifest.json").read_text())["records_count"] == 1
    monkeypatch.setattr(searches, "save", original_save)
    final = search(
        tmp_path,
        "openalex",
        "software",
        200,
        "run",
        lambda *a: pytest.fail("Successful pages survive publication failure"),
        resume=True,
        allow_credentials=True,
    )
    assert final["records_count"] == 2 and not final["truncated"]
    assert json.loads((directory / "checkpoint.json").read_text())["status"] == "completed"
    assert verify_bundle(Path(first["manifest"]))[0]["records_count"] == 1
