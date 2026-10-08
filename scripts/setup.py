"""Prepare a local core environment using an already-installed Python 3.12."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def python_in(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(args: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def prepare(directory: Path) -> Path:
    """Reuse matching environments; never replace an existing incompatible one."""
    interpreter = python_in(directory)
    if directory.exists():
        if not interpreter.is_file():
            raise ValueError(f"{directory.name} is incomplete. Rename it and rerun setup.")
        result = subprocess.run(
            [
                str(interpreter),
                "-c",
                "import json,sys; print(json.dumps([list(sys.version_info[:2]), sys.base_prefix]))",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        version, base = json.loads(result.stdout)
        if version != [3, 12] or Path(base).resolve() != Path(sys.base_prefix).resolve():
            raise ValueError(
                f"{directory.name} uses another Python. Preserve/rename it first; "
                "see docs/windows-setup.md. Setup will not replace it."
            )
    else:
        venv.EnvBuilder(with_pip=True).create(directory)
    return interpreter


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        print(
            "Setup requires an installed Python 3.12. See README platform instructions.",
            file=sys.stderr,
        )
        return 1
    print(f"Using Python: {sys.executable}\nBase installation: {sys.base_prefix}", flush=True)
    try:
        # Check the review environment before installing anything else.
        interpreter = prepare(ROOT / ".venv")
        bootstrap = prepare(ROOT / ".venv-setup")
        settings = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        uv_pin = settings["tool"]["uv"]["required-version"]
        run([str(bootstrap), "-m", "pip", "install", "--disable-pip-version-check", f"uv{uv_pin}"])
        env = dict(os.environ)
        env.update(
            UV_PROJECT_ENVIRONMENT=str(ROOT / ".venv"),
            UV_PYTHON=str(interpreter),
            UV_PYTHON_DOWNLOADS="never",
            UV_PYTHON_PREFERENCE="only-system",
        )
        run(
            [
                str(bootstrap),
                "-m",
                "uv",
                "sync",
                "--locked",
                "--inexact",
                "--extra",
                "dev",
                "--extra",
                "pdf",
            ],
            env=env,
        )
        run([str(interpreter), "scripts/validate_project.py"])
        run([str(interpreter), "-m", "slr_workbench", "--help"])
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Setup stopped: {error}", file=sys.stderr)
        return 1
    print("\nCore setup complete. Existing optional packages were preserved.")
    prefix = ".\\workbench.ps1" if os.name == "nt" else "bash workbench.sh"
    print(f"Run checks: {prefix} test -q")
    print(f"Read a PDF: {prefix} read-pdf path/to/paper.pdf")
    if shutil.which("opencode"):
        print(f"Select the OpenCode profile: {prefix} configure")
        print(f"Start OpenCode: {prefix} opencode")
    else:
        print("OpenCode is not on PATH. Follow docs/installation.md, then reopen the terminal.")
    print("Next: README.md — Connect a model and Prepare your review.")
    print(
        "Protocol approval and research decisions must be completed by you in a separate terminal."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
