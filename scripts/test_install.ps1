# Install tests for start.bat (requirement G). Runs start.bat in a throwaway
# folder with a tiny requirements.txt and BUP_NO_LAUNCH=1, so it never starts
# the app and never touches the real .venv.
#
#   powershell -ExecutionPolicy Bypass -File scripts\test_install.ps1
#
# On a machine where Python 3.12 is reachable through `py -3.12` or `python`
# (GitHub Actions windows-latest after setup-python 3.12) no arguments are
# needed. To test on a machine whose only `py` is a newer Python / the new
# install manager (so the test never installs anything), run:
#
#   ... test_install.ps1 -PythonDir C:\path\to\python312 -HidePyLauncher
#
# -HidePyLauncher removes py.exe from PATH, so start.bat falls through to
# "python on PATH, only if it is 3.12".
param(
    [string]$PythonDir = "",
    [switch]$HidePyLauncher
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path $env:TEMP ("bup_install_test_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$fakeBin = Join-Path $work "fakebin"
New-Item -ItemType Directory -Force -Path $work, $fakeBin | Out-Null
Copy-Item (Join-Path $repo "start.bat") $work
Set-Content -Path (Join-Path $work "requirements.txt") -Value "six==1.16.0" -Encoding ascii

if ($HidePyLauncher) {
    # drop every PATH folder that contains py.exe, so `py` is simply "not found"
    $env:PATH = (($env:PATH -split ";") | Where-Object { $_ -and -not (Test-Path (Join-Path $_ "py.exe")) }) -join ";"
}
if ($PythonDir) { $env:PATH = "$PythonDir;$PythonDir\Scripts;" + $env:PATH }
$env:BUP_NO_LAUNCH = "1"

$failures = @()
function Run-Start {
    param([hashtable]$ExtraEnv = @{})
    foreach ($k in $ExtraEnv.Keys) { Set-Item -Path "Env:$k" -Value $ExtraEnv[$k] }
    Push-Location $work
    & cmd /c "call .\start.bat > run_out.txt 2>&1"
    $code = $LASTEXITCODE
    Pop-Location
    foreach ($k in $ExtraEnv.Keys) { Remove-Item -Path "Env:$k" -ErrorAction SilentlyContinue }
    $out = if (Test-Path (Join-Path $work "run_out.txt")) { Get-Content (Join-Path $work "run_out.txt") -Raw } else { "" }
    return [pscustomobject]@{ Code = $code; Text = $out }
}
function Check($name, $cond, $detail) {
    if ($cond) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name`n$detail"; $script:failures += $name }
}

# 1. no Python 3.12 -> clear message, non-zero exit code, install_log.txt written
$r = Run-Start @{ BUP_TEST_NO_PYTHON = "1" }
Check "no Python 3.12: clear message" ($r.Text -match "Python 3.12 was not found") $r.Text
Check "no Python 3.12: non-zero exit" ($r.Code -ne 0) "exit code $($r.Code)"
Check "no Python 3.12: install_log.txt written" (Test-Path (Join-Path $work "install_log.txt")) ""
Check "no Python 3.12: never blames the internet" ($r.Text -notmatch "internet") $r.Text

# 2. fresh start -> venv created, requirements installed, marker written
$r = Run-Start
Check "fresh start: exit 0" ($r.Code -eq 0) $r.Text
Check "fresh start: python.exe exists" (Test-Path (Join-Path $work ".venv\Scripts\python.exe")) $r.Text
Check "fresh start: hash marker written" (Test-Path (Join-Path $work ".venv\bup_requirements.hash")) $r.Text

# 3. requirements unchanged -> second launch must not call pip
$r = Run-Start
Check "second launch: skips pip" ($r.Text -match "Requirements unchanged - skipping pip") $r.Text
Check "second launch: exit 0" ($r.Code -eq 0) $r.Text

# 4. pip.exe missing/blocked -> still works (proves pip.exe is never used)
Get-ChildItem (Join-Path $work ".venv\Scripts") -Filter "pip*.exe" | Remove-Item -Force
Set-Content -Path (Join-Path $work "requirements.txt") -Value "six==1.16.0`n# changed" -Encoding ascii
$r = Run-Start
Check "pip.exe removed + requirements changed: still installs via python -m pip" ($r.Code -eq 0 -and $r.Text -match "Installing requirements") $r.Text

# 5. .venv made by another Python version -> recreated automatically
$cfg = Join-Path $work ".venv\pyvenv.cfg"
(Get-Content $cfg) -replace "^version = 3\.12.*$", "version = 3.11.0" | Set-Content $cfg -Encoding ascii
$r = Run-Start
Check "wrong-version .venv: recreated" ($r.Text -match "Recreating .venv" -and $r.Code -eq 0) $r.Text

# 6. .venv without python.exe -> recreated
Remove-Item (Join-Path $work ".venv\Scripts\python.exe") -Force
$r = Run-Start
Check "incomplete .venv: recreated" ($r.Text -match "Recreating .venv" -and $r.Code -eq 0) $r.Text

# 7. start.bat contains no pip.exe call and only ASCII
$bat = (Get-Content (Join-Path $repo "start.bat") | Where-Object { $_ -notmatch "^\s*REM\b" }) -join "`n"
Check "start.bat never calls pip.exe or Scripts\pip" ($bat -notmatch "pip\.exe" -and $bat -notmatch "Scripts\\pip") ""
$bytes = [System.IO.File]::ReadAllBytes((Join-Path $repo "start.bat"))
Check "start.bat is ASCII only" (-not ($bytes | Where-Object { $_ -gt 127 })) ""

Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
if ($failures.Count -gt 0) { Write-Host "`n$($failures.Count) FAILED: $($failures -join '; ')"; exit 1 }
Write-Host "`nAll install checks passed."
exit 0
