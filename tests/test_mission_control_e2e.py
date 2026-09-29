"""2026-09-27 review item 7 (Mission Control redesign): the 3D flight
playback view and the live Monte Carlo view, through a real browser -
these are pure client-side three.js/canvas features a Python-level unit
test can't exercise (tests/test_flight_playback.py covers the DATA those
views animate; this covers the actual rendering + controls). Screenshots
go to docs/screenshots/ alongside every other page's, per the review's
own "screenshots of every page + playback mid-flight + live MC"
instruction.
"""
import os
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright
from conftest import launch_chromium

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")


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


def test_flight_playback_and_live_monte_carlo_render_and_animate(tmp_path):
    runs_dir = str(tmp_path / "runs")
    os.makedirs(runs_dir, exist_ok=True)
    port = 8183
    proc, base_url = _start_app(port, runs_dir)
    console_errors = []
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            page.goto(base_url + "/simulate", wait_until="networkidle")
            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(ORK_PATH)
            page.wait_for_timeout(300)
            file_inputs.nth(1).set_input_files(ENG_PATH)
            page.wait_for_timeout(300)
            import re
            page.get_by_role("button", name=re.compile("Load files", re.I)).click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)
            page.get_by_role("button", name=re.compile("^Simulate$", re.I)).click()
            page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)  # 2026-09-28 review item 1: the old "PROVISIONAL" banner is gone - wait on the KPI grid instead, same marker test_phase0_e2e_full.py already uses

            # --- Flight playback (3D): the tab is the default-active one ---
            page.wait_for_timeout(1500)  # three.min.js load + BUP.playback.create()
            canvases = page.locator("canvas")
            canvases.first.wait_for(timeout=10000)
            n_canvases = canvases.count()
            assert n_canvases >= 4, f"expected at least 4 canvases (1 perspective + 3 ortho), got {n_canvases}"
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "13_playback_start.png"), full_page=True)

            play_button = page.get_by_role("button", name=re.compile("^Play$", re.I))
            play_button.click()
            page.wait_for_timeout(2000)
            body_text = page.inner_text("body")
            assert "Traceback" not in body_text
            # The time readout must have advanced off "0.0" once Play has run for 2s.
            time_value = page.locator("text=Time (s)").locator("xpath=following-sibling::div[1]").first.inner_text()
            assert float(time_value) > 0.0, f"playback Time (s) readout did not advance after Play - got {time_value!r}"
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "14_playback_midflight.png"), full_page=True)

            speed_select = page.locator("select").first
            speed_select.select_option("4")
            page.wait_for_timeout(1500)
            time_value_2 = page.locator("text=Time (s)").locator("xpath=following-sibling::div[1]").first.inner_text()
            assert float(time_value_2) > float(time_value), "playback should keep advancing at a faster speed"

            # --- Live Monte Carlo ---
            page.goto(base_url + "/montecarlo", wait_until="networkidle")
            page.wait_for_timeout(300)
            n_input = page.get_by_label("N simulations")
            n_input.fill("5")
            page.get_by_role("button", name=re.compile("Run Monte Carlo", re.I)).click()
            page.wait_for_selector("text=/Done:/i", timeout=60000)
            page.wait_for_timeout(800)
            mc_canvas_count = page.locator("canvas").count()
            assert mc_canvas_count >= 1, "expected the live Monte Carlo canvas to be present after a run"
            body_text = page.inner_text("body")
            assert "Done: 5 completed" in body_text, f"expected the N=5 override to actually be used, got: {body_text[:400]}"
            assert "trajectory(ies) completed" in body_text, "expected the live MC status line to have updated as samples completed"
            assert "Traceback" not in body_text and "Internal Server Error" not in body_text
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "15_live_montecarlo.png"), full_page=True)

            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)

    # ERR_TUNNEL_CONNECTION_FAILED/net::ERR_* here are the Monte Carlo
    # page's pre-existing Leaflet landing map trying (and failing) to
    # fetch OpenStreetMap tiles - there is no internet access in this
    # sandbox (see monte_carlo_page.py's own comment on this), unrelated
    # to the three.js/playback code this test actually exercises.
    js_errors = [e for e in console_errors if "favicon" not in e.lower() and "net::err" not in e.lower()]
    assert not js_errors, f"JavaScript console errors during the 3D views: {js_errors}"
    print(f"\nScreenshots written to {SCREENSHOTS_DIR}")
