"""RCSM Ed.7 Rev.1 constants and a category-aware compliance checker, shared
by every vehicle. See docs/rcsm_reference.md for the source text and rule
IDs - update both together if a future RCSM edition changes a number.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MissionCategory:
    name: str
    propulsion: str  # "solid" or "hybrid" or "liquid"
    target_apogee_m: float
    min_payload_kg: float


CATEGORIES = {
    "0.5km_solid": MissionCategory("0.5km_solid", "solid", 500, 0.400),
    "1km_solid": MissionCategory("1km_solid", "solid", 1000, 0.800),
    "3km_solid": MissionCategory("3km_solid", "solid", 3000, 4.000),
    "1km_hybrid": MissionCategory("1km_hybrid", "hybrid", 1000, 0.400),  # RKT Table 1 "1km" band, hybrid/liquid column
    "3km_hybrid": MissionCategory("3km_hybrid", "hybrid", 3000, 2.000),
}

DUAL_DEPLOY_THRESHOLD_M = 1500  # REC 8.1.1 / 8.1.2
RAIL_LENGTH_SHORT = 4.0  # m, FLT 4.4.1, apogee <= 1500m
RAIL_LENGTH_LONG = 6.0  # m, FLT 4.4.2, apogee > 1500m
DROGUE_MAIN_DEPLOY_MAX_ALT = 500  # m AGL, REC 8.1.4
DROGUE_DESCENT_RATE_RANGE = (20, 45)  # m/s, REC 8.1.3
MIN_STATIC_MARGIN_CAL = 1.5  # FLT 4.3.5
MAX_STATIC_MARGIN_CAL = 4.0  # FLT 4.3.6
MAX_DYNAMIC_MARGIN_CAL = 6.0  # FLT 4.3.6
MIN_RAIL_EXIT_VELOCITY = 30.0  # m/s, FLT 4.3.4 (>=15 m/s needs documented analysis instead)
RAIL_EXIT_VELOCITY_ANALYSIS_FLOOR = 15.0  # m/s, FLT 4.3.4
MIN_THRUST_TO_WEIGHT = 5.0  # PRS 5.1.4
MAX_SRAD_TOTAL_IMPULSE = 40960.0  # N s, PRS 5.1.3
MIN_FIN_FLUTTER_MARGIN = 1.5  # STR 6.3.2, flutter velocity / max velocity
RAIL_BUTTON_COUNT = 2  # STR 6.4.2


def requires_dual_deploy(target_apogee_m):
    return target_apogee_m > DUAL_DEPLOY_THRESHOLD_M


def rail_length_for(target_apogee_m):
    return RAIL_LENGTH_LONG if target_apogee_m > DUAL_DEPLOY_THRESHOLD_M else RAIL_LENGTH_SHORT


def check_compliance(category, flight, rocket, payload_mass_kg, fin_flutter_velocity=None):
    """Returns a list of (rule_id, description, status, detail) tuples.
    status is one of PASS/FAIL/WARN. Mirrors the pattern used in the
    PROMETEO/vehicle_1km_solid repo's compliance.py - keep them consistent.
    """
    rows = []

    rail_v = rocket_rail_exit_velocity(flight)
    if rail_v >= MIN_RAIL_EXIT_VELOCITY:
        rows.append(("FLT 4.3.4", "Rail exit velocity", "PASS", f"{rail_v:.1f} m/s"))
    elif rail_v >= RAIL_EXIT_VELOCITY_ANALYSIS_FLOOR:
        rows.append(("FLT 4.3.4", "Rail exit velocity", "WARN", f"{rail_v:.1f} m/s, needs documented stability analysis"))
    else:
        rows.append(("FLT 4.3.4", "Rail exit velocity", "FAIL", f"{rail_v:.1f} m/s, below {RAIL_EXIT_VELOCITY_ANALYSIS_FLOOR} m/s floor"))

    # 2026-09-26 review 2(b): "(ascent)" in the rule description above was
    # not actually true until this fix - margins were computed over the
    # WHOLE flight (including descent under canopy, where "static margin"
    # is not the aerodynamically meaningful ascent-stability quantity
    # FLT 4.3.5/4.3.6 are about), the same bug pipeline.run_simulation had.
    ascent_times = [t for t in flight.time if flight.out_of_rail_time <= t <= flight.apogee_time]
    margins = [flight.stability_margin(t) for t in ascent_times] or [flight.stability_margin(flight.apogee_time)]
    min_margin = min(margins)
    max_margin = max(margins)
    if min_margin >= MIN_STATIC_MARGIN_CAL:
        rows.append(("FLT 4.3.5", "Static margin >= 1.5 cal (ascent)", "PASS", f"min {min_margin:.2f} cal"))
    else:
        rows.append(("FLT 4.3.5", "Static margin >= 1.5 cal (ascent)", "FAIL", f"min {min_margin:.2f} cal"))

    if max_margin < MAX_STATIC_MARGIN_CAL:
        rows.append(("FLT 4.3.6", "Not over-stable (< 4 cal static)", "PASS", f"max {max_margin:.2f} cal"))
    else:
        rows.append(("FLT 4.3.6", "Not over-stable (< 4 cal static)", "FAIL", f"max {max_margin:.2f} cal"))

    # PRS 5.1.4 says "initial thrust... or average thrust, whichever is
    # greater" - a RASP curve's literal t=0 sample is 0 N by convention, so
    # "initial thrust" here means the thrust during the ignition transient,
    # taken as the curve's peak (which for a typical KN/BATES-style burn
    # happens early); using max(peak, avg) matches the rule's intent of
    # picking whichever number is larger.
    weight_N = rocket.total_mass(0) * 9.80665
    thrust_peak = max(rocket.motor.thrust.y_array)
    thrust_avg = rocket.motor.average_thrust
    tw = max(thrust_peak, thrust_avg) / weight_N
    if tw >= MIN_THRUST_TO_WEIGHT:
        rows.append(("PRS 5.1.4", "Thrust-to-weight >= 5:1", "PASS", f"{tw:.2f}:1"))
    else:
        rows.append(("PRS 5.1.4", "Thrust-to-weight >= 5:1", "FAIL", f"{tw:.2f}:1"))

    impulse = rocket.motor.total_impulse
    if impulse <= MAX_SRAD_TOTAL_IMPULSE:
        rows.append(("PRS 5.1.3", "SRAD total impulse <= 40,960 Ns", "PASS", f"{impulse:.0f} Ns"))
    else:
        rows.append(("PRS 5.1.3", "SRAD total impulse <= 40,960 Ns", "FAIL", f"{impulse:.0f} Ns"))

    min_payload = category.min_payload_kg
    if payload_mass_kg >= min_payload * 0.95:  # RKT 1.1.2 LRR 5% tolerance
        rows.append(("RKT 1.1.2", f"Payload >= {min_payload*1000:.0f} g", "PASS", f"{payload_mass_kg*1000:.0f} g"))
    else:
        rows.append(("RKT 1.1.2", f"Payload >= {min_payload*1000:.0f} g", "FAIL", f"{payload_mass_kg*1000:.0f} g"))

    if requires_dual_deploy(category.target_apogee_m):
        n_chutes = len(rocket.parachutes)
        if n_chutes >= 2:
            rows.append(("REC 8.1.1", "Dual-event recovery required (apogee > 1500m)", "PASS", f"{n_chutes} parachutes configured"))
        else:
            rows.append(("REC 8.1.1", "Dual-event recovery required (apogee > 1500m)", "FAIL", f"only {n_chutes} parachute(s) configured"))

        # 2026-09-26 review item D (new lettering): REC 8.1.3/8.1.4 were
        # long-standing constants with no check ever wired up to them -
        # a reefed main + line cutter counting as dual-event (REC 8.1.1,
        # fixed above by translate.build_rocket now adding it as two real
        # rocketpy Parachutes) only actually matters if these two
        # velocity/altitude rules ALSO get checked, or "counts as dual-
        # event" would be true in name only. Identifies the two stages by
        # deployment ORDER (first = drogue/reefed-equivalent, higher up;
        # last = main/full-equivalent, lower down) via flight.parachute_events,
        # which already records (time, chute) in the order they actually
        # fired during THIS flight - not by name pattern, works for a real
        # drogue+main pair exactly the same as a reefed one.
        events = sorted(getattr(flight, "parachute_events", []), key=lambda te: te[0])
        if len(events) >= 2:
            drogue_t, _ = events[0]
            main_t, _ = events[-1]
            # Sampled just BEFORE the main/full stage takes over, not at
            # the drogue/reefed stage's own opening instant - matching
            # recovery.py's same reasoning (recovery_panel's docstring):
            # right at deployment is still near free-fall speed, not the
            # settled rate under that canopy, which is what REC 8.1.3
            # actually means by "descent rate".
            t_settled = max(main_t - 0.5, drogue_t + 0.5)
            vx, vy, vz = flight.vx(t_settled), flight.vy(t_settled), flight.vz(t_settled)
            drogue_speed = (vx**2 + vy**2 + vz**2) ** 0.5
            lo, hi = DROGUE_DESCENT_RATE_RANGE
            if lo <= drogue_speed <= hi:
                rows.append(("REC 8.1.3", f"Drogue/reefed descent rate {lo}-{hi} m/s", "PASS", f"{drogue_speed:.1f} m/s (settled, sampled t={t_settled:.1f}s)"))
            else:
                rows.append(("REC 8.1.3", f"Drogue/reefed descent rate {lo}-{hi} m/s", "FAIL", f"{drogue_speed:.1f} m/s (settled, sampled t={t_settled:.1f}s)"))

            # NOTE: flight.altitude(t) is ALREADY AGL in rocketpy (unlike
            # flight.z(t)/flight.apogee, which are ASL and need
            # `- flight.env.elevation`) - verified directly (2026-09-26
            # review item D): subtracting elevation again here silently
            # gave a wildly wrong ~5m instead of the real ~500m release
            # altitude on first pass. Confusing two different altitude
            # conventions inside the same file is an easy, quiet way to
            # get a plausible-looking but wrong number - flagged clearly
            # so it doesn't happen again elsewhere.
            main_alt_agl = flight.altitude(main_t)
            final_speed = abs(flight.impact_velocity)
            if main_alt_agl <= DROGUE_MAIN_DEPLOY_MAX_ALT and final_speed < 10.0:
                rows.append(("REC 8.1.4", f"Main/full release <= {DROGUE_MAIN_DEPLOY_MAX_ALT}m AGL, final < 10 m/s", "PASS", f"released @ {main_alt_agl:.0f}m AGL, landed @ {final_speed:.1f} m/s"))
            else:
                rows.append(("REC 8.1.4", f"Main/full release <= {DROGUE_MAIN_DEPLOY_MAX_ALT}m AGL, final < 10 m/s", "FAIL", f"released @ {main_alt_agl:.0f}m AGL, landed @ {final_speed:.1f} m/s"))
        elif n_chutes >= 2:
            rows.append(("REC 8.1.3/8.1.4", "Drogue/main descent rate and release altitude", "WARN", "expected 2 parachute deployment events in this flight but found fewer - check the flight actually reached them"))
    else:
        rows.append(("REC 8.1.2", "Single-event recovery allowed (apogee <= 1500m)", "PASS", "exempt from dual-event"))

    if fin_flutter_velocity is not None:
        margin = fin_flutter_velocity / flight.max_speed
        if margin >= MIN_FIN_FLUTTER_MARGIN:
            rows.append(("STR 6.3.2", "Fin flutter velocity >= 1.5x max speed", "PASS", f"{margin:.2f}x"))
        else:
            rows.append(("STR 6.3.2", "Fin flutter velocity >= 1.5x max speed", "FAIL", f"{margin:.2f}x"))
    else:
        rows.append(("STR 6.3.2", "Fin flutter velocity >= 1.5x max speed", "WARN", "flutter velocity not computed for this rocket (no fins parsed, or no shear modulus available) - see bup_rocketpy.flutter"))

    return rows


def rocket_rail_exit_velocity(flight):
    return flight.out_of_rail_velocity


def print_compliance_table(rows):
    print(f"{'Rule':<10} {'Check':<45} {'Status':<6} {'Detail'}")
    for rule_id, desc, status, detail in rows:
        print(f"{rule_id:<10} {desc:<45} {status:<6} {detail}")
