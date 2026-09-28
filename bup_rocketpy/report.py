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
        plot_theme.savefig(fig2, ellipse_path)
        plt.close(fig2)
    return hist_path, ellipse_path


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

    fig = rocket_drawing.draw_side_profile(parsed, dry_cg_m=sim_result.dry_cg_m, cp_m=cp_m, static_margin_cal=sim_result.min_static_margin_cal)
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


def generate_docx(output_path, data):
    from docx import Document
    from docx.shared import Inches, Pt

    doc = Document()

    # -- Page 1: header (title left / team block right), abstract, KPI cards
    title_p = doc.add_paragraph()
    run = title_p.add_run(f"Mission {data['mission_id']} — {data['vehicle_name']}")
    run.bold = True
    run.font.size = Pt(20)
    doc.add_paragraph("Computational Simulation Report").runs[0].font.size = Pt(13)
    team_p = doc.add_paragraph(data["report_text"]["team"].replace("\n", " · "))
    team_p.runs[0].bold = True
    doc.add_paragraph(f"{data['event_name']}  |  Generated {data['generated_at']}  |  App version {data['app_commit_hash']}  |  Author: {data['author']}")
    doc.add_paragraph(
        f"This report summarizes the predicted flight of {data['vehicle_name']}: an apogee of "
        f"{next(v for k, v in data['kpis'] if k == 'Apogee AGL')} at a peak speed of "
        f"{next(v for k, v in data['kpis'] if k == 'Max speed')} (Mach {next(v for k, v in data['kpis'] if k == 'Max Mach')}), "
        f"with a minimum static margin of {data['vehicle']['min_margin_cal']:.2f} cal through the ascent."
    )
    kt = doc.add_table(rows=2, cols=4)
    for i, (label, value) in enumerate(data["kpi_cards"]):
        kt.rows[0].cells[i].text = label
        kt.rows[1].cells[i].text = value
        kt.rows[1].cells[i].paragraphs[0].runs[0].bold = True if kt.rows[1].cells[i].paragraphs[0].runs else None
    doc.add_page_break()

    doc.add_heading("Table of contents", level=1)
    doc.add_paragraph("(Word: right-click and choose \"Update field\" to populate, or use References > Table of Contents.)")
    doc.add_page_break()

    fig_no = [0]

    def figure(path, caption, width=6):
        if not path:
            return
        fig_no[0] += 1
        doc.add_picture(path, width=Inches(width))
        p = doc.add_paragraph()
        r = p.add_run(f"Figure {fig_no[0]}. {caption}")
        r.bold = True

    doc.add_heading("1. Deliverables and setup", level=1)
    doc.add_paragraph(_prose_deliverables(data))

    doc.add_heading("2. Vehicle configuration and mass properties", level=1)
    v = data["vehicle"]
    figure(v["side_profile_path"], "Vehicle side profile with CG/CP and static margin.", width=6)
    doc.add_paragraph(_prose_vehicle(data, fig_no[0]))
    for label, value in [
        ("Length", f"{v['length_cm']:.1f} cm"), ("Diameter", f"{v['diameter_cm']:.1f} cm"),
        ("Reference area", f"{v['reference_area_m2']:.5f} m2"),
        ("Dry mass", f"{v['dry_mass_kg']:.3f} kg"), ("Dry CG", f"{v['dry_cg_m']:.3f} m from nose"),
        ("Static margin range (ascent)", f"{v['min_margin_cal']:.2f} - {v['max_margin_cal']:.2f} cal"),
        ("Stable (FLT 4.3.5/4.3.6, 1.5-4 cal)", "YES" if v["is_stable"] else "NO"),
    ]:
        doc.add_paragraph(f"{label}: {value}")
    if v["parachutes"]:
        pt = doc.add_table(rows=1, cols=4)
        pt.rows[0].cells[0].text, pt.rows[0].cells[1].text, pt.rows[0].cells[2].text, pt.rows[0].cells[3].text = "Parachute", "Diameter (m)", "Area (m2)", "Cd"
        for name, diam, area, cd in v["parachutes"]:
            row = pt.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = name, f"{diam:.2f}", f"{area:.3f}", f"{cd:.2f}" if cd is not None else "auto"
    if v["mass_plot_path"]:
        figure(v["mass_plot_path"], "Total mass (rocket + motor) vs. time.")

    doc.add_heading("3. Propulsion", level=1)
    pr = data["propulsion"]
    figure(pr["thrust_plot_path"], "Thrust curve used for this simulation.")
    doc.add_paragraph(_prose_propulsion(data, fig_no[0]))
    for label, value in [
        ("Motor", f"{pr['designation']} ({pr['manufacturer']})"),
        ("Total impulse", f"{pr['total_impulse_Ns']:.1f} N*s"),
        ("Average / peak thrust", f"{pr['avg_thrust_N']:.1f} N / {pr['peak_thrust_N']:.1f} N"),
        ("Burn time", f"{pr['burn_time_s']:.2f} s"),
        ("Propellant / dry / total mass", f"{pr['propellant_mass_kg']:.3f} / {pr['dry_mass_kg']:.3f} / {pr['total_mass_kg']:.3f} kg"),
    ]:
        doc.add_paragraph(f"{label}: {value}")

    doc.add_heading("4. Trajectory (nominal and ballistic)", level=1)
    first = True
    for key, title, path in data["trajectory_plots"]:
        if first:
            figure(path, "Ascent and descent trajectory - see remaining plots below for individual quantities.")
            doc.add_paragraph(_prose_trajectory(data, fig_no[0]))
            first = False
        else:
            doc.add_heading(title, level=2)
            doc.add_picture(path, width=Inches(6))

    doc.add_heading("5. Aerodynamics", level=1)
    ae = data["aero"]
    figure(ae["cd_plot_path"], "Drag coefficient vs. Mach (curve actually used).")
    doc.add_paragraph(_prose_aero(data, fig_no[0]))
    for key, title, path in ae["extra_plots"]:
        doc.add_heading(title, level=2)
        doc.add_picture(path, width=Inches(6))

    doc.add_heading("6. Stability", level=1)
    margin_path = next((p for k, t, p in data["stability_plots"] if k == "static_margin"), None)
    figure(margin_path, "Static margin vs. time, with the RCSM's 1.5-4.0 cal allowed band shaded.")
    doc.add_paragraph(_prose_stability(data, fig_no[0]))
    for key, title, path in data["stability_plots"]:
        if key == "static_margin":
            continue
        doc.add_heading(title, level=2)
        doc.add_picture(path, width=Inches(6))
    if data["barrowman"]:
        bw = data["barrowman"]
        doc.add_heading("6.1 Independent hand stability check (Barrowman method)", level=2)
        doc.add_paragraph(bw["method"])
        doc.add_paragraph(f"Nose CN-alpha: {bw['nose_cn_alpha']:.2f}, CP at {bw['nose_cp_m']:.3f} m from nose.")
        doc.add_paragraph(f"Fins CN-alpha (total): {bw['fins_cn_alpha']:.2f}, CP at {bw['fins_cp_m']:.3f} m from nose.")
        doc.add_paragraph(f"Combined hand-calculated CP: {bw['cp_m']:.3f} m from nose (total CN-alpha {bw['cn_alpha_total']:.2f}).")
        if bw.get("rocketpy_cp_m") is not None:
            doc.add_paragraph(f"RocketPy's own CP at t=0: {bw['rocketpy_cp_m']:.3f} m from nose (difference {bw['diff_pct']:+.1f}%).")

    doc.add_heading("7. Recovery and landing footprint", level=1)
    rec = data["recovery"]
    if rec["rows"]:
        rt = doc.add_table(rows=1, cols=7)
        for i, h in enumerate(["Chute", "Diameter (m)", "Area (m2)", "Cd*S (m2)", "Deploy time (s)", "Sim descent (m/s)", "Hand-calc descent (m/s)"]):
            rt.rows[0].cells[i].text = h
        for r in rec["rows"]:
            row = rt.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = r.name, f"{r.diameter_m:.2f}", f"{r.area_m2:.3f}", f"{r.cd_s_m2:.3f}"
            row[4].text, row[5].text, row[6].text = f"{r.deploy_time_s:.1f}", f"{r.descent_rate_sim_ms:.1f}", f"{r.hand_terminal_velocity_at_ground_ms:.1f}"
    figure(rec["descent_plot_path"], "Descent velocity after apogee.")
    doc.add_paragraph(_prose_recovery(data, fig_no[0]))

    doc.add_heading("8. Flight cases (RCSM)", level=1)
    ct = doc.add_table(rows=1, cols=5)
    for i, h in enumerate(["Case", "Apogee AGL (m)", "Max speed (m/s)", "Rail exit (m/s)", "Note"]):
        ct.rows[0].cells[i].text = h
    for name, apogee, max_speed, rail_exit, note in data["cases"]["rows"]:
        row = ct.add_row().cells
        row[0].text = name
        row[1].text = f"{apogee:.1f}" if apogee is not None else "-"
        row[2].text = f"{max_speed:.1f}" if max_speed is not None else "-"
        row[3].text = f"{rail_exit:.1f}" if rail_exit is not None else "-"
        row[4].text = note or ""
    figure(data["cases"]["altitude_overlay_path"], "Altitude comparison across the required flight cases.")

    doc.add_heading("9. Monte Carlo dispersion", level=1)
    mc = data["monte_carlo"]
    doc.add_paragraph(_prose_monte_carlo(data))
    if mc is not None:
        figure(mc["histogram_path"], "Apogee distribution across Monte Carlo trajectories.")
        figure(mc["ellipse_path"], "Landing dispersion footprint (1/2/3-sigma).")
        if mc["uncertainties"]:
            ut = doc.add_table(rows=1, cols=3)
            ut.rows[0].cells[0].text, ut.rows[0].cells[1].text, ut.rows[0].cells[2].text = "Uncertainty", "Std dev", "Source"
            for name, std_dev, source in mc["uncertainties"]:
                row = ut.add_row().cells
                row[0].text, row[1].text, row[2].text = name, f"{std_dev:.4g}", source

    doc.add_heading("10. Flight-test correlation", level=1)
    doc.add_paragraph(_prose_flight_test_correlation(data))

    doc.add_heading("11. Discussion and conclusions", level=1)
    doc.add_heading("11.1 Discussion", level=2)
    doc.add_paragraph(data["report_text"]["discussion"])
    doc.add_heading("11.2 Conclusions", level=2)
    doc.add_paragraph(data["report_text"]["conclusions"])

    doc.add_heading("12. Files delivered", level=1)
    ft = doc.add_table(rows=1, cols=2)
    ft.rows[0].cells[0].text, ft.rows[0].cells[1].text = "Item", "Detail"
    for label, value in data["delivered_files"]:
        row = ft.add_row().cells
        row[0].text, row[1].text = label, value

    doc.add_heading("Assumptions and data sources", level=1)
    for a in data["assumptions"]:
        doc.add_paragraph(a, style="List Bullet")

    if data["validation"] or data["compliance_rows"]:
        doc.add_heading("Appendix", level=1)
        if data["compliance_rows"]:
            doc.add_heading("A.1 RCSM compliance table (Nominal case)", level=2)
            at = doc.add_table(rows=1, cols=4)
            for i, h in enumerate(["Rule", "Check", "Status", "Detail"]):
                at.rows[0].cells[i].text = h
            for row_data in data["compliance_rows"]:
                row = at.add_row().cells
                for i, v in enumerate(row_data[:4]):
                    row[i].text = str(v)
        if data["validation"]:
            doc.add_heading("A.2 Model validation vs. real PROMETEO flights", level=2)
            doc.add_paragraph("This is the SIMULATION MODEL's own track record against 2 real flights of a different vehicle (PROMETEO) - not specific to the vehicle in this report. Included as evidence of how much to trust this app's predictions in general.")
            for line in _validation_paragraphs(data["validation"]):
                doc.add_paragraph(line, style="List Bullet")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    return output_path


