"""2026-10-09 review item 8: STR 6.3.2 used to show "pass fin_flutter_velocity"
(a Python parameter name) verbatim in the compliance table, and RKT 1.1.2
hardcoded payload_mass_kg=1.0 for every rocket regardless of what was
actually loaded. Tests bup_rocketpy/flutter.py (NACA TN 4197 hand
formula + manual-override priority) and rcsm.check_compliance()'s own
consumption of both, using PROMETEO's real fin geometry (no invented
rocket).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import flutter, rcsm
from bup_rocketpy.gui import pipeline
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_flutter_and_rcsm_payload")


def test_hand_calc_gives_a_plausible_flutter_velocity_for_real_fins():
    parsed = read_ork(ORK_PATH)
    result = flutter.worst_case_flutter(parsed, speed_of_sound_ms=340.0, static_pressure_pa=95000.0)
    assert result is not None
    assert 50 < result.flutter_velocity_ms < 2000, f"implausible flutter velocity: {result.flutter_velocity_ms}"
    assert "NACA TN 4197" in result.source
    assert result.is_approximate is True


def test_thicker_fins_flutter_at_a_higher_speed():
    """Sanity check on the formula's own sign: flutter velocity scales
    with thickness^1.5 (t/c cubed inside a sqrt) - a thicker fin must
    never flutter at a LOWER speed than a thinner one, all else equal."""
    import dataclasses
    parsed = read_ork(ORK_PATH)
    thin = parsed.fins[0]
    thick = dataclasses.replace(thin, thickness=thin.thickness * 2)
    r_thin = flutter.hand_calc_flutter_velocity(thin, 340.0, 95000.0)
    r_thick = flutter.hand_calc_flutter_velocity(thick, 340.0, 95000.0)
    assert r_thick.flutter_velocity_ms > r_thin.flutter_velocity_ms


def test_manual_override_always_wins_and_is_not_approximate():
    parsed = read_ork(ORK_PATH)
    result = flutter.worst_case_flutter(
        parsed, 340.0, 95000.0,
        manual_override_ms=500.0, manual_override_source="ANSYS run 2026-10-01",
    )
    assert result.flutter_velocity_ms == 500.0
    assert "ANSYS run 2026-10-01" in result.source
    assert result.is_approximate is False


def test_no_fins_and_no_override_returns_none_not_a_fabricated_number():
    class _NoFins:
        fins = []
    assert flutter.worst_case_flutter(_NoFins(), 340.0, 95000.0) is None


def test_rcsm_compliance_never_shows_the_python_parameter_name():
    """The literal bug report: "pass fin_flutter_velocity" (code name) in
    the user-facing compliance table."""
    os.makedirs(OUT_DIR, exist_ok=True)
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR)
    from bup_rocketpy import rcsm_cases
    cases = rcsm_cases.run_all_cases(lr.parsed_ork, lr.parsed_eng, lr.eng_path, lr.power_off_drag_path, lr.power_on_drag_path, sim.dry_mass_kg, sim.dry_cg_m)
    nominal = cases["Nominal"]
    category = rcsm.CATEGORIES["3km_solid"]

    # No flutter result computed (fin_flutter_velocity=None, the same
    # state as before this review) - the WARN detail text must still
    # never leak the Python parameter name.
    rows = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=4.0, fin_flutter_velocity=None)
    flutter_row = next(r for r in rows if r[0] == "STR 6.3.2")
    assert "fin_flutter_velocity" not in flutter_row[3], f"code parameter name leaked into UI text: {flutter_row[3]!r}"

    # With a real computed flutter velocity, the rule evaluates for real.
    env = nominal.flight.env
    fr = flutter.worst_case_flutter(lr.parsed_ork, env.speed_of_sound(env.elevation), env.pressure(env.elevation))
    rows2 = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=4.0, fin_flutter_velocity=fr.flutter_velocity_ms)
    flutter_row2 = next(r for r in rows2 if r[0] == "STR 6.3.2")
    assert flutter_row2[2] in ("PASS", "FAIL")  # a real verdict, not WARN/"not computed"


def test_rcsm_payload_mass_reflects_what_is_passed_in_not_a_hardcoded_1kg():
    os.makedirs(OUT_DIR, exist_ok=True)
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR)
    from bup_rocketpy import rcsm_cases
    cases = rcsm_cases.run_all_cases(lr.parsed_ork, lr.parsed_eng, lr.eng_path, lr.power_off_drag_path, lr.power_on_drag_path, sim.dry_mass_kg, sim.dry_cg_m)
    nominal = cases["Nominal"]
    category = rcsm.CATEGORIES["3km_solid"]  # min_payload_kg = 4.000

    rows_low = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=1.0)
    rows_high = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=4.0)
    payload_low = next(r for r in rows_low if r[0] == "RKT 1.1.2")
    payload_high = next(r for r in rows_high if r[0] == "RKT 1.1.2")
    assert payload_low[2] == "FAIL"  # 1.0 kg < 4.0 kg category minimum
    assert payload_high[2] == "PASS"
    assert payload_low[3] != payload_high[3]  # the reported grams must reflect the actual mass passed in


if __name__ == "__main__":
    test_hand_calc_gives_a_plausible_flutter_velocity_for_real_fins()
    test_thicker_fins_flutter_at_a_higher_speed()
    test_manual_override_always_wins_and_is_not_approximate()
    test_no_fins_and_no_override_returns_none_not_a_fabricated_number()
    test_rcsm_compliance_never_shows_the_python_parameter_name()
    test_rcsm_payload_mass_reflects_what_is_passed_in_not_a_hardcoded_1kg()
    print("\nFLUTTER + RCSM PAYLOAD: OK")
