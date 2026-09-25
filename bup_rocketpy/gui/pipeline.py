"""The actual work behind the UI, with NO NiceGUI import - so it can be
unit-tested headlessly (tests/test_phase3_headless.py) without a browser,
and so app.py stays a thin wiring layer per CLAUDE.md Sec 1 ("an
importable package bup_rocketpy/ (core, no UI) with bup_rocketpy/gui/
(NiceGUI) as a separate layer").
"""
import glob
import os
import uuid
from dataclasses import dataclass, field

from bup_rocketpy import translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import extract_drag_curves_from_stored_sim, read_ork


def fresh_image_path(outputs_dir, basename):
    """Every dynamically-regenerated plot/drawing needs a NEW filename on
    each render. NiceGUI's ui.image(local_path) serves local files through
    app.add_static_file(), whose URL is `/_nicegui/auto/static/<hash of
    the FILE PATH>/<filename>` with `Cache-Control: public, max-age=3600`
    - the hash depends on the PATH, not the file's contents, so writing a
    new PNG to the same fixed filename (e.g. "rocket_page_profile.png")
    produces the exact same URL, and a browser that already fetched it
    once will keep showing the stale cached bytes for up to an hour. This
    is the real cause of the 2026-09-26 "Rocket page mixes rockets" bug:
    not a data bug (the KPI cards read fresh data and were always
    correct), but a browser image cache showing an old render under the
    same URL. Old files sharing this basename are removed first so
    outputs/gui_run/ doesn't grow unbounded over a long session.
    """
    os.makedirs(outputs_dir, exist_ok=True)
    for stale in glob.glob(os.path.join(outputs_dir, f"{basename}_*.png")):
        try:
            os.remove(stale)
        except OSError:
            pass
    return os.path.join(outputs_dir, f"{basename}_{uuid.uuid4().hex[:8]}.png")


@dataclass
class LoadResult:
    parsed_ork: object
    parsed_eng: object
    eng_path: str
    drag_curve_source: str  # human-readable, always set - CLAUDE.md Sec 4.2: "the UI must always say where the Cd curve came from"
    power_off_drag_path: str  # None means placeholder-only (see drag_curve_source)
    power_on_drag_path: str
    import_table: list  # list of (component, status, detail) tuples, ready for a UI table


@dataclass
class SimResult:
    apogee_agl_m: float
    max_speed_ms: float
    max_mach: float
    max_acceleration_ms2: float  # 2026-09-26 review 2(a): BOOST-PHASE peak only (flight.max_acceleration_power_on) - matches what OpenRocket reports. See parachute_opening_accel_ms2 for the separate descent-phase figure.
    rail_exit_velocity_ms: float
    flight_time_s: float
    min_static_margin_cal: float  # 2026-09-26 review 2(b): computed rail-exit-to-apogee only, not the whole flight (which includes the physically-different post-deployment/descent phase)
    max_static_margin_cal: float
    is_stable: bool  # 2026-09-26 review 2(b): pass/fail against FLT 4.3.5's 1.5-4 cal window, not just margin > 0
    plot_paths: dict  # {"altitude": path, "velocity": path, ...}
    csv_path: str
    provisional_warning: str  # always non-empty until Phase 2's V1/V2 both pass - CLAUDE.md Rule 3
    dry_mass_kg: float = None  # the mass ACTUALLY used to build the flown rocket (override or geometric estimate) - crash (d)/(e) fix: every other page must read this, not the raw UI override field, or they show 0/None whenever no manual override was typed
    dry_cg_m: float = None
    mass_source: str = ""  # human-readable: "override" or "geometric estimate (...)"
    parachute_opening_accel_ms2: float = None  # flight.max_acceleration_power_off - "instantaneous inflation model, upper bound" per 2026-09-26 review 2(a); rocketpy models canopy inflation as instant, which overstates the real jerk, hence "upper bound"
    deployment_events: list = field(default_factory=list)  # [(chute_name, time_s, speed_ms, warn_bool), ...]
    sanity_checks: list = field(default_factory=list)  # list of sanity_checks.SanityCheck, 2026-09-26 review 2(c)
    time_to_apogee_s: float = None  # 2026-09-25 review Section 5 KPI
    max_dynamic_pressure_pa: float = None
    max_dynamic_pressure_time_s: float = None
    ground_hit_velocity_ms: float = None  # |flight.impact_velocity| - 0 for the Ballistic case (no recovery, free-fall impact)
    landing_distance_m: float = None  # straight-line drift from the pad, sqrt(x_impact^2 + y_impact^2)
    recovery_rows: list = field(default_factory=list)  # list of recovery.ParachutePanelRow - the LASC-requested recovery panel


