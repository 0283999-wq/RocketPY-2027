"""DOCX report (2026-09-28 review item 4): a real Word document - Heading
styles (so Word's own navigation pane and TOC field work), a genuine TOC
FIELD (populated by Word itself on open/F9, not a static placeholder
paragraph), a header/footer, bordered tables, and yellow-highlighted
"[EDIT: ...]" runs at the few spots meant for a human to customize
(author, team members) rather than requiring Diego to retype anything
else. Renders from the SAME data dict report.build_report_data()
produces - never a second, independently-typed set of numbers from the
PDF path.
"""
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from bup_rocketpy import report as report_module

WINE_RGB = RGBColor(0x8A, 0x15, 0x38)
GOLD_RGB = RGBColor(0xB7, 0x93, 0x57)
INK_RGB = RGBColor(0x21, 0x1A, 0x16)
MUTED_RGB = RGBColor(0x6B, 0x62, 0x59)
WARNING_RGB = RGBColor(0x95, 0x59, 0x00)  # matches report_html.py's WARNING="#955900"


def _add_toc_field(doc):
    """The standard python-docx TOC-field recipe: a `TOC` field Word
    populates itself (on open, or F9 to refresh) - the reportlab-era
    report had a hand-rolled TOC that was never actually wired to
    notify() and always rendered empty (Diego's "placeholder for table
    of contents" report); this is Word's own native mechanism, so there
    is no custom pagination logic to get wrong."""
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-2" \\h \\z \\u'
    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Right-click and choose \"Update Field\" (or press F9) to populate this table of contents."
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r = run._r
    r.append(fld_begin)
    r.append(instr)
    r.append(fld_separate)
    r.append(placeholder)
    r.append(fld_end)


def _set_table_borders(table):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "B8AEA3")
        borders.append(el)
    tbl_pr.append(borders)


