"""Permanent end-to-end UI test (2026-09-26 overnight review, item 0):
launches the real bup_rocketpy.gui.app as a subprocess (real uvicorn
server, real NiceGUI/Vue/Quasar frontend), drives it through headless
Chromium (pre-installed, PLAYWRIGHT_BROWSERS_PATH already set - do NOT
call playwright install), uploads PROMETEO's real .ork + .eng through the
actual <input type=file> elements (not by calling Python functions
directly - this is what catches "the upload handler never stores the
file" bugs that a pipeline-only test cannot), clicks through to Simulate,
and asserts the apogee number is actually rendered on the page.

Run this after every UI change. Nothing UI-related is considered done
without it passing - this is the rule from the overnight review, not just
a suggestion.
"""
import os
import re
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright

from conftest import launch_chromium

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
PORT = 8177
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module")
def app_server():
    env = dict(os.environ, BUP_ROCKETPY_PORT=str(PORT), BUP_ROCKETPY_SHOW="0", PYTHONPATH=REPO_ROOT)
    env.pop("PYTEST_CURRENT_TEST", None)  # else nicegui's helpers.is_pytest() thinks the SUBPROCESS itself is under pytest and demands NICEGUI_SCREEN_TEST_PORT (its own in-process Screen-testing convention, which this deliberately bypasses in favor of a real subprocess + real browser)
    proc = subprocess.Popen(
        [sys.executable, "-m", "bup_rocketpy.gui.app"],
        cwd=REPO_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    deadline = time.time() + 30
    ready = False
    import urllib.request
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
        pytest.fail(f"app server never became ready on {BASE_URL}. Output:\n{out}")
    yield proc
    proc.kill()
    proc.wait(timeout=10)


def test_upload_ork_and_eng_and_simulate_shows_apogee(app_server):
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page()
        page.goto(BASE_URL + "/simulate", wait_until="networkidle")

        file_inputs = page.locator('input[type="file"]')
        assert file_inputs.count() >= 2, "expected at least the .ork and .eng upload inputs to be present"

        file_inputs.nth(0).set_input_files(ORK_PATH)
        page.wait_for_timeout(500)
        file_inputs.nth(1).set_input_files(ENG_PATH)
        page.wait_for_timeout(500)

        page.get_by_role("button", name=re.compile("Load files", re.I)).click()
        page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)

        import_rows = page.locator("text=IMPORTED")
        assert import_rows.count() > 0, "the import table should show at least some IMPORTED rows after loading a real .ork - if this is 0, the upload handler didn't actually receive the file (this is exactly bug #0)"

        page.get_by_text(re.compile("Advanced:", re.I)).click()  # the mass/CG override fields are in a collapsed panel by design
        page.wait_for_timeout(300)
        # 2026-09-26 review crash (c) fix: the override fields are disabled
        # until "use manual override" is checked (unchecked = the default
        # no-override path, which is what test_phase0_e2e_full.py now
        # exercises instead) - this test still exercises the manual-override
        # path deliberately, so it must check the box first.
        page.get_by_text(re.compile("Use manual mass/CG override", re.I)).click()
        mass_box = page.get_by_label(re.compile("dry mass override", re.I))
        cg_box = page.get_by_label(re.compile("dry CG override", re.I))
        mass_box.fill("5.6622")
        cg_box.fill("0.6279")

        page.get_by_role("button", name=re.compile("^Simulate$", re.I)).click()
        page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)

        page_text = page.content()
        assert "Apogee AGL" in page_text
        apogee_match = re.search(r"Apogee AGL.*?(\d+\.\d+)\s*m", page_text.replace("\n", " "))
        assert apogee_match, "could not find a numeric apogee value on the results page"
        apogee = float(apogee_match.group(1))
        print(f"\nE2E: apogee shown in the real browser UI = {apogee:.1f} m")
        assert 500 < apogee < 2000, f"apogee {apogee} is not in a plausible range - something is badly wrong end to end"

        os.makedirs(os.path.join(REPO_ROOT, "docs", "screenshots"), exist_ok=True)
        page.screenshot(path=os.path.join(REPO_ROOT, "docs", "screenshots", "e2e_results.png"))

        browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
