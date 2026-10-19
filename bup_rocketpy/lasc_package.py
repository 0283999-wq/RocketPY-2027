"""The LASC submission .zip (CLAUDE.md Sec 6 Phase 5; 2026-10-20 "judge-
grade LASC package" review covering CRS 10.1.3-10.1.14 and 10.2.1): the
per-case .py AND .ipynb files, a standalone Monte Carlo .py/.ipynb, the
.eng/.ork/Cd curves, the PDF report, and a README.md documenting all of
it with the exact pip command and expected apogee per case.
"""
import importlib.metadata
import os
import shutil
import zipfile


def _validation_status_line():
    """Live, plain-English validation summary for the LASC package's own
    README - 2026-09-28 review item 1: this used to be a hardcoded
    "PROVISIONAL: see PROGRESS.md" line, which was already stale and
    pointed a LASC judge at an internal repo file they'd never have.
    Falls back to a neutral line rather than failing the whole package
    build if validation can't be computed for some reason."""
    try:
        from bup_rocketpy import validation
        summary = validation.summarize_validation_status()
        return f"Model validation status: {summary.text}. See the app's Validation page for the full breakdown."
    except Exception:
        return "Model validation status: see the app's Validation page for the current breakdown."


def _rocketpy_version():
    """The ACTUALLY installed rocketpy version in this build/test
    environment - read from package metadata rather than hand-copying
    requirements.txt's own pin a second time, so it can never silently
    drift out of sync with what this submission was generated/verified
    against. Falls back to requirements.txt's pin only if metadata truly
    can't be read (e.g. an unusual install method)."""
    try:
        return importlib.metadata.version("rocketpy")
    except importlib.metadata.PackageNotFoundError:
        return "1.13.0"


