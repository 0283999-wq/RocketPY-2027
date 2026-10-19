"""2026-10-19 review ("check every bug" audit, findings of the report/
export report): the standalone per-case .py this app exports (CRS
10.1.3/10.1.5/10.1.6 - the ACTUAL competition deliverable) had five
divergences from what the app itself simulates and reports:

  1. raw thrust_source=<path> let rocketpy's own Motor.import_eng
     re-parse the .eng, which can crash/fly near-zero thrust for a
     normal .eng layout - fixed by baking in the already-parsed curve.
  2. launch-day weather override never reached the exported script.
  3. a reefed main + line cutter collapsed to one wrong-physics chute.
  4. duplicate parachute trigger/lag was never deduped (can crash
     standalone even when the app itself handles it fine).
  5. the "Measured motor mass" override was dropped.
  6. DrogueOnly/MainAtApogee case names could never actually be
     exported at all (no code path built them correctly).
"""
import dataclasses
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import case_export, lasc_package, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
DUAL_ORK_PATH = os.path.join(REPO_ROOT, "reference", "openrocket_examples", "Dual_parachute_deployment.ork")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_case_export_matches_app_flight")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _build_common(ork_path=ORK_PATH):
    parsed = read_ork(ork_path)
    parsed_eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next((t.radius for t in parsed.body_tubes if t.radius), None) or 0.05
    return parsed, parsed_eng, i_axial, i_transverse, radius_m


def test_thrust_curve_is_baked_in_not_a_raw_eng_path():
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    _, source = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "Icarus_I_K519.eng", "power_off_drag.csv", "power_on_drag.csv",
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
    )
    assert "thrust_source=thrust_curve" in source
    assert 'thrust_source=os.path.join(HERE, "Icarus_I_K519.eng")' not in source
    assert f"thrust_curve = {parsed_eng.thrust_curve!r}" in source


def test_launch_override_reaches_the_exported_environment():
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    override = dataclasses.replace(parsed.launch, wind_average_ms=parsed.launch.wind_average_ms + 50.0, wind_direction_deg=parsed.launch.wind_direction_deg)
    _, source_default = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "e.eng", "a.csv", "b.csv", DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
    )
    _, source_override = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "e.eng", "a.csv", "b.csv", DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
        launch_override=override,
    )
    assert source_default != source_override, "a drastically different wind override should change the generated script's own add_wind_gust call"
    assert "real launch-day weather" in source_override


def test_motor_dry_mass_override_is_baked_in():
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    h = parsed_eng.header
    baseline_dry = h.total_mass_kg - h.propellant_mass_kg
    corrected = baseline_dry * 1.5
    _, source = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "e.eng", "a.csv", "b.csv", DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
        motor_dry_override_kg=corrected,
    )
    assert repr(float(corrected)) in source
    assert "measured override" in source


def test_reefed_parachute_generates_two_add_parachute_calls():
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    chute = parsed.parachutes[0]
    reefed = dataclasses.replace(chute, is_reefed=True, reefed_cd=0.3, reefed_diameter_m=0.5, cutter_altitude_m=250.0, cutter_delay_s=0.0)
    parsed.parachutes = [reefed]
    _, source = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "e.eng", "a.csv", "b.csv", DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
    )
    assert source.count("rocket.add_parachute(") == 2, "a reefed main + line cutter should produce TWO rocketpy Parachutes (reefed stage + full stage), same as translate.build_rocket()"
    assert "(reefed)" in source and "(full)" in source


def test_duplicate_trigger_lag_is_deduped_in_generated_script():
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    chute_a = parsed.parachutes[0]
    chute_b = dataclasses.replace(chute_a, name=chute_a.name + " (duplicate)")
    parsed.parachutes = [chute_a, chute_b]
    _, source = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "e.eng", "a.csv", "b.csv", DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
    )
    lags = re.findall(r"lag=([\d.eE+-]+)\)", source)
    assert len(lags) == 2
    assert lags[0] != lags[1], f"two parachutes with the identical (trigger, lag) should get nudged apart to avoid rocketpy's own duplicate-timestamp crash, got {lags}"


