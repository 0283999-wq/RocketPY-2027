"""Translates a parsed .ork (+ a parsed .eng) into rocketpy Environment,
SolidMotor, Rocket and Flight objects.

Coordinate frame: CLAUDE.md Sec 4.3 states RocketPy uses
coordinate_system_orientation="nose_to_tail". The validated PROMETEO
reference implementation (reference/prometeo_mission44/src/prometeo/rocket.py)
instead uses "tail_to_nose" with the origin at the nose tip, i.e. position
= -x_m_from_nose - and that code passed its own mass/inertia acceptance
check. THIS IS A DISCREPANCY - flagged for Diego rather than silently
picked one way; this module follows the validated reference code
("tail_to_nose"), not the CLAUDE.md prose, until that's confirmed.

Mass/inertia: an .ork's own <overridemass>/<overridesubcomponentsmass> is
used whenever present (it's a team-measured number, the most reliable
source available). Where no override exists, mass and inertia are
estimated geometrically from each component's material bulk density
(thin-shell cylinder/cone approximation) - labelled APPROXIMATE, per
CLAUDE.md Sec 4.3 "Inertias" and Rule 2 (never invent without a source).
This is NOT a substitute for a measured mass; it exists so the app can
still produce a flyable model when a component has no override and no
mass column to fall back on.
"""

import math
from dataclasses import dataclass, field

from rocketpy import Environment, Flight, Rocket, SolidMotor


@dataclass
class MassEstimate:
    mass_kg: float
    cg_m: float  # m from nose tip
    source: str  # "override" or "geometric estimate"


def _shell_cylinder_mass_cg_inertia(length, radius, thickness, density, fore_m):
    """Thin-to-moderate walled tube segment. Returns (mass, cg_m_from_nose,
    I_axial_about_own_cg, I_transverse_about_own_cg)."""
    if None in (length, radius, thickness, density) or length <= 0 or radius <= 0:
        return 0.0, fore_m, 0.0, 0.0
    r_out, r_in = radius, max(radius - thickness, 0.0)
    volume = math.pi * (r_out**2 - r_in**2) * length
    mass = volume * density
    cg = fore_m + length / 2.0
    i_axial = 0.5 * mass * (r_out**2 + r_in**2)
    i_transverse = mass * (3 * (r_out**2 + r_in**2) + length**2) / 12.0
    return mass, cg, i_axial, i_transverse


def _cone_shell_mass_cg(length, radius, density, fore_m, thickness_assumed=0.002):
    """Nose cone / transition, approximated as a thin conical shell of
    constant thickness regardless of the real ogive/vonkarman/haack profile
    - the mass this gives is within a few percent of the true profile for
    typical thin composite/plastic nose cones, but is explicitly a shape
    approximation (see CLAUDE.md Sec 4.3 Inertias)."""
    if None in (length, radius, density) or length <= 0 or radius <= 0:
        return 0.0, fore_m, 0.0, 0.0
    slant = math.sqrt(length**2 + radius**2)
    lateral_area = math.pi * radius * slant
    mass = lateral_area * thickness_assumed * density
    cg = fore_m + 0.66 * length  # thin cone shell CG ~2/3 of the way to the base from apex
    i_axial = 0.5 * mass * radius**2  # thin-shell cone about its own axis, approximate
    i_transverse = mass * (3 * radius**2 / 20.0 + length**2 / 10.0)  # solid-cone-like approx, flagged
    return mass, cg, i_axial, i_transverse


def _fin_set_mass_cg(fin, body_radius):
    """Flat trapezoidal fin, uniform thickness, planform area from the
    stored root/tip/span/sweep - CG at the standard trapezoid centroid."""
    if fin.material_density is None:
        return 0.0, fin.position_m, 0.0, 0.0
    area_one = 0.5 * (fin.root_chord + fin.tip_chord) * fin.span
    mass_one = area_one * fin.thickness * fin.material_density
    mass = mass_one * fin.count
    # trapezoid centroid, measured from root-chord leading edge along the axial direction
    # trapezoid centroid along the chordwise (axial) direction, from root-chord LE
    rc, tc, sw = fin.root_chord, fin.tip_chord, fin.sweep_length
    if (rc + tc) > 1e-9:
        x_bar = sw * (2 * tc + rc) / (3 * (rc + tc)) + rc * (rc + 2 * tc) / (3 * (rc + tc))
    else:
        x_bar = rc / 2.0
    cg = fin.position_m + x_bar
    r_eff = body_radius + fin.span / 2.0
    i_axial = mass * r_eff**2  # fins as point masses at mean span radius, about roll axis
    i_transverse = mass * (fin.position_m - cg) ** 2  # placeholder, refined by caller's parallel-axis pass
    return mass, cg, i_axial, i_transverse


