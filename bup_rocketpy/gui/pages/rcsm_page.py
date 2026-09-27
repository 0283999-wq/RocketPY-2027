"""The "RCSM Cases" page: the four case buttons + compliance checklist."""
import os

from nicegui import ui

from bup_rocketpy.gui import components, layout, state
from bup_rocketpy import competition_profiles, rcsm, rcsm_cases

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")

CATEGORY_OPTIONS = list(rcsm.CATEGORIES.keys())
_STATUS_ICON = {"PASS": ("check_circle", "good"), "FAIL": ("cancel", "bad"), "WARN": ("warning", "warn")}


@ui.page("/rcsm")
def rcsm_case_page():
    with layout.layout("RCSM Cases", current_path="/rcsm"):
        components.page_header("RCSM Cases", "The four required flight cases, plus an automatic compliance checklist.")
        if s["load_result"] is None or s["sim_result"] is None:
            components.empty_state("checklist", "Load files and click Simulate on the Simulate page first (no manual override needed - the default path works from the .ork alone).", action_label="Go to Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            return

        profile = competition_profiles.get_profile(s["competition_profile"])
        if profile.compliance_ruleset != "RCSM_ED7_REV1":
            components.status_chip(f"{profile.display_name}: {profile.rules_status}", "warning")
        ui.label("The checks below are always RCSM Ed.7 Rev.1 (the only ruleset this app implements) - for a non-LASC profile they're a reference only, not a verified pass/fail for that competition.").classes("text-xs").style("color: var(--bup-muted)")

        category_select = ui.select(CATEGORY_OPTIONS, value="1km_solid", label="RCSM category").classes("w-64")
        components.button("Run all 4 cases", kind="primary", icon="play_arrow", on_click=lambda: run_cases())
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
                with ui.grid(columns=4).classes("gap-3 w-full"):
                    for i, (name, r) in enumerate(results.items()):
                        with components.card(stagger_index=i):
                            with ui.row().classes("items-center justify-between w-full"):
                                ui.label(name).classes("font-bold")
                                components.status_chip("NOT BUILT" if r.flight is None else "OK", "bad" if r.flight is None else "success")
                            if r.flight is not None:
                                ui.label(f"Apogee AGL: {r.flight.apogee - r.flight.env.elevation:.1f} m").classes("text-sm")
                                ui.label(f"Rail exit: {r.flight.out_of_rail_velocity:.1f} m/s").classes("text-sm")
                            if r.warning:
                                ui.label(r.warning).classes("text-xs mt-1").style("color: var(--bup-warning)")

                with components.card(classes="w-full mt-2"):
                    ui.label("RCSM compliance (Nominal case)").classes("font-bold")
                    for row in compliance_rows:
                        rule, check, status, detail = row[0], row[1], row[2], row[3]
                        icon_name, kind = _STATUS_ICON.get(status, ("help", "neutral"))
                        with ui.row().classes("items-center gap-2 w-full py-1 border-b").style("border-color: var(--bup-border)"):
                            ui.icon(icon_name).style(f"color: var(--bup-{'success' if kind == 'good' else 'error' if kind == 'bad' else 'warning' if kind == 'warn' else 'muted'})")
                            with ui.column().classes("gap-0 flex-1"):
                                ui.label(f"{rule} - {check}").classes("text-sm font-medium")
                                ui.label(detail).classes("text-xs").style("color: var(--bup-muted)")
                            components.status_chip(status, kind if kind != "neutral" else "neutral")
            components.finish_motion()
