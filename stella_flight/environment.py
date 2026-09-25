"""Environment builder shared by all three vehicles. No OpenRocket export to
pull wind/temperature columns from this time (that's the whole point of
going RocketPy-only) - default is rocketpy's standard_atmosphere model
(offline, no measured data required), with an easy switch to a real GFS
forecast or an EnvironmentAnalysis climatology once launch-site history is
gathered for Iacanga/Sugarcane Launch Range.
"""

from rocketpy import Environment

SLR_LATITUDE = -21.908  # Sugarcane Launch Range, from PROMETEO's OpenRocket exports
SLR_LONGITUDE = -48.962
SLR_ELEVATION = 495.0  # m ASL


def build_environment(latitude=SLR_LATITUDE, longitude=SLR_LONGITUDE, elevation=SLR_ELEVATION, atmos="standard"):
    env = Environment(latitude=latitude, longitude=longitude, elevation=elevation)
    if atmos == "standard":
        env.set_atmospheric_model(type="standard_atmosphere")
    elif atmos == "forecast":
        env.set_atmospheric_model(type="Forecast", file="GFS")
    else:
        raise ValueError(f"unknown atmos {atmos!r}")
    return env
