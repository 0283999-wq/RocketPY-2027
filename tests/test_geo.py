"""bup_rocketpy/geo.py - local XY <-> lat/lon conversion for the landing
map (2026-09-25 review Section 7). Pure math, no rocketpy needed.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy.geo import ellipse_to_latlon_polygon, local_xy_to_latlon


def test_local_xy_to_latlon_matches_known_distances():
    origin_lat, origin_lon = -21.9, -48.96
    lat, lon = local_xy_to_latlon(0.0, 111_320.0, origin_lat, origin_lon)
    assert abs(lat - (origin_lat + 1.0)) < 1e-6, "111,320 m north should be +1 deg latitude"
    assert abs(lon - origin_lon) < 1e-9, "pure north offset should not change longitude"

    lat0, lon0 = local_xy_to_latlon(0.0, 0.0, origin_lat, origin_lon)
    assert (lat0, lon0) == (origin_lat, origin_lon), "zero offset should return the origin exactly"


def test_ellipse_polygon_closes_and_has_right_extent():
    origin_lat, origin_lon = -21.9, -48.96
    poly = ellipse_to_latlon_polygon(center_x=100.0, center_y=50.0, width=200.0, height=100.0, angle_deg=0.0, origin_lat=origin_lat, origin_lon=origin_lon, n_points=36)
    assert poly[0] == poly[-1], "polygon should be closed (first point == last point)"
    assert len(poly) == 37

    lats = [p[0] for p in poly]
    max_lat_offset_m = (max(lats) - origin_lat) * 111_320.0
    # ellipse center_y=50, height=100 -> semi-minor axis 50 -> max y = 100 (center + semi-axis, unrotated)
    assert 95 < max_lat_offset_m < 105, f"expected the polygon's northmost point around 100 m north of origin, got {max_lat_offset_m:.1f} m"


if __name__ == "__main__":
    test_local_xy_to_latlon_matches_known_distances()
    test_ellipse_polygon_closes_and_has_right_extent()
    print("PASSED")
