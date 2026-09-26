"""The "Launch Day" page (2026-09-26 review item H): download real
forecast weather for the launch site/date AHEAD of time (while there's
still internet), cache it locally, and optionally apply its wind to the
next Simulate run - all without needing network again afterward. See
bup_rocketpy/weather.py for the actual fetch+cache logic.
"""
import dataclasses
import datetime
import os

from nicegui import ui

from bup_rocketpy import competition_profiles, weather
from bup_rocketpy.gui import layout, state

s = state.state
CACHE_DIR = os.path.join(os.getcwd(), "outputs", "weather_cache")


@ui.page("/launchday")
def launchday_page():
    with layout.layout("Launch Day", current_path="/launchday"):
        ui.label("Launch-day weather (offline-capable)").classes("text-lg font-bold")
        ui.label(
            "Download the forecast for your launch site/date once, while you still have internet - "
            "it's cached to disk after that, so this page (and Simulate, if you apply it below) keeps "
            "working with NO network at the launch site."
        ).classes("text-sm text-gray-500")

        profile = competition_profiles.get_profile(s["competition_profile"])
        launch = s["load_result"].parsed_ork.launch if s["load_result"] is not None else None
        default_lat = launch.latitude if launch else (profile.default_site_lat or 0.0)
        default_lon = launch.longitude if launch else (profile.default_site_lon or 0.0)

        with ui.grid(columns=4).classes("gap-4"):
            lat_input = ui.number(label="Site latitude", value=default_lat, format="%.4f")
            lon_input = ui.number(label="Site longitude", value=default_lon, format="%.4f")
            date_input = ui.input(label="Launch date (YYYY-MM-DD)", value=datetime.date.today().isoformat())
            hour_input = ui.number(label="Launch hour (local, 0-23)", value=12, min=0, max=23)

        status_label = ui.label("")
        result_container = ui.column().classes("w-full mt-2")

        def _target_iso():
            h = int(hour_input.value or 12)
            return f"{date_input.value}T{h:02d}:00"

        def render_profile(profile_obj):
            result_container.clear()
            with result_container:
                try:
                    speed, direction = weather.nearest_hour_wind(profile_obj, _target_iso())
                except ValueError as exc:
                    ui.label(f"Could not read wind from this profile: {exc}").classes("text-red-700")
                    return
                with ui.grid(columns=3).classes("gap-4"):
                    for label, value in [
                        ("Wind speed", f"{speed:.1f} m/s"),
                        ("Wind direction (from)", f"{direction:.0f}°"),
                        ("Source", profile_obj.source),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(value).classes("text-lg font-bold")

                def apply_to_simulate():
                    if s["load_result"] is None:
                        ui.notify("Load a .ork on the Simulate page first - there's no launch site to override yet.", type="warning")
                        return
                    s["launch_override"] = dataclasses.replace(
                        s["load_result"].parsed_ork.launch,
                        wind_average_ms=speed, wind_direction_deg=direction,
                    )
                    ui.notify("Applied - the next Simulate run will use this wind instead of the .ork's own recorded conditions. Re-run Simulate to see the effect.", type="positive")

                ui.button("Use this weather for Simulate", on_click=apply_to_simulate).classes("mt-2")

        if s["launch_override"] is not None:
            ui.label("A cached weather override is currently ACTIVE for Simulate.").classes("bup-provisional-badge px-3 py-1 rounded font-bold inline-block")

            def clear_override():
                s["launch_override"] = None
                ui.notify("Cleared - Simulate will use the .ork's own recorded conditions again.", type="info")
                ui.navigate.reload()

            ui.button("Clear override (use .ork's own recorded weather)", on_click=clear_override, color="negative")

        def download():
            try:
                profile_obj = weather.fetch_forecast_weather(lat_input.value, lon_input.value, date_input.value, CACHE_DIR)
            except weather.WeatherUnavailableError as exc:
                status_label.set_text(str(exc))
                status_label.classes(replace="text-red-700")
                return
            s["weather_profile"] = profile_obj
            status_label.set_text(f"Downloaded/loaded: {profile_obj.source}")
            status_label.classes(replace="text-green-700")
            render_profile(profile_obj)

        ui.button("Download weather for launch day", on_click=download).classes("mt-2")

        if s["weather_profile"] is not None:
            render_profile(s["weather_profile"])
