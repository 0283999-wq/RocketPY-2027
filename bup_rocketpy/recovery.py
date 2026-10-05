"""Recovery panel (2026-09-25 review, Section 5): for each parachute,
diameter, projected area, Cd, Cd*S, and a HAND-CALCULATED terminal
velocity (v = sqrt(2*m*g / (rho*Cd*S))) at both the deployment altitude
and ground level, next to the simulated descent rate - this is what LASC
officials asked the team for on site, per tonight's instructions. The
hand-calc is a deliberately independent cross-check of the simulated
number: if they disagree by a lot, that is itself a signal something
(mass, Cd*S, or the simulation) is off, which is the whole point of
having both.
"""
import math
from dataclasses import dataclass, field

G0 = 9.80665

# 2026-10-06 review: a real case - two parachutes (a real second
# OpenRocket-authored component, plus a separately reefed-marked one)
# both triggered near apogee, ~10ms apart. rocketpy's own Parachute
# physics tracks exactly ONE "currently active" canopy's Cd*S at a time
# (a single self.parachute_cd_s attribute on the Flight object,
# overwritten by setattr() every time ANY parachute's trigger fires -
# verified against rocketpy/simulation/flight.py's own u_dot_parachute)
# - it does NOT sum multiple simultaneously-open canopies. So the FIRST
# parachute to trigger here got its own Cd*S completely REPLACED 10ms
# later when the second one triggered, before it had any real chance to
# slow the rocket down at all - its own row below still shows a near-
# free-fall descent rate, which reads as "it's not applying/doing
# nothing", not because the simulation skipped it, but because rocketpy
# genuinely discarded its contribution the instant the next trigger
# fired. This is the SAME mechanism a normal drogue-then-main dual-
# deploy relies on (main correctly replacing drogue once it opens) -
# it only becomes misleading when two parachutes that were both meant
# to matter end up open at (near) the same moment.
OVERWRITTEN_THRESHOLD_S = 1.0


@dataclass
class ParachutePanelRow:
    name: str
    diameter_m: float
    area_m2: float
    cd: float
    cd_s_m2: float
    deploy_time_s: float
    deploy_altitude_agl_m: float
    descent_rate_sim_ms: float  # simulated |vz| reached under this chute (see recovery_panel() docstring for how this is sampled)
    hand_terminal_velocity_at_deploy_alt_ms: float
    hand_terminal_velocity_at_ground_ms: float
    diff_pct_at_deploy_alt: float  # (sim - hand) / hand * 100, at deployment-altitude density
    diff_pct_at_ground: float
    note: str = ""  # 2026-10-06 review: see OVERWRITTEN_THRESHOLD_S below


def _hand_terminal_velocity(mass_kg, air_density_kgm3, cd_s_m2):
    if cd_s_m2 <= 0 or air_density_kgm3 <= 0:
        return float("nan")
    return math.sqrt(2 * mass_kg * G0 / (air_density_kgm3 * cd_s_m2))


def recovery_panel(flight, env, descent_mass_kg):
    """Returns a list of ParachutePanelRow, one per parachute that
    actually deployed during this flight (flight.parachute_events).

    descent_rate_sim_ms is sampled at the time just before the NEXT
    parachute event fires (or at landing, for the last one) - terminal
    velocity under drag is reached asymptotically, so sampling right
    before the phase ends is the closest the simulation gets to a
    settled "descent rate under this specific canopy" figure, rather
    than the instantaneous (often still-decelerating) speed right at
    that chute's own deployment instant.

    descent_mass_kg: the mass descending under canopy - dry rocket mass
    including the motor's OWN dry mass (propellant is spent by this
    point), matching what's actually hanging under the parachute.
    """
    events = list(getattr(flight, "parachute_events", []))
    if not events:
        return []

    rows = []
    for i, (t_deploy, chute) in enumerate(events):
        next_t = events[i + 1][0] if i + 1 < len(events) else None
        t_sample = next_t - 0.05 if next_t is not None else flight.t_final - 0.05
        t_sample = max(t_sample, t_deploy + 0.01)
        note = ""
        this_name = getattr(chute, "name", "")
        next_name = getattr(events[i + 1][1], "name", "the next parachute") if next_t is not None else ""
        # The reefed stage being replaced by ITS OWN "(full)" counterpart
        # a few seconds later is the INTENDED, correct mechanism (one
        # physical canopy changing size via a line cutter) - not two
        # independent parachutes losing each other's contribution. Only
        # flag a genuinely unrelated pair.
        is_own_reefed_to_full_pair = this_name.endswith(" (reefed)") and next_name == this_name[: -len(" (reefed)")] + " (full)"
        if next_t is not None and (next_t - t_deploy) < OVERWRITTEN_THRESHOLD_S and not is_own_reefed_to_full_pair:
            note = (
                f"'{next_name}' triggered only {next_t - t_deploy:.2f}s later - rocketpy tracks ONE active "
                f"canopy's Cd*S at a time, so '{next_name}' REPLACED (not added to) this one's drag from "
                f"{next_t:.2f}s onward. The descent rate below reflects almost no time under THIS canopy "
                f"alone - if both were meant to contribute, model them as one canopy that changes size "
                f"(the Rocket page's 'Reefed with line cutter' feature) instead of two separate parachutes."
            )
        vx, vy, vz = flight.vx(t_sample), flight.vy(t_sample), flight.vz(t_sample)
        descent_rate_sim = math.sqrt(vx**2 + vy**2 + vz**2)

        cd_s = chute.cd_s
        # translate.build_rocket passes radius=/drag_coefficient= to
        # rocket.add_parachute() precisely so the built rocketpy
        # Parachute object carries the REAL diameter/Cd from the .ork,
        # not just the combined cd_s - read those back here. Falls back
        # to deriving a diameter from cd_s at an assumed Cd only for a
        # Parachute this module didn't build itself (e.g. a hand-built
        # test fixture with no radius set).
        cd = getattr(chute, "drag_coefficient", None) or 1.5  # common round-canopy default if truly unavailable
        radius = getattr(chute, "radius", None)
        diameter = 2.0 * radius if radius else (2.0 * math.sqrt(cd_s / (cd * math.pi)) if cd_s > 0 else 0.0)
        area = math.pi * (diameter / 2.0) ** 2

        deploy_alt_agl = flight.z(t_deploy) - env.elevation
        rho_deploy = env.density(flight.z(t_deploy))
        rho_ground = env.density(env.elevation)

        hand_v_deploy = _hand_terminal_velocity(descent_mass_kg, rho_deploy, cd_s)
        hand_v_ground = _hand_terminal_velocity(descent_mass_kg, rho_ground, cd_s)

        rows.append(ParachutePanelRow(
            name=getattr(chute, "name", f"parachute {i+1}"),
            diameter_m=diameter, area_m2=area, cd=cd, cd_s_m2=cd_s,
            deploy_time_s=t_deploy, deploy_altitude_agl_m=deploy_alt_agl,
            descent_rate_sim_ms=descent_rate_sim,
            hand_terminal_velocity_at_deploy_alt_ms=hand_v_deploy,
            hand_terminal_velocity_at_ground_ms=hand_v_ground,
            diff_pct_at_deploy_alt=(descent_rate_sim - hand_v_deploy) / hand_v_deploy * 100 if hand_v_deploy else float("nan"),
            diff_pct_at_ground=(descent_rate_sim - hand_v_ground) / hand_v_ground * 100 if hand_v_ground else float("nan"),
            note=note,
        ))
    return rows