def _geometric_components(parsed):
    """Every structural component's own (mass, cg_m, i_axial, i_transverse),
    from material bulk density where present. Used both to estimate a total
    mass/CG when there's no whole-rocket override, and - regardless of any
    override - to estimate the *relative* mass distribution an override
    doesn't by itself provide (a rocket-wide override replaces the total,
    not the shape).

    A PER-COMPONENT override (e.g. a single bodytube's <overridemass> with
    override_subcomponents_mass=False - a real pattern: PROMETEO's own .ork
    overrides just the Fuselage shell's own mass, not the whole rocket) is
    applied here by substituting that one component's geometric mass with
    the override value, at its geometric CG/shape (inertia scaled by the
    mass ratio - an approximation, since the override doesn't say how the
    mass redistributed, only that the total for this component changed)."""
    per_component_override = {o.component: o.override_mass for o in parsed.mass_overrides if o.override_mass is not None and not o.override_subcomponents_mass}

    def apply_override(name, mass, cg, i_ax, i_tr):
        override = per_component_override.get(name)
        if override is None or mass <= 0:
            return mass, cg, i_ax, i_tr
        ratio = override / mass
        return override, cg, i_ax * ratio, i_tr * ratio

    components = []
    if parsed.nose is not None:
        radius = parsed.nose.aft_radius or 0.0
        components.append(apply_override(parsed.nose.name, *_cone_shell_mass_cg(parsed.nose.length, radius, parsed.nose.material_density, parsed.nose.position_m)))
    for tube in parsed.body_tubes:
        components.append(apply_override(tube.name, *_shell_cylinder_mass_cg_inertia(tube.length, tube.radius, tube.thickness, tube.material_density, tube.position_m)))
    for tr in parsed.transitions:
        r = tr.aft_radius or tr.fore_radius or 0.0
        components.append(apply_override(tr.name, *_cone_shell_mass_cg(tr.length, r, tr.material_density, tr.position_m)))
    body_radius = next((t.radius for t in parsed.body_tubes if t.radius), 0.05)
    for fin in parsed.fins:
        mass, comp_cg, _, _ = _fin_set_mass_cg(fin, body_radius)
        r_eff = body_radius + fin.span / 2.0
        components.append(apply_override(fin.name, mass, comp_cg, mass * r_eff**2, 0.0))
    for pm in parsed.point_masses:
        components.append((pm.mass, pm.position_m, 0.0, 0.0))
    # 2026-09-26 review item 1: a packed parachute has real mass (0.558 kg
    # for PROMETEO's own, more than any other single component here) and
    # was not counted at all before ork_reader.py started recording its
    # <overridemass> - see that file's parachute-branch comment.
    for chute in parsed.parachutes:
        override = per_component_override.get(chute.name)
        if override is not None:
            components.append((override, chute.position_m, 0.0, 0.0))
    return components


def estimate_dry_mass_and_cg(parsed):
    """Returns MassEstimate for the whole dry (no-motor) airframe.

    Mass: a rocket-wide/bodytube <overridemass> (with subcomponents
    included) wins when present - it's a team-measured number. Otherwise
    the geometric component masses are summed.

    CG: an explicit <overridecg> wins when present. Otherwise the CG is the
    mass-weighted average of the *geometric* component masses (this is
    valid even when the total mass itself came from an override: CG
    position depends on the relative distribution between components, not
    on the absolute total - the two numbers aren't coupled the way this
    function's early drafts assumed).

    If neither an override nor any component material density is
    available, mass is reported 0 with the failure reason - callers must
    not build a Rocket from that; it does not raise here so the import
    table can still show why.
    """
    total_override = next((o for o in parsed.mass_overrides if o.override_mass is not None), None)
    cg_override = next((o for o in parsed.mass_overrides if o.override_cg_m is not None), None)

    components = _geometric_components(parsed)
    geom_mass = sum(c[0] for c in components)

    if geom_mass > 0:
        geom_cg = sum(c[0] * c[1] for c in components) / geom_mass
    else:
        geom_cg = None

    if total_override is not None and total_override.override_subcomponents_mass:
        mass = total_override.override_mass
        mass_source = f"override on '{total_override.component}'"
    elif geom_mass > 0:
        mass = geom_mass
        mass_source = "geometric estimate (thin-shell approximation, see translate.py docstring)"
    else:
        return MassEstimate(0.0, 0.0, "FAILED: no mass override and no component material densities available - cannot build a Rocket from this")

    if cg_override is not None:
        cg = cg_override.override_cg_m
        cg_source = f"override cg on '{cg_override.component}'"
    elif geom_cg is not None:
        cg = geom_cg
        cg_source = "geometric estimate (mass-weighted component centroids)"
    else:
        return MassEstimate(mass, None, f"{mass_source}, but CG unknown: no overridecg and no component material densities to weight a geometric CG")

    return MassEstimate(mass, cg, f"mass: {mass_source}; cg: {cg_source}")


def estimate_dry_inertia(parsed, dry_mass_estimate):
    """Sums each geometric component's own moment of inertia plus its
    parallel-axis contribution about the overall dry CG. Returns
    (I_axial_roll, I_transverse_pitch_yaw) in kg m2. Approximate - see
    module docstring. Needs a resolved CG (dry_mass_estimate.cg_m is not
    None); raises otherwise rather than silently producing 0 - a rocket
    with unknown or zero inertia is not flyable (RocketPy's ODE integrator
    will misbehave, not just be imprecise)."""
    cg = dry_mass_estimate.cg_m
    if cg is None:
        raise ValueError("dry CG is unknown (see MassEstimate.source) - cannot estimate inertia without it; supply an <overridecg> or component material densities")

    i_axial_total = 0.0
    i_transverse_total = 0.0
    for mass, comp_cg, i_ax, i_tr in _geometric_components(parsed):
        d = comp_cg - cg
        i_axial_total += i_ax
        i_transverse_total += i_tr + mass * d**2

    return i_axial_total, i_transverse_total


