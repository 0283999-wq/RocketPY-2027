"""Helper script (NOT collected by pytest - no test_ prefix) run as a
FRESH subprocess by test_encoding_defaults.py, with the environment set
to disable Python's UTF-8 mode and force a non-UTF-8 locale - the
closest available proxy on this Linux sandbox (no cp1252 locale is
installed) for "Windows, open() with no explicit encoding". Prints "OK"
on success; a UnicodeEncodeError or any other exception propagates as a
non-zero exit + traceback on stderr, which the parent test asserts on.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    from bup_rocketpy import openrocket_csv_export, translate
    from bup_rocketpy.motor_reader import read_eng
    from bup_rocketpy.ork_reader import read_ork

    REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
    ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
    POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
    POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
    OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_windows_encoding")
    DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279

    os.makedirs(OUT_DIR, exist_ok=True)
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=False, include_recovery=True,
        dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M,
    )
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    path = os.path.join(OUT_DIR, "flight_data_openrocket_style.csv")

    # This is the literal call Diego's own bug report failed on - the
    # real 58-column OpenRocket header includes a zero-width space
    # (U+200B) in "Stability margin calibers ()".
    openrocket_csv_export.export_openrocket_style_csv(flight, radius_m, path, simulation_name="Windows encoding regression test")

    with open(path, encoding="utf-8-sig") as f:
        content = f.read()
    assert "​" in content, "the zero-width space that broke this on Windows should still be IN the file - utf-8 can represent it fine, this isn't testing that it got stripped"

    print("OK")
