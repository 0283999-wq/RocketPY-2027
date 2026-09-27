"""Full end-to-end UI test across every page (2026-09-25 second review,
Section 4 "tests that match reality" + item 2's screenshot requirement).

Two scenarios, matching Diego's own real-mouse test path, not just the
happy path a pipeline-level test would take:

1. test_corrupt_runs_dir_does_not_crash_history_page: a runs/ folder
   pre-seeded with a truncated/corrupt record.json (exactly the shape
   crash (a) used to produce) - the History page must show a warning,
   not crash the whole app.
2. test_default_path_every_page_and_second_ork: a FRESH runs/ folder;
   load PROMETEO's real .ork + .eng with NO manual override (the actual
   default path every real user takes, not the override path
   test_phase0_e2e.py exercises); Simulate; visit every sidebar page and
   assert there is no error AND real content is shown (not just "didn't
   crash"); then load a second, genuinely different .ork (one of
   OpenRocket's own example rockets - see reference/openrocket_examples/)
   and confirm the Rocket page updates to the new rocket's geometry, not
   stale data from the first one (crash (e)). Screenshots of every page
   go to docs/screenshots/ either way.
"""
import os
import re
import shutil
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
SECOND_ORK_PATH = os.path.join(REPO_ROOT, "reference", "openrocket_examples", "A_simple_model_rocket.ork")
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
CHROMIUM = "/opt/pw-browsers/chromium"

PAGES = [("/", "04_home.png"), ("/rocket", "05_rocket.png"), ("/montecarlo", "06_montecarlo.png"),
         ("/rcsm", "07_rcsm.png"), ("/analysis", "08_analysis.png"), ("/history", "09_history.png"),
         ("/exports", "10_exports.png"), ("/validation", "11_validation.png"), ("/launchday", "12_launchday.png")]

# Text that must appear on each page once real data exists - "no crash"
# alone isn't enough (2026-09-25 review's whole complaint was pages that
# render without a traceback but show nothing useful, or 0/None KPIs).
REAL_CONTENT_MARKERS = {
    "/": "Apogee AGL",  # 2026-09-27 redesign: Home is now the mission-control dashboard, "/simulate" is the load/simulate flow
    "/rocket": "Loaded rocket:",
    "/montecarlo": "Uncertainties",
    "/rcsm": "RCSM category",
    "/analysis": "Weathercocking",
    "/history": None,  # checked specially: the just-completed run's own row, not a fixed string
    "/exports": "Report (PDF",
    "/validation": "PROVISIONAL",
    "/launchday": "Launch-day weather",
}


def _start_app(port, runs_dir):
    env = dict(os.environ, BUP_ROCKETPY_PORT=str(port), BUP_ROCKETPY_SHOW="0", BUP_ROCKETPY_RUNS_DIR=runs_dir, PYTHONPATH=REPO_ROOT)
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.Popen([sys.executable, "-m", "bup_rocketpy.gui.app"], cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    import urllib.request
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    ready = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base_url, timeout=1)
            ready = True
            break
        except Exception:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    if not ready:
        out = proc.stdout.read() if proc.stdout else ""
        proc.kill()
        pytest.fail(f"app server never became ready on {base_url}. Output:\n{out}")
    return proc, base_url


