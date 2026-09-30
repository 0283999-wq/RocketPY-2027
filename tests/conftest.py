"""Shared pytest fixtures/helpers."""
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.browser_launch import launch_chromium  # noqa: F401 - re-exported for `from conftest import launch_chromium`

# 2026-09-30 review item 3: "Windows emulation" CI step - forces the
# SAME multiprocessing start method Windows is stuck with (its ONLY
# option is "spawn"; this project's own Linux runs default to "fork",
# which is why Windows bug 1 - Monte Carlo silently returning "0
# completed" - was invisible here until specifically reproduced). Set
# BUP_WINDOWS_EMULATION=1 (scripts/test_windows_emulation.sh does this,
# alongside the encoding side of the same emulation - see that script)
# to run the WHOLE suite this way, not just the two tests that force it
# locally in their own subprocess (test_windows_spawn_monte_carlo.py,
# test_encoding_defaults.py - those stay isolated in a subprocess even
# without this flag, so they always catch a spawn regression regardless
# of how the suite itself was invoked). Must happen at collection time,
# before any ProcessPoolExecutor is ever created in this interpreter -
# the start method can only be set once.
if os.environ.get("BUP_WINDOWS_EMULATION") == "1":
    multiprocessing.set_start_method("spawn", force=True)
