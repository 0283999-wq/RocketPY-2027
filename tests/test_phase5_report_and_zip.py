"""Phase 5: PDF/DOCX report (validation section first, worded per
CLAUDE.md Sec 3.1) and the LASC .zip package."""
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stella_flight import lasc_package, rcsm, rcsm_cases, report, translate
from stella_flight.motor_reader import read_eng
from stella_flight.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_phase5_report_and_zip")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _build_common():
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    results = rcsm_cases.run_all_cases(parsed, eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    category = rcsm.CATEGORIES["1km_solid"]
    rows = rcsm.check_compliance(category, results["Nominal"].flight, results["Nominal"].flight.rocket, payload_mass_kg=1.0)
    return parsed, eng, results, rows


def test_docx_report_has_validation_section_worded_correctly():
    parsed, eng, results, rows = _build_common()
    path = report.generate_docx(os.path.join(OUT_DIR, "report.docx"), "44", "PROMETEO", results, rows, None, ["test assumption"])
    assert os.path.exists(path) and os.path.getsize(path) > 1000
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "PROVISIONAL" in full_text
    assert "1138" in full_text and "officials" in full_text.lower(), "must credit the officials' own prediction, not claim it as ours (CLAUDE.md Sec 3.1 wording rule)"
    assert "our rocketpy predicted 1,138" not in full_text.lower(), "forbidden wording per CLAUDE.md Sec 3.1"


def test_pdf_report_generates():
    parsed, eng, results, rows = _build_common()
    path = report.generate_pdf(os.path.join(OUT_DIR, "report.pdf"), "44", "PROMETEO", results, rows, None, ["test assumption"])
    assert os.path.exists(path) and os.path.getsize(path) > 1000


def test_lasc_zip_contains_expected_files():
    parsed, eng, results, rows = _build_common()
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(parsed, mass_est)
    radius = next(t.radius for t in parsed.body_tubes if t.radius)
    zip_path = os.path.join(OUT_DIR, "Mission44_LASC.zip")
    lasc_package.build_lasc_zip(zip_path, "44", parsed, eng, ENG_PATH, ORK_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
                                 DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, cases=[("Ballistic", False), ("Nominal", True)])
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "Mission44_Ballistic_RocketPy_v1.py" in names
    assert "Mission44_Nominal_RocketPy_v1.py" in names
    assert "Icarus_I_K519.eng" in names
    assert "PrometeoLasc2026.ork" in names
    assert "power_off_drag.csv" in names and "power_on_drag.csv" in names
    assert "README.txt" in names
    assert not os.path.exists(zip_path[:-4] + "_staging"), "staging dir should be cleaned up after zipping"


if __name__ == "__main__":
    test_docx_report_has_validation_section_worded_correctly()
    test_pdf_report_generates()
    test_lasc_zip_contains_expected_files()
    print("\nPHASE 5 REPORT + ZIP: OK")
