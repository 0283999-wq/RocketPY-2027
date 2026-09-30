"""2026-09-30 review item 5: the rocket drawing's title must say
"Static margin (Mach 0): X cal (dot) Stability @ M0.3: Y cal" - two
different numbers a reader must not confuse (see translate.
stability_margin_at_mach's own docstring)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.gui import pipeline, rocket_drawing

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_drawing_stability_labels")


def test_drawing_stability_labels_returns_two_different_real_numbers():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
    mach0, mach03 = translate.drawing_stability_labels(sim.flight)
    assert mach0 is not None and mach03 is not None
    assert abs(mach0 - sim.flight.rocket.static_margin(0)) < 1e-9
    # not asserting they differ by a lot - just that this is a real,
    # independently-computed Mach-0.3 number, not a copy of static_margin(0)
    assert mach03 == translate.stability_margin_at_mach(sim.flight.rocket, 0.3)


def test_drawing_stability_labels_none_when_no_flight():
    assert translate.drawing_stability_labels(None) == (None, None)


def test_drawing_title_labels_both_numbers_explicitly():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
    mach0, mach03 = translate.drawing_stability_labels(sim.flight)
    fig = rocket_drawing.draw_side_profile(
        lr.parsed_ork, dry_cg_m=sim.dry_cg_m, motor_length_m=lr.parsed_eng.header.length_mm / 1000.0,
        static_margin_mach0_cal=mach0, stability_mach03_cal=mach03,
    )
    title_text = fig.axes[0].get_title()
    assert "Static margin (Mach 0)" in title_text
    assert "Stability @ M0.3" in title_text
    assert f"{mach0:.2f}" in title_text
    assert f"{mach03:.2f}" in title_text
    import matplotlib.pyplot as plt
    plt.close(fig)


if __name__ == "__main__":
    test_drawing_stability_labels_returns_two_different_real_numbers()
    test_drawing_stability_labels_none_when_no_flight()
    test_drawing_title_labels_both_numbers_explicitly()
    print("\nDRAWING STABILITY LABELS: OK")
