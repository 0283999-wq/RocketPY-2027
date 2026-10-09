"""The "Compare Designs" page (2026-10-09 review item 13, top priority
alongside item 12 - "this is what I actually need right now"): load two
full vehicle designs (e.g. two fin options for the same airframe/motor)
and compare them side by side, with an optional common-random-numbers
Monte Carlo run so the reported apogee difference is statistically
defensible, not just two single numbers next to each other.

Replaces the Analysis page's old "drag comparison" card (item 9) for
the broader "which design should I fly" question - that card only ever
varied the Cd curve for ONE loaded rocket; this compares two ENTIRE
designs (different fins, mass, CP, everything).
"""
import os
import tempfile

import matplotlib
import matplotlib.pyplot as plt
from nicegui import run, ui

from bup_rocketpy.gui import components, layout, plot_theme, state
from bup_rocketpy import compare_designs, monte_carlo

matplotlib.use("Agg")
s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run", "compare_designs")


async def _save_upload(e, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    await e.file.save(path)
    return path, e.file.name


def _read_csv_points(path):
    if not path or not os.path.exists(path):
        return [], []
    xs, ys = [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                try:
                    xs.append(float(parts[0]))
                    ys.append(float(parts[1]))
                except ValueError:
                    continue
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    return [xs[i] for i in order], [ys[i] for i in order]


@ui.page("/compare-designs")
def compare_designs_page():
    with layout.layout("Compare Designs", current_path="/compare-designs"):
        components.page_header("Compare Designs", "Load two vehicle designs (e.g. two fin options) and compare them side by side - nominal numbers, Monte Carlo with common random numbers, and a real statistical verdict.")

        up = {"ork_a": None, "ork_a_name": None, "ork_b": None, "ork_b_name": None, "eng": None, "eng_name": None}

        with ui.row().classes("gap-4 w-full items-start flex-wrap"):
            with components.card(classes="flex-1 min-w-[320px]"):
                ui.label("Design A").classes("font-bold")

                async def on_ork_a(e):
                    up["ork_a"], up["ork_a_name"] = await _save_upload(e, ".ork")
                    ui.notify(f"Design A: {up['ork_a_name']}")
                components.dropzone(".ork file", on_ork_a, accept=".ork")

            with components.card(classes="flex-1 min-w-[320px]"):
                ui.label("Design B").classes("font-bold")

                async def on_ork_b(e):
                    up["ork_b"], up["ork_b_name"] = await _save_upload(e, ".ork")
                    ui.notify(f"Design B: {up['ork_b_name']}")
                components.dropzone(".ork file", on_ork_b, accept=".ork")

            with components.card(classes="flex-1 min-w-[260px]"):
                ui.label("Motor (.eng)").classes("font-bold")
                ui.label("Shared by both designs - the common case is comparing two fin options on the same airframe/motor.").classes("text-xs").style("color: var(--bup-muted)")

                async def on_eng(e):
                    up["eng"], up["eng_name"] = await _save_upload(e, ".eng")
                    ui.notify(f"Loaded {up['eng_name']}")
                components.dropzone(".eng file", on_eng, accept=".eng")

        with components.card(classes="w-full mt-2"):
            mc_n_input = ui.number(label="Monte Carlo samples per design (0 = nominal-only, fast)", value=0)
            ui.label("Both designs run with the SAME random seed per sample (common random numbers) - the apogee difference isolates the design change from sampling noise, not a side effect of comparing two independent random draws.").classes("text-xs").style("color: var(--bup-muted)")
            status_label = ui.label("").classes("text-sm")
            components.button("Run comparison", kind="primary", icon="compare_arrows", on_click=lambda: run_comparison())

        results_container = ui.column().classes("w-full mt-4")

        async def run_comparison():
            if not up["ork_a"] or not up["ork_b"] or not up["eng"]:
                ui.notify("Upload Design A, Design B, and a .eng file first.", type="warning")
                return
            status_label.set_text("Running Design A and Design B...")
            os.makedirs(OUTPUTS_DIR, exist_ok=True)
            mc_n = int(mc_n_input.value or 0)
            mc_uncertainties = None
            if mc_n > 0:
                # A reasonable default spread (same list Monte Carlo's own
                # page seeds from) - wind/mass/Cd/etc, not editable here to
                # keep this page's own scope focused on the A/B question.
                mc_uncertainties = monte_carlo.default_uncertainties(5.0, 1800.0, 3.0)

            try:
                result = await run.io_bound(
                    compare_designs.compare_designs,
                    up["ork_a"], up["eng"], up["ork_b"], up["eng"],
                    outputs_dir=OUTPUTS_DIR,
                    ork_filename_a=up["ork_a_name"], ork_filename_b=up["ork_b_name"], eng_filename_a=up["eng_name"],
                    mc_n=mc_n, mc_uncertainties=mc_uncertainties,
                )
            except Exception as exc:
                status_label.set_text(f"Comparison failed: {exc}")
                ui.notify(str(exc), type="negative", multi_line=True, close_button=True)
                return
            status_label.set_text("Done.")

            a, b = result.design_a, result.design_b
            results_container.clear()
            with results_container:
                if a.cd_curve_stale or b.cd_curve_stale:
                    with components.card(classes="w-full mb-2") as c:
                        c.style("border-left: 4px solid var(--bup-warning)")
                        stale_names = ", ".join(x.display_name for x in (a, b) if x.cd_curve_stale)
                        ui.label(f"Cd curve may be outdated for: {stale_names}").classes("font-bold").style("color: var(--bup-warning)")
                        ui.label("Re-run and save all simulations in OpenRocket for that design, then reload here, before trusting this comparison.").classes("text-sm")

                with components.card(classes="w-full"):
                    ui.label("Side-by-side").classes("font-bold mb-2")
                    rows = [
                        ("File", a.ork_filename, b.ork_filename),
                        ("Rocket name", a.display_name, b.display_name),
                        ("Fins", a.fin_summary, b.fin_summary),
                        ("Apogee AGL (nominal)", f"{a.apogee_agl_m:.1f} m", f"{b.apogee_agl_m:.1f} m"),
                        ("Max speed", f"{a.max_speed_ms:.1f} m/s", f"{b.max_speed_ms:.1f} m/s"),
                        ("Max Mach", f"{a.max_mach:.3f}", f"{b.max_mach:.3f}"),
                        ("Rail exit velocity", f"{a.rail_exit_velocity_ms:.1f} m/s", f"{b.rail_exit_velocity_ms:.1f} m/s"),
                        ("Static margin @ t=0", f"{a.static_margin_t0_cal:.2f} cal", f"{b.static_margin_t0_cal:.2f} cal"),
                        ("Static margin, ascent min/max", f"{a.min_static_margin_cal:.2f} / {a.max_static_margin_cal:.2f} cal", f"{b.min_static_margin_cal:.2f} / {b.max_static_margin_cal:.2f} cal"),
                        ("Stability @ Mach 0.3", f"{a.stability_mach03_cal:.2f} cal", f"{b.stability_mach03_cal:.2f} cal"),
                        ("Fin mass", f"{a.fin_mass_kg*1000:.0f} g" if a.fin_mass_kg else "n/a", f"{b.fin_mass_kg*1000:.0f} g" if b.fin_mass_kg else "n/a"),
                        ("Flutter velocity", f"{a.flutter_velocity_ms:.0f} m/s" if a.flutter_velocity_ms else "n/a", f"{b.flutter_velocity_ms:.0f} m/s" if b.flutter_velocity_ms else "n/a"),
                        ("Flutter / (1.5 x max speed)", f"{a.flutter_margin/1.5:.2f}x" if a.flutter_margin else "n/a", f"{b.flutter_margin/1.5:.2f}x" if b.flutter_margin else "n/a"),
                    ]
                    if mc_n > 0:
                        rows.append(("Apogee, Monte Carlo mean [90% CI]", f"{a.apogee_mc_mean_m:.1f} [{a.apogee_mc_ci90[0]:.1f}, {a.apogee_mc_ci90[1]:.1f}] m", f"{b.apogee_mc_mean_m:.1f} [{b.apogee_mc_ci90[0]:.1f}, {b.apogee_mc_ci90[1]:.1f}] m"))
                    ui.table(
                        columns=[{"name": "metric", "label": "Metric", "field": "metric"}, {"name": "a", "label": "Design A", "field": "a"}, {"name": "b", "label": "Design B", "field": "b"}],
                        rows=[{"metric": m, "a": va, "b": vb} for m, va, vb in rows],
                    ).classes("w-full")

                with components.card(classes="w-full mt-2"):
                    ui.label("Apogee difference (B - A)").classes("font-bold")
                    ui.label(f"Nominal: {result.apogee_diff_b_minus_a_m:+.1f} m").classes("text-sm")
                    if mc_n > 0:
                        ci = result.apogee_mc_diff_ci90
                        significant = ci[0] > 0 or ci[1] < 0
                        ui.label(f"Monte Carlo ({result.mc_n_paired} paired samples): {result.apogee_mc_diff_mean_m:+.1f} m, 90% CI [{ci[0]:+.1f}, {ci[1]:+.1f}] m").classes("text-sm")
                        components.status_chip(result.verdict, "success" if significant else "warning")
                    else:
                        components.status_chip(result.verdict, "neutral")

                cd_off_a_x, cd_off_a_y = _read_csv_points(a.power_off_drag_path)
                cd_off_b_x, cd_off_b_y = _read_csv_points(b.power_off_drag_path)
                if cd_off_a_x or cd_off_b_x:
                    with components.card(classes="w-full mt-2"):
                        ui.label("Cd vs. Mach (power-off / coast)").classes("font-bold")
                        fig, ax = plt.subplots(figsize=(7, 4))
                        if cd_off_a_x:
                            ax.plot(cd_off_a_x, cd_off_a_y, label=f"A: {a.display_name}", color="#8A1538")
                        if cd_off_b_x:
                            ax.plot(cd_off_b_x, cd_off_b_y, label=f"B: {b.display_name}", color="#B79357")
                        ax.set_xlabel("Mach number")
                        ax.set_ylabel("Drag coefficient (Cd)")
                        ax.legend()
                        plot_theme.apply(ax, fig)
                        plot_path = os.path.join(OUTPUTS_DIR, "cd_overlay.png")
                        fig.tight_layout()
                        plot_theme.savefig(fig, plot_path)
                        plt.close(fig)
                        ui.image(plot_path).classes("w-full")

                def do_export_zip():
                    zip_path = os.path.join(OUTPUTS_DIR, "compare_designs.zip")
                    compare_designs.export_comparison_zip(result, zip_path)
                    ui.navigate.to(f"/outputs/compare_designs/{os.path.basename(zip_path)}", new_tab=True)
                components.button("Download per-design flight data (.zip)", kind="secondary", icon="folder_zip", on_click=do_export_zip)
            components.finish_motion()
