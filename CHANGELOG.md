# Changelog

## 2026-09-26 overnight run, item 1 - code-to-code check vs OpenRocket

Added `tests/test_code_to_code_vs_openrocket.py`: reproduces OpenRocket's
own two CSV-exported sims with its own exact inputs (no weather
uncertainty). Confirmed **the +10% gap is real, not weather**: Brasil
+10.17%, July4 +9.43%.

July4's gap is now explained (not a bug): OpenRocket used a DIFFERENT
motor for that CSV (1732 Ns/3.12s burn) than the one `.eng` file we have
(1871 Ns/3.57s, Brasil's) - already flagged in `config.py`'s own comments.

Brasil's +10.17% is real and NOT explained by a data mismatch - ruled out
by direct measurement: reference area (exact), Cd curve values at
Mach 0.3 boost/coast (<0.1% off both), motor total impulse/burn time
(exact), atmosphere density/gravity (exact via ideal-gas check),
`terminate_on_apogee` (no effect), drag-curve low-Mach extrapolation (flat,
not degenerate). Root cause NOT isolated tonight - see PROGRESS.md "Item 1
findings" for the full diagnostic table and the leads for next time (rail-
exit speed/timing mismatch, the known 6.6% I_11 inertia error not yet
tested empirically, whether stella_flight.translate's own pipeline shows
the same gap). Not tuned to hide it.

## 2026-09-26 overnight run, item 0 - CRITICAL upload bug fixed

`app.py`'s upload handlers used NiceGUI's old `e.content`/`e.name` API.
NiceGUI 3.17.1 (the pinned version) uses `e.file` (async `FileUpload`,
`.save()`/`.read()`/`.text()`) - the handlers were also plain `def`, not
`async def`, silently swallowing the `AttributeError` and leaving the
upload widget showing "100%" while `state[...]` was never actually set.
This is exactly the "checkmark and 100%, then Load Files says nothing was
uploaded" bug Diego reported. Fixed both the API call and made the
handlers `async`.

Added `tests/test_phase0_e2e.py`, a **permanent** Playwright end-to-end
test: launches the real app as a subprocess, drives real headless
Chromium, uploads real files through the actual file inputs, clicks
through to results, asserts the apogee renders. This is the test that
would have caught the bug Diego found - a pipeline-only test cannot,
since the bug was entirely in the browser-facing upload wiring. Runs
after every UI change from now on; nothing UI-related is "done" without
it passing.

## Phase 5 (partial) - Ballistic + Nominal cases, self-contained .py export

- `translate.build_rocket`/`ork_to_flight` gained `include_recovery=`
  (`False` builds CRS 10.1.11's Ballistic case - no parachutes at all,
  regardless of what the `.ork` has configured).
- `stella_flight/case_export.py`: generates a fully self-contained
  `Mission[ID]_[Case]_RocketPy_v[N].py` per CRS 10.1.6 - every geometry/
  mass/motor/launch value baked in as a literal, **no import of
  `stella_flight`** (CRS 10.1.5: must run with just `pip install
  rocketpy`). The `.eng` and the two drag-curve CSVs stay as sibling files
  referenced by relative path (they're required deliverables in their own
  right per CRS 10.1.9, not something to inline).
