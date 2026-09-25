"""Minimal repro: StochasticRocket.add_nose()/add_trapezoidal_fins()
crash when given a plain (non-Stochastic) NoseCone/TrapezoidalFins - the
natural, DOCUMENTED thing to pass (their own docstrings say
"nose : StochasticNoseCone or NoseCone").

ROOT CAUSE, confirmed by reading rocketpy/stochastic/stochastic_rocket.py
directly (line ~276, shared `_add_surfaces()` helper used by add_nose,
add_trapezoidal_fins, and add_elliptical_fins):

    if isinstance(surfaces, type_):
        surfaces = stochastic_type(component=surfaces)

This always calls the wrapper class with `component=`, but:
  - StochasticNoseCone.__init__ wants `nosecone=`
  - StochasticTrapezoidalFins.__init__ wants `trapezoidal_fins=`
Neither accepts `component=` - so passing a plain NoseCone/
TrapezoidalFins through the PUBLIC, documented add_nose()/
add_trapezoidal_fins() API always raises TypeError.

CONSEQUENCE (also demonstrated below): if a caller works around the
crash by not calling add_nose()/add_trapezoidal_fins() at all, the
StochasticRocket ends up with ZERO aerosurfaces - cp_position(0) == 0,
producing a huge, completely fake "instability" that has nothing to do
with any real uncertainty in the inputs (easy to misdiagnose as "my
uncertainty ranges are too wide" instead of "my rocket has no fins").
"""
import sys

sys.path.insert(0, "docs/rocketpy_issues")
from _minimal_rocket import build_rocket  # noqa: E402

from rocketpy.stochastic import (  # noqa: E402
    StochasticNoseCone,
    StochasticRocket,
    StochasticTrapezoidalFins,
)

rocket = build_rocket()
nose = rocket.nosecones[0]
fins = rocket.fins[0]

stochastic_rocket = StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.1))

print("--- calling the PUBLIC, documented API with a plain NoseCone/TrapezoidalFins ---")
try:
    stochastic_rocket.add_nose(nose=nose)
    print("add_nose(nose=<plain NoseCone>) worked")
except TypeError as exc:
    print(f"add_nose(nose=<plain NoseCone>) FAILED: {exc}")
try:
    stochastic_rocket.add_trapezoidal_fins(fins=fins)
    print("add_trapezoidal_fins(fins=<plain TrapezoidalFins>) worked")
except TypeError as exc:
    print(f"add_trapezoidal_fins(fins=<plain TrapezoidalFins>) FAILED: {exc}")

sample_broken = stochastic_rocket.create_object()
print(f"\nWithout a workaround: sampled rocket has {len(sample_broken.nosecones)} nose cone(s), {len(sample_broken.fins)} fin set(s), cp_position(0)={sample_broken.cp_position(0)}")

print("\n--- WORKAROUND: pre-build the Stochastic* wrapper with its REAL kwarg name, pass that in instead ---")
stochastic_rocket_2 = StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.1))
stochastic_rocket_2.add_nose(nose=StochasticNoseCone(nosecone=nose))
stochastic_rocket_2.add_trapezoidal_fins(fins=StochasticTrapezoidalFins(trapezoidal_fins=fins))
sample_fixed = stochastic_rocket_2.create_object()
print(f"With the workaround: sampled rocket has {len(sample_fixed.nosecones)} nose cone(s), {len(sample_fixed.fins)} fin set(s), cp_position(0)={sample_fixed.cp_position(0)}")

print(f"\nVERDICT: confirmed bug in rocketpy 1.13.0 - _add_surfaces() hardcodes `component=` which neither StochasticNoseCone nor StochasticTrapezoidalFins accept. Workaround: build the Stochastic* wrapper yourself with its real kwarg name ('nosecone='/'trapezoidal_fins=') and pass THAT to add_nose()/add_trapezoidal_fins().")
