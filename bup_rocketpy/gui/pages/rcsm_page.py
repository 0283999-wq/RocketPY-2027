"""The "RCSM Cases" page: the four case buttons + compliance checklist."""
import os

from nicegui import ui

from bup_rocketpy.gui import layout, state
from bup_rocketpy import competition_profiles, rcsm, rcsm_cases

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")

CATEGORY_OPTIONS = list(rcsm.CATEGORIES.keys())


@ui.page("/rcsm")
def rcsm_case_page():
    with layout.layout("RCSM Cases", current_path="/rcsm"):
        if s["load_result"] is None or s["sim_result"] is None:
            ui.label("Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).").classes("text-gray-500")
            return

        profile = competition_profiles.get_profile(s["competition_profile"])
        if profile.compliance_ruleset != "RCSM_ED7_REV1":
            ui.label(f"{profile.display_name}: {profile.rules_status}").classes("bup-provisional-badge px-3 py-2 rounded font-bold")
        ui.label("The checks below are always RCSM Ed.7 Rev.1 (the only ruleset this app implements) - for a non-LASC profile they're a reference only, not a verified pass/fail for that competition.").classes("text-xs text-gray-500")

        category_select = ui.select(CATEGORY_OPTIONS, value="1km_solid", label="RCSM category").classes("w-64")
        results_container = ui.column().classes("w-full mt-4")

        def run_cases():
            parsed = s["load_result"].parsed_ork
            results = rcsm_cases.run_all_cases(
                parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                s["dry_mass_kg"], s["dry_cg_m"],
                i_axial_override=s["dry_i_axial_kgm2"], i_transverse_override=s["dry_i_transverse_kgm2"],
            )
            s["case_results"] = results

            category = rcsm.CATEGORIES[category_select.value]
            nominal = results["Nominal"]
            compliance_rows = rcsm.check_compliance(category, nominal.flight, nominal.flight.rocket, payload_mass_kg=1.0) if nominal.flight else []
            s["compliance_rows"] = compliance_rows

            results_container.clear()
            with results_container:
                ui.label("Case results").classes("text-lg font-bold")
                with ui.grid(columns=4).classes("gap-4"):
                    for name, r in results.items():
                        with ui.card():
                            ui.label(name).classes("font-bold")
                            if r.flight is None:
                                ui.label("NOT BUILT").classes("text-red-600")
                            else:
                                ui.label(f"Apogee AGL: {r.flight.apogee - r.flight.env.elevation:.1f} m")
                                ui.label(f"Rail exit: {r.flight.out_of_rail_velocity:.1f} m/s")
                            if r.warning:
                                ui.label(r.warning).classes("text-xs text-orange-600 mt-1")

                ui.label("RCSM compliance (Nominal case)").classes("text-lg font-bold mt-4")
                ui.table(
                    columns=[{"name": "rule", "label": "Rule", "field": "rule"},
                             {"name": "check", "label": "Check", "field": "check"},
                             {"name": "status", "label": "Status", "field": "status"},
                             {"name": "detail", "label": "Detail", "field": "detail"}],
                    rows=[{"rule": r[0], "check": r[1], "status": r[2], "detail": r[3]} for r in compliance_rows],
                ).classes("w-full")

        ui.button("Run all 4 cases", on_click=run_cases)