- `tests/test_phase5_case_export.py`: builds a genuinely clean venv (not
  reusing the dev one), installs `rocketpy==1.13.0` fresh, runs both
  `Mission44_Ballistic_RocketPy_v1.py` and `Mission44_Nominal_RocketPy_v1.py`
  as real subprocesses, and diffs their printed apogee against the app's
  own in-process result for the same inputs. **Both matched to 0.0027%.**
  This is the actual CLAUDE.md Sec 5 requirement ("Add an automated test
  that runs each exported .py in a clean environment and compares its
  apogee to the app's") - not just confirming the file parses.
- Not done yet: Drogue-only/Main-at-apogee cases (CRS 10.1.10-13, mandatory
  only for >1500m vehicles - PROMETEO is single-deploy, so these matter
  more once Major Tom's 3km `.ork` is in), the PDF/DOCX report, and the
  LASC `.zip` packaging step. See PROGRESS.md priorities.

## Phase 3 - NiceGUI app, start.bat, headless smoke test

- `stella_flight/gui/pipeline.py`: load/simulate logic with **no NiceGUI
  import** (CLAUDE.md Sec 1's core/UI split), so it's directly unit-
  testable without a browser or display server.
- `stella_flight/gui/app.py`: the UI - upload `.ork`+`.eng`(+optional Cd
  CSVs) -> imported-data table -> manual dry-mass/CG override fields ->
  Simulate -> big numbers (apogee, Vmax, max Mach, max accel, rail exit,
  flight time, min static margin, stable Y/N) -> plots -> CSV download.
- Added `ork_reader.extract_drag_curves_from_stored_sim()`: pulls Cd-vs-
  Mach directly from a `.ork`'s own stored `<databranch>` (CLAUDE.md Sec
  4.2's TOP-preference source) - no separate CSV upload needed for the
  common case. Cross-checked against PROMETEO's independently-exported
  CSV-derived curve: subsonic coast Cd range 0.432-0.463 from the `.ork`
  itself vs. 0.431-0.463 from the committed `power_off_drag.csv` - two
  independent sources agree.
- `start.bat`: creates `.venv`, installs pinned `requirements.txt`
  (added `nicegui==3.17.1`, `openpyxl`, `simplekml`), opens the browser.
- `tests/test_phase3_headless.py`, 5/5 pass: drag-curve auto-detection,
  user-CSV override respected, full simulate-with-override (stable,
  plots+CSV written), simulate-without-override honestly surfaces the
  Phase-1-documented instability rather than hiding it, and `app.py`
  imports cleanly (no server started - no display server in this
  container to test an actual browser session, flagged in PROGRESS.md
  for Diego to confirm on his machine).
- Found and fixed while building this: `app.add_static_files()` needs its
  target directory to already exist at import time, not just by the time
  a request arrives - `app.py` now creates `outputs/gui_run/` at module
  load.

## Phase 2 - V1/V2 validation against real flight data

- `tests/test_phase2_validation.py`: V1 (2026-07-04, target 1019.9 m) and
  V2 (LASC, target 1137 m), both against REAL telemetry - see PROGRESS.md
  "Phase 2 findings" for the full breakdown. Neither is within +-5% (V1:
  +10.22%, V2: +5.27%, both PROVISIONAL, neither tuned to force a pass).
  Reuses `reference/prometeo_mission44`'s already-validated rocket model
  directly (per-flight masses substituted via config monkeypatching) rather
  than `stella_flight.translate` - see PROGRESS.md for why.
- Confirmed `power_off_drag.csv`/`power_on_drag.csv` are byte-for-byte
  reproducible from `Prometeo_Launchsite_BRASIL.csv` via
  `scripts/extract_drag_curves.py` - not stale.
- Inspected `telemetry_2026_07_04.xlsx`: 72 packets, ~2.5 Hz, apogee at
  packet 118 (1019.9 m, matches the known target exactly) - see
  PROGRESS.md for the full column/gap inventory. Altitude-residual RMS
  against this table (V1's profile check, not just its apogee) is not yet
  built.

## Phase 1 corrections (autonomous overnight run, real PROMETEO .ork now in repo)

Diego reviewed last night's report and corrected 4 things; all addressed:

1. **The old 0.000% mass/CG check was circular** (synthetic data built from
   the same numbers it was checked against) - now called a smoke test, not
   an acceptance test. The REAL PROMETEO `.ork` (Diego uploaded it -
   `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork`) is now the
   acceptance-test input. `tests/test_phase1_acceptance.py`, 5/5 pass:
   - CP position: 0.48% error vs. OpenRocket's own stored sim (pure
     Barrowman geometry check - the reader's geometry parsing is correct).
   - Diameter: 0.36% error.
   - Dry mass (geometric fallback): **19.2% error, honestly reported, not
     tuned away.** Root cause found and documented: the .ork's own
     `<overridemass>` only covers the Fuselage shell (1.475 kg), not the
     whole rocket - several real bulkheads have `<outerradius>auto</>`
     that never resolves without inheriting the parent tube's inner
     radius, so this reader correctly declines to invent a number for
     them (Rule 2) rather than guess. **Actionable for Diego:** set a
     whole-rocket `overridemass`+`overridecg` in OpenRocket from the LRR
     scale measurement - CRS 10.1.8 wants exact masses anyway, and it's
     the one input this pipeline can't substitute for.
   - Full flight with corrected total mass (but NOT a corrected CG, since
     no overridecg exists to correct it with) comes out marginally
     unstable (-0.01 to -0.11 cal) - not hidden, explained: the missing
     mass is concentrated aft (bulkheads near the motor mount, 1.8-2.3 m
     from nose), so fixing only the total without fixing the CG leaves it
     biased too far forward relative to CP.
2. **Real drag curves now required, Cd=0.5 placeholder removed as a
   default.** `translate.build_rocket`/`ork_to_flight` raise if
   `power_off_drag`/`power_on_drag` aren't passed - no more silent
   fallback. `DRAG_CURVE_PLACEHOLDER_CD` still exists but must be passed
   explicitly, and the caller (not this module) is responsible for
   flagging that choice to the user.
3. **"Validated" now means flight-data-compared, everywhere.** Added
   `ork_reader.SimulationReference`/`parse_stored_simulation_references()`
   which extracts OpenRocket's OWN stored-simulation numbers (mass/CG/CP/
   inertia at t=0, apogee, rail-exit velocity) directly from a `.ork` -
   explicitly documented and printed as "OpenRocket reference", never
   "validated". Only Phase 2's V1/V2 (compared against real telemetry)
   earn that word.
4. **Coordinate convention: `tail_to_nose` kept (matches the validated
   reference code), but now selectable and proven equivalent.**
   `translate._coordinate_transform()` is the one conversion point;
   `build_rocket()` takes `coordinate_system_orientation=` (defaults to
   `"tail_to_nose"`). `tests/test_coordinate_convention.py` builds the same
   real PROMETEO geometry both ways and confirms identical CP (1.211185 m,
   both conventions, to 1e-9 m) and static margin (1.014458 cal, both, to
   1e-9 cal) - it's a style choice, not a source of error.

**Other real bugs found and fixed while building the acceptance test**
(these would not have surfaced without a real `.ork` file):
- `<overridecg>`/`<overridesubcomponentscg>` weren't parsed at all before
  tonight - added to `ork_reader.MassOverride`.
- A **per-component** override (e.g. just one bodytube's shell mass, with
  `override_subcomponents_mass=False` - exactly what PROMETEO's real `.ork`
  does for its Fuselage) was being ignored entirely; only a whole-rocket
  override was ever applied. `translate._geometric_components()` now
  substitutes a per-component override where one exists.
- OpenRocket rail-button **pairs are ONE `<railbutton>` element** with
  `instancecount`/`instanceseparation`, not two separate elements - the
  original parser only ever recorded one button position twice.
- **Nose cone shape names don't map directly**: OpenRocket's `<shape>` is
  vocabulary (`ellipsoid`, `ogive`, `haack`...) that isn't the same string
  rocketpy's `NoseCone(kind=...)` wants (`elliptical`, `tangent`,
  `vonkarman`...) - `ellipsoid` would have raised `ValueError` on literally
  the first real nose cone tested. Added `translate.NOSE_SHAPE_MAP`.
- Point masses/bulkheads nested inside an `<innertube>` (a real, common
  payload/recovery-bay mounting pattern) were resolved against the OUTER
  tube's position frame instead of the inner tube's own - fixed by making
  `_parse_subcomponents_of` recurse into `innertube`/`centeringring`/
  `launchlug`/`tubefin`, not just log them as ignored. (PROMETEO's specific
  file didn't happen to nest anything inside its one `<innertube>`, so this
  didn't change PROMETEO's own numbers, but it's a correctness fix for any
  `.ork` that does - including, plausibly, Major Tom's.)
- `<bulkhead>` was previously dropped entirely (logged IGNORED, no mass).
  It's now approximated as a solid disk (material density x volume) when
  the geometry resolves, and honestly logged as unresolvable when it
  doesn't (this is most of where the 19.2% mass gap above comes from).

## Phase 1 - .ork/.eng readers and translation into rocketpy objects

- Added `stella_flight/ork_reader.py`: pure-Python `.ork` reader (zip or bare
  XML), schema verified against 3 real files from
  github.com/openrocket/openrocket (no PROMETEO/Major Tom `.ork` exists in
  this repo yet - CLAUDE.md Sec 4.1 explicitly sanctions testing against
  OpenRocket's own examples until Diego's files arrive). Extracts nose cone,
  body tubes, transitions, fins, point masses, parachutes, rail buttons,
  mass/CG overrides, and launch conditions from the first stored simulation.
  Every parsed value is logged as IMPORTED / APPROXIMATED / IGNORED - see
  `ParsedRocket.print_import_table()`.
- Added `stella_flight/motor_reader.py`: RASP `.eng` reader (validated against
  PROMETEO's real `Icarus_I_K519.eng`) and a fallback OpenRocket-export
  thrust-CSV reader.
- Added `stella_flight/translate.py`: builds rocketpy `Environment`/
  `SolidMotor`/`Rocket`/`Flight` from parsed `.ork` + `.eng` data. Mass/CG
  prefer a team-measured `<overridemass>`/`<overridecg>` when present;
  otherwise both are estimated geometrically from component material
  densities (thin-shell approximation), all labelled per CLAUDE.md Rule 2.
- **Finding, not yet resolved:** CLAUDE.md Sec 4.3 states RocketPy uses
  `coordinate_system_orientation="nose_to_tail"`, but the validated PROMETEO
  reference (`reference/prometeo_mission44/src/prometeo/rocket.py`) uses
  `"tail_to_nose"` and its own mass/inertia acceptance check passed with
  that convention. `translate.py` follows the validated code, not the
  CLAUDE.md prose - flagged for Diego to confirm which is correct.
- Validated `estimate_dry_mass_and_cg`/`estimate_dry_inertia`/`ork_to_flight`
  against PROMETEO's own already-validated dry mass/CG (from
  `reference/prometeo_mission44/src/prometeo/rocket.py`'s
  `_solve_dry_inertia()`, reconstructed as a synthetic `ParsedRocket` from
  `config.py`'s real numbers, not a real `.ork`): mass and CG plumbing match
  to 0.000%. A full `Flight()` with this geometry + the real `.eng` produced
  a stable rocket (2.38 cal static margin, vs. the validated 1.50-2.79 cal
  range), rail exit 15.9 m/s (validated 16.8 m/s), apogee 1165 m AGL
  (validated Brasil-sim 1082 m) - the gap is expected: this run used a
  **placeholder constant Cd=0.5**, not PROMETEO's real drag curve, and a
  **geometrically-estimated inertia** (I_transverse came out 0.63 vs the
  validated 0.05 kg m2 - a large, informative gap; see Sec 4.3's own
  "Inertias" pitfall). Every such result must show PROVISIONAL until the
  real drag curve is wired in (Phase 2) and a real `.ork` is available.
- **No PROMETEO/Major Tom `.ork` in the repo yet** (Sec 4.1) - Phase 1's
  formal acceptance test (mass/CG/CP within 1% of what OpenRocket itself
  shows) is blocked on that file. Still asking Diego for it.
- `parachute.cd="auto"` (OpenRocket's own internally-computed Cd) cannot be
  read from the file at all - `translate.py` skips adding any parachute
  whose Cd wasn't resolvable and logs why, rather than guessing a number.
- Tried a real-`.ork`-geometry + PROMETEO-motor combination as a second
  end-to-end smoke test (OpenRocket's own "Dual parachute deployment.ork"
  example, an unrelated hobby-rocket airframe, flown with the K-class
  Icarus I motor). It came out aerodynamically unstable (-0.93 cal at
  ignition) and the flight would not terminate in reasonable time - expected
  physics for mismatched geometry/motor, not a bug, but worth remembering:
  this reader's own parse is fine on real files, a *flyable* combination
  still needs geometry and motor that actually belong together.

## Phase 0 - repo realignment

- Restructured `common/` (an earlier, since-abandoned "design tool" plan -
  see CLAUDE.md Sec 1, "no design search") into `stella_flight/`:
  - `common/rules.py` -> `stella_flight/rcsm.py` (unchanged)
  - `common/environment.py` -> `stella_flight/environment.py` (unchanged;
    Phase 2 will add Open-Meteo/GFS/sounding sources and caching)
  - `common/design_search.py` deleted (contradicted CLAUDE.md Sec 1)
  - Added `stella_flight/gui/` (empty, for Phase 3)
- Updated `README.md` to describe the app (not the old parametric-design
  scope).
