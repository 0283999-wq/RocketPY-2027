# PROGRESS - autonomous overnight run

Started 2026-09-25. This file is the resume point if context gets compacted -
check here first, then CHANGELOG.md for detail.

## Checklist

- [x] Phase 0: repo restructure (common/ -> stella_flight/) - commit 59c4c19
- [x] Phase 1a: ork_reader.py, motor_reader.py, translate.py built - commit 0dc168c
- [x] Phase 1b: real acceptance test vs PROMETEO's real .ork (moved to
      `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork`) -
      tests/test_phase1_acceptance.py, 5/5 pass (with 2 honestly-documented
      known limitations, not hidden - see "Phase 1 findings" below)
- [x] Phase 1c: fix Cd=0.5 placeholder -> real power_on/off_drag.csv curves
      (translate.build_rocket/ork_to_flight now REQUIRE a drag curve path,
      no silent default)
- [ ] Phase 1d: coordinate-convention test (tail_to_nose vs nose_to_tail, same CP/margin) - NOT DONE YET, next
- [x] Phase 1e: fix "validated" language - ork_reader.SimulationReference
      docstring + all Phase 1 tests explicitly say "OpenRocket reference,
      NOT validated" (validated = compared to flight data, Phase 2 only)
- [x] Phase 2: V1 (2026-07-04, 1019.9 m) + V2 (LASC, 1137 m) validation tests -
      tests/test_phase2_validation.py. Both OUTSIDE +-5%, honestly reported,
      not tuned - see "Phase 2 findings" below.
- [x] Phase 2: Cd-extraction-from-CSV vs committed drag curves - IDENTICAL
      (re-running scripts/extract_drag_curves.py against
      Prometeo_Launchsite_BRASIL.csv reproduces power_off_drag.csv and
      power_on_drag.csv byte-for-byte - fully deterministic, not stale).
- [x] Phase 2: telemetry_2026_07_04.xlsx inspected - see "Phase 2 findings" below.
- [x] Phase 3: NiceGUI app, start.bat, headless smoke test -
      stella_flight/gui/{pipeline.py,app.py}, tests/test_phase3_headless.py
      (5/5 pass). Upload .ork+.eng -> import table -> Simulate -> big
      numbers + plots + CSV. Drag curve auto-extracted from the .ork's own
      stored sim when present (falls back to user-uploaded CSV or a
      flagged placeholder). Manual dry-mass/CG override fields exposed in
      the UI (needed for PROMETEO right now - see Phase 1 findings).
      start.bat creates .venv + installs pinned requirements + opens
      browser on first run. NOT tested with a live browser/display (no
      display server in this container) - only the pipeline layer (no
      NiceGUI import) and a clean import of app.py are verified headlessly.
- [ ] Phase 4: Monte Carlo + landing ellipse
- [ ] Phase 5: Ballistic + Nominal cases, per-case .py export (CRS 10.1.6),
      tested in a clean venv
- [ ] Phase 5 (rest): drogue-only / main-at-apogee, PDF/DOCX report
- [ ] Phase 6: weathercocking sweep, drag comparison
- [ ] MORNING_REPORT.md written and pushed last

## Phase 2 findings

**telemetry_2026_07_04.xlsx**: sheet "Prometeo-Telemetría" (a 2nd sheet,
"grafica altura vs tiempo", is an empty MATLAB-plot placeholder). Real data
table starts at row 24 (`Pkt_Num, Tiempo_ms, Pitch_deg, Roll_deg,
Altitud_m, Velocidad_ms, Aceleracion_ms2, Estado, Estado_Nombre`), 72
packets, packet numbers 18-132 (not 1-114 - the first 17 packets of the
flight are missing from this export, not just "idle" - unclear if lost or
just not included), median dt=400ms (2.5 Hz, matches config.py's
AVIONICS_SAMPLING_RATE), one gap of 166.9s in the dt sequence (likely
between two logging sessions, e.g. pre-launch idle vs. flight - needs
Diego to confirm, not assumed). Apogee packet is #118 at t=1718923ms,
Altitud_m=1019.9 (matches the known V1 target exactly). Signal is lost
after packet 132 (t=1889023ms), consistent with config.py's
REAL_SIGNAL_LOSS_T=19.4s post-ignition note. A full altitude-residual RMS
against this table (the profile half of V1) is NOT yet built - only the
apogee number was used tonight; that's the next natural addition if time
allows.

