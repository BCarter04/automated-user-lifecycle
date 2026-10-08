@echo off
REM Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
REM Demo only. Double-click this after install.ps1. It does not contact a tenant.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