def test_corrupt_runs_dir_does_not_crash_history_page(tmp_path):
    """crash (a) end-to-end, through a real browser: a runs/ folder with
    a truncated record.json (exactly what a killed process used to leave
    behind before the atomic-write fix) must not take the History page
    down - it should show a warning and still work."""
    runs_dir = str(tmp_path / "runs")
    os.makedirs(os.path.join(runs_dir, "20260101_000000"))
    with open(os.path.join(runs_dir, "20260101_000000", "record.json"), "w") as f:
        f.write('{"run_id": "20260101_000000", "timestamp": "2026-01-01T00:00:00", "apogee_agl_m": 1')  # deliberately truncated JSON

    port = 8179
    proc, base_url = _start_app(port, runs_dir)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.goto(base_url + "/history", wait_until="networkidle")
            body_text = page.inner_text("body")
            assert "Traceback" not in body_text and "Internal Server Error" not in body_text, "History page crashed on a corrupt record.json"
            assert "Skipped corrupt run" in body_text, "expected a visible warning about the corrupt record, not silence"
            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_default_path_every_page_and_second_ork(tmp_path):
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    runs_dir = str(tmp_path / "runs")  # FRESH - directory doesn't exist yet, run_history creates it

    port = 8180
    proc, base_url = _start_app(port, runs_dir)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            # --- Load PROMETEO with NO manual override - the actual default path ---
            page.goto(base_url + "/simulate", wait_until="networkidle")
            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(ORK_PATH)
            page.wait_for_timeout(500)
            file_inputs.nth(1).set_input_files(ENG_PATH)
            page.wait_for_timeout(500)
            page.get_by_role("button", name=re.compile("Load files", re.I)).click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)

            # "Use manual mass/CG override" is deliberately left UNCHECKED here -
            # this is the real no-override path (2026-09-25 review crash c).
            page.get_by_role("button", name=re.compile("^Simulate$", re.I)).click()
            page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)
            page_text = page.content()
            assert "Apogee AGL" in page_text
            apogee_match = re.search(r"Apogee AGL.*?(-?\d+\.\d+)\s*m", page_text.replace("\n", " "))
            assert apogee_match, "no apogee number found on the results page"
            print(f"\nDefault-path (no override) apogee: {float(apogee_match.group(1)):.1f} m")
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_simulate_results.png"), full_page=True)

            # --- Every sidebar page: no error, real content ---
            errors_by_page = {}
            missing_content = {}
            for path, filename in PAGES:
                page.goto(base_url + path, wait_until="networkidle")
                page.wait_for_timeout(500)
                page.screenshot(path=os.path.join(SCREENSHOTS_DIR, filename), full_page=True)
                body_text = page.inner_text("body")
                if "Traceback" in body_text or "Internal Server Error" in body_text:
                    errors_by_page[path] = body_text[:500]
                    continue
                if path == "/history":
                    if "No runs saved yet" in body_text or not re.search(r"\d{8}_\d{6}", body_text):
                        missing_content[path] = "expected the just-completed run's own row (a YYYYMMDD_HHMMSS run_id), found none"
                else:
                    marker = REAL_CONTENT_MARKERS[path]
                    if marker not in body_text:
                        missing_content[path] = f"expected {marker!r} on the page, not found"
                if path == "/exports":
                    # 2026-09-27 review item 6: click the actual button a
                    # real report gets generated from (not just a unit
                    # test of report.py in isolation) - the new prose/TOC/
                    # editable-text-block rewrite must work through the
                    # real running app, not just when called directly.
                    page.get_by_role("button", name=re.compile("Generate PDF report", re.I)).click()
                    page.wait_for_selector("text=/Report written/i", timeout=20000)
                    report_text = page.inner_text("body")
                    if "Traceback" in report_text or "Internal Server Error" in report_text:
                        errors_by_page["/exports (report generation)"] = report_text[:500]

            assert not errors_by_page, f"pages with errors: {errors_by_page}"
            assert not missing_content, f"pages missing real content: {missing_content}"

            # --- Load a second, genuinely different .ork - Rocket page must update, not stay stale (crash e) ---
            page.goto(base_url + "/simulate", wait_until="networkidle")
            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(SECOND_ORK_PATH)
            page.wait_for_timeout(500)
            file_inputs.nth(1).set_input_files(ENG_PATH)  # reused real .eng - see reference/openrocket_examples/README.md
            page.wait_for_timeout(500)
            page.get_by_role("button", name=re.compile("Load files", re.I)).click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)

            page.goto(base_url + "/rocket", wait_until="networkidle")
            page.wait_for_timeout(500)
            rocket_page_text = page.inner_text("body")
            assert "A simple model rocket" in rocket_page_text, f"Rocket page still shows the FIRST loaded rocket's data after loading a second, different .ork - crash (e) regressed. Page text: {rocket_page_text[:300]}"
            assert "PrometeoLasc2026" not in rocket_page_text and "Prometeo" not in rocket_page_text, "Rocket page still mixing in the first rocket's name"
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "05_rocket_second_ork.png"), full_page=True)

            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)

    print(f"\nScreenshots written to {SCREENSHOTS_DIR}")


def test_history_delete_does_not_duplicate_controls_and_detail_page_opens(tmp_path):
    """2026-09-27 review item 4's specific reported bug: "clicking
    'Delete A' adds MORE rows of Compare/Delete controls every time."
    Root cause was the compare/delete row living OUTSIDE the container
    render_table() clears - fixed by moving everything inside it. Seeds
    2 real runs (via save_run, not a hand-typed record.json) so the
    detail page's "Reopen this mission" has real files to work with."""
    runs_dir = str(tmp_path / "runs")
    os.makedirs(runs_dir)
    sys.path.insert(0, REPO_ROOT)
    from bup_rocketpy import run_history
    from bup_rocketpy.gui import pipeline
    os.environ["BUP_ROCKETPY_RUNS_DIR"] = runs_dir
    try:
        outdir = str(tmp_path / "load_outputs")
        load_result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=outdir)
        sim = pipeline.run_simulation(load_result, outdir, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
        for _ in range(2):
            run_history.save_run(REPO_ROOT, sim, load_result, 5.6622, 0.6279, ork_path=ORK_PATH)
            time.sleep(1.1)  # run_id has second-level granularity - without this, both saves collide on the same run_id and overwrite each other
    finally:
        os.environ.pop("BUP_ROCKETPY_RUNS_DIR", None)

    port = 8181
    proc, base_url = _start_app(port, runs_dir)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.goto(base_url + "/history", wait_until="networkidle")
            page.wait_for_timeout(500)

            # Open the first run's detail page (icon buttons have no
            # accessible text name in this NiceGUI version - locate by icon).
            page.locator("button:has(i:text('open_in_new'))").first.click()
            page.wait_for_timeout(500)
            # NiceGUI/Quasar buttons render their label upper-cased via CSS
            # (text-transform), which inner_text() reflects - compare
            # case-insensitively rather than assume the literal casing.
            body_text = page.inner_text("body")
            assert "reopen this mission" in body_text.lower()
            assert "Results" in body_text

            page.go_back(wait_until="networkidle")
            page.wait_for_timeout(500)

            delete_buttons_before = page.locator("button:has(i:text('delete'))").count()
            assert delete_buttons_before == 2, f"expected 2 delete buttons for 2 seeded runs, found {delete_buttons_before}"

            page.locator("button:has(i:text('delete'))").first.click()
            page.wait_for_timeout(300)
            page.get_by_role("button", name="Delete", exact=True).click()
            page.wait_for_timeout(500)

            delete_buttons_after = page.locator("button:has(i:text('delete'))").count()
            assert delete_buttons_after == 1, f"expected exactly 1 delete button left after deleting 1 of 2 runs, found {delete_buttons_after} (the reported duplication bug would show MORE, not fewer)"
            cancel_buttons = page.locator("button", has_text="Cancel").count()
            assert cancel_buttons == 0, "the confirmation dialog's own Cancel button must not linger after a completed delete"
            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
