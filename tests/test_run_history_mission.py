"""2026-09-27 review item 2: "Save them as a 'mission' (files + settings)
that can be reopened later from History." Every session setting that
affects the flown rocket - reefing, mass/CG override, weather override,
competition profile - must round-trip through save_run()/reopen_run(),
not just the RESULT numbers, or reopening a mission silently drops
exactly the settings Diego reported losing (reefing not applied after a
re-upload).
"""
import dataclasses
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import run_history
from bup_rocketpy.gui import pipeline
from bup_rocketpy.ork_reader import LaunchConditions

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_run_history_mission")
RUNS_DIR = os.path.join(REPO_ROOT, "outputs", "test_run_history_mission_runs")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _fresh_runs_dir():
    os.environ["BUP_ROCKETPY_RUNS_DIR"] = RUNS_DIR
    if os.path.isdir(RUNS_DIR):
        import shutil
        shutil.rmtree(RUNS_DIR)
    os.makedirs(RUNS_DIR, exist_ok=True)


def _build_and_reef():
    load_result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    # Mark the real parachute as reefed, same UI action the Rocket page's
    # "Save" button performs (mutating parsed.parachutes[i] in place).
    parsed = load_result.parsed_ork
    parsed.parachutes[0] = dataclasses.replace(
        parsed.parachutes[0], is_reefed=True, reefed_diameter_m=0.6, reefed_cd=1.5, cutter_altitude_m=450.0, cutter_delay_s=1.0,
    )
    sim = pipeline.run_simulation(load_result, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    return load_result, sim


def test_save_and_reopen_round_trips_reefing_and_settings():
    _fresh_runs_dir()
    load_result, sim = _build_and_reef()
    launch_override = LaunchConditions(rail_length_m=4.0, rail_angle_from_vertical_deg=10.0, rail_direction_deg=90.0, altitude_m=490.0, latitude=-21.9, longitude=-48.96, wind_average_ms=7.5, wind_direction_deg=45.0)

    record = run_history.save_run(
        REPO_ROOT, sim, load_result, DRY_MASS_KG, DRY_CG_M,
        ork_path=ORK_PATH, ork_filename="Major_Tom.ork", eng_filename="Icarus.eng",
        dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M,
        launch_override=dataclasses.asdict(launch_override), competition_profile="lasc",
    )
    assert record.ork_saved and record.power_off_drag_saved and record.power_on_drag_saved
    assert any(c["is_reefed"] for c in record.reefing_settings), "reefing_settings must capture the reefed parachute"

    reopened = run_history.reopen_run(REPO_ROOT, record.run_id, OUT_DIR)
    chute = reopened["load_result"].parsed_ork.parachutes[0]
    assert chute.is_reefed is True
    assert chute.reefed_diameter_m == 0.6 and chute.reefed_cd == 1.5 and chute.cutter_altitude_m == 450.0
    assert reopened["dry_mass_override"] == DRY_MASS_KG and reopened["dry_cg_override"] == DRY_CG_M
    assert reopened["launch_override"].wind_average_ms == 7.5 and reopened["launch_override"].wind_direction_deg == 45.0
    assert reopened["competition_profile"] == "lasc"
    assert reopened["ork_filename"] == "Major_Tom.ork"

    # The reopened mission must actually be simulate-able end to end,
    # with the reefing STILL applied (not just present on the parachute
    # object, but actually producing two real rocketpy parachutes).
    from bup_rocketpy import translate
    motor = translate.build_motor(reopened["load_result"].parsed_eng, reopened["load_result"].eng_path)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(reopened["load_result"].parsed_ork, mass_est)
    radius = next(t.radius for t in reopened["load_result"].parsed_ork.body_tubes if t.radius)
    rocket = translate.build_rocket(
        reopened["load_result"].parsed_ork, motor, mass_est, i_ax, i_tr, radius,
        power_off_drag=reopened["load_result"].power_off_drag_path, power_on_drag=reopened["load_result"].power_on_drag_path,
    )
    assert len(rocket.parachutes) == 2, f"expected 2 real parachutes (reefed + full) after reopening, got {len(rocket.parachutes)}"


def test_update_run_text_patches_report_text_without_minting_a_new_run():
    """2026-09-27 review item 6: editable report text blocks are filled in
    on the Exports page AFTER Simulate already saved the run - this must
    patch the EXISTING record (same run_id), not create a duplicate
    history entry, and round-trip through reopen_run()."""
    _fresh_runs_dir()
    load_result, sim = _build_and_reef()
    record = run_history.save_run(REPO_ROOT, sim, load_result, DRY_MASS_KG, DRY_CG_M, ork_path=ORK_PATH)
    assert record.report_text == {} and record.author == ""

    updated = run_history.update_run_text(REPO_ROOT, record.run_id, author="Diego", report_text={"introduction": "Custom intro."})
    assert updated.run_id == record.run_id, "must patch the same run, not create a new one"
    records, _ = run_history.list_runs(REPO_ROOT)
    assert len(records) == 1, "update_run_text must not duplicate the history entry"

    reopened = run_history.reopen_run(REPO_ROOT, record.run_id, OUT_DIR)
    assert reopened["report_text"]["introduction"] == "Custom intro."
    assert reopened["current_run_id"] == record.run_id


def test_reopen_raises_a_clear_error_for_a_run_with_no_saved_ork():
    _fresh_runs_dir()
    load_result, sim = _build_and_reef()
    record = run_history.save_run(REPO_ROOT, sim, load_result, DRY_MASS_KG, DRY_CG_M, ork_path=None)  # no ork_path given -> ork_saved stays False
    assert record.ork_saved is False
    try:
        run_history.reopen_run(REPO_ROOT, record.run_id, OUT_DIR)
        assert False, "expected MissionNotReopenableError"
    except run_history.MissionNotReopenableError as exc:
        assert "no saved .ork" in str(exc)


def test_old_schema_record_without_new_fields_still_loads():
    """Backward compatibility: a record.json saved before this feature
    existed (missing reefing_settings/dry_mass_override_kg/etc. entirely)
    must not break list_runs()/get_run()."""
    _fresh_runs_dir()
    run_id = "20260101_000000"
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    old_record = {
        "run_id": run_id, "timestamp": "2026-01-01T00:00:00+00:00", "vehicle_name": "Old Rocket",
        "ork_filename": "old.ork", "eng_filename": "old.eng", "dry_mass_kg": 5.0, "dry_cg_m": 0.5,
        "apogee_agl_m": 1000.0, "max_speed_ms": 200.0, "min_static_margin_cal": 2.0, "is_stable": True,
    }
    with open(os.path.join(run_dir, "record.json"), "w") as f:
        json.dump(old_record, f)

    records, warnings = run_history.list_runs(REPO_ROOT)
    assert not warnings
    assert len(records) == 1
    assert records[0].reefing_settings == [] and records[0].ork_saved is False


if __name__ == "__main__":
    test_save_and_reopen_round_trips_reefing_and_settings()
    test_update_run_text_patches_report_text_without_minting_a_new_run()
    test_reopen_raises_a_clear_error_for_a_run_with_no_saved_ork()
    test_old_schema_record_without_new_fields_still_loads()
    print("\nRUN HISTORY MISSION: OK")
