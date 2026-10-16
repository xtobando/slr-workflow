"""Bounded HTTPS requests with redacted failures and no credential-bearing redirects."""

from __future__ import annotations

import json
import math
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .catalog import PROVIDERS

MAX_BYTES = 20 * 1024 * 1024
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST: dict[str, float] = {}


class APIError(ValueError):
    """Safe transport diagnostics constructed locally, never from a response body."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def redact(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {
            redact(str(key), secrets): (
                "[REDACTED]"
                if str(key).lower().replace("-", "_")
                in {
                    "apikey",
                    "api_key",
                    "authorization",
                    "x_api_key",
                    "x_els_apikey",
                    "insttoken",
                    "x_els_insttoken",
                }
                else redact(item, secrets)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            for representation in {secret, quote(secret, safe=""), quote_plus(secret)}:
                if representation:
                    value = value.replace(representation, "[REDACTED]")
    return value


def retry_delay(header: str | None, attempt: int) -> float:
    try:
        wait = float(header) if header else 2**attempt
    except ValueError:
        try:
            wait = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError):
            wait = 2**attempt
    if not math.isfinite(wait) or wait > 30:
        raise APIError("Provider requested a long retry delay; retry the search later.")
    return max(0, wait)


def parse_atom(body: bytes) -> dict:
    """Parse the arXiv Atom feed and retain its original text as archived evidence."""
    if b"<!doctype" in body.lower() or b"<!entity" in body.lower():
        raise APIError("arXiv XML declarations/entities are not supported.")
    try:
        feed = ET.fromstring(body)
        ns = {
            "a": "http://www.w3.org/2005/Atom",
            "o": "http://a9.com/-/spec/opensearch/1.1/",
            "r": "http://arxiv.org/schemas/atom",
        }
        if feed.tag != "{http://www.w3.org/2005/Atom}feed":
            raise ValueError("Not an Atom feed")
        entries = []
        for entry in feed.findall("a:entry", ns):
            identity = entry.findtext("a:id", default="", namespaces=ns).strip()
            if not identity.startswith(("https://arxiv.org/abs/", "http://arxiv.org/abs/")):
                raise ValueError("Invalid arXiv identifier or error feed")

            def text(name: str, element: ET.Element = entry) -> str:
                return " ".join(element.findtext(name, default="", namespaces=ns).split())

            entries.append(
                {
                    "id": identity,
                    "title": text("a:title"),
                    "summary": text("a:summary"),
                    "published": text("a:published"),
                    "updated": text("a:updated"),
                    "authors": [
                        " ".join(a.findtext("a:name", default="", namespaces=ns).split())
                        for a in entry.findall("a:author", ns)
                    ],
                    "doi": text("r:doi") or None,
                    "categories": [
                        c.attrib["term"]
                        for c in entry.findall("a:category", ns)
                        if "term" in c.attrib
                    ],
                }
            )
        return {
            "atom_xml": body.decode("utf-8"),
            "entries": entries,
            "total_results": int(feed.findtext("o:totalResults", namespaces=ns)),
            "start_index": int(feed.findtext("o:startIndex", namespaces=ns)),
        }
    except (ET.ParseError, ValueError, TypeError, UnicodeDecodeError):
        raise APIError("arXiv returned invalid Atom metadata or an API error feed.") from None


def get_json(
    endpoint: str, params: dict, headers: dict, *, before_attempt: Callable[[], None] | None = None
) -> dict:
    """Fetch a JSON object or parsed arXiv Atom with bounded physical requests.

    The callback runs before every physical request, including retries, so callers
    can checkpoint and enforce a request budget. A single process serializes calls;
    users must not run multiple arXiv harvesters concurrently across machines.
    """
    if endpoint not in {p.endpoint for p in PROVIDERS.values()}:
        raise APIError("Unsupported API endpoint")
    spec = next(p for p in PROVIDERS.values() if p.endpoint == endpoint)
    is_atom = endpoint == PROVIDERS["arxiv"].endpoint
    request = Request(
        endpoint + "?" + urlencode(params),
        headers={
            "Accept": "application/atom+xml" if is_atom else "application/json",
            "User-Agent": "slr-workbench/0.1 scholarly-metadata-client",
            **headers,
        },
    )
    for attempt in range(3):
        try:
            if before_attempt is not None:
                before_attempt()
            # Hold this lock through the response to keep arXiv at one connection.
            with _REQUEST_LOCK:
                delay = spec.minimum_interval - (
                    time.monotonic() - _LAST_REQUEST.get(endpoint, float("-inf"))
                )
                if delay > 0:
                    time.sleep(delay)
                _LAST_REQUEST[endpoint] = time.monotonic()
                with build_opener(NoRedirect()).open(request, timeout=30) as response:
                    if response.status != 200 or "text/html" in response.headers.get(
                        "Content-Type", ""
                    ):
                        raise APIError(
                            "Provider returned an unsupported response or browser challenge. Use another source or a manual export; automated access was not bypassed."
                        )
                    body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise APIError("API response exceeds the size limit; narrow the query.")
            if is_atom:
                return parse_atom(body)
            result = json.loads(body)
            if not isinstance(result, dict):
                raise TypeError("Bibliographic API must return a JSON object")
            return result
        except HTTPError as error:
            code = error.code
            delay = error.headers.get("Retry-After") if error.headers else None
            error.close()
            if code in (408, 429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(retry_delay(delay, attempt))
                continue
            note = (
                "Check API credentials, institutional network and plan permissions."
                if code in (401, 403)
                else "Check query syntax, quota or provider availability."
            )
            raise APIError(f"Bibliographic API returned HTTP {code}. {note}") from None
        except (URLError, OSError, HTTPException):
            raise APIError(
                "Bibliographic API could not be reached (network/TLS/timeout). No request URL or credential was logged."
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise APIError("Bibliographic API did not return valid JSON.") from None
    raise APIError("Bibliographic API retry limit reached")
