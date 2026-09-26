"""The "Validation" page: V1/V2 status, predicted vs. flight, and why
everything else in the app is PROVISIONAL.

2026-09-26 review item D: this used to show hand-typed numbers that
drifted out of sync with both the actual code (Diego caught this: the
report showed 1124/1197 m, this page showed 1136.5/1071.1 m, and the
real current numbers were neither) - now computed LIVE from
bup_rocketpy.validation (the exact translate.ork_to_flight calls the
tests and the app itself use), every page load. A couple hundred ms of
real computation, not a cached/stale display.
"""
import os

from nicegui import ui

from bup_rocketpy import validation, weather
from bup_rocketpy.gui import layout

CACHE_DIR = os.path.join(os.getcwd(), "outputs", "weather_cache")


def _render_result_card(r):
    ui.label(r.name).classes("text-lg font-bold mt-4")
    with ui.grid(columns=4).classes("gap-4"):
        for label, value in [
            ("Predicted", f"{r.predicted_agl_m:.1f} m"),
            ("Real flight", f"{r.target_agl_m:.1f} m"),
            ("Error", f"{r.error_pct:+.1f}%"),
            ("Status", "PASS" if r.passes else f"FAIL (>{5.0:.0f}%)" if abs(r.error_pct) > 5.0 else "FAIL"),
        ]:
            with ui.card():
                ui.label(label).classes("text-xs text-gray-500")
                ui.label(value).classes("text-lg font-bold")
    ui.label(r.notes).classes("text-sm text-gray-500 mt-1")


