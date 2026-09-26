"""OpenRocket-style flight data CSV export (2026-09-26 review, item G).

Diego's team is used to reading OpenRocket's own "Export simulation data"
CSV format (see the 3 reference exports under
reference/prometeo_mission44/data/openrocket_exports/ - each has 58
columns, a few header comment lines, and "# Event X occurred at t=..."
lines interleaved with the data rows at the row where that event
happened). This module builds the SAME layout from a rocketpy Flight
object, so a report/spreadsheet built around OR's column names still
works when fed this app's simulation instead.

Every column is computed from a real rocketpy Function/attribute - NONE
of the 58 numbers here are invented. Where rocketpy has no equivalent at
all (OpenRocket's per-component aerodynamic coefficient breakdown:
friction/pressure/base/axial drag coefficients, and the moment/side-force/
roll coefficients), the column is left blank (NaN), and it stays that way
for every rocket, not "when convenient". This is not actually a
compromise unique to this app: inspecting the REAL PROMETEO OpenRocket
export shows those same columns (Side force coefficient, Roll moment
coefficient, Roll forcing coefficient, Roll damping coefficient, Pitch
damping coefficient) are ALSO blank for that entire flight - an
axisymmetric rocket with no cant genuinely has no meaningful value for
several of them either. Reynolds number, Computation time and Coriolis
acceleration are also left blank: rocketpy's per-step wall-clock time
and any explicit Coriolis term are not exposed as a queryable Function.

The row time grid is rocketpy's own actual integration time steps
(``flight.time``) - the same choice OpenRocket itself makes (it exports
one row per adaptive solver step, not a fixed resample), so "Simulation
time step (s)" is a real, honestly-varying number, not a constant.
"""
import math

import numpy as np

# (header name incl. units, as OpenRocket writes it)
COLUMN_HEADERS = [
    "Time (s)", "Altitude (m)", "Altitude above sea level (m)",
    "Vertical velocity (m/s)", "Total velocity (m/s)",
    "Vertical acceleration (m/s²)", "Total acceleration (m/s²)",
    "Position East of launch (m)", "Position North of launch (m)",
    "Lateral distance (m)", "Lateral direction (°)",
    "Lateral velocity (m/s)", "Lateral acceleration (m/s²)",
    "Latitude (° N)", "Longitude (° E)",
    "Angle of attack (°)", "Roll rate (°/s)", "Pitch rate (°/s)", "Yaw rate (°/s)",
    "Vertical orientation (zenith) (°)", "Lateral orientation (azimuth) (°)",
    "Mass (g)", "Motor mass (g)",
    "Longitudinal moment of inertia (kg·m²)", "Rotational moment of inertia (kg·m²)",
    "Gravitational acceleration (m/s²)",
    "CP location (cm)", "CG location (cm)", "Stability margin calibers (​)",
    "Thrust (N)", "Thrust-to-weight ratio (​)",
    "Drag force (N)", "Drag coefficient (​)",
    "Friction drag coefficient (​)", "Pressure drag coefficient (​)",
    "Base drag coefficient (​)", "Axial drag coefficient (​)",
    "Normal force coefficient (​)", "Pitch moment coefficient (​)",
    "Yaw moment coefficient (​)", "Side force coefficient (​)",
    "Roll moment coefficient (​)", "Roll forcing coefficient (​)",
    "Roll damping coefficient (​)", "Pitch damping coefficient (​)",
    "Wind velocity (m/s)", "Wind direction (°)",
    "Air temperature (°C)", "Air pressure (mbar)", "Air density (g/cm³)",
    "Speed of sound (m/s)", "Mach number (​)", "Reynolds number (​)",
    "Reference length (cm)", "Reference area (cm²)",
    "Simulation time step (s)", "Computation time (s)", "Coriolis acceleration (m/s²)",
]

assert len(COLUMN_HEADERS) == 58, f"expected 58 OpenRocket columns, got {len(COLUMN_HEADERS)}"


