"""2026-09-30 review item 4: "Overall length = the most-aft point of ANY
component, including swept fin tips that overhang the tail." Uses
PROMETEO's own real fins (a real, if modest, ~7 cm overhang past the
structural airframe end - 154 cm reported vs. 147 cm structural) rather
than a synthetic rocket, so this is checked against real geometry.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.ork_reader import airframe_length_m, fin_envelope_end_m, read_ork, reported_length_m

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")


def test_reported_length_includes_fin_overhang_past_structural_airframe():
    parsed = read_ork(ORK_PATH)
    structural = airframe_length_m(parsed)
    fin_end = fin_envelope_end_m(parsed)
    reported = reported_length_m(parsed)

    assert fin_end > structural, "this test's whole premise is a real fin overhang - if this fails, PROMETEO's .ork geometry changed"
    assert reported == max(structural, fin_end)
    assert reported > structural, "reported length must reflect the fin overhang, not just the structural airframe"


def test_reported_length_falls_back_to_structural_when_fins_dont_overhang():
    """A rocket whose fins end flush with (or before) the airframe's own
    aft end must not report a SHORTER length than the airframe itself."""
    parsed = read_ork(ORK_PATH)
    import dataclasses
    no_fins = dataclasses.replace(parsed, fins=[])
    assert reported_length_m(no_fins) == airframe_length_m(no_fins)


if __name__ == "__main__":
    test_reported_length_includes_fin_overhang_past_structural_airframe()
    test_reported_length_falls_back_to_structural_when_fins_dont_overhang()
    print("\nREPORTED LENGTH: OK")
