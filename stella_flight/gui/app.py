"""NiceGUI UI layer (CLAUDE.md Sec 1: kept separate from stella_flight's
core, which has no NiceGUI import at all - see gui/pipeline.py). English
throughout (CLAUDE.md Rule 5).

Run: python -m stella_flight.gui.app  (or double-click start.bat on
Windows, which sets up the venv first).
"""
import os
import tempfile

from nicegui import app, ui

from stella_flight.gui import pipeline

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")

state = {"load_result": None, "sim_result": None, "ork_path": None, "eng_path": None, "drag_off_path": None, "drag_on_path": None}


async def _save_upload(e, suffix):
    """NiceGUI 3.x's UploadEventArguments carries `.file` (a FileUpload
    with an ASYNC .save()/.read()/.text()) - NOT `.content`/`.name`, which
    was an older NiceGUI API and silently did nothing here (AttributeError
    inside a sync callback NiceGUI swallowed, so the upload widget still
    showed 100% while state[...] was never set - this is bug #0 from the
    2026-09-26 overnight review). The readers in stella_flight all take
    file paths (so they work identically from the CLI and the UI), so
    every upload gets saved straight to a temp file via FileUpload.save()."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    await e.file.save(path)
    return path, e.file.name


@ui.page("/")
def main_page():
    ui.label("stella-flight").classes("text-2xl font-bold")
    ui.label("Flight simulation and analysis for Stella Ignis - drag in your .ork + .eng, click Simulate.").classes("text-sm text-gray-500")

    with ui.row():
        async def on_ork_upload(e):
            state["ork_path"], name = await _save_upload(e, ".ork")
            ui.notify(f"Loaded {name}")
        ui.upload(label=".ork file", on_upload=on_ork_upload, auto_upload=True).props("accept=.ork")

        async def on_eng_upload(e):
            state["eng_path"], name = await _save_upload(e, ".eng")
            ui.notify(f"Loaded {name}")
        ui.upload(label=".eng file", on_upload=on_eng_upload, auto_upload=True).props("accept=.eng")

        async def on_drag_off_upload(e):
            state["drag_off_path"], name = await _save_upload(e, ".csv")
            ui.notify(f"Loaded {name} (power-off drag)")
        ui.upload(label="power_off_drag.csv (optional)", on_upload=on_drag_off_upload, auto_upload=True).props("accept=.csv")

        async def on_drag_on_upload(e):
            state["drag_on_path"], name = await _save_upload(e, ".csv")
            ui.notify(f"Loaded {name} (power-on drag)")
        ui.upload(label="power_on_drag.csv (optional)", on_upload=on_drag_on_upload, auto_upload=True).props("accept=.csv")

    drag_source_label = ui.label("")
    import_table_container = ui.column()
    mass_override_row = ui.row()
    dry_mass_input = ui.number(label="Manual dry mass override (kg)", value=None)
    dry_cg_input = ui.number(label="Manual dry CG override (m from nose)", value=None)
    progress = ui.spinner(size="lg").props("hidden")
    results_container = ui.column()

    def do_load():
        if not state["ork_path"] or not state["eng_path"]:
            ui.notify("Upload both a .ork and a .eng file first.", type="warning")
            return
        result = pipeline.load_files(
            state["ork_path"], state["eng_path"],
            power_off_drag_path=state["drag_off_path"], power_on_drag_path=state["drag_on_path"],
            outputs_dir=OUTPUTS_DIR,
        )
        state["load_result"] = result
        drag_source_label.set_text(f"Drag curve source: {result.drag_curve_source}")
        import_table_container.clear()
        with import_table_container:
            ui.label("Imported / approximated / ignored components (nothing is half-imported silently):").classes("font-bold mt-2")
            ui.table(
                columns=[{"name": "component", "label": "Component", "field": "component"},
                         {"name": "status", "label": "Status", "field": "status"},
                         {"name": "detail", "label": "Detail", "field": "detail"}],
                rows=[{"component": c, "status": s, "detail": d} for c, s, d in result.import_table],
            ).classes("w-full")
        ui.notify("Loaded. Review the table, set a mass override if needed, then click Simulate.")

    def do_simulate():
        if state["load_result"] is None:
            ui.notify("Load the files first.", type="warning")
            return
        progress.props(remove="hidden")
        try:
            sim = pipeline.run_simulation(
                state["load_result"], OUTPUTS_DIR,
                dry_mass_override_kg=dry_mass_input.value, dry_cg_override_m=dry_cg_input.value,
            )
        except ValueError as exc:
            ui.notify(str(exc), type="negative", multi_line=True, timeout=0)
            progress.props("hidden")
            return
        state["sim_result"] = sim
        progress.props("hidden")

        results_container.clear()
        with results_container:
            ui.label(sim.provisional_warning).classes("text-red-600 font-bold")
            with ui.grid(columns=4).classes("gap-4"):
                for label, value, unit in [
                    ("Apogee AGL", f"{sim.apogee_agl_m:.1f}", "m"),
                    ("Max speed", f"{sim.max_speed_ms:.1f}", "m/s"),
                    ("Max Mach", f"{sim.max_mach:.3f}", ""),
                    ("Max acceleration", f"{sim.max_acceleration_ms2:.1f}", "m/s2"),
                    ("Rail exit velocity", f"{sim.rail_exit_velocity_ms:.1f}", "m/s"),
                    ("Flight time", f"{sim.flight_time_s:.1f}", "s"),
                    ("Min static margin", f"{sim.min_static_margin_cal:.2f}", "cal"),
                    ("Stable?", "YES" if sim.is_stable else "NO - UNSTABLE", ""),
                ]:
                    with ui.card():
                        ui.label(label).classes("text-xs text-gray-500")
                        ui.label(f"{value} {unit}").classes("text-xl font-bold")
            for name, path in sim.plot_paths.items():
                if path:
                    ui.image(path).classes("w-full max-w-2xl")
            if sim.csv_path:
                ui.link("Download flight data CSV", f"/outputs/{os.path.basename(sim.csv_path)}")

    with ui.row():
        ui.button("Load files", on_click=do_load)
        ui.button("Simulate", on_click=do_simulate)


os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.add_static_files("/outputs", OUTPUTS_DIR)


def run():
    # STELLA_FLIGHT_PORT/STELLA_FLIGHT_SHOW let tests/test_phase0_e2e.py launch
    # this exact module as a real subprocess on a fixed, non-default port
    # without popping open a browser window in a headless CI/container run.
    port = int(os.environ.get("STELLA_FLIGHT_PORT", "8080"))
    show = os.environ.get("STELLA_FLIGHT_SHOW", "1") != "0"
    ui.run(title="stella-flight", reload=False, show=show, port=port)


if __name__ in ("__main__", "__mp_main__"):
    run()
