"""2026-09-26/27 review items H/I/3: Open-Meteo forecast + historical
weather, cached locally. This cloud sandbox can't reach api.open-meteo.com,
so every test mocks bup_rocketpy.weather._http_get_json directly (per
CLAUDE.md Phase 2's own instruction to test with mocked data) - real
network calls only ever happen on Diego's machine.

Dates used with fetch_forecast_weather are computed RELATIVE TO TODAY
(not hardcoded), since 2026-09-27 review item 3b added a client-side
check that a forecast date must be within Open-Meteo's ~16-day window -
a fixed calendar date would eventually fall outside that window and
break these tests for no real reason.
"""
import os
import sys
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import weather

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "outputs", "test_weather_cache")
NEAR_DATE = (date.today() + timedelta(days=3)).isoformat()

FAKE_OPEN_METEO_RESPONSE = {
    "hourly": {
        "time": [f"{NEAR_DATE}T00:00", f"{NEAR_DATE}T06:00", f"{NEAR_DATE}T12:00", f"{NEAR_DATE}T18:00"],
        "wind_speed_10m": [2.0, 3.0, 5.0, 3.5],  # m/s - wind_speed_unit=ms is always requested now, no manual conversion
        "wind_direction_10m": [90, 100, 45, 105],
        "temperature_2m": [18.0, 16.5, 24.0, 20.0],
        "pressure_msl": [1014.0, 1013.5, 1012.0, 1013.0],
        "wind_speed_1000hPa": [2.1, 3.1, 5.2, 3.6],
        "wind_direction_1000hPa": [90, 100, 45, 105],
        "wind_speed_925hPa": [4.0, 5.0, 8.0, 6.0],
        "wind_direction_925hPa": [80, 95, 50, 100],
        "wind_speed_850hPa": [6.0, 7.0, 10.0, 8.0],
        "wind_direction_850hPa": [70, 90, 55, 95],
        "wind_speed_700hPa": [10.0, 11.0, 14.0, 12.0],
        "wind_direction_700hPa": [60, 85, 60, 90],
    }
}


def _clean_cache():
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            os.remove(os.path.join(CACHE_DIR, f))


def test_fetch_forecast_weather_requests_local_timezone_and_ms_units():
    """2026-09-27 review item 3: the real bug (omitting timezone made
    Open-Meteo return GMT-labeled timestamps, silently misreading '12:00
    local' as 06:00 local) - locked in as a request-shape assertion so
    it can't quietly regress."""
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE) as mock_get:
        weather.fetch_forecast_weather(19.9535, -98.8288, NEAR_DATE, CACHE_DIR)
    params = mock_get.call_args[0][1]
    assert params["timezone"] == "auto", "must request local time for the site, not default to GMT"
    assert params["wind_speed_unit"] == "ms", "must request m/s explicitly, not assume+convert from the km/h default"


def test_fetch_forecast_weather_parses_and_caches():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE) as mock_get:
        profile = weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)

    assert mock_get.call_count == 1
    assert profile.source == "open-meteo forecast"
    assert len(profile.hourly_time) == 4
    assert profile.wind_speed_10m_ms[2] == 5.0  # requested directly in m/s, no conversion
    assert weather.has_cached_weather(CACHE_DIR, -21.900, -48.960, NEAR_DATE, "forecast")


def test_second_call_uses_cache_not_network():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE):
        weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)
    with patch("bup_rocketpy.weather._http_get_json") as mock_get_2:
        profile = weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)
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
            weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)
            assert False, "expected WeatherUnavailableError"
        except weather.WeatherUnavailableError as exc:
            assert "network" in str(exc) or "cached" in str(exc)


def test_offline_with_stale_cache_still_works_and_says_so():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE):
        weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)
    with patch("bup_rocketpy.weather._http_get_json", side_effect=OSError("network unreachable")):
        profile = weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR, force_refresh=True)
    assert "refresh failed" in profile.source


def test_nearest_hour_wind_and_uv_conversion():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE):
        profile = weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)

    speed, direction = weather.nearest_hour_wind(profile, f"{NEAR_DATE}T11:30")
    assert speed == 5.0  # nearest sample is 12:00
    assert direction == 45

    u, v = weather.wind_uv_at(profile, f"{NEAR_DATE}T11:30")
    # sanity: magnitude matches the speed regardless of direction convention
    assert abs((u ** 2 + v ** 2) ** 0.5 - 5.0) < 1e-6


