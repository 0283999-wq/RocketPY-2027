"""2026-09-26 review item G: CSV export matching OpenRocket's own 58-
column format (see reference/prometeo_mission44/data/openrocket_exports/
*.csv for the real layout this mirrors). Uses PROMETEO's real .ork/.eng
through the SAME translate.ork_to_flight() path every other test in this
repo uses - no hand-built rocket.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import openrocket_csv_export, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_openrocket_csv_export")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279  # same independently-verified numbers other tests in this repo use


def _build_flight():
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=False, include_recovery=True,
        dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M,
    )
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    return flight, radius_m


def test_csv_has_58_columns_and_real_event_markers():
    flight, radius_m = _build_flight()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "flight_data_openrocket_style.csv")
    openrocket_csv_export.export_openrocket_style_csv(flight, radius_m, path, simulation_name="PROMETEO test export")

    with open(path, encoding="utf-8-sig") as f:
        lines = f.readlines()

    header_line = lines[3]
    assert header_line.startswith("# Time (s),Altitude (m),Altitude above sea level (m)")
    n_columns = len(header_line[2:].strip().split(","))
    assert n_columns == 58, f"expected 58 columns, got {n_columns}"

    event_lines = [l for l in lines if l.startswith("# Event")]
    event_names = " ".join(event_lines)
    for expected in ["IGNITION", "LAUNCHROD", "BURNOUT", "APOGEE", "GROUND_HIT"]:
        assert expected in event_names, f"missing expected event marker '{expected}'"
    # PROMETEO's real .ork has one parachute - a real dual-event vehicle
    # would show a second RECOVERY_DEVICE_DEPLOYMENT marker here too.
    assert "RECOVERY_DEVICE_DEPLOYMENT" in event_names

    data_lines = [l for l in lines if l and not l.startswith("#")]
    assert len(data_lines) > 100, "expected one row per rocketpy integration step across a multi-hundred-step flight"
    first_row = data_lines[0].strip().split(",")
    assert len(first_row) == 58


def test_sane_apogee_and_mach_columns():
    flight, radius_m = _build_flight()
    rows, events = openrocket_csv_export.build_openrocket_style_rows(flight, radius_m)
    altitudes = [r[1] for r in rows]  # "Altitude (m)" column, AGL
    machs = [r[51] for r in rows]  # "Mach number" column
    assert 800 < max(altitudes) < 1600, f"apogee altitude column looks implausible: {max(altitudes)}"
    assert 0 <= max(machs) < 3, f"max Mach column looks implausible: {max(machs)}"
    apogee_events = [t for t, name in events if name == "APOGEE"]
    assert len(apogee_events) == 1
    assert abs(apogee_events[0] - flight.apogee_time) < 1e-6


def test_cg_and_cp_are_in_nose_referenced_cm_with_cp_aft_of_cg():
    """Regression guard for a real sign bug caught and fixed before
    shipping: a first version multiplied by rocket._csys (always +1 for
    this app's default "tail_to_nose" build) instead of actually
    inverting translate.py's nose-frame<->rocketpy-frame conversion, so
    CG/CP came out negated (~-95cm/-121cm instead of the correct
    +95cm/+121cm from the nose tip). A stable rocket's CP must be AFT of
    (a larger from-nose distance than) its CG."""
    flight, radius_m = _build_flight()
    rows, _ = openrocket_csv_export.build_openrocket_style_rows(flight, radius_m)
    cp_cm_t0, cg_cm_t0 = rows[0][26], rows[0][27]
    assert cg_cm_t0 > 0 and cp_cm_t0 > 0, f"CG/CP should be positive distances from the nose tip, got cg={cg_cm_t0}, cp={cp_cm_t0}"
    assert cp_cm_t0 > cg_cm_t0, f"CP ({cp_cm_t0} cm) should be aft of CG ({cg_cm_t0} cm) for a stable rocket"
    total_length_cm = 147.0  # PROMETEO's real body length, see translate/config
    assert cg_cm_t0 < total_length_cm and cp_cm_t0 < total_length_cm


def test_longitudinal_inertia_column_is_the_larger_transverse_value():
    """Regression guard for a real bug caught and fixed 2026-09-27: a
    first version wrote (I_33, I_11) under the (Longitudinal, Rotational)
    headers - backwards. For a long slender rocket the TRANSVERSE
    (pitch/yaw) inertia is much larger than the AXIAL (roll) one, and
    OpenRocket's own "Longitudinal moment of inertia" column IS the
    transverse value (confirmed against config.py's real OpenRocket-
    sourced constants: INERTIA_LONG_T0_WITH_MOTOR=1.612 kg.m2 >>
    INERTIA_ROT_T0_WITH_MOTOR=0.020 kg.m2), so "Longitudinal" must stay
    larger than "Rotational" here too."""
    flight, radius_m = _build_flight()
    rows, _ = openrocket_csv_export.build_openrocket_style_rows(flight, radius_m)
    longitudinal_t0, rotational_t0 = rows[0][23], rows[0][24]
    assert longitudinal_t0 > rotational_t0, f"Longitudinal ({longitudinal_t0}) should be >> Rotational ({rotational_t0}) for a long slender rocket"


if __name__ == "__main__":
    test_csv_has_58_columns_and_real_event_markers()
    test_sane_apogee_and_mach_columns()
    test_longitudinal_inertia_column_is_the_larger_transverse_value()
    test_cg_and_cp_are_in_nose_referenced_cm_with_cp_aft_of_cg()
    print("\nOPENROCKET CSV EXPORT: OK")
