"""Code-to-code check vs OpenRocket (2026-09-26 overnight review, item 1;
rewritten 2026-09-25 second review, item 3 - "ONE path" rule).

The first version of this test built its own Rocket()/Flight() by hand
via reference/prometeo_mission44/src/prometeo/rocket.py, completely
bypassing bup_rocketpy.translate - the module the actual app uses. That
is why it reported +10.17% while the real app (going through
translate.ork_to_flight) reported -0.7% on the SAME Brasil-config input:
two different code paths, not one bug. This version calls ONLY
bup_rocketpy.{ork_reader,motor_reader,translate} - the exact
load -> translate -> simulate functions bup_rocketpy/gui/pipeline.py
(and therefore the app) calls - reading the real PROMETEO .ork + .eng,
with no hand-built rocket anywhere in this file.

Reproduces OpenRocket's own two CSV-exported simulations with EXACTLY
the inputs OpenRocket itself used (mass, CG->dry-CG derivation, thrust,
conditions, rail - read straight from the CSV/the .ork's own stored
sim), and compares against OpenRocket's OWN apogee for that exact input
set - no weather uncertainty to absorb, unlike V1/V2 which compare
against real flight data.

Target: within 2% of OpenRocket (tighter than V1/V2's 5%).
"""
import dataclasses
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
sys.path.insert(0, REF_ROOT)

import config as prom_config  # noqa: E402 - still used to read historical per-flight mass/CG numbers (see module docstring), NOT to build a rocket
from src.prometeo.io_utils import load_openrocket_csv  # noqa: E402

from bup_rocketpy import translate  # noqa: E402
from bup_rocketpy.motor_reader import read_eng  # noqa: E402
from bup_rocketpy.ork_reader import read_ork  # noqa: E402

