"""Phase 4: Monte Carlo + landing ellipse (2026-09-26 review, item 3).

Also documents 3 real bugs found in rocketpy==1.13.0's own Stochastic
subsystem (explicitly marked "still under testing" in its own warning)
while building this - none of them are in stella_flight's code, all
worked around in stella_flight/monte_carlo.py with comments at each site:

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

from stella_flight import monte_carlo, translate
from stella_flight.motor_reader import read_eng
from stella_flight.ork_reader import read_ork

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


if __name__ == "__main__":
    test_monte_carlo_produces_a_sane_apogee_distribution_with_no_excluded_samples()
    print("\nPHASE 4 MONTE CARLO: OK")
