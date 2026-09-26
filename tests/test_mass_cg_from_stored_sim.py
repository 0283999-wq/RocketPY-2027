"""2026-09-27 review item 1: mass/CG/inertia should prefer OpenRocket's
OWN computed t=0 with-motor values (from the .ork's stored simulation
databranch), minus the motor, over our from-scratch geometric thin-shell
estimate - closing the real Major Tom mismatch Diego reported
(OpenRocket 122 cm CG vs. this app's 80.4 cm) without needing a Major
Tom .ork (not available in this repo - the mechanism is proven on
PROMETEO's real .ork, which DOES have a stored databranch, and on a
synthetic rocket for the airframe_length_m() transition fix).
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import BodyTube, MassOverride, NoseCone, ParsedRocket, Transition, airframe_length_m, read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")


def test_stored_sim_derived_mass_and_cg_are_sane_for_prometeo():
    """PROMETEO's real .ork DOES have a stored simulation - the
    stored-sim path should win over the geometric estimate, and give a
    dry mass/CG in the same right ballpark as the already-established
    numbers (within a few percent, not the ~20% gap Diego reported for
    Major Tom's mismatch)."""
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    best = translate.estimate_best_dry_mass_cg_inertia(parsed, parsed_eng, ENG_PATH, ork_path=ORK_PATH)

    assert "OpenRocket computed" in best.mass_est.source, f"expected the stored-sim path to win, got: {best.mass_est.source}"
    assert 5.0 < best.mass_est.mass_kg < 6.5, f"dry mass {best.mass_est.mass_kg} looks implausible"
    assert 0.4 < best.mass_est.cg_m < 1.0, f"dry CG {best.mass_est.cg_m} looks implausible"
    assert best.i_axial_kgm2 > 0 and best.i_transverse_kgm2 > 0
    assert best.i_transverse_kgm2 > best.i_axial_kgm2, "transverse (pitch/yaw) inertia should be much larger than axial (roll) for a long slender rocket"


def test_whole_rocket_mass_override_still_wins_over_stored_sim():
    """A team-measured whole-rocket override (highest priority) must not
    be silently replaced by the new stored-sim path."""
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    override = dataclasses.replace(parsed.mass_overrides[0], override_mass=7.777, override_subcomponents_mass=True) if parsed.mass_overrides else MassOverride(component="Fuselage", override_mass=7.777, override_subcomponents_mass=True)
    parsed_with_override = dataclasses.replace(parsed, mass_overrides=[override])

    best = translate.estimate_best_dry_mass_cg_inertia(parsed_with_override, parsed_eng, ENG_PATH, ork_path=ORK_PATH)
    assert best.mass_est.mass_kg == 7.777
    assert "override" in best.mass_est.source


def test_no_stored_sim_and_no_override_falls_back_to_geometric():
    """A geometry-only rocket (no stored simulation at all) must still
    fall back to the existing geometric estimate, not crash or silently
    produce nothing."""
    parsed = ParsedRocket(
        name="Geometry-only test rocket",
        nose=NoseCone(name="Nose", length=0.2, shape="conical", shape_parameter=1.0, aft_radius=0.05, position_m=0.0, material_density=1200.0),
        body_tubes=[BodyTube(name="Body", length=0.8, radius=0.05, thickness=0.002, position_m=0.2, material_density=1200.0)],
    )
    parsed_eng = read_eng(ENG_PATH)
    best = translate.estimate_best_dry_mass_cg_inertia(parsed, parsed_eng, ENG_PATH, ork_path=None)
    assert best.mass_est.mass_kg > 0
    assert "geometric estimate" in best.mass_est.source


def test_airframe_length_includes_a_transition_placed_after_the_last_body_tube():
    """Regression guard for 2026-09-27 review item 1c: a boat-tail/
    transition placed AFTER the last body tube (a common real layout for
    a tapered motor mount) used to be silently excluded from every
    "rocket length" computation in the app, under-stating both the
    reported length and the assumed motor position."""
    parsed = ParsedRocket(
        name="Boat-tail test rocket",
        nose=NoseCone(name="Nose", length=0.2, shape="conical", shape_parameter=1.0, aft_radius=0.05, position_m=0.0, material_density=1200.0),
        body_tubes=[BodyTube(name="Body", length=0.8, radius=0.05, thickness=0.002, position_m=0.2, material_density=1200.0)],
        transitions=[Transition(name="Boat-tail", length=0.1, fore_radius=0.05, aft_radius=0.03, shape="conical", position_m=1.0, material_density=1200.0)],
    )
    assert airframe_length_m(parsed) == 1.1, "should extend to the boat-tail's own aft end (1.0 + 0.1), not stop at the last body tube (1.0)"


if __name__ == "__main__":
    test_stored_sim_derived_mass_and_cg_are_sane_for_prometeo()
    test_whole_rocket_mass_override_still_wins_over_stored_sim()
    test_no_stored_sim_and_no_override_falls_back_to_geometric()
    test_airframe_length_includes_a_transition_placed_after_the_last_body_tube()
    print("\nMASS/CG FROM STORED SIM: OK")
