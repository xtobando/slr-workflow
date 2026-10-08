param([string]$PythonPath = "")
$ErrorActionPreference = "Stop"
$Setup = Join-Path $PSScriptRoot "setup.py"
if ($PythonPath) {
    & $PythonPath $Setup
    exit $LASTEXITCODE
}
if ($env:SLR_PYTHON) {
    & $env:SLR_PYTHON $Setup
    exit $LASTEXITCODE
}
foreach ($Candidate in @("python3", "python", "py")) {
    if (-not (Get-Command $Candidate -ErrorAction SilentlyContinue)) { continue }
    $Prefix = @()
    if ($Candidate -eq "py") { $Prefix = @("-3.12") }
    & $Candidate @Prefix -c "import sys; sys.exit(sys.version_info[:2] != (3, 12))" 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $Candidate @Prefix $Setup
        exit $LASTEXITCODE
    }
}
Write-Error 'Python 3.12 was not found. Install it or pass -PythonPath pointing to its executable. See docs/installation.md.'
exit 1
