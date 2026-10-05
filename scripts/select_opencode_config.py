"""Select the appropriate OpenCode major-version profile without handling credentials."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def detect_major(executable: str) -> int:
    """Recognize complete version lines, including OpenCode V2's `opencode v2.x.y`."""
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, check=True, timeout=15
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("OpenCode --version timed out after 15 seconds") from error
    except subprocess.CalledProcessError as error:
        raise ValueError(
            f"OpenCode --version failed (exit {error.returncode}); run it directly for diagnostics"
        ) from error
    except OSError as error:
        raise ValueError(f"Could not run OpenCode --version: {error}") from error
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.stdout + "\n" + result.stderr)
    matches = re.findall(
        r"^\s*(?:opencode\s+(?:version\s+)?)?v?(\d+)\.\d+\.\d+"
        r"(?:-[\w.-]+)?(?:\+[\w.-]+)?\s*$",
        output,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    majors = {int(value) for value in matches}
    if len(majors) != 1:
        raise ValueError(
            "Unrecognized or ambiguous OpenCode version output. Run opencode --version; "
            "use --major 1 or --major 2 only after verifying the installed major version."
        )
    major = majors.pop()
    if major not in (1, 2):
        raise ValueError(f"Unsupported OpenCode major version {major}; available profiles are 1 and 2")
    return major


def select_profile(root: Path, major: int) -> None:
    """Select a bundled project profile while retaining the previous configuration."""
    profile = root / "config" / f"opencode.v{major}.json"
    destination = root / "opencode.json"
    content = profile.read_text(encoding="utf-8")
    if destination.exists() and destination.read_text(encoding="utf-8") != content:
        shutil.copyfile(destination, root / "opencode.previous.json")
        print(
            "Previous project configuration saved as opencode.previous.json; merge your custom settings."
        )
    destination.write_text(json.dumps(json.loads(content), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--major", type=int, choices=[1, 2], help="Override version detection")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    major = args.major
    if major is None:
        executable = shutil.which("opencode")
        if not executable:
            parser.error(
                "OpenCode is not installed/on PATH. Install it or select --major 1/2 explicitly."
            )
        try:
            major = detect_major(executable)
        except ValueError as error:
            parser.error(str(error))
    select_profile(root, major)
    print(f"Selected OpenCode {major} profile. Use /connect and /models inside OpenCode.")


if __name__ == "__main__":
    main()
