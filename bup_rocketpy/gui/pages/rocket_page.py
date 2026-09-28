"""The "Rocket" page (2026-09-26 review, item 2): a side-profile drawing
of the loaded rocket with CG/CP markers, static margin and dimensions.
"""
import os

from nicegui import ui

from bup_rocketpy import openrocket_comparison
from bup_rocketpy.gui import components, layout, pipeline, rocket_drawing, state
from bup_rocketpy.ork_reader import airframe_length_m

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


def _openrocket_comparison_card(parsed, sim_result, ork_path):
    """2026-09-28 review item 2: side-by-side ours-vs-OpenRocket, sourced
    entirely from the .ork's own stored simulation - see
    bup_rocketpy/openrocket_comparison.py's module docstring for why
    each row is computed the way it is (coordinate frame, which numbers
    aren't available from the file at all, the CP-tolerance rationale)."""
    sim_name, rows = openrocket_comparison.compare_to_openrocket(parsed, sim_result, ork_path)
    with components.card(classes="w-full mt-4"):
        ui.label("OpenRocket comparison").classes("font-bold")
        if rows is None:
            ui.label("This design file has no stored OpenRocket simulation to compare against yet - simulate it once in OpenRocket, save, and re-upload the .ork to see this table.").classes("text-sm").style("color: var(--bup-muted)")
            return
        ui.label(f"Against the design file's own stored simulation (\"{sim_name}\") - not flight data, see the Validation page for that.").classes("text-sm").style("color: var(--bup-muted)")
        ui.label("\"Static margin (ascent min.)\" above is the worst point across the WHOLE ascent (rail exit to apogee) - a different, safety-focused number from \"Stability at Mach 0.3\" below, which is OpenRocket's own default design-view snapshot (t=0 mass, Mach 0.3 aerodynamics only).").classes("text-xs mt-1").style("color: var(--bup-muted)")
        with ui.grid(columns=5).classes("gap-2 w-full mt-3 items-center"):
            for header in ["", "Ours", "OpenRocket", "Diff", ""]:
                ui.label(header).classes("font-bold text-xs")
            for row in rows:
                ui.label(row.label).classes("text-sm")
                ui.label(f"{row.ours:.{row.decimals}f} {row.unit}".strip() if row.ours is not None else "n/a").classes("text-sm")
                ui.label(f"{row.openrocket:.{row.decimals}f} {row.unit}".strip() if row.openrocket is not None else "n/a").classes("text-sm")
                if row.pct_diff is None:
                    ui.label("n/a").classes("text-sm").style("color: var(--bup-muted)")
                else:
                    color = "var(--bup-error)" if row.over_threshold else "var(--bup-success)"
                    ui.label(f"{row.pct_diff:+.2f}%").classes("text-sm font-bold").style(f"color: {color}")
                ui.label(row.note).classes("text-xs").style("color: var(--bup-muted)")