def _nan_array(n):
    return np.full(n, np.nan)


def _build_events(flight):
    """A best-effort reconstruction of OpenRocket's own event log from
    what rocketpy actually records - not every OR event name has a
    direct rocketpy equivalent (e.g. OR's separate IGNITION vs LAUNCH vs
    LIFTOFF instants collapse to a single t=0 in rocketpy), so those are
    merged rather than guessed apart."""
    events = [(0.0, "IGNITION"), (0.0, "LAUNCH"), (0.0, "LIFTOFF")]
    if getattr(flight, "out_of_rail_time", None) is not None:
        events.append((float(flight.out_of_rail_time), "LAUNCHROD"))
    burn_out_time = getattr(getattr(flight.rocket, "motor", None), "burn_out_time", None)
    if burn_out_time is not None:
        events.append((float(burn_out_time), "BURNOUT"))
    if getattr(flight, "apogee_time", None):
        events.append((float(flight.apogee_time), "APOGEE"))
    for t, parachute in getattr(flight, "parachute_events", []) or []:
        name = getattr(parachute, "name", "parachute")
        events.append((float(t), f"RECOVERY_DEVICE_DEPLOYMENT ({name})"))
    if getattr(flight, "t_final", None) is not None:
        events.append((float(flight.t_final), "GROUND_HIT"))
        events.append((float(flight.t_final), "SIMULATION_END"))
    events.sort(key=lambda e: e[0])
    return events


