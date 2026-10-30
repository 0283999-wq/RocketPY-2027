# Beyond UP RocketPy: Flight simulation and analysis for Beyond UP (RocketPy)

A flight simulation and analysis **application** built on RocketPy, for the
Beyond UP rocketry team (Universidad Panamericana). It reads a design
Diego already made in OpenRocket (`.ork`) plus its motor (`.eng`), and flies
it: plots, Monte Carlo, landing ellipse, the 4 RCSM cases, a PDF/DOCX report,
and the self-contained `.py` scripts LASC actually grades.

**This app does not design rockets.** Diego designs in OpenRocket; this app
simulates what he designs. See `CLAUDE.md` for the full brief, phases and
verified project facts, and `CHANGELOG.md` for what's been done and why.

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
- **This project is developed on Linux and Diego runs it on Windows -
  those aren't the same environment for multiprocessing (Monte Carlo's
  worker pool) or file encoding (CSV/JSON export)**, and a passing suite
  here does not guarantee a passing run there (see two real bugs this
  caused, git log --grep 'Windows [Bb]ug'). Before pushing anything that
  touches file I/O or the Monte Carlo/drag-comparison worker pool, run
  `scripts/test_windows_emulation.sh` - forces the same multiprocessing
  start method ("spawn") and a non-UTF-8 default file encoding Windows
  is stuck with.
- **Never present a number from this app as validated without checking
  the Validation page first** (`CLAUDE.md` Rule 3, `bup_rocketpy/
  validation.py`) - it computes the V1/V2 flight-data checks live and
  shows a small status chip on the results view summarizing the current
  track record, rather than a hardcoded claim.
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

## Running it

### Windows (no Python knowledge required)

Four steps, once per computer:

1. Install **Git for Windows**: <https://git-scm.com/download/win> (accept the defaults).
2. Install **Python 3.12** (64-bit): <https://www.python.org/downloads/release/python-3120/>.
   In the installer tick **"Add python.exe to PATH"**. (If your computer has
   the new "Python install manager", you can skip this: `start.bat` runs
   `py install 3.12` for you.) Python 3.13 and 3.14 are not supported yet.
3. Open PowerShell and clone into a plain folder **outside OneDrive**:

   ```powershell
   mkdir $env:USERPROFILE\dev
   cd $env:USERPROFILE\dev
   git clone https://github.com/0283999-wq/RocketPY-2027.git
   ```

4. Open the `RocketPY-2027` folder and double-click **`start.bat`**.

The first launch creates `.venv` and installs the requirements (a few
minutes). Later launches skip that completely and just open the app in your
browser. To get new versions, double-click **`update.bat`** (it runs
`git pull` and then `start.bat`). Those two files are all you ever need.

Nothing here runs `pip.exe`: everything goes through
`.venv\Scripts\python.exe -m ...`, so computers that block Python launchers
(Device Guard) still work. If `start.bat` fails it writes the full output to
**`install_log.txt`** - send that file to whoever is helping you.

**The PDF report needs Edge or Chrome** (Edge ships with Windows). If neither
is found, `start.bat` tries Playwright's own Chromium, which is optional: if
it fails the app still runs and the DOCX report works.

If .bat files are blocked on your computer, use the PowerShell launcher
instead (same logic):

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

#### If something goes wrong

| What you see | What it means / what to do |
|---|---|
| "Python 3.12 was not found and could not be installed automatically" | Install Python 3.12 (64-bit) from python.org, tick **Add python.exe to PATH**, double-click `start.bat` again. |
| "Windows on this computer blocks Python programs (Device Guard / Smart App Control)" | The PC's security policy blocks it. Ask your IT department or use another computer. If `python.exe` itself is the blocked file, it is the same problem. |
| "pip could not reach the internet" | A real network problem: check Wi-Fi, VPN or proxy. University networks often block downloads - try a phone hotspot. |
| "The disk is full" | Free some space, then double-click `start.bat` again. |
| "This folder path has accents or special characters" | Move the project to a plain path such as `C:\Users\<you>\dev\RocketPY-2027`. |
| "NOTE: this folder is synced by OneDrive" | It works, but it is slow and risky for `.venv`. Clone into `%USERPROFILE%\dev` instead. |
| "Recreating .venv because ..." | Normal: the old environment was broken or made with another Python version, so it is rebuilt automatically. |
| "Installing the requirements failed (not a network problem)" | Send `install_log.txt`. |

