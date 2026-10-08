# Detailed installation and workflow reference

For the shorter recommended path, start with the [README](../README.md).
This reference includes manual setup, optional adapters and the synthetic walkthrough.

## What you will install

| Component | Purpose | Required? |
| --- | --- | --- |
| Git | Download and update the project | Yes for the clone instructions |
| uv 0.12.23 | Install locked dependencies | Yes for this tutorial |
| Python 3.12 | Run the workbench | Install separately; python.org on Windows/macOS |
| OpenCode | Run the agent and stage skills | Yes for AI-assisted review |
| VS Code and PDF Viewer | Edit configuration and inspect original PDFs | Optional |
| Docling | Convert PDFs into Markdown and structured text | Optional |
| Chroma and embedding model | Search included papers semantically | Optional |

The Python core requires Python 3.11 or newer. The repository pins its default
Python minor version in `.python-version`, uv in `pyproject.toml`, and dependencies in `uv.lock`.
No direct LLM API client or OpenRouter dependency is required by the Python core.
An internet connection is needed for the initial downloads and hosted providers.

## 1. Install tools for your platform

Choose **one** platform below. Skip tools already installed, but verify their
versions. These commands install external tools; they are not project commands.
Use the linked official instructions if an organization manages your software.

### macOS — Terminal (zsh or bash)

Install Git through Apple's command-line tools if `git --version` fails:

```sh
xcode-select --install
```

