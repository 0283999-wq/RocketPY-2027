"""2026-09-26 review items H/I: Open-Meteo forecast + historical weather,
cached locally. This cloud sandbox can't reach api.open-meteo.com, so
every test mocks bup_rocketpy.weather._http_get_json directly (per
CLAUDE.md Phase 2's own instruction to test with mocked data) - real
network calls only ever happen on Diego's machine.
"""
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import weather

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "outputs", "test_weather_cache")

FAKE_OPEN_METEO_RESPONSE = {
    "hourly": {
        "time": ["2026-10-04T00:00", "2026-10-04T06:00", "2026-10-04T12:00", "2026-10-04T18:00"],
        "wind_speed_10m": [7.2, 10.8, 18.0, 12.6],  # km/h
        "wind_direction_10m": [90, 100, 95, 105],
        "temperature_2m": [18.0, 16.5, 24.0, 20.0],
        "pressure_msl": [1014.0, 1013.5, 1012.0, 1013.0],
    }
}


def _clean_cache():
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            os.remove(os.path.join(CACHE_DIR, f))


def test_fetch_forecast_weather_parses_and_caches():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE) as mock_get:
        profile = weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR)

    assert mock_get.call_count == 1
    assert profile.source == "open-meteo forecast"
    assert len(profile.hourly_time) == 4
    # km/h -> m/s conversion: 18.0 km/h == 5.0 m/s
    assert abs(profile.wind_speed_10m_ms[2] - 5.0) < 1e-6
    assert weather.has_cached_weather(CACHE_DIR, -21.900, -48.960, "2026-10-04", "forecast")


def test_second_call_uses_cache_not_network():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE) as mock_get:
        weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR)
    with patch("bup_rocketpy.weather._http_get_json") as mock_get_2:
        profile = weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR)
    mock_get_2.assert_not_called()
    assert "cached" in profile.source


def test_offline_with_no_cache_raises_a_clear_error_not_a_crash():
    """This is what 'launch-day mode fully offline' actually protects
    against: if the operator forgot to download the forecast ahead of
    time AND there's no signal at the site, the page must show a clear
    message, not an unhandled exception."""
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", side_effect=OSError("network unreachable")):
        try:
            weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR)
            assert False, "expected WeatherUnavailableError"
        except weather.WeatherUnavailableError as exc:
            assert "network" in str(exc) or "cached" in str(exc)


def test_offline_with_stale_cache_still_works_and_says_so():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE):
        weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR)
    with patch("bup_rocketpy.weather._http_get_json", side_effect=OSError("network unreachable")):
        profile = weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR, force_refresh=True)
    assert "refresh failed" in profile.source


def test_nearest_hour_wind_and_uv_conversion():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE):
        profile = weather.fetch_forecast_weather(-21.900, -48.960, "2026-10-04", CACHE_DIR)

    speed, direction = weather.nearest_hour_wind(profile, "2026-10-04T11:30")
    assert abs(speed - 5.0) < 1e-6  # nearest sample is 12:00, 18.0 km/h = 5.0 m/s
    assert direction == 95

    u, v = weather.wind_uv_at(profile, "2026-10-04T11:30")
    # sanity: magnitude matches the speed regardless of direction convention
    assert abs((u ** 2 + v ** 2) ** 0.5 - 5.0) < 1e-6


def test_fetch_historical_weather_uses_the_archive_endpoint():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE) as mock_get:
        profile = weather.fetch_historical_weather(-21.900, -48.960, "2026-01-16", CACHE_DIR)
    called_url = mock_get.call_args[0][0]
    assert called_url == weather.HISTORICAL_URL
    assert profile.source == "open-meteo historical (archive)"


if __name__ == "__main__":
    test_fetch_forecast_weather_parses_and_caches()
    test_second_call_uses_cache_not_network()
    test_offline_with_no_cache_raises_a_clear_error_not_a_crash()
    test_offline_with_stale_cache_still_works_and_says_so()
    test_nearest_hour_wind_and_uv_conversion()
    test_fetch_historical_weather_uses_the_archive_endpoint()
    print("\nWEATHER: OK")
