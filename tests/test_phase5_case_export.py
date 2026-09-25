"""Phase 5 (CLAUDE.md Sec 6, Phase 5 + Sec 5's "Design consequence"):
Ballistic + Nominal cases, exported as self-contained per-case .py files
named per CRS 10.1.6 (Mission[ID]_[Case]_RocketPy_v[N]), each run in a
CLEAN venv (no bup_rocketpy on the path) and its apogee compared to the
app's own in-process result - proving the exported file is what it claims
to be: runnable with nothing but `pip install rocketpy`.
"""
import os
import subprocess
import sys
import venv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import case_export, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_phase5_case_export")

# Known-good manual override (config.py's independently-verified dry
# mass/CG) - see Phase 1's documented gap in the .ork's own geometric
# estimate. Real submission scripts need this fixed via a real overridecg.
DRY_MASS_KG = 5.6622
DRY_CG_M = 0.6279

CASES = [("Ballistic", False), ("Nominal", True)]


def _build_common():
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "manual override, see test docstring")
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    return parsed, parsed_eng, mass_est, i_axial, i_transverse, radius_m


def _run_in_process(parsed, parsed_eng, mass_est, i_axial, i_transverse, radius_m, include_recovery):
    from rocketpy import Flight

    motor = translate.build_motor(parsed_eng, ENG_PATH)
    rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG, include_recovery=include_recovery)
    env = translate.build_environment(parsed.launch)
    flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m,
                     inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg,
                     terminate_on_apogee=True)
    return flight.apogee - env.elevation


def test_exported_scripts_match_the_apps_own_apogee_in_a_clean_venv():
    """This is the actual CLAUDE.md requirement: 'Add an automated test
    that runs each exported .py in a clean environment and compares its
    apogee to the app's.' Building one clean venv and reusing it for both
    cases (not one per case) to keep this from becoming the slowest test
    in the suite - rocketpy's own install is the expensive part, not the
    case count."""
    os.makedirs(OUT_DIR, exist_ok=True)
    parsed, parsed_eng, mass_est, i_axial, i_transverse, radius_m = _build_common()

    import shutil
    shutil.copy(ENG_PATH, os.path.join(OUT_DIR, os.path.basename(ENG_PATH)))
    shutil.copy(POWER_OFF_DRAG, os.path.join(OUT_DIR, "power_off_drag.csv"))
    shutil.copy(POWER_ON_DRAG, os.path.join(OUT_DIR, "power_on_drag.csv"))

    clean_venv_dir = os.path.join(OUT_DIR, "clean_venv")
    if not os.path.exists(clean_venv_dir):
        print(f"\nBuilding clean venv at {clean_venv_dir} (rocketpy install, this is the slow part)...")
        venv.EnvBuilder(with_pip=True).create(clean_venv_dir)
        clean_python = os.path.join(clean_venv_dir, "bin", "python3")
        subprocess.run([clean_python, "-m", "pip", "install", "-q", "rocketpy==1.13.0"], check=True, timeout=300)
    clean_python = os.path.join(clean_venv_dir, "bin", "python3")

    for case_name, include_recovery in CASES:
        in_process_apogee = _run_in_process(parsed, parsed_eng, mass_est, i_axial, i_transverse, radius_m, include_recovery)

        filename, source = case_export.generate_case_script(
            mission_id="44", case_name=case_name, version=1,
            parsed=parsed, parsed_eng=parsed_eng,
            eng_filename=os.path.basename(ENG_PATH),
            power_off_drag_filename="power_off_drag.csv", power_on_drag_filename="power_on_drag.csv",
            dry_mass_kg=DRY_MASS_KG, dry_cg_m=DRY_CG_M,
            i_axial=i_axial, i_transverse=i_transverse, radius_m=radius_m,
            include_recovery=include_recovery,
        )
        script_path = os.path.join(OUT_DIR, filename)
        with open(script_path, "w") as f:
            f.write(source)

        assert filename == f"Mission44_{case_name}_RocketPy_v1.py", "CRS 10.1.6 naming: Mission[ID]_[Case]_RocketPy_v[N]"
        assert "bup_rocketpy" not in source, "exported script must NOT import this repo - CRS 10.1.5 needs it runnable standalone"

        proc = subprocess.run([clean_python, script_path], capture_output=True, text=True, timeout=120, cwd=OUT_DIR)
        print(f"\n=== {filename} (clean venv) ===")
        print(proc.stdout[-1500:])
        if proc.returncode != 0:
            print(proc.stderr[-3000:])
        assert proc.returncode == 0, f"{filename} failed to run standalone in a clean venv"

        exported_apogee = None
        for line in proc.stdout.splitlines():
            if line.startswith("Apogee AGL:"):
                exported_apogee = float(line.split(":")[1].strip().split()[0])
        assert exported_apogee is not None, f"{filename} did not print its apogee - can't compare"

        diff_pct = abs(exported_apogee - in_process_apogee) / in_process_apogee * 100
        print(f"{case_name}: in-process apogee={in_process_apogee:.2f} m, exported-script apogee={exported_apogee:.2f} m, diff={diff_pct:.4f}%")
        assert diff_pct < 0.5, f"{filename}'s standalone result should match the app's own to well under 1% (both are the same physics, same inputs) - {diff_pct:.2f}% is too much drift"


if __name__ == "__main__":
    test_exported_scripts_match_the_apps_own_apogee_in_a_clean_venv()
    print("\nPHASE 5 CASE EXPORT: CLEAN-VENV MATCH CONFIRMED")
