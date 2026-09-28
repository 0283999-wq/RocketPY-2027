"""Phase 4: Monte Carlo + landing ellipse (2026-09-26 review, item 3).

Uses rocketpy's own StochasticEnvironment/StochasticSolidMotor/
StochasticRocket/StochasticFlight/MonteCarlo classes - this module wires
them to bup_rocketpy's parsed .ork/.eng data and supplies sensible
default uncertainties, each carrying its source (CLAUDE.md Sec 6 Phase 4:
"every uncertainty is editable and shows its source; if none, label it
'no source, low confidence'").
"""
import concurrent.futures
import math
import os
from dataclasses import dataclass, field

import numpy as np
from rocketpy import Flight, StochasticEnvironment, StochasticFlight, StochasticNoseCone, StochasticParachute, StochasticRocket, StochasticSolidMotor, StochasticTrapezoidalFins


@dataclass
class Uncertainty:
    name: str
    nominal: float
    std_dev: float
    source: str  # e.g. "measured (scale, +-5g)" or "no source, low confidence"
    enabled: bool = True


def default_uncertainties(dry_mass_kg, total_impulse_Ns, wind_speed_ms):
    """CLAUDE.md Phase 4's required list: wind (magnitude/direction), dry
    mass, total impulse, Cd factor, rail inclination/heading, deployment
    delays, parachute Cd*S. None of these std devs come from a measured
    campaign (no repeated-measurement data exists in this project yet) -
    all labeled accordingly, editable, not invented as if authoritative."""
    return [
        Uncertainty("wind_speed_ms", wind_speed_ms, max(wind_speed_ms * 0.3, 1.0), "no source, low confidence - guessed as 30% of the OpenRocket-recorded wind speed"),
        Uncertainty("wind_direction_deg", 0.0, 15.0, "no source, low confidence - typical launch-day wind direction variability"),
        Uncertainty("dry_mass_kg", dry_mass_kg, dry_mass_kg * 0.02, "no source, low confidence - assumed 2% (typical scale + component-count uncertainty for a student rocket)"),
        Uncertainty("dry_cg_m", 0.0, 0.01, "no source, low confidence - assumed +-1cm CG placement/measurement uncertainty. NOTE: rocketpy's StochasticRocket does NOT preserve an overridden center_of_mass_without_motor unless this is explicitly passed - found 2026-09-26, see PROGRESS.md"),
        Uncertainty("total_impulse_Ns", total_impulse_Ns, total_impulse_Ns * 0.02, "no source, low confidence - assumed 2%, typical SRAD motor-to-motor total impulse variation for KNSB"),
        Uncertainty("power_off_drag_factor", 1.0, 0.05, "no source, low confidence - assumed 5% Cd curve uncertainty"),
        Uncertainty("power_on_drag_factor", 1.0, 0.05, "no source, low confidence - assumed 5% Cd curve uncertainty"),
        Uncertainty("inclination_deg", 0.0, 2.0, "no source, low confidence - typical rail-angle setup tolerance, +-2 deg"),
        Uncertainty("heading_deg", 0.0, 5.0, "no source, low confidence - typical rail-heading setup tolerance, +-5 deg"),
        Uncertainty("parachute_lag_s", 0.0, 0.5, "no source, low confidence - avionics/ejection-charge delay jitter"),
        Uncertainty("parachute_cd_s_factor", 1.0, 0.10, "no source, low confidence - assumed 10% parachute Cd*S uncertainty"),
    ]


@dataclass
class MonteCarloResult:
    n_completed: int
    n_excluded: int
    apogee_samples: list
    apogee_mean: float
    apogee_p05: float
    apogee_p95: float
    impact_x_samples: list
    impact_y_samples: list
    filename: str
    exclusion_reasons: list = field(default_factory=list)
    cancelled: bool = False  # True if cancel_check() stopped the run early (n_completed+n_excluded < requested N)


