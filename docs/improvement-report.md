# Workbench improvement and validation record — 2026-10-16

## Verified baseline

Work continued in the existing checkout. It initially contained commit `2df7e5a`,
the synthetic software-testing protocol, and **no review database or search data**.
`status`, `audit` and `report` each returned exit code 1 with `Run slr init first`;
project validation passed. The user confirmed that the separate prosthesis/EMG
review does not exist on this machine and requested software work without it.

Before changing code, a supported backup was created and independently verified.
The clean checkout was fast-forwarded to the previously published `3c52955`, which
already contained the scientific API clients. Neither protocol nor workflow changed.
The starter database was then initialized mechanically, without approval or imports,
so subsequent state can be verified through supported commands.

| Measurement | Observed result |
| --- | --- |
| Imported search runs and archived searches | 0 |
| Imported records / deduplicated records | 0 / 0 |
| Submitted proposals / recorded human decisions | 0 / 0, all revisions and current revision |
| Pending pilot proposals / actionable paper-specific unclear cases | 0 / 0 |
| Retrieved / full-text assessed / included reports | 0 / 0 / 0 |
| Quality / extraction progress | No report pathways or approvals |
| Included studies | 0 |
| Audit | 0 events, 0 documents, 0 archived imports checked; SQLite integrity `ok` |
| Current protocol approval | Not approved |
| Scientific progress made during this task | None; no real review was available |

Counts come from `status`, `pending-review`, `pilot-evaluation`, `search-coverage`
and `audit`, not an LLM estimate. The protocol/workflow revision remains
`629f373449435155ec4b56e0802c06bdc4e0f81ad17075f512c744d2414229a0`.
No human approval, review, retrieval-status or study-link command was executed.

Local, Git-ignored outputs preserve the actual command results:

- `data/maintenance/validation-20261016T131336-89edea03/`: CLI JSON outputs, executed
  argument lists and SHA-256 manifest.
- `data/review-packages/pilot-f32cbc15310f/`: empty numbered-review package with
  explicit protocol/data blockers; this is not a completed screening pilot.
- `data/exports/629f37344943-0-1fd7e8a462ff/`: zero-count PRISMA data and table export.

These are local validation artifacts and are not published as research data.

## Prioritized findings and changes

1. **Unavailable review data blocks scientific work.** Historical arXiv Q1 and five
   capped OpenAlex runs cannot be inspected here. Their truncation, seed recall,
   false positives, pending recommendations and full-text candidates remain
   unverified. No historical total is reproduced or added together.
2. **Search retries previously lacked durable resume.** New v2 runs preserve native
   query definitions, physical request receipts, successful pages, cursor history,
   atomic checkpoints and immutable result snapshots. OpenAlex and arXiv pagination
   have fixture tests. A default anonymous plan does not load credentials or incur
   retrieval costs. Repeated pages/IDs fail explicitly; cursor handling is provider
   specific. New and resumed requests have explicit cumulative budgets.
3. **Human handoff was fragmented.** `pending-review`, `review-sheet` and
   `pilot-evaluation` now expose numbered targets, exact per-shell human commands,
   source evidence, unresolved questions, latest judgments and prerequisite gaps.
   Sheets default to 25 targets; rerunning resumes pending work. Independent
   reviewers get blind output until explicit human unblinding. Existing individual
   decision guards remain authoritative.
4. **DOI-only deduplication missed uncertain identities.** `duplicate-candidates`
   presents conservative title/source-ID/version hints, metadata differences and
   comparison limits. It never merges reports or links studies. Uncertain identity
   resolution remains a human investigation, with no new automatic merge service.
5. **CLI registration and presentation were intertwined.** The public CLI became
   a package with a separate parser; existing imports, commands and terminal guards
   remain. Archive storage/verification is shared by search and coverage. Integrity
   checks now also verify original imported bytes. No SQL migration was modified.
6. **Repeated reports replaced an earlier export folder.** Every report now creates
   a fresh folder and returns its path. Earlier snapshots remain intact. Count JSON
   remains deterministic for the selected revision and event cutoff.

[Project layout and compatibility](project-layout.md) documents the folder map,
entry points, generated-output locations and additive migration behavior. No
archived paper, source record, historical decision or configured data path moved.

## Track A: coverage completion strategy

**Executed:** archive/import inspection (no runs found), software tests, and an
arXiv dry-run plan. No live literature search or retrieval was performed.

**Proposed for the actual review:** restore the real protocol/database/artifacts,
then inventory individual runs with `search-coverage`. Preserve original pilots.
For v2 runs, review the query and request budget and resume without changing the
query. Legacy v1 pilots remain importable; start a separately identified new run
to continue their native query. Do not overwrite a historical run.