def load_files(ork_path, eng_path, power_off_drag_path=None, power_on_drag_path=None, outputs_dir=None):
    """Parses the .ork + .eng, and resolves a drag curve per CLAUDE.md Sec
    4.2's preference order: (1) explicit CSV paths if the caller supplied
    them, (2) the .ork's own stored simulation data, (3) placeholder with a
    loud warning. RocketSerializer cross-check (Sec 4.2 point 3) is not
    implemented - out of scope for tonight, needs Java/the OpenRocket jar."""
    parsed_ork = read_ork(ork_path)
    parsed_eng = read_eng(eng_path)

    curve_warnings = []
    if power_off_drag_path and power_on_drag_path:
        source = f"user-supplied CSV files ({os.path.basename(power_off_drag_path)}, {os.path.basename(power_on_drag_path)})"
        # crash (f), 2026-09-26 review: unlike the .ork's own stored-sim
        # curve (already bin-averaged into unique Mach bins below), a
        # user-uploaded CSV is handed to rocketpy as a raw file path and
        # was never checked for duplicate/unsorted Mach values. Writes a
        # DEDUPED COPY under outputs_dir rather than mutating the input
        # path in place - the input may be a caller-owned file (an
        # earlier version of this rewrote it in place, which silently
        # touched checked-in reference/ CSVs the first time a test
        # passed one straight through; see curve_utils.dedupe_sort_csv).
        if outputs_dir:
            from bup_rocketpy.curve_utils import dedupe_sort_csv
            os.makedirs(outputs_dir, exist_ok=True)
            for label, key in [("power_off_drag.csv", "power_off_drag_path"), ("power_on_drag.csv", "power_on_drag_path")]:
                src = power_off_drag_path if key == "power_off_drag_path" else power_on_drag_path
                dst = os.path.join(outputs_dir, f"deduped_{label}")
                n = dedupe_sort_csv(src, dst)
                if key == "power_off_drag_path":
                    power_off_drag_path = dst
                else:
                    power_on_drag_path = dst
                if n:
                    curve_warnings.append(f"{label}: {n} duplicate/out-of-order Mach value(s) fixed (see curve_utils.dedupe_sort_curve).")
    else:
        boost, coast = extract_drag_curves_from_stored_sim(ork_path)
        if boost and coast and outputs_dir:
            os.makedirs(outputs_dir, exist_ok=True)
            power_on_drag_path = os.path.join(outputs_dir, "power_on_drag_from_ork.csv")
            power_off_drag_path = os.path.join(outputs_dir, "power_off_drag_from_ork.csv")
            with open(power_on_drag_path, "w") as f:
                f.write("\n".join(f"{m},{c}" for m, c in boost))
            with open(power_off_drag_path, "w") as f:
                f.write("\n".join(f"{m},{c}" for m, c in coast))
            source = "the .ork's own stored simulation data (CLAUDE.md Sec 4.2 top preference)"
        else:
            power_off_drag_path = power_on_drag_path = None
            source = "NONE AVAILABLE - this .ork has no stored simulation with drag data and no CSV was supplied. A constant placeholder Cd will be used if you simulate anyway (low confidence, CLAUDE.md Sec 4.2 point 4)."

    import_table = [(row.component, row.status, row.detail) for row in parsed_ork.import_log]
    for w in parsed_eng.warnings:
        import_table.append((".eng thrust curve", "APPROXIMATED", w))
    for w in curve_warnings:
        import_table.append(("drag curve CSV", "APPROXIMATED", w))
    import_table.extend(translate.parachute_import_notes(parsed_ork))

    return LoadResult(
        parsed_ork=parsed_ork, parsed_eng=parsed_eng, eng_path=eng_path,
        drag_curve_source=source,
        power_off_drag_path=power_off_drag_path, power_on_drag_path=power_on_drag_path,
        import_table=import_table,
    )


