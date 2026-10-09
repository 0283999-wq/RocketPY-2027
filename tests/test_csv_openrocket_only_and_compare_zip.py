"""2026-10-09 review item 10: "CSV export = OpenRocket format only" -
the app used to offer TWO CSV downloads per simulation (rocketpy's own
generic FlightDataExporter layout, and a separate OpenRocket-style one),
which is exactly the "which CSV do I even open" confusion the review
reported. Fixed in bup_rocketpy/gui/pipeline.py: there is now exactly
ONE CSV per simulation (sim_result.csv_path IS sim_result.
openrocket_csv_path, same file, no second copy), and compare_all_
simulations() now also keeps a STABLE per-site copy of that CSV (instead
of letting the next site's run silently overwrite the previous one's,
since run_simulation always writes to the same fixed filename inside
outputs_dir) so a zip of every site's own flight data can be built.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs", "test_csv_openrocket_only")


def test_run_simulation_has_exactly_one_csv_and_it_is_openrocket_format():
    load_result = pipeline.load_files(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    sim = pipeline.run_simulation(load_result, OUTPUTS_DIR)

    assert sim.csv_path is not None
    assert sim.openrocket_csv_path is not None
    assert sim.csv_path == sim.openrocket_csv_path, "csv_path must BE the OpenRocket-format file, not a separate second copy"
    assert os.path.exists(sim.csv_path)

    with open(sim.csv_path, encoding="utf-8-sig") as f:
        header = f.readline()
    # OpenRocket's own export header always starts with a comment line
    # naming the simulation - build_openrocket_style_rows' own convention
    # (verified by reading openrocket_csv_export.py, not guessed).
    assert header.startswith("#"), f"expected an OpenRocket-style '#'-commented header line, got: {header!r}"

    # No leftover second CSV file anywhere in outputs_dir from the old
    # FlightDataExporter path (it used to write "flight_data.csv").
    old_style_path = os.path.join(OUTPUTS_DIR, "flight_data.csv")
    assert not os.path.exists(old_style_path), "the old rocketpy-native FlightDataExporter CSV should no longer be generated at all"


def test_compare_all_simulations_keeps_distinct_per_site_csv_files():
    rows = pipeline.compare_all_simulations(ORK_PATH, ENG_PATH, outputs_dir=OUTPUTS_DIR)
    assert len(rows) >= 2, "PROMETEO's real .ork has 2 stored simulations - this test needs at least that many to prove sites don't overwrite each other"

    successful = [r for r in rows if r.success]
    assert len(successful) == len(rows), f"expected every site to simulate successfully: {[r.error for r in rows if not r.success]}"

    csv_paths = [r.csv_path for r in successful]
    assert all(p is not None and os.path.exists(p) for p in csv_paths), "every successful site should have its own saved CSV"
    assert len(set(csv_paths)) == len(csv_paths), "each site must get its OWN csv_path, not all pointing at the same (overwritten) file"

    # Each file must have real, non-trivial content, and the actual
    # per-site apogee values parsed back out must differ between sites -
    # proof the copy happened before the next site's run overwrote the
    # shared fixed-name file run_simulation always writes to (if it
    # hadn't, every "distinct" file would be an identical copy of the
    # LAST site simulated, silently passing the path-uniqueness check
    # above while still being wrong data).
    apogees_from_csv = []
    for row in successful:
        with open(row.csv_path, encoding="utf-8-sig") as f:
            lines = f.readlines()
        assert len(lines) > 10, f"{row.csv_path} should have real flight data rows, got {len(lines)} lines"
        data_lines = [ln for ln in lines if ln and not ln.startswith("#")]
        altitudes = [float(ln.split(",")[1]) for ln in data_lines[1:] if ln.split(",")[1]]
        apogees_from_csv.append(max(altitudes))
    assert len(set(round(a, 1) for a in apogees_from_csv)) == len(apogees_from_csv), f"each site's own CSV should show a DIFFERENT apogee (different site conditions) - got {apogees_from_csv}, suggesting one file overwrote another"

    zip_path = os.path.join(OUTPUTS_DIR, "compare_all_test.zip")
    pipeline.export_comparison_zip(rows, zip_path)
    assert os.path.exists(zip_path)

    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        names_in_zip = zf.namelist()
    assert len(names_in_zip) == len(successful), f"zip should have exactly one entry per successful site, got {names_in_zip}"
