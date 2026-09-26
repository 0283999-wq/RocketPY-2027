"""2026-09-27 review item 6: independent hand-calculated stability check
(classical Barrowman method) for the report's Section 6.1. This is
deliberately NOT a duplicate of RocketPy's own CP - it's a from-scratch
calculation that should land close to, but not identical to, RocketPy's
answer (RocketPy's own model is more complete: it also accounts for body
tube/transition contributions this hand method neglects)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import barrowman, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
ORK_PATH = os.path.join(REF_ROOT, "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REF_ROOT, "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_on_drag.csv")


def test_hand_calc_cp_matches_rocketpy_within_a_few_percent_for_prometeo():
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    result = barrowman.hand_calc_cp(parsed)
    assert result is not None
    assert result["cp_m"] > 0
    assert result["cn_alpha_total"] > result["nose_cn_alpha"], "fins should dominate the normal-force slope for a finned rocket"

    flight, _ = translate.ork_to_flight(parsed, parsed_eng, ENG_PATH, power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
                                         terminate_on_apogee=True, include_recovery=False)
    rocketpy_cp_m = -flight.rocket.cp_position(0)
    error_pct = (result["cp_m"] - rocketpy_cp_m) / rocketpy_cp_m * 100.0
    print(f"\nHand Barrowman CP: {result['cp_m']:.4f} m, RocketPy CP: {rocketpy_cp_m:.4f} m, error {error_pct:+.2f}%")
    assert abs(error_pct) < 5.0, "the classical nose+fins hand method should be within a few percent of RocketPy's own CP for a simple finned airframe"


def test_hand_calc_cp_returns_none_without_fins():
    from bup_rocketpy.ork_reader import NoseCone, ParsedRocket

    parsed = ParsedRocket(name="no fins", nose=NoseCone(name="nose", length=0.3, shape="conical", shape_parameter=0.0, aft_radius=0.05, position_m=0.0))
    assert barrowman.hand_calc_cp(parsed) is None


if __name__ == "__main__":
    test_hand_calc_cp_matches_rocketpy_within_a_few_percent_for_prometeo()
    test_hand_calc_cp_returns_none_without_fins()
    print("\nBARROWMAN HAND CALC: OK")
