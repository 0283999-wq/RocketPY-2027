"""Real weather via Open-Meteo, cached locally (CLAUDE.md Phase 2 +
2026-09-26/27 overnight run items H "launch-day mode", I "real-weather
validation", and 2026-09-27 item 3 "launch-day weather is wrong").

Open-Meteo needs no API key/account (CLAUDE.md Sec Phase 2). This cloud
sandbox cannot reach api.open-meteo.com/archive-api.open-meteo.com
(no internet egress to that host) - real network calls only happen on
Diego's own machine. Every function here is unit-tested with the HTTP
layer mocked (`_http_get_json` is the one seam every test patches), per
CLAUDE.md's own instruction: "Downloads happen on Diego's machine (the
cloud can't reach those servers), so test with mocked data and cache
every downloaded profile next to its result for reproducibility." This
also means the exact Open-Meteo parameter names below (especially the
pressure-level ones) could not be verified against the live API from
this sandbox - double-check them against Open-Meteo's own docs
(open-meteo.com/en/docs) the first time this runs for real, and flag it
here if anything doesn't match.

Caching is not an optimization here, it's a requirement: once a profile
is downloaded, "launch-day mode" (item H) must keep working with NO
network at all (a launch site often has poor/no signal), and a cached
historical profile (item I) must never silently re-fetch and change
between two validation runs.

2026-09-27 review item 3: a real bug shipped last night and caught
today - every request omitted `timezone`, so Open-Meteo returned
`hourly.time` in GMT while the UI's "launch hour" field is LOCAL time
(e.g. America/Mexico_City). Asking for "12:00" therefore silently read
the row for 12:00 UTC = 06:00 local - early morning, characteristically
much calmer than the actual midday wind the public forecast (and Diego)
expected. Every request now passes `timezone=auto` (Open-Meteo resolves
the IANA zone for the given lat/lon itself and returns local-time
timestamps), and `wind_speed_unit=ms` is requested explicitly instead of
assuming the km/h default and converting by hand - removes a whole class
of "did I convert correctly" bugs.
"""
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone

from bup_rocketpy.translate import wind_speed_direction_to_uv

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 16  # Open-Meteo's own documented forecast window

# Pressure levels roughly spanning ground to ~3 km AGL (a typical high-
# power rocket's altitude range) - see module docstring's live-
# verification caveat.
PRESSURE_LEVELS_HPA = [1000, 925, 850, 700]
HOURLY_SURFACE_VARS = ["wind_speed_10m", "wind_direction_10m", "temperature_2m", "pressure_msl"]
HOURLY_PRESSURE_VARS = [f"wind_speed_{p}hPa" for p in PRESSURE_LEVELS_HPA] + [f"wind_direction_{p}hPa" for p in PRESSURE_LEVELS_HPA]

# ICAO standard atmosphere pressure -> geopotential height, m ASL -
# APPROXIMATE, for labeling the profile display only ("~750 m" next to
# "925 hPa"), never used as the actual simulated atmosphere (rocketpy's
# own standard_atmosphere model is unaffected by this).
_STANDARD_ATMOSPHERE_ALTITUDE_M = {1000: 110, 925: 762, 850: 1457, 700: 3012}


@dataclass
class WeatherProfile:
    latitude: float
    longitude: float
    date: str  # ISO "YYYY-MM-DD"
    source: str  # "open-meteo forecast" / "open-meteo historical (archive)" / "cache"
    hourly_time: list = field(default_factory=list)  # ISO datetimes IN LOCAL TIME for the site (timezone=auto), e.g. "2026-10-04T12:00"
    wind_speed_10m_ms: list = field(default_factory=list)
    wind_direction_10m_deg: list = field(default_factory=list)
    temperature_2m_c: list = field(default_factory=list)
    pressure_msl_hpa: list = field(default_factory=list)
    # {"1000": {"speed_ms": [...], "direction_deg": [...]}, "925": {...}, ...}
    # - string keys (JSON-safe), one entry per PRESSURE_LEVELS_HPA level.
    pressure_level_winds: dict = field(default_factory=dict)
    fetched_at_utc: str = ""


