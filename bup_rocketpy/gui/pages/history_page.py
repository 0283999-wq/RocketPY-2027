"""The "History" page: every run saved automatically to runs/. A list
with per-row actions (view/reopen/delete) and a 2-run compare picker;
click a run for its full detail page (2026-09-27 review item 4).
"""
import glob
import os

from nicegui import ui

from bup_rocketpy.gui import layout, state
from bup_rocketpy import run_history

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
s = state.state


def _reopen_mission(run_id):
    """Shared by the list row action and the detail page's own button -
    installs a saved mission's files+settings into state.state and jumps
    to Simulate, matching every key gui/state.py's dict already has."""
    try:
        reopened = run_history.reopen_run(REPO_ROOT, run_id, os.path.join(os.getcwd(), "outputs", "gui_run"))
    except run_history.MissionNotReopenableError as exc:
        ui.notify(str(exc), type="negative", multi_line=True, timeout=0)
        return
    s["load_result"] = reopened["load_result"]
    s["ork_path"] = reopened["ork_path"]
    s["ork_filename"] = reopened["ork_filename"]
    s["eng_filename"] = reopened["eng_filename"]
    s["dry_mass_override"] = reopened["dry_mass_override"]
    s["dry_cg_override"] = reopened["dry_cg_override"]
    s["launch_override"] = reopened["launch_override"]
    s["competition_profile"] = reopened["competition_profile"]
    s["vehicle_name"] = reopened["vehicle_name"]
    s["mission_id"] = reopened["mission_id"]
    s["report_text"] = reopened["report_text"]
    s["current_run_id"] = reopened["current_run_id"]
    # A reopened mission has no fresh Simulate result yet - every page
    # that reads dry_mass_kg/dry_cg_m/sim_result must see "not simulated
    # yet", not stale numbers from whatever was loaded before.
    s["sim_result"] = None
    s["dry_mass_kg"] = reopened["dry_mass_override"]
    s["dry_cg_m"] = reopened["dry_cg_override"]
    s["mass_source"] = ""
    s["dry_i_axial_kgm2"] = None
    s["dry_i_transverse_kgm2"] = None
    s["case_results"] = None
    s["compliance_rows"] = None
    s["mc_result"] = None
    ui.notify(f"Reopened mission '{run_id}' - click Simulate to fly it.", type="positive")
    ui.navigate.to("/")


