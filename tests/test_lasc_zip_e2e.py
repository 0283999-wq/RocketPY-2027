"""2026-10-20 review ("judge-grade LASC package"): a real-browser,
real-server end-to-end check of the Exports page's "Build submission
.zip" button - the most invasive change this review made to the live
app (build_zip went from a sync handler to an async one that awaits a
report-PDF render, two new widgets were added, and the zip's own
contents changed shape). No existing Playwright test clicked this
button at all; everything else only called case_export/lasc_package
functions directly.

Loads PROMETEO's real .ork + .eng (no manual override - the default
path, same convention as test_phase0_e2e_full.py), runs Simulate, opts
into the new "Include a standalone Monte Carlo script/notebook"
checkbox with a small N (speed), and confirms the real zip the browser
would download has the new judge-grade contents.
"""
import os
import re
import subprocess
import sys
import time
import zipfile

import pytest
from playwright.sync_api import sync_playwright
from conftest import launch_chromium

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")


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


def test_build_submission_zip_button_produces_judge_grade_contents(tmp_path):
    runs_dir = str(tmp_path / "runs")
    port = 8181
    proc, base_url = _start_app(port, runs_dir)
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(base_url + "/simulate", wait_until="networkidle")
            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(ORK_PATH)
            page.wait_for_timeout(500)
            file_inputs.nth(1).set_input_files(ENG_PATH)
            page.wait_for_timeout(500)
            page.get_by_role("button", name=re.compile("Load files", re.I)).click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)
            page.get_by_role("button", name=re.compile("^Simulate$", re.I)).click()
            page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)

            page.goto(base_url + "/exports", wait_until="networkidle")
            mission_id_box = page.get_by_label(re.compile("Mission ID", re.I))
            mission_id_box.fill("44")

            page.get_by_text("Include a standalone Monte Carlo script/notebook", exact=False).click()
            n_input = page.get_by_label(re.compile("N simulations", re.I))
            n_input.fill("10")

            page.get_by_role("button", name=re.compile("Build submission", re.I)).click()
            # 300s: the verification gate (item 5) actually runs every
            # exported .py/.ipynb in a clean venv before offering the
            # zip - the FIRST run on a cold cache also installs rocketpy
            # into that venv (outputs/lasc_verify_venv/, reused after).
            page.wait_for_selector("text=/Zip written/i", timeout=300000)

            # The link text is the zip's own basename - read it back to find the real file on disk.
            link_text = page.get_by_role("link", name=re.compile("Download submission", re.I)).get_attribute("href")
            assert link_text is not None
            zip_filename = os.path.basename(link_text)
            zip_path = os.path.join(REPO_ROOT, "outputs", "gui_run", zip_filename)
            assert os.path.exists(zip_path), f"zip link pointed at {zip_path}, which doesn't exist on disk"

            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()

            assert "README.md" in names
            assert any(n.startswith("Mission44_Ballistic_RocketPy_v1") and n.endswith(".py") for n in names)
            assert any(n.startswith("Mission44_Ballistic_RocketPy_v1") and n.endswith(".ipynb") for n in names)
            assert any(n.startswith("Mission44_Nominal_RocketPy_v1") and n.endswith(".py") for n in names)
            assert any(n.startswith("Mission44_MonteCarlo_RocketPy_v1") and n.endswith(".py") for n in names), f"Monte Carlo export missing from zip contents: {names}"
            assert any(n.startswith("Mission44_MonteCarlo_RocketPy_v1") and n.endswith(".ipynb") for n in names)
            assert any(n.endswith(".pdf") for n in names), f"report PDF missing from zip contents: {names}"

            readme_text = zf_read_text(zip_path, "README.md")
            assert "pip install rocketpy" in readme_text
            assert "Ballistic" in readme_text and "Nominal" in readme_text

            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)


def zf_read_text(zip_path, name):
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(name).decode("utf-8")
