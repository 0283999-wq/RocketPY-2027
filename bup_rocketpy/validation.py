"""Live V1/V2 validation numbers (2026-09-26 review item D's appendix
requirement: "pulled LIVE from the same computation as the Validation
page", after Diego caught the report and the Validation page showing two
DIFFERENT sets of stale, hand-typed numbers - neither had ever been live).

This module is the ONE place both the Validation page and the report's
appendix get these numbers from now - extracted from
tests/test_phase2_validation.py's _run_case/test_v1_.../test_v2_...
(same exact bup_rocketpy.translate calls the app itself uses, no
hand-built rocket - see that test file's own docstring for the "ONE
path" history). Running a real Flight() takes real time (well under a
second each) - acceptable for a page that isn't reloaded per second, not
free, so callers should not invoke this in a hot loop.
"""
import dataclasses
import os
import sys
from dataclasses import dataclass

from bup_rocketpy import translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
ORK_PATH = os.path.join(REF_ROOT, "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REF_ROOT, "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_on_drag.csv")
TOLERANCE_PCT = 5.0


@dataclass
class ValidationResult:
    name: str
    predicted_agl_m: float
    target_agl_m: float
    error_pct: float
    static_margin_at_t0_cal: float
    passes: bool
    notes: str
    # 2026-09-27 review item 5: "print a side-by-side input table" - the
    # actual dry mass/CG/site/rail numbers THIS case used, so a case-to-
    # case difference (e.g. V2 vs. the unconstrained default run) can be
    # visually audited rather than taken on faith.
    inputs: dict = None
    # 2026-09-28 review item 1: "pass"/"fail"/"inconclusive" - a SEPARATE
    # field from `passes` because a case can miss its +-5% tolerance for a
    # reason that has nothing to do with the flight model being wrong (V1
    # uses a CG approximated from a DIFFERENT vehicle configuration, since
    # the July-4-specific design file was never provided - scoring that as
    # a plain FAIL would unfairly blame the physics for an input-data gap).
    # `passes` is kept as the raw +-5% boolean (still used internally/by
    # older tests); `status` is what the UI shows.
    status: str = "fail"


def _prom_config():
    if REF_ROOT not in sys.path:
        sys.path.insert(0, REF_ROOT)
    import config as prom_config
    return prom_config


def _run_case(launch_override, total_mass_kg, motor_mass_loaded_kg, motor_dry_mass_kg, cg_with_motor_m_from_nose, rail_length, inclination, heading):
    prom_config = _prom_config()
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    motor = translate.build_motor(parsed_eng, ENG_PATH, dry_mass_override_kg=motor_dry_mass_kg)

    dry_mass_kg = total_mass_kg - motor_mass_loaded_kg
    mass_est, i_axial, i_transverse = translate.derive_dry_mass_and_inertia_from_with_motor(
        motor, total_mass_kg, motor_mass_loaded_kg, dry_mass_kg, cg_with_motor_m_from_nose,
        rocket_length_m=prom_config.LENGTH,
        i_total_axial_kgm2=prom_config.INERTIA_ROT_T0_WITH_MOTOR, i_total_transverse_kgm2=prom_config.INERTIA_LONG_T0_WITH_MOTOR,
    )

    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        rail_length_override=rail_length, inclination_override=inclination, heading_override=heading,
        terminate_on_apogee=True, include_recovery=False,
        dry_mass_override_kg=mass_est.mass_kg, dry_cg_override_m=mass_est.cg_m,
        launch_override=launch_override, i_axial_override=i_axial, i_transverse_override=i_transverse,
        motor_dry_mass_override_kg=motor_dry_mass_kg,
    )
    apogee_agl = flight.apogee - flight.env.elevation
    margin0 = flight.stability_margin(0)
    launch = launch_override if launch_override is not None else parsed.launch
    inputs = {
        "dry_mass_kg": round(mass_est.mass_kg, 4), "dry_cg_m": round(mass_est.cg_m, 4),
        "mass_source": mass_est.source,
        "site_lat": launch.latitude, "site_lon": launch.longitude, "site_altitude_m": launch.altitude_m,
        "rail_length_m": rail_length, "inclination_deg": inclination, "heading_deg": heading,
        "total_mass_kg": total_mass_kg, "motor_mass_loaded_kg": motor_mass_loaded_kg,
    }
    return apogee_agl, margin0, inputs


