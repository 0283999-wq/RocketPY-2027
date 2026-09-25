"""The "Validation" page: V1/V2 status, predicted vs. flight, and why
everything else in the app is PROVISIONAL. These numbers come from the
pytest suite (tests/test_phase2_validation.py and
tests/test_code_to_code_vs_openrocket.py), not a runtime computation
here - re-run pytest and update these if the underlying model changes;
this page is a display, not a live re-derivation, since V1/V2 represent
a specific, audited comparison whose inputs are documented in
PROGRESS.md, not something to silently recompute differently each page
load.

Updated 2026-09-25 review Section 3: both test files were rewritten to
go through bup_rocketpy.translate (the same functions the app itself
uses) instead of a separate hand-built rocket - see PROGRESS.md "Item 3"
for the full story and the 3 real bugs that were found and fixed along
the way (propellant mass, wind never applied, a stale duplicate in the
LASC export script).
"""
from nicegui import ui

from bup_rocketpy.gui import layout


@ui.page("/validation")
def validation_page():
    with layout.layout("Validation", current_path="/validation"):
        ui.label("PROVISIONAL").classes("bup-provisional-badge px-3 py-1 rounded font-bold inline-block")
        ui.label("Every result in this app is provisional until BOTH V1 and V2 pass within +-5%. Neither does yet.").classes("mt-2")

        ui.label("V1 - 2026-07-04 (Pachuca profile)").classes("text-lg font-bold mt-4")
        with ui.grid(columns=4).classes("gap-4"):
            for label, value in [("Predicted", "1136.5 m"), ("Real flight", "1019.9 m"), ("Error", "+11.4%"), ("Status", "FAIL (>5%)")]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-lg font-bold")
        ui.label("Mass/motor from verified_constants.json's julio4_asflown_sim block (the actual as-flown numbers). Dry CG is approximated from the Brasil-config value (no July4-specific CG measurement exists), and this case uses the REAL .ork's fin geometry (not a placeholder) - the leading remaining suspect, see PROGRESS.md Item 3.").classes("text-sm text-gray-500 mt-1")

        ui.label("V2 - LASC 2026 (Iacanga)").classes("text-lg font-bold mt-4")
        with ui.grid(columns=4).classes("gap-4"):
            for label, value in [("Predicted", "1071.1 m"), ("Real flight", "1137 m"), ("Error", "-5.8%"), ("Status", "FAIL (just outside 5%)")]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-lg font-bold")
        ui.label('Mass = 10.370 kg (measured). At the Launch Readiness Review, LASC officials independently re-simulated this vehicle and predicted 1138 m (-0.09% vs. the real flight, CRS 10.2.1). We did NOT reproduce their exact inputs - this is our own independent replication, not a claim of matching their number. Conditions are the .ork\'s OWN recorded wind/atmosphere, NOT the actual Iacanga flight-day weather (still pending from Diego) - see below for why that is now the leading suspect for this gap.').classes("text-sm text-gray-500 mt-1")

        ui.label("Code-to-code check vs. OpenRocket").classes("text-lg font-bold mt-4")
        ui.label("Reproducing OpenRocket's own CSV-exported sim with its EXACT inputs (no weather uncertainty at all, same site/rail/mass/wind the .ork itself recorded) now passes at -1.45% (was +10.17%) - three real bugs were found and fixed: build_motor's propellant mass was 18.8% low, wind was parsed but never actually applied (a rocketpy quirk silently no-ops wind_u/wind_v for the standard_atmosphere model), and the LASC-export script generator had its own stale, unsynced copy of both. See PROGRESS.md 'Item 3' for the full before/after table.").classes("text-sm")
        ui.label("Because that zero-weather-uncertainty case now passes tightly, V2's remaining -5.8% gap (above) increasingly looks like a real difference between the .ork's recorded weather and the actual Iacanga flight-day conditions, not a code bug - it needs Diego's real weather data to resolve further, not more code changes.").classes("text-sm text-gray-500 mt-1")

        ui.label("What this means for you").classes("text-lg font-bold mt-4")
        ui.label("Numbers from this app (apogee, Monte Carlo intervals, RCSM compliance) are useful for design iteration and relative comparisons (does this change help or hurt?), but should not yet be treated as an accurate absolute prediction for a real launch. Do not submit these numbers to LASC as final without closing the gap above.").classes("text-sm")