def motor_grain_params(eng_header):
    """The single-BATES-equivalent-grain sizing shared by build_motor()
    and case_export.py's generated standalone script - kept in ONE place
    (2026-09-26 review item 3's "ONE path" rule) after case_export.py's
    own independent copy was found still using the old hardcoded
    grain_density=1750.0 that under-stated propellant mass by 18.8% (see
    build_motor's docstring) - meaning every exported LASC submission
    script carried that same bug even after it was fixed here, until
    case_export.py was changed to call this instead of re-deriving it.
    Returns (grain_outer_radius_m, grain_inner_radius_m, grain_height_m,
    grain_density_kgm3)."""
    h = eng_header
    grain_outer_r = (h.diameter_mm / 1000.0) / 2.0 * 0.95
    grain_inner_r = (h.diameter_mm / 1000.0) / 2.0 * 0.25
    grain_height = (h.length_mm / 1000.0) * 0.9
    grain_volume = math.pi * (grain_outer_r**2 - grain_inner_r**2) * grain_height
    grain_density = h.propellant_mass_kg / grain_volume if grain_volume > 0 else 1750.0
    return grain_outer_r, grain_inner_r, grain_height, grain_density


def build_motor(parsed_eng, eng_path, dry_mass_override_kg=None):
    """Builds a rocketpy SolidMotor from a parsed .eng. Grain geometry is
    NOT recoverable from a RASP file (it only has total propellant mass and
    the thrust curve) - rocketpy's SolidMotor needs grain dimensions for
    its own mass-flow model, so this builds a single-BATES-equivalent-grain
    approximation sized to match the .eng header's casing length/diameter.
    This reproduces total impulse and thrust curve exactly (rocketpy takes
    thrust_source directly) - the mass-vs-time SHAPE during burn is an
    approximation (flag this in the report) - but the grain DENSITY is
    solved backward from the assumed geometry so that
    SolidMotor.propellant_initial_mass exactly matches the .eng header's
    own declared propellant mass, not just a plausible-looking constant.

    2026-09-26 review item 3: a hardcoded grain_density=1750.0 (a generic
    "typical KNSB" value, not solved for) gave propellant_initial_mass=
    1.637 kg for PROMETEO's real .eng, vs. the file's own declared
    2.0167 kg - 18.8% LOW. Total liftoff mass (rocket.total_mass(0)) was
    therefore ~0.38 kg (3.6%) below what the SAME thrust curve was
    written for, at the SAME thrust - a lighter rocket getting identical
    thrust accelerates more and flies higher. This was found by
    comparing the app's motor build against
    reference/prometeo_mission44's independently-built one (which uses
    real measured GRAIN_DENSITY/dimensions, not a generic constant) on
    identical propellant mass - the two disagreed by exactly this
    amount. This is very likely the dominant single contributor to the
    "+10% high vs. OpenRocket/real flights" gap this review is chasing -
    see PROGRESS.md Item 3 for the before/after numbers.

    dry_mass_override_kg: use this instead of the .eng header's own
    total-minus-propellant figure - the SAME physical motor design can
    have a slightly different measured casing dry mass between individual
    units/flights (e.g. PROMETEO's July4 vs. Brasil-config motors),
    without a different thrust curve or a different .eng file."""
    h = parsed_eng.header
    grain_outer_r, grain_inner_r, grain_height, grain_density = motor_grain_params(h)

    # 2026-09-26 review: passing the raw eng_path let rocketpy re-parse the
    # .eng ITSELF (Motor.import_eng), which unconditionally prepends its own
    # (0, 0) point - its own docstring says "the .eng file must not contain
    # the 0 0 point". A real user-supplied .eng CAN legitimately start with
    # an explicit t=0 row (confirmed with a real file, "Kaboom" M1889,
    # whose second line is "0 0.01") - that collides with rocketpy's own
    # prepended (0, 0), two points at the same x, producing a divide-by-
    # zero in the thrust Function's slope calculation and a degenerate
    # (near-zero) thrust curve - which is exactly why every Monte Carlo
    # sample of a rocket using that motor apogee'd barely above the pad.
    # Passing our OWN already-parsed thrust_curve (a plain list, not a
    # file path) bypasses Motor.import_eng entirely, so this can't happen
    # regardless of what a given .eng file's own first line looks like.
    return SolidMotor(
        thrust_source=parsed_eng.thrust_curve,
        dry_mass=dry_mass_override_kg if dry_mass_override_kg is not None else h.total_mass_kg - h.propellant_mass_kg,
        dry_inertia=(0.01, 0.01, 0.001),  # not recoverable from RASP - placeholder, same as PROMETEO's own motor.py
        nozzle_radius=(h.diameter_mm / 1000.0) * 0.15,  # rough estimate, not in RASP header
        grain_number=1,
        grain_density=grain_density,  # solved to exactly match h.propellant_mass_kg - see docstring
        grain_outer_radius=grain_outer_r,
        grain_initial_inner_radius=grain_inner_r,
        grain_initial_height=grain_height,
        grain_separation=0.005,
        grains_center_of_mass_position=(h.length_mm / 1000.0) / 2.0,
        center_of_dry_mass_position=(h.length_mm / 1000.0) / 2.0,
        nozzle_position=0,
        # (first, last) timestamp of OUR OWN curve, not (0, burn_time_s) -
        # now that rocketpy no longer re-parses the file itself (see the
        # thrust_source comment above), its synthetic (0, 0) point that
        # used to make burn_time=(0, ...) always valid is gone; some real
        # .eng files' own first row isn't at t=0 (this one's isn't), so a
        # bare 0 here would be out of range and rocketpy would just clip it
        # with a warning - passing the curve's real bounds is both more
        # correct and warning-free.
        burn_time=(parsed_eng.thrust_curve[0][0], parsed_eng.burn_time_s),
        throat_radius=(h.diameter_mm / 1000.0) * 0.1,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )


