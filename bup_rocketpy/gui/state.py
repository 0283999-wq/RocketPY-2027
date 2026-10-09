"""Shared in-memory state across pages (2026-09-26 review, item 2). This
is a single-operator desktop-style tool (Diego running it locally), so a
module-level dict is a reasonable, simple choice - not a multi-user
production concern here.
"""
state = {
    "ork_path": None, "eng_path": None, "drag_off_path": None, "drag_on_path": None,
    "ork_filename": None, "eng_filename": None,  # 2026-09-26 review item E: the user's REAL uploaded filenames, not the tempfile path's own basename
    "load_result": None, "sim_result": None,
    "available_simulation_names": [], "selected_simulation_name": None,  # 2026-10-05 review: a .ork can hold several stored simulations (one per site/mission, e.g. Pachuca/LASC/IREC) - which one supplies launch conditions/drag curve/mass-CG reference. None means "the first one in the file" (unchanged default).
    "dry_mass_override": None, "dry_cg_override": None,  # raw manual-override UI fields (None unless the user checked "use manual override")
    "motor_mass_override": None,  # 2026-09-30 review item 2: "Measured motor mass" (dry+propellant, kg) - None unless the user checked its own override checkbox
    "dry_mass_kg": None, "dry_cg_m": None, "mass_source": "",  # the mass/CG ACTUALLY used by the last successful Simulate (override or geometric estimate) - every other page reads THESE, never the override fields above, so they work on the default no-override path too (2026-09-26 review crash d)
    "dry_i_axial_kgm2": None, "dry_i_transverse_kgm2": None, "inertia_source": "",  # 2026-09-27 review item 1: same rule as above, for inertia - Monte Carlo/RCSM cases/exports must read THESE, not re-derive their own, or they can silently disagree with Simulate's own result for the identical rocket
    "case_results": None,  # dict from rcsm_cases.run_all_cases
    "compliance_rows": None,
    "mc_result": None, "mc_uncertainties": None,
    # 2026-10-09 review item 7: "global progress chip" - Monte Carlo runs
    # in a background thread already (see montecarlo_page.py's run_mc),
    # so the operator can navigate to another page while it runs; these
    # let layout.py's header show a live "Monte Carlo: i/total" chip on
    # EVERY page, not just the one that started the run.
    "mc_running": False, "mc_progress_text": "", "mc_progress_fraction": 0.0,
    "weathercocking_result": None,
    "vehicle_name": "Vehicle", "mission_id": "",  # 2026-10-09 review item 5: "Mission ID default empty, not 0" - "0" read as a real (wrong) assigned ID, not "unset"
    "competition_profile": "lasc",  # 2026-09-26 review item H.2 - "lasc" preserves every existing default-path behavior/test
    "weather_profile": None, "launch_override": None,  # 2026-09-26 review item H - cached real-weather + the LaunchConditions override built from it
    "report_text": {},  # 2026-09-27 review item 6: editable report blocks (introduction/objectives/discussion/conclusions/team) - empty values fall back to report.py's auto-generated defaults, never blank
    "current_run_id": None,  # the History run_id THIS session's last Simulate saved to, or reopened from - lets the Exports page patch report_text/author into that same run instead of minting a new one
    # 2026-10-09 review item 8: RKT 1.1.2 used to hardcode payload_mass_kg=1.0
    # regardless of the loaded rocket - these let the operator pick which
    # point-mass components ARE the payload (checkboxes on the RCSM Cases
    # page) or type the payload mass directly; reset to empty on every new
    # .ork load (do_load()) since a different rocket has different
    # components/payload, matching every other per-rocket field above.
    "payload_component_names": [],  # names of parsed.point_masses the operator has checked as "this is payload"
    "payload_mass_override_kg": None,  # typed directly - takes priority over the checkbox total when set
    # STR 6.3.2 flutter - a default shear modulus (editable, source shown)
    # feeds translate.check_drag... no, flutter.hand_calc_flutter_velocity;
    # a manual external-tool result (ANSYS/AEROLAB/etc, with its own source
    # label) always takes priority over the hand formula when given.
    "flutter_shear_modulus_pa": None, "flutter_shear_modulus_source": None,
    "flutter_manual_override_ms": None, "flutter_manual_override_source": None,
}