def _ellipse_params(x, y, n_std):
    """1/2/3-sigma landing ellipse from the impact (x, y) sample cloud -
    eigen-decomposition of the sample covariance, per the standard
    "confidence ellipse" construction."""
    cov = np.cov(x, y)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]
    angle = math.degrees(math.atan2(eigvecs[1, 0], eigvecs[0, 0]))
    width, height = 2 * n_std * np.sqrt(np.clip(eigvals, 0, None))
    return {"center_x": float(np.mean(x)), "center_y": float(np.mean(y)), "width": float(width), "height": float(height), "angle_deg": angle}


import contextlib


@contextlib.contextmanager
def _seeded_rng(seed):
    """Workaround for rocketpy 1.13.0's Stochastic* classes not exposing a
    `seed=` constructor kwarg despite their base class (StochasticModel)
    supporting one - see the long comment in run_monte_carlo. Setting the
    resulting object's private RNG attribute AFTER construction does NOT
    work either: StochasticModel._set_stochastic() (called from
    __init__) captures each uncertainty tuple's sampler as an ALREADY-
    BOUND method of the generator that exists at construction time (e.g.
    `stochastic_rocket.mass = (5.66, 0.1, <bound method
    Generator(...).normal>)`), so replacing the generator afterward
    doesn't change what those already-bound methods point to - found
    empirically 2026-09-26 (a `_force_seed` post-hoc approach was tried
    first and silently did nothing). The only point that actually works
    is intercepting the exact `np.random.default_rng(seed)` call
    StochasticModel.__init__ makes, which is what this context manager
    does - scoped narrowly around just the 4 Stochastic* constructor
    calls, restored immediately after."""
    if seed is None:
        yield
        return
    real_default_rng = np.random.default_rng
    np.random.default_rng = lambda *_a, **_k: real_default_rng(seed)
    try:
        yield
    finally:
        np.random.default_rng = real_default_rng


