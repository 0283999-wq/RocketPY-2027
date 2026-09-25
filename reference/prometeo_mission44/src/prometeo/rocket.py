"""Builds the rocketpy Rocket object and resolves the dry (no-motor) inertia.

Coordinate convention (CRS 10.1.8/§4.4): coordinate_system_orientation is
"tail_to_nose", origin placed at the nose tip. OpenRocket measures positions
as cm-from-nose-tip going aft; converting to this frame is a single sign
flip. Every position in this file goes through or_to_rpy() - do not hand-type
a converted number anywhere else, this is the one place sign errors get
caught.
"""

import os

import numpy as np

import config
from src.prometeo.motor import build_motor
from rocketpy import Rocket


def or_to_rpy(x_cm_from_nose):
    """OpenRocket cm-from-nose -> rocketpy m, tail_to_nose, origin at nose tip."""
    return -x_cm_from_nose / 100.0


# --------------------------------------------------------------------------
# Dry (no-motor) inertia, derived from the t=0 OpenRocket row (with motor)
# via parallel-axis subtraction of the motor's own contribution. See
# docs/model_assumptions.md "Inertia" for the full worked derivation and why
# the result is sensitive to the (unmeasured, TODO CONFIRM) motor axial
# position assumption.
# --------------------------------------------------------------------------
def _solve_dry_inertia():
    motor = build_motor()
    system_cg = or_to_rpy(config.CG_T0_WITH_MOTOR * 100)  # config value is already in m from nose
    m_total = config.LAUNCH_MASS
    m_dry = config.DRY_MASS_NO_MOTOR
    m_motor = config.MOTOR_MASS_LOADED

    # motor nozzle assumed flush with the airframe's aft end (standard for a
    # single-stage integral motor mount) - see config.py MOTOR_CASING_LENGTH
    # TODO CONFIRM note, this assumption is the main source of uncertainty here
    nozzle_x_rpy = or_to_rpy(config.LENGTH * 100)
    motor_cg_rpy = nozzle_x_rpy + motor.center_of_mass(0)  # nozzle_to_combustion_chamber: +offset points toward nose

    d_dry_unknown_cg = None  # solved below
    # system_cg = (m_dry*cg_dry + m_motor*motor_cg) / m_total  =>  cg_dry:
    cg_dry_rpy = (system_cg * m_total - m_motor * motor_cg_rpy) / m_dry

    d_dry = cg_dry_rpy - system_cg
    d_motor = motor_cg_rpy - system_cg

    i_total_11 = config.INERTIA_LONG_T0_WITH_MOTOR
    i_total_33 = config.INERTIA_ROT_T0_WITH_MOTOR
    i_motor_11 = motor.I_11(0)
    i_motor_33 = motor.I_33(0)

    i_dry_11 = i_total_11 - m_dry * d_dry**2 - i_motor_11 - m_motor * d_motor**2
    i_dry_33 = i_total_33 - i_motor_33  # roll axis: axial shift doesn't change it, no parallel-axis term

    return {
        "cg_dry_rpy": cg_dry_rpy,
        "i_dry_11": i_dry_11,
        "i_dry_33": i_dry_33,
        "motor_cg_rpy": motor_cg_rpy,
        "nozzle_x_rpy": nozzle_x_rpy,
    }


def build_rocket():
    motor = build_motor()
    derived = _solve_dry_inertia()

    rocket = Rocket(
        radius=config.RADIUS,
        mass=config.DRY_MASS_NO_MOTOR,
        inertia=(derived["i_dry_11"], derived["i_dry_11"], derived["i_dry_33"]),
        power_off_drag=os.path.join(config.DATA_DIR, "rockets", "power_off_drag.csv"),
        power_on_drag=os.path.join(config.DATA_DIR, "rockets", "power_on_drag.csv"),
        center_of_mass_without_motor=derived["cg_dry_rpy"],
        coordinate_system_orientation="tail_to_nose",
    )

    rocket.add_motor(motor, position=derived["nozzle_x_rpy"])

    rocket.add_nose(
        length=config.NOSE_CONE_LENGTH,
        kind=config.NOSE_CONE_TYPE,
        position=0,
    )
    rocket.add_trapezoidal_fins(
        n=config.FIN_COUNT,
        root_chord=config.FIN_ROOT_CHORD,
        tip_chord=config.FIN_TIP_CHORD,
        span=config.FIN_SPAN,
        sweep_length=config.FIN_SWEEP,
        cant_angle=config.FIN_CANT_ANGLE,
        position=or_to_rpy(config.FIN_POSITION_FROM_NOSE * 100),
    )
    rocket.set_rail_buttons(
        upper_button_position=or_to_rpy(config.RAIL_BUTTON_UPPER_FROM_NOSE * 100),
        lower_button_position=or_to_rpy(config.RAIL_BUTTON_LOWER_FROM_NOSE * 100),
    )

    return rocket, derived


if __name__ == "__main__":
    rocket, derived = build_rocket()

    mass_check = rocket.total_mass(0)
    mass_err = abs(mass_check - config.LAUNCH_MASS) / config.LAUNCH_MASS * 100
    print(f"total_mass(0) = {mass_check:.4f} kg (target {config.LAUNCH_MASS} kg, {mass_err:.3f}% error)")
    assert mass_err < 0.5, "mass check failed CRS acceptance tolerance"

    i11_check = rocket.I_11(0)
    i33_check = rocket.I_33(0)
    i11_err = abs(i11_check - config.INERTIA_LONG_T0_WITH_MOTOR) / config.INERTIA_LONG_T0_WITH_MOTOR * 100
    i33_err = abs(i33_check - config.INERTIA_ROT_T0_WITH_MOTOR) / config.INERTIA_ROT_T0_WITH_MOTOR * 100
    print(f"I_11(0) = {i11_check:.4f} kg m2 (target {config.INERTIA_LONG_T0_WITH_MOTOR}, {i11_err:.3f}% error)")
    print(f"I_33(0) = {i33_check:.4f} kg m2 (target {config.INERTIA_ROT_T0_WITH_MOTOR}, {i33_err:.3f}% error)")
    print(f"dry CG = {derived['cg_dry_rpy']:.4f} m (rpy frame) = {-derived['cg_dry_rpy']*100:.2f} cm from nose")
    print(f"dry I_11 = {derived['i_dry_11']:.4f} kg m2, dry I_33 = {derived['i_dry_33']:.4f} kg m2")

    os.makedirs(os.path.join(config.OUTPUTS_DIR, "figures"), exist_ok=True)
    rocket.plots.static_margin()
    import matplotlib.pyplot as plt

    plt.savefig(os.path.join(config.OUTPUTS_DIR, "figures", "static_margin.png"))
    plt.close("all")
    print("Wrote outputs/figures/static_margin.png")
