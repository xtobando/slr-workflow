"""Select the appropriate OpenCode major-version profile without handling credentials."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


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
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, check=True, timeout=15
        )
        match = re.search(r"\b(\d+)\.\d+\.\d+", result.stdout + result.stderr)
        if not match or int(match[1]) not in (1, 2):
            parser.error(
                "Unsupported or unrecognized version. Check current OpenCode documentation."
            )
        major = int(match[1])
    profile = root / "config" / f"opencode.v{major}.json"
    destination = root / "opencode.json"
    content = profile.read_text(encoding="utf-8")
    if destination.exists() and destination.read_text(encoding="utf-8") != content:
        shutil.copyfile(destination, root / "opencode.previous.json")
        print(
            "Previous project configuration saved as opencode.previous.json; merge your custom settings."
        )
    destination.write_text(json.dumps(json.loads(content), indent=2) + "\n", encoding="utf-8")
    print(f"Selected OpenCode {major} profile. Use /connect and /models inside OpenCode.")


if __name__ == "__main__":
    main()