def build_lasc_zip(output_zip_path, mission_id, parsed, parsed_eng, eng_path, ork_path, power_off_drag_path, power_on_drag_path, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, cases, version=1, eng_filename=None, ork_filename=None, mission_id_template=None, launch_override=None, motor_dry_override_kg=None, mass_source=None, inertia_source=None, launch_date_time_str=None, case_results=None, mc_uncertainties=None, mc_n_simulations=0, mc_seed=None, report_pdf_path=None):
    """cases: list of (case_name, include_recovery) tuples to export -
    typically [("Ballistic", False), ("Nominal", True)] at minimum
    (CRS 10.1.14: the RocketPy award requires nominal and ballistic).

    eng_filename/ork_filename: 2026-09-26 review item E - the user's OWN
    uploaded filenames (e.g. "Major_tom.ork"), not os.path.basename of
    eng_path/ork_path, which are this app's own tempfile paths
    (NiceGUI's upload handler saves to a random tmpXXXX.ork/.eng name and
    the original name was previously discarded right after the upload
    notification). Falls back to the path's own basename only if the
    real name truly isn't available (e.g. a script/test calling this
    directly with a real, meaningfully-named path already).

    launch_override/motor_dry_override_kg: 2026-10-19 review ("check
    every bug" audit) - passed straight through to case_export.
    generate_case_script (see its own docstring); without these, a
    submission built after applying real launch-day weather or a
    measured motor-mass correction would silently fly the UNcorrected
    .ork/.eng values instead of what the app itself actually simulated.

    mass_source/inertia_source/launch_date_time_str (2026-10-20 review,
    judge-grade LASC package): passed straight through to case_export/
    mc_export's own INPUTS block - see those modules' docstrings.

    case_results: optional dict {case_name: object with a .flight
    attribute} - typically state["case_results"] (rcsm_cases.run_all_
    cases's own return value), reused ONLY to print each case's already-
    computed expected apogee in the README, never to re-run anything.
    None (the default) renders "not available" instead of guessing.

    mc_uncertainties/mc_n_simulations/mc_seed: when mc_n_simulations > 0,
    also generates a standalone Mission[ID]_MonteCarlo_RocketPy_v
    [version].py/.ipynb (mc_export.py) using these uncertainties (None
    falls back to monte_carlo.default_uncertainties for this exact
    rocket/motor) - 0 (the default) skips the Monte Carlo export
    entirely, unchanged for every existing caller/test.

    report_pdf_path: an already-generated report PDF (report.
    generate_pdf's own output) to include under a clear submission-
    specific name. None (the default) skips it - unchanged for every
    existing caller/test."""
    from bup_rocketpy import case_export, mc_export

    rp_version = _rocketpy_version()
    eng_filename = eng_filename or os.path.basename(eng_path)
    ork_filename = ork_filename or os.path.basename(ork_path)

    base_path = output_zip_path[:-4] if output_zip_path.endswith(".zip") else output_zip_path
    staging_dir = base_path + "_staging"
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir)

    shutil.copy(eng_path, os.path.join(staging_dir, eng_filename))
    shutil.copy(ork_path, os.path.join(staging_dir, ork_filename))
    # 2026-10-19 review ("check every bug" audit, finding #7 of the
    # report/export report): power_off_drag_path/power_on_drag_path are
    # None whenever there's no Cd curve on file at all (CLAUDE.md Sec
    # 4.2 point 4's explicitly-anticipated "none available" case,
    # already handled at simulate-time via a placeholder Cd) - shutil.
    # copy(None, ...) raised a raw, unhelpful TypeError here instead.
    missing_drag_curves = []
    if power_off_drag_path:
        shutil.copy(power_off_drag_path, os.path.join(staging_dir, "power_off_drag.csv"))
    else:
        missing_drag_curves.append("power_off_drag.csv")
    if power_on_drag_path:
        shutil.copy(power_on_drag_path, os.path.join(staging_dir, "power_on_drag.csv"))
    else:
        missing_drag_curves.append("power_on_drag.csv")
    if missing_drag_curves:
        raise ValueError(
            f"Cannot build the LASC submission zip: no Cd curve available for {', '.join(missing_drag_curves)}. "
            "This .ork has no stored OpenRocket simulation data and no uploaded drag-curve CSV, so there is "
            "nothing real to include - upload a power_off_drag.csv/power_on_drag.csv on the Simulate page, or "
            "re-run and save a simulation in OpenRocket, then reload."
        )

    # 2026-10-19 review ("check every bug" audit, finding #6): DrogueOnly/
    # MainAtApogee need ONE specific, resolved chute (possibly a reefed-
    # stage surrogate), the SAME classification rcsm_cases.run_case
    # already uses for these exact two case names - resolved once here,
    # not re-implemented.
    from bup_rocketpy.rcsm_cases import _classify_parachutes
    drogue, main = (None, None)
    if any(name in ("DrogueOnly", "MainAtApogee") for name, _ in cases):
        drogue, main = _classify_parachutes(parsed)

    case_readme_rows = []
    for case_name, include_recovery in cases:
        recovery_chute, recovery_force_apogee = None, False
        if case_name == "DrogueOnly":
            recovery_chute = drogue
        elif case_name == "MainAtApogee":
            recovery_chute = main or drogue
            recovery_force_apogee = True
        if case_name in ("DrogueOnly", "MainAtApogee") and recovery_chute is None:
            continue  # no parachute with a resolvable Cd - same "can't build this case" condition rcsm_cases.run_case itself checks; skip rather than emit a broken script

        common_kwargs = dict(
            mission_id=mission_id, case_name=case_name, version=version,
            parsed=parsed, parsed_eng=parsed_eng, eng_filename=eng_filename,
            power_off_drag_filename="power_off_drag.csv", power_on_drag_filename="power_on_drag.csv",
            dry_mass_kg=dry_mass_kg, dry_cg_m=dry_cg_m, i_axial=i_axial, i_transverse=i_transverse, radius_m=radius_m,
            include_recovery=include_recovery, mission_id_template=mission_id_template,
            launch_override=launch_override, motor_dry_override_kg=motor_dry_override_kg,
            recovery_chute=recovery_chute, recovery_force_apogee=recovery_force_apogee,
            mass_source=mass_source, inertia_source=inertia_source, launch_date_time_str=launch_date_time_str,
        )
        py_filename, py_source = case_export.generate_case_script(**common_kwargs)
        with open(os.path.join(staging_dir, py_filename), "w", encoding="utf-8") as f:
            f.write(py_source)
        nb_filename, nb_source = case_export.generate_case_notebook(**common_kwargs)
        with open(os.path.join(staging_dir, nb_filename), "w", encoding="utf-8") as f:
            f.write(nb_source)

        apogee_note = "not available - run this case on the RCSM Cases page first"
        case_result = (case_results or {}).get(case_name)
        flight = getattr(case_result, "flight", None)
        if flight is not None:
            apogee_note = f"~{flight.apogee - flight.env.elevation:.0f} m AGL (as last computed by the app)"
        case_readme_rows.append((case_name, py_filename, nb_filename, apogee_note))

    mc_readme_row = None
    if mc_n_simulations and mc_n_simulations > 0:
        from bup_rocketpy import monte_carlo as _monte_carlo
        uncertainties = mc_uncertainties if mc_uncertainties is not None else _monte_carlo.default_uncertainties(dry_mass_kg, parsed_eng.total_impulse_Ns, parsed.launch.wind_average_ms)
        mc_kwargs = dict(
            mission_id=mission_id, version=version, parsed=parsed, parsed_eng=parsed_eng, eng_filename=eng_filename,
            power_off_drag_filename="power_off_drag.csv", power_on_drag_filename="power_on_drag.csv",
            dry_mass_kg=dry_mass_kg, dry_cg_m=dry_cg_m, i_axial=i_axial, i_transverse=i_transverse, radius_m=radius_m,
            uncertainties=uncertainties, n_simulations=mc_n_simulations, include_recovery=True,
            mission_id_template=mission_id_template, launch_override=launch_override, motor_dry_override_kg=motor_dry_override_kg,
            mass_source=mass_source, inertia_source=inertia_source, launch_date_time_str=launch_date_time_str, seed=mc_seed,
        )
        mc_py_filename, mc_py_source = mc_export.generate_mc_script(**mc_kwargs)
        with open(os.path.join(staging_dir, mc_py_filename), "w", encoding="utf-8") as f:
            f.write(mc_py_source)
        mc_nb_filename, mc_nb_source = mc_export.generate_mc_notebook(**mc_kwargs)
        with open(os.path.join(staging_dir, mc_nb_filename), "w", encoding="utf-8") as f:
            f.write(mc_nb_source)
        mc_readme_row = (mc_py_filename, mc_nb_filename, mc_n_simulations)

    report_filename = None
    if report_pdf_path and os.path.exists(report_pdf_path):
        report_filename = f"Mission{mission_id}_Report.pdf"
        shutil.copy(report_pdf_path, os.path.join(staging_dir, report_filename))

    # 2026-10-20 review ("judge-grade LASC package", item 5): before this
    # ever becomes a zip, every case file actually RUNS in a clean venv
    # (no bup_rocketpy on the path - proving "pip install rocketpy" for
    # real) and its apogee/flight-time/landing-point/parachute numbers
    # are checked against the app's own already-computed Flight for that
    # exact case. case_results is only ever None for a caller that has
    # no real Flight to compare against (an existing test, or a script
    # calling this directly) - verification is skipped for those, not
    # faked; the real app (exports_page.py) always has it.
    if case_results:
        from bup_rocketpy import export_verification
        all_mismatches = []
        verified_any = False
        try:
            python_exe = export_verification.ensure_verification_venv(rp_version)
        except Exception as exc:
            shutil.rmtree(staging_dir)
            raise ValueError(f"Cannot build the LASC submission zip: the verification environment could not be prepared ({exc}). Try again, or check network access for 'pip install rocketpy'.") from exc
        for case_name, py_filename, nb_filename, _apogee_note in case_readme_rows:
            case_result = case_results.get(case_name)
            flight = getattr(case_result, "flight", None)
            if flight is None:
                continue  # no ground truth for this case - nothing to verify against, not a failure
            verified_any = True
            all_mismatches += export_verification.verify_case_files(python_exe, case_name, py_filename, nb_filename, staging_dir, flight)
        if mc_readme_row:
            mc_py_filename, mc_nb_filename, n_sims = mc_readme_row
            verified_any = True
            all_mismatches += export_verification.verify_mc_files(python_exe, mc_py_filename, mc_nb_filename, staging_dir, n_sims)
        if all_mismatches:
            shutil.rmtree(staging_dir)
            details = "\n".join(f"  - {m}" for m in all_mismatches)
            raise ValueError(
                f"Cannot build the LASC submission zip: {len(all_mismatches)} exported file(s) did not match the app's "
                f"own simulation when run standalone in a clean environment:\n{details}\n"
                "Fix the underlying mismatch before submitting - a real divergence here means the exported script does "
                "not actually describe the flight the app reported."
            )

    readme = []
    readme.append(f"# LASC submission package - Mission {mission_id}")
    readme.append("")
    readme.append(f"Every `.py`/`.ipynb` file here is self-contained: `pip install rocketpy=={rp_version}` is the only")
    readme.append("dependency, and no file from this app's own repository is imported. Each script's own INPUTS block")
    readme.append("(near the top) lists every mass/CG/inertia/rail/wind/site value with its units and source - edit")
    readme.append("those in place if the Launch Readiness Review (CRS 10.2.1) measures a different value on site.")
    readme.append("")
    readme.append("## Setup")
    readme.append("")
    readme.append("```")
    readme.append(f"pip install rocketpy=={rp_version}")
    readme.append("python Mission<ID>_<Case>_RocketPy_v<N>.py")
    readme.append("```")
    readme.append("")
    readme.append("or open the matching `.ipynb` in Jupyter and run every cell top to bottom. Either way, plots and a")
    readme.append("`results.json`/`results_montecarlo.json` are written to a `results_<filename>/` folder next to it -")
    readme.append("nothing opens a window, so this also runs unattended on a machine with no display.")
    readme.append("")
    readme.append("## Contents")
    readme.append("")
    readme.append("| File | What it is | Expected result |")
    readme.append("|---|---|---|")
    for case_name, py_filename, nb_filename, apogee_note in case_readme_rows:
        readme.append(f"| `{py_filename}` / `{nb_filename}` | {case_name} case (CRS 10.1.6/10.1.10-13) | Apogee {apogee_note} |")
    if mc_readme_row:
        mc_py_filename, mc_nb_filename, n_sims = mc_readme_row
        readme.append(f"| `{mc_py_filename}` / `{mc_nb_filename}` | Monte Carlo dispersion analysis, {n_sims} samples (CLAUDE.md Phase 4) | Apogee mean + 90% CI, landing ellipse (PNG + KML) |")
    readme.append(f"| `{eng_filename}` | The SRAD motor thrust curve (CRS 10.1.9) |  |")
    readme.append(f"| `{ork_filename}` | The OpenRocket design file this was built from |  |")
    readme.append("| `power_off_drag.csv` / `power_on_drag.csv` | The Cd-vs-Mach curves used (CLAUDE.md Sec 4.2) |  |")
    if report_filename:
        readme.append(f"| `{report_filename}` | The full written report: validation, every case, Monte Carlo, compliance |  |")
    readme.append("")
    readme.append(_validation_status_line())
    readme.append("")
    with open(os.path.join(staging_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(readme) + "\n")

    if os.path.exists(output_zip_path):
        os.remove(output_zip_path)
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(staging_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                zf.write(fpath, arcname=os.path.relpath(fpath, staging_dir))

    shutil.rmtree(staging_dir)
    return output_zip_path
