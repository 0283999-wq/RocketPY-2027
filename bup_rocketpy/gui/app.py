"""NiceGUI UI layer (CLAUDE.md Sec 1: kept separate from bup_rocketpy's
core, which has no NiceGUI import at all - see gui/pipeline.py). English
throughout (CLAUDE.md Rule 5).

This module is the "Simulate" page (CLAUDE.md Sec 6 Phase 3 / 2026-09-26
review item 2's 4-step flow: Load -> Review -> Simulate -> Results) and
also registers every other page by importing them (each page module
registers its own @ui.page route on import).

Run: python -m bup_rocketpy.gui.app (or double-click start.bat on
Windows, which sets up the venv first).
"""
import os
import tempfile

from nicegui import app, run, ui

from bup_rocketpy.gui import layout, pipeline, rocket_drawing, state

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
            override_checkbox = ui.checkbox(
                "Use manual mass/CG override (unchecked: use the .ork's own overrides + component masses - the normal path)",
                value=False,
            )
            with ui.row():
                dry_mass_input = ui.number(label="Manual dry mass override (kg)", value=s["dry_mass_override"])
                dry_cg_input = ui.number(label="Manual dry CG override (m from nose)", value=s["dry_cg_override"])
                dry_mass_input.bind_enabled_from(override_checkbox, "value")
                dry_cg_input.bind_enabled_from(override_checkbox, "value")

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

        async def do_simulate():
            if s["load_result"] is None:
                ui.notify("Load the files first.", type="warning")
                return
            if override_checkbox.value and (dry_mass_input.value is None or dry_cg_input.value is None):
                ui.notify("Manual override is checked but mass or CG is empty.", type="warning")
                return
            # 2026-09-26 review crash (c): the override fields used to be
            # passed to run_simulation UNCONDITIONALLY, and NiceGUI's
            # ui.number renders an unset (None) value as 0 - so every
            # "default path" simulation was silently being run with a
            # massless, CG-at-the-nose-tip rocket (apogee -495 m, margin
            # -900 cal). Only pass an override when the checkbox is on;
            # otherwise pipeline.run_simulation falls back to the .ork's
            # own overrides / component-based mass estimate, and raises a
            # clear ValueError (caught below) if even that isn't resolvable
            # - it must never silently simulate with a placeholder 0.
            mass_kw = dict(
                dry_mass_override_kg=dry_mass_input.value if override_checkbox.value else None,
                dry_cg_override_m=dry_cg_input.value if override_checkbox.value else None,
            )
            progress.props(remove="hidden")
            progress_label.set_text("Simulating (this runs in the background - the page stays responsive)...")
            try:
                # 2026-09-26 review crash (b): running the flight simulation
                # synchronously on NiceGUI's single asyncio event loop
                # blocks every websocket ping/pong for the whole simulation,
                # which the browser eventually reports as "Connection
                # lost". run.io_bound runs it in a thread pool instead so
                # the event loop (and the UI) stays alive throughout.
                sim = await run.io_bound(
                    pipeline.run_simulation, s["load_result"], OUTPUTS_DIR, **mass_kw,
                )
            except ValueError as exc:
                ui.notify(str(exc), type="negative", multi_line=True, timeout=0)
                progress.props("hidden")
                progress_label.set_text("")
                return
            s["sim_result"] = sim
            s["dry_mass_kg"] = sim.dry_mass_kg
            s["dry_cg_m"] = sim.dry_cg_m
            s["mass_source"] = sim.mass_source
            if override_checkbox.value:
                s["dry_mass_override"] = dry_mass_input.value
                s["dry_cg_override"] = dry_cg_input.value
            try:
                from bup_rocketpy import run_history
                repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                run_history.save_run(repo_root, sim, s["load_result"], sim.dry_mass_kg, sim.dry_cg_m)
            except Exception as exc:  # history is a convenience, never block a real result on it failing to save
                print(f"WARNING: could not save run history: {exc}")
            progress.props("hidden")
            progress_label.set_text("Done.")

            results_container.clear()
            with results_container:
                ui.label(sim.provisional_warning).classes("bup-provisional-badge px-3 py-1 rounded font-bold inline-block")
                with ui.grid(columns=4).classes("gap-4 mt-2"):
                    for label, value, unit, good in [
                        ("Apogee AGL", f"{sim.apogee_agl_m:.1f}", "m", True),
                        ("Max speed", f"{sim.max_speed_ms:.1f}", "m/s", True),
                        ("Max Mach", f"{sim.max_mach:.3f}", "", True),
                        ("Max acceleration (boost)", f"{sim.max_acceleration_ms2:.1f}", "m/s2", True),
                        ("Rail exit velocity", f"{sim.rail_exit_velocity_ms:.1f}", "m/s", sim.rail_exit_velocity_ms >= 30),
                        ("Flight time", f"{sim.flight_time_s:.1f}", "s", True),
                        ("Min static margin (rail exit-apogee)", f"{sim.min_static_margin_cal:.2f}", "cal", sim.is_stable),
                        ("Stable? (FLT 4.3.5: 1.5-4 cal)", "YES" if sim.is_stable else "NO", "", sim.is_stable),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(f"{value} {unit}").classes("bup-kpi-value text-xl font-bold" if good else "text-xl font-bold text-red-600")
                    if sim.parachute_opening_accel_ms2 is not None:
                        with ui.card():
                            ui.label("Parachute opening accel (instantaneous inflation model, upper bound)").classes("text-xs text-gray-500")
                            ui.label(f"{sim.parachute_opening_accel_ms2:.1f} m/s2 ({sim.parachute_opening_accel_ms2 / 9.80665:.1f} g)").classes("text-xl font-bold")

                if sim.deployment_events:
                    with ui.column().classes("w-full mt-2"):
                        for name, t, speed, warn in sim.deployment_events:
                            cls = "text-orange-600" if warn else "text-gray-600"
                            note = " - ABOVE the ~30 m/s clean-deployment guideline" if warn else ""
                            ui.label(f"{name} deploys at t={t:.1f}s, speed={speed:.1f} m/s{note}").classes(f"text-sm {cls}")

                if sim.sanity_checks:
                    with ui.expansion(f"Automatic sanity checks ({sum(1 for c in sim.sanity_checks if c.status != 'OK')} flagged)").classes("w-full mt-2"):
                        for c in sim.sanity_checks:
                            color = {"OK": "text-green-700", "WARN": "text-orange-600", "FAIL": "text-red-600"}[c.status]
                            ui.label(f"[{c.status}] {c.name}: {c.detail}").classes(f"text-sm {color}")

                ui.label(f"Dry mass/CG used: {sim.dry_mass_kg:.4f} kg / {sim.dry_cg_m:.4f} m from nose ({sim.mass_source})").classes("text-xs text-gray-500")

                fig = rocket_drawing.draw_side_profile(s["load_result"].parsed_ork, dry_cg_m=sim.dry_cg_m, static_margin_cal=sim.min_static_margin_cal)
                rocket_png = pipeline.fresh_image_path(OUTPUTS_DIR, "rocket_profile")
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


def main():
    # BUP_ROCKETPY_PORT/BUP_ROCKETPY_SHOW let tests/test_phase0_e2e.py launch
    # this exact module as a real subprocess on a fixed, non-default port
    # without popping open a browser window in a headless CI/container run.
    #
    # NOTE: this function must NOT be named `run` - `from nicegui import
    # run` is imported at module scope for run.io_bound() (background
    # simulations), and a module-level `def run():` here would silently
    # rebind that name, so every `await run.io_bound(...)` call in this
    # module would fail with "'function' object has no attribute
    # 'io_bound'" - found exactly this way, 2026-09-26 review.
    from bup_rocketpy.gui.pages import analysis_page, exports_page, history_page, montecarlo_page, rcsm_page, rocket_page, validation_page  # noqa: F401

    port = int(os.environ.get("BUP_ROCKETPY_PORT", "8080"))
    show = os.environ.get("BUP_ROCKETPY_SHOW", "1") != "0"
    ui.run(title="Beyond UP RocketPy", reload=False, show=show, port=port)


if __name__ in ("__main__", "__mp_main__"):
    main()
