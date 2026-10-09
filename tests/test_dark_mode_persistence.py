"""2026-10-09 review item 6: "DARK MODE resets to light when I change
page." Root cause: layout.py's `ui.dark_mode()` created a brand new
element at its own default on every page load, with nothing remembering
the last toggle across a real page navigation. Fixed with
app.storage.user (requires storage_secret on ui.run(), added in
app.py). Launches the real app as a subprocess and drives a real
browser - this bug is specifically about cross-page-load persistence,
which a headless/no-browser test cannot exercise.
"""
import os
import subprocess
import sys
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8178


@pytest.fixture(scope="module")
def running_app():
    env = dict(os.environ, BUP_ROCKETPY_PORT=str(PORT), BUP_ROCKETPY_SHOW="0", PYTHONPATH=REPO_ROOT)
    env.pop("PYTEST_CURRENT_TEST", None)  # see test_phase0_e2e.py's own note on why
    proc = subprocess.Popen(
        [sys.executable, "-m", "bup_rocketpy.gui.app"],
        cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        import urllib.request
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://localhost:{PORT}/", timeout=1)
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("app did not come up")
        yield f"http://localhost:{PORT}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_dark_mode_survives_a_real_page_navigation(running_app):
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, REPO_ROOT)
    from bup_rocketpy.browser_launch import launch_chromium

    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            page = browser.new_page()
            page.goto(running_app + "/")
            page.wait_for_timeout(1000)

            before = page.evaluate("document.body.classList.contains('body--dark')")
            assert before is False  # default is light

            page.locator("button:has(i:text('dark_mode'))").first.click()
            page.wait_for_timeout(500)
            after_toggle = page.evaluate("document.body.classList.contains('body--dark')")
            assert after_toggle is True

            # A REAL navigation (new page load, not an SPA route change) -
            # this is exactly where the bug reproduced: a fresh
            # ui.dark_mode() with no stored value reset to light.
            page.goto(running_app + "/simulate")
            page.wait_for_timeout(1000)
            assert page.evaluate("document.body.classList.contains('body--dark')") is True

            page.goto(running_app + "/rocket")
            page.wait_for_timeout(1000)
            assert page.evaluate("document.body.classList.contains('body--dark')") is True
        finally:
            browser.close()
