"""Pre-download verification gate (2026-10-20 review, "judge-grade LASC
package" item 5): before the LASC zip is offered for download, every
exported case .py is actually RUN in a clean verification venv (no
bup_rocketpy on the path - proving the "pip install rocketpy" claim for
real, not just by inspection) and its apogee, flight time, landing
point and parachute/descent-rate numbers are checked against the app's
own already-computed Flight for that exact case. Each companion .ipynb
is checked for consistency against its OWN sibling .py (same code, so
near-exact agreement is expected) rather than a second comparison
against the app - cheaper, and a real divergence there means the .py/
.ipynb generation diverged, which is a different bug than "wrong
physics". If any check fails, build_lasc_zip (the only caller) raises
a clear ValueError naming the file and the specific failing number
instead of ever producing a zip - the caller is expected to surface
that to the user and refuse the download.

The verification venv is created once and cached under outputs/ (pip
install is the slow part; re-syncing an already-satisfied venv is a
fast no-op, same convention as start.bat), not a brand-new venv per
build - that would make every "Build submission .zip" click pay a
30-90s rocketpy install.
"""
import json
import os
import subprocess
import sys
import venv

# A single Flight's ascent is governed by the EXACT same deterministic
# inputs in both the app and the exported script, so apogee/flight-time
# should match to many more than 2 significant figures - 1% is a loose
# ceiling, not a target. Landing point is looser: it depends on the
# DESCENT phase after a sudden Cd discontinuity at parachute deployment,
# where two independently-constructed-but-physically-identical rocketpy
# Rocket/Environment objects can take microscopically different adaptive
# ODE steps and accumulate a few meters of difference over a long
# descent, even with bit-identical ascent physics (confirmed directly:
# PROMETEO's own apogee matched to 12 significant figures while landing
# x differed by ~2%) - a strict 1% here would flag a real, harmless
# numerical artifact as a false "wrong physics" failure.
DEFAULT_TOLERANCES_PCT = {
    "apogee_agl_m": 1.0,
    "flight_time_s": 1.0,
    "landing_x_m": 8.0,
    "landing_y_m": 8.0,
}
DESCENT_RATE_TOLERANCE_PCT = 5.0
NOTEBOOK_CONSISTENCY_TOLERANCE_PCT = 0.5  # the .py and .ipynb share the IDENTICAL generated code - this only allows for float-repr/line-ending jitter, not a real divergence


def _verification_venv_dir():
    return os.path.join(os.getcwd(), "outputs", "lasc_verify_venv")


def ensure_verification_venv(rocketpy_version):
    """Creates (if missing) and re-syncs the cached verification venv,
    returning its python executable path. No bup_rocketpy is ever
    installed into it - that's the entire point."""
    vdir = _verification_venv_dir()
    python_exe = os.path.join(vdir, "bin", "python3")
    if not os.path.exists(python_exe):
        venv.EnvBuilder(with_pip=True).create(vdir)
    subprocess.run([python_exe, "-m", "pip", "install", "-q", f"rocketpy=={rocketpy_version}"], check=True, timeout=300)
    return python_exe


def _pct_diff(expected, actual):
    denom = max(abs(expected), 1e-9)
    return abs(actual - expected) / denom * 100.0


def _run_script_for_results(python_exe, script_path, cwd, results_stem, results_filename="results.json"):
    """Runs script_path with python_exe, cwd=cwd, and reads back
    results_<results_stem>/<results_filename>. results_stem is passed
    explicitly rather than derived from script_path's own filename：the
    notebook-extracted combined script (verify_case_files below) is
    saved under a DIFFERENT temp filename than the notebook itself, but
    its generated code still bakes in the ORIGINAL notebook's own
    filename_stem for RESULTS_DIR (case_export.py's Setup section), so
    deriving the expected directory from script_path would look in the
    wrong place. Returns (results_dict, None) or (None, error_message) -
    never raises, so the caller can report a clear per-file failure
    instead of an unhandled exception."""
    proc = subprocess.run([python_exe, script_path], capture_output=True, text=True, encoding="utf-8", timeout=180, cwd=cwd)
    if proc.returncode != 0:
        return None, f"exited with code {proc.returncode}: {proc.stderr[-1500:]}"
    results_path = os.path.join(cwd, f"results_{results_stem}", results_filename)
    if not os.path.exists(results_path):
        return None, f"ran successfully but never wrote {results_filename}"
    with open(results_path, encoding="utf-8") as f:
        return json.load(f), None


def _notebook_to_combined_script(notebook_path, out_path):
    """Extracts a notebook's code cells (concatenated in order, the same
    thing 'Run All' does) into a plain .py - done HOST-side with
    nbformat, so the verification venv itself never needs a Jupyter
    kernel, just rocketpy."""
    import nbformat
    nb = nbformat.read(notebook_path, as_version=4)
    combined = "\n\n".join("".join(c.source) for c in nb.cells if c.cell_type == "code")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(combined)


def _compare_numbers(label, expected, actual, tolerances_pct):
    mismatches = []
    for key, tol_pct in tolerances_pct.items():
        if key not in expected or key not in actual:
            continue
        diff_pct = _pct_diff(expected[key], actual[key])
        if diff_pct > tol_pct:
            mismatches.append(f"{label}.{key}: app={expected[key]:.3f}, exported={actual[key]:.3f} ({diff_pct:.2f}% > {tol_pct}% tolerance)")
    return mismatches


