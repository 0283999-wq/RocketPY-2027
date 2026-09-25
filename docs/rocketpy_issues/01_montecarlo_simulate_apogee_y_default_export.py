"""Minimal repro: does MonteCarlo.simulate()'s DEFAULT export_list crash
on an unstable sample?

Claimed bug (2026-09-26 review, first pass): "MonteCarlo.simulate()'s
default export list references a Flight attribute that crashes on any
unstable sample." Re-checked against rocketpy==1.13.0's actual source
before writing this: `apogee_x`/`apogee_y` ARE valid Flight attributes
(rocketpy/simulation/monte_carlo.py's __check_export_list standard_output
set includes them, and Flight does define them) - so the ORIGINAL claim,
as literally stated, does not hold up against the source. This script
instead tests the more specific, verifiable version of the claim: does
MonteCarlo.simulate() crash when a sampled rocket configuration is
aerodynamically unstable enough to blow up the ODE integrator?

STATUS: see the printed verdict at the end.
"""
import sys

sys.path.insert(0, "docs/rocketpy_issues")
from _minimal_rocket import build_environment, build_motor, build_rocket  # noqa: E402

from rocketpy import Flight, MonteCarlo  # noqa: E402
from rocketpy.stochastic import (  # noqa: E402
    StochasticEnvironment,
    StochasticFlight,
    StochasticRocket,
    StochasticSolidMotor,
)

rocket = build_rocket()
env = build_environment()
motor = build_motor()
flight = Flight(rocket=rocket, environment=env, rail_length=1.0, inclination=85, heading=0)

stochastic_env = StochasticEnvironment(environment=env, wind_velocity_x_factor=(1, 5))
stochastic_motor = StochasticSolidMotor(solid_motor=motor, total_impulse=(motor.total_impulse, 50))
stochastic_rocket = StochasticRocket(
    rocket=rocket,
    mass=(rocket.mass, 0.3),  # deliberately wide - some samples will be unstable/degenerate
    center_of_mass_without_motor=(-0.6, 0.05),
)
stochastic_flight = StochasticFlight(
    flight=flight,
    inclination=(85, 2), heading=(0, 5),
)

mc = MonteCarlo(
    filename="/tmp/mc_repro",
    environment=stochastic_env,
    rocket=stochastic_rocket,
    flight=stochastic_flight,
)

try:
    mc.simulate(number_of_simulations=15, append=False)
    print("VERDICT: MonteCarlo.simulate() completed without crashing (5 simulations, wide uncertainties).")
except Exception as exc:
    print(f"VERDICT: MonteCarlo.simulate() CRASHED: {type(exc).__name__}: {exc}")
    raise
