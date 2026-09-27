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
import asyncio
import os
import tempfile

from nicegui import app, run, ui

from bup_rocketpy.gui import layout, pipeline, rocket_drawing, state

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")
os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.add_static_files("/outputs", OUTPUTS_DIR)

# 2026-09-27 review item 4: the History detail page serves a saved run's
# own flight_data.csv/plots straight from its runs/<run_id>/ folder - a
# SEPARATE static route from /outputs above (a different directory
# entirely; the two must never be confused). Same BUP_ROCKETPY_RUNS_DIR
# override run_history._runs_dir() itself already honors, so tests that
# redirect the runs folder also get this route pointed at the right place.
_RUNS_DIR = os.environ.get("BUP_ROCKETPY_RUNS_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runs")
os.makedirs(_RUNS_DIR, exist_ok=True)
app.add_static_files("/runs", _RUNS_DIR)

# 2026-09-27 review item 7 (redesign): three.js, vendored offline (MIT
# license, bup_rocketpy/gui/static/vendor/three.min.js - see the LICENSE
# file next to it) - served locally so the 3D flight playback/live Monte
# Carlo views work with no internet access at all, not just "usually".
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.add_static_files("/static", _STATIC_DIR)

s = state.state


async def _save_upload(e, suffix):
    """NiceGUI 3.x's UploadEventArguments carries `.file` (a FileUpload
    with an ASYNC .save()/.read()/.text()) - NOT `.content`/`.name`. See
    CHANGELOG.md 2026-09-26 item 0 for the full story of this bug."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    await e.file.save(path)
    return path, e.file.name


@ui.page("/simulate")
def simulate_page():
    # 2026-09-27 review item 7 (Mission Control redesign): three.js,
    # vendored offline (gui/static/three.min.js, MIT license) + the
    # flight-playback viewer built on it (gui/static/playback.js) - both
    # loaded once per page visit, same pattern theme.apply() already uses
    # for CSS. Only THIS page, Home and Monte Carlo need it, so it's not
    # loaded globally in layout.py for every page.
    ui.add_head_html('<script src="/static/vendor/three.min.js"></script><script src="/static/playback.js"></script>')
    with layout.layout("Simulate", current_path="/simulate"):
        ui.label("1. Load files").classes("text-lg font-bold")
        with ui.row():
            async def on_ork_upload(e):
                s["ork_path"], name = await _save_upload(e, ".ork")
                s["ork_filename"] = name  # 2026-09-26 review item E: the REAL uploaded name - ork_path is this app's own tempfile path, previously the only thing kept
                ui.notify(f"Loaded {name}")
            ui.upload(label=".ork file", on_upload=on_ork_upload, auto_upload=True).props("accept=.ork")

            async def on_eng_upload(e):
                s["eng_path"], name = await _save_upload(e, ".eng")
                s["eng_filename"] = name
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
        # 2026-09-26 review item 2: "never hang" - a single Flight() call has
        # no internal checkpoint we can poll (unlike Monte Carlo's N
        # separate samples), so this can't be a cooperative cancel like
        # montecarlo_page.py's. What it CAN do: stop the UI from waiting on
        # it forever. Clicking Cancel (or the SIMULATION_TIMEOUT_S backstop
        # firing) detaches from the background thread and returns control to
        # the user immediately; the orphaned thread itself keeps running to
        # completion and its result is simply discarded - killing a Python
        # thread mid-ODE-integration isn't something this can do cheaply.
        sim_cancel_button = ui.button("Cancel", color="negative").props("hidden")

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
            # Loading a NEW .ork invalidates every downstream result from
            # the PREVIOUS rocket - without this, the Rocket page (and MC/
            # RCSM/Analysis) kept showing the old rocket's dry_cg_m/margin/
            # case results next to the new rocket's geometry until the user
            # re-ran Simulate, a subtler recurrence of crash (e) found via
            # the Section 4 e2e test's second-.ork screenshot.
            for key in ("sim_result", "dry_mass_kg", "dry_cg_m", "mass_source", "case_results", "compliance_rows", "mc_result", "mc_uncertainties", "weathercocking_result"):
                s[key] = None
            results_container.clear()
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
                launch_override=s["launch_override"],  # 2026-09-26 review item H (launch-day mode): None unless the Launch Day page cached+applied real weather
            )
            progress.props(remove="hidden")
            sim_cancel_button.props(remove="hidden")
            progress_label.set_text(f"Simulating (this runs in the background - the page stays responsive; auto-stops after {pipeline.SIMULATION_TIMEOUT_S}s if it doesn't finish)...")
            cancel_event = asyncio.Event()
            sim_cancel_button.on_click(cancel_event.set)
            try:
                # 2026-09-26 review crash (b): running the flight simulation
                # synchronously on NiceGUI's single asyncio event loop
                # blocks every websocket ping/pong for the whole simulation,
                # which the browser eventually reports as "Connection
                # lost". run.io_bound runs it in a thread pool instead so
                # the event loop (and the UI) stays alive throughout.
                #
                # 2026-09-26 review item 2: "never hang" - a rocket with an
                # out-of-bounds component or a negative t0 static margin
                # (this review's items 1/2) used to make Flight() spin
                # forever in tiny adaptive steps through chaotic tumbling
                # dynamics, with no feedback and no way out short of
                # restarting the app. pipeline.run_simulation now raises a
                # clear ValueError BEFORE calling Flight() for either of
                # those cases (see its own docstring) - this timeout/cancel
                # race is the backstop for every other way a simulation
                # could still take too long.
                sim_task = asyncio.ensure_future(run.io_bound(
                    pipeline.run_simulation, s["load_result"], OUTPUTS_DIR, **mass_kw,
                ))
                cancel_task = asyncio.ensure_future(cancel_event.wait())
                done, pending = await asyncio.wait(
                    [sim_task, cancel_task], timeout=pipeline.SIMULATION_TIMEOUT_S, return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                if sim_task not in done:
                    reason = "Cancelled by user." if cancel_event.is_set() else f"Simulation timed out after {pipeline.SIMULATION_TIMEOUT_S}s (likely an unstable rocket - check the static margin and component positions on the Rocket page)."
                    ui.notify(reason, type="negative", multi_line=True, timeout=0)
                    progress.props("hidden")
                    sim_cancel_button.props("hidden")
                    progress_label.set_text("")
                    return
                sim = sim_task.result()
            except ValueError as exc:
                ui.notify(str(exc), type="negative", multi_line=True, timeout=0)
                progress.props("hidden")
                sim_cancel_button.props("hidden")
                progress_label.set_text("")
                return
            sim_cancel_button.props("hidden")
            s["sim_result"] = sim
            s["dry_mass_kg"] = sim.dry_mass_kg
            s["dry_cg_m"] = sim.dry_cg_m
            s["mass_source"] = sim.mass_source
            s["dry_i_axial_kgm2"] = sim.i_axial_kgm2
            s["dry_i_transverse_kgm2"] = sim.i_transverse_kgm2
            s["inertia_source"] = sim.inertia_source
            if override_checkbox.value:
                s["dry_mass_override"] = dry_mass_input.value
                s["dry_cg_override"] = dry_cg_input.value
            try:
                from bup_rocketpy import run_history
                import dataclasses as _dc
                repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                record = run_history.save_run(
                    repo_root, sim, s["load_result"], sim.dry_mass_kg, sim.dry_cg_m,
                    ork_path=s["ork_path"], ork_filename=s["ork_filename"], eng_filename=s["eng_filename"],
                    # 2026-09-27 review item 2: save EVERY session setting
                    # that affects the flown rocket, not just the result -
                    # "Reopen this mission" (History page) needs these to
                    # reconstitute the exact same state, and it's how
                    # reefing survives past a re-upload/app restart.
                    dry_mass_override_kg=s["dry_mass_override"] if override_checkbox.value else None,
                    dry_cg_override_m=s["dry_cg_override"] if override_checkbox.value else None,
                    launch_override=_dc.asdict(s["launch_override"]) if s["launch_override"] is not None else None,
                    competition_profile=s["competition_profile"],
                    report_text=s["report_text"],
                )
                s["current_run_id"] = record.run_id  # lets the Exports page patch report_text/author into THIS run later (see run_history.update_run_text)
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
                    for label, value, unit in [
                        ("Time to apogee", f"{sim.time_to_apogee_s:.1f}", "s"),
                        ("Max dynamic pressure (Max-Q)", f"{sim.max_dynamic_pressure_pa / 1000.0:.2f}", f"kPa @ t={sim.max_dynamic_pressure_time_s:.1f}s"),
                        ("Ground-hit velocity", f"{sim.ground_hit_velocity_ms:.1f}", "m/s"),
                        ("Landing distance from pad", f"{sim.landing_distance_m:.1f}", "m"),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(f"{value} {unit}").classes("bup-kpi-value text-xl font-bold")

                if sim.recovery_rows:
                    ui.label("Recovery panel").classes("text-lg font-bold mt-4")
                    ui.label("Hand-calc: v = sqrt(2*m*g / (rho*Cd*S)), m = descent mass (dry rocket + spent motor casing), rho at deployment altitude and at ground level - an independent cross-check of the simulated descent rate, not a replacement for it.").classes("text-xs text-gray-500")
                    ui.table(
                        columns=[
                            {"name": "name", "label": "Parachute", "field": "name"},
                            {"name": "diameter", "label": "Diameter (m)", "field": "diameter"},
                            {"name": "area", "label": "Area (m2)", "field": "area"},
                            {"name": "cd", "label": "Cd", "field": "cd"},
                            {"name": "cd_s", "label": "Cd*S (m2)", "field": "cd_s"},
                            {"name": "sim", "label": "Sim descent rate (m/s)", "field": "sim"},
                            {"name": "hand_deploy", "label": "Hand-calc @ deploy alt (m/s)", "field": "hand_deploy"},
                            {"name": "diff_deploy", "label": "% diff @ deploy alt", "field": "diff_deploy"},
                            {"name": "hand_ground", "label": "Hand-calc @ ground (m/s)", "field": "hand_ground"},
                            {"name": "diff_ground", "label": "% diff @ ground", "field": "diff_ground"},
                        ],
                        rows=[{
                            "name": r.name, "diameter": f"{r.diameter_m:.2f}", "area": f"{r.area_m2:.2f}", "cd": f"{r.cd:.2f}", "cd_s": f"{r.cd_s_m2:.3f}",
                            "sim": f"{r.descent_rate_sim_ms:.2f}", "hand_deploy": f"{r.hand_terminal_velocity_at_deploy_alt_ms:.2f}", "diff_deploy": f"{r.diff_pct_at_deploy_alt:+.1f}%",
                            "hand_ground": f"{r.hand_terminal_velocity_at_ground_ms:.2f}", "diff_ground": f"{r.diff_pct_at_ground:+.1f}%",
                        } for r in sim.recovery_rows],
                    ).classes("w-full")

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

                PLAYBACK_TAB = "Flight playback (3D)"
                with ui.tabs().classes("w-full") as tabs:
                    ui.tab(PLAYBACK_TAB)
                    plot_tabs = [ui.tab(sim.plot_titles.get(name, name.replace("_", " ").title())) for name in sim.plot_paths if sim.plot_paths[name]]
                with ui.tab_panels(tabs, value=PLAYBACK_TAB).classes("w-full"):
                    with ui.tab_panel(PLAYBACK_TAB):
                        if sim.flight is not None:
                            import json
                            import uuid as _uuid
                            from bup_rocketpy.gui import flight_playback
                            playback_data = flight_playback.build_playback_data(sim.flight, sim.motor)
                            container_id = f"playback-{_uuid.uuid4().hex[:8]}"
                            ui.html(f'<div id="{container_id}" style="width:100%"></div>')
                            # Polls for window.BUP/THREE instead of a fixed
                            # delay - three.min.js is a ~600KB file loaded
                            # via <script src> in add_head_html above, and
                            # its load time shouldn't be guessed at.
                            ui.run_javascript(
                                "(function poll(){ if (window.BUP && window.BUP.playback && window.THREE) { "
                                f"BUP.playback.create('{container_id}', {json.dumps(playback_data)}); "
                                "} else { setTimeout(poll, 50); } })();"
                            )
                        else:
                            ui.label("Flight playback needs a fresh Simulate run.").classes("text-gray-500")
                    for name, path in sim.plot_paths.items():
                        if path:
                            title = sim.plot_titles.get(name, name.replace("_", " ").title())
                            with ui.tab_panel(title):
                                ui.image(path).classes("w-full max-w-3xl")
                                ui.link("Download PNG", f"/outputs/{os.path.basename(path)}")
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
    from bup_rocketpy.gui.pages import analysis_page, design_system_page, exports_page, history_page, home_page, launchday_page, montecarlo_page, rcsm_page, rocket_page, validation_page  # noqa: F401

    port = int(os.environ.get("BUP_ROCKETPY_PORT", "8080"))
    show = os.environ.get("BUP_ROCKETPY_SHOW", "1") != "0"
    # 2026-09-26 review: "Connection lost" during a Monte Carlo run.
    # nicegui's default reconnect_timeout is 3.0s - the grace period the
    # SERVER gives a dropped websocket to reconnect before it gives up on
    # that browser session entirely. A CPU-heavy background thread (a
    # rocketpy Flight() simulation doesn't release the GIL as generously
    # as I/O does) can delay the event loop's own message delivery enough,
    # on some machines, to blow through that 3s window even though the
    # simulation itself (a background task independent of any one
    # connection - it isn't cancelled by this) keeps running fine. Raised
    # to 30s so a brief stall reconnects instead of dropping the session;
    # this does NOT change how long a truly closed browser tab is kept
    # around, only how patient the server is with a flaky/delayed socket.
    ui.run(title="Beyond UP RocketPy", reload=False, show=show, port=port, reconnect_timeout=30.0)


if __name__ in ("__main__", "__mp_main__"):
    main()
