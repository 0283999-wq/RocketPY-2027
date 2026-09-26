"""Builds a JSON-serializable, DECIMATED flight dataset for the 3D
playback view (2026-09-27 review item 7, Mission Control redesign).
Kept separate from plotting.py (that module makes matplotlib PNGs; this
one feeds the three.js viewer in static/playback.js - plain numbers
only, no plotting library import, no NiceGUI import either, so it stays
usable from a script/test with no browser involved).

Decimated to a fixed number of frames for smooth client-side animation
on a normal laptop - the full-resolution flight is still available via
the CSV export, this is a DISPLAY copy only (the review's own "decimate
trajectories for display, keep full data for export" instruction).
"""


def build_playback_data(flight, motor=None, n_frames=250):
    """Returns {"frames": [...], "events": [...], "bounds": {...}}.

    frames[i] = {t, x, y, z, speed, mach, accel} - x/y/z are in
    RocketPy's own flight frame (x=East, y=North, z=up), with z already
    converted to AGL (the site's own elevation subtracted), matching
    every other altitude figure this app shows.
    """
    elevation = flight.env.elevation
    t0, t1 = float(flight.time[0]), float(flight.t_final)
    n_frames = max(2, n_frames)
    if t1 <= t0:
        ts = [t0, t0]
    else:
        step = (t1 - t0) / (n_frames - 1)
        ts = [t0 + i * step for i in range(n_frames)]

    frames = []
    for t in ts:
        frames.append({
            "t": t,
            "x": float(flight.x(t)), "y": float(flight.y(t)), "z": float(flight.z(t) - elevation),
            "speed": float(flight.speed(t)),
            "mach": float(flight.mach_number(t)),
            "accel": float(flight.acceleration(t)),
        })

    def _point_at(t, name):
        return {"t": float(t), "name": name, "x": float(flight.x(t)), "y": float(flight.y(t)), "z": float(flight.z(t) - elevation)}

    events = []
    try:
        events.append(_point_at(flight.out_of_rail_time, "Rail exit"))
    except Exception:
        pass
    if motor is not None:
        try:
            events.append(_point_at(motor.burn_time[1], "Burnout"))
        except Exception:
            pass
    try:
        events.append(_point_at(flight.apogee_time, "Apogee"))
    except Exception:
        pass
    for t, chute in getattr(flight, "parachute_events", []):
        try:
            events.append(_point_at(t, getattr(chute, "name", "Parachute")))
        except Exception:
            pass
    try:
        events.append(_point_at(flight.t_final, "Landing"))
    except Exception:
        pass
    events.sort(key=lambda e: e["t"])

    xs = [f["x"] for f in frames]
    ys = [f["y"] for f in frames]
    zs = [f["z"] for f in frames]
    bounds = {
        "x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys),
        "z_min": min(0.0, min(zs)), "z_max": max(max(zs), 1.0),
    }

    return {"frames": frames, "events": events, "bounds": bounds}
