"""The "Analysis" page (Phase 6): weathercocking sweep and drag
comparison.
"""
import os

import matplotlib
import matplotlib.pyplot as plt
from nicegui import ui

from stella_flight.gui import layout, state
from stella_flight import analysis, monte_carlo, translate

matplotlib.use("Agg")
s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/analysis")
def analysis_page():
    with layout.layout("Analysis", current_path="/analysis"):
        if s["load_result"] is None or s["dry_mass_override"] is None or s["dry_cg_override"] is None:
            ui.label("Load files and run Simulate (with a dry mass/CG set) on the Simulate page first.").classes("text-gray-500")
            return

        ui.label("Weathercocking: apogee vs. static margin").classes("text-lg font-bold")
        ui.label("Sweeps nose-tip ballast (how you'd tune it on the real rocket), searching for the apogee optimum within the mandatory 1.5-4 cal window.").classes("text-sm text-gray-500")
        wc_container = ui.column().classes("w-full mt-2")

        def run_weathercocking():
            parsed = s["load_result"].parsed_ork
            mass_est = translate.MassEstimate(s["dry_mass_override"], s["dry_cg_override"], "UI")
            i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
            radius = next(t.radius for t in parsed.body_tubes if t.radius)
            result = analysis.weathercocking_sweep(
                parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                s["dry_mass_override"], s["dry_cg_override"], i_ax, i_tr, radius,
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
                ui.image(path).classes("w-full max-w-xl")
                if result.best_point:
                    ui.label(f"Optimum: {result.best_point.ballast_mass_kg:.2f} kg ballast, margin {result.best_point.static_margin_cal:.2f} cal, apogee {result.best_point.apogee_agl_m:.1f} m").classes("font-bold mt-2")
                    if result.hit_lower_bound:
                        ui.label("This lands on the LOWER bound of the tested range - adding ballast only increases margin from here, so no added ballast is needed for this vehicle.").classes("text-sm text-gray-500")

        ui.button("Run weathercocking sweep", on_click=run_weathercocking)

        ui.separator().classes("my-4")
        ui.label("Drag comparison").classes("text-lg font-bold")
        ui.label("Compare two Cd-curve pairs with common random numbers (same seed), so the apogee difference isolates the drag change from sampling noise.").classes("text-sm text-gray-500")
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
            mass_est = translate.MassEstimate(s["dry_mass_override"], s["dry_cg_override"], "UI")
            i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
            radius = next(t.radius for t in parsed.body_tubes if t.radius)
            uncertainties = monte_carlo.default_uncertainties(s["dry_mass_override"], 1871.3, parsed.launch.wind_average_ms)
            result = analysis.drag_comparison(
                parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                (s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path),
                (drag_state["off_b"], drag_state["on_b"]),
                s["dry_mass_override"], s["dry_cg_override"], i_ax, i_tr, radius,
                uncertainties, int(n_input.value), os.path.join(OUTPUTS_DIR, "drag_comparison"), seed=42,
            )
            drag_container.clear()
            with drag_container:
                significant = result.difference_ci_90[0] > 0 or result.difference_ci_90[1] < 0
                ui.label(f"Difference (B - A): {result.mean_difference_m:+.1f} m, 90% CI [{result.difference_ci_90[0]:+.1f}, {result.difference_ci_90[1]:+.1f}] m").classes("font-bold")
                ui.label("The difference is REAL (CI excludes zero)." if significant else "The difference is NOT statistically significant at this N (CI includes zero) - run more samples.").classes("text-sm " + ("text-green-700" if significant else "text-orange-600"))

        ui.button("Run drag comparison", on_click=run_drag_comparison)