class _ReportDocTemplate:
    """Wraps BaseDocTemplate with a real afterFlowable hook so the Table
    of Contents actually gets populated (reportlab's standard two-pass
    TOC recipe - see reportlab's own documentation on TableOfContents).
    The previous version built a TableOfContents flowable but never
    called notify('TOCEntry', ...), so it always rendered as an empty
    table - this was Diego's "placeholder for table of contents" bug."""

    def __new__(cls, *args, **kwargs):
        from reportlab.platypus import BaseDocTemplate

        class _Impl(BaseDocTemplate):
            def afterFlowable(self, flowable):
                from reportlab.platypus import Paragraph
                if not isinstance(flowable, Paragraph):
                    return
                style_name = getattr(flowable.style, "name", "")
                text = flowable.getPlainText()
                level = {"H1Numbered": 0, "H2Numbered": 1}.get(style_name)
                if level is None:
                    return
                self.notify("TOCEntry", (level, text, self.page))
                key = f"bookmark-{id(flowable)}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)

        return _Impl(*args, **kwargs)


class _NumberedCanvas:
    """Footer: "Beyond UP - Mission X - Computational Simulation Report -
    <event>" left, "Page N of M" right - reportlab's standard two-pass
    recipe (BaseDocTemplate.multiBuild already does pass 1/2 for the TOC;
    this canvas subclass piggybacks on the same page count)."""
    def __init__(self, canvas_cls, footer_left=""):
        self._canvas_cls = canvas_cls
        self._footer_left = footer_left

    def __call__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas as canvas_module
        footer_left = self._footer_left

        class NumberedCanvas(canvas_module.Canvas):
            def __init__(self, *a, **kw):
                canvas_module.Canvas.__init__(self, *a, **kw)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.setFont("Helvetica", 8)
                    self.setFillColor(canvas_module.Color(0.13, 0.10, 0.09))
                    if footer_left:
                        self.drawString(0.75 * 72, 20, footer_left)
                    self.drawRightString(200 * 2.83, 20, f"Page {self._pageNumber} of {num_pages}")
                    canvas_module.Canvas.showPage(self)
                canvas_module.Canvas.save(self)

        return NumberedCanvas(*args, **kwargs)