def test_fetch_historical_weather_uses_the_archive_endpoint():
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE) as mock_get:
        profile = weather.fetch_historical_weather(-21.900, -48.960, "2026-01-16", CACHE_DIR)
    called_url = mock_get.call_args[0][0]
    assert called_url == weather.HISTORICAL_URL
    assert profile.source == "open-meteo historical (archive)"


def test_forecast_date_beyond_horizon_raises_a_clear_error():
    """2026-09-27 review item 3b: Diego's December example ('2026-12-04
    doesn't work') - a date beyond Open-Meteo's ~16-day forecast window
    must fail with a clear, specific message pointing at climatology,
    not a confusing generic network error."""
    far_date = (date.today() + timedelta(days=60)).isoformat()
    try:
        weather.fetch_forecast_weather(19.9535, -98.8288, far_date, CACHE_DIR)
        assert False, "expected ForecastHorizonError"
    except weather.ForecastHorizonError as exc:
        assert "climatology" in str(exc).lower()


def test_wind_profile_vs_altitude_includes_pressure_levels():
    """2026-09-27 review item 3a: 'show the full wind profile vs
    altitude, not just one number.'"""
    _clean_cache()
    with patch("bup_rocketpy.weather._http_get_json", return_value=FAKE_OPEN_METEO_RESPONSE):
        profile = weather.fetch_forecast_weather(-21.900, -48.960, NEAR_DATE, CACHE_DIR)
    rows = weather.wind_profile_vs_altitude(profile, f"{NEAR_DATE}T12:00")
    assert len(rows) == 5  # surface (10m) + 4 pressure levels
    altitudes = [r[0] for r in rows]
    assert altitudes == sorted(altitudes), "rows should be surface-first, increasing altitude"
    # surface row's speed matches the plain 10m reading
    assert rows[0][2] == 5.0


def test_climatology_uses_circular_mean_for_direction():
    """A naive arithmetic mean of e.g. 350 deg and 10 deg gives 180 deg
    (exactly backwards) - the correct circular mean is ~0/360."""
    _clean_cache()
    call_count = {"n": 0}

    def fake_get(url, params, timeout=15):
        call_count["n"] += 1
        return {"hourly": {"time": [f"{params['start_date']}T12:00"], "wind_speed_10m": [6.0], "wind_direction_10m": [350.0 if call_count["n"] % 2 else 10.0]}}

    with patch("bup_rocketpy.weather._http_get_json", side_effect=fake_get):
        profile = weather.fetch_climatology(19.9535, -98.8288, month=1, day=15, hour=12, cache_dir=CACHE_DIR, years=4)

    assert profile.wind_speed_mean_ms == 6.0
    assert profile.wind_direction_mean_deg < 20 or profile.wind_direction_mean_deg > 340, f"circular mean of ~0/350/10 split should stay near 0/360, got {profile.wind_direction_mean_deg}"
    assert len(profile.years) == 4


def test_climatology_survives_one_bad_year():
    _clean_cache()
    call_count = {"n": 0}

    def fake_get(url, params, timeout=15):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("network blip")
        return {"hourly": {"time": [f"{params['start_date']}T12:00"], "wind_speed_10m": [5.0], "wind_direction_10m": [90.0]}}

    with patch("bup_rocketpy.weather._http_get_json", side_effect=fake_get):
        profile = weather.fetch_climatology(19.9535, -98.8288, month=6, day=1, hour=12, cache_dir=CACHE_DIR, years=5)
    assert len(profile.years) == 4, "one failed year should be skipped, not sink the whole climatology"


if __name__ == "__main__":
    test_fetch_forecast_weather_requests_local_timezone_and_ms_units()
    test_fetch_forecast_weather_parses_and_caches()
    test_second_call_uses_cache_not_network()
    test_offline_with_no_cache_raises_a_clear_error_not_a_crash()
    test_offline_with_stale_cache_still_works_and_says_so()
    test_nearest_hour_wind_and_uv_conversion()
    test_fetch_historical_weather_uses_the_archive_endpoint()
    test_forecast_date_beyond_horizon_raises_a_clear_error()
    test_wind_profile_vs_altitude_includes_pressure_levels()
    test_climatology_uses_circular_mean_for_direction()
    test_climatology_survives_one_bad_year()
    print("\nWEATHER: OK")
