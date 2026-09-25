"""The "History" page: every run saved automatically to runs/. List,
reopen, delete, and compare two runs side by side.
"""
import os

from nicegui import ui

from bup_rocketpy.gui import layout
from bup_rocketpy import run_history

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@ui.page("/history")
def history_page():
    with layout.layout("History", current_path="/history"):
        records, warnings = run_history.list_runs(REPO_ROOT)
        for w in warnings:
            ui.label(f"⚠ {w}").classes("text-orange-600 text-sm")

        if not records:
            ui.label("No runs saved yet - every Simulate on the Simulate page is saved here automatically.").classes("text-gray-500")
            return

        selected = {"a": None, "b": None}
        compare_container = ui.column().classes("w-full mt-4")

        def render_table():
            nonlocal records
            records, warnings = run_history.list_runs(REPO_ROOT)
            table_container.clear()
            if not records:
                with table_container:
                    ui.label("No runs left.").classes("text-gray-500")
                return
            with table_container:
                ui.table(
                    columns=[{"name": "run_id", "label": "Run", "field": "run_id"},
                             {"name": "vehicle", "label": "Vehicle", "field": "vehicle"},
                             {"name": "apogee", "label": "Apogee (m)", "field": "apogee"},
                             {"name": "margin", "label": "Min margin (cal)", "field": "margin"},
                             {"name": "stable", "label": "Stable", "field": "stable"}],
                    rows=[{"run_id": r.run_id, "vehicle": r.vehicle_name, "apogee": f"{r.apogee_agl_m:.1f}", "margin": f"{r.min_static_margin_cal:.2f}", "stable": "YES" if r.is_stable else "NO"} for r in records],
                ).classes("w-full")

            with ui.row().classes("mt-2"):
                run_ids = [r.run_id for r in records]
                a_select = ui.select(run_ids, label="Compare A", value=run_ids[0] if run_ids else None)
                b_select = ui.select(run_ids, label="Compare B", value=run_ids[1] if len(run_ids) > 1 else None)

                def do_compare():
                    ra = run_history.get_run(REPO_ROOT, a_select.value)
                    rb = run_history.get_run(REPO_ROOT, b_select.value)
                    compare_container.clear()
                    if ra is None or rb is None:
                        with compare_container:
                            ui.label("Could not load one of the selected runs.").classes("text-red-600")
                        return
                    with compare_container:
                        with ui.grid(columns=3).classes("gap-4"):
                            ui.label("Field").classes("font-bold")
                            ui.label(ra.run_id).classes("font-bold")
                            ui.label(rb.run_id).classes("font-bold")
                            for field, fmt in [("apogee_agl_m", "{:.1f} m"), ("max_speed_ms", "{:.1f} m/s"), ("min_static_margin_cal", "{:.2f} cal"), ("dry_mass_kg", "{:.4f} kg")]:
                                ui.label(field)
                                ui.label(fmt.format(getattr(ra, field)))
                                ui.label(fmt.format(getattr(rb, field)))

                ui.button("Compare", on_click=do_compare)

                def do_delete():
                    run_history.delete_run(REPO_ROOT, a_select.value)
                    ui.notify(f"Deleted {a_select.value}")
                    render_table()
                ui.button("Delete A", on_click=do_delete, color="negative")

        table_container = ui.column().classes("w-full")
        render_table()
