"""2026-10-09 review item 13 (top priority addendum): "'COMPARE DESIGNS'
PAGE (this is what I actually need right now)." Load design A and B,
run both with the same sites/seeds, side-by-side table + Cd overlay +
apogee diff with verdict + per-design OpenRocket-format CSV export.

Uses PROMETEO's real, checked-in .ork + text-surgery for a second fin
design (same convention as test_rocket_identity_per_file.py - no
invented rocket, Major Tom's own files are never committed).
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import compare_designs

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_A = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_compare_designs")

ORK_B = None


def _make_fin_b_ork():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(ORK_A, encoding="utf-8") as f:
        data = f.read()
    modified = (
        data
        .replace("<sweeplength>0.17000000000000007</sweeplength>", "<sweeplength>0.35</sweeplength>")
        .replace("<rootchord>0.2</rootchord>", "<rootchord>0.24</rootchord>")
        .replace("<name>PrometeoLasc2026</name>", "<name>PrometeoLasc2026 Fin B</name>", 1)
    )
    assert modified != data
    path = os.path.join(OUT_DIR, "PrometeoFinB.ork")
    with open(path, "w", encoding="utf-8") as f:
        f.write(modified)
    return path


def _ork_b():
    global ORK_B
    if ORK_B is None:
        ORK_B = _make_fin_b_ork()
    return ORK_B


def test_nominal_comparison_gives_different_numbers_for_different_fins():
    os.makedirs(OUT_DIR, exist_ok=True)
    result = compare_designs.compare_designs(
        ORK_A, ENG_PATH, _ork_b(), ENG_PATH, outputs_dir=OUT_DIR,
        ork_filename_a="PrometeoLasc2026.ork", ork_filename_b="PrometeoFinB.ork", eng_filename_a="Icarus_I_K519.eng",
    )
    a, b = result.design_a, result.design_b
    assert a.display_name == "PrometeoLasc2026"
    assert b.display_name == "PrometeoLasc2026 Fin B"
    assert a.apogee_agl_m != b.apogee_agl_m
    assert a.static_margin_t0_cal != b.static_margin_t0_cal
    assert a.fin_summary != b.fin_summary
    assert result.apogee_diff_b_minus_a_m == b.apogee_agl_m - a.apogee_agl_m
    assert "Nominal-only" in result.verdict  # no Monte Carlo run (mc_n=0 default)
    # Everything a real structural/compliance review needs is present, not just apogee.
    assert a.flutter_velocity_ms is not None
    assert a.fin_mass_kg is not None
    assert a.stability_mach03_cal is not None


def test_monte_carlo_common_seed_gives_a_paired_difference_with_a_verdict():
    os.makedirs(OUT_DIR, exist_ok=True)
    result = compare_designs.compare_designs(
        ORK_A, ENG_PATH, _ork_b(), ENG_PATH, outputs_dir=OUT_DIR, mc_n=3,
    )
    assert result.mc_n_paired == 3
    assert result.apogee_mc_diff_mean_m is not None
    assert result.apogee_mc_diff_ci90 is not None
    assert result.design_a.apogee_mc_mean_m is not None
    assert result.design_b.apogee_mc_mean_m is not None
    assert result.verdict  # non-empty - a real sentence either way


def test_same_seed_same_file_twice_gives_identical_mc_samples():
    """Common-random-numbers proof: comparing a design against ITSELF
    with the same seed must give a paired difference of exactly zero -
    if it didn't, the seeding wouldn't actually be common between the
    two runs (the whole point of this feature)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    result = compare_designs.compare_designs(
        ORK_A, ENG_PATH, ORK_A, ENG_PATH, outputs_dir=OUT_DIR, mc_n=3, mc_seed=999,
    )
    assert result.apogee_mc_diff_mean_m == 0.0 or abs(result.apogee_mc_diff_mean_m) < 1e-6


def test_export_zip_has_one_csv_per_design_with_distinct_names():
    os.makedirs(OUT_DIR, exist_ok=True)
    result = compare_designs.compare_designs(
        ORK_A, ENG_PATH, _ork_b(), ENG_PATH, outputs_dir=OUT_DIR,
        ork_filename_a="PrometeoLasc2026.ork", ork_filename_b="PrometeoFinB.ork", eng_filename_a="Icarus_I_K519.eng",
    )
    zip_path = os.path.join(OUT_DIR, "compare_designs.zip")
    compare_designs.export_comparison_zip(result, zip_path)
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert len(names) == 2
    assert names[0] != names[1]
    assert any("PrometeoLasc2026" in n and "Fin B" not in n for n in names)
    assert any("Fin B" in n for n in names)


if __name__ == "__main__":
    test_nominal_comparison_gives_different_numbers_for_different_fins()
    test_monte_carlo_common_seed_gives_a_paired_difference_with_a_verdict()
    test_same_seed_same_file_twice_gives_identical_mc_samples()
    test_export_zip_has_one_csv_per_design_with_distinct_names()
    print("\nCOMPARE DESIGNS: OK")
