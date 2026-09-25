"""Pulls power-on (boost) and power-off (coast) axial drag curves out of the
Brasil OpenRocket export, in the headerless Mach,Cd format rocketpy's
Rocket(power_on_drag=..., power_off_drag=...) expects.

Boost = LIFTOFF..BURNOUT (motor thrusting), coast = BURNOUT..APOGEE. Both
filtered to |AoA| < 2 deg so we're only keeping points where OpenRocket's
axial-drag number is close to the zero-yaw Barrowman value, not contaminated
by the induced-drag component of a pitched-over rocket.

Run: python scripts/extract_drag_curves.py
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.prometeo.io_utils import load_openrocket_csv

SOURCE_CSV = os.path.join(config.DATA_DIR, "openrocket_exports", "Prometeo_Launchsite_BRASIL.csv")
OUT_DIR = os.path.join(config.DATA_DIR, "rockets")
AOA_LIMIT_DEG = 2.0
MACH_ROUND = 3  # bin width for de-duplication, ~1e-3 Mach resolution


def build_curve(df, t_lo, t_hi):
    mask = (df["Time (s)"] >= t_lo) & (df["Time (s)"] <= t_hi) & (df["Angle of attack (°)"].abs() < AOA_LIMIT_DEG)
    sub = df.loc[mask, ["Mach number (​)", "Axial drag coefficient (​)"]].dropna()
    sub = sub.rename(columns={"Mach number (​)": "mach", "Axial drag coefficient (​)": "cd"})
    # multiple time samples land in the same Mach bin (rocket spends a long
    # time near Mach 0 at apogee/liftoff) - average them instead of keeping
    # arbitrary duplicates, which is what "elimina duplicados" means here
    sub["mach_bin"] = sub["mach"].round(MACH_ROUND)
    curve = sub.groupby("mach_bin", as_index=False)["cd"].mean().rename(columns={"mach_bin": "mach"})
    return curve.sort_values("mach").reset_index(drop=True)


def main():
    df, events = load_openrocket_csv(SOURCE_CSV)
    os.makedirs(OUT_DIR, exist_ok=True)

    boost = build_curve(df, events["LIFTOFF"], events["BURNOUT"])
    coast = build_curve(df, events["BURNOUT"], events["APOGEE"])

    subsonic = coast[(coast["mach"] > 0.05) & (coast["mach"] < 0.45)]
    print(f"power_on_drag:  {len(boost)} points, mach range [{boost['mach'].min():.3f}, {boost['mach'].max():.3f}]")
    print(f"power_off_drag: {len(coast)} points, mach range [{coast['mach'].min():.3f}, {coast['mach'].max():.3f}]")
    print(f"Cd sanity check (coast, mach 0.05-0.45): min={subsonic['cd'].min():.3f} max={subsonic['cd'].max():.3f}")
    if not (0.3 <= subsonic["cd"].min() and subsonic["cd"].max() <= 0.7):
        raise RuntimeError(
            f"Cd out of the expected 0.3-0.7 sanity range "
            f"({subsonic['cd'].min():.3f}-{subsonic['cd'].max():.3f}) - stop and check the source data"
        )

    boost.to_csv(os.path.join(OUT_DIR, "power_on_drag.csv"), header=False, index=False)
    coast.to_csv(os.path.join(OUT_DIR, "power_off_drag.csv"), header=False, index=False)
    print(f"Wrote {OUT_DIR}\\power_on_drag.csv and power_off_drag.csv")


if __name__ == "__main__":
    main()