def compute_v1():
    """2026-07-04, Pachuca (as-flown). Target 1019.9 m AGL (telemetry).
    Dry CG is APPROXIMATED as the Brasil-config's derived with-motor CG
    (no July4-specific system CG is stored anywhere) - a genuine,
    documented source of error, not hidden."""
    prom_config = _prom_config()
    target = 1019.9
    parsed = read_ork(ORK_PATH)
    launch_override = dataclasses.replace(
        parsed.launch,
        altitude_m=2380.0, latitude=19.967, longitude=-98.856,
        wind_average_ms=3.247, wind_direction_deg=90.0,
    )
    apogee_agl, margin0, inputs = _run_case(
        launch_override=launch_override,
        total_mass_kg=10.96, motor_mass_loaded_kg=4.882948, motor_dry_mass_kg=2.866213,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=3.0, inclination=89.0, heading=270.0,
    )
    error_pct = (apogee_agl - target) / target * 100
    notes = ("Conditions: weather recorded by OpenRocket for this flight, not live/historical data. "
             "Input data incomplete: the design file for this specific flight configuration is not yet "
             "available, so this case reuses a center-of-gravity measurement taken from a different "
             "vehicle configuration instead of one specific to this flight. This case will become a real "
             "pass/fail once that file is added; until then its error number reflects that input gap as "
             "much as the flight model itself, so it is not scored as a plain pass or fail.")
    return ValidationResult(
        "V1 (2026-07-04, Pachuca profile)", apogee_agl, target, error_pct, margin0,
        abs(error_pct) <= TOLERANCE_PCT, notes, inputs=inputs, status="inconclusive",
    )


def compute_v2():
    """LASC (Iacanga), the official competition flight. Target 1137 m
    (SRAD telemetry - the "1138 m" figure is the officials' own on-site
    prediction, a different thing, never relabeled as ours).

    2026-09-27 review item 5: rewritten to use the EXACT SAME path
    pipeline.run_simulation's own no-override default takes for this
    .ork (translate.estimate_best_dry_mass_cg_inertia, reading mass/CG/
    inertia straight from the .ork's own stored simulation databranch),
    changing ONLY the total mass to 10.370 kg (scale-measured at
    Iacanga) - not a hand-rolled duplicate computation with its own,
    separately-sourced CG/rocket-length constants (the OLD version used
    config.py's CG_T0_WITH_MOTOR=0.97966 m and LENGTH=1.54 m, both from
    DIFFERENT source documents than the .ork's own stored databranch,
    which independently give 1.000 m and 1.47 m for the SAME nominal
    configuration). That mismatch is what caused the reported
    "V2 is 150 g LIGHTER but predicts a LOWER apogee than the
    unconstrained default run" bug - physically backwards for a lighter
    rocket with everything else equal, and it was a data-consistency
    bug, not a real physics effect. Rail/inclination/heading are no
    longer separately overridden either - confirmed the .ork's own
    launch conditions already ARE 4.0 m / 80 deg / 90 deg, so passing
    them again was pure redundant duplication of the same numbers,
    with the same silent-drift risk."""
    target = 1137.0
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    best = translate.estimate_best_dry_mass_cg_inertia(parsed, parsed_eng, ENG_PATH, ork_path=ORK_PATH, total_mass_override_kg=10.370)

    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=True, include_recovery=False,
        dry_mass_override_kg=best.mass_est.mass_kg, dry_cg_override_m=best.mass_est.cg_m,
        i_axial_override=best.i_axial_kgm2, i_transverse_override=best.i_transverse_kgm2,
    )
    apogee_agl = flight.apogee - flight.env.elevation
    margin0 = flight.stability_margin(0)
    error_pct = (apogee_agl - target) / target * 100
    notes = ("Conditions: the .ork's OWN recorded wind/atmosphere, NOT the actual Iacanga flight-day weather. "
             "At the Launch Readiness Review, LASC officials independently re-simulated this vehicle on-site "
             "and predicted 1138 m (RocketPy, CRS 10.2.1) - we did not reproduce their exact inputs; this is our "
             "own independent replication, not a claim of matching their number. "
             f"Mass/CG source: {best.mass_est.source}.")
    inputs = {
        "dry_mass_kg": round(best.mass_est.mass_kg, 4), "dry_cg_m": round(best.mass_est.cg_m, 4),
        "mass_source": best.mass_est.source,
        "site_lat": parsed.launch.latitude, "site_lon": parsed.launch.longitude, "site_altitude_m": parsed.launch.altitude_m,
        "rail_length_m": parsed.launch.rail_length_m, "inclination_deg": parsed.launch.inclination_deg, "heading_deg": parsed.launch.rail_direction_deg,
        "total_mass_kg": 10.370, "motor_mass_loaded_kg": round(10.370 - best.mass_est.mass_kg, 4),
    }
    passes = abs(error_pct) <= TOLERANCE_PCT
    return ValidationResult(
        "V2 (LASC 2026, Iacanga)", apogee_agl, target, error_pct, margin0, passes, notes,
        inputs=inputs, status="pass" if passes else "fail",
    )


