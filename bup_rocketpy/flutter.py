"""Fin flutter velocity (STR 6.3.2) via the classical NACA TN 4197
approximation - the same closed-form hobbyist/competition-rocketry
formula OpenRocket and the Apogee/NAR "flutter boundary" references use,
not a full aeroelastic FEA. Trapezoidal fins only; a freeform set is
approximated by its own bounding trapezoid (root/tip/span measured off
the point list), clearly labelled.

2026-10-09 review item 8: the compliance table used to show
"pass fin_flutter_velocity" verbatim in the UI - a Python parameter name
leaking into user-facing text. This module exists so there is an actual
number to show instead of a placeholder, PLUS an explicit manual-
override path (a real wind-tunnel/FEA/ANSYS/AEROLAB result) that always
takes priority over this hand formula when the team has one.

Formula (shear modulus G, static pressure P, speed of sound a, aspect
ratio AR = 2*span / (root_chord + tip_chord), taper ratio lambda =
tip_chord/root_chord, thickness ratio t/c = thickness/root_chord):

    V_f = a * sqrt( G / [ 1.337 * AR^3 * P * (lambda + 1)
                           / (2 * (AR + 2) * (t/c)^3) ] )

This neglects fin sweep, cant, and any stiffening (fillets, ribs,
laminate layup beyond a single isotropic G) - a conservative, order-of-
magnitude screening number per its own NACA-era derivation, not a
substitute for a real structural analysis on a flight-critical vehicle.
"""
import math
from dataclasses import dataclass

# Shear modulus of common fin materials (Pa) - a starting point only,
# the real value depends on layup/grain direction for anything but a
# truly isotropic material. Always editable + its source shown (CLAUDE.md
# Rule 2: never invent data without a source).
COMMON_SHEAR_MODULI_PA = {
    "G10/G12 fiberglass (typical)": 4.14e9,
    "Plywood (birch, typical)": 0.62e9,
    "Basswood": 0.40e9,
    "Carbon fiber plate (typical, in-plane)": 5.0e9,
    "ABS plastic": 0.90e9,
    "Aluminum 6061-T6": 26.0e9,
}
DEFAULT_SHEAR_MODULUS_PA = COMMON_SHEAR_MODULI_PA["G10/G12 fiberglass (typical)"]
DEFAULT_SHEAR_MODULUS_SOURCE = "G10/G12 fiberglass (typical) - EDIT if the real fin material/layup is known"


@dataclass
class FlutterResult:
    flutter_velocity_ms: float
    source: str  # "hand formula (NACA TN 4197)" or "manual override: <label>"
    aspect_ratio: float = None
    taper_ratio: float = None
    thickness_ratio: float = None
    shear_modulus_pa: float = None
    shear_modulus_source: str = None
    is_freeform_approximation: bool = False
    margin: float = None  # flutter_velocity / max_speed, None until a max_speed is known
    is_approximate: bool = True  # False only for a real manual/external-tool number


def _equivalent_trapezoid(finset):
    """2026-10-09 review item 2: for an elliptical or freeform fin set,
    finset.root_chord/tip_chord/span are the trapezoid SURROGATE fields
    (see ork_reader.FinSet's docstring) - the exact real shape flies in
    the actual simulation, but NACA TN 4197 is itself a trapezoid-planform
    formula with no general closed form for an arbitrary outline, so the
    bounding/equivalent trapezoid is the only honest way to get a flutter
    number at all for these shapes (flagged via is_freeform_approximation
    below, same as before this item's own fin support existed)."""
    return finset.root_chord, finset.tip_chord, finset.span, finset.thickness


def hand_calc_flutter_velocity(finset, speed_of_sound_ms, static_pressure_pa, shear_modulus_pa=None, shear_modulus_source=None, is_freeform=False):
    """Returns a FlutterResult for one fin set, or None if the geometry
    can't support the formula (zero chord/span/thickness)."""
    root, tip, span, thickness = _equivalent_trapezoid(finset)
    if not (root and span and thickness) or root <= 0 or span <= 0 or thickness <= 0:
        return None
    tip = tip or 0.0

    aspect_ratio = 2.0 * span / (root + tip) if (root + tip) > 0 else None
    taper_ratio = tip / root if root > 0 else 0.0
    thickness_ratio = thickness / root
    g = shear_modulus_pa if shear_modulus_pa is not None else DEFAULT_SHEAR_MODULUS_PA
    g_source = shear_modulus_source if shear_modulus_source is not None else DEFAULT_SHEAR_MODULUS_SOURCE

    if not aspect_ratio or aspect_ratio <= 0 or static_pressure_pa <= 0:
        return None

    denom = (1.337 * aspect_ratio**3 * static_pressure_pa * (taper_ratio + 1.0)) / (2.0 * (aspect_ratio + 2.0) * thickness_ratio**3)
    if denom <= 0:
        return None
    v_f = speed_of_sound_ms * math.sqrt(g / denom)

    return FlutterResult(
        flutter_velocity_ms=v_f,
        source="hand formula (NACA TN 4197 approximation)" + (" - freeform fin approximated by its bounding trapezoid" if is_freeform else ""),
        aspect_ratio=aspect_ratio, taper_ratio=taper_ratio, thickness_ratio=thickness_ratio,
        shear_modulus_pa=g, shear_modulus_source=g_source,
        is_freeform_approximation=is_freeform, is_approximate=True,
    )


def worst_case_flutter(parsed, speed_of_sound_ms, static_pressure_pa, shear_modulus_pa=None, shear_modulus_source=None, manual_override_ms=None, manual_override_source=None):
    """The number the RCSM STR 6.3.2 check actually wants: the LOWEST
    (most conservative) flutter velocity across every fin set on the
    rocket, unless a manual override (a real external-tool result) was
    given, which always takes priority per this review's explicit
    instruction ("let me type a flutter velocity from an external tool...
    which then takes priority"). Returns None only if there are no fins
    to compute from AND no override - the caller then shows "not
    computed", never a fabricated number."""
    if manual_override_ms is not None:
        return FlutterResult(
            flutter_velocity_ms=manual_override_ms,
            source=f"manual override: {manual_override_source or 'external tool (source not labelled)'}",
            is_approximate=False,
        )
    if not parsed.fins:
        return None
    results = []
    for finset in parsed.fins:
        r = hand_calc_flutter_velocity(finset, speed_of_sound_ms, static_pressure_pa, shear_modulus_pa, shear_modulus_source, is_freeform=(finset.shape != "trapezoid"))
        if r is not None:
            results.append(r)
    if not results:
        return None
    return min(results, key=lambda r: r.flutter_velocity_ms)
