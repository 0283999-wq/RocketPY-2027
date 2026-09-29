"""PDF + DOCX simulation report (2026-09-27 review item 6: REPLACES the
old numbers-dump layout with a real technical report - written prose,
annotated figures, a working table of contents, Beyond UP branding - in
the structure/tone of the two references under docs/report_references/
(PROMETEO's own submitted report for structure/look; the Colibri Hybrid
report for narrative tone). The RCSM compliance table stays on the RCSM
page as the primary place to check it; it also appears in the optional
Appendix here, off by default. No internal jargon ("CLAUDE.md", "Rule 3",
"PROGRESS.md") anywhere in here - this file goes to LASC judges and
teammates, not other developers.

build_report_data() gathers everything from the app's already-computed
state (SimResult, CaseResult dict, MonteCarloResult, parsed .ork/.eng)
into one plain dict - both generate_pdf() and generate_docx() render
from that SAME dict, so the two formats can never silently disagree.
Every section's prose is generated from that dict's own numbers (never
hand-typed), except the five editable blocks in data["report_text"]
(introduction/objectives/discussion/conclusions/team), which a mission
can set on the Exports page and which persist with it (see
run_history.RunRecord.report_text).
"""
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone

WINE = "#8A1538"
GOLD = "#B79357"
INK = "#211A16"
LIGHT_GREY = "#F2EFEA"

# Regrouped (2026-09-27) from one flat plot list into the sections the
# report's new structure actually wants them in - Trajectory, Aerodynamics
# and Stability are now separate numbered sections, not one grab-bag.
TRAJECTORY_PLOT_ORDER = [
    ("altitude", "Altitude"),
    ("vertical_velocity", "Vertical velocity"),
    ("total_velocity", "Total velocity"),
    ("acceleration_boost", "Acceleration (boost phase)"),
    ("trajectory_3d", "3D trajectory"),
    ("ground_track", "Ground track (top view)"),
]
AERO_EXTRA_PLOT_ORDER = [
    ("mach", "Mach number vs. time"),
    ("dynamic_pressure", "Dynamic pressure vs. time"),
]
STABILITY_PLOT_ORDER = [
    ("static_margin", "Static margin vs. time"),
    ("cg_cp", "CG and CP vs. time"),
    ("angle_of_attack", "Angle of attack"),
]
# Kept for anything that still wants "every nominal plot" as one list.
NOMINAL_PLOT_ORDER = TRAJECTORY_PLOT_ORDER + AERO_EXTRA_PLOT_ORDER + STABILITY_PLOT_ORDER


def _fresh_path(outputs_dir, basename):
    os.makedirs(outputs_dir, exist_ok=True)
    return os.path.join(outputs_dir, f"{basename}_{uuid.uuid4().hex[:8]}.png")


