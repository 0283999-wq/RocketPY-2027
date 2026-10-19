"""2026-10-19 review ("check every bug" audit, finding #5 of the ork_
reader/translate/barrowman report): translate.py's _fin_set_mass_cg used
a closed-form trapezoid centroid formula that was mathematically wrong
for any TAPERED fin (root_chord != tip_chord) - only exactly correct in
the two edge cases (untapered, or a pure triangle). Verified independently
via the shoelace polygon centroid formula (already used and tested for
freeform fins in this same file) before trusting the audit's claim.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.ork_reader import FinSet


def _old_wrong_xbar(rc, tc, sw):
    """The PREVIOUS (buggy) closed-form formula, kept here ONLY to prove
    the new code no longer matches it for a tapered fin."""
    return sw * (2 * tc + rc) / (3 * (rc + tc)) + rc * (rc + 2 * tc) / (3 * (rc + tc))


def test_tapered_fin_centroid_matches_polygon_ground_truth_not_the_old_formula():
    rc, tc, sw, span = 0.15, 0.05, 0.03, 0.14
    outline = [(0.0, 0.0), (sw, span), (sw + tc, span), (rc, 0.0)]
    _, correct_xbar = translate._polygon_area_and_centroid_x(outline)
    old_xbar = _old_wrong_xbar(rc, tc, sw)

    assert abs(correct_xbar - 0.0667) < 0.001, f"expected the known-correct centroid ~0.0667 m, got {correct_xbar}"
    assert abs(old_xbar - 0.075) < 0.001, f"sanity: the OLD formula should give 0.075 m for these numbers, got {old_xbar}"
    pct_diff = abs(correct_xbar - old_xbar) / correct_xbar * 100
    assert pct_diff > 10, f"the old formula's error for this real taper should be >10%, was {pct_diff:.1f}%"

    fin = FinSet(name="test", count=4, root_chord=rc, tip_chord=tc, span=span, sweep_length=sw, thickness=0.003, cant_angle=0.0, position_m=1.0, material_density=1850.0)
    mass, cg, _, _ = translate._fin_set_mass_cg(fin, body_radius=0.0548)
    actual_xbar = cg - fin.position_m
    assert abs(actual_xbar - correct_xbar) < 1e-9, f"_fin_set_mass_cg should now use the polygon-correct centroid ({correct_xbar}), got {actual_xbar}"


def test_untapered_and_triangle_edge_cases_unchanged():
    """The old formula was only EVER correct in these two edge cases -
    confirm the new polygon-based path still agrees with them (no
    regression for the cases that were already right)."""
    span = 0.14

    # Untapered (rectangular) fin: rc == tc, sweep 0 -> centroid at rc/2.
    rc = tc = 0.12
    outline = [(0.0, 0.0), (0.0, span), (tc, span), (rc, 0.0)]
    _, xbar = translate._polygon_area_and_centroid_x(outline)
    assert abs(xbar - rc / 2.0) < 1e-6

    # Pure triangle: tc == 0.
    rc, tc, sw = 0.2, 0.0, 0.05
    outline = [(0.0, 0.0), (sw, span), (sw + tc, span), (rc, 0.0)]
    _, xbar_tri = translate._polygon_area_and_centroid_x(outline)
    old_tri = _old_wrong_xbar(rc, tc, sw)
    assert abs(xbar_tri - old_tri) < 1e-6, "the two formulas should agree for a pure-triangle fin (tc=0) - this was already a correct edge case"


def test_fin_cg_moves_toward_root_for_a_real_tapered_fin_vs_old_formula():
    """End-to-end sanity: for PROMETEO's own real fin taper (root=0.2,
    tip=0.1, sweep~0.17), the corrected CG should sit CLOSER to the root
    leading edge (smaller x_bar) than the old formula claimed - fixing an
    overestimate, not introducing a new one in a random direction."""
    rc, tc, sw, span = 0.2, 0.1, 0.17000000000000007, 0.14
    fin = FinSet(name="Aletas trapezoidales", count=4, root_chord=rc, tip_chord=tc, span=span, sweep_length=sw, thickness=0.003, cant_angle=0.0, position_m=0.0, material_density=1850.0)
    _, cg, _, _ = translate._fin_set_mass_cg(fin, body_radius=0.0548)
    old_xbar = _old_wrong_xbar(rc, tc, sw)
    assert cg < old_xbar, f"corrected fin CG ({cg}) should be closer to the root than the old formula's {old_xbar}"
