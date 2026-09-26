"""Phase 2 validation (CLAUDE.md Sec 6, Phase 2 + Sec 3.1's wording rule):
V1 (2026-07-04 profile) and V2 (LASC apogee) against REAL FLIGHT DATA.
This is the only place in the repo the word "validated" is earned.

Rewritten 2026-09-25 second review, item 3 ("ONE path" rule): the
previous version built its own Rocket()/Flight() by hand via
reference/prometeo_mission44/src/prometeo/rocket.py, a code path the
real app never runs - see test_code_to_code_vs_openrocket.py's module
docstring for why that made these numbers impossible to compare against
what the app itself produces. This version calls ONLY
bup_rocketpy.{ork_reader,motor_reader,translate} - the exact
load -> translate -> simulate functions bup_rocketpy/gui/pipeline.py
(and therefore the app) call - reading the real PROMETEO .ork + .eng,
with no hand-built rocket anywhere in this file. Per-flight mass/CG/site
numbers (config.py's own already-verified constants) are passed in as
explicit overrides to translate.ork_to_flight, the same mechanism the
Simulate page's "manual override" checkbox uses.

Tonight's constraint (per the overnight-run instructions): the cloud
container cannot reach weather APIs. Both cases use the launch-day
conditions already RECORDED in the project's own files (the .ork's stored
simulation, or config.py's CSV-sourced constants) - explicitly labeled
"OpenRocket-recorded conditions, pending real weather", not live weather.
Diego re-runs with Open-Meteo/GFS on his machine tomorrow.

Tolerance: +-5% per CLAUDE.md. A miss is reported with a cause breakdown,
NOT tuned away, and the result stays PROVISIONAL either way (single-flight
comparisons, not a statistically validated model).

2026-09-27 review item 5: bup_rocketpy.validation.compute_v2() was fixed
today to STOP duplicating this file's own hand-rolled _run_case() call -
it found a genuine data-consistency bug (a different, separately-sourced
with-motor CG and rocket-length between the two paths made V2's LIGHTER
10.370 kg config predict a LOWER apogee than the unconstrained default
run, physically backwards) and now reuses the exact same stored-sim-
derived mass/CG/inertia the default no-override Simulate path itself
uses, changing only the total mass. THIS file's own test_v2_lasc_apogee()
below still calls the OLD hand-rolled path on purpose, as a historical/
audit snapshot of the pre-fix numbers - it is intentionally NOT expected
to match bup_rocketpy.validation.compute_v2()'s own (now different,
now-passing) number any more. See PROGRESS.md Section 5 for the numbers
before/after.
"""
import dataclasses
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
sys.path.insert(0, REF_ROOT)  # still used to read historical per-flight mass/CG constants, NOT to build a rocket

import config as prom_config  # noqa: E402

from bup_rocketpy import translate  # noqa: E402
from bup_rocketpy.motor_reader import read_eng  # noqa: E402
from bup_rocketpy.ork_reader import read_ork  # noqa: E402

ORK_PATH = os.path.join(REF_ROOT, "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REF_ROOT, "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_on_drag.csv")

TOLERANCE_PCT = 5.0


def _run_case(launch_override, total_mass_kg, motor_mass_loaded_kg, motor_dry_mass_kg, cg_with_motor_m_from_nose, rail_length, inclination, heading):
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    motor = translate.build_motor(parsed_eng, ENG_PATH, dry_mass_override_kg=motor_dry_mass_kg)

    dry_mass_kg = total_mass_kg - motor_mass_loaded_kg
    mass_est, i_axial, i_transverse = translate.derive_dry_mass_and_inertia_from_with_motor(
        motor, total_mass_kg, motor_mass_loaded_kg, dry_mass_kg, cg_with_motor_m_from_nose,
        rocket_length_m=prom_config.LENGTH,
        i_total_axial_kgm2=prom_config.INERTIA_ROT_T0_WITH_MOTOR, i_total_transverse_kgm2=prom_config.INERTIA_LONG_T0_WITH_MOTOR,
    )

    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        rail_length_override=rail_length, inclination_override=inclination, heading_override=heading,
        terminate_on_apogee=True, include_recovery=False,
        dry_mass_override_kg=mass_est.mass_kg, dry_cg_override_m=mass_est.cg_m,
        launch_override=launch_override, i_axial_override=i_axial, i_transverse_override=i_transverse,
        motor_dry_mass_override_kg=motor_dry_mass_kg,
    )
    apogee_agl = flight.apogee - flight.env.elevation
    margin0 = flight.stability_margin(0)
    return apogee_agl, margin0


