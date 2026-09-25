"""Phase 5: the 4 RCSM cases (Ballistic, Nominal, Drogue-only, Main-at-
apogee) + automatic compliance check. CLAUDE.md Sec 3.4/6: "the app must
warn about it [no drogue] instead of crashing" - this is the requirement
this test enforces for PROMETEO's real single-deploy .ork.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import rcsm, rcsm_cases
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def test_all_four_cases_build_without_crashing():
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    assert set(results.keys()) == set(rcsm_cases.CASE_NAMES)
    for name, r in results.items():
        print(f"\n{name}: flight={'OK' if r.flight else 'NONE'}, warning={r.warning[:80]!r}")
    assert results["Ballistic"].flight is not None and results["Ballistic"].warning == ""
    assert results["Nominal"].flight is not None and results["Nominal"].warning == ""
    # PROMETEO's real .ork has exactly one recovery event - these two MUST
    # warn (single-deploy is not a real dual-deploy topology), NOT crash.
    assert results["DrogueOnly"].flight is not None
    assert "only ONE recovery event" in results["DrogueOnly"].warning
    assert results["MainAtApogee"].flight is not None
    assert "only ONE recovery event" in results["MainAtApogee"].warning


def test_compliance_check_runs_on_nominal_case():
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    nominal = results["Nominal"]
    category = rcsm.CATEGORIES["1km_solid"]
    rows = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=1.0)
    print()
    rcsm.print_compliance_table(rows)
    assert len(rows) >= 6
    statuses = {row[2] for row in rows}
    assert statuses <= {"PASS", "WARN", "FAIL"}
    margin_row = next(r for r in rows if r[0] == "FLT 4.3.5")
    assert margin_row[2] == "PASS", f"expected the corrected-mass case to be stable and margin-compliant: {margin_row}"


def test_drogue_only_and_main_at_apogee_work_on_a_real_dual_deploy_vehicle():
    """2026-09-25 review Section 7: "for 3km/dual-deploy tests, use an
    OpenRocket example .ork that has drogue + main." PROMETEO's own .ork
    only has ONE recovery event, so the two single-deploy-only cases
    above only ever exercise the WARNING path, never the real one. This
    uses reference/openrocket_examples/Dual_parachute_deployment.ork
    (a real drogue + main vehicle) - paired with PROMETEO's real .eng
    for Simulate purposes only (see that folder's README: an honest test
    fixture, not a claim about what motor this rocket actually flies)."""
    import tempfile

    from bup_rocketpy.ork_reader import extract_drag_curves_from_stored_sim

    ORK_2 = os.path.join(REPO_ROOT, "reference", "openrocket_examples", "Dual_parachute_deployment.ork")
    parsed = read_ork(ORK_2)
    eng = read_eng(ENG_PATH)
    assert len(parsed.parachutes) == 2, "expected this fixture to have exactly a drogue + a main"

    from bup_rocketpy.curve_utils import dedupe_sort_curve

    boost, coast = extract_drag_curves_from_stored_sim(ORK_2)
    # this fixture's own stored-sim curve has a duplicate Mach value
    # (unlike PROMETEO's) - same dedupe fix as crash (f), applied here
    # since this test builds the CSVs by hand rather than going through
    # pipeline.load_files (which already does this for the app's own path).
    boost, n_dupes_boost = dedupe_sort_curve(boost)
    coast, n_dupes_coast = dedupe_sort_curve(coast)
    out_dir = tempfile.mkdtemp()
    power_on_path = os.path.join(out_dir, "power_on_drag.csv")
    power_off_path = os.path.join(out_dir, "power_off_drag.csv")
    with open(power_on_path, "w") as f:
        f.write("\n".join(f"{m},{c}" for m, c in boost))
    with open(power_off_path, "w") as f:
        f.write("\n".join(f"{m},{c}" for m, c in coast))

    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, power_off_path, power_on_path, DRY_MASS_KG, DRY_CG_M)
    for name, r in results.items():
        print(f"\n{name}: flight={'OK' if r.flight else 'NONE'}, warning={r.warning[:80]!r}")
    assert results["Ballistic"].flight is not None and results["Ballistic"].warning == ""
    assert results["Nominal"].flight is not None and results["Nominal"].warning == ""
    # THE POINT of this test: with a real 2-parachute vehicle, these must
    # run WITHOUT the "only ONE recovery event" warning this file's other
    # test exists to check for.
    assert results["DrogueOnly"].flight is not None
    assert "only ONE recovery event" not in results["DrogueOnly"].warning, f"unexpected warning on a real dual-deploy vehicle: {results['DrogueOnly'].warning}"
    assert results["MainAtApogee"].flight is not None
    assert "only ONE recovery event" not in results["MainAtApogee"].warning, f"unexpected warning on a real dual-deploy vehicle: {results['MainAtApogee'].warning}"


if __name__ == "__main__":
    test_all_four_cases_build_without_crashing()
    test_compliance_check_runs_on_nominal_case()
    test_drogue_only_and_main_at_apogee_work_on_a_real_dual_deploy_vehicle()
    print("\nPHASE 5 RCSM CASES: OK")
