"""Shared minimal rocket/motor builder for the repro scripts in this
folder. Not a repro itself - imported by the others so each one stays
focused on the ONE thing it's demonstrating. Uses only rocketpy plus
inline data (no external .eng/.csv files) so every script here is fully
self-contained and copy-pasteable into a GitHub issue.
"""
from rocketpy import Environment, Rocket, SolidMotor


def build_motor():
    # A small, made-up but physically plausible thrust curve (roughly a
    # KNSB-class ~I-motor shape) - inline, not read from any file.
    thrust_curve = [
        (0.00, 0.0), (0.02, 900.0), (0.10, 800.0), (0.40, 650.0),
        (0.80, 600.0), (1.20, 550.0), (1.50, 500.0), (1.60, 0.0),
    ]
    return SolidMotor(
        thrust_source=thrust_curve,
        dry_mass=0.5,
        dry_inertia=(0.01, 0.01, 0.001),
        nozzle_radius=0.015,
        grain_number=1,
        grain_density=1750.0,
        grain_outer_radius=0.02,
        grain_initial_inner_radius=0.006,
        grain_initial_height=0.15,
        grain_separation=0.005,
        grains_center_of_mass_position=0.1,
        center_of_dry_mass_position=0.1,
        nozzle_position=0,
        burn_time=1.6,
        throat_radius=0.008,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )


def build_rocket():
    motor = build_motor()
    rocket = Rocket(
        radius=0.04,
        mass=1.5,
        inertia=(0.3, 0.3, 0.002),
        power_off_drag=0.5,
        power_on_drag=0.5,
        center_of_mass_without_motor=0.6,
        coordinate_system_orientation="tail_to_nose",
    )
    rocket.add_motor(motor, position=0.0)
    rocket.add_nose(length=0.15, kind="vonkarman", position=0.9)
    rocket.add_trapezoidal_fins(
        n=4, root_chord=0.10, tip_chord=0.04, span=0.06,
        sweep_length=0.05, position=0.1,
    )
    rocket.add_parachute(
        name="Main", cd_s=1.0, trigger="apogee", sampling_rate=100, lag=1.0,
        radius=0.4, drag_coefficient=1.4,
    )
    return rocket


def build_environment():
    env = Environment(latitude=0.0, longitude=0.0, elevation=0.0)
    env.set_atmospheric_model(type="standard_atmosphere")
    return env
