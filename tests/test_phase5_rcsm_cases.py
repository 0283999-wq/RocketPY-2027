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


if __name__ == "__main__":
    test_all_four_cases_build_without_crashing()
    test_compliance_check_runs_on_nominal_case()
    print("\nPHASE 5 RCSM CASES: OK")
