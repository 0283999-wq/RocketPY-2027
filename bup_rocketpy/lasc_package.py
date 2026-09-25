"""The LASC .zip package (CLAUDE.md Sec 6 Phase 5): the per-case .py
files named per CRS 10.1.6, plus the .eng, .ork and Cd curves.
"""
import os
import shutil
import zipfile


def build_lasc_zip(output_zip_path, mission_id, parsed, parsed_eng, eng_path, ork_path, power_off_drag_path, power_on_drag_path, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, cases, version=1):
    """cases: list of (case_name, include_recovery) tuples to export -
    typically [("Ballistic", False), ("Nominal", True)] at minimum
    (CRS 10.1.14: the RocketPy award requires nominal and ballistic)."""
    from bup_rocketpy import case_export

    base_path = output_zip_path[:-4] if output_zip_path.endswith(".zip") else output_zip_path
    staging_dir = base_path + "_staging"
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir)

    shutil.copy(eng_path, os.path.join(staging_dir, os.path.basename(eng_path)))
    shutil.copy(ork_path, os.path.join(staging_dir, os.path.basename(ork_path)))
    shutil.copy(power_off_drag_path, os.path.join(staging_dir, "power_off_drag.csv"))
    shutil.copy(power_on_drag_path, os.path.join(staging_dir, "power_on_drag.csv"))

    for case_name, include_recovery in cases:
        filename, source = case_export.generate_case_script(
            mission_id=mission_id, case_name=case_name, version=version,
            parsed=parsed, parsed_eng=parsed_eng,
            eng_filename=os.path.basename(eng_path),
            power_off_drag_filename="power_off_drag.csv", power_on_drag_filename="power_on_drag.csv",
            dry_mass_kg=dry_mass_kg, dry_cg_m=dry_cg_m,
            i_axial=i_axial, i_transverse=i_transverse, radius_m=radius_m,
            include_recovery=include_recovery,
        )
        with open(os.path.join(staging_dir, filename), "w") as f:
            f.write(source)

    readme = f"""LASC submission package - Mission {mission_id}

Contents:
- Mission{mission_id}_*_RocketPy_v{version}.py - self-contained simulation
  scripts (CRS 10.1.6 naming). Each runs standalone with `pip install
  rocketpy` - no other files from this repo are needed, only the sibling
  files in this same folder (.eng, drag CSVs).
- {os.path.basename(eng_path)} - the SRAD motor thrust curve (CRS 10.1.9).
- {os.path.basename(ork_path)} - the OpenRocket design file this was built from.
- power_off_drag.csv / power_on_drag.csv - the Cd-vs-Mach curves used.

PROVISIONAL: see this project's PROGRESS.md for validation status before
treating any number here as final.
"""
    with open(os.path.join(staging_dir, "README.txt"), "w") as f:
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
