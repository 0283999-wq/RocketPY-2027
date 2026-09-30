"""2026-09-30 review item 1: the PDF report must prefer an already-
installed system browser (Microsoft Edge/Chrome) over downloading
Playwright's own Chromium, since that download is blocked on some
networks (a real report: a university network times out on
cdn.playwright.dev even with a long timeout). Uses a fake `playwright`
object instead of the real thing so this test doesn't depend on which
browsers happen to be installed wherever it runs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from bup_rocketpy.browser_launch import NoBrowserFoundError, launch_chromium


class _FakeBrowser:
    def __init__(self, channel):
        self.channel = channel


class _FakeChromiumType:
    def __init__(self, working_channels):
        self.working_channels = working_channels
        self.calls = []

    def launch(self, channel=None, executable_path=None):
        self.calls.append(channel or executable_path or "default")
        key = channel or "default"
        if key in self.working_channels:
            return _FakeBrowser(key)
        raise RuntimeError(f"no browser for {key}")


class _FakePlaywright:
    def __init__(self, working_channels):
        self.chromium = _FakeChromiumType(working_channels)


def test_prefers_msedge_over_everything_else():
    pw = _FakePlaywright(working_channels={"msedge", "chrome", "default"})
    browser = launch_chromium(pw)
    assert browser.channel == "msedge"
    assert pw.chromium.calls == ["msedge"], "must not even try chrome/default once msedge works"


def test_falls_back_to_chrome_when_no_edge():
    pw = _FakePlaywright(working_channels={"chrome", "default"})
    browser = launch_chromium(pw)
    assert browser.channel == "chrome"
    assert pw.chromium.calls == ["msedge", "chrome"]


def test_falls_back_to_bundled_chromium_when_no_system_browser():
    pw = _FakePlaywright(working_channels={"default"})
    browser = launch_chromium(pw)
    assert browser.channel == "default"
    assert pw.chromium.calls == ["msedge", "chrome", "default"]


def test_raises_clear_error_when_nothing_works(monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    pw = _FakePlaywright(working_channels=set())
    with pytest.raises(NoBrowserFoundError) as exc_info:
        launch_chromium(pw)
    message = str(exc_info.value)
    assert "Microsoft Edge" in message and "Chrome" in message
    assert "DOCX" in message, "must point at the working fallback, not just report the failure"
