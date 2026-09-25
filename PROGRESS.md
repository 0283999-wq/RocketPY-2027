# PROGRESS - autonomous overnight run

Started 2026-09-25. This file is the resume point if context gets compacted -
check here first, then CHANGELOG.md for detail.

## Checklist (2026-09-26 overnight run: fix upload bug -> code-to-code check -> UI redesign -> remaining phases)

- [x] Item 0: upload handler bug FIXED. Root cause: NiceGUI 3.17.1's
      `UploadEventArguments` has `.file` (async `FileUpload.save()`), not
      the old `.content`/`.name` API `app.py` was written against - the
      handlers were also sync `def`, not `async def`, so the `await` this
      needed couldn't even be added without that change too. Fixed both.
      Added `tests/test_phase0_e2e.py`: launches the real app as a
      subprocess, drives real headless Chromium (pre-installed at
      `/opt/pw-browsers/chromium`, a symlink straight to the chrome
      binary - the pip-installed `playwright` package's own version-
      pinned lookup didn't match what's on disk, had to pass
      `executable_path` explicitly), uploads PROMETEO's real `.ork`+`.eng`
      through the actual `<input type=file>` elements, clicks through to
      results, asserts the apogee (1198.7 m) is rendered. PASSED. Also had
      to strip `PYTEST_CURRENT_TEST` from the subprocess env - NiceGUI's
      own `is_pytest()` check was tripping on it and demanding a
      `NICEGUI_SCREEN_TEST_PORT` env var meant for ITS OWN in-process
      Screen-testing convention, which this deliberately bypasses in favor
      of a real subprocess + real browser.
- [~] Item 1: code-to-code check vs OpenRocket - CONFIRMED real (not
      weather), ROOT CAUSE NOT YET ISOLATED despite rigorous elimination.
      See "Item 1 findings" below for the full diagnostic table and what
      was ruled out with hard numbers. Not tuned to force a match - per
      Diego's explicit instruction, and because tuning without
      understanding the cause would just hide the bug, not fix it.
- [ ] Item 2: UI redesign (palette, sidebar, rocket drawing, History,
      Exports, Validation pages, Playwright screenshots)
- [x] Item 3 / Phase 4: Monte Carlo + landing ellipse -
      stella_flight/monte_carlo.py. Found and worked around 3 real bugs in
      rocketpy==1.13.0's own Stochastic subsystem (see
      tests/test_phase4_monte_carlo.py's docstring for the full list -
      broken default export_list, CG not preserved unless explicit,
      add_nose/add_trapezoidal_fins internal kwarg mismatch). N=20 test:
      0 excluded, apogee 1205.6m mean, 90% interval [1164.6, 1301.5].
      1/2/3-sigma landing ellipses computed from impact sample covariance.
      NOT yet wired into the UI (Monte Carlo page) or given a
      progress-bar/cancel UI - backend only so far.
