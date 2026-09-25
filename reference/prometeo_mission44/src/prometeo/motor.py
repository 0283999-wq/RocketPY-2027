"""Builds the Icarus I SolidMotor object from the .eng file in data/motors/."""

import os

import config
from rocketpy import SolidMotor


def build_motor():
    eng_path = os.path.join(config.DATA_DIR, "motors", "Icarus_I_K519.eng")
    return SolidMotor(
        thrust_source=eng_path,
        dry_mass=config.MOTOR_DRY_MASS,
        dry_inertia=(0.01, 0.01, 0.001),  # TODO CONFIRM - bare-casing inertia not measured, propellant term (which dominates) is geometric and correct
        nozzle_radius=config.NOZZLE_EXIT_RADIUS,
        grain_number=config.GRAIN_COUNT,
        grain_density=config.GRAIN_DENSITY,
        grain_outer_radius=config.GRAIN_OUTER_RADIUS,
        grain_initial_inner_radius=config.GRAIN_INITIAL_INNER_RADIUS,
        grain_initial_height=config.GRAIN_LENGTH,
        grain_separation=config.GRAIN_SEPARATION,
        grains_center_of_mass_position=config.MOTOR_CASING_LENGTH / 2,
        center_of_dry_mass_position=config.MOTOR_CASING_LENGTH / 2,
        nozzle_position=0,
        burn_time=config.BURN_TIME,
        throat_radius=config.THROAT_RADIUS,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )
