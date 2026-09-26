"""Side-profile drawing of a loaded rocket, built straight from parsed
.ork geometry (nose, tubes, transitions, fins, motor), with CG/CP markers,
static margin and dimensions (2026-09-26 review, item 2 - "Rocket" page).

No bup_rocketpy.translate import needed for the drawing itself - it only
needs the parsed geometry (ork_reader.ParsedRocket) plus, optionally, a
dry_cg_m/cp_m/motor length+position to overlay markers. Kept dependency-
light (matplotlib only) so it's reusable from both the Rocket page and the
Results page.
"""
import math

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from bup_rocketpy.gui import theme
from bup_rocketpy.ork_reader import airframe_length_m

matplotlib.use("Agg")


def _nose_profile_points(nose, n=40):
    """A reasonable outline for common OpenRocket nose shapes - exact
    enough for a schematic side view, not a CFD-grade profile."""
    x = np.linspace(0, nose.length, n)
    r = nose.aft_radius or 0.05
    shape = (nose.shape or "").lower()
    if shape in ("conical",):
        y = r * (x / nose.length)
    elif shape in ("ellipsoid", "elliptical"):
        y = r * np.sqrt(1 - (1 - x / nose.length) ** 2)
    elif shape in ("parabolic",):
        y = r * (2 * (x / nose.length) - (x / nose.length) ** 2)
    else:  # ogive, tangent, von karman, haack, powerseries - all close to this generic power-law silhouette for a schematic
        y = r * (x / nose.length) ** 0.6
    return x, y


def draw_side_profile(parsed, dry_cg_m=None, cp_m=None, motor_length_m=None, static_margin_cal=None, title=None, dark=False):
    """Returns a matplotlib Figure. All positions in m from nose tip."""
    bg = theme.DARK_SURFACE if dark else theme.LIGHT_SURFACE
    fg = theme.DARK_TEXT if dark else theme.LIGHT_TEXT
    fig, ax = plt.subplots(figsize=(10, 3.2), dpi=130)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    body_radius = next((t.radius for t in parsed.body_tubes if t.radius), 0.05)

    if parsed.nose is not None:
        nx, ny = _nose_profile_points(parsed.nose)
        ax.plot(nx, ny, color=fg, linewidth=1.4)
        ax.plot(nx, -ny, color=fg, linewidth=1.4)
        ax.fill_between(nx, -ny, ny, color=theme.GOLD, alpha=0.15)

    for tube in parsed.body_tubes:
        r = tube.radius or body_radius
        ax.add_patch(plt.Rectangle((tube.position_m, -r), tube.length, 2 * r, fill=True, facecolor=theme.GOLD, alpha=0.10, edgecolor=fg, linewidth=1.2))

    for tr in parsed.transitions:
        fr, ar = tr.fore_radius or body_radius, tr.aft_radius or body_radius
        xs = [tr.position_m, tr.position_m + tr.length, tr.position_m + tr.length, tr.position_m]
        ys = [fr, ar, -ar, -fr]
        ax.fill(xs, ys, facecolor=theme.GOLD, alpha=0.10, edgecolor=fg, linewidth=1.2)

    for fin in parsed.fins:
        root_x0 = fin.position_m
        xs = [root_x0, root_x0 + fin.sweep_length, root_x0 + fin.sweep_length + fin.tip_chord, root_x0 + fin.root_chord]
        ys_top = [body_radius, body_radius + fin.span, body_radius + fin.span, body_radius]
        ax.fill(xs, ys_top, facecolor=theme.WINE, alpha=0.55, edgecolor=fg, linewidth=1.0)
        ys_bot = [-y for y in ys_top]
        ax.fill(xs, ys_bot, facecolor=theme.WINE, alpha=0.55, edgecolor=fg, linewidth=1.0)

    if motor_length_m and (parsed.body_tubes or parsed.transitions):
        tail_x = airframe_length_m(parsed)
        ax.add_patch(plt.Rectangle((tail_x - motor_length_m, -body_radius * 0.6), motor_length_m, body_radius * 1.2, fill=True, facecolor="#555555", alpha=0.6))

    for pm in parsed.point_masses:
        ax.plot([pm.position_m], [0], marker="s", color="#3A6EA5", markersize=6)
        ax.annotate(pm.name, (pm.position_m, 0), xytext=(0, 10), textcoords="offset points", fontsize=6, color=fg, rotation=90, ha="center")

    if dry_cg_m is not None:
        ax.axvline(dry_cg_m, color=theme.WINE, linestyle="--", linewidth=1.5)
        ax.annotate(f"CG {dry_cg_m*100:.1f} cm", (dry_cg_m, body_radius * 1.6), color=theme.WINE, fontsize=9, ha="center", fontweight="bold")
    if cp_m is not None:
        ax.axvline(cp_m, color=theme.GOLD, linestyle="--", linewidth=1.5)
        ax.annotate(f"CP {cp_m*100:.1f} cm", (cp_m, -body_radius * 2.0), color=theme.GOLD, fontsize=9, ha="center", fontweight="bold")

    total_length = airframe_length_m(parsed) or (parsed.nose.length if parsed.nose else 1.0)
    subtitle = f"Length {total_length*100:.1f} cm, diameter {body_radius*2*100:.1f} cm"
    if static_margin_cal is not None:
        subtitle += f", static margin {static_margin_cal:.2f} cal"
    ax.set_title((title or parsed.name) + "\n" + subtitle, color=fg, fontsize=11)
    ax.set_xlim(-0.05 * total_length, total_length * 1.15)
    ax.set_ylim(-body_radius * 3.2, body_radius * 3.2)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig
