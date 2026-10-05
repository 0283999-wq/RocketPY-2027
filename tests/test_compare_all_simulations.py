"""2026-10-05 review (2nd pass): "add the option to simulate ALL
locations and parameters, and make the whole app compatible" - following
up on per-simulation selection (test_simulation_selection.py) with a
batch comparison across every stored simulation in the .ork, reusing
PROMETEO's own 2 real sims (495 m / 490 m sites).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_compare_all_simulations")


def test_compares_every_stored_simulation_with_real_numbers():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    assert [r.name for r in rows] == ["Ballistic Brasil", "brasil 2026"]
    for row in rows:
        assert row.success, row.error
        assert 800 < row.apogee_agl_m < 1600, f"{row.name}: apogee {row.apogee_agl_m} not in a plausible range"
        assert row.max_speed_ms > 0
        assert row.is_stable == True  # noqa: E712 - rocketpy returns np.bool_, "is True" would fail on that

    # The two sites' own conditions ARE actually different - this is
    # comparing real, distinct launch sites, not the same one twice.
    assert rows[0].altitude_m != rows[1].altitude_m
    assert rows[0].altitude_m == 495.0 and rows[1].altitude_m == 490.0


def test_progress_callback_fires_once_per_site_in_order():
    os.makedirs(OUT_DIR, exist_ok=True)
    calls = []
    pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR, progress_callback=lambda i, n, name: calls.append((i, n, name)))
    assert calls == [(1, 2, "Ballistic Brasil"), (2, 2, "brasil 2026")]


def test_a_failing_site_does_not_take_down_the_whole_comparison():
    """One bad site (e.g. a manual mass override that happens to be
    physically invalid) must not hide the other sites' real results."""
    os.makedirs(OUT_DIR, exist_ok=True)
    # A negative dry mass override is guaranteed to fail run_simulation's
    # own "cannot simulate" check for every site, the same way a single
    # Simulate run would - exercising the per-site try/except, not an
    # invented rocket.
    rows = pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR, dry_mass_override_kg=-1.0, dry_cg_override_m=0.5)
    assert len(rows) == 2
    for row in rows:
        assert row.success is False
        assert row.error  # a real message, not just a blank failure


def test_manual_overrides_carry_through_to_every_site():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
    assert all(r.success for r in rows)
    # Same dry mass for both sites (unlike the default/no-override path,
    # where OpenRocket's own per-simulation mass estimate could differ
    # slightly site to site) - confirms the override reached BOTH runs,
    # not just the first.
    assert abs(rows[0].apogee_agl_m - rows[1].apogee_agl_m) < 5.0


def test_export_comparison_csv_writes_every_row_including_a_failed_one():
    """"now that i simulated the 12 parameters how do i export them?"
    (2026-10 review) - the compare-all table had no download. One real
    site plus one forced-failure site (same technique as the failing-
    site test above), so the CSV must carry both outcomes."""
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR)
    failing_rows = pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUT_DIR, dry_mass_override_kg=-1.0, dry_cg_override_m=0.5)
    mixed = [rows[0], failing_rows[1]]

    csv_path = os.path.join(OUT_DIR, "compare_all_simulations.csv")
    pipeline.export_comparison_csv(mixed, csv_path)
    assert os.path.exists(csv_path)

    with open(csv_path, encoding="utf-8-sig") as f:
        text = f.read()
    lines = text.strip().split("\n")
    assert len(lines) == 3, f"expected 1 header + 2 rows, got {len(lines)}: {lines}"
    assert lines[0].split(",")[0] == "name"
    assert "Ballistic Brasil" in lines[1]
    assert str(rows[0].apogee_agl_m) in lines[1]
    assert "brasil 2026" in lines[2]
    assert "False" in lines[2]  # the forced-failure row's success column


if __name__ == "__main__":
    test_compares_every_stored_simulation_with_real_numbers()
    test_progress_callback_fires_once_per_site_in_order()
    test_a_failing_site_does_not_take_down_the_whole_comparison()
    test_manual_overrides_carry_through_to_every_site()
    test_export_comparison_csv_writes_every_row_including_a_failed_one()
    print("\nCOMPARE ALL SIMULATIONS: OK")