def _compare_parachute_events(label, expected_events, actual_events):
    mismatches = []
    if len(expected_events) != len(actual_events):
        mismatches.append(f"{label}: parachute event count differs (app={len(expected_events)}, exported={len(actual_events)})")
        return mismatches
    for i, (exp, act) in enumerate(zip(expected_events, actual_events)):
        diff_pct = _pct_diff(exp["descent_rate_ms"], act["descent_rate_ms"])
        if diff_pct > DESCENT_RATE_TOLERANCE_PCT:
            mismatches.append(f"{label}: parachute event {i} ({act.get('name', '?')}) descent rate app={exp['descent_rate_ms']:.2f} m/s, exported={act['descent_rate_ms']:.2f} m/s ({diff_pct:.2f}% > {DESCENT_RATE_TOLERANCE_PCT}% tolerance)")
    return mismatches


def _app_case_expected(flight):
    events = list(getattr(flight, "parachute_events", []))
    parachute_events = []
    for i, (t_deploy, chute) in enumerate(events):
        next_t = events[i + 1][0] if i + 1 < len(events) else None
        t_sample = (next_t - 0.05) if next_t is not None else (flight.t_final - 0.05)
        t_sample = max(t_sample, t_deploy + 0.01)
        vx, vy, vz = flight.vx(t_sample), flight.vy(t_sample), flight.vz(t_sample)
        parachute_events.append({"name": getattr(chute, "name", f"parachute {i + 1}"), "descent_rate_ms": (vx ** 2 + vy ** 2 + vz ** 2) ** 0.5})
    return {
        "apogee_agl_m": flight.apogee - flight.env.elevation,
        "flight_time_s": flight.t_final,
        "landing_x_m": flight.x_impact,
        "landing_y_m": flight.y_impact,
    }, parachute_events


def verify_case_files(python_exe, case_name, py_filename, nb_filename, staging_dir, app_flight):
    """Runs the case's .py AND .ipynb (as a combined script) in the
    verification venv, inside staging_dir (so it sees the real sibling
    .eng/CSVs), and checks both against app_flight (the app's own
    already-computed Flight for this exact case) and against each
    other. Returns a list of mismatch strings - empty means it passed."""
    mismatches = []
    expected, expected_events = _app_case_expected(app_flight)
    # The .py and .ipynb share the IDENTICAL baked-in filename_stem for
    # RESULTS_DIR (case_export.py's Setup section) regardless of what
    # either file is actually named on disk - both results land in the
    # SAME results_<stem>/ folder.
    results_stem = os.path.splitext(py_filename)[0]

    py_path = os.path.join(staging_dir, py_filename)
    py_actual, py_err = _run_script_for_results(python_exe, py_path, staging_dir, results_stem)
    if py_err:
        return [f"{py_filename} failed to run standalone in the verification venv: {py_err}"]
    mismatches += _compare_numbers(py_filename, expected, py_actual, DEFAULT_TOLERANCES_PCT)
    mismatches += _compare_parachute_events(py_filename, expected_events, py_actual.get("parachute_events", []))

    nb_path = os.path.join(staging_dir, nb_filename)
    combined_script_path = os.path.join(staging_dir, f"_verify_{os.path.splitext(nb_filename)[0]}.py")
    _notebook_to_combined_script(nb_path, combined_script_path)
    nb_actual, nb_err = _run_script_for_results(python_exe, combined_script_path, staging_dir, results_stem)
    os.remove(combined_script_path)
    if nb_err:
        mismatches.append(f"{nb_filename} failed to run standalone in the verification venv: {nb_err}")
    else:
        # The .py/.ipynb share the identical generated code - compared
        # against EACH OTHER, not the app a second time, so this catches
        # a notebook-generation bug specifically (not a physics question).
        mismatches += _compare_numbers(nb_filename, py_actual, nb_actual, {k: NOTEBOOK_CONSISTENCY_TOLERANCE_PCT for k in DEFAULT_TOLERANCES_PCT})

    return mismatches


def verify_mc_files(python_exe, py_filename, nb_filename, staging_dir, n_simulations):
    """Monte Carlo output is inherently stochastic - there is no single
    "app number" to compare against in general, so this only confirms
    the .py actually runs standalone and produces a sane,
    n_simulations-sized result (never a numeric match requirement)."""
    mismatches = []
    py_path = os.path.join(staging_dir, py_filename)
    results_stem = os.path.splitext(py_filename)[0]
    actual, err = _run_script_for_results(python_exe, py_path, staging_dir, results_stem, results_filename="results_montecarlo.json")
    if err:
        return [f"{py_filename} failed to run standalone in the verification venv: {err}"]
    if actual.get("n_simulations") != n_simulations:
        mismatches.append(f"{py_filename}: ran {actual.get('n_simulations')} samples, expected {n_simulations}")
    if not (actual.get("apogee_agl_mean_m", 0) > 0):
        mismatches.append(f"{py_filename}: apogee_agl_mean_m is not a sane positive number ({actual.get('apogee_agl_mean_m')})")
    return mismatches
