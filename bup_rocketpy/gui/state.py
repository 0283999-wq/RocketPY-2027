"""Shared in-memory state across pages (2026-09-26 review, item 2). This
is a single-operator desktop-style tool (Diego running it locally), so a
module-level dict is a reasonable, simple choice - not a multi-user
production concern here.
"""
state = {
    "ork_path": None, "eng_path": None, "drag_off_path": None, "drag_on_path": None,
    "ork_filename": None, "eng_filename": None,  # 2026-09-26 review item E: the user's REAL uploaded filenames, not the tempfile path's own basename
    "load_result": None, "sim_result": None,
    "dry_mass_override": None, "dry_cg_override": None,  # raw manual-override UI fields (None unless the user checked "use manual override")
    "dry_mass_kg": None, "dry_cg_m": None, "mass_source": "",  # the mass/CG ACTUALLY used by the last successful Simulate (override or geometric estimate) - every other page reads THESE, never the override fields above, so they work on the default no-override path too (2026-09-26 review crash d)
    "case_results": None,  # dict from rcsm_cases.run_all_cases
    "compliance_rows": None,
    "mc_result": None, "mc_uncertainties": None,
    "weathercocking_result": None,
    "vehicle_name": "Vehicle", "mission_id": "0",
}