def run_simulation(load_result, outputs_dir, dry_mass_override_kg=None, dry_cg_override_m=None):
    """Runs the flight and produces everything the UI needs to display,
    all pre-computed and written to disk - the UI layer just points
    ui.image/ui.table at these paths, no plotting logic lives there."""
    os.makedirs(outputs_dir, exist_ok=True)
    parsed = load_result.parsed_ork

    power_off = load_result.power_off_drag_path or translate.DRAG_CURVE_PLACEHOLDER_CD
    power_on = load_result.power_on_drag_path or translate.DRAG_CURVE_PLACEHOLDER_CD

    if dry_mass_override_kg is not None and dry_cg_override_m is not None:
        mass_est = translate.MassEstimate(dry_mass_override_kg, dry_cg_override_m, "user-entered override (LoadResult UI field)")
    else:
        mass_est = translate.estimate_dry_mass_and_cg(parsed)
        if mass_est.mass_kg <= 0 or mass_est.cg_m is None:
            raise ValueError(f"cannot simulate: {mass_est.source}. Enter a manual dry mass + CG override, or complete the .ork's overrides in OpenRocket.")

    motor = translate.build_motor(load_result.parsed_eng, load_result.eng_path)
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next((t.radius for t in parsed.body_tubes if t.radius), None) or (parsed.nose.aft_radius if parsed.nose else 0.05)
    rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off, power_on_drag=power_on)

    from rocketpy import Flight
    env = translate.build_environment(parsed.launch)
    flight = Flight(
        rocket=rocket, environment=env,
        rail_length=parsed.launch.rail_length_m,
        inclination=parsed.launch.inclination_deg,
        heading=parsed.launch.rail_direction_deg,
    )

    # 2026-09-26 review 2(b): margin computed RAIL-EXIT TO APOGEE only.
    # The full-flight window used to include the descent phase, where
    # "static margin" stops being a meaningful aerodynamic concept (the
    # rocket is under canopy, at high AoA, no longer flying nose-first) -
    # combined with 2(a)'s late-deployment bug, a chaotic post-deployment
    # instant could dominate min(margins) and produce a number like the
    # 0.08 cal Diego saw, nothing to do with the actual ascent stability.
    ascent_times = [t for t in flight.time if flight.out_of_rail_time <= t <= flight.apogee_time]
    margins = [flight.stability_margin(t) for t in ascent_times] or [flight.stability_margin(flight.apogee_time)]
    min_margin, max_margin = min(margins), max(margins)
    # FLT 4.3.5: static margin must stay within 1.5-4 cal throughout
    # ascent - "Stable?" is now a pass/fail against that window, not
    # just "margin > 0" (which let a razor-thin or absurdly high margin
    # both silently read "YES").
    is_stable = 1.5 <= min_margin and max_margin <= 4.0

    deployment_events = []
    for t, chute in getattr(flight, "parachute_events", []):
        vx, vy, vz = flight.vx(t), flight.vy(t), flight.vz(t)
        speed = (vx**2 + vy**2 + vz**2) ** 0.5
        deployment_events.append((getattr(chute, "name", "parachute"), t, speed, speed > 30.0))

    from bup_rocketpy.sanity_checks import SanityCheck, run_sanity_checks
    sanity = run_sanity_checks(flight, rocket, motor, mass_est.mass_kg)
    if not (1.5 <= min_margin <= 4.0):
        sanity.insert(0, SanityCheck("Static margin range", "WARN" if min_margin > 0 else "FAIL", f"min margin {min_margin:.2f} cal, max {max_margin:.2f} cal (rail-exit to apogee) - FLT 4.3.5 requires 1.5-4 cal throughout."))
    else:
        sanity.insert(0, SanityCheck("Static margin range", "OK", f"min margin {min_margin:.2f} cal, max {max_margin:.2f} cal (rail-exit to apogee) - within FLT 4.3.5's 1.5-4 cal window."))

    # 2026-09-25 review Section 5 KPIs + the LASC-requested recovery panel.
    # run_simulation always builds WITH recovery (the Ballistic no-chute
    # case is a separate RCSM-case path, rcsm_cases.py, not this button),
    # so flight always reaches a real ground impact here.
    from bup_rocketpy.recovery import recovery_panel
    descent_mass_kg = mass_est.mass_kg + motor.dry_mass  # what's actually hanging under the canopy: dry rocket + spent motor casing
    recovery_rows = recovery_panel(flight, env, descent_mass_kg)
    ground_hit_velocity = abs(flight.impact_velocity)
    landing_distance = (flight.x_impact**2 + flight.y_impact**2) ** 0.5

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_paths = {}
    for plot_name, plot_fn in [
        ("trajectory_3d", flight.plots.trajectory_3d),
        ("linear_kinematics", flight.plots.linear_kinematics_data),
        ("attitude", flight.plots.attitude_data),
    ]:
        try:
            plot_fn()
            path = fresh_image_path(outputs_dir, plot_name)
            plt.savefig(path)
            plt.close("all")
            plot_paths[plot_name] = path
        except Exception as exc:  # a plot failing shouldn't sink the whole simulation - log and continue, per "never invent, but don't crash on the optional part" spirit
            plot_paths[plot_name] = None
            print(f"WARNING: plot {plot_name!r} failed: {exc}")

    csv_path = os.path.join(outputs_dir, "flight_data.csv")
    try:
        from rocketpy.simulation import FlightDataExporter
        FlightDataExporter(flight).export_data(csv_path)
    except Exception as exc:
        csv_path = None
        print(f"WARNING: CSV export failed: {exc}")

    return SimResult(
        apogee_agl_m=flight.apogee - env.elevation,
        max_speed_ms=flight.max_speed,
        max_mach=flight.max_mach_number,
        max_acceleration_ms2=flight.max_acceleration_power_on,
        rail_exit_velocity_ms=flight.out_of_rail_velocity,
        flight_time_s=flight.t_final,
        min_static_margin_cal=min_margin,
        max_static_margin_cal=max_margin,
        is_stable=is_stable,
        plot_paths=plot_paths,
        csv_path=csv_path,
        provisional_warning="PROVISIONAL: V1/V2 flight-data validation has not both passed within +-5% yet (see PROGRESS.md). Do not treat this result as final.",
        dry_mass_kg=mass_est.mass_kg,
        dry_cg_m=mass_est.cg_m,
        mass_source=mass_est.source,
        parachute_opening_accel_ms2=flight.max_acceleration_power_off,
        deployment_events=deployment_events,
        sanity_checks=sanity,
        time_to_apogee_s=flight.apogee_time,
        max_dynamic_pressure_pa=flight.max_dynamic_pressure,
        max_dynamic_pressure_time_s=flight.max_dynamic_pressure_time,
        ground_hit_velocity_ms=ground_hit_velocity,
        landing_distance_m=landing_distance,
        recovery_rows=recovery_rows,
    )
