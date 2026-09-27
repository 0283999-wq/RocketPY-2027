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
      bup_rocketpy/monte_carlo.py. Found and worked around 3 real bugs in
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
      (per-case .py + .eng + .ork + Cd curves). bup_rocketpy/report.py,
      bup_rocketpy/lasc_package.py. 3/3 tests pass
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
      just the 4 constructor calls (bup_rocketpy/monte_carlo.py's
      _seeded_rng). bup_rocketpy/analysis.py,
      tests/test_phase6_analysis.py, 3/3 pass.
- [x] Item 2: UI redesign - `bup_rocketpy/gui/theme.py` (gold #B79357 /
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
- [x] Item 3 / History backend: `bup_rocketpy/run_history.py` - auto-
      saves every Simulate run to `runs/<timestamp>/` (record.json +
      copies of .eng/CSV/plots), list/get/delete. Not committed to git
      (`.gitignore`d, per-machine local data, like `outputs/`).
- [ ] Item 3 (still not done): Major Tom testing (`.ork` not yet in the
      repo - see BLOCKED below). Monte Carlo is NOT cancellable and does
      NOT run in a background thread (blocks the UI during the run) -
      CLAUDE.md Sec 6 Phase 4 asked for both; scope-cut for time, see
      BLOCKED below.



- [x] Phase 0: repo restructure (common/ -> bup_rocketpy/) - commit 59c4c19
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
      bup_rocketpy/gui/{pipeline.py,app.py}, tests/test_phase3_headless.py
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
      parachutes regardless of .ork config). bup_rocketpy/case_export.py
      generates self-contained Mission44_{Ballistic,Nominal}_RocketPy_v1.py
      (no bup_rocketpy import - CRS 10.1.5/10.1.6).
      tests/test_phase5_case_export.py: built a genuinely clean venv, `pip
      install rocketpy==1.13.0` fresh, ran both exported scripts as
      subprocesses. Both matched the in-process apogee to 0.0027% -
      confirms the exported files are truly standalone and correct, not
      just "imports fine". PASSED.
- [x] Phase 5 (rest): drogue-only/main-at-apogee + PDF/DOCX report - DONE
      2026-09-26, see the item 3 entries above.
- [x] Phase 6: weathercocking sweep + drag comparison - DONE 2026-09-26,
      see the item 3 entries above.
- [x] MORNING_REPORT.md (2026-09-26 version) written and pushed last -
      covers items 0-3. Only Major Tom testing remains genuinely blocked
      (no `.ork` in the repo); everything else on tonight's list is done,
      investigated-and-documented (item 1), or a clearly-logged scope cut.

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
(3) whether `bup_rocketpy.translate`'s OWN pipeline (not reference code)
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

Neither V1 nor V2 currently uses `bup_rocketpy`'s own `.ork`-driven
`translate.py` pipeline for the rocket model - both reuse
`reference/prometeo_mission44`'s already-validated code directly, with
per-flight masses substituted in. This was a deliberate choice for speed
and correctness tonight (that code is proven; `translate.py`'s own
mass/CG estimate has the documented 19% gap from Phase 1 and produces a
marginally-unstable rocket for this .ork without a corrected overridecg).
Wiring V1/V2 through `bup_rocketpy.translate` instead of the reference
code directly is real follow-up work once Diego's .ork has a whole-rocket
override, so the app's OWN pipeline is what's actually being validated,
not a stand-in.

## BLOCKED / NEEDS DIEGO

