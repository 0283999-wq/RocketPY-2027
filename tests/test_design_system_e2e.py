"""2026-09-27 UI redesign, Step 1: the design system gallery page loads
cleanly, and - a real bug caught while building it - sidebar/button
icons keep rendering as actual glyphs, not literal text like
"rocket_launch". That bug came from a global `* { font-family: Inter }`
rule unintentionally beating Quasar's own (layered) `.material-icons`
rule, since NiceGUI/Quasar ship their base CSS inside a named
`@layer base` and unlayered rules always win over layered ones,
REGARDLESS of specificity - a real CSS cascade-layers gotcha, not a
typo. This test locks in the fix.
"""
import os
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright
from conftest import launch_chromium

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def test_material_icons_render_as_glyphs_not_literal_text(tmp_path):
    port = 8197
    proc, base_url = _start_app(port, str(tmp_path / "runs"))
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page()
            page.goto(base_url + "/", wait_until="networkidle")
            font_family = page.evaluate(
                "() => { const el = document.querySelector('.material-icons'); "
                "return el ? getComputedStyle(el).fontFamily : null; }"
            )
            assert font_family is not None, "expected at least one .material-icons element on the page"
            assert "Material Icons" in font_family, (
                f"icon font-family resolved to {font_family!r}, not Material Icons - the global Inter font "
                "rule is clobbering Quasar's own (layered) icon CSS again"
            )
            # font-family alone isn't proof the GLYPH actually renders -
            # Material Icons uses ligatures, so the DOM text node always
            # literally contains "rocket_launch" etc. regardless of
            # whether the font applied (innerText can't tell them apart).
            # document.fonts is the real signal: the icon font face must
            # have finished loading (not just been requested).
            icon_font_loaded = page.evaluate(
                "async () => { await document.fonts.ready; return document.fonts.check('24px \"Material Icons\"'); }"
            )
            assert icon_font_loaded, "the Material Icons font face never finished loading (icons would render as literal text)"
            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_design_system_gallery_page_loads_with_no_errors(tmp_path):
    port = 8198
    proc, base_url = _start_app(port, str(tmp_path / "runs"))
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page()
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.goto(base_url + "/design-system", wait_until="networkidle")
            page.wait_for_timeout(300)
            body_text = page.inner_text("body")
            assert "Traceback" not in body_text and "Internal Server Error" not in body_text
            for section in ("Colors", "Buttons", "Status chips", "KPI cards", "Cards (staggered entrance)", "Empty state", "Skeleton loading", "Confirm dialog", "Error bar", "Data table"):
                assert section in body_text, f"missing gallery section {section!r}"

            # Real bug caught while building the Validation page: ui.html's
            # own wrapper has no intrinsic width under a flex column, so
            # error_bar's inner `width:100%` div rendered as a squished
            # sliver instead of spanning its card - fixed by forcing the
            # wrapper itself to w-full. Locks that in by measuring actual
            # rendered widths, not just checking the page didn't crash.
            widths = page.evaluate(
                "() => { const bars = document.querySelectorAll('[style*=\"height:28px\"]'); "
                "return Array.from(bars).map(b => ({bar: b.getBoundingClientRect().width, "
                "parent: b.parentElement.getBoundingClientRect().width})); }"
            )
            assert widths, "expected at least one error_bar element on the design system page"
            for w in widths:
                assert w["bar"] > 0.85 * w["parent"], f"error_bar rendered too narrow relative to its container: {w}"

            js_errors = [e for e in console_errors if "favicon" not in e.lower()]
            assert not js_errors, f"JS console errors on the design system page: {js_errors}"
            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        import pathlib
        test_material_icons_render_as_glyphs_not_literal_text(pathlib.Path(d))
    with tempfile.TemporaryDirectory() as d:
        import pathlib
        test_design_system_gallery_page_loads_with_no_errors(pathlib.Path(d))
    print("\nDESIGN SYSTEM E2E: OK")
