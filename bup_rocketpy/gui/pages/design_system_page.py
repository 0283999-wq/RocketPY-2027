"""Component gallery (2026-09-27 UI redesign, Step 1): every component
from gui/components.py, rendered once so the whole design system can be
screenshotted and checked in one place - not in the main sidebar nav
(this is a reference page for whoever touches the UI next, not a
Diego-facing feature), but reachable directly at /design-system.
Documented alongside docs/design_system.md.
"""
from nicegui import ui

from bup_rocketpy.gui import components, layout, theme


def _section(title):
    ui.label(title).classes("text-lg font-bold mt-4")
    ui.separator()


@ui.page("/design-system")
def design_system_page():
    with layout.layout("Design system", current_path="/design-system"):
        components.page_header(
            "Design system",
            "Every token and component this app is built from - see docs/design_system.md.",
            action_label="Primary action", action_icon="rocket_launch",
        )

        _section("Colors")
        with ui.row().classes("gap-3 flex-wrap"):
            for name, value in [("Wine", theme.WINE), ("Gold", theme.GOLD), ("Success", theme.SUCCESS),
                                 ("Warning", theme.WARNING), ("Error", theme.ERROR), ("Info", theme.INFO)]:
                with ui.column().classes("items-center gap-1"):
                    ui.element("div").style(f"background-color:{value}; width:64px; height:64px; border-radius: var(--bup-radius-md);")
                    ui.label(f"{name}").classes("text-xs")
                    ui.label(value).classes("text-xs").style("color: var(--bup-muted)")

        _section("Buttons")
        with ui.row().classes("gap-3"):
            components.button("Primary", kind="primary", icon="rocket_launch")
            components.button("Secondary", kind="secondary", icon="tune")
            components.button("Ghost", kind="ghost", icon="info")
            components.button("Danger", kind="danger", icon="delete")

        _section("Status chips")
        with ui.row().classes("gap-2"):
            components.status_chip("Neutral", "neutral")
            components.status_chip("Reefing ON", "success")
            components.status_chip("PROVISIONAL", "warning")
            components.status_chip("FAIL", "error")
            components.status_chip("Weather: Open-Meteo", "info")

        _section("KPI cards (with count-up)")
        with ui.grid(columns=4).classes("gap-3 w-full"):
            components.kpi_card("Apogee AGL", None, "m", "target ballpark", status="good", countup_target=1072.1, decimals=1, stagger_index=0)
            components.kpi_card("Max Mach", None, "", "boost phase", status="neutral", countup_target=0.473, decimals=3, stagger_index=1)
            components.kpi_card("Min static margin", None, "cal", "rail exit - apogee", status="warn", countup_target=2.04, decimals=2, stagger_index=2)
            components.kpi_card("Stability", "NO", "", "outside 1.5-4 cal", status="bad", stagger_index=3)

        _section("Cards (staggered entrance)")
        with ui.grid(columns=3).classes("gap-3 w-full"):
            for i in range(3):
                with components.card(interactive=True, stagger_index=i):
                    ui.label(f"Card {i + 1}").classes("font-bold")
                    ui.label("Hover to see the lift + shadow micro-interaction.").classes("text-sm").style("color: var(--bup-muted)")

        _section("Empty state")
        components.empty_state("rocket_launch", "Load your .ork and .eng to start.", action_label="Load files", on_action=lambda: ui.notify("Would navigate to Simulate"))

        _section("Skeleton loading")
        with ui.column().classes("gap-2 w-full max-w-md"):
            components.skeleton(height="16px", width="60%")
            components.skeleton(height="16px", width="90%")
            components.skeleton(height="16px", width="75%")

        _section("Confirm dialog")
        dialog, confirm_btn = components.confirm_dialog("Delete this item? This cannot be undone.")
        confirm_btn.on_click(lambda: (ui.notify("Confirmed (demo only)"), dialog.close()))
        components.button("Open confirm dialog", kind="danger", on_click=dialog.open)

        _section("Error bar")
        ui.label("V1 (FAIL, +11.0%)").classes("text-sm")
        components.error_bar(11.0, tolerance_pct=5.0)
        ui.label("V2 (PASS, -3.4%)").classes("text-sm mt-2")
        components.error_bar(-3.4, tolerance_pct=5.0)

        _section("Data table")
        components.data_table(
            columns=[{"name": "case", "label": "Case", "field": "case"}, {"name": "apogee", "label": "Apogee AGL (m)", "field": "apogee"}],
            rows=[{"case": "Ballistic", "apogee": "980.2"}, {"case": "Nominal", "apogee": "1072.1"}],
        )

        components.finish_motion()