@dataclass
class ClimatologyProfile:
    """2026-09-27 review item 3b: for a date beyond Open-Meteo's ~16-day
    forecast horizon (Diego's December example), the historical archive's
    own MEAN + SPREAD of wind speed/direction for that same month/day/hour
    across several past years - usable as a Monte Carlo wind uncertainty
    source for planning, not a specific-day prediction."""
    latitude: float
    longitude: float
    month: int
    day: int
    hour: int
    years: list  # the actual calendar years averaged over
    wind_speed_mean_ms: float
    wind_speed_std_ms: float
    wind_direction_mean_deg: float  # circular mean - see _circular_mean_deg
    per_year_speed_ms: list  # one value per year, for transparency/debugging
    per_year_direction_deg: list
    source: str = "open-meteo historical (archive), climatology"
    fetched_at_utc: str = ""


class WeatherUnavailableError(RuntimeError):
    """Raised when no cached profile exists AND the network fetch
    failed - callers (the Launch Day page) must catch this and show a
    clear "not cached yet, and couldn't reach the network" message
    rather than let the page crash (CLAUDE.md: "no page ever crashes")."""


class ForecastHorizonError(ValueError):
    """Raised by fetch_forecast_weather when the requested date is
    beyond Open-Meteo's own forecast window (today .. +16 days) -
    2026-09-27 review item 3b: Diego's December example should get this
    clear, specific message (and a climatology suggestion), not a
    confusing generic network-error message from a failed HTTP request."""


def _cache_path(cache_dir, latitude, longitude, date, kind):
    return os.path.join(cache_dir, f"weather_{kind}_{latitude:.3f}_{longitude:.3f}_{date}.json")


def _http_get_json(url, params, timeout=15):
    """The one seam every test mocks (patch this function, not urlopen
    directly) - keeps the real network call in a single, small,
    easy-to-stub place. Open-Meteo returns a JSON body describing the
    problem even on a 4xx response (`{"error": true, "reason": "..."}`)
    - read it instead of losing that detail to a bare HTTPError."""
    full_url = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full_url, timeout=timeout) as resp:  # noqa: S310 - fixed https host, no user-controlled URL
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.load(exc)
            reason = body.get("reason", str(exc))
        except Exception:
            reason = str(exc)
        raise RuntimeError(f"Open-Meteo returned an error: {reason}") from exc


