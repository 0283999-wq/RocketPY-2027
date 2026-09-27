"""The Home page (2026-09-27 UI redesign, Step 3): mission control - the
loaded mission's status, the rocket drawing, a 3D view of the last
trajectory with a Play button, top KPI row, quick actions, and recent
runs. Reads the SAME session state (gui/state.py) every other page
reads/writes - this is a dashboard onto that state, not a separate data
path. Its own empty state covers "nothing loaded yet" (first launch).
"""
import json
import os
import uuid

from nicegui import ui

from bup_rocketpy.gui import components, layout, rocket_drawing, state

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")
s = state.state


def _quick_actions():
    with ui.row().classes("gap-3 flex-wrap"):
        components.button("Simulate", kind="primary", icon="rocket_launch", on_click=lambda: ui.navigate.to("/simulate"))
        components.button("Monte Carlo", kind="secondary", icon="scatter_plot", on_click=lambda: ui.navigate.to("/montecarlo"))
        components.button("Launch Day", kind="secondary", icon="cloud", on_click=lambda: ui.navigate.to("/launchday"))
        components.button("Export", kind="secondary", icon="download", on_click=lambda: ui.navigate.to("/exports"))


def _recent_runs():
    from bup_rocketpy import run_history
    records, _warnings = run_history.list_runs(REPO_ROOT)
    with components.card(classes="w-full"):
        ui.label("Recent runs").classes("font-bold")
        if not records:
            ui.label("No runs saved yet - every Simulate is saved here automatically.").classes("text-sm").style("color: var(--bup-muted)")
            return
        for i, r in enumerate(records[:5]):
            with ui.row().classes("items-center justify-between w-full bup-hoverable rounded px-2 py-1 cursor-pointer").on("click", lambda run_id=r.run_id: ui.navigate.to(f"/history/{run_id}")):
                with ui.column().classes("gap-0"):
                    ui.label(r.vehicle_name).classes("text-sm font-medium")
                    ui.label(r.timestamp.replace("T", " ")[:19]).classes("text-xs").style("color: var(--bup-muted)")
                components.status_chip(f"{r.apogee_agl_m:.0f} m", "success" if r.is_stable else "warning")
        ui.link("See all runs", "/history").classes("text-xs mt-1")


@ui.page("/")
def home_page():
    ui.add_head_html('<script src="/static/vendor/three.min.js"></script><script src="/static/playback.js"></script>')
    with layout.layout("Home", current_path="/"):
        if s["load_result"] is None:
            components.page_header("Mission control", "Load a rocket to get started.")
            components.empty_state(
                "rocket_launch", "Load your .ork and .eng to start.",
                action_label="Load files", on_action=lambda: ui.navigate.to("/simulate"),
            )
            return

        parsed = s["load_result"].parsed_ork
        eng_header = getattr(s["load_result"].parsed_eng, "header", None)
        motor_name = eng_header.designation if eng_header else "-"
        from bup_rocketpy import competition_profiles
        profile = competition_profiles.get_profile(s["competition_profile"])

        components.page_header(parsed.name, f"{motor_name} - {profile.display_name}", action_label="Simulate", action_icon="rocket_launch", on_action=lambda: ui.navigate.to("/simulate"))

        with ui.row().classes("gap-2 flex-wrap"):
            components.status_chip(motor_name, "neutral")
            components.status_chip(profile.display_name, "info")
            reefed = [c for c in parsed.parachutes if c.is_reefed and c.reefed_cd is not None]
            if reefed:
                components.status_chip("Reefing ON", "success")
            if s["sim_result"] is not None:
                components.status_chip("PROVISIONAL" if s["sim_result"].provisional_warning else "Validated", "warning" if s["sim_result"].provisional_warning else "success")

        sim = s["sim_result"]
        if sim is None:
            components.empty_state("rocket_launch", "Loaded, not simulated yet - click Simulate to fly it.", action_label="Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            _quick_actions()
            _recent_runs()
            return

        with ui.grid(columns=4).classes("gap-3 w-full"):
            components.kpi_card("Apogee AGL", None, "m", status="good", countup_target=sim.apogee_agl_m, decimals=1, stagger_index=0)
            components.kpi_card("Max Mach", None, "", status="neutral", countup_target=sim.max_mach, decimals=3, stagger_index=1)
            components.kpi_card("Min static margin", None, "cal", status="good" if sim.is_stable else "bad", countup_target=sim.min_static_margin_cal, decimals=2, stagger_index=2)
            components.kpi_card("Flight time", None, "s", status="neutral", countup_target=sim.flight_time_s, decimals=1, stagger_index=3)

        with ui.row().classes("gap-4 w-full items-start flex-wrap"):
            with components.card(classes="flex-1 min-w-[320px]"):
                ui.label("Vehicle").classes("font-bold")
                fig = rocket_drawing.draw_side_profile(parsed, dry_cg_m=sim.dry_cg_m, static_margin_cal=sim.min_static_margin_cal)
                from bup_rocketpy.gui import pipeline
                png_path = pipeline.fresh_image_path(OUTPUTS_DIR, "home_rocket_profile")
                fig.savefig(png_path)
                import matplotlib.pyplot as plt
                plt.close(fig)
                ui.image(png_path).classes("w-full")

            with components.card(classes="flex-1 min-w-[320px]"):
                ui.label("Last trajectory (3D)").classes("font-bold")
                if sim.flight is not None:
                    from bup_rocketpy.gui import flight_playback
                    playback_data = flight_playback.build_playback_data(sim.flight, sim.motor, n_frames=120)
                    container_id = f"home-playback-{uuid.uuid4().hex[:8]}"
                    ui.html(f'<div id="{container_id}" style="width:100%"></div>')
                    ui.run_javascript(
                        "(function poll(){ if (window.BUP && window.BUP.playback && window.THREE) { "
                        f"BUP.playback.create('{container_id}', {json.dumps(playback_data)}); "
                        "} else { setTimeout(poll, 50); } })();"
                    )
                else:
                    ui.label("Simulate to see the trajectory here.").classes("text-sm").style("color: var(--bup-muted)")

        _quick_actions()
        _recent_runs()
        components.finish_motion()
