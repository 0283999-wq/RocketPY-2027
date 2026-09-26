"""2026-09-27 review item 7 (Mission Control redesign): the decimated
playback dataset the 3D viewer (static/playback.js) animates. Pure data
tests - no browser/NiceGUI involved, that's covered by the Playwright
e2e test instead.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import translate
from bup_rocketpy.gui import flight_playback
from bup_rocketpy.motor_reader import read_eng
from bup_rocketpy.ork_reader import read_ork

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = os.path.join(REPO_ROOT, "reference", "prometeo_mission44")
ORK_PATH = os.path.join(REF_ROOT, "data", "ork", "PrometeoLasc2026.ork")
ENG_PATH = os.path.join(REF_ROOT, "data", "motors", "Icarus_I_K519.eng")
POWER_OFF_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_off_drag.csv")
POWER_ON_DRAG = os.path.join(REF_ROOT, "data", "rockets", "power_on_drag.csv")


def _flight_and_motor():
    parsed = read_ork(ORK_PATH)
    parsed_eng = read_eng(ENG_PATH)
    motor = translate.build_motor(parsed_eng, ENG_PATH)
    flight, _ = translate.ork_to_flight(parsed, parsed_eng, ENG_PATH, power_off_drag=POWER_OFF_DRAG, power_on_drag=POWER_ON_DRAG)
    return flight, motor


def test_build_playback_data_has_the_expected_frame_count_and_fields():
    flight, motor = _flight_and_motor()
    data = flight_playback.build_playback_data(flight, motor, n_frames=120)
    assert len(data["frames"]) == 120
    for key in ("t", "x", "y", "z", "speed", "mach", "accel"):
        assert key in data["frames"][0]
    assert data["frames"][0]["t"] == 0.0 or abs(data["frames"][0]["t"]) < 1e-9
    assert data["frames"][-1]["t"] == flight.t_final


def test_build_playback_data_events_include_rail_exit_burnout_apogee_and_landing():
    flight, motor = _flight_and_motor()
    data = flight_playback.build_playback_data(flight, motor)
    names = [e["name"] for e in data["events"]]
    assert "Rail exit" in names
    assert "Burnout" in names
    assert "Apogee" in names
    assert "Landing" in names
    # events must be in ascending time order (the viewer's "last event" readout relies on this)
    times = [e["t"] for e in data["events"]]
    assert times == sorted(times)


def test_build_playback_data_altitude_is_agl_matching_apogee_kpi():
    flight, motor = _flight_and_motor()
    data = flight_playback.build_playback_data(flight, motor, n_frames=500)
    max_z = max(f["z"] for f in data["frames"])
    expected_apogee_agl = flight.apogee - flight.env.elevation
    assert abs(max_z - expected_apogee_agl) / expected_apogee_agl < 0.02, "decimated max altitude should be close to the real apogee AGL"


def test_build_playback_data_bounds_cover_every_frame():
    flight, motor = _flight_and_motor()
    data = flight_playback.build_playback_data(flight, motor, n_frames=80)
    b = data["bounds"]
    for f in data["frames"]:
        assert b["x_min"] <= f["x"] <= b["x_max"]
        assert b["y_min"] <= f["y"] <= b["y_max"]
        assert b["z_min"] <= f["z"] <= b["z_max"]


if __name__ == "__main__":
    test_build_playback_data_has_the_expected_frame_count_and_fields()
    test_build_playback_data_events_include_rail_exit_burnout_apogee_and_landing()
    test_build_playback_data_altitude_is_agl_matching_apogee_kpi()
    test_build_playback_data_bounds_cover_every_frame()
    print("\nFLIGHT PLAYBACK DATA: OK")