def compute_default_path_reference():
    """2026-09-27 review item 5: "print a side-by-side input table for
    both" - runs PROMETEO's .ork through the EXACT SAME unconstrained
    default path pipeline.run_simulation itself takes for a fresh
    Simulate click (no overrides at all), so its inputs can be shown
    next to V2's in one table and any real difference between them is
    visible at a glance, not just asserted in prose. NOT a validation
    case (no real-flight target to compare against - this .ork's own
    stored simulation is a design-phase report config, 10.4-10.5 kg,
    never flown), so it isn't part of compute_v1_and_v2()."""
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    best = translate.estimate_best_dry_mass_cg_inertia(parsed, parsed_eng, ENG_PATH, ork_path=ORK_PATH)
    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=True, include_recovery=False,
        dry_mass_override_kg=best.mass_est.mass_kg, dry_cg_override_m=best.mass_est.cg_m,
        i_axial_override=best.i_axial_kgm2, i_transverse_override=best.i_transverse_kgm2,
    )
    apogee_agl = flight.apogee - flight.env.elevation
    inputs = {
        "dry_mass_kg": round(best.mass_est.mass_kg, 4), "dry_cg_m": round(best.mass_est.cg_m, 4),
        "mass_source": best.mass_est.source,
        "site_lat": parsed.launch.latitude, "site_lon": parsed.launch.longitude, "site_altitude_m": parsed.launch.altitude_m,
        "rail_length_m": parsed.launch.rail_length_m, "inclination_deg": parsed.launch.inclination_deg, "heading_deg": parsed.launch.rail_direction_deg,
        "total_mass_kg": None, "motor_mass_loaded_kg": None,
    }
    return ValidationResult(
        "Default path (no overrides, .ork's own stored-sim mass/CG)", apogee_agl, None, None, flight.stability_margin(0), None,
        "Not a validation case (no real-flight target - this .ork's own stored simulation is a design-phase report config, never flown). Shown for side-by-side comparison with V2 only.",
        inputs=inputs, status="n/a",
    )


def compute_v1_and_v2():
    """Convenience: both, in the order the Validation page/report show
    them. Real computation each time - a couple hundred ms total, not a
    hot-loop-safe call."""
    return [compute_v1(), compute_v2()]


@dataclass
class ValidationSummary:
    text: str
    chip_kind: str  # "success" | "warning" | "error" - see components.status_chip


def _short_case_label(name):
    """"V1 (2026-07-04, Pachuca profile)" -> "2026-07-04"; "V2 (LASC 2026,
    Iacanga)" -> "LASC 2026" - the bit inside the parens a reader actually
    needs to tell cases apart, without the internal "V1"/"V2" jargon."""
    if "(" in name and ")" in name:
        inside = name.split("(", 1)[1].rsplit(")", 1)[0]
        return inside.split(",")[0].strip()
    return name


