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
  - `translate.py` - builds rocketpy `Environment`/`SolidMotor`/`Rocket`/`Flight` from parsed data (the ONE place OpenRocket's nose-tip coordinate frame gets converted to rocketpy's own)
  - `rcsm.py` / `rcsm_cases.py` - RCSM Ed.7 Rev.1 compliance checker (rail exit, static margin, T/W, recovery topology/timing/rates) and the 4 required flight cases (Ballistic/Nominal/DrogueOnly/MainAtApogee)
  - `monte_carlo.py` - N stochastic flights in parallel across CPU cores (`ProcessPoolExecutor`), apogee histogram + landing ellipse
  - `weather.py` - real weather via Open-Meteo (forecast + historical), cached to disk so it works fully offline once downloaded (see "Launch Day" page below)
  - `competition_profiles.py` - the selectable competition (Test flight/LASC/ENMICE/IREC) that drives mission-ID naming and which compliance ruleset (only RCSM, for LASC) applies
  - `openrocket_csv_export.py` - flight-data CSV export matching OpenRocket's own 58-column format
  - `report.py` - the PDF/DOCX simulation report; `run_history.py` - the local `runs/` auto-save history; `validation.py` - the live V1/V2 checks
  - `case_export.py` / `lasc_package.py` - the self-contained per-case `.py` scripts (CRS 10.1.6) and the submission `.zip`
  - `gui/` - NiceGUI layer, one file per page under `gui/pages/`
    - `pipeline.py` - the actual load/simulate logic, no NiceGUI import (testable headlessly)
    - `app.py` - the Simulate page + app bootstrap (registers every other page)
- `reference/prometeo_mission44/` - PROMETEO / Mission 44 (LASC 2026), the validated reference implementation this app's translation logic is checked against
- `docs/rcsm_reference.md` - RCSM rule text and IDs used by `rcsm.py`
- `tests/` - `pytest`; includes a real `.ork`/`.eng` acceptance test, V1/V2
  flight-data validation, a headless smoke test of the app pipeline, and a
  real-browser (Playwright) end-to-end test across every page

## Pages (left sidebar)

Simulate -> Rocket -> Monte Carlo -> RCSM Cases -> Analysis -> History ->
Exports -> Validation -> **Launch Day**. Load a `.ork`+`.eng` on Simulate
first - every other page reads from that one shared `gui/state.py` dict
and shows "load files first" until you have.

## For new team members

- **Run the tests before changing anything**: `.venv\Scripts\python -m pytest tests\ -q`
  (or `.venv/bin/python -m pytest tests/ -q` outside Windows). One test
  is a real headless-Chromium run and is slower (~20s) than the rest.
- **Everything is PROVISIONAL until V1 and V2 both pass** (`CLAUDE.md`
  Rule 3, `bup_rocketpy/validation.py`, the Validation page). Never
  present a number from this app as final without that badge - see
  `PROGRESS.md` for the current V1/V2 numbers and why they haven't
  passed yet.
- **Two altitude conventions coexist in rocketpy and it's easy to mix
  them up**: `flight.altitude(t)` is already AGL (above ground level);
  `flight.z(t)` and `flight.apogee` are ASL (above sea level, need
  `- flight.env.elevation`). Getting this backwards gives a plausible-
  looking but wrong number - see `bup_rocketpy/rcsm.py`'s REC 8.1.4 check
  for a real bug this caused and how it was caught.
- **Coordinate frame**: OpenRocket measures every position from the nose
  tip, distance increasing toward the tail; rocketpy's own frame is the
  opposite sign for this app's default `"tail_to_nose"` build.
  `translate._coordinate_transform` is the ONE place that conversion
  happens - reuse it (it's its own inverse) rather than hand-deriving a
  sign, see `openrocket_csv_export.py`'s CG/CP columns for the pattern.
  Everything else in this app - mass, CG, drag curves, thrust - **must
  come from a real source** (the `.ork`, the `.eng`, a real drag CSV, or
  an explicit, clearly-labeled "no source, low confidence" placeholder).
  Never invent a coefficient to make a number look better.
- **Monte Carlo runs in separate OS processes**, not threads (Python's
  GIL means threads wouldn't actually parallelize the CPU-bound flight
  sims) - see `monte_carlo.py`'s module docstring for 3 real rocketpy
  1.13.0 bugs found and worked around while building this.
- **Weather downloads need Diego's own machine**, not this cloud dev
  environment (no route to `api.open-meteo.com` from here) - every
  `weather.py` test mocks the HTTP call; a teammate adding a new weather
  source should do the same rather than skip testing it.

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
click Simulate - full KPIs, plots, recovery panel, RCSM cases, Monte Carlo
(parallelized across CPU cores), the PDF/DOCX report, an OpenRocket-format
CSV export, and a self-contained `.py` export all work end to end against
PROMETEO's real `.ork`. **Every result is PROVISIONAL** (per `CLAUDE.md`
Rule 3) until Phase 2's V1/V2 flight-data validation tests both pass
within +-5% - right now neither does (V1: +11.0%, V2: -6.1% - see the
Validation page, computed live, not hardcoded), and the causes are
documented, not hidden (see `PROGRESS.md` - several real bugs were found
and fixed along the way, and the zero-weather-uncertainty code-to-code
check against OpenRocket's own simulation now passes at -1.45%). `PrometeoLasc2026.ork`'s
own OpenRocket overrides are also incomplete (only one bodytube's shell
mass, not the whole rocket), so the app's automatic mass/CG estimate for
it is unstable - a manual override is available in the UI's Advanced
panel until that `.ork` is fixed in OpenRocket.
