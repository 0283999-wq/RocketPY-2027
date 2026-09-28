"""2026-09-26 review item D (new lettering): a reefed main + line cutter
is ONE physical canopy flying in TWO stages. RCSM REC 8.1.1 explicitly
accepts this as real dual-event recovery - before this, a single-chute
vehicle (reefed or not) always got "FAIL REC 8.1.1, only 1 parachute" and
the RCSM DrogueOnly/MainAtApogee cases warned "not a real dual-deploy
topology", both WRONG for a reefed setup.

OpenRocket has no concept of reefing at all, so these fields are always
user-set (dataclasses.replace here stands in for the app's own parachute-
settings UI) - this test uses PROMETEO's real .ork with its one real
parachute marked as reefed, not an invented rocket.
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import rcsm, rcsm_cases, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _load_with_reefed_chute(reefed_diameter_m=0.7, cutter_altitude_m=500.0):
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    chute = parsed.parachutes[0]
    parsed.parachutes[0] = dataclasses.replace(
        chute, is_reefed=True, reefed_diameter_m=reefed_diameter_m, reefed_cd=chute.cd,
        cutter_altitude_m=cutter_altitude_m, cutter_delay_s=0.5,
    )
    return parsed, eng


def test_build_rocket_adds_two_real_parachutes_for_a_reefed_chute():
    parsed, eng = _load_with_reefed_chute()
    motor = translate.build_motor(eng, ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    rocket = translate.build_rocket(parsed, motor, mass_est, i_ax, i_tr, radius, power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG, include_recovery=True)
    assert len(rocket.parachutes) == 2
    names = {p.name for p in rocket.parachutes}
    assert any("reefed" in n for n in names) and any("full" in n for n in names)


def test_all_four_rcsm_cases_run_with_no_dual_deploy_warning():
    """The literal acceptance check: no 'FAIL REC 8.1.1', no 'only ONE
    recovery event' warning, for a reefed single-chute vehicle."""
    parsed, eng = _load_with_reefed_chute()
    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    for name, r in results.items():
        print(f"\n{name}: flight={'OK' if r.flight else 'NONE'}, warning={r.warning!r}")
        assert r.flight is not None, f"{name} failed to build for a reefed vehicle"
        assert "only ONE recovery event" not in r.warning, f"{name}: reefed chute should count as real dual-event, not warn like a single-deploy vehicle"

    nominal = results["Nominal"]
    category = rcsm.CATEGORIES["3km_solid"]
    rows = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=4.0)
    rec_811 = next(row for row in rows if row[0] == "REC 8.1.1")
    assert rec_811[2] == "PASS", f"expected REC 8.1.1 to PASS for a reefed dual-event vehicle, got: {rec_811}"

    # DrogueOnly = cutter never fires (stays reefed to ground) - one chute only
    assert len(results["DrogueOnly"].flight.rocket.parachutes) == 1
    # MainAtApogee = cutter fires AT apogee (full chute at apogee) - one chute only, forced to apogee
    assert len(results["MainAtApogee"].flight.rocket.parachutes) == 1


def test_reefing_shortens_nominal_flight_time_vs_unreefed():
    """2026-09-28 review item 3's explicit checklist: "Reefing ON vs OFF:
    shorter flight time ... 2 stages in the report". The Nominal RCSM
    case (which report.py's own prose/recovery section is built from -
    see bup_rocketpy.recovery.recovery_panel, which reads
    flight.parachute_events, not the design-level parachute count) must
    show BOTH: a real flight-time difference, and 2 deployment events."""
    parsed_reefed, eng = _load_with_reefed_chute()
    parsed_normal = read_ork(ORK_PATH)  # same .ork, chute left alone (not reefed)

    reefed = rcsm_cases.run_all_cases(parsed_reefed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)["Nominal"]
    normal = rcsm_cases.run_all_cases(parsed_normal, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)["Nominal"]

    print(f"\nflight time: reefed={reefed.flight.t_final:.1f} s, not reefed={normal.flight.t_final:.1f} s")
    assert reefed.flight.t_final < normal.flight.t_final, "reefing (fast descent until the cutter) should shorten total flight time vs. a normal single-stage deployment"
    assert len(list(reefed.flight.parachute_events)) == 2, "reefed Nominal case should log 2 deployment events (reefed stage + cutter release)"
    assert len(list(normal.flight.parachute_events)) == 1


def test_rec_813_and_814_checks_are_present_and_use_correct_altitude_convention():
    """Regression guard for a real bug caught during development: mixing
    up flight.altitude() (already AGL) with flight.z()/flight.apogee
    (ASL, need '- flight.env.elevation') silently gave a release altitude
    of ~5m instead of the real ~500m on the first pass."""
    parsed, eng = _load_with_reefed_chute(cutter_altitude_m=500.0)
    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    nominal = results["Nominal"]
    rows = rcsm.check_compliance(rcsm.CATEGORIES["3km_solid"], nominal.flight, nominal.flight.rocket, payload_mass_kg=4.0)
    rec_814 = next(row for row in rows if row[0] == "REC 8.1.4")
    print(f"\n{rec_814}")
    assert "released @" in rec_814[3]
    released_alt = float(rec_814[3].split("released @ ")[1].split("m")[0])
    assert 400 < released_alt < 600, f"expected the release altitude to be close to the configured 500m cutter altitude, got {released_alt}m - the AGL/ASL convention bug may be back"


def test_target_reefed_descent_rate_helper():
    cd_s = translate.required_cd_s_for_descent_rate(target_descent_rate_ms=30.0, mass_kg=6.0)
    assert cd_s > 0
    # sanity: a faster target descent rate needs a SMALLER Cd*S (less drag)
    cd_s_faster = translate.required_cd_s_for_descent_rate(target_descent_rate_ms=45.0, mass_kg=6.0)
    assert cd_s_faster < cd_s
