"""REC 8.1.6 single-event recovery, altitude-triggered to match the as-flown
ESP32-S3 + BMP280 avionics logic (fired at 1017.6 m AGL ascending-to-descending
on 2026-07-04), not rocketpy's default "apogee" string trigger.

cd_s is calibrated (not measured) to reproduce the descent rate the team
reports (config.TARGET_DESCENT_RATE = -6.0 m/s) - see config.py for why that
number itself is a post-flight estimate rather than a directly observed
terminal value.
"""

import math

import config


def main_trigger(p, h, y):
    """REC 8.1.6 single-event. Fires on ascending-crossing of the as-flown
    deployment altitude (1017.6 m AGL, telemetry 2026-07-04), not apogee."""
    return h < config.MAIN_DEPLOY_ALTITUDE and y[5] < 0


def calibrate_cd_s(dry_mass, target_descent_rate=config.TARGET_DESCENT_RATE, elevation=config.SLR_ELEVATION):
    """Solves cd_s from v_terminal = sqrt(2 m g / (rho cd_s)) using a
    standard-atmosphere density estimate at the deployment altitude."""
    from rocketpy import Environment

    env = Environment(elevation=elevation)
    env.set_atmospheric_model(type="standard_atmosphere")
    rho = env.density(elevation + config.MAIN_DEPLOY_ALTITUDE)
    g = config.G0
    v = abs(target_descent_rate)
    cd_s = 2 * dry_mass * g / (rho * v**2)
    return cd_s


def add_main_parachute(rocket, dry_mass):
    cd_s = calibrate_cd_s(dry_mass)
    rocket.add_parachute(
        name="Main",
        cd_s=cd_s,
        trigger=main_trigger,
        sampling_rate=config.AVIONICS_SAMPLING_RATE,
        lag=config.AVIONICS_LAG,
        noise=(0, 8.3, 0.5),  # m AGL, BMP280 typical noise floor, not measured from this unit specifically
    )
    return cd_s
