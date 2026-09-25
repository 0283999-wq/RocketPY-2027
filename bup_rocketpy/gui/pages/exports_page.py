"""The "Exports" page: CSV, PNGs (already produced by Simulate), PDF/DOCX
report, and the LASC .zip with the per-case .py files.
"""
import os

from nicegui import ui

from bup_rocketpy.gui import layout, state
from bup_rocketpy import lasc_package, rcsm, rcsm_cases, report, translate

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/exports")
def exports_page():
    with layout.layout("Exports", current_path="/exports"):
        if s["load_result"] is None or s["dry_mass_override"] is None or s["dry_cg_override"] is None:
            ui.label("Load files and run Simulate (with a dry mass/CG set) on the Simulate page first.").classes("text-gray-500")
            return

        if s["sim_result"] is not None:
            ui.label("Flight data / plots").classes("text-lg font-bold")
            if s["sim_result"].csv_path:
                ui.link("Download flight data CSV", f"/outputs/{os.path.basename(s['sim_result'].csv_path)}")
            for name, path in s["sim_result"].plot_paths.items():
                if path:
                    ui.link(f"Download {name}.png", f"/outputs/{os.path.basename(path)}")

        ui.separator().classes("my-4")
        ui.label("Report (PDF / DOCX)").classes("text-lg font-bold")
        mission_id_input = ui.input(label="Mission ID", value=s["mission_id"])
        report_status = ui.label("")

        def build_report(fmt):
            mission_id = mission_id_input.value
            s["mission_id"] = mission_id
            parsed = s["load_result"].parsed_ork
            if s["case_results"] is None:
                s["case_results"] = rcsm_cases.run_all_cases(
                    parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                    s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                    s["dry_mass_override"], s["dry_cg_override"],
                )
            if s["compliance_rows"] is None:
                category = rcsm.CATEGORIES["1km_solid"]
                nominal = s["case_results"]["Nominal"]
                s["compliance_rows"] = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=1.0) if nominal.flight else []

            assumptions = [
                f"Dry mass: {s['dry_mass_override']} kg (manual override, see Simulate page)",
                f"Dry CG: {s['dry_cg_override']} m from nose (manual override, see Simulate page)",
                f"Drag curve: {s['load_result'].drag_curve_source}",
            ]
            path = os.path.join(OUTPUTS_DIR, f"report.{fmt}")
            if fmt == "docx":
                report.generate_docx(path, mission_id, parsed.name, s["case_results"], s["compliance_rows"], s["mc_result"], assumptions)
            else:
                report.generate_pdf(path, mission_id, parsed.name, s["case_results"], s["compliance_rows"], s["mc_result"], assumptions)
            report_status.set_text(f"Report written: {os.path.basename(path)}")

        with ui.row():
            ui.button("Generate PDF report", on_click=lambda: build_report("pdf"))
            ui.button("Generate DOCX report", on_click=lambda: build_report("docx"))
        report_link_container = ui.column()

        ui.separator().classes("my-4")
        ui.label("LASC submission .zip").classes("text-lg font-bold")
        ui.label("Per-case .py scripts (CRS 10.1.6 naming) + .eng + .ork + Cd curves, tested to run standalone.").classes("text-sm text-gray-500")
        zip_status = ui.label("")

        def build_zip():
            parsed = s["load_result"].parsed_ork
            mass_est = translate.MassEstimate(s["dry_mass_override"], s["dry_cg_override"], "UI export")
            i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
            radius = next(t.radius for t in parsed.body_tubes if t.radius)
            zip_path = os.path.join(OUTPUTS_DIR, f"Mission{mission_id_input.value}_LASC.zip")
            lasc_package.build_lasc_zip(
                zip_path, mission_id_input.value, parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                s["ork_path"], s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                s["dry_mass_override"], s["dry_cg_override"], i_ax, i_tr, radius,
                cases=[("Ballistic", False), ("Nominal", True)],
            )
            zip_status.set_text(f"Zip written: {os.path.basename(zip_path)}")
            ui.link("Download LASC .zip", f"/outputs/{os.path.basename(zip_path)}")

        ui.button("Build LASC .zip", on_click=build_zip)
