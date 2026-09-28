"""2026-09-26 review item D: bup_rocketpy.validation is the ONE place the
Validation page and the report's appendix get V1/V2 from now (previously
each had its own hand-typed, independently-stale numbers). This test
locks in that the module actually computes something, and that its
numbers stay in the right ballpark of tests/test_phase2_validation.py's
own (that test file is the ORIGINAL implementation this was extracted
from - loose bounds only, not exact agreement: 2026-09-27 review item 5
deliberately fixed a data-consistency bug in THIS module's compute_v2()
that test_phase2_validation.py's own hand-rolled version still
reproduces on purpose, as a historical snapshot - see that file's own
module docstring).
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


def test_v1_is_inconclusive_not_fail_and_v2_status_matches_passes():
    """2026-09-28 review item 1: V1 uses a CG approximated from a
    DIFFERENT vehicle configuration (the July-4-specific design file is
    missing) - scoring it a plain FAIL would blame the flight model for
    an input-data gap that has nothing to do with it. It must report
    status="inconclusive" (not "pass"/"fail") until that file exists.
    V2 has no such gap, so its status must track its own +-5% pass/fail
    exactly, same as before this review item."""
    v1 = validation.compute_v1()
    v2 = validation.compute_v2()
    assert v1.status == "inconclusive", f"V1 should be inconclusive (input data incomplete), got {v1.status!r}"
    assert v2.status == ("pass" if v2.passes else "fail")


def test_no_internal_file_names_leak_into_user_facing_validation_text():
    """2026-09-28 review item 1: the old hardcoded banner told users to
    "see PROGRESS.md" - an internal repo file no user has. Every
    user-facing string this module produces (notes, summary chip text,
    the flight-date-unknown error message) must never name an internal
    project file."""
    banned = ["PROGRESS.md", "progress.md"]
    results = validation.compute_v1_and_v2()
    for r in results:
        for term in banned:
            assert term not in r.notes, f"{r.name}.notes leaks an internal file name: {term!r}"
    summary = validation.summarize_validation_status()
    for term in banned:
        assert term not in summary.text
    try:
        validation.compute_v2_with_real_weather(None, "/tmp/unused_cache_dir")
        assert False, "expected V2FlightDateUnknownError"
    except validation.V2FlightDateUnknownError as exc:
        for term in banned:
            assert term not in str(exc)


def test_summarize_validation_status_reflects_current_pass_pending_counts():
    """Locks in the exact shape the mega-prompt asked for: "Model
    validated on 1 flight (LASC 2026, -3.4%) - 1 pending" - computed
    live from real V1 (inconclusive)/V2 (pass) results, not hand-typed."""
    summary = validation.summarize_validation_status()
    assert summary.text.startswith("Model validated on 1 flight ("), summary.text
    assert "LASC 2026" in summary.text
    assert summary.text.endswith("1 pending"), summary.text
    assert summary.chip_kind == "success"


def test_v2_lighter_config_predicts_a_higher_apogee_than_the_default_path():
    """2026-09-27 review item 5's actual reported bug, as a permanent
    regression guard: V2's config (10.370 kg, scale-measured at Iacanga)
    is LIGHTER than the .ork's own stored-sim design-phase total
    (10.400-10.523 kg depending on source) - with everything else held
    equal, a lighter rocket on the SAME motor must reach a HIGHER apogee,
    never a lower one. The pre-fix code gave this backwards (a data-
    consistency bug: two different, separately-sourced with-motor CG/
    rocket-length constants between the two paths), not a real physics
    effect."""
    v2 = validation.compute_v2()
    default_ref = validation.compute_default_path_reference()
    assert v2.inputs["dry_mass_kg"] < default_ref.inputs["dry_mass_kg"], "sanity: V2 really is the lighter config in this comparison"
    assert v2.predicted_agl_m > default_ref.predicted_agl_m, (
        f"V2 ({v2.inputs['total_mass_kg']} kg total, {v2.predicted_agl_m:.1f} m) is LIGHTER than the default "
        f"path's own stored-sim mass but predicted a LOWER apogee ({default_ref.predicted_agl_m:.1f} m) - physically backwards."
    )
    assert v2.passes, f"V2 should now pass within +-5% (got {v2.error_pct:+.2f}%) after the path-consistency fix"
