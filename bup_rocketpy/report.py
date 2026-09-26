"""PDF + DOCX simulation report (2026-09-26 review item D: REPLACES the
old compliance-style report entirely). A formal simulation report, not a
compliance report - the RCSM compliance table stays on the RCSM page
only, per Diego's explicit instruction. No internal jargon
("CLAUDE.md", "Rule 3", "PROGRESS.md") anywhere in here - this file goes
to LASC judges and teammates, not other developers.

build_report_data() gathers everything from the app's already-computed
state (SimResult, CaseResult dict, MonteCarloResult, parsed .ork/.eng)
into one plain dict - both generate_pdf() and generate_docx() render
from that SAME dict, so the two formats can never silently disagree.
"""
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone

WINE = "#8A1538"
GOLD = "#B79357"
INK = "#211A16"

NOMINAL_PLOT_ORDER = [
    ("altitude", "Altitude"),
    ("vertical_velocity", "Vertical velocity"),
    ("total_velocity", "Total velocity"),
    ("acceleration_boost", "Acceleration (boost phase)"),
    ("mach", "Mach number"),
    ("static_margin", "Static margin vs. time"),
    ("angle_of_attack", "Angle of attack"),
    ("dynamic_pressure", "Dynamic pressure"),
    ("cg_cp", "CG and CP vs. time"),
    ("trajectory_3d", "3D trajectory"),
    ("ground_track", "Ground track (top view)"),
]


def _fresh_path(outputs_dir, basename):
    os.makedirs(outputs_dir, exist_ok=True)
    return os.path.join(outputs_dir, f"{basename}_{uuid.uuid4().hex[:8]}.png")