### macOS / Linux

There's no double-click launcher for these yet, but the app itself is
plain Python + NiceGUI and runs the same way:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m bup_rocketpy.gui.app
```

Then open the URL it prints (usually <http://localhost:8080>) in your
browser.

## Status

See `CHANGELOG.md` for the full history of what's been built and every
honestly-documented limitation along the way. Short version: load a
`.ork` + `.eng` with **no overrides** and
click Simulate - full KPIs, plots, recovery panel, RCSM cases, Monte Carlo
(parallelized across CPU cores), the PDF/DOCX report, an OpenRocket-format
CSV export, and a self-contained `.py` export all work end to end against
PROMETEO's real `.ork`. The results view always shows a live-computed
validation chip (never a stale hardcoded claim) summarizing the app's
real flight-data validation track record against Phase 2's V1/V2 tests
(+-5% tolerance) - see the Validation page for the full detail,
including any case still marked inconclusive for lack of input data.
`PrometeoLasc2026.ork`'s
own OpenRocket overrides are also incomplete (only one bodytube's shell
mass, not the whole rocket), so the app's automatic mass/CG estimate for
it is unstable - a manual override is available in the UI's Advanced
panel until that `.ork` is fixed in OpenRocket.

## How to cite / Beyond UP

This project is built on [RocketPy](https://github.com/RocketPy-Team/RocketPy),
whose 6-DOF simulation core does all of the actual trajectory work - this
app is an OpenRocket-to-RocketPy translation layer, a UI, and a report
generator around it, not a replacement for it. If you use RocketPy itself
(directly or through this app), please cite its validation paper:

> Ceotto, G. H., et al. "RocketPy: Six Degree-of-Freedom Rocket Trajectory
> Simulator." *Journal of Aerospace Engineering*, 2021.
> DOI: [10.1061/(ASCE)AS.1943-5525.0001331](http://dx.doi.org/10.1061/%28ASCE%29AS.1943-5525.0001331)

```bibtex
@article{rocketpy,
  title   = {RocketPy: Six Degree-of-Freedom Rocket Trajectory Simulator},
  author  = {Ceotto, Giovani Hidalgo and Alves, Guilherme Fernandes and Junqueira, Mateus Stano and Bressan, Pedro Henrique Marinho and others},
  journal = {Journal of Aerospace Engineering},
  year    = {2021},
  doi     = {10.1061/(ASCE)AS.1943-5525.0001331}
}
```

This application and the Beyond UP RocketPy pipeline were built by the
**Beyond UP** rocketry team at Universidad Panamericana, submitted for the
LASC RocketPy Computational Simulation award. If you reference this
specific app or its PROMETEO / Mission 44 validation work:

```bibtex
@software{beyondup_rocketpy,
  title  = {Beyond UP RocketPy: an OpenRocket-to-RocketPy simulation pipeline},
  author = {{Beyond UP}},
  year   = {2026},
  url    = {<REPLACE WITH THIS REPO'S PUBLIC URL>}
}
```

## License

The application code in this repository (`bup_rocketpy/`, `tests/`, and
the Beyond UP-authored files under `reference/prometeo_mission44/`) is
MIT-licensed - see `LICENSE`. `reference/openrocket_examples/` carries its
own GPLv3 license inherited from the OpenRocket project - see
`LICENSE.OpenRocket` and that folder's own README. RocketPy itself
(a separate, pip-installed dependency, not vendored in this repo) is
MIT-licensed by the RocketPy Team.
