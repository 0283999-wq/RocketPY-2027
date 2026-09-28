"""2026-09-28 review item 2: draw_side_profile's motor rectangle was
real, working code (rocket_drawing.py's own `if motor_length_m and ...`
branch) that had simply never been WIRED UP - none of its 4 call sites
(app.py, home_page.py, rocket_page.py, report.py) ever passed
motor_length_m, so the drawing had silently never shown a motor,
anywhere in the app, ever - part of Diego's "the drawing has no motor"
report. This locks in that the parameter actually draws something when
given a real value, so a future refactor can't silently drop it again
without a test noticing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.gui import rocket_drawing
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")


def _motor_patch_count(fig):
    return sum(1 for p in fig.axes[0].patches if p.get_facecolor()[:3] == (0.3333333333333333, 0.3333333333333333, 0.3333333333333333))


def test_motor_length_m_actually_draws_a_motor_patch():
    parsed = read_ork(ORK_PATH)

    fig_without = rocket_drawing.draw_side_profile(parsed, dry_cg_m=0.6, static_margin_cal=2.0)
    fig_with = rocket_drawing.draw_side_profile(parsed, dry_cg_m=0.6, static_margin_cal=2.0, motor_length_m=0.4)

    assert _motor_patch_count(fig_without) == 0, "no motor_length_m given - there should be no motor patch"
    assert _motor_patch_count(fig_with) == 1, "motor_length_m given - the motor rectangle should be drawn"


def test_transition_still_renders_with_no_exception():
    """Sanity check for the alpha/linewidth bump (2026-09-28 review item
    2) - not a visual regression test (that needs a human/screenshot),
    just confirms the changed fill call didn't break anything. PROMETEO's
    own .ork has no transition/boat-tail, so this builds one synthetically
    via dataclasses.replace on a copy of the parsed rocket."""
    import dataclasses
    from bup_rocketpy.ork_reader import Transition

    parsed = read_ork(ORK_PATH)
    body_radius = next(t.radius for t in parsed.body_tubes if t.radius)
    with_transition = dataclasses.replace(parsed, transitions=[
        Transition(name="Boat-tail", length=0.05, fore_radius=body_radius, aft_radius=body_radius * 0.8, shape="conical", position_m=1.4, material_density=1780.0)
    ])
    fig = rocket_drawing.draw_side_profile(with_transition, dry_cg_m=0.6, static_margin_cal=2.0, motor_length_m=0.4)
    assert fig is not None
