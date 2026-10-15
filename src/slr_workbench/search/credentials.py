"""Read environment keys or a private external JSON file; never accept CLI secret values."""

from __future__ import annotations

import getpass
import json
import os
import sys
import tempfile
from pathlib import Path

from .catalog import PROVIDERS


def credential_path(project: Path) -> Path:
    path = (
        Path(
            os.environ.get(
                "SLR_CREDENTIALS_FILE",
                str(Path.home() / ".config" / "slr-workbench" / "scientific-credentials.json"),
            )
        )
        .expanduser()
        .resolve()
    )
    # Reject not just the current checkout but any workbench checkout/backup source tree.
    if path.is_relative_to(project.resolve()) or any(
        (parent / "protocol.yaml").exists() and (parent / "pyproject.toml").exists()
        for parent in path.parents
    ):
        raise ValueError(
            "Credentials must be stored outside every project checkout. Set SLR_CREDENTIALS_FILE to a private external location."
        )
    return path


def read_store(project: Path) -> dict:
    path = credential_path(project)
    if not path.exists():
        return {}
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ValueError(
            "Credential file permissions are too broad; restrict it to its owner (chmod 600)."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or any(not isinstance(v, dict) for v in data.values()):
            raise ValueError
        for provider, values in data.items():
            if provider not in PROVIDERS or set(values) - PROVIDERS[provider].credentials.keys():
                raise ValueError
            if any(
                not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value
                for value in values.values()
            ):
                raise ValueError
        return data
    except (ValueError, TypeError):
        raise ValueError(
            "Invalid scientific credential file; values have not been printed."
        ) from None


def load_credentials(provider: str, project: Path) -> dict[str, str]:
    # Environment variables take precedence; a malformed external store is not silently ignored.
    stored = read_store(project).get(provider, {})
    result = {
        field: os.environ.get(variable) or stored.get(field, "")
        for field, variable in PROVIDERS[provider].credentials.items()
    }
    if any("\n" in value or "\r" in value for value in result.values()):
        raise ValueError("Credential values must not contain line breaks.")
    return {name: value.strip() for name, value in result.items() if value.strip()}


def configure_credentials(project: Path, provider: str, action: str, field: str) -> dict:
    spec = PROVIDERS[provider]
    if action == "status":
        values = load_credentials(provider, project)
        return {
            "provider": provider,
            "configured": {name: bool(values.get(name)) for name in spec.credentials},
        }
    if field not in spec.credentials:
        raise ValueError("This credential field is not supported by the selected provider.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError(
            "Configure credentials yourself in a separate interactive terminal; do not pipe secrets."
        )
    data = read_store(project)
    if action == "set":
        value = getpass.getpass(
            f"{spec.name} {field} (hidden; API credential, not account password): "
        ).strip()
        if not value or "\n" in value or "\r" in value:
            raise ValueError("A nonempty single-line credential is required.")
        data.setdefault(provider, {})[field] = value
    else:
        data.get(provider, {}).pop(field, None)
    path = credential_path(project)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {
        "provider": provider,
        "field": field,
        "action": action,
        "note": "Stored outside the project, unencrypted. Protect this user-profile location with OS permissions. Environment variables override this file.",
    }
