#Requires -Version 5.1
<#
.SYNOPSIS
    Run the FastAPI backend on http://localhost:8000 with auto-reload.

.DESCRIPTION
    Applies Alembic migrations, ensures the super-admin account, then serves
    uvicorn. Configuration is read from backend\.env (see app/core/config.py).

.PARAMETER SkipMigrations
    Serve immediately without running `alembic upgrade head` first.

.PARAMETER Port
    Port to bind. Defaults to 8000, which frontend\proxy.conf.json expects.

.EXAMPLE
    .\scripts\backend.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipMigrations,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$venvPy  = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPy)) {
    throw "No virtualenv at backend\.venv. Run .\scripts\setup.ps1 first."
}

$envFile = Join-Path $backend '.env'
if (-not (Test-Path $envFile)) {
    throw "backend\.env is missing. Copy backend\.env.example to backend\.env and set DATABASE_URL."
}

# Fail early and clearly rather than surfacing a DNS error from asyncpg.
if (Select-String -Path $envFile -Pattern 'USER:PASSWORD@ep-xxxx' -Quiet) {
    Write-Host 'DATABASE_URL in backend\.env is still the placeholder.' -ForegroundColor Yellow
    Write-Host 'Paste your Neon connection string (Neon > project > Connect) and rerun.' -ForegroundColor Yellow
    exit 1
}

Push-Location $backend
try {
    if (-not $SkipMigrations) {
        Write-Host "`n==> Applying database migrations" -ForegroundColor Cyan
        & $venvPy -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'alembic upgrade head failed' }

        Write-Host "`n==> Ensuring super-admin account" -ForegroundColor Cyan
        & $venvPy -m app.cli.seed_superadmin
        if ($LASTEXITCODE -ne 0) { throw 'super-admin seeding failed' }
    }

    Write-Host "`n==> API      http://localhost:$Port" -ForegroundColor Green
    Write-Host "==> Docs     http://localhost:$Port/docs" -ForegroundColor Green
    Write-Host "==> Health   http://localhost:$Port/api/v1/health`n" -ForegroundColor Green
    & $venvPy -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
} finally {
    Pop-Location
}
