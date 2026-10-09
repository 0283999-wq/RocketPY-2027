"""2026-10-09 review item 5: "File name: let me type it, default
'<RocketName>_<Site>_<YYYY-MM-DD>_Simulation_Report.pdf/.docx' (never
'report (7).docx'). Mission ID default empty, not 0. PDF: omit it when
empty. DOCX: '[EDIT: Mission ID]'."

Uses PROMETEO's real .ork (no invented rocket).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import rcsm_cases, report
from bup_rocketpy.gui import pipeline
from bup_rocketpy.gui.pages.exports_page import _sanitize_filename

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_report_filename_and_mission_id")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _build_data(mission_id):
    os.makedirs(OUT_DIR, exist_ok=True)
    load_result = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim_result = pipeline.run_simulation(load_result, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    case_results = rcsm_cases.run_all_cases(load_result.parsed_ork, load_result.parsed_eng, load_result.eng_path, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    return report.build_report_data(mission_id, "Test Author", load_result, sim_result, case_results, None, None, OUT_DIR)


def test_empty_mission_id_gives_an_empty_phrase_not_mission_blank():
    data = _build_data("")
    assert data["mission_id_phrase"] == ""


def test_set_mission_id_gives_a_real_phrase():
    data = _build_data("44")
    assert data["mission_id_phrase"] == "Mission 44 - "


def test_docx_marks_mission_id_for_edit_only_when_empty():
    data_empty = _build_data("")
    out_empty = os.path.join(OUT_DIR, "report_no_mission.docx")
    report.generate_docx(out_empty, data_empty)
    assert os.path.exists(out_empty)

    data_set = _build_data("44")
    out_set = os.path.join(OUT_DIR, "report_with_mission.docx")
    report.generate_docx(out_set, data_set)
    assert os.path.exists(out_set)

    import docx
    text_empty = "\n".join(p.text for p in docx.Document(out_empty).paragraphs)
    text_set = "\n".join(p.text for p in docx.Document(out_set).paragraphs)
    assert "[EDIT: Mission ID]" in text_empty
    assert "[EDIT: Mission ID]" not in text_set
    assert "Mission 44" in text_set


def test_pdf_omits_mission_id_entirely_when_empty():
    data = _build_data("")
    out_path = os.path.join(OUT_DIR, "report_no_mission.pdf")
    report.generate_pdf(out_path, data)
    assert os.path.exists(out_path)
    import pypdf
    all_text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(out_path).pages)
    assert "Mission " not in all_text or "Mission -" not in all_text  # no dangling "Mission" with nothing after it


def test_sanitize_filename_strips_windows_illegal_characters_and_never_returns_empty():
    assert _sanitize_filename('Rocket "PEZ" / Payload: 4" chute') == "Rocket_PEZ_Payload_4_chute"
    assert _sanitize_filename("") == "Simulation_Report"
    assert _sanitize_filename("   ") == "Simulation_Report"
    assert _sanitize_filename("A  B  C") == "A_B_C"


if __name__ == "__main__":
    test_empty_mission_id_gives_an_empty_phrase_not_mission_blank()
    test_set_mission_id_gives_a_real_phrase()
    test_docx_marks_mission_id_for_edit_only_when_empty()
    test_pdf_omits_mission_id_entirely_when_empty()
    test_sanitize_filename_strips_windows_illegal_characters_and_never_returns_empty()
    print("\nREPORT FILENAME AND MISSION ID: OK")
