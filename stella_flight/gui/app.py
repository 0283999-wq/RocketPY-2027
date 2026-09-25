"""NiceGUI UI layer (CLAUDE.md Sec 1: kept separate from stella_flight's
core, which has no NiceGUI import at all - see gui/pipeline.py). English
throughout (CLAUDE.md Rule 5).

This module is the "Simulate" page (CLAUDE.md Sec 6 Phase 3 / 2026-09-26
review item 2's 4-step flow: Load -> Review -> Simulate -> Results) and
also registers every other page by importing them (each page module
registers its own @ui.page route on import).

Run: python -m stella_flight.gui.app (or double-click start.bat on
Windows, which sets up the venv first).
"""
import os
import tempfile

from nicegui import app, ui

from stella_flight.gui import layout, pipeline, rocket_drawing, state

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")
os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.add_static_files("/outputs", OUTPUTS_DIR)

s = state.state


async def _save_upload(e, suffix):
    """NiceGUI 3.x's UploadEventArguments carries `.file` (a FileUpload
    with an ASYNC .save()/.read()/.text()) - NOT `.content`/`.name`. See
    CHANGELOG.md 2026-09-26 item 0 for the full story of this bug."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    await e.file.save(path)
    return path, e.file.name


@ui.page("/")
def simulate_page():
    with layout.layout("Simulate", current_path="/"):
        ui.label("1. Load files").classes("text-lg font-bold")
        with ui.row():
            async def on_ork_upload(e):
                s["ork_path"], name = await _save_upload(e, ".ork")
                ui.notify(f"Loaded {name}")
            ui.upload(label=".ork file", on_upload=on_ork_upload, auto_upload=True).props("accept=.ork")

            async def on_eng_upload(e):
                s["eng_path"], name = await _save_upload(e, ".eng")
                ui.notify(f"Loaded {name}")
            ui.upload(label=".eng file", on_upload=on_eng_upload, auto_upload=True).props("accept=.eng")

        with ui.expansion("Advanced: manual Cd CSVs and mass/CG override").classes("w-full"):
            with ui.row():
                async def on_drag_off_upload(e):
                    s["drag_off_path"], name = await _save_upload(e, ".csv")
                    ui.notify(f"Loaded {name} (power-off drag)")
                ui.upload(label="power_off_drag.csv (optional)", on_upload=on_drag_off_upload, auto_upload=True).props("accept=.csv")

                async def on_drag_on_upload(e):
                    s["drag_on_path"], name = await _save_upload(e, ".csv")
                    ui.notify(f"Loaded {name} (power-on drag)")
                ui.upload(label="power_on_drag.csv (optional)", on_upload=on_drag_on_upload, auto_upload=True).props("accept=.csv")
            with ui.row():
                dry_mass_input = ui.number(label="Manual dry mass override (kg)", value=s["dry_mass_override"])
                dry_cg_input = ui.number(label="Manual dry CG override (m from nose)", value=s["dry_cg_override"])

        ui.separator()
        ui.label("2. Review import").classes("text-lg font-bold")
        drag_source_label = ui.label("")
        import_table_container = ui.column().classes("w-full")

        ui.separator()
        ui.label("3. Simulate").classes("text-lg font-bold")
        progress = ui.spinner(size="lg").props("hidden")
        progress_label = ui.label("").classes("text-sm text-gray-500")

        ui.separator()
        ui.label("4. Results").classes("text-lg font-bold")
        results_container = ui.column().classes("w-full")

        def do_load():
            if not s["ork_path"] or not s["eng_path"]:
                ui.notify("Upload both a .ork and a .eng file first.", type="warning")
                return
            progress_label.set_text("Loading files...")
            result = pipeline.load_files(
                s["ork_path"], s["eng_path"],
                power_off_drag_path=s["drag_off_path"], power_on_drag_path=s["drag_on_path"],
                outputs_dir=OUTPUTS_DIR,
            )
            s["load_result"] = result
            s["vehicle_name"] = result.parsed_ork.name
            drag_source_label.set_text(f"Drag curve source: {result.drag_curve_source}")
            import_table_container.clear()
            with import_table_container:
                ui.label("Imported / approximated / ignored components (nothing is half-imported silently):").classes("font-bold mt-2")
                ui.table(
                    columns=[{"name": "component", "label": "Component", "field": "component"},
                             {"name": "status", "label": "Status", "field": "status"},
                             {"name": "detail", "label": "Detail", "field": "detail"}],
                    rows=[{"component": c, "status": st, "detail": d} for c, st, d in result.import_table],
                ).classes("w-full")
            progress_label.set_text("Loaded. Review the table, set a mass override if needed, then click Simulate.")

        def do_simulate():
            if s["load_result"] is None:
                ui.notify("Load the files first.", type="warning")
                return
            progress.props(remove="hidden")
            progress_label.set_text("Simulating...")
            try:
                sim = pipeline.run_simulation(
                    s["load_result"], OUTPUTS_DIR,
                    dry_mass_override_kg=dry_mass_input.value, dry_cg_override_m=dry_cg_input.value,
                )
                s["dry_mass_override"] = dry_mass_input.value
                s["dry_cg_override"] = dry_cg_input.value
            except ValueError as exc:
                ui.notify(str(exc), type="negative", multi_line=True, timeout=0)
                progress.props("hidden")
                progress_label.set_text("")
                return
            s["sim_result"] = sim
            try:
                from stella_flight import run_history
                repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                run_history.save_run(repo_root, sim, s["load_result"], dry_mass_input.value, dry_cg_input.value)
            except Exception as exc:  # history is a convenience, never block a real result on it failing to save
                print(f"WARNING: could not save run history: {exc}")
            progress.props("hidden")
            progress_label.set_text("Done.")

            results_container.clear()
            with results_container:
                ui.label(sim.provisional_warning).classes("stella-provisional-badge px-3 py-1 rounded font-bold inline-block")
                with ui.grid(columns=4).classes("gap-4 mt-2"):
                    for label, value, unit, good in [
                        ("Apogee AGL", f"{sim.apogee_agl_m:.1f}", "m", True),
                        ("Max speed", f"{sim.max_speed_ms:.1f}", "m/s", True),
                        ("Max Mach", f"{sim.max_mach:.3f}", "", True),
                        ("Max acceleration", f"{sim.max_acceleration_ms2:.1f}", "m/s2", True),
                        ("Rail exit velocity", f"{sim.rail_exit_velocity_ms:.1f}", "m/s", sim.rail_exit_velocity_ms >= 30),
                        ("Flight time", f"{sim.flight_time_s:.1f}", "s", True),
                        ("Min static margin", f"{sim.min_static_margin_cal:.2f}", "cal", 1.5 <= sim.min_static_margin_cal),
                        ("Stable?", "YES" if sim.is_stable else "NO - UNSTABLE", "", sim.is_stable),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(f"{value} {unit}").classes("stella-kpi-value text-xl font-bold" if good else "text-xl font-bold text-red-600")

                if s["load_result"] is not None and s["dry_cg_override"] is not None:
                    fig = rocket_drawing.draw_side_profile(s["load_result"].parsed_ork, dry_cg_m=s["dry_cg_override"], static_margin_cal=sim.min_static_margin_cal)
                    rocket_png = os.path.join(OUTPUTS_DIR, "rocket_profile.png")
                    fig.savefig(rocket_png)
                    ui.image(rocket_png).classes("w-full max-w-3xl")

                with ui.tabs().classes("w-full") as tabs:
                    plot_tabs = [ui.tab(name.replace("_", " ").title()) for name in sim.plot_paths if sim.plot_paths[name]]
                with ui.tab_panels(tabs).classes("w-full"):
                    for name, path in sim.plot_paths.items():
                        if path:
                            with ui.tab_panel(name.replace("_", " ").title()):
                                ui.image(path).classes("w-full max-w-3xl")
                if sim.csv_path:
                    ui.link("Download flight data CSV", f"/outputs/{os.path.basename(sim.csv_path)}")

        with ui.row():
            ui.button("Load files", on_click=do_load)
            ui.button("Simulate", on_click=do_simulate)


def run():
    # STELLA_FLIGHT_PORT/STELLA_FLIGHT_SHOW let tests/test_phase0_e2e.py launch
    # this exact module as a real subprocess on a fixed, non-default port
    # without popping open a browser window in a headless CI/container run.
    from stella_flight.gui.pages import analysis_page, exports_page, history_page, montecarlo_page, rcsm_page, rocket_page, validation_page  # noqa: F401

    port = int(os.environ.get("STELLA_FLIGHT_PORT", "8080"))
    show = os.environ.get("STELLA_FLIGHT_SHOW", "1") != "0"
    ui.run(title="stella-flight", reload=False, show=show, port=port)


if __name__ in ("__main__", "__mp_main__"):
    run()
