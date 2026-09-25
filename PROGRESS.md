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

- **`.ork` needs a whole-rocket `overridemass`+`overridecg`** (only the
  Fuselage shell is overridden right now) - this is the one input
  `bup_rocketpy`'s generic reader+translate pipeline cannot substitute
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
- **No logo files** at `bup_rocketpy/gui/assets/logo_gold.png` or
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
