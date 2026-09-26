"""Shared header + left sidebar nav (2026-09-26 review, item 2). Every
page calls `with layout("Page Title"):` and fills the returned content
area - keeps navigation/branding in one place per CLAUDE.md's "importable
library, UI kept separate" spirit applied one level down (nav chrome
separate from page content).
"""
import contextlib
import os

from nicegui import ui

from bup_rocketpy.gui import theme

PAGES = [
    ("/", "rocket_launch", "Simulate"),
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
        with ui.row().classes("items-center gap-3"):
            if os.path.exists(theme.LOGO_WINE):
                ui.image(theme.LOGO_WINE).classes("h-8 w-auto")
            else:
                ui.label("Beyond UP RocketPy").classes("text-lg font-bold")
                ui.label("Flight simulation powered by RocketPy").classes("text-sm opacity-80")
        ui.label(title).classes("text-base font-medium")
        dark = ui.dark_mode()
        ui.button(icon="dark_mode", on_click=dark.toggle).props("flat round color=white")

    with ui.left_drawer().classes("bup-sidebar") as drawer:
        for path, icon, label in PAGES:
            classes = "bup-nav-active" if path == current_path else ""
            with ui.row().classes(f"items-center gap-2 p-2 w-full cursor-pointer {classes}").on("click", lambda p=path: ui.navigate.to(p)):
                ui.icon(icon)
                ui.label(label)

    with ui.column().classes("w-full p-4 gap-4") as content:
        yield content