def _plot_case_altitude_overlay(case_results, outputs_dir):
    """Every RCSM case's altitude curve overlaid on one plot - doubles as
    the report's Nominal-vs-Ballistic trajectory comparison (Section 4)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from bup_rocketpy.gui import plot_theme

    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {"Ballistic": plot_theme.AXIS, "Nominal": WINE, "DrogueOnly": GOLD, "MainAtApogee": "#4a7c59"}
    plotted = False
    for name, r in case_results.items():
        if r.flight is None:
            continue
        f = r.flight
        elevation = f.env.elevation
        ts = [t for t in f.time if t <= f.t_final]
        alts = [f.altitude(t) - elevation for t in ts]
        ax.plot(ts, alts, label=name, color=colors.get(name, INK))
        plotted = True
    if not plotted:
        plt.close(fig)
        return None
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Altitude AGL (m)")
    ax.legend()
    ax.set_title("Flight cases: altitude comparison")
    plot_theme.apply(ax, fig)
    path = _fresh_path(outputs_dir, "case_altitude_overlay")
    fig.tight_layout()
    plot_theme.savefig(fig, path)
    plt.close(fig)
    return path


def _plot_mc_histogram_and_ellipse(mc_result, outputs_dir):
    """Rebuilt from raw sample data - the report is self-contained, not
    dependent on a transient plot file the Monte Carlo PAGE happened to
    leave on disk."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from bup_rocketpy import monte_carlo
    from bup_rocketpy.gui import plot_theme

    hist_path = ellipse_path = None
    if mc_result.apogee_samples:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.hist(mc_result.apogee_samples, bins=min(20, max(5, mc_result.n_completed // 3)), color=WINE, alpha=0.75)
        ax.axvline(mc_result.apogee_mean, color=GOLD, linestyle="--", label="mean")
        ax.set_xlabel("Apogee AGL (m)")
        ax.set_ylabel("count")
        ax.legend()
        plot_theme.apply(ax, fig)
        hist_path = _fresh_path(outputs_dir, "report_mc_histogram")
        fig.tight_layout()
        plot_theme.savefig(fig, hist_path)
        plt.close(fig)

    ellipses = monte_carlo.landing_ellipses(mc_result)
    if ellipses:
        from matplotlib.patches import Ellipse
        fig2, ax2 = plt.subplots(figsize=(6, 6))
        for n_std, color in [(3, "#e0c9a6"), (2, "#c9a876"), (1, WINE)]:
            e = ellipses[n_std]
            ax2.add_patch(Ellipse((e["center_x"], e["center_y"]), e["width"], e["height"], angle=e["angle_deg"], facecolor=color, alpha=0.4, edgecolor=color, label=f"{n_std}-sigma"))
        ax2.scatter(mc_result.impact_x_samples, mc_result.impact_y_samples, s=8, color=plot_theme.AXIS, zorder=5)
        ax2.set_xlabel("X (m, downrange)")
        ax2.set_ylabel("Y (m, crossrange)")
        ax2.set_aspect("equal")
        ax2.legend()
        ax2.set_title("Landing dispersion")
        plot_theme.apply(ax2, fig2)
        ellipse_path = _fresh_path(outputs_dir, "report_mc_ellipse")
        fig2.tight_layout()
        # bbox_inches="tight": the equal-aspect axes above almost never
        # fill a square canvas (the landing footprint is usually much
        # wider than it is tall), which otherwise bakes big blank margins
        # into the saved PNG above and below the actual plot.
        plot_theme.savefig(fig2, ellipse_path, bbox_inches="tight")
        plt.close(fig2)
    return hist_path, ellipse_path


def _general_info_block(load_result, sim_result, app_commit_hash):
    """2026-09-28 review item 4: "General Information" block modeled on
    docs/report_references/plantilla solid.docx (SOLIDWORKS Flow
    Simulation's own report template) - Analysis Environment (software +
    versions, CPU, OS, computation time), Model Information (files
    used), Simulation Parameters (integrator tolerances/time step/
    termination). Every value read from the actual objects that ran the
    simulation, never hand-typed."""
    import platform
    import sys
    from importlib import metadata as importlib_metadata

    try:
        rocketpy_version = importlib_metadata.version("rocketpy")
    except importlib_metadata.PackageNotFoundError:
        rocketpy_version = "unknown"

    flight = sim_result.flight
    integrator = None
    if flight is not None:
        atol = flight.atol
        atol_summary = f"{atol[0]:.2g} (position/velocity/quaternion components; see RocketPy's own Flight docs for the full 13-element vector)" if isinstance(atol, (list, tuple)) and atol else str(atol)
        integrator = {
            "ode_solver": flight.ode_solver,
            "equations_of_motion": flight.equations_of_motion,
            "rtol": flight.rtol,
            "atol_summary": atol_summary,
            "max_time_step": "unlimited (adaptive)" if flight.max_time_step == float("inf") else f"{flight.max_time_step:.4g} s",
            "min_time_step": f"{flight.min_time_step:.4g} s",
            "termination": (
                "apogee only (recovery/descent not modeled)" if getattr(flight, "terminate_on_apogee", False)
                else "full flight, through ground impact or landing under recovery"
            ),
        }

    return {
        "software": f"RocketPy {rocketpy_version} (Python {sys.version.split()[0]})",
        "app_version": app_commit_hash,
        # Deliberately coarse (OS family + CPU architecture, not the exact
        # kernel/distro build or processor model string platform.platform()/
        # platform.processor() would give) - this report may be submitted
        # to competition judges, and a precise machine fingerprint is not
        # useful to them but does leak detail about whoever's computer
        # generated it.
        "cpu": platform.machine() or "unknown",
        "os": platform.system() or "unknown",
        "computation_time_s": sim_result.computation_time_s,
        "model_files": [
            ("OpenRocket design file", os.path.basename(load_result.ork_path) if getattr(load_result, "ork_path", None) else "not recorded"),
            ("Motor data file (.eng)", os.path.basename(load_result.eng_path) if load_result.eng_path else "not recorded"),
            ("Drag curve source", load_result.drag_curve_source),
        ],
        "integrator": integrator,
    }


def _global_minmax_rows(sim_result):
    """2026-09-28 review item 4: "Global min-max table" (SOLIDWORKS
    template's own "Global Min-Max-Table") - min/max of every key flight
    variable WITH the time it occurs, read straight off the actual solved
    Flight (sim_result.flight), not a separate/duplicate computation."""
    flight = sim_result.flight
    if flight is None:
        return []
    env = flight.env
    rocket = flight.rocket
    motor = rocket.motor
    t = list(flight.time)
    if not t:
        return []

    def col(label, unit, fn, decimals=2):
        vals = []
        for ti in t:
            try:
                vals.append((fn(ti), ti))
            except Exception:
                continue
        if not vals:
            return (label, unit, None, None, None, None, decimals)
        vmin, tmin = min(vals, key=lambda x: x[0])
        vmax, tmax = max(vals, key=lambda x: x[0])
        return (label, unit, vmin, tmin, vmax, tmax, decimals)

    burn_out = motor.burn_out_time
    return [
        col("Altitude AGL", "m", lambda ti: flight.z(ti) - env.elevation, 1),
        col("Vertical velocity", "m/s", flight.vz, 2),
        col("Total velocity", "m/s", flight.speed, 2),
        col("Total acceleration", "m/s2", flight.acceleration, 2),
        col("Mach number", "-", flight.mach_number, 3),
        col("Dynamic pressure", "kPa", lambda ti: flight.dynamic_pressure(ti) / 1000.0, 2),
        col("Total mass (rocket + motor)", "kg", rocket.total_mass, 3),
        col("Center of gravity", "m from nose", lambda ti: -rocket.center_of_mass(ti), 3),
        col("Center of pressure", "m from nose", lambda ti: -rocket.cp_position(flight.mach_number(ti)), 3),
        col("Static margin", "cal", flight.stability_margin, 2),
        col("Angle of attack", "deg", flight.angle_of_attack, 2),
        col("Thrust", "N", lambda ti: motor.thrust(ti) if ti <= burn_out else 0.0, 1),
    ]


def _appendix_input_data(parsed, load_result, eng_header):
    """2026-09-28 review item 4: Appendix A input data, modeled on the
    SOLIDWORKS template's own "Material Data" appendix - the motor
    table, a drag-curve excerpt (evenly sampled, not just the first N
    rows), parachute data (incl. reefing) and the atmosphere/wind/rail
    setup, so a reader can check every raw input without re-opening the
    original files."""
    motor_table = [
        ("Designation", eng_header.designation),
        ("Manufacturer", eng_header.manufacturer),
        ("Diameter", f"{eng_header.diameter_mm:.1f} mm"),
        ("Length", f"{eng_header.length_mm:.1f} mm"),
        ("Delays", eng_header.delays or "-"),
        ("Propellant mass", f"{eng_header.propellant_mass_kg:.4f} kg"),
        ("Total mass (loaded)", f"{eng_header.total_mass_kg:.4f} kg"),
    ]

    def _sample_curve(path, n=12):
        if not path or not os.path.exists(path):
            return None
        import csv
        rows = []
        with open(path) as f:
            for line in csv.reader(f):
                if len(line) >= 2:
                    try:
                        rows.append((float(line[0]), float(line[1])))
                    except ValueError:
                        continue
        if not rows:
            return None
        step = max(1, len(rows) // n)
        return rows[::step][:n]

    drag_excerpt = {
        "power_off": _sample_curve(getattr(load_result, "power_off_drag_path", None)),
        "power_on": _sample_curve(getattr(load_result, "power_on_drag_path", None)),
    }

    from bup_rocketpy import translate

    parachute_rows = []
    for c in parsed.parachutes:
        trigger, deploy_note = translate.parachute_trigger(c)
        row = {
            "name": c.name, "diameter_m": c.diameter, "cd": c.cd,
            "deploy_event": c.deploy_event, "deploy_altitude_m": c.deploy_altitude, "deploy_delay_s": c.deploy_delay,
            "is_reefed": c.is_reefed,
            "simulated_trigger": trigger, "deploy_note": deploy_note,
        }
        if c.is_reefed:
            row.update(
                reefed_diameter_m=c.reefed_diameter_m, reefed_cd=c.reefed_cd,
                cutter_altitude_m=c.cutter_altitude_m, cutter_delay_s=c.cutter_delay_s,
            )
        parachute_rows.append(row)

    launch = parsed.launch
    rail_atmosphere = {
        "site_lat": launch.latitude if launch else None, "site_lon": launch.longitude if launch else None,
        "site_altitude_m": launch.altitude_m if launch else None,
        "wind_speed_ms": launch.wind_average_ms if launch else None, "wind_direction_deg": launch.wind_direction_deg if launch else None,
        "rail_length_m": launch.rail_length_m if launch else None, "rail_inclination_deg": launch.inclination_deg if launch else None,
        "rail_direction_deg": launch.rail_direction_deg if launch else None,
    }

    return {"motor_table": motor_table, "drag_excerpt": drag_excerpt, "parachutes": parachute_rows, "rail_atmosphere": rail_atmosphere}


_DEFAULT_TEXT_BLOCKS = {
    "introduction": (
        "This report documents the computational flight simulation of {vehicle_name}, "
        "produced with Beyond UP's RocketPy-based simulation pipeline from the vehicle's "
        "OpenRocket design file and motor data file, with no hand-typed inputs beyond the "
        "overrides explicitly listed in Section 2 and the Assumptions section."
    ),
    "objectives": (
        "The objectives of this simulation are to predict the vehicle's ascent and descent "
        "trajectory, verify static stability throughout powered flight against the applicable "
        "safety requirements, characterize the expected landing footprint under wind "
        "uncertainty, and provide the flight cases and supporting data required for "
        "competition submission."
    ),
    "discussion": (
        "The predicted apogee of {apogee_m:.1f} m AGL is reached at t = {t_apogee:.1f} s, with a "
        "maximum velocity of {max_speed:.1f} m/s (Mach {max_mach:.2f}) during the boost phase. "
        "The static margin stays within {min_margin:.2f} to {max_margin:.2f} calibers across the "
        "ascent, which is {stability_word} against the required 1.5-4.0 cal band."
    ),
    "conclusions": (
        "Based on the results above, the vehicle is predicted to fly to {apogee_m:.1f} m AGL and "
        "recover within the dispersion footprint described in Section 8. {stability_sentence} "
        "The assumptions and data sources in this report should be reviewed before treating "
        "these numbers as final for a competition submission."
    ),
    "team": "BEYOND UP\nUniversidad Panamericana · México",
}


def _resolve_text_blocks(report_text, data_for_format):
    """Fills the 5 editable blocks: whatever the mission set (report_text)
    wins verbatim; otherwise a sensible default is generated from this
    report's own numbers, so a fresh report is never blank."""
    report_text = report_text or {}
    resolved = {}
    for key, template in _DEFAULT_TEXT_BLOCKS.items():
        user_value = (report_text.get(key) or "").strip()
        resolved[key] = user_value if user_value else template.format(**data_for_format)
    return resolved


def build_report_data(mission_id, author, load_result, sim_result, case_results, mc_result, mc_uncertainties, outputs_dir,
                       app_commit_hash="unknown", include_appendix=False,
                       report_text=None, competition_profile_key="lasc", compliance_rows=None):
    """Gathers everything the report needs into one plain dict. Real
    computation happens here (case-comparison plot, MC plots rebuilt
    from raw samples, hand-Barrowman cross-check, optional live
    validation) - both output formats render from the result, they don't
    recompute anything themselves."""
    from bup_rocketpy.gui import rocket_drawing  # pure matplotlib, no nicegui import - safe to use from a report builder
    from bup_rocketpy import barrowman, competition_profiles

    parsed = load_result.parsed_ork
    eng_header = load_result.parsed_eng.header
    launch = parsed.launch

    from bup_rocketpy.ork_reader import airframe_length_m

    body_radius = next((t.radius for t in parsed.body_tubes if t.radius), 0.05)
    total_length_m = airframe_length_m(parsed)

    try:
        profile = competition_profiles.get_profile(competition_profile_key)
        event_name = profile.display_name
    except Exception:
        event_name = "Test flight (no competition)"

    cp_m = None
    nominal_flight = case_results.get("Nominal").flight if case_results.get("Nominal") else None
    if nominal_flight is not None:
        try:
            cp_m = -nominal_flight.rocket.cp_position(0)  # tail_to_nose frame - see translate.py's coordinate note
        except Exception:
            cp_m = None

    fig = rocket_drawing.draw_side_profile(parsed, dry_cg_m=sim_result.dry_cg_m, cp_m=cp_m, motor_length_m=eng_header.length_mm / 1000.0, static_margin_cal=sim_result.min_static_margin_cal)
    side_profile_path = _fresh_path(outputs_dir, "report_side_profile")
    fig.savefig(side_profile_path)
    import matplotlib.pyplot as plt
    plt.close(fig)

    motor_dry_mass_kg = eng_header.total_mass_kg - eng_header.propellant_mass_kg
    avg_thrust_N = eng_header.propellant_mass_kg and (load_result.parsed_eng.total_impulse_Ns / load_result.parsed_eng.burn_time_s) or 0.0

    trajectory_plots = [(key, title, sim_result.plot_paths.get(key)) for key, title in TRAJECTORY_PLOT_ORDER if sim_result.plot_paths.get(key)]
    aero_extra_plots = [(key, title, sim_result.plot_paths.get(key)) for key, title in AERO_EXTRA_PLOT_ORDER if sim_result.plot_paths.get(key)]
    stability_plots = [(key, title, sim_result.plot_paths.get(key)) for key, title in STABILITY_PLOT_ORDER if sim_result.plot_paths.get(key)]

    barrowman_result = None
    try:
        barrowman_result = barrowman.hand_calc_cp(parsed)
    except Exception:
        barrowman_result = None
    barrowman_block = None
    if barrowman_result is not None and cp_m is not None:
        diff_pct = (barrowman_result["cp_m"] - cp_m) / cp_m * 100.0 if cp_m else None
        barrowman_block = dict(barrowman_result, rocketpy_cp_m=cp_m, diff_pct=diff_pct)
    elif barrowman_result is not None:
        barrowman_block = dict(barrowman_result, rocketpy_cp_m=None, diff_pct=None)

    case_rows = []
    for name, r in case_results.items():
        if r.flight is None:
            case_rows.append((name, None, None, None, r.warning or "not built"))
            continue
        f = r.flight
        apogee = f.apogee - f.env.elevation
        case_rows.append((name, apogee, f.max_speed, f.out_of_rail_velocity, r.warning))
    case_altitude_plot = _plot_case_altitude_overlay(case_results, outputs_dir)

    mc_block = None
    if mc_result is not None:
        hist_path, ellipse_path = _plot_mc_histogram_and_ellipse(mc_result, outputs_dir)
        n_total = mc_result.n_completed + mc_result.n_excluded
        mc_block = {
            "n_completed": mc_result.n_completed, "n_excluded": mc_result.n_excluded, "n_requested": n_total,
            "low_n_warning": n_total < 100,
            "apogee_mean": mc_result.apogee_mean, "apogee_p05": mc_result.apogee_p05, "apogee_p95": mc_result.apogee_p95,
            "histogram_path": hist_path, "ellipse_path": ellipse_path,
            "uncertainties": [(u.name, u.std_dev, u.source) for u in (mc_uncertainties or []) if u.enabled],
        }

    validation_block = None
    if include_appendix:
        from bup_rocketpy import validation
        validation_block = validation.compute_v1_and_v2()

    # 2026-09-28 review item 4: General Information + Global Min-Max +
    # OpenRocket comparison + Appendix input data - modeled on
    # docs/report_references/plantilla solid.docx (SOLIDWORKS Flow
    # Simulation's own report template) per this review's instruction.
    general_info_block = _general_info_block(load_result, sim_result, app_commit_hash)
    global_minmax_rows = _global_minmax_rows(sim_result)
    openrocket_comparison_block = None
    if getattr(load_result, "ork_path", None):
        try:
            from bup_rocketpy import openrocket_comparison
            sim_name, comparison_rows = openrocket_comparison.compare_to_openrocket(parsed, sim_result, load_result.ork_path)
            if comparison_rows is not None:
                openrocket_comparison_block = {"sim_name": sim_name, "rows": comparison_rows}
        except Exception:
            openrocket_comparison_block = None
    appendix_input_data = _appendix_input_data(parsed, load_result, eng_header)

    assumptions = [
        f"Dry mass: {sim_result.dry_mass_kg:.4f} kg ({sim_result.mass_source})",
        f"Dry CG: {sim_result.dry_cg_m:.4f} m from nose ({sim_result.mass_source})",
        f"Drag curve: {load_result.drag_curve_source}",
        "Atmosphere: standard atmosphere model with the .ork's own recorded average wind speed/direction (not a live weather download, not a full altitude profile).",
    ]
    if sim_result.mach_extrapolated:
        assumptions.append(f"WARNING: this flight reaches Mach {sim_result.max_mach:.2f}, past the drag curve's own {sim_result.drag_curve_max_mach:.2f} Mach coverage - results above that speed are constant-Cd extrapolation, not measured drag.")

    delivered_files = [
        ("Simulation report", f"report.pdf / report.docx (this document)"),
        (".ork design file", os.path.basename(load_result.ork_path) if getattr(load_result, "ork_path", None) else "not recorded"),
        (".eng motor file", os.path.basename(load_result.eng_path) if load_result.eng_path else "not recorded"),
        ("Drag curve source", load_result.drag_curve_source),
        ("Flight data CSV", os.path.basename(sim_result.csv_path) if sim_result.csv_path else "not generated"),
        ("OpenRocket-format flight data CSV", os.path.basename(sim_result.openrocket_csv_path) if getattr(sim_result, "openrocket_csv_path", None) else "not generated"),
    ]
    if mc_result is not None:
        delivered_files.append(("Monte Carlo dispersion data", f"{mc_result.n_completed} completed trajectories"))
    delivered_files.append(("Per-case runnable .py scripts", "see the LASC/competition .zip package (CRS 10.1.3/10.1.5/10.1.6)"))

    apogee_agl_m = sim_result.apogee_agl_m
    max_speed = sim_result.max_speed_ms
    max_mach = sim_result.max_mach
    min_margin = sim_result.min_static_margin_cal
    max_margin = sim_result.max_static_margin_cal
    stability_word = "compliant" if sim_result.is_stable else "NOT compliant"
    stability_sentence = (
        "The vehicle satisfies the RCSM's static margin requirement (FLT 4.3.5/4.3.6) throughout the ascent."
        if sim_result.is_stable else
        "The vehicle does NOT satisfy the RCSM's static margin requirement (FLT 4.3.5/4.3.6) throughout the ascent and should be reconfigured before flight."
    )
    text_format_data = {
        "vehicle_name": parsed.name, "apogee_m": apogee_agl_m, "t_apogee": sim_result.time_to_apogee_s,
        "max_speed": max_speed, "max_mach": max_mach, "min_margin": min_margin, "max_margin": max_margin,
        "stability_word": stability_word, "stability_sentence": stability_sentence,
    }
    resolved_text = _resolve_text_blocks(report_text, text_format_data)

    return {
        "mission_id": mission_id, "vehicle_name": parsed.name, "author": author or "-",
        "event_name": event_name,
        "app_commit_hash": app_commit_hash, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "report_text": resolved_text,
        "kpis": [
            ("Apogee AGL", f"{sim_result.apogee_agl_m:.1f} m"),
            ("Max speed", f"{sim_result.max_speed_ms:.1f} m/s"),
            ("Max Mach", f"{sim_result.max_mach:.3f}"),
            ("Max boost acceleration", f"{sim_result.max_acceleration_ms2:.1f} m/s2"),
            ("Rail exit velocity", f"{sim_result.rail_exit_velocity_ms:.1f} m/s"),
            ("Max-Q", f"{sim_result.max_dynamic_pressure_pa/1000.0:.2f} kPa @ t={sim_result.max_dynamic_pressure_time_s:.1f}s" if sim_result.max_dynamic_pressure_pa else "-"),
            ("Time to apogee", f"{sim_result.time_to_apogee_s:.1f} s"),
            ("Flight time", f"{sim_result.flight_time_s:.1f} s"),
            ("Ground-hit velocity", f"{sim_result.ground_hit_velocity_ms:.1f} m/s" if sim_result.ground_hit_velocity_ms else "-"),
            ("Landing distance", f"{sim_result.landing_distance_m:.1f} m" if sim_result.landing_distance_m else "-"),
        ],
        # The 4 headline cards on page 1 (PROMETEO report look) - a short,
        # fixed subset of the KPI table above, not a duplicate list to keep in sync.
        "kpi_cards": [
            ("Apogee AGL", f"{sim_result.apogee_agl_m:.1f} m"),
            ("Max Mach", f"{sim_result.max_mach:.3f}"),
            ("Min static margin", f"{sim_result.min_static_margin_cal:.2f} cal"),
            ("Flight time", f"{sim_result.flight_time_s:.1f} s"),
        ],
        "vehicle": {
            "side_profile_path": side_profile_path,
            "mass_plot_path": sim_result.plot_paths.get("mass"),
            "length_cm": total_length_m * 100.0, "diameter_cm": body_radius * 2 * 100.0,
            "reference_area_m2": math.pi * body_radius ** 2,
            "dry_mass_kg": sim_result.dry_mass_kg, "dry_cg_m": sim_result.dry_cg_m,
            "mass_source": sim_result.mass_source,
            "min_margin_cal": sim_result.min_static_margin_cal, "max_margin_cal": sim_result.max_static_margin_cal,
            "is_stable": sim_result.is_stable,
            "parachutes": [(c.name, c.diameter, math.pi * (c.diameter / 2.0) ** 2, c.cd) for c in parsed.parachutes],
        },
        "propulsion": {
            "thrust_plot_path": sim_result.plot_paths.get("thrust"),
            "designation": eng_header.designation, "manufacturer": eng_header.manufacturer,
            "total_impulse_Ns": load_result.parsed_eng.total_impulse_Ns, "peak_thrust_N": load_result.parsed_eng.peak_thrust_N,
            "avg_thrust_N": avg_thrust_N, "burn_time_s": load_result.parsed_eng.burn_time_s,
            "propellant_mass_kg": eng_header.propellant_mass_kg, "total_mass_kg": eng_header.total_mass_kg, "dry_mass_kg": motor_dry_mass_kg,
        },
        "aero": {
            "cd_plot_path": sim_result.plot_paths.get("cd_mach"),
            "drag_curve_source": load_result.drag_curve_source,
            "max_mach": sim_result.max_mach, "drag_curve_max_mach": sim_result.drag_curve_max_mach, "mach_extrapolated": sim_result.mach_extrapolated,
            "extra_plots": aero_extra_plots,
        },
        "environment": {
            "site_lat": launch.latitude if launch else None, "site_lon": launch.longitude if launch else None, "site_altitude_m": launch.altitude_m if launch else None,
            "wind_speed_ms": launch.wind_average_ms if launch else None, "wind_direction_deg": launch.wind_direction_deg if launch else None,
            "rail_length_m": launch.rail_length_m if launch else None, "rail_inclination_deg": launch.inclination_deg if launch else None, "rail_direction_deg": launch.rail_direction_deg if launch else None,
        },
        "trajectory_plots": trajectory_plots,
        "stability_plots": stability_plots,
        "barrowman": barrowman_block,
        "openrocket_comparison": openrocket_comparison_block,
        "recovery": {
            "rows": sim_result.recovery_rows,
            "descent_plot_path": sim_result.plot_paths.get("descent_velocity"),
        },
        "cases": {"rows": case_rows, "altitude_overlay_path": case_altitude_plot},
        "monte_carlo": mc_block,
        "assumptions": assumptions,
        "delivered_files": delivered_files,
        "compliance_rows": compliance_rows or [],
        "validation": validation_block,
        "include_appendix": include_appendix,
        "general_info": general_info_block,
        "global_minmax": global_minmax_rows,
        "appendix_input_data": appendix_input_data,
    }


def _validation_paragraphs(validation_block):
    status_word = {"pass": "PASS", "fail": "FAIL", "inconclusive": "INCONCLUSIVE"}
    lines = []
    for r in validation_block:
        status = status_word.get(r.status, "FAIL")
        lines.append(f"{r.name}: predicted {r.predicted_agl_m:.1f} m vs. real flight {r.target_agl_m:.1f} m (error {r.error_pct:+.1f}%, {status} against +-5%). {r.notes}")
    return lines


# ---------------------------------------------------------------------------
# Data-driven prose - one function per section, generated from the SAME dict
# both renderers work from (never hand-typed per report). fig_* args are the
# actual figure numbers assigned at render time by that renderer's own
# counter, so PDF and DOCX always cite the figure that is actually next to
# the paragraph, even though each format numbers its own figures separately.
# ---------------------------------------------------------------------------

def _prose_deliverables(data):
    return (
        f"{data['report_text']['introduction']} "
        f"This mission is submitted for {data['event_name']}. "
        f"{data['report_text']['objectives']}"
    )


def _prose_vehicle(data, fig_profile):
    v = data["vehicle"]
    return (
        f"Figure {fig_profile} shows the vehicle's side profile with its center of gravity and "
        f"center of pressure marked. {data['vehicle_name']} is {v['length_cm']/100.0:.2f} m long "
        f"with a body diameter of {v['diameter_cm']:.1f} cm (reference area {v['reference_area_m2']:.5f} m2). "
        f"The dry mass is {v['dry_mass_kg']:.3f} kg with the center of gravity at {v['dry_cg_m']:.3f} m "
        f"from the nose tip ({v['mass_source']}). Across the ascent the static margin ranges from "
        f"{v['min_margin_cal']:.2f} to {v['max_margin_cal']:.2f} calibers, which is "
        f"{'within' if v['is_stable'] else 'OUTSIDE'} the RCSM's required 1.5-4.0 cal band (FLT 4.3.5/4.3.6)."
    )


def _prose_propulsion(data, fig_thrust):
    pr = data["propulsion"]
    return (
        f"The vehicle is powered by a {pr['designation']} motor ({pr['manufacturer']}), delivering a total "
        f"impulse of {pr['total_impulse_Ns']:.1f} N*s over a {pr['burn_time_s']:.2f} s burn "
        f"(average thrust {pr['avg_thrust_N']:.1f} N, peak {pr['peak_thrust_N']:.1f} N). "
        f"Figure {fig_thrust} shows the thrust curve used for this simulation. Propellant mass is "
        f"{pr['propellant_mass_kg']:.3f} kg out of a total loaded mass of {pr['total_mass_kg']:.3f} kg."
    )


def _prose_trajectory(data, fig_altitude):
    return (
        f"Figure {fig_altitude} shows the predicted altitude, velocity and acceleration through the ascent, "
        f"together with the 3D trajectory and ground track. The nominal case (dual-deployment recovery) is "
        f"compared against the ballistic case (no parachutes) later in Section 8, which bounds the vehicle's "
        f"worst-case impact energy and downrange distance."
    )


def _prose_aero(data, fig_cd):
    ae = data["aero"]
    if ae["mach_extrapolated"]:
        coverage = (
            f"the flight reaches Mach {ae['max_mach']:.2f}, past the drag curve's own {ae['drag_curve_max_mach']:.2f} "
            "Mach coverage - results above that speed use a constant-Cd extrapolation, not measured drag, and should "
            "be treated with reduced confidence"
        )
    elif ae["drag_curve_max_mach"]:
        coverage = f"the flight's peak Mach of {ae['max_mach']:.2f} stays within the drag curve's {ae['drag_curve_max_mach']:.2f} Mach coverage"
    else:
        coverage = "no measured drag curve Mach range is on file for this vehicle"
    return (
        f"The drag coefficient used in this simulation comes from {ae['drag_curve_source']}. "
        f"Figure {fig_cd} shows the power-off (coast) and power-on (boost) drag curves actually used; {coverage}."
    )


def _prose_stability(data, fig_margin, fig_barrowman=None):
    v = data["vehicle"]
    bw = data["barrowman"]
    text = (
        f"Figure {fig_margin} shows the static margin through the flight against the RCSM's required "
        f"1.5-4.0 cal band (FLT 4.3.5/4.3.6, shaded). The minimum margin is {v['min_margin_cal']:.2f} cal "
        f"and the maximum is {v['max_margin_cal']:.2f} cal, so the vehicle is "
        f"{'compliant' if v['is_stable'] else 'NOT compliant'} throughout the ascent."
    )
    if bw is not None:
        if bw.get("rocketpy_cp_m") is not None and bw.get("diff_pct") is not None:
            text += (
                f" As an independent check, a hand calculation using the classical Barrowman (1966) method "
                f"({bw['method']}) places the center of pressure at {bw['cp_m']:.3f} m from the nose tip, "
                f"compared to {bw['rocketpy_cp_m']:.3f} m from RocketPy's own (more complete) model - a "
                f"difference of {bw['diff_pct']:+.1f}%."
            )
        else:
            text += (
                f" As an independent check, a hand calculation using the classical Barrowman (1966) method "
                f"({bw['method']}) places the center of pressure at {bw['cp_m']:.3f} m from the nose tip."
            )
    return text


def _prose_recovery(data, fig_descent):
    rec = data["recovery"]
    if not rec["rows"]:
        return "No parachutes are configured on this vehicle, so no recovery analysis applies."
    names = ", ".join(r.name for r in rec["rows"])
    return (
        f"The recovery system uses {len(rec['rows'])} parachute(s): {names}. "
        f"Figure {fig_descent} shows the descent rate after apogee; the simulated descent rates are compared "
        f"against a hand-calculated terminal velocity for each stage in the table above, as a cross-check on "
        f"the parachute Cd*S values used."
    )


def _prose_monte_carlo(data):
    mc = data["monte_carlo"]
    if mc is None:
        return "Monte Carlo dispersion analysis was not run for this report."
    n_note = (
        f"With only {mc['n_completed']} completed trajectories, this is a rough check, not a statistically "
        "meaningful dispersion estimate (fewer than 100 samples)."
        if mc["low_n_warning"] else
        f"With {mc['n_completed']} completed trajectories, this dispersion estimate is statistically meaningful."
    )
    return (
        f"Monte Carlo dispersion analysis varies the uncertain inputs listed below across {mc['n_completed'] + mc['n_excluded']} "
        f"simulated flights. The apogee is predicted at {mc['apogee_mean']:.1f} m with a 90% interval of "
        f"[{mc['apogee_p05']:.1f}, {mc['apogee_p95']:.1f}] m. The landing footprint (1/2/3-sigma ellipses) bounds "
        f"where the vehicle is expected to land under wind uncertainty. {n_note}"
    )


def _prose_flight_test_correlation(data):
    if data["validation"]:
        return (
            "The simulation model's track record against real PROMETEO flights is included in the Appendix "
            "(model validation), since this vehicle's own flight-test data was not correlated separately for "
            "this report."
        )
    return (
        "No flight-test data has been correlated against this specific vehicle's predictions in this report. "
        "For the simulation model's general track record against real flights, enable the validation appendix "
        "when generating this report."
    )




def generate_pdf(output_path, data):
    """2026-09-28 review item 4: HTML + CSS, printed by a real browser
    engine (Playwright Chromium) - see bup_rocketpy/report_html.py.
    Replaces the old reportlab implementation entirely (this project's
    own instruction: "stop fighting reportlab")."""
    from bup_rocketpy import report_html
    return report_html.render_pdf(output_path, data)


def generate_docx(output_path, data):
    """See bup_rocketpy/report_docx.py - a real Word document (Heading
    styles, a genuine TOC field, bordered tables, header/footer, yellow
    [EDIT: ...] marks at the few spots meant for a human to customize)."""
    from bup_rocketpy import report_docx
    return report_docx.generate_docx(output_path, data)
