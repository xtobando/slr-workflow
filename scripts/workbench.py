"""Short project launcher: CLI commands, OpenCode, tests and local uv."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    name = args.pop(0) if args else "help"
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = ROOT / ".venv" / suffix
    if name in ("help", "--help", "-h"):
        print("Usage: workbench <SLR command> [arguments]")
        print(
            "Helpers: opencode | configure | test | update | uv <arguments> | cli <arguments> | help"
        )
        print("Example: workbench read-pdf paper.pdf")
        return 0
    if not interpreter.is_file():
        print(
            "Environment missing. Run scripts/setup.ps1 or bash scripts/setup.sh first.",
            file=sys.stderr,
        )
        return 1
    env = dict(os.environ)
    env["VIRTUAL_ENV"] = str(ROOT / ".venv")
    env["PATH"] = str(interpreter.parent) + os.pathsep + env.get("PATH", "")
    if name == "opencode":
        executable = shutil.which("opencode", path=env["PATH"])
        if not executable:
            print("OpenCode is not installed/on PATH. See docs/installation.md.", file=sys.stderr)
            return 1
        command = [executable, *args]
    elif name == "cli":
        command = [str(interpreter), "-m", "slr_workbench", *args]
    elif name == "update":
        command = [str(interpreter), "scripts/update.py", *args]
    elif name == "configure":
        command = [str(interpreter), "scripts/select_opencode_config.py", *args]
    elif name == "test":
        command = [str(interpreter), "-m", "pytest", *args]
    elif name == "uv":
        bootstrap = ROOT / ".venv-setup" / suffix
        if not bootstrap.is_file():
            print("Local uv is missing. Rerun guided setup.", file=sys.stderr)
            return 1
        env["UV_PROJECT_ENVIRONMENT"] = str(ROOT / ".venv")
        env["UV_PYTHON"] = str(interpreter)
        command = [str(bootstrap), "-m", "uv", *args]
    else:
        command = [str(interpreter), "-m", "slr_workbench", name, *args]
    try:
        protected = {
            "opencode",
            "init",
            "approve-protocol",
            "import-records",
            "deduplicate",
            "submit",
            "review",
            "attach",
            "retrieval",
            "link-study",
            "unlink-study",
            "convert",
            "configure",
        }
        action = args[0] if name == "cli" and args else name
        automatic = action in protected and env.get("SLR_AUTO_BACKUP", "1") != "0"
        backup_command = [str(interpreter), "-m", "slr_workbench", "backup"]
        if automatic and subprocess.run(backup_command, cwd=ROOT, env=env, check=False).returncode:
            print("Pre-operation backup failed; command was not started.", file=sys.stderr)
            return 1
        if name == "opencode" and env.get("SLR_CHECK_UPDATES") == "1":
            subprocess.run(
                [str(interpreter), "scripts/update.py", "--check"], cwd=ROOT, env=env, check=False
            )
        result = subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
        if automatic and subprocess.run(backup_command, cwd=ROOT, env=env, check=False).returncode:
            print(
                "The operation finished, but its follow-up backup failed. Keep the project and retry backup.",
                file=sys.stderr,
            )
            return result or 1
        return result
    except OSError as error:
        print(f"Could not start command: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