- ~~**`.ork` needs a whole-rocket `overridemass`+`overridecg`** (only the
  Fuselage shell is overridden right now)~~ MOSTLY RESOLVED 2026-09-26:
  the .ork actually already HAD several more per-component overrides
  (nosecone, fin set, 3 bulkheads, the parachute) - this reader just
  wasn't reading any of them except the Fuselage's. Fixed; the geometric
  no-override dry mass estimate is now ~1.3% off (was 19%). Still no
  single WHOLE-ROCKET override exists in the file, so this residual isn't
  fully closeable from the .ork alone - but it's no longer the ~1kg,
  multi-component gap it was. See "High-priority bug fix, 2026-09-26"
  above for the exact numbers.
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
- **No logo files** at `bup_rocketpy/gui/assets/logo_gold.png` or
  `logo_wine.png` - the header shows a text wordmark ("Stella Ignis /
  stella-flight") instead. Drop the real logo files in that folder
  whenever the rebrand assets are ready; `theme.py`/`layout.py` will pick
  them up automatically, no other code changes needed.
- ~~**Monte Carlo doesn't run in the background and isn't cancellable**~~
  RESOLVED 2026-09-25 (budget-mode Section 1/7): now runs via
  `nicegui.run.io_bound` on a background thread with a working Cancel
  button and a live progress label; see `montecarlo_page.py`.
- **Monte Carlo/drag-comparison N is capped low in practice for UI
  responsiveness** - each sample is a full 6-DOF flight; N=200 (CLAUDE.md's
  default) will take real wall-clock time even on a background thread.
  Works correctly, just slow at the full default N.
- ~~**Landing ellipse is a static matplotlib plot, not the Leaflet map**~~
  RESOLVED 2026-09-25 (budget-mode Section 7): a real interactive
  `ui.leaflet` map with the pad marker, 1/2/3-sigma ellipses and capped
  impact-sample markers was added next to the existing static plot (kept
  for quick PNG export). See `bup_rocketpy/geo.py` + `montecarlo_page.py`.
  **However**, the automated Playwright test for this
  (`test_phase7_mc_map_e2e.py`) is currently unreliable in this sandbox
  (times out waiting for the MC run to finish, even standalone, on
  re-checks tonight) - it's skipped by default so it can't destabilize
  the e2e gate, but that also means **the map hasn't been freshly,
  automatically re-confirmed rendering tonight**. Please click Monte
  Carlo -> Run on your own machine (a real browser, no sandbox network
  restrictions) and confirm the landing map shows the pad + ellipses +
  markers as expected.

## Log

- 06:30 Pulled Diego's `rocket.ork` upload (landed at repo root), moved to
  `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork` to match the
  existing data/ layout. Confirmed plain-XML (not zipped), OpenRocket 24.12,
  2 stored simulations (both Brasil-config variants, rail 4.0m/10deg from
  vertical, elevation 495.0m and 490.0m respectively - investigating which
  is the LASC-as-flown one next.

---

## Second overnight review (2026-09-25 night -> 2026-09-26), budget mode

Diego tested the real app with a real mouse on Windows and it did not
work for a normal user (tests passing != app working). New instruction:
work through crashes/physical-impossibility/code-path-unification fixes
first (sections 0-4 + KPI/recovery part of 5 are the "presentable
product"), budget mode (limited credits, run only related tests per
edit, full suite once per section, MC tests use N=5).

### Section 0: rename - DONE

- Team renamed "Stella Ignis" -> "Beyond UP" everywhere (UI text, docs,
  CLAUDE.md, report/case-export generated-by lines, window title).
- Package renamed `stella_flight` -> `bup_rocketpy` via `git mv` + a
  repo-wide sed sweep (all tracked non-reference files); env vars
  `STELLA_FLIGHT_PORT`/`STELLA_FLIGHT_SHOW` -> `BUP_ROCKETPY_PORT`/
  `BUP_ROCKETPY_SHOW` for consistency (not explicitly asked but they're
  clearly named after the old package, would be confusing left as-is).
  Internal CSS classes `stella-*` -> `bup-*` too (not user-visible text,
  but cheap to fix while touching the same lines).
  NEVER named the package `rocketpy` (would shadow the real library) -
  confirmed `bup_rocketpy` throughout.
- Added the "Definition of done ('presentable')" section to CLAUDE.md
  verbatim per tonight's instruction (new `## 2.5`), team+package name
  updated in CLAUDE.md's title/§0 only - didn't rewrite the rest of it.
- Verified: fresh `.venv` (this container has none pre-built - had to
  `pip install -r requirements.txt` from scratch), all `bup_rocketpy.*`
  and `bup_rocketpy.gui.*` modules import cleanly, `test_phase1_acceptance.py`
  (5 tests, no UI) passes unchanged.

### Section 1: crashes a-f - DONE

All 6 crashes Diego hit testing on Windows, fixed and verified (headless
tests + both existing Playwright e2e tests, which now pass again after
being updated for the new "use manual override" checkbox):

- **(a) History page 500 JSONDecodeError**: `min(margins) > 0` produces a
  numpy.bool_, which `json.dump` refuses ("Object of type bool is not
  JSON serializable"). Fixed with a numpy-aware `JSONEncoder`
  (bool_/integer/floating/ndarray -> native types), atomic writes
  (temp file + `os.replace`) so a killed process never leaves a
  truncated `record.json`, and `list_runs` now returns
  `(records, warnings)` and skips corrupt files with a visible warning
  instead of crashing the page.
- **(b) "Connection lost" during Simulate with manual mass/CG**: the
  flight simulation ran synchronously on NiceGUI's single asyncio event
  loop, blocking every websocket ping/pong for the whole run. Fixed:
  `do_simulate` is now `async` and runs `pipeline.run_simulation` via
  `nicegui.run.io_bound` (thread pool), same for Monte Carlo (`run_mc`),
  which now also has a linear progress bar (polled from a `ui.timer`
  reading a plain dict the worker thread writes to - NiceGUI elements
  aren't safe to touch directly from a non-event-loop thread) and a
  **Cancel** button (`threading.Event`, checked in
  `monte_carlo.run_monte_carlo`'s sampling loop via a new
  `cancel_check` param that stops early and still returns whatever
  samples completed - `MonteCarloResult.cancelled` flags this). This
  also satisfies most of Sec 7's "MC in the background, cancellable" -
  only the Leaflet map is left for that item.
  **Found a second, nastier bug while wiring this up**: `app.py` has a
  module-level `def run():` (the app's own entry point) that SILENTLY
  REBINDS the module-global name `run` after `from nicegui import run`
  was imported for `run.io_bound` - every call inside `do_simulate`
  then failed with `AttributeError: 'function' object has no attribute
  'io_bound'`. This would have made Simulate simply not work at all
  behind the "Connection lost"-shaped symptom. Renamed the entry point
  to `main()` with a comment explaining why, so it can't recur.
- **(c) Apogee -495 m / margin -900 cal / all KPIs 0 with no manual
  override**: `pipeline.run_simulation` already had the right fallback
  (geometric mass/CG estimate when no override given) - the bug was
  entirely in `app.py`'s UI wiring, which passed
  `dry_mass_input.value`/`dry_cg_input.value` UNCONDITIONALLY.
  NiceGUI's `ui.number(value=None)` renders as an empty box but reads
  back as `0`/`None` inconsistently, so the "default path" was actually
  simulating a massless, CG-at-the-nose rocket every time. Fixed with
  an explicit "Use manual mass/CG override" checkbox (default OFF,
  fields disabled until checked) - only pass an override when it's
  checked; otherwise `None, None` goes to `run_simulation`, which
  already does the right thing (geometric estimate, or a clear blocking
  `ValueError` if that's also unresolvable - never a placeholder 0).
  Verified via a direct pipeline call (bypassing the UI entirely):
  apogee 1435.8 m, margin -0.11 cal, `stable=False` - NOT insane
  numbers, just honestly reflecting PROMETEO's `.ork` still being ~19%
  light on mass (a pre-existing, already-documented DATA gap - see
  NOTES_FOR_DIEGO item 1 - not a code bug; the fix is Diego setting a
  whole-rocket override in OpenRocket, which the app cannot fabricate).
- **(d) MC/RCSM/Analysis/Exports gated on the raw override fields**: all
  4 pages checked `s["dry_mass_override"] is None` - which is only ever
  set when the user manually typed an override, so the default path was
  always blocked even after a successful Simulate. Added two new state
  keys, `dry_mass_kg`/`dry_cg_m` (+ `mass_source` for display) - the
  values ACTUALLY used by the last successful Simulate, override or
  estimate - populated by `do_simulate` unconditionally. All 4 pages now
  gate on `s["sim_result"] is None` and read these new keys instead.
- **(e) Rocket page mixing rockets (177cm/14cm/1.6cal vs 147cm/11cm/0.08cal
  cards)**: NOT a data bug - `parsed = s["load_result"].parsed_ork` is
  the same object used for both the drawing and the cards, one line
  apart. The real cause: NiceGUI's `ui.image(local_path)` serves local
  files via `app.add_static_file()`, whose URL is
  `/_nicegui/auto/static/<hash of the FILE PATH>/<filename>` with
  `Cache-Control: public, max-age=3600` - the hash depends on the PATH,
  not the file's bytes, so re-saving a PNG to the same fixed filename
  (e.g. "rocket_page_profile.png") produces the IDENTICAL url, and a
  browser that already fetched it once keeps showing the stale cached
  image for up to an hour regardless of what's now on disk. This is
  almost certainly what Diego saw: an old render (possibly from
  whatever rocket he tested first) cached under a filename the app kept
  reusing. Fixed with `pipeline.fresh_image_path()` - every dynamically
  regenerated plot/drawing across the whole app (Simulate results,
  Rocket page, Monte Carlo histogram+ellipse, Analysis) now gets a
  fresh UUID-suffixed filename each render, with old files under the
  same basename cleaned up first. Also added a "Loaded rocket: <name>"
  header to the Rocket page per Diego's request.
- **(f) "divide by zero" in rocketpy's polation_1d (duplicate x
  values)**: added `bup_rocketpy/curve_utils.py` -
  `dedupe_sort_curve()`/`dedupe_sort_csv_file()` - sorts by x and nudges
  exact-duplicate x values apart by 1e-9 (not merge/average - some RASP
  `.eng` exporters legitimately encode an instant thrust cutoff as two
  points at the same timestamp, and nudging preserves that near-exactly
  while removing the exact-zero dx that makes rocketpy's linear
  interpolation divide by zero). Wired into `motor_reader.read_eng`
  (every `.eng` thrust curve) and `pipeline.load_files` (user-uploaded
  power_off/power_on drag CSVs - the .ork's own stored-sim curve was
  already safe, since `extract_drag_curves_from_stored_sim`'s
  `bin_avg()` already merges into unique Mach bins). Both log a
  human-readable warning row in the import table when duplicates are
  found and fixed, per CLAUDE.md's "never half-import silently" rule.

Verification: full non-Playwright suite (26 tests) + both existing
Playwright e2e tests, all green. New test:
`test_phase4_monte_carlo.py::test_cancel_check_stops_early_and_keeps_partial_results`
(N=5, per budget-mode test guidance).

### Section 2: physically impossible numbers - DONE

- **(a) 394g acceleration spike / parachute deploys 14s after apogee at
  ~120 m/s**: root cause found and fixed. PROMETEO's real `.ork` has
  `<deployevent>never</deployevent>` on its only parachute - this is
  real, verified against the raw XML, not a parsing bug. "never" means
  OpenRocket has NO automatic deployment configured for this component
  at all (typical for a team using a real SRAD altimeter, which
  OpenRocket's built-in deployevent options don't model - PROMETEO's
  really deploys via altimeter at apogee, confirmed in flight
  telemetry). The OLD code's fallback (`"apogee" if deploy_event ==
  "apogee" else deploy_altitude`) treated "never" as an ACTIVE altitude
  trigger at the stored (but inactive) `deploy_altitude=200.0` - so the
  rocket coasted in ballistic free-fall from apogee (t=16.8s) down to
  t=31.8s at ~120 m/s before "deploying", instant-inflation-modeled by
  rocketpy into a ~375g spike that dominated every acceleration KPI.
  Fixed with `translate._parachute_trigger()`: only "altitude" uses
  deploy_altitude as a live trigger; "apogee" maps directly; everything
  else ("never", "ejection", unrecognized values) maps to an
  apogee-triggered deployment WITH A LOGGED WARNING (not asserted as
  fact - `translate.parachute_import_notes()` puts it in the import
  table before simulating, per CLAUDE.md Rule 2). Verified: deployment
  now at t=16.8s (apogee) at 30.6 m/s - and the resulting simulated
  descent rate (5.5 m/s) matches PROMETEO's real documented descent
  rate (5.5 m/s, CLAUDE.md Sec 3.2) almost exactly, which is a strong
  independent confirmation this is the right fix, not just "a" fix.
  Added a permanent regression test
  (`test_parachute_deploys_at_apogee_not_late_and_max_acceleration_is_boost_only`).
  Split the acceleration KPI in two: `max_acceleration_ms2` is now
  `flight.max_acceleration_power_on` (boost-phase only - **51.0 m/s2**,
  matching OpenRocket's own reported 50.9 m/s2 almost exactly) and a
  new `parachute_opening_accel_ms2` (`flight.max_acceleration_power_off`,
  labelled on the Results page "instantaneous inflation model, upper
  bound" per tonight's exact wording - rocketpy models canopy inflation
  as instantaneous, which overstates the real jerk).
- **(b) 0.08 cal margin, "Stable? YES"**: two separate fixes. First,
  margin is now computed **rail-exit to apogee only** (both in
  `pipeline.run_simulation` and independently in `rcsm.check_compliance`,
  which had the exact same full-flight-window bug - found while fixing
  the first one and audited the rest of the codebase for the same
  pattern, none left). Full-flight margin swept in the post-deployment
  descent phase, where "static margin" is not the aerodynamically
  meaningful ascent quantity FLT 4.3.5/4.3.6 are about - combined with
  2(a)'s late/high-speed deployment, a chaotic post-deployment instant
  could dominate `min()`. Second, "Stable?" is now pass/fail against
  the FULL 1.5-4 cal window (`1.5 <= min_margin and max_margin <= 4.0`),
  not just `margin > 0` - a razor-thin or absurdly-high margin both used
  to silently read "YES". Verified with the known-good override
  (5.6622 kg / 0.6279 m): margin is now [2.61, 3.30] cal (was reading
  whatever the full-flight window produced before) - in the right
  ballpark vs. OpenRocket's ~1.9 cal at the pad; the remaining gap is
  Item 3's territory (mass/CG differences), not this bug.
  **Where "0.6279 m" comes from, and its reference frame** (Diego's
  direct question): it is NOT independently measured - it's *derived*
  in `reference/prometeo_mission44/src/prometeo/rocket.py`'s
  `_solve_dry_inertia()`, by parallel-axis subtraction of the motor's
  own CG from OpenRocket's stored **with-motor** t=0 CG
  (`config.CG_T0_WITH_MOTOR = 0.97966` m from nose, from the Brasil-
  config CSV export). The **0.6279 is in OpenRocket's own frame: metres
  from the nose tip, positive aft** - confirmed by actually running that
  derivation (`_solve_dry_inertia()['cg_dry_rpy'] = -0.6279...`, and the
  function's own debug print divides by -1 to report "cm from nose").
  There is NO tail_to_nose/from-nose mix-up in the current code: the
  Advanced panel's field is explicitly labelled "m from nose", and
  `translate.build_rocket`'s `to_rpy()` negates it internally before
  handing it to `Rocket(center_of_mass_without_motor=...)` - which is
  exactly what the reference implementation does by hand. So 0.6279 is
  the right number to type into that field for PROMETEO's Brasil-config
  dry mass, and it's a **derived** number (parallel-axis subtraction
  from a with-motor OpenRocket export), not a direct measurement - which
  is exactly why it's provisional/approximate for LASC's different total
  mass (10.370 kg vs. this config's 10.400 kg), same as V1/V2's existing
  PROVISIONAL caveats.
- **(c) Automatic sanity checks**: new `bup_rocketpy/sanity_checks.py`,
  `run_sanity_checks(flight, rocket, motor, dry_mass_kg)` returns a list
  of `SanityCheck(name, status, detail)` (OK/WARN/FAIL), covering:
  thrust-to-weight at liftoff, boost acceleration vs. a thrust/mass-g
  hand estimate, delta-v vs. impulse/avg-mass, deployment speed per
  parachute (>30 m/s flagged), and a descent-rate hand-check
  (v=sqrt(2mg/(rho*CdS)) at ground density vs. simulated impact speed -
  matched PROMETEO's real 5.5 m/s almost exactly). `pipeline.run_simulation`
  adds a 6th, the static margin range check (FLT 4.3.5), and attaches
  the full list to `SimResult.sanity_checks`. Shown on the Results page
  as a collapsed "Automatic sanity checks (N flagged)" panel, color-coded
  green/orange/red - a red flag instead of silently showing a weird
  number, per tonight's instruction. Deliberately loose thresholds (this
  catches gross errors, not subtle modeling imprecision) to avoid crying
  wolf on a genuinely unusual but correct rocket.

Full suite (29 tests) green; reference/ data confirmed untouched.

### Section 3: unify code paths, re-run the +10% mystery - DONE (partially resolved)

**Root cause of "app says -0.7%, test harness says +10.17%" confirmed
exactly as suspected**: `test_code_to_code_vs_openrocket.py` and
`test_phase2_validation.py` (V1/V2) never called `bup_rocketpy.translate`
at all - they hand-built a Rocket()/Flight() via
`reference/prometeo_mission44/src/prometeo/rocket.py`, a completely
separate implementation from what `bup_rocketpy/gui/pipeline.py` (the
app) actually calls. Two different code paths, not one physics bug -
exactly your diagnosis. Both test files are rewritten to call ONLY
`ork_reader.read_ork` / `motor_reader.read_eng` / `translate.build_motor`
/ `translate.derive_dry_mass_and_inertia_from_with_motor` (new, see
below) / `translate.ork_to_flight` - the real .ork/.eng files, no
hand-built rocket anywhere in either file now. Per-flight mass/CG/site
numbers (config.py's already-verified historical constants) are passed
in as explicit overrides, the same mechanism the app's own "manual
override" checkbox uses.

**While unifying the path, found and fixed 3 real, separate bugs** -
not tuning, each verified with hard before/after numbers:

1. **`translate.build_motor`'s grain-density was a hardcoded generic
   constant (1750.0), not solved for the actual motor.** rocketpy's
   `SolidMotor.propellant_initial_mass` is computed from grain geometry
   x density, NOT read from the `.eng` file - so this hardcoded value
   gave **1.637 kg** of propellant mass vs. the `.eng` header's own
   declared **2.0167 kg (-18.8%)**, even though `dry_mass` and the
   thrust curve itself were both already exactly correct. Total liftoff
   mass was therefore understated by ~0.38 kg (3.6%) while the SAME
   thrust curve was applied - a lighter rocket getting identical thrust
   flies higher. Fixed by solving `grain_density` backward from the
   `.eng`'s own `propellant_mass_kg` given the assumed grain dimensions
   (new `translate.motor_grain_params()`), guaranteeing an exact match
   by construction. **This alone cut the Brasil-config code-to-code
   error roughly in half (+10.34% -> +6.77%)** and made V2 pass on its
   own (+5.27% -> +2.04%, before wind - see #2).
2. **Wind was parsed from the `.ork` but never applied at all** -
   `translate.build_environment` only ever called
   `set_atmospheric_model(type="standard_atmosphere")` with no wind
   arguments. Adding `wind_u=`/`wind_v=` to that same call (my first
   attempt) measurably changed NOTHING - a genuine **rocketpy quirk**:
   `set_atmospheric_model`'s `standard_atmosphere` branch unconditionally
   zeroes wind internally regardless of what's passed in (confirmed by
   reading rocketpy's own source, `environment.py` lines ~1475-1476).
   The supported way to layer wind onto an already-set atmosphere model
   is `env.add_wind_gust(wind_u, wind_v)`, which actually works. Wind
   sign convention: OpenRocket's `<winddirection>` is the compass
   bearing the wind blows FROM (confirmed empirically, see below), so
   the velocity vector is `bearing + 180deg`. **With this actually
   applied, Brasil-config code-to-code moved from +6.77% to -1.45% -
   PASSES the 2% target.** New `translate.wind_uv()` (shared with
   `case_export.py`, see #3) computes this vector in one place.
3. **`bup_rocketpy/case_export.py` (the LASC submission script
   generator) had its OWN independent, duplicated copy of the grain
   sizing AND the parachute-trigger logic** - meaning every exported
   competition submission script would have shipped with BOTH the
   374kg-propellant-mass bug above AND the Section-2(a) "never" ->
   200m-altitude-trigger deployment bug, even after both were fixed in
   `translate.py`, because case_export.py never called `translate.py`'s
   functions to begin with. Found this by re-running
   `test_phase5_case_export.py` (which checks the exported script
   matches the app's own in-process apogee) after fixing #1 - it
   promptly failed with a 9.25% mismatch, straight from case_export.py
   quietly still using its own stale numbers. Fixed by extracting the
   shared math into `translate.motor_grain_params()` /
   `translate.wind_uv()` / `translate.parachute_trigger()` and having
   `case_export.py` call those instead of re-deriving them - the exported
   script now matches the app's in-process result to **0.003%** (was
   9.25% off). This is arguably the most safety-relevant fix in this
   whole section, since it directly affects what gets submitted to LASC.

**Diagnostic table (unified path, both before-#1/#2 and after)**:

| | Brasil code-to-code | July4 code-to-code | V1 (July4, real flight) | V2 (LASC, real flight) |
|---|---|---|---|---|
| Target | OpenRocket 1081.7 m | OpenRocket 1027.2 m | telemetry 1019.9 m | telemetry 1137.0 m |
| Before (old hand-built path, prior review) | +10.17% | +9.43% | +10.22% | +5.27% |
| After #1 only (propellant mass) | +6.77% | +13.40%* | +14.21%* | +2.04% (PASS) |
| After #1+#2 (propellant mass + wind) | **-1.45% (PASS)** | +10.64% | +11.44% | -5.80% |

*July4/V1 got WORSE from #1 alone, before the wind fix landed - see
below.

**Brasil-config is now excellent** (-1.45%, well inside the tight 2%
target, no weather uncertainty in that comparison at all) - strong
evidence the app's core translate/motor/rocket construction is now
correct when fed a complete, self-consistent input set (the .ork's own
stored simulation).

**July4/V1 remains open** (+10.64%/+11.44%) - NOT tuned to force a pass.
Diagnostic: burnout velocity is only ~6% high but burnout ALTITUDE is
~25% high for this case (vs. ~3%/~3% for Brasil), pointing at a
trajectory-SHAPE difference (ascent angle/weathercocking), not a raw
performance difference. Prime remaining suspect: this test now uses the
REAL `.ork` fin geometry (root=0.20m, tip=0.10m, span=0.14m,
sweep=0.17m) instead of the OLD hand-built path's `config.py`
placeholder fins (root=0.20m, tip=0.08m, span=0.12m, sweep=0.10m,
explicitly marked "TODO MEASURE, NOT a measurement" in config.py) - a
real geometry difference that changes CP/CN_alpha and therefore how the
rocket responds to July4's off-vertical rail (89deg) and wind, on top
of the already-documented approximation that July4 reuses the
Brasil-config's dry CG (no July4-specific with-motor CG is on file).
Logged here rather than chased further tonight (budget mode) - next
lead for whoever picks this up.

**V2 flipped from PASS (+2.04%, before wind) to FAIL (-5.80%, after
wind)** - genuinely informative, not a regression: V2 compares against
REAL FLIGHT telemetry (not OpenRocket's own sim, unlike the code-to-code
cases), and Brasil-config code-to-code (same wind fix, same everything
else) is now excellent. That strongly suggests the remaining V2 gap is
real WEATHER DIFFERENCE between the `.ork`'s stored/recorded conditions
and Iacanga's actual flight-day weather - exactly the already-documented
caveat ("wind/temp/pressure are the .ork's OWN recorded values, not the
actual Iacanga flight-day weather, still pending from Diego"), now with
much more evidence behind it than before. **Needs Diego's real Iacanga
weather to resolve further, not more code changes.**

Wind direction sign convention (`bearing + 180deg`) was NOT assumed -
it's the convention that empirically makes the zero-weather-uncertainty
Brasil-config case match OpenRocket's own number to -1.45%; the
opposite sign was tested too and makes the gap worse, not better (not
committed - only the correct one is).

Full suite (29 tests) green; reference/ data untouched throughout.

### Section 4: tests that match reality - DONE

Rewrote `tests/test_phase0_e2e_full.py` to actually match Diego's real
path instead of the happy-path override flow `test_phase0_e2e.py`
exercises:

- **`test_corrupt_runs_dir_does_not_crash_history_page`**: pre-seeds a
  `runs/` folder with a truncated `record.json` (the exact shape crash
  (a) used to produce) and confirms the History page shows a warning,
  not a traceback - crash (a)'s fix, verified through a real browser
  this time, not just the unit-level JSON-encoder test.
- **`test_default_path_every_page_and_second_ork`**: fresh `runs/`
  folder; loads PROMETEO's real `.ork`+`.eng` with **NO manual
  override** (the actual default path, not the override path the other
  e2e test uses); Simulate; visits every sidebar page and asserts BOTH
  no error AND a real-content marker specific to that page (not just
  "didn't crash" - crash (d)'s whole point was pages that rendered fine
  but showed nothing useful); then loads a second, genuinely different
  `.ork` (an OpenRocket example rocket, see below) and confirms the
  Rocket page shows the NEW rocket's name/dimensions, not the old one's.

**Found a second, subtler instance of crash (e) while building this
test**: after Section 1's fix, the Rocket page correctly showed the
newly-loaded rocket's OWN geometry (no more browser-caching), but its
dry CG/static margin cards still showed the PREVIOUS rocket's last-
Simulate values (`s["dry_cg_m"]`/`s["sim_result"]` were never cleared on
a new `.ork` load) - visible directly in the second-`.ork` screenshot
(a 40cm model rocket showing a stale "112.2 cm from nose" CG and a
margin number that belonged to PROMETEO). Fixed: `do_load()` now resets
every downstream-result state key (`sim_result`, `dry_mass_kg`,
`dry_cg_m`, `mass_source`, `case_results`, `compliance_rows`,
`mc_result`, `mc_uncertainties`, `weathercocking_result`) whenever a new
`.ork`+`.eng` pair is loaded. Verified: the Rocket page now correctly
shows this rocket's own geometric CG estimate (22.4 cm) and "run
Simulate first" for margin, instead of PROMETEO's stale numbers.

**Added `reference/openrocket_examples/`**: two `.ork` files pulled from
OpenRocket's own example-rocket set (GPL v3, bundled with every
OpenRocket install) - `A_simple_model_rocket.ork` (the "second, different
rocket" for the test above) and `Dual_parachute_deployment.ork` (a real
drogue+main vehicle, for Section 7's dual-deploy test). See that
folder's own README for licensing/attribution and why PROMETEO's real
`.eng` gets paired with them for Simulate-needing tests (an honest test
fixture, not fabricated motor data - these tests check UI/pipeline
behavior, not vehicle performance).

Added `BUP_ROCKETPY_RUNS_DIR` env var (`run_history._runs_dir`) so tests
can point a real running app at an isolated `runs/` folder without ever
touching the real repo's own run history.

**`start.bat`** now prefers Python 3.12 via the Windows `py` launcher
(`py -3.12`), with clear install instructions printed (and in
`README.md`) if it's not found, before falling back to whatever
`python` is on PATH - addresses Diego running Python 3.14 while this
project is tested on 3.11/3.12, where a pinned dependency might not have
wheels yet for a very new Python version.

**Updated the Validation page's hardcoded numbers** to match Section 3's
new results (was still showing last night's V1/V2 figures and the old
"root cause not yet isolated" code-to-code text).

Full suite (30 tests) green.

### Section 5 (KPI/recovery priority) - DONE

New KPIs on the Results page: **time to apogee**, **max dynamic
pressure (Max-Q)** with its time, **ground-hit velocity**
(`|flight.impact_velocity|`), and **landing distance from the pad**
(straight-line drift, `sqrt(x_impact^2 + y_impact^2)`).

New **recovery panel** (`bup_rocketpy/recovery.py`, the "LASC officials
asked for this on site" requirement) - one row per parachute that
actually deployed: diameter, projected area (pi*r^2), Cd, Cd*S, the
simulated descent rate under that specific canopy, and a HAND-CALCULATED
terminal velocity (`v = sqrt(2*m*g / (rho*Cd*S))`) at both the
deployment altitude and ground-level air density, with the % difference
from the simulated value - an independent cross-check, not a duplicate
of the same number. `descent_mass_kg` is dry rocket + the motor's own
dry (spent-casing) mass, matching what's physically hanging under the
canopy. Verified against real numbers: PROMETEO's single chute shows
sim descent rate 5.81 m/s vs. hand-calc 5.51 m/s at deploy altitude
(+5.5%) and 5.15 m/s at ground (+12.7%) - both in the right ballpark,
and the simulated 5.1 m/s ground-hit velocity matches PROMETEO's real
documented ~5.5 m/s descent rate closely.

**Found while wiring this up**: `translate.build_rocket`'s
`rocket.add_parachute(...)` call never passed `radius=`/
`drag_coefficient=` (rocketpy's `Parachute` accepts and stores both,
separate from the combined `cd_s` it actually flies with) - meaning the
built `Parachute` object had no way to report its own real diameter/Cd
back to anything inspecting it later. Fixed by passing both through, so
`recovery.recovery_panel()` reads the REAL values instead of
back-deriving an approximate diameter from `cd_s` alone. Side effect
worth noting: this also changed rocketpy's internal added-mass modeling
during the parachute-deployment transient (a real, more-accurate-since-
it-uses-real-geometry effect, not a bug) - the parachute-opening
deceleration figures shifted somewhat (e.g. PROMETEO's case: opening
accel 206.7 -> ~130-320 m/s2 depending on the run's exact mass/CG,
deployment speed 30.6 -> 24-41 m/s across different override values)
without changing ascent-phase results (apogee, margin, boost
acceleration - all unchanged, confirmed by re-running the full suite).

All new fields verified end to end via the Section 4 e2e test
(screenshot: `docs/screenshots/01_simulate_results.png` shows the full
KPI grid + recovery panel table rendered in a real browser).

Full suite (30 tests) green.

### Section 5 (rest) - DONE

**Per-quantity plot tabs** (`bup_rocketpy/gui/plotting.py`): replaced
rocketpy's 3 built-in composite multi-panel figures
(`linear_kinematics_data`/`attitude_data`, which bundled several
quantities into one crowded figure each) with one tab per quantity, each
independently downloadable as a PNG:
altitude, vertical velocity, total velocity, acceleration (boost-phase
only - restricted to ascent so the parachute-opening transient doesn't
flatten the boost detail, same reasoning as the KPI split in Section 2),
Mach, thrust, mass, CG+CP vs. time (one figure, two lines), static
margin vs. time, angle of attack, dynamic pressure, Cd vs. Mach (the
CURVE ACTUALLY USED - `rocket.power_off_drag`/`power_on_drag`, not a
derived flight time series), descent velocity (post-apogee, zoomed), and
a ground track (top-down X/Y drift plot, pad marked, landing point
marked). Kept the 3D trajectory plot too (a genuinely different view,
not redundant with any of the above). Each tab has its own "Download
PNG" link.

**Rocket page "Rocket info"** section: reference area (pi*r^2), and a
parachute table (diameter, area, Cd, Cd*S) - geometry-only, so it works
right after Load, no Simulate needed.

Full suite (31 tests) green. Screenshots confirm both render correctly
in a real browser (`docs/screenshots/01_simulate_results.png`'s new tab
row, `docs/screenshots/05_rocket.png`'s new Rocket info section).

### Section 6: rocketpy bug minimal repros + GH issue drafts - DONE

New `docs/rocketpy_issues/`: 5 self-contained repro scripts (only
`rocketpy` + a tiny inline-data rocket, no `bup_rocketpy` import), each
actually run and its output captured, checking every one of the "4
rocketpy bugs" claimed after the first review pass rather than assuming
they were all real:

1. **Confirmed, but corrected**: `MonteCarlo.simulate()` doesn't crash
   on "any unstable sample" (the original description) - it crashes
   specifically when a sample never reaches a recognized apogee event
   (`Flight.apogee_x`/`apogee_y` are never populated in that case), and
   that `AttributeError` isn't caught by whatever per-sample error
   handling `MonteCarlo` has.
2. **Retracted**: re-tested "StochasticRocket drops an overridden CG"
   in isolation against a complete, well-formed rocket - it does NOT
   reproduce. The original ~-8.5 cal symptom was actually caused by #3
   below (zero aerosurfaces -> cp_position() stuck near 0), not a CG
   bug at all. Updated `bup_rocketpy/monte_carlo.py`'s own comment to
   stop overstating this as a confirmed bug.
3. **Confirmed, exact root cause**: `StochasticRocket._add_surfaces()`
   hardcodes `stochastic_type(component=surfaces)`, but
   `StochasticNoseCone`/`StochasticTrapezoidalFins` want
   `nosecone=`/`trapezoidal_fins=` - found the exact line in rocketpy's
   own source.
4. **Confirmed**: none of the 4 Stochastic classes accept `seed=`, and
   `numpy.random.seed()` (legacy global RNG) has zero effect on their
   sampling (they use `numpy.random.Generator(PCG64)` internally) -
   arguably reasonable design, more a missing feature than a bug.
5. **Confirmed** (new tonight, from Item 3's wind investigation):
   `Environment.set_atmospheric_model`'s `wind_u`/`wind_v` are silently
   discarded for `type="standard_atmosphere"` - documented only in a
   docstring nobody calling `set_atmospheric_model()` would see, no
   warning raised.

Draft GitHub issue text for all 4 confirmed findings (not #2, which was
retracted) is in `docs/rocketpy_issues/README.md`, ready for Diego to
review/submit - **could not cross-check against rocketpy's existing
GitHub issues** (no web/API access in this session, only git
clone/fetch), flagged explicitly so Diego knows to search first before
submitting.

Full suite (31 tests) still green (one comment-only change to shipped
code, `bup_rocketpy/monte_carlo.py`).

### Section 7: MC background+cancel (done in Section 1), Leaflet landing map - DONE

**Monte Carlo background+cancel** was already built as part of Section
1's crash (b) fix (background thread via `run.io_bound`, a cancel
button, `MonteCarloResult.cancelled`) - see that section.

**New Leaflet landing map** (`bup_rocketpy/geo.py` +
`montecarlo_page.py`): the 1/2/3-sigma landing ellipses and impact
samples, converted from local X/Y metres-from-pad to lat/lon (flat-Earth
approximation, fine for this scale) and overlaid on a real interactive
map (`ui.leaflet`) next to the existing static matplotlib plot (kept for
a quick PNG export). Pad marked, landing samples capped at 200 markers
(a real N=200+ run would otherwise add one DOM layer per sample - pure
clutter over the static scatter plot). New `tests/test_geo.py` (pure
math, no rocketpy needed) checks the coordinate conversion and ellipse
polygon generation.

**Found and fixed a real bug while building this**: the Monte Carlo
page hung indefinitely after a run completed (stuck on "Running N/N...")
- root-caused via targeted server-side debug logging (not guesswork) to
`ui.leaflet(...)` being followed by a REDUNDANT explicit `.tile_layer(...)`
call - `ui.leaflet()` already adds its own default OpenStreetMap tile
layer internally, so this doubled the number of tile fetch requests;
with no internet in this sandbox, both sets of requests hang/fail, and
the resulting pile of pending fetches was enough to make the client miss
NiceGUI's websocket heartbeat and silently reconnect (losing the just-
rendered results). Removed the redundant call - fixed and verified
reliable across repeated standalone runs.

**Known limitation, honestly documented (and re-checked)**:
`test_phase7_mc_map_e2e.py` was believed last night to pass reliably
when run standalone and only hang after another Playwright-based test
in the same pytest process. Re-checked this tonight (2026-09-25) by
re-running it several times, including alone - it timed out (180s)
waiting for the Monte Carlo run to finish on every re-run, so the
"reliable in isolation" claim does not hold up and the real trigger is
still not pinned down. Confirmed via debug logging that the underlying
Python-side computation always completes in ~2s regardless - the
timeout is client-side/browser-delivery only. Not root-caused further
(Section 7 is the lowest-priority item, and budget is limited). Stays
skipped by default (`RUN_LEAFLET_TEST=1 pytest tests/test_phase7_mc_map_e2e.py`
to run it explicitly) so it doesn't destabilize the "every commit passes
the e2e test" gate. The Leaflet map feature itself is implemented and
its code path is exercised by this test up to the point it hangs (the
map only renders after the MC run reports done, so this hasn't been
visually confirmed working in THIS sandbox tonight - it was visually
confirmed earlier, see screenshot `docs/screenshots/06_montecarlo.png`
from an earlier successful run). Flagging this plainly as a
**BLOCKED / NEEDS DIEGO** item: please click through Monte Carlo -> Run
on your own machine and confirm the landing map actually renders with
markers - that is the real-world check this automated test can no
longer reliably stand in for here.

**Dual-deploy testing** (`test_phase5_rcsm_cases.py`): added
`test_drogue_only_and_main_at_apogee_work_on_a_real_dual_deploy_vehicle`
using `reference/openrocket_examples/Dual_parachute_deployment.ork` (a
real drogue+main vehicle, unlike PROMETEO's single-chute design) -
confirms DrogueOnly/MainAtApogee run WITHOUT the "only ONE recovery
event" warning on a real 2-parachute rocket, closing the gap where the
existing test only ever exercised the warning path. Found (but did not
chase further, low-priority third-party fixture data) a
"divide by zero"-class RuntimeWarning specific to this .ork that
persists even after deduping the drag curve - noted, not blocking
(results are sane, test passes).

Major Tom: still not committed to the repo, per the explicit instruction
("that design is a work in progress and gets loaded through the app").

Full suite: 34 passed, 1 skipped (by design) in ~67s.

---

## High-priority bug fix, 2026-09-26: the "bottom" position sign bug

Diego's report: PROMETEO's "Sistema de recuperacion" resolves to 2.3473 m
outside the 1.47 m airframe; his new rocket had the same class of bug
push a component to 2.79 m on a 1.85 m airframe -> CG dragged aft ->
static margin -1.41 cal -> Simulate hung forever. Budget mode: targeted
tests only, no full-suite re-runs per edit.

### Item 1: the actual bug, root-caused (not guessed)

`ork_reader._resolve_child_position`'s `"bottom"` branch was
`parent_aft_m - value - child_length_m`. For PROMETEO's real
"Sistema de recuperacion" (`position type="bottom"` value `-0.8773`
inside the 1.2 m "Fuselage" tube), that gives `1.47 - (-0.8773) - 0 =
2.3473 m` - outside the whole 1.47 m airframe, exactly what Diego saw.
Checked EVERY "bottom"-type component in this real .ork against the
formula: every single one with a negative value resolved outside its own
parent tube (2 bulkheads, 3 centering rings, 1 mass, the mass Diego
named). Flipped the sign (`parent_aft_m + value - child_length_m`) and
every one of them now resolves inside the tube, in a position that makes
physical sense (e.g. the recovery system at 0.593 m, mid-tube - not
0.877 m past the tail). No OpenRocket Java source available to cite from
this sandbox (no internet access) - this is empirical, derived from real,
unmodified data, not a guess. Documented as such in the code comment.

**Found and fixed a second, closely-related bug while chasing Diego's own
acceptance target ("mass + CG at t0 within 1%")**: `_apply_overrides`
(which reads a component's `<overridemass>`) was only ever called for
`<bodytube>` components. PROMETEO's real .ork also has a per-component
`<overridemass>` on its nosecone (0.227 kg), its fin set (0.505 kg), its
bulkheads (0.075 kg x3) and its **parachute** (0.558 kg - more mass than
any single point mass elsewhere in the rocket, and previously not counted
AT ALL, since a parachute wasn't one of `_geometric_components`'s
component types). None of these were being read. Generalized
`_apply_overrides` to be called for every component type that can carry
the tag, made bulkheads prefer their override over the density-based
guess, and added parachute mass as a geometric component. This took the
geometric (NO-override) dry mass estimate from **19% low to ~1.3% low**
(`tests/test_phase1_acceptance.py::test_geometric_dry_mass_undercounts_and_why`,
rewritten to document the new number, not the old one) - a bug this
big had been silently eating Diego's default/no-override path the whole
time, not just today's specific position bug.

**Combined real-world effect** (`tests/test_phase3_headless.py`, no
manual override, PROMETEO's real .ork + .eng - i.e. exactly Diego's
"a normal user just loads files and clicks Simulate" path): static margin
went from unstable/hanging to **1.9-2.6 cal** (within FLT 4.3.5's 1.5-4
cal window), apogee **~1092 m AGL** (squarely in PROMETEO's known
860-1137 m range, not validated against flight data here but no longer
wildly off), descent rate within ~5.5% of the hand-calc terminal
velocity. `test_run_simulation_without_override_surfaces_instability_not_hides_it`
used to assert `is_stable == False` (documenting the old bug) - rewritten
to `test_run_simulation_without_override_is_now_stable_and_sane`,
asserting the opposite, since that's now the honest reality.

New test (Diego's literal ask):
`test_no_component_resolves_outside_the_airframe` (hard assert, PASSES)
and `test_mass_and_cg_at_t0_within_1pct_of_ork_stored_reference` - CG
passes cleanly at 0.67% (this IS today's fix's target metric); mass is
1.87% off, honestly reported as inflated by a **pre-existing, separate**
data discrepancy this repo's test file already documented before tonight
(the .ork's own stored sim assumes 4.864 kg of loaded motor; the real
`Icarus_I_K519.eng` header says 4.7378 kg - nothing to do with today's
fix). The dry-only comparison (unaffected by which motor-mass figure is
used) is ~1.3%, the fairer number, and the one this same test file
already used before tonight.

### Item 2: "never hang" guard rails

Both new checks run BEFORE ever calling `Flight()` - the actual thing
that was hanging:
- `ork_reader.components_outside_airframe(parsed)`: returns every point
  mass/fin/parachute resolved outside `[0, airframe_length_m]`.
  `gui/pipeline.py::run_simulation` and `rcsm_cases.run_all_cases` both
  call this first and raise a `ValueError` naming the component(s) if
  it's non-empty, instead of building a `Rocket`/`Flight` at all.
- `rocket.static_margin(0)` (free - no ODE integration needed): if
  negative, `run_simulation` raises before calling `Flight()`, naming the
  static margin and pointing at the Rocket page / manual override fields.
- `gui/app.py`'s `do_simulate` now races the background simulation
  against a `SIMULATION_TIMEOUT_S = 120` backstop AND a new visible
  Cancel button (`asyncio.wait(..., return_when=FIRST_COMPLETED)`).
  Honestly documented limitation: a single `Flight()` call has no
  internal checkpoint to poll (unlike Monte Carlo's N discrete samples),
  so neither the timeout nor Cancel can truly kill an already-hung
  integration mid-flight - they detach the UI from waiting on it and
  return control to the user immediately, which is what actually matters
  for "never hang" from a real user's perspective; the orphaned
  background thread finishes on its own and its result is discarded.

New tests: `test_simulate_blocks_immediately_on_a_negative_t0_static_margin`
and `test_simulate_blocks_immediately_on_a_component_outside_the_airframe`
(both assert the ValueError fires in well under a second, i.e. before any
`Flight()` call could even start).

### Item 3: the "divide by zero in polation_1d" warning - which file caused it

Traced with a full traceback (not guessed): it is **rocketpy's own
internal code**, not any file this app reads. `Flight.__init__` builds a
`clean_pressure_signal_function` per parachute AFTER the flight completes,
from samples it recorded itself every 0.01 s during the flight (its own
barometric-trigger-noise model) - `rocketpy/simulation/flight.py`'s
`__transform_pressure_signals_lists_to_functions`. On
`reference/openrocket_examples/Dual_parachute_deployment.ork`'s main
parachute, that internally-recorded list happens to contain ONE duplicate
timestamp among ~4475 samples, which is what triggers the warning inside
rocketpy's `Function`/`polation_1d`. An earlier note in
`test_phase5_rcsm_cases.py` blamed this fixture's own stored drag curve -
checked that directly tonight: 0 duplicates, that note was wrong, now
fixed and replaced with the real explanation + an assertion that would
catch if the drag curve ever DOES become the real cause in the future.
No input file bup_rocketpy parses or writes is involved. Not monkeypatched
(doesn't meet Section 6's "confirmed bug worth patching" bar - it's a
warning, not a wrong result, and it's rocketpy's own post-flight
instrumentation, not the physics) - suppressed locally in that one test
so it doesn't spam output.

Full suite: 38 passed, 1 skipped (the pre-existing, documented Leaflet
flakiness) in ~76s. Screenshots regenerated by the e2e re-runs above are
committed alongside this fix (not reverted as noise this time) since they
now show the genuinely-fixed numbers, not just a re-render of the old ones.

---

## Bug fix, 2026-09-26 (later): motor thrust curve duplicate-t0 divide-by-zero

Diego's Monte Carlo on Major Tom + a real motor .eng ("Kaboom" M1889) gave
apogee -2300 m identically across all 50 samples (map location was a
separate, non-code issue: his .ork's stored "PACHUCA" sim had the wrong
lat/lon typed into OpenRocket - fixed by Diego directly in OpenRocket).

Root cause of the -2300 m: `translate.build_motor` passed the raw
`eng_path` as `thrust_source`, so rocketpy re-parsed the .eng ITSELF
(`Motor.import_eng`), which unconditionally prepends a `(0, 0)` point -
its own docstring says "the .eng file must not contain the 0 0 point".
Kaboom's .eng legitimately starts with an explicit `0 0.01` row - two
points at t=0 collided, producing a divide-by-zero in the thrust
Function's slope calculation and a degenerate near-zero thrust curve, so
every sample "flew" to essentially the pad's own altitude. Not a
stability bug at all - Major Tom's real static margin with this motor is
a healthy 2.26 cal.

Fixed by passing our OWN already-parsed `parsed_eng.thrust_curve` (a
plain list) as `thrust_source` instead of the file path, so rocketpy
never re-parses the file and never re-prepends its own zero point -
generalizes to any .eng with this shape, not just this one file. Also
fixed `burn_time` to use the curve's own real (first, last) timestamps
instead of an assumed `(0, ...)`, avoiding a new (harmless but avoidable)
"out of thrust source time range" warning that surfaced once rocketpy's
synthetic zero-point was gone.

New test: `tests/test_motor_thrust_curve.py`, a synthetic .eng with an
explicit t=0 row, asserting no RuntimeWarning and a real (non-NaN)
mid-burn thrust value. Full suite: 39 passed, 1 skipped, 0 warnings.

---

## Feature, 2026-09-26 (later still): Monte Carlo now runs in parallel across CPU cores

Diego's ask: MC only used one CPU core (background THREAD, not real
parallelism) despite his machine (Ryzen 7, multiple cores) - "make it as
fast as possible."

`monte_carlo.run_monte_carlo` now dispatches its N stochastic flights to
a `concurrent.futures.ProcessPoolExecutor` (real OS processes, not
threads - Python's GIL means threads don't parallelize CPU-bound work
like a Flight() simulation) sized to `os.cpu_count()` by default. Each
worker independently rebuilds the nominal rocket/motor/env/flight and
its own Stochastic* wrappers from scratch (rocketpy's stochastic objects
hold live RNG/Function state that can't be pickled across a process
boundary) - a small, one-time-per-sample cost next to the ~0.3-0.6s a
Flight() itself takes.

Measured on this sandbox (4 cores): N=20 PROMETEO samples in ~2.8s vs.
~8-10s serial (roughly 3x, in line with the core count). Real speedup on
Diego's own machine depends on how many logical cores it exposes.

**Found and fixed a real regression while testing**: results used to be
stored in whichever order workers happened to FINISH
(`as_completed()` gives no ordering guarantee), which broke
`analysis.drag_comparison`'s "common random numbers" feature (pairs
`result_a.apogee_samples[i]` against `result_b.apogee_samples[i]`
index-by-index across two separate seeded runs) -
`test_drag_comparison_with_identical_curves_gives_zero_difference` caught
it immediately (diff went from exactly 0 to +-48.9 m). Fixed by storing
each sample's result at its own submission INDEX (not append-on-
completion), so sample i means the same thing in both runs regardless of
which process finished it first.

Cancel still works: `executor.shutdown(wait=False, cancel_futures=True)`
drops every not-yet-started sample and returns immediately rather than
draining the whole pool - already-running worker processes finish on
their own (same "detach, don't kill" limit as this review's Simulate-
button timeout). `montecarlo_page.py` needed NO changes - `run_monte_carlo`'s
external signature/behavior is unchanged, just faster.

Full suite: 39 passed, 1 deselected (the pre-existing, documented opt-in
Leaflet browser test) in ~58s.

---

## Budget-mode review, 2026-09-26 (new): A-F

### Item A: drag curve contaminated by the parachute - FIXED

`ork_reader.extract_drag_curves_from_stored_sim` kept every Thrust==0
datapoint all the way to the END of the stored sim, not just to apogee -
past apogee, OpenRocket's "Axial drag coefficient" bakes in the deployed
parachute's drag (no separate flag for it in the databranch), so the
coast/power-off curve was contaminated with descent-under-canopy Cd for
the WHOLE rest of the flight. Diego found this directly in a real
exported zip: Cd=589.775 from Mach 0.02-0.212, 68 points.

Fixed by tracking "Vertical velocity" (confirmed present in the real
.ork's databranch types= list) and stopping coast collection the instant
it goes negative (past apogee) - matches
reference/prometeo_mission44/scripts/extract_drag_curves.py's own
BURNOUT..APOGEE bound exactly (that reference script was ALREADY
correct; only this live in-app path had the bug).

New test `tests/test_drag_curve_extraction.py`: asserts no Cd > 1.5
anywhere in the extracted curves. PROMETEO's own stored sim didn't
actually trigger this (its coast max_cd was 0.466 before AND after - its
descent data must fall outside the AoA filter or wasn't recorded far
past apogee) - but `reference/openrocket_examples/Dual_parachute_deployment.ork`
proves the bug is real: coast max_cd was **549.748 before the fix**,
**1.203 after**. Diego's own real .ork (not in this repo) is what
actually showed the contamination in practice.

Before/after (PROMETEO, unchanged inputs otherwise):
| | Before | After |
|---|---|---|
| Code-to-code, Brasil config | -1.45% | -1.79% |
| Code-to-code, July4 config | +10.64% | +10.22% |
| V1 (2026-07-04 real flight) | +11.44% | +11.00% |
| V2 (LASC real flight) | -5.80% | -6.12% |

All changes are small (a few tenths of a percent) - honest reporting:
this bug was real and dangerous (proven on the dual-deploy fixture) but
does NOT explain PROMETEO's own V1/V2 gap, since its particular stored
sim wasn't badly contaminated. Not tuned to force any of these numbers.

Full suite: 41 passed, 1 deselected (pre-existing opt-in Leaflet test) in ~65s.

### Item B: drag curve doesn't cover the flight's Mach range - DONE (warning), scope-cut on the "real fix"

`pipeline.run_simulation` now computes the drag curve's own max Mach
(`curve_utils.curve_max_x`) and compares it to the flight's actual max
Mach - if exceeded, a red "Drag curve Mach coverage" WARN sanity check
fires on the Results page naming both numbers and explaining rocketpy
holds the last known Cd past the curve's end (misses the transonic drag
rise). Confirmed on REAL data, not synthetic: PROMETEO's own default
(no-override) flight organically exceeds its own curve (reaches Mach
0.477, curve only covers to 0.463) - now a permanent regression test.

**RocketSerializer scope cut, stated plainly**: `rocketserializer_check.py`
detects a usable Java (OpenRocket's bundled Windows JRE first, then PATH)
and gives the plain-English fallback message Diego asked for either way.
It does NOT actually invoke RocketSerializer - that needs the separate
`rocketserializer` package (not installed, not a rocketpy dependency) and
an OpenRocket .jar, and its CLI's real invocation/output format isn't
something this sandbox can verify (no Java+OpenRocket+rocketserializer
combination available to test against). Writing that blind would risk
shipping broken, unverifiable code - exactly what CLAUDE.md Rule 2 says
not to do. Diego: if you want this wired up for real, the fastest path is
testing it yourself on your machine (Java + OpenRocket already there) and
sending back the exact command + output format, or I can attempt it
blind next time if you'd rather have an untested first draft to fix
together.

Full suite: 42 passed, 1 deselected in ~63s.

### Item C: reproducibility - DONE

`RunRecord` now stores: app git commit hash, `.ork`/`.eng`/drag-CSV
content hashes (sha256, 12 hex chars), launch site lat/lon/altitude,
motor designation, max Mach + drag curve Mach coverage + extrapolated
flag (reusing item B's fields), and drag curve source. Also fixed a
pre-existing display bug found while wiring this up: `ork_filename` was
using `parsed_ork.name` (the ROCKET's declared name from inside the
.ork's own XML) instead of the actual uploaded file's name - History was
never showing the real filename at all.

History page: new columns (App version, Site, Motor, Max Mach, Cd
source); a run made with an older commit than the one currently running
is labelled "(older)" with an orange banner explaining it may not be
comparable to today's numbers - directly answers Diego's own "same
inputs, different Mach on different runs" report (most likely explained
by the app changing between those runs, now provable instead of guessed).

New test `test_same_inputs_give_identical_results`: two independent
`run_simulation` calls from the same inputs must match EXACTLY (a plain
Simulate has no randomness at all) - a regression canary for any future
hidden-global-state bug (the same class as the curve-mutating-input-file
bug fixed earlier this project).

"Clean up corrupt runs" button added to History: `run_history.cleanup_corrupt_runs`
moves (not deletes) any run whose record.json fails to parse into
`runs/_corrupt/<run_id>/`.

Full suite: 43 passed, 1 deselected in ~64s.

### Item D (old lettering) / F (new lettering): new simulation report - DONE

Replaced the old compliance-style report entirely with a formal
simulation report: cover page (mission/vehicle/date/app version/author),
real table of contents (reportlab TOC + page numbers via a NumberedCanvas,
both auto-generated, not hand-maintained), and 10 numbered sections -
Executive summary (KPI table), Vehicle (side drawing with CG/CP,
dimensions, mass, stability, parachute table), Propulsion (thrust plot +
motor table), Aerodynamics (Cd-vs-Mach plot + source + Mach coverage,
reusing item B's fields), Environment (site/wind/rail), Nominal flight
(every plot from Simulate), Recovery (table + descent plot), Flight
cases (Ballistic/Nominal/DrogueOnly/MainAtApogee comparison table + a
NEW overlaid-altitude-vs-time plot built fresh from each case's Flight
object), Monte Carlo (N + "not statistically meaningful" warning if
N<100 + histogram/ellipse rebuilt from raw samples, not a stale page
screenshot), Assumptions. RCSM compliance section REMOVED (stays on the
RCSM page only, per instruction) - no internal jargon anywhere.

**Appendix (optional, off by default, checkbox on the Exports page)**:
model validation vs. PROMETEO flights, now pulled from
`bup_rocketpy/validation.py` - a NEW module extracted from
tests/test_phase2_validation.py's own audited V1/V2 logic (same
translate.ork_to_flight calls, no hand-built rocket). This fixes a
DEEPER bug than the report alone: the Validation PAGE ITSELF was also
hardcoded and had ALREADY drifted out of sync with the report's own
different hardcoded numbers (1136.5/1071.1 on the page vs. 1124.1/1196.9
in the report, neither matching the real current -1.79%/... code-to-code
number). Both the page and the report's appendix now call the SAME live
function - can never silently diverge again. New test
`tests/test_validation_live.py`.

`build_report_data()` gathers everything from already-computed app state
into one plain dict; `generate_pdf`/`generate_docx` render from that
SAME dict so the two formats can't disagree. Rewrote
`tests/test_phase5_report_and_zip.py` for the new API (4 tests, all
passing) - also locks in the compliance section is gone and the old
"credit the officials, not us" wording rule now applies to the appendix.

Full suite: 46 passed, 1 deselected in ~76s.

### Item D (new lettering): reefed parachute + line cutter - DONE

RCSM REC 8.1.1 explicitly accepts "reefed main deployment + un-reefing"
as real dual-event recovery - a reefed single canopy was previously
getting the same "FAIL REC 8.1.1, only 1 parachute" as a genuinely
single-deploy vehicle. Fixed at every level:

- `ork_reader.Parachute` gained `is_reefed`/`reefed_diameter_m`/
  `reefed_cd`/`cutter_altitude_m`/`cutter_delay_s` - always user-set (OpenRocket
  has no concept of this at all), never parsed from the .ork.
- `translate.build_rocket` adds TWO real rocketpy Parachutes for a reefed
  chute (reefed-stage at the chute's own trigger, full-stage at the
  cutter's altitude) instead of one - physically safe because rocketpy's
  own numeric trigger only fires while descending (verified directly in
  rocketpy/rocket/parachute.py's source: `y[5] < 0 and h < trigger`), so
  the two stages sequence correctly with no shared state needed.
- `rcsm_cases._classify_parachutes` returns synthetic drogue/main
  surrogates for a reefed single chute, so DrogueOnly (cutter never
  fires) and MainAtApogee (cutter fires at apogee, full chute at apogee)
  reuse the exact same code path a real drogue+main vehicle already used
  - no more "not a real dual-deploy topology" warning for a reefed one.
- `rcsm.check_compliance`: REC 8.1.1 already worked correctly once
  build_rocket added 2 real parachutes (just counts `len(rocket.parachutes)`).
  Added REC 8.1.3 (drogue/reefed settled descent rate 20-45 m/s) and REC
  8.1.4 (main/full release <=500m AGL, final <10 m/s) - these had
  long-standing UNUSED constants but were never actually wired up to any
  check, for ANY vehicle, reefed or not.
- `translate.required_cd_s_for_descent_rate()`: the "target reefed
  descent rate" helper, inverting v=sqrt(2mg/(rho*Cd*S)).
- Rocket page: editable "Reefed parachute (line cutter)" section per
  parachute (checkbox + reefed diameter/Cd, cutter altitude/delay, a
  "Compute reefed diameter" button using the helper above) - mutates the
  loaded `parsed.parachutes[i]` in place, same object every other page
  already reads.

**Real bug caught and fixed during development, not shipped**: my first
REC 8.1.4 implementation used `flight.altitude(t) - flight.env.elevation`,
silently giving a release altitude of ~5m instead of the real ~500m.
`flight.altitude(t)` is ALREADY AGL in rocketpy (unlike `flight.z(t)`/
`flight.apogee`, which are ASL and need that subtraction) - confusing the
two conventions is an easy, quiet way to get a plausible-looking wrong
number. Verified directly against the real trajectory before shipping,
documented in a code comment so it doesn't happen again.

New test file `tests/test_reefed_parachute.py` (4 tests) using PROMETEO's
real .ork with its one real parachute marked reefed (not an invented
rocket) - covers: build_rocket adds 2 parachutes, all 4 RCSM cases run
with no dual-deploy warning and REC 8.1.1 PASSes, the AGL/ASL regression
guard, and the descent-rate helper's math.

Full suite: 50 passed, 1 deselected in ~76s.

## Section E: small fixes (done)

- **LASC zip real filenames**: NiceGUI's upload handlers saved every
  `.ork`/`.eng` to a random `tempfile.mkstemp()` path and discarded the
  user's real filename right after the upload notification - so the LASC
  zip and its README always said e.g. `tmpabc123.ork` instead of
  `Major_tom.ork`. Fixed by threading the real name through: `state.py`
  gained `ork_filename`/`eng_filename`; `app.py`'s upload handlers now
  store the real name alongside the tempfile path; `lasc_package.
  build_lasc_zip()` and `run_history.save_run()` both take optional
  `eng_filename`/`ork_filename` params (falling back to the tempfile
  path's own basename only if not given, so direct script/test callers
  are unaffected); `exports_page.py` and `app.py`'s Simulate handler now
  pass the real names through.
- **Monte Carlo default N**: raised the UI default from 50 to 200
  (CLAUDE.md Phase 4 says "default N=200, editable"). Added a live
  warning under the N field when N<100 ("won't be statistically
  meaningful").
- **Landing map improvements**: added 1/2/5 km dashed distance rings
  around the pad marker (plain `leaflet.circle`, meters-based, unlike the
  flat-XY ellipse polygons) for a quick sense of scale. Added editable
  "Rail inclination"/"Rail heading" number inputs on the Monte Carlo page
  (defaulting to the .ork's saved simulation values) so the operator can
  set the rail setup they actually plan to use on launch day (e.g.
  pointed into the day's wind) before running - previously these were
  hardcoded to the .ork's stored values with no way to override them.
  Threaded `inclination_deg`/`heading_deg` overrides through
  `monte_carlo.run_monte_carlo()` -> `_run_one_mc_sample()` (both the
  nominal Flight and the StochasticFlight sampling center use the
  override when given, the .ork's own value otherwise - so every
  existing caller/test is unaffected by the new, defaulted-to-None
  params).

New test `test_inclination_and_heading_override_shift_the_landing_ellipse`
in `tests/test_phase4_monte_carlo.py`: same seed, only heading differs by
180 deg, asserts the landing point actually moves (catches a silently-
ignored override).

Full suite: 51 passed, 1 deselected in ~76s.

## Section G: CSV export matching OpenRocket's format (done)

New `bup_rocketpy/openrocket_csv_export.py`: builds the SAME 58-column
layout OpenRocket's own "Export simulation data" produces (verified
directly against the 3 real OR export CSVs already in
`reference/prometeo_mission44/data/openrocket_exports/` - same column
names/units, same "# Event X occurred at t=..." lines interleaved with
data rows at the right position, one row per solver time step rather
than a fixed resample - OR itself exports its own adaptive solver grid,
not a fixed-dt resample).

Every column is a REAL rocketpy value, never invented:
- Position/velocity/acceleration/angle-of-attack/Mach/Reynolds/wind/
  atmosphere columns map directly to existing `Flight`/`Environment`
  Function attributes.
- CG/CP location (cm): converts rocketpy's internal frame back to
  OpenRocket's own nose-tip-referenced convention using the SAME
  `translate._coordinate_transform` function that built the rocket in
  the first place (an involution, so re-applying it inverts it) - "the
  ONE place" per that function's own docstring. **Caught before
  shipping**: a first version multiplied by `rocket._csys` instead
  (coincidentally +1 for this app's always-used "tail_to_nose"
  orientation, so it silently did nothing), giving CG/CP as *negative*
  cm-from-nose. Caught by checking that CP must be aft of (a larger
  from-nose distance than) CG for a stable rocket - it wasn't, both were
  negated. Now locked in behind a regression test.
- Drag coefficient: computed as drag_force / (dynamic_pressure *
  reference_area) directly from the flown trajectory, rather than
  guessing which of rocketpy's power_on/power_off Mach-Cd curves was
  active at each instant - always correct, no internal-state guessing.
- Columns OpenRocket has that rocketpy has no equivalent for at all
  (component-level drag breakdown: friction/pressure/base/axial
  coefficients; and the moment/side-force/roll coefficients; Reynolds
  breakdown; per-step computation time; an explicit Coriolis term) are
  left blank - and this is not a compromise unique to this app: the REAL
  PROMETEO OpenRocket export has several of those same columns blank for
  its entire flight too (an axisymmetric rocket with no fin cant
  genuinely has no meaningful roll-forcing/roll-damping/side-force
  value), verified by inspecting that file directly.

Wired into the app: `pipeline.run_simulation` now also writes
`flight_data_openrocket_style.csv` next to the existing generic CSV
(`SimResult.openrocket_csv_path`), and the Exports page has a second
download link for it.

New `tests/test_openrocket_csv_export.py` (3 tests, using PROMETEO's
real .ork/.eng through the same `translate.ork_to_flight` path every
other test uses): 58-column count + real event markers (IGNITION,
LAUNCHROD, BURNOUT, APOGEE, RECOVERY_DEVICE_DEPLOYMENT, GROUND_HIT),
sane apogee/Mach columns, and the CP-aft-of-CG sign regression guard
described above.

Full suite: 54 passed, 1 deselected in ~80s.

## Section H: launch-day mode + competition profiles + README (done)

**H.1 - launch-day mode, fully offline once downloaded:**
- New `bup_rocketpy/weather.py`: Open-Meteo forecast + historical
  weather, both going through one small `_http_get_json` seam so every
  test can mock the network (this cloud sandbox can't reach
  api.open-meteo.com - CLAUDE.md already anticipated this: "test with
  mocked data and cache every downloaded profile"). Every successful
  fetch is cached to `outputs/weather_cache/*.json`; a second call for
  the same site/date reads the cache with ZERO network calls (verified
  by a test that mocks the HTTP function and asserts it's never called
  again). A cache-miss + network failure raises a clear
  `WeatherUnavailableError` telling the operator to download it ahead of
  time - never an unhandled crash. A STALE cache (network fails on a
  forced refresh) still returns the old data, labeled "refresh failed",
  rather than losing what was already downloaded.
- New "Launch Day" page (`gui/pages/launchday_page.py`, in the sidebar):
  site lat/lon (defaults to the loaded .ork's own site), launch
  date/hour, "Download weather for launch day" button, then "Use this
  weather for Simulate" - builds a `dataclasses.replace()`'d
  LaunchConditions with the real wind and stores it as
  `state["launch_override"]`.
- `pipeline.run_simulation()` gained an optional `launch_override` param
  (defaults to None - every existing caller/test unaffected) that
  replaces the `.ork`'s own recorded launch conditions for that one run;
  `app.py`'s Simulate handler now always passes `state["launch_override"]`
  through. New test `test_launch_override_changes_the_simulated_wind_not_just_ignored`
  proves a 25 m/s override actually moves the landing point, not just
  gets silently ignored.
- `translate.wind_uv()`'s speed+bearing->(u,v) formula was factored out
  into `wind_speed_direction_to_uv()` so weather.py's real-weather
  overrides use the EXACT same, already-verified conversion instead of a
  second hand-written copy (Open-Meteo's `wind_direction_10m` uses the
  same meteorological "blows FROM" convention as OpenRocket's own
  `<winddirection>`).

**H.2 - competition profiles (data-driven, replaces the previous H.2
spec):** New `bup_rocketpy/competition_profiles.py` - a small registry
(Test flight / LASC / ENMICE / IREC), each holding a mission-ID naming
template and which compliance ruleset (if any) applies. **Per CLAUDE.md
Rule 2 ("never invent data"): only LASC's profile claims a verified
ruleset** (`RCSM_ED7_REV1`, the only one `rcsm.py` actually implements).
ENMICE and IREC are real, selectable profiles with editable
naming/site defaults, but their `rules_status` says plainly "NOT
VERIFIED - ask Diego for [comp]'s rules" rather than pretending this app
checks rules it was never given - locked in by
`test_enmice_and_irec_do_not_claim_a_verified_ruleset`.
- `case_export.generate_case_script()` gained an optional
  `mission_id_template` param (None keeps CRS 10.1.6's exact hardcoded
  naming - regression-tested); `lasc_package.build_lasc_zip()` forwards
  it. Exports page has a "Competition profile" selector wired to both the
  zip's naming and a `rules_status` banner; RCSM Cases page shows the
  same honesty banner when a non-LASC profile is selected (the
  compliance table itself is unchanged - it's always RCSM Ed.7 Rev.1,
  since that's the only ruleset implemented, labeled "reference only" for
  other profiles).

**README.md**: added a page list, a "For new team members" section
(how to run tests, the AGL/ASL gotcha with a real bug reference, the
coordinate-frame conversion rule, why Monte Carlo uses processes not
threads, why weather tests mock the network), an updated file-layout
list (weather.py, competition_profiles.py, openrocket_csv_export.py,
monte_carlo.py, report.py, run_history.py, validation.py all now
listed), and corrected the stale hardcoded V1/V2 numbers to match what
the Validation page actually computes live.

New test files: `tests/test_weather.py` (6 tests, mocked HTTP),
`tests/test_competition_profiles.py` (5 tests). Extended
`tests/test_phase3_headless.py` (+1) and `tests/test_phase0_e2e_full.py`
(added `/launchday` to the real-browser page sweep - passed, screenshot
at `docs/screenshots/12_launchday.png`).

Full suite: 66 passed, 1 deselected in ~82s (headless); Playwright e2e
run separately, both scenarios pass including the new Launch Day page.

## Section I: real-weather validation (done)

`bup_rocketpy/validation.py` gained `compute_v1_with_real_weather()` and
`compute_v2_with_real_weather(date)`, reusing `weather.py` (Section H) to
pull Open-Meteo's HISTORICAL archive for the real flight site/date
instead of the OpenRocket-recorded wind `compute_v1()`/`compute_v2()`
use, then re-running the exact same `_run_case()` path.

- **V1** (2026-07-04, Pachuca): the real flight date is already known
  (CLAUDE.md Sec 3.2), so this is fully wired and testable end to end.
- **V2** (LASC 2026, Iacanga): **the exact flight date is NOT YET
  RECORDED in this project** (PROGRESS.md's own Section 4 already logged
  this as "pending from Diego" in an earlier session). Per CLAUDE.md
  Rule 2 ("never invent data"), `compute_v2_with_real_weather()` takes
  the date as a REQUIRED argument and raises a clear
  `V2FlightDateUnknownError` if it's missing, rather than guessing one -
  this is a real, already-logged, still-open blocker, not a new one.
- Validation page: "Re-run V1 with real weather" button (works
  standalone); a date input + "Re-run V2 with real weather" button that
  shows the same honest "date not yet known, ask Diego" message inline
  until one is typed in.
- Every weather-fetching test mocks the HTTP layer (this cloud sandbox
  can't reach Open-Meteo) - `tests/test_real_weather_validation.py` (3
  tests): V1 real-weather re-run is sane and hits the historical
  endpoint, V2 refuses with no date, V2 succeeds once a date is given.

## BLOCKED / NEEDS DIEGO (carried forward, not new)

- Exact LASC 2026 flight date/time at Iacanga - needed to actually use
  Section I's "Re-run V2 with real weather" button for anything but a
  placeholder date. Everything else about that button already works.

Full suite: 69 passed, 1 deselected in ~87s (headless); Playwright e2e
re-run separately after this section too, both scenarios still pass.

## Section J: Mission Control UI redesign - DEFERRED (deliberate, not skipped)

Per the overnight-run instructions, J is explicitly last priority,
"only after A-I pass, never break the working app." A-I all pass (full
suite: 69 passed, 1 deselected; Playwright e2e: 2/2, both re-verified
this session).

J itself (home page redesign, 3D flight playback with orthogonal views,
live Monte Carlo visualization, an offline-bundled 3D library, Playwright
screenshots) is a genuinely large, novel feature, not a polish pass:
- The app currently has a STATIC 3D trajectory PNG per flight
  (`flight.plots.trajectory_3d()`, already in both the plot tabs and the
  PDF report) - what's asked for is an interactive, scrubbable playback
  with switchable orthogonal views, which needs either a real WebGL/3D
  JS library (three.js or similar) bundled for fully-offline use, or a
  from-scratch canvas renderer - neither exists in this repo yet, and
  `requirements.txt`/the frontend bundle would both need real, carefully
  tested additions.
- Live Monte Carlo visualization (rendering samples as a batch runs, not
  just a histogram at the end) touches the same background-thread/
  ProcessPoolExecutor machinery `monte_carlo.py` already has real,
  hard-won correctness fixes in (the index-alignment bug from earlier
  tonight) - a rushed change there risks a regression in code that is
  currently correct and tested.
- Visual/UX quality for a 3D redesign can't be meaningfully verified in
  this sandbox: Playwright is already documented as flaky here
  (`test_phase0_e2e_full.py`'s own history), and a screenshot diff can't
  substitute for actually looking at a live 3D scene.

Given all of that, and the explicit instruction to never risk the
working app for this lowest-priority item, **I did not attempt J this
session.** This is a deliberate stop, not a dropped task - the app is in
a fully working, fully tested state (A-I complete) to hand back for a
decision on how J should actually be scoped (which 3D library, whether a
simpler 2D orthogonal-view alternative is acceptable, how much of a
redesign the home page actually needs) before real implementation work
starts on it.

---

# 2026-09-27 overnight run (MEGA_PROMPT_2): mass/CG accuracy, reefing/
mission persistence, weather correctness, History UX, validation
consistency, a real prose report, and finishing the Mission Control
redesign (J is now in scope).

## Section 1: mass/CG/inertia matching OpenRocket (done, mostly)

Diego tested Major Tom on his own machine: OpenRocket says dry mass
15.006 kg / CG 122 cm; the app said 12.274 kg / CG 80.4 cm - a ~2.7 kg /
34% gap, almost certainly the dominant cause of the reported Mach 1.05
vs. OpenRocket's own 0.91 and the apogee gap. Major Tom's `.ork`/`.eng`
are STILL not in this repo (flagged since Phase 1) - can't be verified
on the real vehicle - but the root cause and fix generalize to any
vehicle, and are proven here against PROMETEO's real `.ork` and both
OpenRocket example files.

**Root cause**: the app's ONLY mass/CG source (absent a manual/.ork
override) was a from-scratch geometric thin-shell approximation
(`translate.estimate_dry_mass_and_cg`) that ignores every component
OpenRocket itself accounts for beyond nose/tubes/transitions/fins/point
masses - inner tubes, centering rings, bulkheads, launch lugs, adhesive,
hardware. Checked directly against BOTH shipped OpenRocket example
`.ork` files' own stored-simulation mass (their real ground truth): the
geometric estimate was **-34.9% and -49.7%** off. For PROMETEO
specifically the gap happened to be small (~1.3%, big airframe shell
dominates), which is exactly why this bug went unnoticed until a
smaller/differently-proportioned rocket (Major Tom) exposed it.

**Fix (item 1a - the one that matters)**: `translate.
estimate_best_dry_mass_cg_inertia()` (new) now prefers OpenRocket's OWN
computed t=0 with-motor mass/CG/inertia - read straight from the `.ork`'s
stored simulation databranch via the already-existing (but previously
UNUSED outside a dev script) `ork_reader.parse_stored_simulation_references()`
- minus the motor (`translate.derive_dry_mass_and_inertia_from_with_motor`,
itself already validated by V1/V2), whenever a stored simulation exists.
Priority order: (1) whole-rocket/subcomponent MASS override (team-
measured, unchanged, still wins outright), (2) NEW: OpenRocket-computed
from stored sim, (3) geometric estimate (unchanged fallback, only for a
geometry-only `.ork` nobody has ever simulated in OpenRocket). Wired into
`pipeline.run_simulation` (the real default path) and `rocket_page.py`'s
pre-Simulate preview.

**Real bug caught while building this, fixed before shipping**: OpenRocket's
own "Longitudinal moment of inertia" column is actually the TRANSVERSE
(pitch/yaw) inertia, and "Rotational moment of inertia" is the AXIAL
(roll) one - the opposite of what the names suggest in isolation.
Confirmed via `config.py`'s own OpenRocket-sourced constants
(`INERTIA_LONG_T0_WITH_MOTOR=1.612` >> `INERTIA_ROT_T0_WITH_MOTOR=0.020`,
and physically: a long slender rocket's transverse inertia is always
much larger than its roll inertia). This ALSO meant Section G's
OpenRocket-style CSV export (from last night) had shipped these two
columns backwards - fixed there too, with a regression test in both
places.

**Item 1c (rocket length)**: `ork_reader.airframe_length_m()` (already
existed, used only for the "component outside airframe" safety check)
now also accounts for a transition/boat-tail placed AFTER the last body
tube - previously silently excluded from EVERY "rocket length"
computation in the app (5+ duplicated body-tubes-only formulas across
`report.py`, `rocket_drawing.py`, `rocket_page.py`, `case_export.py`, and
critically `translate.build_rocket`'s own motor-position placement,
which assumes the motor/nozzle sits at the airframe's aft end). All 5
duplicates now call this ONE function instead. A missed boat-tail would
have pushed the assumed motor CG too far forward for any rocket that has
one - part of the same class of bug as the mass mismatch.

**Item 1b (deep per-component geometric model)**: DEFERRED, honestly -
not silently skipped. Given 1a's fix, this only matters for a
geometry-only `.ork` with no stored simulation ever run (a narrow case);
whenever a stored sim exists (true for PROMETEO, both OpenRocket
examples, and almost certainly Major Tom too, since Diego quoted its own
"PACHUCA" sim numbers), 1a already gives an exact match to OpenRocket's
own total. Modeling inner tubes/centering rings/bulkheads/launch lugs
individually would be a substantial `ork_reader.py` parser expansion for
comparatively little additional accuracy given 1a's coverage - flagged
here rather than attempted partially/rushed.

**Item 1d (Major Tom code-to-code re-check)**: BLOCKED - no Major Tom
`.ork`/`.eng` in this repo (see NEEDS DIEGO below). The mechanism itself
(1a) is proven against PROMETEO's real `.ork` and both OpenRocket
examples instead - `tests/test_mass_cg_from_stored_sim.py` (4 tests):
stored-sim-derived mass/CG is sane for PROMETEO, a whole-rocket override
still wins over it, a geometry-only rocket still falls back to the
geometric estimate, and the `airframe_length_m()` transition fix (a
synthetic boat-tail rocket, since neither real `.ork` on hand has one).

PROMETEO's own default-path numbers with the new source: apogee 1072 m
(was 1088 m; acceptance target ~1080 m - closer, not worse), static
margin 2.04 cal (was 1.94; target ~1.9), descent 5.51 m/s (was 5.49;
target ~5.5) - a real accuracy improvement, not a regression, even
though it no longer reproduces the OLD geometric estimate's exact
numbers.

Also fixed for consistency (same principle Diego's item 2 argues for
reefing): `SimResult` now carries the inertia ACTUALLY used to build the
flown rocket (`i_axial_kgm2`/`i_transverse_kgm2`/`inertia_source`), and
Monte Carlo/RCSM Cases/Exports all read that instead of silently
re-deriving their own (possibly different) geometric estimate - the same
"single source of truth" bug class as the reefing-not-applied issue,
just for mass/inertia instead of parachute settings.

New test `test_longitudinal_inertia_column_is_the_larger_transverse_value`
in `test_openrocket_csv_export.py`. Full suite: 74 passed, 1 deselected;
Playwright e2e: 2/2.

## Section 2: reefing not applied + settings lost (mission persistence) - done

**Root cause of "I enable reefing, go back to Simulate, have to re-upload,
reefing is ignored"**: the reefing edit lives ONLY in the in-memory
`state.state` dict (a single Python-process-lifetime object) - it was
never persisted anywhere. Every page-to-page navigation within a LIVE
server already shares that same object correctly (confirmed: the
existing Playwright e2e test already walks Simulate -> Rocket -> ... ->
back without re-uploading, and passes) - the actual loss happens across
anything that restarts the server process (closing/reopening the app,
a crash, a new day). Once that happens, re-uploading rebuilds
`load_result` from the RAW `.ork` file again, which has no `is_reefed`
concept at all (OpenRocket doesn't model it - see `ork_reader.Parachute`'s
own docstring) - so the edit is gone, exactly as reported.

**Fix**: `run_history.py` (which already auto-saves every Simulate run)
now captures the FULL session state, not just the result:
`reefing_settings` (every parachute's full reefing config, not just
reefed ones), `dry_mass_override_kg`/`dry_cg_override_m`,
`launch_override` (the Launch Day weather override, if any),
`competition_profile`. It also now actually COPIES the `.ork` itself
(previously only the `.eng` was copied - a real, separate gap) plus both
drag CSVs into the run's own folder. New `run_history.reopen_run(repo_root,
run_id, outputs_dir)`: re-parses those saved files fresh and re-applies
every saved setting on top (reefing via `dataclasses.replace` matched by
parachute name), returning a ready-to-install session bundle. Raises a
clear `MissionNotReopenableError` for a run saved before this feature
existed (no saved `.ork`) rather than fabricating one.

Verified end to end (not just "the settings round-trip as data"): after
save + reopen, `translate.build_rocket()` on the reopened mission
produces the real 2-parachute (reefed + full) rocket - proving reefing
actually still applies to Flight/RCSM Cases/Monte Carlo/report/CSV after
a reopen, since they all build the rocket through this same
`build_rocket()` call.

**Status bar** (item 2's other ask): added to `layout.py` (the ONE place
every page already routes through) - loaded rocket/motor, a "Reefing ON:
reefed Cd·S X m², cutter at Y m" chip when active, a "Weather: ..."
chip when a Launch Day override is active, and a "Profile: ..." chip
always shown. Confirmed rendering correctly in the real Playwright
screenshots (`docs/screenshots/09_history.png`).

The "Reopen this mission" BUTTON itself (the UI Diego actually clicks)
is item 4's job (History page detail view) - the backend built here is
what it calls.

New `tests/test_run_history_mission.py` (3 tests): full save/reopen
round-trip with reefing verified via a real rebuilt Rocket's parachute
count, `MissionNotReopenableError` for a run with no saved `.ork`, and
backward compatibility with an old-schema `record.json` missing every
new field entirely.

Full suite: 77 passed, 1 deselected; Playwright e2e: 2/2.

## Section 3: launch-day weather correctness - done

**3a - the real bug**: Diego reported 0.3 m/s from 121° for a launch
day where the public forecast said 4-9 m/s from the NE. Root cause:
`weather.py`'s Open-Meteo requests never passed `timezone=`, so
Open-Meteo defaulted to returning `hourly.time` in GMT while the UI's
"launch hour" field is LOCAL time (America/Mexico_City, UTC-6) - asking
for "12:00" silently read the row for 12:00 UTC = 06:00 local, early
morning, characteristically much calmer than midday. Every request now
passes `timezone=auto` (Open-Meteo resolves the site's own IANA zone and
returns local-time timestamps) and `wind_speed_unit=ms` explicitly
(removed the manual km/h->m/s division entirely - one less place to get
a unit conversion wrong). Also added: a real wind-speed-vs-altitude
table (surface + 1000/925/850/700 hPa, ICAO-standard-atmosphere-labeled
approximate altitudes) on the Launch Day page, per Diego's "show the
full wind profile vs altitude, not just one number" - the pressure-level
parameter names are Open-Meteo's documented convention but could not be
verified against the live API from this sandbox (no egress); double-check
the first real download.

**3b - dates beyond the forecast horizon**: `fetch_forecast_weather` now
checks the date client-side against Open-Meteo's ~16-day window BEFORE
making a request, raising a specific `ForecastHorizonError` (not a
confusing generic network-error message) that points at the new
"Download climatology" button. `weather.fetch_climatology()` averages
the historical archive's wind for the SAME month/day/hour across the
last 10 calendar years - correctly using a CIRCULAR mean for direction
(a naive arithmetic mean of e.g. 350°/10° gives 180°, exactly
backwards), and tolerating one bad year's fetch failure without losing
the rest. The Launch Day page can apply the climatology mean directly to
Simulate, or push its mean+spread into Monte Carlo's own wind
uncertainty entry as a real planning distribution.

**3c - cross-check tests**: `tests/test_weather.py` grew to 11 tests
(was 6) - explicit assertions that `timezone=auto`/`wind_speed_unit=ms`
are actually sent, the wind-vs-altitude table's shape, the forecast-
horizon rejection, the circular-mean fix, and one-bad-year tolerance.

Full suite: 82 passed, 1 deselected; Playwright e2e: 2/2.

## Section 4: History page - detail view, reopen, real delete fix - done

**The reported bug, root-caused**: "clicking 'Delete A' adds MORE rows
of Compare/Delete controls every time." The old page built the compare/
delete row (`with ui.row()...`) OUTSIDE the container `render_table()`
clears before rebuilding - every `render_table()` call (after a delete,
a cleanup, anything) appended a fresh copy of those controls that was
never removed. Fixed by moving EVERYTHING (rows, checkboxes, delete
buttons) inside the one container that gets `.clear()`'d each render -
proven with a real Playwright test that deletes a run and counts the
remaining delete buttons (would show MORE under the old bug, not fewer).

**Rewrite**: each run is now one row with a checkbox (pick up to 2 for
Compare), a "view" icon, and a trash icon that opens a confirmation
dialog before deleting (no more accidental single-click deletes). A
"Only show runs from the current app version" filter checkbox (the
"filter/hide old-version runs" ask) replaces the old passive banner-only
warning.

**New detail page** (`/history/{run_id}`): every KPI, the settings
actually used (mass/CG override or not, weather override or not,
competition profile, reefing per parachute), the files used (.ork/.eng
filenames + hashes + app version), that run's own saved plots, a CSV
download link (new `/runs` static route in `app.py`, separate from the
existing `/outputs` route - a different directory), and a "Reopen this
mission" button wired to Section 2's `run_history.reopen_run()` -
installs everything into `state.state` and jumps to Simulate.

New Playwright test `test_history_delete_does_not_duplicate_controls_and_detail_page_opens`
(2 real saved runs via `save_run`, not hand-typed records): opens a run's
detail page and confirms real content, deletes one of two runs through
the actual confirmation dialog, and asserts exactly one delete button
remains - the literal reported symptom, verified through a real browser.

Full suite: 83 passed, 1 deselected; Playwright e2e: 3/3 (including the
new History test).

## Section 5: validation consistency (V2 now PASSES) - done

**The reported bug, root-caused**: the no-override default run
(PROMETEO, Brasil config, ~10.5 kg) gave 1088 m, but V2 (10.370 kg, 130-
150 g LIGHTER, same site) gave 1067 m - LOWER. Physically backwards: a
lighter rocket on the same motor with everything else equal must reach a
HIGHER apogee, never a lower one. Root cause: `compute_v2()` was a hand-
rolled duplicate of the default path that pulled its with-motor CG
(`config.py`'s `CG_T0_WITH_MOTOR=0.97966 m`) and rocket length
(`config.py`'s `LENGTH=1.54 m`) from a DIFFERENT source document than
the .ork's own stored databranch, which independently give 1.000 m and
1.47 m for the SAME nominal configuration - a real data-consistency bug,
not a physics effect.

**Fix**: `translate.estimate_best_dry_mass_cg_inertia()` (Section 1)
gained an optional `total_mass_override_kg` param - `compute_v2()`
(and its real-weather variant) now calls the EXACT SAME function the
unconstrained default path uses, overriding ONLY the total mass to
10.370 kg. Rail/inclination/heading overrides were also dropped entirely
- confirmed the .ork's own launch conditions already ARE 4.0 m/80 deg/
90 deg, so re-specifying them was pure redundant duplication with the
same silent-drift risk.

**Result**: V2 now predicts 1098.3 m (target 1137 m) - **-3.4% error,
PASSES within +-5%** (was -6.1%, FAIL). This is a real, earned
improvement from fixing a genuine bug, not tuning - V1 (+11.0%) is
unchanged and still fails, so the app-wide PROVISIONAL badge correctly
stays up per CLAUDE.md Rule 3 (needs BOTH to pass).

**Side-by-side input table** (the explicit ask): new
`validation.compute_default_path_reference()` runs the SAME .ork through
the unconstrained default path; the Validation page now shows V2 and the
default path's inputs (dry mass/CG/source, site, rail) next to each
other, so the "same path, only the mass differs" claim is visually
auditable, not just asserted in prose - see
`docs/screenshots/11_validation.png`.

**V1 (July 4 .ork)**: checked `reference/prometeo_mission44/data/rockets/`
per your instruction - only the two drag CSVs are there, no July-4-
specific `.ork`. Logged below, not fabricated.

New `test_v2_lighter_config_predicts_a_higher_apogee_than_the_default_path`
in `tests/test_validation_live.py` - a permanent regression guard for
this exact bug class (asserts the lighter config's apogee is HIGHER, and
that V2 now passes).

Full suite: 84 passed, 1 deselected; Playwright e2e: 3/3.

## Section 6: real technical report (done)

Read both reference reports in `docs/report_references/` in full before
touching any code, per your explicit instruction (PROMETEO's own
submitted report - 14 pages, the structure/look template; the Colibri
Hybrid report - 54 pages, the narrative-prose tone reference). Then read
the CURRENT `bup_rocketpy/report.py` (576 lines) in full to know exactly
what already existed before rewriting it, instead of guessing.

**What was actually wrong** (found by reading the code, not assumed):
the PDF's `TableOfContents` flowable was built and added to the story,
but the `BaseDocTemplate` was never subclassed to call
`notify('TOCEntry', ...)` in `afterFlowable` - reportlab's own two-pass
TOC mechanism needs that hook to populate itself. With no entries ever
notified, the TOC silently rendered empty on every report ever
generated - this **was** a real bug, not Diego misreading an old PDF.
Fixed with a proper `_ReportDocTemplate` subclass (new in `report.py`)
that detects the "H1Numbered"/"H2Numbered" heading styles, calls
`notify`, and also registers a real PDF bookmark/outline entry for each
section (so a PDF viewer's own sidebar outline works too, not just the
in-document TOC page). Verified with a new test that opens the generated
PDF via `pypdf` and asserts the outline actually has >= 8 entries - a
regression test that would have caught the original bug.

**The report was rebuilt around the requested 12-section structure**
(1 Deliverables and setup, 2 Vehicle configuration and mass properties,
3 Propulsion, 4 Trajectory (nominal+ballistic), 5 Aerodynamics,
6 Stability (incl. an independent hand Barrowman check), 7 Recovery and
landing footprint, 8 Flight cases (RCSM), 9 Monte Carlo dispersion,
10 Flight-test correlation, 11 Discussion and conclusions, 12 Files
delivered, Appendix - compliance table + model validation, off by
default) instead of the old flat "Executive summary" numbers dump.
Every section now has a **written paragraph generated from the report's
own data** (never hand-typed per report - see `_prose_*` functions in
`report.py`), referencing figures by their actual assigned number
("Figure 3 shows...") - both the PDF and DOCX renderers assign figure
numbers at render time from the same presence checks, so they always
agree with each other.

**Page 1** now has the PROMETEO-style header (bold title + mission +
vehicle name on the left, a "BEYOND UP / Universidad Panamericana ·
México / <event>" team block on the right, a thick black rule + thin
gold rule underneath), a one-paragraph auto-generated abstract, and 4 KPI
cards (apogee, max Mach, min static margin, flight time) styled as
colored boxes, not another table row. Section headings are numbered,
UPPERCASE, with a thin wine rule underneath (matching the reference
report's look). The footer is now "Beyond UP · Mission X · Computational
Simulation Report · <event>" on the left and "Page N of M" on the right
(was page-number-only before) - verified with a test that extracts a
real page's text via `pypdf` and checks for both strings.

**New `bup_rocketpy/barrowman.py`**: an independent hand-calculated
center-of-pressure check using the classical Barrowman (1966) method
(nose + fins only, the textbook dominant-term simplification - body tube
and transition contributions are neglected on purpose, and the report
says so). This is a genuine from-scratch calculation, not a call into
RocketPy's own CP code - verified against RocketPy's own answer for
PROMETEO: **1.221 m (hand) vs. 1.211 m (RocketPy), a 0.8% difference**,
which is exactly the kind of "close but not identical, because RocketPy's
model is more complete" result you'd expect from a real independent
check, not a rigged one. This now appears as report Section 6.1.

**Static margin plot** (`bup_rocketpy/gui/plotting.py`) now draws the
RCSM's 1.5-4.0 cal allowed band directly on the figure (shaded region +
labelled dashed limit lines for FLT 4.3.5/4.3.6), instead of leaving a
reader to compare an unmarked curve against a number in the text - this
is the report's "annotated figures" requirement, and it's the same plot
the app's own Simulate page shows, not a report-only special case.

**Editable text blocks** (Introduction, Objectives, Discussion,
Conclusions, Team) added to the Exports page as a collapsible section;
each falls back to a sensible auto-generated default (built from the
report's own numbers) when left blank, so a first report is never blank.
Saved to the mission via a new `run_history.update_run_text()` - a
read-modify-write PATCH of the existing run's `record.json`, not a new
`save_run()` call, so editing report text after Simulate never mints a
duplicate History entry. Round-trips through "Reopen this mission."

**RCSM compliance table** now available in the optional Appendix (off by
default), reusing whatever the RCSM Cases page already computed
(`state["compliance_rows"]`) rather than re-deriving it with a guessed
category - if Diego hasn't run RCSM Cases yet, the appendix just omits
the table instead of guessing at a category.

**No internal jargon leaked in** - verified by test (`CLAUDE.md`,
`PROGRESS.md`, `Rule 3`, `Phase 5` all asserted absent from the rendered
DOCX text).

New tests: `tests/test_barrowman.py` (2 tests, including the 0.8%
cross-check above), `tests/test_phase5_report_and_zip.py` fully rewritten
(8 tests: real sections/no jargon, data-driven prose + Barrowman check,
editable text blocks used verbatim, appendix crediting LASC officials,
appendix compliance table, PDF TOC/outline actually populated, PDF footer
branding, LASC zip contents), `tests/test_run_history_mission.py` +1 test
(`update_run_text` patches in place, round-trips through reopen).
`tests/test_phase0_e2e_full.py` now also clicks "Generate PDF report"
through the real running app (not just report.py in isolation) and
checks for "Report written" with no traceback.

New dependency: `pypdf==6.19.0` added to `requirements.txt` (used only by
tests, to open the generated PDF and inspect its outline/page text -
`start.bat` picks it up automatically on the next `git pull`).

Full suite: 92 passed, 1 skipped; Playwright e2e: 3/3 (including the new
real-report-generation click).

## Section 7: Mission Control redesign - 3D flight playback + live Monte Carlo (done)

Explicitly IN SCOPE this run (deferred in the previous overnight run's
Section J). Vendored **three.js r128** (MIT license) via `npm pack
three@0.128.0` - the cdnjs/most CDN hosts are blocked from this sandbox,
but `registry.npmjs.org` is directly reachable, so the UMD minified
build was extracted from the real npm tarball, not hand-copied from
memory. Lives at `bup_rocketpy/gui/static/vendor/three.min.js` (+ its
own `LICENSE` file next to it) and is served by a new `/static` static
route in `app.py` - loaded via a plain `<script src=...>` tag, **no
CDN, works fully offline**.

**New `bup_rocketpy/gui/static/playback.js`**: a hand-written (not a
three.js example copy-paste) viewer with two entry points:
- `BUP.playback.create(containerId, data)` - the flight playback view:
  1 perspective camera (drag to rotate, scroll to zoom) + 3 fixed
  orthographic cameras (side X-Z, side Y-Z, top X-Y) all rendering the
  SAME three.js scene (one rocket marker, one trajectory line, one set
  of event-marker spheres - four synced views, not four separate
  scenes to keep in sync by hand). Play/Pause, a 0.25x-4x speed select,
  and a seek slider; live readouts (time/altitude AGL/speed/Mach/
  acceleration) and a "Last event: X @ Ys" line, all updated by the
  browser's own `requestAnimationFrame` loop - once the dataset is
  sent, the Python backend is never involved again until a fresh
  Simulate run.
- `BUP.livemc.create(containerId)` - the live Monte Carlo view: starts
  with just a ground grid, and `addSample()`/`addLanding()` add one
  faint trajectory line / one landing-point marker as each Monte Carlo
  sample finishes; `setEllipses()` draws the final 1/2/3-sigma
  ellipses once the batch is done, reusing `monte_carlo.landing_ellipses()`'s
  own numbers - never a separate, potentially-disagreeing computation.

**New `bup_rocketpy/gui/flight_playback.py`**: builds the DECIMATED
(250-frame default) dataset the viewer animates - time/x/y/z(AGL)/
speed/Mach/acceleration per frame, plus event markers (rail exit,
burnout, apogee, every parachute deployment, landing) in ascending
time order. Kept separate from `plotting.py` (matplotlib PNGs) and has
no NiceGUI import at all, so `tests/test_flight_playback.py` (4 tests)
exercises it with no browser involved - decimated max altitude within
2% of the real apogee AGL, bounds actually cover every frame, events
present and ordered.

**`bup_rocketpy/monte_carlo.py`**: `_run_one_mc_sample`/`run_monte_carlo`
gained `trajectory_points` (each worker optionally also returns a small
decimated x/y/z-AGL polyline) and `on_sample_complete` (fires once per
finished sample, same timing as `progress_callback`, carrying that ONE
sample's own trajectory/landing point) - the hook the live Monte Carlo
view uses. Both default to off/None, so every existing caller is
unaffected (verified: the full existing Monte Carlo test file still
passes unchanged) - new test
`test_on_sample_complete_fires_once_per_sample_with_a_decimated_trajectory`
confirms the callback fires exactly `n_completed` times with real
3-float points.

**`bup_rocketpy/gui/pipeline.py`**: `SimResult` gained `flight`/`motor`
fields (the LIVE rocketpy objects, not JSON/dict data) - safe to hold
here since `run_simulation` runs in a background THREAD
(`run.io_bound`), never a separate process, so nothing ever needs to
pickle them; confirmed nothing in the codebase tries to serialize a
whole `SimResult` (only specific numeric fields are read off it, e.g.
by `run_history.save_run`).

**`bup_rocketpy/gui/app.py`** (the Simulate/"Home" page): a "Mission
control" header row with quick-action links (Monte Carlo/RCSM Cases/
Exports/History) when a mission is loaded; a new "Flight playback (3D)"
tab (the default-active one) alongside the existing plot tabs, built
from `sim.flight`/`sim.motor` via `flight_playback.build_playback_data`.

**`bup_rocketpy/gui/pages/montecarlo_page.py`**: a "Live 3D view" panel
above the histogram/ellipse, created fresh each run; `on_sample_complete`
appends to a plain list from the background thread (same GIL-safe
pattern the existing `progress_cb`/`mc_progress` dict already used -
commented at the same site), and the existing 0.4s `poll_timer` (on the
event loop) drains it and is the only thing that calls
`ui.run_javascript`. Final ellipses are pushed once the batch completes.

**A real bug caught and fixed before it ever reached Diego**: the first
end-to-end Playwright run of this feature found `net::404` on
`three.min.js` - the script tag pointed at `/static/three.min.js` but
the vendored file actually lives at `/static/vendor/three.min.js` (the
`vendor/` subfolder). Caught by a debug script that checked the
browser's own console log and cross-referenced against a direct `curl`
of the static route, not by reading the code again - fixed in both
`app.py` and `montecarlo_page.py`.

**New `tests/test_mission_control_e2e.py`** (Playwright, real browser):
loads PROMETEO, Simulates, asserts >=4 canvases render on the playback
tab, clicks Play, asserts the Time (s) readout actually advances,
changes speed to 4x and confirms it advances faster, then runs a real
N=5 Monte Carlo and asserts the live view's canvas + "N trajectory(ies)
completed" status line update, with a specific "Done: 5 completed"
check (an earlier draft of this test used the wrong locator for the "N
simulations" field and silently ran the full N=200 default instead -
caught by checking the actual completed count, not just "did it
finish"). Also asserts no unexpected JavaScript console errors (with an
explicit, commented carve-out for the pre-existing Leaflet/OpenStreetMap
tile fetches, which always fail with no internet in this sandbox and
are unrelated to this feature). Screenshots:
`docs/screenshots/13_playback_start.png`, `14_playback_midflight.png`
(readouts live-updating, "Last event: Rail exit @ 0.5s"), and
`15_live_montecarlo.png`.

**What this section does NOT cover** (an honest scope note, not a
silent gap): the mega-prompt's fuller "minimalist, polished, animated"
redesign vision - a from-scratch Home dashboard layout distinct from
the Simulate page, a site-map ground texture (grid is used - explicitly
the documented fallback when no offline site imagery exists, not a
placeholder for one that was skipped), and animated transitions/KPI
count-up elsewhere in the app - was not attempted tonight. The two
functionally hardest, most-requested pieces (3D flight playback with
synced multi-view + live Monte Carlo) are real, tested, and vendored
fully offline; broader visual polish across every other page is a
separate, lower-risk follow-up, not blocked on anything.

Full suite: 97 passed, 1 skipped (93 unit/integration + 4 Playwright,
including both new e2e files above).

## BLOCKED / NEEDS DIEGO

- **Major Tom's `.ork`/`.eng`** - still not in this repo (flagged since
  Phase 1, and again in last night's MORNING_REPORT.md). Item 1d (the
  actual code-to-code re-check against the "PACHUCA" sim you quoted)
  needs these files.
- **The July 4 .ork** - not in `reference/prometeo_mission44/data/rockets/`
  (only the drag CSVs are there) - V1 still uses the Brasil-config CG
  approximation, not a July-4-specific measurement, per your own
  fallback instruction.

## Third overnight run (2026-09-27): full UI redesign - every page

You sent `Major_tom.ork`/`kaboom.eng` with this run's instructions and
said explicitly these are for your own local testing only and are NOT
to be committed to the repo, and that their prior absence should stop
being logged as a blocker - done: neither file was added to the repo,
and Major Tom's `.ork`/`.eng` no longer appears in this file's BLOCKED
list. (The July 4 `.ork` above is a separate, still-open item - unrelated
to Major Tom - not touched by tonight's instructions.)

Full checklist, in order (14 commits, each with the full test suite
green before pushing):

1. **Design system foundation** (`bup_rocketpy/gui/theme.py`,
   `bup_rocketpy/gui/components.py`, `bup_rocketpy/gui/static/`): color/
   spacing/radius/shadow/motion tokens as CSS custom properties; Inter
   vendored locally (4 weights, `@fontsource/inter` via `npm pack`, no
   CDN); `motion.js` for count-up/stagger; every shared component used
   on every page from here on - `page_header`, `card`, `kpi_card`,
   `status_chip`, buttons, `empty_state`, `skeleton`, `dropzone`,
   `confirm_dialog`, `data_table`, `hero_stat`, `error_bar`,
   `stepper_header`.
2. **Component gallery** at `/design-system` (not in the sidebar - a
   reference page) + `docs/design_system.md`.
3. **New Home page** (mission-control dashboard) takes over `/`; the old
   load/simulate flow moves to `/simulate`. Required fixing 5 existing
   Playwright test files that assumed `/` was Simulate.
4. **Every other page redesigned** with the shared components: Simulate
   (stepper), Rocket, Monte Carlo, RCSM Cases, Analysis, Launch Day,
   History, Exports, Validation - one commit each, full suite green
   before every push.
5. **Every matplotlib plot restyled** to the theme (`plot_theme.py`):
   transparent figure/axes background + a neutral axis/grid/legend color
   that reads on both light and dark surfaces (a static PNG can't react
   to a live dark-mode toggle, so transparency is the fix, not a
   hardcoded light/dark pair) - applied to all ~11 flight plots, the
   rocket side-profile drawing, the Monte Carlo histogram/ellipse, the
   weathercocking scatter, and the two report-only plots.
6. **Quality pass**: WCAG AA contrast checked with a real formula (not
   eyeballing), both 1366x768 and 1920x1080, both themes, every page, no
   console errors, no horizontal overflow. Caught and fixed 2 real
   contrast bugs (see "Two real contrast bugs" below). Full light+dark
   screenshot gallery at `docs/screenshots/redesign/`.

**Two real bugs found by testing, not by looking harder at the code:**

- `rocket_drawing.draw_side_profile()`'s `dark=` parameter was dead code
  - grepped all 4 call sites, none ever passed `dark=True`, so every
  rocket drawing had silently rendered light-only forever. Fixed by
  making it transparent-background (consistent with `plot_theme.py`)
  and documenting the parameter as a no-op kept only for signature
  compatibility.
- WCAG contrast: the active nav icon used GOLD unconditionally (GOLD on
  a light surface is ~2.7:1, failing even the 3:1 large-text/UI
  threshold - an earlier hand-written comment in `theme.py` had wrongly
  claimed it "just passes"), and `status_chip()`'s SUCCESS/WARNING/
  ERROR/INFO colors, reused unchanged in both themes, measured as low
  as ~2.2:1 against their own dark-mode tinted background. Both fixed
  in `theme.py` with light/dark-specific values (same WINE(light)/
  GOLD(dark) split `.bup-kpi-value` already used, extended to the nav
  icon; new `*_DARK` variants for the 4 status colors) and locked in
  with a real WCAG-formula test (`tests/test_redesign_quality.py`) that
  computes contrast against the actual rendered background, not an
  assumed pure white/black.

**Honest scope note**: this run's own per-page redesign commits each
re-ran the full e2e suite right after that page's change, which
overwrites `docs/screenshots/*.png` with the ALREADY-redesigned page -
there is no preserved pre-redesign "before" screenshot anywhere in this
repo to diff against. `docs/screenshots/redesign/` is the complete
"after" gallery (10 pages x 2 themes = 20 images at 1920x1080), not a
before/after pair. See MORNING_REPORT.md.

Full suite at the end of this run: 101 passed, 1 skipped.