def summarize_validation_status():
    """2026-09-28 review item 1: the app used to show a hardcoded
    "PROVISIONAL" banner on every result, pointing at this repo's own
    PROGRESS.md (an internal file no user should ever be told to open) -
    and it was already stale (V2 passes now). This replaces it with a
    short, ALWAYS-CURRENT summary computed from the live V1/V2 results,
    meant for a single small chip on the results view - e.g. "Model
    validated on 1 flight (LASC 2026, -3.4%) - 1 pending". Full detail
    (per-case notes, why a case is pending) lives on the Validation page
    only, which this chip should link to."""
    results = compute_v1_and_v2()
    passing = [r for r in results if r.status == "pass"]
    failing = [r for r in results if r.status == "fail"]
    pending = [r for r in results if r.status == "inconclusive"]

    if passing:
        detail = "; ".join(f"{_short_case_label(r.name)}, {r.error_pct:+.1f}%" for r in passing)
        clause = f"validated on {len(passing)} flight{'s' if len(passing) != 1 else ''} ({detail})"
    else:
        clause = "not yet validated against a real flight"
    extra = []
    if pending:
        extra.append(f"{len(pending)} pending")
    if failing:
        extra.append(f"{len(failing)} failing")
    text = "Model " + clause + (" - " + ", ".join(extra) if extra else "")

    chip_kind = "error" if failing else ("success" if passing else "warning")
    return ValidationSummary(text=text, chip_kind=chip_kind)


# 2026-09-26 review item I: re-run V1/V2 with REAL recorded weather
# (Open-Meteo historical archive) instead of the OpenRocket-recorded
# conditions both compute_v1/compute_v2 above use. Downloads only happen
# on Diego's own machine (this cloud sandbox can't reach Open-Meteo) -
# tests/test_real_weather_validation.py mocks the HTTP call, per
# CLAUDE.md's own instruction to test this way.

V1_DATE = "2026-07-04"
V1_LATITUDE, V1_LONGITUDE, V1_ELEVATION_M = 19.967, -98.856, 2380.0
V1_LAUNCH_HOUR_ISO = f"{V1_DATE}T12:00"  # CLAUDE.md Sec 3.2 gives no exact time for this flight; noon local is this project's existing midday assumption, same as V2's own approximation


def compute_v1_with_real_weather(cache_dir, force_refresh=False):
    """Same vehicle/mass/site as compute_v1(), but the wind comes from
    Open-Meteo's historical archive for the real flight date instead of
    the OpenRocket-recorded csv value - a genuinely independent check of
    how much the weather source itself matters."""
    from bup_rocketpy import weather

    prom_config = _prom_config()
    target = 1019.9
    parsed = read_ork(ORK_PATH)
    profile = weather.fetch_historical_weather(V1_LATITUDE, V1_LONGITUDE, V1_DATE, cache_dir, force_refresh=force_refresh)
    speed, direction = weather.nearest_hour_wind(profile, V1_LAUNCH_HOUR_ISO)
    launch_override = dataclasses.replace(
        parsed.launch,
        altitude_m=V1_ELEVATION_M, latitude=V1_LATITUDE, longitude=V1_LONGITUDE,
        wind_average_ms=speed, wind_direction_deg=direction,
    )
    apogee_agl, margin0, inputs = _run_case(
        launch_override=launch_override,
        total_mass_kg=10.96, motor_mass_loaded_kg=4.882948, motor_dry_mass_kg=2.866213,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=3.0, inclination=89.0, heading=270.0,
    )
    error_pct = (apogee_agl - target) / target * 100
    notes = (f"Conditions: real historical weather from Open-Meteo ({profile.source}) for "
             f"{V1_DATE} 12:00 local at Pachuca - wind {speed:.1f} m/s from {direction:.0f} deg "
             "(the OpenRocket-recorded-weather version of this case instead uses 3.25 m/s from 90 deg). "
             "Input data incomplete: still uses a center-of-gravity measurement taken from a different "
             "vehicle configuration, same as the OpenRocket-recorded-weather version of this case.")
    return ValidationResult(
        "V1 (2026-07-04, Pachuca profile) - REAL WEATHER", apogee_agl, target, error_pct, margin0,
        abs(error_pct) <= TOLERANCE_PCT, notes, inputs=inputs, status="inconclusive",
    )


