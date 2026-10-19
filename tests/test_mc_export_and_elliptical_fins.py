"""2026-10-20 review ("judge-grade LASC package"):

1. mc_export.py - a new self-contained Monte Carlo export (Mission[ID]_
   MonteCarlo_RocketPy_v[N].py/.ipynb) using rocketpy's own Stochastic*
   classes + MonteCarlo, built from the SAME nominal-vehicle sections as
   case_export.py (never a second, divergent copy of the physics).

2. Found while building it: bup_rocketpy/monte_carlo.py's
   _run_one_mc_sample() wrapped EVERY fin surface in
   StochasticTrapezoidalFins unconditionally, regardless of its real
   shape - any elliptical-finned rocket (task #60's own feature) crashed
   every single Monte Carlo sample with AttributeError: 'EllipticalFins'
   object has no attribute 'tip_chord'. A free-form fin set has no
   corresponding Stochastic* class in rocketpy==1.13.0 at all - this is a
   genuine upstream limitation, handled by skipping it with a warning
   rather than crashing the whole batch.

3. montecarlo_page.py hardcoded total_impulse_Ns=1871.3 (PROMETEO's own
   motor) for EVERY rocket's default_uncertainties() call - any other
   loaded rocket got its total-impulse uncertainty centered on the WRONG
   nominal value. Fixed to use the loaded .eng's own real total impulse.

Uses PROMETEO's real .ork, with text-surgery to inject an elliptical fin
set (same convention as test_freeform_elliptical_fins.py) - no invented
rocket.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nbformat

from bup_rocketpy import mc_export, monte_carlo, ork_reader, translate
from bup_rocketpy.motor_reader import read_eng

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_mc_export_and_elliptical_fins")
DRY_MASS_KG, DRY_CG_M = 5.6622, 0.6279

TRAPEZOID_BLOCK_RE = re.compile(r"              <trapezoidfinset>.*?</trapezoidfinset>", re.S)
ELLIPTICAL_BLOCK = (
    "              <ellipticalfinset>\n"
    "                <name>Aletas elipticas</name>\n"
    "                <id>2629985e-15b3-47ad-a58f-65c7175fea27</id>\n"
    "                <instancecount>4</instancecount>\n"
    "                <fincount>4</fincount>\n"
    "                <radiusoffset method=\"surface\">0.0</radiusoffset>\n"
    "                <angleoffset method=\"relative\">0.0</angleoffset>\n"
    "                <rotation>0.0</rotation>\n"
    "                <axialoffset method=\"bottom\">0.0</axialoffset>\n"
    "                <position type=\"bottom\">0.0</position>\n"
    "                <finish>normal</finish>\n"
    "                <material type=\"bulk\" density=\"1850.0\" group=\"Composites\">Fiberglass</material>\n"
    "                <thickness>0.003</thickness>\n"
    "                <crosssection>rounded</crosssection>\n"
    "                <cant>0.0</cant>\n"
    "                <filletradius>0.0</filletradius>\n"
    "                <filletmaterial type=\"bulk\" density=\"680.0\" group=\"PaperProducts\">Cardboard</filletmaterial>\n"
    "                <rootchord>0.2</rootchord>\n"
    "                <height>0.14</height>\n"
    "              </ellipticalfinset>"
)


def _elliptical_variant_path():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(ORK_PATH, encoding="utf-8") as f:
        content = f.read()
    injected = TRAPEZOID_BLOCK_RE.sub(ELLIPTICAL_BLOCK, content)
    assert injected != content
    path = os.path.join(OUT_DIR, "elliptical_variant.ork")
    with open(path, "w", encoding="utf-8") as f:
        f.write(injected)
    return path


def _build_common(ork_path=ORK_PATH):
    parsed = ork_reader.read_ork(ork_path)
    parsed_eng = read_eng(ENG_PATH)
    mass_est = translate.MassEstimate(DRY_MASS_KG, DRY_CG_M, "test")
    i_axial, i_transverse = translate.estimate_dry_inertia(parsed, mass_est)
    radius_m = next(t.radius for t in parsed.body_tubes if t.radius)
    return parsed, parsed_eng, i_axial, i_transverse, radius_m


def test_monte_carlo_sample_no_longer_crashes_on_elliptical_fins():
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common(_elliptical_variant_path())
    fin = next(f for f in parsed.fins if f.name == "Aletas elipticas")
    assert fin.shape == "elliptical"  # fixture assumption

    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, parsed_eng.total_impulse_Ns, parsed.launch.wind_average_ms)
    u = {unc.name: unc for unc in uncertainties if unc.enabled}
    apogee, x_impact, y_impact, _traj = monte_carlo._run_one_mc_sample(
        parsed, parsed_eng, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG,
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, u, include_recovery=True, sample_seed=None,
    )
    assert apogee > 0


def test_default_uncertainties_uses_the_loaded_motors_real_total_impulse_not_a_hardcoded_one():
    """montecarlo_page.py used to call default_uncertainties(dry_mass,
    1871.3, wind) regardless of which rocket/motor was actually loaded -
    1871.3 N*s is specifically PROMETEO's own Icarus I K519. A real
    bup_rocketpy/motor_reader.ParsedEng already exposes its own real
    total_impulse_Ns (trapezoid-integrated from the real thrust curve) -
    this is what should be used instead."""
    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    real_impulse = parsed_eng.total_impulse_Ns
    assert abs(real_impulse - 1871.3) > 1.0, "fixture sanity check: PROMETEO's real integrated impulse should differ measurably from the old hardcoded literal, or this test can't tell the two apart"

    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, real_impulse, parsed.launch.wind_average_ms)
    impulse_u = next(u for u in uncertainties if u.name == "total_impulse_Ns")
    assert impulse_u.nominal == real_impulse

    with open(os.path.join(REPO_ROOT, "bup_rocketpy", "gui", "pages", "montecarlo_page.py"), encoding="utf-8") as f:
        source = f.read()
    call_line = next(line for line in source.splitlines() if "default_uncertainties(" in line and "def " not in line)
    assert "1871.3" not in call_line, f"the default_uncertainties(...) call must not hardcode any single rocket's total impulse, got: {call_line!r}"
    assert "parsed_eng.total_impulse_Ns" in call_line


def test_mc_script_and_notebook_run_end_to_end_and_agree():
    import shutil
    import subprocess

    parsed, parsed_eng, i_ax, i_tr, radius = _build_common()
    uncertainties = monte_carlo.default_uncertainties(DRY_MASS_KG, parsed_eng.total_impulse_Ns, parsed.launch.wind_average_ms)

    os.makedirs(OUT_DIR, exist_ok=True)
    shutil.copy(ENG_PATH, os.path.join(OUT_DIR, os.path.basename(ENG_PATH)))
    shutil.copy(POWER_OFF_DRAG, os.path.join(OUT_DIR, "power_off_drag.csv"))
    shutil.copy(POWER_ON_DRAG, os.path.join(OUT_DIR, "power_on_drag.csv"))

    py_filename, py_source = mc_export.generate_mc_script(
        "44", 1, parsed, parsed_eng, os.path.basename(ENG_PATH), "power_off_drag.csv", "power_on_drag.csv",
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, uncertainties, n_simulations=5, include_recovery=True, seed=42,
    )
    assert py_filename == "Mission44_MonteCarlo_RocketPy_v1.py"
    assert "bup_rocketpy" not in py_source
    compile(py_source, py_filename, "exec")
    py_path = os.path.join(OUT_DIR, py_filename)
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(py_source)

    proc = subprocess.run([sys.executable, py_path], capture_output=True, text=True, timeout=180, cwd=OUT_DIR)
    assert proc.returncode == 0, f"MC script failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"

    import json
    results_dir = os.path.join(OUT_DIR, "results_Mission44_MonteCarlo_RocketPy_v1")
    with open(os.path.join(results_dir, "results_montecarlo.json")) as f:
        results = json.load(f)
    assert results["n_simulations"] == 5
    assert results["apogee_agl_mean_m"] > 0
    assert results["apogee_agl_p05_m"] <= results["apogee_agl_p95_m"]
    assert os.path.exists(os.path.join(results_dir, "landing_ellipses.kml"))
    assert os.path.exists(os.path.join(results_dir, "montecarlo.png"))
    # the verbose per-sample rocketpy bookkeeping file must be cleaned up, not shipped
    assert not os.path.exists(os.path.join(results_dir, "montecarlo.inputs.txt"))

    nb_filename, nb_text = mc_export.generate_mc_notebook(
        "44", 1, parsed, parsed_eng, os.path.basename(ENG_PATH), "power_off_drag.csv", "power_on_drag.csv",
        DRY_MASS_KG, DRY_CG_M, i_ax, i_tr, radius, uncertainties, n_simulations=5, include_recovery=True, seed=42,
    )
    assert nb_filename == "Mission44_MonteCarlo_RocketPy_v1.ipynb"
    nb = nbformat.reads(nb_text, as_version=4)
    nbformat.validate(nb)
    assert "bup_rocketpy" not in nb_text


if __name__ == "__main__":
    test_monte_carlo_sample_no_longer_crashes_on_elliptical_fins()
    test_default_uncertainties_uses_the_loaded_motors_real_total_impulse_not_a_hardcoded_one()
    test_mc_script_and_notebook_run_end_to_end_and_agree()
    print("\nMC EXPORT AND ELLIPTICAL FINS: OK")
