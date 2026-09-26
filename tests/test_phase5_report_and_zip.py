"""Phase 5 + 2026-09-26 review item D: the new simulation report (PDF/
DOCX, replacing the old compliance-style one) and the LASC .zip package.
"""
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import lasc_package, monte_carlo, rcsm_cases, report, translate
from bup_rocketpy.gui import pipeline
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_phase5_report_and_zip")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _build_common():
    load_result = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim_result = pipeline.run_simulation(load_result, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    case_results = rcsm_cases.run_all_cases(load_result.parsed_ork, load_result.parsed_eng, load_result.eng_path, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    return load_result, sim_result, case_results


def test_docx_report_builds_and_has_no_compliance_section():
    load_result, sim_result, case_results = _build_common()
    data = report.build_report_data("44", "Test Author", load_result, sim_result, case_results, None, None, OUT_DIR)
    path = report.generate_docx(os.path.join(OUT_DIR, "report.docx"), data)
    assert os.path.exists(path) and os.path.getsize(path) > 1000
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "RCSM compliance" not in full_text, "the compliance section must be REMOVED from the report per 2026-09-26 review item D - RCSM page only"
    assert "CLAUDE.md" not in full_text and "PROGRESS.md" not in full_text, "no internal jargon in a report a judge/teammate reads"
    assert "Executive summary" in full_text and "Propulsion" in full_text and "Recovery" in full_text


def test_docx_report_appendix_credits_lasc_officials_not_us():
    """The old wording rule survives, just moved: when the appendix IS
    included, it must credit the officials' own on-site prediction, never
    claim it as this app's own."""
    load_result, sim_result, case_results = _build_common()
    data = report.build_report_data("44", "", load_result, sim_result, case_results, None, None, OUT_DIR, include_appendix=True)
    path = report.generate_docx(os.path.join(OUT_DIR, "report_appendix.docx"), data)
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "1138" in full_text and "officials" in full_text.lower()
    assert "our rocketpy predicted 1,138" not in full_text.lower()


def test_pdf_report_generates_with_monte_carlo():
    load_result, sim_result, case_results = _build_common()
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(load_result.parsed_ork, mass_est)
    radius = next(t.radius for t in load_result.parsed_ork.body_tubes if t.radius)
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, 1855.9, load_result.parsed_ork.launch.wind_average_ms)
    mc_result = monte_carlo.run_monte_carlo(load_result.parsed_ork, load_result.parsed_eng, load_result.eng_path, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, uncertainties, n_simulations=5, output_dir=OUT_DIR)
    data = report.build_report_data("44", "", load_result, sim_result, case_results, mc_result, uncertainties, OUT_DIR)
    assert data["monte_carlo"]["low_n_warning"] is True, "N=5 must trigger the 'not statistically meaningful' warning"
    path = report.generate_pdf(os.path.join(OUT_DIR, "report.pdf"), data)
    assert os.path.exists(path) and os.path.getsize(path) > 1000


def test_lasc_zip_contains_expected_files():
    load_result, sim_result, case_results = _build_common()
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_ax, i_tr = translate.estimate_dry_inertia(load_result.parsed_ork, mass_est)
    radius = next(t.radius for t in load_result.parsed_ork.body_tubes if t.radius)
    zip_path = os.path.join(OUT_DIR, "Mission44_LASC.zip")
    lasc_package.build_lasc_zip(zip_path, "44", load_result.parsed_ork, load_result.parsed_eng, ENG_PATH, ORK_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
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
    test_docx_report_builds_and_has_no_compliance_section()
    test_docx_report_appendix_credits_lasc_officials_not_us()
    test_pdf_report_generates_with_monte_carlo()
    test_lasc_zip_contains_expected_files()
    print("\nPHASE 5 REPORT + ZIP: OK")