def test_v1_2026_07_04_profile_apogee():
    """V1: 2026-07-04, Pachuca (as-flown). Target 1019.9 m AGL (telemetry,
    packet 118 of 72, ~2.5 Hz - see PROGRESS.md for the full telemetry
    inspection). Mass/motor-mass from verified_constants.json's
    julio4_asflown_sim block (10.96 kg / 4.882948 kg loaded) - these ARE
    the as-flown numbers for this specific date, unlike V2 below. Dry CG
    is APPROXIMATED as the Brasil-config's derived with-motor CG (no
    July4-specific system CG is stored anywhere in the project's files) -
    same airframe, but real mass reductions happened between designs per
    CLAUDE.md Sec 3.1, so this is a genuine, documented source of error,
    not hidden."""
    TARGET_APOGEE_AGL = 1019.9

    parsed = read_ork(ORK_PATH)
    launch_override = dataclasses.replace(
        parsed.launch,
        altitude_m=2380.0, latitude=19.967, longitude=-98.856,
        wind_average_ms=3.247, wind_direction_deg=90.0,
    )
    apogee_agl, margin0 = _run_case(
        launch_override=launch_override,
        total_mass_kg=10.96, motor_mass_loaded_kg=4.882948, motor_dry_mass_kg=2.866213,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=3.0, inclination=89.0, heading=270.0,
    )
    error_pct = (apogee_agl - TARGET_APOGEE_AGL) / TARGET_APOGEE_AGL * 100
    print(f"\nV1 (2026-07-04): predicted apogee AGL={apogee_agl:.1f} m, flight telemetry={TARGET_APOGEE_AGL} m, error={error_pct:+.2f}%")
    print(f"  static margin@0={margin0:.2f} cal, using Brasil-derived dry CG (APPROXIMATION, see docstring)")
    print("  Conditions: OpenRocket-recorded (prometeo4dejulio.csv @ t=0 wind/temp/pressure), NOT live weather.")
    print("  Unified translate.* path (2026-09-25 review item 3) - see test_code_to_code_vs_openrocket.py for the code-to-code check this pairs with.")
    if abs(error_pct) > TOLERANCE_PCT:
        print(f"  OUTSIDE +-{TOLERANCE_PCT}% - breakdown: dry CG is a Brasil-config approximation (see docstring),")
        print("  not a July4-specific measurement; real drag curve is from the Brasil config too, not this flight's own.")
        print("  NOT tuned to force a pass. Result stays PROVISIONAL.")


def test_v2_lasc_apogee():
    """V2: LASC (Iacanga), the official competition flight. Target 1137 m
    (SRAD telemetry - CLAUDE.md Sec 3.1/3.2; the "1138 m" figure is the
    officials' OWN on-site prediction, not something to reproduce and
    relabel as ours - see the wording rule). Mass = 10.370 kg (measured,
    per tonight's explicit instruction). Site/rail: the .ork's OWN stored
    launch conditions apply as-is (490-495 m, -21.9/-48.96, 4.0 m rail,
    10 deg from vertical = 80 deg inclination) - no override needed,
    unlike V1, since this IS that stored configuration."""
    TARGET_APOGEE_AGL = 1137.0

    apogee_agl, margin0 = _run_case(
        launch_override=None,
        total_mass_kg=10.370, motor_mass_loaded_kg=prom_config.MOTOR_MASS_LOADED, motor_dry_mass_kg=prom_config.MOTOR_DRY_MASS,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=4.0, inclination=80.0, heading=90.0,
    )
    error_pct = (apogee_agl - TARGET_APOGEE_AGL) / TARGET_APOGEE_AGL * 100
    print(f"\nV2 (LASC): predicted apogee AGL={apogee_agl:.1f} m, flight telemetry={TARGET_APOGEE_AGL} m, error={error_pct:+.2f}%")
    print(f"  static margin@0={margin0:.2f} cal")
    print("  Conditions: OpenRocket-recorded (.ork 'brasil 2026' stored sim @ t=0), NOT live weather - Diego re-runs with real Iacanga weather tomorrow.")
    print("  Compare: LASC officials' own on-site RocketPy prediction was 1138 m (CRS 10.2.1) - we did NOT reproduce their exact inputs, this is an independent replication (see CLAUDE.md Sec 3.1 wording rule).")
    print("  Unified translate.* path (2026-09-25 review item 3).")
    if abs(error_pct) > TOLERANCE_PCT:
        print(f"  OUTSIDE +-{TOLERANCE_PCT}% - breakdown: motor mass kept at the Brasil-config value (4.7378 kg loaded),")
        print("  since no LASC-specific motor-mass measurement is on file separate from the 10.370 kg total; wind/temp/pressure")
        print("  are the .ork's OWN recorded values, not the actual Iacanga flight-day weather (still pending from Diego).")
        print("  NOT tuned to force a pass. Result stays PROVISIONAL.")


if __name__ == "__main__":
    test_v1_2026_07_04_profile_apogee()
    test_v2_lasc_apogee()
