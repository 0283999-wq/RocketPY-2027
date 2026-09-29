"""Task 28 (2026-09-27 redesign, Step 4 "quality"): the checks the
mega-prompt asked for that no other test file covers -
1. WCAG AA contrast, computed for real (not eyeballed) from the exact
   token values in theme.py, so a future color change that breaks
   contrast fails a test instead of just a comment going stale.
2. Every sidebar page renders with no console errors and no horizontal
   overflow, at both 1366x768 and 1920x1080, in both light and dark
   mode - the two resolutions and both themes the mega-prompt named.
3. A full light+dark screenshot gallery of every page at 1920x1080 to
   docs/screenshots/redesign/, the "after" reference for Diego.

Every other page-content/functional assertion (apogee number, KPI
cards, delete-dedup bug, playback, live Monte Carlo, report
generation) already has its own dedicated test file - this one is
strictly the visual/contrast/no-regression pass, so it doesn't
duplicate those.
"""
import os
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright
from conftest import launch_chromium

from bup_rocketpy.gui import theme

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
REDESIGN_DIR = os.path.join(REPO_ROOT, "docs", "screenshots", "redesign")

ALL_PAGES = [
    ("/", "home"), ("/simulate", "simulate"), ("/rocket", "rocket"),
    ("/montecarlo", "montecarlo"), ("/rcsm", "rcsm"), ("/analysis", "analysis"),
    ("/launchday", "launchday"), ("/history", "history"), ("/exports", "exports"),
    ("/validation", "validation"),
]


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(rgb):
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio_rgb(rgb_a, rgb_b):
    la, lb = _relative_luminance(rgb_a), _relative_luminance(rgb_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _contrast_ratio(hex_a, hex_b):
    return _contrast_ratio_rgb(_hex_to_rgb(hex_a), _hex_to_rgb(hex_b))


def _blend(fg_hex, alpha, bg_hex):
    """fg_hex painted at `alpha` opacity over an opaque bg_hex -
    components.py's CHIP_KIND_STYLE renders status_chip() this way
    (a translucent tint), never on flat white/black, so that's the
    background this test must check against, not pure white."""
    fg, bg = _hex_to_rgb(fg_hex), _hex_to_rgb(bg_hex)
    return tuple(round(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


CHIP_TINT_ALPHA = 0.12  # matches CHIP_KIND_STYLE in components.py

# (fg, bg, minimum ratio, what) - the exact pairs theme.py's own
# CONTRAST_NOTES comment claims; this test is what actually PROVES them.
# 4.5 = WCAG AA normal text, 3.0 = WCAG AA large text (>=24px) / UI components.
NORMAL_TEXT_PAIRS = [
    (theme.WINE, theme.LIGHT_SURFACE, "wine body text on white card"),
    (theme.LIGHT_TEXT, theme.LIGHT_BG, "light-mode ink on light-mode page background"),
    (theme.LIGHT_TEXT, theme.LIGHT_SURFACE, "light-mode ink on light-mode card"),
    (theme.LIGHT_MUTED, theme.LIGHT_BG, "light-mode muted/caption text on page background"),
    (theme.LIGHT_MUTED, theme.LIGHT_SURFACE, "light-mode muted/caption text on card"),
    (theme.DARK_TEXT, theme.DARK_BG, "dark-mode ink on dark-mode page background"),
    (theme.DARK_TEXT, theme.DARK_SURFACE, "dark-mode ink on dark-mode card"),
    (theme.DARK_MUTED, theme.DARK_BG, "dark-mode muted/caption text on page background"),
    (theme.DARK_MUTED, theme.DARK_SURFACE, "dark-mode muted/caption text on card"),
    ("#FFFFFF", theme.WINE, "white header text on the wine header bar"),
]
LARGE_TEXT_OR_UI_PAIRS = [
    # The active nav icon: WINE in light mode, GOLD in dark mode (see
    # .bup-nav-active-icon in theme.py) - a ~24px glyph, so the 3:1
    # large-text/UI threshold applies, not 4.5:1.
    (theme.WINE, theme.LIGHT_SURFACE, "active nav icon (light mode) on the sidebar surface"),
    (theme.GOLD, theme.DARK_SURFACE, "active nav icon (dark mode) on the sidebar surface"),
    (theme.GOLD, theme.DARK_BG, "active nav icon (dark mode) on the page background"),
]

# status_chip()'s actual rendering: colored text at text-xs (12px, not
# bold - i.e. NORMAL text, needs 4.5:1) on its own CHIP_TINT_ALPHA-tinted
# surface, computed per theme since dark mode uses the *_DARK variants.
STATUS_CHIP_PAIRS = []
for name, light_hex, dark_hex in [
    ("SUCCESS", theme.SUCCESS, theme.SUCCESS_DARK),
    ("WARNING", theme.WARNING, theme.WARNING_DARK),
    ("ERROR", theme.ERROR, theme.ERROR_DARK),
    ("INFO", theme.INFO, theme.INFO_DARK),
]:
    STATUS_CHIP_PAIRS.append((light_hex, _blend(light_hex, CHIP_TINT_ALPHA, theme.LIGHT_SURFACE), f"{name} chip text on its own tinted background (light mode)"))
    STATUS_CHIP_PAIRS.append((dark_hex, _blend(dark_hex, CHIP_TINT_ALPHA, theme.DARK_SURFACE), f"{name} chip text on its own tinted background (dark mode)"))


def test_documented_contrast_pairs_actually_meet_wcag_aa():
    failures = []
    for fg, bg, what in NORMAL_TEXT_PAIRS:
        ratio = _contrast_ratio(fg, bg)
        if ratio < 4.5:
            failures.append(f"{what}: {fg} on {bg} = {ratio:.2f}:1, needs >=4.5:1 (AA normal text)")
    for fg, bg, what in LARGE_TEXT_OR_UI_PAIRS:
        ratio = _contrast_ratio(fg, bg)
        if ratio < 3.0:
            failures.append(f"{what}: {fg} on {bg} = {ratio:.2f}:1, needs >=3.0:1 (AA large text/UI)")
    for fg_hex, bg_rgb, what in STATUS_CHIP_PAIRS:
        ratio = _contrast_ratio_rgb(_hex_to_rgb(fg_hex), bg_rgb)
        if ratio < 4.5:
            failures.append(f"{what}: {fg_hex} on {bg_rgb} = {ratio:.2f}:1, needs >=4.5:1 (AA normal text)")
    assert not failures, "WCAG AA contrast failures:\n" + "\n".join(failures)


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


def _set_theme(page, want_dark):
    """Click the header's dark_mode toggle iff the page isn't already in
    the wanted state - the icon itself never changes (always 'dark_mode'),
    so state is read from the real DOM class Quasar applies."""
    is_dark = page.evaluate("document.body.classList.contains('body--dark')")
    if is_dark != want_dark:
        page.locator("button:has(i:text('dark_mode'))").first.click()
        page.wait_for_timeout(250)


def test_every_page_both_themes_both_resolutions_no_console_errors(tmp_path):
    """The mega-prompt's Step 4 checklist: 1366x768 and 1920x1080, light
    AND dark, every page loads with no console errors and no horizontal
    overflow. Also writes the 1920x1080 light+dark screenshot gallery to
    docs/screenshots/redesign/ - the definitive "after" reference.

    Honest scope note for MORNING_REPORT.md: this run's earlier
    per-page redesign commits each re-ran the full e2e suite right after
    that page's own change, which overwrites docs/screenshots/*.png with
    the ALREADY-redesigned page - there is no preserved pre-redesign
    "before" snapshot to diff against here. docs/screenshots/redesign/
    is therefore the complete, current "after" gallery, not a before/
    after pair.
    """
    os.makedirs(REDESIGN_DIR, exist_ok=True)
    runs_dir = str(tmp_path / "runs")
    port = 8182
    proc, base_url = _start_app(port, runs_dir)
    console_errors = {}
    overflow_issues = []
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.on("console", lambda msg: console_errors.setdefault(page.url, []).append(msg.text) if msg.type == "error" else None)

            # Load PROMETEO once (default path, no override) so every page
            # has real data instead of empty states.
            page.goto(base_url + "/simulate", wait_until="networkidle")
            file_inputs = page.locator('input[type="file"]')
            file_inputs.nth(0).set_input_files(ORK_PATH)
            page.wait_for_timeout(500)
            file_inputs.nth(1).set_input_files(ENG_PATH)
            page.wait_for_timeout(500)
            page.get_by_role("button", name="Load files").click()
            page.wait_for_selector("text=/Imported|Approximated|Ignored/i", timeout=15000)
            page.get_by_role("button", name="Simulate", exact=True).click()
            page.wait_for_selector("text=/Apogee AGL/i", timeout=60000)
            page.wait_for_timeout(600)

            for width, height, take_screenshots in [(1920, 1080, True), (1366, 768, False)]:
                page.set_viewport_size({"width": width, "height": height})
                for theme_name, want_dark in [("light", False), ("dark", True)]:
                    for path, slug in ALL_PAGES:
                        page.goto(base_url + path, wait_until="networkidle")
                        _set_theme(page, want_dark)
                        page.wait_for_timeout(400)
                        scroll_w, client_w = page.evaluate(
                            "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
                        )
                        if scroll_w > client_w + 4:
                            overflow_issues.append(f"{path} at {width}x{height} ({theme_name}): scrollWidth {scroll_w} > clientWidth {client_w}")
                        if take_screenshots:
                            page.screenshot(path=os.path.join(REDESIGN_DIR, f"{slug}_{theme_name}.png"), full_page=True)

            browser.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)

    # Same carve-out as test_mission_control_e2e.py: no internet in this
    # sandbox, so Leaflet's OpenStreetMap tile fetches (Monte Carlo map)
    # and any Open-Meteo weather call (Launch Day) always fail with
    # net::ERR_* - unrelated to this redesign pass.
    real_errors = {
        url: [e for e in errs if "favicon" not in e.lower() and "net::err" not in e.lower()]
        for url, errs in console_errors.items()
    }
    real_errors = {url: errs for url, errs in real_errors.items() if errs}
    assert not real_errors, f"console errors found: {real_errors}"
    assert not overflow_issues, "horizontal overflow found:\n" + "\n".join(overflow_issues)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
