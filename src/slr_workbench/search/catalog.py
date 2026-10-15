"""Provider capabilities and credential names; no credentials belong in this file."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    name: str
    endpoint: str
    documentation: str
    syntax: str
    credentials: dict[str, str] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    page_size: int = 100


PROVIDERS = {
    "dblp": Provider(
        "DBLP",
        "https://dblp.org/search/publ/api",
        "https://dblp.org/faq/How+to+use+the+dblp+search+API.html",
        "DBLP CompleteSearch terms/prefix syntax; not universal Boolean syntax. Abstracts are not supplied.",
    ),
    "crossref": Provider(
        "Crossref",
        "https://api.crossref.org/works",
        "https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
        "Bibliographic relevance query; not Boolean eligibility filtering. Abstracts may be absent.",
    ),
    "openalex": Provider(
        "OpenAlex",
        "https://api.openalex.org/works",
        "https://help.openalex.org/api/authentication/",
        "OpenAlex search syntax. A free key is required for cursor paging beyond the first page.",
        {"api_key": "SLR_OPENALEX_API_KEY"},
    ),
    "semantic-scholar": Provider(
        "Semantic Scholar",
        "https://api.semanticscholar.org/graph/v1/paper/search/bulk",
        "https://api.semanticscholar.org/api-docs/",
        "Bulk search Boolean grammar (+, |, -, quotes, parentheses); not relevance search. Totals are estimates.",
        {"api_key": "SLR_SEMANTIC_SCHOLAR_API_KEY"},
        page_size=1000,
    ),
    "ieee": Provider(
        "IEEE Xplore",
        "https://ieeexploreapi.ieee.org/api/v1/search/articles",
        "https://developer.ieee.org/docs/read/Searching_the_IEEE_Xplore_Metadata_API",
        "IEEE querytext syntax, including its supported field and Boolean expressions. Metadata access is separate from full text.",
        {"api_key": "SLR_IEEE_API_KEY"},
        ("api_key",),
    ),
    "scopus": Provider(
        "Scopus",
        "https://api.elsevier.com/content/search/scopus",
        "https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl",
        "Scopus advanced query, e.g. TITLE-ABS-KEY(...). API entitlements/IP access may be required; STANDARD metadata can omit abstracts.",
        {"api_key": "SLR_SCOPUS_API_KEY", "insttoken": "SLR_SCOPUS_INSTTOKEN"},
        ("api_key",),
        25,
    ),
    "wos": Provider(
        "Web of Science Starter",
        "https://api.clarivate.com/apis/wos-starter/v1/documents",
        "https://github.com/clarivate/wosstarter_python_client",
        "Starter-supported WoS field tags, e.g. TS=(...). API plan controls coverage; abstracts are not supplied.",
        {"api_key": "SLR_WOS_API_KEY"},
        ("api_key",),
        50,
    ),
}


def catalog() -> list[dict]:
    return [
        {
            "id": key,
            "name": p.name,
            "mode": "api",
            "documentation": p.documentation,
            "syntax": p.syntax,
            "credential_environment_variables": p.credentials,
            "required_credentials": list(p.required),
        }
        for key, p in PROVIDERS.items()
    ] + [
        {
            "id": "acm",
            "name": "ACM Digital Library",
            "mode": "manual_export",
            "documentation": "https://dl.acm.org/",
            "syntax": "Search in the official browser interface, export bibliographic data and map it to the documented JSON/CSV import format. No ACM login automation/API adapter is implemented.",
        }
    ]