def _plot_case_altitude_overlay(case_results, outputs_dir):
    """New figure (item D section 8): every RCSM case's altitude curve
    overlaid on one plot, so a reader can compare Ballistic/Nominal/
    Drogue-only/Main-at-apogee at a glance instead of flipping pages."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {"Ballistic": "#9c9c9c", "Nominal": WINE, "DrogueOnly": GOLD, "MainAtApogee": "#4a7c59"}
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
    path = _fresh_path(outputs_dir, "case_altitude_overlay")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _plot_mc_histogram_and_ellipse(mc_result, outputs_dir):
    """Rebuilt from raw sample data (mc_result.apogee_samples/impact_x_
    samples/impact_y_samples) - the report is self-contained, not
    dependent on a transient plot file the Monte Carlo PAGE happened to
    leave on disk."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from bup_rocketpy import monte_carlo

    hist_path = ellipse_path = None
    if mc_result.apogee_samples:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.hist(mc_result.apogee_samples, bins=min(20, max(5, mc_result.n_completed // 3)), color=WINE, alpha=0.75)
        ax.axvline(mc_result.apogee_mean, color=GOLD, linestyle="--", label="mean")
        ax.set_xlabel("Apogee AGL (m)")
        ax.set_ylabel("count")
        ax.legend()
        hist_path = _fresh_path(outputs_dir, "report_mc_histogram")
        fig.tight_layout()
        fig.savefig(hist_path)
        plt.close(fig)

    ellipses = monte_carlo.landing_ellipses(mc_result)
    if ellipses:
        from matplotlib.patches import Ellipse
        fig2, ax2 = plt.subplots(figsize=(6, 6))
        for n_std, color in [(3, "#e0c9a6"), (2, "#c9a876"), (1, WINE)]:
            e = ellipses[n_std]
            ax2.add_patch(Ellipse((e["center_x"], e["center_y"]), e["width"], e["height"], angle=e["angle_deg"], facecolor=color, alpha=0.4, edgecolor=color, label=f"{n_std}-sigma"))
        ax2.scatter(mc_result.impact_x_samples, mc_result.impact_y_samples, s=8, color=INK, zorder=5)
        ax2.set_xlabel("X (m, downrange)")
        ax2.set_ylabel("Y (m, crossrange)")
        ax2.set_aspect("equal")
        ax2.legend()
        ax2.set_title("Landing dispersion")
        ellipse_path = _fresh_path(outputs_dir, "report_mc_ellipse")
        fig2.tight_layout()
        fig2.savefig(ellipse_path)
        plt.close(fig2)
    return hist_path, ellipse_path


def build_report_data(mission_id, author, load_result, sim_result, case_results, mc_result, mc_uncertainties, outputs_dir, app_commit_hash="unknown", include_appendix=False):
    """Gathers everything the report needs into one plain dict. Real
    computation happens here (case-comparison plot, MC plots rebuilt
    from raw samples, optional live validation) - both output formats
    render from the result, they don't recompute anything themselves."""
    from bup_rocketpy.gui import rocket_drawing  # pure matplotlib, no nicegui import - safe to use from a report builder

    parsed = load_result.parsed_ork
    eng_header = load_result.parsed_eng.header
    launch = parsed.launch

    from bup_rocketpy.ork_reader import airframe_length_m

    body_radius = next((t.radius for t in parsed.body_tubes if t.radius), 0.05)
    total_length_m = airframe_length_m(parsed)

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

    nominal_plots = [(key, title, sim_result.plot_paths.get(key)) for key, title in NOMINAL_PLOT_ORDER if sim_result.plot_paths.get(key)]

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

    return {
        "mission_id": mission_id, "vehicle_name": parsed.name, "author": author or "-",
        "app_commit_hash": app_commit_hash, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
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
        "vehicle": {
            "side_profile_path": side_profile_path,
            "length_cm": total_length_m * 100.0, "diameter_cm": body_radius * 2 * 100.0,
            "reference_area_m2": math.pi * body_radius ** 2,
            "dry_mass_kg": sim_result.dry_mass_kg, "dry_cg_m": sim_result.dry_cg_m,
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
        },
        "environment": {
            "site_lat": launch.latitude if launch else None, "site_lon": launch.longitude if launch else None, "site_altitude_m": launch.altitude_m if launch else None,
            "wind_speed_ms": launch.wind_average_ms if launch else None, "wind_direction_deg": launch.wind_direction_deg if launch else None,
            "rail_length_m": launch.rail_length_m if launch else None, "rail_inclination_deg": launch.inclination_deg if launch else None, "rail_direction_deg": launch.rail_direction_deg if launch else None,
        },
        "nominal_plots": nominal_plots,
        "recovery": {
            "rows": sim_result.recovery_rows,
            "descent_plot_path": sim_result.plot_paths.get("descent_velocity"),
        },
        "cases": {"rows": case_rows, "altitude_overlay_path": case_altitude_plot},
        "monte_carlo": mc_block,
        "assumptions": assumptions,
        "validation": validation_block,
    }


def _validation_paragraphs(validation_block):
    lines = []
    for r in validation_block:
        status = "PASS" if r.passes else "FAIL"
        lines.append(f"{r.name}: predicted {r.predicted_agl_m:.1f} m vs. real flight {r.target_agl_m:.1f} m (error {r.error_pct:+.1f}%, {status} against +-5%). {r.notes}")
    return lines


def generate_docx(output_path, data):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()

    doc.add_heading(f"Mission {data['mission_id']}", level=0)
    p = doc.add_paragraph(data["vehicle_name"])
    p.runs[0].font.size = Pt(18)
    doc.add_paragraph(f"Beyond UP  |  Generated {data['generated_at']}  |  App version {data['app_commit_hash']}")
    doc.add_paragraph(f"Author: {data['author']}")
    doc.add_page_break()

    doc.add_heading("1. Executive summary", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Metric", "Value"
    for label, value in data["kpis"]:
        row = table.add_row().cells
        row[0].text, row[1].text = label, value

    doc.add_heading("2. Vehicle", level=1)
    doc.add_picture(data["vehicle"]["side_profile_path"], width=Inches(6))
    v = data["vehicle"]
    for label, value in [
        ("Length", f"{v['length_cm']:.1f} cm"), ("Diameter", f"{v['diameter_cm']:.1f} cm"),
        ("Reference area", f"{v['reference_area_m2']:.5f} m2"),
        ("Dry mass", f"{v['dry_mass_kg']:.3f} kg"), ("Dry CG", f"{v['dry_cg_m']:.3f} m from nose"),
        ("Static margin range (ascent)", f"{v['min_margin_cal']:.2f} - {v['max_margin_cal']:.2f} cal"),
        ("Stable (FLT 4.3.5, 1.5-4 cal)", "YES" if v["is_stable"] else "NO"),
    ]:
        doc.add_paragraph(f"{label}: {value}")
    if v["parachutes"]:
        pt = doc.add_table(rows=1, cols=4)
        pt.rows[0].cells[0].text, pt.rows[0].cells[1].text, pt.rows[0].cells[2].text, pt.rows[0].cells[3].text = "Parachute", "Diameter (m)", "Area (m2)", "Cd"
        for name, diam, area, cd in v["parachutes"]:
            row = pt.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = name, f"{diam:.2f}", f"{area:.3f}", f"{cd:.2f}" if cd is not None else "auto"

    doc.add_heading("3. Propulsion", level=1)
    pr = data["propulsion"]
    if pr["thrust_plot_path"]:
        doc.add_picture(pr["thrust_plot_path"], width=Inches(6))
    for label, value in [
        ("Motor", f"{pr['designation']} ({pr['manufacturer']})"),
        ("Total impulse", f"{pr['total_impulse_Ns']:.1f} N*s"),
        ("Average / peak thrust", f"{pr['avg_thrust_N']:.1f} N / {pr['peak_thrust_N']:.1f} N"),
        ("Burn time", f"{pr['burn_time_s']:.2f} s"),
        ("Propellant / dry / total mass", f"{pr['propellant_mass_kg']:.3f} / {pr['dry_mass_kg']:.3f} / {pr['total_mass_kg']:.3f} kg"),
    ]:
        doc.add_paragraph(f"{label}: {value}")

    doc.add_heading("4. Aerodynamics", level=1)
    ae = data["aero"]
    if ae["cd_plot_path"]:
        doc.add_picture(ae["cd_plot_path"], width=Inches(6))
    doc.add_paragraph(f"Drag curve source: {ae['drag_curve_source']}")
    if ae["mach_extrapolated"]:
        doc.add_paragraph(f"WARNING: flight reaches Mach {ae['max_mach']:.2f}, past the curve's {ae['drag_curve_max_mach']:.2f} Mach coverage - results above that speed are constant-Cd extrapolation.")
    else:
        doc.add_paragraph(f"Mach coverage: flight reaches {ae['max_mach']:.2f}, curve covers up to {ae['drag_curve_max_mach']:.2f}." if ae["drag_curve_max_mach"] else "No measured drag curve Mach range on file.")

    doc.add_heading("5. Environment", level=1)
    env = data["environment"]
    doc.add_paragraph(f"Site: {env['site_lat']:.3f}, {env['site_lon']:.3f}, {env['site_altitude_m']:.0f} m MSL" if env["site_lat"] is not None else "Site: not set")
    doc.add_paragraph(f"Wind (recorded average): {env['wind_speed_ms']:.1f} m/s from {env['wind_direction_deg']:.0f} deg" if env["wind_speed_ms"] is not None else "Wind: not set")
    doc.add_paragraph(f"Rail: {env['rail_length_m']:.1f} m, {env['rail_inclination_deg']:.1f} deg inclination, {env['rail_direction_deg']:.0f} deg heading" if env["rail_length_m"] is not None else "Rail: not set")

    doc.add_heading("6. Nominal flight", level=1)
    for key, title, path in data["nominal_plots"]:
        doc.add_heading(title, level=2)
        doc.add_picture(path, width=Inches(6))

    doc.add_heading("7. Recovery", level=1)
    rec = data["recovery"]
    if rec["rows"]:
        rt = doc.add_table(rows=1, cols=7)
        for i, h in enumerate(["Chute", "Diameter (m)", "Area (m2)", "Cd*S (m2)", "Deploy time (s)", "Sim descent (m/s)", "Hand-calc descent (m/s)"]):
            rt.rows[0].cells[i].text = h
        for r in rec["rows"]:
            row = rt.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = r.name, f"{r.diameter_m:.2f}", f"{r.area_m2:.3f}", f"{r.cd_s_m2:.3f}"
            row[4].text, row[5].text, row[6].text = f"{r.deploy_time_s:.1f}", f"{r.descent_rate_sim_ms:.1f}", f"{r.hand_terminal_velocity_at_ground_ms:.1f}"
    if rec["descent_plot_path"]:
        doc.add_picture(rec["descent_plot_path"], width=Inches(6))

    doc.add_heading("8. Flight cases", level=1)
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
    if data["cases"]["altitude_overlay_path"]:
        doc.add_picture(data["cases"]["altitude_overlay_path"], width=Inches(6))

    doc.add_heading("9. Monte Carlo", level=1)
    mc = data["monte_carlo"]
    if mc is None:
        doc.add_paragraph("Not run for this report.")
    else:
        if mc["low_n_warning"]:
            doc.add_paragraph(f"N = {mc['n_requested']} - not statistically meaningful (fewer than 100 samples). Treat this as a rough check, not a real dispersion estimate.")
        doc.add_paragraph(f"N = {mc['n_completed']} completed ({mc['n_excluded']} excluded)")
        doc.add_paragraph(f"Apogee: mean {mc['apogee_mean']:.1f} m, 90% interval [{mc['apogee_p05']:.1f}, {mc['apogee_p95']:.1f}] m")
        if mc["histogram_path"]:
            doc.add_picture(mc["histogram_path"], width=Inches(6))
        if mc["ellipse_path"]:
            doc.add_picture(mc["ellipse_path"], width=Inches(5))
        if mc["uncertainties"]:
            ut = doc.add_table(rows=1, cols=3)
            ut.rows[0].cells[0].text, ut.rows[0].cells[1].text, ut.rows[0].cells[2].text = "Uncertainty", "Std dev", "Source"
            for name, std_dev, source in mc["uncertainties"]:
                row = ut.add_row().cells
                row[0].text, row[1].text, row[2].text = name, f"{std_dev:.4g}", source

    doc.add_heading("10. Assumptions and data sources", level=1)
    for a in data["assumptions"]:
        doc.add_paragraph(a, style="List Bullet")

    if data["validation"]:
        doc.add_heading("Appendix: model validation vs. real PROMETEO flights", level=1)
        doc.add_paragraph("This is the SIMULATION MODEL's own track record against 2 real flights of a different vehicle (PROMETEO) - not specific to the vehicle in this report. Included as evidence of how much to trust this app's predictions in general.")
        for line in _validation_paragraphs(data["validation"]):
            doc.add_paragraph(line, style="List Bullet")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    return output_path


class _NumberedCanvas:
    """Adds 'Page N of M' to every page - reportlab's standard two-pass
    recipe (BaseDocTemplate.multiBuild already does pass 1/2 for the TOC;
    this canvas subclass piggybacks on the same page count)."""
    def __init__(self, canvas_cls):
        self._canvas_cls = canvas_cls

    def __call__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas as canvas_module

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
                    self.drawRightString(200 * 2.83, 20, f"Page {self._pageNumber} of {num_pages}")
                    canvas_module.Canvas.showPage(self)
                canvas_module.Canvas.save(self)

        return NumberedCanvas(*args, **kwargs)


def generate_pdf(output_path, data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import BaseDocTemplate, Frame, Image, PageTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.platypus.tableofcontents import TableOfContents

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1Numbered", parent=styles["Heading1"], textColor=colors.HexColor(WINE)))
    styles.add(ParagraphStyle(name="H2Numbered", parent=styles["Heading2"], textColor=colors.HexColor(INK)))

    frame = Frame(0.75 * inch, 0.75 * inch, letter[0] - 1.5 * inch, letter[1] - 1.5 * inch, id="normal")
    doc = BaseDocTemplate(output_path, pagesize=letter, pageTemplates=[PageTemplate(id="all", frames=[frame])])

    def h1(text, key):
        p = Paragraph(text, styles["H1Numbered"])
        p._bookmarkName = key
        return p

    story = []
    # Cover
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("Beyond UP", ParagraphStyle(name="Cover0", fontSize=14, textColor=colors.HexColor(GOLD), alignment=1)))
    story.append(Paragraph(f"Mission {data['mission_id']}", ParagraphStyle(name="Cover1", fontSize=28, textColor=colors.HexColor(WINE), alignment=1, spaceBefore=10)))
    story.append(Paragraph(data["vehicle_name"], ParagraphStyle(name="Cover2", fontSize=18, alignment=1, spaceBefore=6)))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(f"Generated {data['generated_at']}", ParagraphStyle(name="Cover3", fontSize=10, alignment=1)))
    story.append(Paragraph(f"App version: {data['app_commit_hash']}", ParagraphStyle(name="Cover4", fontSize=10, alignment=1)))
    story.append(Paragraph(f"Author: {data['author']}", ParagraphStyle(name="Cover5", fontSize=10, alignment=1)))
    story.append(Spacer(1, 1 * inch))

    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle(name="TOC1", fontSize=11, leftIndent=10)]
    story.append(Paragraph("Table of contents", styles["Heading1"]))
    story.append(toc)
    story.append(PageBreak())

    def track(text, level=0):
        story.append(Paragraph(text, styles["H1Numbered"] if level == 0 else styles["H2Numbered"]))

    story.append(Paragraph("1. Executive summary", styles["H1Numbered"]))
    kpi_rows = [["Metric", "Value"]] + [[k, v] for k, v in data["kpis"]]
    t = Table(kpi_rows, colWidths=[2.5 * inch, 3 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(WINE)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story.append(t)
    story.append(PageBreak())

    story.append(Paragraph("2. Vehicle", styles["H1Numbered"]))
    v = data["vehicle"]
    story.append(Image(v["side_profile_path"], width=5.5 * inch, height=5.5 * inch * 0.4))
    for label, value in [
        ("Length", f"{v['length_cm']:.1f} cm"), ("Diameter", f"{v['diameter_cm']:.1f} cm"),
        ("Reference area", f"{v['reference_area_m2']:.5f} m2"),
        ("Dry mass", f"{v['dry_mass_kg']:.3f} kg"), ("Dry CG", f"{v['dry_cg_m']:.3f} m from nose"),
        ("Static margin range (ascent)", f"{v['min_margin_cal']:.2f} - {v['max_margin_cal']:.2f} cal"),
        ("Stable (1.5-4 cal)", "YES" if v["is_stable"] else "NO"),
    ]:
        story.append(Paragraph(f"<b>{label}:</b> {value}", styles["BodyText"]))
    if v["parachutes"]:
        rows = [["Parachute", "Diameter (m)", "Area (m2)", "Cd"]] + [[n, f"{d:.2f}", f"{a:.3f}", f"{c:.2f}" if c is not None else "auto"] for n, d, a, c in v["parachutes"]]
        story.append(Table(rows, colWidths=[1.8 * inch, 1.2 * inch, 1.2 * inch, 0.8 * inch]))
    story.append(PageBreak())

    story.append(Paragraph("3. Propulsion", styles["H1Numbered"]))
    pr = data["propulsion"]
    if pr["thrust_plot_path"]:
        story.append(Image(pr["thrust_plot_path"], width=5.5 * inch, height=5.5 * inch * 0.55))
    for label, value in [
        ("Motor", f"{pr['designation']} ({pr['manufacturer']})"),
        ("Total impulse", f"{pr['total_impulse_Ns']:.1f} N*s"),
        ("Average / peak thrust", f"{pr['avg_thrust_N']:.1f} N / {pr['peak_thrust_N']:.1f} N"),
        ("Burn time", f"{pr['burn_time_s']:.2f} s"),
        ("Propellant / dry / total mass", f"{pr['propellant_mass_kg']:.3f} / {pr['dry_mass_kg']:.3f} / {pr['total_mass_kg']:.3f} kg"),
    ]:
        story.append(Paragraph(f"<b>{label}:</b> {value}", styles["BodyText"]))
    story.append(PageBreak())

    story.append(Paragraph("4. Aerodynamics", styles["H1Numbered"]))
    ae = data["aero"]
    if ae["cd_plot_path"]:
        story.append(Image(ae["cd_plot_path"], width=5.5 * inch, height=5.5 * inch * 0.6))
    story.append(Paragraph(f"<b>Drag curve source:</b> {ae['drag_curve_source']}", styles["BodyText"]))
    if ae["mach_extrapolated"]:
        story.append(Paragraph(f"<font color='red'><b>WARNING:</b> flight reaches Mach {ae['max_mach']:.2f}, past the curve's {ae['drag_curve_max_mach']:.2f} Mach coverage - results above that speed are constant-Cd extrapolation.</font>", styles["BodyText"]))
    story.append(PageBreak())

    story.append(Paragraph("5. Environment", styles["H1Numbered"]))
    env = data["environment"]
    if env["site_lat"] is not None:
        story.append(Paragraph(f"<b>Site:</b> {env['site_lat']:.3f}, {env['site_lon']:.3f}, {env['site_altitude_m']:.0f} m MSL", styles["BodyText"]))
    if env["wind_speed_ms"] is not None:
        story.append(Paragraph(f"<b>Wind (recorded average):</b> {env['wind_speed_ms']:.1f} m/s from {env['wind_direction_deg']:.0f} deg", styles["BodyText"]))
    if env["rail_length_m"] is not None:
        story.append(Paragraph(f"<b>Rail:</b> {env['rail_length_m']:.1f} m, {env['rail_inclination_deg']:.1f} deg inclination, {env['rail_direction_deg']:.0f} deg heading", styles["BodyText"]))
    story.append(PageBreak())

    story.append(Paragraph("6. Nominal flight", styles["H1Numbered"]))
    for key, title, path in data["nominal_plots"]:
        story.append(Paragraph(title, styles["H2Numbered"]))
        story.append(Image(path, width=5.5 * inch, height=5.5 * inch * 0.55))
        story.append(Spacer(1, 6))
    story.append(PageBreak())

    story.append(Paragraph("7. Recovery", styles["H1Numbered"]))
    rec = data["recovery"]
    if rec["rows"]:
        rows = [["Chute", "Diam (m)", "Area (m2)", "Cd*S", "Deploy (s)", "Sim (m/s)", "Hand-calc (m/s)"]]
        for r in rec["rows"]:
            rows.append([r.name, f"{r.diameter_m:.2f}", f"{r.area_m2:.3f}", f"{r.cd_s_m2:.3f}", f"{r.deploy_time_s:.1f}", f"{r.descent_rate_sim_ms:.1f}", f"{r.hand_terminal_velocity_at_ground_ms:.1f}"])
        story.append(Table(rows, colWidths=[1.3 * inch] + [0.75 * inch] * 6))
    if rec["descent_plot_path"]:
        story.append(Image(rec["descent_plot_path"], width=5.5 * inch, height=5.5 * inch * 0.55))
    story.append(PageBreak())

    story.append(Paragraph("8. Flight cases", styles["H1Numbered"]))
    rows = [["Case", "Apogee AGL (m)", "Max speed (m/s)", "Rail exit (m/s)", "Note"]]
    for name, apogee, max_speed, rail_exit, note in data["cases"]["rows"]:
        rows.append([name, f"{apogee:.1f}" if apogee is not None else "-", f"{max_speed:.1f}" if max_speed is not None else "-", f"{rail_exit:.1f}" if rail_exit is not None else "-", note or ""])
    story.append(Table(rows, colWidths=[1.1 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch, 1.7 * inch]))
    if data["cases"]["altitude_overlay_path"]:
        story.append(Image(data["cases"]["altitude_overlay_path"], width=5.5 * inch, height=5.5 * inch * 0.55))
    story.append(PageBreak())

    story.append(Paragraph("9. Monte Carlo", styles["H1Numbered"]))
    mc = data["monte_carlo"]
    if mc is None:
        story.append(Paragraph("Not run for this report.", styles["BodyText"]))
    else:
        if mc["low_n_warning"]:
            story.append(Paragraph(f"<font color='orange'>N = {mc['n_requested']} - not statistically meaningful (fewer than 100 samples). Treat this as a rough check, not a real dispersion estimate.</font>", styles["BodyText"]))
        story.append(Paragraph(f"N = {mc['n_completed']} completed ({mc['n_excluded']} excluded)", styles["BodyText"]))
        story.append(Paragraph(f"Apogee: mean {mc['apogee_mean']:.1f} m, 90% interval [{mc['apogee_p05']:.1f}, {mc['apogee_p95']:.1f}] m", styles["BodyText"]))
        if mc["histogram_path"]:
            story.append(Image(mc["histogram_path"], width=5 * inch, height=5 * inch * 0.58))
        if mc["ellipse_path"]:
            story.append(Image(mc["ellipse_path"], width=4 * inch, height=4 * inch))
        if mc["uncertainties"]:
            rows = [["Uncertainty", "Std dev", "Source"]] + [[n, f"{s:.4g}", src] for n, s, src in mc["uncertainties"]]
            story.append(Table(rows, colWidths=[1.5 * inch, 0.8 * inch, 3.2 * inch]))
    story.append(PageBreak())

    story.append(Paragraph("10. Assumptions and data sources", styles["H1Numbered"]))
    for a in data["assumptions"]:
        story.append(Paragraph("- " + a, styles["BodyText"]))

    if data["validation"]:
        story.append(PageBreak())
        story.append(Paragraph("Appendix: model validation vs. real PROMETEO flights", styles["H1Numbered"]))
        story.append(Paragraph("This is the SIMULATION MODEL's own track record against 2 real flights of a different vehicle (PROMETEO) - not specific to the vehicle in this report. Included as evidence of how much to trust this app's predictions in general.", styles["BodyText"]))
        for line in _validation_paragraphs(data["validation"]):
            story.append(Paragraph("- " + line, styles["BodyText"]))

    doc.multiBuild(story, canvasmaker=_NumberedCanvas(None))
    return output_path
