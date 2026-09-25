# stella-flight: Flight simulation and analysis for Stella Ignis (RocketPy)

A flight simulation and analysis **application** built on RocketPy, for the
Stella Ignis rocketry team (Universidad Panamericana). It reads a design
Diego already made in OpenRocket (`.ork`) plus its motor (`.eng`), and flies
it: plots, Monte Carlo, landing ellipse, the 4 RCSM cases, a PDF/DOCX report,
and the self-contained `.py` scripts LASC actually grades.

**This app does not design rockets.** Diego designs in OpenRocket; this app
simulates what he designs. See `CLAUDE.md` for the full brief, phases and
verified project facts - it is the source of truth for this repo, checked
against the real files on 2026-09-24.

```
OpenRocket -> .ork  (+ exported simulation CSV)
openMotor  -> .eng
        v  THIS APP
plots . Monte Carlo . landing ellipse . 4 RCSM cases . report . .py scripts for LASC
```

## Layout

- `stella_flight/` - importable core library (no UI)
  - `ork_reader.py` - pure-Python `.ork` reader (zip or bare XML)
  - `motor_reader.py` - `.eng` (RASP) and OpenRocket thrust-CSV readers
  - `translate.py` - builds rocketpy `Environment`/`SolidMotor`/`Rocket`/`Flight` from parsed data
  - `rcsm.py` - RCSM Ed.7 Rev.1 compliance checker (rail exit, static margin, T/W, recovery topology, payload)
  - `environment.py` - atmosphere builder (Phase 2 will add Open-Meteo/GFS/sounding sources)
  - `gui/` - NiceGUI layer (Phase 3, not started)
- `reference/prometeo_mission44/` - PROMETEO / Mission 44 (LASC 2026), the validated reference implementation this app's translation logic is checked against
- `docs/rcsm_reference.md` - RCSM rule text and IDs used by `rcsm.py`

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Status

**Phase 0** (repo realignment) and **Phase 1** (`.ork`/`.eng` readers +
translation into rocketpy objects) are in progress - see `CHANGELOG.md` and
`NOTES_FOR_DIEGO.md`. There is still no PROMETEO or Major Tom `.ork` file in
this repo, so Phase 1's acceptance check (mass/CG/CP within 1% of OpenRocket)
is **not yet validated** - the reader has instead been checked against
OpenRocket's own public example files. Every result is PROVISIONAL until
Phase 2's V1/V2 validation tests pass (per `CLAUDE.md` Rule 3).
