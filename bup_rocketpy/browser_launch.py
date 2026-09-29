"""Launches Playwright's managed Chromium the portable way.

`playwright.chromium.launch()` with no `executable_path` is the correct,
cross-platform way to do this - it resolves whatever `playwright install
chromium` put in Playwright's own managed browser cache (respecting
PLAYWRIGHT_BROWSERS_PATH if set), the same way on Windows, macOS and
Linux. A hardcoded `executable_path` was found and removed while
preparing this repo for public release: it pointed at a path
("/opt/pw-browsers/chromium") that only ever existed in this project's
own cloud dev sandbox, and would fail on every real machine.

The one wrinkle: that same dev sandbox pre-installs Chromium at a
revision that doesn't match what this pinned playwright package expects
by default, so the plain call above fails *there specifically*. Real
installs (Diego's machine, CI that runs `playwright install` itself,
etc.) don't have this problem. The fallback below only ever matters in
that one sandbox; harmless everywhere else.
"""
import glob
import os


def launch_chromium(playwright):
    try:
        return playwright.chromium.launch()
    except Exception:
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers_path:
            raise
        candidates = (
            glob.glob(os.path.join(browsers_path, "chromium*", "chrome-linux", "chrome"))
            + glob.glob(os.path.join(browsers_path, "chromium*", "chrome-linux64", "chrome"))
            + glob.glob(os.path.join(browsers_path, "chromium"))
        )
        for candidate in candidates:
            if os.path.exists(candidate):
                return playwright.chromium.launch(executable_path=candidate)
        raise
