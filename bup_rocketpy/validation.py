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
    return apogee_agl, margin0


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
    apogee_agl, margin0 = _run_case(
        launch_override=launch_override,
        total_mass_kg=10.96, motor_mass_loaded_kg=4.882948, motor_dry_mass_kg=2.866213,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=3.0, inclination=89.0, heading=270.0,
    )
    error_pct = (apogee_agl - target) / target * 100
    notes = ("Conditions: OpenRocket-recorded (prometeo4dejulio.csv), NOT live weather. "
             "Dry CG is a Brasil-config approximation, not a July4-specific measurement.")
    return ValidationResult("V1 (2026-07-04, Pachuca profile)", apogee_agl, target, error_pct, margin0, abs(error_pct) <= TOLERANCE_PCT, notes)


def compute_v2():
    """LASC (Iacanga), the official competition flight. Target 1137 m
    (SRAD telemetry - the "1138 m" figure is the officials' own on-site
    prediction, a different thing, never relabeled as ours)."""
    prom_config = _prom_config()
    target = 1137.0
    apogee_agl, margin0 = _run_case(
        launch_override=None,
        total_mass_kg=10.370, motor_mass_loaded_kg=prom_config.MOTOR_MASS_LOADED, motor_dry_mass_kg=prom_config.MOTOR_DRY_MASS,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=4.0, inclination=80.0, heading=90.0,
    )
    error_pct = (apogee_agl - target) / target * 100
    notes = ("Conditions: the .ork's OWN recorded wind/atmosphere, NOT the actual Iacanga flight-day weather. "
             "At the Launch Readiness Review, LASC officials independently re-simulated this vehicle on-site "
             "and predicted 1138 m (RocketPy, CRS 10.2.1) - we did not reproduce their exact inputs; this is our "
             "own independent replication, not a claim of matching their number.")
    return ValidationResult("V2 (LASC 2026, Iacanga)", apogee_agl, target, error_pct, margin0, abs(error_pct) <= TOLERANCE_PCT, notes)


def compute_v1_and_v2():
    """Convenience: both, in the order the Validation page/report show
    them. Real computation each time - a couple hundred ms total, not a
    hot-loop-safe call."""
    return [compute_v1(), compute_v2()]


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
    apogee_agl, margin0 = _run_case(
        launch_override=launch_override,
        total_mass_kg=10.96, motor_mass_loaded_kg=4.882948, motor_dry_mass_kg=2.866213,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=3.0, inclination=89.0, heading=270.0,
    )
    error_pct = (apogee_agl - target) / target * 100
    notes = (f"Conditions: REAL historical weather from Open-Meteo ({profile.source}) for "
             f"{V1_DATE} 12:00 local at Pachuca - wind {speed:.1f} m/s from {direction:.0f} deg "
             "(compute_v1() instead uses the OpenRocket-recorded csv wind of 3.25 m/s from 90 deg). "
             "Dry CG is still the Brasil-config approximation (same caveat as compute_v1()).")
    return ValidationResult("V1 (2026-07-04, Pachuca profile) - REAL WEATHER", apogee_agl, target, error_pct, margin0, abs(error_pct) <= TOLERANCE_PCT, notes)


class V2FlightDateUnknownError(ValueError):
    """Raised when compute_v2_with_real_weather is called with no date.
    The exact LASC 2026 flight date/time is NOT YET RECORDED in this
    project (see PROGRESS.md - Diego said this is "pending from me") -
    CLAUDE.md Rule 2 forbids guessing one, so this refuses rather than
    silently picking an arbitrary date's weather."""


def compute_v2_with_real_weather(date, cache_dir, force_refresh=False):
    """date: the real LASC 2026 flight date at Iacanga (ISO "YYYY-MM-DD"),
    which the CALLER must supply (e.g. typed into the Validation page) -
    there is no default here, see V2FlightDateUnknownError."""
    if not date:
        raise V2FlightDateUnknownError(
            "The exact LASC 2026 flight date is not yet recorded in this project - ask Diego for it "
            "(PROGRESS.md already logs this as pending) and enter it above before re-running with real weather."
        )
    from bup_rocketpy import weather

    prom_config = _prom_config()
    target = 1137.0
    parsed = read_ork(ORK_PATH)
    site_lat, site_lon = parsed.launch.latitude, parsed.launch.longitude
    profile = weather.fetch_historical_weather(site_lat, site_lon, date, cache_dir, force_refresh=force_refresh)
    speed, direction = weather.nearest_hour_wind(profile, f"{date}T12:00")
    launch_override = dataclasses.replace(parsed.launch, wind_average_ms=speed, wind_direction_deg=direction)
    apogee_agl, margin0 = _run_case(
        launch_override=launch_override,
        total_mass_kg=10.370, motor_mass_loaded_kg=prom_config.MOTOR_MASS_LOADED, motor_dry_mass_kg=prom_config.MOTOR_DRY_MASS,
        cg_with_motor_m_from_nose=prom_config.CG_T0_WITH_MOTOR,
        rail_length=4.0, inclination=80.0, heading=90.0,
    )
    error_pct = (apogee_agl - target) / target * 100
    notes = (f"Conditions: REAL historical weather from Open-Meteo ({profile.source}) for {date} "
             f"12:00 local at Iacanga - wind {speed:.1f} m/s from {direction:.0f} deg. Still does NOT "
             "reproduce LASC officials' own exact re-simulation inputs (CRS 10.2.1) - an independent replication, "
             "same caveat as compute_v2().")
    return ValidationResult("V2 (LASC 2026, Iacanga) - REAL WEATHER", apogee_agl, target, error_pct, margin0, abs(error_pct) <= TOLERANCE_PCT, notes)
