"""Code-to-code check vs OpenRocket (2026-09-26 overnight review, item 1).

RocketPy came out ~+10% above OpenRocket in BOTH the July4 and LASC-config
cases (V1/V2 in test_phase2_validation.py), using the SAME Cd curves. A
consistent offset with identical inputs points at a translation bug, not
weather/approximation noise - V1/V2 compare against real FLIGHT data
(with its own weather uncertainty baked in); THIS test instead reproduces
OpenRocket's own two CSV-exported simulations with EXACTLY the inputs
OpenRocket itself used (same mass, CG, thrust, conditions, rail - read
straight from the CSV, not approximated), and compares against
OpenRocket's OWN apogee for that exact input set. If this test also shows
~10%, the bug is in translate/rocket/motor construction. If it's small,
the earlier +10% in V1/V2 was mostly OpenRocket-vs-reality weather/model
uncertainty, not a bug here.

Target: within 2% of OpenRocket (tighter than V1/V2's 5%, since there's
no weather uncertainty to absorb here - both sides use the identical
launch-day numbers OpenRocket itself recorded).
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
sys.path.insert(0, REF_ROOT)

import config as prom_config  # noqa: E402
from src.prometeo.environment import build_environment  # noqa: E402
from src.prometeo.io_utils import load_openrocket_csv  # noqa: E402
from src.prometeo.motor import build_motor  # noqa: E402
from src.prometeo.rocket import build_rocket  # noqa: E402
from rocketpy import Flight  # noqa: E402

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


def ours(site, overrides, rail_length, inclination, heading):
    saved = {k: getattr(prom_config, k) for k in list(overrides) + ["DRY_MASS_NO_MOTOR", "PROPELLANT_MASS"]}
    try:
        for k, v in overrides.items():
            setattr(prom_config, k, v)
        prom_config.DRY_MASS_NO_MOTOR = prom_config.LAUNCH_MASS - prom_config.MOTOR_MASS_LOADED
        prom_config.PROPELLANT_MASS = prom_config.MOTOR_MASS_LOADED - prom_config.MOTOR_DRY_MASS

        env = build_environment(site=site, atmos="custom")
        rocket, derived = build_rocket()
        flight = Flight(rocket=rocket, environment=env, rail_length=rail_length,
                         inclination=inclination, heading=heading, terminate_on_apogee=True)

        burnout_state = None
        for t in flight.time:
            if t >= prom_config.BURN_TIME:
                burnout_state = t
                break
        burnout_alt = flight.z(burnout_state) - env.elevation if burnout_state is not None else None
        burnout_v = flight.speed(burnout_state) if burnout_state is not None else None

        return {
            "apogee_alt": flight.apogee - env.elevation,
            "burnout_alt": burnout_alt, "burnout_v": burnout_v,
            "total_impulse": rocket.motor.total_impulse,
            "mass_t0": rocket.total_mass(0),
            "reference_area_m2": 3.14159265 * rocket.radius**2,
        }
    finally:
        for k, v in saved.items():
            setattr(prom_config, k, v)


def _report(name, ork_ref, our_result, csv_path):
    err_pct = (our_result["apogee_alt"] - ork_ref["apogee_alt"]) / ork_ref["apogee_alt"] * 100
    print(f"\n=== {name} vs OpenRocket ({os.path.basename(csv_path)}) ===")
    print(f"{'':25}{'OpenRocket':>15}{'Ours':>15}")
    print(f"{'Apogee AGL (m)':25}{ork_ref['apogee_alt']:>15.2f}{our_result['apogee_alt']:>15.2f}")
    print(f"{'Burnout altitude (m)':25}{ork_ref['burnout_alt']:>15.2f}{our_result['burnout_alt'] or float('nan'):>15.2f}")
    print(f"{'Burnout velocity (m/s)':25}{ork_ref['burnout_v']:>15.2f}{our_result['burnout_v'] or float('nan'):>15.2f}")
    print(f"{'Reference area (m2)':25}{ork_ref['reference_area_cm2']/1e4:>15.5f}{our_result['reference_area_m2']:>15.5f}")
    print(f"{'Total impulse (Ns)':25}{'n/a':>15}{our_result['total_impulse']:>15.1f}")
    print(f"{'Mass t=0 (kg, no motor mass col here)':25}{'see t0 config':>15}{our_result['mass_t0']:>15.4f}")
    cd_b_mach, cd_b = ork_ref["cd_boost_near_mach03"]
    cd_c_mach, cd_c = ork_ref["cd_coast_near_mach03"]
    print(f"OpenRocket Cd near Mach 0.3: boost={cd_b:.4f}@M{cd_b_mach:.3f}, coast={cd_c:.4f}@M{cd_c_mach:.3f}" if cd_b else "OpenRocket Cd near Mach 0.3: n/a")
    print(f"APOGEE ERROR: {err_pct:+.2f}% (target: within +-{TOLERANCE_PCT}%)")
    return err_pct


def test_brasil_config_vs_openrocket():
    """LASC-design config: LAUNCH_MASS=10.400 (config.py defaults - this
    IS what OpenRocket used for this exact CSV, no override needed)."""
    csv_path = os.path.join(REF_ROOT, "data", "openrocket_exports", "Prometeo_Launchsite_BRASIL.csv")
    ork_ref = openrocket_reference(csv_path)
    our_result = ours(site="brasil", overrides={}, rail_length=prom_config.RAIL_LENGTH,
                       inclination=prom_config.RAIL_INCLINATION, heading=prom_config.RAIL_HEADING)
    err_pct = _report("Brasil/LASC-design", ork_ref, our_result, csv_path)
    if abs(err_pct) > TOLERANCE_PCT:
        print(f"OUTSIDE +-{TOLERANCE_PCT}% - see PROGRESS.md for the investigation, not tuned away.")


def test_julio4_asflown_vs_openrocket():
    """July4 as-flown config: LAUNCH_MASS=10.96/MOTOR_MASS_LOADED=4.882948
    (verified_constants.json's julio4_asflown_sim block - this IS what
    OpenRocket used for THIS CSV)."""
    csv_path = os.path.join(REF_ROOT, "data", "openrocket_exports", "prometeo4dejulio.csv")
    ork_ref = openrocket_reference(csv_path)
    our_result = ours(site="julio4", overrides=dict(LAUNCH_MASS=10.96, MOTOR_MASS_LOADED=4.882948, MOTOR_DRY_MASS=2.866213),
                       rail_length=3.0, inclination=89.0, heading=270.0)
    err_pct = _report("July4 as-flown", ork_ref, our_result, csv_path)
    if abs(err_pct) > TOLERANCE_PCT:
        print(f"OUTSIDE +-{TOLERANCE_PCT}% - see PROGRESS.md for the investigation, not tuned away.")


if __name__ == "__main__":
    test_brasil_config_vs_openrocket()
    test_julio4_asflown_vs_openrocket()
