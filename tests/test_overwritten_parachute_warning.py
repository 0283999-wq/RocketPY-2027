"""2026-10-06 review: a real report - "siento que se esta saltando
varios datos... necesitaba saber que velocidad de caida tenia en el
reefed, como que lo esta haciendo balistico" (I feel like it's skipping
data... I needed the descent rate under the reefed stage, like it's
doing it ballistic). Root cause, confirmed against rocketpy's own
source (rocketpy/simulation/flight.py's u_dot_parachute): the user had
put TWO independent parachute components in OpenRocket (to represent a
reefed canopy) PLUS marked one as "reefed" via this app's own line-
cutter feature - three parachute objects total, two of which (the real
second OpenRocket chute, and the reefed-split's own first stage) both
ended up apogee-triggered and fired ~10ms apart (via translate.py's
own duplicate-trigger nudge, previous review). rocketpy's Parachute
physics tracks exactly ONE "currently active" canopy's Cd*S at a time
(a single self.parachute_cd_s attribute, overwritten by setattr() on
EVERY parachute trigger) - it never sums simultaneously-open canopies.
So the first chute to trigger had its own drag contribution silently
discarded the instant the second one fired, 10ms later, before it had
any chance to slow the rocket down - which is exactly why its own row
looked "ballistic".

Uses PROMETEO's real .ork/parachute, duplicated + marked reefed via
dataclasses.replace, matching test_reefed_parachute.py's and
test_duplicate_parachute_trigger.py's own "no invented rocket, just a
realistic second chute" convention.
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import recovery, translate
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279


def _load_with_independent_plus_reefed_chute():
    """The user's real setup: a plain, independent second parachute
    (their "second OpenRocket parachute component"), PLUS the first
    marked reefed via this app's own feature - both apogee-triggered."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    chute = parsed.parachutes[0]
    reefed_chute = dataclasses.replace(
        chute, is_reefed=True, reefed_diameter_m=0.64, reefed_cd=chute.cd,
        cutter_altitude_m=500.0, cutter_delay_s=0.5,
    )
    independent_chute = dataclasses.replace(chute, name="Second chute (independent)")
    parsed.parachutes = [reefed_chute, independent_chute]
    return parsed, eng


def _run(parsed, eng):
    flight, rocket = translate.ork_to_flight(
        parsed, eng, ENG_PATH,
        power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG,
        terminate_on_apogee=False, include_recovery=True,
        dry_mass_override_kg=DRY_MASS_KG, dry_cg_override_m=DRY_CG_M,
    )
    from bup_rocketpy import translate as translate_mod
    env = translate_mod.build_environment(parsed.launch)
    descent_mass_kg = DRY_MASS_KG + flight.rocket.motor.dry_mass
    return recovery.recovery_panel(flight, env, descent_mass_kg)


def test_the_overwritten_chute_gets_a_clear_note():
    parsed, eng = _load_with_independent_plus_reefed_chute()
    rows = _run(parsed, eng)
    assert len(rows) == 3, f"expected 3 deployment events (reefed, independent, full), got {[r.name for r in rows]}"

    # Whichever of the two apogee-triggered chutes fired FIRST got
    # overwritten ~10ms later by the other - it must carry a clear note.
    overwritten = [r for r in rows if r.note]
    assert len(overwritten) == 1, f"expected exactly one overwritten-chute note, got notes on: {[r.name for r in overwritten]}"
    assert "REPLACED" in overwritten[0].note
    assert "Reefed with line cutter" in overwritten[0].note


def test_the_real_reefed_to_full_transition_never_gets_a_false_positive_note():
    """The reefed stage being replaced by its OWN "(full)" counterpart
    later is the INTENDED mechanism (one physical canopy changing size)
    - must never be flagged as if it were two unrelated chutes."""
    parsed, eng = _load_with_independent_plus_reefed_chute()
    rows = _run(parsed, eng)
    reefed_row = next(r for r in rows if r.name.endswith("(reefed)"))
    full_row = next(r for r in rows if r.name.endswith("(full)"))
    assert reefed_row.note == "" or "REPLACED" not in reefed_row.note or "(full)" not in reefed_row.note
    assert full_row.note == ""


def test_a_normal_single_reefed_chute_with_no_independent_second_gets_no_notes():
    """Baseline: the common, correct case (test_reefed_parachute.py's
    own setup - just ONE chute marked reefed, no extra independent
    parachute) must produce zero false-positive notes."""
    parsed = read_ork(ORK_PATH)
    eng = read_eng(ENG_PATH)
    chute = parsed.parachutes[0]
    parsed.parachutes[0] = dataclasses.replace(
        chute, is_reefed=True, reefed_diameter_m=0.7, reefed_cd=chute.cd,
        cutter_altitude_m=500.0, cutter_delay_s=0.5,
    )
    rows = _run(parsed, eng)
    assert all(r.note == "" for r in rows), f"unexpected note(s) on a normal single-reefed-chute flight: {[(r.name, r.note) for r in rows if r.note]}"


if __name__ == "__main__":
    test_the_overwritten_chute_gets_a_clear_note()
    test_the_real_reefed_to_full_transition_never_gets_a_false_positive_note()
    test_a_normal_single_reefed_chute_with_no_independent_second_gets_no_notes()
    print("\nOVERWRITTEN PARACHUTE WARNING: OK")
