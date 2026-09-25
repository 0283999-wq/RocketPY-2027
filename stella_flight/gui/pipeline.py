"""The actual work behind the UI, with NO NiceGUI import - so it can be
unit-tested headlessly (tests/test_phase3_headless.py) without a browser,
and so app.py stays a thin wiring layer per CLAUDE.md Sec 1 ("an
importable package stella_flight/ (core, no UI) with stella_flight/gui/
(NiceGUI) as a separate layer").
"""
import os
from dataclasses import dataclass, field

from stella_flight import translate
from stella_flight.motor_reader import read_eng
from stella_flight.ork_reader import extract_drag_curves_from_stored_sim, read_ork


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
    max_acceleration_ms2: float
    rail_exit_velocity_ms: float
    flight_time_s: float
    min_static_margin_cal: float
    max_static_margin_cal: float
    is_stable: bool
    plot_paths: dict  # {"altitude": path, "velocity": path, ...}
    csv_path: str
    provisional_warning: str  # always non-empty until Phase 2's V1/V2 both pass - CLAUDE.md Rule 3


def load_files(ork_path, eng_path, power_off_drag_path=None, power_on_drag_path=None, outputs_dir=None):
    """Parses the .ork + .eng, and resolves a drag curve per CLAUDE.md Sec
    4.2's preference order: (1) explicit CSV paths if the caller supplied
    them, (2) the .ork's own stored simulation data, (3) placeholder with a
    loud warning. RocketSerializer cross-check (Sec 4.2 point 3) is not
    implemented - out of scope for tonight, needs Java/the OpenRocket jar."""
    parsed_ork = read_ork(ork_path)
    parsed_eng = read_eng(eng_path)

    if power_off_drag_path and power_on_drag_path:
        source = f"user-supplied CSV files ({os.path.basename(power_off_drag_path)}, {os.path.basename(power_on_drag_path)})"
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

    margins = [flight.stability_margin(t) for t in flight.time]

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
            path = os.path.join(outputs_dir, f"{plot_name}.png")
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
        max_acceleration_ms2=flight.max_acceleration,
        rail_exit_velocity_ms=flight.out_of_rail_velocity,
        flight_time_s=flight.t_final,
        min_static_margin_cal=min(margins),
        max_static_margin_cal=max(margins),
        is_stable=min(margins) > 0,
        plot_paths=plot_paths,
        csv_path=csv_path,
        provisional_warning="PROVISIONAL: V1/V2 flight-data validation has not both passed within +-5% yet (see PROGRESS.md). Do not treat this result as final.",
    )
