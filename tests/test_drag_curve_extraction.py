"""2026-09-26 review item A (critical physics bug): the .ork's own stored-
databranch drag-curve extractor used to keep every Thrust==0 datapoint all
the way to the end of the stored simulation, not just to apogee. Past
apogee, OpenRocket's "Axial drag coefficient" includes the deployed
parachute's drag (Diego found Cd=589.775 from Mach 0.02-0.212, 68 points,
in a real exported zip's power_off_drag.csv) - contaminating the coast/
power-off curve used for the WHOLE rest of the ascent-phase simulation,
not just the descent it actually came from.

Fixed in ork_reader.extract_drag_curves_from_stored_sim by tracking
"Vertical velocity" and stopping coast collection the instant it goes
negative (past apogee) - matching reference/prometeo_mission44/scripts/
extract_drag_curves.py's own BURNOUT..APOGEE bound, which was already
correct (only this live in-app path had the bug).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.ork_reader import extract_drag_curves_from_stored_sim

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMETEO_ORK = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
DUAL_DEPLOY_ORK = os.path.join(REPO_ROOT, "reference", "openrocket_examples", "Dual_parachute_deployment.ork")
MAX_SANE_CD = 1.5  # a real rocket's axial Cd is never this high pre-deployment; anything above is contamination


def test_no_contaminated_cd_in_prometeo_stored_sim():
    boost, coast = extract_drag_curves_from_stored_sim(PROMETEO_ORK)
    assert boost and coast, "expected PROMETEO's real .ork to have a stored databranch"
    max_boost_cd = max(c for _, c in boost)
    max_coast_cd = max(c for _, c in coast)
    print(f"\nPROMETEO: boost n={len(boost)} max_cd={max_boost_cd:.3f}; coast n={len(coast)} max_cd={max_coast_cd:.3f}")
    assert max_boost_cd < MAX_SANE_CD, f"boost curve has a contaminated Cd: {max_boost_cd}"
    assert max_coast_cd < MAX_SANE_CD, f"coast curve has a contaminated Cd: {max_coast_cd}"


def test_no_contaminated_cd_in_dual_deploy_example():
    """This fixture is the one that actually reproduces the bug directly
    (before the fix: coast max_cd=549.748, from its recorded descent-
    under-canopy phase) - PROMETEO's own stored sim happens not to
    trigger it, so this is the real regression guard."""
    boost, coast = extract_drag_curves_from_stored_sim(DUAL_DEPLOY_ORK)
    assert boost and coast, "expected this fixture to have a stored databranch"
    max_boost_cd = max(c for _, c in boost)
    max_coast_cd = max(c for _, c in coast)
    print(f"\nDual-deploy example: boost n={len(boost)} max_cd={max_boost_cd:.3f}; coast n={len(coast)} max_cd={max_coast_cd:.3f}")
    assert max_boost_cd < MAX_SANE_CD, f"boost curve has a contaminated Cd: {max_boost_cd}"
    assert max_coast_cd < MAX_SANE_CD, f"coast curve has a contaminated Cd: {max_coast_cd} - this is exactly item A's bug if it fires"


def test_mach_extrapolation_warning_fires_on_real_prometeo_default_path():
    """2026-09-26 review item B: PROMETEO's real default (no-override)
    flight organically exceeds its own drag curve's Mach coverage
    (curve covers 0-0.463, flight reaches ~0.477) - a real, naturally-
    occurring case, not a synthetic one. Confirms pipeline.run_simulation
    computes and flags this rather than silently extrapolating."""
    from bup_rocketpy.gui import pipeline
    import tempfile

    ork = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
    eng = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
    outdir = tempfile.mkdtemp()
    result = pipeline.load_files(ork, eng, outputs_dir=outdir)
    sim = pipeline.run_simulation(result, outdir)

    print(f"\nmax_mach={sim.max_mach:.3f}, drag_curve_max_mach={sim.drag_curve_max_mach:.3f}, extrapolated={sim.mach_extrapolated}")
    assert sim.drag_curve_max_mach is not None
    assert sim.mach_extrapolated is True, "PROMETEO's real curve/flight combination should organically trigger this warning"
    assert any(c.name == "Drag curve Mach coverage" and c.status == "WARN" for c in sim.sanity_checks), "expected a WARN sanity check surfacing this on the Results page"
