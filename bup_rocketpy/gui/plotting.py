"""Per-quantity flight plots (2026-09-25 review, Section 5b): one plot
per physical quantity, each its own tab/PNG, instead of rocketpy's 3
built-in composite figures - CLAUDE.md/tonight's review specifically
lists which quantities are wanted. No NiceGUI import (kept in gui/ only
because it needs OUTPUTS_DIR-style file writing, same pattern as
rocket_drawing.py) - pure matplotlib + rocketpy Function calls.
"""
import math
import os

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

GOLD, WINE = "#B79357", "#8A1538"


def _line_plot(path, x, y, xlabel, ylabel, title, color=WINE):
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(x, y, color=color, linewidth=1.4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_static_margin_with_limits(path, t, margins):
    """FLT 4.3.5/4.3.6 (CLAUDE.md Sec 5): static margin must stay within
    1.5-4.0 cal through the ascent. Drawn ON the plot (shaded allowed band
    + labelled limit lines) rather than left for a reader to infer from an
    unmarked curve, per the report's "annotated figures" requirement."""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.axhspan(1.5, 4.0, color=GOLD, alpha=0.12, label="RCSM allowed band (1.5-4.0 cal)")
    ax.axhline(1.5, color=WINE, linestyle="--", linewidth=1.0)
    ax.axhline(4.0, color=WINE, linestyle="--", linewidth=1.0)
    t_max = t[-1] * 0.98 if len(t) else 1.0
    ax.text(t_max, 1.5, "FLT 4.3.5 min", color=WINE, fontsize=7, ha="right", va="bottom")
    ax.text(t_max, 4.0, "FLT 4.3.6 max", color=WINE, fontsize=7, ha="right", va="top")
    ax.plot(t, margins, color="#211A16", linewidth=1.4, label="static margin", zorder=5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Margin (cal)")
    ax.set_title("Static margin vs. time", fontsize=10)
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def generate_all_plots(flight, rocket, motor, env, outputs_dir):
    """Returns an ordered {key: (title, path)} dict - the UI just needs
    to make one tab per entry and ui.image(path)."""
    from bup_rocketpy.gui.pipeline import fresh_image_path

    os.makedirs(outputs_dir, exist_ok=True)
    t = flight.time
    apogee_t = flight.apogee_time
    burn_end = motor.burn_time[1]

    plots = {}

    def add(key, title, x, y, xlabel, ylabel):
        path = fresh_image_path(outputs_dir, f"plot_{key}")
        _line_plot(path, x, y, xlabel, ylabel, title)
        plots[key] = (title, path)

    add("altitude", "Altitude AGL", t, [flight.z(ti) - env.elevation for ti in t], "Time (s)", "Altitude AGL (m)")
    add("vertical_velocity", "Vertical velocity", t, [flight.vz(ti) for ti in t], "Time (s)", "vz (m/s)")
    add("total_velocity", "Total velocity", t, [flight.speed(ti) for ti in t], "Time (s)", "Speed (m/s)")

    # Boost-phase-scale acceleration (2026-09-25 review 2(a)): restricted to
    # ascent so the parachute-opening transient (a completely different,
    # much larger scale - see the "instantaneous inflation" KPI) doesn't
    # flatten the boost-phase detail this plot exists to show.
    t_boost = [ti for ti in t if ti <= apogee_t]
    add("acceleration_boost", "Acceleration (boost phase, through apogee)", t_boost, [flight.acceleration(ti) for ti in t_boost], "Time (s)", "Acceleration (m/s2)")

    add("mach", "Mach number", t, [flight.mach_number(ti) for ti in t], "Time (s)", "Mach")

    t_burn = [ti for ti in t if ti <= burn_end] or [0, burn_end]
    add("thrust", "Thrust", t_burn, [motor.thrust(ti) for ti in t_burn], "Time (s)", "Thrust (N)")

    add("mass", "Total mass (rocket + motor)", t, [rocket.total_mass(ti) for ti in t], "Time (s)", "Mass (kg)")

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(t, [rocket.center_of_mass(ti) for ti in t], color=WINE, label="CG")
    ax.plot(t, [rocket.cp_position(flight.mach_number(ti)) for ti in t], color=GOLD, label="CP")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Position (m, rocket's own coordinate frame)")
    ax.set_title("CG and CP vs. time", fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    cg_cp_path = fresh_image_path(outputs_dir, "plot_cg_cp")
    fig.savefig(cg_cp_path)
    plt.close(fig)
    plots["cg_cp"] = ("CG and CP vs. time", cg_cp_path)

    sm_path = fresh_image_path(outputs_dir, "plot_static_margin")
    _plot_static_margin_with_limits(sm_path, t, [flight.stability_margin(ti) for ti in t])
    plots["static_margin"] = ("Static margin vs. time", sm_path)
    add("angle_of_attack", "Angle of attack", t, [flight.angle_of_attack(ti) for ti in t], "Time (s)", "AoA (deg)")
    add("dynamic_pressure", "Dynamic pressure", t, [flight.dynamic_pressure(ti) / 1000.0 for ti in t], "Time (s)", "Dynamic pressure (kPa)")

    # Drag coefficient vs. Mach - the CURVE ACTUALLY USED (power_off/power_on
    # drag Function objects the rocket was built with), not a derived
    # flight time series.
    fig, ax = plt.subplots(figsize=(6, 3.5))
    mach_range = [i * 0.02 for i in range(int(max(flight.mach_number(ti) for ti in t) / 0.02) + 5)]
    try:
        ax.plot(mach_range, [rocket.power_off_drag(m) for m in mach_range], color=WINE, label="power off (coast)")
        ax.plot(mach_range, [rocket.power_on_drag(m) for m in mach_range], color=GOLD, label="power on (boost)")
        ax.legend()
    except Exception:
        pass
    ax.set_xlabel("Mach")
    ax.set_ylabel("Cd")
    ax.set_title("Drag coefficient vs. Mach (curve actually used)", fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    cd_path = fresh_image_path(outputs_dir, "plot_cd_mach")
    fig.savefig(cd_path)
    plt.close(fig)
    plots["cd_mach"] = ("Drag coefficient vs. Mach", cd_path)

    # Descent velocity vs. time - zoomed to the descent phase only (post-apogee).
    t_descent = [ti for ti in t if ti >= apogee_t]
    if t_descent:
        add("descent_velocity", "Descent velocity (post-apogee)", t_descent, [-flight.vz(ti) for ti in t_descent], "Time (s)", "Descent rate (m/s, positive = down)")

    # Ground track - top-down view of the drift from the pad.
    fig, ax = plt.subplots(figsize=(5, 5))
    xs = [flight.x(ti) for ti in t]
    ys = [flight.y(ti) for ti in t]
    ax.plot(xs, ys, color=WINE)
    ax.scatter([0], [0], color="black", marker="^", s=60, zorder=5, label="Pad")
    ax.scatter([xs[-1]], [ys[-1]], color=GOLD, marker="x", s=60, zorder=5, label="Landing")
    ax.set_xlabel("X - East (m)")
    ax.set_ylabel("Y - North (m)")
    ax.set_title("Ground track (top view)", fontsize=10)
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    track_path = fresh_image_path(outputs_dir, "plot_ground_track")
    fig.savefig(track_path)
    plt.close(fig)
    plots["ground_track"] = ("Ground track", track_path)

    return plots