def test_drogue_only_and_main_at_apogee_cases_are_actually_generated():
    """A real dual-deploy vehicle (drogue apogee-triggered, main at a
    lower altitude) must produce REAL single-chute DrogueOnly/
    MainAtApogee scripts, not a silent Ballistic-equivalent mislabeled
    with the wrong case name."""
    os.makedirs(OUT_DIR, exist_ok=True)
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common(DUAL_ORK_PATH)
    zip_path = os.path.join(OUT_DIR, "test_dual_deploy.zip")
    lasc_package.build_lasc_zip(
        zip_path, "44", parsed, parsed_eng, ENG_PATH, DUAL_ORK_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        cases=[("Ballistic", False), ("Nominal", True), ("DrogueOnly", True), ("MainAtApogee", True)],
        eng_filename="Icarus_I_K519.eng", ork_filename="Dual_parachute_deployment.ork",
    )
    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        drogue_only_name = next(n for n in names if "DrogueOnly" in n)
        main_apogee_name = next(n for n in names if "MainAtApogee" in n)
        drogue_source = zf.read(drogue_only_name).decode("utf-8")
        main_source = zf.read(main_apogee_name).decode("utf-8")

    assert drogue_source.count("rocket.add_parachute(") == 1, "DrogueOnly must add exactly ONE chute"
    assert "Apex 12" in drogue_source, "DrogueOnly should use the apogee-triggered chute (the drogue), not the altitude-triggered one"

    assert main_source.count("rocket.add_parachute(") == 1, "MainAtApogee must add exactly ONE chute"
    assert "Elliptical 12-Gore" in main_source, "MainAtApogee should use the altitude-triggered chute (the main), forced to apogee trigger"
    assert 'trigger="apogee"' in main_source, "MainAtApogee must force an apogee trigger regardless of the chute's own configured deploy altitude"


def test_parachute_name_with_a_double_quote_does_not_break_generated_source():
    """Found while verifying the DrogueOnly fix above:
    Dual_parachute_deployment.ork's real chute is literally named
    'Apex 12" Drouge Parachute' (a normal OpenRocket inches mark) - the
    generated script used to embed names inside a hand-wrapped '"..."'
    literal with no escaping, so this ONE real, ordinary component name
    broke EVERY exported script's Python syntax outright. Fixed by using
    repr() instead of hand-quoting."""
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common(DUAL_ORK_PATH)
    assert any('"' in c.name for c in parsed.parachutes), "fixture assumption: a real quote-containing name must be present"
    _, source = case_export.generate_case_script(
        "44", "Nominal", 1, parsed, parsed_eng, "e.eng", "a.csv", "b.csv", DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, include_recovery=True,
    )
    compile(source, "generated_nominal.py", "exec")  # raises SyntaxError if this regresses


def test_mission_id_with_illegal_filename_characters_does_not_break_the_zip_or_case_scripts():
    """2026-10-19 review ("check every bug" audit, task #78): mission_id
    feeds directly into this zip's OWN filename AND every per-case .py
    filename inside it (case_export.py's Mission{mission_id}_... pattern).
    A mission ID like "44/Rev2" (LASC reuses mission numbers across
    revisions - a real, plausible value) contains a literal "/" - a path
    separator that would silently write outside the intended directory
    or get rejected outright on Windows. exports_page.py's build_zip now
    sanitizes mission_id ONCE (via its own _sanitize_filename) before
    passing it in here, so this test proves the SANITIZED value - the
    only value this function is ever actually called with from the real
    app - produces a buildable zip with valid, predictable filenames."""
    from bup_rocketpy.gui.pages.exports_page import _sanitize_filename

    raw_mission_id = '44/Rev "2"'
    safe_mission_id = _sanitize_filename(raw_mission_id)
    assert "/" not in safe_mission_id and '"' not in safe_mission_id

    os.makedirs(OUT_DIR, exist_ok=True)
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    zip_path = os.path.join(OUT_DIR, "test_sanitized_mission_id.zip")
    lasc_package.build_lasc_zip(
        zip_path, safe_mission_id, parsed, parsed_eng, ENG_PATH, ORK_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        cases=[("Ballistic", False), ("Nominal", True)],
        eng_filename="Icarus_I_K519.eng", ork_filename="PrometeoLasc2026.ork",
    )
    assert os.path.exists(zip_path)
    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        case_names = [n for n in names if n.endswith(".py")]
        assert len(case_names) == 2
        for n in case_names:
            assert n == _sanitize_filename(n[:-3]) + ".py", f"generated filename {n!r} contains characters the sanitizer would have stripped"
            assert n.startswith(f"Mission{safe_mission_id}_")


def test_lasc_zip_raises_clear_error_with_no_drag_curve_instead_of_crashing():
    os.makedirs(OUT_DIR, exist_ok=True)
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    zip_path = os.path.join(OUT_DIR, "test_no_drag_curve.zip")
    try:
        lasc_package.build_lasc_zip(
            zip_path, "44", parsed, parsed_eng, ENG_PATH, ORK_PATH, None, None,
            DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
            cases=[("Ballistic", False)],
            eng_filename="Icarus_I_K519.eng", ork_filename="PrometeoLasc2026.ork",
        )
        assert False, "expected a clear ValueError, not a silent success"
    except TypeError:
        assert False, "should raise a clear, actionable ValueError, not a raw TypeError from shutil.copy(None, ...)"
    except ValueError as exc:
        assert "Cd curve" in str(exc) or "drag" in str(exc).lower()
