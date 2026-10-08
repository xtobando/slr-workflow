# Validation record — iteration 1

## Recovery and staged update validation (2026-10-07)

All **119 tests pass** locally. Recovery tests include committed uncheckpointed WAL
data, restored customization, checksum failures, unsafe archive paths, disk-full
simulation preserving earlier backups, and refusing to overwrite an existing
restore destination. Launcher tests verify that failed backups prevent writes.
Python discovery is tested with a `python3` executable and no versioned command.

A full staged update succeeded against isolated local Git repositories: the
candidate installed dependencies, ran tests, preserved saved notes and left the
original commit and working review unchanged. Failure-path tests verify that
failed candidate checks do not copy the review database into the candidate.
This does not establish protection against every hardware failure, nor Windows
runtime compatibility; platform CI results must be checked separately.

## PDF reader and launcher validation (2026-10-07)

All **110 tests pass** locally with the `pdf` extra on macOS/Python 3.12.15.
New coverage uses synthetic PDFs to check text/page extraction, missingness,
encrypted/invalid inputs and preservation of existing conversions. Launcher tests
check argument boundaries, inherited terminal input and failure propagation.
Project configuration, skill metadata, Bash syntax and Ruff checks pass.
Guided setup and an offline rerun both succeeded in an isolated clean source
checkout; its Bash launcher successfully ran the tests from outside the checkout.
The scientific configuration revision is unchanged. Windows/PowerShell execution,
OCR, Docling and Chroma remain unverified locally; CI includes the PDF extra.

## Earlier guided setup validation

The suite now passes **103 tests** locally. Setup tests cover preservation of
incomplete/incompatible environments, locked installation with existing extras
retained, and installation failure reporting. Project validation and lint pass;
the Bash wrapper passes a syntax check. CI is configured to exercise the Unix
wrapper on Python 3.12 and the PowerShell wrapper twice with official Windows
Python (including reuse). Those installer runs remain unverified locally.

## Core dependency migration

The argparse/dataclass migration passes **99 tests** on macOS with Python 3.12.15,
including a clean environment containing only core dependencies and pytest.
Tests cover nested validation, unknown fields, serialization, unchanged draft
JSON Schema, module execution, and rejection of piped human decisions. An import
blocker also checks core CLI execution without Typer, Pydantic or ctypes.
This is not a Windows Defender compatibility guarantee. The Windows python.org
installer CI job has been added; its results are pending execution. No scientific
configuration or database migrations were changed.

Use the current [reproducibility commands](reproducibility.md) to rerun checks.
Ruff is a separate optional `lint` extra. Optional conversion/vector adapters
remain outside this core validation.

## Earlier regression validation

Validated on 2026-10-05 on macOS arm64 with Python 3.12.15 and uv 0.12.23,
using the committed dependency lockfile in a separate `.venv-review` environment.
The existing `.venv` used Python 3.9.6 and was left intact.
All **38 tests pass** on Python **3.12.15** and **3.11.17** on macOS arm64.
Ruff and project validation pass. Both source and wheel distributions build,
and their packaged migrations match the source. A fresh extraction of the source
archive installs offline from the populated uv cache, passes all 38 tests, and
successfully runs `slr init`, `slr audit`, `slr status` and `slr report` against a
temporary empty project, without approving its protocol.
Regression coverage includes
whitespace-only evidence against abstracts, Markdown and unconverted PDFs;
retrieval attempts before attachment and rejected regressions after attachment;
and allowed/disallowed members of configured list variables.

The GitHub workflow adds Python 3.11/3.12 checks on Linux, macOS and Windows.
Those hosted runs remain pending until the repository is pushed. Optional
document/vector adapters and provider login have not been runtime-tested here.

## Original build record

The original build recorded validation on 2026-10-05 with Python 3.12.14 on Linux.
The supported Python floor is 3.11; Windows, macOS and Python 3.11 have not been
exercised in this build.

## Historical core checks

The following records describe earlier dependency versions. Use the current
[setup guide](../README.md) and [check commands](reproducibility.md) today.

In the original build, all **21 tests passed**. Ruff reported no remaining errors. Project validation
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

The table describes the original build, not every package in the current lockfile.
`uv.lock` now pins cross-platform dependency resolutions; `.python-version` selects
the default interpreter minor version. The legacy pip requirements still use compatible ranges.
For a real review, retain the lockfile and actual runtime details with your protocol,
project commit and export manifests.

## Checks that remain on your machine

The original build did not have OpenCode installed. A subsequent compatibility
check on 2026-10-05 used the installed OpenCode **2.0.23** on macOS:

- `opencode --version` returned `opencode v2.0.23`. The selector's original regex
  rejected the `v` prefix; detection now handles bare and prefixed versions,
  prerelease/build suffixes, ANSI colors and version output on stderr.
- `python scripts/select_opencode_config.py` successfully selected V2.
- `opencode debug config` loaded the project `opencode.json` and discovered
  the `.opencode` directory.
- `opencode debug agents` recognized `slr` with `mode: primary`.
- All **56 tests passed** on Python 3.12.15, including 18 selector tests for
  version parsing, command failures, unknown versions and profile backup behavior.
  Ruff and the 12-stage project/skill/command validation also passed.

The profile fields match the official [V2 agent configuration](https://opencode.ai/v2/docs/agents)
and [permission rules](https://opencode.ai/v2/docs/permissions).
V1 runtime loading, interactive skill execution, provider authentication, account
quotas and VS Code UI behavior remain unverified. No model request or scientific
approval was made as part of these compatibility diagnostics.

Docling, Chroma and SentenceTransformers are optional, lazy-loaded adapters.
They have not been installed or run against downloaded models here. Validate
conversion on representative PDFs, including tables, formulas and physical page
anchors, and evaluate retrieval using questions with known answers before relying
on those adapters for a review. The core tests do not establish their runtime
compatibility or scientific extraction accuracy.
