"""Bounded HTTPS requests with redacted failures and no credential-bearing redirects."""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .catalog import PROVIDERS

MAX_BYTES = 20 * 1024 * 1024


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


def get_json(endpoint: str, params: dict, headers: dict) -> dict:
    if endpoint not in {p.endpoint for p in PROVIDERS.values()}:
        raise APIError("Unsupported API endpoint")
    request = Request(
        endpoint + "?" + urlencode(params),
        headers={
            "Accept": "application/json",
            "User-Agent": "slr-workbench/0.1 scholarly-metadata-client",
            **headers,
        },
    )
    for attempt in range(3):
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                if response.status != 200 or "text/html" in response.headers.get(
                    "Content-Type", ""
                ):
                    raise APIError(
                        "Provider returned a non-JSON response or browser challenge. Use another source or a manual export; automated access was not bypassed."
                    )
                body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise APIError("API response exceeds the size limit; narrow the query.")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise TypeError("Bibliographic API must return a JSON object")
            return result
        except HTTPError as error:
            code = error.code
            delay = error.headers.get("Retry-After") if error.headers else None
            error.close()
            if code in (429, 502, 503, 504) and attempt < 2:
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
