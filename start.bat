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

REM The PDF report prefers whichever browser is already on this machine
REM (Microsoft Edge, which ships with Windows, or Google Chrome) - no
REM download needed for either. Only if NEITHER is found do we try to
REM download Playwright's own Chromium, since that download is blocked
REM on some networks (university networks in particular) and there is
REM no point waiting on it when a perfectly good browser already exists.
set "HAVE_BROWSER="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "HAVE_BROWSER=1"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "HAVE_BROWSER=1"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "HAVE_BROWSER=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "HAVE_BROWSER=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "HAVE_BROWSER=1"

if defined HAVE_BROWSER (
    echo Found Microsoft Edge or Google Chrome - the PDF report will use it, no download needed.
) else (
    echo Neither Microsoft Edge nor Google Chrome was found - checking the PDF
    echo report's fallback browser engine is installed. If this hangs or fails
    echo ^(common on restrictive networks^), press Ctrl+C: the app still runs
    echo fine and the DOCX report works regardless - see README.md.
    .venv\Scripts\python -m playwright install chromium
    if errorlevel 1 (
        echo Could not install Chromium for Playwright. The app will still run,
        echo but generating a PDF report will fail until either this succeeds
        echo or Microsoft Edge / Google Chrome is installed. The DOCX report
        echo works regardless.
    )
)

:run
echo Starting Beyond UP RocketPy...
.venv\Scripts\python -m bup_rocketpy.gui.app
pause
