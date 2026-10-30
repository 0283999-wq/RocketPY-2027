"""Demo-day fix 3, through a real browser: run a long Monte Carlo, cancel it,
change N, press Run again -> the label must IMMEDIATELY say "Starting 0/<new N>"
(not the old "Running 338/800..." / "Cancelled..."), and the bar shows a
percentage ("12 %"), never a raw fraction ("0.12").
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
PORT = 8186
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module")
def app_server(tmp_path_factory):
    runs_dir = str(tmp_path_factory.mktemp("runs"))
    env = dict(os.environ, BUP_ROCKETPY_PORT=str(PORT), BUP_ROCKETPY_SHOW="0", BUP_ROCKETPY_RUNS_DIR=runs_dir, PYTHONPATH=REPO_ROOT)
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.Popen([sys.executable, "-m", "bup_rocketpy.gui.app"], cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    import urllib.request
    deadline = time.time() + 40
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


def test_run_again_after_cancel_resets_label_and_shows_percent(app_server):
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        page.goto(BASE_URL + "/simulate", wait_until="networkidle")
        inputs = page.locator('input[type="file"]')
        inputs.nth(0).set_input_files(ORK_PATH)
        page.wait_for_timeout(500)
        inputs.nth(1).set_input_files(ENG_PATH)
        page.wait_for_timeout(500)
        page.get_by_role("button", name=re.compile("Load files", re.I)).click()
        page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)
        page.get_by_text(re.compile("Advanced:", re.I)).click()
        page.get_by_text(re.compile("Use manual mass/CG override", re.I)).click()
        page.get_by_label(re.compile("dry mass override", re.I)).fill("5.6622")
        page.get_by_label(re.compile("dry CG override", re.I)).fill("0.6279")
        page.get_by_role("button", name=re.compile("^Simulate$", re.I)).click()
        page.wait_for_selector("text=/Apogee AGL/i", timeout=90000)

        page.goto(BASE_URL + "/montecarlo", wait_until="networkidle")
        page.wait_for_selector("text=/Uncertainties/i", timeout=15000)
        n_input = page.get_by_label(re.compile("N simulations", re.I))
        n_input.fill("800")
        page.get_by_role("button", name=re.compile("^Run Monte Carlo$", re.I)).click()
        page.wait_for_selector("text=/Running \\d+\\/800/", timeout=60000)
        assert re.search(r"\d+ %", page.inner_text("body")), "progress must be shown as a percentage"
        assert not re.search(r"\b0\.\d{2,}\b", page.locator(".q-linear-progress").inner_text()), "bar must not print a raw fraction"
        page.get_by_role("button", name=re.compile("^Cancel$", re.I)).click()
        page.wait_for_selector("text=/Cancelled|Done:/", timeout=120000)

        n_input.fill("500")
        page.get_by_role("button", name=re.compile("^Run Monte Carlo$", re.I)).click()
        page.wait_for_selector("text=/Starting 0\\/500|Running \\d+\\/500/", timeout=5000)
        body = page.inner_text("body")
        assert "/800" not in body, f"the old run's label is still showing: {body[-400:]}"
        assert "Cancelled" not in body

        page.get_by_role("button", name=re.compile("^Cancel$", re.I)).click()
        browser.close()
