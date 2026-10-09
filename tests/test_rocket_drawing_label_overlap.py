"""2026-10-09 review item 11: "on the Rocket drawing the vertical
component labels overlap each other and the title overlaps the 'Length
...' line." PROMETEO's real .ork already has 12 point masses, several
only millimeters apart (e.g. "Sistema de recuperacion" at 0.593 m and
"Plato 3" at 0.602 m) - a real reproduction of the overlap, no invented
rocket needed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.gui import rocket_drawing
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")


def test_many_close_together_point_masses_get_numbered_markers_not_overlapping_names():
    parsed = read_ork(ORK_PATH)
    assert len(parsed.point_masses) >= 10, "fixture assumption: PROMETEO has many point masses to reproduce the overlap with"

    fig = rocket_drawing.draw_side_profile(parsed, dry_cg_m=0.6, cp_m=0.9)
    ax = fig.axes[0]

    # Every point-mass marker is now labelled with just its NUMBER (a
    # short string, never the full component name) - names moved to the
    # separate legend text below the drawing instead.
    number_labels = [t.get_text() for t in ax.texts if t.get_text().strip().isdigit()]
    assert len(number_labels) == len(parsed.point_masses)
    assert sorted(int(n) for n in number_labels) == list(range(1, len(parsed.point_masses) + 1))

    # No text on the drawing itself is a full point-mass NAME anymore
    # (the actual overlap-prone case) - names only appear in the legend.
    all_text = " | ".join(t.get_text() for t in ax.texts)
    assert "Sistema de recuperacion" not in all_text.split("Point masses:")[0] if "Point masses:" in all_text else True

    legend_texts = [t.get_text() for t in ax.texts if "Point masses:" in t.get_text()]
    assert len(legend_texts) == 1
    assert "1=Sistema de recuperacion" in legend_texts[0]

    import matplotlib.pyplot as plt
    plt.close(fig)


def test_two_line_title_has_real_line_spacing_not_the_matplotlib_default():
    parsed = read_ork(ORK_PATH)
    fig = rocket_drawing.draw_side_profile(parsed, static_margin_mach0_cal=2.1, stability_mach03_cal=1.9)
    ax = fig.axes[0]
    title = ax.title
    assert "\n" in title.get_text()
    assert title.get_linespacing() > 1.2  # matplotlib's own default - must be increased, not left at it

    import matplotlib.pyplot as plt
    plt.close(fig)


if __name__ == "__main__":
    test_many_close_together_point_masses_get_numbered_markers_not_overlapping_names()
    test_two_line_title_has_real_line_spacing_not_the_matplotlib_default()
    print("\nROCKET DRAWING LABEL OVERLAP: OK")
