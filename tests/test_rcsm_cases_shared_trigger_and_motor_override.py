"""2026-10-19 review ("check every bug" audit, finding #1/#2 of the
pipeline/MC/compare_designs/rcsm report):

  1. rcsm_cases.py's _add_single_parachute() used to have its OWN
     parachute-trigger logic, reproducing the exact "never"-deploy-event
     bug translate.parachute_trigger() was already written and tested to
     fix elsewhere (PROMETEO's real .ork has deploy_event="never" with a
     STALE deploy_altitude=200.0 that was never a live trigger in
     OpenRocket - treating it as one free-falls the rocket to ~120 m/s
     before "deploying"). Now shares the same fixed function.
  2. run_all_cases() never applied the "Measured motor mass" override,
     unlike pipeline.run_simulation/monte_carlo - now takes the same
     motor_dry_override_kg parameter translate.build_motor already has.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import rcsm_cases, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def test_add_single_parachute_maps_never_deploy_event_to_apogee_not_the_stale_altitude():
    """PROMETEO's real parachute has deploy_event='never' with a stale
    deploy_altitude=200.0 that was never a live OpenRocket trigger - the
    DrogueOnly case (the one call site with no force_apogee_trigger) must
    end up with an 'apogee' rocketpy trigger, not literally 200.0."""
    parsed = read_ork(ORK_PATH)
    chute = next(c for c in parsed.parachutes if c.cd is not None)
    assert chute.deploy_event == "never"
    assert chute.deploy_altitude == 200.0

    eng = read_eng(ENG_PATH)
    motor = translate.build_motor(eng, ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG, include_recovery=False)

    rcsm_cases._add_single_parachute(rocket, chute)
    assert rocket.parachutes[-1].trigger == "apogee", f"expected 'apogee' for a 'never' deploy_event (the shared, fixed translate.parachute_trigger mapping), got {rocket.parachutes[-1].trigger!r} - this is the exact bug: treating a stale deploy_altitude as a live trigger"


def test_drogue_only_case_actually_deploys_near_apogee_speed_not_after_free_fall():
    """End-to-end proof through run_all_cases itself: DrogueOnly's
    descent rate (sampled via the parachute's own deployment, not a
    120+ m/s free-fall speed) should be physically reasonable for a
    canopy that opened near apogee."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    flight = results["DrogueOnly"].flight
    assert flight is not None
    events = sorted(getattr(flight, "parachute_events", []), key=lambda te: te[0])
    assert events, "DrogueOnly should have at least one parachute deployment event"
    deploy_time = events[0][0]
    vx, vy, vz = flight.vx(deploy_time), flight.vy(deploy_time), flight.vz(deploy_time)
    speed_at_deploy = (vx**2 + vy**2 + vz**2) ** 0.5
    assert speed_at_deploy < 50.0, f"deployment speed should be near-apogee (slow), got {speed_at_deploy:.1f} m/s - looks like a free-fall-then-deploy, the exact bug this fix addresses"


def test_run_all_cases_applies_motor_dry_mass_override():
    """A real 'Measured motor mass' correction must change the flown
    motor dry mass in RCSM Cases too, not just Simulate/Monte Carlo."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    baseline = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    baseline_motor_dry = baseline["Nominal"].flight.rocket.motor.dry_mass

    corrected_dry_kg = baseline_motor_dry * 1.5  # a deliberately large, unmistakable correction
    corrected = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M, motor_dry_override_kg=corrected_dry_kg)
    corrected_motor_dry = corrected["Nominal"].flight.rocket.motor.dry_mass

    assert abs(corrected_motor_dry - corrected_dry_kg) < 1e-6, f"expected the override ({corrected_dry_kg}) to be the flown motor dry mass, got {corrected_motor_dry}"
    assert abs(corrected_motor_dry - baseline_motor_dry) > 1e-3, "the override should visibly change the flown motor mass vs the uncorrected .eng header"
