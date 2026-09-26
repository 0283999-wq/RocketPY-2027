# Morning report - overnight autonomous run (2026-09-26 -> 2026-09-27)

Status as of Part 1 (Correctness) complete. This file is updated again at
the end of the run with whatever else got done. `main` builds and passes
its full test suite after every commit below - nothing here left the app
in a broken state.

## Status table

| Item | Status |
|---|---|
| A - drag curve contaminated by parachute descent | **Done** |
| B - drag curve Mach coverage warning | **Done** (RocketSerializer real invocation not attempted - no Java+OpenRocket+rocketserializer available to test against in this sandbox; detection + honest fallback message only) |
| C - reproducibility (commit hash, file hashes, History columns, "Clean up corrupt runs") | **Done** |
| D - reefed parachute with line cutter (RCSM REC 8.1.1) | **Done** |
| E - small fixes (LASC filenames, MC default N, landing map) | **Done** |
| F - new formal report (replaces old compliance-style one) | **Done** (built earlier this run, before item D) |
| G - CSV export like OpenRocket (58 columns, events) | **Done** |
| H - launch-day mode + competition profiles + README | Not started |
| I - real-weather validation (Open-Meteo historical) | Not started |
| J - Mission Control UI redesign | Not started (lowest priority, only attempted if everything else lands safely) |

Continuing now with H, I in that order; J assessed for remaining
time/budget last and will be honestly reported as deferred if there
isn't a safe amount of session left to do it without risking the working
app.

## Validation numbers (before/after this run)

No validation-affecting physics changed sign of before/after in a
regression sense; the two real corrections this run made (A, B) sharpen
honesty of the existing numbers rather than changing PROMETEO's own
default-path apogee:

- **V1** (2026-07-04 profile): predicted 1132.13 m vs target 1019.9 m
  (+11.00%). Unchanged by A-E; this is a Cd-curve/atmosphere-fidelity gap
  already flagged PROVISIONAL, not something A-E touches.
- **V2** (LASC apogee): predicted 1067.42 m vs target 1137.0 m (-6.12%).
  Unchanged by A-E.
- **PROMETEO no-override default path**: apogee ~1080 m, static margin
  ~1.9 cal, descent rate ~5.5 m/s, no Cd>1.5 in the extracted drag curve
  (item A's fix - previously the extracted curve could include points
  from the parachute-descent phase, which are not power-off/power-on
  aerodynamic drag at all and could exceed physically sane Cd values).
- **Major Tom** (single vehicle, single parachute in the .ork): now
  correctly triggers item B's Mach-coverage warning when its flight's max
  Mach exceeds the loaded drag curve's own Mach range, instead of
  silently extrapolating past the curve with no indication on screen.

## Exact PowerShell commands (unchanged from before this run)

```powershell
git pull
.\start.bat
```

`start.bat` re-syncs `requirements.txt` on every run now (fixed earlier
this week), so no separate reinstall step is ever needed after a `git pull`.

## One-line asks (nothing urgent - these are FYI, not blockers)

- Diego: if/when you get a real drop-test descent rate for a reefed
  chute, the "Compute reefed diameter" button on the Rocket page can be
  cross-checked against it (currently unverified physics estimate, says
  so on screen).
- RocketSerializer (item B) still can't be exercised end-to-end without
  Java + the OpenRocket jar on a real machine - if you want the real
  cross-check (not just the detection message), that has to happen on
  your Windows box, not in this cloud sandbox.

No blockers logged under "BLOCKED / NEEDS DIEGO" in PROGRESS.md as of
this point - continuing autonomously per your instructions.
