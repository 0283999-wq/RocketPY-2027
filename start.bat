@echo off
REM Beyond UP RocketPy launcher (Windows). Double-click this file.
REM ASCII only on purpose: cmd.exe mangles UTF-8 characters.
REM
REM What it does, in order:
REM   1. Finds Python 3.12 (py -3.12, then "py install 3.12" if the new Python
REM      install manager exists, then "python" on PATH only if it is 3.12).
REM   2. Creates .venv with it, or recreates .venv if it is broken / made by
REM      another Python version.
REM   3. Installs requirements.txt ONLY when that file changed (hash marker in
REM      .venv\bup_requirements.hash). Normal launches never touch pip.
REM   4. Starts the app with ".venv\Scripts\python.exe -m bup_rocketpy.gui.app".
REM
REM Nothing here ever runs pip.exe or any other .exe inside .venv\Scripts except
REM python.exe: some university PCs block those launchers (Device Guard).
REM Every failure writes the full output to install_log.txt next to this file.
REM Set BUP_NO_LAUNCH=1 to do steps 1-3 and stop (used by the install tests).

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "LOG=%~dp0install_log.txt"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "PYEXE="
set "PIPOUT=%TEMP%\bup_pip_out.txt"

echo ==== start.bat %DATE% %TIME% ==== >> "%LOG%"

REM ---- folder warnings (do not stop) -------------------------------------
echo %~dp0| findstr /i "OneDrive" >nul 2>&1
if not errorlevel 1 (
    echo NOTE: this folder is synced by OneDrive. It works, but OneDrive slows
    echo down the .venv folder. Better: clone into %USERPROFILE%\dev instead.
    echo.
)

REM ---- 1. keep a healthy .venv, otherwise delete it ---------------------
if exist ".venv" (
    call :check_venv
    if errorlevel 1 exit /b 1
)

REM ---- 2. create .venv if needed ----------------------------------------
if not exist "%VENV_PY%" (
    call :find_python
    if not defined PYEXE goto :no_python
    call :check_ascii_path
    if errorlevel 1 exit /b 1
    echo Creating the virtual environment with !PYEXE! ...
    "!PYEXE!" -m venv .venv >> "%LOG%" 2>&1
    if errorlevel 1 (
        type "%LOG%" | findstr /i /c:"Device Guard" /c:"Application Control" /c:"Smart App Control" /c:"blocked by" >nul 2>&1
        if not errorlevel 1 goto :blocked
        echo Could not create the virtual environment.
        goto :fail
    )
)

REM ---- 3. requirements: only when requirements.txt changed ---------------
set "REQHASH="
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile requirements.txt SHA256 2^>nul') do (
    if not defined REQHASH set "REQHASH=%%H"
)
set "OLDHASH="
if exist ".venv\bup_requirements.hash" set /p OLDHASH=<".venv\bup_requirements.hash"
if defined REQHASH if /i "!REQHASH!"=="!OLDHASH!" (
    echo Requirements unchanged - skipping pip.
    goto :after_pip
)

echo Installing requirements ^(first run or requirements.txt changed - a few minutes^)...
"%VENV_PY%" -m pip install -r requirements.txt > "%PIPOUT%" 2>&1
set "PIPERR=!errorlevel!"
type "%PIPOUT%" >> "%LOG%"
if not "!PIPERR!"=="0" goto :pip_failed
if defined REQHASH >".venv\bup_requirements.hash" echo !REQHASH!
call :optional_chromium

:after_pip
if "%BUP_NO_LAUNCH%"=="1" (
    echo Setup finished ^(BUP_NO_LAUNCH=1, not starting the app^).
    exit /b 0
)

echo Starting Beyond UP RocketPy...
"%VENV_PY%" -m bup_rocketpy.gui.app
if errorlevel 1 (
    echo.
    echo The app stopped with an error. The message above, plus install_log.txt, is what to send.
)
pause
exit /b 0

REM =======================================================================
:find_python
set "PYEXE="
if "%BUP_TEST_NO_PYTHON%"=="1" exit /b 0
call :try_py312
if defined PYEXE exit /b 0
py install --help >nul 2>&1
if not errorlevel 1 (
    echo Python 3.12 is missing. Installing it with the Python install manager ^(py install 3.12^)...
    py install -y 3.12 >> "%LOG%" 2>&1
    if errorlevel 1 py install 3.12 >> "%LOG%" 2>&1
    call :try_py312
    if defined PYEXE exit /b 0
)
python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
exit /b 0

:try_py312
set "PYEXE="
py -3.12 -c "import sys" >nul 2>&1
if errorlevel 1 exit /b 0
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
exit /b 0

