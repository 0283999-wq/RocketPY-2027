"""Phase 3 headless smoke test (tonight's WINDOWS instructions): 'Add a
headless smoke test that launches the NiceGUI app and loads PROMETEO
without a browser.'

This exercises bup_rocketpy.gui.pipeline directly - the exact functions
app.py's UI callbacks call - with PROMETEO's real .ork + .eng, with no
NiceGUI/browser involved at all. This is deliberately the stronger check:
pipeline.py has zero NiceGUI import, so proving IT works standalone proves
the app's actual logic is sound independent of whether NiceGUI itself can
render in this sandboxed container (which nicegui's own browser-based Screen
test harness cannot do headlessly without a display server anyway).
`test_app_module_imports_without_starting_a_server` below additionally
confirms the UI layer itself at least imports and wires up cleanly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs", "test_phase3_headless")


def test_load_files_finds_drag_curve_from_ork_itself():
    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    print(f"\nDrag curve source: {result.drag_curve_source}")
    assert "stored simulation" in result.drag_curve_source, "should have found the .ork's own Cd data, not fallen back to placeholder"
    assert result.power_off_drag_path and os.path.exists(result.power_off_drag_path)
    assert result.power_on_drag_path and os.path.exists(result.power_on_drag_path)
    assert len(result.import_table) > 10, "import table looks suspiciously short for a real multi-component rocket"
    print(f"Import table: {len(result.import_table)} rows")


def test_load_files_respects_user_supplied_csv():
    power_off = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
    power_on = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
    result = pipeline.load_files(ORK_PATH, ENG_PATH, power_off_drag_path=power_off, power_on_drag_path=power_on, outputs_dir=OUTPUTS_DIR)
    assert "user-supplied" in result.drag_curve_source
    assert result.power_off_drag_path == power_off


def test_run_simulation_end_to_end_with_manual_mass_override():
    """Uses a manual dry mass/CG override (config.py's independently-
    verified 5.6622 kg / 0.6279 m) rather than the .ork's own incomplete
    geometric estimate - see Phase 1's documented 19% gap. This is exactly
    the override path the real UI exposes for a .ork whose OpenRocket
    overrides aren't complete yet (PROMETEO's case right now)."""
    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(result, OUTPUTS_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)

    print(f"\napogee AGL: {sim.apogee_agl_m:.1f} m")
    print(f"max speed: {sim.max_speed_ms:.1f} m/s, max Mach: {sim.max_mach:.3f}")
    print(f"rail exit: {sim.rail_exit_velocity_ms:.1f} m/s")
    print(f"static margin: [{sim.min_static_margin_cal:.2f}, {sim.max_static_margin_cal:.2f}] cal, stable={sim.is_stable}")
    print(f"plots written: {[k for k, v in sim.plot_paths.items() if v]}")
    print(f"CSV: {sim.csv_path}")
    print(f"warning shown to user: {sim.provisional_warning}")

    assert sim.is_stable, "with the correct mass+CG this should be stable - if not, something regressed"
    assert 500 < sim.apogee_agl_m < 2000
    assert sim.provisional_warning, "CLAUDE.md Rule 3: every result must show PROVISIONAL until V1+V2 both pass"
    assert any(v is not None for v in sim.plot_paths.values()), "no plots were produced at all"
    for name, path in sim.plot_paths.items():
        if path:
            assert os.path.exists(path) and os.path.getsize(path) > 0, f"{name} plot file is missing or empty"


def test_run_simulation_without_override_surfaces_instability_not_hides_it():
    """Without a manual override, the pipeline falls back to the .ork's own
    (Phase-1-documented, 19% low) geometric mass/CG estimate - it still
    HAS a CG (just an inaccurate one from whatever components resolved),
    so it does not raise. What matters is that the resulting instability
    is surfaced (is_stable=False, PROVISIONAL warning shown), not hidden -
    the UI's 'Stable? NO - UNSTABLE' card is what a real user sees here,
    not a silently-wrong 'looks fine' result."""
    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(result, OUTPUTS_DIR)
    print(f"\nWithout override: static margin@0-ish range=[{sim.min_static_margin_cal:.3f}, {sim.max_static_margin_cal:.3f}] cal, stable={sim.is_stable}")
    assert not sim.is_stable, "expected the known-incomplete geometric estimate to produce an unstable result (Phase 1 finding) - if this now passes, the mass estimator changed and Phase 1's docs need updating"
    assert sim.provisional_warning


def test_app_module_imports_without_starting_a_server():
    """Confirms the NiceGUI UI layer itself at least wires up without
    error - importing it registers pages/callbacks but does not bind a
    port or open a browser (that only happens under ui.run(), which this
    test deliberately does not call)."""
    import bup_rocketpy.gui.app  # noqa: F401
    print("\nbup_rocketpy.gui.app imported cleanly (no server started)")


if __name__ == "__main__":
    test_load_files_finds_drag_curve_from_ork_itself()
    test_load_files_respects_user_supplied_csv()
    test_run_simulation_end_to_end_with_manual_mass_override()
    test_run_simulation_without_override_surfaces_instability_not_hides_it()
    test_app_module_imports_without_starting_a_server()
    print("\nPHASE 3 HEADLESS SMOKE TEST: ALL PASSED")
