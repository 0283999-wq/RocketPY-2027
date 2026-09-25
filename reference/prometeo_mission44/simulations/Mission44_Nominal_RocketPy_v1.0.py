"""Mission 44 PROMETEO - Nominal flight case (CRS 10.1.11, mandatory).

Sugarcane Launch Range, 4 m rail, single altitude-triggered main parachute
(REC 8.1.6). Run standalone: python simulations/Mission44_Nominal_RocketPy_v1.0.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.prometeo.environment import build_environment
from src.prometeo.recovery import add_main_parachute
from src.prometeo.rocket import build_rocket
from rocketpy import Flight
from rocketpy.simulation import FlightDataExporter

OUT_FIG = os.path.join(config.OUTPUTS_DIR, "figures")
OUT_DATA = os.path.join(config.OUTPUTS_DIR, "data")


def main():
    os.makedirs(OUT_FIG, exist_ok=True)
    os.makedirs(OUT_DATA, exist_ok=True)

    env = build_environment(site="brasil", atmos="custom")
    rocket, derived = build_rocket()
    cd_s = add_main_parachute(rocket, config.DRY_MASS_NO_MOTOR)
    print(f"Calibrated main cd_s = {cd_s:.3f} m2 (target descent {config.TARGET_DESCENT_RATE} m/s)")

    flight = Flight(
        rocket=rocket,
        environment=env,
        rail_length=config.RAIL_LENGTH,
        inclination=config.RAIL_INCLINATION,
        heading=config.RAIL_HEADING,
    )

    flight.info()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    flight.plots.trajectory_3d()
    plt.savefig(os.path.join(OUT_FIG, "nominal_trajectory_3d.png"))
    plt.close("all")
    flight.plots.linear_kinematics_data()
    plt.savefig(os.path.join(OUT_FIG, "nominal_linear_kinematics.png"))
    plt.close("all")
    flight.plots.attitude_data()
    plt.savefig(os.path.join(OUT_FIG, "nominal_attitude.png"))
    plt.close("all")

    exporter = FlightDataExporter(flight)
    exporter.export_kml(
        file_name=os.path.join(OUT_DATA, "nominal_trajectory.kml"),
        extrude=True,
        altitude_mode="relativetoground",
    )
    exporter.export_data(os.path.join(OUT_DATA, "nominal_flight_data.csv"))

    print("\n=== NOMINAL SUMMARY ===")
    print(f"Apogee AGL: {flight.apogee - env.elevation:.1f} m at t={flight.apogee_time:.2f} s")
    print(f"Max speed: {flight.max_speed:.1f} m/s")
    print(f"Rail exit velocity: {flight.out_of_rail_velocity:.1f} m/s")
    print(f"Max stability margin: {max(flight.stability_margin(t) for t in flight.time)  :.2f} cal")
    print(f"Impact velocity: {flight.impact_velocity:.2f} m/s")
    print(f"Drift distance: {(flight.x_impact**2 + flight.y_impact**2)**0.5:.1f} m")


if __name__ == "__main__":
    main()
