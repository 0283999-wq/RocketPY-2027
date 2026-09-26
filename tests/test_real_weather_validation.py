"""2026-09-26 review item I: re-run V1/V2 with real (Open-Meteo
historical) weather instead of the OpenRocket-recorded conditions.
Mocked HTTP, per CLAUDE.md's own instruction - this sandbox can't reach
Open-Meteo, real downloads only happen on Diego's machine.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import validation

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "outputs", "test_real_weather_validation_cache")

FAKE_RESPONSE = {
    "hourly": {
        "time": ["2026-07-04T06:00", "2026-07-04T12:00", "2026-07-04T18:00"],
        "wind_speed_10m": [2.8, 4.0, 2.5],  # m/s (wind_speed_unit=ms is always requested now)
        "wind_direction_10m": [80, 85, 95],
        "temperature_2m": [12.0, 22.0, 17.0],
        "pressure_msl": [1015.0, 1013.0, 1014.0],
    }
}


def _clean_cache():
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            os.remove(os.path.join(CACHE_DIR, f))


def test_compute_v1_with_real_weather_uses_historical_endpoint_and_is_sane():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_RESPONSE) as mock_get:
        result = validation.compute_v1_with_real_weather(CACHE_DIR)

    assert mock_get.call_args[0][0] == "https://archive-api.open-meteo.com/v1/archive"
    assert "REAL WEATHER" in result.name
    assert 800 < result.predicted_agl_m < 1600
    assert "4.0" in result.notes or "Open-Meteo" in result.notes


def test_compute_v2_with_real_weather_requires_a_date():
    """The exact LASC 2026 flight date is not yet recorded in this
    project (see PROGRESS.md) - this must refuse rather than guess one."""
    try:
        validation.compute_v2_with_real_weather(None, CACHE_DIR)
        assert False, "expected V2FlightDateUnknownError"
    except validation.V2FlightDateUnknownError as exc:
        assert "date" in str(exc)


def test_compute_v2_with_real_weather_given_a_date_is_sane():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_RESPONSE):
        result = validation.compute_v2_with_real_weather("2026-07-04", CACHE_DIR)
    assert "REAL WEATHER" in result.name
    assert 800 < result.predicted_agl_m < 1600


if __name__ == "__main__":
    test_compute_v1_with_real_weather_uses_historical_endpoint_and_is_sane()
    test_compute_v2_with_real_weather_requires_a_date()
    test_compute_v2_with_real_weather_given_a_date_is_sane()
    print("\nREAL WEATHER VALIDATION: OK")
