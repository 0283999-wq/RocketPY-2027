"""2026-10-09 review item 12 (top priority): "I am choosing between two
fin designs... compare_all_simulationsA.csv and compare_all_simulationsB.csv
are IDENTICAL number by number... the app is not using the newly loaded
rocket and/or its Cd curve. The report of B was also titled 'Major Tom A'."

Root cause investigation (see this review's own diagnostic scripts): the
computation layer itself (pipeline.load_files()/run_simulation()/
compare_all_simulations()/rcsm_cases.run_all_cases()/report.
build_report_data()) was ALREADY correct when called twice in the same
process with two different real .ork paths - no lru_cache, no module-
level mutable default, nothing keyed by name was found anywhere in this
codebase. This test proves that directly: two .ork files differing ONLY
in the fin set (same technique as test_duplicate_parachute_trigger.py's
"no invented rocket" convention - PROMETEO's real, checked-in .ork,
text-surgery on one XML tag) must give DIFFERENT CP/static margin/apogee
through every path the app exposes, and every output must carry the
per-file identity (name, hash, fin summary) this review also added
(LoadResult.display_name/ork_hash/fin_summary, translate.fin_summary_text,
translate.check_drag_curve_freshness) - so a future recurrence of "same
rocket for different files" is immediately visible on the output itself,
whatever its trigger (this review could not reproduce a browser-upload-
level cache bug directly - see MORNING_REPORT.md).

Major Tom's own files are NEVER committed (CLAUDE.md, work in progress,
loaded locally) - this uses PROMETEO's real, already-checked-in .ork.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import rcsm_cases, report, translate
from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_A = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_rocket_identity_per_file")


def _make_fin_b_ork():
    """A second .ork, identical to PROMETEO's real one except the fin
    set's sweep length AND root chord - a real "two fin designs" A/B
    comparison, not an invented rocket. Also gives it its own <name> so
    this test covers item 4 (rocket naming) at the same time as item 12
    (per-file identity) - the two bugs were reported together and share
    the same root fix (LoadResult now carries both)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(ORK_A, encoding="utf-8") as f:
        data = f.read()
    modified = (
        data
        .replace("<sweeplength>0.17000000000000007</sweeplength>", "<sweeplength>0.35</sweeplength>")
        .replace("<rootchord>0.2</rootchord>", "<rootchord>0.24</rootchord>")
        .replace("<name>PrometeoLasc2026</name>", "<name>PrometeoLasc2026 Fin B</name>", 1)
    )
    assert modified != data, "text-surgery did not actually change anything - fixture is broken"
    path = os.path.join(OUT_DIR, "PrometeoFinB.ork")
    with open(path, "w", encoding="utf-8") as f:
        f.write(modified)
    return path


ORK_B = None  # set by the first test that needs it (module-level fixture, built once)


def _ork_b():
    global ORK_B
    if ORK_B is None:
        ORK_B = _make_fin_b_ork()
    return ORK_B


def test_load_files_gives_different_identity_for_different_files():
    lr_a = pipeline.load_files(ORK_A, ENG_PATH, outputs_dir=OUT_DIR, ork_filename="PrometeoLasc2026.ork", eng_filename="Icarus_I_K519.eng")
    lr_b = pipeline.load_files(_ork_b(), ENG_PATH, outputs_dir=OUT_DIR, ork_filename="PrometeoFinB.ork", eng_filename="Icarus_I_K519.eng")

    assert lr_a.ork_hash != lr_b.ork_hash, "two different .ork files must never hash the same"
    assert lr_a.fin_summary != lr_b.fin_summary, f"fin summary must reflect the file just parsed: A={lr_a.fin_summary!r} B={lr_b.fin_summary!r}"
    assert lr_a.display_name != lr_b.display_name, f"display_name must reflect the file just parsed: A={lr_a.display_name!r} B={lr_b.display_name!r}"
    assert lr_a.display_name == "PrometeoLasc2026"
    assert lr_b.display_name == "PrometeoLasc2026 Fin B"


def test_single_simulation_gives_different_physics_for_different_fins():
    lr_a = pipeline.load_files(ORK_A, ENG_PATH, outputs_dir=OUT_DIR)
    lr_b = pipeline.load_files(_ork_b(), ENG_PATH, outputs_dir=OUT_DIR)
    sim_a = pipeline.run_simulation(lr_a, OUT_DIR)
    sim_b = pipeline.run_simulation(lr_b, OUT_DIR)

    assert sim_a.apogee_agl_m != sim_b.apogee_agl_m, "different fin geometry must fly a measurably different trajectory"
    assert sim_a.min_static_margin_cal != sim_b.min_static_margin_cal, "different fin geometry must change the static margin"
    # Loading A again, in the SAME process, after B - must give BACK A's
    # own numbers, not B's (the literal "simulates the same rocket for
    # different files" failure mode: the SECOND load silently sticking).
    lr_a_again = pipeline.load_files(ORK_A, ENG_PATH, outputs_dir=OUT_DIR)
    sim_a_again = pipeline.run_simulation(lr_a_again, OUT_DIR)
    assert sim_a_again.apogee_agl_m == sim_a.apogee_agl_m
    assert sim_a_again.min_static_margin_cal == sim_a.min_static_margin_cal


