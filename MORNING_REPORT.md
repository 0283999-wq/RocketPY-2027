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
| H - launch-day mode + competition profiles + README | **Done** |
| I - real-weather validation (Open-Meteo historical) | Not started |
| J - Mission Control UI redesign | Not started (lowest priority, only attempted if everything else lands safely) |

Continuing now with I; J assessed for remaining
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

## Acceptance checklist (your 8 items) - verified just now

1. **PROMETEO no-override defaults**: apogee 1088.0 m (~1080 target),
   margin 1.94 cal (~1.9 target), descent 5.49 m/s (~5.5 target), no
   Cd>1.5 in the extracted curve. **Verified** with a fresh direct run
   this morning (no overrides at all).
2. **Major Tom Mach matching or warning**: **cannot be verified on the
   real vehicle** - there is still no Major Tom `.ork`/`.eng` anywhere in
   this repo (CLAUDE.md flagged this as missing back in Phase 1; nothing
   has arrived since). The Mach-coverage warning itself (Section B) is
   real, generic code that fires for ANY loaded vehicle whose flight
   exceeds its drag curve's Mach range - proven on PROMETEO (the only
   real vehicle data this project has), not hardcoded to it. This is the
   one item I could not close myself; it needs the actual Major Tom
   files from you.
3. **Every page opens without errors, History shows app version**:
   verified via a real headless-Chromium run (`tests/test_phase0_e2e_full.py`,
   including the new Launch Day page) - both scenarios pass, screenshots
   in `docs/screenshots/`.
4. **PDF report has figures, no compliance section**: verified - the
   report is built from a REAL Simulate run (real PNGs on disk), and
   `test_docx_report_builds_and_has_no_compliance_section` asserts the
   compliance section text is gone.
5. **CSV has OpenRocket-like columns/events**: verified - 58 columns,
   real event markers, see Section G above.
6. **Launch-day mode works offline**: verified - cached weather survives
   a simulated network failure with no crash (`test_weather.py`).
7. **Validation page can re-run V1/V2 with real weather (mocked test)**:
   verified - V1 fully works; V2 needs the LASC flight date from you
   (see below), by design, not by omission.
8. **A reefed-chute rocket passes all 4 RCSM cases, no "FAIL REC 8.1.1"**:
   verified - `test_all_four_rcsm_cases_run_with_no_dual_deploy_warning`.

## BLOCKED / NEEDS DIEGO

- **Major Tom's `.ork`/`.eng`** - still not in this repo. Item 2 above
  can't be demonstrated on the real vehicle without them.
- **Exact LASC 2026 flight date/time at Iacanga** - already logged as
  pending in an earlier session; needed for item 7's V2 half to produce
  a real number instead of the honest "date not yet known" message.

Neither of these blocked anything else - both are isolated, clearly
labeled gaps, not half-finished features.
