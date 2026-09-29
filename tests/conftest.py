"""Shared pytest fixtures/helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.browser_launch import launch_chromium  # noqa: F401 - re-exported for `from conftest import launch_chromium`
