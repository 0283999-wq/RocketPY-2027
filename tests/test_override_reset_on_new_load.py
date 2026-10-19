"""2026-10-19 review ("check every bug" audit, GUI pages finding #1):
manual mass/CG/motor-mass overrides used to silently carry over to a
newly-loaded, DIFFERENT rocket - the checkbox stayed checked and the
typed numbers stayed in the input fields across a "Load files" click,
so the SECOND rocket could get simulated with the FIRST rocket's
override values with no warning. Click sequence that reproduced it:
load A, check "manual override", type a value, Simulate (correct) ->
without navigating away, load B, Simulate again -> B silently flew
with A's override.

Real browser test (not a headless pipeline call) because this is
specifically about widget state (a checkbox's checked-ness, a number
input's displayed value) surviving across a click, which only a real
DOM exercises.
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
SECOND_ORK_PATH = os.path.join(REPO_ROOT, "reference", "openrocket_examples", "A_simple_model_rocket.ork")
PORT = 8183


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


def test_manual_override_checkbox_and_values_reset_on_second_load(tmp_path):
    runs_dir = str(tmp_path / "runs")
    proc, base_url = _start_app(PORT, runs_dir)
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            page.goto(base_url + "/simulate", wait_until="networkidle")

            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(ORK_PATH)
            page.wait_for_timeout(400)
            file_inputs.nth(1).set_input_files(ENG_PATH)
            page.wait_for_timeout(400)
            page.get_by_role("button", name="Load files").click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)

            page.get_by_text("Advanced: manual Cd CSVs and mass/CG override").click()
            page.wait_for_timeout(300)
            checkbox_role = page.get_by_role("checkbox").first
            checkbox_role.click()
            mass_input = page.get_by_label(re.compile("Manual dry mass override", re.I))
            cg_input = page.get_by_label(re.compile("Manual dry CG override", re.I))
            mass_input.fill("99.999")
            cg_input.fill("8.888")
            page.wait_for_timeout(200)

            # Load a SECOND, different rocket WITHOUT navigating away first.
            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(SECOND_ORK_PATH)
            page.wait_for_timeout(400)
            file_inputs.nth(1).set_input_files(ENG_PATH)
            page.wait_for_timeout(400)
            page.get_by_role("button", name="Load files").click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)
            page.wait_for_timeout(300)

            checkbox_role = page.get_by_role("checkbox").first
            assert not checkbox_role.is_checked(), "the manual override checkbox must be unchecked after loading a NEW, different rocket - it stayed checked with the FIRST rocket's values, which is exactly this bug"

            mass_value = mass_input.input_value()
            cg_value = cg_input.input_value()
            assert mass_value in ("", "0", None), f"the manual dry mass override field should be cleared after a new load, still shows {mass_value!r}"
            assert cg_value in ("", "0", None), f"the manual dry CG override field should be cleared after a new load, still shows {cg_value!r}"

            # Simulate the second rocket and confirm it does NOT fly with the first rocket's bogus 99.999 kg / 8.888 m override.
            page.get_by_role("button", name="Simulate", exact=True).click()
            page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)
            body_text = page.inner_text("body")
            assert "Traceback" not in body_text
            assert "99.999" not in body_text and "8.888" not in body_text, "the second rocket's results still show the FIRST rocket's bogus override values - the override leaked across the new load"
            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)
