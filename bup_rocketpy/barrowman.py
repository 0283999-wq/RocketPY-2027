"""Independent hand-calculation of the center of pressure using the
classical Barrowman (1966) method - nose + fin normal-force slopes only,
the textbook dominant-term approach. This is deliberately NOT a call into
RocketPy's own CP code: it exists so the report can show a genuine, from-
scratch cross-check against RocketPy's numerical answer, the same way
PROMETEO's own submitted report includes a hand Barrowman verification
next to the RocketPy figure.

Neglects body-tube and transition/boat-tail normal-force contributions
(the classical simplification - both are small next to nose + fins for a
slender airframe). Flagged explicitly in the result so nobody mistakes it
for a full replication of RocketPy's own (more complete) CP model.
"""
import math

_NOSE_CP_FACTOR = {
    "conical": 0.666,
    "cone": 0.666,
    "ogive": 0.466,
    "haack": 0.5,
    "von karman": 0.5,
    "parabolic": 0.5,
    "power": 0.5,
    "elliptical": 0.333,
}


def _body_radius_at(parsed, position_m):
    for bt in parsed.body_tubes:
        if bt.radius and bt.position_m <= position_m <= bt.position_m + bt.length:
            return bt.radius
    for bt in sorted(parsed.body_tubes, key=lambda b: b.position_m):
        if bt.radius:
            return bt.radius
    if parsed.nose is not None:
        return parsed.nose.aft_radius
    return 0.05


def hand_calc_cp(parsed):
    """Returns a dict with the hand-calculated CP (m from nose tip, same
    frame as OpenRocket/ork_reader positions) and a breakdown, or None if
    the rocket has no nose or no fins to compute from."""
    if parsed.nose is None or not parsed.fins:
        return None

    cn_nose = 2.0
    shape_key = (parsed.nose.shape or "").strip().lower()
    k = _NOSE_CP_FACTOR.get(shape_key, 0.5)
    x_nose = k * parsed.nose.length

    cn_fins_total = 0.0
    weighted_x_fins = 0.0
    fin_details = []
    for finset in parsed.fins:
        n = finset.count
        s = finset.span
        # 2026-10-09 review item 2: elliptical/freeform fins reuse this
        # classical trapezoid formula via their root_chord/tip_chord(=0)/
        # sweep_length(=0) SURROGATE fields (see ork_reader.FinSet's
        # docstring) - this cross-check was never meant to need a shape-
        # specific formula for every planform; it reduces to treating the
        # fin as a zero-sweep triangle of the same chord/span, a known,
        # reasonable Barrowman approximation, not an exact match to the
        # REAL simulated CP (which uses the exact geometry - see
        # translate.build_rocket).
        cr, ct = finset.root_chord, finset.tip_chord
        xr = finset.sweep_length
        if n <= 0 or s <= 0 or (cr + ct) <= 0:
            continue
        body_radius = _body_radius_at(parsed, finset.position_m)
        d = 2.0 * body_radius

        cn_alpha = (
            (1.0 + body_radius / (s + body_radius))
            * (4.0 * n * (s / d) ** 2)
            / (1.0 + math.sqrt(1.0 + (2.0 * xr / (cr + ct)) ** 2))
        )
        x_bar = (xr * (cr + 2.0 * ct)) / (3.0 * (cr + ct)) + (1.0 / 6.0) * (cr + ct - (cr * ct) / (cr + ct))
        x_fin_cp = finset.position_m + x_bar

        cn_fins_total += cn_alpha
        weighted_x_fins += cn_alpha * x_fin_cp
        fin_details.append({"name": finset.name, "cn_alpha": cn_alpha, "cp_m": x_fin_cp, "body_radius_m": body_radius})

    if cn_fins_total <= 0:
        return None

    x_fins = weighted_x_fins / cn_fins_total
    cn_total = cn_nose + cn_fins_total
    cp_total_m = (cn_nose * x_nose + cn_fins_total * x_fins) / cn_total

    return {
        "cp_m": cp_total_m,
        "cn_alpha_total": cn_total,
        "nose_cn_alpha": cn_nose, "nose_cp_m": x_nose,
        "fins_cn_alpha": cn_fins_total, "fins_cp_m": x_fins,
        "fin_details": fin_details,
        "method": "Barrowman (1966), nose + fins only - body tube and transition normal-force contributions neglected (standard textbook simplification for a slender airframe).",
    }
