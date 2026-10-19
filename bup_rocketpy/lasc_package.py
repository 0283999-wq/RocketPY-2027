"""The LASC .zip package (CLAUDE.md Sec 6 Phase 5): the per-case .py
files named per CRS 10.1.6, plus the .eng, .ork and Cd curves.
"""
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


def build_lasc_zip(output_zip_path, mission_id, parsed, parsed_eng, eng_path, ork_path, power_off_drag_path, power_on_drag_path, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, cases, version=1, eng_filename=None, ork_filename=None, mission_id_template=None, launch_override=None, motor_dry_override_kg=None):
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
    .ork/.eng values instead of what the app itself actually simulated."""
    from bup_rocketpy import case_export

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

    for case_name, include_recovery in cases:
        recovery_chute, recovery_force_apogee = None, False
        if case_name == "DrogueOnly":
            recovery_chute = drogue
        elif case_name == "MainAtApogee":
            recovery_chute = main or drogue
            recovery_force_apogee = True
        if case_name in ("DrogueOnly", "MainAtApogee") and recovery_chute is None:
            continue  # no parachute with a resolvable Cd - same "can't build this case" condition rcsm_cases.run_case itself checks; skip rather than emit a broken script
        filename, source = case_export.generate_case_script(
            mission_id=mission_id, case_name=case_name, version=version,
            parsed=parsed, parsed_eng=parsed_eng,
            eng_filename=eng_filename,
            power_off_drag_filename="power_off_drag.csv", power_on_drag_filename="power_on_drag.csv",
            dry_mass_kg=dry_mass_kg, dry_cg_m=dry_cg_m,
            i_axial=i_axial, i_transverse=i_transverse, radius_m=radius_m,
            include_recovery=include_recovery,
            mission_id_template=mission_id_template,
            launch_override=launch_override, motor_dry_override_kg=motor_dry_override_kg,
            recovery_chute=recovery_chute, recovery_force_apogee=recovery_force_apogee,
        )
        with open(os.path.join(staging_dir, filename), "w", encoding="utf-8") as f:
            f.write(source)

    readme = f"""LASC submission package - Mission {mission_id}

Contents:
- Mission{mission_id}_*_RocketPy_v{version}.py - self-contained simulation
  scripts (CRS 10.1.6 naming). Each runs standalone with `pip install
  rocketpy` - no other files from this repo are needed, only the sibling
  files in this same folder (.eng, drag CSVs).
- {eng_filename} - the SRAD motor thrust curve (CRS 10.1.9).
- {ork_filename} - the OpenRocket design file this was built from.
- power_off_drag.csv / power_on_drag.csv - the Cd-vs-Mach curves used.

{_validation_status_line()}
"""
    with open(os.path.join(staging_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme)

    if os.path.exists(output_zip_path):
        os.remove(output_zip_path)
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(staging_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                zf.write(fpath, arcname=os.path.relpath(fpath, staging_dir))

    shutil.rmtree(staging_dir)
    return output_zip_path
