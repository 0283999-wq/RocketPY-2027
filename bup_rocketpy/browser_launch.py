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
import shutil


class NoBrowserFoundError(RuntimeError):
    pass


# 2026-10-09 review item 5: "PDF export does not work on my Windows
# machine. Make it work out of the box: try Playwright Chromium, then
# Microsoft Edge (installed on every Windows 10/11: msedge --headless
# --print-to-pdf)." - launch_chromium() above ALREADY tries msedge/
# chrome first via Playwright's own channel= argument, but that path
# goes through Playwright's CDP driver, which can fail to find or drive
# a real Edge install even though the Edge BINARY itself works fine
# (version mismatches, non-standard install locations, permission
# issues with Playwright's own browser-detection registry lookups - a
# real, documented class of Windows-only failure). This is a
# completely separate, simpler fallback: shell out to Edge/Chrome's own
# `--headless --print-to-pdf` CLI flag directly, no Playwright/CDP
# involved at all. It cannot apply a custom header/footer template
# (Chromium's CLI print-to-pdf never supported that - only the CDP
# Page.printToPDF API Playwright/Puppeteer use does), so the report's
# running footer/page-numbers are present only when the Playwright path
# worked - but a PDF without a fancy footer beats no PDF at all.
_COMMON_WINDOWS_EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
_COMMON_WINDOWS_CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def find_cli_browser_binary():
    """Returns a path to an Edge or Chrome executable this machine
    actually has, for the --print-to-pdf CLI fallback - or None if
    nothing was found. Checks PATH first (shutil.which - covers Linux/
    macOS and any Windows install that registered itself there), then
    Windows' own standard install locations (a plain `msedge`/`chrome`
    is usually NOT on PATH on Windows, even though the browser is
    installed - Windows doesn't add Program Files to PATH by default)."""
    for name in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    for path in _COMMON_WINDOWS_EDGE_PATHS + _COMMON_WINDOWS_CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None


def print_to_pdf_via_cli(html_path, output_path, timeout_s=60, binary_override=None):
    """Renders a local HTML file to a PDF via a direct `--headless
    --print-to-pdf` subprocess call - no Playwright/CDP involved. Raises
    NoBrowserFoundError if no Edge/Chrome binary could be found at all;
    raises RuntimeError (with the real stderr) if the binary was found
    but the subprocess itself failed, so the caller can show the actual
    error rather than a generic message. binary_override: test-only hook
    (this sandbox's own Chromium isn't on PATH or at a standard Windows
    install path, same reasoning as launch_chromium()'s own sandbox
    fallback) - production callers never pass it, so find_cli_browser_
    binary()'s real autodetection is always what actually runs there."""
    import subprocess

    binary = binary_override or find_cli_browser_binary()
    if binary is None:
        raise NoBrowserFoundError(
            "Could not find a browser to generate the PDF with, via either Playwright or a direct "
            "command-line call. Install Microsoft Edge or Google Chrome (most Windows machines "
            "already have one), or run '.venv\\Scripts\\python -m playwright install chromium' "
            "with a working internet connection, then try again. The DOCX report doesn't need a "
            "browser and works regardless."
        )
    html_url = "file:///" + os.path.abspath(html_path).replace(os.sep, "/")
    result = subprocess.run(
        # --no-sandbox: rendering TRUSTED, locally-generated HTML (this
        # app's own report template, never arbitrary/attacker-controlled
        # web content) in a one-shot headless print - the sandbox exists
        # to contain a hijacked renderer process in a persistent browsing
        # session, not relevant here, and without it Chrome/Edge refuses
        # to start at all when the OS user happens to be root/admin (a
        # real condition in CI/containers, and not unheard of on a
        # locked-down Windows machine either).
        [binary, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", f"--print-to-pdf={os.path.abspath(output_path)}", html_url],
        capture_output=True, text=True, timeout=timeout_s,
    )
    if result.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"'{binary} --print-to-pdf' failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip() or 'no output'}")
    return output_path


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
