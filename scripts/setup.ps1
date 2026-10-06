param([string]$PythonPath = "")
$ErrorActionPreference = "Stop"
$Setup = Join-Path $PSScriptRoot "setup.py"
if ($PythonPath) {
    & $PythonPath $Setup
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 $Setup
} else {
    Write-Error 'Install Python 3.12 from python.org with the launcher, or pass -PythonPath pointing to its python.exe. See README.'
    exit 1
}
exit $LASTEXITCODE
