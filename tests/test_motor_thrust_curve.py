"""2026-09-26: a real user-supplied .eng ("Kaboom" M1889, sent by Diego for
Major Tom) starts its thrust curve with an explicit "0 <thrust>" row.
rocketpy's own Motor.import_eng() unconditionally prepends a (0, 0) point
when it re-parses a .eng file path itself, so passing the raw path as
thrust_source produced TWO points at t=0 - a divide-by-zero in the thrust
Function's slope calculation, and a degenerate (near-zero) thrust curve.
Every Monte Carlo sample of a rocket using that motor "flew" to
essentially the pad's own altitude as a result - not a stability bug, a
motor-construction bug. Fixed by building the SolidMotor from our own
already-parsed thrust_curve list instead of the file path, so rocketpy
never re-parses the file and never re-prepends its own (0, 0).
"""
import os
import sys
import tempfile
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.motor_reader import read_eng

ENG_WITH_EXPLICIT_T0 = """M1889 127.0 736.6 P 9.157442 15.960163 Kaboom
0 0.01
0.03 1401.5
0.06 1412.1
0.09 1000.0
0.12 500.0
0.15 0.0
"""


def test_eng_starting_with_an_explicit_t0_row_builds_a_clean_motor():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".eng", delete=False) as f:
        f.write(ENG_WITH_EXPLICIT_T0)
        eng_path = f.name

    eng = read_eng(eng_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        motor = translate.build_motor(eng, eng_path)
        # A real thrust value well inside the burn, not NaN/degenerate from
        # a colliding-x-value slope computation.
        thrust_mid_burn = motor.thrust(0.06)
    assert thrust_mid_burn == thrust_mid_burn, "thrust came out NaN - the duplicate-t0 bug is back"
    assert 1000 < thrust_mid_burn < 1500, f"thrust at t=0.06 should be ~1412 N, got {thrust_mid_burn}"