@ui.page("/rocket")
def rocket_page():
    with layout.layout("Rocket", current_path="/rocket"):
        if s["load_result"] is None:
            components.page_header("Rocket", "The loaded vehicle's geometry, mass properties and recovery configuration.")
            components.empty_state("architecture", "Load a .ork on the Simulate page first.", action_label="Go to Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            return

        parsed = s["load_result"].parsed_ork
        components.page_header(parsed.name, "Side profile, dimensions and recovery configuration for the loaded vehicle.")

        # Same loaded object as every other page (crash e fix, 2026-09-26
        # review) - dry CG comes from the last Simulate's actually-used
        # value (override or geometric estimate), never the raw manual
        # override field alone, so this page can never show a different
        # rocket's numbers than the cards on this same page do.
        cg = s["dry_cg_m"]
        margin = None
        cp_m03 = None
        if s["sim_result"] is not None:
            margin = s["sim_result"].min_static_margin_cal
            # CP at Mach 0.3 (t=0) - the same "design view" quantity
            # OpenRocket itself defaults to (CLAUDE.md's own "Stability @
            # M 0.3" convention) - not the ascent-minimum static margin
            # above, see the OpenRocket comparison card below for why
            # these are two different numbers.
            cp_m03 = -s["sim_result"].flight.rocket.cp_position(0.3)
        elif cg is None:
            # Haven't run Simulate yet - show the best available estimate
            # anyway rather than an empty drawing (default path must work).
            # Same source-priority as pipeline.run_simulation itself
            # (2026-09-27 review item 1a), so this preview never shows a
            # different CG than what Simulate will actually use.
            from bup_rocketpy import translate
            best = translate.estimate_best_dry_mass_cg_inertia(parsed, s["load_result"].parsed_eng, s["load_result"].eng_path, ork_path=s["load_result"].ork_path)
            if best.mass_est.cg_m is not None:
                cg = best.mass_est.cg_m

        with components.card(classes="w-full"):
            fig = rocket_drawing.draw_side_profile(parsed, dry_cg_m=cg, cp_m=cp_m03, motor_length_m=s["load_result"].parsed_eng.header.length_mm / 1000.0, static_margin_cal=margin)
            path = pipeline.fresh_image_path(OUTPUTS_DIR, "rocket_page_profile")
            fig.savefig(path)
            ui.image(path).classes("w-full max-w-4xl")

        body_radius = next((t.radius for t in parsed.body_tubes if t.radius), 0.05)
        total_length = airframe_length_m(parsed)
        import math
        with ui.grid(columns=4).classes("gap-3 w-full"):
            components.kpi_card("Length", f"{total_length*100:.1f}", "cm", status="neutral", stagger_index=0)
            components.kpi_card("Diameter", f"{body_radius*2*100:.1f}", "cm", status="neutral", stagger_index=1)
            components.kpi_card("Dry CG", f"{cg*100:.1f} cm from nose" if cg is not None else "not set", "", status="neutral", stagger_index=2)
            components.kpi_card("Static margin (ascent min.)", f"{margin:.2f} cal" if margin is not None else "run Simulate first", "", status=("good" if margin and 1.5 <= margin <= 4.0 else "neutral"), stagger_index=3)
            components.kpi_card("Reference area", f"{math.pi * body_radius**2:.5f}", "m2", status="neutral", stagger_index=4)

        if s["sim_result"] is not None and s["load_result"].ork_path:
            _openrocket_comparison_card(parsed, s["sim_result"], s["load_result"].ork_path)

        # 2026-09-25 review Section 5b: reference area + per-parachute
        # diameter/area/Cd*S - geometry-only, so this works right after
        # Load, no Simulate needed.
        if parsed.parachutes:
            with components.card(classes="w-full mt-2"):
                ui.label("Parachutes").classes("font-bold")
                components.data_table(
                    columns=[
                        {"name": "name", "label": "Name", "field": "name"},
                        {"name": "diameter", "label": "Diameter (m)", "field": "diameter"},
                        {"name": "area", "label": "Area (m2)", "field": "area"},
                        {"name": "cd", "label": "Cd", "field": "cd"},
                        {"name": "cd_s", "label": "Cd*S (m2)", "field": "cd_s"},
                    ],
                    rows=[{
                        "name": c.name, "diameter": f"{c.diameter:.2f}",
                        "area": f"{math.pi * (c.diameter / 2.0) ** 2:.3f}",
                        "cd": f"{c.cd:.2f}" if c.cd is not None else "auto (not resolvable)",
                        "cd_s": f"{c.cd * math.pi * (c.diameter / 2.0) ** 2:.3f}" if c.cd is not None else "n/a",
                    } for c in parsed.parachutes],
                )

            # 2026-09-26 review item D (new lettering): OpenRocket has NO
            # concept of "reefed with a line cutter" at all - this is
            # always set here, by the user, never parsed from the .ork.
            # Mutates the loaded parsed.parachutes[i] IN PLACE, the same
            # object Simulate/Monte Carlo/RCSM Cases all already read from
            # s["load_result"] - no separate "apply" plumbing needed,
            # just re-run Simulate after changing this.
            ui.label("Reefed parachute (line cutter)").classes("text-lg font-bold mt-4")
            ui.label("For a main canopy that deploys reefed (small) and is later released to full size by a line cutter - RCSM REC 8.1.1 accepts this as real dual-event recovery. Leave off for a normal single-stage parachute.").classes("text-xs").style("color: var(--bup-muted)")
            for i, c in enumerate(parsed.parachutes):
                with components.card(classes="w-full mt-2", stagger_index=i):
                    ui.label(c.name).classes("font-bold")
                    reefed_checkbox = ui.checkbox("Reefed with line cutter", value=c.is_reefed)
                    with ui.grid(columns=4).classes("gap-2 mt-1").bind_visibility_from(reefed_checkbox, "value"):
                        reefed_diam_input = ui.number(label="Reefed diameter (m)", value=c.reefed_diameter_m)
                        reefed_cd_input = ui.number(label="Reefed Cd", value=c.reefed_cd)
                        cutter_alt_input = ui.number(label="Cutter release altitude AGL (m)", value=c.cutter_altitude_m)
                        cutter_delay_input = ui.number(label="Cutter release delay (s)", value=c.cutter_delay_s or 0.0)
                    with ui.row().classes("items-center gap-2 mt-1").bind_visibility_from(reefed_checkbox, "value"):
                        target_rate_input = ui.number(label="Target reefed descent rate (m/s)", value=None)

                        def compute_target(i=i, target_rate_input=target_rate_input, reefed_diam_input=reefed_diam_input, reefed_cd_input=reefed_cd_input):
                            if not target_rate_input.value or s["dry_mass_kg"] is None:
                                ui.notify("Need a target rate and a completed Simulate (for the descending mass) first.", type="warning")
                                return
                            from bup_rocketpy import translate
                            import math
                            descent_mass_kg = s["dry_mass_kg"]  # approximate: dry rocket only, ignoring the spent motor casing's small addition - good enough for this estimate helper
                            cd = reefed_cd_input.value or 1.5
                            required_cd_s = translate.required_cd_s_for_descent_rate(target_rate_input.value, descent_mass_kg)
                            reefed_diam_input.value = 2.0 * math.sqrt(required_cd_s / (cd * math.pi))
                            ui.notify(f"Reefed diameter set to {reefed_diam_input.value:.2f} m for ~{target_rate_input.value:.0f} m/s (ESTIMATE - verify with a real drop test).", type="info")

                        components.button("Compute reefed diameter", kind="secondary", icon="calculate", on_click=compute_target)

                    def apply_reefing(i=i, reefed_checkbox=reefed_checkbox, reefed_diam_input=reefed_diam_input, reefed_cd_input=reefed_cd_input, cutter_alt_input=cutter_alt_input, cutter_delay_input=cutter_delay_input):
                        import dataclasses
                        parsed.parachutes[i] = dataclasses.replace(
                            parsed.parachutes[i],
                            is_reefed=reefed_checkbox.value,
                            reefed_diameter_m=reefed_diam_input.value, reefed_cd=reefed_cd_input.value,
                            cutter_altitude_m=cutter_alt_input.value, cutter_delay_s=cutter_delay_input.value or 0.0,
                        )
                        ui.notify("Saved - re-run Simulate to see the effect.", type="positive")

                    components.button("Save", kind="primary", icon="save", on_click=apply_reefing)
