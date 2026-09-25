"""Minimal repro: can a Stochastic* class be seeded for reproducibility?

Two things checked:
1. Does passing `seed=` to StochasticEnvironment/StochasticSolidMotor/
   StochasticRocket/StochasticFlight's constructor work?
2. Does re-seeding numpy's GLOBAL legacy RNG (`numpy.random.seed(...)`)
   before construction make two runs produce identical samples?
"""
import sys

sys.path.insert(0, "docs/rocketpy_issues")
from _minimal_rocket import build_environment, build_motor, build_rocket  # noqa: E402

import numpy as np  # noqa: E402
from rocketpy import Flight  # noqa: E402
from rocketpy.stochastic import StochasticRocket  # noqa: E402

rocket = build_rocket()

print("--- (1) does StochasticRocket accept a seed= kwarg? ---")
try:
    StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.1), seed=42)
    print("StochasticRocket(..., seed=42) worked")
except TypeError as exc:
    print(f"StochasticRocket(..., seed=42) FAILED: {exc}")

print("\n--- (2) does numpy.random.seed() (legacy global RNG) make two create_object() calls identical? ---")


def sample_masses(n=5):
    sr = StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.3))
    return [sr.create_object().mass for _ in range(n)]


np.random.seed(1234)
run_a = sample_masses()
np.random.seed(1234)
run_b = sample_masses()
print(f"run A: {run_a}")
print(f"run B: {run_b}")
if run_a == run_b:
    print("VERDICT: numpy.random.seed() alone DOES make repeated sampling reproducible for this class.")
else:
    print("VERDICT: numpy.random.seed() (legacy global RNG) does NOT make sampling reproducible - rocketpy's Stochastic* classes use their own numpy.random.Generator(PCG64) instances (the modern numpy Generator API), which np.random.seed() has no effect on.")

print("\n--- (3) workaround: monkeypatch numpy.random.default_rng() during construction ---")


def sample_masses_seeded(seed, n=5):
    real_default_rng = np.random.default_rng
    np.random.default_rng = lambda *a, **kw: real_default_rng(seed)
    try:
        sr = StochasticRocket(rocket=rocket, mass=(rocket.mass, 0.3))
    finally:
        np.random.default_rng = real_default_rng
    return [sr.create_object().mass for _ in range(n)]


run_c = sample_masses_seeded(1234)
run_d = sample_masses_seeded(1234)
print(f"run C: {run_c}")
print(f"run D: {run_d}")
print("VERDICT (workaround): monkeypatching numpy.random.default_rng DOES make it reproducible." if run_c == run_d else "VERDICT (workaround): still not reproducible - needs further investigation.")