def derive_dry_mass_and_inertia_from_with_motor(motor, total_mass_kg, motor_mass_loaded_kg, dry_mass_kg, cg_with_motor_m_from_nose, rocket_length_m, i_total_axial_kgm2=None, i_total_transverse_kgm2=None):
    """Derives the dry (no-motor) CG - and, if the total (with-motor)
    inertia is given, dry inertia too - from an OpenRocket reading that
    only reports the COMBINED with-motor figure, via parallel-axis
    subtraction of the motor's own contribution.

    2026-09-26 review item 3: generalizes the one-off derivation that
    used to live only in reference/prometeo_mission44/src/prometeo/
    rocket.py's _solve_dry_inertia() (itself only reachable by hand-
    building a parallel Rocket()/Flight() path, bypassing this module
    entirely) - moved here so the code-to-code/V1/V2 validation tests
    can compute the SAME derived numbers while still calling
    translate.build_rocket()/ork_to_flight(), the functions the app
    itself uses. That divergence (tests building rockets by hand,
    the app going through this module) was the actual root cause behind
    "the app agrees with OpenRocket to -0.7%, but the test harness says
    +10% on the identical input set" - not a physics bug at all.

    Assumes the motor's nozzle sits flush with the airframe's aft end
    (rocket_length_m from the nose tip) - the same assumption the
    original derivation made, flagged there as its main uncertainty.
    Returns (MassEstimate, i_axial_kgm2_or_None, i_transverse_kgm2_or_None).
    MassEstimate.cg_m is in the usual from-nose, positive-aft convention
    this module uses everywhere else (NOT the internal tail_to_nose sign
    used for the intermediate arithmetic).
    """
    to_rpy = _coordinate_transform("tail_to_nose")
    system_cg_rpy = to_rpy(cg_with_motor_m_from_nose)
    nozzle_rpy = to_rpy(rocket_length_m)
    motor_cg_rpy = nozzle_rpy + motor.center_of_mass(0)

    cg_dry_rpy = (system_cg_rpy * total_mass_kg - motor_mass_loaded_kg * motor_cg_rpy) / dry_mass_kg
    cg_dry_from_nose = -cg_dry_rpy  # undo the tail_to_nose sign flip for the returned MassEstimate

    mass_est = MassEstimate(dry_mass_kg, cg_dry_from_nose, f"derived from with-motor CG {cg_with_motor_m_from_nose:.4f} m via parallel-axis subtraction (translate.derive_dry_mass_and_inertia_from_with_motor)")

    i_axial = i_transverse = None
    if i_total_axial_kgm2 is not None and i_total_transverse_kgm2 is not None:
        d_dry = cg_dry_rpy - system_cg_rpy
        d_motor = motor_cg_rpy - system_cg_rpy
        i_motor_axial = motor.I_33(0)
        i_motor_transverse = motor.I_11(0)
        i_axial = i_total_axial_kgm2 - i_motor_axial  # roll axis: axial shift doesn't change it, no parallel-axis term
        i_transverse = i_total_transverse_kgm2 - dry_mass_kg * d_dry**2 - i_motor_transverse - motor_mass_loaded_kg * d_motor**2

    return mass_est, i_axial, i_transverse


@dataclass
class BestMassEstimate:
    mass_est: "MassEstimate"
    i_axial_kgm2: float
    i_transverse_kgm2: float
    inertia_source: str