Install Python 3.12 using the signed macOS installer from
[python.org](https://www.python.org/downloads/release/python-31210/).
Verify `python3 --version` reports 3.12. If it does not, use the setup script to find a compatible installed interpreter. Finish the installation dialogs before continuing. Install the pinned uv version
and the OpenCode V2 version used for the project's compatibility check:

```sh
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | sh
curl -fsSL https://opencode.ai/v2/install | bash -s -- --version 2.0.23
```

Close and reopen Terminal so the installer PATH changes take effect, then check:

```sh
git --version
uv --version
opencode --version
```

For VS Code, follow the [macOS installation guide](https://code.visualstudio.com/docs/setup/mac).
To enable `code` in Terminal, open VS Code's Command Palette and run
**Shell Command: Install 'code' command in PATH**, then reopen Terminal.

### Linux — bash (Ubuntu/Debian example)

Install Git and the download utilities:

```sh
sudo apt update
sudo apt install -y git curl ca-certificates tar
# Ubuntu 24.04 provides Python 3.12:
sudo apt install -y python3.12 python3.12-venv
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | sh
curl -fsSL https://opencode.ai/v2/install | bash -s -- --version 2.0.23
```

Close and reopen the terminal, then verify:

```sh
git --version
uv --version
opencode --version
```

On another distribution, install Python 3.12 with venv support (from the distribution
or build an official python.org source release), Git, curl, CA certificates and tar with its
package manager before running the two installers. For optional VS Code setup,
follow the [Linux installation guide](https://code.visualstudio.com/docs/setup/linux).

### Windows — PowerShell

First install Python 3.12 from the official
[python.org release page](https://www.python.org/downloads/release/python-31210/),
including the Python launcher. Verify `py -3.12 --version`. Python 3.12.10 is the
last 3.12 release with official Windows/macOS installers; later 3.12 security
releases are source-only. This installer choice is not a claim that 3.12.10
contains later security fixes.

Install Git and, optionally, VS Code using Windows Package Manager:

```powershell
winget install --id Git.Git --exact --source winget
winget install --id Microsoft.VisualStudioCode --exact --source winget
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/0.12.23/install.ps1 | iex"
```

The execution-policy option applies to that installer process; this tutorial does
not require changing the system-wide PowerShell policy or activating a `.ps1` file.
If `winget` is unavailable, use the official [Git](https://git-scm.com/downloads/win)
and [VS Code](https://code.visualstudio.com/docs/setup/windows) installers.

For **OpenCode V2**, use the standalone Windows CLI binary linked in the
[official V2 installation page](https://opencode.ai/v2/docs). Choose x64 or ARM64
for the machine; an x64 baseline build is also offered. The V2 documentation
currently does not support Windows package-manager installation.

Create a destination folder:

```powershell
$OpenCodeDir = Join-Path $env:LOCALAPPDATA "Programs\OpenCode"
New-Item -ItemType Directory -Force -Path $OpenCodeDir
explorer.exe $OpenCodeDir
```

Extract the downloaded archive and copy `opencode.exe` into that folder. Add it
to the user PATH once, using the same PowerShell window:

```powershell
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($UserPath -split ';') -notcontains $OpenCodeDir) {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$OpenCodeDir", "User")
}
```

Close and reopen PowerShell, then verify:

```powershell
git --version
uv --version
opencode --version
```

If using WSL instead, follow the Linux instructions entirely inside WSL and keep
its Python environment separate from the native Windows environment.

**Checkpoint:** `uv --version` should report `0.12.23`, and `opencode --version`
should print an installed version. The selector supports OpenCode major versions
1 and 2; the supplied profile defaults to V2. Do not continue with missing commands.
Installer references: [uv](https://docs.astral.sh/uv/getting-started/installation/)
and [OpenCode V2](https://opencode.ai/v2/docs).

## 2. Download the project

In your terminal, choose a parent folder for the project. Copy this repository's
HTTPS clone URL from GitHub's **Code** button and replace `REPOSITORY_URL` below.
The commands work in macOS/Linux shells and Windows PowerShell:

```sh
git clone REPOSITORY_URL slr-workflow
cd slr-workflow
```

If the project is already downloaded, simply open a terminal in its root folder.
You should see `README.md`, `protocol.yaml`, `workflow.yaml` and `pyproject.toml`.
Run all subsequent terminal commands from that folder. Use a fresh checkout for
the synthetic demonstration so it cannot mix with a real review's database.

## 3. Install Python and the workbench

Create the virtual environment with the separately installed Python. If migrating
an existing environment, follow [the Windows migration guide](windows-setup.md)
first; an existing uv-managed environment will not change its base interpreter.

macOS/Linux:

```sh
python3 -c "import sys; assert sys.version_info[:2] == (3, 12), 'Select Python 3.12 first'"
python3 -m venv .venv
uv sync --locked --extra pdf --extra dev --python .venv/bin/python
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
uv sync --locked --extra pdf --extra dev --python .venv\Scripts\python.exe
```

Then, on every platform:

```sh
uv run --no-sync python --version
uv run --no-sync python -m slr_workbench --help
uv run --no-sync python scripts/validate_project.py
uv run --no-sync python -m pytest -q
```

The project disables uv-managed Python downloads and requests a system interpreter.
`--locked` refuses to silently change dependency resolutions. The core installs
Rich and PyYAML; `dev` adds pytest and `pdf` adds the lightweight PDF reader. Validation uses standard-library dataclasses
and the CLI uses argparse. No Typer or Pydantic is required for the core.
PyYAML uses its Python `SafeLoader` through `yaml.safe_load`.

Throughout this tutorial, **`uv run --no-sync` uses the installed environment**
without removing optional packages. No shell activation is needed. On Windows,
`.\.venv\Scripts\python.exe -m slr_workbench --help` also works directly.
`python -m` avoids the generated `slr.exe` and
`pytest.exe` launchers. The legacy `slr` command remains available.

After changing dependencies, explicitly sync all desired extras again. Ruff is
optional locally: install with `uv sync --locked --extra pdf --extra dev --extra lint`, then
run `uv run --no-sync python -m ruff check src scripts tests`, or leave linting to CI.
Legacy `requirements*.txt` are pip entry points with ranges, not locked installs.

## 4. Set up the editor and PDF viewer (optional)

With the `code` command installed, run:

```sh
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension mathematic.vscode-pdf
code .
```

Alternatively, open the folder through VS Code's **File > Open Folder**, open
Extensions and search `@recommended`. Install Python, Pylance and
[PDF Viewer](https://marketplace.visualstudio.com/items?itemName=mathematic.vscode-pdf)
(the viewer requires VS Code 1.95+).

Run **Python: Select Interpreter** from the Command Palette and select `.venv`.
Its interpreter is `.venv/bin/python` on macOS/Linux or
`.venv\Scripts\python.exe` on Windows. Use **Terminal > New Terminal** for the
commands below. The PDF extension displays originals; it does not extract text,
perform OCR or install Docling.

## 5. Configure OpenCode and select a model

In the terminal:

```sh
uv run --no-sync python scripts/select_opencode_config.py
uv run --no-sync opencode
```

The selector chooses the V1 or V2 project profile from the installed version,
including output such as `opencode v2.0.23`. Run it before customizing
`opencode.json`: selecting a different profile backs up the previous file as
`opencode.previous.json` and replaces the project configuration. Provider
credentials are managed by OpenCode outside this repository.

Now enter these commands **inside OpenCode**, one at a time:

```text
/connect
/models
```

Connect an available provider using its supported authentication, then choose a
model from the picker. Availability and quotas depend on the provider. No model is
hard-coded in the project; its skills inherit the session selection. See the
[OpenCode model guide](https://opencode.ai/v2/docs/models) and
[provider notes](providers.md).

The project already supplies `AGENTS.md`, skills and slash commands; an OpenCode
`/init` is unnecessary. Keep this terminal for agent work and open a **second
terminal in the project root** for human review commands. Starting OpenCode through
uv lets its shell tools use the environment’s `python -m slr_workbench` command.

## 6. Customize and approve the scientific protocol

Open these files before importing any papers:

| File | What to configure |
| --- | --- |
| `protocol.yaml` | Topic, questions, sources, criteria, reviewer identities, quality checklist, extraction variables and synthesis plan |
| `workflow.yaml` | Stage IDs, semantic roles, prerequisites and associated skills |

For a demo, retain the synthetic topic and sources. For real research, replace
them. Set `reviewers.identities` to the actual reviewer labels to use; the generic
placeholder `REVIEWER_ID` below must match one of those labels.

OpenCode can help draft amendments with `/slr-protocol`. Review any proposed file
changes yourself. After editing either configuration file, run in the second terminal:

```sh
uv run --no-sync python -m slr_workbench init
uv run --no-sync python -m slr_workbench approve-protocol --reviewer REVIEWER_ID
uv run --no-sync python -m slr_workbench status
uv run --no-sync python -m slr_workbench audit
```

`init` creates the database and registers the exact configuration revision.
`approve-protocol` shows the configuration, asks for a reason and requires explicit
human confirmation. Run it interactively yourself; do not pipe responses or ask an
agent to approve. Later protocol/workflow edits require another `init` and approval;
past decisions stay in history and are not silently reused for the new revision.

**Ready checkpoint:** the CLI and tests work, OpenCode can use a selected model,
and the current protocol is approved. The database can still contain zero papers;
installation does not import research data automatically.

## 7. Practice with the synthetic records

Only use this section in a separate demo checkout with the example sources still
configured. The fixture DOIs and papers are fictional and must never be cited.

In the human terminal:

```sh
uv run --no-sync python -m slr_workbench import-records examples/records.json --run-id demo-search-001 --source demo-database --query "synthetic demonstration" --searched-at "2026-10-05T00:00:00+00:00"
uv run --no-sync python -m slr_workbench deduplicate
uv run --no-sync python -m slr_workbench records
uv run --no-sync python -m slr_workbench status
```

Expect three source records, one exact DOI duplicate, and two records pending
screening. Repeating the same import with identical content and run ID adds zero
records. Real imports use recorded JSON/CSV exports, a configured source ID, the
actual search query and a timestamp with timezone. Live academic API search is
not implemented in this iteration.

Copy a retained record's `id` and `report_id` from `slr records`. Replace
`RECORD_ID`, `REPORT_ID` and `PROPOSAL_ID` in subsequent commands with actual IDs.
The record identifies a search result; the report identifies its publication.

Inside OpenCode:

```text
/slr-screen RECORD_ID
```

Ask it to follow the configured record-screening role, submit the evidence-backed
draft with `slr submit`, and return its proposal ID. In the human terminal:

```sh
uv run --no-sync python -m slr_workbench review PROPOSAL_ID --reviewer REVIEWER_ID
```

Inspect the evidence, choose accept/modify/defer and explicitly confirm saving.
The proposal alone changes no eligibility. Use `--decision-file PATH` with a
complete revised draft JSON if changing values or evidence. Continue to full-text
assessment only for a record with an effective human inclusion decision.

## 8. Attach full text: Markdown demo or real PDF

### Markdown demonstration — no converter required

Attach the synthetic text to the included demo report:

```sh
uv run --no-sync python -m slr_workbench attach REPORT_ID examples/full-text.md --kind markdown
```

This is sufficient to practice the next review stages. Markdown prepared by
another converter can also be attached with `--kind markdown`.

### Real PDF — archive, read and convert

**Optional adapters have a different dependency footprint.** Docling and Chroma
can install Pydantic, Typer and native libraries transitively. They are outside
the simplified core and have not been verified against Windows Defender. For
the minimal installation, attach verified Markdown from another converter.

First import the paper's bibliographic record and complete title/abstract
screening. Copy the actual report ID from `slr records`. Replace the quoted PDF
path with a real local path, keeping quotes around paths containing spaces.

macOS/Linux:

```sh
uv run --no-sync python -m slr_workbench attach REPORT_ID "/path/to/paper.pdf" --kind pdf
uv sync --locked --extra pdf --extra dev --extra documents
uv run --no-sync python -m slr_workbench convert REPORT_ID "/path/to/paper.pdf"
```

Windows PowerShell:

```powershell
uv run --no-sync python -m slr_workbench attach REPORT_ID "C:\path\to\paper.pdf" --kind pdf
uv sync --locked --extra pdf --extra dev --extra documents
uv run --no-sync python -m slr_workbench convert REPORT_ID "C:\path\to\paper.pdf"
```

The original is archived under `data/artifacts/REPORT_ID/`. Open that PDF in
VS Code or another PDF reader. `attach --kind pdf` archives bytes only;
`convert` uses Docling to create Markdown and structured JSON with source anchors.
Docling also archives the original if it has not already been attached.

Full-text review operates on **extracted text**, not the PDF viewer. Verify
important quotations, tables and formulas against the original. Manually prepared
Markdown may use verified physical-page markers such as `<!-- page: 1 -->`;
do not invent page numbers. Structured Docling elements retain anchors where
available. Optional conversion dependencies/models can be large and may download
weights. This adapter has not been runtime-tested against downloaded models in
this build; evaluate it on representative papers before relying on its output.
Conversion failure is an operational issue, not an eligibility exclusion.

## 9. Review, extract and export

Use these commands **inside OpenCode**, one stage at a time:

```text
/slr-full-text REPORT_ID
/slr-quality REPORT_ID
/slr-extract REPORT_ID
```

After **each** stage returns a proposal, stop and review it in the human terminal:

```sh
uv run --no-sync python -m slr_workbench review PROPOSAL_ID --reviewer REVIEWER_ID
```

Do not start a dependent stage until its required approvals are effective.
These commands follow the current role mappings in `workflow.yaml`; renamed
stages must keep their configured role and criterion references consistent.

After verifying that a report represents an underlying study, link it yourself.
Replace `STUDY_ID` and the label with meaningful identifiers for that investigation;
multiple publications can belong to the same study:

```sh
uv run --no-sync python -m slr_workbench link-study REPORT_ID STUDY_ID --label "Study label" --reviewer REVIEWER_ID
uv run --no-sync python -m slr_workbench status
uv run --no-sync python -m slr_workbench report
uv run --no-sync python -m slr_workbench audit
```

`report` prints an export directory under `data/exports/`, containing count JSON,
screening/summary CSV, a LaTeX table and a hash manifest. Approved extraction feeds
the summary; pending or unclear decisions remain visible. PRISMA count data does
not replace the full reporting checklist or certify methodological quality.

If a report cannot be obtained, record that separately from scientific exclusion:

```sh
uv run --no-sync python -m slr_workbench retrieval REPORT_ID not_retrieved --reviewer REVIEWER_ID --reason "Describe the actual retrieval attempts"
```

This human-only command applies before full text is attached. To correct a study
association, use `slr unlink-study` with the report ID, study ID, reviewer and reason;
the original event remains in the audit history.

## 10. Optional semantic search

Literal search needs no additional dependencies and returns text from included
publications:

```sh
uv run --no-sync python -m slr_workbench search-corpus "phrase present in an included paper"
```

To install both optional adapters while retaining development tools:

```sh
uv sync --locked --extra pdf --extra dev --extra documents --extra rag
uv run --no-sync python -m slr_workbench index-corpus
uv run --no-sync python -m slr_workbench retrieve "What evaluation methods were used?"
```

Index only after papers have effective inclusion decisions and extracted text.
Configure embeddings and chunking in `rag.yaml`, conversion in `conversion.yaml`.
Rebuild the index after changes to the corpus or retrieval configuration.
Semantic search requires additional downloads and has not been runtime-tested
against downloaded models here. A dependency lockfile does not pin remote model
weights. If a later `uv sync` omits an extra, its packages may be removed: repeat
all desired extras when syncing, and use `uv run --no-sync` between changes.

## Resume work later

Open two terminals in the project root. In the first:

```sh
uv run --no-sync opencode
```

Select the provider/model as needed and use the appropriate stage command. In
the second:

```sh
uv run --no-sync python -m slr_workbench status
uv run --no-sync python -m slr_workbench audit
```

Continue reviewing proposals there. Do not reimport records under new run IDs or
reapprove an unchanged protocol merely to resume. Back up `data/`, configuration,
lockfile and the project commit for reproducibility. `data/` is ignored by Git:
pushing the source repository does not back up the review database or PDFs.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `uv`, `git`, `opencode` or `code` not found | Reopen the terminal after installation and check the appropriate platform's PATH instructions. `code` is optional. |
| Wrong uv version | Reinstall uv 0.12.23 using step 1; the project enforces that version. |
| `slr` not found | Use `uv run --no-sync python -m slr_workbench ...` from the project root after syncing. |
| Python 3.9 or missing Python packages | Create `.venv` with the installed Python 3.12 as in step 3, then sync dependencies. |
| Configuration changed / approval required | Run `slr init` through uv, inspect the changes and approve the new revision yourself. |
| Unsupported OpenCode version | Check `opencode --version`. Profiles support V1/V2; override with `--major 1` or `--major 2` only after verifying the installed major version. |
| No model available | Connect an available provider with `/connect`, then choose from `/models`. |
| A review stage is blocked | Read the prerequisite error and `slr status`; obtain the required human decisions first. |
| PDF attached but no readable evidence | Convert it with Docling or attach verified Markdown. Installing a PDF viewer does not extract text. |
| Docling/Chroma import error | Sync the required extras again; keep the extras on subsequent sync commands. |
| Human command refuses piped input | Run it yourself in a separate interactive terminal. |

## Each stage is a skill

| Slash command | Stage |
| --- | --- |
| `/slr-protocol` | Protocol design, evaluation and amendments |
| `/slr-search` | Search strategy and recorded imports |
| `/slr-deduplicate` | Exact duplicate handling and ambiguous-match review |
| `/slr-screen` | Title/abstract screening drafts |
| `/slr-retrieve` | Full-text acquisition, archive and processing |
| `/slr-full-text` | Full-text eligibility drafts |
| `/slr-quality` | Methodological quality drafts |
| `/slr-extract` | Typed extraction with evidence |
| `/slr-corpus` | Evidence retrieval and conversational answers |
| `/slr-synthesize` | Synthesis and threats to validity |
| `/slr-report` | Tables, count data and PRISMA checklist coverage |
| `/slr-audit` | Resume/audit and reproducibility checks |

Each skill is editable at `.opencode/skills/<name>/SKILL.md`; each command is
editable at `.opencode/commands/<name>.md`. The common instructions are in
`AGENTS.md`. Read [customization](customization.md) for extension contracts.

## Project map

| Path | Purpose |
| --- | --- |
| `protocol.yaml`, `workflow.yaml`, `conversion.yaml`, `rag.yaml` | Editable scientific protocol, stage graph, conversion and optional retrieval settings |
| `opencode.json`, `config/` | Current and version-specific OpenCode profiles |
| `.opencode/skills/`, `.opencode/commands/` | Stage instructions and slash commands |
| `.vscode/` | Tasks, interpreter settings and debugging entry points |
| `src/slr_workbench/` | Typed configuration, services, CLI, reporting and optional integrations |
| `src/slr_workbench/migrations/` | Versioned SQLite schema |
| `schemas/` | Generated dataclass JSON contracts |
| `scripts/` | Initialization, profile selection and project validation |
| `uv.lock`, `.python-version`, `.github/workflows/ci.yml` | Locked dependencies, default Python and automated core checks |
| `tests/`, `examples/` | Meaningful invariants and synthetic fixtures |
| `docs/` | Architecture, customization, evidence contracts and reporting coverage |
| `data/` | Local review database, originals, drafts, derived text and exports; created at runtime |

## Scope and further documentation

Implemented: recorded manual imports, exact DOI deduplication, evidence validation,
draft submission and human review, full-text attachment, quality/extraction,
study links, count/table exports, literal retrieval and audit.

Live academic API clients, fuzzy merge/reversal, rendered PRISMA diagrams,
updated-review carry-forward and statistical meta-analysis remain future work.
An LLM is not an independent human reviewer. Keep missingness and disagreements
explicit and validate the scientific interpretation of evidence.

For development checks and packaging (omit local linting if Ruff is blocked):

```sh
uv sync --locked --extra pdf --extra dev --extra lint
uv run --no-sync python scripts/validate_project.py
uv run --no-sync python -m ruff check src scripts tests
uv run --no-sync python -m pytest -q
uv build
uv run --no-sync python scripts/validate_distribution.py
```

The sync command installs both test and lint extras. CI is configured
for Linux, macOS and Windows; consult actual workflow results before claiming a
platform passed. The platform installers in this tutorial are based on upstream
instructions, not an end-to-end installation test on every operating system.

- [Customization and extension contracts](customization.md)
- [Draft and evidence contract](draft-contract.md)
- [Architecture and scientific state](architecture.md)
- [Validation record and limits](testing.md)
- [Reproducibility and publishing](reproducibility.md)
- [PRISMA checklist coverage](prisma-checklist.md)
