"""Correction from Diego's review: 'tail_to_nose is fine (a convention).
Convert in one place, and add a test that builds the rocket both ways and
gets identical CP and static margin.'

translate._coordinate_transform is that one place. This test builds the
same real PROMETEO geometry in both "tail_to_nose" (the validated
reference code's convention) and "nose_to_tail" (what CLAUDE.md Sec 4.3's
prose says) and checks CP position and static margin come out identical -
proving the choice is cosmetic, not a source of error, as long as it's
applied consistently everywhere a position is used (which is what having
ONE conversion function guarantees).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stella_flight.ork_reader import read_ork
from stella_flight import translate

ORK_PATH = os.path.join(os.path.dirname(__file__), "..", "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")


def _build(coordinate_system_orientation):
    from rocketpy import Rocket

    parsed = read_ork(ORK_PATH)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    to_rpy = translate._coordinate_transform(coordinate_system_orientation)

    rocket = Rocket(
        radius=radius_m,
        mass=5.0,  # arbitrary - CP and static margin (relative to CG geometry) don't depend on the value chosen, only on consistent placement
        inertia=(1.0, 1.0, 0.02),
        power_off_drag=translate.DRAG_CURVE_PLACEHOLDER_CD,
        power_on_drag=translate.DRAG_CURVE_PLACEHOLDER_CD,
        center_of_mass_without_motor=to_rpy(1.1),  # arbitrary CG for this geometry-only comparison
        coordinate_system_orientation=coordinate_system_orientation,
    )
    if parsed.nose is not None:
        rocket.add_nose(length=parsed.nose.length, kind=translate.rocketpy_nose_kind(parsed.nose.shape), position=to_rpy(0.0))
    for fin in parsed.fins:
        rocket.add_trapezoidal_fins(
            n=fin.count, root_chord=fin.root_chord, tip_chord=fin.tip_chord,
            span=fin.span, sweep_length=fin.sweep_length, cant_angle=fin.cant_angle,
            position=to_rpy(fin.position_m),
        )
    return rocket


def test_tail_to_nose_and_nose_to_tail_give_identical_cp_and_margin():
    rocket_ttn = _build("tail_to_nose")
    rocket_ntt = _build("nose_to_tail")

    cp_ttn = rocket_ttn.cp_position(0)
    cp_ntt = rocket_ntt.cp_position(0)
    # CP is reported IN each rocket's own coordinate frame, so the raw
    # numbers differ in sign/origin - what must match is the PHYSICAL
    # position (distance from nose tip), i.e. the values after inverting
    # each one's own to_rpy.
    cp_ttn_from_nose = -cp_ttn
    cp_ntt_from_nose = cp_ntt
    print(f"\nCP from nose: tail_to_nose={cp_ttn_from_nose:.6f} m, nose_to_tail={cp_ntt_from_nose:.6f} m")
    assert abs(cp_ttn_from_nose - cp_ntt_from_nose) < 1e-9, "the two conventions disagree on physical CP position - _coordinate_transform has a bug"

    margin_ttn = rocket_ttn.static_margin(0)
    margin_ntt = rocket_ntt.static_margin(0)
    print(f"Static margin: tail_to_nose={margin_ttn:.6f} cal, nose_to_tail={margin_ntt:.6f} cal")
    assert abs(margin_ttn - margin_ntt) < 1e-9, "the two conventions disagree on static margin - _coordinate_transform has a bug"


if __name__ == "__main__":
    test_tail_to_nose_and_nose_to_tail_give_identical_cp_and_margin()
    print("\nCOORDINATE CONVENTION EQUIVALENCE CONFIRMED")
