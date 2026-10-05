"""Initialize a project database without approving its scientific protocol."""

from __future__ import annotations

import argparse
from pathlib import Path

from slr_workbench.config import load_configuration
from slr_workbench.service import ReviewService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    service = ReviewService(load_configuration(args.project))
    print(f"Registered revision: {service.initialize()}")
    print(f"Database: {service.config.database}")
    print("Human protocol approval is required before importing search results.")


if __name__ == "__main__":
    main()