- [x] Item 3 / Phase 5 (rest): PDF/DOCX report (validation section first,
      wording checked against CLAUDE.md Sec 3.1's rule) + LASC .zip
      (per-case .py + .eng + .ork + Cd curves). stella_flight/report.py,
      stella_flight/lasc_package.py. 3/3 tests pass
      (tests/test_phase5_report_and_zip.py).
- [x] Item 3 / Phase 6: weathercocking sweep (ballast at nose tip, finds
      PROMETEO's optimum at the lower bound - no ballast needed, matches
      CLAUDE.md's own prediction) + drag comparison with common random
      numbers (identical curves -> exactly 0.0 difference; 15%-higher-Cd
      curve -> -41.1 m [-42.4, -39.8] at 90%, CI excludes zero). Found a
      4th real rocketpy==1.13.0 Stochastic-subsystem bug while building
      this: none of the 4 Stochastic* classes forward `seed=` to their
      base class, and setting the private RNG post-construction doesn't
      work either (samplers are already bound to the old generator) -
      fixed by monkeypatching numpy.random.default_rng narrowly around
      just the 4 constructor calls (stella_flight/monte_carlo.py's
      _seeded_rng). stella_flight/analysis.py,
      tests/test_phase6_analysis.py, 3/3 pass.
- [x] Item 2: UI redesign - `stella_flight/gui/theme.py` (gold #B79357 /
      wine #8A1538, dark mode, WCAG AA contrast notes, one file to swap
      for a rebrand), `layout.py` (header + left sidebar, 8 pages), and
      all 8 pages built: Simulate (4-step: Load->Review->Simulate->
      Results, PROVISIONAL badge, KPI cards, rocket drawing, tabbed
      plots, Advanced panel for overrides/Cd CSVs), Rocket (side-profile
      + dimensions/CG/margin), Monte Carlo (uncertainty table + histogram
      + landing ellipse plot), RCSM Cases (4 buttons + compliance table),
      Analysis (weathercocking + drag comparison UI), History (auto-save
      every run to `runs/`, list/compare/delete), Exports (CSV/PNG/PDF/
      DOCX/LASC zip), Validation (V1/V2 status display).
      `tests/test_phase0_e2e_full.py`: real headless-Chromium run through
      every page, screenshots saved to `docs/screenshots/` (8 files).
      Both E2E tests pass. No logo files exist yet - using the text
      wordmark fallback, see BLOCKED below.
- [x] Item 3 / History backend: `stella_flight/run_history.py` - auto-
      saves every Simulate run to `runs/<timestamp>/` (record.json +
      copies of .eng/CSV/plots), list/get/delete. Not committed to git
      (`.gitignore`d, per-machine local data, like `outputs/`).
- [ ] Item 3 (still not done): Major Tom testing (`.ork` not yet in the
      repo - see BLOCKED below). Monte Carlo is NOT cancellable and does
      NOT run in a background thread (blocks the UI during the run) -
      CLAUDE.md Sec 6 Phase 4 asked for both; scope-cut for time, see
      BLOCKED below.



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
- [x] Phase 5 (Ballistic+Nominal, priority 3): translate.build_rocket/
      ork_to_flight now take include_recovery= (False = Ballistic, no
      parachutes regardless of .ork config). stella_flight/case_export.py
      generates self-contained Mission44_{Ballistic,Nominal}_RocketPy_v1.py
      (no stella_flight import - CRS 10.1.5/10.1.6).
      tests/test_phase5_case_export.py: built a genuinely clean venv, `pip
      install rocketpy==1.13.0` fresh, ran both exported scripts as
      subprocesses. Both matched the in-process apogee to 0.0027% -
      confirms the exported files are truly standalone and correct, not
      just "imports fine". PASSED.
- [ ] Phase 5 (rest): drogue-only / main-at-apogee, PDF/DOCX report
- [ ] Phase 6: weathercocking sweep, drag comparison
- [x] MORNING_REPORT.md written and pushed last - Phase 4/rest-of-5/6 not
      reached (priorities 1-3 done, ran out of tonight's scope after that,
      per Diego's own stated priority order - not a blocker, just where
      tonight stopped).

## Item 1 findings (code-to-code check vs OpenRocket, 2026-09-26)

`tests/test_code_to_code_vs_openrocket.py` reproduces OpenRocket's own two
CSV-exported sims with EXACTLY their own inputs (no weather uncertainty -
both sides use the identical numbers OpenRocket itself recorded).

| | Brasil/LASC-design | July4 as-flown |
|---|---|---|
| OpenRocket apogee AGL | 1081.69 m | 1027.20 m |
| Ours | 1191.70 m | 1124.09 m |
| **Error** | **+10.17%** | **+9.43%** |
| OpenRocket burnout altitude | 248.51 m | 196.92 m |
| Ours | 259.85 m | 242.03 m (see note) |
| OpenRocket burnout velocity | 158.78 m/s | 140.28 m/s |
| Ours | 157.75 m/s | 148.94 m/s (see note) |
| Reference area | 0.00943 m2 | 0.00943 m2 (identical) |

**July4's own gap is now explained, not a code bug**: OpenRocket's July4
CSV shows its OWN burnout at **t=3.12s**, total impulse **1732.4 Ns**,
peak thrust 653 N (`verified_constants.json`'s `julio4_asflown_sim` block)
- a DIFFERENT, shorter/hotter motor burn than the Brasil config
(t=3.57s, 1871 Ns). We only have ONE `.eng` file (the Brasil-derived
Icarus_I_K519.eng), so the July4 comparison necessarily used the WRONG
motor profile - more impulse than OpenRocket assumed for that CSV predicts
a higher apogee, consistent with the direction of the error. This was
already flagged in `config.py`'s own comments ("Its own OpenRocket run
carries a different motor/mass... 1732 Ns vs 1871 Ns impulse... NOT
silently reconciled here") - not a discovery, a confirmation.

**Brasil's gap is real and NOT explained by a data mismatch** - inputs are
apples-to-apples (same `.eng`, same mass, same site). Ruled out by direct
measurement, each confirmed exact or effectively exact:
- Dry mass: 0.000% error (already known).
- Reference area: 0.009434 m2 both sides (OpenRocket's own stored
  94.343 cm2 vs `pi*radius^2` from the same 0.0548 m radius) - Diego's
  suspect #1, ruled out.
- Cd curve values: `rocket.power_on_drag(0.3)=0.4446` vs OpenRocket's own
  boost-phase 0.445 at Mach 0.302; `power_off_drag(0.3)=0.4430` vs
  OpenRocket's own coast-phase 0.443 at Mach 0.300 - matches to <0.1%,
  both curves correctly assigned (not swapped).
- Motor: total impulse 1871.35 Ns (matches), burn_out_time 3.57 s
  (matches), individual thrust samples match the `.eng` file's own listed
  values at several timestamps checked by hand.
- Atmosphere: density 1.16785 kg/m3, matches the ideal-gas calc from
  `config.py`'s own T/P constants to 5 decimal places; gravity 9.78599
  m/s2 matches OpenRocket's own recorded 9.786 exactly.
- `terminate_on_apogee=True` was NOT inflating the number - reran without
  it, identical apogee (1191.70 m either way).
- Drag curve extrapolation below its lowest sample (Mach 0.138) is
  constant (flat at 0.432), not degenerate/collapsing toward zero -
  ruled out a "near-apogee low-Mach drag vanishes" theory.
- Angle-of-attack profile looks physically normal (a few degrees of
  weathercocking early, near-zero mid-flight, a small rise approaching
  apogee) - no obvious sign of an oscillation/instability eating energy
  into induced drag, though this wasn't tested by directly correcting the
  known 6.6%-high I_11 inertia and re-running (would need a rebuild path
  that isn't a quick monkeypatch - flagged as the next thing to try, not
  done tonight).
- Rail exit is actually **slower** in our sim (15.60 m/s) than
  OpenRocket's 16.78 m/s, and **earlier** (t=0.487 vs t=0.52) -
  this rules out the simplest "we apply too little drag/too much thrust
  from t=0" theory (that would predict a HIGHER, not lower, rail-exit
  speed), but is itself an unexplained ~7% discrepancy at the very start
  of flight that could be a clue - not chased further tonight.

**Conclusion, stated plainly**: this is a real, still-unexplained ~10%
systematic overshoot in the reference model's own trajectory integration,
present even with verified-identical mass/area/Cd/thrust/atmosphere
inputs. Not tuned to hide it. Best remaining leads for whoever picks this
up next: (1) the rail-exit speed/timing mismatch despite matching thrust
curves, (2) the known 6.6% I_11 inertia error's effect on AoA/margin
evolution once actually corrected and re-tested (not just reasoned about),
(3) whether `stella_flight.translate`'s OWN pipeline (not reference code)
reproduces the same gap or a different one - would help tell whether this
is in RocketPy's own dynamics for this specific geometry/motor
combination, or something in how `reference/prometeo_mission44`
specifically builds the `Rocket`/`Flight` objects.

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
- ~~**No live browser test of the NiceGUI app**~~ RESOLVED 2026-09-26:
  Playwright + pre-installed headless Chromium now drive the real app
  through real browser sessions (`tests/test_phase0_e2e.py`,
  `test_phase0_e2e_full.py`). Diego should still confirm it looks/feels
  right on his own machine with a real mouse - automated screenshots
  (`docs/screenshots/`) aren't a substitute for actually using it.
- **No logo files** at `stella_flight/gui/assets/logo_gold.png` or
  `logo_wine.png` - the header shows a text wordmark ("Stella Ignis /
  stella-flight") instead. Drop the real logo files in that folder
  whenever the rebrand assets are ready; `theme.py`/`layout.py` will pick
  them up automatically, no other code changes needed.
- **Monte Carlo doesn't run in the background and isn't cancellable** -
  CLAUDE.md Sec 6 Phase 4 asked for both ("runs in the background, with
  progress, cancellable, saving partial results"). Tonight's
  implementation runs synchronously on the UI thread with a progress
  LABEL (updates between simulations) but no true background
  thread/cancel button and no partial-results save if interrupted mid-run
  - a real scope cut for time, not forgotten.
- **Monte Carlo/drag-comparison N is capped low in practice for UI
  responsiveness** - each sample is a full 6-DOF flight; N=200 (CLAUDE.md's
  default) will take real wall-clock time synchronously blocking the
  page. Works correctly, just slow at the full default N without the
  background-thread work above.
- **Landing ellipse is a static matplotlib plot, not the Leaflet map on
  site imagery CLAUDE.md Sec 6 Phase 4 asked for** - shows the correct
  1/2/3-sigma ellipses and impact scatter in X/Y meters from the pad, but
  not overlaid on an actual map. A reasonable scope cut given the time
  left, not a hidden gap.

## Log

- 06:30 Pulled Diego's `rocket.ork` upload (landed at repo root), moved to
  `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork` to match the
  existing data/ layout. Confirmed plain-XML (not zipped), OpenRocket 24.12,
  2 stored simulations (both Brasil-config variants, rail 4.0m/10deg from
  vertical, elevation 495.0m and 490.0m respectively - investigating which
  is the LASC-as-flown one next.
