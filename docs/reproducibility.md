# Reproducibility and GitHub setup

## Reproduce a checkout

For reading source papers inside VS Code, install the workspace-recommended
[PDF Viewer](https://marketplace.visualstudio.com/items?itemName=mathematic.vscode-pdf)
extension (`mathematic.vscode-pdf`; VS Code 1.95+). Open Extensions and search
`@recommended`, or, if the `code` CLI is on your PATH, run:

```sh
code --install-extension mathematic.vscode-pdf
```

Recommendations are declared in `.vscode/extensions.json`; they do not install
extensions automatically. This viewer is an editor dependency, not a pip package,
and is unnecessary for headless tests. Open PDFs under `data/artifacts/` to inspect
the originals. The review workflow uses extracted Markdown/structured text;
installing a PDF viewer does not perform extraction or OCR.

Clone the repository, enter its root and install uv 0.12.23 using the
[official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
For an existing Python with pip, `python -m pip install --user uv==0.12.23` is
another option; use `python3` on macOS/Linux or `py` on Windows as appropriate.
Ensure the installer places `uv` on your PATH.

Install Python 3.12 separately and create `.venv` as described in
[README step 3](../README.md#3-install-python-and-the-workbench). uv is configured
not to download managed Python. Record the exact patch version and distribution;
`.python-version` selects a minor version, not a bit-identical interpreter.

```sh
uv sync --locked --extra dev --extra lint
uv run --no-sync python scripts/validate_project.py
uv run --no-sync python -m ruff check src scripts tests
uv run --no-sync python -m pytest -q
uv run --no-sync python -m slr_workbench --help
uv build
uv run --no-sync python scripts/validate_distribution.py
uv run --no-sync python -c "import sys; print(sys.version); print(sys.executable); print(sys.base_prefix)"
```

Ruff is optional locally; omit `--extra lint` and its command if its executable
is blocked, and use CI linting. Python 3.11 remains the supported minimum.
CI covers Python 3.11/3.12 on Linux, macOS and Windows, plus the signed python.org
3.12.10 Windows installer. Hosted results are only known after those jobs run;
they do not guarantee compatibility with every Defender policy.
The tests create temporary synthetic projects and never approve or modify your
real review. Run real approval commands yourself in a separate terminal.

`uv.lock` records all dependency resolutions, including optional adapters, while
`uv sync --locked --extra dev` installs only the core and development extra.
Optional adapters can reintroduce Pydantic, Typer and native dependencies.
The core does not depend on them. The build backend is pinned in `pyproject.toml`. CI actions are pinned by commit.
Install Python separately; the initial dependency sync needs network access. Repeating the
checks with installed dependencies needs no LLM login or downloaded model.
See [uv's locking documentation](https://docs.astral.sh/uv/concepts/projects/sync/)
for the distinction between locking and syncing.

These pins reproduce the software dependency selection, not bit-identical builds,
operating systems, model outputs or externally downloaded model weights. Record
the OS, architecture, repository commit and model/converter versions for a real
review. Keep the review's protocol, workflow, audit history, original documents
and export manifests in an appropriate private archive.

## Dependency changes

Edit version constraints in `pyproject.toml` when needed, then deliberately update:

```sh
uv lock --upgrade
uv sync --locked --extra dev
```

Run the checks above and commit `pyproject.toml` and `uv.lock` together. Update
`.python-version` and the CI matrix together when changing the default Python.
Update `tool.uv.required-version` when changing uv. Use a fresh `dist/` directory
when validating a new package version; the validation script rejects ambiguous
sets of old and new archives. The legacy pip requirements are convenience
entry points and are not locked installation instructions.

Dependency and validator changes do not silently amend the scientific protocol.
The fixes in this revision reject whitespace-only quotes, validate each member
of list choices, and prevent attached reports from reverting to an unretrieved
status. They do not rewrite earlier proposals or decisions. If you used an older
version, review affected evidence and retrieval history through the established
human workflow before using its exports.

## Upload the repository

The project repository is [xtobando/slr-workflow](https://github.com/xtobando/slr-workflow).
To obtain a fresh checkout:

```sh
git clone https://github.com/xtobando/slr-workflow.git
cd slr-workflow
```

To publish a separate copy, create an empty GitHub repository under your account
with your chosen visibility. From your project root, review and commit the source
before connecting it to your repository:

```sh
git status --short
git diff --check
git add .
git diff --cached --stat
git commit -m "Fix evidence validation and add reproducible setup and CI"
git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY.git
git push -u origin HEAD
```

Replace the account and repository placeholders. If `origin` already exists, use
your existing remote or add the new destination under a different remote name.
The workflow runs automatically
after pushing. No GitHub token belongs in a project file or remote URL; use your
normal Git credential manager or GitHub CLI authentication.

`.gitignore` excludes local environments, `.env` files, review data, SQLite
databases, generated packages and caches. It cannot remove files already tracked
by Git: inspect the staged paths before committing. Only synthetic examples
belong in the public starter repository. The project uses the [MIT License](../LICENSE),
preserved from the GitHub repository's initial commit.
