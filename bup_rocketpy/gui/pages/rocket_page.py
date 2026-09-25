"""The "Rocket" page (2026-09-26 review, item 2): a side-profile drawing
of the loaded rocket with CG/CP markers, static margin and dimensions.
"""
import os

from nicegui import ui

from bup_rocketpy.gui import layout, pipeline, rocket_drawing, state

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


@ui.page("/rocket")
def rocket_page():
    with layout.layout("Rocket", current_path="/rocket"):
        if s["load_result"] is None:
            ui.label("Load a .ork on the Simulate page first.").classes("text-gray-500")
            return

        parsed = s["load_result"].parsed_ork
        ui.label(f"Loaded rocket: {parsed.name}").classes("text-base font-bold")

        # Same loaded object as every other page (crash e fix, 2026-09-26
        # review) - dry CG comes from the last Simulate's actually-used
        # value (override or geometric estimate), never the raw manual
        # override field alone, so this page can never show a different
        # rocket's numbers than the cards on this same page do.
        cg = s["dry_cg_m"]
        margin = None
        if s["sim_result"] is not None:
            margin = s["sim_result"].min_static_margin_cal
        elif cg is None:
            # Haven't run Simulate yet - show the best available estimate
            # anyway rather than an empty drawing (default path must work).
            from bup_rocketpy import translate
            estimate = translate.estimate_dry_mass_and_cg(parsed)
            if estimate.cg_m is not None:
                cg = estimate.cg_m

        fig = rocket_drawing.draw_side_profile(parsed, dry_cg_m=cg, cp_m=None, static_margin_cal=margin)
        path = pipeline.fresh_image_path(OUTPUTS_DIR, "rocket_page_profile")
        fig.savefig(path)
        ui.image(path).classes("w-full max-w-4xl")

        body_radius = next((t.radius for t in parsed.body_tubes if t.radius), 0.05)
        total_length = max((t.position_m + t.length for t in parsed.body_tubes), default=0.0)
        with ui.grid(columns=4).classes("gap-4 mt-4"):
            for label, value in [
                ("Length", f"{total_length*100:.1f} cm"),
                ("Diameter", f"{body_radius*2*100:.1f} cm"),
                ("Dry CG", f"{cg*100:.1f} cm from nose" if cg is not None else "not set"),
                ("Static margin", f"{margin:.2f} cal" if margin is not None else "run Simulate first"),
            ]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-lg font-bold")