def _shade_cell(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _header_row_bold(table, hex_bg="F2EFEA"):
    for cell in table.rows[0].cells:
        _shade_cell(cell, hex_bg)
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True


def _edit_mark(paragraph, text):
    """A yellow-highlighted "[EDIT: ...]" run - CLAUDE.md Rule 2 ("never
    invent data") applied to the report itself: rather than inventing
    team member names or a mission ID this app has no way to know,
    those few genuinely-optional-to-customize spots are marked for a
    human, in the DOCX only (the PDF has no equivalent editable-by-hand
    step, so marking it there would just be visual noise)."""
    run = paragraph.add_run(f" [EDIT: {text}]")
    run.font.highlight_color = 7  # WD_COLOR_INDEX.YELLOW
    run.italic = True


def _style_heading(doc, text, level, color=INK_RGB):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = color
    return h


def _add_header_footer(doc, data):
    section = doc.sections[0]
    header_p = section.header.paragraphs[0]
    header_p.text = f"Beyond UP · Mission {data['mission_id']} · {data['vehicle_name']}"
    header_p.runs[0].font.size = Pt(8)
    header_p.runs[0].font.color.rgb = MUTED_RGB

    footer_p = section.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_p.add_run("Computational Simulation Report · ")
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = MUTED_RGB
    # "Page X of Y" field (PAGE/NUMPAGES), same field-code mechanism as the TOC.
    for instr_text in ("PAGE", " of ", "NUMPAGES"):
        if instr_text == " of ":
            r = footer_p.add_run(instr_text)
            r.font.size = Pt(8)
            r.font.color.rgb = MUTED_RGB
            continue
        run = footer_p.add_run()
        fld_begin = OxmlElement("w:fldChar")
        fld_begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = instr_text
        fld_end = OxmlElement("w:fldChar")
        fld_end.set(qn("w:fldCharType"), "end")
        run._r.append(fld_begin)
        run._r.append(instr)
        run._r.append(fld_end)
        run.font.size = Pt(8)
        run.font.color.rgb = MUTED_RGB


def generate_docx(output_path, data):
    doc = Document()
    for style_name in ("Heading 1", "Heading 2"):
        style = doc.styles[style_name]
        style.font.color.rgb = WINE_RGB if style_name == "Heading 1" else INK_RGB
    doc.styles["Normal"].font.size = Pt(10)

    _add_header_footer(doc, data)

    # -- Title page --
    title_p = doc.add_paragraph()
    run = title_p.add_run("Computational Simulation Report")
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = INK_RGB
    sub_p = doc.add_paragraph(f"Mission {data['mission_id']} · {data['vehicle_name']} · Trajectory, aerodynamics and flight-dynamics analysis")
    sub_p.runs[0].font.size = Pt(12)
    sub_p.runs[0].font.color.rgb = MUTED_RGB

    org_p = doc.add_paragraph()
    org_run = org_p.add_run("BEYOND UP")
    org_run.bold = True
    org_run.font.color.rgb = WINE_RGB
    team_p = doc.add_paragraph(data["report_text"]["team"].replace("\n", " · "))
    if data["report_text"]["team"].strip() == report_module._DEFAULT_TEXT_BLOCKS["team"]:
        _edit_mark(team_p, "add the real team member names for this submission")
    author_p = doc.add_paragraph(f"{data['event_name']}  |  Generated {data['generated_at']}  |  App version {data['app_commit_hash']}  |  Author: {data['author']}")
    if data["author"] in (None, "", "-"):
        _edit_mark(author_p, "add the report author's name")

    doc.add_paragraph(
        f"This report summarizes the predicted flight of {data['vehicle_name']}: an apogee of "
        f"{next(v for k, v in data['kpis'] if k == 'Apogee AGL')} at a peak speed of "
        f"{next(v for k, v in data['kpis'] if k == 'Max speed')} (Mach {next(v for k, v in data['kpis'] if k == 'Max Mach')}), "
        f"with a minimum static margin of {data['vehicle']['min_margin_cal']:.2f} cal through the ascent."
    )
    kt = doc.add_table(rows=2, cols=4)
    _set_table_borders(kt)
    for i, (label, value) in enumerate(data["kpi_cards"]):
        kt.rows[0].cells[i].text = label
        kt.rows[1].cells[i].text = value
        _shade_cell(kt.rows[0].cells[i], "F2EFEA")
        for p in kt.rows[0].cells[i].paragraphs:
            for r in p.runs:
                r.font.size = Pt(8)
                r.font.color.rgb = MUTED_RGB
        for p in kt.rows[1].cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.color.rgb = WINE_RGB
    doc.add_page_break()

    _style_heading(doc, "Table of contents", 1)
    _add_toc_field(doc)
    doc.add_page_break()

    fig_no = [0]

    def figure(path, caption, width=6):
        if not path:
            return None
        fig_no[0] += 1
        doc.add_picture(path, width=Inches(width))
        p = doc.add_paragraph()
        r = p.add_run(f"Figure {fig_no[0]}. {caption}")
        r.bold = True
        r.font.size = Pt(9)
        return fig_no[0]

    def kv_table(rows, cols=2):
        t = doc.add_table(rows=0, cols=cols)
        _set_table_borders(t)
        for row_vals in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row_vals):
                cells[i].text = str(v)
        return t

    # 1. General information and set-up
    _style_heading(doc, "1. General information and set-up", 1)
    doc.add_paragraph(report_module._prose_deliverables(data))
    gi = data.get("general_info")
    if gi:
        _style_heading(doc, "1.1 Analysis environment", 2)
        kv_table([
            ("Simulation engine", gi["software"]), ("Application build", gi["app_version"]),
            ("CPU", gi["cpu"]), ("Operating system", gi["os"]),
            ("Computation time", f"{gi['computation_time_s']:.2f} s" if gi["computation_time_s"] is not None else "n/a"),
        ])
        _style_heading(doc, "1.2 Model information", 2)
        kv_table(gi["model_files"])
        if gi.get("cd_curve_stale"):
            p = doc.add_paragraph()
            run = p.add_run(f"Cd curve may be outdated: {gi['cd_curve_freshness_note']}")
            run.bold = True
            run.font.color.rgb = WARNING_RGB
        if gi["integrator"]:
            _style_heading(doc, "1.3 Simulation parameters", 2)
            integ = gi["integrator"]
            kv_table([
                ("ODE solver", integ["ode_solver"]), ("Equations of motion", integ["equations_of_motion"]),
                ("Relative tolerance (rtol)", integ["rtol"]), ("Absolute tolerance (atol)", integ["atol_summary"]),
                ("Max. time step", integ["max_time_step"]), ("Min. time step", integ["min_time_step"]),
                ("Termination condition", integ["termination"]),
            ])

    # 2. Vehicle
    _style_heading(doc, "2. Vehicle configuration and mass properties", 1)
    v = data["vehicle"]
    fn = figure(v["side_profile_path"], "Vehicle side profile with CG/CP and static margin.", width=6)
    doc.add_paragraph(report_module._prose_vehicle(data, fn or "?"))
    kv_table([
        ("Length", f"{v['length_cm']:.1f} cm"), ("Diameter", f"{v['diameter_cm']:.1f} cm"),
        ("Reference area", f"{v['reference_area_m2']:.5f} m2"),
        ("Dry mass", f"{v['dry_mass_kg']:.3f} kg"), ("Dry CG", f"{v['dry_cg_m']:.3f} m from nose"),
        ("Static margin range (ascent min.)", f"{v['min_margin_cal']:.2f} - {v['max_margin_cal']:.2f} cal"),
        ("Stable (FLT 4.3.5/4.3.6, 1.5-4 cal)", "YES" if v["is_stable"] else "NO"),
    ])
    _style_heading(doc, "2.0 Mass breakdown", 2)
    kv_table([
        ("Dry rocket (no motor)", f"{v['dry_mass_kg']:.3f} kg"), ("Motor, loaded (dry + propellant)", f"{v['motor_loaded_kg']:.3f} kg"),
        ("Motor propellant", f"{v['motor_propellant_kg']:.3f} kg"), ("Motor dry (casing)", f"{v['motor_dry_kg']:.3f} kg"),
        ("Liftoff mass", f"{v['liftoff_mass_kg']:.3f} kg"), ("Descent mass (dry rocket + spent motor casing)", f"{v['descent_mass_kg']:.3f} kg"),
    ])
    if v["parachutes"]:
        pt = doc.add_table(rows=1, cols=4)
        _set_table_borders(pt)
        pt.rows[0].cells[0].text, pt.rows[0].cells[1].text, pt.rows[0].cells[2].text, pt.rows[0].cells[3].text = "Parachute", "Diameter (m)", "Area (m2)", "Cd"
        _header_row_bold(pt)
        for name, diam, area, cd in v["parachutes"]:
            row = pt.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = name, f"{diam:.2f}", f"{area:.3f}", f"{cd:.2f}" if cd is not None else "auto"
    if v["mass_plot_path"]:
        figure(v["mass_plot_path"], "Total mass (rocket + motor) vs. time.")

    # 3. Propulsion
    _style_heading(doc, "3. Propulsion", 1)
    pr = data["propulsion"]
    fn = figure(pr["thrust_plot_path"], "Thrust curve used for this simulation.")
    doc.add_paragraph(report_module._prose_propulsion(data, fn or "?"))
    kv_table([
        ("Motor", f"{pr['designation']} ({pr['manufacturer']})"),
        ("Total impulse", f"{pr['total_impulse_Ns']:.1f} N*s"),
        ("Average / peak thrust", f"{pr['avg_thrust_N']:.1f} N / {pr['peak_thrust_N']:.1f} N"),
        ("Burn time", f"{pr['burn_time_s']:.2f} s"),
        ("Propellant / dry / total mass", f"{pr['propellant_mass_kg']:.3f} / {pr['dry_mass_kg']:.3f} / {pr['total_mass_kg']:.3f} kg"),
    ])

    # 4. Trajectory
    _style_heading(doc, "4. Trajectory (nominal and ballistic)", 1)
    first = True
    for key, title, path in data["trajectory_plots"]:
        if first:
            fn = figure(path, "Ascent and descent trajectory - see remaining plots below for individual quantities.")
            doc.add_paragraph(report_module._prose_trajectory(data, fn or "?"))
            first = False
        else:
            _style_heading(doc, title, 2)
            doc.add_picture(path, width=Inches(6))

    # 5. Aerodynamics
    _style_heading(doc, "5. Aerodynamics", 1)
    ae = data["aero"]
    fn = figure(ae["cd_plot_path"], "Drag coefficient vs. Mach (curve actually used).")
    doc.add_paragraph(report_module._prose_aero(data, fn or "?"))
    for key, title, path in ae["extra_plots"]:
        _style_heading(doc, title, 2)
        doc.add_picture(path, width=Inches(6))

    # 6. Stability
    _style_heading(doc, "6. Stability", 1)
    margin_path = next((p for k, t, p in data["stability_plots"] if k == "static_margin"), None)
    fn = figure(margin_path, "Static margin vs. time, with the RCSM's 1.5-4.0 cal allowed band shaded.")
    doc.add_paragraph(report_module._prose_stability(data, fn or "?"))
    for key, title, path in data["stability_plots"]:
        if key == "static_margin":
            continue
        _style_heading(doc, title, 2)
        doc.add_picture(path, width=Inches(6))
    if data["barrowman"]:
        bw = data["barrowman"]
        _style_heading(doc, "6.1 Independent analytical verification (Barrowman)", 2)
        doc.add_paragraph(bw["method"])
        kv_table([
            ("Nose CN-alpha / CP", f"{bw['nose_cn_alpha']:.2f} /rad @ {bw['nose_cp_m']:.3f} m from nose"),
            ("Fins CN-alpha (total) / CP", f"{bw['fins_cn_alpha']:.2f} /rad @ {bw['fins_cp_m']:.3f} m from nose"),
            ("Hand-calculated CP (total CN-alpha)", f"{bw['cp_m']:.3f} m ({bw['cn_alpha_total']:.2f} /rad)"),
        ] + ([("RocketPy's own CP (t=0) / agreement", f"{bw['rocketpy_cp_m']:.3f} m ({bw['diff_pct']:+.1f}%)")] if bw.get("rocketpy_cp_m") is not None else []))
    if data.get("openrocket_comparison"):
        oc = data["openrocket_comparison"]
        _style_heading(doc, f"6.2 Comparison against OpenRocket ({oc['sim_name']})", 2)
        doc.add_paragraph(
            "\"Static margin (ascent min.)\" above is the worst point across the whole ascent - a different, "
            "safety-focused number from \"Stability at Mach 0.3\" below, which is OpenRocket's own default "
            "design-view snapshot (t=0 mass, Mach 0.3 aerodynamics only)."
        ).runs[0].font.size = Pt(8)
        ct = doc.add_table(rows=1, cols=4)
        _set_table_borders(ct)
        for i, h in enumerate(["Quantity", "Ours", "OpenRocket", "Diff"]):
            ct.rows[0].cells[i].text = h
        _header_row_bold(ct)
        for row in oc["rows"]:
            cells = ct.add_row().cells
            cells[0].text = row.label
            cells[1].text = f"{row.ours:.{row.decimals}f} {row.unit}".strip() if row.ours is not None else "n/a"
            cells[2].text = f"{row.openrocket:.{row.decimals}f} {row.unit}".strip() if row.openrocket is not None else "n/a"
            if row.pct_diff is not None:
                cells[3].text = f"{row.pct_diff:+.2f}%"
                cells[3].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xB3, 0x26, 0x1E) if row.over_threshold else RGBColor(0x2C, 0x77, 0x30)
                cells[3].paragraphs[0].runs[0].bold = True
            else:
                cells[3].text = "n/a"
        doc.add_paragraph(
            "CP-derived rows use a 2% tolerance (RocketPy and OpenRocket use slightly different body-lift models, "
            "a documented and expected difference); every other row uses 1%."
        ).runs[0].font.size = Pt(8)

    # 7. Recovery
    _style_heading(doc, "7. Recovery and landing footprint", 1)
    rec = data["recovery"]
    if rec["rows"]:
        rt = doc.add_table(rows=1, cols=7)
        _set_table_borders(rt)
        for i, h in enumerate(["Stage", "Diameter (m)", "Area (m2)", "Cd*S (m2)", "Deploy (s)", "Sim descent (m/s)", "Hand-calc descent (m/s)"]):
            rt.rows[0].cells[i].text = h
        _header_row_bold(rt)
        for r in rec["rows"]:
            row = rt.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = r.name, f"{r.diameter_m:.2f}", f"{r.area_m2:.3f}", f"{r.cd_s_m2:.3f}"
            row[4].text, row[5].text, row[6].text = f"{r.deploy_time_s:.1f}", f"{r.descent_rate_sim_ms:.1f}", f"{r.hand_terminal_velocity_at_ground_ms:.1f}"
        for r in rec["rows"]:
            if r.note:
                p = doc.add_paragraph()
                run = p.add_run(f'"{r.name}" row above is misleading: {r.note}')
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(0xB3, 0x26, 0x1E)
    fn = figure(rec["descent_plot_path"], "Descent velocity after apogee.")
    doc.add_paragraph(report_module._prose_recovery(data, fn or "?"))

    # 8. Flight cases
    _style_heading(doc, "8. Flight cases (RCSM)", 1)
    ct = doc.add_table(rows=1, cols=5)
    _set_table_borders(ct)
    for i, h in enumerate(["Case", "Apogee AGL (m)", "Max speed (m/s)", "Rail exit (m/s)", "Note"]):
        ct.rows[0].cells[i].text = h
    _header_row_bold(ct)
    for name, apogee, max_speed, rail_exit, note in data["cases"]["rows"]:
        row = ct.add_row().cells
        row[0].text = name
        row[1].text = f"{apogee:.1f}" if apogee is not None else "-"
        row[2].text = f"{max_speed:.1f}" if max_speed is not None else "-"
        row[3].text = f"{rail_exit:.1f}" if rail_exit is not None else "-"
        row[4].text = note or ""
    figure(data["cases"]["altitude_overlay_path"], "Altitude comparison across the required flight cases.")

    # 9. Monte Carlo
    _style_heading(doc, "9. Monte Carlo dispersion", 1)
    mc = data["monte_carlo"]
    doc.add_paragraph(report_module._prose_monte_carlo(data))
    if mc is not None:
        figure(mc["histogram_path"], "Apogee distribution across Monte Carlo trajectories.")
        figure(mc["ellipse_path"], "Landing dispersion footprint (1/2/3-sigma).")
        if mc["uncertainties"]:
            ut = doc.add_table(rows=1, cols=3)
            _set_table_borders(ut)
            ut.rows[0].cells[0].text, ut.rows[0].cells[1].text, ut.rows[0].cells[2].text = "Uncertainty", "Std dev", "Source"
            _header_row_bold(ut)
            for name, std_dev, source in mc["uncertainties"]:
                row = ut.add_row().cells
                row[0].text, row[1].text, row[2].text = name, f"{std_dev:.4g}", source

    # 10. Global min-max table
    _style_heading(doc, "10. Global min-max table", 1)
    doc.add_paragraph("Minimum and maximum of every key flight variable across the full simulated trajectory, with the time each occurs.").runs[0].font.size = Pt(8)
    if data.get("global_minmax"):
        mt = doc.add_table(rows=1, cols=5)
        _set_table_borders(mt)
        for i, h in enumerate(["Variable", "Minimum", "at t (s)", "Maximum", "at t (s)"]):
            mt.rows[0].cells[i].text = h
        _header_row_bold(mt)
        for label, unit, vmin, tmin, vmax, tmax, decimals in data["global_minmax"]:
            row = mt.add_row().cells
            row[0].text = f"{label} ({unit})"
            row[1].text = f"{vmin:.{decimals}f}" if vmin is not None else "n/a"
            row[2].text = f"{tmin:.2f}" if tmin is not None else "-"
            row[3].text = f"{vmax:.{decimals}f}" if vmax is not None else "n/a"
            row[4].text = f"{tmax:.2f}" if tmax is not None else "-"

    # 11. Discussion and conclusions
    _style_heading(doc, "11. Discussion and conclusions", 1)
    _style_heading(doc, "11.1 Discussion", 2)
    doc.add_paragraph(data["report_text"]["discussion"])
    _style_heading(doc, "11.2 Conclusions", 2)
    doc.add_paragraph(data["report_text"]["conclusions"])

    _style_heading(doc, "11.3 Files delivered", 2)
    ft = doc.add_table(rows=1, cols=2)
    _set_table_borders(ft)
    ft.rows[0].cells[0].text, ft.rows[0].cells[1].text = "Item", "Detail"
    _header_row_bold(ft)
    for label, value in data["delivered_files"]:
        row = ft.add_row().cells
        row[0].text, row[1].text = label, value

    _style_heading(doc, "11.4 Assumptions and data sources", 2)
    for a in data["assumptions"]:
        doc.add_paragraph(a, style="List Bullet")

    # Appendix A: input data
    _style_heading(doc, "Appendix A — Input data", 1)
    ai = data.get("appendix_input_data")
    if ai:
        _style_heading(doc, "A.1 Motor", 2)
        kv_table(ai["motor_table"])
        drag = ai["drag_excerpt"]
        if drag["power_off"] or drag["power_on"]:
            _style_heading(doc, "A.2 Drag curve excerpt (evenly sampled)", 2)
            if drag["power_off"]:
                doc.add_paragraph("Power-off (coast)").runs[0].font.size = Pt(8)
                kv_table([(f"{m:.3f}", f"{cd:.4f}") for m, cd in drag["power_off"]])
            if drag["power_on"]:
                doc.add_paragraph("Power-on (boost)").runs[0].font.size = Pt(8)
                kv_table([(f"{m:.3f}", f"{cd:.4f}") for m, cd in drag["power_on"]])
        _style_heading(doc, "A.3 Parachutes", 2)
        for p in ai["parachutes"]:
            line = f"{p['name']}: {p['diameter_m']:.2f} m, Cd {p['cd']:.2f} " if p["cd"] is not None else f"{p['name']}: {p['diameter_m']:.2f} m, Cd auto "
            if p["deploy_event"] == "altitude":
                line += f"- deploy: at {p['deploy_altitude_m']:.0f} m AGL"
            elif p["deploy_event"] == "apogee":
                line += "- deploy: at apogee"
            else:
                line += f"- deploy: simulated at apogee (.ork says \"{p['deploy_event']}\")"
            if p["deploy_delay_s"]:
                line += f", delay {p['deploy_delay_s']:.1f} s"
            doc.add_paragraph(line)
            if p["deploy_note"]:
                doc.add_paragraph(p["deploy_note"]).runs[0].font.size = Pt(8)
            if p["is_reefed"]:
                doc.add_paragraph(
                    f"  Reefed: {p['reefed_diameter_m']:.2f} m @ Cd {p['reefed_cd']:.2f}, cutter release at "
                    f"{p['cutter_altitude_m']:.0f} m AGL (delay {p['cutter_delay_s']:.1f} s)"
                ).runs[0].font.size = Pt(8)
        _style_heading(doc, "A.4 Atmosphere, wind and rail", 2)
        ra = ai["rail_atmosphere"]
        kv_table([
            ("Launch site", f"{ra['site_lat']:.4f}, {ra['site_lon']:.4f}, {ra['site_altitude_m']:.0f} m MSL" if ra["site_lat"] is not None else "-"),
            ("Wind", f"{ra['wind_speed_ms']:.1f} m/s from {ra['wind_direction_deg']:.0f} deg" if ra["wind_speed_ms"] is not None else "-"),
            ("Launch rail", f"{ra['rail_length_m']:.1f} m, {ra['rail_inclination_deg']:.1f} deg from vertical, heading {ra['rail_direction_deg']:.0f} deg" if ra["rail_length_m"] is not None else "-"),
        ])

        if ai.get("component_rows"):
            _style_heading(doc, "A.5 Component-by-component check", 2)
            doc.add_paragraph(
                "Every component the .ork defines, in the order it appears along the airframe (nose to tail) - "
                "mass uses the exact same per-component logic this app actually flies with, so this can never "
                "silently disagree with the mass table in Section 2."
            )
            ct = doc.add_table(rows=1, cols=6)
            _set_table_borders(ct)
            headers = ["Component", "Type", "Position (m)", "Length (m)", "Mass (kg)", "Status"]
            for i, h in enumerate(headers):
                ct.rows[0].cells[i].text = h
            _header_row_bold(ct)
            for row in ai["component_rows"]:
                cells = ct.add_row().cells
                cells[0].text = row.name
                cells[1].text = row.kind
                cells[2].text = f"{row.position_m:.3f}" if row.position_m is not None else "n/a"
                cells[3].text = f"{row.length_m:.3f}" if row.length_m is not None else "n/a"
                cells[4].text = f"{row.mass_kg:.4f}" if row.mass_kg is not None else "n/a"
                cells[5].text = f"{row.status} - {row.flag}" if row.flag else row.status

    # Appendix B: validation (optional)
    if data["validation"]:
        _style_heading(doc, "Appendix B — Model validation", 1)
        doc.add_paragraph(
            "This is the SIMULATION MODEL's own track record against 2 real flights of a different vehicle "
            "(PROMETEO) - not specific to the vehicle in this report. Included as evidence of how much to trust "
            "this application's predictions in general."
        )
        for line in report_module._validation_paragraphs(data["validation"]):
            doc.add_paragraph(line, style="List Bullet")

    # Appendix C: compliance (optional)
    if data["compliance_rows"]:
        _style_heading(doc, "Appendix C — RCSM compliance (Nominal case)", 1)
        at = doc.add_table(rows=1, cols=4)
        _set_table_borders(at)
        for i, h in enumerate(["Rule", "Check", "Status", "Detail"]):
            at.rows[0].cells[i].text = h
        _header_row_bold(at)
        for row_data in data["compliance_rows"]:
            row = at.add_row().cells
            for i, v in enumerate(row_data[:4]):
                row[i].text = str(v)
            status_cell = row[2]
            status_text = str(row_data[2]) if len(row_data) > 2 else ""
            if status_text in ("PASS", "Met"):
                status_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x2C, 0x77, 0x30)
            elif status_text == "FAIL":
                status_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xB3, 0x26, 0x1E)
            else:
                status_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x95, 0x59, 0x00)
            status_cell.paragraphs[0].runs[0].bold = True

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    return output_path
