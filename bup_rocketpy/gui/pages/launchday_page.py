"""The "Launch Day" page (2026-09-26 review item H, 2026-09-27 review
item 3): download real forecast weather for the launch site/date AHEAD
of time (while there's still internet), cache it locally, and optionally
apply its wind to the next Simulate run - all without needing network
again afterward. Beyond Open-Meteo's ~16-day forecast horizon, offers a
climatology (historical average + spread for that date/hour) instead of
failing outright. See bup_rocketpy/weather.py for the actual fetch+cache
logic and the real timezone/units bug fixed there today.
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
            "working with NO network at the launch site. Times are LOCAL to the launch site."
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
        climatology_container = ui.column().classes("w-full mt-2")

        def _target_iso():
            h = int(hour_input.value or 12)
            return f"{date_input.value}T{h:02d}:00"

        def _apply_wind(speed, direction, source_label):
            if s["load_result"] is None:
                ui.notify("Load a .ork on the Simulate page first - there's no launch site to override yet.", type="warning")
                return
            s["launch_override"] = dataclasses.replace(
                s["load_result"].parsed_ork.launch,
                wind_average_ms=speed, wind_direction_deg=direction,
            )
            ui.notify(f"Applied ({source_label}) - the next Simulate run will use this wind instead of the .ork's own recorded conditions. Re-run Simulate to see the effect.", type="positive")

        def render_profile(profile_obj):
            result_container.clear()
            with result_container:
                try:
                    speed, direction = weather.nearest_hour_wind(profile_obj, _target_iso())
                    rows = weather.wind_profile_vs_altitude(profile_obj, _target_iso())
                except ValueError as exc:
                    ui.label(f"Could not read wind from this profile: {exc}").classes("text-red-700")
                    return
                with ui.grid(columns=3).classes("gap-4"):
                    for label, value in [
                        ("Wind speed (10 m)", f"{speed:.1f} m/s"),
                        ("Wind direction (from)", f"{direction:.0f}°"),
                        ("Source", profile_obj.source),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(value).classes("text-lg font-bold")

                # 2026-09-27 review item 3a: "show the full wind profile
                # vs altitude, not just one number."
                ui.label("Wind profile vs altitude").classes("text-md font-bold mt-2")
                ui.label("Altitude is the ICAO standard-atmosphere approximate height for each pressure level (labeled, not the site's own measured elevation) - for a sense of shear with height, not a precise AGL reading.").classes("text-xs text-gray-500")
                ui.table(
                    columns=[
                        {"name": "altitude", "label": "~Altitude (m ASL)", "field": "altitude"},
                        {"name": "pressure", "label": "Pressure level", "field": "pressure"},
                        {"name": "speed", "label": "Wind speed (m/s)", "field": "speed"},
                        {"name": "direction", "label": "Direction (from, °)", "field": "direction"},
                    ],
                    rows=[{
                        "altitude": f"{alt:.0f}", "pressure": f"{p} hPa" if p else "surface (10 m)",
                        "speed": f"{spd:.1f}", "direction": f"{d:.0f}",
                    } for alt, p, spd, d in rows],
                ).classes("w-full")

                ui.button("Use this weather for Simulate", on_click=lambda: _apply_wind(speed, direction, profile_obj.source)).classes("mt-2")

        def render_climatology(clim):
            climatology_container.clear()
            with climatology_container:
                ui.label(f"Climatology for {clim.month:02d}-{clim.day:02d} {clim.hour:02d}:00 local, averaged over {len(clim.years)} years ({min(clim.years)}-{max(clim.years)})").classes("text-md font-bold")
                with ui.grid(columns=3).classes("gap-4"):
                    for label, value in [
                        ("Wind speed (mean ± std)", f"{clim.wind_speed_mean_ms:.1f} ± {clim.wind_speed_std_ms:.1f} m/s"),
                        ("Wind direction (mean, from)", f"{clim.wind_direction_mean_deg:.0f}°"),
                        ("Source", clim.source),
                    ]:
                        with ui.card():
                            ui.label(label).classes("text-xs text-gray-500")
                            ui.label(value).classes("text-lg font-bold")
                ui.label("This is a planning estimate (historical spread for that date/hour), not a specific forecast for this exact year.").classes("text-xs text-gray-500")

                def apply_climatology_mean():
                    _apply_wind(clim.wind_speed_mean_ms, clim.wind_direction_mean_deg, "climatology mean")

                def apply_climatology_to_mc():
                    if not s["mc_uncertainties"]:
                        ui.notify("Visit the Monte Carlo page first (it creates the default uncertainty table) before applying a climatology wind distribution to it.", type="warning")
                        return
                    for u in s["mc_uncertainties"]:
                        if u.name == "wind_speed_ms":
                            u.nominal, u.std_dev = clim.wind_speed_mean_ms, max(clim.wind_speed_std_ms, 0.5)
                            u.source = f"climatology: {clim.source}, {len(clim.years)} years"
                        elif u.name == "wind_direction_deg":
                            u.nominal = clim.wind_direction_mean_deg
                            u.source = f"climatology: {clim.source}, {len(clim.years)} years"
                    ui.notify("Monte Carlo's wind uncertainty now uses this climatology - re-run Monte Carlo to see the effect.", type="positive")

                with ui.row().classes("gap-2 mt-2"):
                    ui.button("Use climatology mean for Simulate", on_click=apply_climatology_mean)
                    ui.button("Use climatology for Monte Carlo's wind distribution", on_click=apply_climatology_to_mc)

        if s["launch_override"] is not None:
            ui.label("A cached weather override is currently ACTIVE for Simulate.").classes("bup-provisional-badge px-3 py-1 rounded font-bold inline-block")

            def clear_override():
                s["launch_override"] = None
                ui.notify("Cleared - Simulate will use the .ork's own recorded conditions again.", type="info")
                ui.navigate.reload()

            ui.button("Clear override (use .ork's own recorded weather)", on_click=clear_override, color="negative")

        def download_climatology():
            try:
                d = datetime.date.fromisoformat(date_input.value)
            except ValueError:
                ui.notify("Enter the launch date as YYYY-MM-DD first.", type="warning")
                return
            try:
                clim = weather.fetch_climatology(lat_input.value, lon_input.value, d.month, d.day, int(hour_input.value or 12), CACHE_DIR)
            except weather.WeatherUnavailableError as exc:
                status_label.set_text(str(exc))
                status_label.classes(replace="text-red-700")
                return
            status_label.set_text(f"Climatology downloaded/loaded ({len(clim.years)} years).")
            status_label.classes(replace="text-green-700")
            render_climatology(clim)

        def download():
            try:
                profile_obj = weather.fetch_forecast_weather(lat_input.value, lon_input.value, date_input.value, CACHE_DIR)
            except weather.ForecastHorizonError as exc:
                # 2026-09-27 review item 3b: a date beyond Open-Meteo's
                # forecast horizon (Diego's December example) - offer
                # climatology right here instead of just failing.
                status_label.set_text(str(exc))
                status_label.classes(replace="text-orange-700")
                ui.notify("Beyond the forecast window - use 'Download climatology' below for a planning estimate instead.", type="warning")
                return
            except weather.WeatherUnavailableError as exc:
                status_label.set_text(str(exc))
                status_label.classes(replace="text-red-700")
                return
            s["weather_profile"] = profile_obj
            status_label.set_text(f"Downloaded/loaded: {profile_obj.source}")
            status_label.classes(replace="text-green-700")
            render_profile(profile_obj)

        with ui.row().classes("gap-2"):
            ui.button("Download weather for launch day", on_click=download).classes("mt-2")
            ui.button("Download climatology (for dates too far out)", on_click=download_climatology, color="secondary").classes("mt-2")

        if s["weather_profile"] is not None:
            render_profile(s["weather_profile"])
