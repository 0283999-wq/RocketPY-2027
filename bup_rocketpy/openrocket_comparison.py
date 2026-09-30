"""OpenRocket comparison (2026-09-28 review item 2): apples-to-apples
rows comparing this app's own computed numbers against OpenRocket's OWN
numbers for the SAME .ork - sourced entirely from the .ork's own stored
simulation databranch (bup_rocketpy.ork_reader.parse_stored_simulation_
references), never hand-typed per-rocket. Works for ANY .ork that has a
stored simulation (Major Tom, PROMETEO, the OpenRocket example files),
not just whichever rocket prompted this feature.

Every "ours" value is computed through the EXACT SAME rocket object
Simulate itself built (sim_result.flight.rocket) - never a fresh,
separately-built Rocket - so this can never silently compare against a
different vehicle configuration than what the rest of the app is
showing.

Coordinate convention: translate.build_rocket() always uses
coordinate_system_orientation="tail_to_nose" (its own default, never
overridden by pipeline.py) - rocketpy's own cp_position()/center_of_mass
values come back in that tail-to-nose frame (more negative = further
aft), so _nose_frame() flips the sign to match the nose-referenced
convention this app uses everywhere else (matching OpenRocket's own).
"""
import dataclasses
import math

# CP (and anything derived from it) gets a wider tolerance: rocketpy and
# OpenRocket use slightly different body-lift/Barrowman implementations,
# a documented, expected model difference, not a bug - see CLAUDE.md's
# own Phase 1 acceptance note and tests/test_phase1_acceptance.py.
CP_TOLERANCE_PCT = 2.0
DEFAULT_TOLERANCE_PCT = 1.0
_CP_LABELS = ("CP at Mach 0.3", "Stability at Mach 0.3 (t=0)")


@dataclasses.dataclass
class ComparisonRow:
    label: str
    ours: float
    openrocket: float  # None when the design file has no comparable stored number
    unit: str
    decimals: int = 2
    note: str = ""

    @property
    def tolerance_pct(self):
        return CP_TOLERANCE_PCT if self.label in _CP_LABELS else DEFAULT_TOLERANCE_PCT

    @property
    def pct_diff(self):
        if self.ours is None or self.openrocket is None or self.openrocket == 0:
            return None
        return (self.ours - self.openrocket) / abs(self.openrocket) * 100

    @property
    def over_threshold(self):
        pct = self.pct_diff
        return pct is not None and abs(pct) > self.tolerance_pct


def _nose_frame(rocketpy_value):
    return -rocketpy_value if rocketpy_value is not None else None


