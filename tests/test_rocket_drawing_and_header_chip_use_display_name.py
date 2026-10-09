"""2026-10-09 review item 4: "report/history/exports/header chip must
always use current file's name, never cached." Two real gaps found
while re-checking this item (NOT covered by item 12's own original
fix, which touched report.py/run_history.py/home_page.py/rocket_page.py
display labels but missed these two):

  1. layout.py's status-bar chip (shown on every page) read
     parsed.name directly - the literal OpenRocket placeholder "Rocket"
     when nobody typed a name, instead of load_result.display_name's
     filename fallback.
  2. The rocket side-profile drawing (home_page.py, rocket_page.py,
     app.py's Simulate results all call rocket_drawing.draw_side_profile)
     never passed `title=`, so draw_side_profile's own `title or
     parsed.name` fallback ALWAYS took the parsed.name branch in
     practice - every rocket drawing silently showed "Rocket" for any
     .ork with no typed name.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.gui import pipeline, rocket_drawing

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs", "test_display_name_drawing")


def test_draw_side_profile_uses_the_passed_title_not_parsed_name():
    load_result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    parsed = load_result.parsed_ork
    assert parsed.name != "A Completely Different Custom Name"

    fig = rocket_drawing.draw_side_profile(parsed, title="A Completely Different Custom Name")
    title_text = fig.axes[0].get_title()
    assert "A Completely Different Custom Name" in title_text
    assert parsed.name not in title_text


def test_three_gui_callers_pass_title_to_draw_side_profile():
    """Static guard: the actual bug was that every caller OMITTED
    title=, so the function-level test above alone would not have
    caught it - re-grep every known call site so a future caller that
    adds a FOURTH place (and forgets this) fails loudly, not silently."""
    callers = [
        ("bup_rocketpy/gui/pages/home_page.py", 1),
        ("bup_rocketpy/gui/pages/rocket_page.py", 1),
        ("bup_rocketpy/gui/app.py", 1),
    ]
    for rel_path, expected_count in callers:
        path = os.path.join(REPO_ROOT, rel_path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        calls = re.findall(r"draw_side_profile\(.*?\n(?:.*\n)*?\s*\)", content)
        assert len(calls) >= expected_count, f"{rel_path}: expected at least {expected_count} draw_side_profile(...) call(s)"
        for call in calls:
            assert "title=" in call, f"{rel_path}: a draw_side_profile(...) call is missing title= - it will silently show the .ork's raw (possibly placeholder) name again"


def test_status_bar_chip_uses_display_name_not_raw_parsed_name():
    path = os.path.join(REPO_ROOT, "bup_rocketpy/gui/layout.py")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "display_name" in content, "layout.py's status bar must resolve display_name, not read parsed.name directly"
