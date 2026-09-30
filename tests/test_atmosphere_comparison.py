"""2026-09-30 review item 7: "Show the launch conditions the app used
(elevation, temperature, pressure, wind) next to the ones stored in the
.ork's simulation, with a warning when they differ, and by default use
the .ork's own conditions when comparing against OpenRocket." A real
case found max speed matching OpenRocket (321.5 vs 322 m/s) but max Mach
not (0.984 vs 0.960) - traced to a temperature/speed-of-sound gap this
test locks in the visibility of.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import openrocket_comparison
from bup_rocketpy.gui import pipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "rockets", "power_on_drag.csv")
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "test_atmosphere_comparison")


def _rows():
    lr = pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR)
    sim = pipeline.run_simulation(lr, OUT_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279)
    _, rows = openrocket_comparison.compare_to_openrocket(lr.parsed_ork, sim, lr.ork_path)
    return {r.label: r for r in rows}


def _row(rows, label):
    return rows[label]


def test_elevation_matches_exactly_by_default():
    """This app must use the .ork's own elevation by default - not a
    separately-configured value that could silently drift from it."""
    row = _row(_rows(), "Elevation (site)")
    assert row.ours == row.openrocket


def test_temperature_pressure_wind_rows_present_with_real_numbers():
    rows = _rows()
    temp = _row(rows, "Temperature (t=0)")
    assert temp.ours > 250 and temp.openrocket > 250, "must be Kelvin, not Celsius (avoids a near-zero-crossing %% diff bug)"
    assert abs(temp.pct_diff) < 5, "PROMETEO's own stored sim should be close to standard atmosphere at this elevation"

    pressure = _row(rows, "Pressure (t=0)")
    assert 800 < pressure.ours < 1100 and 800 < pressure.openrocket < 1100, "must be hPa"

    wind = _row(rows, "Wind speed (t=0)")
    assert wind.ours >= 0 and wind.openrocket >= 0


def test_atmosphere_rows_appear_before_vehicle_rows():
    """So a reader sees the conditions before the numbers those
    conditions affect."""
    _, rows = openrocket_comparison.compare_to_openrocket(
        pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR).parsed_ork,
        pipeline.run_simulation(pipeline.load_files(ORK_PATH, ENG_PATH, POWER_OFF_DRAG, POWER_ON_DRAG, outputs_dir=OUT_DIR), OUT_DIR, dry_mass_override_kg=5.6622, dry_cg_override_m=0.6279),
        ORK_PATH,
    )
    labels = [r.label for r in rows]
    assert labels[:4] == ["Elevation (site)", "Temperature (t=0)", "Pressure (t=0)", "Wind speed (t=0)"]
    assert "Overall length" in labels[4:]


if __name__ == "__main__":
    test_elevation_matches_exactly_by_default()
    test_temperature_pressure_wind_rows_present_with_real_numbers()
    test_atmosphere_rows_appear_before_vehicle_rows()
    print("\nATMOSPHERE COMPARISON: OK")
