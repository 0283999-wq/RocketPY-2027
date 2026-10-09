"""The "RCSM Cases" page: the four case buttons + compliance checklist."""
import os

from nicegui import ui

from bup_rocketpy.gui import components, layout, state
from bup_rocketpy import competition_profiles, flutter, rcsm, rcsm_cases

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

        # 2026-10-09 review item 8: RKT 1.1.2 used to hardcode
        # payload_mass_kg=1.0 for every rocket - let the operator pick
        # which point-mass components in the .ork ARE the payload, or
        # type the mass directly (which always wins when non-empty).
        parsed = s["load_result"].parsed_ork
        with components.card(classes="w-full mt-2"):
            ui.label("RKT 1.1.2 payload mass").classes("font-bold")
            if parsed.point_masses:
                ui.label("Check which of this rocket's point-mass components are the competition payload:").classes("text-sm").style("color: var(--bup-muted)")
                payload_checks = {}
                with ui.row().classes("flex-wrap gap-3"):
                    for pm in parsed.point_masses:
                        checked = pm.name in s["payload_component_names"] or "payload" in pm.name.lower() or "carga" in pm.name.lower()
                        cb = ui.checkbox(f"{pm.name} ({pm.mass*1000:.0f} g)", value=checked)
                        payload_checks[pm.name] = cb

                def _sync_payload_checks():
                    s["payload_component_names"] = [name for name, cb in payload_checks.items() if cb.value]
                for cb in payload_checks.values():
                    cb.on_value_change(lambda _: _sync_payload_checks())
                _sync_payload_checks()  # pre-seed from the default-checked boxes above, not just on the next click
            else:
                ui.label("No point-mass components found in this .ork to pick from - type the payload mass directly below.").classes("text-sm").style("color: var(--bup-muted)")
            payload_override_input = ui.number(label="Or type the payload mass directly (kg) - wins over the checkboxes above when set", value=s["payload_mass_override_kg"])

        # STR 6.3.2 fin flutter - hand formula by default (editable shear
        # modulus + its source), or a real external-tool result that
        # always takes priority when given.
        with components.card(classes="w-full mt-2"):
            ui.label("STR 6.3.2 fin flutter velocity").classes("font-bold")
            ui.label("Hand formula (NACA TN 4197 approximation) by default - a screening estimate, not a substitute for a real structural analysis on a flight-critical vehicle.").classes("text-sm").style("color: var(--bup-muted)")
            with ui.row().classes("items-end gap-3"):
                material_select = ui.select(
                    list(flutter.COMMON_SHEAR_MODULI_PA.keys()), label="Fin material (shear modulus source)",
                    value=s["flutter_shear_modulus_source"] if s["flutter_shear_modulus_source"] in flutter.COMMON_SHEAR_MODULI_PA else "G10/G12 fiberglass (typical)",
                ).classes("w-72")
                shear_modulus_input = ui.number(label="Shear modulus G (Pa)", value=s["flutter_shear_modulus_pa"] or flutter.COMMON_SHEAR_MODULI_PA[material_select.value]).classes("w-48")

                def _material_changed(e):
                    shear_modulus_input.value = flutter.COMMON_SHEAR_MODULI_PA[e.value]
                material_select.on_value_change(_material_changed)
            with ui.row().classes("items-end gap-3"):
                flutter_override_input = ui.number(label="Or type a flutter velocity from an external tool (m/s) - always wins when set", value=s["flutter_manual_override_ms"]).classes("w-80")
                flutter_override_source_input = ui.input(label="Source (e.g. 'ANSYS run 2026-10-01', 'AEROLAB')", value=s["flutter_manual_override_source"] or "").classes("w-80")

        components.button("Run all 4 cases", kind="primary", icon="play_arrow", on_click=lambda: run_cases())
        results_container = ui.column().classes("w-full mt-4")

        def run_cases():
            s["payload_mass_override_kg"] = payload_override_input.value
            s["flutter_shear_modulus_pa"] = shear_modulus_input.value
            s["flutter_shear_modulus_source"] = material_select.value
            s["flutter_manual_override_ms"] = flutter_override_input.value
            s["flutter_manual_override_source"] = flutter_override_source_input.value

            payload_mass_kg = (
                payload_override_input.value if payload_override_input.value
                else sum(pm.mass for pm in parsed.point_masses if pm.name in s["payload_component_names"])
            )

            results = rcsm_cases.run_all_cases(
                parsed, s["load_result"].parsed_eng, s["load_result"].eng_path,
                s["load_result"].power_off_drag_path, s["load_result"].power_on_drag_path,
                s["dry_mass_kg"], s["dry_cg_m"],
                i_axial_override=s["dry_i_axial_kgm2"], i_transverse_override=s["dry_i_transverse_kgm2"],
            )
            s["case_results"] = results

            category = rcsm.CATEGORIES[category_select.value]
            nominal = results["Nominal"]
            flutter_result = None
            if nominal.flight is not None:
                env = nominal.flight.env
                flutter_result = flutter.worst_case_flutter(
                    parsed, env.speed_of_sound(env.elevation), env.pressure(env.elevation),
                    shear_modulus_pa=shear_modulus_input.value, shear_modulus_source=material_select.value,
                    manual_override_ms=flutter_override_input.value or None, manual_override_source=flutter_override_source_input.value or None,
                )
            compliance_rows = rcsm.check_compliance(
                category, nominal.flight, nominal.flight.rocket, payload_mass_kg=payload_mass_kg,
                fin_flutter_velocity=flutter_result.flutter_velocity_ms if flutter_result else None,
            ) if nominal.flight else []
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
                    if flutter_result is not None:
                        ui.label(
                            f"Flutter velocity used above: {flutter_result.flutter_velocity_ms:.1f} m/s "
                            f"({flutter_result.source}" +
                            (f", G={flutter_result.shear_modulus_pa/1e9:.2f} GPa ({flutter_result.shear_modulus_source})" if flutter_result.shear_modulus_pa else "") +
                            ")"
                        ).classes("text-xs mt-2").style("color: var(--bup-muted)")
            components.finish_motion()
