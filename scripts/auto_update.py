"""Stable launch routing with conservative, snapshot-checked automatic activation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def interpreter(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def save(path: Path, state: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def exclusive(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / "running.lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError(
            "Another launcher is active, or a previous run was interrupted. Close all workbench processes before removing .workbench-state/running.lock."
        ) from error
    try:
        (lock / "owner.txt").write_text(str(os.getpid()), encoding="utf-8")
        yield
    finally:
        (lock / "owner.txt").unlink(missing_ok=True)
        lock.rmdir()


def snapshot(root: Path) -> dict:
    # Use the owning environment; do not hash a live SQLite file/WAL independently.
    result = subprocess.run(
        [str(interpreter(root)), "-m", "slr_workbench", "backup"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    import zipfile

    archive = json.loads(result.stdout)["backup"]
    with zipfile.ZipFile(archive) as source:
        return json.loads(source.read("backup-manifest.json"))["files"]


def activate(state: dict, path: Path) -> None:
    pending = state.get("pending")
    if not pending:
        return
    active = Path(state["active"])
    candidate = Path(pending["path"])
    if (
        snapshot(active) != pending["source_files"]
        or snapshot(candidate) != pending["candidate_files"]
    ):
        state["pending"] = None
        save(path, state)
        print("Prepared update changed or became stale; keeping the current review.", flush=True)
        return
    updated = dict(state)
    updated["previous"] = {"path": str(active), "files": pending["source_files"]}
    updated["active"] = str(candidate)
    updated["active_files"] = pending["candidate_files"]
    updated["pending"] = None
    save(path, updated)
    state.update(updated)
    print(f"Activated verified update: {candidate}", flush=True)


def prepare(state: dict, path: Path) -> None:
    active = Path(state["active"])
    if state.get("pending"):
        return
    destination = ROOT.parent / (ROOT.name + "-versions") / uuid4().hex
    source_files = snapshot(active)
    result = subprocess.run(
        [
            str(interpreter(active)),
            "scripts/update.py",
            "--automatic",
            "--destination",
            str(destination),
        ],
        cwd=active,
        text=True,
        capture_output=True,
        check=True,
    )
    info = json.loads(result.stdout)
    if "prepared" not in info:
        return
    candidate_files = snapshot(destination)
    if snapshot(active) != source_files:
        print(
            "Review changed during update preparation; candidate will not be activated.", flush=True
        )
        return
    state["pending"] = {
        "path": str(destination),
        "source_files": source_files,
        "candidate_files": candidate_files,
    }
    save(path, state)
    print(
        "Update prepared and tested. It will activate on the next OpenCode startup if neither copy changes.",
        flush=True,
    )


def dispatch(argv: list[str]) -> int:
    folder = ROOT / ".workbench-state"
    path = folder / "state.json"
    try:
        with exclusive(folder):
            state = (
                json.loads(path.read_text(encoding="utf-8"))
                if path.exists()
                else {"enabled": True, "active": str(ROOT), "pending": None, "previous": None}
            )
            if argv and argv[0] == "auto-update":
                action = argv[1] if len(argv) > 1 else "status"
                if action in {"enable", "disable"}:
                    state["enabled"] = action == "enable"
                elif action == "rollback":
                    previous = state.get("previous")
                    if not previous:
                        raise ValueError("No previous version is available.")
                    if (
                        snapshot(Path(state["active"])) != state.get("active_files")
                        or snapshot(Path(previous["path"])) != previous["files"]
                    ):
                        raise ValueError(
                            "Work has changed since activation. Automatic rollback would risk losing it; use the recovery guide to preserve and migrate the latest data."
                        )
                    state["active"] = previous["path"]
                    state["previous"] = None
                    state["pending"] = None
                    state["enabled"] = False
                elif action != "status":
                    raise ValueError("Use auto-update status, enable, disable or rollback.")
                save(path, state)
                print(
                    json.dumps(
                        {
                            "enabled": state["enabled"],
                            "active": state["active"],
                            "pending": (state.get("pending") or {}).get("path"),
                            "previous": (state.get("previous") or {}).get("path"),
                        },
                        indent=2,
                    )
                )
                return 0
            opening = bool(argv and argv[0] == "opencode")
            if opening and state["enabled"]:
                try:
                    activate(state, path)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    print(f"Update activation skipped: {error}", file=sys.stderr)
            active = Path(state["active"])
            env = dict(os.environ, SLR_ROUTED_LAUNCH="1")
            result = subprocess.run(
                [str(interpreter(active)), str(active / "scripts/workbench.py"), *argv],
                cwd=active,
                env=env,
                check=False,
            ).returncode
            # Prepare after the session, when its latest saved work is available.
            if opening and result == 0 and state["enabled"] and (active / ".git").exists():
                try:
                    prepare(state, path)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    print(
                        f"Automatic update skipped; current version retained: {error}",
                        file=sys.stderr,
                    )
            return result
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Launcher stopped: {error}", file=sys.stderr)
        return 1
