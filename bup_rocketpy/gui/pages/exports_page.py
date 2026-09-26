"""The "Exports" page: CSV, PNGs (already produced by Simulate), PDF/DOCX
report, and the LASC .zip with the per-case .py files.
"""
import os

from nicegui import ui

from bup_rocketpy.gui import layout, state
from bup_rocketpy import lasc_package, rcsm_cases, report, run_history, translate

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/exports")
def exports_page():
    with layout.layout("Exports", current_path="/exports"):
        if s["load_result"] is None or s["sim_result"] is None:
            ui.label("Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).").classes("text-gray-500")
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
        ui.label("A formal simulation report - vehicle, propulsion, aerodynamics, environment, every plot, recovery, flight cases, Monte Carlo, assumptions. Not a compliance report (see the RCSM Cases page for that table).").classes("text-sm text-gray-500")
        mission_id_input = ui.input(label="Mission ID", value=s["mission_id"])
        author_input = ui.input(label="Author (optional)")
        appendix_checkbox = ui.checkbox("Include validation appendix (model's track record vs. real PROMETEO flights - computed live, takes a couple extra seconds)", value=False)
        report_status = ui.label("")

        def build_report(fmt):
            mission_id = mission_id_input.value
            s["mission_id"] = mission_id
            if s["case_results"] is None:
                s["case_results"] = rcsm_cases.run_all_cases(
                    s["load_result"].parsed_ork, s["load_result"].parsed_eng, s["load_result"].eng_path,
                    s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                    s["dry_mass_kg"], s["dry_cg_m"],
                )

            data = report.build_report_data(
                mission_id, author_input.value, s["load_result"], s["sim_result"], s["case_results"],
                s["mc_result"], s["mc_uncertainties"], OUTPUTS_DIR,
                app_commit_hash=run_history.current_app_commit_hash(REPO_ROOT),
                include_appendix=appendix_checkbox.value,
            )
            path = os.path.join(OUTPUTS_DIR, f"report.{fmt}")
            if fmt == "docx":
                report.generate_docx(path, data)
            else:
                report.generate_pdf(path, data)
            report_status.set_text(f"Report written: {os.path.basename(path)}")
            report_link_container.clear()
            with report_link_container:
                ui.link(f"Download {os.path.basename(path)}", f"/outputs/{os.path.basename(path)}")

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
            mass_est = translate.MassEstimate(s["dry_mass_kg"], s["dry_cg_m"], "UI export")
            i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
            radius = next(t.radius for t in parsed.body_tubes if t.radius)
            zip_path = os.path.join(OUTPUTS_DIR, f"Mission{mission_id_input.value}_LASC.zip")
            lasc_package.build_lasc_zip(
                zip_path, mission_id_input.value, parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                s["ork_path"], s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                s["dry_mass_kg"], s["dry_cg_m"], i_ax, i_tr, radius,
                cases=[("Ballistic", False), ("Nominal", True)],
                eng_filename=s["eng_filename"], ork_filename=s["ork_filename"],
            )
            zip_status.set_text(f"Zip written: {os.path.basename(zip_path)}")
            ui.link("Download LASC .zip", f"/outputs/{os.path.basename(zip_path)}")

        ui.button("Build LASC .zip", on_click=build_zip)