@ui.page("/history")
def history_page():
    with layout.layout("History", current_path="/history"):
        records, warnings = run_history.list_runs(REPO_ROOT)
        for w in warnings:
            ui.label(f"⚠ {w}").classes("text-orange-600 text-sm")

        if not records:
            ui.label("No runs saved yet - every Simulate on the Simulate page is saved here automatically.").classes("text-gray-500")
            return

        current_hash = run_history.current_app_commit_hash(REPO_ROOT)
        current_only_checkbox = ui.checkbox("Only show runs from the current app version")
        compare_selection = []  # up to 2 run_ids, in click order
        table_container = ui.column().classes("w-full mt-2")
        compare_container = ui.column().classes("w-full mt-4")

        def render_compare():
            compare_container.clear()
            if len(compare_selection) != 2:
                return
            ra = run_history.get_run(REPO_ROOT, compare_selection[0])
            rb = run_history.get_run(REPO_ROOT, compare_selection[1])
            with compare_container:
                if ra is None or rb is None:
                    ui.label("Could not load one of the selected runs.").classes("text-red-600")
                    return
                with ui.grid(columns=3).classes("gap-4"):
                    ui.label("Field").classes("font-bold")
                    ui.label(ra.run_id).classes("font-bold")
                    ui.label(rb.run_id).classes("font-bold")
                    for field, fmt in [("apogee_agl_m", "{:.1f} m"), ("max_speed_ms", "{:.1f} m/s"), ("min_static_margin_cal", "{:.2f} cal"), ("dry_mass_kg", "{:.4f} kg")]:
                        ui.label(field)
                        ui.label(fmt.format(getattr(ra, field)))
                        ui.label(fmt.format(getattr(rb, field)))

        def render_table():
            table_container.clear()
            shown = records if not current_only_checkbox.value else [r for r in records if r.app_commit_hash == current_hash]
            with table_container:
                if not shown:
                    ui.label("No runs match this filter.").classes("text-gray-500")
                    return
                for r in shown:
                    with ui.row().classes("items-center gap-3 w-full p-2 border-b"):
                        ui.checkbox(value=r.run_id in compare_selection).classes("mr-1").on_value_change(
                            lambda e, run_id=r.run_id: _toggle_compare(run_id, e.value)
                        )
                        with ui.column().classes("cursor-pointer flex-grow").on("click", lambda run_id=r.run_id: ui.navigate.to(f"/history/{run_id}")):
                            ui.label(f"{r.run_id} - {r.vehicle_name}").classes("font-bold")
                            older = " (OLDER APP VERSION)" if r.app_commit_hash not in (current_hash, "unknown") else ""
                            ui.label(f"Apogee {r.apogee_agl_m:.1f} m, margin {r.min_static_margin_cal:.2f} cal, {'stable' if r.is_stable else 'NOT stable'}{older}").classes("text-sm text-gray-500")
                        ui.button(icon="open_in_new", on_click=lambda run_id=r.run_id: ui.navigate.to(f"/history/{run_id}")).props("flat round").tooltip("View detail")

                        def make_delete(run_id):
                            def confirm_delete():
                                run_history.delete_run(REPO_ROOT, run_id)
                                ui.notify(f"Deleted {run_id}")
                                nonlocal records
                                records[:] = [rec for rec in records if rec.run_id != run_id]
                                if run_id in compare_selection:
                                    compare_selection.remove(run_id)
                                dialog.close()
                                render_table()
                                render_compare()

                            with ui.dialog() as dialog, ui.card():
                                ui.label(f"Delete run '{run_id}'? This cannot be undone.")
                                with ui.row():
                                    ui.button("Cancel", on_click=dialog.close)
                                    ui.button("Delete", color="negative", on_click=confirm_delete)
                            dialog.open()

                        ui.button(icon="delete", on_click=lambda run_id=r.run_id: make_delete(run_id)).props("flat round color=negative").tooltip("Delete")

                if any(r.app_commit_hash not in (current_hash, "unknown") for r in shown):
                    ui.label(f"Some runs above were made with an OLDER app version than the one running now ({current_hash}) - re-run them if you need numbers comparable to today's.").classes("text-orange-600 text-sm mt-1")

        def _toggle_compare(run_id, checked):
            if checked:
                if run_id not in compare_selection:
                    compare_selection.append(run_id)
                if len(compare_selection) > 2:
                    compare_selection.pop(0)
            elif run_id in compare_selection:
                compare_selection.remove(run_id)
            render_table()
            render_compare()

        current_only_checkbox.on_value_change(lambda _: render_table())
        do_cleanup_button_container = ui.row()
        with do_cleanup_button_container:
            def do_cleanup():
                moved = run_history.cleanup_corrupt_runs(REPO_ROOT)
                ui.notify(f"Moved {len(moved)} corrupt run(s) to runs/_corrupt/" if moved else "No corrupt runs found.")
                nonlocal records
                records, _ = run_history.list_runs(REPO_ROOT)
                render_table()
            ui.button("Clean up corrupt runs", on_click=do_cleanup, color="warning")

        render_table()


