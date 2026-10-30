"""Demo-day fix 2: a Monte Carlo run where EVERY sample fails with the same
exception must stop after a handful of samples and say why, instead of
grinding through hundreds ("Done: 0 completed, 338 excluded" with no cause).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import monte_carlo, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_mc_failure_abort")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def test_same_failure_repeating_stops_the_run_and_names_the_cause():
    os.makedirs(OUT_DIR, exist_ok=True)
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test"))
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1855.9, parsed.launch.wind_average_ms)
    missing = os.path.join(OUT_DIR, "does_not_exist.csv")  # every sample fails identically: drag file not found

    result = monte_carlo.run_monte_carlo(
        parsed, eng, ENG_PATH, missing, missing, DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        uncertainties, n_simulations=60, output_dir=OUT_DIR, max_workers=2, seed=1,
    )

    assert result.n_completed == 0
    assert result.aborted_message, "the run must say it stopped itself and why"
    assert "5 samples in a row" in result.aborted_message
    assert result.cancelled is True
    assert result.n_excluded < 60, "it must NOT keep running every sample once the same error repeats"
    assert sum(result.exclusion_by_reason.values()) == result.n_excluded
    assert all(":" in reason or reason for reason in result.exclusion_by_reason)
    assert result.first_traceback
