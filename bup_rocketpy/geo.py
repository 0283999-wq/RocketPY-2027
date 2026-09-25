"""Local-frame (X=downrange/East, Y=crossrange/North, metres from the
pad) <-> lat/lon conversion for the Monte Carlo landing map (2026-09-25
review, Section 7). A flat-Earth approximation - fine for the few-
hundred-metre to low-single-digit-km landing dispersions this is used
for; not meant for anything longer range.
"""
import math

METERS_PER_DEG_LAT = 111_320.0  # ~constant everywhere


def local_xy_to_latlon(x_m, y_m, origin_lat, origin_lon):
    """x_m: East offset (m), y_m: North offset (m) - matches rocketpy's
    Flight.x()/Flight.y() convention. Returns (lat, lon)."""
    meters_per_deg_lon = METERS_PER_DEG_LAT * math.cos(math.radians(origin_lat))
    lat = origin_lat + y_m / METERS_PER_DEG_LAT
    lon = origin_lon + x_m / meters_per_deg_lon if meters_per_deg_lon else origin_lon
    return lat, lon


def ellipse_to_latlon_polygon(center_x, center_y, width, height, angle_deg, origin_lat, origin_lon, n_points=48):
    """Converts an (x, y, width, height, rotation) ellipse - as returned
    by monte_carlo.landing_ellipses() - into a closed lat/lon polygon
    (list of [lat, lon] pairs) ready for a Leaflet polygon layer."""
    a, b = width / 2.0, height / 2.0
    theta = math.radians(angle_deg)
    points = []
    for i in range(n_points + 1):
        t = 2 * math.pi * i / n_points
        ex, ey = a * math.cos(t), b * math.sin(t)
        # rotate by angle_deg, then translate to the ellipse center
        rx = ex * math.cos(theta) - ey * math.sin(theta) + center_x
        ry = ex * math.sin(theta) + ey * math.cos(theta) + center_y
        lat, lon = local_xy_to_latlon(rx, ry, origin_lat, origin_lon)
        points.append([lat, lon])
    return points