def estimate_best_dry_mass_cg_inertia(parsed, parsed_eng, eng_path, ork_path=None):
    """2026-09-27 review item 1a: picks the BEST available dry mass/CG/
    inertia source, in priority order:

    1. A whole-rocket/subcomponent MASS override on the .ork
       (estimate_dry_mass_and_cg's own top priority already) - a
       team-measured number, unchanged, still wins outright.
    2. NEW: OpenRocket's OWN computed t=0 with-motor mass/CG/inertia,
       from the .ork's stored simulation databranch (parse_stored_
       simulation_references), minus the motor - via
       derive_dry_mass_and_inertia_from_with_motor(). This is strictly
       better than our own geometric thin-shell approximation whenever
       it's available: it's OpenRocket's own actual computed total,
       already accounting for every real component/material/hardware
       detail (inner tubes, centering rings, bulkheads, adhesive,
       overrides, "override subcomponents") that a from-scratch
       geometric approximation can't fully capture - closing the real
       Major Tom mass/CG mismatch Diego reported (OpenRocket 122 cm CG
       vs. this app's 80.4 cm, a ~2.7 kg/34% gap) without needing to
       perfectly reproduce OpenRocket's internal per-component model.
    3. The existing geometric thin-shell estimate (unchanged fallback,
       only reached with no override AND no usable stored simulation
       data - e.g. a geometry-only .ork nobody has simulated in
       OpenRocket yet).

    Returns a BestMassEstimate. Never raises for a missing stored sim -
    that's an expected, common case (falls through to step 3)."""
    from bup_rocketpy.ork_reader import airframe_length_m, parse_stored_simulation_references

    override_est = estimate_dry_mass_and_cg(parsed)
    has_mass_override = override_est.source.startswith("mass: override")

    if not has_mass_override and ork_path:
        refs = parse_stored_simulation_references(ork_path)
        # Same convention read_ork() itself uses for launch conditions:
        # the FIRST stored simulation in the file, not a specific name -
        # a .ork can (and PROMETEO's does) hold more than one, and there
        # is no general way to know which one the operator considers
        # authoritative without asking; using the first is at least
        # deterministic and documented, same as launch conditions already are.
        ref = next(iter(refs.values()), None)
        if ref is not None and ref.mass_with_motor_t0_kg and ref.motor_mass_t0_kg and ref.cg_with_motor_t0_m is not None:
            motor = build_motor(parsed_eng, eng_path)
            dry_mass_kg = ref.mass_with_motor_t0_kg - ref.motor_mass_t0_kg
            if dry_mass_kg > 0:
                rocket_length_m = airframe_length_m(parsed)
                mass_est, i_ax, i_tr = derive_dry_mass_and_inertia_from_with_motor(
                    motor, ref.mass_with_motor_t0_kg, ref.motor_mass_t0_kg, dry_mass_kg,
                    ref.cg_with_motor_t0_m, rocket_length_m,
                    # OpenRocket's own "Longitudinal moment of inertia" is
                    # the TRANSVERSE (pitch/yaw) value and "Rotational
                    # moment of inertia" is the AXIAL (roll) one - the
                    # opposite of what the names suggest in isolation
                    # (see openrocket_csv_export.py's own regression test
                    # for the numeric check that caught this the same day).
                    i_total_axial_kgm2=ref.i_rot_t0, i_total_transverse_kgm2=ref.i_long_t0,
                )
                mass_est.source = f"OpenRocket computed (stored simulation '{ref.name}', t=0, minus motor - see translate.estimate_best_dry_mass_cg_inertia)"
                if i_ax is not None and i_tr is not None and i_ax > 0 and i_tr > 0:
                    return BestMassEstimate(mass_est, i_ax, i_tr, f"OpenRocket computed (stored simulation '{ref.name}', minus motor)")
                i_ax_geom, i_tr_geom = estimate_dry_inertia(parsed, mass_est)
                return BestMassEstimate(mass_est, i_ax_geom, i_tr_geom, "geometric estimate (stored simulation had no usable inertia columns)")

    i_ax, i_tr = estimate_dry_inertia(parsed, override_est)
    inertia_source = "geometric estimate" if not has_mass_override else "geometric estimate (mass override present, but inertia is still estimated geometrically - the .ork doesn't store inertia directly)"
    return BestMassEstimate(override_est, i_ax, i_tr, inertia_source)


NOSE_SHAPE_MAP = {
    # OpenRocket XML <shape> value -> rocketpy NoseCone kind. Found by
    # feeding this translator a real .ork (PROMETEO's) - "ellipsoid" isn't
    # a string rocketpy recognizes at all (it wants "elliptical"), so this
    # would have failed silently->loudly on the very first real nose cone.
    "conical": "conical",
    "ogive": "tangent",  # OpenRocket's plain "ogive" is a tangent ogive; shapeparameter=1 confirms tangent
    "ellipsoid": "elliptical",
    "power": "powerseries",
    "parabolic": "parabolic",
    "haack": "vonkarman",  # OpenRocket's "haack" + shapeparameter selects the Haack variant; vonkarman (param=0.5) is the common default - TODO CONFIRM against shapeparameter when a non-default one is seen
}


def rocketpy_nose_kind(openrocket_shape):
    kind = NOSE_SHAPE_MAP.get(openrocket_shape.lower())
    if kind is None:
        raise ValueError(f"unrecognized OpenRocket nose shape {openrocket_shape!r} - add it to translate.NOSE_SHAPE_MAP rather than guessing")
    return kind


PARACHUTE_DEPLOY_EVENT_NOTES = {
    # 2026-09-26 review crash 2(a): OpenRocket's <deployevent> has more
    # values than "apogee"/"altitude" - the previous code treated
    # anything-not-"apogee" as an altitude trigger using deploy_altitude,
    # which is WRONG for "never" (this component has NO automatic
    # deployment configured in OpenRocket at all - deploy_altitude is
    # just a stored-but-inactive config value, not a live threshold).
    # PROMETEO's real .ork has exactly this: <deployevent>never</deployevent>,
    # because the real vehicle deploys via an SRAD altimeter at apogee
    # (confirmed in flight telemetry, not something OpenRocket's own
    # deployevent options model) - the app was reading that "never" as
    # "deploy at 200m AGL on the way down", so the rocket coasted in
    # ballistic free-fall from apogee (t=16.8s) to t=31.8s at ~120 m/s
    # before "deploying", producing a ~375g opening-shock spike that
    # swallowed the real max acceleration (boost phase, ~5g) entirely.
    "ejection": "OpenRocket 'ejection' deploy event (fires at the motor's own ejection-charge delay - rocketpy has no direct trigger for that) - approximated as apogee-triggered deployment.",
    "never": "OpenRocket 'never' deploy event (no automatic deployment is configured for this component in the .ork - typical of a real SRAD altimeter system OpenRocket's own deployment options don't model). Assumed apogee-triggered deployment - verify against the actual flight computer's configured deployment altitude/delay.",
}


