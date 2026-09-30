"""2026-09-30 review, Windows bug 1: "Monte Carlo: 'Done: 0 completed,
300 excluded'. No traceback is printed anywhere... Likely cause:
Windows uses the 'spawn' start method for ProcessPoolExecutor (Linux
uses 'fork'), so anything configured only in the parent process
... doesn't exist in the workers."

This project's own test suite runs on Linux, where ProcessPoolExecutor
defaults to "fork" (a full memory copy - nothing needs to survive being
re-imported from scratch), so it never exercised the "spawn" path
Windows is stuck with. This test forces "spawn" via a FRESH subprocess
(tests/_windows_spawn_mc_runner.py) - isolated in its own process so
the global multiprocessing start method never leaks into the rest of
this (fork-based) test session - and checks Monte Carlo still produces
real results under it, for both a plain rocket and a reefed one (the
other half of Diego's own reproduction recipe).

Tolerance is ">=4 of 5" rather than "5 of 5": a real Monte Carlo run
can always exclude a genuinely degenerate/unstable tail sample (that's
what the exclusion mechanism is FOR) - the point of this test is
catching a MECHANISM failure (every sample failing the same way, which
0/5 or "all excluded with an identical exclusion_by_type" would show),
not chasing five-nines determinism out of physical flight simulation.
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(REPO_ROOT, "tests", "_windows_spawn_mc_runner.py")


def _run(mode):
    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)  # match Diego's own repro instruction: leave it randomized, not pinned
    proc = subprocess.run([sys.executable, RUNNER, mode], cwd=REPO_ROOT, env=env,
                           capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, f"subprocess crashed outright (mode={mode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    # the runner's own JSON is the LAST line of stdout - rocketpy/nicegui
    # imports can print unrelated banner/info lines before it
    last_line = proc.stdout.strip().splitlines()[-1]
    return json.loads(last_line), proc.stderr


def test_plain_prometeo_under_forced_spawn():
    result, stderr = _run("plain")
    assert result["n_completed"] >= 4, (
        f"only {result['n_completed']}/5 samples completed under forced spawn - "
        f"by_type={result['exclusion_by_type']}, first traceback:\n{result['first_traceback']}"
    )


def test_reefed_prometeo_under_forced_spawn():
    """Diego's own repro explicitly calls out "a reefed rocket" - the
    StochasticRocket.create_object() parachute-dropping bug
    (test_phase4_monte_carlo.py's own docstring) was previously the kind
    of thing that silently "worked" (no exception) while quietly flying
    the wrong vehicle, so this checks actual sample completion, not just
    the absence of a crash."""
    result, stderr = _run("reefed")
    assert result["n_completed"] >= 4, (
        f"only {result['n_completed']}/5 samples completed under forced spawn - "
        f"by_type={result['exclusion_by_type']}, first traceback:\n{result['first_traceback']}"
    )


if __name__ == "__main__":
    test_plain_prometeo_under_forced_spawn()
    test_reefed_prometeo_under_forced_spawn()
    print("\nWINDOWS SPAWN MONTE CARLO: OK")
