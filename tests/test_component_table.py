"""2026-09-30 review item 5: "a table with every component in the .ork
(name, type, position from nose, length, mass, and whether it's
imported/approximated/ignored). Flag anything ignored or with a
position outside its parent." Locks in translate.component_table()
against PROMETEO's own real, messy geometry (point masses, a parachute
with a mass override, and several IGNORED structural tags), and that it
reaches both the report and the drawing's stability labels.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import report, translate
from bup_rocketpy.gui import pipeline
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_component_table")


def test_component_table_covers_every_real_component_kind():
    parsed = read_ork(ORK_PATH)
    rows = translate.component_table(parsed)
    kinds = {r.kind for r in rows}
    assert "Nose cone" in kinds
    assert "Body tube" in kinds
    assert "Point mass" in kinds
    assert "Parachute" in kinds
    assert any(k.startswith("Fin set") for k in kinds)
    assert "(unhandled tag)" in kinds, "PROMETEO's own .ork has centering rings/inner tubes that are IGNORED for mass - must still show up, flagged"

    # rows must be in nose-to-tail order (ignored/no-position rows last)
    positioned = [r for r in rows if r.position_m is not None]
    assert positioned == sorted(positioned, key=lambda r: r.position_m)


def test_component_table_mass_matches_the_dry_mass_estimate_it_feeds():
    """The whole point of this table is that it can never silently
    disagree with the mass this app actually flies - sum the IMPORTED/
    APPROXIMATED rows' own masses and compare against
    estimate_dry_mass_and_cg()'s independently-computed total."""
    parsed = read_ork(ORK_PATH)
    rows = translate.component_table(parsed)
    summed = sum(r.mass_kg for r in rows if r.mass_kg is not None)
    estimate = translate.estimate_dry_mass_and_cg(parsed)
    assert abs(summed - estimate.mass_kg) < 1e-6, f"component table sums to {summed} kg but the dry mass estimate is {estimate.mass_kg} kg"


def test_ignored_components_are_flagged_and_have_no_mass():
    parsed = read_ork(ORK_PATH)
    rows = translate.component_table(parsed)
    for r in rows:
        if r.status == "IGNORED":
            assert r.mass_kg is None
            assert r.flag, f"an IGNORED row must always explain why: {r}"


def test_component_rows_reach_the_report_appendix():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
    data = report.build_report_data("44", "Test", lr, sim, {}, None, None, OUT_DIR, include_appendix=True)
    rows = data["appendix_input_data"]["component_rows"]
    assert len(rows) == len(translate.component_table(lr.parsed_ork))
    assert any(r.kind == "Nose cone" for r in rows)


if __name__ == "__main__":
    test_component_table_covers_every_real_component_kind()
    test_component_table_mass_matches_the_dry_mass_estimate_it_feeds()
    test_ignored_components_are_flagged_and_have_no_mass()
    test_component_rows_reach_the_report_appendix()
    print("\nCOMPONENT TABLE: OK")
