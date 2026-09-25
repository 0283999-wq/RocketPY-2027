"""Full end-to-end UI test across every page (2026-09-26 review, item 2's
Playwright screenshot requirement). Extends test_phase0_e2e.py's basic
upload-and-simulate flow to click through every sidebar page and save a
screenshot of each to docs/screenshots/, so Diego can review the design
without running the app himself.
"""
import os
import re
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
PORT = 8178
BASE_URL = f"http://127.0.0.1:{PORT}"

PAGES = [("/", "01_simulate_before.png"), ("/rocket", "05_rocket.png"), ("/montecarlo", "06_montecarlo.png"),
         ("/rcsm", "07_rcsm.png"), ("/analysis", "08_analysis.png"), ("/history", "09_history.png"),
         ("/exports", "10_exports.png"), ("/validation", "11_validation.png")]


@pytest.fixture(scope="module")
def app_server():
    env = dict(os.environ, BUP_ROCKETPY_PORT=str(PORT), BUP_ROCKETPY_SHOW="0", PYTHONPATH=REPO_ROOT)
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.Popen([sys.executable, "-m", "bup_rocketpy.gui.app"], cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    import urllib.request
    deadline = time.time() + 30
    ready = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(BASE_URL, timeout=1)
            ready = True
            break
        except Exception:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    if not ready:
        out = proc.stdout.read() if proc.stdout else ""
        proc.kill()
        pytest.fail(f"app server never became ready. Output:\n{out}")
    yield proc
    proc.kill()
    proc.wait(timeout=10)


def test_every_page_loads_and_is_screenshotted(app_server):
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # First, drive the real Simulate flow so the other pages have real data to show.
        page.goto(BASE_URL, wait_until="networkidle")
        file_inputs = page.locator('input[type="file"]')
        file_inputs.nth(0).set_input_files(ORK_PATH)
        page.wait_for_timeout(500)
        file_inputs.nth(1).set_input_files(ENG_PATH)
        page.wait_for_timeout(500)
        page.get_by_role("button", name=re.compile("Load files", re.I)).click()
        page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)
        page.get_by_text(re.compile("Advanced:", re.I)).click()  # the mass/CG override fields are in a collapsed panel by design
        page.wait_for_timeout(300)
        page.get_by_label(re.compile("dry mass override", re.I)).fill("5.6622")
        page.get_by_label(re.compile("dry CG override", re.I)).fill("0.6279")
        page.get_by_role("button", name=re.compile("^Simulate$", re.I)).click()
        page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_simulate_results.png"), full_page=True)

        errors_by_page = {}
        for path, filename in PAGES:
            if path == "/":
                continue
            page.goto(BASE_URL + path, wait_until="networkidle")
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, filename), full_page=True)
            body_text = page.inner_text("body")
            if "Traceback" in body_text or "Internal Server Error" in body_text:
                errors_by_page[path] = body_text[:500]

        browser.close()

    print(f"\nScreenshots written to {SCREENSHOTS_DIR}")
    assert not errors_by_page, f"pages with errors: {errors_by_page}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
