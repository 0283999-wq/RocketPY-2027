"""Parametric geometry search, in RocketPy, no OpenRocket involved.

This is the replacement for "iterate fin/nose shape in OpenRocket, read off
the stability margin". Give it a rocket-builder function (mass/inertia/motor
already fixed, only geometry varies) plus ranges for whatever parameters
you're searching, and it grid-searches for configs that satisfy the RCSM
stability/rail-exit rules and reports how close each one lands to the target
apogee. It does not touch mass properties - those come from your own
measurements/estimates, same as always; this tool only searches shape.
"""

import itertools

from rocketpy import Flight

from . import rules


def grid_search(build_rocket_fn, env, rail_length, inclination, heading, param_grid, target_apogee_m, fixed_kwargs=None, verbose=True):
    """param_grid: dict of {param_name: [values...]}. build_rocket_fn(**params,
    **fixed_kwargs) must return a fully configured Rocket (motor + aero
    surfaces + parachute(s) already added). Returns a list of result dicts
    sorted by |apogee - target|, each carrying the params, apogee, margins,
    rail exit velocity and whether it passes the RCSM stability/rail rules.
    """
    fixed_kwargs = fixed_kwargs or {}
    keys = list(param_grid.keys())
    combos = list(itertools.product(*[param_grid[k] for k in keys]))
    results = []

    for combo in combos:
        params = dict(zip(keys, combo))
        try:
            rocket = build_rocket_fn(**params, **fixed_kwargs)
            flight = Flight(
                rocket=rocket,
                environment=env,
                rail_length=rail_length,
                inclination=inclination,
                heading=heading,
                terminate_on_apogee=True,  # faster - we only need apogee/margins here, not descent
            )
        except Exception as exc:  # a bad geometry combo can make rocketpy choke - skip it, don't kill the sweep
            if verbose:
                print(f"SKIP {params}: {exc}")
            continue

        margins = [flight.stability_margin(t) for t in flight.time]
        min_margin, max_margin = min(margins), max(margins)
        rail_v = flight.out_of_rail_velocity
        apogee_agl = flight.apogee - env.elevation

        stable = rules.MIN_STATIC_MARGIN_CAL <= min_margin and max_margin < rules.MAX_STATIC_MARGIN_CAL
        rail_ok = rail_v >= rules.RAIL_EXIT_VELOCITY_ANALYSIS_FLOOR

        result = {
            "params": params,
            "apogee_agl": apogee_agl,
            "apogee_error_m": apogee_agl - target_apogee_m,
            "min_margin_cal": min_margin,
            "max_margin_cal": max_margin,
            "rail_exit_velocity": rail_v,
            "stable": stable,
            "rail_ok": rail_ok,
            "feasible": stable and rail_ok,
        }
        results.append(result)
        if verbose:
            flag = "OK" if result["feasible"] else "--"
            print(f"[{flag}] {params} -> apogee {apogee_agl:.0f}m (target {target_apogee_m:.0f}m), "
                  f"margin [{min_margin:.2f},{max_margin:.2f}] cal, rail {rail_v:.1f} m/s")

    results.sort(key=lambda r: (not r["feasible"], abs(r["apogee_error_m"])))
    return results
