"""Helper script (NOT collected by pytest - no test_ prefix) run as a
FRESH subprocess by test_windows_spawn_monte_carlo.py, with multiprocessing
forced to "spawn" (Windows' only start method - Linux defaults to "fork",
which is why this project's own test suite never caught the "0 completed,
300 excluded" bug Diego hit on Windows) and PYTHONHASHSEED left to the
interpreter's own randomization (never fixed), matching Diego's own
reproduction recipe (2026-09-30 review, Windows bug 1). Runs in its own
process so forcing the start method here can never leak into the rest of
the pytest session's (fork-based) tests.

Prints one line of JSON: {"n_completed": int, "n_excluded": int,
"exclusion_reasons": [...], "first_traceback": str}. sys.argv[1] selects
"plain" (PROMETEO, no overrides) or "reefed" (same rocket, main chute
marked reefed with a line cutter).
"""
import dataclasses
import json
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)

    from bup_rocketpy import monte_carlo, translate
    from bup_rocketpy.motor_reader import read_eng
    from bup_rocketpy.ork_reader import read_ork

    REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
    ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
    POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
    POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
    OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_windows_spawn_monte_carlo")
    DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279

    mode = sys.argv[1] if len(sys.argv) > 1 else "plain"

    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    if mode == "reefed":
        chute = parsed.parachutes[0]
        parsed = dataclasses.replace(parsed, parachutes=[dataclasses.replace(
            chute, is_reefed=True, reefed_diameter_m=0.7, reefed_cd=chute.cd,
            cutter_altitude_m=500.0, cutter_delay_s=0.5,
        )])

    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    motor = translate.build_motor(eng, ENG_PATH)
    result = monte_carlo.run_monte_carlo(
        parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        uncertainties, n_simulations=5, output_dir=OUT_DIR, include_recovery=True,
        motor_dry_override_kg=motor.dry_mass,
    )
    print(json.dumps({
        "n_completed": result.n_completed,
        "n_excluded": result.n_excluded,
        "exclusion_reasons": result.exclusion_reasons,
        "exclusion_by_type": result.exclusion_by_type,
        "first_traceback": result.first_traceback,
    }))
