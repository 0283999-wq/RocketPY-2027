"""Phase 4: Monte Carlo + landing ellipse (2026-09-26 review, item 3).

Also documents 3 real bugs found in rocketpy==1.13.0's own Stochastic
subsystem (explicitly marked "still under testing" in its own warning)
while building this - none of them are in bup_rocketpy's code, all
worked around in bup_rocketpy/monte_carlo.py with comments at each site:

1. MonteCarlo.simulate()'s default export_list includes 'apogee_y', which
   does not exist on Flight (AttributeError, 100% of the time on ANY
   flight - not specific to this rocket). Worked around by not using
   MonteCarlo.simulate() at all.
2. StochasticRocket.create_object() does not preserve an overridden
   center_of_mass_without_motor unless it is ALSO passed explicitly to
   the StochasticRocket constructor (it silently is not "kept as nominal"
   - it's dropped).
3. StochasticRocket.add_nose()/add_trapezoidal_fins() crash
   (TypeError: unexpected keyword 'component') when given a plain
   NoseCone/TrapezoidalFins, because of a real internal mismatch between
   that method and StochasticNoseCone/StochasticTrapezoidalFins's actual
   constructor kwarg names (`nosecone=`/`trapezoidal_fins=`, not
   `component=`). Worked around by pre-building the Stochastic* wrapper
   ourselves and passing that in instead (hits the method's other,
   working code path).

Bug #2 was the most consequential to catch: without it, every sampled
rocket came out with NO aerosurfaces attached at all (cp_position()==0),
so bug #3's masking effect combined with #2 produced a consistent
~-8.5 cal "instability" that had nothing to do with any of the actual
input uncertainties - it would have been very easy to misdiagnose as
"the uncertainties are too wide" rather than "the aerosurfaces never got
attached to the sampled rocket in the first place".
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
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_phase4_monte_carlo")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279  # config.py's independently-verified numbers, see Phase 1 notes


def test_monte_carlo_produces_a_sane_apogee_distribution_with_no_excluded_samples():
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)

    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)
    result = monte_carlo.run_monte_carlo(
        parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        uncertainties, n_simulations=20, output_dir=OUT_DIR, include_recovery=True,
    )
    print(f"\nn_completed={result.n_completed}, n_excluded={result.n_excluded}")
    print(f"apogee: mean={result.apogee_mean:.1f} m, 90% interval [{result.apogee_p05:.1f}, {result.apogee_p95:.1f}] m")

    assert result.n_completed == 20, f"expected all 20 samples to succeed with the standard uncertainty set, got {result.n_completed} ({result.exclusion_reasons})"
    assert result.n_excluded == 0
    assert 800 < result.apogee_mean < 1600, "apogee mean is not in a plausible range"
    spread_pct = (result.apogee_p95 - result.apogee_p05) / result.apogee_mean * 100
    assert 2 < spread_pct < 30, f"90% interval spread ({spread_pct:.1f}% of mean) looks implausible - either uncertainties collapsed to ~0 or something is blowing up"

    ellipses = monte_carlo.landing_ellipses(result)
    assert set(ellipses.keys()) == {1, 2, 3}
    assert ellipses[3]["width"] > ellipses[2]["width"] > ellipses[1]["width"] > 0, "sigma ellipses should nest (3-sigma widest)"


def test_on_sample_complete_fires_once_per_sample_with_a_decimated_trajectory():
    """2026-09-27 review item 7: the live Monte Carlo 3D view needs each
    completed sample's own trajectory/landing point AS IT FINISHES, not
    just the batch's final arrays."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    calls = []

    def on_sample_complete(trajectory, x_impact, y_impact):
        calls.append((trajectory, x_impact, y_impact))

    result = monte_carlo.run_monte_carlo(
        parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        uncertainties, n_simulations=6, output_dir=OUT_DIR, include_recovery=True,
        on_sample_complete=on_sample_complete, trajectory_points=15,
    )
    assert len(calls) == result.n_completed
    for trajectory, x_impact, y_impact in calls:
        assert trajectory is not None and len(trajectory) == 15
        assert all(len(p) == 3 for p in trajectory), "each trajectory point must be [x, y, z-AGL]"
        assert x_impact is not None and y_impact is not None


def test_cancel_check_stops_early_and_keeps_partial_results():
    """2026-09-26 review, item 7 (Monte Carlo background+cancel): a
    cancelled run must save whatever samples it already completed, not
    throw them away. N=5 per budget-mode test guidance."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    calls = {"n": 0}

    def cancel_after_2(*_a, **_kw):
        calls["n"] += 1
        return calls["n"] >= 2

    result = monte_carlo.run_monte_carlo(
        parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius,
        uncertainties, n_simulations=5, output_dir=OUT_DIR, include_recovery=True,
        cancel_check=lambda: cancel_after_2(),
    )
    print(f"\ncancelled={result.cancelled}, n_completed={result.n_completed}")
    assert result.cancelled is True
    assert result.n_completed + result.n_excluded == 2, "cancel_check returning True on its 2nd call should stop after exactly 2 samples"
    assert result.n_completed > 0, "the 2 completed-before-cancel samples must still be in the result, not discarded"


def test_inclination_and_heading_override_shift_the_landing_ellipse():
    """2026-09-26 review item E: the operator can set the rail
    heading/inclination they actually plan to use on launch day, rather
    than being stuck with whatever the .ork's saved simulation recorded.
    A large heading change (same inclination) must move the mean landing
    point - if the override were silently ignored, both runs would land
    in the same place (same seed => same random offsets, only the
    override differs)."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    kwargs = dict(
        parsed=parsed, parsed_eng=eng, eng_path=ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        dry_mass_kg=DRY_MASS_KG, dry_cg_m=DRY_CG_M, i_axial=i_ax, i_transverse=i_tr, radius_m=radius,
        uncertainties=uncertainties, n_simulations=5, output_dir=OUT_DIR, include_recovery=True, seed=42,
    )
    baseline = monte_carlo.run_monte_carlo(**kwargs, inclination_deg=parsed.launch.inclination_deg, heading_deg=parsed.launch.rail_direction_deg)
    rotated = monte_carlo.run_monte_carlo(**kwargs, inclination_deg=parsed.launch.inclination_deg, heading_deg=parsed.launch.rail_direction_deg + 180)

    dx = rotated.impact_x_samples[0] - baseline.impact_x_samples[0]
    dy = rotated.impact_y_samples[0] - baseline.impact_y_samples[0]
    assert (dx ** 2 + dy ** 2) ** 0.5 > 50, "a 180deg heading override should move the landing point substantially, not leave it unchanged"


if __name__ == "__main__":
    test_monte_carlo_produces_a_sane_apogee_distribution_with_no_excluded_samples()
    test_cancel_check_stops_early_and_keeps_partial_results()
    test_inclination_and_heading_override_shift_the_landing_ellipse()
    print("\nPHASE 4 MONTE CARLO: OK")
