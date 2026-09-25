"""Automatic sanity checks (2026-09-26 review, item 2c): coarse physics
consistency checks meant to catch the CLASS of bug this review found (a
375g acceleration spike, a 0.08 cal margin, a deployment 14s after
apogee at 120 m/s) before a human has to notice the number looks wrong.

These are deliberately loose - order-of-magnitude, not tight validation.
A false positive on a genuinely unusual but correct rocket costs more
than missing a subtle error, so each check only fires on a result that
is not just imprecise but implausible.
"""
import math
from dataclasses import dataclass

G0 = 9.80665


@dataclass
class SanityCheck:
    name: str
    status: str  # "OK", "WARN", "FAIL"
    detail: str


def run_sanity_checks(flight, rocket, motor, dry_mass_kg, ground_air_density_kgm3=1.225):
    checks = []

    # 1. Thrust-to-weight at liftoff - must exceed 1 to leave the pad at
    # all; common rule of thumb wants >5 for a fast, stable rail departure.
    burn_start, burn_end = motor.burn_time
    avg_thrust_N = motor.total_impulse / max(burn_end - burn_start, 1e-6)
    liftoff_mass_kg = rocket.total_mass(0)
    tw = avg_thrust_N / (liftoff_mass_kg * G0)
    if tw < 1.0:
        checks.append(SanityCheck("Thrust-to-weight", "FAIL", f"T/W={tw:.2f} at liftoff (avg thrust {avg_thrust_N:.0f} N / weight {liftoff_mass_kg * G0:.0f} N) - this rocket cannot lift off the pad."))
    elif tw < 3.0:
        checks.append(SanityCheck("Thrust-to-weight", "WARN", f"T/W={tw:.2f} at liftoff is low for a safe, fast rail departure (rule of thumb: >5)."))
    else:
        checks.append(SanityCheck("Thrust-to-weight", "OK", f"T/W={tw:.2f} at liftoff."))

    # 2. Boost acceleration hand-check: (avg thrust - avg weight) / avg
    # mass vs. the simulated PEAK boost acceleration. These are not the
    # same number by design (thrust peaks early in most motors and mass
    # depletes through the burn, so the true peak can be well above the
    # burn-averaged estimate) - only flag a mismatch far outside that.
    avg_mass_kg = liftoff_mass_kg - motor.propellant_initial_mass / 2.0
    hand_accel = (avg_thrust_N - avg_mass_kg * G0) / avg_mass_kg
    sim_accel = flight.max_acceleration_power_on
    if hand_accel > 0 and not (0.3 * hand_accel <= sim_accel <= 4.0 * hand_accel):
        checks.append(SanityCheck("Boost acceleration", "WARN", f"simulated peak boost accel ({sim_accel:.1f} m/s2) is far from a thrust/mass-g hand estimate ({hand_accel:.1f} m/s2, averaged over the burn) - a mismatch of up to ~3-4x is normal, this is further off."))
    else:
        checks.append(SanityCheck("Boost acceleration", "OK", f"simulated peak {sim_accel:.1f} m/s2 vs. hand estimate {hand_accel:.1f} m/s2 (avg thrust/mass - g)."))

    # 3. Delta-v hand-check: impulse / average mass vs. the speed actually
    # gained by burnout. Gravity/drag losses mean the simulated value
    # should be LESS than the hand estimate, not equal - only flag it
    # being higher (impossible) or drastically lower (something else
    # wrong, e.g. drag/mass badly off).
    hand_dv = motor.total_impulse / avg_mass_kg
    burnout_t = burn_end
    vx, vy, vz = flight.vx(burnout_t), flight.vy(burnout_t), flight.vz(burnout_t)
    sim_burnout_speed = math.sqrt(vx**2 + vy**2 + vz**2)
    if sim_burnout_speed > hand_dv * 1.05:
        checks.append(SanityCheck("Delta-v", "WARN", f"simulated burnout speed ({sim_burnout_speed:.1f} m/s) exceeds the hand delta-v estimate ({hand_dv:.1f} m/s = impulse/avg mass, before gravity/drag losses) - that should not be physically possible."))
    elif sim_burnout_speed < hand_dv * 0.4:
        checks.append(SanityCheck("Delta-v", "WARN", f"simulated burnout speed ({sim_burnout_speed:.1f} m/s) is far below the hand delta-v estimate ({hand_dv:.1f} m/s) - more than a typical gravity/drag loss would explain."))
    else:
        checks.append(SanityCheck("Delta-v", "OK", f"simulated burnout speed {sim_burnout_speed:.1f} m/s vs. hand estimate {hand_dv:.1f} m/s (impulse/avg mass, before losses)."))

    # 4. Static margin (FLT 4.3.5: 1.5-4 cal window) is added by the
    # caller (pipeline.run_simulation) - it already computes the
    # ascent-only margin for the KPI cards, no need to recompute it here.

    # 5. Deployment speed - a hard opening shock above ~30 m/s risks
    # canopy/line damage; below is the "expected clean deployment" band.
    for t, chute in getattr(flight, "parachute_events", []):
        vx, vy, vz = flight.vx(t), flight.vy(t), flight.vz(t)
        speed = math.sqrt(vx**2 + vy**2 + vz**2)
        name = getattr(chute, "name", "parachute")
        if speed > 30:
            checks.append(SanityCheck(f"Deployment speed ({name})", "WARN", f"{speed:.1f} m/s at deployment (t={t:.1f} s) - above the ~30 m/s clean-deployment guideline, risks a hard opening shock."))
        else:
            checks.append(SanityCheck(f"Deployment speed ({name})", "OK", f"{speed:.1f} m/s at deployment (t={t:.1f} s)."))

    # 6. Descent rate hand-check: v = sqrt(2mg / (rho * CdS)) at ground
    # density, vs. the simulated impact velocity. A full recovery panel
    # (both deployment- and ground-altitude density) lives on the
    # Results page - this is the coarse "is it in the right universe" check.
    descent_mass_kg = dry_mass_kg + motor.dry_mass
    if getattr(flight, "parachute_events", None):
        last_cd_s = flight.parachute_events[-1][1].cd_s
        if last_cd_s and last_cd_s > 0:
            hand_v = math.sqrt(2 * descent_mass_kg * G0 / (ground_air_density_kgm3 * last_cd_s))
            sim_v = abs(flight.impact_velocity)
            ratio = sim_v / hand_v if hand_v > 0 else float("inf")
            if not (0.5 <= ratio <= 2.0):
                checks.append(SanityCheck("Descent rate", "WARN", f"simulated impact speed ({sim_v:.1f} m/s) is more than 2x off the hand terminal-velocity estimate ({hand_v:.1f} m/s at ground density) - check Cd*S and descent mass."))
            else:
                checks.append(SanityCheck("Descent rate", "OK", f"simulated impact speed {sim_v:.1f} m/s vs. hand estimate {hand_v:.1f} m/s (v=sqrt(2mg/(rho*CdS)) at ground density)."))

    return checks
