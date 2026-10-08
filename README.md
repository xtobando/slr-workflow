# SLR OpenCode Workbench

A local systematic literature review workspace: **OpenCode helps read and draft;
Python validates evidence and stores an audit trail; you approve scientific decisions.**
The example protocol is synthetic. Customize it before using real papers.

[Install](#install) · [Connect a model](#connect-a-model) · [Read a PDF](#read-a-pdf-at-any-stage) · [Review workflow](#prepare-your-review) · [Troubleshooting](#troubleshooting)

## Install

You need **Python 3.12** installed separately, an internet connection for initial
downloads, and **OpenCode** for model-assisted work. Use Python from python.org on
Windows/macOS; Linux users can use a distribution-provided Python 3.12 with venv
support. See [platform installation commands](docs/installation.md#1-install-tools-for-your-platform)
for Python and OpenCode. Git and VS Code are optional.

1. On GitHub choose **Code → Download ZIP**, then extract the entire archive.
   Alternatively, clone this repository.
2. Open a terminal in the extracted project folder.
3. Run the setup command for your platform:

| Windows PowerShell | macOS / Linux Terminal |
| --- | --- |
| `powershell -File scripts/setup.ps1` | `bash scripts/setup.sh` |

If PowerShell scripts are blocked, run `py -3.12 scripts/setup.py` instead.
For a specific Windows interpreter, use
`powershell -File scripts/setup.ps1 -PythonPath "C:\path\to\python.exe"`.

Setup detects an available Python command and verifies version 3.12; it does not
require the executable to be named `python3.12`. Set `SLR_PYTHON` to select an
explicit interpreter path. Setup installs pinned uv locally, creates `.venv`, installs locked dependencies
including the lightweight PDF reader and pytest, and checks the project. No global
uv installation or environment activation is required. Compatible environments
and optional packages are retained; incompatible environments cause setup to stop
with instructions. Setup never deletes review data or approves your protocol.

**Success:** setup prints `Core setup complete` and your next commands.
Rerun the same setup command after downloading a project update. Keep your existing
`data/`, customized configuration and credentials outside any replacement checkout.

## Everyday commands

Use the project launcher from the project folder:

| Task | Windows | macOS / Linux |
| --- | --- | --- |
| Show available helpers | `.\workbench.ps1 help` | `bash workbench.sh help` |
| List SLR commands | `.\workbench.ps1 cli --help` | `bash workbench.sh cli --help` |
| Select OpenCode profile | `.\workbench.ps1 configure` | `bash workbench.sh configure` |
| Start OpenCode | `.\workbench.ps1 opencode` | `bash workbench.sh opencode` |
| Run tests | `.\workbench.ps1 test -q` | `bash workbench.sh test -q` |
| Read a PDF | `.\workbench.ps1 read-pdf "paper.pdf"` | `bash workbench.sh read-pdf "paper.pdf"` |
| Check review status | `.\workbench.ps1 status` | `bash workbench.sh status` |

All scientific CLI subcommands and options work after the launcher. The launcher
selects the local environment and project root and preserves the interactive
terminal for human decisions. If PowerShell scripts are blocked, the equivalent is:

```powershell
.\.venv\Scripts\python.exe scripts/workbench.py status
```

The underlying CLI remains available:

```powershell
# Windows
.\.venv\Scripts\python.exe -m slr_workbench --help
```

```sh
# macOS/Linux
.venv/bin/python -m slr_workbench --help
```

## Connect a model

Install OpenCode if needed, run the launcher's `configure` command once, then
`opencode`. Profile selection detects OpenCode V1/V2 and can replace project
`opencode.json`, backing up a changed profile. Run it before custom profile edits.

Inside OpenCode:

```text
/connect
/models
```

Connect your provider and choose a model. Credentials remain in OpenCode's own
storage; the project does not require OpenRouter or store account tokens.
Use the installed model picker rather than guessing provider/model IDs.
See [provider details](docs/providers.md).

## Read a PDF at any stage

Inside OpenCode, use the new skill command:

```text
/slr-read-pdf "path/to/paper.pdf"
```

Or run `read-pdf "path/to/paper.pdf"` through the project launcher. This works
before protocol approval, before importing records, or during any review stage.
It requires no report ID and does not change inclusion decisions or review counts.

Each conversion creates a folder under `data/reading/` containing:

- `original.pdf`: an archived copy of the source.
- `document.md`: extracted text with physical page markers.
- `manifest.json`: source/output hashes, converter version and missing-page warnings.

OpenCode reads the Markdown to answer your question. It treats document content
as data, not instructions. For long PDFs, it reads relevant pages in chunks.
The lightweight [pypdf reader](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
extracts embedded text; it does not perform OCR or guarantee table/column/formula
layout. Scans can produce no text and require a separate OCR conversion. The skill
reports this instead of claiming it read missing content.

For formal evidence, associate the original and verified Markdown with the correct
registered report using `attach`, following existing workflow prerequisites.
Reading a PDF alone does not import it into your review.
See [PDF reading and evidence](docs/pdf-reading.md) for commands and limitations.

## Prepare your review

1. Edit `protocol.yaml`: research questions, criteria, sources, reviewers and variables.
2. Review `workflow.yaml`: stage roles, prerequisites and skills.
3. In a **separate human-operated terminal**, run the commands below. Replace
   `REVIEWER_ID` with a configured reviewer identity.

```powershell
# Windows
.\workbench.ps1 init
.\workbench.ps1 approve-protocol --reviewer REVIEWER_ID
.\workbench.ps1 status
```

```sh
# macOS/Linux
bash workbench.sh init
bash workbench.sh approve-protocol --reviewer REVIEWER_ID
bash workbench.sh status
```

Read and confirm the protocol yourself. Protocol/workflow changes require a new
revision and approval; historical decisions remain stored. An LLM is not an
independent human reviewer.

## Work through a review

| Step | OpenCode skill / Python operation | Human responsibility |
| --- | --- | --- |
| Import recorded search exports | `/slr-search`, `import-records` | Check sources, queries and search dates |
| Deduplicate | `/slr-deduplicate`, `deduplicate` | Inspect exact DOI matches |
| Screen title/abstract | `/slr-screen RECORD_ID` | `review PROPOSAL_ID --reviewer REVIEWER_ID` |
| Obtain full text | `/slr-retrieve`, `/slr-read-pdf PATH` | Verify identity, originals and text |
| Assess full text | `/slr-full-text REPORT_ID` | Review the submitted proposal |
| Assess quality and extract | `/slr-quality REPORT_ID`, `/slr-extract REPORT_ID` | Review each proposal before the next dependent stage |
| Synthesize and export | `/slr-synthesize`, `/slr-report`, `report`, `audit` | Resolve disagreements and check conclusions |

Slash commands run inside OpenCode; Python operations run through the launcher.
The skills follow the current configured roles. Importing, reading and draft
submission do not themselves establish eligibility. Retrieval failures remain
separate from scientific exclusions. Approval, review, retrieval-status and
study-link decisions remain interactive human operations.

For a complete practice run, use the [synthetic walkthrough](docs/installation.md#7-practice-with-the-synthetic-records)
in a separate checkout. For later sessions, start OpenCode and check `status`;
do not reimport records merely to resume work.

## Optional tools

- **VS Code:** open the project folder, install its recommended Python/Pylance/PDF
  Viewer extensions, and select `.venv`. A PDF viewer displays originals; it does
  not extract text. [Editor setup](docs/installation.md#4-set-up-the-editor-and-pdf-viewer-optional).
- **Docling:** optional OCR/structured conversion for registered reports.
- **Chroma:** optional semantic retrieval over included publications.
- **Ruff:** optional local linting; CI also runs it.

Install extras through the launcher's `uv` helper. For example, on macOS/Linux:

```sh
bash workbench.sh uv sync --locked --extra dev --extra pdf --extra documents
```

On Windows replace `bash workbench.sh` with `.\workbench.ps1`. Keep every desired
extra in a sync command; an exact sync may remove omitted packages. Docling/Chroma
can reintroduce Pydantic and native dependencies. Their model downloads, extraction
quality and Windows Defender compatibility are not established by core tests.

## Troubleshooting

| Problem | Next step |
| --- | --- |
| Python 3.12 not found | Install it separately using the [platform guide](docs/installation.md#1-install-tools-for-your-platform). |
| Existing environment uses another Python | Follow the [environment migration guide](docs/windows-setup.md); setup will not replace it automatically. |
| OpenCode not found | Install OpenCode, reopen the terminal, run `configure`, then `opencode`. |
| PDF reader missing | Rerun guided setup to install the locked `pdf` extra. |
| Empty or incomplete PDF text | Check manifest warnings and original pages; obtain OCR/text for scans. |
| Scientific command blocked | Check `status` and complete the required human approvals. |
| Defender blocks a file | Use the migration guide and record the exact detection/path; no setup command disables Defender. |

## Backups and updates

The launcher now makes verified backups before and after OpenCode sessions and
review-writing commands. Default location: a `PROJECT-backups` folder beside the
project. Set `SLR_BACKUP_DIR` to use another drive or a synced folder. Backups stay
local unless you configure such storage; no archive is uploaded automatically.

| Task | macOS/Linux command (Windows: replace `bash workbench.sh` with `.\workbench.ps1`) |
| --- | --- |
| Back up now | `bash workbench.sh backup` |
| Verify an archive | `bash workbench.sh backup-verify "/path/to/backup.zip"` |
| Restore into a new folder | `bash workbench.sh restore "/path/to/backup.zip" "../recovered-review"` |
| Check upstream for updates | `bash workbench.sh update --check` |
| Prepare a tested update separately | `bash workbench.sh update --destination "../updated-review"` |

Git checkouts now prepare updates automatically after successful OpenCode sessions
and activate a verified, unchanged candidate on the next startup. Keep using the
original launcher: all commands follow the active version. If either review copy
changes, activation is canceled to preserve that work. Protocol/workflow or SQL
migration changes require manual review.

Use `auto-update status`, `auto-update disable`, `auto-update enable` or
`auto-update rollback` after the launcher. Rollback refuses if work has changed
since activation; the old folder and backups remain available for recovery.
Updates require a Git clone and never replace the active project in place.
Close other writers before preparing an update. See the [recovery guide](docs/recovery.md)
for off-device copies, snapshot coverage, exclusions, restore checks and switching
to an updated copy. Snapshot boundaries do not protect unsaved work or every action
inside a long-running session; keep periodic backups and a separate storage copy.

## Files, backups and further reading

`data/` contains the local SQLite review, archived papers and exports. It is ignored
by Git: publishing the repository does **not** back up review data. Preserve it,
your configuration, project commit and export manifests in an appropriate archive.

- [Detailed installation and synthetic tutorial](docs/installation.md)
- [PDF reading and evidence](docs/pdf-reading.md)
- [Customization](docs/customization.md) · [Draft contract](docs/draft-contract.md)
- [Reproducibility](docs/reproducibility.md) · [Validation record](docs/testing.md)
- [Architecture](docs/architecture.md) · [PRISMA coverage](docs/prisma-checklist.md)

Current scope includes manual imports, exact DOI deduplication, human-reviewed
drafts, attachments, quality/extraction, study links, exports, literal search and
audit. Live academic APIs, fuzzy deduplication resolution, rendered PRISMA diagrams
and meta-analysis remain future extensions.
