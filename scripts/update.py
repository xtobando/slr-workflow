"""Prepare and test an updated checkout; never replace the running project."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from slr_workbench.backups import create_backup, unpack_verified
from slr_workbench.config import load_configuration

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    "protocol.yaml",
    "workflow.yaml",
    "conversion.yaml",
    "rag.yaml",
    "opencode.json",
    "AGENTS.md",
}


def git(*args: str, root: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=root or ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def prepare_update(destination: Path, *, check: bool = False) -> dict:
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    remote, branch = upstream.split("/", 1)
    before = git("rev-parse", "HEAD")
    git("fetch", "--", remote, branch)
    revision = git("rev-parse", "FETCH_HEAD")
    git("merge-base", "--is-ancestor", before, revision)
    if check or revision == before:
        return {"update_available": revision != before, "current": before, "available": revision}
    destination = destination.resolve()
    if destination.exists() or destination.is_relative_to(ROOT):
        raise ValueError("Update destination must be a new folder outside this project.")
    modified = set(filter(None, git("diff", "HEAD", "--name-only").splitlines()))
    modified |= set(filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()))
    if any(name not in CONFIG and not name.startswith(".opencode/") for name in modified):
        raise ValueError(
            "Local code changes need manual merging. Commit or preserve them before updating."
        )
    if any(not (ROOT / name).is_file() for name in modified):
        raise ValueError("Locally deleted customization files need manual merging before updating.")
    backup = create_backup(ROOT)
    source_url = git("remote", "get-url", remote)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Clone from the fetched local object store: the exact inspected revision is used.
    git("clone", "--no-hardlinks", "--no-checkout", "--", str(ROOT), str(destination))
    try:
        git("checkout", "-B", branch, revision, root=destination)
        git("remote", "set-url", "origin", source_url, root=destination)
        git("update-ref", f"refs/remotes/origin/{branch}", revision, root=destination)
        git("branch", "--set-upstream-to", f"origin/{branch}", branch, root=destination)
        interpreter = getattr(sys, "_base_executable", sys.executable)
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        env.pop("UV_PROJECT_ENVIRONMENT", None)
        log_path = destination / "update-validation.log"
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(
                [interpreter, "scripts/setup.py"],
                cwd=destination,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
            python = (
                destination / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            subprocess.run(
                [str(python), "-m", "pytest", "-q"],
                cwd=destination,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
            with tempfile.TemporaryDirectory(prefix="slr-update-data-") as temporary:
                old = Path(temporary).resolve()
                manifest = unpack_verified(Path(backup["backup"]), old)
                config = load_configuration(old)
                roots = {"data", config.protocol.paths.artifacts, config.protocol.paths.exports}
                special = CONFIG | modified | {config.protocol.paths.database}
                tracked = set(git("ls-files", root=destination).splitlines())
                for name in manifest["files"]:
                    path = Path(name)
                    if name in special or any(
                        path == Path(r) or Path(r) in path.parents for r in roots
                    ):
                        # Never overwrite new executable source through a misconfigured data path.
                        if name not in CONFIG and name not in modified and name in tracked:
                            raise ValueError(f"Review data overlaps tracked source: {name}")
                        target = destination / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(old / name, target)
                subprocess.run(
                    [str(python), "scripts/validate_project.py"],
                    cwd=destination,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
                if manifest["database"]:
                    subprocess.run(
                        [str(python), "-m", "slr_workbench", "audit"],
                        cwd=destination,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=True,
                    )
        return {
            "prepared": str(destination),
            "revision": revision,
            "backup": backup["backup"],
            "next": "Close the old session before using the new folder. Changes made since the snapshot are not included. Keep the original for rollback.",
        }
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise ValueError(
            f"Candidate failed validation; do not use {destination}. Original review is unchanged. See update-validation.log. {error}"
        ) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if not args.check and args.destination is None:
        parser.error("Provide --destination for a separate checkout, or --check")
    try:
        print(json.dumps(prepare_update(args.destination or ROOT, check=args.check), indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(
            f"Update stopped: {error}. ZIP downloads require a Git clone for automatic update checks.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
