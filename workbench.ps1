$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error 'Run scripts/setup.ps1 first.'
    exit 1
}
& $Python (Join-Path $PSScriptRoot "scripts/workbench.py") @args
exit $LASTEXITCODE
