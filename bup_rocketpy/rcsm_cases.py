"""The four RCSM cases (CRS 10.1.10-14): Ballistic, Nominal, Drogue-only,
Main-at-apogee. The last two are only MANDATORY for vehicles with a real
dual-deployment (drogue + main) recovery topology (REC 8.1.1, >1500m AGL
category) - for a single-deploy vehicle like PROMETEO, CLAUDE.md Sec 3.4
is explicit: "the app must warn about it... instead of crashing". This
module does exactly that: builds what it can, returns a clear warning
string (never raises) when a case doesn't apply to the loaded rocket.
"""
from dataclasses import dataclass

CASE_NAMES = ["Ballistic", "Nominal", "DrogueOnly", "MainAtApogee"]


@dataclass
class CaseResult:
    case_name: str
    flight: object  # rocketpy.Flight, or None if the case couldn't be built
    warning: str  # empty string if none


def _classify_parachutes(parsed):
    """Best-effort drogue/main split: "drogue" = deploys at/near apogee
    (deploy_event=="apogee" or the highest deploy_altitude); "main" =
    deploys at a lower, specific altitude. Returns (drogue, main), either
    of which may be None."""
    chutes = [c for c in parsed.parachutes if c.cd is not None]
    if not chutes:
        return None, None
    if len(chutes) == 1:
        return chutes[0], None  # can't split a single chute into a topology - caller decides how to warn
    apogee_triggered = [c for c in chutes if c.deploy_event == "apogee"]
    altitude_triggered = sorted([c for c in chutes if c.deploy_event != "apogee"], key=lambda c: c.deploy_altitude)
    drogue = apogee_triggered[0] if apogee_triggered else max(chutes, key=lambda c: c.deploy_altitude)
    main = altitude_triggered[0] if altitude_triggered else min((c for c in chutes if c is not drogue), key=lambda c: c.deploy_altitude, default=None)
    return drogue, main


def run_case(case_name, parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag, power_on_drag):
    from rocketpy import Flight

    from bup_rocketpy import translate

    env = translate.build_environment(parsed.launch)

    if case_name == "Ballistic":
        rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=False)
        flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m, inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg, terminate_on_apogee=True)
        return CaseResult(case_name, flight, "")

    if case_name == "Nominal":
        rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=True)
        flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m, inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg)
        return CaseResult(case_name, flight, "")

    drogue, main = _classify_parachutes(parsed)

    if case_name == "DrogueOnly":
        if drogue is None:
            return CaseResult(case_name, None, "No parachute with a resolvable Cd is configured in this .ork - cannot build a Drogue-only case.")
        if main is None:
            warning = "This rocket has only ONE recovery event configured (not a real drogue+main dual-deployment topology - REC 8.1.1). Running with that single chute as if it were the drogue; treat this case as informational, not a real dual-deploy compliance check."
        else:
            warning = ""
        rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=False)
        _add_single_parachute(rocket, drogue)
        flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m, inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg)
        return CaseResult(case_name, flight, warning)

    if case_name == "MainAtApogee":
        chute_for_main_test = main or drogue
        if chute_for_main_test is None:
            return CaseResult(case_name, None, "No parachute with a resolvable Cd is configured in this .ork - cannot build a Main-at-apogee case.")
        warning = "" if main is not None else "This rocket has only ONE recovery event configured (not a real drogue+main dual-deployment topology - REC 8.1.1). Testing that single chute triggered at apogee instead of its normal altitude; treat this case as informational, not a real dual-deploy compliance check."
        rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=False)
        _add_single_parachute(rocket, chute_for_main_test, force_apogee_trigger=True)
        flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m, inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg)
        return CaseResult(case_name, flight, warning)

    raise ValueError(f"unknown case {case_name!r} - must be one of {CASE_NAMES}")


def _add_single_parachute(rocket, chute, force_apogee_trigger=False):
    import math
    cd_s = chute.cd * math.pi * (chute.diameter / 2.0) ** 2
    trigger = "apogee" if (force_apogee_trigger or chute.deploy_event == "apogee") else chute.deploy_altitude
    rocket.add_parachute(name=chute.name, cd_s=cd_s, trigger=trigger, sampling_rate=100, lag=chute.deploy_delay)


def run_all_cases(parsed, parsed_eng, eng_path, power_off_drag, power_on_drag, dry_mass_kg, dry_cg_m):
    from bup_rocketpy import translate

    mass_est = translate.MassEstimate(dry_mass_kg, dry_cg_m, "provided to run_all_cases")
    motor = translate.build_motor(parsed_eng, eng_path)
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    return {name: run_case(name, parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag, power_on_drag) for name in CASE_NAMES}