def parachute_trigger(chute):
    """Maps an OpenRocket <deployevent> to a rocketpy Parachute trigger.
    Only "altitude" uses the .ork's own deploy_altitude as a live
    trigger threshold. Returns (trigger, warning_or_None) - the warning
    is None only for "apogee"/"altitude", which are read directly from
    the file with no assumption involved."""
    event = (chute.deploy_event or "").lower()
    if event == "altitude":
        return chute.deploy_altitude, None
    if event == "apogee":
        return "apogee", None
    return "apogee", PARACHUTE_DEPLOY_EVENT_NOTES.get(
        event, f"unrecognized deploy_event {chute.deploy_event!r} - assumed apogee-triggered deployment, verify manually."
    )


def required_cd_s_for_descent_rate(target_descent_rate_ms, mass_kg, air_density_kgm3=1.225, g=9.80665):
    """2026-09-26 review item D (new lettering): "target reefed descent
    rate" helper - inverts the standard terminal-velocity relation
    v = sqrt(2*m*g/(rho*Cd*S)) to solve for the Cd*S a reefed canopy
    needs to hit a target rate (e.g. "I want 30 m/s under the reefed
    stage"). This is an ESTIMATE from the same simplified hand-calc
    formula recovery.py already uses elsewhere in the app (constant
    ground-density approximation, not the sim's own varying-density
    integration) - labelled as such until measured by a real drop test,
    per Diego's own instruction not to invent unverified precision."""
    if target_descent_rate_ms <= 0:
        raise ValueError("target_descent_rate_ms must be positive")
    return 2 * mass_kg * g / (air_density_kgm3 * target_descent_rate_ms ** 2)


def parachute_import_notes(parsed):
    """(component, status, detail) rows for the import table, so a
    non-"apogee"/"altitude" deploy_event assumption is visible BEFORE
    simulating, not discovered from a physically-impossible result."""
    rows = []
    for chute in parsed.parachutes:
        _, warning = parachute_trigger(chute)
        if warning:
            rows.append((f"{chute.name} (deployment)", "APPROXIMATED", warning))
    return rows


def wind_speed_direction_to_uv(speed_ms, direction_from_deg):
    """rocketpy's East/North wind VELOCITY components from a wind speed
    + the compass bearing the wind blows FROM (standard meteorological
    convention - both OpenRocket's <winddirection> and Open-Meteo's
    wind_direction_10m use this same convention). The velocity vector
    points the OPPOSITE way (bearing + 180 deg), which is why this
    negates sin/cos rather than using them directly. Factored out of
    wind_uv() (2026-09-26 review item H) so bup_rocketpy/weather.py's
    real-weather overrides use the exact same, already-verified formula
    rather than a second hand-written copy."""
    if not speed_ms:
        return 0.0, 0.0
    theta = math.radians(direction_from_deg + 180.0)
    return speed_ms * math.sin(theta), speed_ms * math.cos(theta)


def wind_uv(launch):
    """rocketpy's East/North wind VELOCITY components from an OpenRocket
    LaunchConditions' windaverage/winddirection. Shared by
    build_environment and case_export.py's generated script (2026-09-26
    review item 3's "ONE path" rule) so both compute the identical
    vector."""
    return wind_speed_direction_to_uv(launch.wind_average_ms, launch.wind_direction_deg)


def build_environment(launch):
    """2026-09-26 review item 3: the .ork's own recorded wind
    (windaverage/winddirection) was being read into LaunchConditions but
    never actually applied here - every simulation ran in dead-still air
    even when OpenRocket's own reference sim for the identical input set
    used a real wind. That was a real, unexplained-until-now contributor
    to the "app vs. code-to-code test" +10% gap this review is chasing:
    a no-wind run flies straighter and higher than OpenRocket's own
    windy one, given the same everything else.

    Two bugs had to be fixed together before this actually worked:
    (1) the wind vector's sign convention (see wind_uv() above), and
    (2) a rocketpy quirk (see docs/rocketpy_issues/) where
    Environment.set_atmospheric_model's wind_u/wind_v parameters are
    SILENTLY IGNORED for type="standard_atmosphere" - that branch
    unconditionally zeroes wind internally regardless of what was
    passed in, so the first attempt at this fix (passing wind_u/wind_v
    straight into set_atmospheric_model) measurably changed nothing.
    add_wind_gust() is the supported way to layer a constant wind on
    top of an already-set atmosphere model. Verified against
    test_code_to_code_vs_openrocket.py: with both fixes plus the
    propellant-mass fix in build_motor(), the Brasil-config case's
    apogee error vs. OpenRocket's own recorded result for the identical
    input set moved from +10.17% to -1.45% - within the 2% target. See
    PROGRESS.md "Item 3" for the full before/after table.
    """
    env = Environment(latitude=launch.latitude, longitude=launch.longitude, elevation=launch.altitude_m)
    env.set_atmospheric_model(type="standard_atmosphere")
    wind_u, wind_v = wind_uv(launch)
    if wind_u or wind_v:
        env.add_wind_gust(wind_u, wind_v)
    return env


