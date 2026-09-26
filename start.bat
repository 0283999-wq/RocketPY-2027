@echo off
REM Beyond UP RocketPy launcher (Windows). Double-click this file.
REM First run: creates .venv (preferring Python 3.12). EVERY run:
REM re-syncs requirements.txt (pip is a fast no-op if already satisfied),
REM then opens the app in your browser. Re-syncing every run (not just on
REM first creation) matters because requirements.txt gets new pinned
REM packages over time (e.g. reportlab/python-docx for the PDF/DOCX
REM report) - an old .venv from before that would otherwise silently keep
REM missing them forever, since this script used to only install once.
REM
REM WHY 3.12 specifically (2026-09-25 review, Section 4): this project is
REM developed and tested in the cloud on Python 3.11/3.12. If your machine
REM only has a newer Python (3.13/3.14) on PATH, rocketpy/nicegui/one of
REM their pinned dependencies may not have wheels for it yet, and `pip
REM install` can fail or silently build something broken. The Windows "py"
REM launcher (installed by every official python.org installer) can select
REM a specific version even if a different one is your default - this
REM script prefers that.

cd /d "%~dp0"

if exist .venv (
    goto :install
)

echo Looking for Python 3.12 via the "py" launcher...
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    echo Found Python 3.12. Creating virtual environment...
    py -3.12 -m venv .venv
    goto :install
)

echo Python 3.12 was not found via "py -3.12".
echo This app is tested on Python 3.11/3.12 - a different version already
echo on your PATH (e.g. 3.13/3.14) may fail to install some pinned
echo dependencies. Falling back to your default "python" anyway - if the
echo next step fails, install Python 3.12 first:
echo   1. https://www.python.org/downloads/release/python-3120/
echo      (download "Windows installer (64-bit)", run it, check "Add
echo      python.exe to PATH")
echo   2. Or, if you have winget: winget install -e --id Python.Python.3.12
echo Then delete the (failed) .venv folder here, if one exists, and
echo double-click start.bat again.
echo.
python -m venv .venv
if errorlevel 1 (
    echo Could not create a virtual environment. Is Python installed and on PATH?
    pause
    exit /b 1
)

:install
echo Checking requirements.txt is fully installed...
.venv\Scripts\pip install -r requirements.txt -q
if errorlevel 1 (
    echo Failed to install requirements. Check your internet connection and try again.
    echo If this keeps failing, it is likely a Python-version mismatch - see the
    echo Python 3.12 install instructions printed above ^(or in README.md^).
    pause
    exit /b 1
)

:run
echo Starting Beyond UP RocketPy...
.venv\Scripts\python -m bup_rocketpy.gui.app
pause
