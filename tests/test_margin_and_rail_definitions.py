"""2026-10-09 review item 1: Diego's physics agreement table showed two
real DEFINITION differences, not bugs - "show both definitions, judge
the conservative one":
  - Rail exit velocity: RocketPy fires when the UPPER rail button clears
    the rail; OpenRocket uses the full rod length.
  - Stability: OpenRocket's own minimum (1.67 cal) was lower than ours
    (2.17 cal, "static margin, Mach 0") - show both "static margin
    (Mach 0)" and "stability incl. Mach effects", judge FLT 4.3.5 on
    whichever is lower.

Uses PROMETEO's real .ork (no invented rocket).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import openrocket_comparison, rcsm, rcsm_cases
from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_margin_and_rail_definitions")


def _load_and_sim():
    os.makedirs(OUT_DIR, exist_ok=True)
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR)
    return lr, sim


def test_mach0_margin_is_a_real_separate_number_from_the_mach_varying_one():
    lr, sim = _load_and_sim()
    assert sim.min_static_margin_mach0_cal is not None
    assert sim.max_static_margin_mach0_cal is not None
    # For a real, non-trivial supersonic-adjacent flight (Mach ~0.79 for
    # PROMETEO) the two models should differ measurably - if they were
    # byte-identical, the Mach-0 computation would be a no-op bug, not a
    # genuine cross-check.
    assert sim.min_static_margin_mach0_cal != sim.min_static_margin_cal


def test_is_stable_uses_the_conservative_combination_of_both_margins():
    lr, sim = _load_and_sim()
    conservative_min = min(sim.min_static_margin_cal, sim.min_static_margin_mach0_cal)
    conservative_max = max(sim.max_static_margin_cal, sim.max_static_margin_mach0_cal)
    expected = 1.5 <= conservative_min and conservative_max <= 4.0
    assert sim.is_stable == expected


def test_rcsm_compliance_detail_shows_both_margin_numbers():
    lr, sim = _load_and_sim()
    cases = rcsm_cases.run_all_cases(lr.parsed_ork, lr.parsed_eng, lr.eng_path, lr.power_off_drag_path, lr.power_on_drag_path, sim.dry_mass_kg, sim.dry_cg_m)
    nominal = cases["Nominal"]
    rows = rcsm.check_compliance(rcsm.CATEGORIES["3km_solid"], nominal.flight, nominal.flight.rocket, payload_mass_kg=4.0)
    margin_row = next(r for r in rows if r[0] == "FLT 4.3.5")
    assert "Mach-varying" in margin_row[3]
    assert "Mach 0" in margin_row[3]


def test_flt_4_3_6_checks_static_and_dynamic_margin_against_their_own_ceilings():
    """2026-10-19 review ("check every bug" audit, task #78): FLT 4.3.6
    is TWO conditions (docs/rcsm_reference.md: "static margin <4 cal,
    dynamic margin <6 cal") - rcsm.MAX_DYNAMIC_MARGIN_CAL (6.0) used to
    be defined but never referenced; the old code folded the Mach-0 and
    Mach-varying numbers into one `conservative_max` and judged BOTH
    against the stricter 4 cal static ceiling, which would wrongly FAIL
    a vehicle whose in-flight (Mach-varying) margin legitimately rose
    above 4 cal but stayed under the real 6 cal dynamic ceiling. Now two
    separate FLT 4.3.6 rows exist, each checked against its own ceiling."""
    lr, sim = _load_and_sim()
    cases = rcsm_cases.run_all_cases(lr.parsed_ork, lr.parsed_eng, lr.eng_path, lr.power_off_drag_path, lr.power_on_drag_path, sim.dry_mass_kg, sim.dry_cg_m)
    nominal = cases["Nominal"]
    flight = nominal.flight
    ascent_times = [t for t in flight.time if flight.out_of_rail_time <= t <= flight.apogee_time]
    max_margin = max(flight.stability_margin(t) for t in ascent_times)
    max_margin_mach0 = max(flight.rocket.stability_margin(0, t) for t in ascent_times)

    rows = rcsm.check_compliance(rcsm.CATEGORIES["3km_solid"], flight, flight.rocket, payload_mass_kg=4.0)
    margin_436_rows = [r for r in rows if r[0] == "FLT 4.3.6"]
    assert len(margin_436_rows) == 2, "FLT 4.3.6 must report both its static and dynamic conditions as separate rows"

    static_row = next(r for r in margin_436_rows if "static" in r[1])
    dynamic_row = next(r for r in margin_436_rows if "dynamic" in r[1])
    assert static_row[2] == ("PASS" if max_margin_mach0 < rcsm.MAX_STATIC_MARGIN_CAL else "FAIL")
    assert dynamic_row[2] == ("PASS" if max_margin < rcsm.MAX_DYNAMIC_MARGIN_CAL else "FAIL")
    assert f"{max_margin_mach0:.2f}" in static_row[3]
    assert f"{max_margin:.2f}" in dynamic_row[3]


def test_openrocket_comparison_includes_a_rail_exit_velocity_row_with_both_numbers():
    lr, sim = _load_and_sim()
    sim_name, rows = openrocket_comparison.compare_to_openrocket(lr.parsed_ork, sim, ORK_PATH)
    rail_row = next((r for r in rows if r.label == "Rail exit velocity"), None)
    assert rail_row is not None, "no Rail exit velocity row in the OpenRocket comparison table"
    assert rail_row.ours == sim.rail_exit_velocity_ms
    assert rail_row.openrocket is not None  # PROMETEO's stored sim has launchrodvelocity
    assert "definition" in rail_row.note.lower()
    # A real difference in definition must never render as a red "FAIL"
    # chip - that would read as "go fix this", which is wrong here.
    assert rail_row.over_threshold == False  # noqa: E712 - pct_diff/over_threshold can come back as np.bool_, "is False" fails on that


if __name__ == "__main__":
    test_mach0_margin_is_a_real_separate_number_from_the_mach_varying_one()
    test_is_stable_uses_the_conservative_combination_of_both_margins()
    test_rcsm_compliance_detail_shows_both_margin_numbers()
    test_openrocket_comparison_includes_a_rail_exit_velocity_row_with_both_numbers()
    print("\nMARGIN AND RAIL DEFINITIONS: OK")
