"""Provider-native requests and conservative metadata normalization."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from typing import Any

from ..models import RecordInput
from .catalog import PROVIDERS


class PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain(value: Any) -> str:
    parser = PlainText()
    parser.feed(str(value or ""))
    return unescape(" ".join(parser.parts)).strip()


def items(value: Any) -> list:
    return value if isinstance(value, list) else [value] if value else []


def request(provider: str, query: str, cursor: Any, size: int, keys: dict) -> tuple[dict, dict]:
    """Return transport parameters and headers; never persist these with credentials."""
    key = keys.get("api_key")
    if provider == "dblp":
        return {"q": query, "format": "json", "h": size, "f": cursor or 0, "c": 0}, {}
    if provider == "crossref":
        return {"query.bibliographic": query, "rows": size, "cursor": cursor or "*"}, {}
    if provider == "openalex":
        params = {"search": query, "per_page": size}
        if key:
            params["cursor"] = cursor or "*"
        return params, {"Authorization": f"Bearer {key}"} if key else {}
    if provider == "semantic-scholar":
        params = {"query": query, "fields": "title,abstract,year,authors,externalIds,url,venue"}
        if cursor:
            params["token"] = cursor
        return params, {"x-api-key": key} if key else {}
    if provider == "ieee":
        return {
            "querytext": query,
            "format": "json",
            "apikey": key,
            "max_records": size,
            "start_record": cursor or 1,
            "sort_field": "article_number",
            "sort_order": "asc",
        }, {}
    if provider == "scopus":
        headers = {"X-ELS-APIKey": key}
        if keys.get("insttoken"):
            headers["X-ELS-Insttoken"] = keys["insttoken"]
        return {"query": query, "count": size, "start": cursor or 0, "view": "STANDARD"}, headers
    return {"q": query, "db": "WOS", "limit": size, "page": cursor or 1}, {"X-ApiKey": key}


def page(provider: str, data: dict, cursor: Any, size: int) -> tuple[list[dict], int, object]:
    """Return items, provider total/estimate and next cursor (None at exhaustion)."""
    if provider == "dblp":
        block = data["result"]["hits"]
        rows, total = items(block.get("hit")), int(block["@total"])
        following = (cursor or 0) + len(rows)
    elif provider == "crossref":
        block = data["message"]
        rows, total = block["items"], int(block["total-results"])
        following = block.get("next-cursor")
    elif provider == "openalex":
        rows, total = data["results"], int(data["meta"]["count"])
        following = data["meta"].get("next_cursor")
    elif provider == "semantic-scholar":
        rows, total = data["data"], int(data["total"])
        following = data.get("token")
    elif provider == "ieee":
        rows, total = data.get("articles", []), int(data["total_records"])
        following = (cursor or 1) + len(rows)
    elif provider == "scopus":
        block = data["search-results"]
        total = int(block["opensearch:totalResults"])
        rows = block.get("entry", []) if total else []
        following = (cursor or 0) + len(rows)
    else:
        rows, total = data["hits"], int(data["metadata"]["total"])
        following = (cursor or 1) + 1
    if not isinstance(rows, list) or total < 0 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid metadata page")
    return rows, total, following if rows else None


def normalize(provider: str, raw: dict) -> dict:
    """Missing fields remain missing; no metadata or abstracts are inferred."""
    abstract, authors, doi, year, url = "", [], None, None, None
    if provider == "dblp":
        row = raw["info"]
        identity, title = row.get("key") or raw.get("@id"), row["title"]
        authors = [
            a.get("text", "") if isinstance(a, dict) else a
            for a in items(row.get("authors", {}).get("author"))
        ]
        doi, year, url = row.get("doi"), row.get("year"), row.get("url")
    elif provider == "crossref":
        identity, title = raw["DOI"], next(iter(raw.get("title", [])), "")
        abstract = plain(raw.get("abstract"))
        authors = [
            a.get("name") or " ".join(filter(None, [a.get("given"), a.get("family")]))
            for a in raw.get("author", [])
        ]
        dates = raw.get("published", {}).get("date-parts", [[]])
        year = dates[0][0] if dates and dates[0] else None
        doi, url = identity, raw.get("URL")
    elif provider == "openalex":
        identity, title = raw["id"], raw.get("display_name") or raw.get("title")
        authors = [a["author"].get("display_name", "") for a in raw.get("authorships", [])]
        positions = {}
        for word, indexes in (raw.get("abstract_inverted_index") or {}).items():
            for index in indexes:
                if not isinstance(index, int) or index < 0 or index > 100000 or index in positions:
                    raise ValueError("Invalid abstract positions")
                positions[index] = word
        abstract = " ".join(positions[i] for i in sorted(positions))
        doi, year = raw.get("doi"), raw.get("publication_year")
        url = (raw.get("primary_location") or {}).get("landing_page_url") or identity
    elif provider == "semantic-scholar":
        identity, title = raw["paperId"], raw["title"]
        abstract = raw.get("abstract") or ""
        authors = [a.get("name", "") for a in raw.get("authors", [])]
        doi, year, url = (raw.get("externalIds") or {}).get("DOI"), raw.get("year"), raw.get("url")
    elif provider == "ieee":
        identity, title = raw["article_number"], raw["title"]
        abstract = raw.get("abstract") or ""
        authors = [a.get("full_name", "") for a in raw.get("authors", {}).get("authors", [])]
        doi, year, url = raw.get("doi"), raw.get("publication_year"), raw.get("abstract_url")
    elif provider == "scopus":
        identity, title = raw.get("eid") or raw.get("dc:identifier"), raw["dc:title"]
        authors = [raw["dc:creator"]] if raw.get("dc:creator") else []
        doi, year, url = (
            raw.get("prism:doi"),
            (raw.get("prism:coverDate") or "")[:4],
            raw.get("prism:url"),
        )
    else:
        identity, title = raw["uid"], raw["title"]
        authors = [a.get("displayName", "") for a in raw.get("names", {}).get("authors", [])]
        doi = (raw.get("identifiers") or {}).get("doi")
        year, url = raw.get("source", {}).get("publishYear"), raw.get("links", {}).get("record")
    if not identity or not title or not str(title).strip():
        raise ValueError("Provider record is missing its identifier or title")
    if doi:
        doi = str(doi).removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    record = {
        "source_record_id": str(identity),
        "title": plain(title),
        "abstract": abstract,
        "authors": [a for a in authors if a],
        "doi": doi,
        "year": int(year) if year else None,
        "url": url,
        "metadata": {"provider": provider, "interface": PROVIDERS[provider].endpoint},
    }
    record["metadata"]["missing_fields"] = [
        name for name in ("abstract", "authors", "doi", "year", "url") if not record[name]
    ]
    if provider == "scopus":
        record["metadata"]["authors_scope"] = "STANDARD view may supply only the first author"
    return RecordInput.model_validate(record).model_dump()