def _run_one_mc_sample(parsed, parsed_eng, eng_path, power_off_drag, power_on_drag, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, u, include_recovery, sample_seed, inclination_deg=None, heading_deg=None, trajectory_points=0):
    """Builds ONE stochastic sample and flies it. Module-level (not a
    closure) and takes only plain/picklable arguments (dataclasses,
    dicts, floats, strings) so it can be sent to a separate OS process -
    see run_monte_carlo's docstring for why this runs in a
    ProcessPoolExecutor instead of a loop. Rebuilds the nominal motor/
    rocket/env/flight fresh per call rather than sharing one across
    samples (like the old single-process loop did): rocketpy's
    Stochastic* wrappers hold live, stateful RNGs and Function objects
    that don't survive being pickled to another process, so each worker
    needs its own. That setup is cheap (object construction, not
    simulation) next to the ~0.3-0.6s a Flight() itself takes, so
    duplicating it per sample costs little against the parallelism gained.

    Returns (apogee_agl_m, x_impact_or_None, y_impact_or_None); raises on
    a degenerate/unstable sample - the caller excludes it, same as the
    old per-sample try/except did.

    inclination_deg/heading_deg: 2026-09-26 review item E - lets the UI
    set the rail heading/inclination the operator actually plans to use
    on launch day (e.g. into the current wind), overriding the value
    stored in the .ork's saved simulation. None (the default) keeps the
    .ork's own value, so every existing caller/test is unaffected.
    """
    from bup_rocketpy import translate

    nominal_inclination = inclination_deg if inclination_deg is not None else parsed.launch.inclination_deg
    nominal_heading = heading_deg if heading_deg is not None else parsed.launch.rail_direction_deg

    motor = translate.build_motor(parsed_eng, eng_path)
    mass_est = translate.MassEstimate(dry_mass_kg, dry_cg_m, "provided to run_monte_carlo")
    rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=include_recovery)
    env = translate.build_environment(parsed.launch)
    flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m,
                     inclination=nominal_inclination, heading=nominal_heading, terminate_on_apogee=not include_recovery)

    # Seeding: see _seeded_rng's docstring for why this whole construction
    # block runs inside it (needed for Phase 6's "same random seeds"
    # common-random-numbers drag comparison). sample_seed is None unless
    # the caller passed a base `seed` - in that case it's one of N
    # independent sub-seeds (np.random.SeedSequence.spawn), not the same
    # seed repeated, or every parallel worker would draw identical
    # samples. With sample_seed=None, _seeded_rng is a no-op and each
    # process's own OS-entropy-seeded default_rng() (rocketpy's own
    # per-instance default) already gives independent randomness for
    # free - processes never share random state the way threads/a single
    # loop would.
    with _seeded_rng(sample_seed):
        stochastic_env = StochasticEnvironment(environment=env, wind_velocity_x_factor=(1, u["wind_speed_ms"].std_dev / max(u["wind_speed_ms"].nominal, 0.1)) if "wind_speed_ms" in u else (1, 0))
        stochastic_motor = StochasticSolidMotor(solid_motor=motor, total_impulse=(motor.total_impulse, u["total_impulse_Ns"].std_dev) if "total_impulse_Ns" in u else None)
        stochastic_rocket = StochasticRocket(
            rocket=rocket,
            mass=(dry_mass_kg, u["dry_mass_kg"].std_dev) if "dry_mass_kg" in u else None,
            # center_of_mass_without_motor is passed explicitly, matching
            # the Rocket's own value, as a defensive habit - kept even
            # after 2026-09-25's re-check (docs/rocketpy_issues/02_*.py)
            # found this is NOT itself a bug: in isolation, a
            # StochasticRocket with no CG factor given preserves the
            # nominal CG exactly. The original ~-8.5 cal "every sampled
            # rocket unstable" symptom (2026-09-26, first review pass)
            # was actually caused by docs/rocketpy_issues/03_*.py's bug
            # (add_nose()/add_trapezoidal_fins() silently failing to
            # attach any aerosurface - see add_nose/add_trapezoidal_fins
            # below), which alone produces cp_position()==0 regardless
            # of CG. See PROGRESS.md Item 6 for the full correction.
            # NOTE the sign: translate.build_rocket() converts dry_cg_m (positive,
            # m from nose) to the rocket's own "tail_to_nose" frame (negated)
            # before passing it to Rocket() - the override here must match that
            # SAME frame/sign, not the raw nose-frame value, or this silently
            # points the CG at the wrong end of the rocket.
            center_of_mass_without_motor=(-dry_cg_m, u["dry_cg_m"].std_dev) if "dry_cg_m" in u else (-dry_cg_m, 0),
            power_off_drag_factor=(1, u["power_off_drag_factor"].std_dev) if "power_off_drag_factor" in u else (1, 0),
            power_on_drag_factor=(1, u["power_on_drag_factor"].std_dev) if "power_on_drag_factor" in u else (1, 0),
        )
        stochastic_rocket.add_motor(stochastic_motor)
        # CRITICAL: StochasticRocket.create_object() does NOT carry over the
        # nose/fins/rail-buttons that were added to the nominal `rocket` via
        # rocket.add_nose()/add_trapezoidal_fins() - found empirically
        # 2026-09-26 (every sample came out with cp_position()==0, i.e. no
        # aerosurfaces at all, hence the earlier ~-8.5 cal "instability" that
        # had nothing to do with CG). Each aerosurface must be separately
        # registered on the StochasticRocket itself, or the sampled Rocket has
        # no lift/pitching-moment-producing surfaces whatsoever.
        # Workaround for a SECOND rocketpy 1.13.0 bug found while fixing the
        # first: StochasticRocket.add_nose()/add_trapezoidal_fins() internally
        # do `stochastic_type(component=surfaces)` when given a plain
        # NoseCone/TrapezoidalFins, but StochasticNoseCone/StochasticTrapezoidalFins
        # actually take `nosecone=`/`trapezoidal_fins=`, not `component=` - so
        # passing the plain surface raises TypeError. Pre-building the
        # Stochastic* wrapper ourselves and passing THAT in hits the other,
        # working branch of that method (it only re-wraps a plain surface).
        if parsed.nose is not None:
            stochastic_rocket.add_nose(StochasticNoseCone(nosecone=rocket.nosecones[0]))
        for fin_surface in rocket.fins:
            stochastic_rocket.add_trapezoidal_fins(StochasticTrapezoidalFins(trapezoidal_fins=fin_surface))
        # 2026-09-28 review item 3: SAME bug class as the nose/fins one
        # above (StochasticRocket.create_object() does NOT carry over
        # ANYTHING added to the nominal `rocket` via rocket.add_X() -
        # this one had just never been caught for parachutes specifically,
        # since a Monte Carlo run "completes" either way and only the
        # landing dispersion silently goes wrong, not an exception).
        # Verified empirically: sample_rocket.parachutes was [] every
        # time, reefed or not - the ballistic free-fall-shaped descent
        # this produces still LANDS somewhere, so "same ellipse area
        # with/without reefing" (Diego's report) reads as a plausible
        # result instead of an obvious crash. Every parachute the
        # nominal `rocket` actually has (1 for a normal chute, 2 for a
        # reefed one - see translate.build_rocket) must be individually
        # re-registered here, same as nose/fins.
        for chute in rocket.parachutes:
            cd_s_std = chute.cd_s * u["parachute_cd_s_factor"].std_dev if "parachute_cd_s_factor" in u else 0
            lag_std = u["parachute_lag_s"].std_dev if "parachute_lag_s" in u else 0
            # StochasticParachute's own docstring: "Pay special attention
            # to ensure the lag will not assume negative values based on
            # its mean and standard deviation" - a real deploy lag is
            # very commonly 0 (apogee-triggered, no added delay, true for
            # PROMETEO's own parachute), so randomizing it unconditionally
            # samples a NEGATIVE lag on close to half of all draws -
            # confirmed empirically: rocketpy logs "Trying to add flight
            # phase starting before the one preceding it" and produces a
            # corrupted/NaN trajectory for that sample. Only randomize
            # when the nominal lag is comfortably positive relative to
            # the std dev (2 sigma, ~97.7% chance of staying >=0);
            # otherwise this specific parachute's lag stays fixed at its
            # nominal value for every sample - cd_s is still randomized
            # either way.
            lag_is_safe = chute.lag - 2 * lag_std >= 0
            stochastic_rocket.add_parachute(StochasticParachute(
                parachute=chute,
                cd_s=(chute.cd_s, cd_s_std) if cd_s_std else None,
                lag=(chute.lag, lag_std) if lag_std and lag_is_safe else None,
            ))
        stochastic_flight = StochasticFlight(
            flight=flight,
            inclination=(nominal_inclination, u["inclination_deg"].std_dev) if "inclination_deg" in u else None,
            heading=(nominal_heading, u["heading_deg"].std_dev) if "heading_deg" in u else None,
        )
        sample_rocket = stochastic_rocket.create_object()
        sample_env = stochastic_env.create_object()
        sample_flight = Flight(
            rocket=sample_rocket, environment=sample_env,
            rail_length=stochastic_flight._randomize_rail_length(),
            inclination=stochastic_flight._randomize_inclination(),
            heading=stochastic_flight._randomize_heading(),
            terminate_on_apogee=not include_recovery,
        )

    apogee_agl = sample_flight.apogee - sample_env.elevation
    trajectory = None
    if trajectory_points > 1:
        # 2026-09-27 review item 7: a small, DECIMATED (x, y, z-AGL)
        # polyline per sample - just enough for the live Monte Carlo 3D
        # view (static/playback.js BUP.livemc) to draw a faint line as
        # each trajectory finishes. Kept tiny on purpose: this crosses a
        # process boundary (pickled back from the worker) for every one
        # of up to a few hundred samples, so it must stay cheap.
        t0, t1 = float(sample_flight.time[0]), float(sample_flight.t_final)
        step = (t1 - t0) / (trajectory_points - 1) if t1 > t0 else 0.0
        elevation = sample_env.elevation
        trajectory = [
            [float(sample_flight.x(t)), float(sample_flight.y(t)), float(sample_flight.z(t) - elevation)]
            for t in (t0 + i * step for i in range(trajectory_points))
        ]
    if include_recovery:  # ballistic (terminate_on_apogee=True) never reaches a real impact
        return apogee_agl, sample_flight.x_impact, sample_flight.y_impact, trajectory
    return apogee_agl, None, None, trajectory


