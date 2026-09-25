"""The "Validation" page: V1/V2 status, predicted vs. flight, and why
everything else in the app is PROVISIONAL. These numbers come from the
pytest suite (tests/test_phase2_validation.py), not a runtime
computation here - re-run pytest and update these if the underlying model
changes; this page is a display, not a live re-derivation, since V1/V2
represent a specific, audited comparison whose inputs are documented in
PROGRESS.md, not something to silently recompute differently each page load.
"""
from nicegui import ui

from stella_flight.gui import layout


@ui.page("/validation")
def validation_page():
    with layout.layout("Validation", current_path="/validation"):
        ui.label("PROVISIONAL").classes("stella-provisional-badge px-3 py-1 rounded font-bold inline-block")
        ui.label("Every result in this app is provisional until BOTH V1 and V2 pass within +-5%. Neither does yet.").classes("mt-2")

        ui.label("V1 - 2026-07-04 (Pachuca profile)").classes("text-lg font-bold mt-4")
        with ui.grid(columns=4).classes("gap-4"):
            for label, value in [("Predicted", "1124.1 m"), ("Real flight", "1019.9 m"), ("Error", "+10.2%"), ("Status", "FAIL (>5%)")]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-lg font-bold")
        ui.label("Mass/motor from verified_constants.json's julio4_asflown_sim block (the actual as-flown numbers). Dry CG is approximated from the Brasil-config value (no July4-specific CG measurement exists). See PROGRESS.md for the full breakdown.").classes("text-sm text-gray-500 mt-1")

        ui.label("V2 - LASC 2026 (Iacanga)").classes("text-lg font-bold mt-4")
        with ui.grid(columns=4).classes("gap-4"):
            for label, value in [("Predicted", "1196.9 m"), ("Real flight", "1137 m"), ("Error", "+5.3%"), ("Status", "FAIL (just outside 5%)")]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-lg font-bold")
        ui.label('Mass = 10.370 kg (measured). At the Launch Readiness Review, LASC officials independently re-simulated this vehicle and predicted 1138 m (-0.09% vs. the real flight, CRS 10.2.1). We did NOT reproduce their exact inputs - this is our own independent replication, not a claim of matching their number.').classes("text-sm text-gray-500 mt-1")

        ui.label("Code-to-code check vs. OpenRocket").classes("text-lg font-bold mt-4")
        ui.label("Separately, reproducing OpenRocket's own two CSV-exported sims with its EXACT inputs (no weather uncertainty at all) still shows a +9-10% gap. Reference area, Cd-curve values, motor impulse, atmosphere density and gravity were all checked and matched to <0.1-0.5%. The root cause is not yet isolated - see PROGRESS.md 'Item 1 findings' for the full diagnostic table.").classes("text-sm")

        ui.label("What this means for you").classes("text-lg font-bold mt-4")
        ui.label("Numbers from this app (apogee, Monte Carlo intervals, RCSM compliance) are useful for design iteration and relative comparisons (does this change help or hurt?), but should not yet be treated as an accurate absolute prediction for a real launch. Do not submit these numbers to LASC as final without closing the gap above.").classes("text-sm")
