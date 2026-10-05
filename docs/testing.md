# Validation record — iteration 1

Executed on 2026-10-05 in a fresh Python 3.12.14 virtual environment on Linux.
The supported Python floor is 3.11; Windows, macOS and Python 3.11 have not been
exercised in this build.

## Reproduce the core checks

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_project.py
python -m ruff check src scripts tests
python -m pytest -q
```

All **21 tests passed**. Ruff reported no remaining errors. Project validation
checked the 12 workflow stages, matching skill/command files, portable skill
metadata, acyclic prerequisites and the OpenCode/VS Code JSON files.
The Pydantic draft schema was regenerated successfully and the installed `slr`
entry point exposed all documented commands.
The distributable Python wheel also built successfully, and its contents include
the SQL migration required for database initialization.

The tests cover behavior that affects scientific decisions and reporting:

- Idempotent imports and conflicting search-run identifiers.
- Preserved source records and exact DOI duplicate removal.
- Separation of an agent proposal from a human decision.
- Rejection of invented quotations, incorrect page anchors and inapplicable criteria.
- Protocol approval and upstream eligibility prerequisites.
- Append-only history, superseding decisions and revision isolation.
- Non-retrieval as a distinct outcome from eligibility exclusion.
- Explicit extraction missingness, approved table exports and source retrieval.
- Event-cutoff snapshots and two publications linked to one underlying study.
- Human reviewer disagreement, consensus and adjudication prerequisites.
- Rejection of piped human approvals and the CLI's interactive review path.
- Withdrawal of eligibility or quality approval, with dependent results removed
  from active retrieval and summaries.
- Renamed workflow milestones, invalid retrieval settings and archive tampering.

The interactive CLI test substitutes the terminal check inside pytest so it can
exercise the prompts. This substitution is limited to tests. Real commands
require an interactive terminal; reviewer labels and terminal checks are workflow
controls, not authenticated identity or an operating-system security boundary.

## Independent skill trial

An independent agent read the screening skill and an evidence packet for the
clearly unrelated synthetic record. It submitted an exclusion proposal with
the configured criterion and exact title/abstract quotations, then handed human
review back without recording a decision. A subsequent status/audit check showed
three imported records, one duplicate, two pending records, zero screened records
and an intact event chain.

This trial used this build environment's agent, not a live OpenCode provider
session. Unknown model/session identifiers remained null instead of being
invented. The fixture papers and DOIs are fictional and must never enter a real
review's evidence base.

## Dependency versions used

| Component | Tested version |
| --- | --- |
| Python | 3.12.14 |
| Pydantic | 2.13.5 |
| PyYAML | 6.0.3 |
| Typer | 0.27.2 |
| Rich | 14.3.4 |
| pytest | 9.1.1 |
| Ruff | 0.16.10 |

The requirements define compatible version ranges rather than a cross-platform
lock file. For a real review, freeze the environment you actually use and retain
it with your protocol, project commit and export manifests.

## Checks that remain on your machine

OpenCode is not installed in this build environment. Its V1/V2 profiles and
skills were prepared from official documentation and structurally checked, but
live OpenCode loading, provider authentication, account quotas and VS Code UI
behavior still require a local smoke test.

Docling, Chroma and SentenceTransformers are optional, lazy-loaded adapters.
They have not been installed or run against downloaded models here. Validate
conversion on representative PDFs, including tables, formulas and physical page
anchors, and evaluate retrieval using questions with known answers before relying
on those adapters for a review. The core tests do not establish their runtime
compatibility or scientific extraction accuracy.
