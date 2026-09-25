"""Phase 4: Monte Carlo + landing ellipse (2026-09-26 review, item 3).

Uses rocketpy's own StochasticEnvironment/StochasticSolidMotor/
StochasticRocket/StochasticFlight/MonteCarlo classes - this module wires
them to bup_rocketpy's parsed .ork/.eng data and supplies sensible
default uncertainties, each carrying its source (CLAUDE.md Sec 6 Phase 4:
"every uncertainty is editable and shows its source; if none, label it
'no source, low confidence'").
"""
import math
import os
from dataclasses import dataclass, field

import numpy as np
from rocketpy import Flight, StochasticEnvironment, StochasticFlight, StochasticNoseCone, StochasticRocket, StochasticSolidMotor, StochasticTrapezoidalFins


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


def run_monte_carlo(parsed, parsed_eng, eng_path, power_off_drag, power_on_drag, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, output_dir, include_recovery=True, progress_callback=None, seed=None, cancel_check=None):
    """Runs N stochastic flights, returns a MonteCarloResult plus landing-
    ellipse params (drogue/main - PROMETEO only has one recovery event, so
    "drogue" and "main" here are the same single event unless the loaded
    .ork has two; the caller decides which to label which).
    progress_callback(i, n) is called after each simulation if given -
    that's the hook the UI's progress bar uses (CLAUDE.md: "runs in the
    background, with progress, cancellable"). cancel_check(), if given, is
    also polled after each sample; when it returns True the loop stops
    early and whatever samples completed so far are still returned (a
    cancelled run must save its partial results, not throw them away)."""
    from bup_rocketpy import translate

    os.makedirs(output_dir, exist_ok=True)
    u = {x.name: x for x in uncertainties if x.enabled}

    motor = translate.build_motor(parsed_eng, eng_path)
    mass_est = translate.MassEstimate(dry_mass_kg, dry_cg_m, "provided to run_monte_carlo")
    rocket = translate.build_rocket(parsed, motor, mass_est, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=include_recovery)
    env = translate.build_environment(parsed.launch)
    from rocketpy import Flight
    flight = Flight(rocket=rocket, environment=env, rail_length=parsed.launch.rail_length_m,
                     inclination=parsed.launch.inclination_deg, heading=parsed.launch.rail_direction_deg, terminate_on_apogee=not include_recovery)

    # Seeding: see _seeded_rng's docstring for why this whole construction
    # block runs inside it (needed for Phase 6's "same random seeds"
    # common-random-numbers drag comparison).
    with _seeded_rng(seed):
        stochastic_env = StochasticEnvironment(environment=env, wind_velocity_x_factor=(1, u["wind_speed_ms"].std_dev / max(u["wind_speed_ms"].nominal, 0.1)) if "wind_speed_ms" in u else (1, 0))
        stochastic_motor = StochasticSolidMotor(solid_motor=motor, total_impulse=(motor.total_impulse, u["total_impulse_Ns"].std_dev) if "total_impulse_Ns" in u else None)
        stochastic_rocket = StochasticRocket(
            rocket=rocket,
            mass=(dry_mass_kg, u["dry_mass_kg"].std_dev) if "dry_mass_kg" in u else None,
            # center_of_mass_without_motor MUST be passed explicitly - rocketpy's
            # StochasticRocket.create_object() does not preserve an externally
            # overridden CG otherwise (it falls back to the Rocket's own
            # geometric/component-based CG, which for a rocket built via
            # translate.build_rocket - aero surfaces added with no material
            # density - is wildly wrong). Found empirically 2026-09-26: every
            # sampled rocket came out ~-8.5 cal unstable, consistently, until
            # this was added. See PROGRESS.md.
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
        stochastic_flight = StochasticFlight(
            flight=flight,
            inclination=(parsed.launch.inclination_deg, u["inclination_deg"].std_dev) if "inclination_deg" in u else None,
            heading=(parsed.launch.rail_direction_deg, u["heading_deg"].std_dev) if "heading_deg" in u else None,
        )

    # NOTE: deliberately NOT using rocketpy's own top-level MonteCarlo
    # orchestrator here. rocketpy==1.13.0 ships it with an explicit
    # "still under testing" warning, and in practice it crashes outright
    # (AttributeError on Flight.apogee_y) whenever a sampled configuration
    # comes out badly unstable - which a wide-enough Monte Carlo WILL
    # occasionally draw, by design. That's not a corner case to work
    # around, it's the normal job of a Monte Carlo: some tail samples are
    # unphysical and should be excluded, not allowed to kill the whole
    # batch. So this replicates MonteCarlo's own per-sample construction
    # (StochasticRocket.create_object() + StochasticEnvironment.create_object()
    # + StochasticFlight's own randomized rail/inclination/heading - see
    # rocketpy.simulation.monte_carlo.MonteCarlo.__run_single_simulation,
    # which this mirrors exactly) inside a try/except per sample.
    mc_filename = os.path.join(output_dir, "monte_carlo_run")
    apogees, impact_xs, impact_ys = [], [], []
    n_excluded = 0
    exclusion_reasons = []
    for i in range(n_simulations):
        try:
            sample_rocket = stochastic_rocket.create_object()
            sample_env = stochastic_env.create_object()
            sample_flight = Flight(
                rocket=sample_rocket, environment=sample_env,
                rail_length=stochastic_flight._randomize_rail_length(),
                inclination=stochastic_flight._randomize_inclination(),
                heading=stochastic_flight._randomize_heading(),
                terminate_on_apogee=not include_recovery,
            )
            apogees.append(sample_flight.apogee - sample_env.elevation)
            if include_recovery:  # ballistic (terminate_on_apogee=True) never reaches a real impact
                impact_xs.append(sample_flight.x_impact)
                impact_ys.append(sample_flight.y_impact)
        except Exception as exc:  # a degenerate/unstable tail sample - exclude it, don't kill the batch
            n_excluded += 1
            if len(exclusion_reasons) < 10:
                exclusion_reasons.append(f"sample {i}: {type(exc).__name__}: {exc}")
        if progress_callback:
            progress_callback(i + 1, n_simulations)
        cancelled = cancel_check is not None and cancel_check()
        if cancelled:
            break
    else:
        cancelled = False

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
