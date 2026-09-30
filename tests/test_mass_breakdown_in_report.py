"""2026-09-30 review item 3: a full mass table (dry rocket, motor loaded/
propellant/dry, liftoff, descent) must be visible everywhere - locks in
that it reaches the report (both formats), not just the two GUI pages
(covered by inspection, not an automated test, since they need a live
NiceGUI page)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import report
from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_mass_breakdown_in_report")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _build_data():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    return report.build_report_data("44", "Test", lr, sim, {}, None, None, OUT_DIR), sim


def test_report_data_carries_the_full_mass_breakdown():
    data, sim = _build_data()
    v = data["vehicle"]
    assert v["dry_mass_kg"] == sim.dry_mass_kg
    assert v["motor_loaded_kg"] == sim.motor_loaded_kg
    assert v["motor_propellant_kg"] == sim.motor_propellant_kg
    assert v["motor_dry_kg"] == sim.motor_dry_kg
    assert abs(v["liftoff_mass_kg"] - (v["dry_mass_kg"] + v["motor_loaded_kg"])) < 1e-9
    assert abs(v["descent_mass_kg"] - (v["dry_mass_kg"] + v["motor_dry_kg"])) < 1e-9


def test_docx_report_contains_mass_breakdown_table():
    data, sim = _build_data()
    path = report.generate_docx(os.path.join(OUT_DIR, "report.docx"), data)
    from docx import Document
    doc = Document(path)
    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    assert "Mass breakdown" in "\n".join(p.text for p in doc.paragraphs)
    assert "Liftoff mass" in table_text and f"{sim.liftoff_mass_kg:.3f} kg" in table_text
    assert "Descent mass" in table_text and f"{sim.descent_mass_kg:.3f} kg" in table_text


if __name__ == "__main__":
    test_report_data_carries_the_full_mass_breakdown()
    test_docx_report_contains_mass_breakdown_table()
    print("\nMASS BREAKDOWN IN REPORT: OK")
