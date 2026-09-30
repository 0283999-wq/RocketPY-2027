"""Launches a Chromium-based browser for the PDF report, preferring
whatever's already on the machine over downloading anything.

2026-09-30 review item 1: cdn.playwright.dev (where `playwright install
chromium` fetches its browser from) is blocked on some networks
(reported: university network, times out even with a long timeout) -
Playwright's own bundled Chromium is then simply unavailable, and no
amount of retrying fixes that. Real Windows machines already have
Microsoft Edge (ships with Windows) or Google Chrome (the most common
manual install) - Playwright can drive either of those directly via its
`channel=` argument, with NO download at all, since it launches the
system browser install in place. Order: msedge, then chrome, then
Playwright's own managed Chromium (works if `playwright install
chromium` succeeded, e.g. on networks that aren't blocked) - only if
none of those work does this raise, with a message clear enough to act
on rather than a raw Playwright stack trace.
"""
import glob
import os


class NoBrowserFoundError(RuntimeError):
    pass


def launch_chromium(playwright):
    errors = {}
    for channel in ("msedge", "chrome"):
        try:
            return playwright.chromium.launch(channel=channel)
        except Exception as e:
            errors[channel] = e

    try:
        return playwright.chromium.launch()
    except Exception as e:
        errors["playwright-chromium"] = e
        # This sandbox-only fallback exists for THIS project's own cloud
        # dev environment, where Chromium is pre-installed at a path/
        # revision the pip-installed playwright package doesn't look for
        # by default - see the module this replaced (git history) for the
        # repro. Harmless everywhere else: PLAYWRIGHT_BROWSERS_PATH won't
        # be set on a real user's machine, so this block never runs there.
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if browsers_path:
            candidates = (
                glob.glob(os.path.join(browsers_path, "chromium*", "chrome-linux", "chrome"))
                + glob.glob(os.path.join(browsers_path, "chromium*", "chrome-linux64", "chrome"))
                + glob.glob(os.path.join(browsers_path, "chromium"))
            )
            for candidate in candidates:
                if os.path.exists(candidate):
                    try:
                        return playwright.chromium.launch(executable_path=candidate)
                    except Exception as e2:
                        errors["sandbox-fallback"] = e2

    raise NoBrowserFoundError(
        "Could not find a browser to generate the PDF with. Tried Microsoft Edge, "
        "Google Chrome, and Playwright's own downloaded Chromium (none is installed, "
        "or the download was blocked - this often happens on restrictive networks). "
        "Install Microsoft Edge or Google Chrome (most Windows machines already have "
        "one), or run '.venv\\Scripts\\python -m playwright install chromium' with a "
        "working internet connection, then try again. The DOCX report doesn't need a "
        "browser and works regardless."
    )
