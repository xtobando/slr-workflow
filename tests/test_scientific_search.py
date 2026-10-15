"""Synthetic API fixtures; no network, user credentials or real review decisions."""

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
import yaml

from slr_workbench.config import load_configuration
from slr_workbench.search import http
from slr_workbench.search.adapters import normalize, page, request
from slr_workbench.search.catalog import PROVIDERS
from slr_workbench.search.credentials import credential_path, load_credentials, read_store
from slr_workbench.search.service import import_search, search
from slr_workbench.service import ReviewService


@pytest.fixture(autouse=True)
def isolated_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("SLR_CREDENTIALS_FILE", str(tmp_path / "external" / "credentials.json"))
    for provider in PROVIDERS.values():
        for variable in provider.credentials.values():
            monkeypatch.delenv(variable, raising=False)


def dblp(identifier="journals/test/1"):
    return {
        "info": {
            "key": identifier,
            "title": "Synthetic software testing study",
            "year": "2024",
            "authors": {"author": {"text": "Test Author"}},
        }
    }


def dblp_page(rows, total):
    return {"result": {"hits": {"@total": str(total), "hit": rows}}}


@pytest.mark.parametrize(
    "provider,raw,expected",
    [
        ("dblp", dblp(), "journals/test/1"),
        (
            "crossref",
            {
                "DOI": "10.0000/test",
                "title": ["Fixture"],
                "abstract": "<jats:p>Text</jats:p>",
                "published": {"date-parts": [[2024]]},
            },
            "10.0000/test",
        ),
        (
            "openalex",
            {
                "id": "https://openalex.org/W0",
                "title": "Fixture",
                "abstract_inverted_index": {"second": [1], "First": [0]},
            },
            "https://openalex.org/W0",
        ),
        (
            "semantic-scholar",
            {"paperId": "test-paper", "title": "Fixture", "externalIds": {"DOI": "10.0000/test"}},
            "test-paper",
        ),
        (
            "ieee",
            {
                "article_number": 123,
                "title": "Fixture",
                "authors": {"authors": [{"full_name": "Test Author"}]},
            },
            "123",
        ),
        (
            "scopus",
            {
                "eid": "2-s2.0-test",
                "dc:title": "Fixture",
                "dc:creator": "Test Author",
                "prism:coverDate": "2024-01-01",
            },
            "2-s2.0-test",
        ),
        (
            "wos",
            {
                "uid": "WOS:test",
                "title": "Fixture",
                "source": {"publishYear": 2024},
                "names": {"authors": [{"displayName": "Test Author"}]},
            },
            "WOS:test",
        ),
    ],
)
def test_normalization(provider, raw, expected):
    result = normalize(provider, raw)
    assert result["source_record_id"] == expected
    assert result["metadata"]["provider"] == provider
    if provider == "openalex":
        assert result["abstract"] == "First second"
    elif provider == "crossref":
        assert result["abstract"] == "Text"
    else:
        assert result["abstract"] == ""
        assert "abstract" in result["metadata"]["missing_fields"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_request_auth(provider):
    params, headers = request(
        provider,
        "software testing",
        None,
        25,
        {"api_key": "fake-private-key", "insttoken": "fake-institution-token"},
    )
    serialized = json.dumps([params, headers])
    if PROVIDERS[provider].credentials:
        assert "fake-private-key" in serialized
    assert "fake-private-key" not in json.dumps(
        http.redact([params, headers], ("fake-private-key", "fake-institution-token"))
    )


@pytest.mark.parametrize(
    "provider,data,expected_cursor",
    [
        ("dblp", dblp_page([dblp()], 20), 1),
        (
            "crossref",
            {"message": {"items": [{}], "total-results": 20, "next-cursor": "next"}},
            "next",
        ),
        ("openalex", {"results": [{}], "meta": {"count": 20, "next_cursor": "next"}}, "next"),
        ("semantic-scholar", {"data": [{}], "total": 20, "token": "next"}, "next"),
        ("ieee", {"articles": [{}], "total_records": 20}, 2),
        ("scopus", {"search-results": {"entry": [{}], "opensearch:totalResults": "20"}}, 1),
        ("wos", {"hits": [{}], "metadata": {"total": 20}}, 2),
    ],
)
def test_page_cursors(provider, data, expected_cursor):
    rows, total, cursor = page(provider, data, None, 25)
    assert len(rows) == 1 and total == 20 and cursor == expected_cursor


def test_paging_archive_and_exclusive_run(tmp_path):
    calls = []

    def fetch(endpoint, params, headers):
        calls.append(params["f"])
        return dblp_page([dblp(str(params["f"]))], 2)

    root = tmp_path / "project"
    result = search(root, "dblp", "testing", 10, "run", fetch)
    assert calls == [0, 1]
    assert result["records_count"] == 2 and not result["truncated"]
    assert len(result["pages"]) == 2
    with pytest.raises(FileExistsError):
        search(root, "dblp", "testing", 10, "run", fetch)


def test_bulk_trim_is_truncated_even_without_next_token(tmp_path):
    result = search(
        tmp_path / "project",
        "semantic-scholar",
        "testing",
        1,
        fetch=lambda *a: {
            "data": [{"paperId": str(i), "title": "Fixture"} for i in range(3)],
            "total": 3,
        },
    )
    assert result["records_count"] == 1 and result["truncated"]
    assert result["stop_reason"] == "max_results"


def test_openalex_anonymous_stops_after_first_page(tmp_path):
    result = search(
        tmp_path / "project",
        "openalex",
        "testing",
        200,
        fetch=lambda *a: {
            "results": [{"id": "https://openalex.org/W0", "title": "Fixture"}],
            "meta": {"count": 300, "next_cursor": "next"},
        },
    )
    assert result["truncated"] and result["stop_reason"] == "api_key_required_for_paging"
    assert len(result["pages"]) == 1


def test_failed_page_preserves_partial_without_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("SLR_IEEE_API_KEY", "private-key-do-not-persist")
    calls = 0

    def fetch(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("private-key-do-not-persist")
        return {
            "articles": [
                {
                    "article_number": "1",
                    "title": "Fixture",
                    "abstract": "private-key-do-not-persist",
                }
            ],
            "total_records": 10,
        }

    root = tmp_path / "project"
    with pytest.raises(ValueError, match="Nothing was imported") as error:
        search(root, "ieee", "testing", 5, "failed-run", fetch)
    bundle = root / "data/searches/failed-run"
    assert "private-key-do-not-persist" not in str(error.value)
    for path in bundle.iterdir():
        assert "private-key-do-not-persist" not in path.read_text()
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["status"] == "failed" and manifest["records_count"] == 1
    with pytest.raises(ValueError, match="Only completed"):
        import_search(None, bundle / "manifest.json", "ieee")


def test_repeated_ids_fail_instead_of_silently_losing_records(tmp_path):
    with pytest.raises(ValueError, match="Search failed"):
        search(tmp_path / "project", "dblp", "testing", 5, fetch=lambda *a: dblp_page([dblp()], 10))


def test_import_integrity_and_existing_protocol_gate(review, tmp_path):
    # Map the isolated fixture only; real protocol files and decisions are untouched.
    protocol_path = review.config.root / "protocol.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["sources"][0]["limits"]["api_provider"] = "dblp"
    protocol_path.write_text(yaml.safe_dump(protocol))
    review = ReviewService(load_configuration(review.config.root))
    review.initialize()
    result = search(
        tmp_path / "project", "dblp", "testing", fetch=lambda *a: dblp_page([dblp()], 1)
    )
    manifest = Path(result["manifest"])
    with pytest.raises(ValueError, match="Approve the current protocol"):
        import_search(review, manifest, "demo-database")
    review.approve_protocol("thomas", "Approve API source mapping in isolated synthetic fixture")
    first = import_search(review, manifest, "demo-database")
    second = import_search(review, manifest, "demo-database")
    assert first and second
    records = manifest.parent / "records.json"
    records.write_text("[]")
    with pytest.raises(ValueError, match="checksum"):
        import_search(review, manifest, "demo-database")


def test_unconfigured_source_rejected(review, tmp_path):
    result = search(tmp_path / "project", "dblp", "testing", fetch=lambda *a: dblp_page([], 0))
    with pytest.raises(ValueError, match="Configure this source"):
        import_search(review, Path(result["manifest"]), "demo-database")


def test_external_credentials_and_permissions(tmp_path, monkeypatch):
    project = tmp_path / "project"
    monkeypatch.setenv("SLR_CREDENTIALS_FILE", str(project / "secrets.json"))
    with pytest.raises(ValueError, match="outside"):
        credential_path(project)
    external = tmp_path / "private.json"
    external.write_text(json.dumps({"openalex": {"api_key": "stored-test-key"}}))
    external.chmod(0o600)
    monkeypatch.setenv("SLR_CREDENTIALS_FILE", str(external))
    assert load_credentials("openalex", project)["api_key"] == "stored-test-key"
    monkeypatch.setenv("SLR_OPENALEX_API_KEY", "environment-test-key")
    assert load_credentials("openalex", project)["api_key"] == "environment-test-key"
    import os

    if os.name != "nt":
        external.chmod(0o644)
        with pytest.raises(ValueError, match="permissions"):
            read_store(project)


def test_missing_key_and_unsafe_run_rejected_before_network(tmp_path):
    with pytest.raises(ValueError, match="requires an API key"):
        search(tmp_path / "project", "ieee", "testing")
    with pytest.raises(ValueError, match="safe filename"):
        search(tmp_path / "project", "dblp", "testing", run_id="../escape")


def test_http_retry_and_secret_free_errors(monkeypatch):
    attempts = []

    class Opener:
        def open(self, *args, **kwargs):
            attempts.append(1)
            raise HTTPError("https://test/?apikey=private-key", 429, "private-key", {}, None)

    monkeypatch.setattr(http, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(http.time, "sleep", lambda *a: None)
    with pytest.raises(ValueError, match="HTTP 429") as error:
        http.get_json(PROVIDERS["ieee"].endpoint, {"apikey": "private-key"}, {})
    assert len(attempts) == 3 and "private-key" not in str(error.value)
    assert http.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other/") is None
    with pytest.raises(ValueError, match="retry"):
        http.retry_delay("nan", 0)


def test_browser_challenge_has_safe_actionable_error(tmp_path, monkeypatch):
    class Response:
        status = 202

        def __init__(self):
            self.headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Opener:
        def open(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(http, "build_opener", lambda *a: Opener())
    with pytest.raises(ValueError, match="browser challenge"):
        search(tmp_path / "project", "dblp", "testing")


def test_zero_results_bundle_is_complete(tmp_path):
    result = search(tmp_path / "project", "dblp", "testing", fetch=lambda *a: dblp_page([], 0))
    assert result["status"] == "completed"
    assert result["records_count"] == 0 and result["truncated"] is False


def test_credentials_prompt_refuses_piped_input(tmp_path, monkeypatch):
    import sys

    from slr_workbench.search.credentials import configure_credentials

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(ValueError, match="interactive"):
        configure_credentials(tmp_path / "project", "openalex", "set", "api_key")
