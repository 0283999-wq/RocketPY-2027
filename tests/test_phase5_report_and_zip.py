"""Phase 5 + 2026-09-26/27 review items D and 6: the simulation report
(PDF/DOCX, real prose + real TOC + annotated figures, not a numbers dump)
and the LASC .zip package.
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


def test_docx_report_has_real_sections_and_no_jargon():
    load_result, sim_result, case_results = _build_common()
    data = report.build_report_data("44", "Test Author", load_result, sim_result, case_results, None, None, OUT_DIR)
    path = report.generate_docx(os.path.join(OUT_DIR, "report.docx"), data)
    assert os.path.exists(path) and os.path.getsize(path) > 1000
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "RCSM compliance" not in full_text, "the compliance table only appears in the optional Appendix, off by default"
    for jargon in ("CLAUDE.md", "PROGRESS.md", "Rule 3", "Phase 5"):
        assert jargon not in full_text, f"no internal jargon ({jargon!r}) in a report a judge/teammate reads"
    # 2026-09-29 review item 4: report rewritten as HTML->PDF/DOCX with
    # the mega-prompt's own section numbering; "Deliverables and setup"
    # became "General information and set-up", and flight-test
    # correlation moved into the optional Appendix B (not asserted here
    # since include_appendix defaults to False).
    for section in ("General information and set-up", "Vehicle configuration", "Propulsion", "Trajectory",
                     "Aerodynamics", "Stability", "Recovery", "Monte Carlo", "Discussion and conclusions",
                     "Files delivered"):
        assert section in full_text, f"missing section {section!r}"


def test_docx_report_has_data_driven_prose_and_barrowman_check():
    """2026-09-27 review item 6: a real report, not a data dump - every
    section needs written paragraphs, not just tables/pictures."""
    load_result, sim_result, case_results = _build_common()
    data = report.build_report_data("44", "Test Author", load_result, sim_result, case_results, None, None, OUT_DIR)
    assert data["barrowman"] is not None, "PROMETEO has a nose + fins - the hand Barrowman check should compute"
    assert data["barrowman"]["rocketpy_cp_m"] is not None
    assert abs(data["barrowman"]["diff_pct"]) < 10, "hand Barrowman CP should be in the same ballpark as RocketPy's own"
    path = report.generate_docx(os.path.join(OUT_DIR, "report_prose.docx"), data)
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Figure 1." in full_text and "Figure 2." in full_text, "figures must be numbered and captioned"
    assert "Barrowman" in full_text
    assert data["vehicle_name"] in full_text
    assert f"{sim_result.apogee_agl_m:.1f}" in full_text, "prose should cite the actual computed apogee, not a placeholder"


def test_docx_report_editable_text_blocks_are_used_verbatim():
    load_result, sim_result, case_results = _build_common()
    report_text = {
        "introduction": "CUSTOM INTRO TEXT FOR TEST.",
        "conclusions": "CUSTOM CONCLUSION TEXT FOR TEST.",
    }
    data = report.build_report_data("44", "Test Author", load_result, sim_result, case_results, None, None, OUT_DIR, report_text=report_text)
    assert data["report_text"]["introduction"] == "CUSTOM INTRO TEXT FOR TEST."
    assert data["report_text"]["conclusions"] == "CUSTOM CONCLUSION TEXT FOR TEST."
    # objectives/discussion/team were not overridden - must fall back to a real (non-empty) auto-generated default
    assert data["report_text"]["objectives"].strip() != ""
    assert data["report_text"]["discussion"].strip() != ""
    path = report.generate_docx(os.path.join(OUT_DIR, "report_custom_text.docx"), data)
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "CUSTOM INTRO TEXT FOR TEST." in full_text
    assert "CUSTOM CONCLUSION TEXT FOR TEST." in full_text


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


def test_docx_report_appendix_includes_compliance_table_when_provided():
    load_result, sim_result, case_results = _build_common()
    compliance_rows = [("FLT 4.3.4", "Rail exit velocity", "PASS", "23.4 m/s >= 30 m/s required")]
    data = report.build_report_data("44", "", load_result, sim_result, case_results, None, None, OUT_DIR,
                                     include_appendix=True, compliance_rows=compliance_rows)
    path = report.generate_docx(os.path.join(OUT_DIR, "report_compliance.docx"), data)
    from docx import Document
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    assert "Appendix" in full_text
    assert "FLT 4.3.4" in table_text


def test_pdf_report_generates_with_monte_carlo_and_has_populated_toc():
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

    # 2026-09-29 review item 4: report rewritten as HTML/CSS printed by
    # Chromium (Playwright) - it produces no PDF outline/bookmarks (unlike
    # the old reportlab build), so "the TOC is populated" is checked the
    # way it actually works now: a two-pass render fills each TOC row
    # with the REAL page its section landed on (see report_html.py's
    # _find_toc_page_numbers), not a placeholder "...". Verify both that
    # the numbers are real and that they are correct (the listed page
    # actually contains that section's own heading).
    import re
    import pypdf
    reader = pypdf.PdfReader(path)
    assert len(reader.pages) > 5, "a real multi-section report should be more than a handful of pages"
    pages_text = [p.extract_text() or "" for p in reader.pages]
    toc_page_idx = next(i for i, t in enumerate(pages_text) if "Table of contents" in t)
    toc_text = pages_text[toc_page_idx]
    toc_lines = [l.strip() for l in toc_text.splitlines() if l.strip()]
    numbered_lines = [l for l in toc_lines if re.search(r"\d+$", l)]
    assert len(numbered_lines) >= 8, f"expected >=8 TOC rows with a real page number, got: {toc_lines}"
    assert "..." not in toc_text, "TOC still shows the unresolved placeholder instead of real page numbers"
    m = re.search(r"General information and set-up\s*(\d+)\s*$", toc_text, re.MULTILINE)
    assert m, f"could not find section 1's TOC row: {toc_lines}"
    sec1_page = int(m.group(1))
    assert "General information and set-up" in pages_text[sec1_page - 1], (
        f"TOC says section 1 is on page {sec1_page}, but that page's text doesn't have the heading"
    )


def test_pdf_report_footer_has_mission_and_event_not_just_page_number():
    load_result, sim_result, case_results = _build_common()
    data = report.build_report_data("44", "", load_result, sim_result, case_results, None, None, OUT_DIR)
    path = report.generate_pdf(os.path.join(OUT_DIR, "report_footer.pdf"), data)
    import pypdf
    reader = pypdf.PdfReader(path)
    page_text = reader.pages[2].extract_text() or ""
    assert "Beyond UP" in page_text and "Mission 44" in page_text, f"footer branding missing from page text: {page_text[-200:]}"


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
    test_docx_report_has_real_sections_and_no_jargon()
    test_docx_report_has_data_driven_prose_and_barrowman_check()
    test_docx_report_editable_text_blocks_are_used_verbatim()
    test_docx_report_appendix_credits_lasc_officials_not_us()
    test_docx_report_appendix_includes_compliance_table_when_provided()
    test_pdf_report_generates_with_monte_carlo_and_has_populated_toc()
    test_pdf_report_footer_has_mission_and_event_not_just_page_number()
    test_lasc_zip_contains_expected_files()
    print("\nPHASE 5 REPORT + ZIP: OK")
