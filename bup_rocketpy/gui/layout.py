"""Shared header + left sidebar nav (2026-09-26 review, item 2). Every
page calls `with layout("Page Title"):` and fills the returned content
area - keeps navigation/branding in one place per CLAUDE.md's "importable
library, UI kept separate" spirit applied one level down (nav chrome
separate from page content).
"""
import contextlib
import os

from nicegui import ui

from bup_rocketpy.gui import state, theme

PAGES = [
    ("/", "space_dashboard", "Home"),
    ("/simulate", "rocket_launch", "Simulate"),
    ("/rocket", "architecture", "Rocket"),
    ("/montecarlo", "scatter_plot", "Monte Carlo"),
    ("/rcsm", "checklist", "RCSM Cases"),
    ("/analysis", "insights", "Analysis"),
    ("/history", "history", "History"),
    ("/exports", "download", "Exports"),
    ("/validation", "verified", "Validation"),
    ("/launchday", "cloud", "Launch Day"),
]


@contextlib.contextmanager
def layout(title, current_path="/"):
    # theme.apply() must run INSIDE a page function, not at module import
    # time - this NiceGUI version raises "ui.page cannot be used ... when
    # UI is defined in the global scope" if any ui.* call happens outside
    # a @ui.page-decorated function once multiple pages exist. Calling it
    # here (every page already goes through layout()) means it runs once
    # per page load - harmless repetition of the same <style>/ui.colors()
    # setup, and the only place in this codebase it's now called from.
    theme.apply(ui)
    ui.add_head_html(f'<title>Beyond UP RocketPy - {title}</title>')
    with ui.header().classes("bup-header items-center justify-between"):
        with ui.row().classes("items-center gap-1"):
            drawer_ref = {}
            ui.button(icon="menu", on_click=lambda: drawer_ref["drawer"].toggle()).props("flat round color=white").classes("mr-1")
            if os.path.exists(theme.LOGO_WINE):
                ui.image(theme.LOGO_WINE).classes("h-8 w-auto")
            else:
                with ui.column().classes("gap-0"):
                    ui.label("Beyond UP RocketPy").classes("text-lg font-bold")
                    ui.label("Flight simulation powered by RocketPy").classes("text-sm opacity-80")
        ui.label(title).classes("text-base font-medium")
        dark = ui.dark_mode()
        ui.button(icon="dark_mode", on_click=dark.toggle).props("flat round color=white")

    with ui.left_drawer().classes("bup-sidebar") as drawer:
        drawer_ref["drawer"] = drawer
        for path, icon, label in PAGES:
            active = path == current_path
            classes = "bup-nav-active" if active else "bup-nav-item"
            with ui.row().classes(f"items-center gap-2 p-2 w-full cursor-pointer {classes}").on("click", lambda p=path: ui.navigate.to(p)):
                icon_el = ui.icon(icon)
                if active:
                    icon_el.style(f"color: {theme.GOLD}")
                ui.label(label).classes("font-medium" if active else "")

    _status_bar()

    with ui.column().classes("w-full p-4 gap-4 bup-page-enter") as content:
        yield content


def _status_bar():
    """2026-09-27 review item 2: "a status bar on every page with the
    loaded rocket, motor, and chips like 'Reefing ON: ...' / 'Weather:
    ...' / 'Profile: ...'" - ONE place (this is the only file every page
    already routes through via layout()), so it can never drift out of
    sync with what a specific page happens to show."""
    s = state.state
    if s["load_result"] is None:
        return

    from bup_rocketpy import competition_profiles

    parsed = s["load_result"].parsed_ork
    eng_header = getattr(s["load_result"].parsed_eng, "header", None)
    chips = [f"{parsed.name} / {eng_header.designation if eng_header else s['load_result'].eng_path and os.path.basename(s['load_result'].eng_path)}"]

    reefed = [c for c in parsed.parachutes if c.is_reefed and c.reefed_cd is not None and c.reefed_diameter_m is not None and c.cutter_altitude_m is not None]
    if reefed:
        c = reefed[0]
        import math
        reefed_cd_s = c.reefed_cd * math.pi * (c.reefed_diameter_m / 2.0) ** 2
        chips.append(f"Reefing ON: reefed Cd·S {reefed_cd_s:.2f} m², cutter at {c.cutter_altitude_m:.0f} m")

    if s["launch_override"] is not None:
        profile = s.get("weather_profile")
        label = f"{profile.source} {profile.date}" if profile is not None else "override active"
        chips.append(f"Weather: {label}")

    profile = competition_profiles.get_profile(s["competition_profile"])
    chips.append(f"Profile: {profile.display_name}")

    with ui.row().classes("bup-status-bar items-center gap-2 px-4 py-1 flex-wrap"):
        for chip in chips:
            ui.label(chip).classes("bup-status-chip text-xs px-2 py-1 rounded")
