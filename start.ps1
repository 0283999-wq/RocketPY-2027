# Beyond UP RocketPy launcher for computers where .bat files are blocked.
# Same logic as start.bat. Run it with:
#   powershell -ExecutionPolicy Bypass -File .\start.ps1
# ASCII only. Never runs pip.exe: everything goes through python.exe -m ...
# Every failure writes the full output to install_log.txt.

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$log = Join-Path $PSScriptRoot "install_log.txt"
$venvDir = Join-Path $PSScriptRoot ".venv"
$venvPy = Join-Path $venvDir "Scripts\python.exe"
Add-Content -Path $log -Value "==== start.ps1 $(Get-Date) ===="

function Fail([string]$message) {
    Write-Host ""
    Write-Host $message
    Write-Host "The full output was saved to install_log.txt next to start.ps1 - send that file."
    if ($env:BUP_NO_LAUNCH -ne "1") { Read-Host "Press Enter to close" | Out-Null }
    exit 1
}

function Test-Blocked([string]$text) {
    return $text -match "Device Guard|Application Control|Smart App Control|blocked by"
}

function Blocked-Message {
    Add-Content -Path $log -Value "Blocked by Windows policy."
    Fail "Windows on this computer blocks Python programs (Device Guard / Smart App Control). Ask your IT department, or use another computer."
}

function Find-Python312 {
    if ($env:BUP_TEST_NO_PYTHON -eq "1") { return $null }
    function Try-Py312 {
        $exe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return ($exe | Select-Object -First 1) }
        return $null
    }
    $found = Try-Py312
    if ($found) { return $found }
    & py install --help *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Python 3.12 is missing. Installing it with the Python install manager (py install 3.12)..."
        & py install -y 3.12 *>> $log
        if ($LASTEXITCODE -ne 0) { & py install 3.12 *>> $log }
        $found = Try-Py312
        if ($found) { return $found }
    }
    & python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)" *> $null
    if ($LASTEXITCODE -eq 0) {
        return (& python -c "import sys; print(sys.executable)" | Select-Object -First 1)
    }
    return $null
}

# folder warning
if ($PSScriptRoot -match "OneDrive") {
    Write-Host "NOTE: this folder is synced by OneDrive. It works, but OneDrive slows down .venv. Better: clone into $env:USERPROFILE\dev."
}

# keep a healthy .venv, otherwise delete it
if (Test-Path $venvDir) {
    $why = $null
    $cfg = Join-Path $venvDir "pyvenv.cfg"
    if (-not (Test-Path $venvPy)) { $why = "it has no python.exe" }
    elseif (-not (Test-Path $cfg)) { $why = "it has no pyvenv.cfg" }
    else {
        $cfgText = Get-Content $cfg -Raw
        if ($cfgText -notmatch "(?m)^version = 3\.12") { $why = "it was made with a Python that is not 3.12" }
        elseif ($cfgText -match "(?m)^home = (.+)$" -and -not (Test-Path (Join-Path $Matches[1].Trim() "python.exe"))) {
            $why = "the Python it points to no longer exists"
        }
        else {
            $probe = & $venvPy -c "import sys" 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) {
                Add-Content -Path $log -Value $probe
                if (Test-Blocked $probe) { Blocked-Message }
                $why = "its python.exe does not run"
            }
        }
    }
    if ($why) {
        Write-Host "Recreating .venv because $why..."
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
    }
}

# create .venv if needed
if (-not (Test-Path $venvPy)) {
    $py = Find-Python312
    if (-not $py) {
        Add-Content -Path $log -Value "No Python 3.12 found."
        Fail "Python 3.12 was not found and could not be installed automatically.`n  1. Download 'Windows installer (64-bit)' for Python 3.12 from https://www.python.org/downloads/release/python-3120/`n  2. In the installer, tick 'Add python.exe to PATH', then Install.`n  3. Run start.ps1 again. (Python 3.13 and 3.14 are not supported yet.)"
    }
    & $py -c "import sys; sys.exit(0 if sys.argv[1].isascii() else 1)" $PSScriptRoot *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail "This folder path has accents or special characters ($PSScriptRoot). Move the project to a plain path such as $env:USERPROFILE\dev\RocketPY-2027."
    }
    Write-Host "Creating the virtual environment with $py ..."
    $out = & $py -m venv $venvDir 2>&1 | Out-String
    Add-Content -Path $log -Value $out
    if ($LASTEXITCODE -ne 0) {
        if (Test-Blocked $out) { Blocked-Message }
        Fail "Could not create the virtual environment."
    }
}

# requirements: only when requirements.txt changed
$reqHash = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $PSScriptRoot "requirements.txt")).Hash
$marker = Join-Path $venvDir "bup_requirements.hash"
$oldHash = if (Test-Path $marker) { (Get-Content $marker -Raw).Trim() } else { "" }
if ($reqHash -eq $oldHash) {
    Write-Host "Requirements unchanged - skipping pip."
}
else {
    Write-Host "Installing requirements (first run or requirements.txt changed - a few minutes)..."
    $out = & $venvPy -m pip install -r (Join-Path $PSScriptRoot "requirements.txt") 2>&1 | Out-String
    $code = $LASTEXITCODE
    Add-Content -Path $log -Value $out
    if ($code -ne 0) {
        if (Test-Blocked $out) { Blocked-Message }
        if ($out -match "Could not fetch|ConnectionError|SSLError|ProxyError|getaddrinfo|Max retries exceeded|timed out") {
            Fail "pip could not reach the internet. Check your connection, VPN or proxy. University networks sometimes block package downloads: try your phone hotspot."
        }
        if ($out -match "No space left|Errno 28") { Fail "The disk is full. Free some space and run start.ps1 again." }
        Fail "Installing the requirements failed (not a network problem)."
    }
    Set-Content -Path $marker -Value $reqHash -Encoding ascii
    $haveBrowser = @(
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
    ) | Where-Object { Test-Path $_ }
    if ($haveBrowser) { Write-Host "Found Microsoft Edge or Google Chrome - the PDF report will use it." }
    else {
        Write-Host "Neither Edge nor Chrome found - trying the optional PDF fallback browser..."
        & $venvPy -m playwright install chromium *>> $log
        if ($LASTEXITCODE -ne 0) { Write-Host "Could not install it. The app still runs; DOCX reports work, PDF needs Edge or Chrome." }
    }
}

if ($env:BUP_NO_LAUNCH -eq "1") { Write-Host "Setup finished (BUP_NO_LAUNCH=1, not starting the app)."; exit 0 }
Write-Host "Starting Beyond UP RocketPy..."
& $venvPy -m bup_rocketpy.gui.app
if ($LASTEXITCODE -ne 0) { Write-Host "The app stopped with an error. The message above, plus install_log.txt, is what to send." }
Read-Host "Press Enter to close" | Out-Null