DRAG_CURVE_PLACEHOLDER_CD = 0.5  # last resort per CLAUDE.md Sec 4.2 point 4 - only used if the caller explicitly has no curve at all


def _coordinate_transform(coordinate_system_orientation):
    """The ONE place the OpenRocket (nose-tip-origin, distance-increases-
    aft) frame gets converted to a rocketpy frame. CLAUDE.md Sec 4.3 says
    RocketPy uses "nose_to_tail"; the validated PROMETEO reference code
    uses "tail_to_nose" (see module docstring). Both are valid rocketpy
    conventions - this function supports either, and
    test_coordinate_convention_equivalence (tests/) proves they give the
    same physical answer (same CP, same static margin) when used
    consistently, so this is a style choice, not a correctness bug."""
    if coordinate_system_orientation == "tail_to_nose":
        return lambda x_m_from_nose: -x_m_from_nose
    elif coordinate_system_orientation == "nose_to_tail":
        return lambda x_m_from_nose: x_m_from_nose
    raise ValueError(f"unknown coordinate_system_orientation {coordinate_system_orientation!r}")


def build_rocket(parsed, motor, dry_mass_estimate, i_axial, i_transverse, radius_m, power_off_drag=None, power_on_drag=None, coordinate_system_orientation="tail_to_nose", include_recovery=True):
    """Builds the rocketpy Rocket. Defaults to "tail_to_nose" (the
    validated reference code's convention, not CLAUDE.md Sec 4.3's prose -
    see module docstring); pass coordinate_system_orientation="nose_to_tail"
    for the other one. See _coordinate_transform for why both are fine.

    power_off_drag/power_on_drag: path to a 2-column (Mach, Cd) CSV, per
    CLAUDE.md Sec 4.2's source-preference order. Required - there is no
    silent default. Pass DRAG_CURVE_PLACEHOLDER_CD explicitly (a float, not
    a path) only when no curve exists at all, per Sec 4.2 point 4 - and the
    caller must flag that choice to the user, this function does not."""
    if power_off_drag is None or power_on_drag is None:
        raise ValueError("power_off_drag/power_on_drag are required - pass a real Cd-vs-Mach CSV path, or DRAG_CURVE_PLACEHOLDER_CD explicitly if truly none exists (CLAUDE.md Sec 4.2: never default to a constant silently)")

    to_rpy = _coordinate_transform(coordinate_system_orientation)

    rocket = Rocket(
        radius=radius_m,
        mass=dry_mass_estimate.mass_kg,
        inertia=(i_transverse, i_transverse, i_axial),
        power_off_drag=power_off_drag,
        power_on_drag=power_on_drag,
        center_of_mass_without_motor=to_rpy(dry_mass_estimate.cg_m),
        coordinate_system_orientation=coordinate_system_orientation,
    )

    from bup_rocketpy.ork_reader import airframe_length_m

    nose_tip_rpy = to_rpy(0.0)
    # 2026-09-27 review item 1c: airframe_length_m() (nose + body tubes +
    # transitions) replaces a body-tubes-only formula that silently
    # ignored a transition/boat-tail placed after the last body tube -
    # a real, common layout that put the assumed motor position too far
    # forward for any such rocket.
    rocket.add_motor(motor, position=to_rpy(airframe_length_m(parsed)))

    if parsed.nose is not None:
        rocket.add_nose(length=parsed.nose.length, kind=rocketpy_nose_kind(parsed.nose.shape), position=nose_tip_rpy)

    for fin in parsed.fins:
        rocket.add_trapezoidal_fins(
            n=fin.count,
            root_chord=fin.root_chord,
            tip_chord=fin.tip_chord,
            span=fin.span,
            sweep_length=fin.sweep_length,
            cant_angle=fin.cant_angle,
            position=to_rpy(fin.position_m),
        )

    if parsed.rail_buttons is not None:
        rocket.set_rail_buttons(
            upper_button_position=to_rpy(parsed.rail_buttons.upper_position_m),
            lower_button_position=to_rpy(parsed.rail_buttons.lower_position_m),
        )

    if include_recovery:
        for chute in parsed.parachutes:
            if chute.cd is None:
                continue  # can't add a parachute rocketpy can simulate without a Cd - already flagged in the import log
            trigger, _ = parachute_trigger(chute)  # warning already surfaced via parachute_import_notes() at load time
            if chute.is_reefed and chute.reefed_cd is not None and chute.reefed_diameter_m is not None and chute.cutter_altitude_m is not None:
                # 2026-09-26 review item D (new lettering): a reefed main
                # + line cutter is ONE physical canopy that flies in TWO
                # stages - modeled as two independent rocketpy Parachutes,
                # not one (rocketpy has no native "reefed" concept either).
                # This is physically safe because both triggers are
                # "descending AND below altitude X" (rocketpy's own numeric-
                # trigger semantics, verified in rocketpy/rocket/parachute.py:
                # `y[5] < 0 and h < trigger` - never fires on the way up) -
                # the cutter's altitude is always BELOW the reefed stage's
                # own deployment altitude/apogee, so the two fire in the
                # correct order automatically, with no shared state needed.
                reefed_cd_s = chute.reefed_cd * math.pi * (chute.reefed_diameter_m / 2.0) ** 2
                rocket.add_parachute(name=f"{chute.name} (reefed)", cd_s=reefed_cd_s, trigger=trigger, sampling_rate=100, lag=chute.deploy_delay, radius=chute.reefed_diameter_m / 2.0, drag_coefficient=chute.reefed_cd)
                full_cd_s = chute.cd * math.pi * (chute.diameter / 2.0) ** 2
                rocket.add_parachute(name=f"{chute.name} (full)", cd_s=full_cd_s, trigger=chute.cutter_altitude_m, sampling_rate=100, lag=chute.cutter_delay_s, radius=chute.diameter / 2.0, drag_coefficient=chute.cd)
                continue
            cd_s = chute.cd * math.pi * (chute.diameter / 2.0) ** 2
            # radius/drag_coefficient: rocketpy's Parachute stores these
            # verbatim (they don't affect the physics beyond what cd_s
            # already captures) - passing them means the built Parachute
            # object itself carries the REAL diameter/Cd for anything that
            # inspects it later (e.g. bup_rocketpy.recovery's panel),
            # instead of having to back-derive an approximate diameter
            # from cd_s alone.
            rocket.add_parachute(name=chute.name, cd_s=cd_s, trigger=trigger, sampling_rate=100, lag=chute.deploy_delay, radius=chute.diameter / 2.0, drag_coefficient=chute.cd)
    # include_recovery=False is CRS 10.1.11's Ballistic case: no recovery
    # deployment at all, rocket free-falls under drag alone to ground impact.

    return rocket


