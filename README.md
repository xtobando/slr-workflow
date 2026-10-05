# SLR OpenCode Workbench — iteration 1

An English, local, editable systematic literature review project for VS Code.
OpenCode runs the LLM and loads a skill for each review stage. Python validates
evidence, records proposals/decisions in SQLite and calculates reporting data.
No OpenRouter or direct LLM API dependency is required by the Python core.

This iteration is a working foundation, with synthetic fixtures to exercise the
workflow. Replace the illustrative protocol before using real research data.
It assists a Kitchenham-style review and PRISMA reporting; it does not certify
methodological quality or complete the PRISMA checklist automatically.

## Start in VS Code

1. Open this folder as a VS Code workspace. Install the workspace's recommended
   extensions: Python, Pylance and
   [PDF Viewer](https://marketplace.visualstudio.com/items?itemName=mathematic.vscode-pdf)
   (`mathematic.vscode-pdf`, requires VS Code 1.95+). In Extensions, search
   `@recommended` to find the workspace recommendations. The PDF viewer lets you
   open archived papers directly in VS Code; it is installed separately from
   Python dependencies and does not convert documents for the workflow.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) **0.12.23**.
   The project pins that tool version in `pyproject.toml`, Python **3.12.15** in
   `.python-version`, and dependency versions and hashes in `uv.lock`.
   uv downloads the supported Python automatically; the macOS system Python 3.9
   is not sufficient to run this project.
3. Install the locked core, select `.venv` with **Python: Select Interpreter**,
   activate it in the integrated terminal, and initialize:

```sh
uv sync --locked
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell alternative: .venv\Scripts\Activate.ps1
# Windows cmd alternative: .venv\Scripts\activate.bat
slr init
```

On Windows, if PowerShell blocks activation scripts, use a cmd terminal or select
the environment interpreter in VS Code and run the included process tasks.
Changing the global PowerShell execution policy is unnecessary for this project.
Alternatively, run commands through `uv run --locked slr ...` without activation.
If you already have an incompatible `.venv`, preserve anything you need from it
before syncing: uv can recreate it using the pinned Python version.

For development, use `uv sync --locked --extra dev` and retain `--extra dev` on
`uv run` commands so the test tools stay installed. The legacy `requirements*.txt`
files remain available for pip users with Python 3.11+, but those range-based
installs do not reproduce the lockfile.

4. Edit `protocol.yaml`: review topic, criteria, sources, reviewer identities,
   quality checklist, extraction variables and synthesis plan. Edit `workflow.yaml`
   to customize stage names, ordering, skills and prerequisites. Run `slr init`
   again after changes.
5. Review both files, then approve the exact revision from your terminal:

```sh
slr approve-protocol --reviewer thomas
```

Use your configured identity if you replaced `thomas`. Enter an approval reason
and explicitly confirm. Agents must hand this command to you.

## OpenCode and provider connections

