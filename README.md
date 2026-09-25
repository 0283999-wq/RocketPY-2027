# Beyond UP RocketPy: Flight simulation and analysis for Beyond UP (RocketPy)

A flight simulation and analysis **application** built on RocketPy, for the
Beyond UP rocketry team (Universidad Panamericana). It reads a design
Diego already made in OpenRocket (`.ork`) plus its motor (`.eng`), and flies
it: plots, Monte Carlo, landing ellipse, the 4 RCSM cases, a PDF/DOCX report,
and the self-contained `.py` scripts LASC actually grades.

**This app does not design rockets.** Diego designs in OpenRocket; this app
simulates what he designs. See `CLAUDE.md` for the full brief, phases and
verified project facts, and `PROGRESS.md` for exactly what's done, what's
approximate, and what's blocked right now.

```
OpenRocket -> .ork  (+ exported simulation CSV)
openMotor  -> .eng
        v  THIS APP
plots . Monte Carlo . landing ellipse . 4 RCSM cases . report . .py scripts for LASC
```

## Layout

- `bup_rocketpy/` - importable core library (no UI)
  - `ork_reader.py` - pure-Python `.ork` reader (zip or bare XML); also
    extracts OpenRocket's own stored-simulation drag curve and reference
    numbers directly from a `.ork`, no separate export needed
  - `motor_reader.py` - `.eng` (RASP) and OpenRocket thrust-CSV readers
  - `translate.py` - builds rocketpy `Environment`/`SolidMotor`/`Rocket`/`Flight` from parsed data
  - `rcsm.py` - RCSM Ed.7 Rev.1 compliance checker (rail exit, static margin, T/W, recovery topology, payload)
  - `environment.py` - atmosphere builder (Open-Meteo/GFS/sounding sources still to come)
  - `gui/` - NiceGUI layer
    - `pipeline.py` - the actual load/simulate logic, no NiceGUI import (testable headlessly)
    - `app.py` - the UI itself: upload `.ork`+`.eng`, imported-data table, Simulate, big numbers, plots
- `reference/prometeo_mission44/` - PROMETEO / Mission 44 (LASC 2026), the validated reference implementation this app's translation logic is checked against
- `docs/rcsm_reference.md` - RCSM rule text and IDs used by `rcsm.py`
- `tests/` - `pytest`; includes a real `.ork`/`.eng` acceptance test, V1/V2
  flight-data validation, and a headless smoke test of the app pipeline

## Running it (Windows)

Double-click **`start.bat`**. First run creates `.venv` and installs
`requirements.txt` (pinned versions); every run after that just opens the
app in your browser. No Python knowledge required.

**Python version: this app is tested on Python 3.11/3.12.** `start.bat`
prefers Python **3.12** specifically, via the Windows `py` launcher
(`py -3.12`), even if a different version is your default - a newer
Python already on your machine (3.13, 3.14) may not have installable
wheels yet for rocketpy/nicegui or one of their pinned dependencies, and
`pip install` can fail or install something broken with no clear error.

If `start.bat` prints "Python 3.12 was not found", install it first:
1. Download it: <https://www.python.org/downloads/release/python-3120/>
   ("Windows installer (64-bit)"). During install, check **"Add python.exe
   to PATH"**.
2. Or, with `winget`: `winget install -e --id Python.Python.3.12`
3. Delete the `.venv` folder in this repo if one already exists (it may
   have been created with the wrong version), then double-click
   `start.bat` again.

If you'd rather run it from PowerShell yourself:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m bup_rocketpy.gui.app
```

## Status

See `PROGRESS.md` for the live checklist and every honestly-documented
limitation (what's approximate, what's blocked, what needs a decision from
Diego). Short version: load a `.ork` + `.eng` with **no overrides** and
click Simulate - full KPIs, plots, recovery panel, RCSM cases, and a
self-contained `.py` export all work end to end against PROMETEO's real
`.ork`. **Every result is PROVISIONAL** (per `CLAUDE.md` Rule 3) until
Phase 2's V1/V2 flight-data validation tests both pass within +-5% - right
now neither does (V1: +11.4%, V2: -5.8%), and the causes are documented,
not hidden (see `PROGRESS.md` "Item 3" - three real bugs were found and
fixed along the way, and the zero-weather-uncertainty code-to-code check
against OpenRocket's own simulation now passes at -1.45%). `PrometeoLasc2026.ork`'s
own OpenRocket overrides are also incomplete (only one bodytube's shell
mass, not the whole rocket), so the app's automatic mass/CG estimate for
it is unstable - a manual override is available in the UI's Advanced
panel until that `.ork` is fixed in OpenRocket.
