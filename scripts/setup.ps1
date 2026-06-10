#Requires -Version 5.1
<#
.SYNOPSIS
    One-command setup for the Daily Brief Agent (Windows PowerShell).

.DESCRIPTION
    Idempotent and safe to re-run. It:
      1. Creates a local virtual environment (.venv) using uv if available, else python -m venv.
      2. Installs the package in editable mode with dev dependencies.
      3. Copies .env.example -> .env if .env is missing (defaults need no secrets).
      4. Initializes the SQLite database (daily-brief init-db).
      5. Prints the next steps.

.EXAMPLE
    ./scripts/setup.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvDir = '.venv'

function Write-Info($msg) { Write-Host "==> $msg" -ForegroundColor Blue }
function Write-Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }
function Test-Have($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

function Find-Python {
    foreach ($candidate in @('python', 'python3', 'py')) {
        if (Test-Have $candidate) {
            $ok = & $candidate -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}

if (Test-Have 'uv') {
    Write-Info "Using uv ($(uv --version))"
    uv venv --allow-existing --python '>=3.11' $VenvDir
    uv pip install --python $VenvDir -e ".[dev]"
    $Python = Join-Path $VenvDir 'Scripts/python.exe'
}
else {
    Write-Warn 'uv not found; falling back to python -m venv + pip.'
    $PyBin = Find-Python
    if (-not $PyBin) {
        Write-Warn 'Could not find Python >= 3.11.'
        Write-Warn 'Install Python 3.11+ (https://www.python.org/downloads/) or uv (https://docs.astral.sh/uv/) and re-run.'
        exit 1
    }
    Write-Info "Using $PyBin ($(& $PyBin --version 2>&1))"
    if (-not (Test-Path $VenvDir)) {
        & $PyBin -m venv $VenvDir
    }
    $Python = Join-Path $VenvDir 'Scripts/python.exe'
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -e ".[dev]"
}

if (-not (Test-Path '.env')) {
    Write-Info 'Creating .env from .env.example (safe console defaults, no secrets required).'
    Copy-Item '.env.example' '.env'
}
else {
    Write-Info '.env already exists; leaving it untouched.'
}

Write-Info 'Initializing database.'
& $Python -m daily_brief.cli init-db

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host ''
Write-Host 'Activate the environment:'
Write-Host "  .\$VenvDir\Scripts\Activate.ps1"
Write-Host ''
Write-Host 'Then try the zero-config demo (writes a preview to var/outbox/):'
Write-Host '  daily-brief dry-run'
Write-Host '  daily-brief preview-email'
Write-Host ''
Write-Host 'Or without activating:'
Write-Host "  .\$VenvDir\Scripts\daily-brief.exe dry-run"
Write-Host ''
Write-Host 'Other useful commands:'
Write-Host '  daily-brief doctor        # readiness checks'
Write-Host '  daily-brief serve         # web dashboard at http://127.0.0.1:8000'
Write-Host '  daily-brief list-runs     # recent run history'
Write-Host ''
Write-Host 'Edit .env to enable live sources or a real delivery channel.'
