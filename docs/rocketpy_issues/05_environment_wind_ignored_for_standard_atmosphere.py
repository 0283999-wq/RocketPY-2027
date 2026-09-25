"""Minimal repro: Environment.set_atmospheric_model(type="standard_atmosphere",
wind_u=..., wind_v=...) silently ignores the wind arguments.

Found 2026-09-25 review Item 3 while chasing a code-to-code apogee
mismatch against OpenRocket - wind was being parsed from a .ork file but
never actually affecting the simulation, because this call site
accepted wind_u/wind_v as documented parameters but produced zero wind
regardless.

ROOT CAUSE, confirmed by reading rocketpy/environment/environment.py:
set_atmospheric_model's "standard_atmosphere" branch calls
self.process_standard_atmosphere(), whose OWN docstring says "Note that
the wind profiles are set to zero" and which unconditionally does:

    self.__set_wind_direction_function(0)
    self.__set_wind_heading_function(0)
    self.__set_wind_velocity_x_function(0)
    self.__set_wind_velocity_y_function(0)
    self.__set_wind_speed_function(0)

So this IS documented behavior of process_standard_atmosphere() itself -
but set_atmospheric_model()'s own docstring lists wind_u/wind_v as
generic parameters without flagging that they are silently no-ops for
type="standard_atmosphere" specifically, and no warning is raised when
a caller passes them anyway. A caller reading set_atmospheric_model()'s
signature alone (the entry point most people actually call) has no way
to know this. env.add_wind_gust(wind_u, wind_v), called AFTER
set_atmospheric_model(), is the supported way to layer a constant wind
on top of "standard_atmosphere".
"""
from rocketpy import Environment

print("--- wind_u/wind_v passed directly to set_atmospheric_model(type='standard_atmosphere') ---")
env1 = Environment(latitude=0, longitude=0, elevation=0)
env1.set_atmospheric_model(type="standard_atmosphere", wind_u=5.0, wind_v=3.0)
print(f"wind_velocity_x(0) = {env1.wind_velocity_x(0)} (expected 5.0 if honored)")
print(f"wind_velocity_y(0) = {env1.wind_velocity_y(0)} (expected 3.0 if honored)")

print("\n--- workaround: add_wind_gust() called AFTER set_atmospheric_model ---")
env2 = Environment(latitude=0, longitude=0, elevation=0)
env2.set_atmospheric_model(type="standard_atmosphere")
env2.add_wind_gust(5.0, 3.0)
print(f"wind_velocity_x(0) = {env2.wind_velocity_x(0)}")
print(f"wind_velocity_y(0) = {env2.wind_velocity_y(0)}")

if env1.wind_velocity_x(0) == 0.0 and env1.wind_velocity_y(0) == 0.0:
    print("\nVERDICT: confirmed - wind_u/wind_v are silently ignored for type='standard_atmosphere'. add_wind_gust() after set_atmospheric_model is the workaround.")
else:
    print("\nVERDICT: NOT reproduced in this rocketpy version - wind_u/wind_v were honored directly.")