def run_monte_carlo(parsed, parsed_eng, eng_path, power_off_drag, power_on_drag, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, output_dir, include_recovery=True, progress_callback=None, seed=None, cancel_check=None, max_workers=None, inclination_deg=None, heading_deg=None, on_sample_complete=None, trajectory_points=0):
    """Runs N stochastic flights IN PARALLEL across OS processes (one
    Flight() simulation doesn't parallelize internally, but N of them are
    embarrassingly parallel - CLAUDE.md never asked for this, added
    2026-09-26 at Diego's request for real wall-clock speed on his own
    multi-core machine, not just a background thread that keeps the page
    responsive while still running samples one at a time). Returns a
    MonteCarloResult plus landing-ellipse params (drogue/main - PROMETEO
    only has one recovery event, so "drogue" and "main" here are the same
    single event unless the loaded .ork has two; the caller decides which
    to label which).

    max_workers defaults to os.cpu_count() (every logical core) - each
    worker process is otherwise idle waiting on this one call, and a
    Flight() simulation is CPU-bound with a small memory footprint, so
    there's little reason to leave cores unused. Override it if a
    machine needs to keep some cores free for other work.

    inclination_deg/heading_deg: 2026-09-26 review item E - lets the
    operator set the rail heading/inclination they actually plan to use
    on launch day (e.g. pointed into the day's wind) before running the
    batch, instead of being stuck with whatever the .ork's saved
    simulation recorded. None (the default) keeps the .ork's own value.

    progress_callback(i, n) is called as EACH sample finishes (i =
    however many have completed so far, not sample i's own index -
    samples finish out of submission order under parallel execution)-
    that's the hook the UI's progress bar uses (CLAUDE.md: "runs in the
    background, with progress, cancellable"). cancel_check(), if given,
    is polled after each completion; when it returns True, all NOT-YET-
    STARTED samples are cancelled and whatever completed so far is still
    returned (a cancelled run must save its partial results, not throw
    them away) - already-running worker processes finish on their own
    rather than being killed mid-flight, the same "detach, don't kill"
    limitation as this review's Simulate-button timeout/cancel.

    on_sample_complete(trajectory_or_None, x_impact_or_None, y_impact_or_None)
    (2026-09-27 review item 7): called once per sample AS IT FINISHES,
    same timing as progress_callback but carrying that ONE sample's own
    data - the hook the live Monte Carlo 3D view uses to draw each
    trajectory/landing point as it lands, instead of waiting for the
    whole batch. trajectory_points>0 asks each worker to also return a
    small decimated (x, y, z-AGL) polyline for exactly this purpose;
    leave it 0 (the default) to skip that extra pickled payload when
    nothing is watching for it (e.g. every existing caller/test)."""
    os.makedirs(output_dir, exist_ok=True)
    u = {x.name: x for x in uncertainties if x.enabled}

    if seed is not None:
        sample_seeds = [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(seed).spawn(n_simulations)]
    else:
        sample_seeds = [None] * n_simulations

    mc_filename = os.path.join(output_dir, "monte_carlo_run")
    # 2026-09-26: results are stored BY SAMPLE INDEX, not in whatever
    # order workers happen to finish in (concurrent.futures.as_completed
    # makes no ordering guarantee) - analysis.drag_comparison's "common
    # random numbers" feature (CLAUDE.md Sec 6 point 2) pairs
    # result_a.apogee_samples[i] against result_b.apogee_samples[i]
    # index-by-index across two SEPARATE run_monte_carlo calls that share
    # the same seed, expecting sample i to mean the same thing in both -
    # true with the old single-process loop (deterministic submission AND
    # completion order), broken by parallelizing until this was caught by
    # test_drag_comparison_with_identical_curves_gives_zero_difference
    # (identical drag curves + a shared seed no longer gave an exactly
    # zero difference, since two runs could complete their otherwise-
    # identical samples in two different relative orders).
    apogees_by_index = [None] * n_simulations
    impact_x_by_index = [None] * n_simulations
    impact_y_by_index = [None] * n_simulations
    excluded_indices = set()
    exclusion_reasons = []
    n_workers = max_workers or os.cpu_count() or 1
    completed = 0
    cancelled = False

    executor = concurrent.futures.ProcessPoolExecutor(max_workers=n_workers)
    try:
        futures = {
            executor.submit(_run_one_mc_sample, parsed, parsed_eng, eng_path, power_off_drag, power_on_drag, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, u, include_recovery, sample_seeds[i], inclination_deg, heading_deg, trajectory_points): i
            for i in range(n_simulations)
        }
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            trajectory = None
            try:
                apogee, x_impact, y_impact, trajectory = future.result()
                apogees_by_index[i] = apogee
                if include_recovery:
                    impact_x_by_index[i] = x_impact
                    impact_y_by_index[i] = y_impact
            except Exception as exc:  # a degenerate/unstable tail sample - exclude it, don't kill the batch
                excluded_indices.add(i)
                if len(exclusion_reasons) < 10:
                    exclusion_reasons.append(f"sample {i}: {type(exc).__name__}: {exc}")
            completed += 1
            if progress_callback:
                progress_callback(completed, n_simulations)
            if on_sample_complete and i not in excluded_indices:
                on_sample_complete(trajectory, impact_x_by_index[i] if include_recovery else None, impact_y_by_index[i] if include_recovery else None)
            if cancel_check is not None and cancel_check():
                cancelled = True
                break
    finally:
        # cancel_futures=True drops every NOT-YET-STARTED sample instead
        # of waiting for the full pool to drain - the point of Cancel is
        # to return control promptly, not to wait out however many
        # samples happened to already be running.
        executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

    # Indices left as None are either excluded (recorded separately in
    # excluded_indices) or never attempted at all (cancelled before that
    # sample's future was submitted/completed) - both are simply dropped
    # here, same as the old sequential loop dropped whatever a `break`
    # left untried. What's kept preserves ascending sample-index order.
    apogees = [v for v in apogees_by_index if v is not None]
    if include_recovery:
        impact_xs = [v for v in impact_x_by_index if v is not None]
        impact_ys = [v for v in impact_y_by_index if v is not None]
    else:
        impact_xs, impact_ys = [], []
    n_excluded = len(excluded_indices)

    if apogees:
        arr = np.array(apogees)
        mean, p05, p95 = float(arr.mean()), float(np.percentile(arr, 5)), float(np.percentile(arr, 95))
    else:
        mean = p05 = p95 = float("nan")

    return MonteCarloResult(
        n_completed=len(apogees), n_excluded=n_excluded, apogee_samples=apogees, apogee_mean=mean, apogee_p05=p05, apogee_p95=p95,
        impact_x_samples=impact_xs, impact_y_samples=impact_ys, filename=mc_filename, exclusion_reasons=exclusion_reasons,
        cancelled=cancelled,
    )


def landing_ellipses(mc_result):
    if len(mc_result.impact_x_samples) < 2:
        return {}
    x, y = np.array(mc_result.impact_x_samples), np.array(mc_result.impact_y_samples)
    return {n: _ellipse_params(x, y, n) for n in (1, 2, 3)}
