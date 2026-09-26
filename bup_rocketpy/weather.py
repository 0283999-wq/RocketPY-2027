"""Real weather via Open-Meteo, cached locally (CLAUDE.md Phase 2 +
2026-09-26 overnight run items H "launch-day mode" and I "real-weather
validation").

Open-Meteo needs no API key/account (CLAUDE.md Sec Phase 2). This cloud
sandbox cannot reach api.open-meteo.com/archive-api.open-meteo.com
(no internet egress to that host) - real network calls only happen on
Diego's own machine. Every function here is unit-tested with the HTTP
layer mocked (`_http_get_json` is the one seam every test patches), per
CLAUDE.md's own instruction: "Downloads happen on Diego's machine (the
cloud can't reach those servers), so test with mocked data and cache
every downloaded profile next to its result for reproducibility."

Caching is not an optimization here, it's a requirement: once a profile
is downloaded, "launch-day mode" (item H) must keep working with NO
network at all (a launch site often has poor/no signal), and a cached
historical profile (item I) must never silently re-fetch and change
between two validation runs.
"""
import json
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from bup_rocketpy.translate import wind_speed_direction_to_uv

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = "wind_speed_10m,wind_direction_10m,temperature_2m,pressure_msl"


@dataclass
class WeatherProfile:
    latitude: float
    longitude: float
    date: str  # ISO "YYYY-MM-DD"
    source: str  # "open-meteo forecast" / "open-meteo historical (archive)" / "cache"
    hourly_time: list = field(default_factory=list)  # ISO datetimes, e.g. "2026-10-04T12:00"
    wind_speed_10m_ms: list = field(default_factory=list)
    wind_direction_10m_deg: list = field(default_factory=list)
    temperature_2m_c: list = field(default_factory=list)
    pressure_msl_hpa: list = field(default_factory=list)
    fetched_at_utc: str = ""


class WeatherUnavailableError(RuntimeError):
    """Raised when no cached profile exists AND the network fetch
    failed - callers (the Launch Day page) must catch this and show a
    clear "not cached yet, and couldn't reach the network" message
    rather than let the page crash (CLAUDE.md: "no page ever crashes")."""


def _cache_path(cache_dir, latitude, longitude, date, kind):
    return os.path.join(cache_dir, f"weather_{kind}_{latitude:.3f}_{longitude:.3f}_{date}.json")


def _http_get_json(url, params, timeout=15):
    """The one seam every test mocks (patch this function, not urlopen
    directly) - keeps the real network call in a single, small,
    easy-to-stub place."""
    full_url = url + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(full_url, timeout=timeout) as resp:  # noqa: S310 - fixed https host, no user-controlled URL
        return json.load(resp)


def _parse_open_meteo_response(data, latitude, longitude, date, source):
    hourly = data.get("hourly", {})
    wind_kmh = hourly.get("wind_speed_10m", [])
    return WeatherProfile(
        latitude=latitude, longitude=longitude, date=date, source=source,
        hourly_time=hourly.get("time", []),
        wind_speed_10m_ms=[v / 3.6 if v is not None else None for v in wind_kmh],  # Open-Meteo's default wind unit is km/h
        wind_direction_10m_deg=hourly.get("wind_direction_10m", []),
        temperature_2m_c=hourly.get("temperature_2m", []),
        pressure_msl_hpa=hourly.get("pressure_msl", []),
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def load_cached_weather(path):
    with open(path) as f:
        return WeatherProfile(**json.load(f))


def has_cached_weather(cache_dir, latitude, longitude, date, kind="forecast"):
    return os.path.exists(_cache_path(cache_dir, latitude, longitude, date, kind))


def _fetch(url, latitude, longitude, date, cache_dir, kind, source_label, force_refresh):
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, latitude, longitude, date, kind)
    if not force_refresh and os.path.exists(path):
        profile = load_cached_weather(path)
        profile.source = f"{profile.source} (cached {profile.fetched_at_utc})"
        return profile

    try:
        data = _http_get_json(url, {
            "latitude": latitude, "longitude": longitude,
            "start_date": date, "end_date": date,
            "hourly": HOURLY_VARS,
        })
    except Exception as exc:
        if os.path.exists(path):  # stale cache beats no data at all - still usable offline
            profile = load_cached_weather(path)
            profile.source = f"{profile.source} (cached {profile.fetched_at_utc}; refresh failed: {exc})"
            return profile
        raise WeatherUnavailableError(
            f"No cached weather for this site/date and the network fetch failed ({exc}). "
            "Download it once with a working internet connection before launch day."
        ) from exc

    profile = _parse_open_meteo_response(data, latitude, longitude, date, source_label)
    with open(path, "w") as f:
        json.dump(asdict(profile), f, indent=2)
    return profile


def fetch_forecast_weather(latitude, longitude, date, cache_dir, force_refresh=False):
    """date: ISO "YYYY-MM-DD", must be within Open-Meteo's forecast
    window (today .. +16 days). This is what the Launch Day page's
    "Download weather for launch day" button calls, ahead of time, while
    there's still internet - the cached result then works with none."""
    return _fetch(FORECAST_URL, latitude, longitude, date, cache_dir, "forecast", "open-meteo forecast", force_refresh)


def fetch_historical_weather(latitude, longitude, date, cache_dir, force_refresh=False):
    """date: ISO "YYYY-MM-DD" of a PAST flight, for V1/V2-style
    revalidation against real recorded weather (item I) instead of the
    OpenRocket-recorded conditions used until now."""
    return _fetch(HISTORICAL_URL, latitude, longitude, date, cache_dir, "historical", "open-meteo historical (archive)", force_refresh)


def nearest_hour_wind(profile, target_iso_datetime):
    """Returns (wind_speed_ms, wind_direction_from_deg) at the hourly
    sample closest to target_iso_datetime (e.g. "2026-10-04T12:00").
    Raises ValueError if the profile has no hourly data at all (an empty/
    malformed response) - callers must not silently treat that as
    "no wind"."""
    if not profile.hourly_time:
        raise ValueError(f"weather profile for {profile.date} has no hourly data to sample")
    target = datetime.fromisoformat(target_iso_datetime)
    times = [datetime.fromisoformat(t) for t in profile.hourly_time]
    idx = min(range(len(times)), key=lambda i: abs((times[i] - target).total_seconds()))
    return profile.wind_speed_10m_ms[idx], profile.wind_direction_10m_deg[idx]


def wind_uv_at(profile, target_iso_datetime):
    """rocketpy East/North wind velocity components at the sample
    closest to target_iso_datetime - reuses translate's already-verified
    speed+bearing-from -> (u, v) formula (same convention Open-Meteo's
    wind_direction_10m and OpenRocket's <winddirection> both use)."""
    speed_ms, direction_deg = nearest_hour_wind(profile, target_iso_datetime)
    return wind_speed_direction_to_uv(speed_ms, direction_deg)
