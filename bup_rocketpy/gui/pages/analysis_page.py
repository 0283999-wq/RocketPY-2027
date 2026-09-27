"""The "Analysis" page (Phase 6): weathercocking sweep and drag
comparison.
"""
import os

import matplotlib
import matplotlib.pyplot as plt
from nicegui import ui

from bup_rocketpy.gui import components, layout, state
from bup_rocketpy import analysis, monte_carlo, translate

matplotlib.use("Agg")
s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/analysis")
def analysis_page():
    with layout.layout("Analysis", current_path="/analysis"):
        components.page_header("Analysis", "Questions only RocketPy can answer: weathercocking sensitivity and drag-source comparisons.")
        if s["load_result"] is None or s["sim_result"] is None:
            components.empty_state("insights", "Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).", action_label="Go to Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            return

        with ui.row().classes("gap-4 w-full items-start flex-wrap"):
            with components.card(classes="flex-1 min-w-[380px]"):
                ui.label("Weathercocking: apogee vs. static margin").classes("font-bold")
                ui.label("Sweeps nose-tip ballast (how you'd tune it on the real rocket), searching for the apogee optimum within the mandatory 1.5-4 cal window.").classes("text-sm").style("color: var(--bup-muted)")
                wc_container = ui.column().classes("w-full mt-2")

                def run_weathercocking():
                    parsed = s["load_result"].parsed_ork
                    mass_est = translate.MassEstimate(s["dry_mass_kg"], s["dry_cg_m"], "UI")
                    # 2026-09-27 review item 1: start from the SAME inertia Simulate
                    # itself used for this rocket (state["dry_i_*"]), not a fresh
                    # geometric re-derivation that could silently disagree with it -
                    # the sweep below still recomputes inertia per candidate ballast
                    # position, this is only the baseline/no-ballast starting point.
                    i_ax, i_tr = (s["dry_i_axial_kgm2"], s["dry_i_transverse_kgm2"]) if s["dry_i_axial_kgm2"] is not None else translate.estimate_dry_inertia(parsed, mass_est)
                    radius = next(t.radius for t in parsed.body_tubes if t.radius)
                    result = analysis.weathercocking_sweep(
                        parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                        s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                        s["dry_mass_kg"], s["dry_cg_m"], i_ax, i_tr, radius,
                    )
                    s["weathercocking_result"] = result
                    wc_container.clear()
                    with wc_container:
                        fig, ax = plt.subplots(figsize=(6, 3.5))
                        margins = [p.static_margin_cal for p in result.points]
                        apogees = [p.apogee_agl_m for p in result.points]
                        colors = ["#8A1538" if p.in_valid_range else "#999999" for p in result.points]
                        ax.scatter(margins, apogees, c=colors)
                        ax.axvline(1.5, color="#B79357", linestyle=":", label="1.5-4 cal window")
                        ax.axvline(4.0, color="#B79357", linestyle=":")
                        ax.set_xlabel("Static margin (cal)")
                        ax.set_ylabel("Apogee AGL (m)")
                        ax.legend()
                        path = os.path.join(OUTPUTS_DIR, "weathercocking.png")
                        fig.tight_layout()
                        fig.savefig(path)
                        plt.close(fig)
                        ui.image(path).classes("w-full")
                        if result.best_point:
                            components.status_chip(
                                f"Optimum: {result.best_point.ballast_mass_kg:.2f} kg ballast, margin {result.best_point.static_margin_cal:.2f} cal, apogee {result.best_point.apogee_agl_m:.1f} m",
                                "success",
                            )
                            if result.hit_lower_bound:
                                ui.label("This lands on the LOWER bound of the tested range - adding ballast only increases margin from here, so no added ballast is needed for this vehicle.").classes("text-sm mt-1").style("color: var(--bup-muted)")
                    components.finish_motion()

                components.button("Run weathercocking sweep", kind="primary", icon="tune", on_click=run_weathercocking)

            with components.card(classes="flex-1 min-w-[380px]"):
                ui.label("Drag comparison").classes("font-bold")
                ui.label("Compare two Cd-curve pairs with common random numbers (same seed), so the apogee difference isolates the drag change from sampling noise.").classes("text-sm").style("color: var(--bup-muted)")
                with ui.row():
                    off_b = ui.upload(label="power_off_drag.csv, option B", auto_upload=True)
                    on_b = ui.upload(label="power_on_drag.csv, option B", auto_upload=True)
                n_input = ui.number(label="N simulations", value=30)
                drag_container = ui.column().classes("w-full mt-2")
                drag_state = {"off_b": None, "on_b": None}

                async def _save(e, suffix, key):
                    import tempfile
                    fd, path = tempfile.mkstemp(suffix=suffix)
                    os.close(fd)
                    await e.file.save(path)
                    drag_state[key] = path
                    ui.notify(f"Loaded option B: {e.file.name}")

                off_b.on_upload(lambda e: _save(e, ".csv", "off_b"))
                on_b.on_upload(lambda e: _save(e, ".csv", "on_b"))

                def run_drag_comparison():
                    if not drag_state["off_b"] or not drag_state["on_b"]:
                        ui.notify("Upload both CSVs for option B first.", type="warning")
                        return
                    parsed = s["load_result"].parsed_ork
                    mass_est = translate.MassEstimate(s["dry_mass_kg"], s["dry_cg_m"], "UI")
                    # 2026-09-27 review item 1: same rocket as Simulate's own
                    # Nominal result - use its actually-used inertia, not a fresh
                    # geometric re-derivation, or the two drag curves being
                    # compared would each fly a subtly different rocket.
                    i_ax, i_tr = (s["dry_i_axial_kgm2"], s["dry_i_transverse_kgm2"]) if s["dry_i_axial_kgm2"] is not None else translate.estimate_dry_inertia(parsed, mass_est)
                    radius = next(t.radius for t in parsed.body_tubes if t.radius)
                    uncertainties = monte_carlo.default_uncertainties(s["dry_mass_kg"], 1871.3, parsed.launch.wind_average_ms)
                    result = analysis.drag_comparison(
                        parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                        (s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path),
                        (drag_state["off_b"], drag_state["on_b"]),
                        s["dry_mass_kg"], s["dry_cg_m"], i_ax, i_tr, radius,
                        uncertainties, int(n_input.value), os.path.join(OUTPUTS_DIR, "drag_comparison"), seed=42,
                    )
                    drag_container.clear()
                    with drag_container:
                        significant = result.difference_ci_90[0] > 0 or result.difference_ci_90[1] < 0
                        ui.label(f"Difference (B - A): {result.mean_difference_m:+.1f} m, 90% CI [{result.difference_ci_90[0]:+.1f}, {result.difference_ci_90[1]:+.1f}] m").classes("font-bold")
                        components.status_chip(
                            "The difference is REAL (CI excludes zero)." if significant else "The difference is NOT statistically significant at this N (CI includes zero) - run more samples.",
                            "success" if significant else "warning",
                        )
                    components.finish_motion()

                components.button("Run drag comparison", kind="primary", icon="compare_arrows", on_click=run_drag_comparison)
