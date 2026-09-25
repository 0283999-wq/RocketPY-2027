# rocketpy==1.13.0 bugs found while building this app

Each numbered script here is a minimal, self-contained reproduction
(only `rocketpy` + a tiny inline-data rocket in `_minimal_rocket.py` -
no `bup_rocketpy` import, no PROMETEO files) you can run directly:

```powershell
py -3.12 -m pip install rocketpy==1.13.0
py -3.12 docs\rocketpy_issues\01_montecarlo_simulate_apogee_y_default_export.py
```

**I could not check these against rocketpy's existing GitHub issues** -
this session's network access doesn't reach github.com's web UI or API
(only `git clone`/`fetch`, which can't search issues). Please search
<https://github.com/RocketPy-Team/RocketPy/issues> for each one before
submitting, in case it's already reported - I don't want to file a
duplicate on your behalf.

## Verdict summary

| # | Claim | Verdict |
|---|---|---|
| 1 | `MonteCarlo.simulate()` crashes on an unstable/degenerate sample | **Confirmed**, but the ORIGINAL description was imprecise - see below |
| 2 | `StochasticRocket.create_object()` drops an overridden CG | **NOT confirmed as a separate bug** - retracted, see the script |
| 3 | `StochasticRocket.add_nose()`/`add_trapezoidal_fins()` crash on a plain surface | **Confirmed**, exact line-level root cause found |
| 4 | Stochastic classes ignore `numpy.random.seed()` | **Confirmed** (expected, given they use the modern `Generator` API - see below) |
| 5 | `Environment.set_atmospheric_model`'s `wind_u`/`wind_v` are ignored for `standard_atmosphere` | **Confirmed**, and it's "documented" only in a docstring nobody reading `set_atmospheric_model()` alone would see |

Bugs #1 and #3 are the ones I'd actually recommend filing - they're
unambiguous, have an exact root cause, and a real fix is small. #4 is
arguably "working as designed" (see below) - more of a documentation gap
than a bug. #5 is somewhere in between.

---

## 1. `MonteCarlo.simulate()` crashes when a sample never reaches apogee

**File:** `01_montecarlo_simulate_apogee_y_default_export.py`

**Correction from the first review pass:** the earlier report said "the
default export list references a Flight attribute that crashes on any
unstable sample," implying `apogee_x`/`apogee_y` are always invalid.
That's wrong - they're normal, valid `Flight` attributes for a flight
that reaches a proper apogee. The REAL trigger is narrower and more
interesting: for a sample so unstable it never reaches a recognized
apogee event (immediate tumble/blow-up), `apogee_x`/`apogee_y` are never
set at all (they're populated inside the apogee-event handler), and
`MonteCarlo.__evaluate_flight_outputs()`'s dict comprehension
(`getattr(flight, export_item)` for every item in the default export
list) then raises a bare `AttributeError` that is NOT caught by
whatever per-sample error handling `MonteCarlo` has for physics
failures - it kills the entire `simulate()` call instead of skipping
that one sample.

**Draft issue text:**

> **Title:** `MonteCarlo.simulate()` crashes with `AttributeError` when a
> sample's Flight never reaches a recognized apogee event
>
> **Body:**
> When a stochastically-sampled rocket is unstable enough that its
> `Flight` never reaches a proper apogee event (e.g. it tumbles
> immediately), `Flight.apogee_x`/`Flight.apogee_y` are never populated
> (they appear to be set only inside the apogee-event handler). Because
> these are in `MonteCarlo`'s default `export_list`, the very next
> sample's `__evaluate_flight_outputs()` call raises a bare
> `AttributeError: 'Flight' object has no attribute 'apogee_x'`, which
> propagates all the way out of `simulate()` and kills the entire Monte
> Carlo run - not just that one degenerate sample.
>
> Given `MonteCarlo` already has infrastructure to skip/record failed
> samples (an `.errors.txt` output file), I'd expect a missing-apogee
> sample to be recorded as a failure and skipped, not to crash the whole
> batch. Minimal repro attached (rocketpy==1.13.0).
>
> Workaround: don't use `MonteCarlo.simulate()`'s own sampling loop;
> build the sample rockets/flights manually via
> `StochasticRocket.create_object()` and wrap each `Flight(...)` call in
> its own try/except.

---

## 2. (Retracted) `StochasticRocket` CG override

**File:** `02_stochastic_rocket_cg_override_dropped.py`

Re-tested in isolation and does **not** reproduce - a `StochasticRocket`
built with no CG factor preserves the nominal `Rocket`'s CG exactly. The
original ~-8.5 cal "every sample unstable" symptom that led to this
claim was actually caused by bug #3 below (a `StochasticRocket` with
zero aerosurfaces attached has `cp_position()` stuck at/near 0,
independent of CG). **No issue to file for this one** - keeping the
script on record as a "checked and it wasn't a bug" data point, since
tonight's instructions specifically asked to verify each claim rather
than assume all of them were real.

---

## 3. `StochasticRocket.add_nose()`/`add_trapezoidal_fins()` crash on a plain surface

**File:** `03_stochastic_add_nose_fins_component_kwarg.py`

**Root cause, exact:** `stochastic_rocket.py`'s shared `_add_surfaces()`
helper (used by `add_nose`, `add_trapezoidal_fins`, and
`add_elliptical_fins`) does:

```python
if isinstance(surfaces, type_):
    surfaces = stochastic_type(component=surfaces)
```

`StochasticNoseCone.__init__` wants `nosecone=`, and
`StochasticTrapezoidalFins.__init__` wants `trapezoidal_fins=` - neither
accepts `component=`. So calling `add_nose()`/`add_trapezoidal_fins()`
with a plain `NoseCone`/`TrapezoidalFins` - exactly what their own
docstrings say is valid ("nose : StochasticNoseCone or NoseCone") -
always raises `TypeError`. If a caller works around the crash by simply
not calling `add_nose()`/`add_trapezoidal_fins()`, the resulting
`StochasticRocket` silently has **zero aerosurfaces**, and
`cp_position()` sits at/near 0 - a huge, completely fake instability
that has nothing to do with the actual sampled uncertainties (see #2
above for exactly how easy this is to misdiagnose as a CG bug instead).

**Draft issue text:**

> **Title:** `StochasticRocket.add_nose()`/`add_trapezoidal_fins()` raise
> `TypeError` on a plain `NoseCone`/`TrapezoidalFins`, contrary to their
> own docstrings
>
> **Body:**
> `add_nose()`'s docstring says its `nose` parameter accepts
> `StochasticNoseCone or NoseCone`, and `add_trapezoidal_fins()` says
> the same for `StochasticTrapezoidalFins or TrapezoidalFins`. In
> practice, passing a plain `NoseCone`/`TrapezoidalFins` (e.g. one
> already attached to an existing `Rocket`, the natural thing to reuse
> when building a `StochasticRocket` from a validated design) always
> raises:
> ```
> TypeError: StochasticNoseCone.__init__() got an unexpected keyword argument 'component'
> ```
> Root cause: `StochasticRocket._add_surfaces()` calls
> `stochastic_type(component=surfaces)`, but neither
> `StochasticNoseCone` (`nosecone=`) nor `StochasticTrapezoidalFins`
> (`trapezoidal_fins=`) accept a `component` kwarg. This looks like a
> straightforward rename/refactor that missed updating
> `_add_surfaces()` - a one-line fix per surface type (or a small
> dispatch table mapping `stochastic_type` to its real kwarg name).
> Minimal repro attached (rocketpy==1.13.0).
>
> This is worth prioritizing: a caller who works around the crash by
> skipping `add_nose()`/`add_trapezoidal_fins()` gets a
> `StochasticRocket` with **no aerosurfaces at all**, which fails
> silently (no error) with a nonsensical `cp_position()` near 0 - very
> easy to misattribute to the wrong cause (I initially misdiagnosed it
> as a CG-override bug, see the attached script #2).
>
> Workaround: pre-build the `Stochastic*` wrapper yourself with its real
> kwarg name and pass THAT to `add_nose()`/`add_trapezoidal_fins()`
> (their internal `isinstance(surfaces, stochastic_type)` branch skips
> the broken re-wrap when you do this).

---

## 4. Stochastic classes ignore `numpy.random.seed()`

**File:** `04_stochastic_classes_ignore_seed.py`

None of the 4 `Stochastic*` classes accept a `seed=` constructor
argument, and seeding numpy's legacy global RNG
(`numpy.random.seed(...)`) beforehand has no effect on their sampling -
because they each construct their own `numpy.random.Generator(PCG64)`
instance internally (the modern numpy random API), which is
architecturally independent of the legacy global RNG `numpy.random.seed()`
controls. This is arguably reasonable/intentional design (the modern
`Generator` API is what numpy itself recommends over global seeding),
but there is no supported way to get REPRODUCIBLE sampling at all - for
common-random-numbers variance reduction (comparing two designs under
"the same" random draws) or just a reproducible bug report, a caller
currently has no choice but to monkeypatch `numpy.random.default_rng`
around construction (workaround included in the script; this repo's
`bup_rocketpy/monte_carlo.py` uses exactly this).

**Draft issue text:**

> **Title:** No supported way to get reproducible sampling from
> `Stochastic*` classes
>
> **Body:**
> None of `StochasticEnvironment`/`StochasticSolidMotor`/
> `StochasticRocket`/`StochasticFlight` accept a `seed` parameter, and
> `numpy.random.seed()` (the legacy global RNG) has no effect on their
> sampling, since each instance builds its own
> `numpy.random.Generator(PCG64)` via `numpy.random.default_rng()`
> internally. This makes two reasonable things impossible without a
> private-API monkeypatch: (1) a reproducible Monte Carlo run for
> debugging/CI, and (2) "common random numbers" variance reduction when
> comparing two design variants (e.g. two drag-curve options) - you want
> BOTH variants to draw the identical wind/mass/etc. samples so the only
> difference in the output is attributable to the thing you changed, not
> sampling noise.
>
> Feature request: accept an optional `seed` (or an injectable
> `numpy.random.Generator`) in each `Stochastic*` constructor, or at
> minimum a documented, non-monkeypatch way to control their RNG.
> Workaround used today (fragile, relies on construction-order
> monkeypatching `numpy.random.default_rng`) attached.

---

## 5. `Environment.set_atmospheric_model`'s `wind_u`/`wind_v` are silently ignored for `standard_atmosphere`

**File:** `05_environment_wind_ignored_for_standard_atmosphere.py`

`set_atmospheric_model(type="standard_atmosphere", wind_u=..., wind_v=...)`
accepts and documents `wind_u`/`wind_v` as generic parameters, but for
`type="standard_atmosphere"` specifically they are silently discarded:
that branch calls `process_standard_atmosphere()`, whose OWN docstring
says "the wind profiles are set to zero" - but `set_atmospheric_model()`
itself gives no indication of this per-type behavior difference, and
raises no warning when a caller passes wind values that will be
ignored. `env.add_wind_gust(wind_u, wind_v)`, called AFTER
`set_atmospheric_model()`, is the supported way to add a constant wind
on top.

**Draft issue text:**

> **Title:** `set_atmospheric_model(type="standard_atmosphere",
> wind_u=..., wind_v=...)` silently ignores wind_u/wind_v with no
> warning
>
> **Body:**
> `set_atmospheric_model()`'s docstring lists `wind_u`/`wind_v` as
> generic optional parameters. For `type="standard_atmosphere"`
> specifically, they have no effect at all - the branch calls
> `process_standard_atmosphere()`, which unconditionally zeroes every
> wind-related function. This is technically documented in
> `process_standard_atmosphere()`'s own docstring ("Note that the wind
> profiles are set to zero"), but not in `set_atmospheric_model()` - the
> entry point almost everyone actually calls - and no warning is raised
> when wind_u/wind_v are passed alongside `type="standard_atmosphere"`.
> I lost real time chasing an unrelated-looking apogee mismatch before
> realizing wind I'd explicitly requested was silently being thrown
> away with no error.
>
> Suggested fix: either honor `wind_u`/`wind_v` for
> `type="standard_atmosphere"` too (layering them the same way
> `add_wind_gust()` does), or raise a `UserWarning` when non-zero
> `wind_u`/`wind_v` are passed with a type that ignores them.
> Minimal repro attached (rocketpy==1.13.0).
