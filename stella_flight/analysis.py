"""Phase 6: questions only RocketPy can answer (2026-09-26 review, item 3).

1. Weathercocking: sweep apogee vs static margin by adding a ballast point
   mass at the nose tip (how Diego would actually do it on the real
   rocket - CLAUDE.md Sec 6), searching for the apogee optimum within the
   mandatory 1.5-4 cal stability window (FLT 4.3.5/4.3.6).
2. Drag comparison: two power_off/power_on Cd-curve pairs, each run
   through Monte Carlo with the SAME random seed (common random numbers),
   reporting the apogee difference with a confidence interval.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from stella_flight import translate
from stella_flight.rcsm import MAX_STATIC_MARGIN_CAL, MIN_STATIC_MARGIN_CAL


@dataclass
class WeathercockingPoint:
    ballast_mass_kg: float
    dry_mass_kg: float
    dry_cg_m: float
    static_margin_cal: float
    apogee_agl_m: float
    in_valid_range: bool


@dataclass
class WeathercockingResult:
    points: list
    best_point: object  # WeathercockingPoint with highest apogee among in_valid_range points, or None
    hit_lower_bound: bool  # True if the optimum is the smallest-margin point tested still in range (CLAUDE.md: "it will probably land on the lower bound, and the app must say so")


def weathercocking_sweep(parsed, parsed_eng, eng_path, power_off_drag, power_on_drag, base_dry_mass_kg, base_dry_cg_m, i_axial, i_transverse, radius_m, ballast_masses_kg=None):
    """Adds ballast at the nose tip (position 0, in the "m from nose"
    frame) - moving CG forward increases static margin. Reruns a full
    flight per ballast level (deterministic, not a Monte Carlo per point -
    keeps this fast enough to sweep in the UI; wrap in Monte Carlo
    per-point separately if a full uncertainty band per point is wanted)."""
    from rocketpy import Flight

    if ballast_masses_kg is None:
        ballast_masses_kg = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]

    points = []
    for ballast in ballast_masses_kg:
        new_total_mass = base_dry_mass_kg + ballast
        # ballast at the nose tip (x=0): new_cg = (base_mass*base_cg + ballast*0) / new_total_mass
        new_cg = (base_dry_mass_kg * base_dry_cg_m) / new_total_mass
        # parallel-axis: shifting mass distribution changes I_transverse; ballast at x=0 contributes ballast*(0-new_cg)^2, and the rest of the rocket's own inertia about the NEW cg shifts by base_mass*(new_cg-base_cg)^2 relative to its own inertia about the OLD cg
        d_base = new_cg - base_dry_cg_m
        new_i_transverse = i_transverse + base_dry_mass_kg * d_base**2 + ballast * new_cg**2
        new_i_axial = i_axial  # ballast on the centerline doesn't add roll inertia

        mass_est = translate.MassEstimate(new_total_mass, new_cg, f"ballast sweep: {ballast:.3f} kg at nose tip")
        motor = translate.build_motor(parsed_eng, eng_path)
        rocket = translate.build_rocket(parsed, motor, mass_est, new_i_axial, new_i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=False)
        env = translate.build_environment(parsed.launch)
        flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m, inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg, terminate_on_apogee=True)

        margin0 = flight.stability_margin(0)
        in_range = MIN_STATIC_MARGIN_CAL <= margin0 <= MAX_STATIC_MARGIN_CAL
        points.append(WeathercockingPoint(ballast, new_total_mass, new_cg, margin0, flight.apogee - env.elevation, in_range))

    valid = [p for p in points if p.in_valid_range]
    best = max(valid, key=lambda p: p.apogee_agl_m) if valid else None
    hit_lower_bound = False
    if best is not None and valid:
        min_margin_in_valid = min(p.static_margin_cal for p in valid)
        hit_lower_bound = abs(best.static_margin_cal - min_margin_in_valid) < 0.05

    return WeathercockingResult(points=points, best_point=best, hit_lower_bound=hit_lower_bound)


@dataclass
class DragComparisonResult:
    apogee_a_samples: list
    apogee_b_samples: list
    mean_difference_m: float
    difference_ci_90: tuple  # (low, high)
    n_paired: int


def drag_comparison(parsed, parsed_eng, eng_path, drag_pair_a, drag_pair_b, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, output_dir, seed=12345):
    """drag_pair_a/b: (power_off_drag_path, power_on_drag_path) tuples.
    Runs each through the SAME seeded Monte Carlo (common random numbers)
    so the paired difference isolates the drag-curve effect from sampling
    noise, per CLAUDE.md Sec 6 point 2."""
    from stella_flight import monte_carlo

    result_a = monte_carlo.run_monte_carlo(parsed, parsed_eng, eng_path, drag_pair_a[0], drag_pair_a[1], dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, output_dir + "_a", include_recovery=False, seed=seed)
    result_b = monte_carlo.run_monte_carlo(parsed, parsed_eng, eng_path, drag_pair_b[0], drag_pair_b[1], dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, output_dir + "_b", include_recovery=False, seed=seed)

    n = min(result_a.n_completed, result_b.n_completed)
    a = np.array(result_a.apogee_samples[:n])
    b = np.array(result_b.apogee_samples[:n])
    diffs = b - a  # b relative to a

    mean_diff = float(diffs.mean()) if n else float("nan")
    if n > 1:
        se = diffs.std(ddof=1) / math.sqrt(n)
        ci = (mean_diff - 1.645 * se, mean_diff + 1.645 * se)  # 90% CI, normal approx
    else:
        ci = (float("nan"), float("nan"))

    return DragComparisonResult(apogee_a_samples=list(a), apogee_b_samples=list(b), mean_difference_m=mean_diff, difference_ci_90=ci, n_paired=n)
