# Changelog

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
