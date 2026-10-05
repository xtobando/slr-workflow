# Validation record — iteration 1

## Current regression validation

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

## Reproduce the core checks

```sh
uv sync --locked --extra dev
uv run --locked --extra dev python scripts/validate_project.py
uv run --locked --extra dev ruff check src scripts tests
uv run --locked --extra dev pytest -q
uv build
uv run --locked --extra dev python scripts/validate_distribution.py
```

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
`uv.lock` now pins cross-platform dependency resolutions; `.python-version` pins
the default interpreter. The legacy pip requirements still use compatible ranges.
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