ORK_PATH = os.path.join(REF_ROOT, "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REF_ROOT, "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_on_drag.csv")
TOLERANCE_PCT = 2.0


def _col(df, prefix):
    return next(c for c in df.columns if c.startswith(prefix))


def openrocket_reference(csv_path):
    """Pulls OpenRocket's own burnout state, apogee, and Cd-near-Mach-0.3
    (both boost and coast) directly out of its CSV export - no
    interpretation, straight columns."""
    df, events = load_openrocket_csv(csv_path)
    t_c, alt_c, v_c = "Time (s)", "Altitude (m)", "Total velocity (m/s)"
    mach_c, cd_c = _col(df, "Mach number"), _col(df, "Axial drag coefficient")

    burnout_idx = (df[t_c] - events["BURNOUT"]).abs().idxmin()
    burnout = df.loc[burnout_idx]
    apogee_idx = df[alt_c].idxmax()
    apogee_row = df.loc[apogee_idx]

    def cd_near_mach(lo_t, hi_t, target_mach=0.3):
        seg = df[(df[t_c] > lo_t) & (df[t_c] < hi_t)].dropna(subset=[mach_c, cd_c])
        if seg.empty:
            return None, None
        idx = (seg[mach_c] - target_mach).abs().idxmin()
        row = seg.loc[idx]
        return row[mach_c], row[cd_c]

    boost_mach, boost_cd = cd_near_mach(events["LIFTOFF"], events["BURNOUT"])
    coast_mach, coast_cd = cd_near_mach(events["BURNOUT"], events["APOGEE"])

    return {
        "burnout_t": burnout[t_c], "burnout_alt": burnout[alt_c], "burnout_v": burnout[v_c], "burnout_mach": burnout[mach_c],
        "apogee_alt": apogee_row[alt_c], "apogee_t": apogee_row[t_c],
        "cd_boost_near_mach03": (boost_mach, boost_cd), "cd_coast_near_mach03": (coast_mach, coast_cd),
        "reference_area_cm2": df[_col(df, "Reference area")].iloc[0],
        "reference_length_cm": df[_col(df, "Reference length")].iloc[0],
    }


def ours(launch_override, total_mass_kg, motor_mass_loaded_kg, motor_dry_mass_kg, cg_with_motor_m_from_nose, i_total_long_kgm2, i_total_rot_kgm2, rail_length, inclination, heading):
    """Builds and flies the rocket through bup_rocketpy.translate ONLY -
    ork_reader.read_ork + motor_reader.read_eng + translate.build_motor/
    derive_dry_mass_and_inertia_from_with_motor/ork_to_flight - the exact
    same functions bup_rocketpy/gui/pipeline.py calls for a real
    Simulate click in the app. The per-flight mass/CG/site numbers are
    legitimate historical validation inputs (same idea as V1/V2's
    dry_mass_override_kg/dry_cg_override_m), not a parallel rocket-
    construction path."""
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    motor = translate.build_motor(parsed_eng, ENG_PATH, dry_mass_override_kg=motor_dry_mass_kg)

    dry_mass_kg = total_mass_kg - motor_mass_loaded_kg
    mass_est, i_axial, i_transverse = translate.derive_dry_mass_and_inertia_from_with_motor(
        motor, total_mass_kg, motor_mass_loaded_kg, dry_mass_kg, cg_with_motor_m_from_nose,
        rocket_length_m=prom_config.LENGTH,
        i_total_axial_kgm2=i_total_rot_kgm2, i_total_transverse_kgm2=i_total_long_kgm2,
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
    env = flight.env

    burnout_state = None
    for t in flight.time:
        if t >= motor.burn_time[1]:
            burnout_state = t
            break
    burnout_alt = flight.z(burnout_state) - env.elevation if burnout_state is not None else None
    burnout_v = flight.speed(burnout_state) if burnout_state is not None else None

    return {
        "apogee_alt": flight.apogee - env.elevation,
        "burnout_alt": burnout_alt, "burnout_v": burnout_v,
        "total_impulse": motor.total_impulse,
        "mass_t0": flight.rocket.total_mass(0),
        "reference_area_m2": 3.14159265 * flight.rocket.radius**2,
    }


def _report(name, ork_ref, our_result, csv_path):
    err_pct = (our_result["apogee_alt"] - ork_ref["apogee_alt"]) / ork_ref["apogee_alt"] * 100
    print(f"\n=== {name} vs OpenRocket ({os.path.basename(csv_path)}) - unified translate.* path ===")
    print(f"{'':25}{'OpenRocket':>15}{'Ours':>15}")
    print(f"{'Apogee AGL (m)':25}{ork_ref['apogee_alt']:>15.2f}{our_result['apogee_alt']:>15.2f}")
    print(f"{'Burnout altitude (m)':25}{ork_ref['burnout_alt']:>15.2f}{our_result['burnout_alt'] or float('nan'):>15.2f}")
    print(f"{'Burnout velocity (m/s)':25}{ork_ref['burnout_v']:>15.2f}{our_result['burnout_v'] or float('nan'):>15.2f}")
    print(f"{'Reference area (m2)':25}{ork_ref['reference_area_cm2']/1e4:>15.5f}{our_result['reference_area_m2']:>15.5f}")
    print(f"{'Total impulse (Ns)':25}{'n/a':>15}{our_result['total_impulse']:>15.1f}")
    print(f"{'Mass t=0 (kg)':25}{'see t0 config':>15}{our_result['mass_t0']:>15.4f}")
    cd_b_mach, cd_b = ork_ref["cd_boost_near_mach03"]
    cd_c_mach, cd_c = ork_ref["cd_coast_near_mach03"]
    print(f"OpenRocket Cd near Mach 0.3: boost={cd_b:.4f}@M{cd_b_mach:.3f}, coast={cd_c:.4f}@M{cd_c_mach:.3f}" if cd_b else "OpenRocket Cd near Mach 0.3: n/a")
    print(f"APOGEE ERROR: {err_pct:+.2f}% (target: within +-{TOLERANCE_PCT}%)")
    return err_pct


def test_brasil_config_vs_openrocket():
    """Brasil/LASC-design config: the .ork's OWN stored launch conditions
    (site, rail, wind) apply as-is - this exact CSV IS that stored sim's
    export, so no launch_override is needed at all, unlike July4 below."""
    csv_path = os.path.join(REF_ROOT, "data", "openrocket_exports", "Prometeo_Launchsite_BRASIL.csv")
    ork_ref = openrocket_reference(csv_path)
    our_result = ours(
        launch_override=None,
        total_mass_kg=prom_config.LAUNCH_MASS, motor_mass_loaded_kg=prom_config.MOTOR_MASS_LOADED,
        motor_dry_mass_kg=prom_config.MOTOR_DRY_MASS, cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        i_total_long_kgm2=prom_config.INERTIA_LONG_T0_WITH_MOTOR, i_total_rot_kgm2=prom_config.INERTIA_ROT_T0_WITH_MOTOR,
        rail_length=prom_config.RAIL_LENGTH, inclination=prom_config.RAIL_INCLINATION, heading=prom_config.RAIL_HEADING,
    )
    err_pct = _report("Brasil/LASC-design", ork_ref, our_result, csv_path)
    if abs(err_pct) > TOLERANCE_PCT:
        print(f"OUTSIDE +-{TOLERANCE_PCT}% - see PROGRESS.md Item 3 for the investigation, not tuned away.")


def test_julio4_asflown_vs_openrocket():
    """July4 as-flown config: different site (Pachuca, 2380m) - needs a
    launch_override built from the SAME LaunchConditions the .ork itself
    would produce, just with July4's own site/wind/rail substituted in
    (dataclasses.replace, not a hand-built Environment)."""
    parsed = read_ork(ORK_PATH)
    launch_override = dataclasses.replace(
        parsed.launch,
        altitude_m=2380.0, latitude=19.967, longitude=-98.856,
        wind_average_ms=3.247, wind_direction_deg=90.0,
    )
    csv_path = os.path.join(REF_ROOT, "data", "openrocket_exports", "prometeo4dejulio.csv")
    ork_ref = openrocket_reference(csv_path)
    our_result = ours(
        launch_override=launch_override,
        total_mass_kg=10.96, motor_mass_loaded_kg=4.882948, motor_dry_mass_kg=2.866213,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,  # APPROXIMATION: no July4-specific with-motor CG on file, see docstring
        i_total_long_kgm2=prom_config.INERTIA_LONG_T0_WITH_MOTOR, i_total_rot_kgm2=prom_config.INERTIA_ROT_T0_WITH_MOTOR,
        rail_length=3.0, inclination=89.0, heading=270.0,
    )
    err_pct = _report("July4 as-flown", ork_ref, our_result, csv_path)
    if abs(err_pct) > TOLERANCE_PCT:
        print(f"OUTSIDE +-{TOLERANCE_PCT}% - see PROGRESS.md Item 3 for the investigation, not tuned away.")


if __name__ == "__main__":
    test_brasil_config_vs_openrocket()
    test_julio4_asflown_vs_openrocket()
