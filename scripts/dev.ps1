#Requires -Version 5.1
<#
.SYNOPSIS
    Start the backend and both Angular apps, each in its own window.

.DESCRIPTION
    Opens three PowerShell windows so each process keeps its own log stream and
    responds to Ctrl+C independently. Close a window to stop that service.

.PARAMETER SkipPortal
    Start only the backend and the staff app.

.EXAMPLE
    .\scripts\dev.ps1
#>
[CmdletBinding()]
param([switch]$SkipPortal)

$ErrorActionPreference = 'Stop'

function Start-Service-Window($title, $script) {
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-ExecutionPolicy', 'Bypass',
        '-Command', "`$Host.UI.RawUI.WindowTitle = '$title'; & '$script'"
    )
}

Start-Service-Window 'CMS backend' (Join-Path $PSScriptRoot 'backend.ps1')
Start-Sleep -Seconds 2
Start-Service-Window 'CMS staff'   (Join-Path $PSScriptRoot 'staff.ps1')
if (-not $SkipPortal) {
    Start-Service-Window 'CMS portal' (Join-Path $PSScriptRoot 'portal.ps1')
}

Write-Host "`nStarted:" -ForegroundColor Green
Write-Host '  Backend         http://localhost:8000/docs'
Write-Host '  Staff app       http://localhost:4200'
if (-not $SkipPortal) {
    Write-Host '  Student portal  http://localhost:4300'
}
