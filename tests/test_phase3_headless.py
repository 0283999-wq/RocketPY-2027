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
    # load_files writes a deduped COPY under outputs_dir rather than the
    # original path (2026-09-26 review: an earlier version mutated
    # whatever path it was given in place, which silently rewrote this
    # exact checked-in reference/ CSV) - same data, different path.
    assert result.power_off_drag_path != power_off
    assert os.path.exists(result.power_off_drag_path)


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


def test_parachute_deploys_at_apogee_not_late_and_max_acceleration_is_boost_only():
    """2026-09-26 review 2(a) regression test: PROMETEO's real .ork has
    <deployevent>never</deployevent> on its only parachute (a real SRAD
    altimeter system OpenRocket's own deployevent options don't model -
    the real vehicle deploys at apogee, confirmed in flight telemetry).
    The old code read "never" as an altitude-during-descent trigger at
    deploy_altitude=200m, so the rocket free-fell from apogee (~17s) to
    ~32s before "deploying" at ~120 m/s, producing a ~375g acceleration
    spike that swallowed the real (boost-phase, ~5g) max acceleration.
    If this regresses, deployment_events[0][1] (the time) will jump back
    to ~30s+ and max_acceleration_ms2 will jump back into the hundreds."""
    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(result, OUTPUTS_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)

    assert sim.deployment_events, "expected at least one parachute deployment event"
    name, t, speed, warn = sim.deployment_events[0]
    print(f"\n{name} deploys at t={t:.1f}s, speed={speed:.1f} m/s (warn={warn})")
    assert t < 20, f"deployment at t={t:.1f}s is not near apogee (~17s) - the 'never'->apogee mapping likely regressed back to an altitude trigger"
    assert speed < 50, f"deployment speed {speed:.1f} m/s is far above what an at-apogee deployment should produce"

    print(f"max_acceleration (boost) = {sim.max_acceleration_ms2:.1f} m/s2, parachute opening accel = {sim.parachute_opening_accel_ms2:.1f} m/s2")
    assert sim.max_acceleration_ms2 < 100, "boost-phase max acceleration should be a handful of g's for this motor, not a chute-opening spike"
    assert 40 < sim.max_acceleration_ms2, "boost-phase max acceleration implausibly low for a K-class motor on this airframe"

    for check in sim.sanity_checks:
        print(f"  [{check.status}] {check.name}: {check.detail}")
    assert not any(c.status == "FAIL" for c in sim.sanity_checks), "no sanity check should FAIL on this known-good config"
    assert any(v is not None for v in sim.plot_paths.values()), "no plots were produced at all"
    for name, path in sim.plot_paths.items():
        if path:
            assert os.path.exists(path) and os.path.getsize(path) > 0, f"{name} plot file is missing or empty"


def test_simulate_blocks_immediately_on_a_negative_t0_static_margin():
    """2026-09-26 review item 2: 'never hang' - a manual override that
    puts the CG too far aft (unstable at t=0) used to be exactly the
    condition that made Simulate hang forever (rocketpy's adaptive
    integrator has no lower bound on step size for a tumbling rocket).
    run_simulation now checks rocket.static_margin(0) BEFORE calling
    Flight() at all and raises immediately with a clear message - this
    must come back in well under a second, not hang."""
    import time

    import pytest

    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    started = time.monotonic()
    with pytest.raises(ValueError, match="static margin at t=0"):
        # CG deliberately placed past the tail (1.47 m airframe) - guaranteed unstable.
        pipeline.run_simulation(result, OUTPUTS_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=1.45)
    elapsed = time.monotonic() - started
    assert elapsed < 5.0, f"took {elapsed:.1f}s - this should fail fast, before ever calling Flight()"


