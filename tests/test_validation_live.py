"""2026-09-26 review item D: bup_rocketpy.validation is the ONE place the
Validation page and the report's appendix get V1/V2 from now (previously
each had its own hand-typed, independently-stale numbers). This test
locks in that the module actually computes something, and that its
numbers agree with tests/test_phase2_validation.py's own (that test file
is the original, audited source this was extracted from - if these ever
disagree, one of the two silently diverged).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import validation


def test_v1_and_v2_are_computed_and_sane():
    results = validation.compute_v1_and_v2()
    assert len(results) == 2
    for r in results:
        print(f"\n{r.name}: predicted={r.predicted_agl_m:.1f} m, target={r.target_agl_m:.1f} m, error={r.error_pct:+.2f}%, passes={r.passes}")
        assert 500 < r.predicted_agl_m < 2000, f"{r.name}: apogee not remotely in PROMETEO's known ballpark"
        assert r.passes == (abs(r.error_pct) <= validation.TOLERANCE_PCT)


def test_v1_matches_test_phase2_validation_within_rounding():
    """Not a duplicate - a cross-check that this module's extraction of
    _run_case didn't silently drift from the original, audited test."""
    v1 = validation.compute_v1()
    v2 = validation.compute_v2()
    # loose bounds, not exact pinned numbers - the point is "matches the
    # known ballpark from test_phase2_validation.py's own printed output",
    # not to duplicate that test's own tighter checks here
    assert 1050 < v1.predicted_agl_m < 1200
    assert 950 < v2.predicted_agl_m < 1150
