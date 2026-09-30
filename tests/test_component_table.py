"""2026-09-30 review item 5: "a table with every component in the .ork
(name, type, position from nose, length, mass, and whether it's
imported/approximated/ignored). Flag anything ignored or with a
position outside its parent." Locks in translate.component_table()
against PROMETEO's own real, messy geometry (point masses, a parachute
with a mass override, and several structural tags), and that it reaches
both the report and the drawing's stability labels.

2026-09-30 review (2nd pass): a user screenshot showed real aluminum
centering rings/an inner tube marked "IGNORED... negligible mass" on
this exact table, despite OpenRocket itself computing a real, nonzero
mass for them (density x geometry) - not negligible at all for a metal
part. ork_reader.py's innertube/centeringring/launchlug/tubefin/
tubecoupler branches now compute that same density x hollow-cylinder-
volume mass (mirroring the bulkhead branch's own pre-existing pattern)
instead of unconditionally giving up, so PROMETEO's own 3 centering
rings and inner tube no longer fall into the generic "(unhandled tag)"
IGNORED bucket below - locked in by
test_centering_rings_and_inner_tube_get_a_real_computed_mass.
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

    # rows must be in nose-to-tail order (ignored/no-position rows last)
    positioned = [r for r in rows if r.position_m is not None]
    assert positioned == sorted(positioned, key=lambda r: r.position_m)


def test_centering_rings_and_inner_tube_get_a_real_computed_mass():
    """A user's real .ork showed this exact case: aluminum centering
    rings and an inner tube marked "IGNORED... negligible mass" even
    though they have a real <material density=...> and enough geometry
    (outer/inner radius, length) for OpenRocket's own UI to compute a
    real mass from - an aluminum ring is not negligible. PROMETEO's own
    .ork has this exact shape: 3 <centeringring>s with <outerradius>
    "auto" (sized to fit the parent body tube's inside - the common
    case) and one <innertube> with explicit numeric geometry."""
    parsed = read_ork(ORK_PATH)
    rows = translate.component_table(parsed)
    by_name = {r.name: r for r in rows}

    for ring_name in ("Anillo aletas 1", "Anillo aletas 2", "Anillo aletas 4"):
        row = by_name[ring_name]
        assert row.status != "IGNORED", f"{ring_name} should have a real computed mass, not be ignored as negligible"
        assert row.mass_kg is not None and row.mass_kg > 0.001, f"{ring_name}: expected a real aluminum-ring mass, got {row.mass_kg}"

    # No structural tag should fall into the generic IGNORED bucket for
    # this file any more - everything here has real material+geometry.
    assert "(unhandled tag)" not in {r.kind for r in rows}, "a component that should now compute a real mass fell back to IGNORED - check its geometry/material resolution"


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
