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

from bup_rocketpy.gui import components, layout, pipeline, rocket_drawing, state

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
        components.page_header("Simulate", "Load a rocket, review what was imported, then fly it.")

        STEPS = ["Load", "Review", "Simulate", "Results"]
        stepper_container = ui.row().classes("w-full")

        def _render_stepper():
            index = 0
            if s["load_result"] is not None:
                index = 1
            if s["sim_result"] is not None:
                index = 3
            stepper_container.clear()
            with stepper_container:
                components.stepper_header(STEPS, index)

        _render_stepper()

        with components.card(classes="w-full"):
            ui.label("1. Load files").classes("font-bold")
            with ui.row().classes("w-full gap-4"):
                async def on_ork_upload(e):
                    s["ork_path"], name = await _save_upload(e, ".ork")
                    s["ork_filename"] = name  # 2026-09-26 review item E: the REAL uploaded name - ork_path is this app's own tempfile path, previously the only thing kept
                    # 2026-10-05 review: "I have a set of places (LASC,
                    # IREC, Pachuca...) - a button that shows up when I
                    # load the files" - a real .ork commonly holds several
                    # stored simulations (one per site/mission; Major
                    # Tom's has 12), each with its own launch conditions.
                    # read_ork() used to always silently use the first one
                    # - this lets the operator pick, for fast
                    # site-to-site comparison without the full Launch Day
                    # real-weather flow.
                    from bup_rocketpy import ork_reader
                    sim_names = ork_reader.list_simulation_names(s["ork_path"])
                    s["available_simulation_names"] = sim_names
                    if s["selected_simulation_name"] not in sim_names:
                        s["selected_simulation_name"] = sim_names[0] if sim_names else None
                    _render_sim_selector()
                    extra = f" - {len(sim_names)} stored simulations found, pick one below" if len(sim_names) > 1 else ""
                    ui.notify(f"Loaded {name}{extra}")
                components.dropzone(".ork file", on_ork_upload, accept=".ork")

                async def on_eng_upload(e):
                    s["eng_path"], name = await _save_upload(e, ".eng")
                    s["eng_filename"] = name
                    ui.notify(f"Loaded {name}")
                components.dropzone(".eng file", on_eng_upload, accept=".eng")

            sim_selector_container = ui.column().classes("w-full")

            def _render_sim_selector():
                sim_selector_container.clear()
                names = s["available_simulation_names"]
                if len(names) <= 1:
                    return  # the common case (one sim, or none) - nothing to choose, no extra UI clutter
                with sim_selector_container:
                    ui.label("This .ork has multiple stored simulations - pick which one supplies the launch site/conditions (and is checked against on the Rocket page):").classes("text-sm").style("color: var(--bup-muted)")

                    def _on_select(e):
                        s["selected_simulation_name"] = e.value

                    ui.select(names, value=s["selected_simulation_name"], on_change=_on_select).classes("w-full max-w-md")

            _render_sim_selector()  # re-shows the picker on a page revisit after an .ork is already loaded (e.g. navigating back from another page)

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

                # 2026-09-30 review item 2: a real .eng can simply declare
                # the wrong motor mass (found via the import-table warning
                # this same review adds) - this overrides it with a
                # MEASURED total (dry+propellant, same convention as the
                # .eng header and the .ork's own stored-sim "Motor mass"
                # column) while keeping that motor's own thrust curve and
                # propellant mass exactly as declared.
                motor_mass_checkbox = ui.checkbox(
                    "Use measured motor mass (unchecked: use the .eng header's own declared total mass)",
                    value=False,
                )
                motor_mass_input = ui.number(label="Measured motor mass, loaded - dry + propellant (kg)", value=s["motor_mass_override"])
                motor_mass_input.bind_enabled_from(motor_mass_checkbox, "value")

        with components.card(classes="w-full"):
            ui.label("2. Review import").classes("font-bold")
            simulation_name_label = ui.label("")
            drag_source_label = ui.label("")
            import_table_container = ui.column().classes("w-full")

        with components.card(classes="w-full"):
            ui.label("3. Simulate").classes("font-bold")
            progress = ui.spinner(size="lg").props("hidden")
            progress_label = ui.label("").classes("text-sm").style("color: var(--bup-muted)")
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

        with components.card(classes="w-full"):
            ui.label("4. Results").classes("font-bold")
            results_container = ui.column().classes("w-full")

        def do_load():
            if not s["ork_path"] or not s["eng_path"]:
                ui.notify("Upload both a .ork and a .eng file first.", type="warning")
                return
            progress_label.set_text("Loading files...")
            result = pipeline.load_files(
                s["ork_path"], s["eng_path"],
                power_off_drag_path=s["drag_off_path"], power_on_drag_path=s["drag_on_path"],
                outputs_dir=OUTPUTS_DIR, simulation_name=s["selected_simulation_name"],
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
            if result.simulation_name is not None:
                simulation_name_label.set_text(f"Launch conditions, drag curve and mass/CG reference from stored simulation: \"{result.simulation_name}\"")
            elif len(result.available_simulation_names) > 1:
                simulation_name_label.set_text(f"Using the first stored simulation (\"{result.available_simulation_names[0]}\") - pick a different one above and click Load files again to switch.")
            else:
                simulation_name_label.set_text("")
            drag_source_label.set_text(f"Drag curve source: {result.drag_curve_source}")
            import_table_container.clear()
            with import_table_container:
                ui.label("Imported / approximated / ignored components (nothing is half-imported silently):").classes("font-bold mt-2")
                # Grouped by status (2026-09-27 redesign: "collapsible import
                # table grouped by status") - IMPORTED first and expanded by
                # default (the common case, nothing to double check);
                # APPROXIMATED/IGNORED start collapsed since they're the ones
                # worth a closer look, but collapsed != hidden.
                by_status = {"IMPORTED": [], "APPROXIMATED": [], "IGNORED": []}
                for c, st, d in result.import_table:
                    by_status.setdefault(st, []).append((c, st, d))
                for st, rows in by_status.items():
                    if not rows:
                        continue
                    with ui.expansion(f"{st} ({len(rows)})", value=(st == "IMPORTED")).classes("w-full"):
                        ui.table(
                            columns=[{"name": "component", "label": "Component", "field": "component"},
                                     {"name": "detail", "label": "Detail", "field": "detail"}],
                            rows=[{"component": c, "detail": d} for c, _st, d in rows],
                        ).classes("w-full")
            progress_label.set_text("Loaded. Review the table, set a mass override if needed, then click Simulate.")
            _render_stepper()

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
            if motor_mass_checkbox.value and motor_mass_input.value is None:
                ui.notify("Measured motor mass is checked but empty.", type="warning")
                return
            mass_kw = dict(
                dry_mass_override_kg=dry_mass_input.value if override_checkbox.value else None,
                dry_cg_override_m=dry_cg_input.value if override_checkbox.value else None,
                launch_override=s["launch_override"],  # 2026-09-26 review item H (launch-day mode): None unless the Launch Day page cached+applied real weather
                motor_total_mass_override_kg=motor_mass_input.value if motor_mass_checkbox.value else None,
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
            if motor_mass_checkbox.value:
                s["motor_mass_override"] = motor_mass_input.value
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
            _render_stepper()

            results_container.clear()
            with results_container:
                components.status_chip(sim.validation_summary_text, sim.validation_summary_kind).classes("cursor-pointer").on("click", lambda: ui.navigate.to("/validation")).tooltip("Open the Validation page for the full breakdown")
                with ui.grid(columns=4).classes("gap-3 mt-2 w-full"):
                    kpi_i = 0
                    for label, target, unit, decimals, good in [
                        ("Apogee AGL", sim.apogee_agl_m, "m", 1, True),
                        ("Max speed", sim.max_speed_ms, "m/s", 1, True),
                        ("Max Mach", sim.max_mach, "", 3, True),
                        ("Max acceleration (boost)", sim.max_acceleration_ms2, "m/s2", 1, True),
                        ("Rail exit velocity", sim.rail_exit_velocity_ms, "m/s", 1, sim.rail_exit_velocity_ms >= 30),
                        ("Flight time", sim.flight_time_s, "s", 1, True),
                        ("Min static margin (rail exit-apogee)", sim.min_static_margin_cal, "cal", 2, sim.is_stable),
                    ]:
                        components.kpi_card(label, None, unit, status="good" if good else "bad", countup_target=target, decimals=decimals, stagger_index=kpi_i)
                        kpi_i += 1
                    components.kpi_card("Stable? (FLT 4.3.5: 1.5-4 cal)", "YES" if sim.is_stable else "NO", "", status="good" if sim.is_stable else "bad", stagger_index=kpi_i)
                    kpi_i += 1
                    if sim.parachute_opening_accel_ms2 is not None:
                        components.kpi_card(
                            "Parachute opening accel (instantaneous inflation, upper bound)", None, "m/s2",
                            caption=f"{sim.parachute_opening_accel_ms2 / 9.80665:.1f} g", status="neutral",
                            countup_target=sim.parachute_opening_accel_ms2, decimals=1, stagger_index=kpi_i,
                        )
                        kpi_i += 1
                    for label, target, unit, decimals, caption in [
                        ("Time to apogee", sim.time_to_apogee_s, "s", 1, None),
                        ("Max dynamic pressure (Max-Q)", sim.max_dynamic_pressure_pa / 1000.0, "kPa", 2, f"@ t={sim.max_dynamic_pressure_time_s:.1f}s"),
                        ("Ground-hit velocity", sim.ground_hit_velocity_ms, "m/s", 1, None),
                        ("Landing distance from pad", sim.landing_distance_m, "m", 1, None),
                    ]:
                        components.kpi_card(label, None, unit, caption=caption, status="neutral", countup_target=target, decimals=decimals, stagger_index=kpi_i)
                        kpi_i += 1

                # 2026-09-30 review item 3: a full mass breakdown, visible
                # everywhere a rocket's numbers are shown (Rocket page,
                # here, and the report) - not just the dry/liftoff figures
                # that happened to already exist somewhere on each page.
                ui.label("Mass breakdown").classes("text-lg font-bold mt-4")
                with ui.grid(columns=3).classes("gap-2 w-full max-w-2xl"):
                    for label, value in [
                        ("Dry rocket (no motor)", sim.dry_mass_kg),
                        ("Motor, loaded (dry + propellant)", sim.motor_loaded_kg),
                        ("Motor propellant", sim.motor_propellant_kg),
                        ("Motor dry (casing)", sim.motor_dry_kg),
                        ("Liftoff mass", sim.liftoff_mass_kg),
                        ("Descent mass (dry rocket + spent motor casing)", sim.descent_mass_kg),
                    ]:
                        with ui.column().classes("gap-0"):
                            ui.label(label).classes("text-xs").style("color: var(--bup-muted)")
                            ui.label(f"{value:.3f} kg" if value is not None else "n/a").classes("text-sm font-bold")
                ui.label(f"Motor mass source: {sim.motor_mass_source}").classes("text-xs mt-1").style("color: var(--bup-muted)")

                if sim.recovery_rows:
                    ui.label("Recovery panel").classes("text-lg font-bold mt-4")
                    # 2026-09-30 review item 6: the descent mass the hand-
                    # calc below actually uses, shown as a real number next
                    # to it - not just named in the caption's own prose.
                    ui.label(f"Descent mass (dry rocket + spent motor casing): {sim.descent_mass_kg:.3f} kg (= {sim.dry_mass_kg:.3f} kg dry rocket + {sim.motor_dry_kg:.3f} kg spent motor casing)").classes("text-sm font-bold")
                    ui.label("Hand-calc: v = sqrt(2*m*g / (rho*Cd*S)), m = descent mass above, rho at deployment altitude and at ground level - an independent cross-check of the simulated descent rate, not a replacement for it.").classes("text-xs text-gray-500")
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

                from bup_rocketpy.translate import drawing_stability_labels
                static_margin_mach0_cal, stability_mach03_cal = drawing_stability_labels(sim.flight)
                fig = rocket_drawing.draw_side_profile(
                    s["load_result"].parsed_ork, dry_cg_m=sim.dry_cg_m, motor_length_m=s["load_result"].parsed_eng.header.length_mm / 1000.0,
                    static_margin_mach0_cal=static_margin_mach0_cal, stability_mach03_cal=stability_mach03_cal,
                )
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
            components.finish_motion()

        with ui.row():
            components.button("Load files", kind="secondary", icon="folder_open", on_click=do_load)
            components.button("Simulate", kind="primary", icon="rocket_launch", on_click=do_simulate)


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


# 2026-09-30 review item 1: NOT "__mp_main__" (nicegui's own quickstart
# template's default guard, kept here since the original commit). This
# app's own Monte Carlo/drag-comparison code (bup_rocketpy/monte_carlo.py)
# starts its own ProcessPoolExecutor pool DIRECTLY (not through nicegui's
# run.cpu_bound), and start.bat launches this module with `python -m`, so
# on Windows (spawn is its only multiprocessing start method) EVERY worker
# process re-imports this exact module with __name__ forced to
# "__mp_main__" as part of Python's own spawn bootstrap - unavoidable,
# not a bug. Matching that value here would re-run main() (importing
# every GUI/report/rocketpy page module, then calling ui.run()) inside
# EVERY Monte Carlo worker, on top of the actual simulation work it's
# there to do. nicegui's own ui.run() already no-ops when
# multiprocessing.current_process().name != "MainProcess" (see
# nicegui/ui_run.py), so this was never needed to stop a second web
# server from starting - only "__main__" (the literal `python -m
# bup_rocketpy.gui.app` entry point) should ever call main().
if __name__ == "__main__":
    main()