REM =======================================================================
:check_venv
REM Deletes .venv when it is incomplete, made by another Python version, or
REM points to a Python that no longer exists. Says so in one line.
set "WHY="
if not exist ".venv\Scripts\python.exe" set "WHY=it has no python.exe"
if not defined WHY if not exist ".venv\pyvenv.cfg" set "WHY=it has no pyvenv.cfg"
if not defined WHY (
    findstr /b /c:"version = 3.12" ".venv\pyvenv.cfg" >nul 2>&1
    if errorlevel 1 set "WHY=it was made with a Python that is not 3.12"
)
if not defined WHY (
    set "HOMEDIR="
    for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"home" ".venv\pyvenv.cfg"') do set "HOMEDIR=%%B"
    if defined HOMEDIR (
        set "HOMEDIR=!HOMEDIR:~1!"
        if not exist "!HOMEDIR!\python.exe" set "WHY=the Python it points to no longer exists"
    )
)
if not defined WHY (
    ".venv\Scripts\python.exe" -c "import sys" > "%PIPOUT%" 2>&1
    if errorlevel 1 (
        type "%PIPOUT%" >> "%LOG%"
        findstr /i /c:"Device Guard" /c:"Application Control" /c:"Smart App Control" /c:"blocked by" "%PIPOUT%" >nul 2>&1
        if not errorlevel 1 goto :blocked
        set "WHY=its python.exe does not run"
    )
)
if defined WHY (
    echo Recreating .venv because !WHY!...
    rmdir /s /q ".venv" >> "%LOG%" 2>&1
)
exit /b 0

:check_ascii_path
"!PYEXE!" -c "import sys; sys.exit(0 if sys.argv[1].isascii() else 1)" "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo.
    echo This folder path has accents or special characters:
    echo   %~dp0
    echo Python tools often break on that. Move the project to a plain path
    echo such as %USERPROFILE%\dev\RocketPY-2027 and double-click start.bat there.
    echo.
    pause
    exit /b 1
)
exit /b 0

:optional_chromium
REM The PDF report uses Edge or Chrome when present. Playwright's Chromium is
REM only a fallback and is OPTIONAL: if it fails, the app still runs.
set "HAVE_BROWSER="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "HAVE_BROWSER=1"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "HAVE_BROWSER=1"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "HAVE_BROWSER=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "HAVE_BROWSER=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "HAVE_BROWSER=1"
if defined HAVE_BROWSER (
    echo Found Microsoft Edge or Google Chrome - the PDF report will use it.
    exit /b 0
)
echo Neither Edge nor Chrome found - trying the optional PDF fallback browser...
"%VENV_PY%" -m playwright install chromium >> "%LOG%" 2>&1
if errorlevel 1 echo Could not install it. The app still runs; DOCX reports work, PDF needs Edge or Chrome.
exit /b 0

REM =======================================================================
:no_python
echo.
echo Python 3.12 was not found and could not be installed automatically.
echo   1. Download "Windows installer (64-bit)" for Python 3.12 from
echo      https://www.python.org/downloads/release/python-3120/
echo   2. In the installer, tick "Add python.exe to PATH", then Install.
echo   3. Double-click start.bat again.
echo ^(Python 3.13 and 3.14 are not supported yet.^)
echo No Python 3.12 found. >> "%LOG%"
echo The details were saved to install_log.txt - send that file if you ask for help.
if not "%BUP_NO_LAUNCH%"=="1" pause
exit /b 1

:blocked
echo.
echo Windows on this computer blocks Python programs ^(Device Guard / Smart
echo App Control^). Ask your IT department, or use another computer.
echo Blocked by Windows policy. >> "%LOG%"
echo Details were saved to install_log.txt - send that file if you ask for help.
if not "%BUP_NO_LAUNCH%"=="1" pause
exit /b 1

:pip_failed
echo.
findstr /i /c:"Device Guard" /c:"Application Control" /c:"Smart App Control" /c:"blocked by" "%PIPOUT%" >nul 2>&1
if not errorlevel 1 goto :blocked
findstr /i /c:"Could not fetch" /c:"ConnectionError" /c:"SSLError" /c:"ProxyError" /c:"getaddrinfo" /c:"Max retries exceeded" /c:"timed out" "%PIPOUT%" >nul 2>&1
if not errorlevel 1 (
    echo pip could not reach the internet. Check your connection, VPN or proxy.
    echo University networks sometimes block package downloads: try your phone hotspot.
    goto :fail_quiet
)
findstr /i /c:"No space left" /c:"Errno 28" "%PIPOUT%" >nul 2>&1
if not errorlevel 1 (
    echo The disk is full. Free some space and double-click start.bat again.
    goto :fail_quiet
)
echo Installing the requirements failed ^(not a network problem^).
goto :fail

:fail
echo.
:fail_quiet
echo The full output was saved to install_log.txt next to start.bat.
echo Send that file to whoever is helping you.
if not "%BUP_NO_LAUNCH%"=="1" pause
exit /b 1