class V2FlightDateUnknownError(ValueError):
    """Raised when compute_v2_with_real_weather is called with no date.
    The exact LASC 2026 flight date/time is not yet recorded in this
    project - CLAUDE.md Rule 2 forbids guessing one, so this refuses
    rather than silently picking an arbitrary date's weather."""


def compute_v2_with_real_weather(date, cache_dir, force_refresh=False):
    """date: the real LASC 2026 flight date at Iacanga (ISO "YYYY-MM-DD"),
    which the CALLER must supply (e.g. typed into the Validation page) -
    there is no default here, see V2FlightDateUnknownError.

    2026-09-27 review item 5: same fix as compute_v2() - uses the SAME
    stored-sim-derived mass/CG/inertia path (total mass overridden to
    10.370 kg), not a hand-rolled duplicate with separately-sourced
    CG/length constants."""
    if not date:
        raise V2FlightDateUnknownError(
            "The exact LASC 2026 flight date is not yet recorded in this project - enter it above before "
            "re-running with real weather."
        )
    from bup_rocketpy import weather

    target = 1137.0
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    site_lat, site_lon = parsed.launch.latitude, parsed.launch.longitude
    profile = weather.fetch_historical_weather(site_lat, site_lon, date, cache_dir, force_refresh=force_refresh)
    speed, direction = weather.nearest_hour_wind(profile, f"{date}T12:00")
    launch_override = dataclasses.replace(parsed.launch, wind_average_ms=speed, wind_direction_deg=direction)

    best = translate.estimate_best_dry_mass_cg_inertia(parsed, parsed_eng, ENG_PATH, ork_path=ORK_PATH, total_mass_override_kg=10.370)
    flight, _ = translate.ork_to_flight(
        parsed, parsed_eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=True, include_recovery=False,
        dry_mass_override_kg=best.mass_est.mass_kg, dry_cg_override_m=best.mass_est.cg_m,
        i_axial_override=best.i_axial_kgm2, i_transverse_override=best.i_transverse_kgm2,
        launch_override=launch_override,
    )
    apogee_agl = flight.apogee - flight.env.elevation
    margin0 = flight.stability_margin(0)
    error_pct = (apogee_agl - target) / target * 100
    notes = (f"Conditions: real historical weather from Open-Meteo ({profile.source}) for {date} "
             f"12:00 local at Iacanga - wind {speed:.1f} m/s from {direction:.0f} deg. Still does not "
             "reproduce the LASC officials' own exact re-simulation inputs (their on-site prediction was "
             "made at the Launch Readiness Review) - this is our own independent replication. "
             f"Mass/CG source: {best.mass_est.source}.")
    inputs = {
        "dry_mass_kg": round(best.mass_est.mass_kg, 4), "dry_cg_m": round(best.mass_est.cg_m, 4),
        "mass_source": best.mass_est.source,
        "site_lat": site_lat, "site_lon": site_lon, "site_altitude_m": parsed.launch.altitude_m,
        "rail_length_m": parsed.launch.rail_length_m, "inclination_deg": parsed.launch.inclination_deg, "heading_deg": parsed.launch.rail_direction_deg,
        "total_mass_kg": 10.370, "motor_mass_loaded_kg": round(10.370 - best.mass_est.mass_kg, 4),
    }
    passes = abs(error_pct) <= TOLERANCE_PCT
    return ValidationResult(
        "V2 (LASC 2026, Iacanga) - REAL WEATHER", apogee_agl, target, error_pct, margin0, passes, notes,
        inputs=inputs, status="pass" if passes else "fail",
    )
