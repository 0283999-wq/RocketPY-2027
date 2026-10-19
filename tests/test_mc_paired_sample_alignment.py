"""2026-10-19 review ("check every bug" audit, task #78): the "common
random numbers" paired comparison (analysis.drag_comparison and
compare_designs.compare_designs's Monte Carlo diff) used to pair
result_a.apogee_samples[i] against result_b.apogee_samples[i] - but
those lists are COMPACTED (excluded/never-attempted sample indices
dropped, the rest shifted left). If run A excludes a DIFFERENT sample
index than run B (the realistic case: two different designs/drag
curves can have different stability margins, so different tail samples
go unstable), the two compacted lists silently shift out of alignment
from that point on, and the "paired" diff compares unrelated samples.

Fixed by adding MonteCarloResult.apogee_by_sample_index (same data,
NOT compacted - None at any excluded/not-attempted index) and pairing
on that instead, keeping only indices where BOTH runs have a value.

These tests use synthetic MonteCarloResult objects (monkeypatched in
place of a real run_monte_carlo call) because what's under test is the
PAIRING ARITHMETIC itself, not any physical fact about a real rocket -
consistent with CLAUDE.md's "never invent data" rule, which is about
physical/simulation inputs (mass, Cd, thrust...), not synthetic test
fixtures for pure index-alignment logic.
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import analysis, compare_designs, monte_carlo
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_mc_paired_sample_alignment")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _fake_result(apogee_by_sample_index):
    completed = [v for v in apogee_by_sample_index if v is not None]
    return monte_carlo.MonteCarloResult(
        n_completed=len(completed), n_excluded=len(apogee_by_sample_index) - len(completed),
        apogee_samples=completed, apogee_by_sample_index=apogee_by_sample_index,
        apogee_mean=0.0, apogee_p05=0.0, apogee_p95=0.0,
        impact_x_samples=[], impact_y_samples=[], filename="fake",
    )


def test_drag_comparison_pairs_by_true_sample_index_not_compacted_position():
    # A excludes index 1; B excludes index 3 - a DIFFERENT index. The old
    # positional-slice code would pair A's compacted [100, 300, 400, 500]
    # against B's compacted [110, 210, 310, 510] element-by-element
    # (wrongly pairing e.g. A's real sample 2 (300) against B's real
    # sample 1 (110)). The fix must only use indices 0, 2, 4 - the ones
    # where BOTH have a real value.
    a_by_index = [100.0, None, 300.0, 400.0, 500.0]
    b_by_index = [110.0, 210.0, 310.0, None, 510.0]
    expected_pairs = [(100.0, 110.0), (300.0, 310.0), (500.0, 510.0)]  # indices 0, 2, 4
    expected_mean_diff = sum(b - a for a, b in expected_pairs) / len(expected_pairs)

    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    from bup_rocketpy import translate
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1871.3, parsed.launch.wind_average_ms)

    with mock.patch("bup_rocketpy.monte_carlo.run_monte_carlo", side_effect=[_fake_result(a_by_index), _fake_result(b_by_index)]):
        result = analysis.drag_comparison(
            parsed, eng, ENG_PATH, (POWER_OFF_DRAG, POWER_ON_DRAG), (POWER_OFF_DRAG, POWER_ON_DRAG),
            DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, uncertainties, n_simulations=5,
            output_dir=os.path.join(OUT_DIR, "drag_comparison"), seed=1,
        )

    assert result.n_paired == 3, "must pair only the 3 indices where BOTH runs have a real value"
    assert result.mean_difference_m == expected_mean_diff


def test_compare_designs_mc_diff_pairs_by_true_sample_index_not_compacted_position():
    a_by_index = [1000.0, None, 1200.0, 1300.0, 1400.0]
    b_by_index = [1010.0, 1110.0, 1210.0, None, 1410.0]
    expected_pairs = [(1000.0, 1010.0), (1200.0, 1210.0), (1400.0, 1410.0)]
    expected_mean_diff = sum(b - a for a, b in expected_pairs) / len(expected_pairs)

    os.makedirs(OUT_DIR, exist_ok=True)
    with mock.patch("bup_rocketpy.monte_carlo.run_monte_carlo", side_effect=[_fake_result(a_by_index), _fake_result(b_by_index)]):
        result = compare_designs.compare_designs(
            ORK_PATH, ENG_PATH, ORK_PATH, ENG_PATH, outputs_dir=os.path.join(OUT_DIR, "compare"),
            mc_n=5, mc_seed=1,
        )

    assert result.mc_n_paired == 3, "must pair only the 3 indices where BOTH designs have a real value"
    assert result.apogee_mc_diff_mean_m == expected_mean_diff


if __name__ == "__main__":
    test_drag_comparison_pairs_by_true_sample_index_not_compacted_position()
    test_compare_designs_mc_diff_pairs_by_true_sample_index_not_compacted_position()
    print("\nMC PAIRED SAMPLE ALIGNMENT: OK")
