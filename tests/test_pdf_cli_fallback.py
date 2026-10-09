"""2026-10-09 review item 5: "PDF export does not work on my Windows
machine. Make it work out of the box: try Playwright Chromium, then
Microsoft Edge... silently. Only if both fail, show the real error
message in one line." Playwright's own msedge/chrome channel launch can
fail on Windows even when the browser itself works fine (CDP driver
detection issues) - bup_rocketpy.browser_launch.print_to_pdf_via_cli()
is the direct `--print-to-pdf` CLI fallback for exactly that case.

Uses PROMETEO's real .ork (no invented rocket). The sandbox's own
Chromium isn't on PATH or at a standard Windows install path, so
find_cli_browser_binary() is monkeypatched to point at it - same
reasoning as browser_launch.launch_chromium()'s own sandbox fallback;
production code never does this, real autodetection runs there.
"""
import glob
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import browser_launch, rcsm_cases, report
from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_pdf_cli_fallback")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _sandbox_chromium_path():
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers_path:
        return None
    candidates = glob.glob(os.path.join(browsers_path, "chromium*", "chrome-linux", "chrome"))
    return candidates[0] if candidates else None


def test_find_cli_browser_binary_returns_none_when_nothing_on_path_or_standard_locations():
    with mock.patch("shutil.which", return_value=None), mock.patch("os.path.exists", return_value=False):
        assert browser_launch.find_cli_browser_binary() is None


def test_print_to_pdf_via_cli_raises_no_browser_found_error_with_nothing_available():
    with mock.patch("bup_rocketpy.browser_launch.find_cli_browser_binary", return_value=None):
        try:
            browser_launch.print_to_pdf_via_cli("/tmp/does_not_matter.html", "/tmp/out.pdf")
            assert False, "expected NoBrowserFoundError"
        except browser_launch.NoBrowserFoundError:
            pass


def test_print_to_pdf_via_cli_produces_a_real_pdf():
    chromium = _sandbox_chromium_path()
    if chromium is None:
        import pytest
        pytest.skip("no sandbox chromium available to drive the CLI fallback with")
    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, "cli_test.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<html><body><h1>CLI fallback test</h1><p>hello</p></body></html>")
    out_path = os.path.join(OUT_DIR, "cli_test.pdf")
    if os.path.exists(out_path):
        os.remove(out_path)
    browser_launch.print_to_pdf_via_cli(html_path, out_path, binary_override=chromium)
    assert os.path.exists(out_path)
    import pypdf
    reader = pypdf.PdfReader(out_path)
    assert len(reader.pages) >= 1
    assert "CLI fallback test" in (reader.pages[0].extract_text() or "")


def test_render_pdf_falls_back_to_cli_when_playwright_cannot_launch_any_browser():
    """End-to-end through report_html.render_pdf() (the real production
    function exports_page.py calls) - Playwright's launch_chromium is
    forced to fail exactly like it would if msedge/chrome's CDP driver
    detection failed on a real Windows machine, and find_cli_browser_
    binary is pointed at the sandbox's own Chromium so the fallback has
    something to drive."""
    chromium = _sandbox_chromium_path()
    if chromium is None:
        import pytest
        pytest.skip("no sandbox chromium available to drive the CLI fallback with")

    os.makedirs(OUT_DIR, exist_ok=True)
    load_result = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim_result = pipeline.run_simulation(load_result, OUT_DIR, dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M)
    case_results = rcsm_cases.run_all_cases(load_result.parsed_ork, load_result.parsed_eng, load_result.eng_path, POWER_OFF_DRAG, POWER_ON_DRAG, DRY_MASS_KG, DRY_CG_M)
    data = report.build_report_data("44", "Test Author", load_result, sim_result, case_results, None, None, OUT_DIR)

    out_path = os.path.join(OUT_DIR, "fallback_report.pdf")
    if os.path.exists(out_path):
        os.remove(out_path)

    with mock.patch("bup_rocketpy.report_html.launch_chromium", side_effect=browser_launch.NoBrowserFoundError("forced failure for this test")), \
         mock.patch("bup_rocketpy.browser_launch.find_cli_browser_binary", return_value=chromium):
        report.generate_pdf(out_path, data)

    assert os.path.exists(out_path)
    import pypdf
    reader = pypdf.PdfReader(out_path)
    assert len(reader.pages) >= 2  # a real multi-page report, not a 1-line stub
    all_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "PrometeoLasc2026" in all_text


if __name__ == "__main__":
    test_find_cli_browser_binary_returns_none_when_nothing_on_path_or_standard_locations()
    test_print_to_pdf_via_cli_raises_no_browser_found_error_with_nothing_available()
    test_print_to_pdf_via_cli_produces_a_real_pdf()
    test_render_pdf_falls_back_to_cli_when_playwright_cannot_launch_any_browser()
    print("\nPDF CLI FALLBACK: OK")
