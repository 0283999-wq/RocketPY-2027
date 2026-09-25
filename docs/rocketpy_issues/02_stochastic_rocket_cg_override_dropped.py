"""Minimal repro / RETRACTION: does StochasticRocket.create_object()
preserve an overridden center_of_mass_without_motor?

Originally reported (2026-09-26, first review pass) as a 4th confirmed
bug: "StochasticRocket.create_object() silently drops an overridden CG
unless re-passed explicitly ... every sampled rocket came out ~-8.5 cal
unstable". Re-tested here in ISOLATION, against a complete, well-formed
rocket (real nose + fins actually attached) - and it does NOT reproduce:
the sampled CG matches the nominal CG exactly with no CG factor passed
at all (see the printed verdict).

CONCLUSION: this was very likely a MISDIAGNOSIS, not a separate bug -
the real cause of that symptom is 03_stochastic_add_nose_fins_component_kwarg.py's
bug (a StochasticRocket built with NO aerosurfaces attached, because
add_nose()/add_trapezoidal_fins() were silently failing, has
cp_position() stuck near 0 - which alone is enough to produce a huge,
fake instability number with nothing to do with CG at all). Keeping
this script and its negative result on record rather than deleting it,
per tonight's instruction to check each claim rather than assume all 4
are real - this is exactly the kind of claim that needed checking.
"""
import sys

sys.path.insert(0, "docs/rocketpy_issues")
from _minimal_rocket import build_rocket  # noqa: E402

from rocketpy.stochastic import StochasticRocket  # noqa: E402

rocket = build_rocket()
print(f"nominal rocket.center_of_mass_without_motor = {rocket.center_of_mass_without_motor}")

# Case A: mass uncertainty given, CG uncertainty NOT given - does the
# sampled object keep the nominal CG?
stochastic_a = StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.2))
sample_a = stochastic_a.create_object()
print(f"Case A (no CG factor passed) - sampled rocket CG = {sample_a.center_of_mass_without_motor}")

# Case B: CG uncertainty explicitly given too.
stochastic_b = StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.2), center_of_mass_without_motor=(rocket.center_of_mass_without_motor, 0.01))
sample_b = stochastic_b.create_object()
print(f"Case B (CG factor explicitly passed) - sampled rocket CG = {sample_b.center_of_mass_without_motor}")

nominal_cg = float(rocket.center_of_mass_without_motor(0)) if callable(rocket.center_of_mass_without_motor) else float(rocket.center_of_mass_without_motor)
sample_a_cg = float(sample_a.center_of_mass_without_motor(0)) if callable(sample_a.center_of_mass_without_motor) else float(sample_a.center_of_mass_without_motor)

if abs(sample_a_cg - nominal_cg) > 1e-6:
    print(f"VERDICT: Case A's sampled CG ({sample_a_cg:.4f}) differs from the nominal CG ({nominal_cg:.4f}) even though no CG uncertainty was requested - center_of_mass_without_motor is NOT preserved by default, must be re-passed explicitly to StochasticRocket.")
else:
    print("VERDICT: Case A's sampled CG matches the nominal CG - no bug found for THIS rocket/case (see docs/rocketpy_issues/README.md for the .ork-based case where this mattered).")
