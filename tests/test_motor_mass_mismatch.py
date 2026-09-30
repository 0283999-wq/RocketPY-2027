"""2026-09-30 review item 2: a real case found an .eng declaring the
motor's total mass 550 g heavier than what the .ork's own stored
simulation (and the team's actual measured motor) used - the app
silently flew the wrong rocket with no way to notice. This test locks
in the detection (translate.check_motor_mass_mismatch), the import-table
warning (pipeline.load_files), and the "measured motor mass" override
(pipeline.run_simulation) - keeping the .eng's own thrust curve/
propellant mass while replacing only the dry (casing) mass build_motor()
sees.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.gui import pipeline
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_motor_mass_mismatch")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def test_check_motor_mass_mismatch_matches_hand_calc():
    """The real case this fix is for: .eng says 15.960163 kg loaded, the
    real/OpenRocket-recorded motor is 6.25 + 9.158 = 15.408 kg - about
    550 g (3.5%) over, well past the 1% threshold."""
    parsed_eng = read_eng(ENG_PATH)
    import dataclasses
    header = dataclasses.replace(parsed_eng.header, total_mass_kg=15.960163, propellant_mass_kg=9.157442)

    class _FakeRef:
        motor_mass_t0_kg = 15.407726  # 6.25 + 9.157726, close enough to the 15.406 the report gave

    import bup_rocketpy.ork_reader as ork_reader_module
    orig = ork_reader_module.parse_stored_simulation_references
    ork_reader_module.parse_stored_simulation_references = lambda path: {"sim": _FakeRef()}
    try:
        result = translate.check_motor_mass_mismatch(header, "unused-path")
    finally:
        ork_reader_module.parse_stored_simulation_references = orig

    assert result is not None
    assert result.over_threshold
    assert abs(result.diff_g - 552.4) < 1.0
    assert 3.0 < result.diff_pct < 4.0


def test_check_motor_mass_mismatch_none_when_no_stored_sim():
    parsed_eng = read_eng(ENG_PATH)
    import bup_rocketpy.ork_reader as ork_reader_module
    orig = ork_reader_module.parse_stored_simulation_references
    ork_reader_module.parse_stored_simulation_references = lambda path: {}
    try:
        assert translate.check_motor_mass_mismatch(parsed_eng.header, "unused-path") is None
    finally:
        ork_reader_module.parse_stored_simulation_references = orig


def test_load_files_flags_a_real_motor_mass_mismatch_on_prometeo():
    """PROMETEO's own reference files have a real (smaller, opposite-
    direction) mismatch: the .eng declares 4.7378 kg, the .ork's stored
    sim used 4.864 kg (-2.6%) - past the 1% threshold, so this is a real,
    previously-undetected finding, not a synthetic one."""
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    assert lr.motor_mismatch is not None
    assert lr.motor_mismatch.over_threshold
    assert any("motor mass" in row[0] for row in lr.import_table), lr.import_table


def test_measured_motor_mass_override_keeps_thrust_curve_changes_only_dry_mass():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    baseline = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    overridden = pipeline.run_simulation(
        lr, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M,
        motor_total_mass_override_kg=5.0,
    )
    assert overridden.motor_loaded_kg == 5.0
    # propellant mass (and therefore the thrust curve's own total impulse) is untouched
    assert abs(overridden.motor_propellant_kg - baseline.motor_propellant_kg) < 1e-9
    assert overridden.motor_dry_kg != baseline.motor_dry_kg
    assert "override" in overridden.motor_mass_source.lower()
    assert ".eng header" in baseline.motor_mass_source


def test_mass_breakdown_liftoff_minus_propellant_equals_descent():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    assert abs(sim.liftoff_mass_kg - sim.motor_propellant_kg - sim.descent_mass_kg) < 1e-9
    assert abs(sim.liftoff_mass_kg - (DRY_MASS_KG + sim.motor_loaded_kg)) < 1e-9
    assert abs(sim.descent_mass_kg - (DRY_MASS_KG + sim.motor_dry_kg)) < 1e-9


if __name__ == "__main__":
    test_check_motor_mass_mismatch_matches_hand_calc()
    test_check_motor_mass_mismatch_none_when_no_stored_sim()
    test_load_files_flags_a_real_motor_mass_mismatch_on_prometeo()
    test_measured_motor_mass_override_keeps_thrust_curve_changes_only_dry_mass()
    test_mass_breakdown_liftoff_minus_propellant_equals_descent()
    print("\nMOTOR MASS MISMATCH: OK")