def test_compare_all_simulations_gives_different_results_and_carries_file_identity():
    rows_a = pipeline.compare_all_simulations(ORK_A, ENG_PATH, outputs_dir=OUT_DIR)
    rows_b = pipeline.compare_all_simulations(_ork_b(), ENG_PATH, outputs_dir=OUT_DIR)

    assert len(rows_a) == len(rows_b) == 2  # PROMETEO's 2 real stored sims
    for ra, rb in zip(rows_a, rows_b):
        assert ra.success and rb.success, (ra.error, rb.error)
        assert ra.apogee_agl_m != rb.apogee_agl_m, f"'{ra.name}': compare-all gave the SAME apogee for two different fin files - this is the exact bug reported"
        assert ra.min_static_margin_cal != rb.min_static_margin_cal
        assert ra.ork_hash != rb.ork_hash
        assert ra.fin_summary != rb.fin_summary

    csv_a = os.path.join(OUT_DIR, "compare_all_A.csv")
    csv_b = os.path.join(OUT_DIR, "compare_all_B.csv")
    pipeline.export_comparison_csv(rows_a, csv_a)
    pipeline.export_comparison_csv(rows_b, csv_b)
    with open(csv_a, encoding="utf-8-sig") as f:
        text_a = f.read()
    with open(csv_b, encoding="utf-8-sig") as f:
        text_b = f.read()
    assert text_a != text_b, "compare_all_simulationsA.csv and ...B.csv came out byte-identical - the exact bug reported"


def test_rcsm_cases_give_different_stability_for_different_fins():
    lr_a = pipeline.load_files(ORK_A, ENG_PATH, outputs_dir=OUT_DIR)
    lr_b = pipeline.load_files(_ork_b(), ENG_PATH, outputs_dir=OUT_DIR)
    mass_a = translate.estimate_dry_mass_and_cg(lr_a.parsed_ork)
    mass_b = translate.estimate_dry_mass_and_cg(lr_b.parsed_ork)

    cases_a = rcsm_cases.run_all_cases(lr_a.parsed_ork, lr_a.parsed_eng, lr_a.eng_path, lr_a.power_off_drag_path, lr_a.power_on_drag_path, mass_a.mass_kg, mass_a.cg_m)
    cases_b = rcsm_cases.run_all_cases(lr_b.parsed_ork, lr_b.parsed_eng, lr_b.eng_path, lr_b.power_off_drag_path, lr_b.power_on_drag_path, mass_b.mass_kg, mass_b.cg_m)

    nominal_a, nominal_b = cases_a["Nominal"].flight, cases_b["Nominal"].flight
    assert nominal_a is not None and nominal_b is not None
    margin_a = nominal_a.stability_margin(nominal_a.out_of_rail_time)
    margin_b = nominal_b.stability_margin(nominal_b.out_of_rail_time)
    assert margin_a != margin_b, "RCSM cases gave the SAME static margin for two different fin files"


def test_report_data_never_mixes_up_two_loaded_files():
    """The literal 'report of Major Tom B was titled Major Tom A' report."""
    lr_a = pipeline.load_files(ORK_A, ENG_PATH, outputs_dir=OUT_DIR, ork_filename="PrometeoLasc2026.ork", eng_filename="Icarus_I_K519.eng")
    lr_b = pipeline.load_files(_ork_b(), ENG_PATH, outputs_dir=OUT_DIR, ork_filename="PrometeoFinB.ork", eng_filename="Icarus_I_K519.eng")
    sim_a = pipeline.run_simulation(lr_a, OUT_DIR)
    sim_b = pipeline.run_simulation(lr_b, OUT_DIR)
    cases_a = rcsm_cases.run_all_cases(lr_a.parsed_ork, lr_a.parsed_eng, lr_a.eng_path, lr_a.power_off_drag_path, lr_a.power_on_drag_path, sim_a.dry_mass_kg, sim_a.dry_cg_m)
    cases_b = rcsm_cases.run_all_cases(lr_b.parsed_ork, lr_b.parsed_eng, lr_b.eng_path, lr_b.power_off_drag_path, lr_b.power_on_drag_path, sim_b.dry_mass_kg, sim_b.dry_cg_m)

    data_a = report.build_report_data("0", "tester", lr_a, sim_a, cases_a, None, None, OUT_DIR)
    data_b = report.build_report_data("0", "tester", lr_b, sim_b, cases_b, None, None, OUT_DIR)

    assert data_a["vehicle_name"] == "PrometeoLasc2026"
    assert data_b["vehicle_name"] == "PrometeoLasc2026 Fin B"
    assert data_a["vehicle_name"] != data_b["vehicle_name"]
    assert data_a["kpis"] != data_b["kpis"]

    # general_info.model_files must carry EACH report's own file's hash/
    # fin summary, never the other one's.
    files_a = dict(data_a["general_info"]["model_files"])
    files_b = dict(data_b["general_info"]["model_files"])
    assert files_a["Fin geometry"] != files_b["Fin geometry"]
    assert lr_a.ork_hash in files_a["OpenRocket design file"]
    assert lr_b.ork_hash in files_b["OpenRocket design file"]
    assert lr_a.ork_hash not in files_b["OpenRocket design file"]


if __name__ == "__main__":
    test_load_files_gives_different_identity_for_different_files()
    test_single_simulation_gives_different_physics_for_different_fins()
    test_compare_all_simulations_gives_different_results_and_carries_file_identity()
    test_rcsm_cases_give_different_stability_for_different_fins()
    test_report_data_never_mixes_up_two_loaded_files()
    print("\nROCKET IDENTITY PER FILE: OK")