def ork_to_flight(ork_parsed, parsed_eng, eng_path, power_off_drag=None, power_on_drag=None, rail_length_override=None, inclination_override=None, heading_override=None, terminate_on_apogee=False, include_recovery=True, dry_mass_override_kg=None, dry_cg_override_m=None, launch_override=None, i_axial_override=None, i_transverse_override=None, motor_dry_mass_override_kg=None):
    """End-to-end: parsed .ork + parsed .eng -> a runnable rocketpy Flight.
    Raises if the .ork had no launch conditions and no overrides were
    given - CRS 10.1.8 requires exact site data, so this refuses to guess
    a launch site silently. power_off_drag/power_on_drag: see build_rocket.
    include_recovery=False builds CRS 10.1.11's Ballistic case (no
    parachutes regardless of what the .ork has configured).

    launch_override: a full LaunchConditions to use INSTEAD of the .ork's
    own stored one (e.g. dataclasses.replace(parsed.launch, altitude_m=...,
    wind_average_ms=...) for a different historical flight's site/weather
    on the SAME airframe .ork) - added 2026-09-26 review item 3, so a
    validation test can vary site/weather per real flight while still
    going through this one function, instead of a parallel hand-built
    Rocket()/Flight() path (the actual cause of the "app says -0.7%,
    the test harness says +10%" discrepancy that review reported).
    i_axial_override/i_transverse_override: use these dry inertia values
    instead of the geometric per-component estimate - for when a caller
    already has a better inertia figure (e.g. derived from an OpenRocket
    with-motor CG/inertia reading via
    derive_dry_mass_and_inertia_from_with_motor())."""
    launch = launch_override if launch_override is not None else ork_parsed.launch
    if launch is None and None in (rail_length_override, inclination_override, heading_override):
        raise ValueError("no launch conditions in the .ork and no manual overrides given - supply rail_length/inclination/heading or a .ork with a stored simulation")

    env = build_environment(launch)
    motor = build_motor(parsed_eng, eng_path, dry_mass_override_kg=motor_dry_mass_override_kg)

    if dry_mass_override_kg is not None and dry_cg_override_m is not None:
        dry_mass_estimate = MassEstimate(dry_mass_override_kg, dry_cg_override_m, "manual override passed to ork_to_flight")
    else:
        dry_mass_estimate = estimate_dry_mass_and_cg(ork_parsed)
    if i_axial_override is not None and i_transverse_override is not None:
        i_axial, i_transverse = i_axial_override, i_transverse_override
    else:
        i_axial, i_transverse = estimate_dry_inertia(ork_parsed, dry_mass_estimate)
    radius_m = next((t.radius for t in ork_parsed.body_tubes if t.radius), None) or (ork_parsed.nose.aft_radius if ork_parsed.nose else 0.05)

    rocket = build_rocket(ork_parsed, motor, dry_mass_estimate, i_axial, i_transverse, radius_m, power_off_drag=power_off_drag, power_on_drag=power_on_drag, include_recovery=include_recovery)

    flight = Flight(
        rocket=rocket,
        environment=env,
        rail_length=rail_length_override if rail_length_override is not None else launch.rail_length_m,
        inclination=inclination_override if inclination_override is not None else launch.inclination_deg,
        heading=heading_override if heading_override is not None else launch.rail_direction_deg,
        terminate_on_apogee=terminate_on_apogee,
    )
    return flight, dry_mass_estimate
