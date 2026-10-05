"""Isolated fixtures; synthetic human decisions never touch a real review."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from slr_workbench.config import load_configuration
from slr_workbench.service import ReviewService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def review(tmp_path: Path) -> ReviewService:
    for name in ("protocol.yaml", "workflow.yaml", "rag.yaml"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    service = ReviewService(load_configuration(tmp_path))
    service.initialize()
    service.approve_protocol("thomas", "Approve synthetic fixture for isolated tests only")
    service.import_records(
        ROOT / "examples/records.json",
        "demo-run",
        "demo-database",
        "synthetic fixture",
        "2026-10-05T00:00:00+00:00",
    )
    service.deduplicate()
    return service