Install OpenCode using its [official instructions](https://opencode.ai/docs/).
This project includes version-specific profiles because V1 and V2 use different
configuration keys, tool actions and permission formats.

```sh
opencode --version
python scripts/select_opencode_config.py
opencode
```

Automatic detection selects the matching major-version profile. You can select
explicitly with `--major 1` or `--major 2`. The supplied root `opencode.json` is
the V2 profile. Select the version **before customizing** this file: selecting a
profile replaces it and saves different existing content to `opencode.previous.json`.
Global provider credentials/configuration are not modified by the selector.
Detection accepts both bare versions such as `1.3.0` and prefixed output such as
`opencode v2.0.23`. The selector and V2 project configuration were verified locally
with OpenCode 2.0.23 on macOS; see [validation details](docs/testing.md).

Inside OpenCode:

```text
/connect
/models
/slr-protocol
/slr-search
/slr-screen <record-id>
```

No model is hard-coded. Skills and commands inherit your selected model. You can
set a model per agent or slash command using your OpenCode version's syntax.

Account support is not identical across providers. As checked on 2026-10-05:

| Provider | Setup supported by the referenced documentation |
| --- | --- |
| ChatGPT Plus/Pro | OpenCode documents OpenAI login using the ChatGPT Plus/Pro option. Availability/quota depend on your account and installed version. |
| Claude | Use the Anthropic API connection in OpenCode. The current V1 provider guide says Claude subscription auth plugins stopped being bundled as of 1.3.0 and are prohibited by Anthropic; this project does not promise Claude Pro/Max subscription login. |
| Gemini | Use a Gemini API key or the documented Vertex AI connection. Google says consumer Code Assist/Gemini CLI Login with Google access ended on June 18, 2026; the old consumer OAuth plugin is not a reliable route for Google AI Pro/Ultra subscriptions. |
| Other/local providers | Choose any usable OpenCode provider. Review your version's connection methods and model capabilities. |

See [provider setup](docs/providers.md) for sources and version caveats. This
project does not implement OAuth, copy browser cookies or reuse another CLI's
tokens. OpenCode manages its supported authentication outside the project.

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
`AGENTS.md`. Read [customization](docs/customization.md) for extension contracts.

## Try the synthetic workflow

These records and DOIs are fictional fixtures, clearly marked synthetic. Never
cite them in a review. Use a fresh demo project/database, then approve the example
protocol before importing:

```sh
slr import-records examples/records.json --run-id demo-search-001 --source demo-database --query "synthetic demonstration" --searched-at "2026-10-05T00:00:00+00:00"
slr deduplicate
slr records
slr status
```

You should see three source records, one exact DOI duplicate, and two records
awaiting screening. A repeated import with the same run ID and content adds zero
records. A different result set with the same ID is rejected.

Ask `/slr-screen <record-id>` to obtain a packet, write a JSON draft and call
`slr submit`. The agent should give you the returned proposal ID. In a **separate**
VS Code terminal, review its evidence and decision:

```sh
slr review <proposal-id> --reviewer thomas
```

You can accept, modify or defer. To edit extracted values/evidence, save a revised
complete draft JSON and use `--decision-file <path>`. The original proposal and
previous decisions remain in the history. Entering nothing defaults to defer;
final confirmation defaults to no.

After the relevant record is human-included, attach the synthetic full text to
the publication ID shown by `slr records`:

```sh
slr attach <report-id> examples/full-text.md --kind markdown
```

Use `/slr-full-text`, `/slr-quality` and `/slr-extract` in sequence. Each generates
a draft requiring the same human review command. Link the publication to an
underlying study after confirming the relationship:

```sh
slr link-study <report-id> demo-study-001 --label "Synthetic demonstration study" --reviewer thomas
slr report
slr audit
slr search-corpus "synthetic dataset"
```

Missing full text is recorded with `slr retrieval ... not_retrieved`; it is not
treated as eligibility exclusion. The count JSON exposes pending and unclear
work rather than counting it as excluded.
Once full text is attached, `sought` and `not_retrieved` updates are rejected so
reporting and corpus retrieval continue to agree.

To correct a study relationship, use `slr unlink-study <report-id> <study-id>
--reviewer thomas --reason "Correction justification"` in your terminal. The
original relationship and correction remain in the audit trail.

## Optional document and semantic retrieval adapters

Full-text review works with extracted text: manually prepared Markdown or the
Markdown and structured JSON produced by Docling. Attaching a PDF alone archives
its original bytes; it does not extract readable text. The PDF viewer is for your
visual inspection, while conversion supplies text and anchors to evidence packets.

```sh
uv sync --locked --extra documents
slr convert <report-id> <paper.pdf>

uv sync --locked --extra rag
slr index-corpus
slr retrieve "What evaluation methods were used?"
```

These dependencies/models can be large and may download model weights. The core
works without them. Docling keeps the original PDF plus structured JSON and
Markdown. Equations/tables still need human verification. Configure embeddings
and character-window chunking in `rag.yaml`, and Docling options in `conversion.yaml`; evaluate retrieval before relying
on it. Chroma indexes are disposable, corpus/configuration-fingerprinted caches.
OpenCode generates the conversational answer from retrieved evidence.
To keep both adapters installed, pass both `--extra documents --extra rag` when
syncing; add `--extra dev` to retain development tools. Locking their dependencies
does not establish runtime compatibility or pin externally downloaded model weights.

You can also attach Markdown prepared outside Docling:

```sh
slr attach REPORT_ID /path/to/paper.md --kind markdown
```

Replace `REPORT_ID` with the paper's actual report ID from `slr records`. Keep the
original PDF attached as well. Markdown can retain verified physical PDF page
boundaries with markers such as `<!-- page: 1 -->`; do not invent page numbers.
Docling's structured representation retains element/page information where
available, and semantic indexing prefers it over plain Markdown. Always verify
important quotes, tables and formulas against the original PDF.

## Project map

| Path | Purpose |
| --- | --- |
| `protocol.yaml`, `workflow.yaml`, `conversion.yaml`, `rag.yaml` | Editable scientific protocol, stage graph, conversion and optional retrieval settings |
| `opencode.json`, `config/` | Current and version-specific OpenCode profiles |
| `.opencode/skills/`, `.opencode/commands/` | Stage instructions and slash commands |
| `.vscode/` | Tasks, interpreter settings and debugging entry points |
| `src/slr_workbench/` | Typed configuration, services, CLI, reporting and optional integrations |
| `src/slr_workbench/migrations/` | Versioned SQLite schema |
| `schemas/` | Generated Pydantic contracts |
| `scripts/` | Initialization, profile selection and project validation |
| `uv.lock`, `.python-version`, `.github/workflows/ci.yml` | Locked dependencies, default Python and automated core checks |
| `tests/`, `examples/` | Meaningful invariants and synthetic fixtures |
| `docs/` | Architecture, customization, evidence contracts and reporting coverage |
| `data/` | Local review database, originals, drafts, derived text and exports; created at runtime |

Use **Tasks: Run Task** in VS Code for setup, initialization, human review, status,
export, audit and tests. OpenCode must inherit the activated environment for the
`slr` executable to be available. Python process tasks use the selected interpreter.

## What is implemented and what remains

The core workflow is executable offline after installing dependencies. Live
academic API clients, fuzzy merge/reversal operations, rendered PRISMA diagrams,
updated-review carried-over-study handling and statistical meta-analysis remain
future iterations. Skill instructions identify these boundaries explicitly.

The included Docling/Chroma adapters have not been exercised against downloaded
models in this build. OpenCode configuration/skill files have been checked against
official V1/V2 documentation and local structural validation. OpenCode 2.0.23
also successfully loaded the project configuration and discovered the SLR agent
locally. Provider login and model execution require your machine/account.

For developer validation:

```sh
uv sync --locked --extra dev
uv run --locked --extra dev python scripts/validate_project.py
uv run --locked --extra dev ruff check src scripts tests
uv run --locked --extra dev pytest -q
uv build
uv run --locked --extra dev python scripts/validate_distribution.py
```

See `docs/testing.md` for the executed checks and their limits.
See [reproducibility and GitHub setup](docs/reproducibility.md) for fresh-clone
instructions, dependency updates and publishing this repository.
