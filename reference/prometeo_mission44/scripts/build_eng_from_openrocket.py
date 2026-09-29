"""CRS 10.1.9 - SRAD motor requires a delivered .eng file, not just an OpenRocket export.

Pulls the Time vs Thrust curve straight from Prometeo_Launchsite_BRASIL.csv
(the OpenRocket run the team actually used), reduces it to a RASP-legal point
count with Ramer-Douglas-Peucker, and writes data/motors/Icarus_I_K519.eng.

Run: python scripts/build_eng_from_openrocket.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.prometeo.io_utils import load_openrocket_csv

SOURCE_CSV = os.path.join(config.DATA_DIR, "openrocket_exports", "Prometeo_Launchsite_BRASIL.csv")
OUT_ENG = os.path.join(config.DATA_DIR, "motors", "Icarus_I_K519.eng")

MAX_POINTS = 50
IMPULSE_TOLERANCE = 0.001  # 0.1%, CRS 10.1.9 self-imposed target


def rdp(points, epsilon):
    """Ramer-Douglas-Peucker line simplification. points: (N,2) array [t, thrust]."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    line_vec = end - start
    line_len = np.hypot(*line_vec)
    if line_len == 0:
        dists = np.hypot(*(points[1:-1] - start).T)
    else:
        # perpendicular distance of each point to the start-end chord (2D
        # cross product's z-component; np.cross itself dropped 2D support)
        rel = points[1:-1] - start
        cross_z = line_vec[0] * rel[:, 1] - line_vec[1] * rel[:, 0]
        dists = np.abs(cross_z) / line_len
    if len(dists) == 0:
        return points
    idx = np.argmax(dists)
    if dists[idx] > epsilon:
        left = rdp(points[: idx + 2], epsilon)
        right = rdp(points[idx + 1 :], epsilon)
        return np.vstack([left[:-1], right])
    return np.array([start, end])


def resample_preserving_impulse(t, thrust, max_points):
    """Smallest RDP epsilon that still fits under max_points - maximizes
    curve fidelity (and so impulse accuracy) subject to the RASP point cap."""
    points = np.column_stack([t, thrust])
    epsilon_lo, epsilon_hi = 0.0, float(thrust.max())
    best = rdp(points, epsilon_hi)
    for _ in range(30):
        eps = (epsilon_lo + epsilon_hi) / 2
        simplified = rdp(points, eps)
        if len(simplified) <= max_points:
            best = simplified
            epsilon_hi = eps
        else:
            epsilon_lo = eps
    return best


def main():
    df, events = load_openrocket_csv(SOURCE_CSV)
    burnout_t = events["BURNOUT"]  # 3.57 s, see config.BURN_TIME note on the 3.60 briefed value

    curve = df.loc[(df["Time (s)"] >= 0) & (df["Time (s)"] <= burnout_t), ["Time (s)", "Thrust (N)"]]
    curve = curve.dropna().drop_duplicates(subset="Time (s)").sort_values("Time (s)")
    t_raw = curve["Time (s)"].to_numpy()
    thrust_raw = curve["Thrust (N)"].to_numpy()
    if thrust_raw[-1] != 0.0:
        t_raw = np.append(t_raw, burnout_t)
        thrust_raw = np.append(thrust_raw, 0.0)

    true_impulse = np.trapezoid(thrust_raw, t_raw)
    print(f"Raw curve: {len(t_raw)} points, impulse = {true_impulse:.2f} N s, burnout = {burnout_t} s")

    reduced = resample_preserving_impulse(t_raw, thrust_raw, MAX_POINTS)
    # rocketpy's Motor.import_eng() always prepends its own (0, 0) point (see
    # motor.py docstring: "the .eng file must not contain the 0 0 point") -
    # writing our own t=0 row here would collide with it and produce a
    # zero-width interval that NaNs the interpolation slope.
    if reduced[0, 0] == 0.0:
        reduced = reduced[1:]
    # impulse as rocketpy will actually see it: its synthetic (0,0) + our points
    as_loaded = np.vstack([[0.0, 0.0], reduced])
    reduced_impulse = np.trapezoid(as_loaded[:, 1], as_loaded[:, 0])
    err_pct = abs(reduced_impulse - true_impulse) / true_impulse * 100
    print(f"Reduced curve: {len(reduced)} points, impulse = {reduced_impulse:.2f} N s ({err_pct:.4f}% error)")

    if len(reduced) > MAX_POINTS:
        raise RuntimeError(f"RDP reduction gave {len(reduced)} points, RASP wants <= {MAX_POINTS}")
    if err_pct > IMPULSE_TOLERANCE * 100:
        raise RuntimeError(f"impulse error {err_pct:.4f}% exceeds {IMPULSE_TOLERANCE*100}% target")

    os.makedirs(os.path.dirname(OUT_ENG), exist_ok=True)
    with open(OUT_ENG, "w", encoding="ascii") as f:
        f.write(f"; Icarus I - SRAD KNSB 65:35 motor - Team Beyond UP - LASC 2026 Mission 44\n")
        f.write(f"; Total impulse {reduced_impulse:.1f} Ns | Avg thrust {reduced_impulse/burnout_t:.1f} N | Burn time {burnout_t:.2f} s\n")
        f.write(f"; Thrust curve source: Prometeo_Launchsite_BRASIL.csv, resampled {len(t_raw)}->{len(reduced)} pts (RDP, impulse error {err_pct:.4f}%)\n")
        f.write(f"; Casing diameter/length are TODO CONFIRM - see docs/OPEN_ITEMS.md\n")
        casing_dia_mm = config.MOTOR_CASING_DIAMETER * 1000
        casing_len_mm = config.MOTOR_CASING_LENGTH * 1000
        f.write(
            f"{config.MOTOR_DESIGNATION} {casing_dia_mm:.0f} {casing_len_mm:.0f} 0 "
            f"{config.PROPELLANT_MASS:.4f} {config.MOTOR_MASS_LOADED:.4f} BeyondUP\n"
        )
        for t, thrust in reduced:
            f.write(f"   {t:.3f} {thrust:.2f}\n")
        f.write(";\n")

    print(f"Wrote {OUT_ENG}")
    validate(OUT_ENG, reduced_impulse)


def validate(eng_path, expected_impulse):
    from rocketpy import SolidMotor

    motor = SolidMotor(
        thrust_source=eng_path,
        dry_mass=config.MOTOR_DRY_MASS,
        dry_inertia=(0.01, 0.01, 0.001),  # placeholder, motor.py owns the real value
        nozzle_radius=config.NOZZLE_EXIT_RADIUS,  # TODO CONFIRM, see config.py
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
    loaded_impulse = motor.total_impulse
    err_pct = abs(loaded_impulse - expected_impulse) / expected_impulse * 100
    print(f"rocketpy SolidMotor loaded impulse = {loaded_impulse:.2f} N s ({err_pct:.4f}% vs written file)")
    if err_pct > 0.5:
        raise RuntimeError(f"loaded .eng impulse off by {err_pct:.2f}%, expected <=0.5%")
    print("PASS: .eng file validated against rocketpy SolidMotor loader.")


if __name__ == "__main__":
    main()
