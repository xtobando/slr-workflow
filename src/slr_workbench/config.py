"""Load editable YAML and compute the exact protocol/workflow revision."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from .models import Protocol, Stage, Workflow


@dataclass(frozen=True)
class Configuration:
    root: Path
    protocol: Protocol
    workflow: Workflow
    revision: str
    protocol_yaml: str
    workflow_yaml: str

    @property
    def database(self) -> Path:
        return self.root / self.protocol.paths.database

    def stage(self, stage_id: str) -> Stage:
        for stage in self.workflow.stages:
            if stage.id == stage_id and stage.enabled:
                return stage
        raise ValueError(f"Unknown or disabled stage: {stage_id}")


def load_configuration(root: Path) -> Configuration:
    """Read both files; never silently substitute defaults for invalid content."""
    root = root.resolve()
    protocol_raw = (root / "protocol.yaml").read_text(encoding="utf-8")
    workflow_raw = (root / "workflow.yaml").read_text(encoding="utf-8")
    protocol = Protocol.model_validate(yaml.safe_load(protocol_raw))
    workflow = Workflow.model_validate(yaml.safe_load(workflow_raw))
    known = {s.id for s in workflow.stages}
    for criterion in protocol.eligibility:
        if set(criterion.stages) - known:
            raise ValueError(f"Unknown stage in criterion {criterion.id}")
    revision = hashlib.sha256(
        (protocol_raw + "\n---WORKFLOW---\n" + workflow_raw).encode()
    ).hexdigest()
    return Configuration(root, protocol, workflow, revision, protocol_raw, workflow_raw)
