"""2026-10-19 review ("check every bug" audit, finding #3 of the
pipeline/MC/compare_designs report): monte_carlo.py's StochasticEnvironment
only ever randomized wind_velocity_x_factor - wind_velocity_y_factor was
never set (rocketpy's own default (1, 0), i.e. zero dispersion), so a
real wind-speed uncertainty only ever perturbed whichever axis the
deterministic wind happened to be aligned with. The landing-ellipse Monte
Carlo therefore under-dispersed and was direction-blind relative to the
declared uncertainty. Fixed by applying the SAME wind-speed-derived
factor to both axes (StochasticEnvironment samples each independently,
so this also restores real directional dispersion as a side effect).
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import monte_carlo, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")


def test_wind_velocity_y_factor_is_set_from_the_same_uncertainty_as_x():
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(5.6622, 0.6279, "test")
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(5.6622, 1800.0, 3.0)
    u = {unc.name: unc for unc in uncertainties if unc.enabled}

    with mock.patch("bup_rocketpy.monte_carlo.StochasticEnvironment", wraps=monte_carlo.StochasticEnvironment) as spy:
        monte_carlo._run_one_mc_sample(
            parsed, parsed_eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
            5.6622, 0.6279, i_axial, i_transverse, radius_m,
            u, include_recovery=True, sample_seed=None,
        )
        assert spy.call_count == 1
        _, kwargs = spy.call_args
        x_factor = kwargs["wind_velocity_x_factor"]
        y_factor = kwargs["wind_velocity_y_factor"]
        assert y_factor == x_factor, f"wind_velocity_y_factor should be set to the SAME wind-speed-derived factor as x, got x={x_factor} y={y_factor}"
        assert y_factor != (1, 0), "y_factor must not be left at rocketpy's own zero-dispersion default"
        assert y_factor[1] > 0, "the std_dev component of the wind factor should be strictly positive when wind_speed_ms is an enabled uncertainty"


def test_wind_direction_source_string_is_honest_about_the_real_limitation():
    uncertainties = monte_carlo.default_uncertainties(5.6622, 1800.0, 3.0)
    wind_dir = next(u for u in uncertainties if u.name == "wind_direction_deg")
    assert "no effect" in wind_dir.source.lower() or "not currently modeled" in wind_dir.source.lower(), f"this field is genuinely inert (no rocketpy mechanism exists for it) - its own source string must say so, not read like an ordinary 'low confidence, guessed' value, got: {wind_dir.source!r}"
