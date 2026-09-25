@echo off
REM Beyond UP RocketPy launcher (Windows). Double-click this file.
REM First run: creates .venv and installs requirements.txt (pinned versions).
REM Every run: activates .venv and opens the app in your browser.

cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create a virtual environment. Is Python installed and on PATH?
        pause
        exit /b 1
    )
    echo Installing requirements ^(this only happens once^)...
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install requirements. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

echo Starting Beyond UP RocketPy...
.venv\Scripts\python -m bup_rocketpy.gui.app
pause
