"""The "Monte Carlo" page: uncertainties table (editable, sourced),
run/cancel, apogee histogram, landing ellipses.
"""
import os
import threading

import matplotlib
import matplotlib.pyplot as plt
from nicegui import run, ui

from bup_rocketpy.gui import layout, pipeline, state
from bup_rocketpy import monte_carlo

matplotlib.use("Agg")
s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/montecarlo")
def montecarlo_page():
    with layout.layout("Monte Carlo", current_path="/montecarlo"):
        if s["load_result"] is None or s["sim_result"] is None:
            ui.label("Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).").classes("text-gray-500")
            return

        if s["mc_uncertainties"] is None:
            parsed = s["load_result"].parsed_ork
            s["mc_uncertainties"] = monte_carlo.default_uncertainties(s["dry_mass_kg"], 1871.3, parsed.launch.wind_average_ms)

        ui.label("Uncertainties (editable; every one shows its source)").classes("text-lg font-bold")
        rows_container = ui.column().classes("w-full")
        with rows_container:
            for u in s["mc_uncertainties"]:
                with ui.row().classes("items-center gap-2"):
                    u_enabled = ui.checkbox(value=u.enabled)
                    u_enabled.on_value_change(lambda e, u=u: setattr(u, "enabled", e.value))
                    ui.label(u.name).classes("w-48")
                    std_input = ui.number(label="std dev", value=u.std_dev).classes("w-32")
                    std_input.on_value_change(lambda e, u=u: setattr(u, "std_dev", e.value))
                    ui.label(u.source).classes("text-xs text-gray-500 flex-1")

        n_input = ui.number(label="N simulations", value=50)
        progress_bar = ui.linear_progress(value=0).props("hidden")
        progress_label = ui.label("")
        run_button = ui.button("Run Monte Carlo")
        cancel_button = ui.button("Cancel", color="negative").props("hidden")
        results_container = ui.column().classes("w-full mt-4")

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

        def poll_progress():
            progress_label.set_text(mc_progress["text"])
            if mc_progress["done"]:
                poll_timer.deactivate()

        poll_timer = ui.timer(0.4, poll_progress, active=False)

        async def run_mc():
            parsed = s["load_result"].parsed_ork
            i_ax, i_tr = _get_inertia()
            radius = next(t.radius for t in parsed.body_tubes if t.radius)
            n = int(n_input.value)

            def progress_cb(i, total):
                mc_progress["text"] = f"Running {i}/{total}..."

            cancel_flag.clear()
            mc_progress["done"] = False
            progress_bar.props(remove="hidden")
            run_button.props("hidden")
            cancel_button.props(remove="hidden")
            poll_timer.activate()

            try:
                result = await run.io_bound(
                    monte_carlo.run_monte_carlo,
                    parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                    s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                    s["dry_mass_kg"], s["dry_cg_m"], i_ax, i_tr, radius,
                    s["mc_uncertainties"], n, os.path.join(OUTPUTS_DIR, "monte_carlo"),
                    include_recovery=True, progress_callback=progress_cb, cancel_check=cancel_flag.is_set,
                )
            finally:
                mc_progress["done"] = True
                progress_bar.props("hidden")
                run_button.props(remove="hidden")
                cancel_button.props("hidden")

            s["mc_result"] = result
            status = f"Done: {result.n_completed} completed, {result.n_excluded} excluded."
            if result.cancelled:
                status = f"Cancelled - partial results kept: {status}"
            progress_label.set_text(status)

            results_container.clear()
            with results_container:
                with ui.grid(columns=3).classes("gap-4"):
                    for label, value in [
                        ("Apogee mean", f"{result.apogee_mean:.1f} m"),
                        ("90% interval low", f"{result.apogee_p05:.1f} m"),
                        ("90% interval high", f"{result.apogee_p95:.1f} m"),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(value).classes("bup-kpi-value text-xl font-bold")

                fig, ax = plt.subplots(figsize=(6, 3.5))
                ax.hist(result.apogee_samples, bins=min(20, max(5, result.n_completed // 3)), color="#8A1538", alpha=0.75)
                ax.axvline(result.apogee_mean, color="#B79357", linestyle="--", label="mean")
                ax.set_xlabel("Apogee AGL (m)")
                ax.set_ylabel("count")
                ax.legend()
                hist_path = pipeline.fresh_image_path(OUTPUTS_DIR, "mc_histogram")
                fig.tight_layout()
                fig.savefig(hist_path)
                plt.close(fig)
                ui.image(hist_path).classes("w-full max-w-xl")

                ellipses = monte_carlo.landing_ellipses(result)
                if ellipses:
                    fig2, ax2 = plt.subplots(figsize=(6, 6))
                    for n_std, color in [(3, "#e0c9a6"), (2, "#c9a876"), (1, "#8A1538")]:
                        e = ellipses[n_std]
                        from matplotlib.patches import Ellipse
                        ax2.add_patch(Ellipse((e["center_x"], e["center_y"]), e["width"], e["height"], angle=e["angle_deg"], facecolor=color, alpha=0.4, edgecolor=color, label=f"{n_std}-sigma"))
                    ax2.scatter(result.impact_x_samples, result.impact_y_samples, s=8, color="#211A16", zorder=5)
                    ax2.set_xlabel("X (m, downrange)")
                    ax2.set_ylabel("Y (m, crossrange)")
                    ax2.set_aspect("equal")
                    ax2.legend()
                    ax2.set_title("Landing ellipse (single recovery event)")
                    ellipse_path = pipeline.fresh_image_path(OUTPUTS_DIR, "mc_ellipse")
                    fig2.tight_layout()
                    fig2.savefig(ellipse_path)
                    plt.close(fig2)
                    ui.image(ellipse_path).classes("w-full max-w-xl")
                else:
                    ui.label("No landing ellipse: this case terminates at apogee (Ballistic) or too few samples completed.").classes("text-gray-500")

        def _get_inertia():
            from bup_rocketpy import translate
            parsed = s["load_result"].parsed_ork
            mass_est = translate.MassEstimate(s["dry_mass_kg"], s["dry_cg_m"], "UI")
            return translate.estimate_dry_inertia(parsed, mass_est)

        run_button.on_click(run_mc)
        cancel_button.on_click(cancel_flag.set)
