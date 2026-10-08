# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
# Demo only. This installer does not contact a tenant and does not install paid software.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "DEMO ONLY. No tenant is contacted."
Write-Host "Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE."
Write-Host ""

$python = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) {
    Write-Host "Python 3 is not installed."
    Write-Host "Install it from https://www.python.org/downloads/ and tick Add python.exe to PATH."
    Write-Host "Then run this installer again. Nothing else needs to be installed."
    exit 1
}

& $python --version
New-Item -ItemType Directory -Force -Path data, logs, reports | Out-Null
if (-not (Test-Path config.json)) {
    Copy-Item config.example.json config.json
    Write-Host "Created config.json from the example. It uses a fake tenant."
}

Write-Host "Checking the sample workflow..."
& $python -m unittest tests/test_lifecycle.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Running the demo..."
& $python src/lifecycle.py demo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Ready."
Write-Host "Next:  python src/lifecycle.py menu"
Write-Host "Ticket: reports\demo-summary.md"
Write-Host "List:   python src/lifecycle.py list"