Complete pagination **before** importing a run: extending an already imported run
changes its byte signature and the existing idempotent import service will reject
it. Plan a separate new round when an imported pilot must be expanded. A refined
query is a new methodological choice and run ID; it does not complete the original.

Verify a small relevant seed set across the actual evidence streams using original
publications and recorded identifiers. `search-coverage --seeds <file>` measures
identifier recall against this declared set; it does not verify relevance. Inspect
missed seeds and false-positive patterns before deciding whether to complete or
formally refine a query. Provider totals overlap; never sum them as unique papers.
A relevance-ranked capped page is not a representative sample. Exhausting an API
query does not establish exhaustive literature coverage.

A seed JSON file contains an array of entries with a unique `id`, `doi` and/or
`source_ids` mapping provider/source names to identifier lists, `verified: true`,
and a nonempty `verification_note`. `evidence_stream` is optional and user-defined.
Only add genuine identifiers and independently verified relevance. No real seed
set was created or sensitivity score claimed during this task.

Consult [scientific search](scientific-search.md) for current provider documentation,
rate limits, authorization/cost opt-in, planning and resume commands. The updated
arXiv/resume paths are fixture-tested; they are not claimed as live-validated.

## Track B: screening and full-text pilot

**Executed:** existing-proposal inspection, generation of the empty review package,
read-only pilot evaluation and duplicate inspection. No new drafts were submitted.

**Pending:** actual pilot reviews, comparison with human decisions, boundary-case
analysis, representative full-text retrieval, anchored conversion inspection,
quality assessment and extraction-form evaluation. No eligible candidates exist
in this checkout; selecting papers to fill requested evidence categories would
invent review work. Missing data is a blocker, not an exclusion.

Once actual records are present, use the [pilot guide](review-pilot.md): inspect
existing recommendations, hand individual commands to the user, evaluate the
recorded pilot, then choose batch sizes according to capacity and ambiguity.
Attempt lawful public-source discovery for real human-advanced candidates before
asking the user for a PDF. Verify identity and originals, load `slr-read-pdf`, check
conversion/page anchors, then follow the configured full-text → quality → extraction
prerequisites and wait at every required human gate. Keep evidence streams,
populations, simulations and transfer/clinical conclusions distinct.

## Validation results

| Check | Result |
| --- | --- |
| Original active checkout `2df7e5a` | 128 tests passed; no baseline failures |
| Published `3c52955`, tested in an isolated source snapshot | 169 tests passed; no baseline failures |
| Updated complete test suite | 226 tests passed |
| Ruff `check src scripts tests` | Passed |
| Project validation | 12 stages and matching skills/commands; revision unchanged |
| Updated skill validation | Passed; project validation checks all skill metadata |
| Source/wheel build | Passed, offline with locked build backend |
| Packaged migrations and new CLI package | Passed; obsolete `cli.py` absent |
| Wheel-only CLI import/arXiv dry-run | Passed from the wheel archive |
| Active project launcher | `pending-review` smoke test passed |
| Status, audit, report, coverage and pilot inspection | Passed with the zero-count state above |

The 57 additional collected cases cover pagination/resume/interruption and budgets,
legacy imports and archive integrity, duplicate candidates, read-only/blind review
support, revision/consensus boundaries, CLI compatibility and preserved exports.
Existing exact-quotation, dependency, extraction missingness and human-gate tests
also pass. Tests use temporary synthetic databases, not the initialized starter DB.

Local execution used macOS arm64 and CPython 3.12.15 in an isolated environment.
The interpreter used for this validation came from a temporary test toolchain;
end-user guided setup still uses a separately installed compatible Python.
No Windows/Linux runtime or authenticated paid-provider integration was run here.
The CI matrix remains configured for supported platforms/Python versions; its hosted
results are not inferred from these local tests. Software validation is not
scientific validation, proof of independent review or a guarantee against every
hardware failure. Use verified backups with a separate storage copy.

## Reproduce and hand off

From the project root with the environment activated:

```sh
python scripts/validate_project.py
python -m ruff check src scripts tests
python -m pytest -q
python -m slr_workbench status
python -m slr_workbench audit
python -m slr_workbench search-coverage
python -m slr_workbench pending-review --limit 25
python -m slr_workbench pilot-evaluation
```

The human's next scientific step is to restore or configure the actual review,
not approve the synthetic example as if it were the missing review. After editing
its protocol/workflow, initialize the revision and personally run its approval in
a separate interactive terminal:

```sh
python -m slr_workbench init
python -m slr_workbench approve-protocol --reviewer REVIEWER_ID
```

Replace `REVIEWER_ID` with the identity configured in that actual protocol. Later,
`review-sheet --reviewer REVIEWER_ID` supplies the exact existing proposal-specific
review commands. No commands are fabricated for papers or proposals absent here.
