@echo off
REM Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
REM Double-click this. It opens the first-run window. No command to type.
cd /d "%~dp0"
where python >nul 2>&1 && start "" python "%~dp0src\gui.py" && exit /b 0
where python3 >nul 2>&1 && start "" python3 "%~dp0src\gui.py" && exit /b 0
where py >nul 2>&1 && start "" py "%~dp0src\gui.py" && exit /b 0
echo Python 3 is not installed.
echo Install it from https://www.python.org/downloads/ and tick Add python.exe to PATH.
echo Then double-click Start-Here.bat again.
pause
