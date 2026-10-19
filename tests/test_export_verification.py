"""2026-10-20 review ("judge-grade LASC package", item 5): "Before the
download is offered, the app runs every exported file in a clean venv
and checks apogee, parachute events, descent rates, flight time and
landing point against the app (< 1 %). If any check fails, block the
download and say which one."

bup_rocketpy/export_verification.py implements this; lasc_package.
build_lasc_zip() calls it whenever a real case_results dict (with
usable Flight objects - what exports_page.py's real UI flow always
supplies) is given, BEFORE the zip is ever written to disk.

These tests are necessarily slower than most of this suite - they
build/reuse a real venv and actually run the exported scripts, which
is the whole point of the check. Uses PROMETEO's real .ork/.eng (no
invented rocket); the FAILURE-path test substitutes a deliberately
wrong (synthetic, clearly-labeled-as-fake) Flight-like stand-in for one
case to prove the gate actually fires, not PROMETEO's own real numbers.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from bup_rocketpy import lasc_package, rcsm_cases, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_export_verification")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _build_common():
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    return parsed, parsed_eng, i_axial, i_transverse, radius_m


def test_pct_diff_and_compare_helpers():
    """Fast, no-subprocess unit coverage of the comparison arithmetic
    itself, isolated from the slow end-to-end tests below."""
    from bup_rocketpy import export_verification as ev

    assert ev._pct_diff(1000.0, 1000.0) == 0.0
    assert abs(ev._pct_diff(1000.0, 1010.0) - 1.0) < 1e-9
    mismatches = ev._compare_numbers("x", {"apogee_agl_m": 1000.0}, {"apogee_agl_m": 1200.0}, {"apogee_agl_m": 1.0})
    assert len(mismatches) == 1 and "apogee_agl_m" in mismatches[0]
    ok = ev._compare_numbers("x", {"apogee_agl_m": 1000.0}, {"apogee_agl_m": 1005.0}, {"apogee_agl_m": 1.0})
    assert ok == []


def test_build_lasc_zip_passes_verification_for_the_real_matching_rocket():
    os.makedirs(OUT_DIR, exist_ok=True)
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    case_results = rcsm_cases.run_all_cases(parsed, parsed_eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M, i_axial_override=i_ax, i_transverse_override=i_tr)
    assert case_results["Ballistic"].flight is not None  # fixture sanity check

    zip_path = os.path.join(OUT_DIR, "test_verified.zip")
    lasc_package.build_lasc_zip(
        zip_path, "44", parsed, parsed_eng, ENG_PATH, ORK_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        cases=[("Ballistic", False), ("Nominal", True)],
        eng_filename="Icarus_I_K519.eng", ork_filename="PrometeoLasc2026.ork",
        case_results=case_results,
    )
    assert os.path.exists(zip_path), "the real app's own numbers must pass its own verification gate"


def test_build_lasc_zip_blocks_the_download_when_app_and_exported_disagree():
    """Substitutes a deliberately wrong (synthetic) Flight-like object
    for the Ballistic case's "what the app computed" baseline - proves
    the gate actually compares and actually blocks, rather than always
    passing."""
    os.makedirs(OUT_DIR, exist_ok=True)
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    case_results = rcsm_cases.run_all_cases(parsed, parsed_eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M, i_axial_override=i_ax, i_transverse_override=i_tr)
    real_ballistic_flight = case_results["Ballistic"].flight
    assert real_ballistic_flight is not None

    fake_flight = types.SimpleNamespace(
        apogee=real_ballistic_flight.apogee + 999999.0,  # absurdly, deliberately wrong - not a real physical value
        env=types.SimpleNamespace(elevation=real_ballistic_flight.env.elevation),
        t_final=real_ballistic_flight.t_final,
        x_impact=real_ballistic_flight.x_impact,
        y_impact=real_ballistic_flight.y_impact,
        parachute_events=[],
    )
    case_results["Ballistic"] = types.SimpleNamespace(case_name="Ballistic", flight=fake_flight, warning="")

    zip_path = os.path.join(OUT_DIR, "test_blocked.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with pytest.raises(ValueError, match="did not match the app"):
        lasc_package.build_lasc_zip(
            zip_path, "44", parsed, parsed_eng, ENG_PATH, ORK_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
            DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
            cases=[("Ballistic", False)],
            eng_filename="Icarus_I_K519.eng", ork_filename="PrometeoLasc2026.ork",
            case_results=case_results,
        )
    assert not os.path.exists(zip_path), "the zip must never be written when verification fails - that's the whole point of the gate"


if __name__ == "__main__":
    test_pct_diff_and_compare_helpers()
    test_build_lasc_zip_passes_verification_for_the_real_matching_rocket()
    test_build_lasc_zip_blocks_the_download_when_app_and_exported_disagree()
    print("\nEXPORT VERIFICATION: OK")
