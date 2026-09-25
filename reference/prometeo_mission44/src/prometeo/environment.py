"""Environment builder. Default is fully offline (CRS 10.1.5: a judge must be
able to run this with no internet) - custom atmosphere built straight from
the OpenRocket export's own wind/temperature/pressure columns at t=0. Pass
atmos="forecast" for a live GFS pull when internet is available; that path is
never the default.
"""

import math

import config
from rocketpy import Environment


def build_environment(site="brasil", atmos="custom"):
    if site == "brasil":
        lat, lon, elev = config.SLR_LATITUDE, config.SLR_LONGITUDE, config.SLR_ELEVATION
        wind_speed, wind_dir = config.SLR_WIND_SPEED, config.SLR_WIND_DIRECTION
        temp_C, pressure_mbar = config.SLR_TEMPERATURE, config.SLR_PRESSURE
    elif site == "pachuca":
        lat, lon, elev = config.PACHUCA_LATITUDE, config.PACHUCA_LONGITUDE, config.PACHUCA_ELEVATION
        wind_speed, wind_dir = config.SLR_WIND_SPEED, config.SLR_WIND_DIRECTION  # no site-specific wind column used here
        temp_C, pressure_mbar = config.SLR_TEMPERATURE, config.SLR_PRESSURE
    elif site == "julio4":
        lat, lon, elev = 19.967, -98.856, config.JULIO4_ELEVATION
        wind_speed, wind_dir = 3.247, 90.0  # prometeo4dejulio.csv @ t=0
        temp_C, pressure_mbar = 15.0, 755.184  # same file @ t=0
    else:
        raise ValueError(f"unknown site {site!r}")

    env = Environment(latitude=lat, longitude=lon, elevation=elev)

    if atmos == "forecast":
        env.set_atmospheric_model(type="Forecast", file="GFS")
    else:
        # constant-with-altitude profile from the OpenRocket t=0 row - not a
        # full sounding (none was delivered), but reproducible offline and
        # good enough for the ~1km AGL envelope this rocket flies in
        env.set_atmospheric_model(
            type="custom_atmosphere",
            wind_u=wind_speed * math.sin(math.radians(wind_dir)),
            wind_v=wind_speed * math.cos(math.radians(wind_dir)),
            temperature=temp_C + 273.15,
            pressure=pressure_mbar * 100,
        )
    return env
