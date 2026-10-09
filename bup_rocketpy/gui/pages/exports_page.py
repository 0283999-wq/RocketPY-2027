"""The "Exports" page: CSV, PNGs (already produced by Simulate), PDF/DOCX
report, and the LASC .zip with the per-case .py files.
"""
import os
import re

from nicegui import run, ui

from bup_rocketpy.gui import components, layout, state
from bup_rocketpy import competition_profiles, lasc_package, rcsm_cases, report, run_history, translate

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(name):
    """Strips characters Windows (the only OS this app's users run on,
    per CLAUDE.md) refuses in a file name, and collapses whitespace to
    underscores - a rocket/site name can freely contain spaces, slashes,
    quotes (e.g. a parachute size like 4" showing up via some other
    field) that would otherwise make the OS reject the save outright."""
    name = _INVALID_FILENAME_CHARS.sub("", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name or "Simulation_Report"


@ui.page("/exports")
def exports_page():
    with layout.layout("Exports", current_path="/exports"):
        components.page_header("Exports", "Flight data, the formal report, and the competition submission package.")
        if s["load_result"] is None or s["sim_result"] is None:
            components.empty_state("download", "Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).", action_label="Go to Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            return

        with ui.row().classes("gap-4 w-full items-start flex-wrap"):
            with components.card(classes="flex-1 min-w-[320px]"):
                ui.label("Flight data / plots").classes("font-bold")
                # 2026-10-09 review item 10: "CSV export = OpenRocket
                # format only" - one CSV per simulation now (pipeline.py's
                # csv_path IS openrocket_csv_path, not a second file).
                if s["sim_result"].csv_path:
                    ui.link("Download flight data CSV (OpenRocket format - 58 columns, event markers)", f"/outputs/{os.path.basename(s['sim_result'].csv_path)}")
                for name, path in s["sim_result"].plot_paths.items():
                    if path:
                        ui.link(f"Download {name}.png", f"/outputs/{os.path.basename(path)}")
                # Preview: the altitude plot, the one every reader wants first.
                altitude_path = s["sim_result"].plot_paths.get("altitude")
                if altitude_path:
                    ui.label("Preview").classes("text-xs mt-2").style("color: var(--bup-muted)")
                    ui.image(altitude_path).classes("w-full rounded")

            with components.card(classes="flex-1 min-w-[320px]"):
                ui.label("Report (PDF / DOCX)").classes("font-bold")
                ui.label("A formal simulation report - vehicle, propulsion, aerodynamics, environment, every plot, recovery, flight cases, Monte Carlo, assumptions. Not a compliance report (see the RCSM Cases page for that table).").classes("text-sm").style("color: var(--bup-muted)")
                mission_id_input = ui.input(label="Mission ID (optional)", value=s["mission_id"])
                author_input = ui.input(label="Author (optional)")
                # 2026-10-09 review item 5: "let me type it, default
                # '<RocketName>_<Site>_<YYYY-MM-DD>_Simulation_Report'
                # (never 'report (7).docx')." - the old code always wrote
                # to the SAME fixed "report.pdf"/"report.docx", so a
                # browser's own download mechanism renamed every repeat
                # download "report (1).pdf", "report (2).pdf"... Typing a
                # real, distinct name each time means every generated
                # report keeps its own identity.
                import datetime as _datetime
                _site = (s["load_result"].simulation_name if s["load_result"] else None) or "Site"
                _default_filename = _sanitize_filename(f"{s['vehicle_name']}_{_site}_{_datetime.date.today().isoformat()}_Simulation_Report")
                filename_input = ui.input(label="File name (no extension - .pdf/.docx added automatically)", value=_default_filename).classes("w-full")
                appendix_checkbox = ui.checkbox("Include validation appendix (model's track record vs. real PROMETEO flights - computed live, takes a couple extra seconds) + RCSM compliance table", value=False)
                report_status = ui.label("")

                with ui.expansion("Editable report text (Introduction, Objectives, Discussion, Conclusions, Team)", value=False).classes("w-full"):
                    ui.label("Leave any of these blank to use an auto-generated default built from this run's own numbers. Saved with the mission (see History) so it survives a reopen.").classes("text-sm").style("color: var(--bup-muted)")
                    text_inputs = {}
                    for key, label in [
                        ("introduction", "Introduction"), ("objectives", "Objectives"),
                        ("discussion", "Discussion"), ("conclusions", "Conclusions"),
                        ("team", "Team block (page 1 header, right side)"),
                    ]:
                        text_inputs[key] = ui.textarea(label=label, value=s["report_text"].get(key, "")).classes("w-full")

                    def _save_report_text():
                        s["report_text"] = {k: inp.value for k, inp in text_inputs.items()}
                        if s.get("current_run_id"):
                            run_history.update_run_text(REPO_ROOT, s["current_run_id"], author=author_input.value, report_text=s["report_text"])
                            ui.notify("Report text saved to this mission.", type="positive")
                        else:
                            ui.notify("Report text saved for this session (no saved mission yet to attach it to - click Simulate first).", type="warning")

                    components.button("Save text to mission", kind="secondary", icon="save", on_click=_save_report_text)

                report_preview_container = ui.column().classes("w-full mt-2")

                async def build_report(fmt):
                    mission_id = mission_id_input.value
                    s["mission_id"] = mission_id
                    s["report_text"] = {k: inp.value for k, inp in text_inputs.items()}
                    if s.get("current_run_id"):
                        run_history.update_run_text(REPO_ROOT, s["current_run_id"], author=author_input.value, report_text=s["report_text"])
                    if s["case_results"] is None:
                        s["case_results"] = rcsm_cases.run_all_cases(
                            s["load_result"].parsed_ork, s["load_result"].parsed_eng, s["load_result"].eng_path,
                            s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                            s["dry_mass_kg"], s["dry_cg_m"],
                            i_axial_override=s["dry_i_axial_kgm2"], i_transverse_override=s["dry_i_transverse_kgm2"],
                        )

                    # Reuses whatever the RCSM Cases page already computed (same
                    # "ONE place" rule as dry_i_axial_kgm2 etc.) rather than
                    # re-deriving a compliance table with its own guessed category -
                    # if Diego hasn't run RCSM Cases yet, the appendix just omits
                    # the table instead of guessing.
                    compliance_rows = s["compliance_rows"] if appendix_checkbox.value else None

                    data = report.build_report_data(
                        mission_id, author_input.value, s["load_result"], s["sim_result"], s["case_results"],
                        s["mc_result"], s["mc_uncertainties"], OUTPUTS_DIR,
                        app_commit_hash=run_history.current_app_commit_hash(REPO_ROOT),
                        include_appendix=appendix_checkbox.value,
                        report_text=s["report_text"], competition_profile_key=s["competition_profile"],
                        compliance_rows=compliance_rows,
                    )
                    chosen_name = _sanitize_filename(filename_input.value or _default_filename)
                    path = os.path.join(OUTPUTS_DIR, f"{chosen_name}.{fmt}")
                    # 2026-09-29 review item 4: generate_pdf() launches
                    # Playwright's SYNC API (Chromium) - calling that
                    # directly from a plain on_click handler runs it on
                    # NiceGUI's own event-loop thread, and Playwright's
                    # sync API refuses to run inside a thread that has a
                    # running asyncio loop ("use the Async API instead"),
                    # so the report silently never finished and the e2e
                    # test's wait for "Report written" timed out. run.
                    # io_bound (the same pattern Monte Carlo already uses)
                    # runs it on a real worker thread instead.
                    if fmt == "docx":
                        await run.io_bound(report.generate_docx, path, data)
                    else:
                        from bup_rocketpy.browser_launch import NoBrowserFoundError
                        try:
                            await run.io_bound(report.generate_pdf, path, data)
                        except NoBrowserFoundError as e:
                            report_status.set_text(str(e))
                            ui.notify(str(e), type="negative", multi_line=True, close_button=True)
                            return
                        except RuntimeError as e:
                            # 2026-10-09 review item 5: "try Playwright
                            # Chromium, then Microsoft Edge... silently.
                            # Only if both fail, show the real error
                            # message in one line." - a browser WAS found
                            # for the --print-to-pdf CLI fallback but that
                            # subprocess itself failed (report_html.py's
                            # _print_pdf raises plain RuntimeError for
                            # this, distinct from "no browser at all").
                            msg = f"PDF generation failed: {e}"
                            report_status.set_text(msg)
                            ui.notify(msg, type="negative", multi_line=True, close_button=True)
                            return
                    report_status.set_text(f"Report written: {os.path.basename(path)}")
                    report_preview_container.clear()
                    with report_preview_container:
                        ui.link(f"Download {os.path.basename(path)}", f"/outputs/{os.path.basename(path)}")
                        if fmt == "pdf":
                            # Chromium (and most browsers) render a PDF natively in
                            # an iframe - a real preview, not just a download link.
                            ui.html(f'<iframe src="/outputs/{os.path.basename(path)}" style="width:100%;height:500px;border:1px solid var(--bup-border);border-radius:var(--bup-radius-md);"></iframe>')

                with ui.row():
                    components.button("Generate PDF report", kind="primary", icon="picture_as_pdf", on_click=lambda: build_report("pdf"))
                    components.button("Generate DOCX report", kind="secondary", icon="description", on_click=lambda: build_report("docx"))

        # 2026-10-09 review item 10: "new 'Compare with OpenRocket' card" -
        # reuses rocket_page.py's own card (same function, not a
        # re-implementation) so this can never silently disagree with
        # what the Rocket page itself shows for the same run.
        if s["load_result"].ork_path:
            from bup_rocketpy.gui.pages.rocket_page import _openrocket_comparison_card
            _openrocket_comparison_card(s["load_result"].parsed_ork, s["sim_result"], s["load_result"].ork_path, simulation_name=s["load_result"].simulation_name)

        with components.card(classes="w-full mt-4"):
            ui.label("Competition profile").classes("font-bold")
            profile_select = ui.select(
                {k: p.display_name for k, p in competition_profiles.PROFILES.items()},
                value=s["competition_profile"], label="Competition",
            )
            profile_status = ui.label("").classes("text-sm").style("color: var(--bup-muted)")

            def _refresh_profile_status():
                profile = competition_profiles.get_profile(profile_select.value)
                s["competition_profile"] = profile_select.value
                profile_status.set_text(profile.rules_status)

            profile_select.on_value_change(lambda _: _refresh_profile_status())
            _refresh_profile_status()

        with components.card(classes="w-full mt-4"):
            ui.label("Competition submission .zip").classes("font-bold")
            ui.label("Per-case .py scripts + .eng + .ork + Cd curves, tested to run standalone. Naming follows the selected competition profile above (CRS 10.1.6 for LASC).").classes("text-sm").style("color: var(--bup-muted)")
            zip_status = ui.label("")
            zip_preview_container = ui.column().classes("w-full mt-2")

            def build_zip():
                profile = competition_profiles.get_profile(s["competition_profile"])
                parsed = s["load_result"].parsed_ork
                mass_est = translate.MassEstimate(s["dry_mass_kg"], s["dry_cg_m"], "UI export")
                # 2026-09-27 review item 1: the LASC submission script must
                # describe the EXACT SAME rocket Simulate/RCSM Cases already
                # ran - use its actually-used inertia, not a fresh geometric
                # re-derivation.
                i_ax, i_tr = (s["dry_i_axial_kgm2"], s["dry_i_transverse_kgm2"]) if s["dry_i_axial_kgm2"] is not None else translate.estimate_dry_inertia(parsed, mass_est)
                radius = next(t.radius for t in parsed.body_tubes if t.radius)
                zip_path = os.path.join(OUTPUTS_DIR, f"Mission{mission_id_input.value}_{profile.key}.zip")
                lasc_package.build_lasc_zip(
                    zip_path, mission_id_input.value, parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                    s["ork_path"], s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                    s["dry_mass_kg"], s["dry_cg_m"], i_ax, i_tr, radius,
                    cases=[("Ballistic", False), ("Nominal", True)],
                    eng_filename=s["eng_filename"], ork_filename=s["ork_filename"],
                    mission_id_template=profile.mission_id_template,
                )
                zip_status.set_text(f"Zip written: {os.path.basename(zip_path)}")
                zip_preview_container.clear()
                with zip_preview_container:
                    ui.link("Download submission .zip", f"/outputs/{os.path.basename(zip_path)}")
                    import zipfile
                    with zipfile.ZipFile(zip_path) as zf:
                        names = zf.namelist()
                    ui.label(f"Preview: {len(names)} file(s) inside").classes("text-xs mt-1").style("color: var(--bup-muted)")
                    for name in names:
                        ui.label(f"  - {name}").classes("text-xs font-mono")

            components.button("Build submission .zip", kind="primary", icon="folder_zip", on_click=build_zip)