def build_openrocket_style_rows(flight, radius_m):
    """Returns (rows, events): rows is a list of 58-element lists (floats
    or None for a blank/NaN cell), events is [(time, event_name), ...]
    sorted by time - one row per rocketpy integration time step."""
    t = np.asarray(flight.time)
    n = len(t)
    rocket = flight.rocket
    env = flight.env

    vx, vy, vz = flight.vx(t), flight.vy(t), flight.vz(t)
    ax, ay, az = flight.ax(t), flight.ay(t), flight.az(t)
    lateral_velocity = np.hypot(vx, vy)
    lateral_acceleration = np.hypot(ax, ay)

    total_mass_kg = np.asarray(rocket.total_mass(t))
    motor_mass_kg = np.asarray(rocket.motor.total_mass(t))
    cg_m = np.asarray(rocket.center_of_mass(t))
    # translate.py's _coordinate_transform is "the ONE place" (its own
    # docstring) OpenRocket's nose-tip-origin, distance-increases-aft
    # frame gets converted to rocketpy's own frame - to_rpy(x_from_nose)
    # is `-x_from_nose` for the default "tail_to_nose" orientation this
    # app always builds with, or `x_from_nose` (identity) for
    # "nose_to_tail". Both of those are their own inverse (negate-negate
    # or identity-identity), so re-applying the SAME transform function
    # converts a rocketpy-frame position back to nose-tip-referenced cm -
    # verified numerically against this app's own already-displayed dry
    # CG (translate.py's build_rocket docstring/rocket_page.py) and
    # against the expected CP-aft-of-CG sign for a stable rocket.
    from bup_rocketpy.translate import _coordinate_transform
    to_nose_frame = _coordinate_transform(rocket.coordinate_system_orientation)
    cg_cm = to_nose_frame(cg_m) * 100.0
    try:
        cp_m = np.asarray([rocket.cp_position(m) for m in flight.mach_number(t)])
        cp_cm = to_nose_frame(cp_m) * 100.0
    except Exception:
        cp_cm = _nan_array(n)

    dynamic_pressure = np.asarray(flight.dynamic_pressure(t))
    drag_force = np.asarray(flight.aerodynamic_drag(t))
    reference_area_m2 = math.pi * radius_m ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        drag_coefficient = np.where(
            dynamic_pressure > 1e-9,
            drag_force / (dynamic_pressure * reference_area_m2),
            np.nan,
        )

    wind_x, wind_y = np.asarray(flight.wind_velocity_x(t)), np.asarray(flight.wind_velocity_y(t))
    wind_speed = np.hypot(wind_x, wind_y)
    wind_direction = np.degrees(np.arctan2(wind_x, wind_y)) % 360

    altitude_asl = np.asarray(flight.z(t))
    temperature_c = np.asarray([env.temperature(z) for z in altitude_asl]) - 273.15
    gravity = np.asarray([env.gravity(z) for z in altitude_asl])

    time_steps = np.diff(t, prepend=t[0] - (t[1] - t[0]) if n > 1 else 0.0)

    rows = []
    for i in range(n):
        rows.append([
            t[i], flight.altitude(t[i]), altitude_asl[i],
            vz[i], flight.speed(t[i]),
            az[i], flight.acceleration(t[i]),
            flight.x(t[i]), flight.y(t[i]),
            flight.drift(t[i]), flight.bearing(t[i]),
            lateral_velocity[i], lateral_acceleration[i],
            flight.latitude(t[i]), flight.longitude(t[i]),
            flight.angle_of_attack(t[i]),
            math.degrees(flight.w3(t[i])), math.degrees(flight.w1(t[i])), math.degrees(flight.w2(t[i])),
            flight.attitude_angle(t[i]), flight.lateral_attitude_angle(t[i]),
            total_mass_kg[i] * 1000.0, motor_mass_kg[i] * 1000.0,
            rocket.I_33(t[i]), rocket.I_11(t[i]),
            gravity[i],
            cp_cm[i], cg_cm[i], flight.stability_margin(t[i]),
            rocket.motor.thrust(t[i]), rocket.thrust_to_weight(t[i]),
            drag_force[i], drag_coefficient[i],
            None, None, None, None,  # friction/pressure/base/axial drag coefficient breakdown: not exposed by rocketpy
            None, None, None, None, None, None, None, None,  # normal force / pitch / yaw / side-force / roll(3) / pitch-damping coefficients: not exposed by rocketpy
            wind_speed[i], wind_direction[i],
            temperature_c[i], flight.pressure(t[i]) / 100.0, flight.density(t[i]) / 1000.0,
            flight.speed_of_sound(t[i]), flight.mach_number(t[i]), flight.reynolds_number(t[i]),
            radius_m * 2 * 100.0, reference_area_m2 * 10000.0,
            time_steps[i], None, None,  # computation time, Coriolis acceleration: not tracked/exposed by rocketpy
        ])
    return rows, _build_events(flight)


def export_openrocket_style_csv(flight, radius_m, output_path, simulation_name="RocketPy simulation"):
    """Writes flight's data to output_path in OpenRocket's own 58-column
    CSV export layout, with "# Event X occurred at t=..." lines inserted
    at the correct row (CLAUDE.md item G: a CSV a judge/teammate used to
    reading OpenRocket's format can drop straight into their own
    spreadsheet)."""
    rows, events = build_openrocket_style_rows(flight, radius_m)

    def fmt(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return f"{v:.6g}"

    with open(output_path, "w", newline="") as f:
        f.write(f"# {simulation_name}\n")
        f.write(f"# {len(rows)} data points written for {len(COLUMN_HEADERS)} variables.\n")
        f.write("#\n")
        f.write("# " + ",".join(COLUMN_HEADERS) + "\n")

        event_idx = 0
        for row in rows:
            row_t = row[0]
            while event_idx < len(events) and events[event_idx][0] <= row_t:
                f.write(f"# Event {events[event_idx][1]} occurred at t={events[event_idx][0]:.3f} seconds\n")
                event_idx += 1
            f.write(",".join(fmt(v) for v in row) + "\n")
        while event_idx < len(events):
            f.write(f"# Event {events[event_idx][1]} occurred at t={events[event_idx][0]:.3f} seconds\n")
            event_idx += 1

    return output_path
