"""2026-10-19 review: "a new page dedicated on the calculations... for
me to check them at hand." calculations_page.py is a thin rendering
layer over functions that already have their own test coverage
(barrowman.py, flutter.py, recovery.py, translate.component_table) - this
file exercises the SAME data-gathering calls the page itself makes, for
two real, checked-in rockets (one with rail buttons parsed, one without),
to catch a crash or a None-handling bug in the page's own glue code
without needing a full browser test for every formula.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import barrowman, flutter, recovery, translate
from bup_rocketpy.gui import pipeline
from bup_rocketpy.ork_reader import airframe_length_m

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PROMETEO = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
ORK_DUAL = os.path.join(REPO_ROOT, "reference", "openrocket_examples", "Dual_parachute_deployment.ork")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs", "test_calculations_page")


def _run(ork_path, eng_path):
    lr = pipeline.load_files(ork_path, eng_path, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(lr, OUTPUTS_DIR)
    return lr, sim


def test_all_calculations_sections_resolve_without_crashing_prometeo():
    """PROMETEO's real .ork has NO parsed rail buttons - the rail exit
    velocity section must degrade to an honest 'not available' message,
    not crash with an AttributeError on None.rail_buttons.upper_position_m
    or similar."""
    lr, sim = _run(ORK_PROMETEO, ENG_PATH)
    parsed = lr.parsed_ork
    flight = sim.flight
    rocket = flight.rocket
    env = flight.env

    assert parsed.rail_buttons is None  # the exact condition the page must handle gracefully

    rows = translate.component_table(parsed)
    countable = [r for r in rows if r.mass_kg is not None and r.position_m is not None]
    assert countable
    total_mass = sum(r.mass_kg for r in countable)
    assert abs(total_mass - sim.dry_mass_kg) / sim.dry_mass_kg < 0.05  # the hand-summed table should roughly match the mass actually flown (small gap is fine - this is independent of overrides)

    cp_calc = barrowman.hand_calc_cp(parsed)
    assert cp_calc is not None
    assert cp_calc["cp_m"] > 0

    rail_length = parsed.launch.rail_length_m if parsed.launch else None
    upper_button = parsed.rail_buttons.upper_position_m if parsed.rail_buttons else None
    assert rail_length is not None  # launch conditions ARE present
    assert upper_button is None  # rail button position is NOT - the page shows "not available", doesn't crash
    nozzle_pos = airframe_length_m(parsed)
    assert nozzle_pos > 0

    speed_of_sound = env.speed_of_sound(env.elevation)
    pressure = env.pressure(env.elevation)
    for finset in parsed.fins:
        result = flutter.hand_calc_flutter_velocity(finset, speed_of_sound, pressure, None, None, is_freeform=(finset.shape != "trapezoid"))
        assert result is not None
        assert result.flutter_velocity_ms > 0

    panel_rows = recovery.recovery_panel(flight, env, sim.descent_mass_kg)
    assert panel_rows  # PROMETEO's stored sim deploys its one parachute


def test_all_calculations_sections_resolve_with_rail_buttons_present():
    """A different real, checked-in .ork that DOES have rail buttons
    parsed - the rail exit velocity formula's inputs must all resolve to
    real numbers, not fall into the 'not available' branch.

    2026-10-19 review ("check every bug" audit, task #78): this used to
    route through the full pipeline.run_simulation() via _run(), even
    though nothing below touches a `sim` result - only lr.parsed_ork and
    translate.component_table(parsed), both already available right
    after load_files(), no Flight() needed. That unused extra step tied
    this test to the full stability pipeline, and broke it:
    Dual_parachute_deployment.ork has no real .eng of its own in this
    repo (a generic OpenRocket example, used only as a structural "has
    rail buttons" fixture), so ENG_PATH stands in PROMETEO's real
    Icarus_I_K519.eng (a far heavier K-class SRAD motor) for whatever
    small motor the example actually ships with. Pairing this ~1.6 kg
    airframe with a wildly oversized motor is physically nonsensical for
    a full flight simulation (the motor's own mass/placement swamps the
    total CG, regardless of this airframe's own OpenRocket-confirmed
    ~3.8-4.7 cal stable dry stability - see the file's own stored
    simulation's "Stability margin calibers" column) - but is completely
    irrelevant to what this test actually checks. Loading (not
    simulating) sidesteps the mismatch entirely."""
    lr = pipeline.load_files(ORK_DUAL, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    parsed = lr.parsed_ork
    assert parsed.rail_buttons is not None

    rail_length = parsed.launch.rail_length_m if parsed.launch else None
    upper_button = parsed.rail_buttons.upper_position_m
    nozzle_pos = airframe_length_m(parsed)
    assert rail_length is not None and upper_button is not None
    effective_rail = rail_length - abs(nozzle_pos - upper_button)
    assert effective_rail > 0, f"effective rail travel should be a positive distance, got {effective_rail}"

    # Mass/CG table still resolves for a second, geometrically different rocket.
    rows = translate.component_table(parsed)
    countable = [r for r in rows if r.mass_kg is not None and r.position_m is not None]
    assert countable


def test_parachute_canopy_area_formula_matches_computed_mass_direction():
    """The page shows canopy area = pi*(diameter/2)^2 next to the
    already-computed mass - sanity-check that multiplying area by a
    plausible fabric density lands in the right ballpark of the real
    computed_mass_kg (catches a stale/disconnected formula display, not
    just a crash)."""
    lr, _ = _run(ORK_PROMETEO, ENG_PATH)
    parsed = lr.parsed_ork
    chute = next((c for c in parsed.parachutes if c.computed_mass_kg is not None), None)
    assert chute is not None, "PROMETEO's real parachute should have a computed or overridden mass"
    canopy_area = math.pi * (chute.diameter / 2.0) ** 2
    assert canopy_area > 0
    # computed_mass_kg for a real ~2.8 m parachute should be well under 2 kg and well over 0 - a sane physical range, not a formula that silently returned garbage.
    assert 0.0 < chute.computed_mass_kg < 2.0
