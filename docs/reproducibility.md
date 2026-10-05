python scripts/select_opencode_config.py# Reproducibility and GitHub setup

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

```sh
uv sync --locked --extra dev
uv run --locked --extra dev python scripts/validate_project.py
uv run --locked --extra dev ruff check src scripts tests
uv run --locked --extra dev pytest -q
uv run --locked --extra dev slr --help
uv build
uv run --locked --extra dev python scripts/validate_distribution.py
```

The default interpreter is Python 3.12.15. Python 3.11 is the supported minimum;
CI checks both versions on Linux, macOS and Windows. CI is configured to run on
pushes and pull requests; its results are only known after it runs on GitHub.
The tests create temporary synthetic projects and never approve or modify your
real review. Run real approval commands yourself in a separate terminal.

`uv.lock` records all dependency resolutions, including optional adapters, while
`uv sync --locked --extra dev` installs only the core and development extra.
The build backend is pinned in `pyproject.toml`. CI actions are pinned by commit.
An initial setup needs network access for Python and packages. Repeating the
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

Create an empty GitHub repository under your account with your chosen visibility.
This checkout has no GitHub remote configured. From the project root, review and
commit the source before connecting it to your repository:

```sh
git status --short
git diff --check
git add .
git diff --cached --stat
git commit -m "Fix evidence validation and add reproducible setup and CI"
git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY.git
git push -u origin HEAD
```

Replace the account and repository placeholders. The workflow runs automatically
after pushing. No GitHub token belongs in a project file or remote URL; use your
normal Git credential manager or GitHub CLI authentication.

`.gitignore` excludes local environments, `.env` files, review data, SQLite
databases, generated packages and caches. It cannot remove files already tracked
by Git: inspect the staged paths before committing. Only synthetic examples
belong in the public starter repository. A source license has not been selected;
the owner should choose one before offering the project for third-party reuse.
