"""The "Analysis" page (Phase 6): weathercocking sweep and drag
comparison.
"""
import os

import matplotlib
import matplotlib.pyplot as plt
from nicegui import ui

from bup_rocketpy.gui import components, layout, plot_theme, state
from bup_rocketpy import analysis, translate

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
                        colors = ["#8A1538" if p.in_valid_range else plot_theme.AXIS for p in result.points]
                        ax.scatter(margins, apogees, c=colors)
                        ax.axvline(1.5, color="#B79357", linestyle=":", label="1.5-4 cal window")
                        ax.axvline(4.0, color="#B79357", linestyle=":")
                        ax.set_xlabel("Static margin (cal)")
                        ax.set_ylabel("Apogee AGL (m)")
                        ax.legend()
                        plot_theme.apply(ax, fig)
                        path = os.path.join(OUTPUTS_DIR, "weathercocking.png")
                        fig.tight_layout()
                        plot_theme.savefig(fig, path)
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
                ui.label("Comparing two designs?").classes("font-bold")
                # 2026-10-09 review item 13: "this replaces the confusing
                # drag-comparison card" - that card only ever varied the Cd
                # curve for the ONE already-loaded rocket (asking for "power_
                # off_drag.csv, option B" with no explanation of what to put
                # there, per item 9's own complaint); the real question
                # ("should I fly fin set A or B") needs two FULL designs
                # (different mass/CP/everything), not just two Cd files for
                # the same one - see /compare-designs.
                ui.label("The old drag-comparison card (two Cd CSVs for the SAME loaded rocket) moved to its own page, which compares two FULL .ork designs side by side - apogee, stability, flutter, Cd overlay, and a Monte Carlo verdict with common random numbers.").classes("text-sm").style("color: var(--bup-muted)")
                components.button("Go to Compare Designs", kind="primary", icon="compare_arrows", on_click=lambda: ui.navigate.to("/compare-designs"))