@ui.page("/history/{run_id}")
def history_detail_page(run_id: str):
    with layout.layout(f"History - {run_id}", current_path="/history"):
        record = run_history.get_run(REPO_ROOT, run_id)
        if record is None:
            ui.label(f"Run '{run_id}' not found (it may have been deleted).").classes("text-red-600")
            ui.link("Back to History", "/history")
            return

        current_hash = run_history.current_app_commit_hash(REPO_ROOT)
        ui.link("< Back to History", "/history").classes("text-sm")
        ui.label(f"{record.vehicle_name} - {run_id}").classes("text-xl font-bold mt-2")
        ui.label(record.timestamp).classes("text-sm text-gray-500")
        if record.app_commit_hash not in (current_hash, "unknown"):
            ui.label(f"Made with an OLDER app version ({record.app_commit_hash}) than the one running now ({current_hash}) - reopen and re-run for numbers comparable to today's.").classes("bup-provisional-badge px-3 py-1 rounded font-bold inline-block")

        ui.button("Reopen this mission", on_click=lambda: _reopen_mission(run_id), color="primary").classes("mt-2")
        if not record.ork_saved:
            ui.label("This run predates mission persistence - no saved .ork, so it can't be reopened (view only).").classes("text-xs text-orange-600")

        ui.label("Results").classes("text-lg font-bold mt-4")
        with ui.grid(columns=4).classes("gap-4"):
            for label, value in [
                ("Apogee AGL", f"{record.apogee_agl_m:.1f} m"),
                ("Max speed", f"{record.max_speed_ms:.1f} m/s"),
                ("Max Mach", f"{record.max_mach:.2f}" + (" EXTRAPOLATED" if record.mach_extrapolated else "") if record.max_mach is not None else "-"),
                ("Min static margin", f"{record.min_static_margin_cal:.2f} cal"),
                ("Stable?", "YES" if record.is_stable else "NO"),
                ("Dry mass / CG", f"{record.dry_mass_kg:.4f} kg / {record.dry_cg_m:.4f} m"),
            ]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-lg font-bold")

        ui.label("Settings used").classes("text-lg font-bold mt-4")
        with ui.grid(columns=3).classes("gap-4"):
            for label, value in [
                ("Mass/CG override", f"{record.dry_mass_override_kg:.4f} kg / {record.dry_cg_override_m:.4f} m" if record.dry_mass_override_kg is not None else "none (used the best-available estimate)"),
                ("Weather override", "active" if record.launch_override else "none (.ork's own recorded conditions)"),
                ("Competition profile", record.competition_profile or "lasc"),
                ("Site (lat, lon)", f"{record.site_lat:.3f}, {record.site_lon:.3f}" if record.site_lat is not None else "-"),
                ("Motor", record.motor_designation or "-"),
                ("Drag curve source", record.drag_curve_source or "-"),
            ]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(value).classes("text-md font-bold")

        if record.reefing_settings:
            reefed = [c for c in record.reefing_settings if c.get("is_reefed")]
            if reefed:
                ui.label("Reefed parachutes").classes("text-md font-bold mt-2")
                for c in reefed:
                    ui.label(f"{c['name']}: reefed {c['reefed_diameter_m']:.2f} m / Cd {c['reefed_cd']:.2f}, cutter at {c['cutter_altitude_m']:.0f} m AGL").classes("text-sm")

        ui.label("Files used").classes("text-lg font-bold mt-4")
        with ui.grid(columns=2).classes("gap-4"):
            for label, value in [
                (".ork", f"{record.ork_filename} ({'saved' if record.ork_saved else 'not saved with this run'})"),
                (".eng", record.eng_filename),
                ("App version", record.app_commit_hash),
                ("File hashes (.ork/.eng)", f"{record.ork_file_hash or '-'} / {record.eng_file_hash or '-'}"),
            ]:
                with ui.card():
                    ui.label(label).classes("text-xs text-gray-500")
                    ui.label(str(value)).classes("text-sm font-bold")

        run_dir = run_history.run_dir_path(REPO_ROOT, run_id)
        csv_path = os.path.join(run_dir, "flight_data.csv")
        if os.path.exists(csv_path):
            ui.link("Download flight data CSV", f"/runs/{run_id}/flight_data.csv").classes("mt-2")

        plot_files = sorted(glob.glob(os.path.join(run_dir, "*.png")))
        if plot_files:
            ui.label("Plots").classes("text-lg font-bold mt-4")
            with ui.grid(columns=2).classes("gap-4"):
                for path in plot_files:
                    ui.image(path).classes("w-full")

        if record.notes:
            ui.label("Notes").classes("text-lg font-bold mt-4")
            ui.label(record.notes)
