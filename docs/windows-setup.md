# Windows: migrate to an installed Python

This setup uses Python from [python.org](https://www.python.org/downloads/release/python-31210/)
and uv for dependencies. Python 3.12.10 is the last 3.12 release with official
Windows installers; later security releases are source-only. Choose an installer
matching the machine. Include the Python launcher. This changes the distribution
providing Python's DLLs; it does not establish that Defender will allow every file.

Run the following in PowerShell from the project root. Close running OpenCode,
Python processes and terminals using the old environment first. Open a new terminal
without the old environment activated.

```powershell
py -3.12 -c "import sys; print(sys.version); print(sys.executable); print(sys.base_prefix)"
```

Verify this is the python.org installation, not a path under uv's managed Python
folder. If multiple distributions are installed, replace `py -3.12` below with
`& 'C:\actual\path\to\python.exe'` for the verified official installation.

Preserve the existing environment, then create its replacement:

```powershell
if (Test-Path .venv) {
    if (Test-Path .venv-before-migration) { throw 'Choose another backup name first' }
    Rename-Item .venv .venv-before-migration
}
py -3.12 -m venv .venv
uv sync --locked --extra dev --python .venv\Scripts\python.exe
.\.venv\Scripts\python.exe -m slr_workbench --help
.\.venv\Scripts\python.exe scripts/validate_project.py
.\.venv\Scripts\python.exe -m pytest -q
```

No activation script is required. The backup is for recovery, not for execution
under its new name (virtual environments contain absolute paths). These commands
do not delete or migrate `data/`, protocol files, PDFs or scientific decisions.
The new core preserves the draft schema and database migrations. No new protocol
approval is required solely for this dependency change. New proposals record the
updated skill hashes; existing proposals retain their historical provenance.

Resume with `uv run --no-sync opencode` in one terminal. In your separate human
terminal use, for example:

```powershell
.\.venv\Scripts\python.exe -m slr_workbench status
```

For each command in the README, the prefix `uv run --no-sync python` can be
replaced with `.\.venv\Scripts\python.exe`. Human approval commands still require
your interactive confirmation. The generated `slr.exe` and `pytest.exe` launchers
are unnecessary. Ruff is optional locally and still runs in CI.

Docling and Chroma extras can reinstall Pydantic, Typer and native libraries.
Keep them out of the minimal environment unless required. Verified Markdown can
be attached without either adapter. PyYAML retains `safe_load` with its Python
loader; Rich retains tables and prompts with native Windows console probing
turned off in the CLI.

If Defender still blocks a file, record the exact file path, detection name and
Python distribution/version for troubleshooting. An old blocked file may belong
to the preserved environment. These instructions do not change Defender settings.
Windows CI checks application behavior, not every local security policy.

See [uv's interpreter selection documentation](https://docs.astral.sh/uv/concepts/python-versions/).
The project sets `python-downloads = "never"` and `python-preference = "only-system"`;
these settings do not replace an already-existing virtual environment.
