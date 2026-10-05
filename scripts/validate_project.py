"""Validate editable configuration, portable skill metadata and slash-command wiring."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from slr_workbench.config import load_configuration


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_configuration(root)
    for stage in config.workflow.stages:
        path = root / ".opencode" / "skills" / stage.skill / "SKILL.md"
        content = path.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)
        if not match:
            raise ValueError(f"Missing YAML frontmatter: {path}")
        metadata = yaml.safe_load(match[1])
        if metadata.get("name") != stage.skill or not re.fullmatch(
            r"[a-z0-9]+(-[a-z0-9]+)*", stage.skill
        ):
            raise ValueError(f"Invalid portable skill name: {stage.skill}")
        if not 1 <= len(metadata.get("description", "")) <= 1024 or len(stage.skill) > 64:
            raise ValueError(f"Invalid skill metadata: {stage.skill}")
        command = root / ".opencode" / "commands" / f"{stage.skill}.md"
        if stage.skill not in command.read_text(encoding="utf-8"):
            raise ValueError(f"Command is not wired to its skill: {command}")
    for path in [root / "opencode.json", *sorted((root / "config").glob("opencode.*.json"))]:
        json.loads(path.read_text(encoding="utf-8"))
    for path in (root / ".vscode").glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    print(
        f"Valid: {len(config.workflow.stages)} stages and matching skills/commands; revision {config.revision}"
    )


if __name__ == "__main__":
    main()