def compare_to_openrocket(parsed, sim_result, ork_path):
    """Returns (sim_name, [ComparisonRow, ...]), or (None, None) if the
    .ork has no stored simulation to compare against (a geometry-only
    design nobody has simulated in OpenRocket yet - an expected, common
    case, not an error). sim_result: pipeline.SimResult from a completed
    Simulate run on THIS SAME .ork (needs sim_result.flight/.motor)."""
    from bup_rocketpy.ork_reader import parse_stored_simulation_references, reported_length_m

    refs = parse_stored_simulation_references(ork_path)
    ref = next(iter(refs.values()), None)  # same "first stored sim" convention translate.estimate_best_dry_mass_cg_inertia already uses
    if ref is None or ref.mass_with_motor_t0_kg is None:
        return None, None

    rocket = sim_result.flight.rocket
    radius = rocket.radius
    our_cg_t0 = _nose_frame(rocket.center_of_mass(0))
    our_cp_m03 = _nose_frame(rocket.cp_position(0.3))

    our_dry_mass = sim_result.dry_mass_kg
    ref_dry_mass = (
        ref.mass_with_motor_t0_kg - ref.motor_mass_t0_kg
        if ref.motor_mass_t0_kg is not None else None
    )

    ref_max_diameter = ref.reference_length_m if ref.reference_length_is_max_diameter else None

    cp_note = ""
    if ref.cp_at_mach_0_3_m is not None and ref.cp_at_mach_0_3_actual_mach is not None and abs(ref.cp_at_mach_0_3_actual_mach - 0.3) > 0.01:
        cp_note = f"OpenRocket's nearest recorded point was Mach {ref.cp_at_mach_0_3_actual_mach:.3f}, not exactly 0.300"

    stability_note = (
        "Both sides use OUR OWN t=0 CG (not OpenRocket's) so this isolates the aerodynamic "
        "CP model difference (see the CP row) from any separate mass/CG disagreement, which "
        "the rows above already cover on their own. Stability is a SMALL difference of two "
        "close numbers (CP minus CG), so the same CP gap shows up as a much larger percentage "
        "here than in the CP row itself - expected amplification, not a second, separate error."
    )
    ref_stability_m03 = (
        (ref.cp_at_mach_0_3_m - our_cg_t0) / (2 * radius)
        if ref.cp_at_mach_0_3_m is not None and our_cg_t0 is not None else None
    )
    our_stability_m03 = (our_cp_m03 - our_cg_t0) / (2 * radius) if our_cp_m03 is not None and our_cg_t0 is not None else None

    # 2026-09-30 review item 7: a real case found our simulated SPEED
    # matching OpenRocket closely (321.5 vs. 322 m/s) but the reported
    # MACH not (0.984 vs. 0.960) - traced to a different assumed
    # temperature (our standard-atmosphere speed of sound ~327 m/s vs.
    # OpenRocket's own recorded ~335 m/s at the same elevation). Shown
    # here so a mismatch is visible up front, not chased down by hand.
    env = sim_result.flight.env
    atmosphere_rows = []
    if ref.air_temp_k_t0 is not None:
        our_temp_k = env.temperature(env.elevation)
        our_pressure_pa = env.pressure(env.elevation)
        our_wind_ms = env.wind_speed(env.elevation)
        atmosphere_rows = [
            ComparisonRow("Elevation (site)", env.elevation, parsed.launch.altitude_m if parsed.launch else None, "m", 0,
                           "From the .ork's own launch conditions - used by default (this app never substitutes a different elevation)."),
            ComparisonRow("Temperature (t=0)", our_temp_k, ref.air_temp_k_t0, "K", 1,
                           f"Ours: standard atmosphere (ISA) at this elevation ({our_temp_k - 273.15:.1f} degC) vs. OpenRocket's own stored value ({ref.air_temp_k_t0 - 273.15:.1f} degC), which may reflect a custom/measured atmosphere instead - a gap here explains a Mach-number mismatch even when speed itself agrees."),
            ComparisonRow("Pressure (t=0)", our_pressure_pa / 100.0, ref.air_pressure_pa_t0 / 100.0, "hPa", 1),
            ComparisonRow("Wind speed (t=0)", our_wind_ms, ref.wind_speed_ms_t0, "m/s", 2,
                           "Ours is the .ork's own CONFIGURED average wind (used by default). OpenRocket's own stored value is what it happened to SAMPLE at t=0 in that one run - it applies random wind variation around the average by default, so some difference here is normal/expected, not necessarily a mismatch."),
        ]

    rows = atmosphere_rows + [
        ComparisonRow("Overall length", reported_length_m(parsed), None, "m", 3,
                       "Includes swept fin tip overhang past the tail. Not stored in the design file (OpenRocket computes this live in its own UI, never persists it) - read it off OpenRocket's own panel to compare by hand."),
        ComparisonRow("Max diameter", 2 * radius, ref_max_diameter, "m", 3,
                       "" if ref_max_diameter is not None else "The design file's reference length isn't declared as the rocket's maximum diameter (<referencetype> is not \"maximum\") - not shown as a diameter."),
        ComparisonRow("Mass without motor", our_dry_mass, ref_dry_mass, "kg", 4),
        ComparisonRow("Mass with motor (t=0)", rocket.total_mass(0), ref.mass_with_motor_t0_kg, "kg", 4),
        ComparisonRow("CG with motor (t=0, from nose)", our_cg_t0, ref.cg_with_motor_t0_m, "m", 4),
        ComparisonRow("CP at Mach 0.3", our_cp_m03, ref.cp_at_mach_0_3_m, "m", 4, cp_note),
        ComparisonRow("Stability at Mach 0.3 (t=0)", our_stability_m03, ref_stability_m03, "cal", 3, stability_note),
        ComparisonRow("Apogee AGL", sim_result.apogee_agl_m, ref.apogee_agl_m, "m", 1,
                       "OpenRocket's own stored simulation, not real flight data - see the Validation page for the only comparisons against a real flight."),
        ComparisonRow("Max Mach", sim_result.max_mach, ref.max_mach, "", 3),
    ]
    return ref.name, rows
