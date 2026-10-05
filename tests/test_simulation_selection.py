"""2026-10-05 review: "I have a set of places (LASC, IREC, Pachuca -
Brasil, Midland, Pachuca) - when I load the files, a button shows up and
shows the sim I want to use... in Major Tom I have 12 simulations with
different parameters." A real .ork commonly holds several stored
simulations (one per launch site/mission), each with its own launch
conditions (site, rail, wind) - before this, read_ork() always silently
used the FIRST one in the file with no way to pick a different one.

PROMETEO's own .ork conveniently has 2 real stored simulations
("Ballistic Brasil" at 495 m, "brasil 2026" at 490 m) - used directly
here instead of an invented fixture.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import ork_reader, translate
from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_simulation_selection")


def test_list_simulation_names_finds_both_real_stored_sims():
    names = ork_reader.list_simulation_names(ORK_PATH)
    assert names == ["Ballistic Brasil", "brasil 2026"]


def test_read_ork_default_matches_original_first_simulation_behavior():
    """No regression: not passing simulation_name must behave EXACTLY
    like before this feature existed."""
    parsed_default = ork_reader.read_ork(ORK_PATH)
    parsed_explicit_first = ork_reader.read_ork(ORK_PATH, simulation_name="Ballistic Brasil")
    assert parsed_default.launch.altitude_m == parsed_explicit_first.launch.altitude_m
    assert parsed_default.launch.latitude == parsed_explicit_first.launch.latitude


def test_read_ork_with_simulation_name_picks_the_real_different_conditions():
    parsed_a = ork_reader.read_ork(ORK_PATH, simulation_name="Ballistic Brasil")
    parsed_b = ork_reader.read_ork(ORK_PATH, simulation_name="brasil 2026")
    assert parsed_a.launch.altitude_m == 495.0
    assert parsed_b.launch.altitude_m == 490.0
    assert parsed_a.launch.altitude_m != parsed_b.launch.altitude_m


def test_read_ork_falls_back_to_first_for_an_unknown_name():
    """A stale selection (e.g. the .ork was re-exported without that
    sim) should degrade gracefully, not raise or silently return no
    launch conditions at all."""
    parsed = ork_reader.read_ork(ORK_PATH, simulation_name="does not exist")
    parsed_first = ork_reader.read_ork(ORK_PATH)
    assert parsed.launch.altitude_m == parsed_first.launch.altitude_m


def test_load_files_threads_the_selection_into_the_load_result():
    os.makedirs(OUT_DIR, exist_ok=True)
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR, simulation_name="brasil 2026")
    assert lr.simulation_name == "brasil 2026"
    assert lr.available_simulation_names == ["Ballistic Brasil", "brasil 2026"]
    assert lr.parsed_ork.launch.altitude_m == 490.0


def test_load_files_default_has_no_selection_but_lists_both():
    os.makedirs(OUT_DIR, exist_ok=True)
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    assert lr.simulation_name is None
    assert lr.available_simulation_names == ["Ballistic Brasil", "brasil 2026"]


def test_mass_cg_estimate_and_openrocket_comparison_follow_the_same_selection():
    """2026-10-05 review's own consistency requirement: the mass/CG
    reference and the OpenRocket comparison card must check against the
    SAME stored simulation the launch conditions came from, not silently
    fall back to "first" independently."""
    from bup_rocketpy import openrocket_comparison
    from bup_rocketpy.motor_reader import read_eng

    for sim_name, expected_alt in [("Ballistic Brasil", 495.0), ("brasil 2026", 490.0)]:
        parsed = ork_reader.read_ork(ORK_PATH, simulation_name=sim_name)
        eng = read_eng(ENG_PATH)
        assert parsed.launch.altitude_m == expected_alt

        best = translate.estimate_best_dry_mass_cg_inertia(parsed, eng, ENG_PATH, ork_path=ORK_PATH, simulation_name=sim_name)
        assert sim_name in best.mass_est.source, f"expected the mass/CG source to name {sim_name!r}, got: {best.mass_est.source}"

        mass_est = translate.MassEstimate(best.mass_est.mass_kg, best.mass_est.cg_m, "test")
        motor = translate.build_motor(eng, ENG_PATH)
        radius = next(t.radius for t in parsed.body_tubes if t.radius)
        i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
        power_off_drag = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
        power_on_drag = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
        rocket = translate.build_rocket(parsed, motor, mass_est, i_ax, i_tr, radius, power_off_drag=power_off_drag, power_on_drag=power_on_drag)
        from rocketpy import Flight
        env = translate.build_environment(parsed.launch)
        flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m, inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg, terminate_on_apogee=True)
        sim_result = pipeline.SimResult(
            apogee_agl_m=flight.apogee - env.elevation, max_speed_ms=flight.max_speed, max_mach=flight.max_mach_number,
            max_acceleration_ms2=flight.max_acceleration, rail_exit_velocity_ms=flight.out_of_rail_velocity,
            flight_time_s=flight.t_final, min_static_margin_cal=0, max_static_margin_cal=0, is_stable=True,
            plot_paths={}, csv_path="", validation_summary_text="", dry_mass_kg=mass_est.mass_kg,
            flight=flight, motor=motor,
        )
        returned_sim_name, rows = openrocket_comparison.compare_to_openrocket(parsed, sim_result, ORK_PATH, simulation_name=sim_name)
        assert returned_sim_name == sim_name


if __name__ == "__main__":
    test_list_simulation_names_finds_both_real_stored_sims()
    test_read_ork_default_matches_original_first_simulation_behavior()
    test_read_ork_with_simulation_name_picks_the_real_different_conditions()
    test_read_ork_falls_back_to_first_for_an_unknown_name()
    test_load_files_threads_the_selection_into_the_load_result()
    test_load_files_default_has_no_selection_but_lists_both()
    test_mass_cg_estimate_and_openrocket_comparison_follow_the_same_selection()
    print("\nSIMULATION SELECTION: OK")
