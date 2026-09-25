"""Phase 6: weathercocking sweep and drag comparison (2026-09-26 review,
item 3). The drag comparison also documents a 4th real rocketpy==1.13.0
bug found while building this: none of the Stochastic* classes forward a
`seed=` kwarg to their base class despite the base class supporting one,
AND setting the resulting object's private RNG attribute after
construction doesn't work either (the per-attribute sampler is already a
bound method of the OLD generator by the time you could intervene). The
only working fix is monkeypatching numpy.random.default_rng for the
narrow scope of the 4 Stochastic* constructor calls - see
stella_flight.monte_carlo._seeded_rng.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stella_flight import analysis, monte_carlo, translate
from stella_flight.motor_reader import read_eng
from stella_flight.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_phase6_analysis")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def test_weathercocking_sweep_finds_the_lower_bound_for_prometeo():
    """PROMETEO's nominal (no-ballast) margin is already 2.54 cal, above
    the 1.5 cal floor - adding ballast only INCREASES margin (moving CG
    forward), so the apogee-optimal point should be the no-ballast case
    itself, and the sweep should say so (CLAUDE.md Sec 6: "it will
    probably land on the lower bound, and the app must say so")."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)

    result = analysis.weathercocking_sweep(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius)
    print()
    for p in result.points:
        print(f"ballast={p.ballast_mass_kg:.2f}kg margin={p.static_margin_cal:.2f}cal apogee={p.apogee_agl_m:.1f}m in_range={p.in_valid_range}")
    print(f"best: ballast={result.best_point.ballast_mass_kg}, margin={result.best_point.static_margin_cal:.2f} cal, apogee={result.best_point.apogee_agl_m:.1f} m")
    print(f"hit_lower_bound: {result.hit_lower_bound}")

    assert all(1.0 < p.static_margin_cal < 5.0 for p in result.points), "static margins are not in a plausible range"
    assert result.best_point is not None
    assert result.best_point.ballast_mass_kg == 0.0, "expected the no-ballast case to be optimal for this vehicle"
    assert result.hit_lower_bound, "should report landing on the lower bound, per CLAUDE.md Sec 6"


def test_drag_comparison_with_identical_curves_gives_zero_difference():
    """The strongest proof the common-random-numbers seeding actually
    works: comparing a curve against ITSELF must give exactly 0
    difference (both sides draw the identical random sequence)."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    result = analysis.drag_comparison(parsed, eng, ENG_PATH, (POWER_OFF_DRAG, POWER_ON_DRAG), (POWER_OFF_DRAG, POWER_ON_DRAG),
                                       DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, uncertainties, n_simulations=6, output_dir=os.path.join(OUT_DIR, "identical"), seed=42)
    print(f"\nidentical-curve comparison: mean_diff={result.mean_difference_m}, CI={result.difference_ci_90}")
    assert result.mean_difference_m == 0.0
    assert result.difference_ci_90 == (0.0, 0.0)


def test_drag_comparison_with_different_curves_gives_a_real_difference():
    """A curve with 15% higher Cd should produce a meaningfully lower
    apogee, with a tight enough CI (thanks to common random numbers) to
    exclude zero - i.e. "the difference is real" (CLAUDE.md Sec 6's own
    example wording)."""
    import csv

    scaled_off = os.path.join(OUT_DIR, "power_off_scaled.csv")
    scaled_on = os.path.join(OUT_DIR, "power_on_scaled.csv")
    os.makedirs(OUT_DIR, exist_ok=True)
    for src, dst in [(POWER_OFF_DRAG, scaled_off), (POWER_ON_DRAG, scaled_on)]:
        with open(src) as f_in, open(dst, "w") as f_out:
            for line in f_in:
                mach, cd = line.strip().split(",")
                f_out.write(f"{mach},{float(cd) * 1.15}\n")

    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    result = analysis.drag_comparison(parsed, eng, ENG_PATH, (POWER_OFF_DRAG, POWER_ON_DRAG), (scaled_off, scaled_on),
                                       DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, uncertainties, n_simulations=10, output_dir=os.path.join(OUT_DIR, "different"), seed=42)
    print(f"\n15%-higher-Cd comparison: mean_diff={result.mean_difference_m:.1f} m, 90% CI={result.difference_ci_90}")
    assert result.mean_difference_m < -10, "higher drag should meaningfully lower apogee"
    assert result.difference_ci_90[1] < 0, "the 90% CI should exclude zero - this is what makes the difference 'real', not noise"


if __name__ == "__main__":
    test_weathercocking_sweep_finds_the_lower_bound_for_prometeo()
    test_drag_comparison_with_identical_curves_gives_zero_difference()
    test_drag_comparison_with_different_curves_gives_a_real_difference()
    print("\nPHASE 6 ANALYSIS: OK")
