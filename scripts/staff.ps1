#Requires -Version 5.1
<#
.SYNOPSIS
    Run the staff Angular app (teachers + administrators) on http://localhost:4200.

.DESCRIPTION
    `ng serve` proxies /api to the backend at 127.0.0.1:8000 via proxy.conf.json,
    so the SPA calls the API same-origin and the httpOnly refresh cookie stays
    first-party. Start the backend first (scripts\backend.ps1).

.PARAMETER Port
    Port to serve on. Defaults to 4200; change it if something else holds it.

.EXAMPLE
    .\scripts\staff.ps1 -Port 4201
#>
[CmdletBinding()]
param([int]$Port = 4200)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$app  = Join-Path $root 'frontend-staff'

if (-not (Test-Path (Join-Path $app 'node_modules'))) {
    throw "frontend-staff\node_modules is missing. Run .\scripts\setup.ps1 first."
}

Push-Location $app
try {
    Write-Host "`n==> Staff app  http://localhost:$Port  (proxying /api to 127.0.0.1:8000)`n" -ForegroundColor Green
    npm run start -- --port $Port
} finally {
    Pop-Location
}
