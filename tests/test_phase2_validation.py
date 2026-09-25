"""Phase 2 validation (CLAUDE.md Sec 6, Phase 2 + Sec 3.1's wording rule):
V1 (2026-07-04 profile) and V2 (LASC apogee) against REAL FLIGHT DATA.
This is the only place in the repo the word "validated" is earned.

Tonight's constraint (per the overnight-run instructions): the cloud
container cannot reach weather APIs. Both cases use the launch-day
conditions already RECORDED in the project's own files (the .ork's stored
simulation, or config.py's CSV-sourced constants) - explicitly labeled
"OpenRocket-recorded conditions, pending real weather", not live weather.
Diego re-runs with Open-Meteo/GFS on his machine tomorrow.

Reuses reference/prometeo_mission44's own ALREADY-VALIDATED rocket model
(rocket.py/motor.py/environment.py/recovery.py) rather than re-deriving
physics from scratch - the fastest, most defensible path, since that code
already passed its own mass/inertia acceptance assert. Per-flight inputs
(mass, motor mass, site) are swapped in via monkeypatching config's
module-level constants, since that's how the reference code is structured
(no dependency injection) - restored after each test.

Tolerance: +-5% per CLAUDE.md. A miss is reported with a cause breakdown,
NOT tuned away, and the result stays PROVISIONAL either way (single-flight
comparisons, not a statistically validated model).
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
sys.path.insert(0, REF_ROOT)  # reference code does bare `import config`

import config as prom_config  # noqa: E402
from src.prometeo.environment import build_environment  # noqa: E402
from src.prometeo.motor import build_motor  # noqa: E402
from src.prometeo.rocket import build_rocket  # noqa: E402
from rocketpy import Flight  # noqa: E402

TOLERANCE_PCT = 5.0


class _ConfigOverride:
    """Context manager: temporarily monkeypatches module-level constants on
    reference config.py (and the 3 that are DERIVED from them at import
    time, which don't update on their own), restores on exit."""

    def __init__(self, **overrides):
        self.overrides = overrides
        self.saved = {}

    def __enter__(self):
        for k in list(self.overrides.keys()) + ["DRY_MASS_NO_MOTOR", "PROPELLANT_MASS"]:
            self.saved[k] = getattr(prom_config, k)
        for k, v in self.overrides.items():
            setattr(prom_config, k, v)
        prom_config.DRY_MASS_NO_MOTOR = prom_config.LAUNCH_MASS - prom_config.MOTOR_MASS_LOADED
        prom_config.PROPELLANT_MASS = prom_config.MOTOR_MASS_LOADED - prom_config.MOTOR_DRY_MASS
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(prom_config, k, v)


def _run_case(site, rail_length, inclination_zenith_deg, heading_deg, overrides):
    with _ConfigOverride(**overrides):
        env = build_environment(site=site, atmos="custom")
        rocket, derived = build_rocket()
        flight = Flight(
            rocket=rocket,
            environment=env,
            rail_length=rail_length,
            inclination=inclination_zenith_deg,
            heading=heading_deg,
            terminate_on_apogee=True,
        )
        apogee_agl = flight.apogee - env.elevation
        margin0 = flight.stability_margin(0)
    return apogee_agl, margin0, derived


def test_v1_2026_07_04_profile_apogee():
    """V1: 2026-07-04, Pachuca (as-flown). Target 1019.9 m AGL (telemetry,
    packet 118 of 72, ~2.5 Hz - see PROGRESS.md for the full telemetry
    inspection). Mass/motor-mass from verified_constants.json's
    julio4_asflown_sim block (10.96 kg / 4.882948 kg loaded) - these ARE
    the as-flown numbers for this specific date, unlike V2 below. Dry CG
    is APPROXIMATED as the Brasil-config's derived value (no July4-specific
    system CG is stored anywhere in the project's files) - same airframe,
    but real mass reductions happened between designs per CLAUDE.md Sec
    3.1, so this is a genuine, documented source of error, not hidden."""
    TARGET_APOGEE_AGL = 1019.9

    apogee_agl, margin0, derived = _run_case(
        site="julio4", rail_length=3.0, inclination_zenith_deg=89.0, heading_deg=270.0,
        overrides=dict(LAUNCH_MASS=10.96, MOTOR_MASS_LOADED=4.882948, MOTOR_DRY_MASS=2.866213),
    )
    error_pct = (apogee_agl - TARGET_APOGEE_AGL) / TARGET_APOGEE_AGL * 100
    print(f"\nV1 (2026-07-04): predicted apogee AGL={apogee_agl:.1f} m, flight telemetry={TARGET_APOGEE_AGL} m, error={error_pct:+.2f}%")
    print(f"  static margin@0={margin0:.2f} cal, using Brasil-derived dry CG (APPROXIMATION, see docstring)")
    print("  Conditions: OpenRocket-recorded (prometeo4dejulio.csv @ t=0 wind/temp/pressure), NOT live weather.")
    if abs(error_pct) > TOLERANCE_PCT:
        print(f"  OUTSIDE +-{TOLERANCE_PCT}% - breakdown: dry CG is a Brasil-config approximation (see docstring),")
        print("  not a July4-specific measurement; real drag curve is from the Brasil config too, not this flight's own.")
        print("  NOT tuned to force a pass. Result stays PROVISIONAL.")


def test_v2_lasc_apogee():
    """V2: LASC (Iacanga), the official competition flight. Target 1137 m
    (SRAD telemetry - CLAUDE.md Sec 3.1/3.2; the "1138 m" figure is the
    officials' OWN on-site prediction, not something to reproduce and
    relabel as ours - see the wording rule). Mass = 10.370 kg (measured,
    per tonight's explicit instruction). Site/rail from the real .ork's
    "brasil 2026" stored simulation (490 m, -21.9/-48.96, 4.0 m rail,
    10 deg from vertical = 80 deg inclination, matches config.py's own
    already-used RAIL_INCLINATION=80/RAIL_HEADING=90)."""
    TARGET_APOGEE_AGL = 1137.0

    apogee_agl, margin0, derived = _run_case(
        site="brasil", rail_length=4.0, inclination_zenith_deg=80.0, heading_deg=90.0,
        overrides=dict(LAUNCH_MASS=10.370, MOTOR_MASS_LOADED=prom_config.MOTOR_MASS_LOADED, MOTOR_DRY_MASS=prom_config.MOTOR_DRY_MASS),
    )
    error_pct = (apogee_agl - TARGET_APOGEE_AGL) / TARGET_APOGEE_AGL * 100
    print(f"\nV2 (LASC): predicted apogee AGL={apogee_agl:.1f} m, flight telemetry={TARGET_APOGEE_AGL} m, error={error_pct:+.2f}%")
    print(f"  static margin@0={margin0:.2f} cal")
    print("  Conditions: OpenRocket-recorded (.ork 'brasil 2026' stored sim @ t=0), NOT live weather - Diego re-runs with real Iacanga weather tomorrow.")
    print("  Compare: LASC officials' own on-site RocketPy prediction was 1138 m (CRS 10.2.1) - we did NOT reproduce their exact inputs, this is an independent replication (see CLAUDE.md Sec 3.1 wording rule).")
    if abs(error_pct) > TOLERANCE_PCT:
        print(f"  OUTSIDE +-{TOLERANCE_PCT}% - breakdown: motor mass kept at the Brasil-config value (4.7378 kg loaded),")
        print("  since no LASC-specific motor-mass measurement is on file separate from the 10.370 kg total; wind/temp/pressure")
        print("  are the .ork's OWN recorded values, not the actual Iacanga flight-day weather (still pending from Diego).")
        print("  NOT tuned to force a pass. Result stays PROVISIONAL.")


if __name__ == "__main__":
    test_v1_2026_07_04_profile_apogee()
    test_v2_lasc_apogee()
