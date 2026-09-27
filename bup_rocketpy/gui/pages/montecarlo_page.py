"""The "Monte Carlo" page: uncertainties table (editable, sourced),
run/cancel, apogee histogram, landing ellipses.
"""
import json
import os
import threading
import uuid

import matplotlib
import matplotlib.pyplot as plt
from nicegui import run, ui

from bup_rocketpy.gui import components, layout, pipeline, plot_theme, state
from bup_rocketpy import monte_carlo

matplotlib.use("Agg")
s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/montecarlo")
def montecarlo_page():
    # 2026-09-27 review item 7: three.js + the live-MC viewer, vendored
    # offline - see gui/app.py's simulate_page for the same pattern.
    ui.add_head_html('<script src="/static/vendor/three.min.js"></script><script src="/static/playback.js"></script>')
    with layout.layout("Monte Carlo", current_path="/montecarlo"):
        components.page_header("Monte Carlo", "Dispersion analysis: uncertainties in, apogee distribution and landing footprint out.")
        if s["load_result"] is None or s["sim_result"] is None:
            components.empty_state("scatter_plot", "Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).", action_label="Go to Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            return

        if s["mc_uncertainties"] is None:
            parsed = s["load_result"].parsed_ork
            s["mc_uncertainties"] = monte_carlo.default_uncertainties(s["dry_mass_kg"], 1871.3, parsed.launch.wind_average_ms)

        with ui.row().classes("gap-4 w-full items-start flex-wrap"):
            with components.card(classes="flex-1 min-w-[380px]"):
                ui.label("Settings").classes("font-bold")
                ui.label("Uncertainties (editable; every one shows its source)").classes("text-sm font-medium mt-2")
                rows_container = ui.column().classes("w-full")
                with rows_container:
                    for u in s["mc_uncertainties"]:
                        with ui.row().classes("items-center gap-2"):
                            u_enabled = ui.checkbox(value=u.enabled)
                            u_enabled.on_value_change(lambda e, u=u: setattr(u, "enabled", e.value))
                            ui.label(u.name).classes("w-48")
                            std_input = ui.number(label="std dev", value=u.std_dev).classes("w-32")
                            std_input.on_value_change(lambda e, u=u: setattr(u, "std_dev", e.value))
                            ui.label(u.source).classes("text-xs flex-1").style("color: var(--bup-muted)")

                n_input = ui.number(label="N simulations", value=200).classes("mt-2")
                n_warning_label = ui.label("").classes("text-xs").style("color: var(--bup-warning)")

                def _check_n_warning():
                    if n_input.value and n_input.value < 100:
                        n_warning_label.set_text("N < 100: the apogee mean/90% interval and landing ellipse won't be statistically meaningful. Default is 200.")
                    else:
                        n_warning_label.set_text("")

                n_input.on_value_change(lambda _: _check_n_warning())
                _check_n_warning()

                parsed_for_rail = s["load_result"].parsed_ork
                with ui.row().classes("items-center gap-2 mt-2"):
                    rail_inclination_input = ui.number(label="Rail inclination (deg from horizontal)", value=parsed_for_rail.launch.inclination_deg if parsed_for_rail.launch else None).classes("w-56")
                    rail_heading_input = ui.number(label="Rail heading (deg)", value=parsed_for_rail.launch.rail_direction_deg if parsed_for_rail.launch else None).classes("w-40")
                ui.label("Defaults to the .ork's saved simulation; edit to match the rail setup you actually plan to use on launch day (e.g. pointed into the wind) before running.").classes("text-xs").style("color: var(--bup-muted)")

                progress_bar = ui.linear_progress(value=0).props("hidden").classes("mt-2")
                progress_label = ui.label("").classes("text-sm").style("color: var(--bup-muted)")
                with ui.row().classes("gap-2 mt-1"):
                    run_button = components.button("Run Monte Carlo", kind="primary", icon="play_arrow")
                    cancel_button = components.button("Cancel", kind="danger", icon="stop").props("hidden")

            with components.card(classes="flex-1 min-w-[380px]"):
                ui.label("Live 3D view (fills in as each trajectory completes)").classes("font-bold")
                live_mc_container = ui.column().classes("w-full")

        results_container = ui.column().classes("w-full mt-4")

        def render_results(result):
            # Split out so a finished run's result (s["mc_result"]) can be
            # re-shown on a fresh page load too, not just right after
            # run_mc() itself finishes. A run started here keeps going in
            # a background task even if you navigate to another page and
            # back (nicegui's click-handler tasks aren't tied to one
            # page's connection) - but before this fix, coming back to
            # /montecarlo just showed an empty page, as if nothing had
            # run, even though the result was sitting in s["mc_result"]
            # the whole time.
            results_container.clear()
            with results_container:
                with ui.grid(columns=3).classes("gap-3 w-full"):
                    components.kpi_card("Apogee mean", None, "m", status="neutral", countup_target=result.apogee_mean, decimals=1, stagger_index=0)
                    components.kpi_card("90% interval low", None, "m", status="neutral", countup_target=result.apogee_p05, decimals=1, stagger_index=1)
                    components.kpi_card("90% interval high", None, "m", status="neutral", countup_target=result.apogee_p95, decimals=1, stagger_index=2)

                fig, ax = plt.subplots(figsize=(6, 3.5))
                ax.hist(result.apogee_samples, bins=min(20, max(5, result.n_completed // 3)), color="#8A1538", alpha=0.75)
                ax.axvline(result.apogee_mean, color="#B79357", linestyle="--", label="mean")
                ax.set_xlabel("Apogee AGL (m)")
                ax.set_ylabel("count")
                ax.legend()
                plot_theme.apply(ax, fig)
                hist_path = pipeline.fresh_image_path(OUTPUTS_DIR, "mc_histogram")
                fig.tight_layout()
                plot_theme.savefig(fig, hist_path)
                plt.close(fig)
                with components.card(classes="w-full max-w-xl mt-2"):
                    ui.image(hist_path).classes("w-full")

                ellipses = monte_carlo.landing_ellipses(result)
                if ellipses:
                    fig2, ax2 = plt.subplots(figsize=(6, 6))
                    for n_std, color in [(3, "#e0c9a6"), (2, "#c9a876"), (1, "#8A1538")]:
                        e = ellipses[n_std]
                        from matplotlib.patches import Ellipse
                        ax2.add_patch(Ellipse((e["center_x"], e["center_y"]), e["width"], e["height"], angle=e["angle_deg"], facecolor=color, alpha=0.4, edgecolor=color, label=f"{n_std}-sigma"))
                    ax2.scatter(result.impact_x_samples, result.impact_y_samples, s=8, color=plot_theme.AXIS, zorder=5)
                    ax2.set_xlabel("X (m, downrange)")
                    ax2.set_ylabel("Y (m, crossrange)")
                    ax2.set_aspect("equal")
                    ax2.legend()
                    ax2.set_title("Landing ellipse (single recovery event)")
                    plot_theme.apply(ax2, fig2)
                    ellipse_path = pipeline.fresh_image_path(OUTPUTS_DIR, "mc_ellipse")
                    fig2.tight_layout()
                    plot_theme.savefig(fig2, ellipse_path)
                    plt.close(fig2)
                    with components.card(classes="w-full max-w-xl mt-2"):
                        ui.image(ellipse_path).classes("w-full")

                    # 2026-09-25 review Section 7: interactive Leaflet map
                    # overlaying the same ellipses/samples on real site
                    # imagery, alongside the static plot above (which stays
                    # for a quick PNG export). Requires internet for the
                    # OpenStreetMap tiles - the map itself, markers and
                    # polygons render regardless of whether tiles load.
                    # ui.leaflet() already adds its own default OSM tile
                    # layer internally - an extra explicit tile_layer() call
                    # here only doubles tile requests for no benefit (and,
                    # with no internet in this sandbox, doubles the pile of
                    # failed/pending fetches), so it's deliberately omitted.
                    # Landing samples are capped at 200 circle markers - a
                    # a real N=200+ run would otherwise add one DOM layer
                    # per sample, which is unnecessary map clutter and a
                    # slow client-side render for no real benefit over the
                    # static scatter plot above.
                    launch = s["load_result"].parsed_ork.launch
                    if launch is not None:
                        from bup_rocketpy.geo import ellipse_to_latlon_polygon, local_xy_to_latlon
                        origin_lat, origin_lon = launch.latitude, launch.longitude
                        ui.label("Landing map").classes("text-lg font-bold mt-2")
                        leaflet = ui.leaflet(center=(origin_lat, origin_lon), zoom=15).classes("w-full rounded-lg overflow-hidden").style("height: 400px")
                        leaflet.marker(latlng=(origin_lat, origin_lon))
                        # 2026-09-26 review item E: distance rings give a
                        # quick-glance sense of scale (how far is the
                        # ellipse from the road/property line etc.)
                        # without needing to zoom/measure - plain circles
                        # centered on the pad, radius in meters (leaflet's
                        # native circle() takes a radius in meters, unlike
                        # the ellipse polygons above which are computed in
                        # local flat-earth XY and only look like ellipses
                        # over this small an area).
                        for radius_m, label in [(1000, "1 km"), (2000, "2 km"), (5000, "5 km")]:
                            leaflet.generic_layer(name="circle", args=[[origin_lat, origin_lon], {"radius": radius_m, "color": "#666666", "fill": False, "weight": 1, "dashArray": "4,4"}])
                        for n_std, color in [(3, "#e0c9a6"), (2, "#c9a876"), (1, "#8A1538")]:
                            e = ellipses[n_std]
                            poly = ellipse_to_latlon_polygon(e["center_x"], e["center_y"], e["width"], e["height"], e["angle_deg"], origin_lat, origin_lon)
                            leaflet.generic_layer(name="polygon", args=[poly, {"color": color, "fillColor": color, "fillOpacity": 0.25}])
                        max_markers = 200
                        step = max(1, len(result.impact_x_samples) // max_markers)
                        for x, y in list(zip(result.impact_x_samples, result.impact_y_samples))[::step]:
                            lat, lon = local_xy_to_latlon(x, y, origin_lat, origin_lon)
                            leaflet.generic_layer(name="circleMarker", args=[[lat, lon], {"radius": 3, "color": "#211A16"}])
                    else:
                        ui.label("No launch site lat/lon in the .ork - can't place the landing map.").classes("text-gray-500 text-sm")
                else:
                    ui.label("No landing ellipse: this case terminates at apogee (Ballistic) or too few samples completed.").classes("text-gray-500")
            components.finish_motion()

        if s["mc_result"] is not None:
            progress_label.set_text(f"Done: {s['mc_result'].n_completed} completed, {s['mc_result'].n_excluded} excluded.")
            render_results(s["mc_result"])

        # 2026-09-26 review crash (b) + item 7: N stochastic Flight sims
        # run in a background thread (run.io_bound) so the event loop -
        # and the "Connection lost" websocket heartbeat - stays alive.
        # progress_cb/cancel_check run INSIDE that thread, so they only
        # touch a plain dict (GIL-safe for simple read/write); a ui.timer
        # on the main event loop polls it and is the only thing that
        # actually touches NiceGUI elements, which is not safe to do
        # directly from a worker thread.
        mc_progress = {"text": "", "done": False}
        cancel_flag = threading.Event()
        # 2026-09-27 review item 7: on_sample_complete (called from the
        # SAME background thread as progress_cb) appends to this plain
        # list - GIL-safe list.append/pop, same reasoning as mc_progress
        # above. poll_progress (on the event loop) drains it and is the
        # only thing that actually calls ui.run_javascript.
        mc_live_queue = []
        live_mc_state = {"container_id": None}

        def poll_progress():
            progress_label.set_text(mc_progress["text"])
            container_id = live_mc_state["container_id"]
            while mc_live_queue:
                trajectory, x_impact, y_impact = mc_live_queue.pop(0)
                if container_id:
                    ui.run_javascript(
                        f"(function(){{ var v = window.BUP && window.BUP._mcViewers && window.BUP._mcViewers['{container_id}']; "
                        f"if (!v) return; v.addSample({json.dumps(trajectory)}); "
                        f"if ({json.dumps(x_impact)} !== null) v.addLanding({json.dumps(x_impact)}, {json.dumps(y_impact)}); }})();"
                    )
            if mc_progress["done"]:
                poll_timer.deactivate()

        poll_timer = ui.timer(0.4, poll_progress, active=False)

        def _get_inertia():
            # 2026-09-27 review item 1: use the SAME inertia Simulate itself
            # used for this rocket, not a fresh geometric re-derivation that
            # could silently disagree with it.
            if s["dry_i_axial_kgm2"] is not None:
                return s["dry_i_axial_kgm2"], s["dry_i_transverse_kgm2"]
            from bup_rocketpy import translate
            parsed = s["load_result"].parsed_ork
            mass_est = translate.MassEstimate(s["dry_mass_kg"], s["dry_cg_m"], "UI")
            return translate.estimate_dry_inertia(parsed, mass_est)

        async def run_mc():
            parsed = s["load_result"].parsed_ork
            i_ax, i_tr = _get_inertia()
            radius = next(t.radius for t in parsed.body_tubes if t.radius)
            n = int(n_input.value)

            def progress_cb(i, total):
                mc_progress["text"] = f"Running {i}/{total}..."

            def on_sample_complete(trajectory, x_impact, y_impact):
                mc_live_queue.append((trajectory, x_impact, y_impact))

            cancel_flag.clear()
            mc_progress["done"] = False
            mc_live_queue.clear()
            progress_bar.props(remove="hidden")
            run_button.props("hidden")
            cancel_button.props(remove="hidden")

            container_id = f"livemc-{uuid.uuid4().hex[:8]}"
            live_mc_state["container_id"] = container_id
            live_mc_container.clear()
            with live_mc_container:
                ui.html(f'<div id="{container_id}" style="width:100%"></div>')
            ui.run_javascript(
                "(function poll(){ if (window.BUP && window.BUP.livemc && window.THREE) { "
                f"BUP.livemc.create('{container_id}'); }} else {{ setTimeout(poll, 50); }} }})();"
            )
            poll_timer.activate()

            try:
                result = await run.io_bound(
                    monte_carlo.run_monte_carlo,
                    parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                    s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                    s["dry_mass_kg"], s["dry_cg_m"], i_ax, i_tr, radius,
                    s["mc_uncertainties"], n, os.path.join(OUTPUTS_DIR, "monte_carlo"),
                    include_recovery=True, progress_callback=progress_cb, cancel_check=cancel_flag.is_set,
                    inclination_deg=rail_inclination_input.value, heading_deg=rail_heading_input.value,
                    on_sample_complete=on_sample_complete, trajectory_points=25,
                )
            finally:
                mc_progress["done"] = True
                progress_bar.props("hidden")
                run_button.props(remove="hidden")
                cancel_button.props("hidden")

            # Drain any samples that finished after the last poll tick, then
            # draw the final 1/2/3-sigma ellipses on the live view too - the
            # SAME numbers landing_ellipses() already gives the static plot.
            poll_progress()
            ellipses = monte_carlo.landing_ellipses(result)
            if ellipses and live_mc_state["container_id"]:
                colors = {1: "0x8a1538", 2: "0xc9a876", 3: "0xe0c9a6"}
                payload = [dict(e, color=int(colors[n], 16)) for n, e in ellipses.items()]
                ui.run_javascript(
                    f"(function(){{ var v = window.BUP && window.BUP._mcViewers && window.BUP._mcViewers['{live_mc_state['container_id']}']; "
                    f"if (v) v.setEllipses({json.dumps(payload)}); }})();"
                )

            s["mc_result"] = result
            status = f"Done: {result.n_completed} completed, {result.n_excluded} excluded."
            if result.cancelled:
                status = f"Cancelled - partial results kept: {status}"
            progress_label.set_text(status)
            render_results(result)

        run_button.on_click(run_mc)
        cancel_button.on_click(cancel_flag.set)
