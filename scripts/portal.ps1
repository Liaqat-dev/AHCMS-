#Requires -Version 5.1
<#
.SYNOPSIS
    Run the student portal Angular app on http://localhost:4300.

.DESCRIPTION
    A separate application from the staff app: students sign in with a roll
    number and reach only their own record. It proxies /api to the same backend
    at 127.0.0.1:8000, so its refresh cookie stays first-party too.

.PARAMETER Port
    Port to serve on. Defaults to 4300, keeping it clear of the staff app.

.EXAMPLE
    .\scripts\portal.ps1 -Port 4301
#>
[CmdletBinding()]
param([int]$Port = 4300)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$app  = Join-Path $root 'frontend-portal'

if (-not (Test-Path (Join-Path $app 'node_modules'))) {
    throw "frontend-portal\node_modules is missing. Run .\scripts\setup.ps1 first."
}

Push-Location $app
try {
    Write-Host "`n==> Student portal  http://localhost:$Port  (proxying /api to 127.0.0.1:8000)`n" -ForegroundColor Green
    npm run start -- --port $Port
} finally {
    Pop-Location
}