**Cd extraction reproducibility**: re-ran
`reference/prometeo_mission44/scripts/extract_drag_curves.py` fresh
against `Prometeo_Launchsite_BRASIL.csv` and diffed the output against the
already-committed `power_off_drag.csv`/`power_on_drag.csv` - **byte-for-
byte identical**. The committed curves are exactly reproducible from
source, not stale or hand-edited.

**V1 (2026-07-04)**: predicted apogee AGL = 1124.1 m vs. flight telemetry
1019.9 m, **error +10.22%** (outside +-5%). Used
`reference/prometeo_mission44`'s own validated rocket model (config.py's
already-existing `site="julio4"` environment, with `LAUNCH_MASS=10.96`,
`MOTOR_MASS_LOADED=4.882948`, `MOTOR_DRY_MASS=2.866213` from
`verified_constants.json`'s `julio4_asflown_sim` block - these ARE this
flight's own as-flown numbers). Breakdown of the miss: the dry CG used is
the **Brasil**-config's derived value (0.6279 m from nose), not a July4-
specific measurement - none exists anywhere in the project's files.
CLAUDE.md Sec 3.1 documents that real mass reductions happened between
report-time and LASC-flight-time; the July4 flight sits at a different
point in that same timeline, so reusing the Brasil CG is a real,
documented approximation, not a hidden one. Drag curve used is also the
Brasil-config curve. **Not tuned to force a pass - stays PROVISIONAL.**

**V2 (LASC)**: predicted apogee AGL = 1196.9 m vs. flight telemetry 1137 m,
**error +5.27%** (just outside +-5%). Mass = 10.370 kg (measured, per
tonight's explicit instruction). Site/rail from the real .ork's "brasil
2026" stored simulation. Breakdown: motor mass kept at the Brasil-config
value (4.7378 kg loaded) since no LASC-specific motor-mass figure exists
separately from the 10.370 kg total; wind/temp/pressure are the .ork's own
recorded t=0 values, NOT the real Iacanga flight-day weather (that's
explicitly pending from Diego per tonight's validation rules - the
Open-Meteo/GFS path is built but untested against real data here). Worth
flagging: this result is close (0.27 points over the line) - real weather
alone could plausibly close the gap. **Not tuned to force a pass - stays
PROVISIONAL.**

Neither V1 nor V2 currently uses `stella_flight`'s own `.ork`-driven
`translate.py` pipeline for the rocket model - both reuse
`reference/prometeo_mission44`'s already-validated code directly, with
per-flight masses substituted in. This was a deliberate choice for speed
and correctness tonight (that code is proven; `translate.py`'s own
mass/CG estimate has the documented 19% gap from Phase 1 and produces a
marginally-unstable rocket for this .ork without a corrected overridecg).
Wiring V1/V2 through `stella_flight.translate` instead of the reference
code directly is real follow-up work once Diego's .ork has a whole-rocket
override, so the app's OWN pipeline is what's actually being validated,
not a stand-in.

## BLOCKED / NEEDS DIEGO

- **`.ork` needs a whole-rocket `overridemass`+`overridecg`** (only the
  Fuselage shell is overridden right now) - this is the one input
  `stella_flight`'s generic reader+translate pipeline cannot substitute
  for. See Phase 1 findings in CHANGELOG.md.
- **Real Iacanga flight-day weather** for V2 - Diego runs Open-Meteo/GFS
  on his own machine per tonight's validation rules; the cloud can't reach
  those servers.
- **Exact LASC flight date/time** (Diego said "pending from me", 2026-09-03
  to 09-05 around 12:00 local) - needed once real weather is pulled.
- **Major Tom's `.ork`** and both `.eng` files (K503, M1739-P) - not
  touched tonight, PROMETEO validation was the priority.
- **No live browser test of the NiceGUI app** - this container has no
  display server. Diego should double-click `start.bat` and confirm the
  UI actually renders and the upload/Simulate flow works end to end on
  his machine; only the underlying pipeline is verified here.

## Log

- 06:30 Pulled Diego's `rocket.ork` upload (landed at repo root), moved to
  `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork` to match the
  existing data/ layout. Confirmed plain-XML (not zipped), OpenRocket 24.12,
  2 stored simulations (both Brasil-config variants, rail 4.0m/10deg from
  vertical, elevation 495.0m and 490.0m respectively - investigating which
  is the LASC-as-flown one next.