@ui.page("/validation")
def validation_page():
    with layout.layout("Validation", current_path="/validation"):
        ui.label("PROVISIONAL").classes("bup-provisional-badge px-3 py-1 rounded font-bold inline-block")
        ui.label("Every result in this app is provisional until BOTH V1 and V2 pass within +-5%.").classes("mt-2")

        results = validation.compute_v1_and_v2()
        both_pass = all(r.passes for r in results)
        if both_pass:
            ui.label("Both currently pass.").classes("mt-1 text-green-700 font-bold")
        else:
            ui.label("Neither does yet." if not any(r.passes for r in results) else "Not both do yet.").classes("mt-1")

        for r in results:
            _render_result_card(r)

        ui.label("Code-to-code check vs. OpenRocket").classes("text-lg font-bold mt-4")
        ui.label("Reproducing OpenRocket's own CSV-exported simulation with its EXACT inputs (no weather uncertainty at all, same site/rail/mass/wind the .ork itself recorded) currently passes within 2% (see PROGRESS.md for the exact number and history - not re-computed live on this page, it needs an OpenRocket CSV export as its reference that isn't loaded here).").classes("text-sm")
        ui.label("V2's remaining gap above is most likely the difference between the .ork's recorded weather and the actual Iacanga flight-day conditions, not a code bug - real weather data can help resolve this further, below.").classes("text-sm text-gray-500 mt-1")

        # 2026-09-27 review item 5: "print a side-by-side input table" -
        # V2's inputs next to the unconstrained default path's own, so a
        # real difference between them (or the lack of one) is visible,
        # not just asserted. Both now go through the exact same
        # translate.estimate_best_dry_mass_cg_inertia() code path.
        ui.label("V2 vs. the default (no-override) path - side by side").classes("text-lg font-bold mt-4")
        v2_result = next(r for r in results if r.name.startswith("V2"))
        default_ref = validation.compute_default_path_reference()
        input_keys = [
            ("Dry mass", "dry_mass_kg", "{:.4f} kg"),
            ("Dry CG (from nose)", "dry_cg_m", "{:.4f} m"),
            ("Mass/CG source", "mass_source", "{}"),
            ("Total (with-motor) mass", "total_mass_kg", "{}"),
            ("Site altitude", "site_altitude_m", "{:.1f} m"),
            ("Rail length", "rail_length_m", "{:.1f} m"),
            ("Rail inclination", "inclination_deg", "{:.1f} deg"),
            ("Rail heading", "heading_deg", "{:.1f} deg"),
        ]
        with ui.grid(columns=3).classes("gap-2"):
            ui.label("Input").classes("font-bold")
            ui.label("V2 (10.370 kg, as-flown)").classes("font-bold")
            ui.label("Default path (.ork's own stored-sim mass)").classes("font-bold")

            ui.label("Predicted apogee AGL")
            ui.label(f"{v2_result.predicted_agl_m:.1f} m")
            ui.label(f"{default_ref.predicted_agl_m:.1f} m")

            ui.label("Site (lat, lon)")
            ui.label(f"{v2_result.inputs['site_lat']:.4f}, {v2_result.inputs['site_lon']:.4f}")
            ui.label(f"{default_ref.inputs['site_lat']:.4f}, {default_ref.inputs['site_lon']:.4f}")

            for label, key, fmt in input_keys:
                ui.label(label)
                v2_val, def_val = v2_result.inputs.get(key), default_ref.inputs.get(key)
                ui.label("n/a" if v2_val is None else fmt.format(v2_val))
                ui.label("n/a" if def_val is None else fmt.format(def_val))
        ui.label("Both rows use the IDENTICAL code path (translate.estimate_best_dry_mass_cg_inertia + translate.ork_to_flight) - the only real input difference is the total mass (10.370 kg scale-measured for V2 vs. the .ork's own stored-sim design-phase total). The lighter V2 config correctly predicts a HIGHER apogee than the default path, as physics requires - this used to be backwards due to a data-consistency bug (see PROGRESS.md Section 5).").classes("text-xs text-gray-500 mt-1")

        ui.separator().classes("my-4")
        ui.label("Re-run with real weather (Open-Meteo historical)").classes("text-lg font-bold")
        ui.label("Replaces the OpenRocket-recorded wind above with real historical weather for the actual flight date/site. Downloads once, then cached - needs internet on first use (not available in every environment this app runs in).").classes("text-sm text-gray-500")

        v1_result_container = ui.column().classes("w-full mt-2")

        def rerun_v1():
            v1_result_container.clear()
            with v1_result_container:
                try:
                    r = validation.compute_v1_with_real_weather(CACHE_DIR)
                    _render_result_card(r)
                except weather.WeatherUnavailableError as exc:
                    ui.label(str(exc)).classes("text-red-700")

        ui.button("Re-run V1 with real weather", on_click=rerun_v1)

        ui.label(
            "V2 (LASC 2026, Iacanga): the exact flight date is NOT YET RECORDED in this project "
            "(PROGRESS.md logs this as pending from Diego) - enter it below once known."
        ).classes("text-sm text-gray-500 mt-4")
        with ui.row().classes("items-center gap-2"):
            v2_date_input = ui.input(label="LASC 2026 flight date (YYYY-MM-DD)")

            def rerun_v2():
                v2_result_container.clear()
                with v2_result_container:
                    try:
                        r = validation.compute_v2_with_real_weather(v2_date_input.value, CACHE_DIR)
                        _render_result_card(r)
                    except validation.V2FlightDateUnknownError as exc:
                        ui.label(str(exc)).classes("text-orange-700")
                    except weather.WeatherUnavailableError as exc:
                        ui.label(str(exc)).classes("text-red-700")

            ui.button("Re-run V2 with real weather", on_click=rerun_v2)
        v2_result_container = ui.column().classes("w-full mt-2")

        ui.label("What this means for you").classes("text-lg font-bold mt-4")
        ui.label("Numbers from this app (apogee, Monte Carlo intervals, RCSM compliance) are useful for design iteration and relative comparisons (does this change help or hurt?), but should not yet be treated as an accurate absolute prediction for a real launch. Do not submit these numbers to LASC as final without closing the gap above.").classes("text-sm")