def generate_pdf(output_path, data):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Frame, HRFlowable, Image, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.platypus.tableofcontents import TableOfContents

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1Numbered", parent=styles["Heading1"], textColor=colors.HexColor(WINE)))
    styles.add(ParagraphStyle(name="H2Numbered", parent=styles["Heading2"], textColor=colors.HexColor(INK)))
    styles.add(ParagraphStyle(name="FigureCaption", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor(INK), spaceBefore=2, spaceAfter=10))
    styles.add(ParagraphStyle(name="RightSmall", parent=styles["BodyText"], alignment=TA_RIGHT, fontSize=9))
    styles.add(ParagraphStyle(name="TitleLeft", fontName="Helvetica-Bold", fontSize=20, textColor=colors.HexColor(WINE)))
    styles.add(ParagraphStyle(name="SubtitleLeft", fontName="Helvetica", fontSize=12, textColor=colors.HexColor(INK), spaceAfter=4))

    frame = Frame(0.75 * inch, 0.75 * inch, letter[0] - 1.5 * inch, letter[1] - 1.5 * inch, id="normal")
    footer_left = f"Beyond UP · Mission {data['mission_id']} · Computational Simulation Report · {data['event_name']}"
    doc = _ReportDocTemplate(output_path, pagesize=letter, pageTemplates=[PageTemplate(id="all", frames=[frame])])

    story = []

    # --- Page 1: header (title left / team block right), rules, abstract, KPI cards
    team_lines = data["report_text"]["team"].split("\n")
    header_left = [
        Paragraph(f"Mission {data['mission_id']}", styles["TitleLeft"]),
        Paragraph(data["vehicle_name"], styles["SubtitleLeft"]),
        Paragraph("Computational Simulation Report", styles["SubtitleLeft"]),
    ]
    header_right = [Paragraph(line, styles["RightSmall"]) for line in team_lines]
    header_right.append(Paragraph(data["event_name"], styles["RightSmall"]))
    header_table = Table([[header_left, header_right]], colWidths=[3.75 * inch, 2.75 * inch])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD), spaceAfter=10))

    story.append(Paragraph(
        f"This report summarizes the predicted flight of {data['vehicle_name']}: an apogee of "
        f"{next(v for k, v in data['kpis'] if k == 'Apogee AGL')} at a peak speed of "
        f"{next(v for k, v in data['kpis'] if k == 'Max speed')} (Mach {next(v for k, v in data['kpis'] if k == 'Max Mach')}), "
        f"with a minimum static margin of {data['vehicle']['min_margin_cal']:.2f} cal through the ascent. "
        f"Generated {data['generated_at']}, app version {data['app_commit_hash']}, author: {data['author']}.",
        styles["BodyText"],
    ))
    story.append(Spacer(1, 8))

    card_row = []
    for label, value in data["kpi_cards"]:
        cell = Table([[Paragraph(f"<font color='white'>{label}</font>", ParagraphStyle(name="CardLabel", fontSize=8, alignment=1))],
                      [Paragraph(f"<b>{value}</b>", ParagraphStyle(name="CardValue", fontSize=14, alignment=1, textColor=colors.HexColor(INK)))]],
                     colWidths=[1.3 * inch])
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(WINE)),
            ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(LIGHT_GREY)),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(GOLD)),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        card_row.append(cell)
    story.append(Table([card_row], colWidths=[1.35 * inch] * 4))
    story.append(PageBreak())

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(name="TOC1", fontSize=11, leftIndent=10, spaceBefore=4),
        ParagraphStyle(name="TOC2", fontSize=9, leftIndent=20),
    ]
    story.append(Paragraph("Table of contents", styles["Heading1"]))
    story.append(toc)
    story.append(PageBreak())

    fig_no = [0]

    def h1(number, title):
        story.append(Paragraph(f"{number}. {title.upper()}", styles["H1Numbered"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(WINE), spaceAfter=8))

    def h2(text):
        story.append(Paragraph(text, styles["H2Numbered"]))

    def para(text):
        story.append(Paragraph(text, styles["BodyText"]))
        story.append(Spacer(1, 4))

    def figure(path, caption, width=5.5, height_ratio=0.55):
        if not path:
            return None
        fig_no[0] += 1
        story.append(Image(path, width=width * inch, height=width * inch * height_ratio))
        story.append(Paragraph(f"<b>Figure {fig_no[0]}.</b> {caption}", styles["FigureCaption"]))
        return fig_no[0]

    def side_by_side(left_flowables, right_flowables, left_w=3.35, right_w=3.35):
        story.append(Table([[left_flowables, right_flowables]], colWidths=[left_w * inch, right_w * inch],
                            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))

    # 1. Deliverables and setup
    h1(1, "Deliverables and setup")
    para(_prose_deliverables(data))
    kpi_rows = [["Metric", "Value"]] + [[k, v] for k, v in data["kpis"]]
    t = Table(kpi_rows, colWidths=[2.5 * inch, 3 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story.append(t)
    story.append(PageBreak())

    # 2. Vehicle
    h1(2, "Vehicle configuration and mass properties")
    v = data["vehicle"]
    fn = figure(v["side_profile_path"], "Vehicle side profile with CG/CP and static margin.", width=5.5, height_ratio=0.4)
    para(_prose_vehicle(data, fn))
    left_rows = [["Parameter", "Value"]] + [
        [label, value] for label, value in [
            ("Length", f"{v['length_cm']:.1f} cm"), ("Diameter", f"{v['diameter_cm']:.1f} cm"),
            ("Reference area", f"{v['reference_area_m2']:.5f} m2"),
            ("Dry mass", f"{v['dry_mass_kg']:.3f} kg"), ("Dry CG", f"{v['dry_cg_m']:.3f} m from nose"),
            ("Static margin range", f"{v['min_margin_cal']:.2f} - {v['max_margin_cal']:.2f} cal"),
            ("Stable (1.5-4 cal)", "YES" if v["is_stable"] else "NO"),
        ]
    ]
    left_table = Table(left_rows, colWidths=[1.7 * inch, 1.65 * inch])
    left_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    if v["parachutes"]:
        right_rows = [["Parachute", "Diam (m)", "Cd"]] + [[n, f"{d:.2f}", f"{c:.2f}" if c is not None else "auto"] for n, d, a, c in v["parachutes"]]
        right_table = Table(right_rows, colWidths=[1.5 * inch, 0.9 * inch, 0.9 * inch])
        right_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        side_by_side([left_table], [right_table])
    else:
        story.append(left_table)
    if v["mass_plot_path"]:
        figure(v["mass_plot_path"], "Total mass (rocket + motor) vs. time.")
    story.append(PageBreak())

    # 3. Propulsion
    h1(3, "Propulsion")
    pr = data["propulsion"]
    fn = figure(pr["thrust_plot_path"], "Thrust curve used for this simulation.")
    para(_prose_propulsion(data, fn))
    rows = [["Parameter", "Value"]] + [
        [label, value] for label, value in [
            ("Motor", f"{pr['designation']} ({pr['manufacturer']})"),
            ("Total impulse", f"{pr['total_impulse_Ns']:.1f} N*s"),
            ("Average / peak thrust", f"{pr['avg_thrust_N']:.1f} N / {pr['peak_thrust_N']:.1f} N"),
            ("Burn time", f"{pr['burn_time_s']:.2f} s"),
            ("Propellant / dry / total mass", f"{pr['propellant_mass_kg']:.3f} / {pr['dry_mass_kg']:.3f} / {pr['total_mass_kg']:.3f} kg"),
        ]
    ]
    t = Table(rows, colWidths=[2.5 * inch, 3 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story.append(t)
    story.append(PageBreak())

    # 4. Trajectory
    h1(4, "Trajectory (nominal and ballistic)")
    first = True
    for key, title, path in data["trajectory_plots"]:
        if first:
            fn = figure(path, "Ascent trajectory - see the flight-case comparison in Section 8 for ballistic vs. nominal.")
            para(_prose_trajectory(data, fn))
            first = False
        else:
            h2(title)
            story.append(Image(path, width=5.5 * inch, height=5.5 * inch * 0.55))
            story.append(Spacer(1, 6))
    story.append(PageBreak())

    # 5. Aerodynamics
    h1(5, "Aerodynamics")
    ae = data["aero"]
    fn = figure(ae["cd_plot_path"], "Drag coefficient vs. Mach (curve actually used).", width=5.5, height_ratio=0.6)
    para(_prose_aero(data, fn))
    for key, title, path in ae["extra_plots"]:
        h2(title)
        story.append(Image(path, width=5.5 * inch, height=5.5 * inch * 0.55))
        story.append(Spacer(1, 6))
    story.append(PageBreak())

    # 6. Stability
    h1(6, "Stability")
    margin_path = next((p for k, t, p in data["stability_plots"] if k == "static_margin"), None)
    fn = figure(margin_path, "Static margin vs. time, with the RCSM's 1.5-4.0 cal allowed band shaded (FLT 4.3.5/4.3.6).")
    para(_prose_stability(data, fn))
    for key, title, path in data["stability_plots"]:
        if key == "static_margin":
            continue
        h2(title)
        story.append(Image(path, width=5.5 * inch, height=5.5 * inch * 0.55))
        story.append(Spacer(1, 6))
    if data["barrowman"]:
        bw = data["barrowman"]
        h2("6.1 Independent hand stability check (Barrowman method)")
        para(bw["method"])
        rows = [["Component", "CN-alpha", "CP (m from nose)"],
                ["Nose", f"{bw['nose_cn_alpha']:.2f}", f"{bw['nose_cp_m']:.3f}"],
                ["Fins (total)", f"{bw['fins_cn_alpha']:.2f}", f"{bw['fins_cp_m']:.3f}"],
                ["Combined (hand calc)", f"{bw['cn_alpha_total']:.2f}", f"{bw['cp_m']:.3f}"]]
        if bw.get("rocketpy_cp_m") is not None:
            rows.append(["RocketPy (t=0)", "-", f"{bw['rocketpy_cp_m']:.3f}"])
        t = Table(rows, colWidths=[2 * inch, 1.5 * inch, 1.7 * inch])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        story.append(t)
    story.append(PageBreak())

    # 7. Recovery
    h1(7, "Recovery and landing footprint")
    rec = data["recovery"]
    if rec["rows"]:
        rows = [["Chute", "Diam (m)", "Area (m2)", "Cd*S", "Deploy (s)", "Sim (m/s)", "Hand-calc (m/s)"]]
        for r in rec["rows"]:
            rows.append([r.name, f"{r.diameter_m:.2f}", f"{r.area_m2:.3f}", f"{r.cd_s_m2:.3f}", f"{r.deploy_time_s:.1f}", f"{r.descent_rate_sim_ms:.1f}", f"{r.hand_terminal_velocity_at_ground_ms:.1f}"])
        t = Table(rows, colWidths=[1.3 * inch] + [0.75 * inch] * 6)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        story.append(t)
    fn = figure(rec["descent_plot_path"], "Descent velocity after apogee.")
    para(_prose_recovery(data, fn))
    story.append(PageBreak())

    # 8. Flight cases
    h1(8, "Flight cases (RCSM)")
    rows = [["Case", "Apogee AGL (m)", "Max speed (m/s)", "Rail exit (m/s)", "Note"]]
    for name, apogee, max_speed, rail_exit, note in data["cases"]["rows"]:
        rows.append([name, f"{apogee:.1f}" if apogee is not None else "-", f"{max_speed:.1f}" if max_speed is not None else "-", f"{rail_exit:.1f}" if rail_exit is not None else "-", note or ""])
    t = Table(rows, colWidths=[1.1 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch, 1.7 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    story.append(t)
    figure(data["cases"]["altitude_overlay_path"], "Altitude comparison across the required flight cases.")
    story.append(PageBreak())

    # 9. Monte Carlo
    h1(9, "Monte Carlo dispersion")
    mc = data["monte_carlo"]
    para(_prose_monte_carlo(data))
    if mc is not None:
        if mc["low_n_warning"]:
            para(f"<font color='#B36B00'>N = {mc['n_requested']} - not statistically meaningful (fewer than 100 samples).</font>")
        hist_fig = figure(mc["histogram_path"], "Apogee distribution across Monte Carlo trajectories.", width=5, height_ratio=0.58)
        ellipse_fig = figure(mc["ellipse_path"], "Landing dispersion footprint (1/2/3-sigma).", width=4, height_ratio=1.0)
        if mc["uncertainties"]:
            rows = [["Uncertainty", "Std dev", "Source"]] + [[n, f"{s:.4g}", src] for n, s, src in mc["uncertainties"]]
            t = Table(rows, colWidths=[1.5 * inch, 0.8 * inch, 3.2 * inch])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
            story.append(t)
    story.append(PageBreak())

    # 10. Flight-test correlation
    h1(10, "Flight-test correlation")
    para(_prose_flight_test_correlation(data))
    story.append(PageBreak())

    # 11. Discussion and conclusions
    h1(11, "Discussion and conclusions")
    h2("11.1 Discussion")
    para(data["report_text"]["discussion"])
    h2("11.2 Conclusions")
    para(data["report_text"]["conclusions"])
    story.append(PageBreak())

    # 12. Files delivered
    h1(12, "Files delivered")
    rows = [["Item", "Detail"]] + [[label, value] for label, value in data["delivered_files"]]
    t = Table(rows, colWidths=[2.2 * inch, 3.3 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    story.append(t)

    h1(13, "Assumptions and data sources")
    for a in data["assumptions"]:
        para("- " + a)

    if data["validation"] or data["compliance_rows"]:
        story.append(PageBreak())
        story.append(Paragraph("APPENDIX", styles["H1Numbered"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(WINE), spaceAfter=8))
        if data["compliance_rows"]:
            h2("A.1 RCSM compliance table (Nominal case)")
            rows = [["Rule", "Check", "Status", "Detail"]] + [[str(c) for c in row[:4]] for row in data["compliance_rows"]]
            t = Table(rows, colWidths=[0.9 * inch, 1.6 * inch, 0.7 * inch, 2.3 * inch])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_GREY)), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7)]))
            story.append(t)
            story.append(Spacer(1, 10))
        if data["validation"]:
            h2("A.2 Model validation vs. real PROMETEO flights")
            para("This is the SIMULATION MODEL's own track record against 2 real flights of a different vehicle (PROMETEO) - not specific to the vehicle in this report. Included as evidence of how much to trust this app's predictions in general.")
            for line in _validation_paragraphs(data["validation"]):
                para("- " + line)

    doc.multiBuild(story, canvasmaker=_NumberedCanvas(None, footer_left=footer_left))
    return output_path
