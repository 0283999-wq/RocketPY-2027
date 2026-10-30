@echo off
REM Beyond UP RocketPy updater (Windows). Double-click this file to get the
REM latest version and start the app. ASCII only: cmd.exe mangles UTF-8.
REM It runs "git pull" and then start.bat, which re-checks Python and
REM reinstalls requirements only if requirements.txt changed.

setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=%~dp0install_log.txt"

where git >nul 2>&1
if errorlevel 1 (
    echo Git is not installed or not on PATH. Install Git for Windows from
    echo https://git-scm.com/download/win and double-click update.bat again.
    echo git not found. >> "%LOG%"
    pause
    exit /b 1
)

echo Getting the latest version...
git pull >> "%LOG%" 2>&1
if errorlevel 1 (
    echo "git pull" failed. If you edited files in this folder, ask for help.
    echo The details were saved to install_log.txt - send that file.
    pause
    exit /b 1
)
echo Up to date.
call "%~dp0start.bat"
