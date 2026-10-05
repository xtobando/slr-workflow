"""Check that built distributions include the schema needed for initialization."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
    sources = list((root / "dist").glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected one wheel and one source archive; use a clean dist directory")
    migrations = sorted((root / "src/slr_workbench/migrations").glob("*.sql"))
    if not migrations:
        raise ValueError("No source migrations found")
    with zipfile.ZipFile(wheels[0]) as wheel, tarfile.open(sources[0]) as source:
        for migration in migrations:
            member = f"slr_workbench/migrations/{migration.name}"
            if wheel.read(member) != migration.read_bytes():
                raise ValueError(f"Wheel migration differs: {member}")
            matches = [name for name in source.getnames() if name.endswith(f"/src/{member}")]
            if len(matches) != 1:
                raise ValueError(f"Missing or duplicate source migration: {member}")
            stream = source.extractfile(matches[0])
            if stream is None or stream.read() != migration.read_bytes():
                raise ValueError(f"Source migration differs: {member}")
    print(f"Valid: wheel and source archive contain {len(migrations)} matching migration(s)")


if __name__ == "__main__":
    main()
