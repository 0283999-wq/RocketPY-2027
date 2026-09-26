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
from nicegui import ui

from bup_rocketpy import validation
from bup_rocketpy.gui import layout


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

        ui.label("Code-to-code check vs. OpenRocket").classes("text-lg font-bold mt-4")
        ui.label("Reproducing OpenRocket's own CSV-exported simulation with its EXACT inputs (no weather uncertainty at all, same site/rail/mass/wind the .ork itself recorded) currently passes within 2% (see PROGRESS.md for the exact number and history - not re-computed live on this page, it needs an OpenRocket CSV export as its reference that isn't loaded here).").classes("text-sm")
        ui.label("Because that zero-weather-uncertainty case passes tightly, V2's remaining gap above increasingly looks like a real difference between the .ork's recorded weather and the actual Iacanga flight-day conditions, not a code bug - it needs real weather data to resolve further (see the Validation page's 'Re-run with real weather' button once available), not more code changes.").classes("text-sm text-gray-500 mt-1")

        ui.label("What this means for you").classes("text-lg font-bold mt-4")
        ui.label("Numbers from this app (apogee, Monte Carlo intervals, RCSM compliance) are useful for design iteration and relative comparisons (does this change help or hurt?), but should not yet be treated as an accurate absolute prediction for a real launch. Do not submit these numbers to LASC as final without closing the gap above.").classes("text-sm")
