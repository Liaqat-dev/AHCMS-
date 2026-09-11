#Requires -Version 5.1
<#
.SYNOPSIS
    One-time setup: backend virtualenv + dependencies, frontend node_modules.

.DESCRIPTION
    Prefers `uv` when it is installed; otherwise falls back to the stdlib venv
    module plus pip (backend/scripts/pip_sync.py reads the same pyproject.toml,
    so both paths install the identical dependency set).

.PARAMETER Force
    Recreate the backend virtualenv from scratch instead of reusing it.

.EXAMPLE
    .\scripts\setup.ps1
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'

$root     = Split-Path -Parent $PSScriptRoot
$backend  = Join-Path $root 'backend'
# Two independent Angular workspaces: staff (teachers + admins) and the
# student portal. Each has its own node_modules and its own deployment.
$frontends = @(
    (Join-Path $root 'frontend-staff'),
    (Join-Path $root 'frontend-portal')
)
$venv     = Join-Path $backend '.venv'
$venvPy   = Join-Path $venv 'Scripts\python.exe'

function Write-Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }

# ---------------------------------------------------------------- backend ---
Write-Step 'Backend: Python environment'

$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

if ($Force -and (Test-Path $venv)) {
    Write-Host 'Removing the existing virtualenv (-Force)'
    Remove-Item -Recurse -Force $venv
}

Push-Location $backend
try {
    if ($hasUv) {
        Write-Host 'Using uv'
        uv sync
        if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
    } else {
        Write-Host 'uv not found; using python -m venv + pip'
        if (-not (Test-Path $venvPy)) {
            $systemPy = Get-Command python -ErrorAction SilentlyContinue
            if (-not $systemPy) { throw 'Python 3.11+ is required but was not found on PATH.' }
            & $systemPy.Source -m venv $venv
            if ($LASTEXITCODE -ne 0) { throw 'Failed to create the virtualenv' }
        }
        & $venvPy -m pip install --upgrade pip --quiet
        & $venvPy (Join-Path $backend 'scripts\pip_sync.py') --dev
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    }
} finally {
    Pop-Location
}

Write-Step 'Backend: environment file'
$envFile = Join-Path $backend '.env'
if (Test-Path $envFile) {
    Write-Host 'backend\.env already exists; leaving it untouched'
} else {
    Copy-Item (Join-Path $backend '.env.example') $envFile
    Write-Host 'Created backend\.env from .env.example'
}

# --------------------------------------------------------------- frontend ---
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is required but was not found on PATH. Install Node.js 20.19+ or 22.12+.'
}
foreach ($frontend in $frontends) {
    Write-Step "Frontend: npm dependencies ($(Split-Path -Leaf $frontend))"
    Push-Location $frontend
    try {
        if (Test-Path (Join-Path $frontend 'package-lock.json')) { npm ci } else { npm install }
        if ($LASTEXITCODE -ne 0) { throw "npm install failed in $frontend" }
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------ done ----
Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host 'Next: put your Neon connection string in backend\.env (DATABASE_URL), then run .\scripts\dev.ps1'
Write-Host '  Staff app       http://localhost:4200'
Write-Host '  Student portal  http://localhost:4300'