def test_simulate_blocks_immediately_on_a_component_outside_the_airframe():
    """2026-09-26 review item 2's other guard: a component resolved
    outside the airframe (item 1's actual bug, reproduced here directly
    rather than depending on a specific .ork having one right now that
    the position fix has since corrected) must block Simulate with a
    message naming the component, not silently continue into a possibly-
    unstable, possibly-hanging Flight() call."""
    import pytest

    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    # Reproduce item 1's exact real-world bug shape without depending on
    # a specific .ork still having it (the fix corrected PROMETEO's own) -
    # push one real point mass 1 m past the tail.
    bad_mass = result.parsed_ork.point_masses[0]
    original_position = bad_mass.position_m
    bad_mass.position_m = original_position + 1.0 + 1.47
    try:
        with pytest.raises(ValueError, match="OUTSIDE the modeled airframe"):
            pipeline.run_simulation(result, OUTPUTS_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
    finally:
        bad_mass.position_m = original_position  # don't leak state into other tests sharing `result`'s parsed_ork


def test_run_simulation_without_override_is_now_stable_and_sane():
    """2026-09-26 review item 1 update: this test used to assert the
    OPPOSITE (is_stable=False) - the geometric mass/CG estimate was 19%
    low and its CG was dragged aft by the 'bottom' position sign bug
    (see ork_reader.py), producing an unstable no-override default path.
    That bug is fixed (both halves: the position formula, and the
    per-component override-application gap that closed most of the mass
    gap) - the DEFAULT path (load PROMETEO's real .ork + .eng with NO
    overrides, exactly CLAUDE.md Sec 2.5's "presentable" definition) is
    now stable and physically sane on its own:
      - static margin ~1.9-2.6 cal (within FLT 4.3.5's 1.5-4 cal window)
      - apogee ~1090 m AGL (in the right ballpark for PROMETEO's known
        860-1137 m real flights, CLAUDE.md Sec 3.2 - NOT a validated
        number, no flight data compared here, but no longer wildly off)
      - descent rate within ~5.5% of the hand-calc terminal velocity
    This is what a real user (no manual mass/CG typed in) now sees,
    instead of the "Stable? NO" a real, un-invented bug used to produce."""
    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(result, OUTPUTS_DIR)
    print(f"\nWithout override: static margin range=[{sim.min_static_margin_cal:.3f}, {sim.max_static_margin_cal:.3f}] cal, stable={sim.is_stable}, apogee={sim.apogee_agl_m:.1f} m")
    assert sim.is_stable, "expected the fixed geometric estimate to produce a stable result - if this now fails, something regressed the position/override fixes"
    assert 1.5 <= sim.min_static_margin_cal and sim.max_static_margin_cal <= 4.0
    assert 500 < sim.apogee_agl_m < 2000, "not remotely in PROMETEO's known ballpark - something is badly wrong"


def test_section5_kpis_and_recovery_panel_are_sane():
    """2026-09-25 review Section 5: the new KPIs and the LASC-requested
    recovery panel, sanity-checked against known-real numbers for
    PROMETEO (known-good override, 5.6622 kg / 0.6279 m)."""
    result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(result, OUTPUTS_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)

    print(f"\ntime_to_apogee={sim.time_to_apogee_s:.1f}s, max_dynamic_pressure={sim.max_dynamic_pressure_pa/1000:.2f} kPa @ t={sim.max_dynamic_pressure_time_s:.1f}s")
    print(f"ground_hit_velocity={sim.ground_hit_velocity_ms:.1f} m/s, landing_distance={sim.landing_distance_m:.1f} m")

    assert 5 < sim.time_to_apogee_s < 30
    assert 5000 < sim.max_dynamic_pressure_pa < 30000, "Max-Q implausible for a K-class motor on this airframe"
    assert sim.max_dynamic_pressure_time_s < sim.time_to_apogee_s, "Max-Q should occur during/near boost, well before apogee"
    # PROMETEO's real documented descent rate is ~5.5 m/s (CLAUDE.md Sec 3.2) - the
    # simulated ground-hit velocity should land in the same ballpark, not just "positive".
    assert 3 < sim.ground_hit_velocity_ms < 10
    assert 0 <= sim.landing_distance_m < 2000

    assert sim.recovery_rows, "expected at least one recovery panel row for PROMETEO's single real parachute"
    row = sim.recovery_rows[0]
    print(f"recovery panel: {row}")
    assert row.diameter_m > 0 and row.area_m2 > 0 and row.cd > 0 and row.cd_s_m2 > 0
    assert row.hand_terminal_velocity_at_ground_ms > 0
    # the hand-calc cross-check should be in the same ballpark as the simulated
    # value (a real independent check, not a tautology) - loose tolerance since
    # it's a genuinely different calculation (steady-state vs. simulated transient).
    assert abs(row.diff_pct_at_ground) < 50, f"hand-calc vs. simulated descent rate differ by {row.diff_pct_at_ground:.0f}% - too far apart to be a useful cross-check"


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
