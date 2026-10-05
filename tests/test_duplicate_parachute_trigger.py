"""2026-10-05 review: a real crash report - "array must not contain infs
or NaNs" when clicking Simulate, right after editing the .ork in
OpenRocket. The actual chain (confirmed against a real console log):

1. Two parachutes both ended up with deploy_event "never" (OpenRocket's
   own UI has no trigger configured - common right after adding a second
   chute without setting its deployment up) - translate.parachute_trigger
   falls back to apogee-triggered deployment for BOTH, with the SAME
   deploy_delay (0.0, the usual default).
2. rocketpy warns "Trying to add flight phase starting *together* with
   the one *preceding* it... may be caused by multiple parachutes being
   triggered simultaneously" - two flight phases start at the EXACT
   same timestamp.
3. The next time rocketpy fits a cubic spline through the flight
   solution (mathutils/_calc/_fitting.py), the duplicate timestamp makes
   an `h` (time-step) entry exactly 0.0, dividing by zero
   ("RuntimeWarning: invalid value encountered in divide") and poisoning
   the fit with NaN/inf - which some later numpy/scipy call then refuses
   to accept ("array must not contain infs or NaNs").

Uses PROMETEO's real .ork/parachute (whose own deploy_event IS "never")
duplicated via dataclasses.replace, matching test_reefed_parachute.py's
own "no invented rocket, just a realistic second chute" convention.
"""
import dataclasses
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _load_with_duplicate_chute():
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    chute = parsed.parachutes[0]
    assert chute.deploy_event == "never", "sanity: PROMETEO's own parachute should still be the 'never' case this bug needs"
    second = dataclasses.replace(chute, name=chute.name + " (duplicate)")
    parsed.parachutes.append(second)
    return parsed, eng


def test_import_notes_flag_the_simultaneous_trigger():
    parsed, _ = _load_with_duplicate_chute()
    notes = translate.parachute_import_notes(parsed)
    detail_text = " ".join(detail for _, _, detail in notes)
    assert "SAME trigger" in detail_text, f"expected a warning about the duplicate trigger, got: {notes}"


def test_build_rocket_nudges_the_duplicate_lag_instead_of_colliding():
    parsed, eng = _load_with_duplicate_chute()
    motor = translate.build_motor(eng, ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    rocket = translate.build_rocket(parsed, motor, mass_est, i_ax, i_tr, radius, power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG, include_recovery=True)
    assert len(rocket.parachutes) == 2
    lags = [p.lag for p in rocket.parachutes]
    assert lags[0] != lags[1], f"both parachutes still share the exact same lag ({lags}) - would still collide in the solver"
    # 0.0137s per nudge (translate.build_rocket's own _dedupe_lag) - not
    # microseconds: a smaller epsilon still crashed in testing, since
    # rocketpy's OWN internal self-heal (+1e-7s) runs first and lands
    # the collision too close for the adaptive solver's own float time
    # grid to keep distinct. Still negligible next to a real deployment
    # delay (seconds), just not "tiny" in the naive sense.
    assert abs(lags[0] - lags[1]) < 0.1, "the nudge should be a small timing offset, not a real deployment-timing change"


def test_simulate_does_not_crash_with_two_apogee_triggered_chutes():
    """The actual end-to-end repro: before the fix, this raised
    ValueError('array must not contain infs or NaNs') from inside
    rocketpy's own post-processing."""
    parsed, eng = _load_with_duplicate_chute()
    flight, rocket = translate.ork_to_flight(
        parsed, eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=False, include_recovery=True,
        dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M,
    )
    assert math.isfinite(flight.apogee)
    assert math.isfinite(flight.max_speed)
    assert math.isfinite(flight.x_impact)
    assert math.isfinite(flight.y_impact)


if __name__ == "__main__":
    test_import_notes_flag_the_simultaneous_trigger()
    test_build_rocket_nudges_the_duplicate_lag_instead_of_colliding()
    test_simulate_does_not_crash_with_two_apogee_triggered_chutes()
    print("\nDUPLICATE PARACHUTE TRIGGER: OK")
