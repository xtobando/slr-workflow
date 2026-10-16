# Project layout and compatibility

This is the existing workbench, with a small CLI split and cohesive new services.
The current size does not justify generic domain/services/repository hierarchies.

```text
AGENTS.md                   Project guardrails, kept at the root
protocol.yaml               Editable scientific protocol, unchanged in this revision
workflow.yaml               Editable stages and roles, unchanged in this revision
conversion.yaml, rag.yaml   Optional adapter settings
.opencode/                  Discoverable stage skills and slash commands
config/                     Maintained OpenCode profile templates
schemas/                    Published draft contract
src/slr_workbench/
    cli/__init__.py         Entry point, presentation and interactive human gates
    cli/parser.py           Argparse command definitions
    models.py, validation.py Typed contracts and explicit validation
    config.py               Configuration loading and revision hashing
    service.py              Existing review operations and scientific prerequisites
    database.py, migrations/SQLite transactions and immutable versioned schema
    search/                 Native API adapters, external credentials and archives
    coverage.py             Read-only completeness and declared seed sensitivity
    review_support.py       Pending sheets, pilot comparison and human handoffs
    duplicate_candidates.py Read-only bibliographic and report-family hints
    reporting.py, audit.py   Deterministic counts, exports and integrity checks
    pdf_reader.py           Independent PDF-to-Markdown conversion
    integrations.py         Optional Docling and Chroma adapters
    backups.py              Verified backup/restore
scripts/                    Maintained setup, launcher, update and validation tools
tests/                      Automated synthetic tests, separate from real review data
examples/                   Explicitly synthetic walkthrough inputs
docs/                       User, scientific-method and development documentation
```

Flat `tests/` and `docs/` remain practical at this size. Tests have descriptive
module names, and `conftest.py`/test helpers provide disposable synthetic fixtures.
No source export, PDF, database reference, root protocol or skill location is moved.

## Data lifecycle

All paths below are local and ignored by Git. Configurable database/artifact/export
paths in the protocol remain authoritative; these are starter defaults.

| Path | Role and preservation |
| --- | --- |
| `data/slr.sqlite` | Authoritative source records, proposals, decisions and event history |
| `data/artifacts/` | Attached originals and immutable derived evidence, addressed by document ID/hash |
| `data/searches/<run>/` | Search definition, request/page receipts, checkpoints and versioned manifests/records |
| `data/reading/` | Archived standalone PDF originals, extracted Markdown and conversion manifests |
| `data/packets/` | Recommended location for future generated evidence packets; choose explicit filenames |
| `data/drafts/` | Agent drafts and separately authored human decision files |
| `data/review-packages/` | New immutable review sheet packages and provenance manifests |
| `data/candidates/` | Fresh read-only duplicate candidate exports |
| `data/maintenance/` | Local mechanical validation receipts and hashes; no scientific decisions |
| `data/exports/` | New per-invocation PRISMA count/table snapshots and manifests |
| `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.workbench-state/` | Environment/cache/launcher state, ignored by Git |

Search snapshots and source evidence are preserved. Only the documented latest
search aliases and atomic checkpoint are replaceable pointers. Pending packages
and candidate exports are generated summaries, not new scientific decisions.
Keep originals and review data in verified backups; Git does not back up `data/`.

## Compatibility and migration

- Python's entry points remain `python -m slr_workbench` and `slr_workbench.cli:app`.
  Importing `app`, `build_parser`, `console` or the existing interactive helpers from
  `slr_workbench.cli` still works. `cli.py` became a package; no old implementation
  remains. Setuptools discovers it automatically.
- Existing CLI names and approval guards remain. New commands are additive.
  Windows PowerShell launchers continue forwarding arguments to the same entry point.
- No schema or migration changes, no data moves, and no protocol/workflow amendments
  are needed for these software changes. Existing decisions retain their revision.
- Existing v1 search bundles remain importable. They do not contain resumable page
  receipts; preserve them and start a new run when continuing their query. New v2
  snapshots can be resumed with the original query; see the search tutorial.
- Search requests are anonymous by default. `--allow-credentials` explicitly opts
  into configured credentials and possible provider costs. Review the plan first.
- Each `report` call now returns a **new export directory**, even for an unchanged
  cutoff. Consume the printed `export_directory`; do not construct its name.
  Earlier export folders stay intact. Count JSON remains deterministic at a cutoff.
- No broad source rewrite or optional package installation was performed. Core
  dependencies and the lockfile are unchanged. Local testing here covers macOS
  with Python 3.12; cross-platform CI results must be checked separately.