def _parse_open_meteo_response(data, latitude, longitude, date, source):
    hourly = data.get("hourly", {})
    pressure_level_winds = {}
    for p in PRESSURE_LEVELS_HPA:
        speed = hourly.get(f"wind_speed_{p}hPa")
        direction = hourly.get(f"wind_direction_{p}hPa")
        if speed is not None and direction is not None:
            pressure_level_winds[str(p)] = {"speed_ms": speed, "direction_deg": direction}
    return WeatherProfile(
        latitude=latitude, longitude=longitude, date=date, source=source,
        hourly_time=hourly.get("time", []),
        wind_speed_10m_ms=hourly.get("wind_speed_10m", []),
        wind_direction_10m_deg=hourly.get("wind_direction_10m", []),
        temperature_2m_c=hourly.get("temperature_2m", []),
        pressure_msl_hpa=hourly.get("pressure_msl", []),
        pressure_level_winds=pressure_level_winds,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def load_cached_weather(path):
    with open(path) as f:
        return WeatherProfile(**json.load(f))


def has_cached_weather(cache_dir, latitude, longitude, date, kind="forecast"):
    return os.path.exists(_cache_path(cache_dir, latitude, longitude, date, kind))


def _fetch(url, latitude, longitude, date, cache_dir, kind, source_label, force_refresh, include_pressure_levels):
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, latitude, longitude, date, kind)
    if not force_refresh and os.path.exists(path):
        profile = load_cached_weather(path)
        profile.source = f"{profile.source} (cached {profile.fetched_at_utc})"
        return profile

    hourly_vars = list(HOURLY_SURFACE_VARS)
    if include_pressure_levels:
        hourly_vars += HOURLY_PRESSURE_VARS

    try:
        data = _http_get_json(url, {
            "latitude": latitude, "longitude": longitude,
            "start_date": date, "end_date": date,
            "hourly": ",".join(hourly_vars),
            "wind_speed_unit": "ms",
            # "auto": Open-Meteo resolves the IANA timezone for this
            # lat/lon itself and returns hourly.time in THAT local time -
            # see module docstring for the real bug this fixes.
            "timezone": "auto",
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
    window (today .. +16 days) - checked client-side BEFORE the request
    so a too-far-out date gets a clear ForecastHorizonError instead of a
    confusing generic network-error message (2026-09-27 review item 3b).
    This is what the Launch Day page's "Download weather for launch day"
    button calls, ahead of time, while there's still internet - the
    cached result then works with none."""
    requested = date_cls.fromisoformat(date)
    horizon = date_cls.today() + timedelta(days=FORECAST_HORIZON_DAYS)
    if requested > horizon or requested < date_cls.today():
        raise ForecastHorizonError(
            f"{date} is outside Open-Meteo's forecast window (today through {horizon.isoformat()}, "
            f"~{FORECAST_HORIZON_DAYS} days ahead). Use 'Download climatology' instead for planning "
            "further out - it gives the historical average and spread for that date/hour, not a specific forecast."
        )
    return _fetch(FORECAST_URL, latitude, longitude, date, cache_dir, "forecast", "open-meteo forecast", force_refresh, include_pressure_levels=True)


def fetch_historical_weather(latitude, longitude, date, cache_dir, force_refresh=False):
    """date: ISO "YYYY-MM-DD" of a PAST flight, for V1/V2-style
    revalidation against real recorded weather (item I) instead of the
    OpenRocket-recorded conditions used until now."""
    return _fetch(HISTORICAL_URL, latitude, longitude, date, cache_dir, "historical", "open-meteo historical (archive)", force_refresh, include_pressure_levels=False)


def _circular_mean_deg(degrees):
    """Correct mean of a set of compass bearings - a plain arithmetic
    mean of e.g. [350, 10] gives 180 (backwards); this converts each to
    a unit vector, averages those, and converts back."""
    if not degrees:
        return None
    x = sum(math.cos(math.radians(d)) for d in degrees) / len(degrees)
    y = sum(math.sin(math.radians(d)) for d in degrees) / len(degrees)
    return math.degrees(math.atan2(y, x)) % 360


def fetch_climatology(latitude, longitude, month, day, hour, cache_dir, years=10, force_refresh=False):
    """2026-09-27 review item 3b: for a date beyond the forecast horizon
    (Diego's December example), the historical archive's own wind
    speed/direction for the SAME month/day/hour across the last `years`
    calendar years - mean + spread, usable as a Monte Carlo wind
    uncertainty distribution for planning, not a single-day forecast.
    Caches the whole multi-year fetch under one key (month/day/hour),
    so repeated planning look-ups for the same date don't re-download."""
    cache_key_date = f"climatology_{month:02d}-{day:02d}_{hour:02d}h"
    path = _cache_path(cache_dir, latitude, longitude, cache_key_date, "climatology")
    if not force_refresh and os.path.exists(path):
        with open(path) as f:
            profile = ClimatologyProfile(**json.load(f))
        profile.source = f"{profile.source} (cached {profile.fetched_at_utc})"
        return profile

    this_year = date_cls.today().year
    candidate_years = list(range(this_year - years, this_year))
    speeds, directions, used_years = [], [], []
    last_exc = None
    for year in candidate_years:
        try:
            target_date = date_cls(year, month, day).isoformat()
        except ValueError:
            continue  # e.g. Feb 29 in a non-leap year - skip, don't fabricate a substitute day
        try:
            data = _http_get_json(HISTORICAL_URL, {
                "latitude": latitude, "longitude": longitude,
                "start_date": target_date, "end_date": target_date,
                "hourly": "wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "ms", "timezone": "auto",
            })
        except Exception as exc:
            last_exc = exc
            continue  # one bad year shouldn't sink the whole climatology - averaged over whatever years DID succeed
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        target_hour_str = f"{target_date}T{hour:02d}:00"
        if target_hour_str in times:
            idx = times.index(target_hour_str)
            speeds.append(hourly["wind_speed_10m"][idx])
            directions.append(hourly["wind_direction_10m"][idx])
            used_years.append(year)

    if not speeds:
        raise WeatherUnavailableError(
            f"Could not build a climatology for {month:02d}-{day:02d} {hour:02d}:00 at ({latitude}, {longitude}): "
            f"every year's fetch failed ({last_exc}). Try again with a working internet connection."
        )

    mean_speed = sum(speeds) / len(speeds)
    std_speed = (sum((v - mean_speed) ** 2 for v in speeds) / len(speeds)) ** 0.5
    profile = ClimatologyProfile(
        latitude=latitude, longitude=longitude, month=month, day=day, hour=hour,
        years=used_years, wind_speed_mean_ms=mean_speed, wind_speed_std_ms=std_speed,
        wind_direction_mean_deg=_circular_mean_deg(directions),
        per_year_speed_ms=speeds, per_year_direction_deg=directions,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with open(path, "w") as f:
        json.dump(asdict(profile), f, indent=2)
    return profile


def nearest_hour_wind(profile, target_iso_datetime):
    """Returns (wind_speed_ms, wind_direction_from_deg) at the hourly
    sample closest to target_iso_datetime (e.g. "2026-10-04T12:00",
    LOCAL time for the site - matches profile.hourly_time's own
    convention now that every fetch requests timezone=auto). Raises
    ValueError if the profile has no hourly data at all (an empty/
    malformed response) - callers must not silently treat that as
    "no wind"."""
    if not profile.hourly_time:
        raise ValueError(f"weather profile for {profile.date} has no hourly data to sample")
    target = datetime.fromisoformat(target_iso_datetime)
    times = [datetime.fromisoformat(t) for t in profile.hourly_time]
    idx = min(range(len(times)), key=lambda i: abs((times[i] - target).total_seconds()))
    return profile.wind_speed_10m_ms[idx], profile.wind_direction_10m_deg[idx]


def wind_profile_vs_altitude(profile, target_iso_datetime):
    """2026-09-27 review item 3a: "show the full wind profile vs
    altitude, not just one number." Returns a list of
    (altitude_m_asl_approx, pressure_hpa, speed_ms, direction_deg) rows,
    surface first - altitude is the ICAO standard-atmosphere approximate
    height for that pressure level (labeled as such; NOT the site's own
    measured elevation-adjusted height), for display only."""
    if not profile.hourly_time:
        raise ValueError(f"weather profile for {profile.date} has no hourly data to sample")
    target = datetime.fromisoformat(target_iso_datetime)
    times = [datetime.fromisoformat(t) for t in profile.hourly_time]
    idx = min(range(len(times)), key=lambda i: abs((times[i] - target).total_seconds()))

    rows = [(10.0, None, profile.wind_speed_10m_ms[idx], profile.wind_direction_10m_deg[idx])]
    for p in PRESSURE_LEVELS_HPA:
        level = profile.pressure_level_winds.get(str(p))
        if level is None:
            continue
        rows.append((_STANDARD_ATMOSPHERE_ALTITUDE_M[p], p, level["speed_ms"][idx], level["direction_deg"][idx]))
    return rows


def wind_uv_at(profile, target_iso_datetime):
    """rocketpy East/North wind velocity components at the sample
    closest to target_iso_datetime - reuses translate's already-verified
    speed+bearing-from -> (u, v) formula (same convention Open-Meteo's
    wind_direction_10m and OpenRocket's <winddirection> both use)."""
    speed_ms, direction_deg = nearest_hour_wind(profile, target_iso_datetime)
    return wind_speed_direction_to_uv(speed_ms, direction_deg)
